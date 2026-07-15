from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass
from datetime import datetime
from hmac import compare_digest
from pathlib import Path

from flask import Flask, abort, redirect, render_template, request, send_file, send_from_directory, session, url_for

try:
    from PIL import Image, ImageOps

    PIL_SUPPORT_AVAILABLE = True
except ImportError:
    Image = None
    ImageOps = None
    PIL_SUPPORT_AVAILABLE = False

try:
    from pillow_heif import register_heif_opener

    register_heif_opener()
    HEIF_SUPPORT_AVAILABLE = True
except ImportError:
    HEIF_SUPPORT_AVAILABLE = False


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
PREVIEW_IMAGE_EXTENSIONS = IMAGE_EXTENSIONS - {".svg"}
HEIF_IMAGE_EXTENSIONS = {".heic", ".heif"}
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
    previewable: bool
    size: int
    modified_at: datetime

    @property
    def is_live(self) -> bool:
        return self.video_rel is not None


def create_app() -> Flask:
    app = Flask(__name__)

    app.config["MEDIA_ROOT"] = resolve_media_root()
    app.config["CACHE_ROOT"] = resolve_cache_root()
    app.config["THUMBNAIL_SIZE"] = int_env("PICSHOW_THUMBNAIL_SIZE", 640)
    app.config["ZOOM_PREVIEW_SIZE"] = int_env("PICSHOW_ZOOM_PREVIEW_SIZE", 2200)
    app.config["ACCESS_PASSWORD"] = os.environ.get("PICSHOW_PASSWORD", "picshow")
    app.secret_key = os.environ.get("PICSHOW_SECRET_KEY", secrets.token_hex(32))
    app.config["MEDIA_ROOT"].mkdir(parents=True, exist_ok=True)
    app.config["CACHE_ROOT"].mkdir(parents=True, exist_ok=True)

    @app.before_request
    def require_login():
        if request.endpoint in {"login", "static"}:
            return None
        if request.endpoint == "download_file":
            relative_path = (request.view_args or {}).get("relative_path")
            if is_valid_download_token(
                app.config["MEDIA_ROOT"],
                relative_path,
                request.args.get("token", ""),
                app.secret_key,
            ):
                return None
        if session.get("authenticated"):
            return None
        return redirect(url_for("login", next=request.full_path))

    @app.context_processor
    def download_helpers():
        def download_url(relative_path: str) -> str:
            return url_for(
                "download_file",
                relative_path=relative_path,
                token=download_token(
                    app.config["MEDIA_ROOT"],
                    relative_path,
                    app.secret_key,
                ),
            )

        return {"download_url": download_url}

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
            "unsupported": sum(1 for item in items if not item.previewable and not item.browser_image),
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
        target = resolve_media_file(media_root, relative_path)
        if target is None:
            abort(404)
        return send_from_directory(media_root, relative_path, conditional=True)

    @app.route("/downloads/<path:relative_path>")
    def download_file(relative_path: str):
        media_root = app.config["MEDIA_ROOT"]
        target = resolve_media_file(media_root, relative_path)
        if target is None:
            abort(404)
        return send_file(
            target,
            as_attachment=True,
            download_name=target.name,
            conditional=True,
            max_age=0,
        )

    @app.route("/previews/<path:relative_path>")
    def preview_file(relative_path: str):
        media_root = app.config["MEDIA_ROOT"]
        target = resolve_media_file(media_root, relative_path)
        if target is None or target.suffix.lower() not in PREVIEW_IMAGE_EXTENSIONS:
            abort(404)
        if not can_generate_preview(target.suffix.lower()):
            abort(415)

        size_name = request.args.get("size", "thumb")
        max_size = app.config["ZOOM_PREVIEW_SIZE"] if size_name == "large" else app.config["THUMBNAIL_SIZE"]
        cache_path = preview_cache_path(
            app.config["CACHE_ROOT"],
            media_root,
            target,
            max_size,
        )
        if not cache_path.exists():
            generate_preview(target, cache_path, max_size)
        return send_file(cache_path, mimetype="image/webp", conditional=True, max_age=86400)

    return app


def resolve_media_root() -> Path:
    configured = os.environ.get("PICSHOW_MEDIA_DIR", "media")
    media_root = Path(configured).expanduser()
    if not media_root.is_absolute():
        media_root = BASE_DIR / media_root
    return media_root.resolve()


def resolve_cache_root() -> Path:
    configured = os.environ.get("PICSHOW_CACHE_DIR", ".picshow-cache")
    cache_root = Path(configured).expanduser()
    if not cache_root.is_absolute():
        cache_root = BASE_DIR / cache_root
    return cache_root.resolve()


def int_env(name: str, default: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError:
        return default
    return max(128, value)


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
                previewable=can_generate_preview(extension),
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


def resolve_media_file(media_root: Path, relative_path: str) -> Path | None:
    target = (media_root / relative_path).resolve()
    if not is_relative_to(target, media_root) or not target.is_file():
        return None
    return target


def download_token(media_root: Path, relative_path: str, secret_key: str) -> str:
    target = resolve_media_file(media_root, relative_path)
    if target is None:
        return ""
    return file_signature_token(media_root, target, secret_key)


def is_valid_download_token(media_root: Path, relative_path: str | None, token: str, secret_key: str) -> bool:
    if not relative_path or not token:
        return False
    target = resolve_media_file(media_root, relative_path)
    if target is None:
        return False
    expected = file_signature_token(media_root, target, secret_key)
    return compare_digest(token, expected)


def file_signature_token(media_root: Path, target: Path, secret_key: str) -> str:
    stat = target.stat()
    relative_path = target.relative_to(media_root).as_posix()
    message = f"{relative_path}:{stat.st_mtime_ns}:{stat.st_size}".encode("utf-8")
    return hmac.new(secret_key.encode("utf-8"), message, hashlib.sha256).hexdigest()


def can_generate_preview(extension: str) -> bool:
    if not PIL_SUPPORT_AVAILABLE or extension not in PREVIEW_IMAGE_EXTENSIONS:
        return False
    if extension in HEIF_IMAGE_EXTENSIONS and not HEIF_SUPPORT_AVAILABLE:
        return False
    return True


def preview_cache_path(cache_root: Path, media_root: Path, source: Path, max_size: int) -> Path:
    source_stat = source.stat()
    relative_path = source.relative_to(media_root).as_posix()
    cache_key = f"{relative_path}:{source_stat.st_mtime_ns}:{source_stat.st_size}:{max_size}"
    digest = hashlib.sha1(cache_key.encode("utf-8")).hexdigest()
    return cache_root / digest[:2] / f"{digest}.webp"


def generate_preview(source: Path, destination: Path, max_size: int) -> None:
    if Image is None or ImageOps is None:
        abort(415)

    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_destination = destination.with_name(f"{destination.stem}.{os.getpid()}.{secrets.token_hex(8)}.tmp")
    try:
        with Image.open(source) as image:
            image = ImageOps.exif_transpose(image)
            image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            if image.mode not in {"RGB", "L"}:
                image = image.convert("RGB")
            image.save(temp_destination, "WEBP", quality=82, method=4)
        os.replace(temp_destination, destination)
    except Exception:
        if temp_destination.exists():
            temp_destination.unlink()
        abort(415)


def safe_next_url(next_url: str | None) -> str | None:
    if not next_url or not next_url.startswith("/") or next_url.startswith("//"):
        return None
    return next_url


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
