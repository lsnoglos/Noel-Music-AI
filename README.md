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
