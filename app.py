from __future__ import annotations

import ast
import asyncio
import base64
import hashlib
import io
import json
import math
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

import edge_tts
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from pydub import AudioSegment
import streamlit as st

# ==============================================================================
# CONFIGURACIÓN DE PÁGINA Y RUTAS PERSISTENTES
# ==============================================================================
st.set_page_config(
    page_title="BASA Universal AI Studio · Autónomo 100/100",
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
# CATÁLOGO MUNDIAL DE GÉNEROS, REGIONES Y VOCES
# ==============================================================================
REGION_GENRE_DEFAULTS: dict[str, list[str]] = {
    "República Dominicana (Caribe)": [
        "Bachata Dominicana",
        "Merengue de Calle / Mambo",
        "Salsa Clásica",
    ],
    "México": [
        "Ranchera / Mariachi",
        "Música Mexicana / Banda",
        "Balada",
    ],
    "Puerto Rico / Urbano Latino": [
        "Reggaetón",
        "Salsa Clásica",
        "Dembow / Urbano",
    ],
    "Estados Unidos / Internacional": [
        "Pop / Rock Americano",
        "R&B / Soul Americano",
        "Balada",
    ],
    "Colombia / Sudamérica": [
        "Salsa Clásica",
        "Cumbia / Vallenato",
        "Bolero",
    ],
    "Global / Personalizado": [
        "Bachata Dominicana",
        "Merengue de Calle / Mambo",
        "Salsa Clásica",
    ],
}

ALL_WORLD_GENRES: list[str] = [
    "Bachata Dominicana",
    "Merengue de Calle / Mambo",
    "Merengue Tipico (Perico Ripiao)",
    "Salsa Clásica",
    "Bolero",
    "Reggaetón",
    "Balada",
    "Ranchera / Mariachi",
    "Música Mexicana / Banda",
    "Pop / Rock Americano",
    "R&B / Soul Americano",
    "Dembow / Urbano",
    "Cumbia / Vallenato",
    "Score Cinematográfico / Orquestal",
]

VOICE_PROFILES: dict[str, dict[str, Any]] = {
    "Voz Masculina": {
        "voice": "es-DO-EmilioNeural",
        "rate": "+0%",
        "pitch": "+0Hz",
        "mode": "solo",
    },
    "Voz Femenina": {
        "voice": "es-DO-RamonaNeural",
        "rate": "+0%",
        "pitch": "+0Hz",
        "mode": "solo",
    },
    "Voz Juvenil Masculina": {
        "voice": "es-MX-JorgeNeural",
        "rate": "+8%",
        "pitch": "+18Hz",
        "mode": "solo",
    },
    "Voz Juvenil Femenina": {
        "voice": "es-MX-DaliaNeural",
        "rate": "+8%",
        "pitch": "+22Hz",
        "mode": "solo",
    },
    "Voz Infantil (Niño/Niña)": {
        "voice": "es-MX-DaliaNeural",
        "rate": "+5%",
        "pitch": "+55Hz",
        "mode": "solo",
    },
    "Coro Grupal (Voces en Bloque)": {
        "voice": "es-DO-RamonaNeural",
        "rate": "+2%",
        "pitch": "+0Hz",
        "mode": "choir",
    },
    "Solo Instrumental (Sin Voz)": {
        "voice": "",
        "rate": "+0%",
        "pitch": "+0Hz",
        "mode": "instrumental",
    },
}

CINEMA_STYLES: dict[
    str, tuple[tuple[int, int, int], tuple[int, int, int], tuple[int, int, int]]
] = {
    "Cine Épico / Hollywood Dorado": (
        (14, 18, 34),
        (245, 208, 97),
        (225, 232, 245),
    ),
    "Acción / Cyberpunk Neón": ((10, 12, 24), (0, 240, 255), (235, 245, 255)),
    "Animación 3D / Familiar": ((22, 34, 68), (255, 185, 65), (255, 255, 255)),
    "Documental / Historia Real": (
        (24, 22, 20),
        (218, 175, 110),
        (238, 234, 228),
    ),
    "Drama / Suspenso Nocturno": ((8, 10, 14), (220, 65, 65), (215, 220, 225)),
}


# ==============================================================================
# UTILIDADES DE BÓVEDA Y AUTOGUARDADO CONTINUO
# ==============================================================================
def init_dirs() -> None:
  MEDIA_DIR.mkdir(parents=True, exist_ok=True)
  BACKUP_DIR.mkdir(parents=True, exist_ok=True)
  AUTO_EXPORT_DIR.mkdir(parents=True, exist_ok=True)


def load_autosave_state() -> dict[str, Any]:
  init_dirs()
  default_ui = {
      "project_title": "Rumbo a Celebrar (Navidad)",
      "selected_region": "República Dominicana (Caribe)",
      "selected_genres": [
          "Bachata Dominicana",
          "Merengue de Calle / Mambo",
          "Salsa Clásica",
      ],
      "voice_type": "Voz Masculina",
      "bpm": 135,
      "master_prompt": "",
      "cine_title": "El Lápiz Pesa Más que el Pico",
      "cine_ep": "Película Completa · T01",
      "cine_style": "Cine Épico / Hollywood Dorado",
      "cine_voice": "Voz Masculina",
      "cine_music_genre": "Score Cinematográfico / Orquestal",
      "cine_idea": "Historia de superación desde cero hasta alcanzar el éxito en República Dominicana.",
      "cine_storyboard_text": (
          "Escena 01 | El Inicio | Amanecer en Santo Domingo, plano general de la ciudad despertando con esperanza.\n"
          "Escena 02 | El Desafío | Con esfuerzo diario, disciplina y visión, cada paso construye un nuevo horizonte.\n"
          "Escena 03 | La Victoria | Celebración en familia con música, luz y orgullo para toda Quisqueya."
      ),
      "pub_title": "Rumbo a Celebrar (Versión Studio)",
      "pub_artist": "BASA Productions · El Forense de la Música",
      "pub_lyrics": "Producido en BASA Universal AI Studio. Arreglos y producción original.",
  }
  if UI_STATE_FILE.exists():
    try:
      loaded = json.loads(UI_STATE_FILE.read_text(encoding="utf-8"))
      default_ui.update(loaded)
    except Exception:
      pass
  return default_ui


def autosave_callback() -> None:
  """Guarda automáticamente el estado completo al hacer clic o cambiar de sección."""
  init_dirs()
  current = load_autosave_state()
  snapshot = {
      "project_title": st.session_state.get(
          "ui_project_title", current["project_title"]
      ),
      "selected_region": st.session_state.get(
          "ui_region", current["selected_region"]
      ),
      "selected_genres": st.session_state.get(
          "ui_genres", current["selected_genres"]
      ),
      "voice_type": st.session_state.get(
          "ui_voice_type", current["voice_type"]
      ),
      "bpm": st.session_state.get("ui_bpm", current["bpm"]),
      "master_prompt": st.session_state.get(
          "ui_master_prompt", current["master_prompt"]
      ),
      "cine_title": st.session_state.get(
          "ui_cine_title", current["cine_title"]
      ),
      "cine_ep": st.session_state.get("ui_cine_ep", current["cine_ep"]),
      "cine_style": st.session_state.get(
          "ui_cine_style", current["cine_style"]
      ),
      "cine_voice": st.session_state.get(
          "ui_cine_voice", current["cine_voice"]
      ),
      "cine_music_genre": st.session_state.get(
          "ui_cine_music_genre", current["cine_music_genre"]
      ),
      "cine_idea": st.session_state.get("ui_cine_idea", current["cine_idea"]),
      "cine_storyboard_text": st.session_state.get(
          "ui_cine_storyboard_text", current["cine_storyboard_text"]
      ),
      "pub_title": st.session_state.get("ui_pub_title", current["pub_title"]),
      "pub_artist": st.session_state.get(
          "ui_pub_artist", current["pub_artist"]
      ),
      "pub_lyrics": st.session_state.get(
          "ui_pub_lyrics", current["pub_lyrics"]
      ),
      "saved_at": datetime.now().isoformat(),
  }
  UI_STATE_FILE.write_text(
      json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8"
  )


def on_region_change() -> None:
  reg = st.session_state.get("ui_region", "República Dominicana (Caribe)")
  st.session_state["ui_genres"] = REGION_GENRE_DEFAULTS.get(
      reg,
      [
          "Bachata Dominicana",
          "Merengue de Calle / Mambo",
          "Salsa Clásica",
      ],
  )[:3]
  autosave_callback()


def init_vault() -> dict[str, Any]:
  init_dirs()
  default_station = {
      "station_name": "BASA Radio Autónoma 24/7",
      "autonomous_permission": True,
      "auto_advance": True,
      "active_track_id": None,
  }
  if not INDEX_FILE.exists():
    default_data = {
        "created_at": datetime.now().isoformat(),
        "assets": [],
        "autonomous_modules": [],
        "station_config": default_station,
    }
    INDEX_FILE.write_text(
        json.dumps(default_data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
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
        INDEX_FILE.write_text(
            json.dumps(restored, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return restored
      except Exception:
        continue
    return {
        "created_at": datetime.now().isoformat(),
        "assets": [],
        "autonomous_modules": [],
        "station_config": default_station,
    }


def load_users_vault() -> dict[str, Any]:
  init_dirs()
  if not ACCOUNTS_FILE.exists():
    base = {
        "delegates": ["pedro.baldera"],
        "users": {},
