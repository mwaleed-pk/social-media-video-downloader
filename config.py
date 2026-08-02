"""
FastSave Backend – config.py
Centralized configuration for the Flask application.
"""

import os
from pathlib import Path

# ── Base Paths ──────────────────────────────────────────────────
BASE_DIR       = Path(__file__).resolve().parent
DOWNLOADS_DIR  = BASE_DIR / "downloads"
DOWNLOADS_DIR.mkdir(exist_ok=True)

# ── Server ──────────────────────────────────────────────────────
HOST        = os.getenv("HOST", "0.0.0.0")
PORT        = int(os.getenv("PORT", 5000))
DEBUG       = os.getenv("DEBUG", "false").lower() == "true"

# ── CORS ────────────────────────────────────────────────────────
# Comma-separated list of allowed origins for CORS.
# Example: "https://mysite.netlify.app,https://fastsave.io"
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "*"   # <-- tighten in production
)

# ── yt-dlp defaults ─────────────────────────────────────────────
# Format strings: prefer pre-merged mp4 (works WITHOUT ffmpeg).
# Falls back progressively: pre-merged → ffmpeg-merged → best available.
YTDLP_QUALITY_MAP = {
    # 1080p: try pre-merged mp4 first, then merged with ffmpeg, then best
    "1080": (
        "bestvideo[height<=1080][ext=mp4][vcodec!*=av01]+bestaudio[ext=m4a]/"
        "bestvideo[height<=1080][ext=mp4]+bestaudio/"
        "best[height<=1080][ext=mp4]/"
        "best[height<=1080]/"
        "best"
    ),
    # 720p
    "720": (
        "bestvideo[height<=720][ext=mp4][vcodec!*=av01]+bestaudio[ext=m4a]/"
        "bestvideo[height<=720][ext=mp4]+bestaudio/"
        "best[height<=720][ext=mp4]/"
        "best[height<=720]/"
        "best"
    ),
    # 480p
    "480": (
        "bestvideo[height<=480][ext=mp4][vcodec!*=av01]+bestaudio[ext=m4a]/"
        "bestvideo[height<=480][ext=mp4]+bestaudio/"
        "best[height<=480][ext=mp4]/"
        "best[height<=480]/"
        "best"
    ),
    # Best quality
    "best": (
        "bestvideo[ext=mp4][vcodec!*=av01]+bestaudio[ext=m4a]/"
        "bestvideo[ext=mp4]+bestaudio/"
        "best[ext=mp4]/"
        "best"
    ),
}

YTDLP_AUDIO_QUALITY_MAP = {
    "320": "320",
    "192": "192",
    "128": "128",
}

# Max file retention in downloads/ (seconds). Files older than this are purged.
MAX_FILE_AGE_SECONDS = int(os.getenv("MAX_FILE_AGE", 600))   # 10 minutes

# Request timeout for yt-dlp operations (seconds)
YTDLP_TIMEOUT = int(os.getenv("YTDLP_TIMEOUT", 300))
