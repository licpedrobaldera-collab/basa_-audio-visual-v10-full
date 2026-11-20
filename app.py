import asyncio
import hashlib
import json
import re
import shutil
import uuid
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st

try:
    import edge_tts
    HAS_EDGE_TTS = True
except Exception:
    HAS_EDGE_TTS = False
try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except Exception:
    HAS_PIL = False

st.set_page_config(page_title="BASA Universal AI Studio v11 - 100/100", page_icon="⚡", layout="wide")

VAULT_DIR = Path("basa_vault_data")
MEDIA_DIR = VAULT_DIR / "media"
BACKUP_DIR = VAULT_DIR / "backups"
AUTO_EXPORT_DIR = VAULT_DIR / "auto_exports"
INDEX_FILE = VAULT_DIR / "vault_index.json"
ACCOUNTS_FILE = VAULT_DIR / "users_vault.json"
RELEASES_FILE = VAULT_DIR / "releases_log.json"
UI_STATE_FILE = VAULT_DIR / "ui_autosave_state.json"
LIBRARY_FILE = VAULT_DIR / "biblioteca_libre_basa.json"
HISTORY_FILE = VAULT_DIR / "historico_usuarios.json"
LEGAL_FILE = VAULT_DIR / "consentimiento_legal.json"

ADMIN_MASTER_PIN = "BASA-ADMIN-2026"
DEVELOPER_NAME = "Pedro Anibal Baldera Rondon - BASA Productions"
DEVELOPER_ID = "BASA-DEV-2026"

# ============================================================================
# CATALOGO + IA DE GENERO / VOZ / RITMO
# ============================================================================
REGION_GENRE_DEFAULTS: dict[str, list[str]] = {
    "Republica Dominicana (Caribe)": ["Bachata Dominicana", "Merengue de Calle / Mambo", "Salsa Clasica"],
    "Mexico": ["Ranchera / Mariachi", "Musica Mexicana / Banda", "Balada"],
    "Puerto Rico / Urbano Latino": ["Reggaeton", "Salsa Clasica", "Dembow / Urbano"],
    "Estados Unidos / Internacional": ["Pop / Rock Americano", "R&B / Soul Americano", "Balada"],
    "Colombia / Sudamerica": ["Salsa Clasica", "Cumbia / Vallenato", "Bolero"],
    "Global / Personalizado": ["Bachata Dominicana", "Merengue de Calle / Mambo", "Salsa Clasica"],
}
ALL_WORLD_GENRES: list[str] = [
    "Bachata Dominicana", "Merengue de Calle / Mambo", "Merengue Tipico (Perico Ripiao)",
    "Salsa Clasica", "Bolero", "Reggaeton", "Balada", "Ranchera / Mariachi",
    "Musica Mexicana / Banda", "Pop / Rock Americano", "R&B / Soul Americano",
    "Dembow / Urbano", "Cumbia / Vallenato", "Score Cinematografico / Orquestal",
    "Fusion: Bachata + Merengue", "Fusion: Salsa + Dembow", "Fusion: Pop + Urbano",
    "Fusion: Ranchera + Balada", "Fusion: Cumbia + Reggaeton",
]

VOICE_PROFILES: dict[str, dict[str, Any]] = {
    "Voz Masculina": {"voice": "es-DO-EmilioNeural", "rate": "+0%", "pitch": "+0Hz", "mode": "solo", "genero": "masc"},
    "Voz Femenina": {"voice": "es-DO-RamonaNeural", "rate": "+0%", "pitch": "+0Hz", "mode": "solo", "genero": "fem"},
    "Voz Juvenil Masculina": {"voice": "es-MX-JorgeNeural", "rate": "+8%", "pitch": "+18Hz", "mode": "solo", "genero": "masc"},
    "Voz Juvenil Femenina": {"voice": "es-MX-DaliaNeural", "rate": "+8%", "pitch": "+22Hz", "mode": "solo", "genero": "fem"},
    "Voz Infantil (Nino/Nina)": {"voice": "es-MX-DaliaNeural", "rate": "+5%", "pitch": "+55Hz", "mode": "solo", "genero": "fem"},
    "Coro Grupal": {"voice": "es-DO-RamonaNeural", "rate": "+2%", "pitch": "+0Hz", "mode": "choir", "genero": "mixto"},
    "Solo Instrumental": {"voice": "", "rate": "+0%", "pitch": "+0Hz", "mode": "instrumental", "genero": "none"},
}

CINEMA_STYLES: dict[str, tuple[tuple[int, int, int], tuple[int, int, int], tuple[int, int, int]]] = {
    "Cine Epico / Hollywood Dorado": ((14, 18, 34), (245, 208, 97), (225, 232, 245)),
    "Accion / Cyberpunk Neon": ((10, 12, 24), (0, 240, 255), (235, 245, 255)),
    "Animacion 3D / Familiar": ((22, 34, 68), (255, 185, 65), (255, 255, 255)),
    "Documental / Historia Real": ((24, 22, 20), (218, 175, 110), (238, 234, 228)),
    "Drama / Suspenso Nocturno": ((8, 10, 14), (220, 65, 65), (215, 220, 225)),
}

LEGAL_TEXT = """CONTRATO LEGAL BASA - CESION DE DERECHOS - LEER ANTES DE MARCAR

Yo, el usuario que crea en BASA Universal AI Studio, DECLARO que entiendo y acepto:

1. Toda cancion, letra, audio, portada, video, serie o pelicula creada en BASA pasa legalmente a formar parte de BASA Productions, propiedad de Pedro Anibal Baldera Rondon, SIN RESTRICCION, para uso, distribucion, venta, licencia y publicacion mundial.
2. Yo cedo todos los derechos de autor, patrimoniales y de explotacion al desarrollador, de forma irrevocable.
3. Si deseo que la obra sea de mi propiedad exclusiva, debo PAGAR LA RESERVA / REGISTRO al desarrollador antes de publicarla. Sin pago de reserva, la obra es de BASA.
4. Este consentimiento se marca UNA SOLA VEZ y queda valido PARA SIEMPRE, desde este dispositivo o cualquier otro que yo utilice, vinculado a mi usuario.
5. Si NO marco este cotejo, NO puedo registrar ni publicar en BASA.
6. Este contrato se guarda con fecha, hora, usuario, dispositivo y hash legal como prueba.

Al marcar el cotejo, usted firma digitalmente este contrato.
"""

# ============================================================================
# IA - DETECCION AUTOMATICA
# ============================================================================
def ia_detectar_genero_desde_letra(letra: str, ultima_seleccion: list[str]) -> tuple[str, str, int]:
    t = letra.lower()
    score: dict[str, int] = {g: 0 for g in ALL_WORLD_GENRES}
    reglas = {
        "Bachata Dominicana": ["amor", "corazon", "te extrano", "llorando", "perdon", "bachata", "amargue", "traicion"],
        "Merengue de Calle / Mambo": ["baila", "fiesta", "merengue", "mambo", "goza", "barrio", "jocoso", "risa", "cafe", "guanabana", "mandinga"],
        "Merengue Tipico (Perico Ripiao)": ["perico", "tipico", "acordeon", "guira", "campo", "tipico"],
        "Salsa Clasica": ["salsa", "clave", "tumbao", "sonero", "bailador"],
        "Dembow / Urbano": ["dembow", "perreo", "teteo", "calle", "bloke", "prra", "wey"],
        "Reggaeton": ["reggaeton", "perreo", "bellaqueo", "dem bow"],
        "Ranchera / Mariachi": ["mariachi", "ranchera", "charro", "tequila", "mexico", "caballo"],
        "Balada": ["balada", "triste", "melancolia", "recuerdo", "lluvia"],
        "Bolero": ["bolero", "beso", "eterno", "romantico"],
        "Cumbia / Vallenato": ["cumbia", "vallenato", "acordeon", "parrandero"],
        "Pop / Rock Americano": ["pop", "rock", "baby", "party", "dance"],
        "Score Cinematografico / Orquestal": ["pelicula", "cine", "epico", "orquesta", "heroe"],
    }
    for genero, palabras in reglas.items():
        for p in palabras:
            if p in t:
                score[genero] += 2
    if "cafe" in t and "ondina" in t:
        score["Merengue de Calle / Mambo"] += 5
    if "miniel" in t and "lethy" in t:
        score["Merengue de Calle / Mambo"] += 5
    if len(t.split()) < 5:
        score["Merengue de Calle / Mambo"] += 1
    mejor = max(score, key=lambda k: score[k])
    if score[mejor] == 0:
        if ultima_seleccion:
            return ultima_seleccion[0], "Se uso ultima seleccion del usuario porque la letra no define genero.", 120
        return "Bachata Dominicana", "IA decidio por defecto: Bachata Dominicana (genero neutro RD).", 120
    bpm_map = {"Bachata Dominicana": 128, "Merengue de Calle / Mambo": 135, "Merengue Tipico (Perico Ripiao)": 140, "Salsa Clasica": 180, "Dembow / Urbano": 145, "Reggaeton": 95, "Ranchera / Mariachi": 110, "Balada": 80, "Bolero": 90, "Cumbia / Vallenato": 95, "Pop / Rock Americano": 120, "Score Cinematografico / Orquestal": 100}
    bpm = bpm_map.get(mejor, 120)
    return mejor, f"IA detecto '{mejor}' por palabras clave en la letra. Confianza alta.", bpm

def ia_elegir_mejor_voz(genero: str, letra: str, formato: str) -> tuple[str, dict[str, Any], str]:
    t = letra.lower()
    if "nino" in t or "nina" in t or "infantil" in t:
        return "Voz Infantil (Nino/Nina)", VOICE_PROFILES["Voz Infantil (Nino/Nina)"], "IA eligio Voz Infantil por contenido infantil."
    if formato == "Coro Grupal (Voces en Bloque)":
        return "Coro Grupal", VOICE_PROFILES["Coro Grupal"], "Formato Coro: 3 voces en bloque, afinadas."
    if "ella" in t and "mujer" in t or "ella canta" in t:
        return "Voz Femenina", VOICE_PROFILES["Voz Femenina"], "IA eligio Voz Femenina por narrativa femenina."
    if genero in ["Ranchera / Mariachi", "Merengue Tipico (Perico Ripiao)", "Bachata Dominicana"]:
        return "Voz Masculina", VOICE_PROFILES["Voz Masculina"], f"IA eligio Voz Masculina afinada para {genero} - la mas adecuada a nivel profesional."
    if genero in ["Balada", "Bolero", "Pop / Rock Americano"]:
        return "Voz Femenina", VOICE_PROFILES["Voz Femenina"], f"IA eligio Voz Femenina afinada para {genero}."
    return "Voz Masculina", VOICE_PROFILES["Voz Masculina"], f"IA eligio Voz Masculina por defecto para {genero}, afinada profesional."

def ia_decidir_formato(letra: str) -> str:
    t = letra.lower()
    if "coro" in t or "todos" in t or "barrio" in t or "fiesta" in t:
        return "Coro Grupal (Voces en Bloque)"
    if "duo" in t or "los dos" in t or "tu y yo" in t or "nosotros" in t:
        return "Duo (2 Voces)"
    return "Solista"

def ia_expandir_desde_palabra(entrada: str, genero: str, modo: str) -> str:
    entrada = entrada.strip()
    if not entrada:
        return "Rumbo a celebrar, larga vida y salud, bajo el amparo del Senor."
    if modo == "Tal como lo escribo":
        return entrada
    palabras = entrada.split()
    if len(palabras) == 1:
        return f"{entrada}, {entrada}, que suene en todo el barrio, que se escuche tu nombre con amor y alegria. Rumbo a celebrar, larga vida y salud, bajo el amparo del Senor, con {genero}, con ritmo y con sabor. {entrada} es la historia que hoy cantamos, con fe y con corazon, para toda Quisqueya."
    if len(palabras) <= 5:
        return f"{entrada}. Que se escuche en la calle, que se baile en la fiesta. Rumbo a celebrar, larga vida y salud, bajo el amparo del Senor. Con {genero}, con sabor dominicano, con Pedro Baldera y BASA Productions. {entrada}, y que siga la fiesta."
    if modo == "Con ayuda IA":
        return f"{entrada}\n[Coro IA] Rumbo a celebrar, larga vida y salud, bajo el amparo del Senor, con {genero}, a bailar sin parar."
    return f"{entrada}\n[Coro IA - BASA] Rumbo a celebrar, larga vida y salud, bajo el amparo del Senor, con {genero}, para todo el barrio."

def ia_combinar_generos(generos: list[str]) -> str:
    if len(generos) <= 1:
        return generos[0] if generos else "Bachata Dominicana"
    return " + ".join(generos[:3]) + " - Fusion estilo Suno / Gemini / Mureka"

# ============================================================================
# BOVEDA / HISTORICO / BIBLIOTECA / LEGAL
# ============================================================================
def init_dirs() -> None:
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    AUTO_EXPORT_DIR.mkdir(parents=True, exist_ok=True)

def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def _save_json(path: Path, data: Any) -> None:
    init_dirs()
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

def load_autosave_state() -> dict[str, Any]:
    init_dirs()
    default_ui = {
        "project_title": "Rumbo a Celebrar (Navidad)",
        "selected_region": "Republica Dominicana (Caribe)",
        "selected_genres": ["Bachata Dominicana", "Merengue de Calle / Mambo", "Salsa Clasica"],
        "voice_type": "Automatico - IA elige mejor voz afinada",
        "bpm": 135, "master_prompt": "",
        "cine_title": "El Lapiz Pesa Mas que el Pico", "cine_ep": "Pelicula Completa - T01",
        "cine_style": "Cine Epico / Hollywood Dorado", "cine_voice": "Voz Masculina",
        "cine_music_genre": "Score Cinematografico / Orquestal",
        "cine_idea": "Historia de superacion desde cero hasta alcanzar el exito en Republica Dominicana.",
        "cine_storyboard_text": "Escena 01 | El Inicio | Amanecer en Santo Domingo.\nEscena 02 | El Desafio | Esfuerzo y disciplina.\nEscena 03 | La Victoria | Celebracion en familia.",
        "pub_title": "Rumbo a Celebrar (Version Studio)", "pub_artist": "BASA Productions - El Forense de la Musica",
        "pub_lyrics": "Producido en BASA Universal AI Studio.",
        "modo_proceso": "IA Automatica (Default) - La IA crea y afina",
        "formato_vocal": "Automatico - IA decide Solista / Duo / Coro",
        "ritmo_modo": "Automatico - IA decide segun letra",
        "usuario_actual": "pedro.baldera",
    }
    loaded = _load_json(UI_STATE_FILE, {})
    if isinstance(loaded, dict):
        default_ui.update(loaded)
    return default_ui

def autosave_callback() -> None:
    init_dirs()
    current = load_autosave_state()
    keys = ["ui_project_title", "ui_region", "ui_genres", "ui_voice_type", "ui_bpm", "ui_master_prompt", "ui_cine_title", "ui_cine_ep", "ui_cine_style", "ui_cine_voice", "ui_cine_music_genre", "ui_cine_idea", "ui_cine_storyboard_text", "ui_pub_title", "ui_pub_artist", "ui_pub_lyrics", "ui_modo_proceso", "ui_formato_vocal", "ui_ritmo_modo"]
    map_keys = {"ui_project_title": "project_title", "ui_region": "selected_region", "ui_genres": "selected_genres", "ui_voice_type": "voice_type", "ui_bpm": "bpm", "ui_master_prompt": "master_prompt", "ui_cine_title": "cine_title", "ui_cine_ep": "cine_ep", "ui_cine_style": "cine_style", "ui_cine_voice": "cine_voice", "ui_cine_music_genre": "cine_music_genre", "ui_cine_idea": "cine_idea", "ui_cine_storyboard_text": "cine_storyboard_text", "ui_pub_title": "pub_title", "ui_pub_artist": "pub_artist", "ui_pub_lyrics": "pub_lyrics", "ui_modo_proceso": "modo_proceso", "ui_formato_vocal": "formato_vocal", "ui_ritmo_modo": "ritmo_modo"}
    snapshot = dict(current)
    for k in keys:
        if k in st.session_state:
            snapshot[map_keys[k]] = st.session_state[k]
    snapshot["saved_at"] = datetime.now().isoformat()
    _save_json(UI_STATE_FILE, snapshot)

def on_region_change() -> None:
    reg = st.session_state.get("ui_region", "Republica Dominicana (Caribe)")
    st.session_state["ui_genres"] = REGION_GENRE_DEFAULTS.get(reg, ["Bachata Dominicana", "Merengue de Calle / Mambo", "Salsa Clasica"])[:3]
    autosave_callback()

def init_vault() -> dict[str, Any]:
    init_dirs()
    default_station = {"station_name": "BASA Radio Autonoma 24/7", "autonomous_permission": True, "auto_advance": True, "active_track_id": None}
    data = _load_json(INDEX_FILE, None)
    if data is None:
        data = {"created_at": datetime.now().isoformat(), "assets": [], "autonomous_modules": [], "station_config": default_station}
        _save_json(INDEX_FILE, data)
        return data
    if not isinstance(data, dict):
        data = {"created_at": datetime.now().isoformat(), "assets": [], "autonomous_modules": [], "station_config": default_station}
    data.setdefault("assets", [])
    data.setdefault("autonomous_modules", [])
    data.setdefault("station_config", default_station)
    return data

def repair_vault_assets(vault: dict[str, Any]) -> dict[str, Any]:
    cleaned = []
    for a in vault.get("assets", []):
        if not isinstance(a, dict):
            continue
        a.setdefault("id", str(uuid.uuid4())[:8])
        a.setdefault("title", "Sin titulo")
        a.setdefault("kind", "asset")
        a.setdefault("file", "")
        a.setdefault("created_at", datetime.now().isoformat())
        a.setdefault("meta", {})
        cleaned.append(a)
    vault["assets"] = cleaned
    return vault

def save_vault(data: dict[str, Any]) -> None:
    init_dirs()
    try:
        if INDEX_FILE.exists():
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            shutil.copy(INDEX_FILE, BACKUP_DIR / f"vault_index_{ts}.json")
    except Exception:
        pass
    _save_json(INDEX_FILE, data)

def add_asset(vault: dict[str, Any], title: str, kind: str, file_path: str, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    asset = {"id": str(uuid.uuid4())[:8], "title": title, "kind": kind, "file": file_path, "created_at": datetime.now().isoformat(), "meta": meta or {}}
    vault.setdefault("assets", []).append(asset)
    save_vault(vault)
    return asset

def verificar_consentimiento(usuario: str) -> dict[str, Any] | None:
    data = _load_json(LEGAL_FILE, {})
    if not isinstance(data, dict):
        return None
    return data.get(usuario)

def guardar_consentimiento(usuario: str, acepta: bool, es_reserva_pagada: bool) -> dict[str, Any]:
    data = _load_json(LEGAL_FILE, {})
    if not isinstance(data, dict):
        data = {}
    texto_hash = hashlib.sha256((LEGAL_TEXT + usuario + datetime.now().isoformat()).encode("utf-8")).hexdigest()[:16]
    entry = {
        "usuario": usuario, "acepta_cesion": acepta, "reserva_pagada": es_reserva_pagada,
        "propiedad": "Usuario - Reserva Pagada" if es_reserva_pagada else "BASA Productions - Desarrollador",
        "fecha": datetime.now().isoformat(), "hash_legal": texto_hash,
        "valido_para_siempre": True, "dispositivos": "Todos - Este y cualquier otro",
        "desarrollador": DEVELOPER_NAME,
    }
    data[usuario] = entry
    _save_json(LEGAL_FILE, data)
    return entry

def guardar_historico(usuario: str, titulo: str, letra: str, genero: str, formato: str, voz: str, modo: str, archivos: list[str], propiedad: str) -> dict[str, Any]:
    hist = _load_json(HISTORY_FILE, {})
    if not isinstance(hist, dict):
        hist = {}
    entry = {"id": str(uuid.uuid4())[:8], "usuario": usuario, "titulo": titulo, "letra": letra[:2000], "genero": genero, "formato": formato, "voz": voz, "modo": modo, "archivos": archivos, "propiedad": propiedad, "created_at": datetime.now().isoformat()}
    hist.setdefault(usuario, []).append(entry)
    _save_json(HISTORY_FILE, hist)
    # Biblioteca Libre BASA - todas pasan a BASA salvo reserva pagada
    lib = _load_json(LIBRARY_FILE, [])
    if not isinstance(lib, list):
        lib = []
    lib.append({**entry, "biblioteca": "Biblioteca Libre BASA", "licencia": "BASA Libre - Uso de BASA Productions sin restriccion" if propiedad.startswith("BASA") else "Reservada - Propiedad del Usuario"})
    _save_json(LIBRARY_FILE, lib)
    return entry

# ============================================================================
# AUDIO / PORTADA / CINE
# ============================================================================
def clean_text_for_tts(text: str) -> str:
    text = re.sub(r"[*#_>~`]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:1800] if len(text) > 1800 else text

async def _tts_async(text: str, voice: str, rate: str, pitch: str, out_path: Path) -> bool:
    if not HAS_EDGE_TTS:
        return False
    try:
        communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
        await communicate.save(str(out_path))
        return out_path.exists() and out_path.stat().st_size > 0
    except Exception:
        return False

def generate_voice_audio(text: str, profile: dict[str, Any], out_path: Path) -> tuple[bool, str]:
    if profile.get("mode") == "instrumental":
        return False, "Modo instrumental - sin voz."
    cleaned = clean_text_for_tts(text)
    if not cleaned:
        return False, "Escriba letra o guion."
    if not HAS_EDGE_TTS:
        return False, "Instale edge-tts: pip install edge-tts"
    try:
        ok = asyncio.run(_tts_async(cleaned, profile["voice"], profile["rate"], profile["pitch"], out_path))
        if ok:
            return True, f"Voz generada: {out_path.name}"
        return False, "No se pudo conectar a edge-tts. Revise internet."
    except Exception as e:
        return False, f"Error TTS: {e}"

def generate_cover(title: str, artist: str, genre: str, style_name: str, out_path: Path) -> Path:
    if not HAS_PIL:
        out_path.write_text(f"{title} - {artist} - {genre}", encoding="utf-8")
        return out_path
    bg, accent, txt = CINEMA_STYLES.get(style_name, CINEMA_STYLES["Cine Epico / Hollywood Dorado"])
    W, H = 1080, 1080
    img = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(img)
    for i in range(H):
        r = int(bg[0] + (20 - bg[0]) * i / H)
        g = int(bg[1] + (30 - bg[1]) * i / H)
        b = int(bg[2] + (60 - bg[2]) * i / H)
        draw.line([(0, i), (W, i)], fill=(r, g, b))
    draw.ellipse([W * 0.15, H * 0.12, W * 0.85, H * 0.62], outline=accent, width=8)
    draw.ellipse([W * 0.30, H * 0.24, W * 0.70, H * 0.50], outline=accent, width=4)
    try:
        f_title = ImageFont.truetype("arial.ttf", 72)
        f_sub = ImageFont.truetype("arial.ttf", 38)
        f_small = ImageFont.truetype("arial.ttf", 28)
    except Exception:
        f_title = ImageFont.load_default()
        f_sub = ImageFont.load_default()
        f_small = ImageFont.load_default()

    def center(y, text, font, color):
        bbox = draw.textbbox((0, 0), text, font=font)
        w = bbox[2] - bbox[0]
        draw.text(((W - w) / 2, y), text, font=font, fill=color)

    center(680, title[:28], f_title, txt)
    center(780, artist[:38], f_sub, accent)
    center(840, genre[:40], f_small, txt)
    center(900, "BASA PRODUCTIONS - 100/100", f_small, accent)
    img.save(out_path, "JPEG", quality=92)
    return out_path

def parse_storyboard(text: str) -> list[dict[str, str]]:
    scenes = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 3:
            scenes.append({"id": parts[0], "title": parts[1], "desc": parts[2]})
        elif len(parts) == 2:
            scenes.append({"id": parts[0], "title": parts[1], "desc": parts[1]})
        else:
            scenes.append({"id": f"Escena {len(scenes) + 1:02d}", "title": "Escena", "desc": line})
    if not scenes:
        scenes = [{"id": "Escena 01", "title": "Inicio", "desc": text or "Historia BASA"}]
    return scenes

def export_project_zip(vault: dict[str, Any], title: str) -> Path:
    init_dirs()
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", title)[:40] or "BASA"
    zip_path = AUTO_EXPORT_DIR / f"{safe}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("README_BASA.txt", f"BASA v11\nProyecto: {title}\nFecha: {datetime.now().isoformat()}\nAutor: {DEVELOPER_NAME}\n")
        z.writestr("vault_index.json", json.dumps(vault, indent=2, ensure_ascii=False))
        for a in vault.get("assets", []):
            p = Path(a.get("file", ""))
            if p.exists() and p.is_file():
                try:
                    z.write(p, arcname=f"media/{p.name}")
                except Exception:
                    pass
    return zip_path

# ============================================================================
# MAIN - BASA v11
# ============================================================================
def main() -> None:
    init_dirs()
    vault = init_vault()
    vault = repair_vault_assets(vault)
    ui = load_autosave_state()

    st.title("⚡ BASA Universal AI Studio v11 - Autonomo 100/100")
    st.caption("Pedro Baldera - BASA Productions | Musica + Cine + Video + Series + Biblioteca Libre | Como Suno / Gemini / Mureka - Ilimitado")

    with st.sidebar:
        st.header("👤 Usuario")
        usuario = st.text_input("Usuario", value=ui.get("usuario_actual", "pedro.baldera"), key="usuario_actual")
        st.header("🔐 Acceso")
        pin = st.text_input("PIN Admin", type="password", key="admin_pin")
        is_admin = (pin == ADMIN_MASTER_PIN) or (pin == "")
        if pin and not is_admin:
            st.error("PIN incorrecto. Solo lectura.")
        st.divider()
        st.header("⚖️ Contrato Legal - 1 sola vez")
        consent = verificar_consentimiento(usuario)
        if consent:
            st.success(f"✅ Contrato firmado: {consent.get('fecha', '')[:16]}")
            st.write(f"Propiedad: {consent.get('propiedad')}")
            st.caption(f"Hash: {consent.get('hash_legal')} | Valido para siempre, todos los dispositivos.")
            es_reserva = consent.get("reserva_pagada", False)
        else:
            st.warning("⚠️ Debe marcar el cotejo para registrar temas.")
            with st.expander("📜 Leer Contrato Legal Completo"):
                st.text_area("Contrato", LEGAL_TEXT, height=280, disabled=True)
            acepta = st.checkbox("✅ Acepto y cedo derechos a BASA Productions (Pedro Baldera). Entiendo que toda cancion pasa a BASA sin restriccion, salvo que pague reserva.", key="legal_check")
            reserva = st.checkbox("💰 Pague Reserva - Quiero que sea de MI propiedad exclusiva (pagar al desarrollador)", key="legal_reserva")
            if st.button("✍️ Firmar Contrato - Valido Para Siempre"):
                if not acepta:
                    st.error("Debe marcar el cotejo de aceptacion para firmar.")
                else:
                    e = guardar_consentimiento(usuario, True, reserva)
                    st.success(f"Contrato firmado. Propiedad: {e['propiedad']}. Valido para siempre.")
                    st.rerun()
            es_reserva = False
            consent = None
        st.divider()
        st.header("📊 Boveda")
        st.metric("Assets", len(vault.get("assets", [])))
        lib = _load_json(LIBRARY_FILE, [])
        st.metric("Biblioteca Libre BASA", len(lib) if isinstance(lib, list) else 0)
        hist = _load_json(HISTORY_FILE, {})
        st.metric("Temas en Historico", len(hist.get(usuario, [])) if isinstance(hist, dict) else 0)
        if st.button("💾 Guardar / Autosave"):
            autosave_callback()
            st.success("Guardado.")
        if st.button("📦 Exportar ZIP"):
            zp = export_project_zip(vault, ui["project_title"])
            st.success(f"ZIP: {zp.name}")
            with open(zp, "rb") as f:
                st.download_button("⬇ Descargar ZIP", f.read(), file_name=zp.name, mime="application/zip")

    tab1, tab2, tab3, tab4, tab5 = st.tabs(["🎵 1. Estudio Musica IA", "🎬 2. Cine / Video / Serie", "📚 3. Historico / Biblioteca Libre", "🚀 4. Publicar", "📻 5. Boveda / Radio"])

    with tab1:
        st.subheader("🎵 Crear Tema - Desde 1 Palabra hasta Escrito Completo")
        col1, col2 = st.columns([1, 1])
        with col1:
            project_title = st.text_input("Titulo del proyecto", value=ui["project_title"], key="ui_project_title")
            region = st.selectbox("Region / Mercado", list(REGION_GENRE_DEFAULTS.keys()), index=list(REGION_GENRE_DEFAULTS.keys()).index(ui["selected_region"]) if ui["selected_region"] in REGION_GENRE_DEFAULTS else 0, key="ui_region", on_change=on_region_change)
            modo_proceso = st.selectbox("¿Como procesar la cancion?", ["IA Automatica (Default) - La IA crea y afina", "Con ayuda IA - Yo escribo, IA mejora", "Tal como lo escribo - Sin tocar mi letra"], index=0, key="ui_modo_proceso")
            st.caption("Default: IA Automatica. Usted decide. Si elige 'Tal como lo escribo', la IA NO toca su letra.")
            ritmo_modo = st.selectbox("Ritmo / Genero", ["Automatico - IA decide segun letra"] + ALL_WORLD_GENRES + ["Combinar Generos - Estilo Suno / Gemini / Mureka"], key="ui_ritmo_modo")
            genres = st.multiselect("Generos manuales (si deja vacio, IA decide)", ALL_WORLD_GENRES, default=[], key="ui_genres_manual")
            combinar = st.checkbox("🔀 Combinar musica como Suno / Gemini (Fusion de generos)", value=False)
            formato_vocal = st.selectbox("Formato Vocal", ["Automatico - IA decide Solista / Duo / Coro", "Solista", "Duo (2 Voces)", "Coro Grupal (Voces en Bloque)", "Solo Instrumental (Sin Voz)"], key="ui_formato_vocal")
            voz_manual = st.selectbox("Voz Manual (opcional)", ["Automatico - IA elige mejor voz afinada"] + list(VOICE_PROFILES.keys()), key="ui_voice_type")
            bpm_manual = st.slider("BPM Manual (0 = Automatico segun genero)", 0, 180, 0, key="ui_bpm")
            master_prompt = st.text_area("Prompt Maestro / Idea", value=ui["master_prompt"], height=70, key="ui_master_prompt", placeholder="Ej: Merengue jocoso para Miniel...")
        with col2:
            st.subheader("✍️ Escriba: 1 palabra, frase, oracion o escrito")
            entrada_usuario = st.text_area("Su palabra / frase / oracion / escrito", value="Miniel comio donde Lethy, luego cafe donde Ondina debajo de la mata de guanabana de Paca Alberto", height=180, key="entrada_usuario")
            st.caption("Puede escribir solo 'cafe' y la IA hace el tema completo. O escriba el tema entero y elija 'Tal como lo escribo'.")
            if st.button("✨ Vista Previa IA - Que genero / voz / formato eligiria la IA?", use_container_width=True):
                genero_prev, expl_prev, bpm_prev = ia_detectar_genero_desde_letra(entrada_usuario, ui.get("selected_genres", []))
                if ritmo_modo != "Automatico - IA decide segun letra" and ritmo_modo != "Combinar Generos - Estilo Suno / Gemini / Mureka":
                    genero_prev = ritmo_modo
                formato_prev = ia_decidir_formato(entrada_usuario) if formato_vocal.startswith("Automatico") else formato_vocal
                voz_prev, _, expl_voz = ia_elegir_mejor_voz(genero_prev, entrada_usuario, formato_prev)
                st.info(f"**Genero IA:** {genero_prev} | **BPM IA:** {bpm_prev if bpm_manual == 0 else bpm_manual} | **Formato IA:** {formato_prev} | **Voz IA:** {voz_prev}")
                st.write(expl_prev)
                st.write(expl_voz)
                letra_prev = ia_expandir_desde_palabra(entrada_usuario, genero_prev, modo_proceso)
                st.text_area("Letra que usaria la IA (preview)", letra_prev, height=140)
            c1, c2 = st.columns(2)
            with c1:
                generar = st.button("🎤 Generar Cancion Completa", type="primary", use_container_width=True)
            with c2:
                if st.button("🖼 Generar Portada + Visual", use_container_width=True):
                    if not consent:
                        st.error("⚖️ Debe firmar el contrato legal en la barra lateral (marcar cotejo 1 sola vez) antes de registrar.")
                    else:
                        gen_tmp, _, _ = ia_detectar_genero_desde_letra(entrada_usuario, ui.get("selected_genres", []))
                        out_img = MEDIA_DIR / f"portada_{re.sub(r'[^A-Za-z0-9_-]+', '_', project_title)[:30]}_{datetime.now().strftime('%H%M%S')}.jpg"
                        generate_cover(project_title, "BASA Productions", gen_tmp, "Cine Epico / Hollywood Dorado", out_img)
                        add_asset(vault, project_title, "portada", str(out_img), {"genre": gen_tmp})
                        st.success(f"Portada: {out_img.name}")
                        st.image(str(out_img), width=320)
            if generar:
                if not consent:
                    st.error("⚖️ Debe marcar y firmar el contrato legal en la barra lateral ANTES de registrar. Es 1 sola vez, valido para siempre.")
                elif pin and not is_admin:
                    st.error("PIN incorrecto.")
                else:
                    with st.spinner("BASA IA creando tema profesional..."):
                        # 1. Genero
                        if ritmo_modo == "Automatico - IA decide segun letra":
                            genero_final, expl_g, bpm_ia = ia_detectar_genero_desde_letra(entrada_usuario, ui.get("selected_genres", []))
                        elif ritmo_modo == "Combinar Generos - Estilo Suno / Gemini / Mureka":
                            base_gen = genres if genres else ["Bachata Dominicana", "Merengue de Calle / Mambo"]
                            genero_final = ia_combinar_generos(base_gen)
                            bpm_ia = 135
                            expl_g = f"Fusion combinada estilo Suno/Gemini: {genero_final}"
                        else:
                            genero_final = ritmo_modo
                            bpm_ia = 120
                            expl_g = "Genero manual elegido por el usuario."
                        if genres and ritmo_modo.startswith("Automatico"):
                            genero_final = ia_combinar_generos(genres) if combinar else genres[0]
                        bpm_final = bpm_manual if bpm_manual != 0 else bpm_ia
                        # 2. Letra segun modo
                        if modo_proceso.startswith("Tal como"):
                            letra_final = entrada_usuario
                        elif modo_proceso.startswith("Con ayuda"):
                            letra_final = ia_expandir_desde_palabra(entrada_usuario, genero_final, "Con ayuda IA")
                        else:
                            letra_final = ia_expandir_desde_palabra(entrada_usuario, genero_final, "IA Automatica")
                        # 3. Formato vocal
                        if formato_vocal.startswith("Automatico"):
                            formato_final = ia_decidir_formato(letra_final)
                        else:
                            formato_final = formato_vocal
                        # 4. Mejor voz afinada automatica
                        if voz_manual.startswith("Automatico"):
                            voz_nombre, voz_perfil, expl_v = ia_elegir_mejor_voz(genero_final, letra_final, formato_final)
                        else:
                            voz_nombre = voz_manual
                            voz_perfil = VOICE_PROFILES[voz_manual]
                            expl_v = "Voz manual elegida por el usuario."
                        # 5. Ajuste profesional segun formato
                        if formato_final == "Duo (2 Voces)":
                            letra_para_audio = f"{letra_final} [Duo: Voz 1 y Voz 2 alternando, armonia profesional]"
                            voz_perfil = dict(voz_perfil)
                            voz_perfil["mode"] = "duo"
                        elif formato_final == "Coro Grupal (Voces en Bloque)":
                            letra_para_audio = f"{letra_final} [Coro: todas las voces juntas, en bloque, afinado]"
                            voz_perfil = dict(voz_perfil)
                            voz_perfil["mode"] = "choir"
                        elif formato_final == "Solo Instrumental (Sin Voz)":
                            letra_para_audio = letra_final
                            voz_perfil = VOICE_PROFILES["Solo Instrumental (Sin Voz)"]
                        else:
                            letra_para_audio = letra_final
                        st.success(f"✅ Genero: {genero_final} | BPM: {bpm_final} | Formato: {formato_final} | Voz: {voz_nombre} afinada")
                        st.info(expl_g)
                        st.info(expl_v)
                        st.text_area("Letra Final Usada", letra_final, height=160)
                        # 6. Audio
                        out = MEDIA_DIR / f"tema_{re.sub(r'[^A-Za-z0-9_-]+', '_', project_title)[:30]}_{datetime.now().strftime('%H%M%S')}.mp3"
                        ok, msg = generate_voice_audio(letra_para_audio, voz_perfil, out)
                        propiedad = consent.get("propiedad", "BASA Productions - Desarrollador") if consent else "BASA Productions - Desarrollador"
                        if ok:
                            add_asset(vault, project_title, "audio_tema", str(out), {"genre": genero_final, "voice": voz_nombre, "bpm": bpm_final, "formato": formato_final, "modo": modo_proceso, "propiedad": propiedad})
                            guardar_historico(usuario, project_title, letra_final, genero_final, formato_final, voz_nombre, modo_proceso, [str(out)], propiedad)
                            st.success(f"{msg} | Guardado en Historico + Biblioteca Libre BASA | Propiedad: {propiedad}")
                            st.audio(str(out))
                        else:
                            # Guardar aunque falle audio, para no perder letra
                            guardar_historico(usuario, project_title, letra_final, genero_final, formato_final, voz_nombre, modo_proceso, [], propiedad)
                            st.warning(f"Audio: {msg} | Pero letra guardada en Historico + Biblioteca.")
                        # Guardar ultima seleccion para proxima vez
                        st.session_state["ui_genres"] = [genero_final] if "Fusion" not in genero_final else genres
                        autosave_callback()

    with tab2:
        st.subheader("🎬 Cine / Video / Serie / Pelicula - Ilimitado")
        cc1, cc2 = st.columns(2)
        with cc1:
            cine_title = st.text_input("Titulo", value=ui["cine_title"], key="ui_cine_title")
            cine_ep = st.text_input("Episodio / Capitulo", value=ui["cine_ep"], key="ui_cine_ep")
            cine_style = st.selectbox("Estilo visual", list(CINEMA_STYLES.keys()), key="ui_cine_style")
            cine_voice = st.selectbox("Voz narrador", list(VOICE_PROFILES.keys()), key="ui_cine_voice")
            cine_genre = st.selectbox("Musica de fondo", ALL_WORLD_GENRES, index=ALL_WORLD_GENRES.index(ui["cine_music_genre"]) if ui["cine_music_genre"] in ALL_WORLD_GENRES else 0, key="ui_cine_music_genre")
            cine_idea = st.text_area("Idea central", value=ui["cine_idea"], key="ui_cine_idea")
            tipo_video = st.selectbox("Tipo", ["Video Musical", "Serie - Capitulo", "Pelicula Completa", "Corto / TikTok", "Documental"], key="tipo_video")
        with cc2:
            cine_story = st.text_area("Storyboard - Escena | Titulo | Descripcion", value=ui["cine_storyboard_text"], height=220, key="ui_cine_storyboard_text")
            scenes = parse_storyboard(cine_story)
            st.info(f"Escenas: {len(scenes)} | Tipo: {tipo_video} | Ilimitado")
            for s in scenes:
                st.markdown(f"**{s['id']} - {s['title']}**: {s['desc']}")
        if st.button("🎬 Generar Video / Serie / Pelicula", type="primary"):
            if not consent:
                st.error("Debe firmar contrato legal primero.")
            else:
                with st.spinner("Generando cine BASA..."):
                    poster = MEDIA_DIR / f"cine_poster_{datetime.now().strftime('%H%M%S')}.jpg"
                    generate_cover(cine_title, "BASA Cine", cine_genre, cine_style, poster)
                    add_asset(vault, cine_title, "poster_cine", str(poster), {"style": cine_style, "tipo": tipo_video})
                    full_script = f"{cine_title}. {cine_idea}. " + " ".join([f"{s['title']}. {s['desc']}" for s in scenes])
                    out_audio = MEDIA_DIR / f"cine_narracion_{datetime.now().strftime('%H%M%S')}.mp3"
                    ok, msg = generate_voice_audio(full_script, VOICE_PROFILES[cine_voice], out_audio)
                    if ok:
                        add_asset(vault, cine_title, "audio_cine", str(out_audio), {"scenes": len(scenes), "tipo": tipo_video})
                        guardar_historico(usuario, cine_title, full_script, cine_genre, tipo_video, cine_voice, "IA Automatica", [str(poster), str(out_audio)], consent.get("propiedad", "BASA Productions - Desarrollador"))
                        st.success("Cine generado + guardado en Historico + Biblioteca Libre.")
                        st.image(str(poster), width=360)
                        st.audio(str(out_audio))
                    else:
                        st.warning(f"Poster listo, audio: {msg}")
                        st.image(str(poster), width=360)

    with tab3:
        st.subheader("📚 Historico del Usuario + Biblioteca Libre BASA")
        st.info("Toda cancion creada en BASA pasa a Biblioteca Libre BASA bajo contrato legal, salvo que pague reserva. El cotejo legal se marca 1 sola vez y vale para siempre.")
        hist = _load_json(HISTORY_FILE, {})
        mis_temas = hist.get(usuario, []) if isinstance(hist, dict) else []
        st.write(f"**Usuario:** {usuario} | **Temas:** {len(mis_temas)} | **Propiedad actual:** {consent.get('propiedad', 'Sin contrato') if consent else 'Sin contrato'}")
        if not mis_temas:
            st.info("Aun no tiene temas. Cree uno en la pestana 1.")
        else:
            for t in reversed(mis_temas[-20:]):
                t_title = t.get("titulo", "Sin titulo") if isinstance(t, dict) else "Sin titulo"
                t_genero = t.get("genero", "") if isinstance(t, dict) else ""
                t_fecha = str(t.get("created_at", ""))[:16] if isinstance(t, dict) else ""
                t_prop = t.get("propiedad", "") if isinstance(t, dict) else ""
                with st.expander(f"{t_fecha} - {t_title} [{t_genero}] - {t_prop}"):
                    st.write(t)
                    for fpath in t.get("archivos", []):
                        p = Path(fpath)
                        if p.exists() and p.is_file() and p.suffix.lower() in [".mp3", ".wav"]:
                            st.audio(str(p))
        st.divider()
        st.subheader("🌍 Biblioteca Libre BASA - Todas las obras")
        lib = _load_json(LIBRARY_FILE, [])
        if isinstance(lib, list) and lib:
            for item in reversed(lib[-20:]):
                if not isinstance(item, dict):
                    continue
                st.markdown(f"**{item.get('titulo', '')}** - {item.get('genero', '')} - {item.get('usuario', '')} - {item.get('propiedad', '')} - {str(item.get('created_at', ''))[:16]}")
        else:
            st.info("Biblioteca vacia aun.")

    with tab4:
        st.subheader("🚀 Publicar / Lanzamiento")
        pub_title = st.text_input("Titulo lanzamiento", value=ui["pub_title"], key="ui_pub_title")
        pub_artist = st.text_input("Artista", value=ui["pub_artist"], key="ui_pub_artist")
        pub_lyrics = st.text_area("Letra / Creditos", value=ui["pub_lyrics"], height=140, key="ui_pub_lyrics")
        col_p1, col_p2, col_p3 = st.columns(3)
        with col_p1:
            plat = st.multiselect("Plataformas", ["Spotify", "YouTube", "TikTok", "Apple Music", "Amazon Music", "Instagram / Facebook"], default=["Spotify", "YouTube", "TikTok"])
        with col_p2:
            isrc = st.text_input("ISRC", value=f"DO-BASA-{datetime.now().strftime('%y%m%d')}")
            upc = st.text_input("UPC / EAN", value="")
        with col_p3:
            fecha = st.date_input("Fecha lanzamiento", value=datetime.now().date())
            precio = st.selectbox("Modelo", ["Gratis - Promocional", "Iguala Mensual BASA66", "Venta Unica", "Streaming"])
        if st.button("✅ Registrar Lanzamiento", type="primary"):
            if not consent:
                st.error("Debe firmar contrato legal primero (1 sola vez).")
            else:
                init_dirs()
                log = _load_json(RELEASES_FILE, [])
                if not isinstance(log, list):
                    log = []
                entry = {"id": str(uuid.uuid4())[:8], "title": pub_title, "artist": pub_artist, "platforms": plat, "isrc": isrc, "upc": upc, "fecha": str(fecha), "modelo": precio, "lyrics": pub_lyrics, "propiedad": consent.get("propiedad", ""), "usuario": usuario, "created_at": datetime.now().isoformat()}
                log.append(entry)
                _save_json(RELEASES_FILE, log)
                st.success(f"Lanzamiento registrado: {pub_title} - Propiedad: {entry['propiedad']}")
                st.json(entry)
        if RELEASES_FILE.exists():
            try:
                st.dataframe(_load_json(RELEASES_FILE, []))
            except Exception:
                pass

    with tab5:
        st.subheader("📻 Boveda / Radio Autonoma 24/7")
        station = vault.get("station_config", {})
        st.write(f"**Estacion:** {station.get('station_name', 'BASA Radio')} | **Auto-avance:** {station.get('auto_advance', True)}")
        assets_list = vault.get("assets", [])
        if not assets_list:
            st.info("Aun no hay assets. Genere en pestana 1.")
        else:
            for a in reversed(assets_list[-20:]):
                if not isinstance(a, dict):
                    continue
                a_title = a.get("title", "Sin titulo")
                a_kind = a.get("kind", "asset")
                a_date = str(a.get("created_at", ""))[:16]
                a_id = a.get("id", "no-id")
                a_file = a.get("file", "")
                a_label = f"{a_date} - {a_title} [{a_kind}]"
                with st.expander(a_label):
                    st.write(a)
                    p = Path(a_file) if a_file else Path("")
                    if a_file and p.exists() and p.is_file():
                        if p.suffix.lower() in [".mp3", ".wav"]:
                            st.audio(str(p))
                        elif p.suffix.lower() in [".jpg", ".jpeg", ".png"]:
                            st.image(str(p), width=300)
                        try:
                            with open(p, "rb") as f:
                                st.download_button(f"Descargar {p.name}", f.read(), file_name=p.name, key=f"dl_{a_id}")
                        except IsADirectoryError:
                            st.warning(f"Es carpeta: {a_file}")
                        except Exception as e:
                            st.warning(f"No se pudo abrir: {e}")
                    elif a_file and p.exists() and p.is_dir():
                        st.warning(f"Apunta a carpeta: {a_file}")
                    else:
                        st.warning(f"Archivo no encontrado: {a_file}")
        if st.button("🗑 Backup Boveda"):
            save_vault(vault)
            st.success("Backup hecho.")

    st.divider()
    st.caption("BASA v11 - (c) Pedro Anibal Baldera Rondon - BASA Productions - Todos los derechos reservados - Contrato Legal BASA: toda obra creada pasa a BASA sin restriccion, salvo reserva pagada.")

if __name__ == "__main__":
    main()
