"""
video_agent.py — Agente de Video
Extrae frames de un video (ej: tutorial del portal SRI, captura de proceso
de declaración) y los analiza con VisionAgent para obtener contexto visual.
"""

import os
from PIL import Image

from config import VIDEO_FRAME_INTERVAL, VIDEO_MAX_FRAMES
from .log_agent import LogAgent, Stage
from .vision_agent import VisionAgent


class VideoAgent:
    """
    Procesa videos relacionados con trámites tributarios:
    tutoriales del portal SRI, procesos de declaración, errores en pantalla.
    """

    def __init__(self, log_agent: LogAgent, vision_agent: VisionAgent):
        self.log = log_agent
        self.vision = vision_agent

    def process(self, video_path: str) -> str:
        if not video_path or not os.path.exists(str(video_path)):
            return ""
        try:
            import cv2
        except ImportError:
            # "" en error, nunca un string-sentinela — ver nota en
            # vision_agent.analyze.
            self.log.log(Stage.VIDEO, "OpenCV no instalado. Instala: pip install opencv-python")
            return ""

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            self.log.log(Stage.ERROR, f"No se puede abrir el video: {video_path}")
            return ""

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 24
        duration = total_frames / fps
        self.log.log(Stage.VIDEO, f"Video: {total_frames} frames, {fps:.0f}fps, {duration:.1f}s")

        descriptions = []
        frame_idx = 0
        frames_analyzed = 0

        while frames_analyzed < VIDEO_MAX_FRAMES:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            if not ret:
                break
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(rgb_frame)
            self.log.log(Stage.VIDEO, f"Analizando frame {frame_idx}/{total_frames}...")
            try:
                desc = self.vision.analyze(pil_img)
                if desc:
                    descriptions.append(f"Frame {frames_analyzed+1}: {desc}")
            except Exception as exc:
                self.log.log(Stage.VIDEO, f"Frame {frame_idx} omitido: {exc}")
            frame_idx += VIDEO_FRAME_INTERVAL
            frames_analyzed += 1

        cap.release()

        if not descriptions:
            self.log.log(Stage.ADVERTENCIA, "No se pudo analizar el contenido del video.")
            return ""

        result = " | ".join(descriptions)
        self.log.log(Stage.VIDEO, f"✓ Video procesado: {len(descriptions)} frame(s) analizados.")
        return result
