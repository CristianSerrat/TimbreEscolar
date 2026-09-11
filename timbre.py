#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
====================================================================
SISTEMA DE MEGAFONÍA/TIMBRES ESCOLARES - FASE 1 COMPLETA
====================================================================
Script base en Python (CLI / Backend)
- Lee configuración desde config.json
- Reproduce audios locales en horarios programados
- Precisión temporal con zona horaria
- Anti-repetición por minuto
====================================================================
"""

import argparse
import json
import signal
import sys
import time
from datetime import datetime, time as dt_time, timedelta
from pathlib import Path

import pytz
import pygame


# ============================================================
# CONFIGURACIÓN DE RUTAS
# ============================================================
BASE_DIR = Path(__file__).parent.resolve()
CONFIG_PATH = BASE_DIR / "config.json"


# ============================================================
# VARIABLES GLOBALES DE CONTROL
# ============================================================
ejecutando = True
ultimo_timbre_minuto = None
MODO_SIMULACION = False


# ============================================================
# MANEJO DE SEÑALES
# ============================================================

def manejar_senial(signum, frame):
    global ejecutando
    print("\n\n🛑 Señal de interrupción recibida. Cerrando sistema...")
    ejecutando = False

signal.signal(signal.SIGINT, manejar_senial)


# ============================================================
# FUNCIONES DE CONFIGURACIÓN (del Paso 1.1, mejoradas)
# ============================================================

def log(mensaje: str, tipo: str = "info"):
    """
    Imprime un mensaje con timestamp.
    """
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    iconos = {
        "info": "ℹ️ ",
        "ok": "✅",
        "warn": "⚠️ ",
        "error": "❌",
        "timbre": "🔔",
        "debug": "🔧"
    }
    icono = iconos.get(tipo, "•")
    print(f"[{ahora}] {icono} {mensaje}")


def cargar_configuracion(ruta: Path) -> dict:
    if not ruta.exists():
        raise FileNotFoundError(f"No se encontró el archivo de configuración: {ruta}")

    with open(ruta, "r", encoding="utf-8") as f:
        config = json.load(f)

    if "configuracion_global" not in config:
        raise ValueError("Falta la sección 'configuracion_global' en el JSON")
    if "horarios" not in config:
        raise ValueError("Falta la sección 'horarios' en el JSON")

    return config


def validar_audio_existe(ruta_audio: str, base_dir: Path) -> Path:
    ruta = Path(ruta_audio)
    if not ruta.is_absolute():
        ruta = base_dir / ruta

    if not ruta.exists():
        raise FileNotFoundError(f"Archivo de audio no encontrado: {ruta}")

    return ruta.resolve()


def parsear_hora(cadena_hora: str) -> dt_time:
    try:
        return datetime.strptime(cadena_hora, "%H:%M").time()
    except ValueError:
        raise ValueError(f"Formato de hora inválido: '{cadena_hora}'. Use HH:MM (24h)")


def validar_y_normalizar_horarios(horarios: list, config_global: dict, base_dir: Path) -> list:
    """
    Valida horarios y enriquece con rutas de audio resueltas.
    """
    horarios_validados = []
    ids_vistos = set()
    audio_default = config_global.get("audio_por_defecto")
    volumen_default = config_global.get("volumen_por_defecto", 0.8)

    # Validar que existe el audio por defecto
    if audio_default:
        validar_audio_existe(audio_default, base_dir)

    for idx, h in enumerate(horarios, start=1):
        if "id" not in h:
            raise ValueError(f"Horario #{idx}: falta el campo 'id'")
        if "hora" not in h:
            raise ValueError(f"Horario #{idx}: falta el campo 'hora'")

        if h["id"] in ids_vistos:
            raise ValueError(f"ID duplicado encontrado: {h['id']}")
        ids_vistos.add(h["id"])

        hora_obj = parsear_hora(h["hora"])

        # Determinar audio final para este horario
        audio_especifico = h.get("audio_especifico")
        ruta_audio_final = None

        if audio_especifico:
            try:
                ruta_audio_final = validar_audio_existe(audio_especifico, base_dir)
            except FileNotFoundError:
                log(f"Audio específico no encontrado para horario {h['id']}, usando default", "warn")
                ruta_audio_final = validar_audio_existe(audio_default, base_dir) if audio_default else None
        else:
            ruta_audio_final = validar_audio_existe(audio_default, base_dir) if audio_default else None

        horarios_validados.append({
            "id": h["id"],
            "hora_str": h["hora"],
            "hora_obj": hora_obj,
            "descripcion": h.get("descripcion", "Sin descripción"),
            "ruta_audio": ruta_audio_final,
            "volumen": h.get("volumen", volumen_default),
            "activo": h.get("activo", True)
        })

    return horarios_validados


# ============================================================
# FUNCIONES DE AUDIO (del Paso 1.2, integradas)
# ============================================================

def inicializar_mixer():
    log("Inicializando pygame.mixer...", "debug")
    pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
    log("Mixer inicializado correctamente", "ok")


def reproducir_audio(ruta_audio: Path, volumen: float = 0.8):
    if MODO_SIMULACION:
        log(f"[SIMULACIÓN] Se reproduciría: {ruta_audio.name} (volumen: {volumen*100:.0f}%)", "timbre")
        time.sleep(2)  # Simular duración
        return True

    if not ruta_audio or not ruta_audio.exists():
        log(f"Archivo de audio no encontrado: {ruta_audio}", "error")
        return False

    try:
        pygame.mixer.music.load(str(ruta_audio))
        pygame.mixer.music.set_volume(volumen)
        pygame.mixer.music.play()

        while pygame.mixer.music.get_busy():
            time.sleep(0.1)
        return True
    except pygame.error as e:
        log(f"Error de pygame: {e}", "error")
        return False


def cerrar_mixer():
    pygame.mixer.quit()
    log("Mixer liberado", "ok")


# ============================================================
# FUNCIONES DEL TEMPORIZADOR (del Paso 1.3, integradas)
# ============================================================

def obtener_hora_actual(zona: str) -> datetime:
    tz = pytz.timezone(zona)
    return datetime.now(tz)


def hora_coincide(hora_actual: dt_time, hora_programada: dt_time) -> bool:
    return (hora_actual.hour == hora_programada.hour and 
            hora_actual.minute == hora_programada.minute)


def es_dia_laborable(ahora: datetime) -> bool:
    """Devuelve True solo si el día de la semana es de lunes (0) a viernes (4)."""
    return ahora.weekday() < 5  # 0=lunes … 4=viernes; 5=sábado, 6=domingo


def sonar_timbre(horario: dict, zona: str):
    global ultimo_timbre_minuto

    ahora = obtener_hora_actual(zona)
    minuto_actual = ahora.strftime("%H:%M")

    # Anti-repetición: solo una vez por minuto
    if ultimo_timbre_minuto == minuto_actual:
        return

    ultimo_timbre_minuto = minuto_actual

    log(f"{'='*50}", "timbre")
    log(f"¡TIMBRE! {horario['descripcion']}", "timbre")
    log(f"Hora: {horario['hora_str']} | Zona: {zona}", "timbre")
    log(f"Audio: {horario['ruta_audio'].name if horario['ruta_audio'] else 'N/A'}", "timbre")
    log(f"{'='*50}", "timbre")

    reproducir_audio(horario["ruta_audio"], horario["volumen"])

    log(f"Timbre '{horario['descripcion']}' completado", "ok")


def bucle_planificador(config: dict, horarios: list):
    global ejecutando

    zona = config["configuracion_global"].get("zona_horaria", "Europe/Madrid")
    horarios_activos = [h for h in horarios if h["activo"]]

    log(f"Zona horaria: {zona}")
    log(f"Horarios activos: {len(horarios_activos)}")
    for h in horarios_activos:
        audio_name = h['ruta_audio'].name if h['ruta_audio'] else 'N/A'
        log(f"  • {h['hora_str']} - {h['descripcion']} [{audio_name}]", "info")

    if MODO_SIMULACION:
        log("⚠️  MODO SIMULACIÓN ACTIVADO: No se reproducirá audio real", "warn")

    log("Planificador iniciado. Esperando horarios... (Ctrl+C para detener)\n")

    while ejecutando:
        ahora = obtener_hora_actual(zona)
        hora_actual = ahora.time()

        if es_dia_laborable(ahora):
            for horario in horarios_activos:
                if hora_coincide(hora_actual, horario["hora_obj"]):
                    sonar_timbre(horario, zona)
        
        time.sleep(1)


# ============================================================
# FUNCIÓN PRINCIPAL
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Sistema de Timbres Escolares")
    parser.add_argument("--simular", action="store_true", help="Modo simulación (sin audio real)")
    args = parser.parse_args()

    global MODO_SIMULACION
    MODO_SIMULACION = args.simular

    print("=" * 60)
    print("🔔 SISTEMA DE TIMBRES ESCOLARES - Fase 1 COMPLETA")
    print("=" * 60)

    try:
        # 1. Cargar y validar configuración
        log("Cargando configuración...")
        config = cargar_configuracion(CONFIG_PATH)
        log("Configuración cargada", "ok")

        # 2. Validar y normalizar horarios
        log("Validando horarios...")
        horarios = validar_y_normalizar_horarios(
            config["horarios"],
            config["configuracion_global"],
            BASE_DIR
        )
        log(f"{len(horarios)} horario(s) validado(s)", "ok")

        # 3. Inicializar audio
        inicializar_mixer()

        # 4. Iniciar planificador
        bucle_planificador(config, horarios)

    except FileNotFoundError as e:
        log(str(e), "error")
        sys.exit(1)
    except ValueError as e:
        log(str(e), "error")
        sys.exit(1)
    except Exception as e:
        log(f"Error inesperado: {e}", "error")
        sys.exit(1)
    finally:
        cerrar_mixer()
        log("Sistema detenido correctamente", "ok")


if __name__ == "__main__":
    main()