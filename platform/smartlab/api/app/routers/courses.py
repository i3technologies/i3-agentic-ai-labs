"""
Courses Router — full CRUD + AI generation pipeline for courses.
"""
import uuid
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.db import get_db
from app.services import ai_service, scorm_packager, storage_service

logger = logging.getLogger("smartlab.courses")
router = APIRouter()


# ── Pydantic models ────────────────────────────────────────────────────────────

class CreateCourseRequest(BaseModel):
    title:            Optional[str] = None
    topic:            str           = Field(..., min_length=3, max_length=500)
    level:            str           = Field("beginner", pattern="^(beginner|intermediate|advanced|expert)$")
    duration_minutes: int           = Field(60, ge=10, le=480)
    language:         str           = Field("en", min_length=2, max_length=5)
    num_modules:      int           = Field(5, ge=1, le=20)
    scorm_version:    str           = Field("2004", pattern="^(1\\.2|2004)$")
    description:      Optional[str] = None
    tags:             list[str]     = []
    author_id:        str           = ""   # set from Keycloak token in production


class CourseResponse(BaseModel):
    id:              str
    title:           str
    status:          str
    scorm_version:   str
    job_id:          Optional[str] = None
    message:         str


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/", response_model=CourseResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_course(
    req: CreateCourseRequest,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new course and trigger AI outline generation.
    Returns immediately with a job_id — poll /api/v1/jobs/{job_id} for progress.
    """
    course_id = str(uuid.uuid4())
    job_id    = str(uuid.uuid4())

    # Insert course record (draft)
    await db.execute(text("""
        INSERT INTO courses (id, author_id, title, topic, level, language,
                             duration_minutes, status, scorm_version, tags, ai_generated)
        VALUES (:id, :author_id, :title, :topic, :level, :language,
                :duration, 'draft', :scorm_version, :tags, TRUE)
    """), {
        "id":           course_id,
        "author_id":    req.author_id or "00000000-0000-0000-0000-000000000000",
        "title":        req.title or req.topic,
        "topic":        req.topic,
        "level":        req.level,
        "language":     req.language,
        "duration":     req.duration_minutes,
        "scorm_version": req.scorm_version,
        "tags":         req.tags,
    })

    # Insert ai_job record
    await db.execute(text("""
        INSERT INTO ai_jobs (id, job_type, entity_type, entity_id, status, model_used)
        VALUES (:id, 'course_outline', 'course', :entity_id, 'queued', :model)
    """), {
        "id":        job_id,
        "entity_id": course_id,
        "model":     "qwen-fast",
    })

    # Schedule AI generation in background
    background.add_task(
        _generate_course_outline_task,
        course_id, job_id, req
    )

    return CourseResponse(
        id=course_id,
        title=req.title or req.topic,
        status="draft",
        scorm_version=req.scorm_version,
        job_id=job_id,
        message="Course creation started. Poll /api/v1/jobs/{job_id} for progress.",
    )


async def _generate_course_outline_task(
    course_id: str, job_id: str, req: CreateCourseRequest
):
    """
    Background task: calls AI to generate outline, then stores modules/lessons.
    """
    from app.db import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        try:
            # Mark job running
            await db.execute(text(
                "UPDATE ai_jobs SET status='running', updated_at=NOW() WHERE id=:id"
            ), {"id": job_id})
            await db.commit()

            # Call AI
            outline = await ai_service.generate_course_outline(
                topic=req.topic,
                level=req.level,
                duration_minutes=req.duration_minutes,
                language=req.language,
                num_modules=req.num_modules,
            )

            # Update course title + description from AI
            await db.execute(text("""
                UPDATE courses
                SET title=:title, description=:description, updated_at=NOW()
                WHERE id=:id
            """), {
                "id":          course_id,
                "title":       outline.get("title", req.topic),
                "description": outline.get("description", ""),
            })

            progress = 10
            modules = outline.get("modules", [])

            # Insert modules + lessons
            for mod_i, mod in enumerate(modules):
                mod_id = str(uuid.uuid4())
                await db.execute(text("""
                    INSERT INTO modules (id, course_id, title, description, position)
                    VALUES (:id, :course_id, :title, '', :position)
                """), {"id": mod_id, "course_id": course_id,
                       "title": mod["title"], "position": mod_i})

                for les_i, lesson in enumerate(mod.get("lessons", [])):
                    les_id = str(uuid.uuid4())
                    await db.execute(text("""
                        INSERT INTO lessons
                            (id, module_id, course_id, title, position, ai_generated)
                        VALUES
                            (:id, :module_id, :course_id, :title, :position, TRUE)
                    """), {
                        "id":        les_id,
                        "module_id": mod_id,
                        "course_id": course_id,
                        "title":     lesson["title"],
                        "position":  les_i,
                    })

                progress = 10 + int(80 * (mod_i + 1) / len(modules))
                await db.execute(text(
                    "UPDATE ai_jobs SET progress=:p, updated_at=NOW() WHERE id=:id"
                ), {"p": progress, "id": job_id})
                await db.commit()

            # Mark done
            await db.execute(text("""
                UPDATE ai_jobs
                SET status='done', progress=100, result_data=:rd, updated_at=NOW()
                WHERE id=:id
            """), {"id": job_id, "rd": str(outline)})
            await db.commit()
            logger.info(f"Course outline generated: {course_id}")

        except Exception as e:
            logger.error(f"Course outline generation failed: {e}")
            await db.execute(text("""
                UPDATE ai_jobs
                SET status='failed', error_message=:err, updated_at=NOW()
                WHERE id=:id
            """), {"id": job_id, "err": str(e)})
            await db.commit()


@router.get("/{course_id}")
async def get_course(course_id: str, db: AsyncSession = Depends(get_db)):
    """Get full course with modules and lessons."""
    course = await db.execute(text(
        "SELECT * FROM courses WHERE id=:id"
    ), {"id": course_id})
    row = course.mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Course not found")

    modules = await db.execute(text(
        "SELECT * FROM modules WHERE course_id=:id ORDER BY position"
    ), {"id": course_id})

    result = dict(row)
    result["modules"] = []
    for mod in modules.mappings():
        m = dict(mod)
        lessons = await db.execute(text(
            "SELECT * FROM lessons WHERE module_id=:mid ORDER BY position"
        ), {"mid": m["id"]})
        m["lessons"] = [dict(l) for l in lessons.mappings()]
        result["modules"].append(m)
    return result


@router.get("/")
async def list_courses(
    status: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    where = "WHERE status=:status" if status else ""
    rows = await db.execute(text(f"""
        SELECT id, title, status, level, language, scorm_version,
               duration_minutes, created_at, updated_at
        FROM courses {where}
        ORDER BY created_at DESC
        LIMIT :limit OFFSET :offset
    """), {"status": status, "limit": limit, "offset": offset})
    return {"courses": [dict(r) for r in rows.mappings()]}


@router.post("/{course_id}/package-scorm")
async def package_scorm(
    course_id: str,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Package the course as a SCORM ZIP and upload to SeaweedFS.
    Returns a job_id to track progress.
    """
    course_row = await db.execute(text(
        "SELECT * FROM courses WHERE id=:id"
    ), {"id": course_id})
    course = course_row.mappings().first()
    if not course:
        raise HTTPException(404, "Course not found")

    job_id = str(uuid.uuid4())
    await db.execute(text("""
        INSERT INTO ai_jobs (id, job_type, entity_type, entity_id, status)
        VALUES (:id, 'scorm_package', 'course', :entity_id, 'queued')
    """), {"id": job_id, "entity_id": course_id})

    background.add_task(_package_scorm_task, course_id, job_id, dict(course))
    return {"job_id": job_id, "message": "SCORM packaging started"}


async def _package_scorm_task(course_id: str, job_id: str, course: dict):
    from app.db import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        try:
            await db.execute(text(
                "UPDATE ai_jobs SET status='running', progress=5 WHERE id=:id"
            ), {"id": job_id})
            await db.commit()

            # Build full course data structure for packager
            modules_q = await db.execute(text(
                "SELECT * FROM modules WHERE course_id=:id ORDER BY position"
            ), {"id": course_id})
            modules = []
            for mod in modules_q.mappings():
                m = dict(mod)
                lessons_q = await db.execute(text(
                    "SELECT * FROM lessons WHERE module_id=:mid ORDER BY position"
                ), {"mid": m["id"]})
                m_lessons = []
                for les in lessons_q.mappings():
                    l = dict(les)
                    # Load slide data
                    l["slides"] = l.get("slide_data") or []
                    # Load quiz
                    quiz_q = await db.execute(text(
                        "SELECT * FROM quizzes WHERE lesson_id=:lid LIMIT 1"
                    ), {"lid": l["id"]})
                    quiz_row = quiz_q.mappings().first()
                    if quiz_row:
                        questions_q = await db.execute(text(
                            "SELECT * FROM quiz_questions WHERE quiz_id=:qid ORDER BY position"
                        ), {"qid": quiz_row["id"]})
                        quiz = dict(quiz_row)
                        quiz["questions"] = [dict(q) for q in questions_q.mappings()]
                        l["quiz"] = quiz
                    m_lessons.append(l)
                m["lessons"] = m_lessons
                modules.append(m)

            course_data = {
                "id":      course_id,
                "title":   course["title"],
                "modules": modules,
            }

            await db.execute(text(
                "UPDATE ai_jobs SET progress=40 WHERE id=:id"
            ), {"id": job_id})
            await db.commit()

            # Build SCORM ZIP
            zip_bytes = scorm_packager.build_scorm_package(
                course_data,
                scorm_version=course.get("scorm_version", "2004"),
            )

            await db.execute(text(
                "UPDATE ai_jobs SET progress=80 WHERE id=:id"
            ), {"id": job_id})
            await db.commit()

            # Upload to SeaweedFS
            s3_key = storage_service.upload_scorm_package(course_id, zip_bytes)

            # Update course record
            await db.execute(text(
                "UPDATE courses SET s3_scorm_key=:key, updated_at=NOW() WHERE id=:id"
            ), {"key": s3_key, "id": course_id})

            await db.execute(text(
                "UPDATE ai_jobs SET status='done', progress=100, result_data=:rd WHERE id=:id"
            ), {"id": job_id, "rd": f'{{"s3_key":"{s3_key}","size":{len(zip_bytes)}}}'})
            await db.commit()
            logger.info(f"SCORM packaged: {course_id} → {s3_key}")

        except Exception as e:
            logger.error(f"SCORM packaging failed: {e}")
            await db.execute(text(
                "UPDATE ai_jobs SET status='failed', error_message=:err WHERE id=:id"
            ), {"id": job_id, "err": str(e)})
            await db.commit()
