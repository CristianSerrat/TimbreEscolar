#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sistema de Megafonía/Timbres Escolares - Fase 1, Paso 1.3
Tutor: Módulo de temporizador preciso y sincronización
"""

import time
import signal
import sys
from datetime import datetime, time as dt_time
from pathlib import Path

import pytz
import pygame


# ============================================================
# CONFIGURACIÓN DE PRUEBA (hardcodeada para este paso)
# ============================================================
BASE_DIR = Path(__file__).parent.resolve()
AUDIO_DEFAULT = BASE_DIR / "audios" / "timbre_default.mp3"
ZONA_HORARIA = "Europe/Madrid"

# Horarios de PRUEBA: se ajustarán automáticamente a tu hora actual +1 min
# (Puedes modificar esto manualmente si prefieres una hora concreta)
HORARIOS_PRUEBA = [
    {"hora": "08:00", "descripcion": "Inicio de clases", "audio": None},
    {"hora": "10:30", "descripcion": "Recreo", "audio": None},
    {"hora": "12:00", "descripcion": "Fin de clases", "audio": None},
]


# ============================================================
# VARIABLES GLOBALES DE CONTROL
# ============================================================
ejecutando = True
ultimo_timbre_minuto = None  # Evita sonar dos veces en el mismo minuto


# ============================================================
# MANEJO DE SEÑALES (Ctrl+C para salir limpio)
# ============================================================

def manejar_senial(signum, frame):
    global ejecutando
    print("\n\n🛑 Señal de interrupción recibida. Cerrando sistema...")
    ejecutando = False

signal.signal(signal.SIGINT, manejar_senial)


# ============================================================
# FUNCIONES DE AUDIO (reutilizadas del Paso 1.2)
# ============================================================

def inicializar_mixer():
    pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
    print("   ✅ Mixer inicializado")


def reproducir_audio(ruta_audio: Path, volumen: float = 0.8):
    if not ruta_audio.exists():
        print(f"   ⚠️  Archivo no encontrado: {ruta_audio}")
        return False

    pygame.mixer.music.load(str(ruta_audio))
    pygame.mixer.music.set_volume(volumen)
    pygame.mixer.music.play()

    while pygame.mixer.music.get_busy():
        time.sleep(0.1)
    return True


def cerrar_mixer():
    pygame.mixer.quit()


# ============================================================
# FUNCIONES DEL TEMPORIZADOR
# ============================================================

def obtener_hora_actual(zona: str) -> datetime:
    """
    Obtiene la hora actual en la zona horaria configurada.
    """
    tz = pytz.timezone(zona)
    return datetime.now(tz)


def hora_coincide(hora_actual: dt_time, hora_programada: str) -> bool:
    """
    Comprueba si la hora actual coincide con la hora programada (HH:MM).
    """
    try:
        hora_prog = datetime.strptime(hora_programada, "%H:%M").time()
        return (hora_actual.hour == hora_prog.hour and 
                hora_actual.minute == hora_prog.minute)
    except ValueError:
        return False


def sonar_timbre(horario: dict):
    """
    Ejecuta la reproducción del timbre para un horario dado.
    """
    print(f"\n{'='*60}")
    print(f"🔔 ¡TIMBRE! {horario['descripcion']}")
    print(f"   Hora: {horario['hora']}")
    print(f"{'='*60}")

    # Determinar qué audio reproducir
    ruta_audio = Path(horario["audio"]) if horario["audio"] else AUDIO_DEFAULT
    if not ruta_audio.is_absolute():
        ruta_audio = BASE_DIR / ruta_audio

    reproducir_audio(ruta_audio, volumen=0.8)

    print(f"✅ Timbre '{horario['descripcion']}' completado\n")


# ============================================================
# BUCLE PRINCIPAL DEL PLANIFICADOR
# ============================================================

def bucle_planificador(horarios: list):
    """
    Bucle infinito que comprueba cada segundo si hay que tocar un timbre.
    """
    global ultimo_timbre_minuto

    print(f"\n🕐 Zona horaria activa: {ZONA_HORARIA}")
    print(f"⏱️  Comprobando cada segundo...")
    print(f"📋 Horarios programados:")
    for h in horarios:
        print(f"   • {h['hora']} - {h['descripcion']}")
    print(f"\n🚀 Planificador iniciado. Esperando horarios...")
    print(f"   (Presiona Ctrl+C para detener)\n")

    while ejecutando:
        ahora = obtener_hora_actual(ZONA_HORARIA)
        hora_actual = ahora.time()
        minuto_actual = ahora.strftime("%H:%M")

        # Revisar cada horario programado
        for horario in horarios:
            if hora_coincide(hora_actual, horario["hora"]):
                # Anti-repetición: solo suena una vez por minuto
                if ultimo_timbre_minuto != minuto_actual:
                    ultimo_timbre_minuto = minuto_actual
                    sonar_timbre(horario)

        time.sleep(1)  # Comprobar cada segundo (balance precisión/CPU)


# ============================================================
# FUNCIÓN PRINCIPAL
# ============================================================

def main():
    print("=" * 60)
    print("🔔 SISTEMA DE TIMBRES ESCOLARES - Fase 1, Paso 1.3")
    print("   Módulo: Temporizador preciso y sincronización")
    print("=" * 60)

    # Ajustar horario de prueba ahora + 1 minuto para test inmediato
    ahora = obtener_hora_actual(ZONA_HORARIA)
    hora_prueba = (ahora.replace(second=0, microsecond=0) + __import__('datetime').timedelta(minutes=1)).strftime("%H:%M")
    
    horarios_test = HORARIOS_PRUEBA.copy()
    horarios_test.insert(0, {
        "hora": hora_prueba,
        "descripcion": "🧪 PRUEBA AUTOMÁTICA (ahora + 1 min)",
        "audio": None
    })

    print(f"\n🧪 MODO PRUEBA ACTIVADO")
    print(f"   Se ha añadido un horario de prueba a las {hora_prueba}")
    print(f"   para que no tengas que esperar.\n")

    try:
        inicializar_mixer()
        bucle_planificador(horarios_test)

    except Exception as e:
        print(f"\n💥 ERROR: {e}")
    finally:
        cerrar_mixer()
        print("\n✅ Sistema detenido correctamente")


if __name__ == "__main__":
    main()