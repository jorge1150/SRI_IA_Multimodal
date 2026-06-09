"""
scanner.py — Escáner de dispositivos de audio.
Ejecutar una vez para identificar índices de micrófono y altavoz.

Uso: python audio/scanner.py
     python audio/scanner.py <índice>
"""

import sounddevice as sd
import numpy as np
import sys


def listar_dispositivos():
    print("\n" + "=" * 70)
    print("DISPOSITIVOS DE AUDIO DISPONIBLES")
    print("=" * 70)
    for i, d in enumerate(sd.query_devices()):
        tipo = []
        if d["max_input_channels"] > 0:
            tipo.append("ENTRADA")
        if d["max_output_channels"] > 0:
            tipo.append("SALIDA")
        print(f"[{i:2d}] {d['name'][:50]:<50} | {' + '.join(tipo)}")
    print("=" * 70)
    print(f"\nEntrada por defecto: {sd.default.device[0]}")
    print(f"Salida por defecto:  {sd.default.device[1]}")


def probar_microfono(indice: int, duracion: int = 2):
    print(f"\n[PRUEBA] Grabando {duracion}s del dispositivo #{indice}...")
    try:
        grabacion = sd.rec(
            int(duracion * 48000), samplerate=48000,
            channels=1, dtype="float32", device=indice,
        )
        sd.wait()
        volumen = np.max(np.abs(grabacion))
        barra = "#" * int(volumen * 50)
        estado = ">>> VOZ DETECTADA <<<" if volumen > 0.05 else "Silencio / Ruido bajo"
        print(f"  [{indice:2d}] Volumen: {volumen:.4f} | {barra:<50} | {estado}")
    except Exception as e:
        print(f"  [{indice:2d}] ERROR: {e}")


def main():
    listar_dispositivos()
    if len(sys.argv) > 1:
        try:
            probar_microfono(int(sys.argv[1]))
        except ValueError:
            print("Uso: python audio/scanner.py [índice_del_micrófono]")
    else:
        print("\nUso: python audio/scanner.py <índice> para probar un micrófono.")
        print("Actualiza MIC_DEVICE_INDEX en config.py con el índice correcto.")


if __name__ == "__main__":
    main()
