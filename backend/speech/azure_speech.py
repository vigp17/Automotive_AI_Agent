"""Azure Speech Services STT/TTS wrappers plus mocks for MOCK_MODE."""

from __future__ import annotations

import asyncio
import io
import struct
import threading
import wave

import httpx

from app.config import get_settings


class MockSpeechClient:
    """Deterministic mock: fixed transcript, short silent WAV for TTS."""

    async def transcribe(self, audio: bytes, content_type: str = "audio/wav") -> str:
        return "What's my battery level?"

    async def synthesize(self, text: str) -> bytes:
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(16000)
            wav.writeframes(struct.pack("<h", 0) * 8000)  # 0.5 s silence
        return buffer.getvalue()


class LocalWhisperClient:
    """Real speech-to-text with no cloud keys: faster-whisper running locally.

    Used when Azure Speech is not configured. Decodes WebM/Opus, WAV, etc. via
    PyAV, so browser MediaRecorder uploads work directly. TTS returns empty
    audio; the frontend speaks replies with the browser's speechSynthesis.
    """

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._model = None
        self._lock = threading.Lock()

    def _get_model(self):
        with self._lock:
            if self._model is None:
                from faster_whisper import WhisperModel

                # Downloads (~145 MB for base.en) to the HuggingFace cache on
                # first use, then loads from disk.
                self._model = WhisperModel(self.model_name, compute_type="int8")
            return self._model

    def _transcribe_sync(self, audio: bytes) -> str:
        segments, _info = self._get_model().transcribe(io.BytesIO(audio), language="en")
        return " ".join(segment.text.strip() for segment in segments).strip()

    async def transcribe(self, audio: bytes, content_type: str = "audio/wav") -> str:
        return await asyncio.get_event_loop().run_in_executor(
            None, self._transcribe_sync, audio
        )

    async def synthesize(self, text: str) -> bytes:
        return b""


class AzureSpeechClient:
    """REST wrappers for Azure Speech short-form STT and TTS."""

    def __init__(self, key: str, region: str) -> None:
        self.key = key
        self.region = region

    async def transcribe(self, audio: bytes, content_type: str = "audio/wav") -> str:
        url = (
            f"https://{self.region}.stt.speech.microsoft.com/speech/recognition/"
            "conversation/cognitiveservices/v1"
        )
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                url,
                params={"language": "en-US"},
                headers={
                    "Ocp-Apim-Subscription-Key": self.key,
                    "Content-Type": content_type,
                },
                content=audio,
            )
            resp.raise_for_status()
            return resp.json().get("DisplayText", "")

    async def synthesize(self, text: str) -> bytes:
        url = f"https://{self.region}.tts.speech.microsoft.com/cognitiveservices/v1"
        ssml = (
            "<speak version='1.0' xml:lang='en-US'>"
            "<voice name='en-US-AvaMultilingualNeural'>"
            f"{text}</voice></speak>"
        )
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                url,
                headers={
                    "Ocp-Apim-Subscription-Key": self.key,
                    "Content-Type": "application/ssml+xml",
                    "X-Microsoft-OutputFormat": "riff-24khz-16bit-mono-pcm",
                },
                content=ssml.encode(),
            )
            resp.raise_for_status()
            return resp.content


_client: MockSpeechClient | AzureSpeechClient | LocalWhisperClient | None = None


def get_speech_client():
    global _client
    if _client is None:
        settings = get_settings()
        if not settings.mock_mode and settings.azure_speech_key:
            _client = AzureSpeechClient(settings.azure_speech_key, settings.azure_speech_region)
        elif settings.local_stt:
            _client = LocalWhisperClient(settings.whisper_model)
        else:
            _client = MockSpeechClient()
    return _client
