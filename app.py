"""
FastSave Backend – app.py
Flask REST API server. Entry point for the backend.

Endpoints:
  POST /api/info       → fetch video metadata
  POST /api/video      → download video (MP4)
  POST /api/audio      → download audio (MP3)
  POST /api/thumbnail  → download thumbnail image
  GET  /health         → health check
"""

import os
import re
import logging
import mimetypes
from pathlib import Path
from urllib.parse import urlparse

from flask import Flask, request, jsonify, send_file, after_this_request, send_from_directory
from flask_cors import CORS

from config import (
    HOST, PORT, DEBUG,
    ALLOWED_ORIGINS,
    DOWNLOADS_DIR,
)
from downloader import (
    get_video_info,
    download_video,
    download_audio,
    download_thumbnail,
    detect_platform,
)

# ── Logging setup ────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("fastsave.app")

# ── Paths ────────────────────────────────────────────────────────
BASE_DIR     = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR.parent / "frontend"

# ── Flask app ────────────────────────────────────────────────────
# Serve static frontend files from the frontend/ folder
app = Flask(
    __name__,
    static_folder=str(FRONTEND_DIR),
    static_url_path="",
)

# CORS – allow ALL origins (including null from file://) for API routes
CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=False)


# ── Serve Frontend ───────────────────────────────────────────────
@app.route("/")
@app.route("/<path:filename>")
def serve_frontend(filename="index.html"):
    """Serve the frontend SPA from the frontend/ directory."""
    target = FRONTEND_DIR / filename
    if target.is_file():
        return send_from_directory(str(FRONTEND_DIR), filename)
    # Fallback → index.html for SPA routing
    return send_from_directory(str(FRONTEND_DIR), "index.html")


# ── Request validation helpers ───────────────────────────────────
def _get_url() -> tuple[str, None] | tuple[None, str]:
    """Extract and validate 'url' from JSON body. Returns (url, None) or (None, error_msg)."""
    body = request.get_json(silent=True) or {}
    url  = body.get("url", "").strip()
    if not url:
        return None, "Missing 'url' field in request body."
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return None, "URL must start with http:// or https://"
    except Exception:
        return None, "Invalid URL format."
    return url, None


def _error(msg: str, status: int = 400) -> tuple:
    logger.warning(f"API error [{status}]: {msg}")
    return jsonify({"error": msg}), status


def _sanitize_filename(name: str) -> str:
    """Make a string safe for Content-Disposition filename."""
    name = re.sub(r'[\\/*?:"<>|]', "_", name)
    name = name.strip(". ")
    return name[:128] or "fastsave_file"


# ── Routes ───────────────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok", "service": "FastSave API"}), 200


@app.route("/api/info", methods=["POST"])
def api_info():
    """
    Fetch video metadata (no download).
    Body: { "url": "..." }
    Response: { title, uploader, duration, thumbnail, platform, filesize }
    """
    url, err = _get_url()
    if err:
        return _error(err)

    logger.info(f"[INFO] {url}")
    try:
        info = get_video_info(url)
        return jsonify(info), 200
    except ValueError as e:
        return _error(str(e), 422)
    except Exception as e:
        logger.exception("Unexpected error in /api/info")
        return _error("Internal server error.", 500)


# ── Async Downloads & Progress Tracking ────────────────────────────
progress_store = {}

def _update_progress(d, task_id):
    if d['status'] == 'downloading':
        try:
            downloaded = d.get('downloaded_bytes', 0)
            total = d.get('total_bytes') or d.get('total_bytes_estimate') or 1
            percent = (downloaded / total) * 100
            progress_store[task_id]['percent'] = min(percent, 99.9)
        except Exception:
            pass
    elif d['status'] == 'finished':
        progress_store[task_id]['percent'] = 100
    elif d['status'] == 'error':
        progress_store[task_id]['status'] = 'error'
        progress_store[task_id]['error'] = 'yt-dlp encountered an error'

def _background_worker(task_id, dl_type, url, quality):
    try:
        def hook(d):
            _update_progress(d, task_id)
            
        if dl_type == 'mp4':
            file_path = download_video(url, quality=quality, progress_hook=hook)
        elif dl_type == 'mp3':
            file_path = download_audio(url, quality=quality, progress_hook=hook)
        elif dl_type == 'thumbnail':
            # Thumbnails download quickly without yt-dlp hooks
            file_path = download_thumbnail(url)
            progress_store[task_id]['percent'] = 100
        else:
            raise ValueError(f"Unknown type {dl_type}")

        progress_store[task_id]['status'] = 'completed'
        progress_store[task_id]['percent'] = 100
        progress_store[task_id]['file_path'] = file_path
    except Exception as e:
        logger.exception("Background download failed")
        progress_store[task_id]['status'] = 'error'
        progress_store[task_id]['error'] = str(e)


@app.route("/api/start-download", methods=["POST"])
def api_start_download():
    """
    Start download in background.
    Body: { "url": "...", "type": "mp4"|"mp3"|"thumbnail", "quality": "..." }
    """
    url, err = _get_url()
    if err:
        return _error(err)

    body = request.get_json(silent=True) or {}
    dl_type = body.get("type", "mp4")
    quality = str(body.get("quality", "1080"))

    import uuid, threading
    task_id = uuid.uuid4().hex
    progress_store[task_id] = {
        'status': 'downloading',
        'percent': 0,
        'file_path': None,
        'error': None,
        'type': dl_type
    }

    t = threading.Thread(target=_background_worker, args=(task_id, dl_type, url, quality))
    t.daemon = True
    t.start()

    return jsonify({"task_id": task_id}), 200


@app.route("/api/progress/<task_id>", methods=["GET"])
def api_progress(task_id):
    """Poll for progress."""
    state = progress_store.get(task_id)
    if not state:
        return _error("Task not found", 404)
    
    return jsonify({
        "status": state['status'],
        "percent": state['percent'],
        "error": state.get('error')
    }), 200


@app.route("/api/download-file/<task_id>", methods=["GET"])
def api_download_file(task_id):
    """Retrieve the completed file."""
    state = progress_store.get(task_id)
    if not state or state['status'] != 'completed':
        return _error("File not ready", 400)
        
    file_path = state['file_path']
    dl_type = state['type']
    
    if not file_path or not file_path.exists():
        return _error("File missing on disk", 500)

    # Determine safe name and mimetype
    ext = file_path.suffix.lower()
    safe_name_base = _sanitize_filename(file_path.stem)
    safe_name = f"{safe_name_base}{ext}"
    
    if dl_type == 'mp4':
        mimetype = "video/mp4"
    elif dl_type == 'mp3':
        mime_map = {".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".webm": "audio/webm", ".ogg": "audio/ogg", ".aac": "audio/aac"}
        mimetype = mime_map.get(ext, "audio/mpeg")
    else:
        mimetype = mimetypes.types_map.get(ext, "image/jpeg")
        safe_name = f"fastsave_thumbnail{ext}"

    # We do NOT unlink the file here immediately using @after_this_request
    # because some browsers will abort download if the file is unlinked too quickly.
    # The cleanup_old_files() chron-like job will handle it next time.
    # However, to save disk space if possible, we can try.
    @after_this_request
    def remove_file(response):
        try:
            # We delay removal slightly by not doing it here, or we trust cleanup job.
            # But let's keep the cleanup logic since users might download once.
            pass
        except Exception:
            pass
        return response

    return send_file(
        file_path,
        as_attachment=True,
        download_name=safe_name,
        mimetype=mimetype,
    )


# ── Error handlers ────────────────────────────────────────────────
@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Endpoint not found."}), 404


@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({"error": "Method not allowed."}), 405


@app.errorhandler(500)
def internal_error(e):
    return jsonify({"error": "Internal server error."}), 500


# ── Entry point ───────────────────────────────────────────────────
if __name__ == "__main__":
    logger.info(f"FastSave API starting → http://localhost:{PORT}")
    logger.info(f"Frontend served from  → {FRONTEND_DIR}")
    logger.info(f"Downloads dir         → {DOWNLOADS_DIR}")
    app.run(host=HOST, port=PORT, debug=DEBUG, threaded=True)
