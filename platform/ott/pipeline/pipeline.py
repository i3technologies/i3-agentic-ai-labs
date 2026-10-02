#!/usr/bin/env python3
"""
OTT Automated Content Pipeline
Triggered by OvenMediaEngine stream-end webhook.
Steps:
  1. Receive stream-end event (stream name, recording path)
  2. FFmpeg ABR transcode to HLS segments  [async subprocess — no worker blocking]
  3. Whisper subtitle generation + SRT
  4. Upload segments + manifests to SeaweedFS S3
  5. Update Directus CMS metadata record
  6. POST completion callback so n8n can proceed immediately

Environment Variables:
  SEAWEEDFS_ENDPOINT     — e.g. http://seaweedfs-s3.i3-ott.svc.cluster.local:8333
  SEAWEEDFS_BUCKET       — e.g. i3-vod
  AWS_ACCESS_KEY_ID      — SeaweedFS HMAC key
  AWS_SECRET_ACCESS_KEY
  DIRECTUS_URL           — e.g. https://cms.i3technologies.co.ke
  DIRECTUS_TOKEN         — Static token from Directus / OpenBao
  WHISPER_MODEL          — base | small | medium (default: small)
  PIPELINE_WEBHOOK_SECRET— HMAC-SHA256 secret shared with OME webhook caller
  N8N_CALLBACK_URL       — Optional n8n webhook URL to call when pipeline completes
"""
import asyncio
import hashlib
import hmac
import json
import logging
import os
import tempfile
from pathlib import Path

import boto3
import httpx
from faster_whisper import WhisperModel
from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("ott-pipeline")

app = FastAPI(title="OTT Content Pipeline", version="1.1.0")

# ── Configuration ─────────────────────────────────────────────────────────────
SEAWEEDFS_ENDPOINT   = os.environ["SEAWEEDFS_ENDPOINT"]
SEAWEEDFS_BUCKET     = os.getenv("SEAWEEDFS_BUCKET", "i3-vod")
DIRECTUS_URL         = os.environ["DIRECTUS_URL"]
DIRECTUS_TOKEN       = os.environ["DIRECTUS_TOKEN"]
WHISPER_MODEL_SIZE   = os.getenv("WHISPER_MODEL", "small")
# Shared secret between OME webhook caller and this service (HC-5: gateway auth)
WEBHOOK_SECRET       = os.environ.get("PIPELINE_WEBHOOK_SECRET", "")
# Optional n8n callback URL called on pipeline completion (replaces hard-coded 5-min wait)
N8N_CALLBACK_URL     = os.environ.get("N8N_CALLBACK_URL", "")

# ABR ladder: (suffix, width, height, video_bitrate, audio_bitrate)
ABR_LADDER = [
    ("1080p", 1920, 1080, "4000k", "128k"),
    ("720p",  1280, 720,  "2000k", "128k"),
    ("480p",  854,  480,  "800k",  "96k"),
    ("240p",  426,  240,  "300k",  "64k"),
]

# Lazy-loaded faster-whisper model
_whisper_model = None

def get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        log.info(f"Loading faster-whisper model: {WHISPER_MODEL_SIZE}")
        _whisper_model = WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
    return _whisper_model


def s3_client():
    return boto3.client(
        "s3",
        endpoint_url=SEAWEEDFS_ENDPOINT,
        aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
        region_name="eu-de",
    )


# ── HMAC Webhook Signature Verification ─────────────────────────────────────
def verify_webhook_signature(body: bytes, signature: str | None) -> bool:
    """
    Validate X-OME-Signature header using HMAC-SHA256.
    Expected header format: "sha256=<hex-digest>"
    If PIPELINE_WEBHOOK_SECRET is not set (dev mode) verification is skipped.
    """
    if not WEBHOOK_SECRET:
        log.warning("PIPELINE_WEBHOOK_SECRET not set — webhook authentication disabled")
        return True
    if not signature:
        return False
    try:
        scheme, digest = signature.split("=", 1)
        if scheme != "sha256":
            return False
        expected = hmac.new(
            WEBHOOK_SECRET.encode("utf-8"), body, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, digest)
    except Exception:
        return False


# ── Step 1: FFmpeg ABR Transcode (async — no worker thread blocking) ─────────
async def transcode_abr(input_path: str, output_dir: Path, stream_name: str) -> Path:
    """
    Transcodes input recording to multi-rendition HLS using asyncio subprocess.
    Non-blocking: Uvicorn workers remain free during encode.
    Returns path to master playlist.
    """
    hls_dir = output_dir / "hls"
    hls_dir.mkdir(parents=True, exist_ok=True)

    ffmpeg_args = ["ffmpeg", "-y", "-i", input_path, "-threads", "0"]

    variant_playlists = []
    for suffix, w, h, vb, ab in ABR_LADDER:
        rendition_dir = hls_dir / suffix
        rendition_dir.mkdir(exist_ok=True)
        seg_pattern = str(rendition_dir / "seg%03d.ts")
        playlist    = str(rendition_dir / "playlist.m3u8")

        ffmpeg_args += [
            "-map", "0:v:0", "-map", "0:a:0",
            "-c:v", "libx264", "-preset", "fast", "-crf", "22",
            "-vf", f"scale={w}:{h}:flags=lanczos",
            "-b:v", vb, "-maxrate", vb, "-bufsize", f"{int(vb[:-1])*2}k",
            "-c:a", "aac", "-b:a", ab, "-ac", "2",
            "-hls_time", "6",
            "-hls_playlist_type", "vod",
            "-hls_segment_filename", seg_pattern,
            playlist,
        ]
        variant_playlists.append((suffix, playlist, vb))

    log.info(f"[{stream_name}] Transcoding → ABR HLS ({len(ABR_LADDER)} renditions) [async]")

    # Use asyncio subprocess — does NOT block the event loop
    proc = await asyncio.create_subprocess_exec(
        *ffmpeg_args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()

    if proc.returncode != 0:
        raise RuntimeError(f"FFmpeg failed (exit {proc.returncode}): {stderr.decode()[-2000:]}")

    # Generate master playlist
    master_path = hls_dir / "master.m3u8"
    with open(master_path, "w") as f:
        f.write("#EXTM3U\n#EXT-X-VERSION:3\n\n")
        bw_map  = {"1080p": 4128000, "720p": 2128000, "480p": 896000,  "240p": 364000}
        res_map = {"1080p": "1920x1080", "720p": "1280x720", "480p": "854x480", "240p": "426x240"}
        for suffix, _, _ in variant_playlists:
            rel = f"{suffix}/playlist.m3u8"
            f.write(
                f'#EXT-X-STREAM-INF:BANDWIDTH={bw_map[suffix]},'
                f'RESOLUTION={res_map[suffix]},'
                f'CODECS="avc1.42e01e,mp4a.40.2"\n{rel}\n\n'
            )

    log.info(f"[{stream_name}] Master playlist written: {master_path}")
    return master_path


# ── Step 2: Whisper Subtitle Generation ─────────────────────────────────────
async def generate_subtitles(input_path: str, output_dir: Path, stream_name: str) -> Path:
    """Run Whisper ASR in a thread pool executor to avoid blocking the event loop."""
    loop = asyncio.get_running_loop()

    def _run_whisper():
        model = get_whisper_model()
        log.info(f"[{stream_name}] Running faster-whisper ({WHISPER_MODEL_SIZE})")
        segments, info = model.transcribe(input_path, task="transcribe")
        return list(segments), info

    segments, info = await loop.run_in_executor(None, _run_whisper)

    def fmt_ts(t: float) -> str:
        h, r = divmod(int(t), 3600)
        m, s = divmod(r, 60)
        ms = int((t % 1) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    srt_path = output_dir / "subtitles.srt"
    with open(srt_path, "w", encoding="utf-8") as f:
        for i, segment in enumerate(segments, 1):
            f.write(
                f"{i}\n"
                f"{fmt_ts(segment.start)} --> {fmt_ts(segment.end)}\n"
                f"{segment.text.strip()}\n\n"
            )

    log.info(f"[{stream_name}] SRT generated ({len(segments)} segments)")
    return srt_path


# ── Step 3: Upload to SeaweedFS ───────────────────────────────────────────────
async def upload_to_seaweedfs(
    hls_dir: Path, stream_name: str, srt_path: Path
) -> dict[str, str]:
    """Upload all HLS segments + manifests + SRT to SeaweedFS (runs in thread pool)."""
    loop = asyncio.get_running_loop()

    def _upload():
        s3 = s3_client()
        uploaded: dict[str, str] = {}
        prefix = f"vod/{stream_name}"

        # Upload SRT
        srt_key = f"{prefix}/subtitles.srt"
        s3.upload_file(str(srt_path), SEAWEEDFS_BUCKET, srt_key,
                       ExtraArgs={"ContentType": "text/plain; charset=utf-8"})
        uploaded["srt"] = f"{SEAWEEDFS_ENDPOINT}/{SEAWEEDFS_BUCKET}/{srt_key}"

        # Upload all HLS files
        ct_map = {
            ".m3u8": "application/vnd.apple.mpegurl",
            ".ts":   "video/mp2t",
            ".m4s":  "video/iso.segment",
        }
        for f in sorted(hls_dir.rglob("*")):
            if f.is_file():
                rel = f.relative_to(hls_dir)
                key = f"{prefix}/hls/{rel}"
                ct  = ct_map.get(f.suffix, "application/octet-stream")
                s3.upload_file(str(f), SEAWEEDFS_BUCKET, key,
                               ExtraArgs={"ContentType": ct})
                if f.name == "master.m3u8":
                    uploaded["master_playlist"] = (
                        f"{SEAWEEDFS_ENDPOINT}/{SEAWEEDFS_BUCKET}/{key}"
                    )

        log.info(f"Uploaded {len(uploaded)} objects for stream '{stream_name}'")
        return uploaded

    return await loop.run_in_executor(None, _upload)


# ── Step 4: Update Directus CMS ──────────────────────────────────────────────
async def update_directus(stream_name: str, uploaded: dict[str, str], duration: float):
    """Create or update a VOD content record in Directus."""
    headers = {"Authorization": f"Bearer {DIRECTUS_TOKEN}"}
    payload = {
        "stream_name":     stream_name,
        "hls_master_url":  uploaded.get("master_playlist", ""),
        "subtitle_url":    uploaded.get("srt", ""),
        "duration_secs":   int(duration),
        "status":          "published",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{DIRECTUS_URL}/items/vod_recordings",
            params={"filter[stream_name][_eq]": stream_name},
            headers=headers,
        )
        data = resp.json().get("data", [])

        if data:
            record_id = data[0]["id"]
            await client.patch(
                f"{DIRECTUS_URL}/items/vod_recordings/{record_id}",
                json=payload,
                headers=headers,
            )
            log.info(f"Updated Directus record {record_id} for stream '{stream_name}'")
        else:
            await client.post(
                f"{DIRECTUS_URL}/items/vod_recordings",
                json=payload,
                headers=headers,
            )
            log.info(f"Created new Directus record for stream '{stream_name}'")


# ── Step 5: n8n Completion Callback ─────────────────────────────────────────
async def notify_n8n(stream_name: str, uploaded: dict[str, str], duration: float):
    """
    POST pipeline completion back to n8n so the workflow can proceed immediately
    instead of waiting a fixed 5 minutes.
    No-op if N8N_CALLBACK_URL is not configured.
    """
    if not N8N_CALLBACK_URL:
        return
    payload = {
        "status":           "pipeline_complete",
        "stream":           stream_name,
        "hls_master_url":   uploaded.get("master_playlist", ""),
        "subtitle_url":     uploaded.get("srt", ""),
        "duration_secs":    int(duration),
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(N8N_CALLBACK_URL, json=payload)
        log.info(f"[{stream_name}] n8n callback sent → {N8N_CALLBACK_URL}")
    except Exception as exc:
        log.warning(f"[{stream_name}] n8n callback failed (non-fatal): {exc}")


# ── Pipeline Orchestrator ─────────────────────────────────────────────────────
async def run_pipeline(stream_name: str, recording_path: str):
    """Full pipeline: transcode → subtitles → upload → CMS update → n8n callback."""
    log.info(f"[{stream_name}] Pipeline started. Input: {recording_path}")

    with tempfile.TemporaryDirectory(prefix=f"ott-{stream_name}-") as tmpdir:
        out = Path(tmpdir)

        # Step 1: Async transcode (non-blocking)
        await transcode_abr(recording_path, out, stream_name)

        # Step 2: Async Whisper (thread pool)
        srt_path = await generate_subtitles(recording_path, out, stream_name)

        # Step 3: Async S3 upload (thread pool)
        uploaded = await upload_to_seaweedfs(out / "hls", stream_name, srt_path)

        # Step 4: CMS — get duration via async ffprobe
        probe_proc = await asyncio.create_subprocess_exec(
            "ffprobe", "-v", "quiet", "-print_format", "json", "-show_format",
            recording_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        probe_stdout, _ = await probe_proc.communicate()
        duration = 0.0
        try:
            duration = float(json.loads(probe_stdout)["format"]["duration"])
        except Exception:
            pass

        await update_directus(stream_name, uploaded, duration)

        # Step 5: Callback to n8n (replaces hard-coded 5-min wait)
        await notify_n8n(stream_name, uploaded, duration)

    log.info(f"[{stream_name}] Pipeline complete. Duration: {duration:.1f}s")


# ── Webhook Endpoint ──────────────────────────────────────────────────────────
@app.post("/webhook/stream-end")
async def stream_end_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_ome_signature: str | None = Header(default=None, alias="X-OME-Signature"),
):
    """
    OvenMediaEngine webhook on stream end.
    Expected payload: {"stream": {"name": "..."}, "output_path": "/recordings/..."}
    Secured by HMAC-SHA256 via X-OME-Signature header.
    """
    body = await request.body()

    if not verify_webhook_signature(body, x_ome_signature):
        log.warning("Webhook signature verification failed — request rejected")
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    payload = json.loads(body)
    stream_name    = payload.get("stream", {}).get("name")
    recording_path = payload.get("output_path")

    if not stream_name or not recording_path:
        raise HTTPException(status_code=400, detail="Missing stream.name or output_path")

    background_tasks.add_task(run_pipeline, stream_name, recording_path)
    return {"status": "pipeline_queued", "stream": stream_name}


@app.get("/health")
async def health():
    return {"status": "ok", "service": "ott-pipeline", "version": "1.1.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8090, log_level="info")
