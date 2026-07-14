# PicShow

一个用于展示本地图片目录的 Flask 应用，支持常规图片展示，也支持 Apple Live Photo 常见的同名图片 + 同名视频组合。

## 功能

- 递归扫描图片目录。
- 支持 `.jpg`、`.jpeg`、`.png`、`.gif`、`.webp`、`.bmp`、`.svg`、`.avif` 等浏览器可直接展示的图片。
- 通过服务端缓存预览直接展示 `.heic`、`.heif`、`.tif`、`.tiff` 等格式。
- 使用 WebP 缩略图快速加载大量照片，点击图片可以打开大图预览。
- 自动匹配同目录、同文件名的 `.mov`、`.mp4`、`.m4v` 作为 Live Photo 视频。
- 支持文件名/文件夹搜索，以及全部、照片、实况、待转码筛选。

## Live Photo 文件结构

把 Apple Live Photo 的图片和视频放在同一个目录，并保持相同文件名：

```text
media/
  IMG_0001.HEIC
  IMG_0001.MOV
  trip/
    IMG_1002.JPG
    IMG_1002.MOV
```

应用会把这些文件识别为实况图片。HEIC/HEIF 原图会在服务端转成 WebP 预览用于网页展示，原图按钮仍下载原始静态图文件。

## 本地运行

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

默认图库目录是项目中的 `media/`。也可以指定任意目录：

```powershell
$env:PICSHOW_MEDIA_DIR="D:\Photos"
python app.py
```

默认访问密码是 `picshow`。可以通过环境变量修改：

```powershell
$env:PICSHOW_PASSWORD="your-password"
$env:PICSHOW_SECRET_KEY="replace-with-a-long-random-string"
python app.py
```

缩略图和大图预览会缓存在 `.picshow-cache/`。可以调整缓存目录和预览尺寸：

```powershell
$env:PICSHOW_CACHE_DIR=".picshow-cache"
$env:PICSHOW_THUMBNAIL_SIZE="640"
$env:PICSHOW_ZOOM_PREVIEW_SIZE="2200"
python app.py
```

打开 [http://localhost:5000](http://localhost:5000)。

## Docker

构建镜像：

```powershell
docker build -t picshow .
```

运行容器并挂载图片目录、缓存目录，同时设置访问密码：

```powershell
docker run --rm -p 5000:5000 -e PICSHOW_PASSWORD=your-password -v ${PWD}\media:/app/media:ro -v picshow-cache:/app/.picshow-cache picshow
```

指定其它图片目录：

```powershell
docker run --rm -p 5000:5000 -e PICSHOW_PASSWORD=your-password -v D:\Photos:/app/media:ro -v picshow-cache:/app/.picshow-cache picshow
```

## Docker Compose

使用 `ghcr.io/rreinger0328/picshow:latest` 镜像，默认将 `/vol1/1002/Photos/show` 映射到容器的 `/app/media`。

```powershell
docker compose up -d
```

可以复制 `.env.example` 为 `.env` 并修改其中的配置：

```powershell
cp .env.example .env
```

也可以直接在命令行设置环境变量：

```powershell
$env:PICSHOW_HOST_MEDIA_DIR="/vol1/1002/Photos/show"
$env:PICSHOW_PORT="5000"
$env:PICSHOW_PASSWORD="your-password"
$env:PICSHOW_SECRET_KEY="replace-with-a-long-random-string"
docker compose up -d
```

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `PICSHOW_MEDIA_DIR` | `media` | 图片扫描根目录（容器内为 `/app/media`） |
| `PICSHOW_PASSWORD` | `picshow` | 网页登录密码 |
| `PICSHOW_SECRET_KEY` | 随机生成 | Flask session 签名密钥，用于加密用户的登录会话 cookie。**如果不设置固定值，每次重启应用密钥都会变化，所有已登录用户将被强制退出。** 建议通过环境变量或 `.env` 文件设置一个固定的随机字符串。 |
| `PICSHOW_CACHE_DIR` | `.picshow-cache` | WebP 缩略图和大图预览缓存目录（容器内为 `/app/.picshow-cache`） |
| `PICSHOW_THUMBNAIL_SIZE` | `640` | 列表缩略图最长边尺寸 |
| `PICSHOW_ZOOM_PREVIEW_SIZE` | `2200` | 点击放大预览图最长边尺寸 |
| `PICSHOW_PORT` | `5000` | 应用监听端口（仅 Docker Compose） |
| `PICSHOW_HOST_MEDIA_DIR` | `/vol1/1002/Photos/show` | 宿主机图片目录（仅 Docker Compose） |

生成安全的 `PICSHOW_SECRET_KEY`：

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

## GitHub Actions

仓库包含 `.github/workflows/docker-image.yml`：

- `pull_request`：只构建镜像，不推送。
- `push` 到 `main` 或 `master`：构建并推送到 GitHub Container Registry。
- 推送 `v*.*.*` tag：构建并生成版本标签。
- `workflow_dispatch`：支持手动触发。

镜像地址格式：

```text
ghcr.io/<owner>/<repo>
```

workflow 使用 `GITHUB_TOKEN` 发布镜像，需要仓库 Actions 拥有 `packages: write` 权限。
