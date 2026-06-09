"""
voice_agent.py — Agente STT (Speech-to-Text)
Convierte audio de consultas tributarias (micrófono o archivo) a texto en español.
Usa faster-whisper con cpu_threads=1 para evitar conflictos en macOS.
"""

import os
import subprocess
import numpy as np
import sounddevice as sd
import scipy.signal
import scipy.io.wavfile

from config import (
    DEVICE, WHISPER_MODEL_SIZE, WHISPER_COMPUTE_TYPE,
    WHISPER_BEAM_SIZE, WHISPER_LANGUAGE,
    SAMPLE_RATE_RECORD, SAMPLE_RATE_WHISPER,
    RECORD_DURATION, AUDIO_SAFETY_CEILING,
    MIC_DEVICE_INDEX,
)
from .log_agent import LogAgent


class VoiceAgent:
    """
    Agente STT basado en faster-whisper.
    Transcribe consultas tributarias del usuario en español.
    """

    def __init__(self, log_agent: LogAgent):
        self.log = log_agent
        self._model = None

    def _load_model(self):
        if self._model is not None:
            return
        self.log.log("STT", f"Cargando Whisper '{WHISPER_MODEL_SIZE}' ({WHISPER_COMPUTE_TYPE})...")
        from faster_whisper import WhisperModel
        self._model = WhisperModel(
            WHISPER_MODEL_SIZE,
            device=DEVICE if DEVICE in ("cuda", "cpu") else "cpu",
            compute_type=WHISPER_COMPUTE_TYPE,
            cpu_threads=1,
            num_workers=1,
        )
        self.log.log("STT", "Modelo Whisper listo.")

    def transcribe(self, audio_input) -> str:
        self._load_model()
        audio_array = self._get_audio_array(audio_input)
        if audio_array is None or len(audio_array) == 0:
            self.log.log("STT", "Entrada de audio inválida o vacía.")
            return ""
        dur = len(audio_array) / SAMPLE_RATE_WHISPER
        self.log.log("STT", f"Transcribiendo consulta: {dur:.1f}s de audio...")
        segments, info = self._model.transcribe(
            audio_array,
            beam_size=WHISPER_BEAM_SIZE,
            language=WHISPER_LANGUAGE,
        )
        text = " ".join(s.text for s in segments).strip()
        self.log.log("STT", f"Transcripción ({info.language}): «{text[:80]}»")
        return text

    def record_and_transcribe(self) -> str:
        self.log.log("STT", f"Escuchando {RECORD_DURATION} segundos...")
        try:
            grabacion = sd.rec(
                int(RECORD_DURATION * SAMPLE_RATE_RECORD),
                samplerate=SAMPLE_RATE_RECORD,
                channels=1,
                dtype="float32",
                device=MIC_DEVICE_INDEX,
            )
            sd.wait()
        except Exception as exc:
            self.log.log("ERROR", f"Falla al grabar audio: {exc}")
            return ""
        audio_array = self._normalize_audio(grabacion.flatten(), SAMPLE_RATE_RECORD)
        return self.transcribe(audio_array)

    def _get_audio_array(self, audio_input):
        if isinstance(audio_input, tuple):
            sr, data = audio_input
            return self._normalize_audio(data, sr)
        if isinstance(audio_input, np.ndarray):
            return audio_input
        if isinstance(audio_input, (str, os.PathLike)) and os.path.exists(str(audio_input)):
            return self._load_audio_file(str(audio_input))
        return None

    def _normalize_audio(self, data: np.ndarray, sr: int) -> np.ndarray:
        if data.dtype == np.int16:
            audio = data.astype(np.float32) / 32768.0
        elif data.dtype == np.int32:
            audio = data.astype(np.float32) / 2147483648.0
        elif data.dtype != np.float32:
            audio = data.astype(np.float32)
        else:
            audio = data.copy()
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        if sr != SAMPLE_RATE_WHISPER:
            num = int(len(audio) * SAMPLE_RATE_WHISPER / sr)
            audio = scipy.signal.resample(audio, num)
        peak = np.max(np.abs(audio))
        if peak > 0:
            audio = audio / peak * AUDIO_SAFETY_CEILING
        return audio.astype(np.float32)

    def _load_audio_file(self, path: str):
        try:
            sr, data = scipy.io.wavfile.read(path)
            return self._normalize_audio(data, sr)
        except Exception:
            pass
        return self._load_via_ffmpeg(path)

    def _load_via_ffmpeg(self, path: str):
        try:
            proc = subprocess.run(
                ["ffmpeg", "-y", "-i", path,
                 "-ar", str(SAMPLE_RATE_WHISPER), "-ac", "1", "-f", "f32le", "pipe:1"],
                capture_output=True, timeout=30,
            )
            if proc.returncode != 0:
                self.log.log("ERROR", f"ffmpeg: {proc.stderr.decode()[:200]}")
                return None
            return np.frombuffer(proc.stdout, dtype=np.float32).copy()
        except FileNotFoundError:
            self.log.log("ERROR", "ffmpeg no disponible en PATH")
            return None
        except Exception as exc:
            self.log.log("ERROR", f"Error cargando audio: {exc}")
            return None
