# Noel Music AI

Estudio local de música para Windows x64. Esta primera entrega conecta una interfaz de comandos en español con ACE-Step C++ y guarda cada interpretación como una versión independiente. La prueba objetivo es una RTX 3070 Laptop de 8 GB con 16 GB de RAM.

## Primera canción

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
