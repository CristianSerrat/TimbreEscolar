#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sistema de Megafonía/Timbres Escolares - Fase 1, Paso 1.2
Tutor: Módulo de prueba de reproducción de audio con pygame
"""

import time
import sys
from pathlib import Path

import pygame


# ============================================================
# CONFIGURACIÓN DE PRUEBA (hardcodeada para este paso)
# ============================================================
BASE_DIR = Path(__file__).parent.resolve()
AUDIO_DEFAULT = BASE_DIR / "audios" / "timbre_default.mp3"
AUDIO_ESPECIFICO = BASE_DIR / "audios" / "salida.mp3"  # Puede no existir, lo manejamos


# ============================================================
# FUNCIONES DE AUDIO
# ============================================================

def inicializar_mixer():
    """
    Inicializa el subsistema de audio de pygame.
    """
    print("🔧 Inicializando pygame.mixer...")
    pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
    print("   ✅ Mixer inicializado correctamente")


def reproducir_audio(ruta_audio: Path, volumen: float = 0.8, descripcion: str = "Audio"):
    """
    Reproduce un archivo MP3 y espera a que termine.
    
    Args:
        ruta_audio: Ruta al archivo MP3
        volumen: Nivel de volumen (0.0 a 1.0)
        descripcion: Texto descriptivo para mostrar en consola
    """
    if not ruta_audio.exists():
        print(f"   ⚠️  {descripcion}: archivo no encontrado → {ruta_audio}")
        return False

    print(f"\n🎵 Reproduciendo: {descripcion}")
    print(f"   📁 Archivo: {ruta_audio}")
    print(f"   🔊 Volumen: {volumen * 100:.0f}%")

    try:
        # Cargar y reproducir
        pygame.mixer.music.load(str(ruta_audio))
        pygame.mixer.music.set_volume(volumen)
        pygame.mixer.music.play()

        # Esperar a que termine la reproducción
        while pygame.mixer.music.get_busy():
            time.sleep(0.1)

        print(f"   ✅ Reproducción de '{descripcion}' finalizada")
        return True

    except pygame.error as e:
        print(f"   ❌ Error de pygame: {e}")
        return False


def cerrar_mixer():
    """
    Libera los recursos del mixer.
    """
    pygame.mixer.quit()
    print("\n🔧 Mixer liberado correctamente")


# ============================================================
# FUNCIÓN PRINCIPAL DE PRUEBA
# ============================================================

def main():
    print("=" * 60)
    print("🔔 SISTEMA DE TIMBRES ESCOLARES - Fase 1, Paso 1.2")
    print("   Módulo: Prueba de reproducción de audio")
    print("=" * 60)

    try:
        # 1. Inicializar
        inicializar_mixer()

        # 2. Prueba 1: Audio por defecto
        print("\n" + "-" * 60)
        print("🧪 PRUEBA 1: Reproducción de audio POR DEFECTO")
        print("-" * 60)
        reproducir_audio(AUDIO_DEFAULT, volumen=0.8, descripcion="Timbre por defecto")

        # 3. Prueba 2: Audio específico (si existe)
        print("\n" + "-" * 60)
        print("🧪 PRUEBA 2: Reproducción de audio ESPECÍFICO")
        print("-" * 60)
        if AUDIO_ESPECIFICO.exists():
            reproducir_audio(AUDIO_ESPECIFICO, volumen=1.0, descripcion="Timbre de salida")
        else:
            print(f"   ℹ️  No se encontró '{AUDIO_ESPECIFICO.name}'")
            print("   (Esto es normal si aún no tienes un audio específico)")
            print("   Copia cualquier MP3 como 'audios/salida.mp3' si quieres probarlo")

        # 4. Prueba 3: Volumen bajo (para no molestar si estás en clase 😄)
        print("\n" + "-" * 60)
        print("🧪 PRUEBA 3: Reproducción con volumen reducido (20%)")
        print("-" * 60)
        reproducir_audio(AUDIO_DEFAULT, volumen=0.2, descripcion="Timbre silencioso")

        # 5. Cierre limpio
        cerrar_mixer()

        print("\n" + "=" * 60)
        print("✅ PASO 1.2 COMPLETADO: Módulo de audio probado correctamente")
        print("=" * 60)

    except Exception as e:
        print(f"\n💥 ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()