# Componentes y procedencia

El cliente propio usa Python 3.11+ y su biblioteca estándar. Para construir se utilizan Git, MSVC, Windows SDK, Ninja, CMake y NVIDIA CUDA Toolkit. Para descargar se invoca curl. Los componentes externos conservan sus términos originales. Este repositorio no redistribuye ejecutables, pesos ni grabaciones.

| Dependencia | Revisión y términos revisados |
|---|---|
| ServeurpersoCom/acestep.cpp | 973517be024ff8b6bbd50e0adc9e308ab2ed71b3, MIT. La compilación trae ggml ef4555b7aede4467a5de803b103615e0a5f30dd8 y dependencias vendorizadas del árbol. Mantener sus avisos al distribuir binarios. |
| Serveurperso/ACE-Step-1.5-GGUF | 83f32e465c3abd605271d0c1c935ad2faf28c197. La ficha del repositorio declara MIT. El manifiesto noel/models.py fija tamaños y SHA-256 de tres conversiones. |
| Referencias de investigación | Inventario y licencias de código en docs/research/ENGINE_EVALUATION.md. No son dependencias instaladas. |

La licencia de código, los términos de pesos y bancos de voz, los derechos de grabaciones y los datos de entrenamiento tienen procedencias distintas. Revisar esos inventarios por componente antes de distribuir una versión empaquetada o perfiles vocales. El propietario mantiene la decisión sobre la licencia de publicación del cliente propio.

El bootstrapper utiliza PowerShell y WinForms del sistema. Python 3.14.10 x64 se obtiene de python.org con autorización, SHA-256 y Authenticode. Tk forma parte de la instalación seleccionada. El paquete Windows incluye DLL necesarias de GGML, CUDA y MSVC. Los controladores de GPU pertenecen al sistema.

- ttkbootstrap 2.2.7 (MIT): https://pypi.org/project/ttkbootstrap/2.2.7/
- Pillow 12.2.0 (HPND): https://pypi.org/project/pillow/12.2.0/
  Las ruedas redistribuidas incluyen sus metadatos y avisos de licencia.
