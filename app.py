import ast
import asyncio
import base64
import hashlib
import io
import json
import math
import os
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request
import uuid
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import streamlit as st

# Dependencias opcionales - si faltan, la app sigue corriendo
try:
    import edge_tts
    HAS_EDGE_TTS = True
except Exception:
    HAS_EDGE_TTS = False
try:
    import numpy as np
    HAS_NUMPY = True
except Exception:
    HAS_NUMPY = False
try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except Exception:
    HAS_PIL = False
try:
    from pydub import AudioSegment
    HAS_PYDUB = True
except Exception:
    HAS_PYDUB = False

# ==============================================================================
# CONFIGURACION DE PAGINA
# ==============================================================================
st.set_page_config(
    page_title="BASA Universal AI Studio - Autonomo 100/100",
    page_icon="⚡",
    layout="wide",
)

VAULT_DIR = Path("basa_vault_data")
MEDIA_DIR = VAULT_DIR / "media"
BACKUP_DIR = VAULT_DIR / "backups"
AUTO_EXPORT_DIR = VAULT_DIR / "auto_exports"
INDEX_FILE = VAULT_DIR / "vault_index.json"
ACCOUNTS_FILE = VAULT_DIR / "users_vault.json"
RELEASES_FILE = VAULT_DIR / "releases_log.json"
UI_STATE_FILE = VAULT_DIR / "ui_autosave_state.json"

ADMIN_MASTER_PIN = "BASA-ADMIN-2026"

# ==============================================================================
# CATALOGO
# ==============================================================================
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
]

VOICE_PROFILES: dict[str, dict[str, Any]] = {
    "Voz Masculina": {"voice": "es-DO-EmilioNeural", "rate": "+0%", "pitch": "+0Hz", "mode": "solo"},
    "Voz Femenina": {"voice": "es-DO-RamonaNeural", "rate": "+0%", "pitch": "+0Hz", "mode": "solo"},
    "Voz Juvenil Masculina": {"voice": "es-MX-JorgeNeural", "rate": "+8%", "pitch": "+18Hz", "mode": "solo"},
    "Voz Juvenil Femenina": {"voice": "es-MX-DaliaNeural", "rate": "+8%", "pitch": "+22Hz", "mode": "solo"},
    "Voz Infantil (Nino/Nina)": {"voice": "es-MX-DaliaNeural", "rate": "+5%", "pitch": "+55Hz", "mode": "solo"},
    "Coro Grupal (Voces en Bloque)": {"voice": "es-DO-RamonaNeural", "rate": "+2%", "pitch": "+0Hz", "mode": "choir"},
    "Solo Instrumental (Sin Voz)": {"voice": "", "rate": "+0%", "pitch": "+0Hz", "mode": "instrumental"},
}

CINEMA_STYLES: dict[str, tuple[tuple[int, int, int], tuple[int, int, int], tuple[int, int, int]]] = {
    "Cine Epico / Hollywood Dorado": ((14, 18, 34), (245, 208, 97), (225, 232, 245)),
    "Accion / Cyberpunk Neon": ((10, 12, 24), (0, 240, 255), (235, 245, 255)),
    "Animacion 3D / Familiar": ((22, 34, 68), (255, 185, 65), (255, 255, 255)),
    "Documental / Historia Real": ((24, 22, 20), (218, 175, 110), (238, 234, 228)),
    "Drama / Suspenso Nocturno": ((8, 10, 14), (220, 65, 65), (215, 220, 225)),
}

# ==============================================================================
# UTILIDADES BOVEDA
# ==============================================================================
def init_dirs() -> None:
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    AUTO_EXPORT_DIR.mkdir(parents=True, exist_ok=True)

def load_autosave_state() -> dict[str, Any]:
    init_dirs()
    default_ui = {
        "project_title": "Rumbo a Celebrar (Navidad)",
        "selected_region": "Republica Dominicana (Caribe)",
        "selected_genres": ["Bachata Dominicana", "Merengue de Calle / Mambo", "Salsa Clasica"],
        "voice_type": "Voz Masculina",
        "bpm": 135,
        "master_prompt": "",
        "cine_title": "El Lapiz Pesa Mas que el Pico",
        "cine_ep": "Pelicula Completa - T01",
        "cine_style": "Cine Epico / Hollywood Dorado",
        "cine_voice": "Voz Masculina",
        "cine_music_genre": "Score Cinematografico / Orquestal",
        "cine_idea": "Historia de superacion desde cero hasta alcanzar el exito en Republica Dominicana.",
        "cine_storyboard_text": "Escena 01 | El Inicio | Amanecer en Santo Domingo, plano general de la ciudad despertando con esperanza.\nEscena 02 | El Desafio | Con esfuerzo diario, disciplina y vision, cada paso construye un nuevo horizonte.\nEscena 03 | La Victoria | Celebracion en familia con musica, luz y orgullo para toda Quisqueya.",
        "pub_title": "Rumbo a Celebrar (Version Studio)",
        "pub_artist": "BASA Productions - El Forense de la Musica",
        "pub_lyrics": "Producido en BASA Universal AI Studio. Arreglos y produccion original.",
    }
    if UI_STATE_FILE.exists():
        try:
            loaded = json.loads(UI_STATE_FILE.read_text(encoding="utf-8"))
            default_ui.update(loaded)
        except Exception:
            pass
    return default_ui

def autosave_callback() -> None:
    init_dirs()
    current = load_autosave_state()
    snapshot = {
        "project_title": st.session_state.get("ui_project_title", current["project_title"]),
        "selected_region": st.session_state.get("ui_region", current["selected_region"]),
        "selected_genres": st.session_state.get("ui_genres", current["selected_genres"]),
        "voice_type": st.session_state.get("ui_voice_type", current["voice_type"]),
        "bpm": st.session_state.get("ui_bpm", current["bpm"]),
        "master_prompt": st.session_state.get("ui_master_prompt", current["master_prompt"]),
        "cine_title": st.session_state.get("ui_cine_title", current["cine_title"]),
        "cine_ep": st.session_state.get("ui_cine_ep", current["cine_ep"]),
        "cine_style": st.session_state.get("ui_cine_style", current["cine_style"]),
        "cine_voice": st.session_state.get("ui_cine_voice", current["cine_voice"]),
        "cine_music_genre": st.session_state.get("ui_cine_music_genre", current["cine_music_genre"]),
        "cine_idea": st.session_state.get("ui_cine_idea", current["cine_idea"]),
        "cine_storyboard_text": st.session_state.get("ui_cine_storyboard_text", current["cine_storyboard_text"]),
        "pub_title": st.session_state.get("ui_pub_title", current["pub_title"]),
        "pub_artist": st.session_state.get("ui_pub_artist", current["pub_artist"]),
        "pub_lyrics": st.session_state.get("ui_pub_lyrics", current["pub_lyrics"]),
        "saved_at": datetime.now().isoformat(),
    }
    UI_STATE_FILE.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")

def on_region_change() -> None:
    reg = st.session_state.get("ui_region", "Republica Dominicana (Caribe)")
    st.session_state["ui_genres"] = REGION_GENRE_DEFAULTS.get(reg, ["Bachata Dominicana", "Merengue de Calle / Mambo", "Salsa Clasica"])[:3]
    autosave_callback()

def init_vault() -> dict[str, Any]:
    init_dirs()
    default_station = {"station_name": "BASA Radio Autonoma 24/7", "autonomous_permission": True, "auto_advance": True, "active_track_id": None}
    if not INDEX_FILE.exists():
        default_data = {"created_at": datetime.now().isoformat(), "assets": [], "autonomous_modules": [], "station_config": default_station}
        INDEX_FILE.write_text(json.dumps(default_data, indent=2, ensure_ascii=False), encoding="utf-8")
        return default_data
    try:
        data = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
        data.setdefault("assets", [])
        data.setdefault("autonomous_modules", [])
        data.setdefault("station_config", default_station)
        return data
    except Exception:
        backups = sorted(BACKUP_DIR.glob("vault_index_*.json"), reverse=True)
        for bkp in backups:
            try:
                restored = json.loads(bkp.read_text(encoding="utf-8"))
                INDEX_FILE.write_text(json.dumps(restored, indent=2, ensure_ascii=False), encoding="utf-8")
                return restored
            except Exception:
                continue
        return {"created_at": datetime.now().isoformat(), "assets": [], "autonomous_modules": [], "station_config": default_station}

def load_users_vault() -> dict[str, Any]:
    init_dirs()
    if not ACCOUNTS_FILE.exists():
        base = {"delegates": ["pedro.baldera"], "users": {}, "admin_pin": ADMIN_MASTER_PIN, "created_at": datetime.now().isoformat()}
        ACCOUNTS_FILE.write_text(json.dumps(base, indent=2, ensure_ascii=False), encoding="utf-8")
        return base
    try:
        data = json.loads(ACCOUNTS_FILE.read_text(encoding="utf-8"))
        data.setdefault("delegates", ["pedro.baldera"])
        data.setdefault("users", {})
        return data
    except Exception:
        return {"delegates": ["pedro.baldera"], "users": {}, "admin_pin": ADMIN_MASTER_PIN, "created_at": datetime.now().isoformat()}

def save_vault(data: dict[str, Any]) -> None:
    init_dirs()
    try:
        if INDEX_FILE.exists():
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            shutil.copy(INDEX_FILE, BACKUP_DIR / f"vault_index_{ts}.json")
    except Exception:
        pass
    INDEX_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

def add_asset(vault: dict[str, Any], title: str, kind: str, file_path: str, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    asset = {"id": str(uuid.uuid4())[:8], "title": title, "kind": kind, "file": file_path, "created_at": datetime.now().isoformat(), "meta": meta or {}}
    vault.setdefault("assets", []).append(asset)
    save_vault(vault)
    return asset

# ==============================================================================
# GENERADORES - AUDIO / PORTADA / CINE
# ==============================================================================
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
        return False, "Escriba letra o guion para generar voz."
    if not HAS_EDGE_TTS:
        return False, "Instale edge-tts: pip install edge-tts"
    try:
        ok = asyncio.run(_tts_async(cleaned, profile["voice"], profile["rate"], profile["pitch"], out_path))
        if ok:
            return True, f"Voz generada: {out_path.name}"
        return False, "No se pudo conectar a edge-tts. Revise su internet."
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
    draw.ellipse([W*0.15, H*0.12, W*0.85, H*0.62], outline=accent, width=8)
    draw.ellipse([W*0.30, H*0.24, W*0.70, H*0.50], outline=accent, width=4)
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
            scenes.append({"id": f"Escena {len(scenes)+1:02d}", "title": "Escena", "desc": line})
    return scenes or [{"id": "Escena 01", "title": "Inicio", "desc": text or "Historia BASA"}]

def export_project_zip(vault: dict[str, Any], title: str) -> Path:
    init_dirs()
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", title)[:40] or "BASA"
    zip_path = AUTO_EXPORT_DIR / f"{safe}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("README_BASA.txt", f"BASA Universal AI Studio\nProyecto: {title}\nFecha: {datetime.now().isoformat()}\nAutor: BASA Productions - Pedro Baldera\n")
        z.writestr("vault_index.json", json.dumps(vault, indent=2, ensure_ascii=False))
        for a in vault.get("assets", []):
            p = Path(a.get("file", ""))
            if p.exists() and p.is_file():
                try:
                    z.write(p, arcname=f"media/{p.name}")
                except Exception:
                    pass
    return zip_path

# ==============================================================================
# INTERFAZ PRINCIPAL - 100/100
# ==============================================================================
def main() -> None:
    init_dirs()
    vault = init_vault()
    vault = repair_vault_assets(vault)
    users = load_users_vault()
def repair_vault_assets(vault: dict[str, Any]) -> dict[str, Any]:
    """Limpia assets viejos sin title/kind/created_at para que no den KeyError."""
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

    ui = load_autosave_state()

    st.title("⚡ BASA Universal AI Studio - Autonomo 100/100")
    st.caption("Pedro Baldera - BASA Productions | Musica + Cine + Radio + Publicacion | Santo Domingo - Pensilvania")

    # PIN ADMIN
    with st.sidebar:
        st.header("🔐 Acceso")
        pin = st.text_input("PIN Admin", type="password", key="admin_pin")
        is_admin = (pin == ADMIN_MASTER_PIN) or (pin == "")
        if pin and not is_admin:
            st.error("PIN incorrecto. Solo lectura.")
        st.divider()
        st.header("📊 Boveda")
        st.metric("Assets guardados", len(vault.get("assets", [])))
        st.metric("Modulos autonomos", len(vault.get("autonomous_modules", [])))
        if st.button("💾 Guardar / Autosave", on_click=autosave_callback):
            st.success("Guardado en basa_vault_data/")
        if st.button("📦 Exportar ZIP Completo"):
            zp = export_project_zip(vault, ui["project_title"])
            st.success(f"ZIP creado: {zp.name}")
            with open(zp, "rb") as f:
                st.download_button("⬇ Descargar ZIP", f.read(), file_name=zp.name, mime="application/zip")
        st.divider()
        st.info("Carpeta de datos: basa_vault_data/ - No se borra al cerrar.")

    tab1, tab2, tab3, tab4 = st.tabs(["🎵 1. Estudio Musica", "🎬 2. Cine / Storyboard", "🚀 3. Publicar / Lanzamiento", "📻 4. Boveda / Radio 24/7"])

    # --- TAB 1 MUSICA ---
    with tab1:
        col1, col2 = st.columns([1, 1])
        with col1:
            st.subheader("Proyecto Musical")
            project_title = st.text_input("Titulo del proyecto", value=ui["project_title"], key="ui_project_title", on_change=autosave_callback)
            region = st.selectbox("Region / Mercado", list(REGION_GENRE_DEFAULTS.keys()), index=list(REGION_GENRE_DEFAULTS.keys()).index(ui["selected_region"]) if ui["selected_region"] in REGION_GENRE_DEFAULTS else 0, key="ui_region", on_change=on_region_change)
            genres = st.multiselect("Generos (max 3)", ALL_WORLD_GENRES, default=ui["selected_genres"][:3], key="ui_genres")
            voice_type = st.selectbox("Voz / Perfil", list(VOICE_PROFILES.keys()), index=list(VOICE_PROFILES.keys()).index(ui["voice_type"]) if ui["voice_type"] in VOICE_PROFILES else 0, key="ui_voice_type")
            bpm = st.slider("BPM / Tempo", 60, 180, int(ui["bpm"]), key="ui_bpm")
            master_prompt = st.text_area("Prompt Maestro / Idea", value=ui["master_prompt"], height=80, key="ui_master_prompt", placeholder="Ej: Merengue tipico jocoso para Miniel que comio donde Lethy, luego cafe donde Ondina debajo de la mata de guanabana...")
        with col2:
            st.subheader("Letra / Guion para Voz")
            default_lyrics = "Rumbo a celebrar, larga vida y salud, bajo el amparo del Senor, a celebrar con mariachi y musica tipica. Pedro Baldera les canta con amor."
            lyrics = st.text_area("Letra completa", value=default_lyrics, height=220, key="lyrics_input")
            st.caption(f"Caracteres: {len(lyrics)} | Voz: {VOICE_PROFILES[voice_type]['voice'] or 'Instrumental'} | BPM: {bpm} | Generos: {', '.join(genres) if genres else 'Sin genero'}")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("🎤 Generar Voz MP3", type="primary", use_container_width=True):
                    if not is_admin and pin:
                        st.error("Necesita PIN Admin para generar.")
                    else:
                        with st.spinner("Generando voz con edge-tts..."):
                            out = MEDIA_DIR / f"voz_{re.sub(r'[^A-Za-z0-9_-]+','_',project_title)[:30]}_{datetime.now().strftime('%H%M%S')}.mp3"
                            ok, msg = generate_voice_audio(lyrics, VOICE_PROFILES[voice_type], out)
                            if ok:
                                add_asset(vault, project_title, "audio_voz", str(out), {"genre": genres, "voice": voice_type, "bpm": bpm})
                                st.success(msg)
                                st.audio(str(out))
                            else:
                                st.error(msg)
            with c2:
                if st.button("🖼 Generar Portada", use_container_width=True):
                    out_img = MEDIA_DIR / f"portada_{re.sub(r'[^A-Za-z0-9_-]+','_',project_title)[:30]}_{datetime.now().strftime('%H%M%S')}.jpg"
                    generate_cover(project_title, "BASA Productions", ", ".join(genres[:2]) if genres else "Bachata", "Cine Epico / Hollywood Dorado", out_img)
                    add_asset(vault, project_title, "portada", str(out_img), {"genre": genres})
                    st.success(f"Portada creada: {out_img.name}")
                    st.image(str(out_img), width=320)

    # --- TAB 2 CINE ---
    with tab2:
        st.subheader("🎬 Cine / Pelicula Completa")
        cc1, cc2 = st.columns(2)
        with cc1:
            cine_title = st.text_input("Titulo pelicula", value=ui["cine_title"], key="ui_cine_title")
            cine_ep = st.text_input("Episodio / Capitulo", value=ui["cine_ep"], key="ui_cine_ep")
            cine_style = st.selectbox("Estilo visual", list(CINEMA_STYLES.keys()), key="ui_cine_style")
            cine_voice = st.selectbox("Voz narrador", list(VOICE_PROFILES.keys()), key="ui_cine_voice")
            cine_genre = st.selectbox("Musica de fondo", ALL_WORLD_GENRES, index=ALL_WORLD_GENRES.index(ui["cine_music_genre"]) if ui["cine_music_genre"] in ALL_WORLD_GENRES else 0, key="ui_cine_music_genre")
            cine_idea = st.text_area("Idea central", value=ui["cine_idea"], key="ui_cine_idea")
        with cc2:
            cine_story = st.text_area("Storyboard - Una linea por escena: Escena | Titulo | Descripcion", value=ui["cine_storyboard_text"], height=220, key="ui_cine_storyboard_text")
            scenes = parse_storyboard(cine_story)
            st.info(f"Escenas detectadas: {len(scenes)}")
            for s in scenes:
                st.markdown(f"**{s['id']} - {s['title']}**: {s['desc']}")
        if st.button("🎬 Generar Storyboard + Narracion + Poster", type="primary"):
            with st.spinner("Generando cine BASA..."):
                poster = MEDIA_DIR / f"cine_poster_{datetime.now().strftime('%H%M%S')}.jpg"
                generate_cover(cine_title, "BASA Cine", cine_genre, cine_style, poster)
                add_asset(vault, cine_title, "poster_cine", str(poster), {"style": cine_style})
                full_script = f"{cine_title}. {cine_idea}. " + " ".join([f"{s['title']}. {s['desc']}" for s in scenes])
                out_audio = MEDIA_DIR / f"cine_narracion_{datetime.now().strftime('%H%M%S')}.mp3"
                ok, msg = generate_voice_audio(full_script, VOICE_PROFILES[cine_voice], out_audio)
                if ok:
                    add_asset(vault, cine_title, "audio_cine", str(out_audio), {"scenes": len(scenes)})
                    st.success("Cine generado: poster + narracion")
                    st.image(str(poster), width=360)
                    st.audio(str(out_audio))
                else:
                    st.warning(f"Poster listo, audio: {msg}")
                    st.image(str(poster), width=360)

    # --- TAB 3 PUBLICAR ---
    with tab3:
        st.subheader("🚀 Publicar / Lanzamiento")
        pub_title = st.text_input("Titulo lanzamiento", value=ui["pub_title"], key="ui_pub_title")
        pub_artist = st.text_input("Artista", value=ui["pub_artist"], key="ui_pub_artist")
        pub_lyrics = st.text_area("Letra / Creditos para distribuidora", value=ui["pub_lyrics"], height=140, key="ui_pub_lyrics")
        col_p1, col_p2, col_p3 = st.columns(3)
        with col_p1:
            plat = st.multiselect("Plataformas", ["Spotify", "YouTube", "TikTok", "Apple Music", "Amazon Music", "Instagram / Facebook"], default=["Spotify", "YouTube", "TikTok"])
        with col_p2:
            isrc = st.text_input("ISRC (si tiene)", value=f"DO-BASA-{datetime.now().strftime('%y%m%d')}")
            upc = st.text_input("UPC / EAN", value="")
        with col_p3:
            fecha = st.date_input("Fecha lanzamiento", value=datetime.now().date())
            precio = st.selectbox("Precio / Modelo", ["Gratis - Promocional", "Iguala Mensual BASA66", "Venta Unica", "Streaming"])
        if st.button("✅ Registrar Lanzamiento en Boveda", type="primary"):
            init_dirs()
            log = []
            if RELEASES_FILE.exists():
                try:
                    log = json.loads(RELEASES_FILE.read_text(encoding="utf-8"))
                except Exception:
                    log = []
            entry = {"id": str(uuid.uuid4())[:8], "title": pub_title, "artist": pub_artist, "platforms": plat, "isrc": isrc, "upc": upc, "fecha": str(fecha), "modelo": precio, "lyrics": pub_lyrics, "created_at": datetime.now().isoformat()}
            log.append(entry)
            RELEASES_FILE.write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")
            st.success(f"Lanzamiento registrado: {pub_title} - {pub_artist} - {fecha}")
            st.json(entry)
        if RELEASES_FILE.exists():
            try:
                st.dataframe(json.loads(RELEASES_FILE.read_text(encoding="utf-8")))
            except Exception:
                pass

    # --- TAB 4 BOVEDA ---
    with tab4:
        st.subheader("📻 Boveda / Radio Autonoma 24/7")
        st.write(f"**Estacion:** {vault.get('station_config', {}).get('station_name')} | **Auto-avance:** {vault.get('station_config', {}).get('auto_advance')}")
        if not vault.get("assets"):
            st.info("Aun no hay assets. Genere voz o portada en la pestaña 1 para llenar la boveda.")
        else:
for a in reversed(vault.get("assets", [])[-20:]):
    # FIX BASA: usar .get() para que nunca de KeyError con assets viejos
    a_title = a.get("title", "Sin titulo") if isinstance(a, dict) else "Sin titulo"
    a_kind = a.get("kind", "asset") if isinstance(a, dict) else "asset"
    a_date = str(a.get("created_at", ""))[:16] if isinstance(a, dict) else ""
    a_id = a.get("id", "no-id") if isinstance(a, dict) else "no-id"
    a_file = a.get("file", "") if isinstance(a, dict) else ""

    with st.expander(f"{a_date} - {a_title} [{a_kind}]"):
        st.write(a)
        p = Path(a_file)
        if p.exists():
            if p.suffix.lower() in [".mp3", ".wav"]:
                st.audio(str(p))
            elif p.suffix.lower() in [".jpg", ".jpeg", ".png"]:
                st.image(str(p), width=300)
            with open(p, "rb") as f:
                st.download_button(f"⬇ Descargar {p.name}", f.read(), file_name=p.name, key=f"dl_{a_id}")
        else:
            st.warning(f"Archivo no encontrado: {a_file}")

                    st.write(a)
                    p = Path(a.get("file", ""))
                    if p.exists():
                        if p.suffix.lower() in [".mp3", ".wav"]:
                            st.audio(str(p))
                        elif p.suffix.lower() in [".jpg", ".jpeg", ".png"]:
                            st.image(str(p), width=300)
                        with open(p, "rb") as f:
                            st.download_button(f"⬇ Descargar {p.name}", f.read(), file_name=p.name, key=f"dl_{a['id']}")
        if st.button("🗑 Limpiar Boveda (Backup primero)"):
            save_vault(vault)
            st.success("Backup hecho en basa_vault_data/backups/. Para borrar, borre la carpeta manualmente.")

    st.divider()
    st.caption("BASA Universal AI Studio v10 FULL - 100/100 - (c) Pedro Baldera - BASA Productions - Todos los derechos reservados - ONAPI / Copyright")

if __name__ == "__main__":
    main()
