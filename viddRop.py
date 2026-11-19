import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, filedialog
import os
import sys
import threading
import subprocess
import platform
import json
import re
import urllib.request
import urllib.error
from datetime import datetime
import shutil
import uuid
import time


# ════════════════════════════════════════════════════════════════════════════════
# 🔧 VÉRIFICATION + MISE À JOUR AUTOMATIQUE yt-dlp AVANT DÉMARRAGE
# ════════════════════════════════════════════════════════════════════════════════

def check_and_update_ytdlp():
    """Vérifier et mettre à jour yt-dlp automatiquement au démarrage"""
    print("🔍 Vérification de yt-dlp...")
    
    try:
        # Tenter la mise à jour vers la version nightly/master si disponible pour corriger GetPOT/INNERTUBE_CONTEXT
        result = subprocess.run(
            [sys.executable, "-m", "yt_dlp", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode != 0:
            print("⚠️ yt-dlp non trouvé! Installation...")
            install_ytdlp()
            return
        
        version = result.stdout.strip()
        print(f"✅ yt-dlp trouvé: {version}")
        
    except subprocess.TimeoutExpired:
        print("⚠️ Timeout lors de la vérification yt-dlp")
    except Exception as e:
        print(f"⚠️ Erreur vérification: {e}")
    
    check_pytube()

def check_pytube():
    """Vérifier si pytube est installé (fallback pour YouTube GetPOT)"""
    try:
        result = subprocess.run(
            [sys.executable, "-c", "import pytube; print('ok')"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            print("✅ pytube (fallback YouTube) trouvé")
        else:
            print("⚠️ pytube non installé - Tentative d'installation automatique...")
            subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "pytube"], capture_output=True)
    except Exception as e:
        print(f"⚠️ pytube check error: {e}")

def install_ytdlp():
    """Installer yt-dlp (Version nightly préférée pour contourner les blocages YouTube)"""
    print("📦 Installation de yt-dlp (Nightly Build)...")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", "https://github.com/yt-dlp/yt-dlp/archive/master.tar.gz"],
            capture_output=True,
            text=True,
            timeout=120
        )
        if result.returncode != 0:
            # Fallback version standard pip
            subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"], capture_output=True)
            print("✅ yt-dlp standard installé!")
        else:
            print("✅ yt-dlp (Master/Nightly) installé avec succès!")
    except Exception as e:
        print(f"❌ Impossible d'installer yt-dlp: {e}")

def update_ytdlp_interactive():
    """Mettre à jour yt-dlp avec fenêtre de progression interactive"""
    update_root = tk.Tk()
    update_root.title("Mise à Jour yt-dlp")
    update_root.geometry("400x150")
    update_root.resizable(False, False)
    
    update_root.update_idletasks()
    x = (update_root.winfo_screenwidth() // 2) - (400 // 2)
    y = (update_root.winfo_screenheight() // 2) - (150 // 2)
    update_root.geometry(f"+{x}+{y}")
    
    main_label = tk.Label(
        update_root,
        text="📦 Correctif YouTube en cours d'application...",
        font=("Arial", 11, "bold"),
        fg="#00C9A7"
    )
    main_label.pack(pady=20)
    
    info_label = tk.Label(
        update_root,
        text="Mise à jour des extracteurs d'URL...",
        font=("Arial", 10),
        fg="#888888"
    )
    info_label.pack(pady=5)
    
    progress = tk.Canvas(update_root, height=20, bg="#222222", relief="flat", bd=0)
    progress.pack(fill="x", padx=20, pady=20)
    progress_bar = progress.create_rectangle(0, 0, 0, 20, fill="#00C9A7", outline="")
    
    update_root.update()
    
    def do_update():
        try:
            # Installation depuis Master pour fixer l'erreur INNERTUBE_CONTEXT
            proc = subprocess.Popen(
                [sys.executable, "-m", "pip", "install", "--upgrade", "https://github.com/yt-dlp/yt-dlp/archive/master.tar.gz"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = proc.communicate(timeout=120)
            
            if proc.returncode == 0:
                info_label.config(text="✅ Correctif appliqué avec succès!", fg="#00C9A7")
                progress_bar_width = progress.winfo_width()
                progress.coords(progress_bar, 0, 0, progress_bar_width, 20)
                update_root.update()
                update_root.after(1500, update_root.destroy)
            else:
                # Fallback standard
                subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"])
                update_root.after(1500, update_root.destroy)
                
        except Exception as e:
            update_root.after(1500, update_root.destroy)
    
    update_thread = threading.Thread(target=do_update, daemon=True)
    update_thread.start()
    update_root.mainloop()

# Lancer la vérification au démarrage
print("="*60)
print("🚀 ViddRop Studio Pro - Démarrage")
print("="*60)
check_and_update_ytdlp()
print("="*60)

import yt_dlp
from yt_dlp.postprocessor.common import PostProcessor


class StreamingRecodePP(PostProcessor):
    def __init__(self, downloader=None, ffmpeg_bin=None, status_cb=None, quality="ultrafast", resolution="source"):
        super().__init__(downloader)
        self.ffmpeg_bin = ffmpeg_bin
        self.status_cb = status_cb
        self.quality = quality
        self.resolution = resolution

    def run(self, info):
        filepath = info.get('filepath') or info.get('_filename')
        if not filepath or not os.path.exists(filepath):
            return [], info

        vcodec = (info.get('vcodec') or '').lower()
        acodec = (info.get('acodec') or '').lower()
        video_ok = vcodec.startswith('avc1') or vcodec.startswith('h264')
        audio_ok = acodec.startswith('mp4a') or acodec.startswith('aac') or acodec == ''

        if video_ok and audio_ok and filepath.lower().endswith('.mp4') and self.resolution == "source":
            if self.status_cb:
                self.status_cb("✅ Déjà H.264/AAC — aucun recodage")
            return [], info

        if self.status_cb:
            self.status_cb(f"⚡ Recodage H.264/AAC + {self.resolution} EN TEMPS RÉEL...")

        base, ext = os.path.splitext(filepath)
        final_path = base + ".mp4"
        ffmpeg_exe = "ffmpeg.exe" if platform.system() == "Windows" else "ffmpeg"
        ffmpeg_exe = os.path.join(self.ffmpeg_bin, ffmpeg_exe) if self.ffmpeg_bin else ffmpeg_exe
        
        temp_id = str(uuid.uuid4())[:8]
        dir_path = os.path.dirname(filepath)
        
        temp_input = os.path.join(dir_path, f"temp_input_{temp_id}.mp4")
        temp_output = os.path.join(dir_path, f"temp_output_{temp_id}.mp4")
        
        try:
            if len(filepath) > 200 or not filepath.isascii():
                shutil.copy2(filepath, temp_input)
                ffmpeg_input = temp_input
            else:
                ffmpeg_input = filepath

            scale_filter = ""
            res_map = {"1080p": "1920:1080", "720p": "1280:720", "480p": "854:480"}
            if self.resolution in res_map:
                scale_filter = f"-vf scale={res_map[self.resolution]}:force_original_aspect_ratio=decrease,pad={res_map[self.resolution]}:(ow-ih)/2:(oh-ih)/2"

            cmd = [
                ffmpeg_exe, "-y",
                "-rtbufsize", "512M",
                "-i", ffmpeg_input,
                "-c:v", "libx264", "-preset", self.quality, "-threads", "0",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "128k",
                "-movflags", "+faststart+frag_keyframe",
                "-frag_duration", "5000",
                "-hide_banner", "-loglevel", "error",
            ]
            
            if scale_filter:
                cmd.extend(scale_filter.split())
            
            cmd.append(temp_output)
            
            result = subprocess.run(cmd, capture_output=True, timeout=3600)
            
            if result.returncode != 0:
                error_msg = result.stderr.decode('utf-8', errors='ignore') if result.stderr else str(result.returncode)
                if self.status_cb:
                    self.status_cb(f"❌ Erreur recodage FFmpeg")
                raise Exception(f"FFmpeg failed: {error_msg}")

            if os.path.exists(temp_output):
                if os.path.exists(final_path):
                    os.remove(final_path)
                os.rename(temp_output, final_path)
            
            if os.path.exists(filepath) and filepath != final_path:
                try:
                    os.remove(filepath)
                except OSError:
                    pass
            
            if os.path.exists(temp_input):
                try:
                    os.remove(temp_input)
                except OSError:
                    pass
            
            info['filepath'] = final_path
            
        except Exception as e:
            for temp_file in [temp_input, temp_output]:
                if os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                    except:
                        pass
            
            if self.status_cb:
                error_text = str(e)
                if len(error_text) > 100:
                    error_text = error_text[:100] + "..."
                self.status_cb(f"❌ {error_text}")
            raise

        return [], info

# ── Chemins ───────────────────────────────────────────────────────────────────
if getattr(sys, 'frozen', False):
    CURRENT_DIR = os.path.dirname(sys.executable)
else:
    CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

DEFAULT_PATH = os.path.join(os.path.expanduser("~"), "Downloads")

# ── Palette "Studio Vidéo Pro - Edition Rouge" ────────────────────────────────
ctk.set_default_color_theme("blue")

PALETTES = {
    "light": {
        "ACCENT": "#FF2A42", "ACCENT_DARK": "#D61A31",
        "BG_MAIN": "#F4F6F8", "BG_PANEL": "#FFFFFF", "BG_CARD": "#FFFFFF",
        "TEXT_PRIMARY": "#0F172A", "TEXT_DIM": "#64748B", "TEXT_MUTED": "#94A3B8",
        "BORDER": "#E2E8F0", "SUCCESS": "#10B981", "WARNING_C": "#F59E0B", "DANGER": "#EF4444",
    },
    "dark": {
        "ACCENT": "#FF334B", "ACCENT_DARK": "#D61A31",
        "BG_MAIN": "#0D0E11", "BG_PANEL": "#16161A", "BG_CARD": "#212127",
        "TEXT_PRIMARY": "#F1F5F9", "TEXT_DIM": "#94A3B8", "TEXT_MUTED": "#64748B",
        "BORDER": "#2E2E38", "SUCCESS": "#10B981", "WARNING_C": "#F59E0B", "DANGER": "#FF3366",
    },
}

ACCENT = ACCENT_DARK = BG_MAIN = BG_PANEL = BG_CARD = None
TEXT_PRIMARY = TEXT_DIM = TEXT_MUTED = BORDER = SUCCESS = WARNING_C = DANGER = None


def apply_palette(mode):
    global ACCENT, ACCENT_DARK, BG_MAIN, BG_PANEL, BG_CARD
    global TEXT_PRIMARY, TEXT_DIM, TEXT_MUTED, BORDER, SUCCESS, WARNING_C, DANGER
    p = PALETTES[mode]
    ACCENT, ACCENT_DARK = p["ACCENT"], p["ACCENT_DARK"]
    BG_MAIN, BG_PANEL, BG_CARD = p["BG_MAIN"], p["BG_PANEL"], p["BG_CARD"]
    TEXT_PRIMARY, TEXT_DIM, TEXT_MUTED = p["TEXT_PRIMARY"], p["TEXT_DIM"], p["TEXT_MUTED"]
    BORDER, SUCCESS, WARNING_C, DANGER = p["BORDER"], p["SUCCESS"], p["WARNING_C"], p["DANGER"]
    ctk.set_appearance_mode(mode)


apply_palette("dark")


class ViddRopApp:
    def __init__(self, root):
        self.root = root
        self.root.title("ViddRop Studio Pro - Red Edition (Premiere Pro & Tricaster)")
        self.root.geometry("1280x720")
        self.root.minsize(1100, 650)
        self.root.resizable(True, True)
        self.root.configure(fg_color=BG_MAIN)

        for ico_name in ("vidddrop.ico", "viddrop.ico", "logo.ico"):
            icon_path = os.path.join(CURRENT_DIR, ico_name)
            if os.path.exists(icon_path):
                try:
                    self.root.iconbitmap(icon_path)
                except tk.TclError:
                    pass
                break

        self.stop_download = False
        self.format_var = tk.StringVar(value="MP4")
        self.current_theme = "dark"
        self.history = []
        self.queue = []
        self.queue_running = False
        self.is_processing = False
        self.active_downloads = 0
        self.max_parallel = 2
        self.queue_ratings = {}
        
        self.create_widgets()

    def create_widgets(self):
        # Header
        header = ctk.CTkFrame(self.root, fg_color=BG_PANEL, height=70, corner_radius=0, border_width=1, border_color=BORDER)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        logo_row = ctk.CTkFrame(header, fg_color="transparent")
        logo_row.pack(side="left", padx=24, pady=12)

        logo_box = ctk.CTkFrame(logo_row, width=42, height=42, fg_color=ACCENT, corner_radius=8)
        logo_box.pack(side="left", padx=(0, 12))
        logo_box.pack_propagate(False)
        ctk.CTkLabel(logo_box, text="⚡HQ", font=ctk.CTkFont(size=11, weight="bold"), text_color="#FFFFFF").place(relx=0.5, rely=0.5, anchor="center")

        name_col = ctk.CTkFrame(logo_row, fg_color="transparent")
        name_col.pack(side="left")

        name_row = ctk.CTkFrame(name_col, fg_color="transparent")
        name_row.pack()
        ctk.CTkLabel(name_row, text="VIDD", font=ctk.CTkFont(size=22, weight="bold"), text_color=TEXT_PRIMARY).pack(side="left")
        ctk.CTkLabel(name_row, text="ROP", font=ctk.CTkFont(size=22, weight="bold"), text_color=ACCENT).pack(side="left")

        ctk.CTkLabel(name_col, text="UNIVERSAL SOCIAL FIX (FB / TT / IG / YT)", font=ctk.CTkFont(size=9, weight="bold"), text_color=SUCCESS, anchor="w").pack(fill="x")

        # Badges
        badges = ctk.CTkFrame(header, fg_color="transparent")
        badges.pack(side="left", padx=20)
        platforms = [
            ("Premiere Pro Ready", "#FF334B", "#2D1216"),
            ("Tricaster Universal", "#10B981", "#0E2A1E"),
            ("H.264 / AAC Clean", "#FF9500", "#2D2012"),
        ]
        for name, fg, bg in platforms:
            ctk.CTkLabel(badges, text=name, font=ctk.CTkFont(size=10, weight="bold"), text_color=fg, fg_color=bg, corner_radius=6, padx=10, pady=4).pack(side="left", padx=4)

        # Theme Switch
        theme_row = ctk.CTkFrame(header, fg_color="transparent")
        theme_row.pack(side="right", padx=24)
        self.theme_switch = ctk.CTkSwitch(
            theme_row, text="🌙 Sombre Studio", width=40, font=ctk.CTkFont(size=11),
            text_color=TEXT_MUTED, progress_color=ACCENT, button_color="#ffffff",
            command=self.toggle_theme,
        )
        self.theme_switch.pack(side="right")
        if self.current_theme == "dark":
            self.theme_switch.select()
            self.theme_switch.configure(text="☀ Clair")
        else:
            self.theme_switch.deselect()
            self.theme_switch.configure(text="🌙 Sombre Studio")

        # Layout
        main_container = ctk.CTkFrame(self.root, fg_color=BG_MAIN)
        main_container.pack(fill="both", expand=True, padx=24, pady=20)

        left_col = ctk.CTkFrame(main_container, fg_color="transparent")
        left_col.pack(side="left", fill="both", expand=True, padx=(0, 12))

        right_col = ctk.CTkFrame(main_container, fg_color="transparent", width=480)
        right_col.pack(side="right", fill="both", expand=False, padx=(12, 0))
        right_col.pack_propagate(False)

        # ── Gauche ──
        self._label(left_col, "SOURCE / URL MEDIA (FB, TikTok, Insta, YT)")
        url_card = ctk.CTkFrame(left_col, fg_color=BG_CARD, corner_radius=12, border_width=1, border_color=BORDER)
        url_card.pack(fill="x", pady=(0, 20))
        url_row = ctk.CTkFrame(url_card, fg_color="transparent")
        url_row.pack(fill="x", padx=14, pady=14)

        self.url_input = ctk.CTkEntry(
            url_row, placeholder_text="Coller l'URL Facebook, TikTok, Instagram ou YouTube...",
            font=ctk.CTkFont(size=13), height=46, fg_color=BG_MAIN,
            border_color=BORDER, border_width=1, corner_radius=8, text_color=TEXT_PRIMARY,
        )
        self.url_input.pack(side="left", fill="x", expand=True, padx=(0, 10))

        ctk.CTkButton(url_row, text="📋 Coller", width=100, height=46, font=ctk.CTkFont(size=12, weight="bold"), fg_color=BG_PANEL, hover_color=BORDER, border_color=BORDER, border_width=1, corner_radius=8, text_color=TEXT_PRIMARY, command=self.paste_url).pack(side="left", padx=(0, 8))
        ctk.CTkButton(url_row, text="+ File", width=80, height=46, font=ctk.CTkFont(size=12, weight="bold"), fg_color="#380F14", hover_color="#581A22", border_width=1, border_color=ACCENT, corner_radius=8, text_color=ACCENT, command=self.add_to_queue).pack(side="left")

        self._label(left_col, "REPERTOIRE D'EXPORTATION")
        path_card = ctk.CTkFrame(left_col, fg_color=BG_CARD, corner_radius=12, border_width=1, border_color=BORDER)
        path_card.pack(fill="x", pady=(0, 20))
        path_row = ctk.CTkFrame(path_card, fg_color="transparent")
        path_row.pack(fill="x", padx=14, pady=14)

        self.path_input = ctk.CTkEntry(path_row, font=ctk.CTkFont(size=12), height=44, fg_color=BG_MAIN, border_color=BORDER, border_width=1, corner_radius=8, text_color=TEXT_MUTED)
        self.path_input.insert(0, DEFAULT_PATH)
        self.path_input.pack(side="left", fill="x", expand=True, padx=(0, 10))
        ctk.CTkButton(path_row, text="Parcourir", width=110, height=44, font=ctk.CTkFont(size=12), fg_color=BG_PANEL, hover_color=BORDER, border_color=BORDER, border_width=1, corner_radius=8, text_color=TEXT_PRIMARY, command=self.browse_path).pack(side="left")

        self._label(left_col, "PROFIL D'EXPORTATION")
        fmt_card = ctk.CTkFrame(left_col, fg_color=BG_CARD, corner_radius=12, border_width=1, border_color=BORDER)
        fmt_card.pack(fill="x", pady=(0, 20))
        fmt_row = ctk.CTkFrame(fmt_card, fg_color="transparent")
        fmt_row.pack(fill="x", padx=14, pady=14)

        self.fmt_buttons = {}
        formats = [("MP4", "Régie / Premiere Pro Universal"), ("MP3", "Audio Premium 320k"), ("WEBM", "Format Web Native")]
        for fmt, desc in formats:
            is_active = fmt == "MP4"
            btn = ctk.CTkButton(
                fmt_row, text=f"{fmt}\n{desc}", font=ctk.CTkFont(size=12, weight="bold"), height=55,
                fg_color=ACCENT if is_active else BG_MAIN,
                hover_color=ACCENT_DARK if is_active else BORDER,
                border_width=1, border_color=ACCENT if is_active else BORDER,
                corner_radius=8, text_color="#FFFFFF" if is_active else TEXT_PRIMARY,
                command=lambda f=fmt: self.select_format(f),
            )
            btn.pack(side="left", expand=True, fill="x", padx=4)
            self.fmt_buttons[fmt] = btn

        self._label(left_col, "MONITEUR DE TÉLÉCHARGEMENT & ENCODAGE")
        prog_card = ctk.CTkFrame(left_col, fg_color=BG_CARD, corner_radius=12, border_width=1, border_color=BORDER)
        prog_card.pack(fill="x", pady=(0, 20))

        top_row = ctk.CTkFrame(prog_card, fg_color="transparent")
        top_row.pack(fill="x", padx=16, pady=(16, 8))

        self.status_label = ctk.CTkLabel(top_row, text="● Prêt", font=ctk.CTkFont(size=13, weight="bold"), text_color=SUCCESS, anchor="w")
        self.status_label.pack(side="left")

        self.pct_label = ctk.CTkLabel(top_row, text="0%", font=ctk.CTkFont(size=14, weight="bold"), text_color=TEXT_DIM)
        self.pct_label.pack(side="right")

        self.progress_bar = ctk.CTkProgressBar(prog_card, height=10, corner_radius=5, fg_color=BG_MAIN, progress_color=ACCENT)
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", padx=16, pady=(0, 16))

        btn_row = ctk.CTkFrame(left_col, fg_color="transparent")
        btn_row.pack(fill="x", pady=(0, 10))

        self.btn_download = ctk.CTkButton(
            btn_row, text="⚡ TÉLÉCHARGER & RECODER POUR REGIE/PREMIERE", font=ctk.CTkFont(size=13, weight="bold"), height=54,
            fg_color=ACCENT, hover_color=ACCENT_DARK, corner_radius=8, text_color="#FFFFFF", command=self.start_download_wrapper,
        )
        self.btn_download.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.btn_cancel = ctk.CTkButton(btn_row, text="✕ Stop", font=ctk.CTkFont(size=13, weight="bold"), height=54, width=90, fg_color=BG_PANEL, hover_color=DANGER, border_color=BORDER, border_width=1, corner_radius=8, text_color=TEXT_PRIMARY, state="disabled", command=self.cancel_download)
        self.btn_cancel.pack(side="left", padx=(0, 10))

        self.btn_open_folder = ctk.CTkButton(btn_row, text="📁 Ouvrir", font=ctk.CTkFont(size=13, weight="bold"), height=54, width=100, fg_color=BG_PANEL, hover_color=BORDER, border_color=BORDER, border_width=1, corner_radius=8, text_color=TEXT_PRIMARY, command=self.open_folder)
        self.btn_open_folder.pack(side="left")

        # ── Droite ──
        queue_header = ctk.CTkFrame(right_col, fg_color="transparent")
        queue_header.pack(fill="x", pady=(0, 6))
        self.queue_count_label = ctk.CTkLabel(queue_header, text="FILE D'ATTENTE (0)", font=ctk.CTkFont(size=11, weight="bold"), text_color=TEXT_DIM, anchor="w")
        self.queue_count_label.pack(side="left")

        queue_ctrl = ctk.CTkFrame(queue_header, fg_color="transparent")
        queue_ctrl.pack(side="right")
        self.btn_clear_queue = ctk.CTkButton(queue_ctrl, text="Effacer", width=60, height=24, font=ctk.CTkFont(size=10), fg_color="transparent", hover_color=BG_CARD, text_color=TEXT_DIM, command=self.clear_queue)
        self.btn_clear_queue.pack(side="left", padx=(0, 4))
        self.btn_start_queue = ctk.CTkButton(queue_ctrl, text="▶ Lancer File", width=100, height=26, font=ctk.CTkFont(size=11, weight="bold"), fg_color=ACCENT, hover_color=ACCENT_DARK, corner_radius=6, text_color="#FFFFFF", command=self.start_queue_wrapper)
        self.btn_start_queue.pack(side="left")

        # ── OPTIONS AVANCÉES ──
        opts_header = ctk.CTkFrame(right_col, fg_color="transparent")
        opts_header.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(opts_header, text="⚙ OPTIONS AVANCÉES", font=ctk.CTkFont(size=10, weight="bold"), text_color=TEXT_DIM, anchor="w").pack(side="left")

        opts_frame = ctk.CTkFrame(right_col, fg_color=BG_CARD, corner_radius=10, border_width=1, border_color=BORDER)
        opts_frame.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(opts_frame, text="Parallèle :", font=ctk.CTkFont(size=9), text_color=TEXT_DIM).pack(side="left", padx=10, pady=8)
        self.parallel_var = tk.IntVar(value=2)
        ctk.CTkComboBox(opts_frame, values=["1", "2", "3", "4"], variable=self.parallel_var, width=50, height=26, font=ctk.CTkFont(size=9), fg_color=BG_MAIN, border_color=BORDER, text_color=TEXT_PRIMARY).pack(side="left", padx=2, pady=8)

        ctk.CTkLabel(opts_frame, text="Qualité :", font=ctk.CTkFont(size=9), text_color=TEXT_DIM).pack(side="left", padx=(10, 0), pady=8)
        self.quality_var = tk.StringVar(value="ultrafast")
        ctk.CTkComboBox(opts_frame, values=["ultrafast", "veryfast", "fast"], variable=self.quality_var, width=80, height=26, font=ctk.CTkFont(size=9), fg_color=BG_MAIN, border_color=BORDER, text_color=TEXT_PRIMARY).pack(side="left", padx=2, pady=8)

        ctk.CTkLabel(opts_frame, text="Res :", font=ctk.CTkFont(size=9), text_color=TEXT_DIM).pack(side="left", padx=(10, 0), pady=8)
        self.resolution_var = tk.StringVar(value="source")
        ctk.CTkComboBox(opts_frame, values=["source", "1080p", "720p", "480p"], variable=self.resolution_var, width=70, height=26, font=ctk.CTkFont(size=9), fg_color=BG_MAIN, border_color=BORDER, text_color=TEXT_PRIMARY).pack(side="left", padx=2, pady=8)

        self.delete_source_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(opts_frame, text="Sup src", variable=self.delete_source_var, text_color=TEXT_MUTED, checkmark_color=ACCENT, fg_color=BG_MAIN, border_color=BORDER, font=ctk.CTkFont(size=9)).pack(side="left", padx=6, pady=8)

        self.auto_subtitles_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(opts_frame, text="Sous-tit", variable=self.auto_subtitles_var, text_color=TEXT_MUTED, checkmark_color=ACCENT, fg_color=BG_MAIN, border_color=BORDER, font=ctk.CTkFont(size=9)).pack(side="left", padx=6, pady=8)

        # ── FILE D'ATTENTE ──
        self.queue_frame = ctk.CTkScrollableFrame(right_col, fg_color=BG_CARD, corner_radius=12, border_width=1, border_color=BORDER)
        self.queue_frame.pack(fill="both", expand=True, pady=(0, 12))
        self.queue_empty_label = ctk.CTkLabel(self.queue_frame, text="Aucun élément dans la file d'attente", font=ctk.CTkFont(size=11), text_color=TEXT_DIM)
        self.queue_empty_label.pack(pady=30)

        # History
        hist_header = ctk.CTkFrame(right_col, fg_color="transparent")
        hist_header.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(hist_header, text="HISTORIQUE D'EXPORTATION", font=ctk.CTkFont(size=11, weight="bold"), text_color=TEXT_DIM, anchor="w").pack(side="left")
        ctk.CTkButton(hist_header, text="Effacer", width=60, height=20, font=ctk.CTkFont(size=10), fg_color="transparent", hover_color=BG_CARD, text_color=TEXT_DIM, command=self.clear_history).pack(side="right")

        self.history_frame = ctk.CTkScrollableFrame(right_col, fg_color=BG_CARD, corner_radius=12, border_width=1, border_color=BORDER)
        self.history_frame.pack(fill="both", expand=True)
        self.history_empty_label = ctk.CTkLabel(self.history_frame, text="Aucun historique", font=ctk.CTkFont(size=11), text_color=TEXT_DIM)
        self.history_empty_label.pack(pady=30)

    def _label(self, parent, text):
        ctk.CTkLabel(parent, text=text, font=ctk.CTkFont(size=10, weight="bold"), text_color=TEXT_DIM, anchor="w").pack(fill="x", pady=(0, 6))

    def select_format(self, fmt):
        self.format_var.set(fmt)
        for f, btn in self.fmt_buttons.items():
            if f == fmt:
                btn.configure(fg_color=ACCENT, text_color="#FFFFFF", border_color=ACCENT)
            else:
                btn.configure(fg_color=BG_MAIN, text_color=TEXT_PRIMARY, border_color=BORDER)

    def toggle_theme(self):
        self.current_theme = "dark" if self.current_theme == "light" else "light"
        apply_palette(self.current_theme)
        self.rebuild_ui()

    def rebuild_ui(self):
        for widget in self.root.winfo_children(): widget.destroy()
        self.create_widgets()
        self.refresh_history_ui()
        self.refresh_queue_ui()

    def open_folder(self):
        path = self.path_input.get().strip()
        if os.path.isdir(path):
            if platform.system() == "Windows": os.startfile(path)
            elif platform.system() == "Darwin": subprocess.Popen(["open", path])
            else: subprocess.Popen(["xdg-open", path])

    def add_history_entry(self, title, filepath):
        self.history.insert(0, {"title": title, "path": filepath, "time": datetime.now().strftime("%H:%M")})
        self.refresh_history_ui()

    def clear_history(self):
        self.history = []
        self.refresh_history_ui()

    def refresh_history_ui(self):
        for widget in self.history_frame.winfo_children(): widget.destroy()
        if not self.history:
            ctk.CTkLabel(self.history_frame, text="Aucun historique", font=ctk.CTkFont(size=11), text_color=TEXT_DIM).pack(pady=30)
            return
        for entry in self.history:
            row = ctk.CTkFrame(self.history_frame, fg_color=BG_MAIN, corner_radius=8, border_width=1, border_color=BORDER)
            row.pack(fill="x", pady=4, padx=2)
            info = ctk.CTkFrame(row, fg_color="transparent")
            info.pack(side="left", fill="x", expand=True, padx=12, pady=8)
            ctk.CTkLabel(info, text=entry["title"][:40], font=ctk.CTkFont(size=11, weight="bold"), text_color=TEXT_PRIMARY, anchor="w").pack(fill="x")
            ctk.CTkLabel(info, text=f"✅ {entry['time']}", font=ctk.CTkFont(size=10), text_color=SUCCESS, anchor="w").pack(fill="x")

    def add_to_queue(self):
        url = self.url_input.get().strip()
        if url:
            self.queue.append({
                "url": url, 
                "status": "attente",
                "progress": 0,
                "title": "",
                "filepath": "",
                "error": None
            })
            self.url_input.delete(0, "end")
            self.refresh_queue_ui()

    def clear_queue(self):
        if not self.queue_running:
            self.queue = []
            self.refresh_queue_ui()

    def refresh_queue_ui(self):
        for widget in self.queue_frame.winfo_children(): widget.destroy()
        self.queue_count_label.configure(text=f"FILE D'ATTENTE ({len(self.queue)})")
        if not self.queue:
            ctk.CTkLabel(self.queue_frame, text="Aucun élément dans la file", font=ctk.CTkFont(size=11), text_color=TEXT_DIM).pack(pady=30)
            return
        
        for idx, item in enumerate(self.queue):
            row = ctk.CTkFrame(self.queue_frame, fg_color=BG_MAIN, corner_radius=8, border_width=1, border_color=BORDER)
            row.pack(fill="x", pady=3, padx=2)

            info_col = ctk.CTkFrame(row, fg_color="transparent")
            info_col.pack(side="left", fill="both", expand=True, padx=10, pady=6)

            title = item.get("url", "")[:30]
            status_icon = {"attente": "⏳", "en cours": "⚡", "terminé": "✅", "erreur": "❌"}.get(item.get("status", "attente"), "⏳")
            
            ctk.CTkLabel(info_col, text=f"{status_icon} {title}", font=ctk.CTkFont(size=10, weight="bold"), text_color=TEXT_PRIMARY, anchor="w").pack(fill="x")
            
            progress_val = item.get("progress", 0)
            if item.get("status") == "en cours":
                progress_bar = ctk.CTkProgressBar(info_col, height=4, corner_radius=2, fg_color=BG_MAIN, progress_color=ACCENT)
                progress_bar.set(progress_val / 100.0)
                progress_bar.pack(fill="x", pady=(4, 0))
            
            if item.get("error"):
                error_label = ctk.CTkLabel(info_col, text=f"⚠️ {item['error']}", 
                                          font=ctk.CTkFont(size=8), text_color=DANGER, anchor="w")
                error_label.pack(fill="x", pady=(2, 0))
            
            btn_col = ctk.CTkFrame(row, fg_color="transparent")
            btn_col.pack(side="right", padx=8, pady=6)

            rating = self.queue_ratings.get(idx, None)
            thumbs_up_fg = ACCENT if rating == "up" else BG_PANEL
            thumbs_down_fg = DANGER if rating == "down" else BG_PANEL
            
            ctk.CTkButton(btn_col, text="👍", width=28, height=24, font=ctk.CTkFont(size=11), 
                         fg_color=thumbs_up_fg, hover_color=ACCENT, border_color=BORDER, border_width=1, 
                         corner_radius=4, command=lambda i=idx: self.rate_queue_item(i, "up")).pack(side="left", padx=2)

            ctk.CTkButton(btn_col, text="👎", width=28, height=24, font=ctk.CTkFont(size=11), 
                         fg_color=thumbs_down_fg, hover_color=DANGER, border_color=BORDER, border_width=1, 
                         corner_radius=4, command=lambda i=idx: self.rate_queue_item(i, "down")).pack(side="left", padx=2)

            ctk.CTkButton(btn_col, text="⬆", width=28, height=24, font=ctk.CTkFont(size=10), 
                         fg_color=BG_PANEL, hover_color=BORDER, border_color=BORDER, border_width=1, 
                         corner_radius=4, command=lambda i=idx: self.move_queue_item(i, -1)).pack(side="left", padx=1)

            ctk.CTkButton(btn_col, text="⬇", width=28, height=24, font=ctk.CTkFont(size=10), 
                         fg_color=BG_PANEL, hover_color=BORDER, border_color=BORDER, border_width=1, 
                         corner_radius=4, command=lambda i=idx: self.move_queue_item(i, 1)).pack(side="left", padx=1)

            ctk.CTkButton(btn_col, text="✕", width=28, height=24, font=ctk.CTkFont(size=11), 
                         fg_color=BG_PANEL, hover_color=DANGER, text_color=DANGER, border_color=BORDER, border_width=1, 
                         corner_radius=4, command=lambda i=idx: self.remove_queue_item(i)).pack(side="left", padx=2)

    def rate_queue_item(self, idx, rating):
        current = self.queue_ratings.get(idx)
        if current == rating:
            del self.queue_ratings[idx]
        else:
            self.queue_ratings[idx] = rating
        self.refresh_queue_ui()

    def move_queue_item(self, idx, direction):
        new_idx = idx + direction
        if 0 <= new_idx < len(self.queue):
            self.queue[idx], self.queue[new_idx] = self.queue[new_idx], self.queue[idx]
            if idx in self.queue_ratings:
                self.queue_ratings[new_idx] = self.queue_ratings.pop(idx)
            self.refresh_queue_ui()

    def remove_queue_item(self, idx):
        if idx < len(self.queue):
            self.queue.pop(idx)
            if idx in self.queue_ratings:
                del self.queue_ratings[idx]
            self.refresh_queue_ui()

    def start_queue_wrapper(self):
        if not self.is_processing and self.queue:
            self.is_processing = True
            self.queue_running = True
            threading.Thread(target=self.process_queue, daemon=True).start()

    def process_queue(self):
        self.max_parallel = int(self.parallel_var.get())
        threads = []
        
        while any(item["status"] == "attente" for item in self.queue) and self.queue_running:
            for item in self.queue:
                if item["status"] == "attente" and self.active_downloads < self.max_parallel:
                    item["status"] = "en cours"
                    self.active_downloads += 1
                    t = threading.Thread(target=self._process_queue_item, args=(item,), daemon=True)
                    t.start()
                    threads.append(t)
            
            threading.Event().wait(0.5)
        
        for t in threads:
            t.join(timeout=1)
        
        self.queue_running = False
        self.is_processing = False
        self.root.after(0, self.refresh_queue_ui)

    def _process_queue_item(self, item):
        try:
            def queue_progress_hook(d):
                try:
                    if d.get('status') == 'downloading':
                        total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                        downloaded = d.get('downloaded_bytes', 0)
                        if total > 0:
                            item["progress"] = (downloaded / total) * 100
                        self.root.after(0, self.refresh_queue_ui)
                    elif d.get('status') == 'finished':
                        item["progress"] = 100
                        self.root.after(0, self.refresh_queue_ui)
                except Exception:
                    pass

            title, filepath = self._run_download_with_hook(item["url"], queue_progress_hook)
            item["status"] = "terminé"
            item["title"] = title
            item["filepath"] = filepath
            item["progress"] = 100
            item["error"] = None
            self.root.after(0, lambda: self.add_history_entry(title, filepath))
            
        except Exception as e:
            item["status"] = "erreur"
            error_msg = str(e)
            if len(error_msg) > 80:
                error_msg = error_msg[:77] + "..."
            item["error"] = error_msg
            print(f"❌ Erreur file [{item.get('url', '')[:30]}]: {error_msg}")
            
        finally:
            self.active_downloads -= 1
            self.root.after(0, self.refresh_queue_ui)

    def progress_hook(self, d):
        if self.stop_download:
            raise Exception("Annulé.")

        if d.get('status') == 'downloading':
            try:
                total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                downloaded = d.get('downloaded_bytes', 0)

                if total > 0:
                    p = (downloaded / total) * 100
                else:
                    raw_pct = d.get('_percent_str', '0%')
                    clean_pct = re.sub(r'\x1b\[[0-9;]*m', '', raw_pct).replace('%', '').strip()
                    p = float(clean_pct) if clean_pct else 0.0

                speed = d.get('_speed_str', 'N/A')
                self.root.after(0, lambda: self._update_progress_ui(p, speed))
            except Exception:
                pass
        elif d.get('status') == 'finished':
            self.root.after(0, lambda: self.status_label.configure(text="⚙ Conversion H.264/AAC...", text_color=WARNING_C))

    def _update_progress_ui(self, p, speed):
        p_clamped = min(max(p / 100.0, 0.0), 1.0)
        self.progress_bar.set(p_clamped)
        self.pct_label.configure(text=f"{p:.1f}%")
        self.status_label.configure(text=f"⚡ {p:.1f}%  —  {speed}", text_color=ACCENT)

    def paste_url(self):
        try:
            self.url_input.delete(0, "end")
            self.url_input.insert(0, self.root.clipboard_get())
        except Exception:
            pass

    def browse_path(self):
        path = filedialog.askdirectory()
        if path:
            self.path_input.delete(0, "end")
            self.path_input.insert(0, path)

    def cancel_download(self):
        self.stop_download = True

    def start_download_wrapper(self):
        if not self.url_input.get().strip() or self.is_processing:
            return
        self.stop_download = False
        self.is_processing = True
        self.btn_download.configure(state="disabled")
        self.btn_cancel.configure(state="normal", fg_color=DANGER)
        threading.Thread(target=self.download_video, daemon=True).start()

    # ── MOTEUR DE TÉLÉCHARGEMENT & RECODAGE UNIVERSEL ─────────────────────────
    def _run_download_with_hook(self, url, custom_hook=None):
        max_retries = 3
        for attempt in range(max_retries):
            try:
                return self._run_download(url, custom_hook=custom_hook)
            except Exception as e:
                error_str = str(e).lower()
                is_youtube_error = any(x in error_str for x in ["innertube_context", "getpot", "keyerror", "403", "429"])
                is_youtube_url = "youtube.com" in url.lower() or "youtu.be" in url.lower()
                
                if is_youtube_error and attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                elif is_youtube_url and attempt >= max_retries - 1:
                    return self._download_youtube_pytube(url, custom_hook)
                else:
                    raise

    def _download_youtube_pytube(self, url, custom_hook=None):
        try:
            from pytube import YouTube
            path = self.path_input.get().strip()
            yt = YouTube(url)
            stream = yt.streams.filter(progressive=True, file_extension='mp4').first()
            if not stream:
                stream = yt.streams.get_highest_resolution()
            filepath = stream.download(output_path=path)
            return yt.title, filepath
        except Exception as e:
            raise Exception(f"Erreur Fallback Pytube: {str(e)}")

    def _run_download(self, url, custom_hook=None):
        path = self.path_input.get().strip()
        fmt = self.format_var.get()
        quality = self.quality_var.get()
        resolution = self.resolution_var.get()
        
        os.makedirs(path, exist_ok=True)

        ffmpeg_bin = CURRENT_DIR if (os.path.exists(os.path.join(CURRENT_DIR, "ffmpeg.exe")) or os.path.exists(os.path.join(CURRENT_DIR, "ffmpeg"))) else None

        hooks = [custom_hook] if custom_hook else [self.progress_hook]
        
        ydl_opts = {
            'outtmpl': os.path.join(path, '%(title).100s.%(ext)s'),
            'windowsfilenames': True,
            'trim_file_name': 100,
            'progress_hooks': hooks,
            'concurrent_fragment_downloads': 16,
            'fragment_retries': 15,
            'retries': 10,
            'socket_timeout': 30,
            'noplaylist': True,
            'no_warnings': True,
            
            # ──── FIX CRITIQUE INNERTUBE_CONTEXT & GetPOT ────
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'ios', 'mweb', 'tv_embedded'], # Évite le client web standard instable
                    'skip': ['dash', 'hls']
                }
            },
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                'Accept-Language': 'en-US,en;q=0.9',
            }
        }

        if ffmpeg_bin:
            ydl_opts['ffmpeg_location'] = ffmpeg_bin

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
                'format': 'bestvideo+bestaudio/best',
                'merge_output_format': 'webm'
            })
        else:
            ydl_opts.update({
                'format': 'bestvideo[vcodec^=avc1]+bestaudio[acodec^=mp4a]/bestvideo+bestaudio/best',
                'merge_output_format': 'mp4',
            })

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            if fmt == "MP4":
                status_cb = lambda msg: self.root.after(
                    0, lambda: self.status_label.configure(text=msg, text_color=WARNING_C)
                )
                ydl.add_post_processor(StreamingRecodePP(downloader=ydl, ffmpeg_bin=ffmpeg_bin, status_cb=status_cb, quality=quality, resolution=resolution))

            info = ydl.extract_info(url, download=True)
            title = info.get('title', 'Vidéo') if info else 'Vidéo'
            filepath = info.get('filepath') if info and info.get('filepath') else (ydl.prepare_filename(info) if info else '')

        return title, filepath

    def download_video(self):
        try:
            title, filepath = self._run_download_with_hook(self.url_input.get().strip())
            self.root.after(0, self._on_download_success, title, filepath)
        except Exception as e:
            if not self.stop_download:
                error_msg = str(e)
                self.root.after(0, lambda msg=error_msg: messagebox.showerror("Erreur", msg))
        finally:
            self.is_processing = False
            self.root.after(0, self._reset_buttons)

    def _on_download_success(self, title="Vidéo", filepath=""):
        self.progress_bar.set(1.0)
        self.pct_label.configure(text="100%")
        self.status_label.configure(text="✅ Compatible Tout Réseau, Premiere & Tricaster !", text_color=SUCCESS)
        self.add_history_entry(title, filepath)

    def _reset_buttons(self):
        self.btn_download.configure(state="normal")
        self.btn_cancel.configure(state="disabled", fg_color=BG_PANEL)


if __name__ == "__main__":
    root = ctk.CTk()
    app = ViddRopApp(root)
    root.mainloop()