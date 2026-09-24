"""
AI Router — direct AI endpoints: quiz generation, tutor, image analysis.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from app.services import ai_service

router = APIRouter()


class QuizGenRequest(BaseModel):
    lesson_title:    str
    content_summary: str
    num_questions:   int = Field(5, ge=1, le=20)
    passing_score:   int = Field(80, ge=50, le=100)


class TutorRequest(BaseModel):
    question:       str
    course_context: str
    lesson_context: str = ""


class ImageAnalyseRequest(BaseModel):
    image_url:  str
    context:    str = ""


class NarrationRequest(BaseModel):
    text:  str = Field(..., max_length=5000)
    voice: str = "en-us-amy-low"


@router.post("/generate-quiz")
async def generate_quiz(req: QuizGenRequest):
    """Generate a quiz using AI (synchronous — for small quizzes)."""
    quiz = await ai_service.generate_quiz(
        req.lesson_title, req.content_summary,
        req.num_questions, req.passing_score
    )
    return quiz


@router.post("/tutor")
async def ai_tutor(req: TutorRequest):
    """Real-time AI tutor answer (granite-nano, <1s)."""
    answer = await ai_service.ai_tutor_answer(
        req.question, req.course_context, req.lesson_context
    )
    return {"answer": answer}


@router.post("/analyse-image")
async def analyse_image(req: ImageAnalyseRequest):
    """Analyse an uploaded image with the vision model."""
    result = await ai_service.analyse_image(req.image_url, req.context)
    return result


@router.post("/narrate")
async def narrate_text(req: NarrationRequest):
    """Generate TTS narration audio and return as base64."""
    import base64
    audio_bytes = await ai_service.generate_narration(req.text, req.voice)
    return {
        "audio_base64": base64.b64encode(audio_bytes).decode(),
        "content_type": "audio/mpeg",
        "size_bytes": len(audio_bytes),
    }
