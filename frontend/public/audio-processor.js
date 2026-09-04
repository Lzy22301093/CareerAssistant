/**
 * PCM16 AudioWorklet 处理器
 *
 * 从麦克风接收 Float32 音频（16kHz），转换为 PCM16 Int16 并 base64 编码后
 * 通过 postMessage 发送回主线程。
 *
 * 参考 voice-chat 项目的实现。
 */

class Pcm16Processor extends AudioWorkletProcessor {
  constructor() {
    super()
    this._buffer = new Float32Array(0)
  }

  process(inputs) {
    const input = inputs[0]
    if (!input || !input[0]) return true

    const channelData = input[0] // Float32, mono

    // 追加到缓冲区
    const newBuffer = new Float32Array(this._buffer.length + channelData.length)
    newBuffer.set(this._buffer)
    newBuffer.set(channelData, this._buffer.length)
    this._buffer = newBuffer

    // 每 512 样本（~32ms @ 16kHz）发送一次
    while (this._buffer.length >= 512) {
      const chunk = this._buffer.slice(0, 512)
      this._buffer = this._buffer.slice(512)

      // Float32 → PCM16 Int16
      const pcm16 = new Int16Array(chunk.length)
      for (let i = 0; i < chunk.length; i++) {
        const s = chunk[i]
        pcm16[i] = s < 0 ? Math.max(-32768, s * 32768) : Math.min(32767, s * 32767)
      }

      // Int16 → base64（AudioWorklet 中无 btoa，手动编码）
      const bytes = new Uint8Array(pcm16.buffer)
      const CHARS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
      let base64 = ''
      for (let i = 0; i < bytes.length; i += 3) {
        const b0 = bytes[i]
        const b1 = i + 1 < bytes.length ? bytes[i + 1] : 0
        const b2 = i + 2 < bytes.length ? bytes[i + 2] : 0
        base64 += CHARS[b0 >> 2]
        base64 += CHARS[((b0 & 3) << 4) | (b1 >> 4)]
        base64 += i + 1 < bytes.length ? CHARS[((b1 & 15) << 2) | (b2 >> 6)] : '='
        base64 += i + 2 < bytes.length ? CHARS[b2 & 63] : '='
      }

      this.port.postMessage({ pcm16base64: base64 })
    }

    return true
  }
}

registerProcessor('pcm16-processor', Pcm16Processor)
