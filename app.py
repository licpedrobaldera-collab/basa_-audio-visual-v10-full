import math
import random
import re
import sqlite3
import struct
import urllib.request
import uuid
import wave
from datetime import datetime
from pathlib import Path
import pandas as pd
import streamlit as st

st.set_page_config(page_title="BASA Universal AI Studio", page_icon="🤖", layout="wide")

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "basa_universal_studio.db"
DROP_DIR = BASE_DIR / "assets" / "auto_drop"
RAW_DIR = BASE_DIR / "assets" / "audio_raw"


def init_db():
    DROP_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as c:
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS activos_ia (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                titulo TEXT,
                tipo_activo TEXT,
                plataforma_ia TEXT,
                genero_categoria TEXT,
                prompt_o_script TEXT,
                ruta_archivo TEXT,
                url_origen TEXT,
                fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS enlaces_vigilados (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE,
                plataforma TEXT,
                ultimo_chequeo TIMESTAMP,
                estado TEXT DEFAULT 'Activo'
            )
            """
        )
        c.commit()


def guardar_activo(titulo, tipo_activo, plataforma_ia, genero_categoria, prompt_o_script, ruta_archivo="", url_origen=""):
    with sqlite3.connect(DB_PATH) as c:
        c.execute(
            "INSERT INTO activos_ia (titulo, tipo_activo, plataforma_ia, genero_categoria, prompt_o_script, ruta_archivo, url_origen) VALUES (?,?,?,?,?,?,?)",
            (titulo, tipo_activo, plataforma_ia, genero_categoria, prompt_o_script, ruta_archivo, url_origen),
        )
        c.commit()


def listar_activos():
    with sqlite3.connect(DB_PATH) as c:
        return pd.read_sql_query("SELECT * FROM activos_ia ORDER BY id DESC", c)


def eliminar_activo(activo_id):
    with sqlite3.connect(DB_PATH) as c:
        c.execute("DELETE FROM activos_ia WHERE id = ?", (activo_id,))
        c.commit()


ESCALAS = {
    "Merengue Tipico (Perico Ripiao)": [261.63, 293.66, 329.63, 392.00, 440.00, 466.16, 523.25],
    "Merengue de Calle": [293.66, 329.63, 369.99, 440.00, 493.88, 587.33],
    "Bachata": [220.00, 261.63, 293.66, 329.63, 369.99, 392.00, 440.00],
    "Salsa": [261.63, 293.66, 311.13, 349.23, 392.00, 440.00, 466.16, 523.25],
    "Dembow / Urbano": [196.00, 207.65, 233.08, 261.63, 293.66, 349.23, 392.00],
    "Ranchera / Mariachi": [293.66, 329.63, 369.99, 392.00, 440.00, 493.88, 554.37, 587.33],
    "Bolero / Balada": [220.00, 246.94, 261.63, 293.66, 329.63, 349.23, 415.30, 440.00],
    "Bossa Nova / Samba": [261.63, 293.66, 329.63, 369.99, 392.00, 440.00, 493.88, 523.25],
    "Tango": [293.66, 329.63, 349.23, 392.00, 440.00, 466.16, 554.37, 587.33],
    "Reggae / Dub": [196.00, 220.00, 246.94, 261.63, 293.66, 329.63, 349.23, 392.00],
    "Afrobeat / Funk": [246.94, 293.66, 329.63, 369.99, 415.30, 440.00, 493.88],
    "Flamenco / Rumba": [329.63, 349.23, 415.30, 440.00, 493.88, 523.25, 587.33, 659.25],
    "Jazz / Blues": [220.00, 261.63, 293.66, 311.13, 329.63, 392.00, 440.00],
    "Pop / Hip-Hop / Trap": [261.63, 293.66, 311.13, 349.23, 392.00, 415.30, 466.16, 523.25],
    "Arabe / Maqam Hijaz": [261.63, 277.18, 329.63, 349.23, 392.00, 415.30, 466.16, 523.25],
    "Raga Hindu / Bollywood": [261.63, 277.18, 329.63, 349.23, 392.00, 415.30, 493.88, 523.25],
    "Japonesa / Hirajoshi": [293.66, 329.66, 349.23, 440.00, 466.16, 587.33],
    "China Pentatonica": [349.23, 392.00, 440.00, 523.25, 587.33, 698.46],
}


def generar_audio_autonomo(titulo, genero, bpm=130, duracion_seg=20):
    sr = 44100
    n_samples = int(sr * duracion_seg)
    escala = ESCALAS.get(genero, [261.63, 293.66, 329.63, 392.00, 440.00])
    beat_dur = 60.0 / max(60, min(220, int(bpm)))
    samples_per_beat = int(sr * beat_dur)

    random.seed(sum(ord(c) for c in (titulo + genero)))
    total_beats = int(duracion_seg / beat_dur) + 8
    melodia = [random.choice(escala) for _ in range(total_beats)]
    nota_base = min(escala)
    nota_quinta = escala[min(3, len(escala) - 1)]
    bajo_notas = [nota_base / 2.0 if i % 4 == 0 else (nota_quinta / 2.0) for i in range(total_beats)]

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = "".join(c if c.isalnum() else "_" for c in (titulo or "basa_track"))[:25]
    ruta_wav = RAW_DIR / f"{safe_name}_WORLD_{stamp}.wav"

    with wave.open(str(ruta_wav), "w") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        buf = bytearray()

        for i in range(n_samples):
            t = i / sr
            beat_idx = i // samples_per_beat
            pos_beat = (i % samples_per_beat) / samples_per_beat
            compas_4 = beat_idx % 4

            f_mel = melodia[beat_idx % len(melodia)]
            f_baj = bajo_notas[beat_idx % len(bajo_notas)]

            env_mel = math.exp(-3.2 * pos_beat)
            onda_mel = (math.sin(2 * math.pi * f_mel * t) + 0.3 * math.sin(4 * math.pi * f_mel * t)) * env_mel * 0.32
            env_baj = math.exp(-2.2 * pos_beat)
            onda_baj = math.sin(2 * math.pi * f_baj * t) * env_baj * 0.38

            perc = 0.0
            if compas_4 in (0, 2) and pos_beat < 0.08:
                perc += math.sin(2 * math.pi * 105 * t) * 0.35
            elif compas_4 in (1, 3) and pos_beat < 0.07:
                perc += random.uniform(-0.20, 0.20)

            val_l = max(-0.95, min(0.95, onda_mel + onda_baj + perc))
            val_r = max(-0.95, min(0.95, (onda_mel * 0.82) + onda_baj + perc))
            buf.extend(struct.pack("<hh", int(val_l * 32767), int(val_r * 32767)))

        wf.writeframes(buf)

    return str(ruta_wav)


init_db()

if "clave_libre" not in st.session_state:
    st.session_state["clave_libre"] = f"BASA-UNIV-{uuid.uuid4().hex[:12].upper()}"

with st.sidebar:
    st.header("🤖 Nucleo Autonomo")
    autonomia = st.toggle("Auto-Actualizacion cada 30s", value=False)
    if autonomia:
        st.success("Vigilancia Activa (30s)")
        st.markdown('<meta http-equiv="refresh" content="30">', unsafe_allow_html=True)
    st.divider()
    st.text_input("Licencia Universal Libre", value=st.session_state["clave_libre"], disabled=True)

st.title("🤖 BASA Universal AI Studio · Produccion Online")
st.caption("Compatible con Suno, Mureka, Gemini Music, ChatGPT y ritmos mundiales · 100% Operativo en la Nube")

df_act = listar_activos()
c1, c2, c3 = st.columns(3)
c1.metric("Total Activos en Boveda", len(df_act))
c2.metric("Audios / Canciones", int((df_act["tipo_activo"] == "Cancion / Audio").sum()) if not df_act.empty else 0)
c3.metric("Prompts / Scripts", int((df_act["tipo_activo"] != "Cancion / Audio").sum()) if not df_act.empty else 0)

tab_crear, tab_migrar, tab_boveda = st.tabs([
    "🎹 Generar Musica & Multi-Prompt",
    "🌐 Migrar Links y Archivos (Suno/Mureka/ChatGPT)",
    "📚 Boveda Multimedia",
])

with tab_crear:
    c_izq, c_der = st.columns([1.15, 1])
    with c_izq:
        t_tema = st.text_input("Titulo del proyecto", placeholder="Ej. Caribe Futurista")
        g_tema = st.selectbox("Genero / Ritmo Mundial", list(ESCALAS.keys()))
        b_col, d_col = st.columns(2)
        bpm_tema = b_col.number_input("BPM", 60, 220, 132)
        dur_tema = d_col.slider("Duracion pista libre (seg)", 10, 60, 20)
        idea_tema = st.text_area("Escribe tu idea, letra o prompt maestro", height=140)

        if st.button("🎵 Generar Audio + Prompts Multi-IA", type="primary", use_container_width=True):
            tit_ok = t_tema.strip() or "Creacion Universal BASA"
            ruta_wav = generar_audio_autonomo(tit_ok, g_tema, int(bpm_tema), int(dur_tema))
            st.session_state["ultimo_wav"] = ruta_wav
            paquete_multi = (
                f"=== SUNO v6 ===\nStyle: {g_tema}, {bpm_tema} BPM, studio mix\nLyrics:\n{idea_tema}\n\n"
                f"=== GEMINI MUSIC / LYRIA 3.5 ===\nCreate a {g_tema} track at {bpm_tema} BPM. {idea_tema}\n\n"
                f"=== MUREKA AI ===\nGenre: {g_tema} | Tempo: {bpm_tema} BPM\n{idea_tema}\n\n"
                f"=== CHATGPT / IA ===\nActua como productor de {g_tema} ({bpm_tema} BPM): {idea_tema}"
            )
            st.session_state["ultimo_paquete"] = paquete_multi
            guardar_activo(tit_ok, "Cancion / Audio", "Motor Libre BASA", g_tema, paquete_multi, ruta_wav)
            st.success("Audio generado y guardado en tu boveda!")

    with c_der:
        st.subheader("Salida de Audio y Prompts")
        if st.session_state.get("ultimo_wav") and Path(st.session_state["ultimo_wav"]).exists():
            st.audio(st.session_state["ultimo_wav"])
            st.download_button(
                "⬇️ Descargar Audio (.WAV)",
                data=Path(st.session_state["ultimo_wav"]).read_bytes(),
                file_name=Path(st.session_state["ultimo_wav"]).name,
                use_container_width=True,
            )
        if st.session_state.get("ultimo_paquete"):
            st.text_area("Prompts listos para copiar:", value=st.session_state["ultimo_paquete"], height=220)

with tab_migrar:
    col_u, col_f = st.columns(2)
    with col_u:
        st.markdown("#### Migrar Enlaces Web (Suno, Mureka, ChatGPT)")
        links_input = st.text_area("Pega tus links (uno por linea)", height=140, placeholder="https://suno.com...")
        if st.button("🚀 Importar Enlaces", type="primary", use_container_width=True):
            urls = [u.strip() for u in links_input.splitlines() if u.strip()]
            for u in urls:
                plat = "Suno" if "suno" in u else ("Mureka" if "mureka" in u else "Web / IA")
