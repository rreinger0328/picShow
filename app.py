from __future__ import annotations

import hashlib
import os
import secrets
from dataclasses import dataclass
from datetime import datetime
from hmac import compare_digest
from pathlib import Path

from flask import Flask, abort, redirect, render_template, request, send_from_directory, session, url_for


BASE_DIR = Path(__file__).resolve().parent

IMAGE_EXTENSIONS = {
    ".avif",
    ".bmp",
    ".gif",
    ".heic",
    ".heif",
    ".jfif",
    ".jpeg",
    ".jpg",
    ".png",
    ".svg",
    ".tif",
    ".tiff",
    ".webp",
}
BROWSER_IMAGE_EXTENSIONS = {
    ".avif",
    ".bmp",
    ".gif",
    ".jfif",
    ".jpeg",
    ".jpg",
    ".png",
    ".svg",
    ".webp",
}
VIDEO_EXTENSIONS = {
    ".m4v",
    ".mov",
    ".mp4",
}
VIDEO_EXTENSION_PRIORITY = {
    ".mov": 0,
    ".mp4": 1,
    ".m4v": 2,
}


@dataclass(frozen=True)
class MediaItem:
    id: str
    title: str
    folder: str
    image_rel: str
    video_rel: str | None
    extension: str
    browser_image: bool
    size: int
    modified_at: datetime

    @property
    def is_live(self) -> bool:
        return self.video_rel is not None


def create_app() -> Flask:
    app = Flask(__name__)

    app.config["MEDIA_ROOT"] = resolve_media_root()
    app.config["ACCESS_PASSWORD"] = os.environ.get("PICSHOW_PASSWORD", "picshow")
    app.secret_key = os.environ.get("PICSHOW_SECRET_KEY", secrets.token_hex(32))
    app.config["MEDIA_ROOT"].mkdir(parents=True, exist_ok=True)

    @app.before_request
    def require_login():
        if request.endpoint in {"login", "static"}:
            return None
        if session.get("authenticated"):
            return None
        return redirect(url_for("login", next=request.full_path))

    @app.template_filter("filesize")
    def filesize(value: int) -> str:
        units = ("B", "KB", "MB", "GB", "TB")
        size = float(value)
        for unit in units:
            if size < 1024 or unit == units[-1]:
                if unit == "B":
                    return f"{int(size)} {unit}"
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{value} B"

    @app.template_filter("datetime_local")
    def datetime_local(value: datetime) -> str:
        return value.strftime("%Y-%m-%d %H:%M")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        error = None
        if request.method == "POST":
            password = request.form.get("password", "")
            if compare_digest(password, app.config["ACCESS_PASSWORD"]):
                session.clear()
                session["authenticated"] = True
                return redirect(safe_next_url(request.form.get("next")) or url_for("index"))
            error = "密码不正确"

        return render_template(
            "login.html",
            error=error,
            next_url=safe_next_url(request.args.get("next")) or url_for("index"),
        )

    @app.post("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.route("/")
    def index():
        media_root = app.config["MEDIA_ROOT"]
        items = scan_media(media_root)
        counts = {
            "total": len(items),
            "live": sum(1 for item in items if item.is_live),
            "unsupported": sum(1 for item in items if not item.browser_image),
        }
        counts["photo"] = counts["total"] - counts["live"]

        return render_template(
            "index.html",
            counts=counts,
            items=items,
            media_root=media_root,
        )

    @app.route("/files/<path:relative_path>")
    def media_file(relative_path: str):
        media_root = app.config["MEDIA_ROOT"]
        target = (media_root / relative_path).resolve()
        if not is_relative_to(target, media_root) or not target.is_file():
            abort(404)
        return send_from_directory(media_root, relative_path, conditional=True)

    return app


def resolve_media_root() -> Path:
    configured = os.environ.get("PICSHOW_MEDIA_DIR", "media")
    media_root = Path(configured).expanduser()
    if not media_root.is_absolute():
        media_root = BASE_DIR / media_root
    return media_root.resolve()


def scan_media(media_root: Path) -> list[MediaItem]:
    if not media_root.exists():
        return []

    files = sorted(
        (path for path in media_root.rglob("*") if path.is_file()),
        key=lambda path: path.relative_to(media_root).as_posix().casefold(),
    )
    videos_by_key = index_live_videos(files)
    items: list[MediaItem] = []

    for image_path in files:
        extension = image_path.suffix.lower()
        if extension not in IMAGE_EXTENSIONS:
            continue

        relative_path = image_path.relative_to(media_root)
        video_path = videos_by_key.get(live_key(image_path))
        stat = image_path.stat()
        item_id = hashlib.sha1(relative_path.as_posix().encode("utf-8")).hexdigest()[:12]
        folder = relative_path.parent.as_posix()
        items.append(
            MediaItem(
                id=item_id,
                title=image_path.name,
                folder="" if folder == "." else folder,
                image_rel=relative_path.as_posix(),
                video_rel=video_path.relative_to(media_root).as_posix() if video_path else None,
                extension=extension.lstrip("."),
                browser_image=extension in BROWSER_IMAGE_EXTENSIONS,
                size=stat.st_size,
                modified_at=datetime.fromtimestamp(stat.st_mtime),
            )
        )

    items.sort(key=lambda item: item.modified_at, reverse=True)
    return items


def index_live_videos(files: list[Path]) -> dict[tuple[Path, str], Path]:
    candidates = [
        path
        for path in files
        if path.suffix.lower() in VIDEO_EXTENSIONS
    ]
    candidates.sort(
        key=lambda path: (
            path.parent.as_posix().casefold(),
            path.stem.casefold(),
            VIDEO_EXTENSION_PRIORITY.get(path.suffix.lower(), 99),
            path.name.casefold(),
        )
    )

    videos: dict[tuple[Path, str], Path] = {}
    for path in candidates:
        videos.setdefault(live_key(path), path)
    return videos


def live_key(path: Path) -> tuple[Path, str]:
    return path.parent, path.stem.casefold()


def is_relative_to(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
    except ValueError:
        return False
    return True


def safe_next_url(next_url: str | None) -> str | None:
    if not next_url or not next_url.startswith("/") or next_url.startswith("//"):
        return None
    return next_url


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
