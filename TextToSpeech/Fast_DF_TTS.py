# ==================================================
# Fast_DF_TTS.py — Edge-TTS Only (Streamlined)
#
# Single engine: Edge TTS + ffmpeg + sounddevice
# Voice: en-US-AriaNeural (high quality, fast, free)
#
# Architecture:
#   edge-tts stream() → MP3 chunks → ffmpeg (mp3→s16le) → sounddevice
#   First audio in ~150-300ms. No Gemini, no pygame, no fallbacks.
# ==================================================

import asyncio
import hashlib
import os
import queue
import shutil
import subprocess
import threading
import time
from pathlib import Path

# Load environment variables before discovering FFmpeg
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# ───────── edge-tts ─────────
try:
    import edge_tts
    _HAS_EDGE_TTS = True
except Exception as e:
    print(f"[TTS] edge-tts not available: {e}")
    edge_tts = None
    _HAS_EDGE_TTS = False

# ───────── sounddevice (primary playback) ─────────
try:
    import sounddevice as sd
    import numpy as np
    _HAS_SOUNDDEVICE = True
except Exception as e:
    print(f"[TTS] sounddevice not available: {e}")
    sd = None
    np = None
    _HAS_SOUNDDEVICE = False

# ───────── ffmpeg ─────────
def _discover_ffmpeg() -> str | None:
    """Discover FFmpeg executable from settings or PATH."""
    # Try explicit path from environment first (direct, no circular import)
    ffmpeg_path = os.getenv("FFMPEG_PATH", "").strip()
    if ffmpeg_path:
        if os.path.isfile(ffmpeg_path) and os.access(ffmpeg_path, os.X_OK):
            print(f"[TTS] Using FFmpeg from FFMPEG_PATH: {ffmpeg_path}")
            return ffmpeg_path
        else:
            print(f"[TTS] FFMPEG_PATH set but not executable: {ffmpeg_path}")

    # Try vivie_core.settings as fallback
    try:
        from vivie_core.settings import FFMPEG_PATH
        if FFMPEG_PATH:
            if os.path.isfile(FFMPEG_PATH) and os.access(FFMPEG_PATH, os.X_OK):
                print(f"[TTS] Using FFmpeg from settings: {FFMPEG_PATH}")
                return FFMPEG_PATH
            else:
                print(f"[TTS] FFMPEG_PATH set but not executable: {FFMPEG_PATH}")
    except ImportError:
        # vivie_core.settings may not be available in all contexts
        pass
    except Exception as e:
        print(f"[TTS] Error loading FFMPEG_PATH from settings: {e}")

    # Fall back to PATH discovery
    path = shutil.which("ffmpeg")
    if path:
        print(f"[TTS] Found FFmpeg in PATH: {path}")
    return path

FFMPEG = _discover_ffmpeg()
_HAS_FFMPEG = FFMPEG is not None
_HAS_STREAMING = _HAS_FFMPEG and _HAS_SOUNDDEVICE

if not _HAS_FFMPEG:
    print("[TTS] ffmpeg not found — streaming disabled. Install ffmpeg or set FFMPEG_PATH.")
if not _HAS_SOUNDDEVICE:
    print("[TTS] sounddevice not available — audio playback disabled.")

# ───────── voice personality ─────────
try:
    from . import voice_personality as vp
except ImportError:
    import voice_personality as vp


# ==================================================
# Module state
# ==================================================
_is_playing      = False
_stop_event      = threading.Event()
_loop            = None
_loop_thread     = None
_last_spoke_at   = 0.0

_speak_queue     = queue.Queue()
_worker_started  = False
_worker_lock     = threading.Lock()

# Audio format
SAMPLE_RATE      = 24000
CHANNELS         = 1
BLOCKSIZE        = 1024
BYTES_PER_FRAME  = 2 * CHANNELS      # s16le

# Edge-TTS settings
VOICE            = "en-US-AriaNeural"
VOICE_FALLBACKS  = ["en-US-JennyNeural", "en-US-GuyNeural"]
FETCH_TIMEOUT_S  = 5.0
FIRST_CHUNK_TIMEOUT_S = 5.0
MAX_WORDS        = 150

# Persistent cache
_CACHE_DIR = Path.home() / "vivie" / "tts_cache"
try:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
except Exception as e:
    print(f"[TTS] cache dir fallback to /tmp: {e}")
    import tempfile
    _CACHE_DIR = Path(tempfile.gettempdir()) / "vivie_tts_cache"
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)


# ==================================================
# asyncio loop (shared, daemon)
# ==================================================
def _get_loop():
    global _loop, _loop_thread
    if _loop is None or not _loop.is_running():
        _loop = asyncio.new_event_loop()
        _loop_thread = threading.Thread(target=_loop.run_forever, daemon=True)
        _loop_thread.start()
    return _loop


# ==================================================
# voice_state bridge
# ==================================================
def _enter_speaking_state() -> bool:
    try:
        from voice_state import set_speaking, is_speaking
        if is_speaking():
            return False
        set_speaking(True)
        return True
    except Exception:
        return False


def _exit_speaking_state(owned: bool):
    if not owned:
        return
    try:
        from voice_state import set_speaking
        set_speaking(False)
    except Exception:
        pass


# ==================================================
# Text preprocessing
# ==================================================
def _preprocess(text: str) -> str:
    text = vp.clean_for_speech(text)
    words = text.split()
    if len(words) > MAX_WORDS:
        text = " ".join(words[:MAX_WORDS]) + "."
    return text


# ==================================================
# Cache
# ==================================================
def _cache_key(text: str, params: dict) -> str:
    sig = f"{text}|{params['voice']}|{params['rate']}|{params['pitch']}|{params['volume']}"
    return hashlib.md5(sig.encode("utf-8")).hexdigest() + ".mp3"


def _cache_path(text: str, params: dict) -> str:
    return str(_CACHE_DIR / _cache_key(text, params))


# ==================================================
# Edge-TTS MP3 producer — yields raw MP3 chunks
# ==================================================
def _start_mp3_producer(text: str, params: dict) -> "queue.Queue[bytes | None]":
    chunk_q: "queue.Queue[bytes | None]" = queue.Queue(maxsize=128)

    async def _producer():
        last_err = None
        voices = [params["voice"]] + [v for v in VOICE_FALLBACKS if v != params["voice"]]
        for v in voices:
            if _stop_event.is_set():
                break
            try:
                comm = edge_tts.Communicate(
                    text, v,
                    rate=params["rate"],
                    pitch=params["pitch"],
                    volume=params["volume"],
                )
                async for evt in comm.stream():
                    if _stop_event.is_set():
                        return
                    if evt.get("type") == "audio":
                        data = evt.get("data")
                        if data:
                            chunk_q.put(data)
                return
            except Exception as e:
                last_err = e
                print(f"[TTS] voice '{v}' failed: {e}")
        if last_err:
            print(f"[TTS] all voices failed: {last_err}")

    loop = _get_loop()
    fut = asyncio.run_coroutine_threadsafe(_producer(), loop)

    def _on_done(_f):
        chunk_q.put(None)

    fut.add_done_callback(_on_done)
    return chunk_q


# ==================================================
# STREAMING playback (ffmpeg + sounddevice)
# ==================================================
def _stream_play(text: str, params: dict, save_path: str | None) -> bool:
    if not _HAS_STREAMING:
        return False

    try:
        proc = subprocess.Popen(
            [
                FFMPEG, "-loglevel", "quiet", "-nostdin",
                "-f", "mp3", "-i", "pipe:0",
                "-f", "s16le", "-ar", str(SAMPLE_RATE), "-ac", str(CHANNELS),
                "pipe:1",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=0,
        )
    except Exception as e:
        print(f"[TTS] could not start ffmpeg: {e}")
        return False

    chunk_q  = _start_mp3_producer(text, params)
    saver_fp = open(save_path, "wb") if save_path else None

    first_audio_seen = threading.Event()
    producer_done    = threading.Event()
    pcm_done         = threading.Event()

    def _writer():
        try:
            deadline = time.time() + FIRST_CHUNK_TIMEOUT_S
            while True:
                if _stop_event.is_set():
                    return
                timeout = max(0.05, deadline - time.time())
                try:
                    item = chunk_q.get(timeout=timeout)
                except queue.Empty:
                    print(f"[TTS] no audio in {FIRST_CHUNK_TIMEOUT_S}s — abort")
                    return
                if item is None:
                    return
                first_audio_seen.set()
                _write_chunk(item)
                break

            while True:
                if _stop_event.is_set():
                    return
                try:
                    item = chunk_q.get(timeout=10.0)
                except queue.Empty:
                    return
                if item is None:
                    return
                _write_chunk(item)
        finally:
            producer_done.set()
            try:
                proc.stdin.close()
            except Exception:
                pass
            if saver_fp:
                try:
                    saver_fp.flush()
                    saver_fp.close()
                except Exception:
                    pass

    def _write_chunk(data: bytes):
        if saver_fp:
            try:
                saver_fp.write(data)
            except Exception:
                pass
        try:
            proc.stdin.write(data)
        except Exception:
            pass

    pcm_q: "queue.Queue[bytes | None]" = queue.Queue(maxsize=128)
    READ_SIZE = BLOCKSIZE * BYTES_PER_FRAME

    def _reader():
        try:
            while True:
                if _stop_event.is_set():
                    return
                data = proc.stdout.read(READ_SIZE)
                if not data:
                    return
                pcm_q.put(data)
        finally:
            pcm_q.put(None)
            pcm_done.set()

    threading.Thread(target=_writer, daemon=True).start()
    threading.Thread(target=_reader, daemon=True).start()

    leftover  = bytearray()
    finished  = threading.Event()

    def _cb(outdata, frames, time_info, status):
        needed = frames * BYTES_PER_FRAME
        out    = bytearray()

        while len(out) < needed:
            if _stop_event.is_set():
                break
            if leftover:
                take = min(needed - len(out), len(leftover))
                out += leftover[:take]
                del leftover[:take]
                continue
            try:
                chunk = pcm_q.get_nowait()
            except queue.Empty:
                break
            if chunk is None:
                finished.set()
                break
            leftover.extend(chunk)

        if len(out) < needed:
            out += b"\x00" * (needed - len(out))
        outdata[: len(out)] = bytes(out)

        if _stop_event.is_set():
            raise sd.CallbackAbort
        if finished.is_set() and not leftover and pcm_q.empty():
            raise sd.CallbackStop

    # Wait for first PCM before opening stream
    pre_buf_deadline = time.time() + FETCH_TIMEOUT_S
    while pcm_q.empty():
        if _stop_event.is_set():
            _cleanup_proc(proc)
            return False
        if pcm_done.is_set():
            break
        if time.time() > pre_buf_deadline:
            print(f"[TTS] decoder produced no PCM in {FETCH_TIMEOUT_S}s — abort")
            _cleanup_proc(proc)
            return False
        time.sleep(0.02)

    if pcm_q.empty() and pcm_done.is_set():
        _cleanup_proc(proc)
        return False

    interrupted = False
    try:
        with sd.RawOutputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            blocksize=BLOCKSIZE,
            callback=_cb,
        ):
            while not finished.is_set() and not _stop_event.is_set():
                time.sleep(0.04)
            interrupted = _stop_event.is_set()
    except Exception as e:
        print(f"[TTS] sounddevice stream error: {e}")
        interrupted = True
    finally:
        _cleanup_proc(proc)

    if interrupted and save_path and os.path.exists(save_path):
        try:
            os.remove(save_path)
        except Exception:
            pass

    return not interrupted


def _cleanup_proc(proc: subprocess.Popen):
    try:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=0.5)
            except Exception:
                proc.kill()
    except Exception:
        pass


# ==================================================
# WHOLE-FILE playback (cache hits / no streaming)
# ==================================================
def _play_file_full(path: str):
    if not _HAS_SOUNDDEVICE or not _HAS_FFMPEG:
        print("[TTS] Cannot play — sounddevice or ffmpeg missing")
        return

    try:
        result = subprocess.run(
            [
                FFMPEG, "-loglevel", "quiet", "-nostdin",
                "-i", path,
                "-f", "s16le", "-ar", str(SAMPLE_RATE), "-ac", str(CHANNELS),
                "pipe:1",
            ],
            capture_output=True,
            timeout=30,
        )
        if result.returncode == 0 and result.stdout:
            pcm = np.frombuffer(result.stdout, dtype=np.int16)
            sd.play(pcm, samplerate=SAMPLE_RATE)
            duration_s = len(pcm) / SAMPLE_RATE
            elapsed = 0.0
            step = 0.05
            while elapsed < duration_s + 0.1:
                if _stop_event.is_set():
                    sd.stop()
                    break
                time.sleep(step)
                elapsed += step
            return
    except Exception as e:
        print(f"[TTS] whole-file playback error: {e}")


# ==================================================
# Main blocking pipeline
# ==================================================
def _play_blocking_audio(text: str, intent: str = "chat"):
    global _is_playing, _last_spoke_at
    if not text or not text.strip():
        return

    _stop_event.clear()

    params = vp.get_voice_params(text, intent)
    path   = _cache_path(text, params)
    owned  = _enter_speaking_state()
    _is_playing = True

    try:
        # 1) Cache hit
        if os.path.exists(path) and os.path.getsize(path) > 0:
            _play_file_full(path)
            return

        # 2) Streaming pipeline (Edge-TTS + ffmpeg)
        if _HAS_STREAMING:
            ok = _stream_play(text, params, save_path=path)
            if ok:
                return
            if _stop_event.is_set():
                return

        # 3) Non-streaming fallback: download full MP3, then play
        chunk_q = _start_mp3_producer(text, params)
        buf = bytearray()
        deadline = time.time() + FETCH_TIMEOUT_S
        while True:
            if _stop_event.is_set():
                return
            timeout = max(0.05, deadline - time.time())
            try:
                item = chunk_q.get(timeout=timeout)
            except queue.Empty:
                print(f"[TTS] fetch timed out after {FETCH_TIMEOUT_S}s")
                return
            if item is None:
                break
            buf.extend(item)
            deadline = max(deadline, time.time() + 10.0)

        if not buf or _stop_event.is_set():
            return

        with open(path, "wb") as f:
            f.write(buf)
        _play_file_full(path)

    finally:
        _is_playing = False
        _last_spoke_at = time.time()
        _exit_speaking_state(owned)


# ==================================================
# Worker for non-blocking speak()
# ==================================================
def _worker():
    while True:
        text, intent = _speak_queue.get()
        try:
            _play_blocking_audio(text, intent)
        except Exception as e:
            print(f"[TTS worker] {e}")


def _ensure_worker():
    global _worker_started
    with _worker_lock:
        if not _worker_started:
            threading.Thread(target=_worker, daemon=True).start()
            _worker_started = True


def _announce_text(text: str) -> None:
    try:
        print(f"\n[Vivie] {text}\n")
    except UnicodeEncodeError:
        safe = text.encode("ascii", errors="replace").decode("ascii")
        print(f"\n[Vivie] {safe}\n")


# ==================================================
# PUBLIC API
# ==================================================
def speak(text: str, intent: str = "chat") -> bool:
    """Non-blocking; serialized via internal queue."""
    if not text or not text.strip():
        return False
    clean = _preprocess(text)
    if not clean:
        return False
    _announce_text(text)
    _ensure_worker()
    _speak_queue.put((clean, intent))
    return True


def speak_blocking(text: str, intent: str = "chat") -> bool:
    """Blocking; speaks immediately on caller's thread."""
    if not text or not text.strip():
        return False
    clean = _preprocess(text)
    if not clean:
        return False
    _announce_text(text)
    _play_blocking_audio(clean, intent)
    return True


def stop_speaking():
    """Interrupt current speech within ~50ms."""
    _stop_event.set()
    try:
        while True:
            _speak_queue.get_nowait()
    except queue.Empty:
        pass
    if _HAS_SOUNDDEVICE:
        try:
            sd.stop()
        except Exception:
            pass


def is_speaking() -> bool:
    return _is_playing


def time_since_last_spoke() -> float:
    """Seconds since TTS last finished. Used by listen_loop for post-speak cooldown."""
    return time.time() - _last_spoke_at


def cache_dir() -> str:
    return str(_CACHE_DIR)


def get_health() -> dict:
    return {
        "edge_tts": _HAS_EDGE_TTS,
        "sounddevice": _HAS_SOUNDDEVICE,
        "ffmpeg": _HAS_FFMPEG,
        "streaming": _HAS_STREAMING,
        "voice": VOICE,
        "cache_dir": str(_CACHE_DIR),
        "speaking": _is_playing,
    }

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Test Fast_DF_TTS")
    parser.add_argument("text", nargs="?", default="Hello, this is a test of the Fast DF TTS system.")
    args = parser.parse_args()
    speak_blocking(args.text)
