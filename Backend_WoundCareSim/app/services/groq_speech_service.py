import base64
import logging
from typing import Optional

import httpx

from app.core.config import (
    GROQ_API_KEY,
    GROQ_BASE_URL,
    GROQ_STT_MODEL,
    GROQ_TTS_MODEL,
    GROQ_TTS_VOICE,
)

logger = logging.getLogger(__name__)


class GroqSpeechService:
    def __init__(
        self,
        api_key: str = GROQ_API_KEY,
        base_url: str = GROQ_BASE_URL,
        stt_model: str = GROQ_STT_MODEL,
        tts_model: str = GROQ_TTS_MODEL,
        tts_voice: str = GROQ_TTS_VOICE,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.stt_model = stt_model
        self.tts_model = tts_model
        self.tts_voice = tts_voice

    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def transcribe_audio(
        self,
        audio_bytes: bytes,
        filename: str,
        mime_type: str,
    ) -> str:
        if not self.is_configured():
            raise RuntimeError("Groq API key is not configured.")

        headers = {"Authorization": f"Bearer {self.api_key}"}
        data = {"model": self.stt_model}
        files = {"file": (filename, audio_bytes, mime_type)}

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/audio/transcriptions",
                headers=headers,
                data=data,
                files=files,
            )
            response.raise_for_status()

        payload = response.json()
        transcript = (payload.get("text") or "").strip()
        if not transcript:
            raise ValueError("Groq STT returned empty transcript.")
        return transcript

    async def synthesize_speech(
        self,
        text: str,
        response_format: str = "wav",
    ) -> Optional[dict]:
        if not text:
            return None
        if not self.is_configured():
            return None

        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {
            "model": self.tts_model,
            "voice": self.tts_voice,
            "input": text,
            "response_format": response_format,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/audio/speech",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()

        audio_base64 = base64.b64encode(response.content).decode("utf-8")
        return {
            "audio_base64": audio_base64,
            "audio_mime_type": f"audio/{response_format}",
        }
