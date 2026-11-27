# Editor musical: evaluación y fases

## Fase 1 — motor fijado, sin nuevas descargas
ACE-Step C++ revisión 973517be024ff8b6bbd50e0adc9e308ab2ed71b3: https://github.com/ServeurpersoCom/acestep.cpp/blob/973517be024ff8b6bbd50e0adc9e308ab2ed71b3/docs/ARCHITECTURE.md
- cover-nofsq: fuente y referencia tímbrica, letra nueva; regenera toda la mezcla. No equivale a preservar pista instrumental.
- repaint: latentes originales fuera del intervalo; opcionalmente copiar PCM original fuera de rango para WAV estéreo 48 kHz 16 bits. Los latentes del motor se conservan por separado cuando la salida se empalma.
- text2music con ref_audio: referencia tímbrica, no clonación exacta. Solo fragmentos de voz autorizados de hasta 30 s.
- Primera implementación: WAV PCM 16 bits mono/estéreo 44.1/48 kHz, hasta 300 s y 64 MiB; MP3 importación pendiente. Turbo Q8 por defecto.
- Pruebas sintéticas de multipart, no sobrescritura y PCM. Pendiente inferencia real con CUDA.

## Fase 2 — separar voz e instrumental
Evaluar python-audio-separator (MIT, https://github.com/nomadkaraoke/python-audio-separator), MDX ONNX como primer candidato ligero y Mel-Band/BS-RoFormer como alternativa. Revisar licencias de cada peso y CUDA/cuDNN, aislar entorno. Mantener el instrumental extraído como archivo inmutable. Si se aporta pista instrumental original, no separarla ni regenerarla. No confundir separación estimada con máster instrumental exacto.

## Fase 3 — conversión vocal autorizada
SoulX-Singer-SVC (https://github.com/Soul-AILab/SoulX-Singer, Apache-2.0 según upstream) y Seed-VC (https://github.com/Plachtaa/seed-vc, GPL-3.0, archivado). SVC conserva contenido y melodía de una interpretación nueva; no crea palabras nuevas por sí solo. Evaluar referencia limpia, 8 GiB VRAM, entorno aislado y frases cortas. No distribuir voces sin permisos.

## Fase 4 — nuevas palabras con melodía existente
YingMusic-Singer-Plus (https://github.com/ASLP-lab/YingMusic-Singer-Plus) ofrece letra modificada + referencia melódica + timbre opcional, pero tokenizer chino/inglés; licencia CC BY 4.0 con excepción Stability AI Community License para VAE. SoulX-Singer SVS usa F0/MIDI y corpus mandarín, inglés, cantonés; español no demostrado. Evaluar DiffSinger/OpenUtau con banco que soporte fonemas españoles y licencia adecuada, más extracción de notas y alineación silábica. No incorporar automáticamente paquetes pesados antes de pruebas. Qwen puede adaptar métrica, no canta. Mezclar nueva voz con instrumental inmutable usando pistas separadas. 
## Validación
Comparar audio original, referencia y edición; verificar palabras, melodía, sincronía, timbre, artefactos, duración, RAM/VRAM y tiempo real. Empezar con 15-30 s de material propio y luego 120 s. Las pruebas CI no demuestran calidad de audio ni fidelidad vocal.
