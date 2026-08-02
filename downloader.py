"""
FastSave Backend – downloader.py
Core yt-dlp engine: video info, video download, audio extraction, thumbnail download.

IMPORTANT: All functions work WITHOUT ffmpeg installed.
  - Video: downloads best pre-merged mp4 format
  - Audio: downloads native m4a/webm (no conversion needed)
  - Thumbnail: downloaded via HTTP requests
  - FFmpeg is optional; if present, better quality merging is possible
"""

import os
import re
import time
import uuid
import shutil
import logging
import requests
from pathlib import Path
from urllib.parse import urlparse

import yt_dlp
import requests

from config import (
    DOWNLOADS_DIR,
    YTDLP_QUALITY_MAP,
    YTDLP_AUDIO_QUALITY_MAP,
    MAX_FILE_AGE_SECONDS,
)

logger = logging.getLogger("fastsave.downloader")

# Detect if ffmpeg is available once at startup
FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None
logger.info(f"FFmpeg available: {FFMPEG_AVAILABLE}")


# ── Platform detection ──────────────────────────────────────────
PLATFORM_PATTERNS = {
    "youtube":   [r"youtube\.com", r"youtu\.be"],
    "tiktok":    [r"tiktok\.com"],
    "facebook":  [r"facebook\.com", r"fb\.watch", r"fb\.com"],
    "instagram": [r"instagram\.com"],
}


def detect_platform(url: str) -> str:
    """Return the social platform name for a given URL, or 'unknown'."""
    url_lower = url.lower()
    for platform, patterns in PLATFORM_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, url_lower):
                return platform
    return "unknown"


# ── Platform-specific extra opts ─────────────────────────────────
def _platform_extra_opts(platform: str) -> dict:
    """Extra yt-dlp opts specific to each platform."""
    opts = {}
    if platform == "tiktok":
        opts["http_headers"] = {
            "User-Agent": (
                "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
            ),
        }
    if platform == "instagram":
        opts["http_headers"] = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
        }
    return opts


# ── Common yt-dlp base options ────────────────────────────────────
def _base_opts(quiet: bool = True) -> dict:
    return {
        "quiet":           quiet,
        "no_warnings":     quiet,
        "noplaylist":      True,
        "socket_timeout":  10,
        "retries":         0,
        "source_address":  "0.0.0.0",
        "noprogress":      True,
        "concurrent_fragment_downloads": 10, # Ultra fast fragment downloading
        "http_chunk_size": 10485760,         # 10MB chunk size for faster downloads
        # Prefer safe formats that don't need ffmpeg
        "prefer_free_formats": False,
    }


# ── Video format string (ffmpeg-aware) ───────────────────────────
def _video_format_string(quality: str) -> str:
    """
    Build a yt-dlp format string.
    If FFmpeg is available: prefer separate best video+audio (merged).
    If FFmpeg is NOT available: prefer pre-merged single-file mp4.
    """
    q = str(quality)
    h_map = {"1080": 1080, "720": 720, "480": 480, "best": None}
    h = h_map.get(q)
    height_filter = f"[height<={h}]" if h else ""

    if FFMPEG_AVAILABLE:
        # Best possible quality with merging
        return (
            f"bestvideo{height_filter}[ext=mp4]+bestaudio[ext=m4a]/"
            f"bestvideo{height_filter}[ext=mp4]+bestaudio/"
            f"best{height_filter}[ext=mp4]/"
            f"best{height_filter}/"
            "best"
        )
    else:
        # Pre-merged single-file formats (no ffmpeg needed)
        return (
            f"best{height_filter}[ext=mp4][acodec!=none][vcodec!=none]/"
            f"best{height_filter}[ext=mp4]/"
            f"best{height_filter}[acodec!=none][vcodec!=none]/"
            f"best{height_filter}/"
            "best"
        )


# ── Audio format string (ffmpeg-aware) ───────────────────────────
def _audio_format_string() -> str:
    """
    If FFmpeg available: download best audio for conversion to mp3.
    If not: download best native audio (m4a/webm) as-is.
    """
    if FFMPEG_AVAILABLE:
        return "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best"
    else:
        # Download native audio, no conversion
        return "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best"


# ── File cleanup ──────────────────────────────────────────────────
def cleanup_old_files() -> int:
    """Remove files older than MAX_FILE_AGE_SECONDS from downloads/. Returns count removed."""
    removed = 0
    now = time.time()
    try:
        for f in DOWNLOADS_DIR.iterdir():
            if f.is_file() and f.name != ".gitkeep":
                try:
                    if now - f.stat().st_mtime > MAX_FILE_AGE_SECONDS:
                        f.unlink()
                        removed += 1
                except OSError:
                    pass
    except Exception:
        pass
    return removed


# ── Video info ────────────────────────────────────────────────────
def get_video_info(url: str) -> dict:
    """
    Fetch metadata for a URL without downloading.
    Returns a dict with title, uploader, duration, thumbnail, platform, filesize.
    Raises ValueError on failure.
    """
    platform = detect_platform(url)
    
    # ── TikTok TikWM API Bypass ───────────────────────────────
    if platform == 'tiktok':
        r = requests.get("https://www.tikwm.com/api/", params={"url": url}, timeout=10)
        json_data = r.json()
        data = json_data.get("data")
        
        if data:
            title = data.get("title") or "TikTok Video"
            uploader = data.get("author", {}).get("nickname", "Unknown")
            is_slideshow = bool(data.get("images"))
            if is_slideshow:
                title = f"[Photo Slideshow] {title}"
            
            return {
                "title": title,
                "uploader": uploader,
                "duration": data.get("duration", 0),
                "thumbnail": data.get("cover", ""),
                "platform": "tiktok",
                "filesize": data.get("size", 0) or 0,
                "webpage_url": url,
                "_tikwm_play": data.get("play"),
                "_tikwm_music": data.get("music"),
                "_is_slideshow": is_slideshow
            }
        else:
            raise ValueError(f"TikWM Error: {json_data.get('msg', 'Unknown error')}")
            
    opts = {
        **_base_opts(quiet=True),
        **_platform_extra_opts(platform),
        "skip_download":  True,
        "writeinfojson":  False,
        "writethumbnail": False,
        # NOTE: Do NOT set 'format' here – it causes yt-dlp to validate
        # format availability even during metadata-only extraction,
        # which throws "Requested format is not available" errors.
    }

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)

        if not info:
            raise ValueError("Could not extract video information.")

        # Filesize estimate
        filesize = (
            info.get("filesize")
            or info.get("filesize_approx")
            or _best_format_size(info)
        )

        return {
            "title":       info.get("title", "Unknown Title"),
            "uploader":    info.get("uploader") or info.get("channel") or info.get("creator") or "",
            "duration":    info.get("duration"),            # seconds (int)
            "thumbnail":   _best_thumbnail(info),
            "platform":    platform,
            "filesize":    filesize,
            "webpage_url": info.get("webpage_url", url),
        }

    except yt_dlp.utils.DownloadError as e:
        raise ValueError(f"yt-dlp error: {_clean_error(str(e))}")
    except Exception as e:
        raise ValueError(f"Unexpected error: {str(e)}")


def _best_thumbnail(info: dict) -> str:
    """Return the highest-resolution thumbnail URL."""
    thumbnails = info.get("thumbnails") or []
    if thumbnails:
        filtered = [t for t in thumbnails if t.get("url")]
        if filtered:
            best = sorted(
                filtered,
                key=lambda t: (t.get("preference", 0), t.get("width", 0) or 0),
            )
            return best[-1].get("url", "")
    return info.get("thumbnail", "") or ""


def _best_format_size(info: dict) -> int:
    """Get filesize from the best available format."""
    formats = info.get("formats") or []
    # Try to find a complete format (has both audio and video)
    for f in reversed(formats):
        if f.get("vcodec") != "none" and f.get("acodec") != "none":
            sz = f.get("filesize") or f.get("filesize_approx") or 0
            if sz:
                return sz
    # Fallback: sum best available
    total = 0
    for f in formats[-3:]:  # last 3 (usually best quality)
        total += f.get("filesize") or f.get("filesize_approx") or 0
    return total


# ── Video download ────────────────────────────────────────────────
def download_video(url: str, quality: str = "1080", fmt: str = "mp4", progress_hook=None) -> Path:
    """
    Download video as MP4 (works with or without FFmpeg).
    Returns the Path to the downloaded file.
    Raises ValueError on failure.
    """
    cleanup_old_files()
    platform = detect_platform(url)
    uid = uuid.uuid4().hex[:12]
    output_template = str(DOWNLOADS_DIR / f"{uid}.%(ext)s")

    format_str = _video_format_string(quality)
    opts = {
        **_base_opts(quiet=True),
        **_platform_extra_opts(platform),
        "format": format_str,
        "outtmpl": output_template,
        "merge_output_format": "mp4",
    }
    
    # ── TikTok Custom Downloader for TikWM Fallback ────────────
    if platform == 'tiktok':
        # Try TikWM API first to bypass yt-dlp errors
        try:
            r = requests.get("https://www.tikwm.com/api/", params={"url": url}, timeout=10)
            data = r.json().get("data")
            if data and data.get("play") and not data.get("images"):
                play_url = data["play"]
                res = requests.get(play_url, stream=True, timeout=15)
                res.raise_for_status()
                
                final_path = Path(output_template.replace("%(ext)s", "mp4"))
                total_size = int(res.headers.get('content-length', 0))
                downloaded = 0
                
                with open(final_path, 'wb') as f:
                    for chunk in res.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if progress_hook and total_size > 0:
                                percent = (downloaded / total_size) * 100
                                progress_hook({
                                    "status": "downloading",
                                    "_percent_str": f"{percent:.1f}%",
                                    "filename": str(final_path)
                                })
                
                if progress_hook:
                    progress_hook({"status": "finished", "filename": str(final_path)})
                return final_path
            elif data and data.get("images"):
                raise ValueError("This TikTok is a Photo Slideshow. Please use the Audio format to download its sound, as slideshows cannot be downloaded as video.")
        except ValueError as ve:
            raise ve
        except Exception:
            pass # Fallback to yt-dlp

    if progress_hook:
        opts["progress_hooks"] = [progress_hook]

    # Only add merge/postprocess opts if FFmpeg is available
    if FFMPEG_AVAILABLE:
        opts["merge_output_format"] = "mp4"
        opts["postprocessors"] = [
            {
                "key":            "FFmpegVideoConvertor",
                "preferedformat": "mp4",
            }
        ]

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not info:
                raise ValueError("Download returned no information.")

        # Find the output file (any extension)
        final_file = _find_output_file(uid)
        if not final_file or not final_file.exists():
            raise ValueError("Downloaded file not found on disk.")

        sz_kb = final_file.stat().st_size // 1024
        logger.info(f"[VIDEO] Done: {final_file.name} ({sz_kb} KB)")
        return final_file

    except yt_dlp.utils.DownloadError as e:
        raise ValueError(f"Download failed: {_clean_error(str(e))}")
    except Exception as e:
        raise ValueError(f"Unexpected error during video download: {str(e)}")


# ── Audio download ────────────────────────────────────────────────
def download_audio(url: str, quality: str = "320", progress_hook=None) -> Path:
    """
    Download audio.
    With FFmpeg: converts to MP3 at specified bitrate.
    Without FFmpeg: downloads native audio (m4a/webm) as-is.
    Returns the Path to the audio file.
    Raises ValueError on failure.
    """
    cleanup_old_files()
    platform = detect_platform(url)
    uid = uuid.uuid4().hex[:12]
    output_template = str(DOWNLOADS_DIR / f"{uid}.%(ext)s")
    audio_q = YTDLP_AUDIO_QUALITY_MAP.get(str(quality), "320")

    opts = {
        **_base_opts(quiet=True),
        **_platform_extra_opts(platform),
        "format":  _audio_format_string(),
        "outtmpl": output_template,
    }
    
    # ── TikTok Custom Downloader for Audio ────────────
    if platform == 'tiktok':
        try:
            r = requests.get("https://www.tikwm.com/api/", params={"url": url}, timeout=10)
            data = r.json().get("data")
            if data and data.get("music"):
                music_url = data["music"]
                res = requests.get(music_url, stream=True, timeout=15)
                res.raise_for_status()
                
                final_path = Path(output_template.replace("%(ext)s", "mp3"))
                total_size = int(res.headers.get('content-length', 0))
                downloaded = 0
                
                with open(final_path, 'wb') as f:
                    for chunk in res.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if progress_hook and total_size > 0:
                                percent = (downloaded / total_size) * 100
                                progress_hook({
                                    "status": "downloading",
                                    "_percent_str": f"{percent:.1f}%",
                                    "filename": str(final_path)
                                })
                
                if progress_hook:
                    progress_hook({"status": "finished", "filename": str(final_path)})
                return final_path
        except Exception:
            pass # Fallback to yt-dlp
    if progress_hook:
        opts["progress_hooks"] = [progress_hook]

    if FFMPEG_AVAILABLE:
        # Convert to MP3 with ffmpeg
        opts["postprocessors"] = [
            {
                "key":              "FFmpegExtractAudio",
                "preferredcodec":   "mp3",
                "preferredquality": audio_q,
            },
            {"key": "FFmpegMetadata"},
        ]
        expected_ext = "mp3"
    else:
        # Download native audio (m4a / webm) — no conversion
        expected_ext = None   # accept any extension

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.extract_info(url, download=True)

        final_file = _find_output_file(uid, ext=expected_ext)
        if not final_file or not final_file.exists():
            raise ValueError("Audio file not found on disk.")

        sz_kb = final_file.stat().st_size // 1024
        logger.info(f"[AUDIO] Done: {final_file.name} ({sz_kb} KB)")
        return final_file

    except yt_dlp.utils.DownloadError as e:
        raise ValueError(f"Audio extraction failed: {_clean_error(str(e))}")
    except Exception as e:
        raise ValueError(f"Unexpected error during audio download: {str(e)}")


# ── Thumbnail download ────────────────────────────────────────────
def download_thumbnail(url: str) -> Path:
    """
    Download the best-quality thumbnail for a URL.
    Returns the Path to the JPEG file.
    Raises ValueError on failure.
    """
    cleanup_old_files()
    uid = uuid.uuid4().hex[:12]

    info = get_video_info(url)
    thumb_url = info.get("thumbnail")
    if not thumb_url:
        raise ValueError("No thumbnail found for this video.")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Referer": url,
    }

    try:
        r = requests.get(thumb_url, timeout=20, stream=True, headers=headers)
        r.raise_for_status()
        ext = _guess_image_ext(r.headers.get("Content-Type", ""))
        out_path = DOWNLOADS_DIR / f"{uid}{ext}"
        with open(out_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)

        sz_kb = out_path.stat().st_size // 1024
        logger.info(f"[THUMB] Done: {out_path.name} ({sz_kb} KB)")
        return out_path

    except requests.RequestException as e:
        raise ValueError(f"Thumbnail download failed: {str(e)}")


# ── Helpers ───────────────────────────────────────────────────────
def _find_output_file(uid: str, ext: str = None) -> Path | None:
    """Search DOWNLOADS_DIR for a file starting with uid and optional ext."""
    matches = []
    try:
        for f in DOWNLOADS_DIR.iterdir():
            if f.name.startswith(uid) and f.name != ".gitkeep":
                if ext is None or f.suffix.lower() == f".{ext}":
                    matches.append(f)
    except Exception:
        pass

    if not matches:
        return None
    # Return the largest file (most complete)
    return max(matches, key=lambda f: f.stat().st_size)


def _clean_error(msg: str) -> str:
    """Strip noisy yt-dlp prefixes from error messages."""
    msg = re.sub(r"ERROR:\s*", "", msg)
    msg = re.sub(r"\[.+?\]\s*", "", msg, count=1)
    return msg.strip()


def _guess_image_ext(content_type: str) -> str:
    ct = content_type.lower()
    if "png"  in ct: return ".png"
    if "webp" in ct: return ".webp"
    return ".jpg"
