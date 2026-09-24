"""
Books Router — EPUB3 digital book creation pipeline.
"""
import uuid
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.db import get_db
from app.services import ai_service, storage_service, epub_builder

logger = logging.getLogger("smartlab.books")
router = APIRouter()


class CreateBookRequest(BaseModel):
    title:       str
    description: str = ""
    language:    str = "en"
    author_name: str = ""
    style:       str = "educational"
    author_id:   str = ""


@router.post("/")
async def create_book(req: CreateBookRequest, db: AsyncSession = Depends(get_db)):
    """Create a new book record (draft)."""
    book_id = str(uuid.uuid4())
    await db.execute(text("""
        INSERT INTO books (id, author_id, title, description, language, status)
        VALUES (:id, :author_id, :title, :desc, :lang, 'draft')
    """), {
        "id":        book_id,
        "author_id": req.author_id or "00000000-0000-0000-0000-000000000000",
        "title":     req.title,
        "desc":      req.description,
        "lang":      req.language,
    })
    await db.commit()
    return {"book_id": book_id, "status": "draft"}


@router.post("/{book_id}/upload-source")
async def upload_source_document(
    book_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload a DOCX/PDF/Markdown source document for a book."""
    book_row = await db.execute(text("SELECT * FROM books WHERE id=:id"), {"id": book_id})
    if not book_row.mappings().first():
        raise HTTPException(404, "Book not found")

    content = await file.read()
    s3_key = storage_service.upload_bytes(
        storage_service.BUCKET_CONTENT,
        f"books/{book_id}/source/{file.filename}",
        content,
        file.content_type or "application/octet-stream",
    )

    await db.execute(text(
        "UPDATE books SET source_s3_key=:k, updated_at=NOW() WHERE id=:id"
    ), {"k": s3_key, "id": book_id})
    await db.commit()
    return {"book_id": book_id, "source_s3_key": s3_key, "filename": file.filename}


@router.post("/{book_id}/enrich-chapters")
async def enrich_chapters(
    book_id: str,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """AI-enrich all chapters of a book using qwen-heavy."""
    book_row = await db.execute(text("SELECT * FROM books WHERE id=:id"), {"id": book_id})
    book = book_row.mappings().first()
    if not book:
        raise HTTPException(404, "Book not found")

    job_id = str(uuid.uuid4())
    await db.execute(text("""
        INSERT INTO ai_jobs (id, job_type, entity_type, entity_id, status, model_used)
        VALUES (:id, 'lesson_content', 'book', :entity_id, 'queued', 'qwen-heavy')
    """), {"id": job_id, "entity_id": book_id})

    background.add_task(_enrich_chapters_task, book_id, job_id, dict(book))
    return {"job_id": job_id, "message": "Chapter enrichment started"}


async def _enrich_chapters_task(book_id: str, job_id: str, book: dict):
    from app.db import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        try:
            await db.execute(text(
                "UPDATE ai_jobs SET status='running', progress=5 WHERE id=:id"
            ), {"id": job_id})
            await db.commit()

            chapters_q = await db.execute(text(
                "SELECT * FROM book_chapters WHERE book_id=:id ORDER BY position"
            ), {"id": book_id})
            chapters = list(chapters_q.mappings())

            for i, ch in enumerate(chapters):
                enriched = await ai_service.enrich_book_chapter(
                    chapter_title=ch["title"],
                    raw_content=ch.get("content_html", ch["title"]),
                    style=book.get("style", "educational"),
                    language=book.get("language", "en"),
                )
                await db.execute(text("""
                    UPDATE book_chapters
                    SET content_html=:html, updated_at=NOW()
                    WHERE id=:id
                """), {"id": ch["id"], "html": enriched.get("content_html", "")})

                progress = 5 + int(90 * (i + 1) / len(chapters))
                await db.execute(text(
                    "UPDATE ai_jobs SET progress=:p WHERE id=:id"
                ), {"p": progress, "id": job_id})
                await db.commit()

            await db.execute(text(
                "UPDATE ai_jobs SET status='done', progress=100 WHERE id=:id"
            ), {"id": job_id})
            await db.commit()

        except Exception as e:
            logger.error(f"Chapter enrichment failed: {e}")
            await db.execute(text(
                "UPDATE ai_jobs SET status='failed', error_message=:err WHERE id=:id"
            ), {"id": job_id, "err": str(e)})
            await db.commit()


@router.post("/{book_id}/build-epub")
async def build_epub(
    book_id: str,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Build the EPUB3 file from book chapters."""
    book_row = await db.execute(text("SELECT * FROM books WHERE id=:id"), {"id": book_id})
    book = book_row.mappings().first()
    if not book:
        raise HTTPException(404, "Book not found")

    job_id = str(uuid.uuid4())
    await db.execute(text("""
        INSERT INTO ai_jobs (id, job_type, entity_type, entity_id, status)
        VALUES (:id, 'epub_build', 'book', :entity_id, 'queued')
    """), {"id": job_id, "entity_id": book_id})

    background.add_task(_build_epub_task, book_id, job_id, dict(book))
    return {"job_id": job_id, "message": "EPUB build started"}


async def _build_epub_task(book_id: str, job_id: str, book: dict):
    from app.db import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        try:
            await db.execute(text(
                "UPDATE ai_jobs SET status='running', progress=20 WHERE id=:id"
            ), {"id": job_id})
            await db.commit()

            chapters_q = await db.execute(text(
                "SELECT * FROM book_chapters WHERE book_id=:id ORDER BY position"
            ), {"id": book_id})
            chapters = [dict(c) for c in chapters_q.mappings()]

            book_data = {
                "id":       book_id,
                "title":    book["title"],
                "author":   book.get("author", "i3 SmartLab"),
                "description": book.get("description", ""),
                "language": book.get("language", "en"),
                "publisher": book.get("publisher", "i3 Technologies"),
                "chapters": [
                    {
                        "title":       c["title"],
                        "content_html": c.get("content_html", ""),
                        "narration_url": (
                            f"{storage_service.S3_ENDPOINT}/"
                            f"{storage_service.BUCKET_CONTENT}/{c['narration_s3_key']}"
                            if c.get("narration_s3_key") else ""
                        ),
                    }
                    for c in chapters
                ],
            }

            await db.execute(text(
                "UPDATE ai_jobs SET progress=60 WHERE id=:id"
            ), {"id": job_id})
            await db.commit()

            epub_bytes = epub_builder.build_epub3(book_data)
            s3_key = storage_service.upload_epub(book_id, epub_bytes)

            await db.execute(text("""
                UPDATE books SET epub_s3_key=:k, updated_at=NOW() WHERE id=:id
            """), {"k": s3_key, "id": book_id})

            await db.execute(text(
                "UPDATE ai_jobs SET status='done', progress=100 WHERE id=:id"
            ), {"id": job_id})
            await db.commit()
            logger.info(f"EPUB built: {book_id} → {s3_key}")

        except Exception as e:
            logger.error(f"EPUB build failed: {e}")
            await db.execute(text(
                "UPDATE ai_jobs SET status='failed', error_message=:err WHERE id=:id"
            ), {"id": job_id, "err": str(e)})
            await db.commit()


@router.get("/{book_id}")
async def get_book(book_id: str, db: AsyncSession = Depends(get_db)):
    book_row = await db.execute(text("SELECT * FROM books WHERE id=:id"), {"id": book_id})
    book = book_row.mappings().first()
    if not book:
        raise HTTPException(404, "Book not found")
    chapters_q = await db.execute(text(
        "SELECT * FROM book_chapters WHERE book_id=:id ORDER BY position"
    ), {"id": book_id})
    result = dict(book)
    result["chapters"] = [dict(c) for c in chapters_q.mappings()]
    return result
