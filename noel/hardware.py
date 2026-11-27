"""Conservative recommendations, not performance guarantees."""
from .models import MUSIC, LYRIC_MODELS

def recommend(info):
    gpu = info.get("gpu") or {}
    total = gpu.get("total_mib") or 0
    free = gpu.get("free_mib") or 0
    ram = (info.get("ram_total") or 0)/2**30
    available = (info.get("ram_available") or 0)/2**30
    threads = info.get("cpu_threads") or 0
    if not gpu or total < 4096:
        lyric = "qwen17" if ram >= 12 and available >= 5 and threads >= 8 else "qwen06"
        return {"device":"cpu","music":"turbo4","lyrics":lyric,
                "reason":"No se detectó una GPU NVIDIA con al menos 4 GiB de VRAM. La generación de música por CPU puede tardar mucho. Qwen3 0.6B es la alternativa más ligera."}
    if total < 8192 or free < 5500:
        return {"device":"gpu","music":"turbo4","lyrics":"qwen17" if free >= 2500 else "qwen06",
                "reason":"GPU NVIDIA detectada con memoria gráfica limitada o actualmente ocupada. Prueba modelos ligeros y libera memoria antes de generar."}
    return {"device":"gpu","music":"dit","lyrics":"qwen",
            "reason":"GPU NVIDIA con al menos 8 GiB y VRAM libre suficiente según el diagnóstico. Turbo Q8 conserva el perfil rápido; Qwen 4B prioriza instrucciones."}

def recommendation_text(info, recommendation):
    gpu = info.get("gpu") or {}
    details = (f"{gpu['name']} · {gpu.get('free_mib',0)} / {gpu.get('total_mib',0)} MiB libres"
               if gpu.get("name") else "Sin GPU NVIDIA detectada")
    return (details + f"\nRAM disponible: {(info.get('ram_available') or 0)/2**30:.1f} GiB"
            + f" · Hilos CPU: {info.get('cpu_threads') or '—'}\n\n"
            + recommendation["reason"] + "\n\nMúsica: " + MUSIC[recommendation["music"]]
            + "\nLetras: " + LYRIC_MODELS[recommendation["lyrics"]]
            + "\nSon recomendaciones iniciales; no garantizan velocidad ni compatibilidad.")


def operation_warning(info,device,purpose,selected):
    gpu=info.get("gpu") or {}
    free=gpu.get("free_mib") or 0
    ram=(info.get("ram_available") or 0)/2**30
    if purpose not in ("music","lyrics","editor"):
        raise ValueError("Operación desconocida")
    models=LYRIC_MODELS if purpose=="lyrics" else MUSIC
    label=models[selected]
    if device!="cpu" and not gpu:
        return f"El modelo {label} está configurado para GPU, pero no se detectó NVIDIA. Ajusta el procesador a CPU para poder utilizarlo."
    if purpose=="editor":
        if device=="cpu":
            return "El Editor musical procesa audio de referencia y puede requerir más tiempo y memoria que crear música. En CPU comienza con fragmentos cortos y cierra programas innecesarios."
        if free<4500 or ram<4:
            return "Recursos limitados para edición de audio. Libera memoria y prueba fragmentos cortos con Turbo Q4."
        return ""
    if purpose=="lyrics":
        if ram<3:
            return f"Solo hay {ram:.1f} GiB de RAM libre. {label} puede agotar la memoria; libera recursos antes de componer."
        if device=="cpu" and selected=="qwen" and ram<6:
            return "Qwen3 4B puede ser lento con la RAM libre actual. En Configuración puedes seleccionar Qwen3 0.6B o 1.7B."
        if device!="cpu" and free<2048:
            return "Hay poca VRAM libre para el compositor. Libera memoria o selecciona CPU."
        return ""
    if device=="cpu":
        return f"{label} generará música usando CPU. Puede tardar bastante; prueba una duración corta. Turbo Q4 es el modelo ACE-Step más ligero disponible en Noel."
    if free<3500 or ram<3:
        return f"Memoria disponible limitada para {label} ({free} MiB VRAM y {ram:.1f} GiB RAM). Prueba Turbo Q4 y una duración corta."
    return ""
