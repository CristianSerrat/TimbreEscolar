#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
====================================================================
SISTEMA DE MEGAFONÍA/TIMBRES ESCOLARES - FASE 2, PASO 2.2
====================================================================
Interfaz gráfica con NiceGUI + Planificador de audio integrado
- Reloj en tiempo real
- Estado del sistema con planificador funcional
- Notificaciones web cuando suena un timbre
- Tabla de horarios desde config.json
====================================================================
"""

import asyncio
import json
import signal
import time
from datetime import datetime, time as dt_time
from pathlib import Path

from nicegui import ui, app
import pytz
import pygame


# ============================================================
# CONFIGURACIÓN
# ============================================================
BASE_DIR = Path(__file__).parent.resolve()
CONFIG_PATH = BASE_DIR / "config.json"


# ============================================================
# FUNCIONES DE CONFIGURACIÓN (reutilizadas de la Fase 1)
# ============================================================

def cargar_configuracion() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


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
    horarios_validados = []
    ids_vistos = set()
    audio_default = config_global.get("audio_por_defecto")
    volumen_default = config_global.get("volumen_por_defecto", 0.8)

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

        audio_especifico = h.get("audio_especifico")
        ruta_audio_final = None

        if audio_especifico:
            try:
                ruta_audio_final = validar_audio_existe(audio_especifico, base_dir)
            except FileNotFoundError:
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


def obtener_hora_actual(zona: str) -> datetime:
    tz = pytz.timezone(zona)
    return datetime.now(tz)


def hora_coincide(hora_actual: dt_time, hora_programada: dt_time) -> bool:
    return (hora_actual.hour == hora_programada.hour and 
            hora_actual.minute == hora_programada.minute)


# ============================================================
# FUNCIONES DE AUDIO
# ============================================================

def inicializar_mixer():
    pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)


def reproducir_audio(ruta_audio: Path, volumen: float = 0.8):
    if not ruta_audio or not ruta_audio.exists():
        return False
    try:
        pygame.mixer.music.load(str(ruta_audio))
        pygame.mixer.music.set_volume(volumen)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            time.sleep(0.1)
        return True
    except pygame.error:
        return False


def cerrar_mixer():
    pygame.mixer.quit()


# ============================================================
# VARIABLES DE ESTADO GLOBAL
# ============================================================
estado_sistema = {
    "activo": False,
    "config": None,
    "zona_horaria": "Europe/Madrid",
    "horarios": [],
    "ultimo_timbre_minuto": None,
    "tarea_planificador": None
}


# ============================================================
# PLANIFICADOR ASÍNCRONO (corre en segundo plano)
# ============================================================

async def bucle_planificador():
    """
    Bucle asíncrono que comprueba cada segundo si hay que tocar un timbre.
    Se ejecuta en segundo plano sin bloquear la interfaz web.
    """
    zona = estado_sistema["zona_horaria"]
    horarios_activos = [h for h in estado_sistema["horarios"] if h["activo"]]

        # DEBUG
    print(f"[DEBUG] Horarios activos cargados: {len(horarios_activos)}")
    for h in horarios_activos:
        print(f"  - ID {h['id']}: {h['hora_str']} (obj: {h['hora_obj']}) | activo: {h['activo']}")

    ui.notify(f"Planificador iniciado. {len(horarios_activos)} horario(s) activo(s).", type="positive")

    while estado_sistema["activo"]:
        ahora = obtener_hora_actual(zona)
        hora_actual = ahora.time()
        minuto_actual = ahora.strftime("%H:%M")

          # DEBUG: muestra cada 10 segundos qué hora ve el planificador
        if int(minuto_actual.split(":")[1]) % 10 == 0 and int(ahora.strftime("%S")) == 0:
            print(f"[DEBUG] Hora actual: {minuto_actual} | Buscando: {[h['hora_str'] for h in horarios_activos]}")

        for horario in horarios_activos:
            # DEBUG
            print(f"[DEBUG] Comparando: actual={hora_actual.hour}:{hora_actual.minute} vs programada={horario['hora_obj'].hour}:{horario['hora_obj'].minute}")

            if hora_coincide(hora_actual, horario["hora_obj"]):
                # Anti-repetición: solo una vez por minuto
                if estado_sistema["ultimo_timbre_minuto"] != minuto_actual:
                    estado_sistema["ultimo_timbre_minuto"] = minuto_actual
                    
                    # Notificación en la web
                    ui.notify(
                        f"🔔 ¡TIMBRE! {horario['descripcion']} ({horario['hora_str']})",
                        type="positive",
                        close_button=True
                    )
                    
                    # Reproducir audio
                    reproducir_audio(horario["ruta_audio"], horario["volumen"])

        await asyncio.sleep(1)  # Asíncrono: no bloquea la UI

    ui.notify("Planificador detenido.", type="warning")


# ============================================================
# COMPONENTES DE LA INTERFAZ
# ============================================================

def crear_cabecera():
    with ui.header().classes("bg-blue-600 text-white"):
        with ui.row().classes("w-full items-center justify-between"):
            ui.label("🔔 Sistema de Timbres Escolares").classes("text-xl font-bold")
            ui.label("Panel de Control").classes("text-sm opacity-80")


def crear_reloj():
    with ui.card().classes("w-full"):
        ui.label("⏰ Hora Actual").classes("text-lg font-semibold text-gray-600")
        
        with ui.row().classes("items-baseline gap-4"):
            hora_label = ui.label("00:00:00").classes("text-5xl font-mono font-bold text-blue-700")
            fecha_label = ui.label("Cargando...").classes("text-md text-gray-500")
        
        def actualizar_reloj():
            hora_label.set_text(obtener_hora_actual(estado_sistema["zona_horaria"]).strftime("%H:%M:%S"))
            fecha_label.set_text(obtener_hora_actual(estado_sistema["zona_horaria"]).strftime("%A, %d de %B de %Y"))
        
        ui.timer(interval=1.0, callback=actualizar_reloj)
        actualizar_reloj()


def crear_estado_sistema():
    with ui.card().classes("w-full"):
        ui.label("📡 Estado del Sistema").classes("text-lg font-semibold text-gray-600")
        
        with ui.row().classes("items-center gap-4 mt-2"):
            indicador = ui.icon("circle", size="24px")
            texto_estado = ui.label("DETENIDO").classes("text-xl font-bold")
            boton = ui.button("Iniciar Planificador", color="green", icon="play_arrow")
            
            async def toggle_estado():
                estado_sistema["activo"] = not estado_sistema["activo"]
                
                if estado_sistema["activo"]:
                    # Iniciar planificador
                    indicador.classes("text-green-500", remove="text-red-500")
                    texto_estado.set_text("ACTIVO - Escuchando horarios")
                    texto_estado.classes("text-green-600", remove="text-red-600")
                    boton.set_text("Detener Planificador")
                    boton.props("color=red icon=stop")
                    
                    # Inicializar audio y lanzar planificador en background
                    inicializar_mixer()
                    estado_sistema["tarea_planificador"] = asyncio.create_task(bucle_planificador())
                    
                else:
                    # Detener planificador
                    indicador.classes("text-red-500", remove="text-green-500")
                    texto_estado.set_text("DETENIDO")
                    texto_estado.classes("text-red-600", remove="text-green-600")
                    boton.set_text("Iniciar Planificador")
                    boton.props("color=green icon=play_arrow")
                    
                    estado_sistema["activo"] = False
                    if estado_sistema["tarea_planificador"]:
                        estado_sistema["tarea_planificador"].cancel()
                        estado_sistema["tarea_planificador"] = None
                    cerrar_mixer()
            
            boton.on_click(toggle_estado)
            indicador.classes("text-red-500")
            texto_estado.classes("text-red-600")


def crear_tabla_horarios():
    with ui.card().classes("w-full"):
        ui.label("📋 Horarios Programados").classes("text-lg font-semibold text-gray-600 mb-2")
        
        horarios = estado_sistema.get("horarios", [])
        
        columnas = [
            {"name": "id", "label": "ID", "field": "id", "align": "center", "sortable": True},
            {"name": "hora", "label": "Hora", "field": "hora", "align": "center", "sortable": True},
            {"name": "descripcion", "label": "Descripción", "field": "descripcion", "align": "left"},
            {"name": "audio", "label": "Audio", "field": "audio", "align": "left"},
            {"name": "estado", "label": "Estado", "field": "estado", "align": "center"},
        ]
        
        filas = []
        for h in horarios:
            # CORREGIDO: usar h["hora_str"] y h["ruta_audio"] en vez de campos del JSON crudo
            audio = h["ruta_audio"].name if h["ruta_audio"] else "🎵 Por defecto"
            activo = "🟢 Activo" if h.get("activo", True) else "🔴 Inactivo"
            filas.append({
                "id": h["id"],
                "hora": h["hora_str"],  # ← CORREGIDO: era h["hora"]
                "descripcion": h.get("descripcion", "-"),
                "audio": audio,
                "estado": activo
            })
        
        if filas:
            ui.table(columns=columnas, rows=filas, row_key="id").classes("w-full")
        else:
            ui.label("No hay horarios configurados").classes("text-gray-400 italic")

def crear_info_config():
    with ui.card().classes("w-full"):
        ui.label("⚙️ Configuración Global").classes("text-lg font-semibold text-gray-600 mb-2")
        
        config = estado_sistema["config"]
        if config:
            global_cfg = config.get("configuracion_global", {})
            
            with ui.grid(columns=2).classes("gap-2"):
                ui.label("Audio por defecto:").classes("text-gray-500")
                ui.label(global_cfg.get("audio_por_defecto", "N/A")).classes("font-mono text-sm")
                
                ui.label("Volumen:").classes("text-gray-500")
                ui.label(f"{global_cfg.get('volumen_por_defecto', 'N/A')}").classes("font-mono")
                
                ui.label("Zona horaria:").classes("text-gray-500")
                ui.label(global_cfg.get("zona_horaria", "N/A")).classes("font-mono")
        else:
            ui.label("No se pudo cargar la configuración").classes("text-red-500")


# ============================================================
# PÁGINA PRINCIPAL
# ============================================================

@ui.page("/")
def pagina_principal():
    try:
        config = cargar_configuracion()
        estado_sistema["config"] = config
        cfg = config.get("configuracion_global", {})
        estado_sistema["zona_horaria"] = cfg.get("zona_horaria", "Europe/Madrid")
        estado_sistema["horarios"] = validar_y_normalizar_horarios(
            config["horarios"], cfg, BASE_DIR
        )
    except Exception as e:
        ui.notify(f"Error cargando config.json: {e}", type="negative")
        estado_sistema["config"] = None
        estado_sistema["horarios"] = []
    
    crear_cabecera()
    
    with ui.column().classes("w-full max-w-4xl mx-auto p-4 gap-4"):
        crear_reloj()
        crear_estado_sistema()
        crear_info_config()
        crear_tabla_horarios()
        
        ui.separator()
        ui.label("Fase 2.2 - NiceGUI + Planificador | Sistema de Timbres Escolares").classes(
            "text-center text-xs text-gray-400"
        )


# ============================================================
# PUNTO DE ENTRADA
# ============================================================

if __name__ in {"__main__", "__mp_main__"}:
    ui.run(
        title="Sistema de Timbres Escolares",
        host="0.0.0.0",
        port=8080,
        reload=False,
        show=False
    )