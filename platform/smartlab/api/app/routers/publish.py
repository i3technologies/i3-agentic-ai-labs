"""
Publish Router — publishes courses and books to i3EduBridge (Moodle) + VOD to OTT.
"""
import uuid
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.db import get_db
from app.services import moodle_service, storage_service

logger = logging.getLogger("smartlab.publish")
router = APIRouter()


class PublishCourseRequest(BaseModel):
    moodle_category_id: int  = 1
    moodle_section:     int  = 0
    visible:            bool = True


class PublishBookRequest(BaseModel):
    moodle_course_id:  Optional[int] = None
    moodle_section:    int = 0


@router.post("/course/{course_id}")
async def publish_course_to_moodle(
    course_id: str,
    req: PublishCourseRequest,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Publish a packaged SCORM course to i3EduBridge.
    The course must already be packaged (s3_scorm_key must be set).
    """
    course_row = await db.execute(text("SELECT * FROM courses WHERE id=:id"), {"id": course_id})
    course = course_row.mappings().first()
    if not course:
        raise HTTPException(404, "Course not found")
    if not course["s3_scorm_key"]:
        raise HTTPException(400, "Course not yet packaged. Call POST /courses/{id}/package-scorm first.")

    job_id = str(uuid.uuid4())
    await db.execute(text("""
        INSERT INTO ai_jobs (id, job_type, entity_type, entity_id, status)
        VALUES (:id, 'scorm_package', 'course', :entity_id, 'queued')
    """), {"id": job_id, "entity_id": course_id})

    background.add_task(
        _publish_course_task, course_id, job_id, dict(course), req
    )
    return {"job_id": job_id, "message": "Publishing to i3EduBridge started"}


async def _publish_course_task(
    course_id: str, job_id: str, course: dict, req: PublishCourseRequest
):
    from app.db import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        try:
            await db.execute(text(
                "UPDATE ai_jobs SET status='running', progress=10 WHERE id=:id"
            ), {"id": job_id})
            await db.commit()

            # Download SCORM ZIP from SeaweedFS
            zip_bytes = storage_service.download_bytes(
                storage_service.BUCKET_SCORM, course["s3_scorm_key"]
            )

            await db.execute(text(
                "UPDATE ai_jobs SET progress=30 WHERE id=:id"
            ), {"id": job_id})
            await db.commit()

            # Get or create Moodle course
            shortname = f"i3sl-{course_id[:8]}"
            moodle_course = await moodle_service.get_or_create_course(
                shortname=shortname,
                fullname=course["title"],
                category_id=req.moodle_category_id,
                summary=course.get("description", ""),
                visible=req.visible,
            )
            moodle_course_id = moodle_course["id"]

            await db.execute(text(
                "UPDATE ai_jobs SET progress=60 WHERE id=:id"
            ), {"id": job_id})
            await db.commit()

            # Upload SCORM activity
            activity = await moodle_service.upload_scorm_package(
                course_id=moodle_course_id,
                section_id=req.moodle_section,
                scorm_zip_bytes=zip_bytes,
                activity_name=course["title"],
                scorm_version=course.get("scorm_version", "2004"),
            )

            # Update course record
            await db.execute(text("""
                UPDATE courses
                SET moodle_course_id=:cid, moodle_module_id=:mid,
                    status='published', updated_at=NOW()
                WHERE id=:id
            """), {
                "id":  course_id,
                "cid": moodle_course_id,
                "mid": activity.get("id", 0),
            })

            await db.execute(text(
                "UPDATE ai_jobs SET status='done', progress=100 WHERE id=:id"
            ), {"id": job_id})
            await db.commit()

            logger.info(
                f"Course published: {course_id} → Moodle course {moodle_course_id}"
            )

        except Exception as e:
            logger.error(f"Course publish failed: {e}")
            await db.execute(text(
                "UPDATE ai_jobs SET status='failed', error_message=:err WHERE id=:id"
            ), {"id": job_id, "err": str(e)})
            await db.commit()


@router.post("/book/{book_id}")
async def publish_book_to_moodle(
    book_id: str,
    req: PublishBookRequest,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Publish an EPUB3 book to i3EduBridge as a file resource."""
    book_row = await db.execute(text("SELECT * FROM books WHERE id=:id"), {"id": book_id})
    book = book_row.mappings().first()
    if not book:
        raise HTTPException(404, "Book not found")
    if not book["epub_s3_key"]:
        raise HTTPException(400, "Book not yet built. Call POST /books/{id}/build-epub first.")

    job_id = str(uuid.uuid4())
    background.add_task(_publish_book_task, book_id, job_id, dict(book), req)
    return {"job_id": job_id, "message": "Book publish started"}


async def _publish_book_task(
    book_id: str, job_id: str, book: dict, req: PublishBookRequest
):
    from app.db import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        try:
            epub_bytes = storage_service.download_bytes(
                storage_service.BUCKET_EPUB, book["epub_s3_key"]
            )

            moodle_course_id = req.moodle_course_id
            if not moodle_course_id:
                # Create a new Moodle course for this book
                shortname = f"i3bk-{book_id[:8]}"
                moodle_course = await moodle_service.get_or_create_course(
                    shortname=shortname,
                    fullname=book["title"],
                    summary=book.get("description", ""),
                )
                moodle_course_id = moodle_course["id"]

            result = await moodle_service.upload_epub_resource(
                course_id=moodle_course_id,
                section_id=req.moodle_section,
                epub_bytes=epub_bytes,
                title=book["title"],
                description=book.get("description", ""),
            )

            await db.execute(text("""
                UPDATE books
                SET moodle_file_id=:fid, status='published', updated_at=NOW()
                WHERE id=:id
            """), {"id": book_id, "fid": result.get("id", 0)})
            await db.commit()
            logger.info(f"Book published: {book_id} → Moodle")

        except Exception as e:
            logger.error(f"Book publish failed: {e}")
