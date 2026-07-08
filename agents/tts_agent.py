"""
tts_agent.py — Agente TTS (Text-to-Speech)
Sintetiza las respuestas tributarias en voz española.

Estrategia de fallback (en orden):
  1. Piper TTS (piper-tts Python package) con modelo es_ES-sharvard-medium
  2. Piper TTS binario del sistema
  3. macOS 'say' command (fallback nativo)
"""

import os
import subprocess
import threading
import wave

from config import (
    PIPER_MODEL_PATH, PIPER_CONFIG_PATH, TTS_SAMPLE_RATE,
    TEMP_DIR, AUDIO_OUTPUT_DIR,
)
from .log_agent import LogAgent, Stage


class TTSAgent:
    """
    Sintetiza respuestas tributarias en voz con tres backends en cascada.
    Guarda el audio en archivo WAV para reproducción en Gradio.
    """

    def __init__(self, log_agent: LogAgent):
        self.log = log_agent
        self._piper_voice = None
        self._backend: str | None = None
        self._detect_backend()

    def _detect_backend(self):
        if os.path.exists(PIPER_MODEL_PATH):
            try:
                from piper import PiperVoice  # noqa: F401
                self._backend = "piper_python"
                self.log.log(Stage.TTS, "Backend: piper-tts (Python package)")
                return
            except ImportError:
                pass
        if self._command_exists("piper"):
            self._backend = "piper_binary"
            self.log.log(Stage.TTS, "Backend: piper (binario del sistema)")
            return
        if self._command_exists("say"):
            self._backend = "macos_say"
            self.log.log(Stage.TTS, "Backend: macOS say (fallback nativo)")
            return
        self.log.log(Stage.TTS, "ADVERTENCIA: no se encontró motor TTS.")
        self._backend = None

    def synthesize(self, text: str) -> str | None:
        if not text or not text.strip():
            return None
        output_path = os.path.join(TEMP_DIR, "sri_response_audio.wav")
        text_clean = text[:800].strip()
        self.log.log(Stage.TTS, f"Sintetizando {len(text_clean)} caracteres...")
        success = False
        if self._backend == "piper_python":
            success = self._synth_piper_python(text_clean, output_path)
        elif self._backend == "piper_binary":
            success = self._synth_piper_binary(text_clean, output_path)
        elif self._backend == "macos_say":
            success = self._synth_macos_say(text_clean, output_path)
        if success and os.path.exists(output_path):
            self.log.log(Stage.TTS, f"Audio generado: {output_path}")
            return output_path
        self.log.log(Stage.TTS, "No se pudo generar audio.")
        return None

    def play_async(self, audio_path: str):
        if not audio_path:
            return
        t = threading.Thread(target=self._play, args=(audio_path,), daemon=True)
        t.start()

    def _synth_piper_python(self, text: str, output_path: str) -> bool:
        try:
            from piper import PiperVoice
            if self._piper_voice is None:
                self._piper_voice = PiperVoice.load(
                    PIPER_MODEL_PATH,
                    config_path=PIPER_CONFIG_PATH,
                    use_cuda=False,
                )
            chunks = list(self._piper_voice.synthesize(text))
            if not chunks:
                return False
            first = chunks[0]
            with wave.open(output_path, "w") as wf:
                wf.setnchannels(first.sample_channels)
                wf.setsampwidth(first.sample_width)
                wf.setframerate(first.sample_rate)
                for chunk in chunks:
                    wf.writeframes(chunk.audio_int16_bytes)
            return True
        except Exception as exc:
            self.log.log(Stage.TTS, f"piper-tts Python falló: {exc}")
            return False

    def _synth_piper_binary(self, text: str, output_path: str) -> bool:
        try:
            result = subprocess.run(
                ["piper", "--model", PIPER_MODEL_PATH, "--output_file", output_path],
                input=text.encode("utf-8"),
                capture_output=True,
                timeout=30,
            )
            return result.returncode == 0
        except Exception as exc:
            self.log.log(Stage.TTS, f"piper binario falló: {exc}")
            return False

    def _synth_macos_say(self, text: str, output_path: str) -> bool:
        try:
            aiff_path = output_path.replace(".wav", ".aiff")
            subprocess.run(
                ["say", "-v", "Monica", "-o", aiff_path, text],
                timeout=30, check=True,
            )
            if os.path.exists(aiff_path):
                subprocess.run(
                    ["afconvert", "-f", "WAVE", "-d", "LEI16", aiff_path, output_path],
                    timeout=10, check=True,
                )
                os.remove(aiff_path)
                return True
        except Exception as exc:
            self.log.log(Stage.TTS, f"macOS say falló: {exc}")
            try:
                subprocess.run(["say", "-v", "Monica", text], timeout=30)
            except Exception:
                pass
        return False

    def _play(self, audio_path: str):
        try:
            subprocess.run(["afplay", audio_path], timeout=60)
        except Exception:
            pass

    @staticmethod
    def _command_exists(cmd: str) -> bool:
        try:
            subprocess.run(["which", cmd], capture_output=True, check=True)
            return True
        except subprocess.CalledProcessError:
            return False
