# Verificación de la integración · 26 de noviembre de 2026

Entorno Linux x86_64 con g++ 14, CMake 4.4.5 y backend CPU. nvidia-smi ausente. Se compiló ace-server en Release desde 973517b y su submódulo ggml fijado. Los modelos de varios GB no se descargaron.

| Ensayo | Resultado observado |
|---|---|
| Arranque con GGUF sintéticos de metadatos | El binario real reconoció 1 text-encoder, 1 DiT, 1 VAE, 0 LM; política STRICT; /synth disponible. |
| HTTP real con el adaptador propio | Salud ok, revisión 973517b, solicitud sin caption rechazada con 400, trabajo con modelo inexistente identificado y reportado failed. |
| Fixtures unitarios y transporte HTTP simulado | Pareja WAV/latente, versión con hash, trabajo fallido, timeout, interrupción, silencio, duración y multipart truncado. |
| Diagnóstico e inventario sin descarga | Ambos comandos finalizaron en Linux y mostraron campos ausentes y tamaños de pesos. |
| Inferencia y benchmark CUDA con audio real | Pendientes. No se ha medido RTF ni fidelidad. |

Para reproducir el contrato en Linux, usar el árbol y submódulos fijados, configurar CMake en Release con GGML_NATIVE=OFF, compilar el target ace-server y ejecutar python -m tests.server_contract con la ruta del binario. Los fixtures contienen metadatos GGUF sin tensores de inferencia.

La suite local también verifica las cuatro duraciones, las repeticiones, el informe parcial de un benchmark fallido y la instalación con consentimiento y comprobación de hash. Se ejecutaron 12 pruebas automatizadas y la prueba independiente del servidor real.
