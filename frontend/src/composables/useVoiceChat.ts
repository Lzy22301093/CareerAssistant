/**
 * useVoiceChat — WebSocket 语音面试 composable
 *
 * 管理：WebSocket 连接、录音（AudioWorklet）、播放（AudioContext 24kHz）、打断
 */

import { reactive, onUnmounted } from 'vue'

// ── 类型 ──────────────────────────────────────────────────

export interface ChatLogEntry {
  role: 'user' | 'ai'
  text: string
}

export interface VoiceState {
  connected: boolean
  recording: boolean
  playing: boolean
  stage: 'idle' | 'listening' | 'thinking' | 'speaking' | 'done' | 'error'
  asrText: string
  currentQuestion: string
  chatLog: ChatLogEntry[]
  report: Record<string, unknown> | null
  errorMessage: string
}

export interface UseVoiceChatOptions {
  /** WebSocket URL，如 ws://localhost:8000/ws/interview */
  wsUrl: string
  /** 面试启动参数（首次连接时发送） */
  startPayload?: {
    jd_analysis: Record<string, unknown>
    profile: Record<string, unknown>
    referenced_questions?: string[]
    max_turns?: number
  }
  /** 面试 ID（重连时传入恢复） */
  interviewId?: string
}

// ── 常量 ──────────────────────────────────────────────────

const SAMPLE_RATE_INPUT = 16000
const SAMPLE_RATE_OUTPUT = 24000
const PING_INTERVAL = 5000
const PONG_TIMEOUT = 15000
const RECONNECT_BASE = 1000
const RECONNECT_MAX = 30000

// ── Composable ────────────────────────────────────────────

export function useVoiceChat(options: UseVoiceChatOptions) {
  const state = reactive<VoiceState>({
    connected: false,
    recording: false,
    playing: false,
    stage: 'idle',
    asrText: '',
    currentQuestion: '',
    chatLog: [],
    report: null,
    errorMessage: '',
  })

  // WebSocket
  let ws: WebSocket | null = null
  let pingTimer: ReturnType<typeof setInterval> | null = null
  let pongTimer: ReturnType<typeof setTimeout> | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let reconnectAttempt = 0

  // 录音
  let audioContext: AudioContext | null = null
  let mediaStream: MediaStream | null = null
  let workletNode: AudioWorkletNode | null = null

  // 播放
  let playContext: AudioContext | null = null
  let playNextTime = 0
  const playSources = new Set<AudioBufferSourceNode>()
  let audioChunkCount = 0
  let playbackStopped = false

  // ── WebSocket ──────────────────────────────────────────

  function connect() {
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return

    ws = new WebSocket(options.wsUrl)

    ws.onopen = () => {
      state.connected = true
      state.stage = 'idle'
      state.errorMessage = ''
      reconnectAttempt = 0
      startPing()

      // 发送面试启动参数
      if (options.startPayload) {
        send({
          type: 'start',
          ...options.startPayload,
        })
      } else if (options.interviewId) {
        send({ type: 'resume', interview_id: options.interviewId })
      }
    }

    ws.onmessage = (ev) => {
      if (typeof ev.data === 'string') {
        handleJsonMessage(JSON.parse(ev.data))
      } else if (ev.data instanceof Blob) {
        ev.data.arrayBuffer().then(handleAudioChunk)
      }
    }

    ws.onclose = () => {
      state.connected = false
      stopPing()
      scheduleReconnect()
    }

    ws.onerror = () => {
      state.errorMessage = '连接出错'
    }
  }

  function disconnect() {
    if (reconnectTimer) clearTimeout(reconnectTimer)
    reconnectTimer = null
    stopPing()
    stopRecording()
    if (ws) {
      ws.close()
      ws = null
    }
    state.connected = false
    state.stage = 'idle'
  }

  function send(obj: Record<string, unknown>) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(obj))
    }
  }

  // ── 消息处理 ──────────────────────────────────────────

  function handleJsonMessage(msg: Record<string, unknown>) {
    const type = msg.type as string

    switch (type) {
      case 'asr_final': {
        const text = (msg.text as string) || ''
        state.asrText = text
        if (text) {
          state.chatLog.push({ role: 'user', text })
        }
        break
      }

      case 'thinking':
        state.stage = 'thinking'
        // 为新一轮 AI 回答清空缓冲
        state.currentQuestion = ''
        break

      case 'llm_token':
        // 累积 token（interview 模式一次发全文，voice-chat 逐 token 发）
        state.currentQuestion += (msg.content as string) || ''
        break

      case 'tts_start':
        state.playing = true
        state.stage = 'speaking'
        playNextTime = 0
        audioChunkCount = 0
        playbackStopped = false
        break

      case 'tts_end': {
        state.playing = false
        // AI 回答已完整，推入对话日志
        const aiText = state.currentQuestion
        if (aiText) {
          state.chatLog.push({ role: 'ai', text: aiText })
        }
        // 浏览器 TTS 回退：如果没收到任何音频 chunk，用浏览器朗读
        if (audioChunkCount === 0 && aiText) {
          fallbackTTS(aiText)
        }
        state.currentQuestion = ''
        state.asrText = ''
        break
      }

      case 'interrupted':
        state.playing = false
        state.stage = 'listening'
        state.currentQuestion = ''
        state.asrText = ''
        stopPlayback()
        break

      case 'done':
        state.stage = 'done'
        state.report = (msg.report as Record<string, unknown>) || null
        stopRecording()
        break

      case 'error':
        state.errorMessage = (msg.message as string) || '未知错误'
        state.stage = 'error'
        break

      case 'pong':
        if (pongTimer) clearTimeout(pongTimer)
        pongTimer = null
        break
    }
  }

  function handleAudioChunk(buffer: ArrayBuffer) {
    if (playbackStopped) return
    if (!playContext) {
      playContext = new AudioContext({ sampleRate: SAMPLE_RATE_OUTPUT })
    }

    audioChunkCount++

    const int16 = new Int16Array(buffer)
    const float32 = new Float32Array(int16.length)
    for (let i = 0; i < int16.length; i++) {
      float32[i] = int16[i] / 32768.0
    }

    const audioBuffer = playContext.createBuffer(1, float32.length, SAMPLE_RATE_OUTPUT)
    audioBuffer.getChannelData(0).set(float32)

    const source = playContext.createBufferSource()
    source.buffer = audioBuffer
    source.connect(playContext.destination)

    const now = playContext.currentTime
    if (playNextTime < now) playNextTime = now
    source.start(playNextTime)
    playNextTime += audioBuffer.duration

    playSources.add(source)
    source.onended = () => playSources.delete(source)
  }

  function stopPlayback() {
    playbackStopped = true
    playSources.forEach((s) => {
      try { s.stop() } catch { /* ignore */ }
    })
    playSources.clear()
    playNextTime = 0
    // 同时取消浏览器 TTS 回退
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel()
    }
  }

  /** 浏览器 TTS 回退：服务端 TTS 不可用时用 Web Speech API 朗读 */
  function fallbackTTS(text: string) {
    if (!('speechSynthesis' in window) || !text) return
    window.speechSynthesis.cancel()
    const utterance = new SpeechSynthesisUtterance(text)
    utterance.lang = 'zh-CN'
    utterance.rate = 1.0
    utterance.onstart = () => {
      state.playing = true
      state.stage = 'speaking'
    }
    utterance.onend = () => {
      state.playing = false
    }
    utterance.onerror = () => {
      state.playing = false
    }
    window.speechSynthesis.speak(utterance)
  }

  // ── 录音 ──────────────────────────────────────────────

  async function startRecording() {
    if (state.recording) return

    try {
      // 恢复被浏览器挂起的 AudioContext（自动播放策略）
      if (playContext?.state === 'suspended') {
        await playContext.resume()
      }
      mediaStream = await navigator.mediaDevices.getUserMedia({ audio: { sampleRate: SAMPLE_RATE_INPUT, channelCount: 1 } })
      audioContext = new AudioContext({ sampleRate: SAMPLE_RATE_INPUT })

      await audioContext.audioWorklet.addModule('/audio-processor.js')
      const source = audioContext.createMediaStreamSource(mediaStream)

      workletNode = new AudioWorkletNode(audioContext, 'pcm16-processor')
      workletNode.port.onmessage = (ev) => {
        const { pcm16base64 } = ev.data as { pcm16base64: string }
        send({ type: 'audio', data: pcm16base64 })
      }

      source.connect(workletNode)
      workletNode.connect(audioContext.destination)

      state.recording = true
      state.stage = 'listening'
    } catch (err) {
      state.errorMessage = `录音启动失败: ${err}`
      state.stage = 'error'
    }
  }

  function stopRecording() {
    state.recording = false

    if (workletNode) {
      workletNode.disconnect()
      workletNode = null
    }
    if (audioContext) {
      audioContext.close()
      audioContext = null
    }
    if (mediaStream) {
      mediaStream.getTracks().forEach((t) => t.stop())
      mediaStream = null
    }
  }

  function endOfSpeech() {
    send({ type: 'end_of_speech' })
    state.stage = 'thinking'
  }

  function interrupt() {
    if (state.playing) {
      send({ type: 'interrupt' })
      stopPlayback()
      state.playing = false
      state.stage = 'listening'
    }
  }

  function sendText(text: string) {
    send({ type: 'text', content: text })
    state.stage = 'thinking'
  }

  // ── Ping/Pong ─────────────────────────────────────────

  function startPing() {
    stopPing()
    pingTimer = setInterval(() => {
      send({ type: 'ping' })
      pongTimer = setTimeout(() => {
        // pong 超时，断开重连
        ws?.close()
      }, PONG_TIMEOUT)
    }, PING_INTERVAL)
  }

  function stopPing() {
    if (pingTimer) clearInterval(pingTimer)
    pingTimer = null
    if (pongTimer) clearTimeout(pongTimer)
    pongTimer = null
  }

  // ── 重连 ──────────────────────────────────────────────

  function scheduleReconnect() {
    if (reconnectTimer) return
    const delay = Math.min(RECONNECT_BASE * Math.pow(2, reconnectAttempt), RECONNECT_MAX)
    reconnectAttempt++
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null
      connect()
    }, delay)
  }

  // ── 清理 ──────────────────────────────────────────────

  onUnmounted(() => {
    disconnect()
  })

  return {
    state,
    connect,
    disconnect,
    startRecording,
    stopRecording,
    endOfSpeech,
    interrupt,
    sendText,
  }
}
