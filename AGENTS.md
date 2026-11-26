# Desarrollo de Noel Music AI

Use exclusivamente este repositorio. Preserve versiones, material privado y datos ajenos. Mantenga .runtime, modelos y resultados de usuario fuera del control de versiones. No haga force push. Para trabajo nuevo use ramas. Verifique firmas de API en la revisión fijada antes de modificar adaptadores. Los tests sintéticos y el contrato del servidor no demuestran inferencia. No anuncie fidelidad ni rendimiento antes de escuchar y medir en hardware objetivo.

Ejecute python -m unittest discover -v y, cuando haya binario, python -m tests.server_contract RUTA. Actualice PROJECT_STATUS.md, decisiones y resultados después de cada incremento. No instale ni descargue pesos grandes sin una acción explícita del usuario.

Para modificar la distribución, ejecutar los tests y comprobar el job de Windows, sus DLL y su manifiesto. Mantener el bootstrapper independiente de Python.
