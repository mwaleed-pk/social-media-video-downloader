<div align="center">

# ⚡ FastSave — Social Media Video Downloader

**Paste a link. Get your video.** Download videos, audio, and thumbnails from YouTube, TikTok, Instagram, and Facebook — with real-time progress, straight from your browser.

![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.1-000000?style=flat-square&logo=flask&logoColor=white)
![yt-dlp](https://img.shields.io/badge/yt--dlp-powered-FF0000?style=flat-square&logo=youtube&logoColor=white)
![Gunicorn](https://img.shields.io/badge/Gunicorn-499848?style=flat-square&logo=gunicorn&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)

</div>

---

## ✨ Features

- **Multi-platform downloads** — YouTube, TikTok, Instagram, and Facebook links with automatic platform detection
- **Metadata preview** — `POST /api/info` fetches title, uploader, duration, thumbnail, and platform before you download anything
- **Non-blocking downloads** — downloads run in background threads; the API returns a `task_id` instantly so the UI never freezes
- **Real-time progress** — poll `GET /api/progress/<task_id>` for live percentage updates, powered by yt-dlp progress hooks
- **Flexible quality** — MP4 at 1080p / 720p / 480p / best, plus MP3/M4A audio extraction at 128–320 kbps
- **Thumbnail grabber** — download the cover image of any supported video in one call
- **Works without ffmpeg** — smart format selection prefers pre-merged MP4 so it runs on minimal servers; ffmpeg is picked up automatically when present for even better merges
- **Self-cleaning storage** — downloaded files are purged automatically after a configurable retention window (`MAX_FILE_AGE`)
- **Platform-tuned requests** — per-platform HTTP headers (e.g. mobile UA for TikTok) for more reliable extraction
- **Production-ready serving** — ships with `gunicorn` config, `nginx.conf` reverse-proxy template with TLS, and a supervisor-style `fastsave.conf` process definition

## 🛠️ Tech Stack

| Layer      | Technology |
|------------|------------|
| Backend    | Python 3.12, Flask 3.1 |
| Extraction | yt-dlp |
| API/CORS   | Flask-CORS |
| Concurrency| Python threading (background workers + progress hooks) |
| WSGI       | Gunicorn |
| Reverse proxy | Nginx (TLS via Let's Encrypt) |
| Frontend   | Vanilla JS + HTML/CSS, Netlify-ready (`netlify.toml`) |

## 🏗️ Architecture / How It Works

```
Browser (frontend/) ──HTTPS──▶ Nginx ──proxy──▶ Gunicorn (4 workers) ──▶ Flask app
                                                                        │
                                    ┌─────────────── background thread ──┘
                                    ▼
                              yt-dlp extraction
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
              downloads/*.mp4  downloads/*.m4a  thumbnails
                                    │
                              progress_store (in-memory task registry)
                                    │
                              cleanup job purges files older than MAX_FILE_AGE
```

1. Client sends `{ "url": "..." }` to `/api/info` → instant metadata preview.
2. Client sends `{ "url", "type": "mp4"|"mp3"|"thumbnail", "quality" }` to `/api/start-download` → gets a `task_id` immediately.
3. A daemon thread runs yt-dlp with a progress hook that updates the task's percentage in `progress_store`.
4. Client polls `/api/progress/<task_id>` until `status: "completed"`.
5. Client fetches the file from `/api/download-file/<task_id>` with a sanitized filename and correct MIME type.

## 🚀 Getting Started

### Prerequisites

- Python 3.10+
- `pip`
- (Optional) `ffmpeg` for best-quality stream merging
- (Production) Nginx + a domain with TLS

### Installation

```bash
git clone https://github.com/mwaleed-pk/social-media-video-downloader.git
cd social-media-video-downloader
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | `0.0.0.0` | Bind host |
| `PORT` | `5000` | Bind port |
| `DEBUG` | `false` | Flask debug mode — keep `false` in production |
| `ALLOWED_ORIGINS` | `*` | Comma-separated CORS origins — **restrict this in production** |
| `MAX_FILE_AGE` | `600` | Seconds before downloaded files are auto-purged |
| `YTDLP_TIMEOUT` | `300` | yt-dlp operation timeout (seconds) |

### Run

**Development:**

```bash
python app.py
# → http://localhost:5000  (API + frontend served together)
```

**Production (Gunicorn):**

```bash
gunicorn -w 4 -b 0.0.0.0:5000 --timeout 300 app:app
```

**Behind Nginx:** use the provided `nginx.conf` as a starting template (TLS via certbot), pointing `/api/` and `/health` at the Gunicorn backend. `fastsave.conf` contains a ready supervisor-style process definition.

**Smoke test:**

```bash
python test_ytdlp.py   # verifies yt-dlp extraction works in this environment
```

## 📁 Project Structure

```
social-media-video-downloader/
├── app.py            # Flask API: info, async downloads, progress, file serving
├── downloader.py     # yt-dlp engine: platform detection, quality maps, downloads
├── config.py         # Centralized config (env-driven: host, CORS, quality maps, retention)
├── requirements.txt  # flask, flask-cors, yt-dlp, requests, gunicorn
├── nginx.conf        # Reverse-proxy + TLS template for production
├── fastsave.conf     # Supervisor-style process definition
├── test_ytdlp.py     # Extraction smoke test
└── frontend/
    ├── index.html    # Single-page UI
    ├── app.js        # Fetch → download → progress polling logic
    ├── style.css
    └── netlify.toml  # Static hosting config + security headers
```

## 🔌 API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET`  | `/health` | Health check → `{ "status": "ok" }` |
| `POST` | `/api/info` | Fetch video metadata. Body: `{ "url" }` |
| `POST` | `/api/start-download` | Start background download. Body: `{ "url", "type": "mp4"│"mp3"│"thumbnail", "quality" }` → `{ "task_id" }` |
| `GET`  | `/api/progress/<task_id>` | Poll download state → `{ "status", "percent", "error" }` |
| `GET`  | `/api/download-file/<task_id>` | Download the finished file as an attachment |

All error responses follow `{ "error": "<message>" }` with appropriate HTTP status codes (400 / 404 / 422 / 500).

## 🔒 Security Notes

- **CORS:** `ALLOWED_ORIGINS` defaults to `*` for development — set it to your exact frontend domain(s) in production.
- **Secrets:** all configuration is env-driven (`config.py`); never commit credentials or tokens.
- **Input validation:** URLs are scheme-checked (`http`/`https` only); download filenames are sanitized before `Content-Disposition`.
- **Disk hygiene:** the downloads directory is auto-purged on a retention window so abandoned files can't fill the disk.
- **Transport:** terminate TLS at Nginx (template included); never expose Gunicorn directly to the internet.
- **Legal:** only download content you have the right to. Respect each platform's Terms of Service.

## 🗺️ Roadmap

- [ ] WebSocket-based progress push (replace polling)
- [ ] Playlist / batch download support
- [ ] Persistent task store (Redis) for multi-worker deployments
- [ ] Rate limiting per IP
- [ ] Docker image + docker-compose (app + nginx)

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repo and create a feature branch (`git checkout -b feature/my-feature`)
2. Keep the no-ffmpeg-required philosophy intact for new download paths
3. Add/extend tests where it makes sense
4. Open a pull request with a clear description of the change

## 📄 License

MIT — see [LICENSE](LICENSE) for details.

## 👤 Author

**Muhammad Waleed (MW Trader)** — https://github.com/mwaleed-pk
