# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```powershell
# Local development
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py                          # starts on http://localhost:5000

# Docker build (local)
docker build -t picshow .
docker run --rm -p 5000:5000 -v ${PWD}\media:/app/media picshow

# Docker Compose (pulls ghcr.io/rreinger0328/picshow:latest, does not build locally)
docker compose up -d
```

There is no test suite, no linter, and no type checker configured.

## Architecture

Single-module Flask app (`app.py`) — no blueprints, no ORM, no database. Everything is file-system driven. The app scans a media directory recursively, builds `MediaItem` dataclass instances, and renders them in a Jinja2 gallery.

```
app.py              ← Flask factory + routes + media scanning (~240 lines)
templates/
  index.html        ← gallery page: search, filter (all/photo/live/unsupported), logout
  login.html        ← password-only login form
static/
  css/app.css       ← single CSS file, no preprocessor (teal accent, light theme)
  js/gallery.js     ← vanilla JS: client-side filter/search, hover-to-play live photos, sound toggle
```

### Request flow

1. `before_request` hook checks `session["authenticated"]` on every request except `/login` and `/static/*` — redirects to login if not authenticated.
2. `GET /` calls `scan_media()` which walks `MEDIA_ROOT` recursively, pairs images with same-stem videos, and returns `MediaItem` list sorted by `modified_at` descending.
3. Gallery renders each item with `<img>` for browser-compatible images, `<video>` for live photo pairs, or an "unsupported" placeholder for HEIC/TIFF. All served as original files via `/files/<path>`.

### Live Photo matching

`live_key()` returns `(parent_dir, stem.lower())`. `scan_media()` indexes all videos by this key first, then for each image looks up whether a matching video exists. Video priority: `.mov` > `.mp4` > `.m4v`. Only the first video per key wins.

### Environment variables

| Variable | Role |
|---|---|
| `PICSHOW_MEDIA_DIR` | Media root path (defaults to `./media` relative to `app.py`) |
| `PICSHOW_PASSWORD` | Login password (default `picshow`), compared with `hmac.compare_digest` |
| `PICSHOW_SECRET_KEY` | Flask `secret_key` — signs session cookies. If unset, generates a random key per startup, invalidating all existing sessions. |
| `PORT` | Only used by the `__main__` block (5000). The Dockerfile uses gunicorn bound to `0.0.0.0:5000`. |

### Docker

- **Dockerfile**: `python:3.12-slim`, runs as non-root `appuser`, uses gunicorn with 2 workers / 4 threads.
- **docker-compose.yaml**: pulls `ghcr.io/rreinger0328/picshow:latest` (no local build), mounts `PICSHOW_HOST_MEDIA_DIR` (default `/vol1/1002/Photos/show`) into `/app/media`.
- **GitHub Actions**: on push to `main`/`master`, builds and pushes to GHCR with tags: `latest`, branch name, semver (for `v*` tags), and `sha-<hash>`.

### Key constraints

- No image thumbnailing or transcoding — the browser loads original files. HEIC/HEIF/TIFF have no browser preview and show as "unsupported."
- Authentication is a single shared password with no user management.
- All state is in Flask session cookies — no server-side sessions beyond the signed cookie.
