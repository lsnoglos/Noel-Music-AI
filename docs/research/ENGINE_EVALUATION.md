# Selección técnica para la primera prueba

**Decisión.** Medir primero la síntesis directa de acestep.cpp en CUDA con Turbo estándar Q8, embedding Q8 y VAE BF16. En 8 GB interesa eliminar etapas evitables, usar un lote de uno y medir la memoria libre. No hay evidencia comparativa de velocidad o calidad en la laptop objetivo.

| Candidato y revisión inspeccionada | Evidencia y mecanismo | Reutilización y riesgo de integración |
|---|---|---|
| [acestep.cpp](https://github.com/ServeurpersoCom/acestep.cpp/tree/973517be024ff8b6bbd50e0adc9e308ab2ed71b3) · MIT | Confirmado en tools/ace-server.cpp, src/request.cpp, model-registry.h, model-store.cpp y pipeline-synth-ops.cpp: HTTP asíncrono, selección GGUF por arquitectura y nombre, política estricta, WAV y latentes. CMake enlaza ggml-cuda y permite sm_86. | Proceso externo con intercambio de audio/latentes; coste de copias por medir. El preview y la toma definitiva se guardan por separado. Validación real de arranque y errores en CPU. |
| [ACE-Step 1.5 oficial](https://github.com/ace-step/ACE-Step-1.5/tree/ca1e85fe9430179831e6bc6be790c332190a3866) · MIT | Revisados el árbol de inferencia, pyproject.toml y opciones de offload de acestep/acestep_v15_pipeline.py. Referencia PyTorch para DiT/Flow Matching y extensiones. Los scripts Windows incluyen instalación y arranque. | Mayor superficie de dependencias y movimiento de tensores; la experiencia histórica del propietario justifica medir antes de adoptar. Variantes XL y LM 4B precisan series separadas. |
| [ComfyUI-AceStep_SFT](https://github.com/jeankassio/ComfyUI-AceStep_SFT/tree/3e802eae7132f954e7a99ea30d4e20e94561dddc) · MIT | Revisados nodes.py, conditioning_precompute.py y módulos de adaptación. Las rutas encode_tiled/decode_tiled dependen de la VAE y del runtime de ComfyUI. | Referencia para acondicionamiento, latentes y adaptación de voz. Una representación PyTorch de un nodo requiere validar forma, escala y compatibilidad antes de trasladarla a C++. |

### Coste, reproducción y viabilidad

| Ruta | Disco de pesos de esta prueba | Windows / offline | VRAM, RAM, tiempo de arranque e inferencia | Calidad musical, vocal y fidelidad |
|---|---:|---|---|---|
| C++ directo | 3.671 GB decimales; 3.42 GiB | Compilación Windows prevista por upstream. Ejecución local con pesos instalados. | Pendientes en RTX 3070. Diagnóstico y benchmark incluidos. | Pendiente escucha de tomas reales. |
| Oficial Python | Depende de variante y LM | Scripts Windows; instalar dependencias y checkpoints antes de desconectar. | Pendientes; reproducir el entorno exacto antes de comparar con el informe del propietario. | Pendiente comparación con mismo prompt, duración y semilla. |
| Nodos SFT | Depende de los modelos del workflow | Requiere ComfyUI y pesos locales compatibles. | Pendientes; no extrapolar resultados de una 3090. | Identidad y continuación experimentales; medir por frases. |

Para cada ruta, fijar motor, pesos y semilla documenta las condiciones. Las implementaciones y los kernels pueden producir salidas diferentes. Guardar el audio aprobado garantiza recuperar esa toma.

### Inventario para etapas posteriores

Se inspeccionaron árboles, licencias y documentación de cada revisión. La selección de pesos, el consumo de RAM/VRAM, tamaños, tiempos en Windows, calidad en español, compatibilidad offline con todas las dependencias y mantenimiento a la fecha de distribución requieren ensayos por candidato. Ninguno de estos motores se ejecutó para generar audio en esta entrega.

| Proyecto y revisión | Código | Uso y prueba decisiva |
|---|---|---|
| [adefossez/demucs](https://github.com/adefossez/demucs/tree/829d218) y [facebookresearch/demucs](https://github.com/facebookresearch/demucs/tree/e976d93) | MIT | Línea base Hybrid Demucs. Comparar el fork con el original en separación por segmentos y residuos vocales. |
| [python-audio-separator](https://github.com/nomadkaraoke/python-audio-separator/tree/4dd3477) | MIT | Adaptador de separación a evaluar por modelo MDX/RoFormer, proveedor ONNX y licencia individual. |
| [UVR GUI](https://github.com/Anjok07/ultimatevocalremovergui/tree/a5f8845) | README declara MIT | Comparador auditivo y referencia de separación. Evitar incluir la GUI completa. |
| [Seed-VC](https://github.com/Plachtaa/seed-vc/tree/51383ef) | GPL-3.0 | Candidato zero-shot para convertir una interpretación cantada. Probar referencia corta autorizada, registro, F0 y segmentos. Revisar pesos antes de empaquetar. |
| [RVC](https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI/tree/81eed5e) | MIT | Comparar voz entrenada, extracción de pitch y coste de preparación individual. |
| [DiffSinger](https://github.com/openvpi/DiffSinger/tree/17d8140) / [OpenUtau](https://github.com/stakira/OpenUtau/tree/08222cb) | Apache-2.0 / MIT | Síntesis desde partitura y fonemas. Validar renderer y banco español con licencia identificada y letra nueva. |
| [Basic Pitch](https://github.com/spotify/basic-pitch/tree/fa5997a) | Apache-2.0 | Medir errores de notas MIDI en stem vocal aislado; revisar vibrato y corrección manual. Contrastar con F0 de RMVPE o CREPE. |
| [Whisper](https://github.com/openai/whisper/tree/8609812) / [faster-whisper](https://github.com/SYSTRAN/faster-whisper/tree/6cb639e) | MIT / MIT | Comparar transcripción por frase y timestamps en canto español; el segundo usa CTranslate2. |
| [Essentia](https://github.com/MTG/essentia/tree/df27f94) / [librosa](https://github.com/librosa/librosa/tree/6327f7f) | AGPL-3.0 / ISC | Comparar tempo/tonalidad con anotaciones humanas; preferir la dependencia mínima que alcance la precisión medida. |
| [FFmpeg](https://github.com/FFmpeg/FFmpeg/tree/625234b) | LGPL/GPL según configuración | DSP y exportación posteriores. Inventariar flags y codecs del binario distribuido. |

Fuentes de los archivos GGUF: [punteros LFS con tamaños y hashes](https://huggingface.co/Serveurperso/ACE-Step-1.5-GGUF/commit/83f32e465c3abd605271d0c1c935ad2faf28c197). Las licencias citadas para repositorios de código no sustituyen la revisión de cada checkpoint.
