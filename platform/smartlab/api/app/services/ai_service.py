"""
i3 SmartLab — AI Service
Calls LiteLLM gateway for all content generation tasks.
Models used:
  qwen-fast   → outlines, lesson text, quiz questions
  qwen-heavy  → deep rewrites, Bloom's alignment
  vision      → image analysis, slide captioning
  coder       → coding exercises
  embed       → semantic indexing
  granite-nano→ real-time AI tutor
  TTS         → narration audio
  STT         → transcription
"""
import os
import json
import httpx
import logging
from typing import Optional

logger = logging.getLogger("smartlab.ai")

LITELLM_BASE = os.environ["LITELLM_BASE_URL"]
LITELLM_KEY  = os.environ["LITELLM_API_KEY"]
STT_BASE     = os.environ["STT_BASE_URL"]
TTS_BASE     = os.environ["TTS_BASE_URL"]

HEADERS = {
    "Authorization": f"Bearer {LITELLM_KEY}",
    "Content-Type": "application/json",
}

# ── model aliases ──────────────────────────────────────────────────────────────
MODEL_FAST   = os.environ.get("MODEL_CONTENT", "qwen-fast")
MODEL_HEAVY  = os.environ.get("MODEL_ENRICH",  "qwen-heavy")
MODEL_VISION = os.environ.get("MODEL_VISION",  "vision")
MODEL_CODE   = os.environ.get("MODEL_CODE",    "coder")
MODEL_EMBED  = os.environ.get("MODEL_EMBED",   "embed")
MODEL_TUTOR  = os.environ.get("MODEL_TUTOR",   "granite-nano")

# ── helpers ────────────────────────────────────────────────────────────────────

async def _chat(model: str, messages: list, temperature: float = 0.7,
                max_tokens: int = 4096, timeout: int = 90) -> str:
    """Single call to LiteLLM /v1/chat/completions. Returns content string."""
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            f"{LITELLM_BASE}/v1/chat/completions",
            headers=HEADERS,
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


async def _embed(text: str) -> list[float]:
    """Embed text via LiteLLM /v1/embeddings."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{LITELLM_BASE}/v1/embeddings",
            headers=HEADERS,
            json={"model": MODEL_EMBED, "input": text},
        )
        resp.raise_for_status()
        return resp.json()["data"][0]["embedding"]


# ── Course generation ──────────────────────────────────────────────────────────

async def generate_course_outline(
    topic: str, level: str, duration_minutes: int,
    language: str = "en", num_modules: int = 5
) -> dict:
    """
    Returns:
    {
      "title": "...",
      "description": "...",
      "learning_outcomes": [...],
      "modules": [
        {
          "title": "...",
          "lessons": [
            {"title": "...", "objectives": [...], "duration_minutes": 10}
          ]
        }
      ]
    }
    """
    system = (
        "You are an expert instructional designer. "
        "Output ONLY valid JSON — no markdown, no prose, no code fences."
    )
    user = f"""
Design a {level}-level course on "{topic}" in {language}.
Target total duration: {duration_minutes} minutes.
Create {num_modules} modules, each with 2-4 lessons.
Every lesson must have Bloom's-aligned learning objectives.
Respond ONLY with this JSON structure:
{{
  "title": "string",
  "description": "string (2-3 sentences)",
  "learning_outcomes": ["string", ...],
  "modules": [
    {{
      "title": "string",
      "lessons": [
        {{
          "title": "string",
          "objectives": ["string", ...],
          "duration_minutes": number,
          "blooms_level": "remember|understand|apply|analyse|evaluate|create"
        }}
      ]
    }}
  ]
}}
"""
    raw = await _chat(MODEL_FAST, [
        {"role": "system", "content": system},
        {"role": "user",   "content": user},
    ], temperature=0.6, max_tokens=3000)

    # Strip any accidental markdown fences
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw)


async def generate_lesson_content(
    lesson_title: str, objectives: list[str],
    course_context: str, language: str = "en"
) -> dict:
    """
    Returns:
    {
      "content_html": "...",
      "slides": [{"title":"...","body":"...","speaker_notes":"..."}],
      "key_terms": ["term:definition", ...],
      "summary": "..."
    }
    """
    system = (
        "You are an expert educator. Create engaging, accurate lesson content. "
        "Output ONLY valid JSON — no markdown, no code fences."
    )
    objectives_str = "\n".join(f"- {o}" for o in objectives)
    user = f"""
Create full lesson content for: "{lesson_title}"
Course context: {course_context}
Learning objectives:
{objectives_str}
Language: {language}

Respond ONLY with this JSON:
{{
  "content_html": "<p>Full HTML lesson body (500-800 words)</p>",
  "slides": [
    {{
      "slide_number": 1,
      "title": "string",
      "body": "3-5 bullet points as plain text",
      "speaker_notes": "string (narrator script, 2-3 sentences)"
    }}
  ],
  "key_terms": ["term: definition"],
  "summary": "string (3-4 sentence summary)"
}}
Produce 6-8 slides covering the lesson objectives.
"""
    raw = await _chat(MODEL_FAST, [
        {"role": "system", "content": system},
        {"role": "user",   "content": user},
    ], temperature=0.65, max_tokens=4096)
    raw = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
    return json.loads(raw)


async def generate_quiz(
    lesson_title: str, content_summary: str,
    num_questions: int = 5, passing_score: int = 80
) -> dict:
    """
    Returns:
    {
      "title": "...",
      "questions": [
        {
          "question_text": "...",
          "question_type": "mcq",
          "options": [{"id":"a","text":"...","correct":true/false},...],
          "explanation": "...",
          "blooms_level": "..."
        }
      ]
    }
    """
    system = (
        "You are an assessment expert. Create fair, varied quiz questions. "
        "Output ONLY valid JSON — no markdown, no code fences."
    )
    user = f"""
Create a quiz for the lesson: "{lesson_title}"
Content summary: {content_summary}
Number of questions: {num_questions}
Include a mix of difficulty levels. Each question must have exactly 4 options,
one correct, with a clear explanation.

Respond ONLY with this JSON:
{{
  "title": "string",
  "questions": [
    {{
      "question_text": "string",
      "question_type": "mcq",
      "options": [
        {{"id": "a", "text": "string", "correct": false}},
        {{"id": "b", "text": "string", "correct": true}},
        {{"id": "c", "text": "string", "correct": false}},
        {{"id": "d", "text": "string", "correct": false}}
      ],
      "explanation": "string",
      "blooms_level": "remember|understand|apply|analyse|evaluate|create"
    }}
  ]
}}
"""
    raw = await _chat(MODEL_FAST, [
        {"role": "system", "content": system},
        {"role": "user",   "content": user},
    ], temperature=0.5, max_tokens=3000)
    raw = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
    return json.loads(raw)


async def enrich_book_chapter(
    chapter_title: str, raw_content: str,
    style: str = "educational", language: str = "en"
) -> dict:
    """
    Uses qwen-heavy to rewrite/enrich an uploaded document chapter.
    Returns: {"content_html": "...", "image_prompt": "...", "summary": "..."}
    """
    system = (
        "You are an expert educational book editor. "
        "Rewrite the provided content in an engaging, clear, accurate style. "
        "Output ONLY valid JSON."
    )
    user = f"""
Rewrite and enrich this chapter for a {style} book in {language}:
Chapter: "{chapter_title}"
Original content:
---
{raw_content[:4000]}
---
Respond ONLY with:
{{
  "content_html": "<full enriched HTML chapter>",
  "image_prompt": "A detailed image generation prompt for a chapter illustration",
  "summary": "2-3 sentence summary for table of contents"
}}
"""
    raw = await _chat(MODEL_HEAVY, [
        {"role": "system", "content": system},
        {"role": "user",   "content": user},
    ], temperature=0.6, max_tokens=4096, timeout=180)
    raw = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
    return json.loads(raw)


async def detect_video_chapters(transcript: str, video_duration_seconds: int) -> list[dict]:
    """
    Uses qwen-fast to split a transcript into logical chapters.
    Returns: [{"title":"...","start_seconds":0,"end_seconds":300,"summary":"..."}]
    """
    system = "You are a video editor. Identify logical chapter breaks in this transcript. Output ONLY valid JSON."
    user = f"""
Video duration: {video_duration_seconds} seconds
Transcript:
---
{transcript[:6000]}
---
Identify 4-8 logical chapters. Estimate timestamps proportionally from position in transcript.
Respond ONLY with a JSON array:
[
  {{"title": "string", "start_seconds": number, "end_seconds": number, "summary": "string"}}
]
"""
    raw = await _chat(MODEL_FAST, [
        {"role": "system", "content": system},
        {"role": "user",   "content": user},
    ], temperature=0.3, max_tokens=1500)
    raw = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
    return json.loads(raw)


async def ai_tutor_answer(
    question: str, course_context: str, lesson_context: str = ""
) -> str:
    """
    Real-time AI tutor using granite-nano for low latency.
    Returns plain text answer.
    """
    system = (
        "You are a helpful, concise tutor for the i3 SmartLab learning platform. "
        "Answer questions accurately using only the course context provided. "
        "Be encouraging and clear. Keep answers under 150 words."
    )
    user = f"""
Course context: {course_context[:800]}
Current lesson: {lesson_context[:400]}
Student question: {question}
"""
    return await _chat(MODEL_TUTOR, [
        {"role": "system", "content": system},
        {"role": "user",   "content": user},
    ], temperature=0.4, max_tokens=250, timeout=30)


async def analyse_image(image_url: str, context: str = "") -> dict:
    """
    Uses vision model to analyse an uploaded image/slide.
    Returns: {"description":"...", "alt_text":"...", "caption":"..."}
    """
    system = "You are an educational content analyst. Output ONLY valid JSON."
    user_content = [
        {"type": "text",      "text": f"Analyse this educational image. Context: {context}\nRespond with: {{\"description\":\"...\",\"alt_text\":\"...\",\"caption\":\"...\"}}"},
        {"type": "image_url", "image_url": {"url": image_url}},
    ]
    raw = await _chat(MODEL_VISION, [
        {"role": "user", "content": user_content}
    ], temperature=0.3, max_tokens=500, timeout=60)
    raw = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
    return json.loads(raw)


# ── Voice services ─────────────────────────────────────────────────────────────

async def transcribe_audio(audio_bytes: bytes, filename: str = "audio.mp3") -> str:
    """Send audio to Whisper STT. Returns plain text transcript."""
    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.post(
            f"{STT_BASE}/v1/audio/transcriptions",
            files={"file": (filename, audio_bytes, "audio/mpeg")},
            data={"model": "whisper-1", "response_format": "text"},
        )
        resp.raise_for_status()
        return resp.text.strip()


async def generate_narration(text: str, voice: str = "en-us-amy-low") -> bytes:
    """Send text to Piper TTS. Returns MP3 bytes."""
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{TTS_BASE}/v1/audio/speech",
            json={"model": "tts-1", "input": text, "voice": voice},
        )
        resp.raise_for_status()
        return resp.content


async def get_embedding(text: str) -> list[float]:
    """Get semantic embedding for content indexing."""
    return await _embed(text)
