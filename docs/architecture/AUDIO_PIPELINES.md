# Flujos de audio

## Primera prueba ejecutable

Descripción + letra opcional → text2music sin LM → codificador textual, DiT Turbo y VAE → WAV PCM16 y latente → versión. El LM de 4B puede planificar códigos musicales, pero /synth admite condicionamiento directo. Este primer benchmark mide exclusivamente el recorrido directo.

## Edición contemplada

El código de src/pipeline-synth-ops.cpp aplica audio_cover_strength a la fracción de pasos con contexto fuente. cover_noise_strength controla la mezcla inicial y el tramo de pasos restante. cover-nofsq permite usar los latentes fuente evitando el paso por el cuantizador. Repaint selecciona una región. Los latentes capturados pueden viajar como src_latents o ref_latents en multipart. Cambiar pasos o semilla puede modificar la interpretación.

Para conservar la instrumental, guardar el stem original, alinear notas y sílabas de la nueva letra, corregir frases, sintetizar una interpretación y mezclarla con ese stem. La conversión vocal necesita que esa interpretación ya contenga las palabras nuevas. Contrastar alineación, letra, afinación y residuos vocales con escucha A/B. Estos modos y el consentimiento de perfiles se desarrollarán después de medir el motor musical.

Una mejora que deba conservar la interpretación partirá del WAV aprobado para DSP. Un refinamiento generativo creará otra versión. Ningún proceso posterior deberá reemplazar los bytes de una toma aprobada.
