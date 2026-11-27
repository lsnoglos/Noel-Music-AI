"""Translate user-friendly controls into explicit musical conditioning."""
VOICES = {
    "Automática": "",
    "Masculina": "solo male lead singer, clearly masculine singing voice, no female lead vocals",
    "Femenina": "solo female lead singer, clearly feminine singing voice, no male lead vocals",
    "Dúo": "male and female vocal duet, alternating lead lines, harmonized chorus",
    "Coro masculino": "male vocal ensemble, layered male harmonies",
    "Coro femenino": "female vocal ensemble, layered female harmonies",
    "Coro mixto": "mixed male and female choir, layered vocal harmonies",
    "Instrumental": "instrumental only, no singing, no spoken words",
}
MOODS = {
    "Natural": "", "Romántica": "romantic, tender", "Alegre": "joyful, uplifting",
    "Melancólica": "melancholic, bittersweet", "Nostálgica": "nostalgic",
    "Apasionada": "passionate, expressive", "Épica": "epic, triumphant",
    "Sensual": "sensual, intimate", "Esperanzadora": "hopeful",
    "Relajante": "calm, soothing", "Motivadora": "motivational, inspiring",
    "Divertida": "playful, humorous", "Misteriosa": "mysterious",
    "Dramática": "dramatic, emotional", "Rebelde": "rebellious",
    "Enérgica": "energetic", "Espiritual": "spiritual", "Eufórica": "euphoric",
    "Triste": "sad, reflective",
}
AMBIENCES = {
    "Libre": "", "Estudio profesional": "clean professional studio production",
    "Acústico": "organic acoustic arrangement", "Verano": "warm summer atmosphere",
    "Playa tropical": "tropical beach atmosphere", "Atardecer": "warm sunset atmosphere",
    "Noche romántica": "romantic nighttime atmosphere", "Íntimo": "intimate room ambience",
    "Concierto": "live concert performance", "Fiesta": "festive party atmosphere",
    "Discoteca": "nightclub production", "Cinematográfico": "cinematic soundscape",
    "Orquestal": "orchestral arrangement", "Bar nocturno": "late night lounge",
    "Festival": "open air festival", "Naturaleza": "organic nature ambience",
    "Iglesia": "reverberant sacred atmosphere", "Navideño": "festive Christmas atmosphere",
    "Retro años 80": "1980s retro production", "Urbano": "urban production",
    "Futurista": "futuristic electronic sound",
}
STRUCTURES = {
    "Comercial": "intro, verse, pre-chorus, catchy chorus, verse, bridge, final chorus, outro",
    "Narrativa": "storytelling verses, recurring chorus, meaningful conclusion",
    "Verso y coro": "alternating verses and chorus",
    "Dúo": "alternating male and female vocal verses, duet chorus",
    "Libre": "natural song structure",
}
def caption(genre, mood, ambience, voice, style):
    return ", ".join(filter(None, (genre, MOODS[mood], AMBIENCES[ambience], VOICES[voice], style.strip()))) or "melodic song"

def lyric_prompt(topic, musical_style, structure, complexity, extra):
    if not topic.strip():
        raise ValueError("Escribe primero el tema de la canción.")
    complexity = {"Poética": "poetic", "Sencilla y pegadiza": "simple and catchy",
                  "Narrativa y profunda": "narrative and meaningful", "Divertida": "playful",
                  "Romántica": "romantic"}.get(complexity, complexity)
    return (f"Write original Spanish song lyrics about: {topic.strip()}. "
            f"Musical style: {musical_style}. Structure: {STRUCTURES[structure]}. "
            f"Writing preference: {complexity}. Use bracketed section labels and singable lines. "
            f"Additional instructions: {extra.strip()}").strip()
