import json
from .models import matches


def verify_engine(binary):
    manifest = binary.parent.parent / "engine-manifest.json"
    if binary.parent.name != "engine":
        return
    entries = json.loads(manifest.read_text(encoding="utf-8-sig"))
    if not any(e["name"] == "ace-server.exe" for e in entries):
        raise ValueError("El manifiesto carece del motor.")
    for entry in entries:
        path = binary.parent / entry["name"]
        if path.parent != binary.parent or not matches(path, entry["bytes"], entry["sha256"].lower()):
            raise ValueError(f"Componente dañado: {path.name}. Extraiga de nuevo el paquete Windows.")
