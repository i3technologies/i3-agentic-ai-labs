"""
Jobs Router — poll async AI job status.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.db import get_db

router = APIRouter()


@router.get("/{job_id}")
async def get_job(job_id: str, db: AsyncSession = Depends(get_db)):
    """Poll the status of an async AI/packaging job."""
    row = await db.execute(text("SELECT * FROM ai_jobs WHERE id=:id"), {"id": job_id})
    job = row.mappings().first()
    if not job:
        raise HTTPException(404, "Job not found")
    return dict(job)


@router.get("/entity/{entity_id}")
async def get_entity_jobs(entity_id: str, db: AsyncSession = Depends(get_db)):
    """Get all jobs for a given entity (course, lesson, book)."""
    rows = await db.execute(text("""
        SELECT * FROM ai_jobs WHERE entity_id=:id ORDER BY created_at DESC LIMIT 20
    """), {"id": entity_id})
    return {"jobs": [dict(r) for r in rows.mappings()]}
