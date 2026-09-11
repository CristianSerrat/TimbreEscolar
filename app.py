#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
====================================================================
SISTEMA DE MEGAFONÍA/TIMBRES ESCOLARES - PANEL WEB (NiceGUI)
====================================================================
Interfaz gráfica con NiceGUI + Planificador de audio asíncrono
- Reloj sincronizado en tiempo real
- Planificador en segundo plano no bloqueante con auto-recarga de config.json
- Notificaciones seguras a todos los clientes web conectados
- Botón de prueba manual de sonido
- Tabla dinámica de horarios y estado del sistema
====================================================================
"""

import asyncio
import json
import time
from datetime import datetime, time as dt_time
from pathlib import Path

from nicegui import ui, app, Client
import pytz
import pygame


# ============================================================
# CONFIGURACIÓN DE RUTAS
# ============================================================
BASE_DIR = Path(__file__).parent.resolve()
CONFIG_PATH = BASE_DIR / "config.json"


# ============================================================
# LOGGING CON TIMESTAMP
# ============================================================
def log(mensaje: str, tipo: str = "info"):
    """Imprime un mensaje con timestamp en consola del servidor."""
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
    print(f"[{ahora}] {icono} {mensaje}", flush=True)


# ============================================================
# VARIABLES DE ESTADO GLOBAL
# ============================================================
estado_sistema = {
    "activo": True,  # Iniciar activo para funcionar desatendido en el servidor
    "config": None,
    "zona_horaria": "Europe/Madrid",
    "horarios": [],
    "ultimo_timbre_minuto": None,
    "tarea_planificador": None,
    "config_mtime": 0.0,
    "ultimo_timbre_tocado": None,
}


# ============================================================
# GESTIÓN DE CONFIGURACIÓN
# ============================================================
def cargar_configuracion() -> dict:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"No se encontró el archivo de configuración: {CONFIG_PATH}")
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
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
    horarios_validados = []
    ids_vistos = set()
    audio_default = config_global.get("audio_por_defecto")
    volumen_default = config_global.get("volumen_por_defecto", 0.8)

    if audio_default:
        try:
            validar_audio_existe(audio_default, base_dir)
        except FileNotFoundError:
            log(f"Audio por defecto no encontrado: {audio_default}", "warn")

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
                log(f"Audio específico no encontrado para horario {h['id']}, usando default", "warn")
                try:
                    ruta_audio_final = validar_audio_existe(audio_default, base_dir) if audio_default else None
                except FileNotFoundError:
                    ruta_audio_final = None
        else:
            try:
                ruta_audio_final = validar_audio_existe(audio_default, base_dir) if audio_default else None
            except FileNotFoundError:
                ruta_audio_final = None

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


def recargar_configuracion() -> tuple[bool, str]:
    """Lee config.json del disco y actualiza el estado global."""
    try:
        config = cargar_configuracion()
        estado_sistema["config"] = config
        cfg = config.get("configuracion_global", {})
        estado_sistema["zona_horaria"] = cfg.get("zona_horaria", "Europe/Madrid")
        estado_sistema["horarios"] = validar_y_normalizar_horarios(
            config["horarios"], cfg, BASE_DIR
        )
        try:
            estado_sistema["config_mtime"] = CONFIG_PATH.stat().st_mtime
        except Exception:
            pass
        msg = f"Configuración cargada correctamente ({len(estado_sistema['horarios'])} horarios)"
        log(msg, "ok")
        return True, msg
    except json.JSONDecodeError as e:
        msg = f"Error de formato JSON (línea {e.lineno}, col {e.colno}): {e.msg}"
        log(msg, "error")
        return False, msg
    except Exception as e:
        msg = f"Error cargando config.json: {e}"
        log(msg, "error")
        return False, msg


def verificar_actualizacion_config():
    """Detecta si config.json fue modificado en el disco y recarga automáticamente."""
    try:
        mtime = CONFIG_PATH.stat().st_mtime
        if mtime != estado_sistema["config_mtime"]:
            log("Cambio detectado en config.json. Recargando automáticamente...", "info")
            exito, msg = recargar_configuracion()
            if exito:
                notificar_clientes(f"Configuración recargada: {msg}", tipo="info")
            else:
                notificar_clientes(f"❌ {msg}", tipo="negative")
    except Exception:
        pass


# ============================================================
# FUNCIONES DE AUDIO (Asíncronas y seguras)
# ============================================================
def inicializar_mixer():
    if not pygame.mixer.get_init():
        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            log("Mixer de audio inicializado", "ok")
        except Exception as e:
            log(f"Error inicializando pygame.mixer: {e}", "error")


def cerrar_mixer():
    if pygame.mixer.get_init():
        pygame.mixer.quit()
        log("Mixer de audio liberado", "ok")


async def reproducir_audio(ruta_audio: Path, volumen: float = 0.8) -> bool:
    """Reproduce audio de forma asíncrona sin bloquear el event loop de NiceGUI."""
    if not ruta_audio or not ruta_audio.exists():
        log(f"Archivo de audio no encontrado para reproducir: {ruta_audio}", "error")
        return False

    try:
        inicializar_mixer()
        pygame.mixer.music.load(str(ruta_audio))
        pygame.mixer.music.set_volume(volumen)
        pygame.mixer.music.play()

        # Espera asíncrona: permite que el servidor y la web sigan respondiendo
        while pygame.mixer.music.get_busy():
            await asyncio.sleep(0.1)

        return True
    except pygame.error as e:
        log(f"Error de pygame al reproducir audio: {e}", "error")
        return False
    except Exception as e:
        log(f"Error inesperado en reproducción: {e}", "error")
        return False


# ============================================================
# GESTIÓN DE TIEMPO Y SINCRONIZACIÓN
# ============================================================
def obtener_hora_actual(zona: str) -> datetime:
    try:
        tz = pytz.timezone(zona)
    except Exception:
        tz = pytz.timezone("Europe/Madrid")
    return datetime.now(tz)


def hora_coincide(hora_actual: dt_time, hora_programada: dt_time) -> bool:
    return (hora_actual.hour == hora_programada.hour and 
            hora_actual.minute == hora_programada.minute)


def es_dia_laborable(ahora: datetime) -> bool:
    """Devuelve True solo si el día de la semana es de lunes (0) a viernes (4)."""
    return ahora.weekday() < 5  # 0=lunes … 4=viernes; 5=sábado, 6=domingo


# ============================================================
# NOTIFICACIONES A CLIENTES WEB
# ============================================================
def notificar_clientes(mensaje: str, tipo: str = "positive"):
    """Envía notificaciones a todas las sesiones web activas sin depender del slot context."""
    payload = {
        "message": str(mensaje),
        "type": tipo,
        "closeBtn": True,
        "position": "bottom",
        "multiLine": False,
    }
    for client in list(Client.instances.values()):
        try:
            if getattr(client, "has_socket_connection", False):
                client.outbox.enqueue_message("notify", payload, client.id)
        except Exception:
            pass


# ============================================================
# PLANIFICADOR ASÍNCRONO
# ============================================================
async def bucle_planificador():
    """Bucle que comprueba cada segundo los horarios programados."""
    log("Bucle planificador iniciado", "ok")
    notificar_clientes("Planificador activo y escuchando horarios", tipo="positive")

    while estado_sistema["activo"]:
        try:
            # Auto-recargar si config.json cambió en el disco
            verificar_actualizacion_config()

            zona = estado_sistema.get("zona_horaria", "Europe/Madrid")
            ahora = obtener_hora_actual(zona)
            hora_actual = ahora.time()
            minuto_actual = ahora.strftime("%H:%M")

            horarios_activos = [h for h in estado_sistema.get("horarios", []) if h.get("activo", True)]

            if es_dia_laborable(ahora):
                for horario in horarios_activos:
                    if hora_coincide(hora_actual, horario["hora_obj"]):
                        # Anti-repetición: solo una vez por minuto
                        if estado_sistema["ultimo_timbre_minuto"] != minuto_actual:
                            estado_sistema["ultimo_timbre_minuto"] = minuto_actual
                            estado_sistema["ultimo_timbre_tocado"] = f"{horario['descripcion']} ({minuto_actual})"

                            log(f"{'='*50}", "timbre")
                            log(f"¡TIMBRE! {horario['descripcion']} ({horario['hora_str']})", "timbre")
                            log(f"Audio: {horario['ruta_audio'].name if horario['ruta_audio'] else 'N/A'}", "timbre")
                            log(f"{'='*50}", "timbre")

                            notificar_clientes(
                                f"🔔 ¡TIMBRE! {horario['descripcion']} ({horario['hora_str']})",
                                tipo="positive"
                            )

                            # Reproducir audio de forma asíncrona
                            exito = await reproducir_audio(horario["ruta_audio"], horario.get("volumen", 0.8))
                            if exito:
                                log(f"Timbre '{horario['descripcion']}' completado con éxito", "ok")
                            else:
                                log(f"Fallo al reproducir timbre '{horario['descripcion']}'", "error")

        except asyncio.CancelledError:
            log("Tarea del planificador cancelada", "warn")
            break
        except Exception as e:
            log(f"Error inesperado en bucle planificador: {e}", "error")

        await asyncio.sleep(1)

    log("Planificador detenido", "info")


def iniciar_planificador():
    if estado_sistema["tarea_planificador"] is None or estado_sistema["tarea_planificador"].done():
        estado_sistema["activo"] = True
        inicializar_mixer()
        estado_sistema["tarea_planificador"] = asyncio.create_task(bucle_planificador())


def detener_planificador():
    estado_sistema["activo"] = False
    if estado_sistema["tarea_planificador"]:
        estado_sistema["tarea_planificador"].cancel()
        estado_sistema["tarea_planificador"] = None
    cerrar_mixer()


# ============================================================
# COMPONENTES DE LA INTERFAZ WEB
# ============================================================
def crear_cabecera():
    with ui.header().classes("bg-blue-700 text-white shadow-md"):
        with ui.row().classes("w-full items-center justify-between px-4"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("notifications_active", size="28px")
                ui.label("Sistema de Timbre Escolar ISP").classes("text-xl font-bold")
            ui.label("Panel de Control").classes("text-sm opacity-90")


def crear_reloj():
    with ui.card().classes("w-full shadow-sm"):
        ui.label("⏰ Hora Actual").classes("text-lg font-semibold text-gray-700")
        
        with ui.row().classes("items-baseline gap-4"):
            hora_label = ui.label("00:00:00").classes("text-5xl font-mono font-bold text-blue-700")
            fecha_label = ui.label("Cargando...").classes("text-md text-gray-500")

        def actualizar_reloj():
            ahora = obtener_hora_actual(estado_sistema.get("zona_horaria", "Europe/Madrid"))
            hora_label.set_text(ahora.strftime("%H:%M:%S"))
            fecha_label.set_text(ahora.strftime("%A, %d of %B of %Y"))

        ui.timer(interval=1.0, callback=actualizar_reloj)
        actualizar_reloj()


def crear_estado_sistema():
    with ui.card().classes("w-full shadow-sm"):
        ui.label("📡 Estado del Planificador").classes("text-lg font-semibold text-gray-700")

        with ui.row().classes("items-center gap-4 mt-2"):
            indicador = ui.icon("circle", size="24px")
            texto_estado = ui.label("").classes("text-xl font-bold")
            boton_toggle = ui.button()
            boton_prueba = ui.button("Probar Audio", icon="volume_up", color="indigo")

            def actualizar_vista_estado():
                if estado_sistema["activo"]:
                    indicador.classes("text-green-500", remove="text-red-500")
                    texto_estado.set_text("ACTIVO - Escuchando horarios")
                    texto_estado.classes("text-green-600", remove="text-red-600")
                    boton_toggle.set_text("Detener Planificador")
                    boton_toggle.props("color=red icon=stop")
                else:
                    indicador.classes("text-red-500", remove="text-green-500")
                    texto_estado.set_text("DETENIDO")
                    texto_estado.classes("text-red-600", remove="text-green-600")
                    boton_toggle.set_text("Iniciar Planificador")
                    boton_toggle.props("color=green icon=play_arrow")

            async def toggle_planificador():
                if estado_sistema["activo"]:
                    detener_planificador()
                    ui.notify("Planificador detenido manualmente", type="warning")
                else:
                    iniciar_planificador()
                    ui.notify("Planificador iniciado", type="positive")
                actualizar_vista_estado()

            async def ejecutar_prueba_audio():
                ui.notify("Reproduciendo prueba de sonido...", type="info")
                cfg = estado_sistema.get("config", {}).get("configuracion_global", {})
                audio_default = cfg.get("audio_por_defecto", "audios/timbre_default.mp3")
                try:
                    ruta = validar_audio_existe(audio_default, BASE_DIR)
                    exito = await reproducir_audio(ruta, cfg.get("volumen_por_defecto", 0.8))
                    if exito:
                        ui.notify("✅ Prueba de sonido completada con éxito", type="positive")
                    else:
                        ui.notify("❌ Error al reproducir la prueba de sonido", type="negative")
                except Exception as err:
                    ui.notify(f"❌ Error: {err}", type="negative")

            boton_toggle.on_click(toggle_planificador)
            boton_prueba.on_click(ejecutar_prueba_audio)

            # Inicializar vista con el estado real
            actualizar_vista_estado()

            # Timer para mantener la interfaz sincronizada si el estado cambia
            ui.timer(interval=2.0, callback=actualizar_vista_estado)


def obtener_filas_horarios() -> list[dict]:
    """Genera las filas para ui.table a partir del estado global."""
    filas = []
    for h in estado_sistema.get("horarios", []):
        audio_nombre = h["ruta_audio"].name if h["ruta_audio"] else "🎵 Por defecto"
        activo = "🟢 Activo" if h.get("activo", True) else "🔴 Inactivo"
        filas.append({
            "id": h["id"],
            "hora": h["hora_str"],
            "descripcion": h.get("descripcion", "-"),
            "audio": audio_nombre,
            "estado": activo
        })
    return filas


def crear_tabla_horarios():
    with ui.card().classes("w-full shadow-sm"):
        with ui.row().classes("w-full items-center justify-between mb-2"):
            ui.label("📋 Horarios Programados").classes("text-lg font-semibold text-gray-700")

            async def refrescar_tabla():
                exito, msg = recargar_configuracion()
                tabla.rows = obtener_filas_horarios()
                tabla.update()
                if exito:
                    ui.notify(f"✅ {msg}", type="positive")
                else:
                    ui.notify(f"❌ {msg}", type="negative", close_button=True)

            ui.button("Recargar config.json", icon="refresh", color="gray-700", on_click=refrescar_tabla).props("outline size=sm")

        columnas = [
            {"name": "id", "label": "ID", "field": "id", "align": "center", "sortable": True},
            {"name": "hora", "label": "Hora", "field": "hora", "align": "center", "sortable": True},
            {"name": "descripcion", "label": "Descripción", "field": "descripcion", "align": "left"},
            {"name": "audio", "label": "Archivo de Audio", "field": "audio", "align": "left"},
            {"name": "estado", "label": "Estado", "field": "estado", "align": "center"},
        ]

        tabla = ui.table(columns=columnas, rows=obtener_filas_horarios(), row_key="id").classes("w-full")

        # Mantener la tabla sincronizada si config.json cambia externamente
        def sincronizar_tabla():
            nuevas_filas = obtener_filas_horarios()
            if tabla.rows != nuevas_filas:
                tabla.rows = nuevas_filas
                tabla.update()

        ui.timer(interval=2.0, callback=sincronizar_tabla)


def crear_info_config():
    with ui.card().classes("w-full shadow-sm"):
        ui.label("⚙️ Configuración Global").classes("text-lg font-semibold text-gray-700 mb-2")
        config = estado_sistema.get("config")
        if config:
            global_cfg = config.get("configuracion_global", {})
            with ui.grid(columns=2).classes("gap-2 w-full"):
                ui.label("Audio por defecto:").classes("text-gray-500")
                ui.label(global_cfg.get("audio_por_defecto", "N/A")).classes("font-mono text-sm")

                ui.label("Volumen global:").classes("text-gray-500")
                ui.label(f"{int(global_cfg.get('volumen_por_defecto', 0.8) * 100)}%").classes("font-mono")

                ui.label("Zona horaria:").classes("text-gray-500")
                ui.label(global_cfg.get("zona_horaria", "Europe/Madrid")).classes("font-mono")
        else:
            ui.label("No se pudo cargar la configuración global").classes("text-red-500")


# ============================================================
# PÁGINA PRINCIPAL
# ============================================================
@ui.page("/")
def pagina_principal():
    # Recargar configuración si está vacía
    if not estado_sistema["horarios"]:
        recargar_configuracion()

    crear_cabecera()

    with ui.column().classes("w-full max-w-4xl mx-auto p-4 gap-4"):
        crear_reloj()
        crear_estado_sistema()
        crear_info_config()
        crear_tabla_horarios()

        ui.separator()
        ui.label("Sistema de Megafonía y Timbres Escolares | NiceGUI + Pygame Mixer").classes(
            "text-center text-xs text-gray-400 w-full"
        )


# ============================================================
# ARRANQUE AUTOMÁTICO AL INICIAR EL SERVIDOR
# ============================================================
def arranque_servidor():
    log("Iniciando servicio de megafonía escolar...", "info")
    recargar_configuracion()
    iniciar_planificador()

app.on_startup(arranque_servidor)
app.on_shutdown(detener_planificador)


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