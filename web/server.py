import os
import sys
import uuid
import time
import json
import asyncio
import platform
import subprocess
import threading
import mimetypes
from typing import Dict, Any, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp

# ── RÉPERTOIRES & DÉTECTION FFMPEG ──────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IS_VERCEL = bool(os.environ.get("VERCEL"))

if IS_VERCEL:
    DOWNLOADS_DIR = "/tmp/downloads"
else:
    DOWNLOADS_DIR = os.path.join(BASE_DIR, "downloads")

STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

os.makedirs(DOWNLOADS_DIR, exist_ok=True)
try:
    os.makedirs(STATIC_DIR, exist_ok=True)
    os.makedirs(TEMPLATES_DIR, exist_ok=True)
except Exception:
    pass

# Recherche de ffmpeg.exe & ffprobe.exe
PARENT_DIR = os.path.abspath(os.path.join(BASE_DIR, ".."))
V5_DIR = os.path.join(PARENT_DIR, "v5")

FFMPEG_BIN = None
for candidate in (PARENT_DIR, V5_DIR, BASE_DIR):
    if os.path.exists(os.path.join(candidate, "ffmpeg.exe")) or os.path.exists(os.path.join(candidate, "ffmpeg")):
        FFMPEG_BIN = candidate
        break

if FFMPEG_BIN:
    if FFMPEG_BIN not in os.environ.get("PATH", ""):
        os.environ["PATH"] = FFMPEG_BIN + os.pathsep + os.environ.get("PATH", "")
    print(f"✅ FFmpeg détecté: {FFMPEG_BIN}")
else:
    print("⚠️ FFmpeg non trouvé dans les dossiers locaux, utilisation du PATH système.")

# Test accélération GPU NVIDIA NVENC
USE_NVENC = False
if FFMPEG_BIN:
    try:
        ffmpeg_exe = os.path.join(FFMPEG_BIN, "ffmpeg.exe" if platform.system() == "Windows" else "ffmpeg")
        chk_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if platform.system() == "Windows" else 0
        chk = subprocess.run(
            [ffmpeg_exe, "-f", "lavfi", "-i", "nullsrc=s=64x64:d=0.1", "-c:v", "h264_nvenc", "-f", "null", "-"],
            capture_output=True, timeout=2, creationflags=chk_flags
        )
        USE_NVENC = (chk.returncode == 0)
    except Exception:
        USE_NVENC = False

print(f"🚀 Accélération matérielle NVIDIA NVENC: {'ACTIVE' if USE_NVENC else 'INACTIVE (CPU VeryFast)'}")

# Registre des fichiers téléchargeables en mémoire: file_id -> { "path": ..., "name": ..., "time": ... }
DOWNLOAD_REGISTRY: Dict[str, Dict[str, Any]] = {}

# ── FASTAPI APP ─────────────────────────────────────────────────────────────
app = FastAPI(title="ViddRop Studio Web", version="3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Montage des fichiers statiques avec détection multi-chemins (Local & Vercel)
for sc in (STATIC_DIR, os.path.join(PARENT_DIR, "web", "static"), os.path.join(os.getcwd(), "web", "static")):
    if os.path.exists(sc):
        app.mount("/static", StaticFiles(directory=sc), name="static")
        break


# Nettoyage automatique des fichiers temporaires vieux de plus de 2 heures
def cleanup_old_files():
    while True:
        try:
            now = time.time()
            for fid, item in list(DOWNLOAD_REGISTRY.items()):
                if now - item.get("time", 0) > 7200:
                    p = item.get("path")
                    if p and os.path.exists(p):
                        try: os.remove(p)
                        except: pass
                    DOWNLOAD_REGISTRY.pop(fid, None)
            
            # Nettoyer aussi les fichiers orphelins dans downloads/
            for f in os.listdir(DOWNLOADS_DIR):
                fp = os.path.join(DOWNLOADS_DIR, f)
                if os.path.isfile(fp) and (now - os.path.getmtime(fp) > 7200):
                    try: os.remove(fp)
                    except: pass
        except Exception as e:
            print(f"⚠️ Erreur nettoyage: {e}")
        time.sleep(600)

threading.Thread(target=cleanup_old_files, daemon=True).start()


# Middleware pour corriger les chemins réécrits par Vercel Serverless
@app.middleware("http")
async def fix_vercel_paths(request, call_next):
    path = request.url.path
    # Vercel rewrites root to /api/index.py or /api
    if path in ("/api/index.py", "/api/index", "/api", "/api/"):
        request.scope["path"] = "/"
    elif path.startswith("/api/static/"):
        request.scope["path"] = path[4:]  # devienne /static/...
    elif path.startswith("/api/api/"):
        request.scope["path"] = path[4:]  # devienne /api/...
    return await call_next(request)


@app.get("/", response_class=HTMLResponse)
@app.get("/api", response_class=HTMLResponse)
@app.get("/api/", response_class=HTMLResponse)
@app.get("/api/index", response_class=HTMLResponse)
@app.get("/api/index.py", response_class=HTMLResponse)
async def get_index():
    candidates = [
        os.path.join(TEMPLATES_DIR, "index.html"),
        os.path.join(PARENT_DIR, "web", "templates", "index.html"),
        os.path.join(BASE_DIR, "templates", "index.html"),
        os.path.join(os.getcwd(), "web", "templates", "index.html")
    ]
    for c in candidates:
        if os.path.exists(c):
            with open(c, "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>ViddRop Studio Web - Chargement...</h1>")


@app.get("/static/{file_path:path}")
@app.get("/api/static/{file_path:path}")
async def serve_static_fallback(file_path: str):
    candidates = [
        os.path.join(STATIC_DIR, file_path),
        os.path.join(PARENT_DIR, "web", "static", file_path),
        os.path.join(BASE_DIR, "static", file_path),
        os.path.join(os.getcwd(), "web", "static", file_path),
        os.path.join(os.getcwd(), "static", file_path)
    ]
    for c in candidates:
        if os.path.isfile(c):
            media_type, _ = mimetypes.guess_type(c)
            return FileResponse(c, media_type=media_type or "application/octet-stream")
    raise HTTPException(status_code=404, detail="File not found")


@app.post("/api/info")
async def get_video_info(data: dict):
    """Récupère les métadonnées d'une vidéo en 1 seconde sans la télécharger"""
    url = (data.get("url") or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL requise")

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'socket_timeout': 15,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
        }
    }

    try:
        loop = asyncio.get_event_loop()
        def fetch():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=False)
        info = await loop.run_in_executor(None, fetch)
        if not info:
            raise HTTPException(status_code=404, detail="Impossible de lire les infos de cette vidéo")

        # Extraction des résolutions disponibles
        formats = info.get("formats", [])
        heights = set()
        for f in formats:
            h = f.get("height")
            if h and f.get("vcodec") != "none":
                heights.add(h)
        sorted_heights = sorted(list(heights), reverse=True)

        return {
            "title": info.get("title", "Vidéo"),
            "uploader": info.get("uploader") or info.get("channel") or "Inconnu",
            "duration": info.get("duration", 0),
            "duration_str": time.strftime('%H:%M:%S', time.gmtime(info.get('duration', 0))) if info.get('duration') else "Direct",
            "thumbnail": info.get("thumbnail") or "/static/viddRop.png",
            "resolutions": sorted_heights,
            "max_res": f"{sorted_heights[0]}p" if sorted_heights else "HD"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur d'analyse: {str(e)[:150]}")


@app.get("/api/download-file/{file_id}")
async def download_file(file_id: str):
    item = DOWNLOAD_REGISTRY.get(file_id)
    if not item or not os.path.exists(item["path"]):
        raise HTTPException(status_code=404, detail="Fichier introuvable ou expiré")

    return FileResponse(
        path=item["path"],
        filename=item["name"],
        media_type="application/octet-stream"
    )


# ── MOTEUR DE TÉLÉCHARGEMENT UNIFIÉ (HTTP & WEBSOCKET) ─────────────────────
def perform_core_download(url: str, fmt: str, resolution: str, progress_hook=None, status_hook=None, loop=None):
    res_limit = ""
    res_height_map = {"1080p": 1080, "720p": 720, "480p": 480}
    if resolution in res_height_map:
        h = res_height_map[resolution]
        res_limit = f"[height<={h}]"

    task_id = str(uuid.uuid4())[:8]
    outtmpl = os.path.join(DOWNLOADS_DIR, f"{task_id}_%(title).90s.%(ext)s")

    hooks = []
    if progress_hook:
        hooks.append(progress_hook)

    ydl_opts = {
        'outtmpl': outtmpl,
        'windowsfilenames': True,
        'progress_hooks': hooks,
        'concurrent_fragment_downloads': 16,
        'fragment_retries': 15,
        'retries': 10,
        'socket_timeout': 30,
        'noplaylist': True,
        'no_warnings': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
        }
    }

    if FFMPEG_BIN:
        ydl_opts['ffmpeg_location'] = FFMPEG_BIN
        if fmt == "MP3":
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '320',
                }],
            })
        elif fmt == "WEBM":
            ydl_opts.update({
                'format': f'bestvideo{res_limit}+bestaudio/best{res_limit}/best',
                'merge_output_format': 'webm'
            })
        else:  # MP4
            ydl_opts.update({
                'format': f'bestvideo{res_limit}[vcodec^=avc1]+bestaudio[acodec^=mp4a]/bestvideo{res_limit}+bestaudio/best{res_limit}/best',
                'merge_output_format': 'mp4',
            })
    else:
        # Vercel Serverless environment (sans FFmpeg préinstallé)
        if fmt == "MP3":
            ydl_opts.update({
                'format': 'bestaudio[ext=m4a]/bestaudio/best',
            })
        else:
            ydl_opts.update({
                'format': f'best[ext=mp4]/bestvideo{res_limit}[ext=mp4]+bestaudio[ext=m4a]/best{res_limit}/best',
            })

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        title = info.get('title', 'Vidéo') if info else 'Vidéo'
        
        filepath = ydl.prepare_filename(info) if info else ''
        if not os.path.exists(filepath):
            for f in os.listdir(DOWNLOADS_DIR):
                if f.startswith(task_id):
                    filepath = os.path.join(DOWNLOADS_DIR, f)
                    break

    if fmt == "MP4" and filepath and os.path.exists(filepath) and FFMPEG_BIN:
        filepath = ensure_h264_aac(filepath, resolution, status_hook, loop)

    if not filepath or not os.path.exists(filepath):
        raise Exception("Le fichier résultant est introuvable après traitement.")

    file_id = str(uuid.uuid4())
    ext = os.path.splitext(filepath)[1]
    clean_name = f"{title[:70]}{ext}".replace("/", "_").replace("\\", "_")
    file_size_mb = os.path.getsize(filepath) / (1024 * 1024)

    DOWNLOAD_REGISTRY[file_id] = {
        "path": filepath,
        "name": clean_name,
        "time": time.time()
    }

    return {
        "type": "complete",
        "title": title,
        "filename": clean_name,
        "size": f"{file_size_mb:.1f} Mo",
        "download_url": f"/api/download-file/{file_id}"
    }


# ── ROUTE HTTP DIRECTE (POUR VERCEL SERVERLESS ET FALLBACK) ────────────────
@app.post("/api/download-http")
async def http_download(data: dict):
    url = (data.get("url") or "").strip()
    fmt = (data.get("format") or "MP4").upper()
    resolution = data.get("resolution") or "source"

    if not url:
        raise HTTPException(status_code=400, detail="URL requise")

    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(None, perform_core_download, url, fmt, resolution)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)[:200])


# ── WEBSOCKET POUR LE TÉLÉCHARGEMENT EN TEMPS RÉEL ──────────────────────────
@app.websocket("/ws/download")
async def websocket_download(websocket: WebSocket):
    await websocket.accept()
    loop = asyncio.get_event_loop()

    try:
        data = await websocket.receive_json()
        url = (data.get("url") or "").strip()
        fmt = (data.get("format") or "MP4").upper()
        resolution = data.get("resolution") or "source"
        
        if not url:
            await websocket.send_json({"type": "error", "message": "URL manquante"})
            await websocket.close()
            return

        async def send_status(msg: str):
            try:
                await websocket.send_json({"type": "status", "message": msg})
            except: pass

        async def send_progress(pct: float, speed: str, eta: str):
            try:
                await websocket.send_json({
                    "type": "progress",
                    "percent": round(pct, 1),
                    "speed": speed,
                    "eta": eta
                })
            except: pass

        await send_status("🔍 Analyse de la vidéo...")

        # Hook de progression yt-dlp
        def progress_hook(d):
            if d.get('status') == 'downloading':
                try:
                    total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                    downloaded = d.get('downloaded_bytes', 0)
                    pct = (downloaded / total * 100) if total > 0 else 0.0
                    speed = d.get('_speed_str', 'N/A')
                    eta = d.get('_eta_str', 'N/A')
                    asyncio.run_coroutine_threadsafe(send_progress(pct, speed, eta), loop)
                except Exception:
                    pass
            elif d.get('status') == 'finished':
                asyncio.run_coroutine_threadsafe(
                    send_status("⚙ Finalisation / Recodage Studio..."), loop
                )

        result = await loop.run_in_executor(
            None, perform_core_download, url, fmt, resolution, progress_hook, send_status, loop
        )

        await websocket.send_json(result)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "message": str(e)[:150]})
        except: pass
    finally:
        try:
            await websocket.close()
        except: pass


# ── GARANTIE DU FORMAT H.264 / AAC POUR PREMIERE PRO & TRICASTER ───────────
def ensure_h264_aac(filepath: str, resolution: str, send_status_coro=None, loop=None) -> str:
    if not FFMPEG_BIN:
        return filepath

    ffmpeg_exe = os.path.join(FFMPEG_BIN, "ffmpeg.exe" if platform.system() == "Windows" else "ffmpeg")
    ffprobe_exe = os.path.join(FFMPEG_BIN, "ffprobe.exe" if platform.system() == "Windows" else "ffprobe")

    vcodec = ''
    acodec = ''
    actual_w = 0
    actual_h = 0

    try:
        probe_cmd = [
            ffprobe_exe, "-v", "quiet", "-print_format", "json",
            "-show_streams", filepath
        ]
        chk_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if platform.system() == "Windows" else 0
        probe_res = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=15, creationflags=chk_flags)
        if probe_res.returncode == 0:
            data = json.loads(probe_res.stdout)
            for stream in data.get('streams', []):
                if stream.get('codec_type') == 'video':
                    vcodec = (stream.get('codec_name') or '').lower()
                    actual_w = stream.get('width', 0)
                    actual_h = stream.get('height', 0)
                elif stream.get('codec_type') == 'audio':
                    acodec = (stream.get('codec_name') or '').lower()
    except Exception as e:
        print(f"⚠️ ffprobe exception: {e}")

    video_ok = vcodec in ('h264', 'avc1') or vcodec.startswith('avc1') or vcodec.startswith('h264')
    audio_ok = acodec in ('aac', 'mp4a') or acodec.startswith('mp4a') or acodec.startswith('aac') or acodec == ''

    if video_ok and audio_ok and filepath.lower().endswith('.mp4') and resolution == "source":
        # Déjà parfait, 0 seconde de traitement !
        return filepath

    # Doit être recodé
    if send_status_coro and loop:
        try:
            asyncio.run_coroutine_threadsafe(
                send_status_coro("⚡ Recodage Studio H.264/AAC en cours..."), loop
            )
        except Exception:
            pass

    base, _ = os.path.splitext(filepath)
    output_clean = base + "_studio.mp4"

    scale_filter = ""
    res_map = {"1080p": "1920:1080", "720p": "1280:720", "480p": "854:480"}
    if resolution in res_map:
        scale_filter = f"-vf scale={res_map[resolution]}:force_original_aspect_ratio=decrease,pad={res_map[resolution]}:(ow-ih)/2:(oh-ih)/2"

    if USE_NVENC:
        v_encoder = ["-c:v", "h264_nvenc", "-preset", "p4", "-cq", "19"]
    else:
        v_encoder = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-threads", "0"]

    cmd = [
        ffmpeg_exe, "-y",
        "-rtbufsize", "512M",
        "-i", filepath,
        *v_encoder,
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "320k",
        "-movflags", "+faststart",
        "-hide_banner", "-loglevel", "error",
    ]
    if scale_filter:
        cmd.extend(scale_filter.split())
    cmd.append(output_clean)

    chk_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if platform.system() == "Windows" else 0
    res = subprocess.run(cmd, capture_output=True, timeout=3600, creationflags=chk_flags)
    if res.returncode == 0 and os.path.exists(output_clean):
        try: os.remove(filepath)
        except: pass
        return output_clean

    return filepath


if __name__ == "__main__":
    import uvicorn
    print("\n" + "="*60)
    print("🚀 VIDDROP STUDIO WEB DÉMARRÉ")
    print("👉 Ouvrez votre navigateur sur : http://localhost:8000")
    print("="*60 + "\n")
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)
