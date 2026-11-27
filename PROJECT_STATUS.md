# Estado de Noel Music AI

Fase 1, integración de desarrollo. La base de arquitectura está en 1eaf85d. El commit de implementación se identifica con git log -1 -- noel/engine.py. Esta entrega trabaja en síntesis directa de una descripción y letra opcional.

**Implementado**: cliente local, inventario fijado y verificación de pesos, arranque CUDA en primer plano, diagnóstico, seguimiento y cancelación cooperativa, conservación de WAV/latente, manifiestos de versión y benchmark JSON/CSV.

**Comprobado en Linux**: compilación CPU del servidor fijado, arranque, identificación de los tres tipos GGUF con fixtures de metadatos, salud, props, rechazo de solicitudes inválidas y fallo asíncrono. Pruebas de transporte y audio con fixtures. Ver docs/benchmarks/DEVELOPMENT.md.

**Pendiente indispensable**: compilar en Windows y medir una generación real con pesos en la RTX 3070 Laptop. Sigue abierta la validación de escucha, tiempo, memoria, estabilidad y cancelación durante un kernel real. El ajuste VAE es experimental. El ejecutable portable de escritorio, conversión vocal, sustitución de letra, banco español y demás fases están en docs/ROADMAP.md.

**Siguiente tarea**: ejecutar el protocolo de 15/30/60/120 s, conservar logs y resultados y decidir el perfil predeterminado a partir de evidencia de la máquina objetivo.

Etapa 2 en desarrollo. Bootstrapper WinForms, GUI Tk, instalación selectiva, reparación de modelos, control de proceso y biblioteca implementados. La publicación preview requiere que el workflow Windows compile y valide el paquete. Pendientes escucha y mediciones CUDA en la RTX 3070.

Incremento de usabilidad: interfaz de cuatro secciones, asistente de composición local opcional, preferencias vocales en inglés, duración 300 s, Turbo/SFT, progreso contextual, reproductor compartido con búsqueda temporal y espectro calculado del WAV. Pendientes: prueba real de LM, SFT, duración de 300 s, audio y tema moderno en el equipo objetivo. No cambia la revisión del motor.

Separación de distribución: compilación CUDA manual, actualización de aplicación y portable completo desde un motor publicado y fijado por SHA-256. Actualizador con copia de seguridad y preservación de datos; pruebas en CI y prueba real de actualización pendientes.

Interfaz creativa: reproductor fijo, tarjetas, exportación MP3, ayuda flotante, compositor integrado multilingüe y estructura personalizada, instrumentos, estados de modelos y mantenimiento explicado. Pendientes las pruebas reales de voz, idioma, instrumentación y exportación en el equipo objetivo. Sin cambios de motor CUDA.

Centro de modelos: importación/exportación verificada, Qwen independiente con instalación por dispositivo, Turbo Q4, preferencias persistentes y copiar letra. Pendiente comprobar inferencia local Qwen y CPU/híbrido reales. No se recompila ACE-Step.

Editor musical fase 1: adaptador multipart nativo, Cover sin FSQ, Repaint (PCM exterior opcional), referencia tímbrica y guardado independiente. Pendientes pruebas reales RTX 3070 y separación/síntesis vocal. No se cambia el motor fijado ni se descargan modelos.

Espacio creativo: panel de generación fijo, instrumentos visibles, duración 60 s, piano de actividad, descarga completa, Qwen3 0.6B/1.7B, recomendación de hardware. Pendientes CI y benchmark real de nuevos Qwen y dimensiones/DPI del equipo. Motor ACE-Step sin cambios.

Interfaz compacta y avisos separados. Stable Audio 3 Small Music permanece en evaluación: motor Windows LiteRT, instrumental hasta 120 s, licencia y dependencias por verificar antes de incluir descargas. No se altera ACE-Step. Pruebas Windows pendientes.

Corrección adicional: desplazamiento auxiliar solo si no caben los campos y botón de composición fijo; aviso específico de edición con CPU o memoria limitada.

Mis voces: perfil de referencia local, grabación/importación WAV, selección en creación y edición, conversión de canciones existentes; integración experimental de audio.cpp/HTDemucs/Seed-VC con descargas verificadas. Pendiente validar micrófono Windows, contrato real de CLI, formato de stems e inferencia GPU/CPU. MIDI y motores instrumentales ligeros pendientes.

Laboratorio TTS: Qwen3-TTS 0.6B Q8 con SHA-256, transcripción opcional, frase de prueba y exportación WAV; géneros ampliados y condicionamiento estructurado. Pendiente inferencia real, compatibilidad CPU/CUDA, seguimiento de tipos vocales (niño/tenor/etc.) y comparación perceptual.
