"""Translate user-friendly controls into explicit musical conditioning."""
import re
VOICES = {
    "Automática": "",
    "Masculina": "solo male lead singer, clearly masculine singing voice, no female lead vocals",
    "Femenina": "solo female lead singer, clearly feminine singing voice, no male lead vocals",
    "Dúo": "male and female vocal duet, alternating lead lines, harmonized chorus",
    "Coro masculino": "male vocal ensemble, layered male harmonies",
    "Coro femenino": "female vocal ensemble, layered female harmonies",
    "Coro mixto": "mixed male and female choir, layered vocal harmonies",
    "Niño": "solo boy treble singer, youthful high register, light clear childlike vocal timbre",
    "Niña": "solo girl treble singer, youthful high register, light clear childlike vocal timbre",
    "Coro de niños": "children\'s choir as lead vocal ensemble, bright youthful treble voices in unison and harmony",
    "Tenor": "solo male tenor lead, resonant high male register, supported sustained notes, singing in the selected musical genre",
    "Barítono": "male baritone, warm resonant lower register",
    "Bajo": "male bass singer, deep resonant low register",
    "Soprano (ópera)": "solo operatic soprano lead, soaring upper female register, controlled vibrato and lyrical projection, singing in the selected musical genre",
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
    "Enérgica": "energetic", "Espiritual": "contemplative, reverent emotional expression, sense of transcendence", "Eufórica": "euphoric",
    "Triste": "sad, reflective",
}
AMBIENCES = {
    "Libre": "", "Estudio profesional": "clean professional studio production",
    "Acústico": "natural organic recording texture, minimal artificial effects", "Verano": "warm summer atmosphere",
    "Playa tropical": "tropical beach atmosphere", "Atardecer": "warm sunset atmosphere",
    "Noche romántica": "warm intimate nighttime atmosphere", "Íntimo": "intimate room ambience",
    "Concierto": "live stage sound, spacious hall ambience, subtle audience atmosphere", "Fiesta": "festive party atmosphere",
    "Discoteca": "club-style sound system, punchy low end, spacious dancefloor production", "Cinematográfico": "cinematic soundscape",
    "Orquestal": "expansive orchestral concert-hall spatial acoustics", "Bar nocturno": "small late-night venue, close warm sound, subtle room reflections", "Nocturno": "dark spacious late-night atmosphere, restrained ambient textures",
    "Festival": "open air festival", "Naturaleza": "open-air spatial atmosphere, subtle natural background textures",
    "Iglesia": "large stone church acoustics, spacious natural reverb, long reverberation tails", "Navideño": "warm festive seasonal atmosphere",
    "Retro años 80": "1980s retro production", "Urbano": "modern urban production texture",
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
    parts = [f"Primary musical genre and rhythm: {genre}" if genre else "",
             f"Lead vocal performance: {VOICES[voice]}" if VOICES[voice] else "",
             f"Featured instruments: {ensemble}; prioritize this selected ensemble" if ensemble else "",
             f"Emotional expression: {MOODS[mood]}" if MOODS[mood] else "",
             f"Recording atmosphere and production: {AMBIENCES[ambience]}, retaining the primary genre" if AMBIENCES[ambience] else "",
             f"Additional production details: {style.strip()}" if style.strip() else ""]
    return ". ".join(filter(None,parts)) or "melodic song"


VOCAL_HINTS = {
    "Masculina":"male lead vocal", "Femenina":"female lead vocal",
    "Dúo":"male and female duet", "Coro masculino":"male choir",
    "Coro femenino":"female choir", "Coro mixto":"mixed choir",
    "Niño":"boy treble vocal", "Niña":"girl treble vocal", "Coro de niños":"children's choir",
    "Tenor":"tenor lead vocal", "Barítono":"baritone lead vocal", "Bajo":"bass lead vocal",
    "Soprano (ópera)":"operatic soprano lead", "Mezzosoprano":"mezzo-soprano lead", "Contralto":"contralto lead",
}

def vocal_lyrics(lyrics,voice):
    """Add short experimental performance hints without changing sung words or explicit tags."""
    hint=VOCAL_HINTS.get(voice)
    if not hint or not lyrics.strip():
        return lyrics
    pattern=r"(?im)^([ \t]*)\[((?:verse|chorus|pre-chorus|post-chorus|bridge|verso|coro|pre-coro|puente)(?:[ \t]+\d+)?)\]([ \t]*)$"
    if re.search(pattern,lyrics):
        return re.sub(pattern,lambda m:f"{m[1]}[{m[2]} - {hint}]{m[3]}",lyrics)
    if not re.search(r"(?m)^\s*\[[^\n\]]+\]",lyrics):
        return f"[Verse - {hint}]\n"+lyrics
    return lyrics


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
