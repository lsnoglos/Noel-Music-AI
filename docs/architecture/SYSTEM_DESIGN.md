# Diseño del primer incremento

La CLI llama a un adaptador Python de biblioteca estándar. Un proceso ace-server independiente, enlazado con GGML/CUDA, ejecuta la inferencia. El servidor se inicia en primer plano para que su ciclo de vida, dispositivo y mensajes técnicos sean visibles. La comunicación se limita a HTTP en IPv4 loopback. Las descargas de pesos son una operación separada con consentimiento explícito.

## Contrato del motor fijado

| Operación | Transporte y resultado |
|---|---|
| Salud e inventario | GET /health y /props. Verificar status, versión y buckets embedding, dit y vae. |
| Generación | POST /synth con caption, lyrics, duration, seed, synth_model, vae, task_type, inference_steps, synth_batch_size y output_format=wav16. La respuesta inmediata contiene id hexadecimal de 16 caracteres. |
| Estado | GET /job?id=… devuelve running, done, failed o cancelled. El cliente solo solicita result=1 después de done. |
| Cancelación | POST /job?id=…&cancel=1. La señal es cooperativa. El motor puede necesitar tiempo para liberar recursos. |
| Resultado | multipart/mixed. Para lote 1 hay una parte audio/wav seguida por application/octet-stream con nombre latent. Cada frame latente ocupa 64 float32 little-endian. |
| Capacidades adicionales de upstream | /lm genera metadatos y códigos con LM instalado. /understand necesita LM y fuente. /vae acepta audio para codificar o src_latents para decodificar. El resultado de /vae es un cuerpo binario en el resultado del trabajo. |

El orquestador comprueba la duración, el formato, la longitud real de muestras y la pareja de latentes antes de publicar la versión. Escribe en una carpeta temporal del mismo volumen y la renombra. Un error conserva las versiones anteriores. El manifiesto registra parámetros, revisión de pesos, modelos declarados, hashes y procedencia IA. El catálogo SQLite con migraciones se incorporará con la gestión de proyectos de escritorio.

Contratos posteriores: separación devuelve stems alineados; análisis devuelve atributos con confianza; alineación devuelve intervalos editables; síntesis recibe notas/fonemas; conversión recibe interpretación y referencia autorizada; masterización recibe un WAV y crea una versión derivada. Cada adaptador requerirá validación independiente antes de habilitar su función.

## Escritorio Windows
WinForms arranca sin Python. Tk utiliza la biblioteca estándar para evitar descargas de un framework gráfico. Los trabajos de red y GPU se ejecutan en un hilo separado. El proceso de síntesis usa loopback y un puerto libre. Cada generación posee y cierra su proceso. Los motores reparados se instalan en directorios independientes con un puntero actualizado al final.
