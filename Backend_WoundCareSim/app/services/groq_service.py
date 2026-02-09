from __future__ import annotations

from io import BytesIO
from typing import Optional

import httpx

from app.core.config import GROQ_API_KEY


class GroqService:
    STT_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
    TTS_URL = "https://api.groq.com/openai/v1/audio/speech"
    STT_MODEL = "whisper-large-v3"
    TTS_MODEL = "distil-whisper-large-v3-en"
    TTS_VOICE = "alloy"

    @classmethod
    async def transcribe_audio(
        cls,
        filename: str,
        content: bytes,
        content_type: Optional[str] = None,
    ) -> str:
        if not GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY is not configured")

        headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
        files = {
            "file": (filename, content, content_type or "application/octet-stream"),
        }
        data = {"model": cls.STT_MODEL, "response_format": "json"}

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                cls.STT_URL,
                headers=headers,
                files=files,
                data=data,
            )

        response.raise_for_status()
        payload = response.json()
        text = payload.get("text")
        if not text:
            raise RuntimeError("Groq STT response missing text")
        return text

    @classmethod
    async def synthesize_speech(
        cls,
        text: str,
        model: Optional[str] = None,
        voice: Optional[str] = None,
    ) -> bytes:
        if not GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY is not configured")

        headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
        payload = {
            "model": model or cls.TTS_MODEL,
            "input": text,
            "voice": voice or cls.TTS_VOICE,
        }

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(cls.TTS_URL, headers=headers, json=payload)

        response.raise_for_status()
        return BytesIO(response.content).getvalue()
