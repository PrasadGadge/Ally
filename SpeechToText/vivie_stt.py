# ==================================================
# SpeechToText/vivie_stt.py — Groq Whisper STT
#
# Primary:  Groq API → whisper-large-v3-turbo
# Fallback: local faster-whisper tiny.en
#
# Anti-hallucination:
#   - Known Whisper phantom phrases filtered (e.g. "thank you")
#   - Energy validation on final recording before transcription
#   - Minimum utterance duration enforced
#   - Post-speak cooldown respected
# ==================================================

import io
import os
import time
import wave
import threading
from typing import Any, Union, TYPE_CHECKING

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

if TYPE_CHECKING:
    import numpy as _np
    NDArray = _np.ndarray
else:
    NDArray = Any

AudioArray = Union[NDArray, list]

# ── Audio deps (lazy initialization) ────────────────
np = None
sd = None
_HAS_AUDIO = False

def _ensure_audio_deps():
    """Lazy audio dependency initialization."""
    global np, sd, _HAS_AUDIO
    if _HAS_AUDIO:
        return True
    try:
        import numpy as _np
        import sounddevice as _sd
        np = _np
        sd = _sd
        _HAS_AUDIO = True
        print("[STT] Audio dependencies loaded.")
    except Exception as e:
        print(f"[STT] Audio dependencies unavailable: {e}")
        _HAS_AUDIO = False
    return _HAS_AUDIO

# ── Groq client (lazy initialization) ────────────────
try:
    from groq import Groq as _Groq
    _GROQ_KEY = os.getenv("GROQ_API_KEY", "")
    _groq_client = None  # Lazy: initialize on first use
    _HAS_GROQ = bool(_GROQ_KEY)
    if not _HAS_GROQ:
        print("[STT] GROQ_API_KEY not set — Groq STT disabled, using local fallback.")
except Exception:
    _groq_client = None
    _HAS_GROQ = False

def _get_groq_client():
    """Lazy Groq client initialization."""
    global _groq_client
    if _groq_client is None and _HAS_GROQ and _GROQ_KEY:
        try:
            _groq_client = _Groq(api_key=_GROQ_KEY)
            print("[STT] Groq client initialized.")
        except Exception as e:
            print(f"[STT] Groq client initialization failed: {e}")
            _groq_client = None
    return _groq_client

# ── Local Whisper fallback (lazy initialization) ─────
_WhisperModel = None
_HAS_WHISPER = False
_local_model = None
_local_model_lock = threading.Lock()

def _ensure_whisper():
    """Lazy Whisper model initialization."""
    global _WhisperModel, _HAS_WHISPER
    if _HAS_WHISPER:
        return True
    try:
        from faster_whisper import WhisperModel as _WhisperModel
        _HAS_WHISPER = True
        print("[STT] Whisper module loaded.")
    except Exception as e:
        print(f"[STT] Whisper unavailable: {e}")
        _HAS_WHISPER = False
    return _HAS_WHISPER

# ───────── Tunables ─────────────────────────────────
SAMPLE_RATE         = 16000
CHANNELS            = 1
PROBE_SECONDS       = 0.4
MIN_UTTERANCE_SEC   = 0.6            # raised from 0.5
CALIBRATION_SECONDS = 0.8
NOISE_MULTIPLIER    = 3.5            # raised from 2.5 — less sensitive to system sounds
MIN_THRESHOLD_FLOOR = 450            # raised from 200 — filters more ambient noise
LOCAL_MODEL_NAME    = "tiny.en"

GROQ_MODEL          = "whisper-large-v3-turbo"
SILENCE_DURATION    = 1.2
MAX_RECORD_TIME     = 12
GROQ_FAIL_LIMIT     = 3
_strip_wake_prefix  = None

# ── Energy gate for final recording ─────────────────
# If average energy of full recording is below this, skip transcription.
# This catches cases where the mic triggers on a blip but the actual
# recording is near-silence → Whisper would hallucinate.
MIN_RECORDING_ENERGY = 400

try:
    from vivie_core.text import strip_wake_prefix as _strip_wake_prefix
    from vivie_core.settings import (
        STT_GROQ_FAIL_LIMIT,
        STT_GROQ_MODEL,
        STT_MAX_RECORD_SEC,
        STT_SILENCE_DURATION,
    )
    GROQ_MODEL = STT_GROQ_MODEL
    GROQ_FAIL_LIMIT = STT_GROQ_FAIL_LIMIT
    MAX_RECORD_TIME = int(STT_MAX_RECORD_SEC)
    SILENCE_DURATION = STT_SILENCE_DURATION
except ImportError:
    pass

# ───────── Whisper Hallucination Filter ─────────────
# Known phrases Whisper hallucinates on near-silence / short noise.
# All lowercase, stripped. Checked after transcription.
WHISPER_HALLUCINATIONS = frozenset({
    "thank you",
    "thank you.",
    "thanks",
    "thanks.",
    "thank you for watching",
    "thank you for watching.",
    "thanks for watching",
    "thanks for watching.",
    "subscribe",
    "subscribe.",
    "please subscribe",
    "like and subscribe",
    "bye",
    "bye.",
    "goodbye",
    "goodbye.",
    "you",
    "you.",
    "the end",
    "the end.",
    "hmm",
    "hmm.",
    "uh",
    "um",
    "oh",
    "ah",
    "...",
    "",
    "so",
    "okay",
    "okay.",
    "i'm sorry",
    "silence",
    "music",
    "applause",
    "laughter",
})

# ───────── State ────────────────────────────────────
_noise_threshold      = None
_last_calibrated_at   = 0.0
RECALIBRATE_INTERVAL  = 15 * 60      # recalibrate every 15 minutes
_ready_announced      = False
_warned_no_audio      = False
_groq_fail_count      = 0


# ───────── Helpers ──────────────────────────────────
def _energy(audio: AudioArray) -> float:
    if not _ensure_audio_deps() or np is None or len(audio) == 0:
        return 0.0
    return float(np.sqrt(np.mean(audio.astype(np.float32) ** 2)))


def _is_vivie_speaking() -> bool:
    try:
        from voice_state import is_speaking
        return is_speaking()
    except Exception:
        return False


def _time_since_last_spoke() -> float:
    """Check how long since TTS finished — for extra cooldown protection."""
    try:
        from TextToSpeech.Fast_DF_TTS import time_since_last_spoke
        return time_since_last_spoke()
    except Exception:
        return 999.0


def _calibrate(stream) -> float:
    samples = stream.read(int(SAMPLE_RATE * CALIBRATION_SECONDS))[0].flatten()
    ambient  = _energy(samples)
    threshold = max(MIN_THRESHOLD_FLOOR, ambient * NOISE_MULTIPLIER)
    print(f"[STT] Ambient={ambient:.0f}  threshold={threshold:.0f}")
    return threshold


def _get_local_model():
    global _local_model
    if not _ensure_whisper():
        return None
    with _local_model_lock:
        if _local_model is None and _WhisperModel:
            print(f"[STT] Loading local Whisper '{LOCAL_MODEL_NAME}' fallback...")
            _local_model = _WhisperModel(
                LOCAL_MODEL_NAME, device="cpu",
                compute_type="int8", num_workers=2
            )
            print("[STT] Local Whisper ready.")
    return _local_model


def _strip_wake_word(text: str) -> str:
    if _strip_wake_prefix is not None:
        return _strip_wake_prefix(text)
    t = text.strip()
    return (t[0].upper() + t[1:]) if t else ""


def _is_hallucination(text: str) -> bool:
    """Check if transcribed text is a known Whisper hallucination."""
    clean = text.strip().lower().rstrip(".")
    # Exact match
    if clean in WHISPER_HALLUCINATIONS or (clean + ".") in WHISPER_HALLUCINATIONS:
        return True
    # Very short single-word outputs that are likely noise
    if len(clean) <= 2:
        return True
    # Repeated single word/syllable (e.g. "you you you")
    words = clean.split()
    if len(words) >= 2 and len(set(words)) == 1:
        return True
    return False


def get_health() -> dict:
    # Ensure audio dependencies are initialized before reporting health
    # This fixes the false-negative where get_health() was called before
    # _ensure_audio_deps() ran, causing audio=False even when deps were available
    _ensure_audio_deps()

    return {
        "audio": _HAS_AUDIO,
        "groq": _HAS_GROQ,
        "local_whisper": _HAS_WHISPER,
        "backend": (
            "groq"
            if _HAS_GROQ and _groq_fail_count < GROQ_FAIL_LIMIT
            else ("local" if _HAS_WHISPER else "none")
        ),
        "groq_fail_count": _groq_fail_count,
        "model": GROQ_MODEL,
    }


def test_microphone() -> dict:
    """
    Diagnostic: Test microphone access and device enumeration.
    Returns device information without continuous recording.
    Safe to run in chat mode (does not start background loops).
    """
    if not _ensure_audio_deps():
        return {
            "available": False,
            "error": "Audio dependencies (numpy/sounddevice) not available",
        }

    try:
        if sd is None:
            return {
                "available": False,
                "error": "sounddevice module not loaded",
            }

        # Query available devices
        devices = sd.query_devices()
        device_count = len(devices)
        default_input = sd.default.device[0]  # Default input device index

        # Get default input device details
        input_device = None
        if default_input < device_count:
            input_device = {
                "index": default_input,
                "name": str(devices[default_input]["name"]),
                "max_input_channels": int(devices[default_input]["max_input_channels"]),
                "default_samplerate": float(devices[default_input]["default_samplerate"]),
            }

        return {
            "available": True,
            "device_count": device_count,
            "default_input": input_device,
            "sample_rate": SAMPLE_RATE,
            "channels": CHANNELS,
        }
    except Exception as e:
        return {
            "available": False,
            "error": str(e),
        }


def _audio_to_wav_bytes(audio: NDArray) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio.tobytes())
    buf.seek(0)
    return buf.read()


# ───────── Transcription backends ───────────────────
def _transcribe_groq(audio: NDArray) -> str:
    global _groq_fail_count
    client = _get_groq_client()
    if not _HAS_GROQ or client is None:
        return ""
    if len(audio) < SAMPLE_RATE * MIN_UTTERANCE_SEC:
        return ""
    try:
        wav_bytes = _audio_to_wav_bytes(audio)
        result = client.audio.transcriptions.create(
            file            = ("audio.wav", wav_bytes),
            model           = GROQ_MODEL,
            language        = "en",
            response_format = "text",
        )
        _groq_fail_count = 0
        return (result or "").strip()
    except Exception as e:
        _groq_fail_count += 1
        print(f"[STT] Groq error ({_groq_fail_count}/{GROQ_FAIL_LIMIT}): {e}")
        return ""


def _transcribe_local(audio: NDArray) -> str:
    if not _HAS_WHISPER or np is None:
        return ""
    if len(audio) < SAMPLE_RATE * MIN_UTTERANCE_SEC:
        return ""
    try:
        model = _get_local_model()
        if model is None:
            return ""
        audio_float = audio.astype(np.float32) / 32768.0
        segments, _ = model.transcribe(
            audio_float,
            language                   = "en",
            beam_size                  = 3,
            vad_filter                 = True,
            condition_on_previous_text = False,
        )
        return " ".join(s.text.strip() for s in segments).strip()
    except Exception as e:
        print(f"[STT] Local transcribe error: {e}")
        return ""


def _transcribe(audio: NDArray) -> str:
    use_groq = _HAS_GROQ and _groq_fail_count < GROQ_FAIL_LIMIT

    if use_groq:
        result = _transcribe_groq(audio)
        if result:
            return result
        if _groq_fail_count >= GROQ_FAIL_LIMIT:
            print("[STT] Groq failing repeatedly — switching to local fallback.")

    return _transcribe_local(audio)


# ───────── Public API ────────────────────────────────
def listen() -> str:
    """
    Record mic until silence, transcribe via Groq Whisper (or local fallback).
    Returns lowercase clean transcript or '' if nothing useful captured.
    """
    global _noise_threshold, _last_calibrated_at, _ready_announced, _warned_no_audio

    if not _ensure_audio_deps():
        if not _warned_no_audio:
            print("[STT] Audio deps missing (sounddevice / numpy). Mic disabled.")
            _warned_no_audio = True
        time.sleep(0.5)
        return ""

    probe_samples     = int(SAMPLE_RATE * PROBE_SECONDS)
    silence_needed    = max(1, int(SILENCE_DURATION / PROBE_SECONDS))
    max_probes_record = int(MAX_RECORD_TIME / PROBE_SECONDS)

    try:
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS,
                            dtype='int16') as stream:

            # Recalibrate periodically
            now = time.time()
            if _noise_threshold is None or (now - _last_calibrated_at) > RECALIBRATE_INTERVAL:
                _noise_threshold    = _calibrate(stream)
                _last_calibrated_at = now

            if not _ready_announced:
                backend = "Groq Whisper" if _HAS_GROQ else "local Whisper"
                print(f"[STT] Vivie STT Ready — backend: {backend}")
                _ready_announced = True

            # ── Phase 1: wait for voice ──────────────────
            while True:
                # Skip if Vivie is speaking
                if _is_vivie_speaking():
                    time.sleep(0.1)
                    continue

                # Extra cooldown: don't start listening too soon after speech
                if _time_since_last_spoke() < 2.0:
                    time.sleep(0.1)
                    continue

                data, _ = stream.read(probe_samples)
                flat    = data.flatten()

                if _energy(flat) < _noise_threshold:
                    continue

                # Double-check: if energy barely crosses threshold, read one more
                # probe to confirm it's real speech, not a transient click/pop.
                data2, _ = stream.read(probe_samples)
                flat2 = data2.flatten()
                if _energy(flat2) < _noise_threshold * 0.7:
                    # First probe was a transient — ignore
                    continue

                print("[STT] listening...")
                first_chunk = np.concatenate([flat, flat2])
                break

            # ── Phase 2: record full utterance ───────────
            chunks         = [first_chunk]
            silence_chunks = 0

            for _ in range(max_probes_record):
                # Check BEFORE reading so TTS audio isn't captured
                if _is_vivie_speaking():
                    break

                data, _ = stream.read(probe_samples)
                flat    = data.flatten()
                chunks.append(flat)

                if _energy(flat) < _noise_threshold:
                    silence_chunks += 1
                    if silence_chunks >= silence_needed:
                        break
                else:
                    silence_chunks = 0

        audio = np.concatenate(chunks) if chunks else np.array([], dtype=np.int16)

    except Exception as e:
        print(f"[STT] Stream error: {e}")
        time.sleep(0.3)
        return ""

    # ── Phase 3: validate recording ─────────────────
    # Check minimum duration
    duration_sec = len(audio) / SAMPLE_RATE
    if duration_sec < MIN_UTTERANCE_SEC:
        print(f"[STT] Recording too short ({duration_sec:.2f}s) — skipping")
        return ""

    # Check average energy of entire recording
    avg_energy = _energy(audio)
    if avg_energy < MIN_RECORDING_ENERGY:
        print(f"[STT] Recording energy too low ({avg_energy:.0f}) — likely noise, skipping")
        return ""

    # ── Phase 4: transcribe ──────────────────────────
    text = _transcribe(audio)
    if not text:
        return ""

    # ── Phase 5: hallucination filter ────────────────
    if _is_hallucination(text):
        print(f"[STT] Filtered hallucination: '{text}'")
        return ""

    clean = _strip_wake_word(text)
    if not clean or len(clean) < 2:
        return ""

    print(f"User: {clean}")
    return clean.lower()