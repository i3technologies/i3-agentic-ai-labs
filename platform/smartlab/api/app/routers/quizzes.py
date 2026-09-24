"""
Quizzes Router — quiz CRUD + AI generation.
"""
import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.db import get_db
from app.services import ai_service

logger = logging.getLogger("smartlab.quizzes")
router = APIRouter()


class GenerateQuizRequest(BaseModel):
    num_questions: int  = Field(5, ge=1, le=20)
    passing_score: int  = Field(80, ge=50, le=100)


@router.post("/lesson/{lesson_id}/generate")
async def generate_quiz_for_lesson(
    lesson_id: str,
    req: GenerateQuizRequest,
    db: AsyncSession = Depends(get_db),
):
    """AI-generate a quiz for a lesson (synchronous — returns quiz directly)."""
    lesson_row = await db.execute(text("SELECT * FROM lessons WHERE id=:id"), {"id": lesson_id})
    lesson = lesson_row.mappings().first()
    if not lesson:
        raise HTTPException(404, "Lesson not found")

    summary = lesson.get("content_html", "")[:1000] or lesson["title"]
    quiz_data = await ai_service.generate_quiz(
        lesson["title"], summary, req.num_questions, req.passing_score
    )

    # Save quiz + questions to DB
    quiz_id = str(uuid.uuid4())
    await db.execute(text("""
        INSERT INTO quizzes (id, lesson_id, title, passing_score, max_attempts)
        VALUES (:id, :lesson_id, :title, :score, 3)
    """), {
        "id":        quiz_id,
        "lesson_id": lesson_id,
        "title":     quiz_data.get("title", "Knowledge Check"),
        "score":     req.passing_score,
    })

    for i, q in enumerate(quiz_data.get("questions", [])):
        await db.execute(text("""
            INSERT INTO quiz_questions
              (id, quiz_id, question_text, question_type, options, explanation, blooms_level, position, ai_generated)
            VALUES
              (:id, :quiz_id, :qt, :qtype, :options, :expl, :blooms, :pos, TRUE)
        """), {
            "id":      str(uuid.uuid4()),
            "quiz_id": quiz_id,
            "qt":      q["question_text"],
            "qtype":   q.get("question_type", "mcq"),
            "options": str(q.get("options", [])),
            "expl":    q.get("explanation", ""),
            "blooms":  q.get("blooms_level", "understand"),
            "pos":     i,
        })

    await db.commit()
    return {"quiz_id": quiz_id, "quiz": quiz_data}


@router.get("/{quiz_id}")
async def get_quiz(quiz_id: str, db: AsyncSession = Depends(get_db)):
    quiz_row = await db.execute(text("SELECT * FROM quizzes WHERE id=:id"), {"id": quiz_id})
    quiz = quiz_row.mappings().first()
    if not quiz:
        raise HTTPException(404, "Quiz not found")
    questions_row = await db.execute(text(
        "SELECT * FROM quiz_questions WHERE quiz_id=:id ORDER BY position"
    ), {"id": quiz_id})
    result = dict(quiz)
    result["questions"] = [dict(q) for q in questions_row.mappings()]
    return result
