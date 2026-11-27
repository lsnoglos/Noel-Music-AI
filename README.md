# Noel Music AI

Estudio local de música para Windows x64. Esta primera entrega conecta una interfaz de comandos en español con ACE-Step C++ y guarda cada interpretación como una versión independiente. La prueba objetivo es una RTX 3070 Laptop de 8 GB con 16 GB de RAM.

## Abrir en Windows

Descargue el ZIP portable en [Releases](https://github.com/lsnoglos/Noel-Music-AI/releases) cuando haya una compilación publicada. Las compilaciones de prueba también se distribuyen desde [Actions](https://github.com/lsnoglos/Noel-Music-AI/actions/workflows/windows-cuda.yml). Extraiga el ZIP completo y abra **NoelMusicAI.cmd**. El asistente comprueba Python x64 y permite instalar el entorno en la carpeta privada del proyecto.

Abra **Modelos** y verifique los tres componentes básicos (hasta 3.67 GB). Si utiliza el ZIP de código fuente, el botón de instalación busca un motor compatible en las versiones publicadas. En **Crear música**, elija un género, escriba su letra y pruebe primero 15 segundos. **Biblioteca** permite reproducir la canción y guardar una copia WAV.

## Uso por consola

1. Siga la [instalación para Windows](docs/installation/WINDOWS.md) para compilar el motor CUDA y verificar los tres modelos.
2. Abra el motor con `NoelMusicAI.cmd start` y mantenga abierta su consola.
3. En otra consola, desde la carpeta del proyecto, ejecute:

   ```cmd
   NoelMusicAI.cmd generate "Balada acústica con guitarra de nylon y piano" --seconds 15
   ```

La ruta impresa abre el WAV estéreo a 48 kHz. Para probar letra propia, añada `--lyrics "Amanece y vuelvo a cantar"`. La semilla predeterminada es 42. Cada ejecución crea una carpeta en `runs` con el audio, su latente y los parámetros. Conserve el WAV de cualquier versión aprobada. Ctrl+C solicita cancelar el trabajo en curso.

## Verificación

```cmd
NoelMusicAI.cmd diagnose
NoelMusicAI.cmd health
NoelMusicAI.cmd benchmark --repeat 3
```

Consulte el [protocolo de medición](docs/benchmarks/PROTOCOL.md), los [resultados de desarrollo](docs/benchmarks/DEVELOPMENT.md) y el [estado de funciones](PROJECT_STATUS.md). La edición de letras conservando la instrumental y la creación con un perfil vocal autorizado son hitos posteriores.

## Desarrollo

Python 3.11 o superior, biblioteca estándar. Desde la raíz: `python -m unittest discover -v`. Prueba contra el servidor compilado: `python -m tests.server_contract RUTA_AL_BINARIO`. El motor y los pesos se instalan por separado. [Investigación](docs/research/ENGINE_EVALUATION.md) · [Arquitectura](docs/architecture/SYSTEM_DESIGN.md) · [Hoja de ruta](docs/ROADMAP.md).

## Mejoras de uso (rama de desarrollo)

La interfaz reúne Inicio, Crear música, Modelos y Configuración. Las descargas se gestionan por componente; los tres pesos básicos existentes siguen siendo necesarios. Los modelos LM 0.6B (709.85 MB) y SFT Q8 son opcionales. El compositor local usa /lm inspire y la letra permanece editable. Las preferencias vocales son condicionamiento textual, no una garantía de identidad o género vocal. El perfil Turbo Q8 de 8 pasos sigue predeterminado. Hasta 300 s y SFT son experimentales hasta comprobar la RTX 3070. El paquete Windows incorpora ruedas de ttkbootstrap/Pillow para una instalación privada sin conexión; si se ejecuta solo el código fuente sin esas bibliotecas se usa Tk como alternativa. Para desarrollo: python -m pip install -r requirements-ui.txt (preferentemente en un entorno virtual).

### Probar el código nuevo sobre un portable anterior

Cierra Noel Music AI. Haz una copia de seguridad. Extrae la rama de desarrollo en una carpeta separada y copia únicamente noel/, requirements-ui.txt y scripts/ en la instalación portable existente, conservando engine/, .runtime/, runs/ y engine-manifest.json. Para activar el tema en esta actualización de código fuente, instala las dependencias en la carpeta privada correspondiente a tu versión de Python, por ejemplo con Python 3.11: py -3.11 -m pip install --target ".runtime/ui-3.11" -r requirements-ui.txt. Después abre NoelMusicAI.cmd. La alternativa es utilizar el nuevo paquete portable cuando se publique.

## Distribución y actualizaciones ligeras

El workflow **Noel Music AI application packages** ejecuta pruebas y publica dos paquetes: NoelMusicAI-Update.zip (aplicación y ruedas de interfaz, sin motor ni modelos) y NoelMusicAI-Windows.zip (portable completo). El motor se reutiliza desde la publicación fijada en scripts/engine-base.json, verificando su tamaño, SHA-256, revisión e inventario. No se instala CUDA Toolkit para empaquetar cambios de interfaz. Para actualizar una instalación portable existente, cierra Noel y el motor, extrae el ZIP de actualización en otra carpeta y abre Actualizar.cmd; selecciona la instalación habitual. El instalador valida los archivos y conserva engine/, .runtime/ y runs/, incluyendo canciones, modelos y configuración. Conserva una copia de los archivos sustituidos en .noel-update-backup-*. No borres la copia hasta comprobar el funcionamiento. Verifica el SHA-256 publicado del ZIP antes de extraerlo.

El workflow **Compile CUDA engine (manual)** se ejecuta solo cuando se necesita reconstruir el motor. Tras validar una compilación nueva, actualiza scripts/engine-base.json con la revisión, URL, tamaño y hash del paquete publicado. Si la revisión no coincide, el empaquetado falla en lugar de usar un motor incompatible.

### Interfaz creativa
Inicio muestra tarjetas con acciones por canción, reproductor fijo, exportación WAV/MP3 local (320 kbps), letras y copia de ruta para compartir. El compositor integrado permite siete idiomas experimentales, seis secciones personalizadas, intención y estilo de escritura. La casilla instrumental ignora la letra sin borrarla. Los instrumentos y voces son condicionamiento, no garantía. El tema se inspira en degradados fucsia, violeta y azul. El motor y los pesos anteriores se conservan.

## Centro de modelos y compositor Qwen
Modelos separados por función. Cargar modelo importa un GGUF por tamaño y SHA-256 exactos; Guardar copia exporta sin mover el original. Qwen3 4B Instruct Q4_K_M (2.50 GB) se guarda en text-models para evitar el registro ACE-Step. Instala también el motor llama.cpp b12635 para CPU (~25 MB) o CUDA (~749 MB), mediante Modelos. Configuración permite CPU, GPU o CPU + GPU (ACE-Step en GPU y Qwen con 18 capas GPU). Los modelos se cargan bajo demanda, no simultáneamente. Turbo Q4 (1.45 GB) es una alternativa experimental de menor memoria; CPU puede ser lento. El perfil Q8 de 8 pasos sigue predeterminado. No hay benchmark de Qwen ni CPU real todavía.

Al descargar Qwen por primera vez se ofrece instalar su motor para el dispositivo seleccionado en la misma autorización. Si después cambias de CPU a GPU, o importas únicamente el GGUF, puedes instalar el motor correspondiente por separado. No se descargan pesos sin permiso.

## Editor musical (experimental)
La nueva sección conecta Cover sin FSQ, Repaint y referencia tímbrica de ACE-Step. No requiere modelos adicionales. Usa WAV PCM 16 bits de 44.1/48 kHz y material autorizado. Repaint permite preservar PCM fuera del intervalo si el WAV es estéreo 48 kHz. La nueva versión nunca sustituye el original. Referencia vocal no equivale a clonación exacta. Separación instrumental y síntesis cantada con letras nuevas permanecen pendientes; consulta docs/research/MUSIC_EDITOR.md.

## Espacio de creación y detección de recursos
Generar, instrumentos visibles (Automático/Manual) y duración inicial 60 s permanecen sobre el historial o compositor integrado. Animación silenciosa de cinco teclas durante trabajos en segundo plano; reproducción disponible. Descargar todo autoriza todos los modelos del catálogo y los motores pertinentes para el equipo, conserva archivos válidos. Nuevos Qwen3 0.6B Q4 (484 MB) y 1.7B Q4 (1.28 GB) usan llama.cpp con modo no-thinking; calidad y velocidad pendientes de benchmark. Las recomendaciones usan RAM, hilos CPU, GPU NVIDIA y VRAM, no representan garantías ni cambian la selección sin aceptación. En Configuración puedes elegir manualmente.

### Interfaz compacta
Los modelos para música y letras se seleccionan exclusivamente en Configuración. Los avisos de recursos son específicos por operación, centrados y solo permiten continuar o ajustar modelos. Entradas y listas blancas, copiar letra deshabilitado si está vacía, compositor compacto y tarjetas con play/pausa central y menú contextual. No se incorpora todavía Stable Audio 3: requiere un backend LiteRT separado, validación de licencias/descargas y pruebas CPU. SongGen no cuenta con benchmark CPU ni español validado.

El compositor mantiene Generar letra visible. Solo si la resolución o escala impiden mostrar todos los campos aparece desplazamiento auxiliar automático; la edición musical también tiene un aviso de recursos propio.

## Mis voces (experimental)
Perfiles locales con autorización: grabación por micrófono Windows MCI o importación WAV PCM16 de 5–30 s; recomendado 15–30 s limpios. Los perfiles aparecen en Crear música y Editor musical (excepto Repaint, para no modificar el audio exterior). Instalación opcional de audio.cpp v0.9.6 y pesos HTDemucs Q8/Seed-VC Q8 verificados. Genera primero con ACE-Step, libera el motor, separa, convierte y mezcla; conserva el original y el instrumental extraído. No garantiza timbre exacto ni pista de estudio original. CPU/GPU y duración real pendientes de benchmark. MIDI y generadores instrumentales ligeros permanecen pendientes, sin ediciones separadas.

Desde Editor musical, Sustituir cantante sin regenerar música aplica la conversión al WAV de origen, no a la letra escrita en el formulario; conserva la versión original. Descargar todo incluye los componentes vocales con autorización explícita. Las muestras de micrófono no salen del equipo.

### Laboratorio de voz
Qwen3-TTS 0.6B Base Q8 (1.99 GB) es opcional e independiente de Seed-VC/HTDemucs. Selecciona un perfil, escribe una frase y sintetiza WAV local; una transcripción exacta opcional habilita referencia de audio y texto, sin ella usa modo x-vector. No garantiza acento, ritmo de habla o identidad exactos. Conserva la referencia original y una prueba por perfil. Los géneros se amplían; Instrumental queda como check único. Las dimensiones musicales se expresan explícitamente en el caption y los tags vocales genéricos se refuerzan sin alterar palabras ni sobrescribir etiquetas explícitas. No son controles garantizados; pruebas de escucha pendientes.

### Espacio de voces
Prepara MP3/WAV o graba, navega por la onda, selecciona un fragmento de hasta 30 s (mínimo 5 s), opcionalmente extrae voz con HTDemucs, prueba frases y guarda solo cuando te convenza. Los borradores son temporales y las frases de cada perfil se guardan independientemente en WAV + JSON. Las pruebas antiguas sin texto se conservan como legado. Modelos de voz y motor se instalan desde Modelos; sustitución de cantante permanece en Editor musical. MP3 usa miniaudio local; no requiere FFmpeg. Límite de importación 5 minutos.

El actualizador incluye miniaudio en el wheelhouse y comprueba que esté importable al iniciar; no se necesita una instalación global. La transcripción se mantiene oculta como opción avanzada, y la reproducción de la muestra usa el reproductor compartido.
