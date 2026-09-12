"""Voice protocol + audio_utils 单元测试。"""

import base64
import json

from app.voice.audio_utils import pcm16_chunks_to_wav_b64, pcm16_to_wav, wav_b64_to_data_url
from app.voice.protocol import (
    ClientMsg,
    ClientMsgType,
    ServerMsg,
    ServerMsgType,
    encode_server_msg,
    parse_client_msg,
)


# ── Protocol Tests ──

def test_parse_client_audio():
    raw = json.dumps({"type": "audio", "data": "AAAA"})
    msg = parse_client_msg(raw)
    assert msg is not None
    assert msg.type == ClientMsgType.AUDIO
    assert msg.data == "AAAA"


def test_parse_client_end_of_speech():
    raw = json.dumps({"type": "end_of_speech"})
    msg = parse_client_msg(raw)
    assert msg is not None
    assert msg.type == ClientMsgType.END_OF_SPEECH


def test_parse_client_interrupt():
    raw = json.dumps({"type": "interrupt"})
    msg = parse_client_msg(raw)
    assert msg is not None
    assert msg.type == ClientMsgType.INTERRUPT


def test_parse_client_text():
    raw = json.dumps({"type": "text", "content": "你好"})
    msg = parse_client_msg(raw)
    assert msg is not None
    assert msg.type == ClientMsgType.TEXT
    assert msg.content == "你好"


def test_parse_client_ping():
    raw = json.dumps({"type": "ping"})
    msg = parse_client_msg(raw)
    assert msg is not None
    assert msg.type == ClientMsgType.PING


def test_parse_client_resume():
    raw = json.dumps({"type": "resume", "interview_id": "abc-123"})
    msg = parse_client_msg(raw)
    assert msg is not None
    assert msg.type == ClientMsgType.RESUME
    assert msg.interview_id == "abc-123"


def test_encode_server_started_with_interview_id():
    msg = ServerMsg(type=ServerMsgType.STARTED, interview_id="abc-123")
    obj = json.loads(encode_server_msg(msg))
    assert obj["type"] == "started"
    assert obj["interview_id"] == "abc-123"


def test_parse_invalid_json():
    assert parse_client_msg("not json") is None


def test_parse_unknown_type():
    assert parse_client_msg('{"type": "unknown"}') is None


def test_parse_missing_type():
    assert parse_client_msg('{"data": "x"}') is None


def test_encode_server_asr_final():
    msg = ServerMsg(type=ServerMsgType.ASR_FINAL, text="你好")
    encoded = encode_server_msg(msg)
    obj = json.loads(encoded)
    assert obj["type"] == "asr_final"
    assert obj["text"] == "你好"


def test_encode_server_done_with_report():
    report = {"overall_score": 8.0, "summary": "不错"}
    msg = ServerMsg(type=ServerMsgType.DONE, report=report)
    encoded = encode_server_msg(msg)
    obj = json.loads(encoded)
    assert obj["type"] == "done"
    assert obj["report"]["overall_score"] == 8.0


def test_encode_server_error():
    msg = ServerMsg(type=ServerMsgType.ERROR, message="出错了")
    encoded = encode_server_msg(msg)
    obj = json.loads(encoded)
    assert obj["type"] == "error"
    assert obj["message"] == "出错了"


# ── Audio Utils Tests ──

def test_pcm16_to_wav_header():
    pcm = b"\x00\x00" * 100  # 100 samples of silence
    wav = pcm16_to_wav(pcm, 16000)
    assert wav[:4] == b"RIFF"
    assert wav[8:12] == b"WAVE"
    assert wav[12:16] == b"fmt "
    # data chunk at offset 36
    assert wav[36:40] == b"data"


def test_pcm16_chunks_to_wav_b64():
    chunk1 = b"\x00\x00" * 50
    chunk2 = b"\xFF\x7F" * 50
    b64 = pcm16_chunks_to_wav_b64([chunk1, chunk2], 16000)
    decoded = base64.b64decode(b64)
    assert decoded[:4] == b"RIFF"
    # 100 samples * 2 bytes = 200 bytes PCM
    assert len(decoded) == 44 + 200  # WAV header + data


def test_wav_b64_to_data_url_prefix():
    b64 = base64.b64encode(b"test").decode()
    url = wav_b64_to_data_url(b64)
    assert url.startswith("data:audio/wav;base64,")


def test_wav_b64_to_data_url_already_prefixed():
    existing = "data:audio/wav;base64,dGVzdA=="
    assert wav_b64_to_data_url(existing) == existing
