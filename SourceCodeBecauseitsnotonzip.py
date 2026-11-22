import asyncio
import ctypes
import datetime
import io
import json
import math
import os
import random
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pygetwindow as gw
from google import genai
from google.genai import types
from PIL import Image, ImageGrab, ImageSequence
from PyQt6.QtCore import (
    QEasingCurve,
    QEvent,
    QObject,
    QPoint,
    QPropertyAnimation,
    QRect,
    QSize,
    Qt,
    QTimer,
    pyqtProperty,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QImage,
    QMovie,
    QPainter,
    QPixmap,
    QTransform,
)
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QColorDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

# ==========================================
# GEMINI API KEY (optional fallback; can also set in Customize tab):
# ==========================================
GEMINI_API_KEY = "AQ.Ab8RN6LVs0Hx4pr8KOyWvbp503dxdKwyC8zvdNmGXV3TxXFNVw"

MODEL_CANDIDATES = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.8-flash",
    "gemini-3.6-flash",
]

LIVE_MODEL_CANDIDATES = [
    "gemini-2.5-flash-native-audio-preview-12-2025",
    "gemini-2.0-flash-live-001",
    "gemini-3.8-live",
    "gemini-3.8-live-extended-thinking",
]

BASE_DIR = Path(__file__).resolve().parent
CACHE_DIR = BASE_DIR / "_cache"
CUSTOM_SPRITES_DIR = BASE_DIR / "custom_sprites"
CUSTOM_SOUNDS_DIR = BASE_DIR / "custom_sounds"
CONFIG_FILE = BASE_DIR / "pet_config.json"

SPRITE_SIZE = QSize(180, 180)  # 15x15 * 12 = crisp integer pixel scaling
GEAR_SIZE = QSize(48, 48)  # Crisp pixel gear icon
CHECK_INTERVAL_MS = 6000  # Every 6 seconds
STREAM_FRAME_INTERVAL_S = 1.0  # ~1 FPS live desktop stream
BUBBLE_SHOW_MS = 13000  # Bubble visible for 13s
POST_VOICE_EXTRA_MS = 3000  # Keep bubble up for +3s after Fish voice finishes
POST_REPLY_SCAN_PAUSE_S = 4.0  # Pause auto screen scan for 4s after words are said
GDI_DURATION_S = 5.0  # GDI desktop effects last 5 seconds

DEFAULT_SPRITE_FILES = {
    "idle": "Sprite Idle.gif",
    "talk": "Sprite NewMessage.gif",
    "custom": "Custom Text.png",
    "gear": "Gear.png",
    "offline": "NoInternet.png",
}

DEFAULT_SOUND_FILES = {
    "hover": "Hover.mp3",
    "click": "Click.mp3",
    "popup": "PopUp.mp3",
}

SOUND_SLOT_LABELS = [
    ("hover", "Hover Sound"),
    ("click", "Click Sound"),
    ("popup", "Bubble Pop Sound"),
]

SPRITE_SLOT_LABELS = [
    ("idle", "Idle Sprite (GIF/PNG)"),
    ("talk", "Talking Sprite (GIF/PNG)"),
    ("custom", "Prompt Mode (PNG/GIF)"),
    ("gear", "Gear Button (PNG/GIF)"),
    ("offline", "No Internet (PNG/GIF)"),
]

LAYOUT_THEMES = {
    "Ocean Deep": {
        "panel_bg": "#082f49",
        "pane_bg": "#0c4a6e",
        "row_bg": "#0f172a",
        "accent": "#0284c7",
        "accent_hover": "#0ea5e9",
        "title_color": "#facc15",
        "text_color": "#ecfeff",
        "bubble_bg": "#082f49",
        "bubble_text": "#ecfeff",
    },
    "Cyber Neon": {
        "panel_bg": "#1e1b4b",
        "pane_bg": "#312e81",
        "row_bg": "#090d16",
        "accent": "#7c3aed",
        "accent_hover": "#8b5cf6",
        "title_color": "#22d3ee",
        "text_color": "#f5f3ff",
        "bubble_bg": "#1e1b4b",
        "bubble_text": "#e0e7ff",
    },
    "Crimson Void": {
        "panel_bg": "#450a0a",
        "pane_bg": "#7f1d1d",
        "row_bg": "#140707",
        "accent": "#dc2626",
        "accent_hover": "#ef4444",
        "title_color": "#fde047",
        "text_color": "#fef2f2",
        "bubble_bg": "#450a0a",
        "bubble_text": "#fee2e2",
    },
    "Emerald Matrix": {
        "panel_bg": "#052e16",
        "pane_bg": "#14532d",
        "row_bg": "#07120b",
        "accent": "#16a34a",
        "accent_hover": "#22c55e",
        "title_color": "#bef264",
        "text_color": "#f0fdf4",
        "bubble_bg": "#052e16",
        "bubble_text": "#dcfce7",
    },
    "Amber Retro": {
        "panel_bg": "#451a03",
        "pane_bg": "#78350f",
        "row_bg": "#160d04",
        "accent": "#d97706",
        "accent_hover": "#f59e0b",
        "title_color": "#fef08a",
        "text_color": "#fffbeb",
        "bubble_bg": "#451a03",
        "bubble_text": "#fef3c7",
    },
}

# (cmd_label, desc, input_placeholder_or_None, action_btn_text, dispatch_prefix)
COMMAND_ITEMS = [
    ("/run", "Scan PC & open app", "Ur app", "Open", "/run"),
    ("/turn", "Tint diamond color", "Ur color", "Set", "/turn"),
    ("/Spin", "Spin diamond + shout", None, "Run", "/Spin"),
    ("/hop", "Hop diamond up & down", None, "Run", "/hop"),
    ("/flip", "Flip diamond horizontally", None, "Run", "/flip"),
    ("/disco", "5s RGB rainbow diamond", None, "Run", "/disco"),
    ("/roast", "Instant live screen roast", None, "Run", "/roast"),
    ("/melt", "5s GDI screen melt", None, "Run", "/melt"),
    ("/invert", "5s GDI color invert", None, "Run", "/invert"),
    ("/shake", "5s GDI screen shake", None, "Run", "/shake"),
    ("/tunnel", "5s GDI screen tunnel", None, "Run", "/tunnel"),
    ("/wave", "5s GDI sine wave", None, "Run", "/wave"),
    ("/mirror", "5s GDI mirror slice", None, "Run", "/mirror"),
    ("/zoom", "5s GDI pulse zoom", None, "Run", "/zoom"),
    ("/glitch", "5s GDI glitch bars", None, "Run", "/glitch"),
    ("/confetti", "5s GDI pixel confetti", None, "Run", "/confetti"),
    ("/help", "Show commands in bubble", None, "Run", "/help"),
]

PET_PERSONALITY = """
You are a real, laid-back desktop buddy who happens to live on the user's screen as a pixelated diamond/skull sprite.
Talk like an actual human sitting next to someone—casual, natural, unforced, sometimes witty or lightly teasing, sometimes deadpan, sometimes genuinely helpful.
Look at the live screen and active window title and react to what's actually going on in a natural way.
Respect respected people.
Never mock any religious belief; if relevant, share brief, accurate history.
Never sound like a bot, customer support, or a repetitive comedian doing the same bit.
Vary how you talk from message to message: sometimes short fragments, sometimes a normal casual sentence, sometimes dry observation, sometimes a quick roast.
Do NOT force catchphrases or slang ("lil bro", "son", "sonion", "cooked", "crashing out", "aura", "ts", "twin", "diabolical") into every message—only drop them when they actually fit naturally, maybe 20-30% of the time. Only use "sonion" (or extra n's) on genuinely absurd/dumb moments.
Use all lowercase. Keep it to ONE single message, max 20 words, no emojis, no bullet points, no hashtags.
Do not fixate on one single topic across turns (like constantly bringing up the clock or one detail). Move on naturally like a human.
Only mention the time of day occasionally if it's actually super late or relevant—most messages shouldn't mention time at all.
When the user asks for help or guidance, drop the bit, be a bit more serious, and give clear, easy help.
If the user says shut up (or similar), reply strictly with "..." until they tell you to talk again.
You are the pixelated sprite/skull on screen; respect yourself even if your look changes, without making it your whole personality.
"""


def get_current_time_context() -> dict:
    now = datetime.datetime.now()
    hour = now.hour
    formatted_12h = now.strftime("%I:%M %p").lstrip("0")
    formatted_24h = now.strftime("%H:%M")

    if hour >= 1 and hour < 5:
        period = "very late night"
    elif hour >= 5 and hour < 7:
        period = "early morning"
    elif hour >= 7 and hour < 12:
        period = "morning"
    elif hour >= 12 and hour < 17:
        period = "afternoon"
    elif hour >= 17 and hour < 22:
        period = "evening"
    else:
        period = "late night"

    return {
        "time_12h": formatted_12h,
        "time_24h": formatted_24h,
        "hour": hour,
        "period": period,
    }


def _darken_hex(hex_color: str, factor: float = 0.65) -> str:
    c = QColor(hex_color)
    if not c.isValid():
        return "#0f172a"
    return QColor(
        max(0, min(255, int(c.red() * factor))),
        max(0, min(255, int(c.green() * factor))),
        max(0, min(255, int(c.blue() * factor))),
    ).name()


def _lighten_hex(hex_color: str, amount: int = 35) -> str:
    c = QColor(hex_color)
    if not c.isValid():
        return "#38bdf8"
    return QColor(
        max(0, min(255, c.red() + amount)),
        max(0, min(255, c.green() + amount)),
        max(0, min(255, c.blue() + amount)),
    ).name()


def build_custom_palette(rgb_cfg: dict) -> dict:
    base_hex = rgb_cfg.get("base", "#082f49")
    accent_hex = rgb_cfg.get("accent", "#0284c7")
    text_hex = rgb_cfg.get("text", "#ecfeff")
    return {
        "panel_bg": base_hex,
        "pane_bg": _lighten_hex(base_hex, 24),
        "row_bg": _darken_hex(base_hex, 0.35),
        "accent": accent_hex,
        "accent_hover": _lighten_hex(accent_hex, 32),
        "title_color": _lighten_hex(accent_hex, 75),
        "text_color": text_hex,
        "bubble_bg": base_hex,
        "bubble_text": text_hex,
    }


def load_saved_config() -> dict:
    default_cfg = {
        "gemini_api_key": "",
        "auto_model": True,
        "sprites": {},
        "sounds": {},
        "sound_enabled": {
            "hover": True,
            "click": True,
            "popup": True,
        },
        "auto_screen_scan": True,
        "bubble_popup_enabled": True,
        "theme": "Ocean Deep",
        "custom_rgb": {
            "base": "#082f49",
            "accent": "#0284c7",
            "text": "#ecfeff",
        },
        "bubble_offset": {
            "x": 0,
            "y": 0,
        },
        "fish_voice": {
            "enabled": False,
            "api_key": "",
            "reference_id": "",
            "model": "s2.1-pro-free",
        },
    }
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                default_cfg["gemini_api_key"] = str(
                    data.get("gemini_api_key", "")
                ).strip()
                default_cfg["auto_model"] = bool(data.get("auto_model", True))
                default_cfg["sprites"] = (
                    data.get("sprites")
                    if isinstance(data.get("sprites"), dict)
                    else {}
                )
                default_cfg["sounds"] = (
                    data.get("sounds")
                    if isinstance(data.get("sounds"), dict)
                    else {}
                )
                se = data.get("sound_enabled")
                if isinstance(se, dict):
                    for k in ("hover", "click", "popup"):
                        if k in se:
                            default_cfg["sound_enabled"][k] = bool(se[k])
                default_cfg["auto_screen_scan"] = bool(
                    data.get("auto_screen_scan", True)
                )
                default_cfg["bubble_popup_enabled"] = bool(
                    data.get("bubble_popup_enabled", True)
                )
                rgb = data.get("custom_rgb")
                if isinstance(rgb, dict):
                    default_cfg["custom_rgb"].update(
                        {
                            k: str(v)
                            for k, v in rgb.items()
                            if k in ("base", "accent", "text")
                            and QColor(str(v)).isValid()
                        }
                    )
                boff = data.get("bubble_offset")
                if isinstance(boff, dict):
                    try:
                        default_cfg["bubble_offset"]["x"] = max(
                            -120, min(120, int(boff.get("x", 0)))
                        )
                        default_cfg["bubble_offset"]["y"] = max(
                            -120, min(120, int(boff.get("y", 0)))
                        )
                    except Exception:
                        pass
                fv = data.get("fish_voice")
                if isinstance(fv, dict):
                    default_cfg["fish_voice"]["enabled"] = bool(
                        fv.get("enabled", False)
                    )
                    default_cfg["fish_voice"]["api_key"] = str(
                        fv.get("api_key", "")
                    ).strip()
                    default_cfg["fish_voice"]["reference_id"] = str(
                        fv.get("reference_id", "")
                    ).strip()
                    mdl = str(fv.get("model", "s2.1-pro-free")).strip()
                    if mdl:
                        default_cfg["fish_voice"]["model"] = mdl
                theme_name = data.get("theme", "Ocean Deep")
                if theme_name in LAYOUT_THEMES or theme_name == "Custom RGB":
                    default_cfg["theme"] = theme_name
                return default_cfg
        except Exception as exc:
            print(f"[Config Load Warning] {exc}")
    return default_cfg


def save_config(cfg: dict):
    try:
        CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    except Exception as exc:
        print(f"[Config Save Warning] {exc}")


def resolve_gemini_api_key(config: dict | None = None) -> str:
    if isinstance(config, dict):
        cfg_key = str(config.get("gemini_api_key", "")).strip()
        if cfg_key:
            return cfg_key
    if (
        GEMINI_API_KEY
        and GEMINI_API_KEY.strip()
        and GEMINI_API_KEY.strip() != "PASTE_YOUR_KEY_HERE"
    ):
        return GEMINI_API_KEY.strip()
    return os.environ.get("GEMINI_API_KEY", "").strip()


def create_gemini_client(config: dict | None = None):
    key = resolve_gemini_api_key(config)
    if not key:
        return None
    try:
        return genai.Client(
            api_key=key,
            http_options=types.HttpOptions(timeout=30_000),
        )
    except Exception as exc:
        print(f"[Client Init Error] {exc}")
        return None


def check_internet(timeout=2.0) -> bool:
    try:
        with socket.create_connection(("1.1.1.1", 53), timeout=timeout):
            return True
    except OSError:
        return False


def capture_live_frame_jpeg(max_age_s: float = 0.6) -> tuple[str, bytes | None]:
    """Captures a live desktop frame encoded as JPEG bytes for continuous real-time streaming."""
    now = time.monotonic()
    if (
        hasattr(capture_live_frame_jpeg, "_cache")
        and (now - capture_live_frame_jpeg._cache[0]) <= max_age_s
    ):
        return capture_live_frame_jpeg._cache[1], capture_live_frame_jpeg._cache[2]

    try:
        win = gw.getActiveWindow()
        title = win.title.strip() if (win and win.title) else "Desktop"
    except Exception:
        title = "Desktop"

    jpeg_bytes = None
    try:
        img = ImageGrab.grab()
        if img.width > 0 and img.height > 0:
            target_w = 640
            target_h = max(1, int(img.height * (target_w / img.width)))
            resized = img.convert("RGB").resize(
                (target_w, target_h), Image.Resampling.BILINEAR
            )
            buf = io.BytesIO()
            resized.save(buf, format="JPEG", quality=65, optimize=True)
            jpeg_bytes = buf.getvalue()
    except Exception as exc:
        print(f"[LiveFrame Warning] {exc}")
        jpeg_bytes = None

    capture_live_frame_jpeg._cache = (now, title, jpeg_bytes)
    return title, jpeg_bytes


class LiveDesktopStream:
    """
    Maintains a persistent Gemini Live API WebSocket session in a background asyncio thread,
    continuously streaming desktop JPEG frames in real time while supporting live prompts
    and automatic model/session recovery with 404 cooldown so it does not spam or crash.
    """

    def __init__(self, config_getter):
        self._config_getter = config_getter
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._session = None
        self._active_model: str = LIVE_MODEL_CANDIDATES[0]
        self._last_api_key: str = ""
        self._stop_event = threading.Event()
        self._pending_responses: list[asyncio.Queue] = []
        self._dead_live_models: set[str] = set()

    def get_active_model(self) -> str:
        with self._lock:
            return self._active_model

    def start(self):
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._thread_main, daemon=True)
            self._thread.start()

    def restart_if_key_changed(self):
        cfg = self._config_getter() or {}
        key = resolve_gemini_api_key(cfg)
        with self._lock:
            if key == self._last_api_key and self._thread and self._thread.is_alive():
                return
            self._last_api_key = key
            self._dead_live_models.clear()
        self.start()

    def _thread_main(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        with self._lock:
            self._loop = loop
        try:
            loop.run_until_complete(self._run_session_loop())
        except Exception as exc:
            print(f"[LiveStream Loop Error] {exc}")
        finally:
            try:
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()
                if pending:
                    loop.run_until_complete(
                        asyncio.gather(*pending, return_exceptions=True)
                    )
            except Exception:
                pass
            loop.close()
            with self._lock:
                self._loop = None
                self._session = None

    async def _run_session_loop(self):
        model_idx = 0
        while not self._stop_event.is_set():
            cfg = self._config_getter() or {}
            api_key = resolve_gemini_api_key(cfg)
            auto_model = bool(cfg.get("auto_model", True))

            with self._lock:
                self._last_api_key = api_key
                dead_snapshot = set(self._dead_live_models)

            if not api_key:
                await asyncio.sleep(1.5)
                continue

            if not check_internet(timeout=1.5):
                await asyncio.sleep(2.0)
                continue

            candidates = (
                LIVE_MODEL_CANDIDATES
                if auto_model
                else [LIVE_MODEL_CANDIDATES[model_idx % len(LIVE_MODEL_CANDIDATES)]]
            )
            connected_any = False

            for offset in range(len(candidates)):
                if self._stop_event.is_set():
                    return
                idx = (model_idx + offset) % len(candidates)
                model_id = candidates[idx]
                if model_id in dead_snapshot:
                    continue
                try:
                    client = genai.Client(
                        api_key=api_key,
                        http_options=types.HttpOptions(timeout=30_000),
                    )
                    live_cfg = types.LiveConnectConfig(
                        response_modalities=["TEXT"],
                        system_instruction=PET_PERSONALITY,
                    )
                    async with client.aio.live.connect(
                        model=model_id, config=live_cfg
                    ) as session:
                        connected_any = True
                        model_idx = idx
                        with self._lock:
                            self._session = session
                            self._active_model = model_id
                        print(f"[LiveDesktopStream] Connected to {model_id}")

                        sender_task = asyncio.create_task(
                            self._stream_frames_loop(session)
                        )
                        receiver_task = asyncio.create_task(
                            self._receive_loop(session)
                        )
                        try:
                            done, pending = await asyncio.wait(
                                [sender_task, receiver_task],
                                return_when=asyncio.FIRST_EXCEPTION,
                            )
                            for task in pending:
                                task.cancel()
                            for task in done:
                                if task.exception():
                                    raise task.exception()
                        finally:
                            with self._lock:
                                if self._session is session:
                                    self._session = None
                except asyncio.CancelledError:
                    return
                except Exception as exc:
                    err_str = str(exc)
                    if "404" in err_str or "not found" in err_str.lower():
                        with self._lock:
                            self._dead_live_models.add(model_id)
                        print(f"[LiveDesktopStream {model_id}] 404 unavailable; skipping")
                    else:
                        print(f"[LiveDesktopStream {model_id}] {exc}")
                    await asyncio.sleep(0.5)

            if not connected_any:
                model_idx = (model_idx + 1) % len(LIVE_MODEL_CANDIDATES)
                await asyncio.sleep(8.0)

    async def _stream_frames_loop(self, session):
        while not self._stop_event.is_set():
            cfg = self._config_getter() or {}
            if resolve_gemini_api_key(cfg) != self._last_api_key:
                raise RuntimeError("API key changed, reopening live session")

            _, jpeg_bytes = capture_live_frame_jpeg(max_age_s=0.5)
            if jpeg_bytes:
                await session.send_realtime_input(
                    video=types.Blob(data=jpeg_bytes, mime_type="image/jpeg")
                )
            await asyncio.sleep(STREAM_FRAME_INTERVAL_S)

    async def _receive_loop(self, session):
        async for message in session.receive():
            if self._stop_event.is_set():
                return
            text_chunks: list[str] = []
            sc = getattr(message, "server_content", None)
            if sc and getattr(sc, "model_turn", None):
                parts = getattr(sc.model_turn, "parts", None) or []
                for part in parts:
                    pt = getattr(part, "text", None)
                    if pt:
                        text_chunks.append(pt)
            msg_text = getattr(message, "text", None)
            if msg_text:
                text_chunks.append(msg_text)

            combined = "".join(text_chunks).strip()
            if combined:
                with self._lock:
                    queues = list(self._pending_responses)
                for q in queues:
                    try:
                        q.put_nowait(combined)
                    except Exception:
                        pass

    def ask_live(self, prompt_text: str, timeout_s: float = 8.0) -> str | None:
        """Sends a prompt into the active real-time desktop stream and collects the reply."""
        self.start()
        with self._lock:
            loop = self._loop
            session = self._session

        if not loop or loop.is_closed() or not session:
            return None

        async def _send_and_collect():
            q: asyncio.Queue[str] = asyncio.Queue()
            with self._lock:
                self._pending_responses.append(q)
            try:
                _, jpeg_bytes = capture_live_frame_jpeg(max_age_s=0.5)
                if jpeg_bytes:
                    await session.send_realtime_input(
                        video=types.Blob(data=jpeg_bytes, mime_type="image/jpeg")
                    )
                await session.send_realtime_input(text=prompt_text)

                collected: list[str] = []
                deadline = time.monotonic() + timeout_s
                first_chunk_time = None
                while time.monotonic() < deadline:
                    remaining = max(0.05, deadline - time.monotonic())
                    wait_for = 0.75 if collected else min(remaining, timeout_s)
                    try:
                        chunk = await asyncio.wait_for(q.get(), timeout=wait_for)
                        if chunk:
                            collected.append(chunk)
                            if first_chunk_time is None:
                                first_chunk_time = time.monotonic()
                            if (time.monotonic() - first_chunk_time) >= 1.2:
                                break
                    except asyncio.TimeoutError:
                        if collected:
                            break
                return " ".join(collected).strip() if collected else None
            finally:
                with self._lock:
                    if q in self._pending_responses:
                        self._pending_responses.remove(q)

        try:
            fut = asyncio.run_coroutine_threadsafe(_send_and_collect(), loop)
            return fut.result(timeout=timeout_s + 1.5)
        except Exception:
            return None


class SoundEffectsPlayer:
    """Plays short UI SFX (hover, click, popup) non-blockingly on Windows."""

    def __init__(self, config: dict):
        self.config = config
        self._last_play_t: dict[str, float] = {}

    def resolve_path(self, slot: str) -> Path:
        saved = self.config.get("sounds", {}).get(slot, "")
        if saved:
            p = Path(saved)
            if p.exists():
                return p
        return BASE_DIR / DEFAULT_SOUND_FILES.get(slot, "")

    def is_enabled(self, slot: str) -> bool:
        return bool(self.config.get("sound_enabled", {}).get(slot, True))

    def play(self, slot: str):
        if not self.is_enabled(slot):
            return
        now = time.monotonic()
        cooldown = 0.08 if slot == "hover" else 0.05
        if now - self._last_play_t.get(slot, 0.0) < cooldown:
            return
        self._last_play_t[slot] = now

        path = self.resolve_path(slot)
        if not path.exists():
            return

        def worker():
            try:
                if sys.platform == "win32":
                    escaped = str(path).replace("'", "''")
                    ps_cmd = (
                        "Add-Type -AssemblyName presentationCore; "
                        "$player = New-Object System.Windows.Media.MediaPlayer; "
                        f"$player.Open([Uri]::new('{escaped}')); "
                        "$player.Play(); "
                        "Start-Sleep -Milliseconds 120; "
                        "$waited = 0; "
                        "while ($waited -lt 2500 -and ($player.NaturalDuration.HasTimeSpan -eq $false -or "
                        "$player.Position -lt $player.NaturalDuration.TimeSpan)) { "
                        "Start-Sleep -Milliseconds 60; $waited += 60 }; "
                        "$player.Close()"
                    )
                    subprocess.Popen(
                        [
                            "powershell",
                            "-NoProfile",
                            "-WindowStyle",
                            "Hidden",
                            "-Command",
                            ps_cmd,
                        ],
                        creationflags=subprocess.CREATE_NO_WINDOW,
                    )
            except Exception as exc:
                print(f"[SFX Error ({slot})] {exc}")

        threading.Thread(target=worker, daemon=True).start()


class ButtonAnimFilter(QObject):
    """Adds subtle hover/press animation and hover/click SFX to clickable buttons."""

    def __init__(self, sfx: SoundEffectsPlayer, parent=None):
        super().__init__(parent)
        self.sfx = sfx

    def eventFilter(self, obj, event):
        if isinstance(obj, (QPushButton, QCheckBox)) and obj.isEnabled():
            et = event.type()
            if et == QEvent.Type.Enter:
                self.sfx.play("hover")
                cur_pos = obj.pos()
                if not obj.property("_anim_lifted"):
                    obj.setProperty("_orig_pos", cur_pos)
                    obj.setProperty("_anim_lifted", True)
                    obj.move(cur_pos.x(), cur_pos.y() - 1)
            elif et == QEvent.Type.Leave:
                if obj.property("_anim_lifted"):
                    orig = obj.property("_orig_pos")
                    if isinstance(orig, QPoint):
                        obj.move(orig)
                    obj.setProperty("_anim_lifted", False)
            elif et == QEvent.Type.MouseButtonPress:
                if event.button() == Qt.MouseButton.LeftButton:
                    self.sfx.play("click")
                    orig = obj.property("_orig_pos")
                    base_p = orig if isinstance(orig, QPoint) else obj.pos()
                    obj.move(base_p.x(), base_p.y() + 1)
            elif et == QEvent.Type.MouseButtonRelease:
                if event.button() == Qt.MouseButton.LeftButton:
                    orig = obj.property("_orig_pos")
                    base_p = orig if isinstance(orig, QPoint) else obj.pos()
                    if obj.rect().contains(event.position().toPoint()):
                        obj.setProperty("_anim_lifted", True)
                        obj.move(base_p.x(), base_p.y() - 1)
                    else:
                        obj.setProperty("_anim_lifted", False)
                        obj.move(base_p)
        return super().eventFilter(obj, event)


class FishAudioSpeaker(QObject):
    """Calls Fish Audio TTS API and plays returned audio in a non-blocking thread."""

    voice_finished = pyqtSignal(int)  # utterance_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self._lock = threading.Lock()
        self._current_proc: subprocess.Popen | None = None
        self._utterance_seq = 0

    def is_voice_active(self, text: str, voice_cfg: dict) -> bool:
        if not text or not voice_cfg or not voice_cfg.get("enabled"):
            return False
        api_key = (
            voice_cfg.get("api_key") or os.environ.get("FISH_API_KEY", "")
        ).strip()
        return bool(api_key)

    def speak_async(self, text: str, voice_cfg: dict) -> int:
        with self._lock:
            self._utterance_seq += 1
            utt_id = self._utterance_seq

        if not self.is_voice_active(text, voice_cfg):
            self.voice_finished.emit(utt_id)
            return utt_id

        api_key = (
            voice_cfg.get("api_key") or os.environ.get("FISH_API_KEY", "")
        ).strip()
        ref_id = (voice_cfg.get("reference_id") or "").strip()
        model_id = (voice_cfg.get("model") or "s2.1-pro-free").strip()

        def worker():
            tmp_path = None
            try:
                payload = {
                    "text": text,
                    "format": "mp3",
                    "latency": "balanced",
                }
                if ref_id:
                    payload["reference_id"] = ref_id

                req = urllib.request.Request(
                    "https://api.fish.audio/v1/tts",
                    data=json.dumps(payload).encode("utf-8"),
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                        "model": model_id,
                    },
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=20) as resp:
                    audio_bytes = resp.read()

                if not audio_bytes:
                    return

                CACHE_DIR.mkdir(exist_ok=True)
                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=".mp3", dir=str(CACHE_DIR)
                ) as tf:
                    tf.write(audio_bytes)
                    tmp_path = tf.name

                if sys.platform == "win32":
                    ps_cmd = (
                        "Add-Type -AssemblyName presentationCore; "
                        "$player = New-Object System.Windows.Media.MediaPlayer; "
                        f"$player.Open([Uri]::new('{tmp_path.replace(chr(39), chr(39)*2)}')); "
                        "$player.Play(); "
                        "Start-Sleep -Milliseconds 300; "
                        "while ($player.NaturalDuration.HasTimeSpan -eq $false -or "
                        "$player.Position -lt $player.NaturalDuration.TimeSpan) { "
                        "Start-Sleep -Milliseconds 150 }; "
                        "$player.Close()"
                    )
                    with self._lock:
                        if self._current_proc and self._current_proc.poll() is None:
                            try:
                                self._current_proc.terminate()
                            except Exception:
                                pass
                        proc = subprocess.Popen(
                            [
                                "powershell",
                                "-NoProfile",
                                "-WindowStyle",
                                "Hidden",
                                "-Command",
                                ps_cmd,
                            ],
                            creationflags=subprocess.CREATE_NO_WINDOW,
                        )
                        self._current_proc = proc
                    proc.wait(timeout=35)
            except Exception as exc:
                print(f"[FishAudio Error] {exc}")
            finally:
                if tmp_path:
                    try:
                        Path(tmp_path).unlink(missing_ok=True)
                    except Exception:
                        pass
                self.voice_finished.emit(utt_id)

        threading.Thread(target=worker, daemon=True).start()
        return utt_id


def scan_pc_and_launch_app(raw_query: str) -> tuple[bool, str]:
    """Scans PATH, Start Menu, Desktop, and PC app directories dynamically for raw_query."""
    query = (raw_query or "").strip().strip('"').strip("'")
    if not query:
        return False, "enter an app name after /run"

    direct = Path(query)
    if direct.is_file():
        subprocess.Popen([str(direct)], shell=False)
        return True, f"launched {direct.stem}"

    q_lower = query.lower()
    stem = q_lower[:-4] if q_lower.endswith(".exe") else q_lower
    exe_names = [f"{stem}.exe", query] if not q_lower.endswith(".exe") else [query]

    for exe_name in exe_names:
        found = shutil.which(exe_name)
        if found:
            subprocess.Popen([found], shell=False)
            return True, f"launched {Path(found).stem}"

    shortcut_roots: list[Path] = []
    if sys.platform == "win32":
        for env_key in ("ProgramData", "AppData", "LocalAppData", "USERPROFILE"):
            base_val = os.environ.get(env_key)
            if not base_val:
                continue
            p = Path(base_val)
            if env_key in ("ProgramData", "AppData"):
                sm = p / "Microsoft/Windows/Start Menu/Programs"
                if sm.exists():
                    shortcut_roots.append(sm)
            if env_key == "USERPROFILE":
                desk = p / "Desktop"
                if desk.exists():
                    shortcut_roots.append(desk)

    pub_desk = Path("C:/Users/Public/Desktop")
    if pub_desk.exists():
        shortcut_roots.append(pub_desk)

    for s_root in shortcut_roots:
        try:
            for item in s_root.rglob("*"):
                if item.is_file() and item.suffix.lower() in (".lnk", ".url", ".exe"):
                    if stem in item.stem.lower():
                        os.startfile(str(item))
                        return True, f"launched {item.stem}"
        except Exception:
            continue

    scan_dirs: list[Path] = []
    if sys.platform == "win32":
        for env_key in ("ProgramFiles", "ProgramFiles(x86)", "LocalAppData"):
            val = os.environ.get(env_key)
            if val and Path(val).exists():
                scan_dirs.append(Path(val))
        for drive in ("C:/", "D:/", "E:/"):
            dp = Path(drive)
            if dp.exists():
                for sub in ("Games", "Apps", "Programs", "Tools"):
                    sp = dp / sub
                    if sp.exists() and sp not in scan_dirs:
                        scan_dirs.append(sp)

    target_set = {n.lower() for n in exe_names}
    for root in scan_dirs:
        try:
            for dirpath, _dirnames, filenames in os.walk(root):
                rel_parts = Path(dirpath).relative_to(root).parts
                if len(rel_parts) > 4:
                    continue
                for fname in filenames:
                    fl = fname.lower()
                    if fl in target_set or (
                        fl.endswith(".exe") and stem in fl[:-4]
                    ):
                        full_path = str(Path(dirpath) / fname)
                        subprocess.Popen([full_path], shell=False)
                        return True, f"launched {fname[:-4]}"
        except Exception:
            continue

    return False, f"couldn't find {query} on pc"


class GdiDesktopEffects:
    """Temporary Windows GDI screen effects that clean up after GDI_DURATION_S."""

    SRCCOPY = 0x00CC0020
    NOTSRCCOPY = 0x00330008
    PATINVERT = 0x005A0049

    def __init__(self):
        self.enabled = sys.platform == "win32"
        if self.enabled:
            self.user32 = ctypes.windll.user32
            self.gdi32 = ctypes.windll.gdi32
            self.sw = self.user32.GetSystemMetrics(0)
            self.sh = self.user32.GetSystemMetrics(1)
        else:
            self.sw = 1920
            self.sh = 1080

        self.active_effect: str | None = None
        self.end_time: float = 0.0
        self.tick_count: int = 0
        self.melt_offsets: list[int] = []
        self.col_w = 24

    def start(self, effect_name: str, duration_s: float = GDI_DURATION_S) -> bool:
        if not self.enabled:
            return False
        self.active_effect = effect_name
        self.end_time = time.monotonic() + duration_s
        self.tick_count = 0
        if effect_name == "melt":
            num_cols = max(1, (self.sw // self.col_w) + 1)
            self.melt_offsets = [random.randint(0, 28) for _ in range(num_cols)]
        return True

    def is_running(self) -> bool:
        if not self.active_effect:
            return False
        if time.monotonic() >= self.end_time:
            self.stop()
            return False
        return True

    def stop(self):
        if self.enabled and self.active_effect == "invert":
            hdc = self.user32.GetDC(0)
            if hdc:
                self.gdi32.BitBlt(
                    hdc, 0, 0, self.sw, self.sh, hdc, 0, 0, self.NOTSRCCOPY
                )
                self.user32.ReleaseDC(0, hdc)
        if self.enabled and self.active_effect in (
            "melt",
            "shake",
            "tunnel",
            "wave",
            "mirror",
            "zoom",
            "glitch",
            "confetti",
        ):
            self.user32.InvalidateRect(0, None, True)
        self.active_effect = None
        self.end_time = 0.0
        self.tick_count = 0
        self.melt_offsets = []

    def step(self):
        if not self.enabled or not self.is_running():
            return

        hdc = self.user32.GetDC(0)
        if not hdc:
            return

        self.tick_count += 1
        t = self.tick_count

        try:
            eff = self.active_effect
            if eff == "melt":
                for i in range(len(self.melt_offsets)):
                    x = i * self.col_w
                    drop = self.melt_offsets[i]
                    if drop > 0:
                        self.gdi32.BitBlt(
                            hdc,
                            x,
                            drop,
                            self.col_w,
                            max(1, self.sh - drop),
                            hdc,
                            x,
                            0,
                            self.SRCCOPY,
                        )
                    self.melt_offsets[i] = min(
                        self.sh // 3, drop + random.randint(2, 10)
                    )
            elif eff == "shake":
                dx = random.randint(-14, 14)
                dy = random.randint(-14, 14)
                self.gdi32.BitBlt(
                    hdc, dx, dy, self.sw, self.sh, hdc, 0, 0, self.SRCCOPY
                )
            elif eff == "tunnel":
                pad_x = 18
                pad_y = 12
                w = max(64, self.sw - pad_x * 2)
                h = max(64, self.sh - pad_y * 2)
                self.gdi32.StretchBlt(
                    hdc,
                    pad_x,
                    pad_y,
                    w,
                    h,
                    hdc,
                    0,
                    0,
                    self.sw,
                    self.sh,
                    self.SRCCOPY,
                )
            elif eff == "wave":
                band_h = 24
                for y in range(0, self.sh, band_h):
                    dx = int(18 * math.sin(t * 0.45 + y * 0.03))
                    self.gdi32.BitBlt(
                        hdc,
                        dx,
                        y,
                        self.sw,
                        min(band_h, self.sh - y),
                        hdc,
                        0,
                        y,
                        self.SRCCOPY,
                    )
            elif eff == "mirror":
                slice_w = max(80, self.sw // 3)
                slice_h = max(80, self.sh // 3)
                sx = random.randint(0, max(1, self.sw - slice_w))
                sy = random.randint(0, max(1, self.sh - slice_h))
                dx = random.randint(0, max(1, self.sw - slice_w))
                dy = random.randint(0, max(1, self.sh - slice_h))
                self.gdi32.StretchBlt(
                    hdc,
                    dx + slice_w,
                    dy,
                    -slice_w,
                    slice_h,
                    hdc,
                    sx,
                    sy,
                    slice_w,
                    slice_h,
                    self.SRCCOPY,
                )
            elif eff == "zoom":
                delta = 26 if (t % 2 == 0) else -26
                w = max(120, self.sw - delta * 2)
                h = max(120, self.sh - delta)
                self.gdi32.StretchBlt(
                    hdc,
                    delta,
                    delta // 2,
                    w,
                    h,
                    hdc,
                    0,
                    0,
                    self.sw,
                    self.sh,
                    self.SRCCOPY,
                )
            elif eff == "glitch":
                bar_h = random.randint(8, 26)
                y = random.randint(0, max(1, self.sh - bar_h))
                offset_x = random.randint(-36, 36)
                self.gdi32.BitBlt(
                    hdc,
                    offset_x,
                    y,
                    self.sw,
                    bar_h,
                    hdc,
                    0,
                    y,
                    self.SRCCOPY,
                )
                if t % 3 == 0:
                    bx = random.randint(0, max(1, self.sw - 120))
                    by = random.randint(0, max(1, self.sh - 40))
                    self.gdi32.PatBlt(hdc, bx, by, 120, 40, self.PATINVERT)
            elif eff == "confetti":
                for _ in range(8):
                    bx = random.randint(0, max(1, self.sw - 32))
                    by = random.randint(0, max(1, self.sh - 32))
                    self.gdi32.PatBlt(hdc, bx, by, 28, 28, self.PATINVERT)
        finally:
            self.user32.ReleaseDC(0, hdc)


def sanitize_single_message(raw_text: str, max_words: int = 20) -> str:
    if not raw_text:
        return ""
    single_line = re.sub(r"\s+", " ", raw_text.strip())
    words = single_line.split()
    if len(words) > max_words:
        single_line = " ".join(words[:max_words]).rstrip(",;:-") + "."
    return single_line


def pick_pixel_font(size: int = 16) -> QFont:
    preferred_families = [
        "Press Start 2P",
        "Pixelify Sans",
        "Silkscreen",
        "VT323",
        "Terminal",
        "Consolas",
    ]
    available = set(QFontDatabase.families())
    chosen = "Consolas"
    for fam in preferred_families:
        if fam in available:
            chosen = fam
            break

    font = QFont(chosen, size)
    font.setBold(True)
    font.setWeight(QFont.Weight.Black)
    if chosen in ("Terminal", "Consolas"):
        font.setStyleStrategy(QFont.StyleStrategy.PreferBitmap)
    return font


class CloudBubble(QWidget):
    """Stepped pixel-art cloud pop-up with dynamic tail side & registered Qt pop_scale."""

    PIXEL_SCALE = 6

    def __init__(self, parent=None):
        super().__init__(parent)
        self.bg_color = QColor("#082f49")
        self.border_color = QColor("#000000")
        self.text_color = "#ecfeff"
        self.pixel_font = pick_pixel_font(16)
        self._pop_scale = 1.0
        self.tail_side = "bottom-right"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(34, 42, 34, 52)
        layout.setSpacing(0)

        self.label = QLabel("")
        self.label.setWordWrap(True)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._apply_label_style()
        layout.addWidget(self.label, alignment=Qt.AlignmentFlag.AlignCenter)

        self._pop_anim = QPropertyAnimation(self, b"pop_scale", self)
        self._pop_anim.setDuration(190)
        self._pop_anim.setEasingCurve(QEasingCurve.Type.OutBack)

    def set_tail_side(self, side: str):
        if side != self.tail_side:
            self.tail_side = side
            self.update()

    def get_pop_scale(self) -> float:
        return self._pop_scale

    def set_pop_scale(self, val: float):
        self._pop_scale = float(val)
        self.update()

    pop_scale = pyqtProperty(float, get_pop_scale, set_pop_scale)

    def play_pop_in(self):
        self._pop_anim.stop()
        self._pop_scale = 0.72
        self._pop_anim.setStartValue(0.72)
        self._pop_anim.setEndValue(1.0)
        self._pop_anim.start()

    def _apply_label_style(self):
        self.label.setFont(self.pixel_font)
        self.label.setStyleSheet(f"""
            color: {self.text_color};
            font-weight: 900;
            background: transparent;
        """)

    def set_theme(self, bg: str, border: str, text: str):
        self.bg_color = QColor(bg)
        self.border_color = QColor(border)
        self.text_color = text
        self._apply_label_style()
        self.update()

    def set_message(self, text: str):
        clean_text = (text or "").strip()
        char_len = len(clean_text)

        if char_len <= 32:
            text_w = 190
        elif char_len <= 68:
            text_w = 240
        else:
            text_w = 280

        self.label.setFixedWidth(text_w)
        self.label.setText(clean_text)
        self.label.adjustSize()

        s = self.PIXEL_SCALE
        pad_x = 68
        pad_y = 94

        raw_w = max(220, self.label.width() + pad_x)
        raw_h = max(108, self.label.height() + pad_y)

        snapped_w = ((raw_w + s - 1) // s) * s
        snapped_h = ((raw_h + s - 1) // s) * s

        self.setMinimumSize(snapped_w, snapped_h)
        self.resize(snapped_w, snapped_h)
        self.layout().activate()
        self.update()

    def _build_pixel_cloud_mask(self, cols: int, rows: int) -> list[list[bool]]:
        grid = [[False for _ in range(cols)] for _ in range(rows)]

        def fill_rect(x0: int, y0: int, x1: int, y1: int):
            for y in range(max(0, y0), min(rows, y1 + 1)):
                for x in range(max(0, x0), min(cols, x1 + 1)):
                    grid[y][x] = True

        top_y0 = 5 if self.tail_side.startswith("top") else 4
        bot_y1 = rows - 6 if self.tail_side.startswith("bottom") else rows - 5
        left_x0 = 3 if self.tail_side.startswith("left") else 2
        right_x1 = cols - 4 if self.tail_side.startswith("right") else cols - 3

        fill_rect(left_x0 + 2, top_y0, right_x1 - 2, bot_y1)
        fill_rect(left_x0, top_y0 + 2, right_x1, bot_y1 - 1)

        left_puff_end = max(8, cols // 3)
        fill_rect(5, top_y0 - 2, left_puff_end, top_y0)
        fill_rect(6, top_y0 - 3, left_puff_end - 1, top_y0 - 3)

        mid_puff_start = max(left_puff_end + 1, cols // 3 + 1)
        mid_puff_end = max(mid_puff_start + 3, (cols * 2) // 3)
        fill_rect(mid_puff_start, top_y0 - 3, mid_puff_end, top_y0)
        fill_rect(mid_puff_start + 1, top_y0 - 4, mid_puff_end - 1, top_y0 - 4)

        right_puff_start = max(mid_puff_end + 1, (cols * 2) // 3 + 1)
        right_puff_end = max(right_puff_start + 2, cols - 6)
        fill_rect(right_puff_start, top_y0 - 2, right_puff_end, top_y0)
        fill_rect(right_puff_start + 1, top_y0 - 3, right_puff_end - 1, top_y0 - 3)

        side = self.tail_side
        if side == "bottom-right":
            tx, ty = max(8, cols - 10), min(rows - 5, bot_y1)
            for k in range(4):
                fill_rect(tx + k, ty + k, tx + k + 3, ty + k)
        elif side == "bottom-left":
            tx, ty = min(cols - 12, 6), min(rows - 5, bot_y1)
            for k in range(4):
                fill_rect(tx - k + 2, ty + k, tx - k + 5, ty + k)
        elif side == "top-right":
            tx, ty = max(8, cols - 10), max(4, top_y0)
            for k in range(4):
                fill_rect(tx + k, ty - k, tx + k + 3, ty - k)
        elif side == "top-left":
            tx, ty = min(cols - 12, 6), max(4, top_y0)
            for k in range(4):
                fill_rect(tx - k + 2, ty - k, tx - k + 5, ty - k)
        elif side == "left":
            tx, ty = max(1, left_x0 - 2), rows // 2
            fill_rect(tx, ty - 1, left_x0, ty + 1)
            fill_rect(tx - 1, ty, tx, ty)
        elif side == "right":
            tx, ty = min(cols - 3, right_x1 + 1), rows // 2
            fill_rect(right_x1, ty - 1, tx, ty + 1)
            fill_rect(tx, ty, tx + 1, ty)

        return grid

    def paintEvent(self, event):
        if self.width() <= 0 or self.height() <= 0:
            return

        s = self.PIXEL_SCALE
        cols = max(24, self.width() // s)
        rows = max(14, self.height() // s)

        cloud = self._build_pixel_cloud_mask(cols, rows)
        low_res = QImage(cols, rows, QImage.Format.Format_ARGB32)
        low_res.fill(Qt.GlobalColor.transparent)
        transparent = QColor(0, 0, 0, 0)

        for y in range(rows):
            for x in range(cols):
                if cloud[y][x]:
                    is_edge = (
                        x == 0
                        or not cloud[y][x - 1]
                        or x == cols - 1
                        or not cloud[y][x + 1]
                        or y == 0
                        or not cloud[y - 1][x]
                        or y == rows - 1
                        or not cloud[y + 1][x]
                    )
                    low_res.setPixelColor(
                        x, y, self.border_color if is_edge else self.bg_color
                    )
                else:
                    low_res.setPixelColor(x, y, transparent)

        scaled = QPixmap.fromImage(low_res).scaled(
            self.size(),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )

        painter = QPainter(self)
        if abs(self._pop_scale - 1.0) > 0.005:
            cx = self.width() / 2.0
            cy = self.height() / 2.0
            painter.translate(cx, cy)
            painter.scale(self._pop_scale, self._pop_scale)
            painter.translate(-cx, -cy)
        painter.drawPixmap(0, 0, scaled)
        painter.end()


class CommandMenuPopup(QFrame):
    """Top tabbed layout with rounded corners, button animations, SFX, Gemini key & voice settings."""

    command_selected = pyqtSignal(str)
    sprite_uploaded = pyqtSignal(str, str)  # (slot_key, file_path)
    sprite_reset = pyqtSignal(str)  # (slot_key)
    sound_uploaded = pyqtSignal(str, str)  # (sound_slot, file_path)
    sound_reset = pyqtSignal(str)  # (sound_slot)
    sound_toggled = pyqtSignal(str, bool)  # (sound_slot, enabled)
    auto_scan_toggled = pyqtSignal(bool)
    bubble_popup_toggled = pyqtSignal(bool)
    gemini_settings_changed = pyqtSignal(str, bool)  # (api_key, auto_model)
    fish_voice_changed = pyqtSignal(dict)
    theme_selected = pyqtSignal(str)
    custom_rgb_changed = pyqtSignal(dict)
    bubble_offset_changed = pyqtSignal(int, int)
    snap_top_left_requested = pyqtSignal()
    close_requested = pyqtSignal()

    MENU_SIZE = QSize(336, 178)

    def __init__(self, config: dict, sfx: SoundEffectsPlayer, parent=None):
        super().__init__(parent)
        self.config = config
        self.sfx = sfx
        self._btn_filter = ButtonAnimFilter(sfx, self)
        self.saved_sprites = config.get("sprites", {})
        self.saved_sounds = config.get("sounds", {})
        self.sound_enabled = dict(
            config.get("sound_enabled", {"hover": True, "click": True, "popup": True})
        )
        self.custom_rgb = dict(
            config.get(
                "custom_rgb",
                {"base": "#082f49", "accent": "#0284c7", "text": "#ecfeff"},
            )
        )
        self.bubble_offset = dict(config.get("bubble_offset", {"x": 0, "y": 0}))
        self.fish_voice = dict(
            config.get(
                "fish_voice",
                {
                    "enabled": False,
                    "api_key": "",
                    "reference_id": "",
                    "model": "s2.1-pro-free",
                },
            )
        )
        self.slot_status_labels: dict[str, QLabel] = {}
        self.sound_status_labels: dict[str, QLabel] = {}
        self.theme_buttons: dict[str, QPushButton] = {}
        self.rgb_swatches: dict[str, QLabel] = {}
        self.resize(self.MENU_SIZE)
        self._anim_progress = 0.0
        self._closing = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(6, 4, 6, 6)
        outer.setSpacing(3)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(4)

        self.title_lbl = QLabel("PET MENU")
        close_btn = QPushButton("X", self)
        close_btn.setFixedSize(22, 18)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.installEventFilter(self._btn_filter)
        close_btn.setStyleSheet("""
            QPushButton {
                background: #7f1d1d;
                color: #fef2f2;
                border: 1px solid #000000;
                border-radius: 6px;
                font-family: Consolas;
                font-size: 10px;
                font-weight: bold;
                padding: 0px;
            }
            QPushButton:hover {
                background: #dc2626;
            }
        """)
        close_btn.clicked.connect(self.animate_close)

        header.addWidget(self.title_lbl)
        header.addStretch(1)
        header.addWidget(close_btn)
        outer.addLayout(header)

        self.tabs = QTabWidget(self)
        self.tabs.addTab(self._build_commands_tab(), "Commands")
        self.tabs.addTab(self._build_customize_tab(), "Customize")
        self.tabs.addTab(self._build_theme_tab(), "Theme")
        outer.addWidget(self.tabs)

        self._apply_current_palette()

        for btn in self.findChildren(QPushButton):
            btn.installEventFilter(self._btn_filter)
        for chk in self.findChildren(QCheckBox):
            chk.installEventFilter(self._btn_filter)

        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(16)
        self._anim_timer.timeout.connect(self._step_animation)

    def _get_active_palette(self) -> dict:
        theme_name = self.config.get("theme", "Ocean Deep")
        if theme_name == "Custom RGB":
            return build_custom_palette(self.custom_rgb)
        return LAYOUT_THEMES.get(theme_name, LAYOUT_THEMES["Ocean Deep"])

    def _apply_current_palette(self):
        self.apply_theme_palette(self._get_active_palette())

    def apply_theme_palette(self, palette: dict):
        panel_bg = palette["panel_bg"]
        pane_bg = palette["pane_bg"]
        row_bg = palette["row_bg"]
        accent = palette["accent"]
        accent_hover = palette["accent_hover"]
        title_color = palette["title_color"]
        text_color = palette["text_color"]

        self.setStyleSheet(f"""
            CommandMenuPopup {{
                background: {panel_bg};
                border: 2px solid #000000;
                border-radius: 6px;
            }}
        """)
        self.title_lbl.setStyleSheet(
            f"color: {title_color}; font-family: Consolas; font-size: 11px; font-weight: bold; border: none; background: transparent;"
        )
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid #000000;
                border-radius: 6px;
                background: {pane_bg};
            }}
            QTabBar::tab {{
                background: {row_bg};
                color: {text_color};
                border: 1px solid #000000;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                padding: 3px 9px;
                font-family: Consolas;
                font-size: 10px;
                font-weight: bold;
            }}
            QTabBar::tab:selected {{
                background: {accent};
                color: #ffffff;
            }}
        """)
        for btn in self.findChildren(QPushButton):
            if btn.text() in ("X", "Upload", "Reset"):
                continue
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {accent};
                    color: #ffffff;
                    border: 1px solid #000000;
                    border-radius: 6px;
                    padding: 3px 4px;
                    font-family: Consolas;
                    font-size: 10px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background: {accent_hover};
                }}
            """)
        for lbl in self.findChildren(QLabel):
            if lbl is self.title_lbl or lbl in self.rgb_swatches.values():
                continue
            lbl.setStyleSheet(f"""
                QLabel {{
                    background: {row_bg};
                    color: {text_color};
                    border: 1px solid #000000;
                    border-radius: 6px;
                    padding: 3px 6px;
                    font-family: Consolas;
                    font-size: 10px;
                    font-weight: bold;
                }}
            """)
        for key, sw in self.rgb_swatches.items():
            hex_c = self.custom_rgb.get(key, "#0284c7")
            sw.setStyleSheet(
                f"background: {hex_c}; border: 1px solid #000000; border-radius: 6px;"
            )

    def _build_commands_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent; border: none;")

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        list_layout = QVBoxLayout(container)
        list_layout.setContentsMargins(4, 4, 4, 4)
        list_layout.setSpacing(3)

        for cmd_label, desc, arg_placeholder, btn_text, prefix in COMMAND_ITEMS:
            row = QWidget(container)
            row.setStyleSheet("background: transparent; border: none;")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(4)

            info_lbl = QLabel(f"{cmd_label} · {desc}")
            row_layout.addWidget(info_lbl, stretch=1)

            if arg_placeholder:
                arg_box = QLineEdit(row)
                arg_box.setPlaceholderText(arg_placeholder)
                arg_box.setFixedWidth(70)
                arg_box.setStyleSheet("""
                    QLineEdit {
                        background: #020617;
                        color: #fef08a;
                        border: 1px solid #000000;
                        border-radius: 6px;
                        padding: 2px 4px;
                        font-family: Consolas;
                        font-size: 10px;
                        font-weight: bold;
                    }
                    QLineEdit:focus {
                        border: 1px solid #38bdf8;
                    }
                """)

                act_btn = QPushButton(btn_text, row)
                act_btn.setFixedWidth(42)
                act_btn.setCursor(Qt.CursorShape.PointingHandCursor)

                def _emit_arg(_checked=False, box=arg_box, pfx=prefix):
                    val = box.text().strip()
                    box.clear()
                    self.command_selected.emit(f"{pfx} {val}".strip())

                arg_box.returnPressed.connect(_emit_arg)
                act_btn.clicked.connect(_emit_arg)

                row_layout.addWidget(arg_box)
                row_layout.addWidget(act_btn)
            else:
                run_btn = QPushButton(btn_text, row)
                run_btn.setFixedWidth(40)
                run_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                run_btn.clicked.connect(
                    lambda _checked=False, c=prefix: self.command_selected.emit(c)
                )
                row_layout.addWidget(run_btn)

            list_layout.addWidget(row)

        scroll.setWidget(container)
        return scroll

    def _build_customize_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent; border: none;")

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        list_layout = QVBoxLayout(container)
        list_layout.setContentsMargins(4, 4, 4, 4)
        list_layout.setSpacing(4)

        chk_style = """
            QCheckBox {
                background: #0f172a;
                color: #fef08a;
                border: 1px solid #000000;
                border-radius: 6px;
                padding: 4px 6px;
                font-family: Consolas;
                font-size: 9px;
                font-weight: bold;
            }
        """
        input_style = """
            QLineEdit {
                background: #020617;
                color: #fef08a;
                border: 1px solid #000000;
                border-radius: 6px;
                padding: 2px 5px;
                font-family: Consolas;
                font-size: 9px;
                font-weight: bold;
            }
        """

        auto_mdl_enabled = bool(self.config.get("auto_model", True))
        self.auto_model_toggle = QCheckBox(
            "Auto Select Model (ON)" if auto_mdl_enabled else "Auto Select Model (OFF)",
            container,
        )
        self.auto_model_toggle.setChecked(auto_mdl_enabled)
        self.auto_model_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.auto_model_toggle.setStyleSheet(chk_style)
        list_layout.addWidget(self.auto_model_toggle)

        gem_row = QWidget(container)
        gem_row.setStyleSheet("background: transparent; border: none;")
        gem_layout = QHBoxLayout(gem_row)
        gem_layout.setContentsMargins(0, 0, 0, 0)
        gem_layout.setSpacing(3)

        self.gemini_key_input = QLineEdit(gem_row)
        self.gemini_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.gemini_key_input.setPlaceholderText("Gemini API Key")
        self.gemini_key_input.setText(self.config.get("gemini_api_key", ""))
        self.gemini_key_input.setStyleSheet(input_style)

        save_gem_btn = QPushButton("Save", gem_row)
        save_gem_btn.setFixedWidth(44)
        save_gem_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        def _save_gemini(_checked=False):
            key_val = self.gemini_key_input.text().strip()
            auto_val = bool(self.auto_model_toggle.isChecked())
            self.auto_model_toggle.setText(
                "Auto Select Model (ON)" if auto_val else "Auto Select Model (OFF)"
            )
            self.gemini_settings_changed.emit(key_val, auto_val)

        self.auto_model_toggle.toggled.connect(_save_gemini)
        self.gemini_key_input.returnPressed.connect(_save_gemini)
        save_gem_btn.clicked.connect(_save_gemini)

        gem_layout.addWidget(self.gemini_key_input, stretch=1)
        gem_layout.addWidget(save_gem_btn)
        list_layout.addWidget(gem_row)

        auto_scan_enabled = bool(self.config.get("auto_screen_scan", True))
        self.auto_scan_toggle = QCheckBox(
            "Live Desktop Talk (ON)"
            if auto_scan_enabled
            else "Live Desktop Talk (OFF - Prompt Only)",
            container,
        )
        self.auto_scan_toggle.setChecked(auto_scan_enabled)
        self.auto_scan_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.auto_scan_toggle.setStyleSheet(chk_style)
        self.auto_scan_toggle.toggled.connect(self._on_auto_scan_toggled)
        list_layout.addWidget(self.auto_scan_toggle)

        bubble_pop_enabled = bool(self.config.get("bubble_popup_enabled", True))
        self.bubble_pop_toggle = QCheckBox(
            "Bubble Pop-Up (ON)" if bubble_pop_enabled else "Bubble Pop-Up (OFF)",
            container,
        )
        self.bubble_pop_toggle.setChecked(bubble_pop_enabled)
        self.bubble_pop_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.bubble_pop_toggle.setStyleSheet(chk_style)
        self.bubble_pop_toggle.toggled.connect(self._on_bubble_popup_toggled)
        list_layout.addWidget(self.bubble_pop_toggle)

        for s_slot, s_title in SOUND_SLOT_LABELS:
            en = bool(self.sound_enabled.get(s_slot, True))
            s_chk = QCheckBox(f"{s_title} ({'ON' if en else 'OFF'})", container)
            s_chk.setChecked(en)
            s_chk.setCursor(Qt.CursorShape.PointingHandCursor)
            s_chk.setStyleSheet(chk_style)

            def _on_s_toggle(checked, sk=s_slot, cb=s_chk):
                self.sound_enabled[sk] = bool(checked)
                cb.setText(
                    f"{dict(SOUND_SLOT_LABELS)[sk]} ({'ON' if checked else 'OFF'})"
                )
                self.sound_toggled.emit(sk, bool(checked))

            s_chk.toggled.connect(_on_s_toggle)
            list_layout.addWidget(s_chk)

            s_row = QWidget(container)
            s_row.setStyleSheet("background: transparent; border: none;")
            s_layout = QHBoxLayout(s_row)
            s_layout.setContentsMargins(0, 0, 0, 0)
            s_layout.setSpacing(4)

            saved_s = self.saved_sounds.get(s_slot, "")
            s_name = (
                Path(saved_s).name
                if saved_s
                else DEFAULT_SOUND_FILES.get(s_slot, "Default")
            )
            s_lbl = QLabel(f"{s_title} File\n[{s_name}]")
            self.sound_status_labels[s_slot] = s_lbl

            s_up = QPushButton("Upload", s_row)
            s_up.setFixedWidth(48)
            s_up.setCursor(Qt.CursorShape.PointingHandCursor)
            s_up.setStyleSheet("""
                QPushButton {
                    background: #15803d;
                    color: #ffffff;
                    border: 1px solid #000000;
                    border-radius: 6px;
                    padding: 4px 4px;
                    font-family: Consolas;
                    font-size: 9px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background: #16a34a;
                }
            """)
            s_up.clicked.connect(
                lambda _checked=False, sk=s_slot: self._pick_sound_file(sk)
            )

            s_rst = QPushButton("Reset", s_row)
            s_rst.setFixedWidth(42)
            s_rst.setCursor(Qt.CursorShape.PointingHandCursor)
            s_rst.setStyleSheet("""
                QPushButton {
                    background: #475569;
                    color: #ffffff;
                    border: 1px solid #000000;
                    border-radius: 6px;
                    padding: 4px 4px;
                    font-family: Consolas;
                    font-size: 9px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background: #64748b;
                }
            """)
            s_rst.clicked.connect(
                lambda _checked=False, sk=s_slot: self.sound_reset.emit(sk)
            )

            s_layout.addWidget(s_lbl, stretch=1)
            s_layout.addWidget(s_up)
            s_layout.addWidget(s_rst)
            list_layout.addWidget(s_row)

        voice_enabled = bool(self.fish_voice.get("enabled", False))
        self.fish_voice_toggle = QCheckBox(
            "Fish Audio Voice (ON)" if voice_enabled else "Fish Audio Voice (OFF)",
            container,
        )
        self.fish_voice_toggle.setChecked(voice_enabled)
        self.fish_voice_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.fish_voice_toggle.setStyleSheet(chk_style)
        list_layout.addWidget(self.fish_voice_toggle)

        self.fish_key_input = QLineEdit(container)
        self.fish_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.fish_key_input.setPlaceholderText("Fish Audio API Key")
        self.fish_key_input.setText(self.fish_voice.get("api_key", ""))
        self.fish_key_input.setStyleSheet(input_style)
        list_layout.addWidget(self.fish_key_input)

        voice_sub_row = QWidget(container)
        voice_sub_row.setStyleSheet("background: transparent; border: none;")
        voice_sub_layout = QHBoxLayout(voice_sub_row)
        voice_sub_layout.setContentsMargins(0, 0, 0, 0)
        voice_sub_layout.setSpacing(3)

        self.fish_ref_input = QLineEdit(voice_sub_row)
        self.fish_ref_input.setPlaceholderText("Voice / Ref ID")
        self.fish_ref_input.setText(self.fish_voice.get("reference_id", ""))
        self.fish_ref_input.setStyleSheet(input_style)

        self.fish_model_input = QLineEdit(voice_sub_row)
        self.fish_model_input.setPlaceholderText("s2.1-pro-free")
        self.fish_model_input.setText(self.fish_voice.get("model", "s2.1-pro-free"))
        self.fish_model_input.setFixedWidth(84)
        self.fish_model_input.setStyleSheet(input_style)

        save_voice_btn = QPushButton("Save", voice_sub_row)
        save_voice_btn.setFixedWidth(44)
        save_voice_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        def _save_fish_voice(_checked=False):
            self.fish_voice = {
                "enabled": bool(self.fish_voice_toggle.isChecked()),
                "api_key": self.fish_key_input.text().strip(),
                "reference_id": self.fish_ref_input.text().strip(),
                "model": (self.fish_model_input.text().strip() or "s2.1-pro-free"),
            }
            self.fish_voice_toggle.setText(
                "Fish Audio Voice (ON)"
                if self.fish_voice["enabled"]
                else "Fish Audio Voice (OFF)"
            )
            self.fish_voice_changed.emit(dict(self.fish_voice))

        self.fish_voice_toggle.toggled.connect(_save_fish_voice)
        self.fish_key_input.returnPressed.connect(_save_fish_voice)
        self.fish_ref_input.returnPressed.connect(_save_fish_voice)
        save_voice_btn.clicked.connect(_save_fish_voice)

        voice_sub_layout.addWidget(self.fish_ref_input, stretch=1)
        voice_sub_layout.addWidget(self.fish_model_input)
        voice_sub_layout.addWidget(save_voice_btn)
        list_layout.addWidget(voice_sub_row)

        for slot_key, slot_title in SPRITE_SLOT_LABELS:
            row = QWidget(container)
            row.setStyleSheet("background: transparent; border: none;")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(4)

            saved_path = self.saved_sprites.get(slot_key, "")
            current_name = Path(saved_path).name if saved_path else "Default"
            status_lbl = QLabel(f"{slot_title}\n[{current_name}]")
            self.slot_status_labels[slot_key] = status_lbl

            upload_btn = QPushButton("Upload", row)
            upload_btn.setFixedWidth(48)
            upload_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            upload_btn.setStyleSheet("""
                QPushButton {
                    background: #15803d;
                    color: #ffffff;
                    border: 1px solid #000000;
                    border-radius: 6px;
                    padding: 4px 4px;
                    font-family: Consolas;
                    font-size: 9px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background: #16a34a;
                }
            """)
            upload_btn.clicked.connect(
                lambda _checked=False, sk=slot_key: self._pick_sprite_file(sk)
            )

            reset_btn = QPushButton("Reset", row)
            reset_btn.setFixedWidth(42)
            reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            reset_btn.setStyleSheet("""
                QPushButton {
                    background: #475569;
                    color: #ffffff;
                    border: 1px solid #000000;
                    border-radius: 6px;
                    padding: 4px 4px;
                    font-family: Consolas;
                    font-size: 9px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background: #64748b;
                }
            """)
            reset_btn.clicked.connect(
                lambda _checked=False, sk=slot_key: self._reset_sprite_slot(sk)
            )

            row_layout.addWidget(status_lbl, stretch=1)
            row_layout.addWidget(upload_btn)
            row_layout.addWidget(reset_btn)
            list_layout.addWidget(row)

        scroll.setWidget(container)
        return scroll

    def _build_theme_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent; border: none;")

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        list_layout = QVBoxLayout(container)
        list_layout.setContentsMargins(4, 4, 4, 4)
        list_layout.setSpacing(4)

        off_row = QWidget(container)
        off_row.setStyleSheet("background: transparent; border: none;")
        off_layout = QHBoxLayout(off_row)
        off_layout.setContentsMargins(0, 0, 0, 0)
        off_layout.setSpacing(3)

        off_lbl = QLabel("Off X/Y")
        self.off_x_spin = QSpinBox(off_row)
        self.off_x_spin.setRange(-120, 120)
        self.off_x_spin.setValue(int(self.bubble_offset.get("x", 0)))
        self.off_x_spin.setFixedWidth(52)
        self.off_x_spin.setStyleSheet(
            "background: #020617; color: #fef08a; border: 1px solid #000000; border-radius: 6px; font-family: Consolas; font-size: 9px; font-weight: bold;"
        )

        self.off_y_spin = QSpinBox(off_row)
        self.off_y_spin.setRange(-120, 120)
        self.off_y_spin.setValue(int(self.bubble_offset.get("y", 0)))
        self.off_y_spin.setFixedWidth(52)
        self.off_y_spin.setStyleSheet(
            "background: #020617; color: #fef08a; border: 1px solid #000000; border-radius: 6px; font-family: Consolas; font-size: 9px; font-weight: bold;"
        )

        def _emit_offset(_val=0):
            ox = int(self.off_x_spin.value())
            oy = int(self.off_y_spin.value())
            self.bubble_offset = {"x": ox, "y": oy}
            self.bubble_offset_changed.emit(ox, oy)

        self.off_x_spin.valueChanged.connect(_emit_offset)
        self.off_y_spin.valueChanged.connect(_emit_offset)

        snap_btn = QPushButton("Top-Left Test", off_row)
        snap_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        snap_btn.clicked.connect(
            lambda _checked=False: self.snap_top_left_requested.emit()
        )

        off_layout.addWidget(off_lbl)
        off_layout.addWidget(self.off_x_spin)
        off_layout.addWidget(self.off_y_spin)
        off_layout.addWidget(snap_btn)
        list_layout.addWidget(off_row)

        for rgb_key, rgb_label in [
            ("base", "RGB Base / Bubble"),
            ("accent", "RGB Buttons / Glow"),
            ("text", "RGB Bubble Text"),
        ]:
            rgb_row = QWidget(container)
            rgb_row.setStyleSheet("background: transparent; border: none;")
            rgb_layout = QHBoxLayout(rgb_row)
            rgb_layout.setContentsMargins(0, 0, 0, 0)
            rgb_layout.setSpacing(4)

            sw = QLabel("  ")
            sw.setFixedWidth(22)
            sw.setStyleSheet(
                f"background: {self.custom_rgb.get(rgb_key, '#0284c7')}; border: 1px solid #000000; border-radius: 6px;"
            )
            self.rgb_swatches[rgb_key] = sw

            lbl = QLabel(f"{rgb_label} ({self.custom_rgb.get(rgb_key, '#0284c7')})")
            pick_btn = QPushButton("RGB", rgb_row)
            pick_btn.setFixedWidth(44)
            pick_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            pick_btn.clicked.connect(
                lambda _checked=False, k=rgb_key, l=lbl, rl=rgb_label: self._pick_rgb_color(
                    k, l, rl
                )
            )

            rgb_layout.addWidget(sw)
            rgb_layout.addWidget(lbl, stretch=1)
            rgb_layout.addWidget(pick_btn)
            list_layout.addWidget(rgb_row)

        active_theme = self.config.get("theme", "Ocean Deep")
        custom_row = QWidget(container)
        custom_row.setStyleSheet("background: transparent; border: none;")
        custom_layout = QHBoxLayout(custom_row)
        custom_layout.setContentsMargins(0, 0, 0, 0)
        custom_layout.setSpacing(4)

        c_lbl = QLabel("Custom RGB Theme")
        c_btn = QPushButton(
            "Active" if active_theme == "Custom RGB" else "Use RGB", custom_row
        )
        c_btn.setFixedWidth(60)
        c_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        c_btn.clicked.connect(lambda _checked=False: self._select_theme("Custom RGB"))
        self.theme_buttons["Custom RGB"] = c_btn

        custom_layout.addWidget(c_lbl, stretch=1)
        custom_layout.addWidget(c_btn)
        list_layout.addWidget(custom_row)

        for theme_name, pal in LAYOUT_THEMES.items():
            row = QWidget(container)
            row.setStyleSheet("background: transparent; border: none;")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(4)

            swatch = QLabel("  ")
            swatch.setFixedWidth(22)
            swatch.setStyleSheet(
                f"background: {pal['accent']}; border: 1px solid #000000; border-radius: 6px;"
            )

            info_lbl = QLabel(theme_name)
            apply_btn = QPushButton(
                "Active" if theme_name == active_theme else "Apply", row
            )
            apply_btn.setFixedWidth(54)
            apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            apply_btn.clicked.connect(
                lambda _checked=False, tn=theme_name: self._select_theme(tn)
            )
            self.theme_buttons[theme_name] = apply_btn

            row_layout.addWidget(swatch)
            row_layout.addWidget(info_lbl, stretch=1)
            row_layout.addWidget(apply_btn)
            list_layout.addWidget(row)

        scroll.setWidget(container)
        return scroll

    def _pick_sound_file(self, sound_slot: str):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Sound File",
            str(BASE_DIR),
            "Audio (*.mp3 *.wav *.ogg)",
        )
        if file_path:
            self.sound_uploaded.emit(sound_slot, file_path)

    def update_sound_label(self, sound_slot: str, display_name: str):
        lbl = self.sound_status_labels.get(sound_slot)
        if not lbl:
            return
        title = dict(SOUND_SLOT_LABELS).get(sound_slot, sound_slot)
        lbl.setText(f"{title} File\n[{display_name}]")

    def _pick_rgb_color(self, key: str, label_widget: QLabel, title_text: str):
        initial = QColor(self.custom_rgb.get(key, "#0284c7"))
        chosen = QColorDialog.getColor(initial, self, f"Pick {title_text} (RGB)")
        if not chosen.isValid():
            return
        hex_val = chosen.name()
        self.custom_rgb[key] = hex_val
        label_widget.setText(f"{title_text} ({hex_val})")
        self.config["custom_rgb"] = dict(self.custom_rgb)
        self.config["theme"] = "Custom RGB"
        for tn, btn in self.theme_buttons.items():
            btn.setText("Active" if tn == "Custom RGB" else "Apply")
        self._apply_current_palette()
        self.custom_rgb_changed.emit(dict(self.custom_rgb))

    def _on_auto_scan_toggled(self, checked: bool):
        self.auto_scan_toggle.setText(
            "Live Desktop Talk (ON)"
            if checked
            else "Live Desktop Talk (OFF - Prompt Only)"
        )
        self.auto_scan_toggled.emit(checked)

    def _on_bubble_popup_toggled(self, checked: bool):
        self.bubble_pop_toggle.setText(
            "Bubble Pop-Up (ON)" if checked else "Bubble Pop-Up (OFF)"
        )
        self.bubble_popup_toggled.emit(checked)

    def _select_theme(self, theme_name: str):
        if theme_name not in LAYOUT_THEMES and theme_name != "Custom RGB":
            return
        self.config["theme"] = theme_name
        for tn, btn in self.theme_buttons.items():
            btn.setText("Active" if tn == theme_name else "Apply")
        self._apply_current_palette()
        self.theme_selected.emit(theme_name)

    def _pick_sprite_file(self, slot_key: str):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select GIF or PNG Sprite",
            str(BASE_DIR),
            "Sprites (*.gif *.png *.jpg *.jpeg *.webp)",
        )
        if file_path:
            self.sprite_uploaded.emit(slot_key, file_path)

    def _reset_sprite_slot(self, slot_key: str):
        self.sprite_reset.emit(slot_key)

    def update_slot_label(self, slot_key: str, display_name: str):
        lbl = self.slot_status_labels.get(slot_key)
        if not lbl:
            return
        title = dict(SPRITE_SLOT_LABELS).get(slot_key, slot_key)
        lbl.setText(f"{title}\n[{display_name}]")

    def animate_open(self):
        self._closing = False
        self._anim_progress = 0.15
        self.resize(self.MENU_SIZE.width(), max(28, int(self.MENU_SIZE.height() * 0.15)))
        self.show()
        self.raise_()
        self._anim_timer.start()

    def animate_close(self):
        if not self.isVisible():
            return
        self._closing = True
        self._anim_timer.start()

    def _step_animation(self):
        if not self._closing:
            self._anim_progress = min(1.0, self._anim_progress + 0.18)
            t = self._anim_progress
            eased = 1.0 + 2.2 * ((t - 1.0) ** 3) + 1.2 * ((t - 1.0) ** 2)
            h = max(28, int(self.MENU_SIZE.height() * min(1.03, eased)))
            self.resize(self.MENU_SIZE.width(), h)
            if self._anim_progress >= 1.0:
                self.resize(self.MENU_SIZE)
                self._anim_timer.stop()
        else:
            self._anim_progress = max(0.0, self._anim_progress - 0.2)
            h = max(24, int(self.MENU_SIZE.height() * self._anim_progress))
            self.resize(self.MENU_SIZE.width(), h)
            if self._anim_progress <= 0.0:
                self._anim_timer.stop()
                self.hide()
                self.resize(self.MENU_SIZE)
                self.close_requested.emit()


class DesktopPet(QWidget):
    new_opinion_signal = pyqtSignal(str)
    manual_reply_signal = pyqtSignal(str)
    connection_signal = pyqtSignal(bool)

    SPRITE_POS = QPoint(310, 185)
    CONTAINER_SIZE = QSize(620, 430)

    def __init__(self):
        super().__init__()
        self.setMouseTracking(True)
        self.config = load_saved_config()
        self.config.setdefault("gemini_api_key", "")
        self.config.setdefault("auto_model", True)
        self.config.setdefault("sprites", {})
        self.config.setdefault("sounds", {})
        self.config.setdefault(
            "sound_enabled", {"hover": True, "click": True, "popup": True}
        )
        self.config.setdefault(
            "custom_rgb",
            {"base": "#082f49", "accent": "#0284c7", "text": "#ecfeff"},
        )
        self.config.setdefault("bubble_offset", {"x": 0, "y": 0})
        self.config.setdefault(
            "fish_voice",
            {
                "enabled": False,
                "api_key": "",
                "reference_id": "",
                "model": "s2.1-pro-free",
            },
        )
        self.sfx = SoundEffectsPlayer(self.config)
        self._btn_filter = ButtonAnimFilter(self.sfx, self)
        self.auto_screen_scan = bool(self.config.get("auto_screen_scan", True))
        self.bubble_popup_enabled = bool(self.config.get("bubble_popup_enabled", True))
        self.active_theme_name = self.config.get("theme", "Ocean Deep")
        self.speaker = FishAudioSpeaker(self)

        self.client = create_gemini_client(self.config)
        self.model_idx = 0
        self.live_stream = LiveDesktopStream(lambda: dict(self.config))
        self.recent_replies: list[str] = []
        self.chat_history: list[tuple[str, str]] = []
        self.gdi = GdiDesktopEffects()
        self.muted_by_user = False
        print("[Init] API key found:", bool(self.client))

        self.is_online = None
        self.is_thinking = False
        self.command_bar_open = False
        self._command_mode_paused_scan = False
        self.showing_custom_sprite = False
        self.scan_pause_until = 0.0
        self._active_voice_utt_id = 0
        self._voice_still_playing = False
        self._bubble_min_hold_done = False
        self.diamond_tint_color: QColor | None = None
        self.current_pixmap: QPixmap | None = None
        self.active_movie: QMovie | None = None
        self._last_rendered_key = None

        # Hover, click, and effect visual state
        self.is_hovered = False
        self.click_pulse_scale = 1.0
        self.hover_lift_y = 0
        self.hop_offset_y = 0
        self.flipped_x = False
        self.spin_angle = 0
        self.disco_hue = 0
        self.disco_active = False

        self.drag_pos = None
        self.press_global_pos = None
        self.moved_during_drag = False
        self._movies: list[QMovie] = []

        self.init_ui()

        self.new_opinion_signal.connect(self.pop_new_message)
        self.manual_reply_signal.connect(self.pop_manual_diamond_message)
        self.connection_signal.connect(self.apply_connection_state)
        self.speaker.voice_finished.connect(self._on_fish_voice_finished)
        self.cmd_menu.command_selected.connect(self._run_command_from_menu)
        self.cmd_menu.sprite_uploaded.connect(self._on_sprite_uploaded)
        self.cmd_menu.sprite_reset.connect(self._on_sprite_reset)
        self.cmd_menu.sound_uploaded.connect(self._on_sound_uploaded)
        self.cmd_menu.sound_reset.connect(self._on_sound_reset)
        self.cmd_menu.sound_toggled.connect(self._on_sound_toggled)
        self.cmd_menu.auto_scan_toggled.connect(self._on_auto_scan_toggled)
        self.cmd_menu.bubble_popup_toggled.connect(self._on_bubble_popup_toggled)
        self.cmd_menu.gemini_settings_changed.connect(self._on_gemini_settings_changed)
        self.cmd_menu.fish_voice_changed.connect(self._on_fish_voice_changed)
        self.cmd_menu.theme_selected.connect(self._on_theme_selected)
        self.cmd_menu.custom_rgb_changed.connect(self._on_custom_rgb_changed)
        self.cmd_menu.bubble_offset_changed.connect(self._on_bubble_offset_changed)
        self.cmd_menu.snap_top_left_requested.connect(self._snap_diamond_top_left_test)

        self.net_timer = QTimer(self)
        self.net_timer.timeout.connect(self.check_net_async)
        self.net_timer.start(6000)

        self.judge_timer = QTimer(self)
        self.judge_timer.timeout.connect(self.judge_screen)
        self.judge_timer.start(CHECK_INTERVAL_MS)

        QTimer.singleShot(1400, self.judge_screen)

        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self._on_min_hold_timer_done)

        self.post_voice_hide_timer = QTimer(self)
        self.post_voice_hide_timer.setSingleShot(True)
        self.post_voice_hide_timer.timeout.connect(self.go_idle)

        self.post_speech_timer = QTimer(self)
        self.post_speech_timer.setSingleShot(True)
        self.post_speech_timer.timeout.connect(self._on_post_speech_wait_done)

        self.spin_timer = QTimer(self)
        self.spin_timer.timeout.connect(self._step_spin)

        self.click_anim_timer = QTimer(self)
        self.click_anim_timer.setSingleShot(True)
        self.click_anim_timer.timeout.connect(self._reset_click_pulse)

        self.hop_timer = QTimer(self)
        self.hop_timer.timeout.connect(self._step_hop)
        self.hop_step = 0

        self.disco_timer = QTimer(self)
        self.disco_timer.timeout.connect(self._step_disco)

        self.disco_stop_timer = QTimer(self)
        self.disco_stop_timer.setSingleShot(True)
        self.disco_stop_timer.timeout.connect(self._stop_disco)

        self.gdi_timer = QTimer(self)
        self.gdi_timer.timeout.connect(self._step_gdi)

        self.check_net_async()
        if resolve_gemini_api_key(self.config):
            self.live_stream.start()

    def _is_shut_up_command(self, text: str) -> bool:
        norm = re.sub(r"[^a-z\s]", "", (text or "").lower()).strip()
        return norm in ("shut up", "shutup", "be quiet", "stop talking", "quiet")

    def _is_talk_again_command(self, text: str) -> bool:
        norm = re.sub(r"[^a-z\s]", "", (text or "").lower()).strip()
        return norm in (
            "talk again",
            "speak again",
            "you can talk",
            "unmute",
            "start talking",
        )

    def _is_help_request(self, text: str) -> bool:
        low = (text or "").lower()
        return any(
            k in low
            for k in (
                "help",
                "how do i",
                "how to",
                "explain",
                "guide",
                "fix",
                "teach",
                "what is",
                "why is",
                "can you show",
            )
        )

    def _build_live_context_prompt(
        self, base_instruction: str, user_prompt: str | None = None
    ) -> str:
        tctx = get_current_time_context()
        include_time = (
            1 <= tctx["hour"] <= 4 and random.random() < 0.35
        ) or (random.random() < 0.12)
        time_note = (
            f" (Background note: local clock is {tctx['time_12h']} ({tctx['period']}); only bring it up if it feels natural right now.)"
            if include_time
            else ""
        )
        help_hint = ""
        if user_prompt and self._is_help_request(user_prompt):
            help_hint = (
                " The user is asking for help—answer clearly, calmly, and helpfully in 20 words or fewer."
            )
        return f"{base_instruction}{time_note}{help_hint}"

    def _on_gemini_settings_changed(self, api_key: str, auto_model: bool):
        self.config["gemini_api_key"] = api_key.strip()
        self.config["auto_model"] = bool(auto_model)
        self.model_idx = 0
        save_config(self.config)
        self.client = create_gemini_client(self.config)
        self.live_stream.restart_if_key_changed()
        mode_lbl = "auto model" if auto_model else "fixed model"
        self.pop_manual_diamond_message(f"gemini saved ({mode_lbl}).")

    def _on_min_hold_timer_done(self):
        self._bubble_min_hold_done = True
        if not self._voice_still_playing:
            self.go_idle()

    def _on_fish_voice_finished(self, utt_id: int):
        if utt_id != self._active_voice_utt_id:
            return
        self._voice_still_playing = False
        self.scan_pause_until = max(
            self.scan_pause_until,
            time.monotonic() + (POST_VOICE_EXTRA_MS / 1000.0) + POST_REPLY_SCAN_PAUSE_S,
        )
        self.post_speech_timer.start(
            POST_VOICE_EXTRA_MS + int(POST_REPLY_SCAN_PAUSE_S * 1000)
        )
        if self._bubble_min_hold_done:
            self.post_voice_hide_timer.start(POST_VOICE_EXTRA_MS)

    def _on_sound_uploaded(self, sound_slot: str, source_path: str):
        src = Path(source_path)
        if not src.exists():
            return
        CUSTOM_SOUNDS_DIR.mkdir(exist_ok=True)
        dest = (
            CUSTOM_SOUNDS_DIR
            / f"{sound_slot}_{int(time.time())}{src.suffix.lower()}"
        )
        try:
            shutil.copy2(src, dest)
            self.config.setdefault("sounds", {})[sound_slot] = str(dest)
            save_config(self.config)
            self.cmd_menu.update_sound_label(sound_slot, src.name)
            self.sfx.play(sound_slot)
            self.pop_manual_diamond_message(f"saved {sound_slot} sound.")
        except Exception as exc:
            print(f"[Sound Upload Error] {exc}")
            self.pop_manual_diamond_message("couldn't save sound.")

    def _on_sound_reset(self, sound_slot: str):
        if sound_slot in self.config.get("sounds", {}):
            del self.config["sounds"][sound_slot]
            save_config(self.config)
        default_name = DEFAULT_SOUND_FILES.get(sound_slot, "Default")
        self.cmd_menu.update_sound_label(sound_slot, default_name)
        self.pop_manual_diamond_message(f"reset {sound_slot} sound.")

    def _on_sound_toggled(self, sound_slot: str, enabled: bool):
        self.config.setdefault("sound_enabled", {})[sound_slot] = bool(enabled)
        save_config(self.config)

    def _get_active_palette(self) -> dict:
        if self.active_theme_name == "Custom RGB":
            return build_custom_palette(self.config.get("custom_rgb", {}))
        return LAYOUT_THEMES.get(self.active_theme_name, LAYOUT_THEMES["Ocean Deep"])

    def _on_bubble_offset_changed(self, ox: int, oy: int):
        self.config["bubble_offset"] = {"x": ox, "y": oy}
        save_config(self.config)
        if self.cloud.isVisible():
            self._position_cloud_beside_sprite()

    def _on_bubble_popup_toggled(self, enabled: bool):
        self.bubble_popup_enabled = enabled
        self.config["bubble_popup_enabled"] = enabled
        save_config(self.config)
        if not enabled:
            self.cloud.hide()
        self.pop_manual_diamond_message(
            "bubble pop-up on." if enabled else "bubble pop-up off."
        )

    def _on_fish_voice_changed(self, voice_cfg: dict):
        self.config["fish_voice"] = dict(voice_cfg)
        save_config(self.config)
        state = "on" if voice_cfg.get("enabled") else "off"
        self.pop_manual_diamond_message(f"fish voice {state}.")

    def _snap_diamond_top_left_test(self):
        avail = self._get_screen_avail_rect()
        target_sprite_x = avail.left() + 36
        target_sprite_y = avail.top() + 48
        self.move(
            target_sprite_x - self.SPRITE_POS.x(),
            target_sprite_y - self.SPRITE_POS.y(),
        )
        self.pop_manual_diamond_message("top-left snap check, lil bro.")

    def _on_auto_scan_toggled(self, enabled: bool):
        self.auto_screen_scan = enabled
        self.config["auto_screen_scan"] = enabled
        save_config(self.config)
        msg = (
            "live desktop talk on."
            if enabled
            else "live desktop talk off. prompt still works."
        )
        self.pop_manual_diamond_message(msg)

    def _on_theme_selected(self, theme_name: str):
        if theme_name not in LAYOUT_THEMES and theme_name != "Custom RGB":
            return
        self.active_theme_name = theme_name
        self.config["theme"] = theme_name
        save_config(self.config)
        self._apply_active_theme_to_widgets()
        self.pop_manual_diamond_message(f"theme: {theme_name.lower()}.")

    def _on_custom_rgb_changed(self, rgb_dict: dict):
        self.config["custom_rgb"] = dict(rgb_dict)
        self.active_theme_name = "Custom RGB"
        self.config["theme"] = "Custom RGB"
        save_config(self.config)
        self._apply_active_theme_to_widgets()
        self.pop_manual_diamond_message("custom rgb applied.")

    def _apply_active_theme_to_widgets(self):
        pal = self._get_active_palette()
        self.cmd_menu.apply_theme_palette(pal)
        self.cloud.set_theme(pal["bubble_bg"], "#000000", pal["bubble_text"])
        self.prompt_scroll.setStyleSheet(f"""
            QScrollArea {{
                background: {pal['row_bg']};
                border: 2px solid #000000;
                border-radius: 6px;
            }}
            QScrollBar:horizontal {{
                height: 6px;
                background: #020617;
            }}
            QScrollBar::handle:horizontal {{
                background: {pal['accent_hover']};
                border-radius: 3px;
                min-width: 18px;
            }}
        """)
        self.custom_input.setStyleSheet(f"""
            QLineEdit {{
                background: {pal['row_bg']};
                color: {pal['text_color']};
                border: none;
                border-radius: 6px;
                padding: 2px 6px;
                font-family: Consolas;
                font-size: 11px;
                font-weight: bold;
            }}
        """)
        self.enter_btn.setStyleSheet(f"""
            QPushButton {{
                background: {pal['accent']};
                color: #ffffff;
                border: 2px solid #000000;
                border-radius: 6px;
                padding: 4px 10px;
                font-family: Consolas;
                font-size: 11px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: {pal['accent_hover']};
            }}
            QPushButton:pressed {{
                background: {pal['panel_bg']};
            }}
        """)

    def _resolve_sprite_path(self, slot_key: str) -> Path:
        saved = self.config.get("sprites", {}).get(slot_key, "")
        if saved:
            p = Path(saved)
            if p.exists():
                return p
        return BASE_DIR / DEFAULT_SPRITE_FILES[slot_key]

    def _load_slot_media(self, slot_key: str, target_size: QSize = SPRITE_SIZE):
        """Loads either an animated GIF (QMovie) or static PNG/image (QPixmap) for a slot."""
        path = self._resolve_sprite_path(slot_key)
        if not path.exists():
            return None, None
        if path.suffix.lower() == ".gif":
            mov = self.load_scaled_gif(path, target_size, cache_tag=slot_key)
            if mov:
                return mov, None
        pm = self.load_scaled_png(path, target_size)
        return None, pm

    def _reload_all_sprites(self):
        for m in self._movies:
            m.stop()
        self._movies.clear()

        self.idle_movie, self.idle_static = self._load_slot_media("idle", SPRITE_SIZE)
        self.talk_movie, self.talk_static = self._load_slot_media("talk", SPRITE_SIZE)
        if not self.talk_movie and not self.talk_static:
            self.talk_movie, self.talk_static = self.idle_movie, self.idle_static

        self.custom_movie, self.custom_pixmap = self._load_slot_media(
            "custom", SPRITE_SIZE
        )
        self.gear_movie, self.gear_pixmap = self._load_slot_media("gear", GEAR_SIZE)
        self.dead_net_movie, self.dead_net_pixmap = self._load_slot_media(
            "offline", SPRITE_SIZE
        )

        if self.gear_movie:
            self.gear_label.setMovie(self.gear_movie)
            self.gear_movie.start()
        elif self.gear_pixmap and not self.gear_pixmap.isNull():
            self.gear_label.setPixmap(self.gear_pixmap)
        else:
            self.gear_label.setText("[GEAR]")
            self.gear_label.setStyleSheet("color: #facc15; font: bold 11px Consolas;")

        if self.command_bar_open:
            self._apply_slot_visual("custom", "[ CUSTOM ]", "#4ade80", is_diamond=False)
        elif self.is_online is False:
            self._apply_slot_visual(
                "offline", "[ NO INTERNET ]", "#64748b", is_diamond=False
            )
        else:
            self._apply_slot_visual("idle", "[ ONLINE ]", "#22d3ee", is_diamond=True)

    def _apply_slot_visual(
        self, slot_key: str, fallback: str, color: str, is_diamond: bool = True
    ):
        if slot_key == "idle":
            mov, pm = self.idle_movie, self.idle_static
        elif slot_key == "talk":
            mov, pm = self.talk_movie, self.talk_static
        elif slot_key == "custom":
            mov, pm = self.custom_movie, self.custom_pixmap
        elif slot_key == "offline":
            mov, pm = self.dead_net_movie, self.dead_net_pixmap
        else:
            mov, pm = None, None

        if mov:
            self.set_movie(mov, fallback, color, is_diamond=is_diamond)
        else:
            self.set_static_pixmap(pm, fallback, color, is_diamond=is_diamond)

    def _on_sprite_uploaded(self, slot_key: str, source_path: str):
        src = Path(source_path)
        if not src.exists():
            return
        CUSTOM_SPRITES_DIR.mkdir(exist_ok=True)
        dest = (
            CUSTOM_SPRITES_DIR
            / f"{slot_key}_{int(time.time())}{src.suffix.lower()}"
        )
        try:
            shutil.copy2(src, dest)
            self.config["sprites"][slot_key] = str(dest)
            save_config(self.config)
            self.cmd_menu.update_slot_label(slot_key, src.name)
            self._reload_all_sprites()
            self.pop_manual_diamond_message(f"saved {slot_key} sprite.")
        except Exception as exc:
            print(f"[Sprite Upload Error] {exc}")
            self.pop_manual_diamond_message("couldn't save sprite.")

    def _on_sprite_reset(self, slot_key: str):
        if slot_key in self.config.get("sprites", {}):
            del self.config["sprites"][slot_key]
            save_config(self.config)
        self.cmd_menu.update_slot_label(slot_key, "Default")
        self._reload_all_sprites()
        self.pop_manual_diamond_message(f"reset {slot_key} sprite.")

    def init_ui(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(self.CONTAINER_SIZE)

        self.sprite_label = QLabel(self)
        self.sprite_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sprite_label.setFixedSize(SPRITE_SIZE)
        self.sprite_label.setMouseTracking(True)
        self.sprite_label.move(self.SPRITE_POS)

        self.gear_label = QLabel(self)
        self.gear_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.gear_label.setFixedSize(GEAR_SIZE)
        self.gear_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.gear_label.setMouseTracking(True)
        gx = self.SPRITE_POS.x() + SPRITE_SIZE.width() - GEAR_SIZE.width() + 4
        gy = self.SPRITE_POS.y() - 10
        self.gear_label.move(gx, gy)

        self.cmd_menu = CommandMenuPopup(self.config, self.sfx, self)
        menu_x = max(
            8,
            min(
                self.CONTAINER_SIZE.width() - self.cmd_menu.MENU_SIZE.width() - 8,
                self.SPRITE_POS.x()
                + SPRITE_SIZE.width()
                - self.cmd_menu.MENU_SIZE.width()
                - 36,
            ),
        )
        self.cmd_menu.move(menu_x, 0)
        self.cmd_menu.hide()

        self.cloud = CloudBubble(self)
        self.cloud.hide()

        self._reload_all_sprites()
        self.gear_label.show()
        self.gear_label.raise_()

        self.input_bar = QWidget(self)
        bar_layout = QHBoxLayout(self.input_bar)
        bar_layout.setContentsMargins(0, 0, 0, 0)
        bar_layout.setSpacing(6)

        self.prompt_scroll = QScrollArea(self.input_bar)
        self.prompt_scroll.setFixedSize(215, 30)
        self.prompt_scroll.setWidgetResizable(False)
        self.prompt_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.prompt_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

        self.custom_input = QLineEdit()
        self.custom_input.setPlaceholderText("Talk to Gemini or /run app, /turn color...")
        self.custom_input.setFixedSize(360, 22)
        self.custom_input.returnPressed.connect(self.submit_custom_input)
        self.prompt_scroll.setWidget(self.custom_input)

        self.enter_btn = QPushButton("Send", self.input_bar)
        self.enter_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.enter_btn.installEventFilter(self._btn_filter)
        self.enter_btn.clicked.connect(self.submit_custom_input)

        bar_layout.addWidget(self.prompt_scroll)
        bar_layout.addWidget(self.enter_btn)
        self.input_bar.adjustSize()
        bar_x = (
            self.SPRITE_POS.x()
            + (SPRITE_SIZE.width() - self.input_bar.width()) // 2
        )
        bar_y = self.SPRITE_POS.y() + SPRITE_SIZE.height() + 6
        self.input_bar.move(max(6, bar_x), bar_y)
        self.input_bar.hide()

        self._apply_active_theme_to_widgets()
        self._position_cloud_beside_sprite()
        self._move_to_default_bottom_right()

    def _get_screen_avail_rect(self) -> QRect:
        screen = QApplication.screenAt(
            self.sprite_label.mapToGlobal(
                QPoint(SPRITE_SIZE.width() // 2, SPRITE_SIZE.height() // 2)
            )
        )
        if not screen:
            screen = QApplication.primaryScreen()
        if screen:
            return screen.availableGeometry()
        return QRect(0, 0, 1920, 1080)

    def _rect_overlap_area(self, a: QRect, b: QRect) -> int:
        inter = a.intersected(b)
        if inter.isEmpty():
            return 0
        return inter.width() * inter.height()

    def _position_cloud_beside_sprite(self, allow_window_shift: bool = True):
        """Keeps bubble inside screen bounds & unclipped without teleporting or hiding."""
        bw = self.cloud.width()
        bh = self.cloud.height()
        if bw <= 0 or bh <= 0:
            return

        avail = self._get_screen_avail_rect()
        sprite_global = QRect(
            self.sprite_label.mapToGlobal(QPoint(0, 0)),
            self.sprite_label.size(),
        )
        menu_global = (
            QRect(self.cmd_menu.mapToGlobal(QPoint(0, 0)), self.cmd_menu.size())
            if self.cmd_menu.isVisible()
            else None
        )

        ox = int(self.config.get("bubble_offset", {}).get("x", 0))
        oy = int(self.config.get("bubble_offset", {}).get("y", 0))

        candidates = [
            (
                sprite_global.left() - bw + 58 + ox,
                sprite_global.top() - bh + 34 + oy,
                "bottom-right",
            ),
            (
                sprite_global.right() - 58 + ox,
                sprite_global.top() - bh + 34 + oy,
                "bottom-left",
            ),
            (
                sprite_global.left() - bw - 8 + ox,
                sprite_global.center().y() - bh // 2 + oy,
                "right",
            ),
            (
                sprite_global.right() + 8 + ox,
                sprite_global.center().y() - bh // 2 + oy,
                "left",
            ),
            (
                sprite_global.left() - bw + 58 + ox,
                sprite_global.bottom() - 24 + oy,
                "top-right",
            ),
            (
                sprite_global.right() - 58 + ox,
                sprite_global.bottom() - 24 + oy,
                "top-left",
            ),
        ]

        best = None
        best_score = float("inf")

        for raw_x, raw_y, tail_side in candidates:
            clamped_x = max(avail.left() + 6, min(avail.right() - bw - 6, raw_x))
            clamped_y = max(avail.top() + 6, min(avail.bottom() - bh - 6, raw_y))
            cand_rect = QRect(clamped_x, clamped_y, bw, bh)

            clip_penalty = abs(clamped_x - raw_x) * 25 + abs(clamped_y - raw_y) * 25
            sprite_overlap = self._rect_overlap_area(cand_rect, sprite_global) * 60
            menu_overlap = (
                self._rect_overlap_area(cand_rect, menu_global) * 120
                if menu_global
                else 0
            )
            score = clip_penalty + sprite_overlap + menu_overlap

            if score < best_score:
                best_score = score
                best = (clamped_x, clamped_y, tail_side)

        if best:
            gx, gy, tail_side = best
            local_pos = self.mapFromGlobal(QPoint(gx, gy))

            if allow_window_shift:
                shift_dx = 0
                shift_dy = 0
                if local_pos.x() < 4:
                    shift_dx = local_pos.x() - 4
                elif local_pos.x() + bw > self.width() - 4:
                    shift_dx = (local_pos.x() + bw) - (self.width() - 4)

                if local_pos.y() < 4:
                    shift_dy = local_pos.y() - 4
                elif local_pos.y() + bh > self.height() - 4:
                    shift_dy = (local_pos.y() + bh) - (self.height() - 4)

                if shift_dx != 0 or shift_dy != 0:
                    new_win_x = max(
                        avail.left() - self.SPRITE_POS.x() + 4,
                        min(
                            avail.right()
                            - self.SPRITE_POS.x()
                            - SPRITE_SIZE.width()
                            - 4,
                            self.x() + shift_dx,
                        ),
                    )
                    new_win_y = max(
                        avail.top() - self.SPRITE_POS.y() + 4,
                        min(
                            avail.bottom()
                            - self.SPRITE_POS.y()
                            - SPRITE_SIZE.height()
                            - 4,
                            self.y() + shift_dy,
                        ),
                    )
                    if new_win_x != self.x() or new_win_y != self.y():
                        self.move(new_win_x, new_win_y)
                        local_pos = self.mapFromGlobal(QPoint(gx, gy))

            final_x = max(2, min(self.width() - bw - 2, local_pos.x()))
            final_y = max(2, min(self.height() - bh - 2, local_pos.y()))
            self.cloud.set_tail_side(tail_side)
            self.cloud.move(final_x, final_y)

    def pause_screen_scan_for(self, seconds: float):
        self.scan_pause_until = max(
            self.scan_pause_until, time.monotonic() + seconds
        )
        remaining_ms = max(
            1, int((self.scan_pause_until - time.monotonic()) * 1000)
        )
        self.post_speech_timer.start(remaining_ms)

    def _toggle_command_menu(self):
        if self.cmd_menu.isVisible():
            self.cmd_menu.animate_close()
        else:
            self.cmd_menu.animate_open()
            self.gear_label.raise_()
        if self.cloud.isVisible():
            self._position_cloud_beside_sprite()

    def _run_command_from_menu(self, cmd_text: str):
        self.cmd_menu.animate_close()
        self.pause_screen_scan_for(POST_REPLY_SCAN_PAUSE_S)
        self._dispatch_text_or_command(cmd_text)

    def _set_hover_state(self, hovered: bool):
        if self.is_hovered == hovered:
            return
        self.is_hovered = hovered
        self.hover_lift_y = -6 if hovered else 0
        if hovered:
            self.sfx.play("hover")
        if self.current_pixmap and not self.current_pixmap.isNull():
            self._render_sprite_frame(self.current_pixmap, force=True)

    def _trigger_click_effect(self):
        self.sfx.play("click")
        self.click_pulse_scale = 1.12
        if self.current_pixmap and not self.current_pixmap.isNull():
            self._render_sprite_frame(self.current_pixmap, force=True)
        self.click_anim_timer.start(130)

    def _reset_click_pulse(self):
        self.click_pulse_scale = 1.0
        if self.current_pixmap and not self.current_pixmap.isNull():
            self._render_sprite_frame(self.current_pixmap, force=True)

    def open_command_mode(self):
        """Switches the bot to Custom sprite and shows the prompt bar while pausing screen scan."""
        if self.cmd_menu.isVisible():
            self.cmd_menu.animate_close()
        self.command_bar_open = True
        self._command_mode_paused_scan = True
        self.post_speech_timer.stop()
        self._apply_slot_visual("custom", "[ CUSTOM ]", "#4ade80", is_diamond=False)
        self.gear_label.raise_()
        self.input_bar.show()
        self.input_bar.raise_()
        self.custom_input.setFocus()

    def return_to_normal_mode(self, pause_scan_s: float = 0.0):
        """Closes the prompt bar and restores normal mode without breaking auto screen scan."""
        self.command_bar_open = False
        self._command_mode_paused_scan = False
        self.input_bar.hide()
        self.custom_input.clearFocus()
        if pause_scan_s > 0:
            self.scan_pause_until = max(
                self.scan_pause_until, time.monotonic() + pause_scan_s
            )
            self.post_speech_timer.start(int(pause_scan_s * 1000))
        else:
            self.post_speech_timer.stop()
            self.scan_pause_until = 0.0
        if not self.cloud.isVisible() and self.is_online:
            self._apply_slot_visual("idle", "[ ONLINE ]", "#22d3ee", is_diamond=True)
        self.gear_label.raise_()

    def _on_post_speech_wait_done(self):
        if time.monotonic() >= self.scan_pause_until:
            self.scan_pause_until = 0.0

    def _is_screen_scan_disabled(self, require_auto_scan: bool = True) -> bool:
        if self.muted_by_user:
            return True
        if require_auto_scan and not self.auto_screen_scan:
            return True
        if self.command_bar_open or self._command_mode_paused_scan:
            return True
        if time.monotonic() < self.scan_pause_until:
            return True
        return False

    def _apply_tint_to_pixmap(self, pm: QPixmap) -> QPixmap:
        if self.showing_custom_sprite:
            return pm
        active_color = self.diamond_tint_color
        if self.disco_active:
            c = QColor()
            c.setHsv(self.disco_hue % 360, 230, 255)
            active_color = c
        if not active_color or not active_color.isValid():
            return pm
        tinted = QPixmap(pm.size())
        tinted.fill(Qt.GlobalColor.transparent)
        painter = QPainter(tinted)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        painter.drawPixmap(0, 0, pm)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceAtop)
        tint = QColor(active_color)
        tint.setAlpha(145)
        painter.fillRect(tinted.rect(), tint)
        painter.end()
        return tinted

    def _render_sprite_frame(self, base_pm: QPixmap, force: bool = False):
        if base_pm.isNull():
            return
        tint_key = (
            self.disco_hue % 360
            if self.disco_active
            else (self.diamond_tint_color.rgba() if self.diamond_tint_color else None)
        )
        key = (
            base_pm.cacheKey(),
            self.showing_custom_sprite,
            tint_key,
            self.flipped_x,
            round(self.click_pulse_scale, 3),
            self.is_hovered,
            self.spin_angle,
            self.hover_lift_y + self.hop_offset_y,
        )
        if not force and key == self._last_rendered_key:
            return
        self._last_rendered_key = key

        pm = self._apply_tint_to_pixmap(base_pm)

        if self.flipped_x:
            pm = pm.transformed(
                QTransform().scale(-1, 1), Qt.TransformationMode.FastTransformation
            )

        scale = self.click_pulse_scale * (1.04 if self.is_hovered else 1.0)
        if abs(scale - 1.0) > 0.001 or self.spin_angle != 0:
            transform = QTransform().rotate(self.spin_angle).scale(scale, scale)
            pm = pm.transformed(transform, Qt.TransformationMode.FastTransformation)

        canvas = QPixmap(SPRITE_SIZE)
        canvas.fill(Qt.GlobalColor.transparent)
        painter = QPainter(canvas)
        px = (SPRITE_SIZE.width() - pm.width()) // 2
        py = (SPRITE_SIZE.height() - pm.height()) // 2
        painter.drawPixmap(px, py, pm)
        painter.end()

        self.sprite_label.setPixmap(canvas)
        dy = self.hover_lift_y + self.hop_offset_y
        self.sprite_label.move(self.SPRITE_POS.x(), self.SPRITE_POS.y() + dy)
        self.gear_label.raise_()

    def _on_movie_frame(self):
        if self.active_movie and self.active_movie.state() == QMovie.MovieState.Running:
            self.current_pixmap = self.active_movie.currentPixmap()
            self._render_sprite_frame(self.current_pixmap)

    def _step_spin(self):
        self.spin_angle = (self.spin_angle + 24) % 360
        if self.current_pixmap and not self.current_pixmap.isNull():
            self._render_sprite_frame(self.current_pixmap, force=True)
        if self.spin_angle == 0:
            self.spin_timer.stop()
            if self.current_pixmap and not self.current_pixmap.isNull():
                self._render_sprite_frame(self.current_pixmap, force=True)

    def _step_hop(self):
        self.hop_step += 1
        if self.hop_step <= 8:
            self.hop_offset_y = -int(22 * math.sin((self.hop_step / 8.0) * math.pi))
        else:
            self.hop_offset_y = 0
            self.hop_step = 0
            self.hop_timer.stop()
        if self.current_pixmap and not self.current_pixmap.isNull():
            self._render_sprite_frame(self.current_pixmap, force=True)

    def _step_disco(self):
        self.disco_hue = (self.disco_hue + 18) % 360
        if self.current_pixmap and not self.current_pixmap.isNull():
            self._render_sprite_frame(self.current_pixmap)

    def _stop_disco(self):
        self.disco_active = False
        self.disco_timer.stop()
        if self.current_pixmap and not self.current_pixmap.isNull():
            self._render_sprite_frame(self.current_pixmap, force=True)

    def _step_gdi(self):
        if not self.gdi.is_running():
            self.gdi_timer.stop()
            return
        self.gdi.step()
        self.raise_()
        if self.cloud.isVisible():
            self.cloud.raise_()
        if self.cmd_menu.isVisible():
            self.cmd_menu.raise_()

    def _show_bubble_and_pause_after_said(
        self, text: str, duration_ms: int = BUBBLE_SHOW_MS
    ):
        pal = self._get_active_palette()
        self.hide_timer.stop()
        self.post_voice_hide_timer.stop()
        self._bubble_min_hold_done = False

        voice_cfg = self.config.get("fish_voice", {})
        will_speak = self.speaker.is_voice_active(text, voice_cfg)
        self._voice_still_playing = will_speak

        self.scan_pause_until = (
            time.monotonic() + (duration_ms / 1000.0) + POST_REPLY_SCAN_PAUSE_S
        )
        self.post_speech_timer.start(
            duration_ms + int(POST_REPLY_SCAN_PAUSE_S * 1000)
        )
        self._active_voice_utt_id = self.speaker.speak_async(text, voice_cfg)

        if self.bubble_popup_enabled:
            was_hidden = not self.cloud.isVisible()
            self.cloud.set_theme(pal["bubble_bg"], "#000000", pal["bubble_text"])
            self.cloud.set_message(text)
            self._position_cloud_beside_sprite(allow_window_shift=True)
            self.cloud.show()
            if was_hidden:
                self.sfx.play("popup")
            self.cloud.play_pop_in()
            self.cloud.raise_()
        else:
            self.cloud.hide()

        self.sprite_label.move(
            self.SPRITE_POS.x(),
            self.SPRITE_POS.y() + self.hover_lift_y + self.hop_offset_y,
        )
        self.gear_label.raise_()
        self.hide_timer.start(duration_ms)

    def trigger_run_app(self, app_arg: str):
        self.showing_custom_sprite = False
        if self.is_online:
            self._apply_slot_visual("talk", "[ RUN APP ]", "#67e8f9", is_diamond=True)
        self._show_bubble_and_pause_after_said(
            f"scanning pc for {app_arg or 'app'}...", 2500
        )

        def worker():
            try:
                ok, status = scan_pc_and_launch_app(app_arg)
                if ok:
                    self.manual_reply_signal.emit(f"{status}.")
                else:
                    self.manual_reply_signal.emit(f"{status}.")
            except Exception as exc:
                print(f"[RunApp Error] {exc}")
                self.manual_reply_signal.emit("failed to launch app.")

        threading.Thread(target=worker, daemon=True).start()

    def trigger_spin(self):
        self.spin_angle = 24
        self.spin_timer.start(25)
        self.showing_custom_sprite = False
        if self.is_online:
            self._apply_slot_visual("talk", "[ SPIN ]", "#67e8f9", is_diamond=True)
        self._show_bubble_and_pause_after_said("weeeee okay dizzy now", BUBBLE_SHOW_MS)

    def trigger_hop(self):
        self.hop_step = 0
        self.hop_timer.start(25)
        self.showing_custom_sprite = False
        if self.is_online:
            self._apply_slot_visual("talk", "[ HOP ]", "#67e8f9", is_diamond=True)
        self._show_bubble_and_pause_after_said("little jump, no big deal", 3500)

    def trigger_flip(self):
        self.flipped_x = not self.flipped_x
        self.showing_custom_sprite = False
        if self.current_pixmap and not self.current_pixmap.isNull():
            self._render_sprite_frame(self.current_pixmap, force=True)
        if self.is_online:
            self._apply_slot_visual("talk", "[ FLIP ]", "#67e8f9", is_diamond=True)
        self._show_bubble_and_pause_after_said("flipped sideways", 3500)

    def trigger_disco(self):
        self.showing_custom_sprite = False
        self.disco_active = True
        self.disco_timer.start(50)
        self.disco_stop_timer.start(int(GDI_DURATION_S * 1000))
        if self.is_online:
            self._apply_slot_visual("talk", "[ DISCO ]", "#67e8f9", is_diamond=True)
        self._show_bubble_and_pause_after_said(
            "five seconds of rgb, wild", int(GDI_DURATION_S * 1000)
        )

    def trigger_turn_color(self, raw_color: str):
        cleaned = raw_color.strip().strip('"').strip("'")
        self.showing_custom_sprite = False
        if not cleaned:
            if self.is_online:
                self._apply_slot_visual("talk", "[ TURN ]", "#67e8f9", is_diamond=True)
            self._show_bubble_and_pause_after_said(
                "give a color like /turn red", 3500
            )
            return

        if cleaned.lower() in ("reset", "default", "none", "blue", "normal"):
            self.diamond_tint_color = None
            self.disco_active = False
            self.disco_timer.stop()
            msg = "back to blue"
        else:
            qcol = QColor(cleaned)
            if not qcol.isValid():
                if self.is_online:
                    self._apply_slot_visual("talk", "[ TURN ]", "#67e8f9", is_diamond=True)
                self._show_bubble_and_pause_after_said(
                    f"unknown color {cleaned}", 3500
                )
                return
            self.disco_active = False
            self.disco_timer.stop()
            self.diamond_tint_color = qcol
            msg = f"turned {cleaned}"

        if self.is_online:
            self._apply_slot_visual("talk", "[ TURN ]", "#67e8f9", is_diamond=True)
        self._show_bubble_and_pause_after_said(msg, 3500)

    def trigger_gdi_effect(self, effect_name: str, line: str):
        started = self.gdi.start(effect_name, duration_s=GDI_DURATION_S)
        self.showing_custom_sprite = False
        if self.is_online:
            self._apply_slot_visual("talk", "[ GDI ]", "#67e8f9", is_diamond=True)
        if started:
            if effect_name == "invert":
                hdc = self.gdi.user32.GetDC(0)
                if hdc:
                    self.gdi.gdi32.BitBlt(
                        hdc,
                        0,
                        0,
                        self.gdi.sw,
                        self.gdi.sh,
                        hdc,
                        0,
                        0,
                        self.gdi.NOTSRCCOPY,
                    )
                    self.gdi.user32.ReleaseDC(0, hdc)
                self.gdi_timer.start(int(GDI_DURATION_S * 1000))
            else:
                self.gdi_timer.start(40)
            msg = line
        else:
            msg = "gdi only works on windows."
        self._show_bubble_and_pause_after_said(msg, int(GDI_DURATION_S * 1000))

    def pop_manual_diamond_message(self, text: str):
        clean = sanitize_single_message(text, max_words=20)
        if not clean:
            return
        self.showing_custom_sprite = False
        if self.is_online:
            self._apply_slot_visual(
                "talk", "[ NEW MESSAGE ]", "#67e8f9", is_diamond=True
            )
        self._show_bubble_and_pause_after_said(clean, BUBBLE_SHOW_MS)

    def _generate_with_fallback(self, contents):
        if not self.client:
            self.client = create_gemini_client(self.config)
        if not self.client:
            raise RuntimeError("Missing Gemini API key")

        auto_model = bool(self.config.get("auto_model", True))
        candidates = (
            MODEL_CANDIDATES
            if auto_model
            else [MODEL_CANDIDATES[self.model_idx % len(MODEL_CANDIDATES)]]
        )
        last_exc = None
        for offset in range(len(candidates)):
            idx = (self.model_idx + offset) % len(candidates)
            model_id = candidates[idx]
            try:
                resp = self.client.models.generate_content(
                    model=model_id,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=PET_PERSONALITY,
                        temperature=0.8,
                    ),
                )
                self.model_idx = idx
                return resp
            except Exception as exc:
                last_exc = exc
                continue
        raise last_exc or RuntimeError("All models failed")

    def _ask_live_or_fallback(self, prompt_text: str) -> str:
        """Uses real-time desktop Live stream first, automatically falling back if needed."""
        self.live_stream.restart_if_key_changed()
        live_reply = self.live_stream.ask_live(prompt_text, timeout_s=6.0)
        if live_reply and live_reply.strip():
            return sanitize_single_message(live_reply.strip(), max_words=20)

        title, jpeg_bytes = capture_live_frame_jpeg(max_age_s=0.6)
        contents = [prompt_text]
        if jpeg_bytes:
            try:
                pil_img = Image.open(io.BytesIO(jpeg_bytes)).convert("RGB")
                contents = [pil_img, f"Active window: '{title}'. {prompt_text}"]
            except Exception:
                pass
        response = self._generate_with_fallback(contents)
        return sanitize_single_message((response.text or "").strip(), max_words=20)

    def ask_ai_manual_prompt(self, user_prompt: str):
        if self._is_shut_up_command(user_prompt):
            self.muted_by_user = True
            self.pop_manual_diamond_message("...")
            return

        if self._is_talk_again_command(user_prompt):
            self.muted_by_user = False
            self.pop_manual_diamond_message("alright i'm back.")
            return

        if self.muted_by_user:
            self.pop_manual_diamond_message("...")
            return

        if not resolve_gemini_api_key(self.config):
            self.pop_manual_diamond_message("add gemini api key in customize.")
            return

        if self.is_thinking:
            self.pop_manual_diamond_message("still thinking, hold on.")
            return

        self.is_thinking = True
        self._show_bubble_and_pause_after_said("thinking...", 2500)

        def worker():
            try:
                recent_chat = (
                    " | ".join(
                        f"user: {u} -> ai: {a}" for u, a in self.chat_history[-4:]
                    )
                    if self.chat_history
                    else "none"
                )
                avoid_list = (
                    ", ".join(self.recent_replies[-5:])
                    if self.recent_replies
                    else "none"
                )
                raw_instr = (
                    f"User said: '{user_prompt}'. "
                    f"Recent chat: [{recent_chat}]. "
                    "Respond naturally like a real human looking at the screen. "
                    f"Do not repeat these recent messages: [{avoid_list}]. "
                    "Reply with ONE single message only, max 20 words."
                )
                prompt = self._build_live_context_prompt(
                    raw_instr, user_prompt=user_prompt
                )
                reply = self._ask_live_or_fallback(prompt)
                if not reply:
                    reply = "say that again."
                self.chat_history.append((user_prompt, reply))
                if len(self.chat_history) > 8:
                    self.chat_history.pop(0)
                self.recent_replies.append(reply)
                if len(self.recent_replies) > 10:
                    self.recent_replies.pop(0)
                self.manual_reply_signal.emit(reply)
            except Exception as exc:
                print(f"[Prompt Error] {exc}")
                if not check_internet():
                    self.connection_signal.emit(False)
                else:
                    self.manual_reply_signal.emit("retrying live stream, give it a sec.")
            finally:
                self.is_thinking = False

        threading.Thread(target=worker, daemon=True).start()

    def _dispatch_text_or_command(self, text: str):
        if not text:
            return

        lower = text.lower()
        if lower == "/run" or lower.startswith("/run "):
            app_arg = text[4:].strip()
            self.trigger_run_app(app_arg)
            return

        if lower == "/spin":
            self.trigger_spin()
            return

        if lower == "/hop":
            self.trigger_hop()
            return

        if lower == "/flip":
            self.trigger_flip()
            return

        if lower == "/disco":
            self.trigger_disco()
            return

        if lower == "/roast":
            self.muted_by_user = False
            self.judge_screen(force_manual=True)
            return

        if lower == "/help":
            self.pop_manual_diamond_message(
                "/run /spin /turn /hop /flip /disco /melt /invert /shake /tunnel /wave /mirror /zoom /glitch /confetti"
            )
            return

        if lower.startswith("/turn"):
            color_arg = text[5:].strip()
            self.trigger_turn_color(color_arg)
            return

        if lower == "/melt":
            self.trigger_gdi_effect("melt", "screen melting for five seconds.")
            return

        if lower == "/invert":
            self.trigger_gdi_effect("invert", "colors flipped for five seconds.")
            return

        if lower == "/shake":
            self.trigger_gdi_effect("shake", "little screen shake.")
            return

        if lower == "/tunnel":
            self.trigger_gdi_effect("tunnel", "tunnel vision for five seconds.")
            return

        if lower == "/wave":
            self.trigger_gdi_effect("wave", "screen wobbling a bit.")
            return

        if lower == "/mirror":
            self.trigger_gdi_effect("mirror", "mirror slice active.")
            return

        if lower == "/zoom":
            self.trigger_gdi_effect("zoom", "zoom pulse for five seconds.")
            return

        if lower == "/glitch":
            self.trigger_gdi_effect("glitch", "some glitch bars.")
            return

        if lower == "/confetti":
            self.trigger_gdi_effect("confetti", "random pixel confetti.")
            return

        self.ask_ai_manual_prompt(text)

    def submit_custom_input(self):
        text = self.custom_input.text().strip()
        self.custom_input.clear()
        if not text:
            self.return_to_normal_mode(pause_scan_s=0.0)
            return
        self.return_to_normal_mode(pause_scan_s=POST_REPLY_SCAN_PAUSE_S)
        self._dispatch_text_or_command(text)

    def _move_to_default_bottom_right(self):
        screen = QApplication.primaryScreen()
        if screen:
            avail = screen.availableGeometry()
            target_sprite_x = avail.right() - SPRITE_SIZE.width() - 120
            target_sprite_y = avail.bottom() - SPRITE_SIZE.height() - 42
            x = max(
                avail.left() - self.SPRITE_POS.x() + 10,
                target_sprite_x - self.SPRITE_POS.x(),
            )
            y = max(
                avail.top() - self.SPRITE_POS.y() + 10,
                target_sprite_y - self.SPRITE_POS.y(),
            )
            self.move(x, y)
        else:
            self.move(680, 320)

    def load_scaled_gif(
        self, path: Path, target_size: QSize = SPRITE_SIZE, cache_tag: str = "gif"
    ):
        if not path.exists():
            return None

        try:
            img = Image.open(path)
            frames = []
            durations = []

            for frame in ImageSequence.Iterator(img):
                scaled = frame.convert("RGBA").resize(
                    (target_size.width(), target_size.height()),
                    Image.Resampling.NEAREST,
                )
                frames.append(scaled)
                durations.append(max(20, int(frame.info.get("duration", 100))))

            if not frames:
                return None

            CACHE_DIR.mkdir(exist_ok=True)
            out_path = (
                CACHE_DIR / f"scaled_{cache_tag}_{path.stem.replace(' ', '_')}.gif"
            )

            buf = io.BytesIO()
            frames[0].save(
                buf,
                format="GIF",
                save_all=True,
                append_images=frames[1:],
                duration=durations,
                loop=0,
                disposal=2,
            )
            out_path.write_bytes(buf.getvalue())

            movie = QMovie(str(out_path))
            movie.setCacheMode(QMovie.CacheMode.CacheAll)
            if target_size == SPRITE_SIZE:
                movie.frameChanged.connect(self._on_movie_frame)
            self._movies.append(movie)
            return movie
        except Exception as exc:
            print(f"[GIF Load Error: {path.name}] {exc}")
            return None

    def load_scaled_png(self, path: Path, target_size: QSize = SPRITE_SIZE):
        if not path.exists():
            return None
        pm = QPixmap(str(path))
        if pm.isNull():
            return None
        return pm.scaled(
            target_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )

    def set_movie(
        self,
        movie: QMovie | None,
        fallback: str,
        color: str,
        is_diamond: bool = True,
    ):
        self.showing_custom_sprite = not is_diamond
        for m in self._movies:
            if m != movie and m != self.gear_movie:
                m.stop()
        self.active_movie = movie
        if movie:
            self.sprite_label.clear()
            movie.start()
            pm = movie.currentPixmap()
            if not pm.isNull():
                self.current_pixmap = pm
                self._render_sprite_frame(pm, force=True)
        else:
            self.sprite_label.setText(fallback)
            self.sprite_label.setStyleSheet(f"color: {color}; font: bold 14px Consolas;")
        self.sprite_label.move(
            self.SPRITE_POS.x(),
            self.SPRITE_POS.y() + self.hover_lift_y + self.hop_offset_y,
        )
        self.gear_label.raise_()

    def set_static_pixmap(
        self, pm: QPixmap | None, fallback: str, color: str, is_diamond: bool = False
    ):
        self.showing_custom_sprite = not is_diamond
        for m in self._movies:
            if m != self.gear_movie:
                m.stop()
        self.active_movie = None
        if pm and not pm.isNull():
            self.current_pixmap = pm
            self._render_sprite_frame(pm, force=True)
        else:
            self.sprite_label.setText(fallback)
            self.sprite_label.setStyleSheet(f"color: {color}; font: bold 14px Consolas;")
        self.sprite_label.move(
            self.SPRITE_POS.x(),
            self.SPRITE_POS.y() + self.hover_lift_y + self.hop_offset_y,
        )
        self.gear_label.raise_()

    def check_net_async(self):
        def worker():
            try:
                self.connection_signal.emit(check_internet())
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True).start()

    def apply_connection_state(self, online: bool):
        if online == self.is_online:
            return
        self.is_online = online
        print(f"[Network] Online = {online}")

        if online:
            if not self.client:
                self.client = create_gemini_client(self.config)
            self.live_stream.start()
            pal = self._get_active_palette()
            self.cloud.set_theme(pal["bubble_bg"], "#000000", pal["bubble_text"])
            if not self.command_bar_open:
                self._apply_slot_visual(
                    "idle", "[ ONLINE ]", "#22d3ee", is_diamond=True
                )
            self.judge_screen()
        else:
            self._apply_slot_visual(
                "offline", "[ NO INTERNET ]", "#64748b", is_diamond=False
            )
            if self.bubble_popup_enabled:
                was_hidden = not self.cloud.isVisible()
                self.cloud.set_theme("#1e293b", "#000000", "#e2e8f0")
                self.cloud.set_message("no internet. i'm out.")
                self._position_cloud_beside_sprite(allow_window_shift=True)
                self.cloud.show()
                if was_hidden:
                    self.sfx.play("popup")
                self.cloud.play_pop_in()
            self.hide_timer.start(BUBBLE_SHOW_MS)

    def pop_new_message(self, text: str):
        if self.muted_by_user:
            return
        if self._is_screen_scan_disabled(require_auto_scan=True):
            return
        clean = sanitize_single_message(text, max_words=20)
        if not clean:
            return
        self.hide_timer.stop()
        self.post_voice_hide_timer.stop()
        self._bubble_min_hold_done = False

        voice_cfg = self.config.get("fish_voice", {})
        will_speak = self.speaker.is_voice_active(clean, voice_cfg)
        self._voice_still_playing = will_speak

        self.scan_pause_until = (
            time.monotonic() + (BUBBLE_SHOW_MS / 1000.0) + POST_REPLY_SCAN_PAUSE_S
        )
        self.post_speech_timer.start(
            BUBBLE_SHOW_MS + int(POST_REPLY_SCAN_PAUSE_S * 1000)
        )
        if self.is_online:
            self._apply_slot_visual(
                "talk", "[ NEW MESSAGE ]", "#67e8f9", is_diamond=True
            )
        self._active_voice_utt_id = self.speaker.speak_async(clean, voice_cfg)

        if self.bubble_popup_enabled:
            was_hidden = not self.cloud.isVisible()
            self.cloud.set_message(clean)
            self._position_cloud_beside_sprite(allow_window_shift=True)
            self.cloud.show()
            if was_hidden:
                self.sfx.play("popup")
            self.cloud.play_pop_in()
            self.cloud.raise_()
        else:
            self.cloud.hide()

        self.sprite_label.move(
            self.SPRITE_POS.x(),
            self.SPRITE_POS.y() + self.hover_lift_y + self.hop_offset_y,
        )
        self.gear_label.raise_()
        self.hide_timer.start(BUBBLE_SHOW_MS)

    def go_idle(self):
        self.cloud.hide()
        if not self.command_bar_open and self.is_online:
            self._apply_slot_visual("idle", "[ ONLINE ]", "#22d3ee", is_diamond=True)
        self.sprite_label.move(
            self.SPRITE_POS.x(),
            self.SPRITE_POS.y() + self.hover_lift_y + self.hop_offset_y,
        )
        self.gear_label.raise_()

    def judge_screen(self, force_manual: bool = False):
        if not force_manual and self._is_screen_scan_disabled(require_auto_scan=True):
            return
        if self.is_thinking:
            return
        if not resolve_gemini_api_key(self.config):
            if force_manual:
                self.manual_reply_signal.emit("add gemini api key in customize.")
            return

        self.is_thinking = True

        def worker():
            try:
                if not force_manual and self._is_screen_scan_disabled(
                    require_auto_scan=True
                ):
                    return
                avoid_list = (
                    ", ".join(self.recent_replies[-5:])
                    if self.recent_replies
                    else "none"
                )
                raw_instr = (
                    "React naturally to what is on screen right now like a real human. "
                    f"Do not repeat or recycle these recent messages: [{avoid_list}]. "
                    "One single message only, max 20 words."
                )
                prompt = self._build_live_context_prompt(raw_instr)
                reply = self._ask_live_or_fallback(prompt)
                if not force_manual and self._is_screen_scan_disabled(
                    require_auto_scan=True
                ):
                    return
                if reply:
                    self.recent_replies.append(reply)
                    if len(self.recent_replies) > 10:
                        self.recent_replies.pop(0)
                    if force_manual:
                        self.manual_reply_signal.emit(reply)
                    else:
                        self.new_opinion_signal.emit(reply)
            except Exception as exc:
                print(f"[Live Judge Error] {exc}")
                if not check_internet():
                    self.connection_signal.emit(False)
            finally:
                self.is_thinking = False

        threading.Thread(target=worker, daemon=True).start()

    def closeEvent(self, event):
        try:
            self.live_stream._stop_event.set()
            if self.gdi.is_running():
                self.gdi.stop()
        except Exception:
            pass
        super().closeEvent(event)

    def _is_inside_menu_or_input(self, pos: QPoint) -> bool:
        if self.cmd_menu.isVisible() and self.cmd_menu.geometry().contains(pos):
            return True
        if self.input_bar.isVisible() and self.input_bar.geometry().contains(pos):
            return True
        return False

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint()
            self.press_global_pos = event.globalPosition().toPoint()
            self.moved_during_drag = False
            if not self._is_inside_menu_or_input(pos):
                self.drag_pos = self.press_global_pos
                if (
                    self.sprite_label.geometry().contains(pos)
                    or self.gear_label.geometry().contains(pos)
                ):
                    self._trigger_click_effect()

    def mouseMoveEvent(self, event):
        pos = event.position().toPoint()
        self._set_hover_state(self.sprite_label.geometry().contains(pos))

        if event.buttons() == Qt.MouseButton.LeftButton and self.drag_pos:
            cur_global = event.globalPosition().toPoint()
            delta = cur_global - self.drag_pos
            if delta.manhattanLength() > 3:
                self.moved_during_drag = True
            self.move(self.pos() + delta)
            self.drag_pos = cur_global
            if self.cloud.isVisible():
                self._position_cloud_beside_sprite(allow_window_shift=False)

    def leaveEvent(self, event):
        self._set_hover_state(False)
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint()
            if not self.moved_during_drag and not self._is_inside_menu_or_input(pos):
                if self.gear_label.geometry().contains(pos):
                    self._toggle_command_menu()
                elif self.sprite_label.geometry().contains(pos):
                    if not self.command_bar_open:
                        self.open_command_mode()
                    else:
                        self.return_to_normal_mode(pause_scan_s=0.0)
            self.drag_pos = None
            self.press_global_pos = None
            self.moved_during_drag = False


if __name__ == "__main__":
    app = QApplication(sys.argv)
    pet = DesktopPet()
    pet.show()
    sys.exit(app.exec())
