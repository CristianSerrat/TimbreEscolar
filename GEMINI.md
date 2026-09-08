# Instrucciones del Proyecto para Agentes de IA

## 🎯 Objetivo General
**Sistema de Megafonía y Timbres Escolares Automatizado**.
Aplicación diseñada para automatizar y gestionar la reproducción programada de timbres, alertas sonoras y música escolar (entradas, recreos, cambios de clase y salidas) en centros educativos. Cuenta tanto con un motor CLI/servicio en segundo plano (`timbre.py`) como con un panel de control web interactivo (`app.py`) con reloj en tiempo real, monitoreo de estado y gestión de horarios.

## 🛠️ Stack Tecnológico
- **Lenguaje principal:** Python 3 (>= 3.10)
- **Interfaz Gráfica / Panel Web:** NiceGUI (FastAPI, Starlette, Uvicorn, Vue/Quasar, Socket.IO)
- **Motor de Audio:** Pygame (`pygame.mixer`) para reproducción y control de volumen de archivos MP3/WAV
- **Gestión Temporal y Planificación:** `asyncio`, `pytz` (soporte de zonas horarias IANA, por defecto `Europe/Madrid`), `schedule`, `datetime`
- **Almacenamiento y Configuración:** Archivos JSON estructurados (`config.json`), manipulación de rutas con `pathlib.Path`
- **Entorno y Dependencias:** `requeriments.txt` (Virtualenv en `.venv`)

## 📁 Estructura del Proyecto
- `app.py`: Aplicación web interactiva basada en NiceGUI (panel de administración, reloj sincronizado, monitor de estado del planificador asíncrono y visualización de horarios).
- `timbre.py`: Script CLI/backend autónomo para ejecución en consola o como servicio daemon; incluye modo simulación (`--simular`).
- `config.json`: Configuración centralizada del sistema (zona horaria, volumen por defecto, audio predeterminado y lista de horarios programados).
- `audios/`: Directorio de archivos de audio locales (ej. `timbre_default.mp3`, `salida.mp3`).
- `test_audio.py`: Script de verificación del subsistema de reproducción y mezclador con Pygame.
- `test_temporizador.py`: Script de prueba para validar la sincronización temporal y el mecanismo anti-repetición.
- `requeriments.txt`: Lista de dependencias del entorno de Python.

## 📋 Reglas de Desarrollo
1. **Calidad de Código y Tipado:** Escribe código en Python 3 limpio, modular y legible. Añade type annotations (`str`, `Path`, `dt_time`, etc.) en firmas de funciones.
2. **Gestión Portátil de Rutas:** Utiliza siempre `pathlib.Path` relativo a `BASE_DIR = Path(__file__).parent.resolve()` para garantizar compatibilidad multiplataforma (macOS, Linux/Raspberry Pi, Windows). Evita rutas absolutas codificadas en el código.
3. **Manejo de Errores y Robustez:** Implementa bloques `try/except` específicos capturando `FileNotFoundError`, `ValueError` y `pygame.error`. El sistema debe ser tolerante a fallos para no interrumpir el servicio escolar continuo.
4. **Ciclo de Vida de Audio:** Asegura la inicialización explícita (`pygame.mixer.init(...)`) y el cierre/liberación de recursos (`pygame.mixer.quit()`) en bloques `finally` o al detener servicios.
5. **No Bloqueo en UI:** En la interfaz de NiceGUI (`app.py`), el planificador debe ser asíncrono (`asyncio.sleep(1)` y `asyncio.create_task`) para evitar congelar el bucle de eventos y el renderizado web.
6. **Mecanismo Anti-repetición:** Mantén el control de activación por minuto (`ultimo_timbre_minuto`) para prevenir disparos duplicados dentro del mismo intervalo de 60 segundos.
7. **Pruebas y Validación:** Antes de dar por finalizada una tarea, verifica que no se rompan las dependencias y que los scripts de prueba (`test_audio.py`, `test_temporizador.py`) o la carga de `config.json` funcionen correctamente.

## ⛔ Restricciones
- **Sin Bloqueos Síncronos en NiceGUI:** Nunca uses `time.sleep()` prolongado dentro de corrutinas o eventos de la interfaz web en `app.py`.
- **Integridad de Configuración:** Valida la existencia de las secciones `configuracion_global` y `horarios` antes de procesar `config.json`.
- **Rutas de Audio Seguras:** Si un horario referencia un `audio_especifico` inexistente, aplica fallback automático a `audio_por_defecto` antes de fallar.
- **Rendimiento y Ligereza:** Mantén la aplicación optimizada para ejecutarse de forma continua en hardware ligero (como mini-PCs o Raspberry Pi conectadas a sistemas de megafonía escolar).
- **Control de Secretos y Configuración Sensible:** No almacenes datos sensibles ni credenciales en el repositorio; utiliza variables de entorno si se integran servicios externos.
