import io
import json
import math
import os
import random
import re
import sqlite3
import struct
import sys
import threading
import time
import traceback
import urllib.request
import uuid
import wave
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

# Configuración inicial obligatoria como primera instrucción de Streamlit
st.set_page_config(
    page_title="BASA Audit Intelligence & Media Production Suite Global (10/10)",
    page_icon="📥",
    layout="wide",
    initial_sidebar_state="expanded",
)

try:
    from streamlit_autorefresh import st_autorefresh
    AUTOREFRESH_DISPONIBLE = True
except ImportError:
    AUTOREFRESH_DISPONIBLE = False

try:
    from google import genai
    from google.genai import types
    GOOGLE_GENAI_DISPONIBLE = True
except ImportError:
    GOOGLE_GENAI_DISPONIBLE = False

if AUTOREFRESH_DISPONIBLE:
    st_autorefresh(interval=15 * 1000, key="basa_v47_full_15s")

# ============================================================================
# RUTAS, DIRECTORIOS Y CONSTANTES MAESTRAS
# ============================================================================
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "basa_universal_studio.db"
DROP_DIR = BASE_DIR / "assets" / "auto_drop"
RAW_DIR = BASE_DIR / "assets" / "audio_raw"

ARCHIVO_MAESTRO_V47 = "basa_sistema_maestro_v47.json"
ARCHIVO_CONFIG_SEGURA = "basa_config_segura_v47.json"

CARPETAS_INDEPENDIENTES = {
    "Musica_Dembow_Tipico": "basa_recursos/musica",
    "Audiovisual_Peliculas": "basa_recursos/audiovisual",
    "Series_Navidenas": "basa_recursos/series",
    "Analitica_Tesoreria": "basa_recursos/tesoreria_bhd",
    "Dependencias_IA": "basa_recursos/dependencias_ia",
    "Configuracion_Segura": "basa_recursos/seguridad",
}

ESCALAS = {
    "Merengue Tipico (Perico Ripiao)": [261.63, 293.66, 329.63, 392.00, 440.00, 466.16, 523.25],
    "Merengue de Calle": [293.66, 329.63, 369.99, 440.00, 493.88, 587.33],
    "Bachata": [220.00, 261.63, 293.66, 329.63, 369.99, 392.00, 440.00],
    "Salsa": [261.63, 293.66, 311.13, 349.23, 392.00, 440.00, 466.16, 523.25],
    "Dembow / Urbano": [196.00, 207.65, 233.08, 261.63, 293.66, 349.23, 392.00],
    "Ranchera / Mariachi": [293.66, 329.63, 369.99, 392.00, 440.00, 493.88, 554.37, 587.33],
    "Bolero / Balada": [220.00, 246.94, 261.63, 293.66, 329.63, 349.23, 415.30, 440.00],
    "Bossa Nova / Samba (Brasil)": [261.63, 293.66, 329.63, 369.99, 392.00, 440.00, 493.88, 523.25],
    "Tango (Argentina)": [293.66, 329.63, 349.23, 392.00, 440.00, 466.16, 554.37, 587.33],
    "Reggae / Dub (Jamaica)": [196.00, 220.00, 246.94, 261.63, 293.66, 329.63, 349.23, 392.00],
    "Afrobeat / Funk": [246.94, 293.66, 329.63, 369.99, 415.30, 440.00, 493.88],
    "Highlife / Soukous (Africa)": [261.63, 293.66, 329.63, 392.00, 440.00, 523.25],
    "Flamenco / Rumba Espanola": [329.63, 349.23, 415.30, 440.00, 493.88, 523.25, 587.33, 659.25],
    "Celta / Folk Irlandes": [293.66, 329.63, 349.23, 392.00, 440.00, 493.88, 523.25, 587.33],
    "Klezmer / Balcanica": [293.66, 311.13, 369.99, 392.00, 440.00, 466.16, 523.25, 587.33],
    "Clasica / Sinfonica (Europa)": [261.63, 293.66, 329.63, 349.23, 392.00, 440.00, 493.88, 523.25],
    "Jazz / Blues (EE.UU.)": [220.00, 261.63, 293.66, 311.13, 329.63, 392.00, 440.00],
    "Pop / Hip-Hop / Trap / EDM": [261.63, 293.66, 311.13, 349.23, 392.00, 415.30, 466.16, 523.25],
}

# ============================================================================
# ESTILOS VISUALES SUPREMOS
# ============================================================================
st.markdown(
    """<style>
.main { background-color: #020202; color: white; }
.stButton>button { background-color: #00FF66; color: black; font-weight: bold; border-radius: 20px; }
.card-media { background-color: #0A0A0A; padding: 15px; border-radius: 10px; border: 1px solid #00FF66; margin-bottom: 12px; }
.author-banner { background: linear-gradient(90deg, #111 0%, #033 100%); padding: 12px; border-radius: 8px; border-left: 5px solid #00FF66; margin-bottom: 20px; }
.download-badge { background-color: #00FF66; color: black; padding: 6px 12px; border-radius: 15px; font-weight: bold; font-size: 14px; }
</style>""",
    unsafe_allow_html=True,
)

# ============================================================================
# MOTOR DE BASE DE DATOS SQLITE & SÍNTESIS DE AUDIO REAL (UNIVERSAL STUDIO)
# ============================================================================
def init_db_y_entorno():
    DROP_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for ruta in CARPETAS_INDEPENDIENTES.values():
        os.makedirs(ruta, exist_ok=True)

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
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS plataformas_personalizadas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT UNIQUE,
                formato_prompt TEXT
            )
            """
        )
        c.commit()


init_db_y_entorno()


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


def agregar_enlace_vigilado(url, plataforma):
    with sqlite3.connect(DB_PATH) as c:
        c.execute(
            "INSERT OR REPLACE INTO enlaces_vigilados (url, plataforma, ultimo_chequeo, estado) VALUES (?, ?, CURRENT_TIMESTAMP, 'Activo')",
            (url.strip(), plataforma),
        )
        c.commit()


def listar_vigilados():
    with sqlite3.connect(DB_PATH) as c:
        return pd.read_sql_query("SELECT * FROM enlaces_vigilados ORDER BY id DESC", c)


def obtener_plataformas():
    base = [
        "Motor Libre BASA (0 Errores)",
        "Suno (v4 / v5 / v6 Unlimited)",
        "Gemini Music / Lyria 3.5",
        "Mureka AI",
        "ChatGPT / OpenAI",
        "Udio Music",
        "Stable Audio / Riffusion",
        "Video IA (Sora / Runway / Kling)",
        "IA Futura / Personalizada",
    ]
    with sqlite3.connect(DB_PATH) as c:
        extras = [r[0] for r in c.execute("SELECT nombre FROM plataformas_personalizadas").fetchall()]
    return base + [e for e in extras if e not in base]


def registrar_nueva_ia(nombre, formato_prompt):
    with sqlite3.connect(DB_PATH) as c:
        c.execute(
            "INSERT OR IGNORE INTO plataformas_personalizadas (nombre, formato_prompt) VALUES (?, ?)",
            (nombre.strip(), formato_prompt.strip()),
        )
        c.commit()


def sintetizar_audio_wav_bytes(genero: str = "Merengue Tipico (Perico Ripiao)", duracion_seg: int = 6) -> bytes:
    """Genera audio WAV real estéreo/mono basado en las escalas musicales BASA."""
    notas = ESCALAS.get(genero, ESCALAS["Merengue Tipico (Perico Ripiao)"])
    sample_rate = 44100
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        frames = bytearray()
        paso_muestras = int(sample_rate * 0.25)
        total_muestras = sample_rate * duracion_seg
        for i in range(total_muestras):
            idx_nota = (i // paso_muestras) % len(notas)
            freq = notas[idx_nota]
            env = 1.0 - ((i % paso_muestras) / paso_muestras) * 0.65
            val = math.sin(2.0 * math.pi * freq * (i / sample_rate)) * 0.5
            val += math.sin(2.0 * math.pi * (freq * 0.5) * (i / sample_rate)) * 0.25
            sample = int(max(-32767, min(32767, val * env * 32767)))
            frames.extend(struct.pack("<h", sample))
        wf.writeframes(bytes(frames))
    return buf.getvalue()


def rastrear_y_extraer_url(url: str, plataforma_hint: str = "Auto") -> dict:
    url = url.strip()
    titulo = f"Recurso Web {datetime.now().strftime('%H:%M:%S')}"
    contenido_extraido = ""
    ruta_descarga = ""
    tipo = "Prompt / Pagina Web"

    if "suno.com" in url:
        plataforma = "Suno (v4 / v5 / v6 Unlimited)"
        tipo = "Cancion / Audio"
    elif "mureka" in url:
        plataforma = "Mureka AI"
        tipo = "Cancion / Audio"
    elif "chatgpt.com" in url or "openai.com" in url:
        plataforma = "ChatGPT / OpenAI"
        tipo = "Prompt / Script"
    elif "aistudio.google" in url or "gemini" in url:
        plataforma = "Gemini Music / Lyria 3.5"
        tipo = "Prompt / Audio"
    else:
        plataforma = plataforma_hint if plataforma_hint != "Auto" else "IA Futura / Web"

