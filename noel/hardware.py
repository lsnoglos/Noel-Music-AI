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
