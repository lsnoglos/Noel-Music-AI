"""Translate user-friendly controls into explicit musical conditioning."""
VOICES = {
    "Automática": "",
    "Masculina": "solo male lead singer, clearly masculine singing voice, no female lead vocals",
    "Femenina": "solo female lead singer, clearly feminine singing voice, no male lead vocals",
    "Dúo": "male and female vocal duet, alternating lead lines, harmonized chorus",
    "Coro masculino": "male vocal ensemble, layered male harmonies",
    "Coro femenino": "female vocal ensemble, layered female harmonies",
    "Coro mixto": "mixed male and female choir, layered vocal harmonies",
    "Niño": "young boy singing voice, childlike male treble",
    "Niña": "young girl singing voice, childlike female treble",
    "Coro de niños": "children's choir, youthful voices singing together",
    "Tenor": "male classical tenor, resonant upper register",
    "Barítono": "male baritone, warm resonant lower register",
    "Bajo": "male bass singer, deep resonant low register",
    "Soprano (ópera)": "female operatic soprano, classical lyrical singing",
    "Mezzosoprano": "female classical mezzo-soprano, rich middle register",
    "Contralto": "female contralto, deep warm lower register",
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
LANGUAGES = {"Español": ("es", "Spanish"), "Inglés": ("en", "English"),
             "Portugués": ("pt", "Portuguese"), "Francés": ("fr", "French"),
             "Italiano": ("it", "Italian"), "Alemán": ("de", "German"),
             "Japonés": ("ja", "Japanese")}
INSTRUMENTS = {
    "Guitarra acústica": "acoustic guitar", "Guitarra eléctrica": "electric guitar",
    "Requinto": "requinto guitar", "Piano": "piano", "Bajo": "bass guitar",
    "Violín": "violin", "Violonchelo": "cello", "Batería": "drums",
    "Bongó": "bongos", "Congas": "congas", "Güira": "guira",
    "Maracas": "maracas", "Trompeta": "trumpet", "Saxofón": "saxophone",
    "Flauta": "flute", "Acordeón": "accordion", "Marimba": "marimba",
    "Sintetizador": "synthesizer", "Arpa": "harp", "Órgano": "organ",
}
SECTIONS = {"Omitir": "", "Intro": "Intro", "Verso 1": "Verse 1", "Verso 2": "Verse 2",
            "Verso 3": "Verse 3", "Pre-coro": "Pre-Chorus", "Coro": "Chorus",
            "Puente": "Bridge", "Outro": "Outro", "Hablado": "Spoken Word",
            "Instrumental": "Instrumental Break", "Solo": "Instrumental Solo"}
INTENTIONS = {"Libre": "free theme", "Patriótica": "patriotic pride", "Enamorada": "being in love",
              "Protesta": "social protest", "Desahogo": "emotional release",
              "Desamor": "heartbreak", "Esperanza": "hope", "Celebración": "celebration",
              "Inspiración": "inspiration", "Espiritual": "spiritual reflection",
              "Humor": "humorous", "Nostalgia": "nostalgia", "Infantil": "child-friendly story"}
COMPLEXITIES = {"Poética": "poetic with imagery", "Sencilla y pegadiza": "simple and catchy",
                "Narrativa y profunda": "narrative and meaningful", "Divertida": "playful",
                "Romántica": "romantic"}
def caption(genre, mood, ambience, voice, style, instruments=()):
    ensemble = ", ".join(INSTRUMENTS[x] for x in instruments)
    instrumentation = "featured instruments: " + ensemble if ensemble else ""
    return ", ".join(filter(None, (genre, MOODS[mood], AMBIENCES[ambience], VOICES[voice],
                                   instrumentation, style.strip()))) or "melodic song"


def lyric_prompt(topic, musical_style, structure, complexity, extra, language="Español",
                 intention="Libre", sections=(), seconds=120):
    if not topic.strip():
        raise ValueError("Escribe primero el tema de la canción.")
    code, name = LANGUAGES[language]
    if structure == "Personalizada":
        labels = [SECTIONS[x] for x in sections if SECTIONS[x]]
        if not labels:
            raise ValueError("Selecciona al menos una sección.")
        order = "exactly in this order: " + ", ".join("["+x+"]" for x in labels)
    else:
        order = STRUCTURES[structure]
    preference = COMPLEXITIES.get(complexity, complexity)
    return (f"Write original song lyrics entirely in {name} ({code}), "
            f"Topic: {topic.strip()}. Musical style: {musical_style}. "
            f"Song duration: about {seconds} seconds. Structure: {order}. "
            f"Lyrical intention: {INTENTIONS[intention]}. Writing preference: {preference}. "
            f"Use bracketed section labels, singable lines and no explanations. "
            f"Additional instructions: {extra.strip()}. All sung words must be in {name}.").strip()
