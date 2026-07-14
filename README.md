# PicShow

一个用于展示本地图片目录的 Flask 应用，支持常规图片展示，也支持 Apple Live Photo 常见的同名图片 + 同名视频组合。

## 功能

- 递归扫描图片目录。
- 支持 `.jpg`、`.jpeg`、`.png`、`.gif`、`.webp`、`.bmp`、`.svg`、`.avif` 等浏览器可直接展示的图片。
- 识别 `.heic`、`.heif`、`.tif`、`.tiff` 等图片并展示为待转码项目。
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

应用会把这些文件识别为实况图片。浏览器不能直接显示的 HEIC/HEIF 图片会优先显示配对视频。

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

打开 [http://localhost:5000](http://localhost:5000)。

## Docker

构建镜像：

```powershell
docker build -t picshow .
```

运行容器并挂载图片目录，同时设置访问密码：

```powershell
docker run --rm -p 5000:5000 -e PICSHOW_PASSWORD=your-password -v ${PWD}\media:/app/media picshow
```

指定其它图片目录：

```powershell
docker run --rm -p 5000:5000 -e PICSHOW_PASSWORD=your-password -v D:\Photos:/app/media picshow
```

## Docker Compose

默认把宿主机当前项目的 `./media` 映射到容器 `/app/media`：

```powershell
docker compose up -d --build
```

默认访问密码是 `picshow`。可以在启动前修改宿主机图片目录、端口和密码：

```powershell
$env:PICSHOW_HOST_MEDIA_DIR="D:\Photos"
$env:PICSHOW_PORT="5000"
$env:PICSHOW_PASSWORD="your-password"
$env:PICSHOW_SECRET_KEY="replace-with-a-long-random-string"
docker compose up -d --build
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
