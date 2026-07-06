"""
vision_agent.py — Agente de Visión
Analiza imágenes con Moondream via Ollama.
Especializado en reconocer formularios SRI, errores del portal web,
comprobantes electrónicos y pantallas de declaraciones tributarias.
"""

import base64
import io
import requests
from PIL import Image

from config import OLLAMA_URL, VISION_MODEL, VISION_TIMEOUT, MOONDREAM_PROMPT, MOONDREAM_NUM_PREDICT
from .log_agent import LogAgent


class VisionAgent:
    """
    Agente que usa Moondream (LLM de visión) para describir:
    - Formularios SRI (104, 101, 102, etc.)
    - Errores en el portal sri.gob.ec
    - Comprobantes electrónicos (facturas, notas de crédito)
    - Pantallas de declaraciones y estados de cuenta
    """

    def __init__(self, log_agent: LogAgent):
        self.log = log_agent

    def analyze(self, image_input) -> str:
        try:
            pil_img = self._to_pil(image_input)
            if pil_img is None:
                return ""
            b64 = self._to_base64(pil_img)
            self.log.log("VISION", f"Analizando imagen {pil_img.size} con {VISION_MODEL}...")

            description = self._call_generate(b64)
            if not description:
                # Moondream2 in newer Ollama uses /api/chat
                self.log.log("VISION", "generate vacío, intentando /api/chat...")
                description = self._call_chat(b64)

            self.log.log("VISION", f"Descripción: «{description[:100]}»")
            return description
        except requests.exceptions.ConnectionError:
            self.log.log("ERROR", "No se puede conectar a Ollama.")
            return "[Ollama no disponible]"
        except requests.exceptions.Timeout:
            self.log.log("ERROR", f"Timeout después de {VISION_TIMEOUT}s esperando Moondream.")
            return "[Timeout en visión]"
        except Exception as exc:
            self.log.log("ERROR", f"Falla en visión: {exc}")
            return ""

    def _call_generate(self, b64: str) -> str:
        payload = {
            "model": VISION_MODEL,
            "prompt": MOONDREAM_PROMPT,
            "images": [b64],
            "stream": False,
            "options": {"temperature": 0.1, "num_predict": MOONDREAM_NUM_PREDICT},
        }
        resp = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json=payload,
            timeout=VISION_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json().get("response", "").strip()

    def _call_chat(self, b64: str) -> str:
        payload = {
            "model": VISION_MODEL,
            "messages": [{
                "role": "user",
                "content": MOONDREAM_PROMPT,
                "images": [b64],
            }],
            "stream": False,
            "options": {"temperature": 0.1, "num_predict": MOONDREAM_NUM_PREDICT},
        }
        resp = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json=payload,
            timeout=VISION_TIMEOUT,
        )
        resp.raise_for_status()
        msg = resp.json().get("message", {})
        return msg.get("content", "").strip()

    def _to_pil(self, image_input) -> Image.Image | None:
        if image_input is None:
            return None
        if isinstance(image_input, Image.Image):
            return image_input.convert("RGB")
        if isinstance(image_input, str):
            return Image.open(image_input).convert("RGB")
        try:
            import numpy as np
            if isinstance(image_input, np.ndarray):
                return Image.fromarray(image_input).convert("RGB")
        except ImportError:
            pass
        if isinstance(image_input, dict):
            for key in ("composite", "background", "layers"):
                val = image_input.get(key)
                if val is not None:
                    return self._to_pil(val)
        self.log.log("ERROR", f"Formato de imagen no reconocido: {type(image_input)}")
        return None

    def _to_base64(self, img: Image.Image) -> str:
        # Moondream performs best at small resolutions; resize if too large
        max_side = 512
        w, h = img.size
        if max(w, h) > max_side:
            ratio = max_side / max(w, h)
            img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=85)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")
