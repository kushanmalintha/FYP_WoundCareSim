from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.services.groq_service import GroqService

router = APIRouter(prefix="/voice", tags=["Voice"])

ALLOWED_AUDIO_TYPES = {
    "audio/wav",
    "audio/x-wav",
    "audio/mpeg",
    "audio/mp3",
    "audio/webm",
    "audio/ogg",
}


class SynthesizeRequest(BaseModel):
    text: str
    model: str | None = None
    voice: str | None = None


@router.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    content_type = None
    if file.content_type:
        content_type = file.content_type.split(";", 1)[0].strip().lower()
    if content_type and content_type not in ALLOWED_AUDIO_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported audio format")

    try:
        content = await file.read()
        text = await GroqService.transcribe_audio(
            filename=file.filename or "audio",
            content=content,
            content_type=content_type or file.content_type,
        )
        return {"text": text}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/synthesize")
async def synthesize_audio(payload: SynthesizeRequest):
    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="Text is required")

    try:
        audio_bytes = await GroqService.synthesize_speech(
            text=payload.text,
            model=payload.model,
            voice=payload.voice,
        )
        return StreamingResponse(
            iter([audio_bytes]),
            media_type="audio/mpeg",
            headers={"Content-Disposition": "inline; filename=output.mp3"},
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
