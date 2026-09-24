"""
Lessons Router — content generation, narration, transcript, video.
"""
import uuid
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.db import get_db
from app.services import ai_service, storage_service

logger = logging.getLogger("smartlab.lessons")
router = APIRouter()


class GenerateLessonContentRequest(BaseModel):
    regenerate: bool = False


class GenerateNarrationRequest(BaseModel):
    slide_index: Optional[int] = None   # None = narrate all slides
    voice: str = "en-us-amy-low"


@router.get("/{lesson_id}")
async def get_lesson(lesson_id: str, db: AsyncSession = Depends(get_db)):
    row = await db.execute(text("SELECT * FROM lessons WHERE id=:id"), {"id": lesson_id})
    lesson = row.mappings().first()
    if not lesson:
        raise HTTPException(404, "Lesson not found")
    return dict(lesson)


@router.post("/{lesson_id}/generate-content")
async def generate_content(
    lesson_id: str,
    req: GenerateLessonContentRequest,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Generate full lesson content (HTML + slides) using AI."""
    lesson_row = await db.execute(text(
        "SELECT l.*, c.title as course_title, c.level, c.language FROM lessons l "
        "JOIN courses c ON l.course_id = c.id WHERE l.id=:id"
    ), {"id": lesson_id})
    lesson = lesson_row.mappings().first()
    if not lesson:
        raise HTTPException(404, "Lesson not found")

    if lesson["content_html"] and not req.regenerate:
        return {"message": "Lesson already has content. Use regenerate=true to overwrite.",
                "lesson_id": lesson_id}

    job_id = str(uuid.uuid4())
    await db.execute(text("""
        INSERT INTO ai_jobs (id, job_type, entity_type, entity_id, status, model_used)
        VALUES (:id, 'lesson_content', 'lesson', :entity_id, 'queued', 'qwen-fast')
    """), {"id": job_id, "entity_id": lesson_id})

    background.add_task(_generate_lesson_task, lesson_id, job_id, dict(lesson))
    return {"job_id": job_id, "lesson_id": lesson_id,
            "message": "Content generation started"}


async def _generate_lesson_task(lesson_id: str, job_id: str, lesson: dict):
    from app.db import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        try:
            await db.execute(text(
                "UPDATE ai_jobs SET status='running', progress=10 WHERE id=:id"
            ), {"id": job_id})
            await db.commit()

            content = await ai_service.generate_lesson_content(
                lesson_title=lesson["title"],
                objectives=[],          # TODO: load from modules.objectives JSON
                course_context=f"{lesson.get('course_title','')} ({lesson.get('level','')})",
                language=lesson.get("language", "en"),
            )

            await db.execute(text("""
                UPDATE lessons
                SET content_html=:html, slide_data=:slides, updated_at=NOW()
                WHERE id=:id
            """), {
                "id":     lesson_id,
                "html":   content.get("content_html", ""),
                "slides": str(content.get("slides", [])),
            })

            await db.execute(text(
                "UPDATE ai_jobs SET status='done', progress=100 WHERE id=:id"
            ), {"id": job_id})
            await db.commit()

        except Exception as e:
            logger.error(f"Lesson content generation failed: {e}")
            await db.execute(text(
                "UPDATE ai_jobs SET status='failed', error_message=:err WHERE id=:id"
            ), {"id": job_id, "err": str(e)})
            await db.commit()


@router.post("/{lesson_id}/narrate")
async def generate_narration(
    lesson_id: str,
    req: GenerateNarrationRequest,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Generate TTS narration for lesson slides."""
    lesson_row = await db.execute(text("SELECT * FROM lessons WHERE id=:id"), {"id": lesson_id})
    lesson = lesson_row.mappings().first()
    if not lesson:
        raise HTTPException(404, "Lesson not found")

    job_id = str(uuid.uuid4())
    await db.execute(text("""
        INSERT INTO ai_jobs (id, job_type, entity_type, entity_id, status, model_used)
        VALUES (:id, 'narration', 'lesson', :entity_id, 'queued', 'tts')
    """), {"id": job_id, "entity_id": lesson_id})

    background.add_task(
        _narrate_lesson_task, lesson_id, job_id, dict(lesson), req.voice
    )
    return {"job_id": job_id, "message": "Narration generation started"}


async def _narrate_lesson_task(lesson_id: str, job_id: str, lesson: dict, voice: str):
    from app.db import AsyncSessionLocal
    import json as _json
    async with AsyncSessionLocal() as db:
        try:
            await db.execute(text(
                "UPDATE ai_jobs SET status='running', progress=5 WHERE id=:id"
            ), {"id": job_id})
            await db.commit()

            slides = lesson.get("slide_data") or []
            if isinstance(slides, str):
                try:
                    slides = _json.loads(slides)
                except Exception:
                    slides = []

            narration_keys = []
            for i, slide in enumerate(slides):
                text_to_speak = slide.get("speaker_notes") or slide.get("body", "")
                if not text_to_speak:
                    continue
                audio_bytes = await ai_service.generate_narration(text_to_speak, voice)
                s3_key = storage_service.upload_narration(lesson_id, i + 1, audio_bytes)
                narration_keys.append(s3_key)

                progress = 5 + int(90 * (i + 1) / len(slides))
                await db.execute(text(
                    "UPDATE ai_jobs SET progress=:p WHERE id=:id"
                ), {"p": progress, "id": job_id})
                await db.commit()

            # Store first narration key as main lesson audio ref
            if narration_keys:
                await db.execute(text(
                    "UPDATE lessons SET narration_s3_key=:k, updated_at=NOW() WHERE id=:id"
                ), {"k": narration_keys[0], "id": lesson_id})

            await db.execute(text(
                "UPDATE ai_jobs SET status='done', progress=100 WHERE id=:id"
            ), {"id": job_id})
            await db.commit()

        except Exception as e:
            logger.error(f"Narration generation failed: {e}")
            await db.execute(text(
                "UPDATE ai_jobs SET status='failed', error_message=:err WHERE id=:id"
            ), {"id": job_id, "err": str(e)})
            await db.commit()


@router.post("/{lesson_id}/transcribe")
async def transcribe_lesson_video(
    lesson_id: str,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Transcribe lesson video via Whisper STT."""
    lesson_row = await db.execute(text("SELECT * FROM lessons WHERE id=:id"), {"id": lesson_id})
    lesson = lesson_row.mappings().first()
    if not lesson:
        raise HTTPException(404, "Lesson not found")
    if not lesson["video_s3_key"]:
        raise HTTPException(400, "Lesson has no video to transcribe")

    job_id = str(uuid.uuid4())
    await db.execute(text("""
        INSERT INTO ai_jobs (id, job_type, entity_type, entity_id, status, model_used)
        VALUES (:id, 'transcription', 'lesson', :entity_id, 'queued', 'whisper')
    """), {"id": job_id, "entity_id": lesson_id})

    background.add_task(_transcribe_task, lesson_id, job_id, lesson["video_s3_key"])
    return {"job_id": job_id, "message": "Transcription started"}


async def _transcribe_task(lesson_id: str, job_id: str, video_s3_key: str):
    from app.db import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        try:
            await db.execute(text(
                "UPDATE ai_jobs SET status='running', progress=10 WHERE id=:id"
            ), {"id": job_id})
            await db.commit()

            # Download video audio from SeaweedFS
            video_bytes = storage_service.download_bytes(
                storage_service.BUCKET_VIDEO, video_s3_key
            )

            await db.execute(text(
                "UPDATE ai_jobs SET progress=30 WHERE id=:id"
            ), {"id": job_id})
            await db.commit()

            # Transcribe
            transcript = await ai_service.transcribe_audio(
                video_bytes, filename="lesson.mp4"
            )

            # Generate VTT subtitles (basic timed version)
            vtt = _transcript_to_vtt(transcript)
            vtt_key = storage_service.upload_vtt(lesson_id, vtt)

            await db.execute(text("""
                UPDATE lessons
                SET transcript=:t, vtt_s3_key=:vk, updated_at=NOW()
                WHERE id=:id
            """), {"id": lesson_id, "t": transcript, "vk": vtt_key})

            await db.execute(text(
                "UPDATE ai_jobs SET status='done', progress=100 WHERE id=:id"
            ), {"id": job_id})
            await db.commit()

        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            await db.execute(text(
                "UPDATE ai_jobs SET status='failed', error_message=:err WHERE id=:id"
            ), {"id": job_id, "err": str(e)})
            await db.commit()


def _transcript_to_vtt(transcript: str) -> str:
    """Very basic VTT from transcript (words evenly distributed)."""
    lines = [l.strip() for l in transcript.split(".") if l.strip()]
    vtt = "WEBVTT\n\n"
    seconds = 0
    for i, line in enumerate(lines):
        start = _fmt_time(seconds)
        seconds += max(3, len(line.split()) // 2)
        end = _fmt_time(seconds)
        vtt += f"{i+1}\n{start} --> {end}\n{line}.\n\n"
    return vtt


def _fmt_time(s: int) -> str:
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{sec:02d}.000"
