"""
i3 SmartLab — Authoring API
FastAPI application entry point
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os
import logging

from app.routers import courses, lessons, quizzes, books, live, jobs, publish, ai
from app.db import engine, Base
from app.middleware import keycloak_auth

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("smartlab")

app = FastAPI(
    title="i3 SmartLab Authoring API",
    description="AI-powered SCORM, EPUB and OTT content authoring platform",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — allow Studio UI + Moodle webhook
origins = os.getenv("ALLOWED_ORIGINS", "https://author.i3technologies.co.ke").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(courses.router,  prefix="/api/v1/courses",  tags=["Courses"])
app.include_router(lessons.router,  prefix="/api/v1/lessons",  tags=["Lessons"])
app.include_router(quizzes.router,  prefix="/api/v1/quizzes",  tags=["Quizzes"])
app.include_router(books.router,    prefix="/api/v1/books",    tags=["Books"])
app.include_router(live.router,     prefix="/api/v1/live",     tags=["Live"])
app.include_router(jobs.router,     prefix="/api/v1/jobs",     tags=["Jobs"])
app.include_router(publish.router,  prefix="/api/v1/publish",  tags=["Publish"])
app.include_router(ai.router,       prefix="/api/v1/ai",       tags=["AI"])

@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok", "service": "i3-smartlab-api", "version": "1.0.0"}

@app.get("/", tags=["Health"])
async def root():
    return {"service": "i3 SmartLab Authoring API", "docs": "/docs"}
