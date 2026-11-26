# Instalación de desarrollo en Windows x64

Esta distribución inicial compila desde fuentes. Reserve espacio para el compilador, CUDA, la compilación, 3.671 GB decimales de pesos y las versiones de audio. El entorno inicial necesita internet y permisos normales de escritura en la carpeta elegida. Los componentes de desarrollo de Windows pueden pedir permisos al instalarse.

1. Instale Git para Windows, Python 3.11 x64 con el lanzador py, Visual Studio 2022 Build Tools con «Desarrollo para el escritorio con C++», MSVC x64 compatible con CUDA 12.8, Windows SDK, CMake y Ninja. Instale CUDA Toolkit 12.8 y el controlador NVIDIA compatible. Un controlador que ejecuta aplicaciones CUDA por sí solo carece del compilador nvcc.
2. Abra **x64 Native Tools Command Prompt for VS 2022**. Ejecute cada línea y corrija cualquier error antes de seguir.

   ```cmd
   git clone https://github.com/lsnoglos/Noel-Music-AI.git
   cd Noel-Music-AI
   NoelMusicAI.cmd diagnose
   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\build-windows.ps1
   NoelMusicAI.cmd models
   ```

3. Revise los tres archivos y tamaños mostrados. Para autorizar la transferencia ejecute `NoelMusicAI.cmd models --download`. La descarga usa curl con HTTPS, un commit fijo y validación SHA-256. Ctrl+C conserva el parcial. Repita el comando para reanudar. Si un cierre forzoso dejó `.runtime/models/.installing`, cierre cualquier instalador de Noel antes de quitar únicamente ese archivo.
4. Ejecute `NoelMusicAI.cmd start`. Comprueba los hashes y selecciona CUDA0. Espere la línea «Listening on 127.0.0.1:8085». En una segunda consola de la misma carpeta ejecute `NoelMusicAI.cmd health` y el ejemplo del README. Desde este punto puede trabajar sin conexión.
5. Para guardar los pesos en otro disco, anteponga `--models-dir "D:\Noel\Modelos"` a los comandos models y start. Dedique esa carpeta a los tres modelos. Para exportar en otra ruta, anteponga `--output "D:\Noel\Canciones"` a generate o benchmark. El puerto se cambia anteponiendo `--port 8086` a start y a cada cliente.

## Diagnóstico y reparación

- **No aparece la GPU**. Ejecute nvidia-smi. Compruebe el controlador, la GPU con índice 0 y la memoria disponible. En un equipo con varias GPU esta versión utiliza el índice 0.
- **Falla la compilación**. Verifique `where cl`, `where nvcc`, `where cmake` y `where ninja` en la misma consola. Revise el primer error de CMake. Si cambió de compilador, renombre .runtime/build antes de recompilar.
- **El motor rechaza una versión o un modelo**. Use el binario construido por este proyecto y los pesos del manifiesto. Vuelva a ejecutar models --download para verificar la instalación.
- **Memoria insuficiente o trabajo fallido**. Guarde el mensaje de la consola del motor, cierre aplicaciones que usen GPU y repita primero con 15 segundos. El estado health solo acredita conectividad e inventario.
- **Detener y conservar proyectos**. Ctrl+C en el cliente solicita cancelar. Ctrl+C en la consola del servidor lo detiene. Para retirar la instalación, conserve runs y cualquier salida personalizada y retire únicamente la carpeta de instalación que creó. Las dependencias compartidas se administran aparte.
