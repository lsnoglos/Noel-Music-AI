# Memoria y ejecución

El servidor fijado crea ModelStore con EVICT_STRICT mientras se omita --keep-loaded. Al liberarse el último usuario de un módulo, el almacén puede descargarlo. El pico también depende de activaciones, longitud, buffers CUDA y VAE. Sumar el tamaño de los GGUF no predice ese pico.

Perfil inicial experimental: CUDA0, lote 1, Turbo 8 pasos. Al arrancar, el lanzador mide la VRAM libre. Usa bloques VAE de 128 frames si hay menos de 6000 MiB libres y 256 en otro caso, con solapamiento de 32. Es una hipótesis para medir en Ampere. El tamaño se fija al arrancar y puede requerir reinicio si cambia la carga del equipo. El motor encola los trabajos en un worker. El benchmark emite solicitudes secuenciales y detiene la serie ante el primer fallo.

El diagnóstico mide RAM física y VRAM disponible. El benchmark registra picos muestreados del sistema, que incluyen otras aplicaciones. No obtiene memoria compartida WDDM ni atribuye toda la VRAM a Noel. La compilación específica sm_86 y --device CUDA0 seleccionan el backend; el uso real por operación deberá contrastarse con la consola y la telemetría en Windows.
