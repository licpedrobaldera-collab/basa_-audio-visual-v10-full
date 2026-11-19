from __future__ import annotations

import ast
import base64
import hashlib
import importlib.util
import io
import json
import math
import re
import shutil
import struct
import subprocess
import time
import urllib.error
import urllib.request
import uuid
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import numpy as np
from PIL import Image, ImageDraw, ImageFont
import streamlit as st

# Detección segura de pydub sin provocar ModuleNotFoundError si falta
PYDUB_AVAILABLE = importlib.util.find_spec("pydub") is not None
if PYDUB_AVAILABLE:
  from pydub import AudioSegment  # type: ignore
else:
  AudioSegment = None  # type: ignore

st.set_page_config(
    page_title="BASA Universal AI Studio · Vigilante Autónomo",
    page_icon="🛡️",
    layout="wide",
)

VAULT_DIR = Path("basa_vault_data")
MEDIA_DIR = VAULT_DIR / "media"
BACKUP_DIR = VAULT_DIR / "backups"
AUTO_EXPORT_DIR = VAULT_DIR / "auto_exports"
INDEX_FILE = VAULT_DIR / "vault_index.json"
ACCOUNTS_FILE = VAULT_DIR / "users_vault.json"
RELEASES_FILE = VAULT_DIR / "releases_log.json"

ADMIN_MASTER_PIN = "BASA-ADMIN-2026"


def init_dirs() -> None:
  for d in (VAULT_DIR, MEDIA_DIR, BACKUP_DIR, AUTO_EXPORT_DIR):
    d.mkdir(parents=True, exist_ok=True)


def _default_vault_payload() -> dict[str, Any]:
  return {
      "created_at": datetime.now().isoformat(),
      "assets": [],
      "autonomous_modules": [],
      "station_config": {
          "station_name": "BASA Radio Autónoma 24/7",
          "autonomous_permission": True,
          "auto_advance": True,
          "active_track_id": None,
      },
  }


def _is_valid_vault_dict(obj: Any) -> bool:
  return (
      isinstance(obj, dict)
      and isinstance(obj.get("assets"), list)
      and isinstance(obj.get("autonomous_modules"), list)
      and isinstance(obj.get("station_config"), dict)
  )


def init_vault() -> dict[str, Any]:
  """Carga la bóveda de forma segura; si está corrupta, restaura desde respaldo."""
  init_dirs()
  if not INDEX_FILE.exists():
    base = _default_vault_payload()
    INDEX_FILE.write_text(
        json.dumps(base, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return base

  try:
    raw_txt = INDEX_FILE.read_text(encoding="utf-8")
    parsed = json.loads(raw_txt)
    if _is_valid_vault_dict(parsed):
      return parsed
  except Exception:
    pass

  # Autorecuperación desde respaldos válidos
  for bkp in sorted(BACKUP_DIR.glob("vault_index_*.json"), reverse=True):
    try:
      cand = json.loads(bkp.read_text(encoding="utf-8"))
      if _is_valid_vault_dict(cand):
        INDEX_FILE.write_text(
            json.dumps(cand, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return cand
    except Exception:
      continue

  fallback = _default_vault_payload()
  INDEX_FILE.write_text(
      json.dumps(fallback, indent=2, ensure_ascii=False), encoding="utf-8"
  )
  return fallback


def save_vault_data_safe(
    data: dict[str, Any],
    auto_export: bool = True,
    reason: str = "Guardado seguro",
) -> None:
  """Escritura atómica con validación previa para no corromper la base de datos."""
  init_dirs()
  if not _is_valid_vault_dict(data):
    raise ValueError("Estructura de bóveda inválida; escritura cancelada.")

  serialized = json.dumps(data, indent=2, ensure_ascii=False)
  # Verificar que el JSON serializado sea parseable antes de sobrescribir
  json.loads(serialized)

  tmp_file = INDEX_FILE.with_suffix(".json.tmp")
  tmp_file.write_text(serialized, encoding="utf-8")
  os_replace_safe(tmp_file, INDEX_FILE)

  ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
  shutil.copy2(INDEX_FILE, BACKUP_DIR / f"vault_index_{ts}.json")
  for old_b in sorted(BACKUP_DIR.glob("vault_index_*.json"), reverse=True)[30:]:
    try:
      old_b.unlink()
    except Exception:
      pass

  if auto_export:
    try:
      zip_path = auto_export_bundle(
          reason=reason,
          username=st.session_state.get("active_user", "Invitado Libre"),
          device_type=st.session_state.get("active_device", "Celular"),
      )
      st.session_state["last_auto_export"] = str(zip_path)
    except Exception:
      pass


def os_replace_safe(src: Path, dst: Path) -> None:
  try:
    src.replace(dst)
  except Exception:
    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    if src.exists():
      try:
        src.unlink()
      except Exception:
        pass


def load_users_vault() -> dict[str, Any]:
  init_dirs()
  default_u = {"delegates": ["pedro.baldera"], "users": {}, "device_history": []}
  if not ACCOUNTS_FILE.exists():
    ACCOUNTS_FILE.write_text(
        json.dumps(default_u, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return default_u
  try:
    d = json.loads(ACCOUNTS_FILE.read_text(encoding="utf-8"))
    if isinstance(d, dict):
      d.setdefault("delegates", ["pedro.baldera"])
      d.setdefault("users", {})
      d.setdefault("device_history", [])
      return d
  except Exception:
    pass
  return default_u


def save_users_vault(data: dict[str, Any]) -> None:
  init_dirs()
  serialized = json.dumps(data, indent=2, ensure_ascii=False)
  json.loads(serialized)
  tmp = ACCOUNTS_FILE.with_suffix(".json.tmp")
  tmp.write_text(serialized, encoding="utf-8")
  os_replace_safe(tmp, ACCOUNTS_FILE)


def obfuscate_key(secret: str) -> str:
  raw = secret.encode("utf-8")
  salted = hashlib.sha256(b"BASA_KEY_SALT::" + raw).hexdigest()[:12]
  return f"ENC[{salted}]:{base64.b64encode(raw).decode('ascii')}"


def reveal_key(encoded: str) -> str:
  if not encoded or ":" not in encoded:
    return ""
  _, b64_part = encoded.split(":", 1)
  try:
    return base64.b64decode(b64_part.encode("ascii")).decode("utf-8")
  except Exception:
    return ""


def log_device_event(
    username: str, device_type: str, action: str, access_mode: str
) -> None:
  u_data = load_users_vault()
  u_data["device_history"].insert(
      0,
      {
          "id": f"DEV-{uuid.uuid4().hex[:8].upper()}",
          "user": username or "Invitado Libre",
          "device": device_type,
          "action": action,
          "access_mode": access_mode,
          "timestamp": datetime.now().isoformat(),
      },
  )
  u_data["device_history"] = u_data["device_history"][:200]
  save_users_vault(u_data)


def auto_export_bundle(reason: str, username: str, device_type: str) -> Path:
  init_dirs()
  ts = datetime.now().strftime("%Y%m%d_%H%M%S")
  zip_path = AUTO_EXPORT_DIR / f"basa_auto_export_{ts}.zip"
  vault_obj = init_vault()
  users_obj = load_users_vault()
  sanitized = {
      "delegates": users_obj.get("delegates", []),
      "users_count": len(users_obj.get("users", {})),
      "device_history": users_obj.get("device_history", [])[:50],
      "exported_reason": reason,
      "exported_by": username,
      "device": device_type,
      "exported_at": datetime.now().isoformat(),
  }
  with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
    if INDEX_FILE.exists():
      zf.write(INDEX_FILE, arcname="vault_index.json")
    zf.writestr(
        "session_and_devices_export.json",
        json.dumps(sanitized, indent=2, ensure_ascii=False),
    )
    for asset in vault_obj.get("assets", [])[:25]:
      fpath = asset.get("file_path")
      if fpath:
        p = Path(fpath)
        if p.exists() and p.is_file():
          zf.write(p, arcname=f"media/{p.name}")

  for old_z in sorted(AUTO_EXPORT_DIR.glob("basa_auto_export_*.zip"), reverse=True)[20:]:
    try:
      old_z.unlink()
    except Exception:
      pass
  return zip_path


def save_asset_to_vault(
    title: str,
    asset_type: str,
    genre_or_format: str,
    duration_sec: int,
    content_bytes: bytes | None = None,
    extension: str = "wav",
    script_text: str = "",
    prompts_bundle: str = "",
) -> dict[str, Any]:
  data = init_vault()
  asset_id = f"BASA-{uuid.uuid4().hex[:10].upper()}"
  timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
  safe_title = "".join(
      c if c.isalnum() or c in ("-", "_") else "_" for c in title
  )[:40]

  file_rel_path = None
  if content_bytes is not None:
    file_name = f"{timestamp}_{safe_title}_{asset_id}.{extension.lstrip('.')}"
    full_path = MEDIA_DIR / file_name
    full_path.write_bytes(content_bytes)
    file_rel_path = str(full_path)

  record = {
      "id": asset_id,
      "title": title,
      "type": asset_type,
      "genre_or_format": genre_or_format,
      "duration_sec": int(duration_sec),
      "created_at": datetime.now().isoformat(),
      "owner_user": st.session_state.get("active_user", "Invitado Libre"),
      "device": st.session_state.get("active_device", "Celular"),
      "file_path": file_rel_path,
      "extension": extension,
      "script_text": script_text,
      "prompts_bundle": prompts_bundle,
  }
  data["assets"].insert(0, record)
  save_vault_data_safe(data, auto_export=True, reason=f"Activo: {title}")
  return record


def load_releases_log() -> list[dict[str, Any]]:
  init_dirs()
  if not RELEASES_FILE.exists():
    RELEASES_FILE.write_text("[]", encoding="utf-8")
    return []
  try:
    d = json.loads(RELEASES_FILE.read_text(encoding="utf-8"))
    return d if isinstance(d, list) else []
  except Exception:
    return []


def save_release_record(record: dict[str, Any]) -> None:
  logs = load_releases_log()
  logs.insert(0, record)
  RELEASES_FILE.write_text(
      json.dumps(logs, indent=2, ensure_ascii=False), encoding="utf-8"
  )


# ==============================================================================
# MOTOR DE AUDIO CON RESPALDO NATIVO (FUNCIONA CON O SIN PYDUB)
# ==============================================================================
def _pack_pcm16_wav(samples_mono: np.ndarray, sample_rate: int = 44100) -> bytes:
  clipped = np.clip(samples_mono, -0.85, 0.85)
  pcm16 = (clipped * 32767.0).astype(np.int16)
  stereo = np.column_stack((pcm16, pcm16)).tobytes()
  num_channels = 2
  bits_per_sample = 16
  byte_rate = sample_rate * num_channels * bits_per_sample // 8
  block_align = num_channels * bits_per_sample // 8
  data_size = len(stereo)
  header = struct.pack(
      "<4sI4s4sIHHIIHH4sI",
      b"RIFF",
      36 + data_size,
      b"WAVE",
      b"fmt ",
      16,
      1,
      num_channels,
      sample_rate,
      byte_rate,
      block_align,
      bits_per_sample,
      b"data",
      data_size,
  )
  return header + stereo


def generate_pulse_bed_wav(
    duration_sec: int, bpm: int = 132, sample_rate: int = 44100
) -> bytes:
  duration_sec = max(5, min(int(duration_sec), 1800))
  total_samples = duration_sec * sample_rate
  t = np.arange(total_samples, dtype=np.float32) / sample_rate

  beat_freq = max(0.5, bpm / 60.0)
  beat_phase = (t * beat_freq) % 1.0
  kick_env = np.exp(-beat_phase * 14.0)
  kick_freq = 55.0 + 65.0 * np.exp(-beat_phase * 18.0)
  kick = 0.22 * kick_env * np.sin(2.0 * np.pi * kick_freq * t)

  pad = (
      0.06 * np.sin(2.0 * np.pi * 220.0 * t)
      + 0.05 * np.sin(2.0 * np.pi * 277.18 * t)
      + 0.05 * np.sin(2.0 * np.pi * 329.63 * t)
  )
  fade_in = np.minimum(1.0, t / 1.5)
  fade_out = np.minimum(1.0, (duration_sec - t) / 2.0)
  return _pack_pcm16_wav((kick + pad) * fade_in * fade_out, sample_rate)


def stitch_audio_segments(
    segments_bytes: list[tuple[str, bytes]],
    crossfade_ms: int = 800,
    target_duration_sec: int | None = None,
) -> tuple[bytes, int]:
  if not segments_bytes:
    raise ValueError("No hay segmentos para unir.")

  if PYDUB_AVAILABLE and AudioSegment is not None:
    loaded = []
    for _, raw in segments_bytes:
      seg = AudioSegment.from_file(io.BytesIO(raw))
      seg = seg.set_channels(2).set_frame_rate(44100)
      loaded.append(seg)
    combined = loaded[0]
    for nxt in loaded[1:]:
      cf = max(0, min(crossfade_ms, len(combined) // 2, len(nxt) // 2))
      combined = combined.append(nxt, crossfade=cf)
    if target_duration_sec and target_duration_sec > 0:
      target_ms = int(target_duration_sec * 1000)
      while len(combined) < target_ms:
        faltante = target_ms - len(combined)
        trozo = combined[: min(len(combined), faltante + 1500)]
        cf = max(0, min(crossfade_ms, len(combined) // 2, len(trozo) // 2))
        combined = combined.append(trozo, crossfade=cf)
      combined = combined[:target_ms]
    buf = io.BytesIO()
    combined.export(buf, format="wav")
    return buf.getvalue(), max(1, math.ceil(len(combined) / 1000.0))

  # Respaldo nativo sin pydub (empalme directo de frames PCM WAV o extensión por repetición)
  all_frames = bytearray()
  sample_rate = 44100
  for _, raw in segments_bytes:
    try:
      with io.BytesIO(raw) as bio:
        import wave

        with wave.open(bio, "rb") as wf:
          sample_rate = wf.getframerate() or 44100
          n_ch = wf.getnchannels()
          raw_pcm = wf.readframes(wf.getnframes())
          arr = np.frombuffer(raw_pcm, dtype=np.int16).astype(np.float32) / 32767.0
          if n_ch > 1:
            arr = arr.reshape(-1, n_ch).mean(axis=1)
          all_frames.extend(_pack_pcm16_wav(arr, sample_rate)[44:])
    except Exception:
      continue

  if not all_frames:
    dur = target_duration_sec or 30
    return generate_pulse_bed_wav(dur, 120, sample_rate), dur

  arr_total = (
      np.frombuffer(bytes(all_frames), dtype=np.int16).astype(np.float32) / 32767.0
  )
  # Promediar pares estéreo a mono de trabajo
  if len(arr_total) >= 2:
    arr_mono = arr_total[::2]
  else:
    arr_mono = arr_total

  if target_duration_sec and target_duration_sec > 0:
    wanted_len = int(target_duration_sec * sample_rate)
    if len(arr_mono) < wanted_len and len(arr_mono) > 0:
      reps = math.ceil(wanted_len / len(arr_mono))
      arr_mono = np.tile(arr_mono, reps)[:wanted_len]
    elif len(arr_mono) > wanted_len:
      arr_mono = arr_mono[:wanted_len]

  out_wav = _pack_pcm16_wav(arr_mono, sample_rate)
  return out_wav, max(1, int(round(len(arr_mono) / sample_rate)))


def create_scene_poster_png(
    project_title: str,
    episode_label: str,
    scene_title: str,
    visual_prompt: str,
    width: int = 1280,
    height: int = 720,
) -> bytes:
  img = Image.new("RGB", (width, height), color=(14, 18, 32))
  draw = ImageDraw.Draw(img)
  draw.rectangle([0, 0, width, 70], fill=(8, 10, 18))
  draw.rectangle([0, height - 85, width, height], fill=(8, 10, 18))
  draw.line([(40, 85), (width - 40, 85)], fill=(212, 175, 55), width=2)
  font_title = ImageFont.load_default()
  draw.text(
      (48, 28),
      f"BASA STUDIO VIGILANTE  |  {project_title}",
      fill=(245, 208, 97),
      font=font_title,
  )
  draw.text(
      (48, 105),
      f"{episode_label} — {scene_title}",
      fill=(255, 255, 255),
      font=font_title,
  )
  words = visual_prompt.split()
  lines, cur = [], ""
  for w in words:
    test = f"{cur} {w}".strip()
    if len(test) > 85:
      lines.append(cur)
      cur = w
    else:
      cur = test
  if cur:
    lines.append(cur)
  y = 160
  for ln in lines[:12]:
    draw.text((48, y), ln, fill=(210, 220, 235), font=font_title)
    y += 26
  buf = io.BytesIO()
  img.save(buf, format="PNG")
  return buf.getvalue()


def render_video_mp4(audio_wav_bytes: bytes, image_png_bytes: bytes) -> tuple[bytes, str]:
  tmp_dir = VAULT_DIR / "tmp_render"
  tmp_dir.mkdir(parents=True, exist_ok=True)
  uid = uuid.uuid4().hex[:8]
  img_p = tmp_dir / f"f_{uid}.png"
  aud_p = tmp_dir / f"a_{uid}.wav"
  out_p = tmp_dir / f"v_{uid}.mp4"
  img_p.write_bytes(image_png_bytes)
  aud_p.write_bytes(audio_wav_bytes)
  cmd = [
      "ffmpeg",
      "-y",
      "-loop",
      "1",
      "-i",
      str(img_p),
      "-i",
      str(aud_p),
      "-c:v",
      "libx264",
      "-tune",
      "stillimage",
      "-pix_fmt",
      "yuv420p",
      "-c:a",
      "aac",
      "-b:a",
      "192k",
      "-shortest",
      str(out_p),
  ]
  try:
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0 or not out_p.exists():
      return b"", f"FFmpeg no disponible en este contenedor ({proc.stderr[-180:]})."
    return out_p.read_bytes(), "OK"
  finally:
    for p in (img_p, aud_p, out_p):
      if p.exists():
        try:
          p.unlink()
        except Exception:
          pass


# ==============================================================================
# MÓDULOS AUTÓNOMOS PLUG-AND-PLAY & GITHUB ISSUES
# ==============================================================================
def validate_python_code(code: str) -> tuple[bool, str]:
  if not code.strip():
    return False, "El código está vacío."
  try:
    ast.parse(code)
    return True, "Sintaxis Python válida (AST verificado)."
  except SyntaxError as exc:
    return False, f"Error de sintaxis en línea {exc.lineno}: {exc.msg}"


def compile_and_register_module(
    name: str, code: str, source_ref: str = "Local / Issue"
) -> tuple[bool, str]:
  ok, msg = validate_python_code(code)
  if not ok:
    return False, msg
  ns: dict[str, Any] = {"__name__": f"basa_mod_{uuid.uuid4().hex[:8]}"}
  try:
    exec(compile(code, filename=f"{name}.py", mode="exec"), ns)
  except Exception as exc:
    return False, f"Error al ejecutar módulo: {exc}"

  callables = [k for k, v in ns.items() if callable(v) and not k.startswith("_")]
  data = init_vault()
  entry = {
      "id": f"MOD-{uuid.uuid4().hex[:8].upper()}",
      "name": name.strip() or "Modulo_Autonomo",
      "source_ref": source_ref,
      "code": code,
      "valid_syntax": True,
      "callables": callables,
      "updated_at": datetime.now().isoformat(),
  }
  existing = [m for m in data.get("autonomous_modules", []) if m.get("name") != entry["name"]]
  existing.insert(0, entry)
  data["autonomous_modules"] = existing
  save_vault_data_safe(data, auto_export=True, reason=f"Módulo: {entry['name']}")

  st.session_state.setdefault("loaded_callables", {})
  for fn_name in callables:
    st.session_state["loaded_callables"][f"{entry['name']}.{fn_name}"] = ns[fn_name]

  return True, f"Módulo '{entry['name']}' conectado ({', '.join(callables) or 'sin funciones'})."


def run_registered_callable(fq_name: str, payload: dict[str, Any]) -> tuple[bool, Any]:
  fn: Callable[..., Any] | None = st.session_state.get("loaded_callables", {}).get(fq_name)
  if fn is None:
    for m in init_vault().get("autonomous_modules", []):
      compile_and_register_module(m.get("name", "Mod"), m.get("code", ""), m.get("source_ref", ""))
      fn = st.session_state.get("loaded_callables", {}).get(fq_name)
      if fn is not None:
        break
  if fn is None:
    return False, f"Función '{fq_name}' no encontrada."
  try:
    return True, fn(payload)
  except TypeError:
    try:
      return True, fn()
    except Exception as exc:
      return False, str(exc)
  except Exception as exc:
    return False, str(exc)


def parse_github_issue_input(raw_input: str) -> tuple[str, str, int] | None:
  txt = raw_input.strip()
  m_url = re.search(r"github\.com/([^/\s]+)/([^/\s]+)/issues/(\d+)", txt, re.IGNORECASE)
  if m_url:
    return m_url.group(1), m_url.group(2).removesuffix(".git"), int(m_url.group(3))
  m_short = re.match(r"^([^/\s]+)/([^\s#]+)#(\d+)$", txt)
  if m_short:
    return m_short.group(1), m_short.group(2), int(m_short.group(3))
  return None


def fetch_github_issue_code(owner: str, repo: str, issue_number: int) -> tuple[bool, str, str, str]:
  api_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}"
  req = urllib.request.Request(
      api_url,
      headers={"User-Agent": "BASA-Vigilante", "Accept": "application/vnd.github+json"},
  )
  try:
    with urllib.request.urlopen(req, timeout=12) as resp:
      payload = json.loads(resp.read().decode("utf-8"))
  except urllib.error.HTTPError as e:
    return False, "", "", f"Error HTTP {e.code} en GitHub."
  except Exception as e:
    return False, "", "", f"Error de red: {e}"
  title = payload.get("title", f"Issue #{issue_number}")
  body = payload.get("body") or ""
  blocks = re.findall(r"```(?:python|py)?\s*\n(.*?)```", body, flags=re.DOTALL | re.IGNORECASE)
  code = "\n\n".join(b.strip() for b in blocks if b.strip()) if blocks else body.strip()
  if not code:
    return False, title, "", "El issue no contiene código."
  return True, title, code, "OK"


# ==============================================================================
# INICIALIZACIÓN DE SESIÓN, VIGILANTE Y BARRA LATERAL
# ==============================================================================
vault_data = init_vault()
users_data = load_users_vault()
assets: list[dict[str, Any]] = vault_data.get("assets", [])
modules: list[dict[str, Any]] = vault_data.get("autonomous_modules", [])
station_cfg: dict[str, Any] = vault_data.get("station_config", {})

st.session_state.setdefault("active_user", "Invitado Libre")
st.session_state.setdefault("active_device", "Celular")
st.session_state.setdefault("access_mode", "LIBRE")
st.session_state.setdefault("admin_unlocked", False)

with st.sidebar:
  st.header("🛡️ Vigilante Autónomo")
  vigilante_3s = st.checkbox(
      "Vigilante / Refresco cada 3 segundos",
      value=False,
      help="Refresca el estado y verifica integridad de datos cada 3s cuando está activo.",
  )
  st.caption(
      f"Motor pydub: {'✅ Activo' if PYDUB_AVAILABLE else '⚠️ Respaldo nativo WAV (sin caída)'}"
  )
  st.text_input("Licencia Universal Libre", value="BASA-UNIV-C6D4D15AABCE")

  st.divider()
  st.subheader("📱 Dispositivo & Acceso")
  selected_device = st.selectbox(
      "Dispositivo actual",
      ["Celular", "Laptop", "Tablet", "PC"],
      index=["Celular", "Laptop", "Tablet", "PC"].index(
          st.session_state.get("active_device", "Celular")
      ),
  )
  st.session_state["active_device"] = selected_device

  access_choice = st.radio(
      "Modo de entrada",
      ["Entrar Libre (Sin registro)", "Registrar / Vincular Cuenta"],
      index=0 if st.session_state.get("access_mode") == "LIBRE" else 1,
  )
  if access_choice.startswith("Entrar Libre"):
    st.session_state["access_mode"] = "LIBRE"
    st.session_state["active_user"] = "Invitado Libre"
  else:
    st.session_state["access_mode"] = "REGISTRADA"
    acc_user = st.text_input(
        "Usuario / Correo / Alias", value=st.session_state.get("active_user", "")
    )
    acc_key = st.text_input("Clave privada (oculta)", type="password")
    save_private_key = st.checkbox(
        "Guardar clave en historial privado (Admin/Delegado)", value=True
    )
    if st.button("🔗 Vincular y Cargar Automáticamente"):
      clean_u = acc_user.strip() or "Usuario_Vinculado"
      users_map = users_data.setdefault("users", {})
      existing_u = users_map.get(clean_u, {})
      encoded_k = (
          obfuscate_key(acc_key.strip())
          if (acc_key.strip() and save_private_key)
          else existing_u.get("encoded_key", "")
      )
      users_map[clean_u] = {
          "username": clean_u,
          "encoded_key": encoded_k,
          "key_saved": bool(encoded_k),
          "last_device": selected_device,
          "updated_at": datetime.now().isoformat(),
      }
      save_users_vault(users_data)
      st.session_state["active_user"] = clean_u
      log_device_event(clean_u, selected_device, "Vinculación automática", "REGISTRADA")
      exp_zip = auto_export_bundle(f"Vinculación: {clean_u}", clean_u, selected_device)
      st.session_state["last_auto_export"] = str(exp_zip)
      st.success(f"Cuenta '{clean_u}' enlazada.")
      st.rerun()

  st.divider()
  st.subheader("🎛️ Duración Extendida")
  duracion_extendida = st.slider(
      "Duracion pista libre (seg)", min_value=10, max_value=600, value=120, step=10
  )
  st.caption(
      f"Tiempo activo: **{duracion_extendida // 60}:{duracion_extendida % 60:02d}** ({duracion_extendida}s)"
  )
  crossfade_ms = st.slider("Crossfade entre tomas (ms)", 0, 3000, 800, 100)

  last_exp = st.session_state.get("last_auto_export")
  if last_exp and Path(last_exp).exists():
    st.download_button(
        "⬇️ Descargar Último Export (.ZIP)",
        data=Path(last_exp).read_bytes(),
        file_name=Path(last_exp).name,
        mime="application/zip",
    )

# ==============================================================================
# ENCABEZADO Y KPIs
# ==============================================================================
total_assets = len(assets)
total_audios = sum(1 for a in assets if a.get("type") == "audio")
total_scripts_videos = sum(1 for a in assets if a.get("type") in ("script", "video"))

st.title("🤖 BASA Universal AI Studio · Produccion Online")
st.caption(
    f"Usuario: **{st.session_state.get('active_user')}** · Dispositivo: **{st.session_state.get('active_device')}** · Base protegida con autorecuperación"
)

k1, k2, k3 = st.columns(3)
k1.metric("Total Activos en Boveda", total_assets)
k2.metric("Audios / Canciones", total_audios)
k3.metric("Prompts / Scripts", total_scripts_videos)

st.divider()

# ==============================================================================
# PESTAÑAS PRINCIPALES
# ==============================================================================
(
    tab_music,
    tab_cinema,
    tab_station,
    tab_publish,
    tab_modules,
    tab_security_devices,
    tab_migrate,
    tab_vault,
) = st.tabs([
    "🎹 Generar Musica & Multi-Prompt",
    "🎬 Películas, Series & Video",
    "📡 Emisora Autónoma BASA",
    "🚀 Publicar en Redes Musicales",
    "🧩 Módulos Autónomos & GitHub",
    "🔐 Claves Privadas & Dispositivos",
    "🌐 Migrar Links y Archivos (Suno/Mureka/ChatGPT)",
    "📚 Boveda Multimedia",
])

with tab_music:
  col_l, col_r = st.columns([1.2, 1])
  with col_l:
    project_title = st.text_input("Titulo del proyecto", value="Himno de Navidad en Quisqueya")
    genre = st.selectbox(
        "Genero / Ritmo Mundial",
        [
            "Merengue Tipico (Perico Ripiao)",
            "Merengue de Calle / Mambo",
            "Bachata Dominicana",
            "Salsa Clásica",
            "Balada / Bolero",
            "Score Cinematográfico / Orquestal",
            "Dembow / Urbano",
        ],
    )
    bpm = st.number_input("BPM", min_value=50, max_value=220, value=132, step=1)
    master_prompt = st.text_area("Escribe tu idea, letra o prompt maestro", height=190)
    uploaded_segments = st.file_uploader(
        "Opcional: sube pistas o escenas para unir",
        type=["wav", "mp3", "ogg", "m4a"],
        accept_multiple_files=True,
    )

    b1, b2 = st.columns(2)
    gen_btn = b1.button("🎵 Generar Audio + Prompts Multi-IA", type="primary")
    auto_btn = b2.button("⚡ CICLO AUTÓNOMO 100/100 (Audio + Prompts + ZIP)")

    if gen_btn or auto_btn:
      if uploaded_segments:
        pairs = [(f.name, f.getvalue()) for f in uploaded_segments]
        wav_bytes, real_sec = stitch_audio_segments(
            pairs, crossfade_ms=crossfade_ms, target_duration_sec=duracion_extendida
        )
      else:
        base_wav = generate_pulse_bed_wav(min(duracion_extendida, 60), bpm=bpm)
        wav_bytes, real_sec = stitch_audio_segments(
            [("base", base_wav)],
            crossfade_ms=crossfade_ms,
            target_duration_sec=duracion_extendida,
        )

      prompts_pack = (
          f"=== SUNO ===\nStyle: {genre}, {bpm} BPM, {real_sec}s\n{master_prompt}\n\n"
          f"=== GEMINI MUSIC ===\nTrack: {genre}, {bpm} BPM, {real_sec}s\n{master_prompt}\n\n"
          f"=== MUREKA AI ===\nGenre: {genre} | BPM: {bpm} | Duration: {real_sec}s\n{master_prompt}"
      )
      saved_a = save_asset_to_vault(
          title=project_title,
          asset_type="audio",
          genre_or_format=f"{genre} ({bpm} BPM)",
          duration_sec=real_sec,
          content_bytes=wav_bytes,
          extension="wav",
          script_text=master_prompt,
          prompts_bundle=prompts_pack,
      )
      st.session_state["last_audio"] = saved_a

      if auto_btn:
        save_asset_to_vault(
            title=f"Prompts & Script - {project_title}",
            asset_type="script",
            genre_or_format=f"Pack Multi-IA ({genre})",
            duration_sec=real_sec,
            content_bytes=None,
            extension="txt",
            script_text=master_prompt,
            prompts_bundle=prompts_pack,
        )
        kit_txt = f"TÍTULO: {project_title}\nGÉNERO: {genre} ({bpm} BPM)\nDURACIÓN: {real_sec}s\n\n{master_prompt}"
        save_release_record({
            "id": f"REL-{uuid.uuid4().hex[:8].upper()}",
            "title": project_title,
            "artist": "BASA Productions",
            "platforms": ["YouTube / YouTube Music", "Spotify", "SoundCloud"],
            "created_at": datetime.now().isoformat(),
            "kit": kit_txt,
        })
        zbuf = io.BytesIO()
        safe = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in project_title)[:35]
        with zipfile.ZipFile(zbuf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
          zf.writestr(f"{safe}.wav", wav_bytes)
          zf.writestr(f"{safe}_letra_prompts.txt", prompts_pack)
          zf.writestr(f"{safe}_release_kit.txt", kit_txt)
        st.session_state["ready_upload_zip"] = zbuf.getvalue()
        st.session_state["ready_upload_name"] = f"{safe}_100_100.zip"

      st.success(f"¡Completado ({real_sec}s) y guardado sin corrupción!")
      st.rerun()

  with col_r:
    st.subheader("Salida de Audio y Prompts")
    if st.session_state.get("ready_upload_zip"):
      st.download_button(
          "📦 Descargar Paquete 100/100 (.ZIP)",
          data=st.session_state["ready_upload_zip"],
          file_name=st.session_state.get("ready_upload_name", "basa_100_100.zip"),
          mime="application/zip",
          type="primary",
      )
    last_audio = st.session_state.get("last_audio")
    if last_audio and last_audio.get("file_path"):
      p = Path(last_audio["file_path"])
      if p.exists():
        raw_aud = p.read_bytes()
        st.caption(
            f"0:00 / {last_audio['duration_sec'] // 60}:{last_audio['duration_sec'] % 60:02d} — {last_audio['title']}"
        )
        st.audio(raw_aud, format="audio/wav")
        st.download_button(
            "⬇️ Descargar Audio (.WAV)",
            data=raw_aud,
            file_name=f"{last_audio['id']}.wav",
            mime="audio/wav",
        )
      st.text_area("Prompts listos para copiar:", value=last_audio.get("prompts_bundle", ""), height=240)

with tab_cinema:
  st.subheader("🎬 Estudio de Películas, Series y Ensamblaje de Video")
  c1, c2, c3 = st.columns(3)
  cine_title = c1.text_input("Título de Película / Serie", value="El Lápiz Pesa Más que el Pico")
  cine_ep = c2.text_input("Temporada / Episodio", value="T01 · E01")
  cine_scene = c3.text_input("Escena / Secuencia", value="Escena 01 - De la Obra al Escritorio")
  cine_dur = st.slider("Duración de escena (seg)", 10, 600, max(30, min(duracion_extendida, 120)), 10)
  cine_script = st.text_area("Guion / Diálogo", height=110, value="NARRADOR: Cada paso construye un nuevo horizonte.")
  cine_vprompt = st.text_area("Prompt Visual Cinematográfico", height=100, value="Cinematic wide shot, golden hour, 35mm film.")

  if st.button("🎥 Renderizar Escena (.MP4 / Storyboard)", type="primary"):
    wav_c = generate_pulse_bed_wav(cine_dur, 110)
    png_c = create_scene_poster_png(cine_title, cine_ep, cine_scene, f"{cine_vprompt}\n\n{cine_script}")
    mp4_b, msg_v = render_video_mp4(wav_c, png_c)
    if mp4_b:
      saved_v = save_asset_to_vault(
          f"{cine_title} - {cine_scene}", "video", f"MP4 ({cine_ep})", cine_dur, mp4_b, "mp4", cine_script, cine_vprompt
      )
      st.video(mp4_b)
      st.download_button("⬇️ Descargar Video (.MP4)", data=mp4_b, file_name=f"{saved_v['id']}.mp4", mime="video/mp4")
    else:
      st.info(msg_v)
      save_asset_to_vault(
          f"{cine_title} - {cine_scene}", "script", f"Storyboard ({cine_ep})", cine_dur, png_c, "png", cine_script, cine_vprompt
      )
      st.image(png_c, caption="Storyboard guardado en bóveda.")
    st.rerun()

with tab_station:
  st.subheader("📡 Emisora Autónoma BASA")
  st_name = st.text_input("Nombre de la Emisora", value=station_cfg.get("station_name", "BASA Radio Autónoma 24/7"))
  auto_perm = st.checkbox("Permiso Autónomo Full (catálogo propio)", value=bool(station_cfg.get("autonomous_permission", True)))
  if st.button("📻 Guardar Emisora"):
    d_now = init_vault()
    d_now["station_config"] = {"station_name": st_name, "autonomous_permission": auto_perm, "auto_advance": True, "active_track_id": None}
    save_vault_data_safe(d_now, auto_export=True, reason="Emisora actualizada")
    st.success("Emisora guardada.")
    st.rerun()

  aud_list = [a for a in assets if a.get("type") == "audio" and a.get("file_path")]
  if aud_list:
    sel = st.selectbox("Pista al aire", options=list(range(len(aud_list))), format_func=lambda i: f"{aud_list[i].get('title')} ({aud_list[i].get('duration_sec', 0)}s)")
    tp = Path(aud_list[sel]["file_path"])
    if tp.exists():
      st.audio(tp.read_bytes(), format=f"audio/{aud_list[sel].get('extension', 'wav')}")

with tab_publish:
  st.subheader("🚀 Publicación y Distribución Musical")
  pub_title = st.text_input("Título oficial", value="Himno de Navidad en Quisqueya")
  pub_artist = st.text_input("Artista / Sello", value="BASA Productions")
  pub_plats = st.multiselect("Plataformas", ["YouTube / YouTube Music", "Spotify", "SoundCloud", "TikTok / Reels"], default=["YouTube / YouTube Music", "Spotify", "SoundCloud"])
  pub_notes = st.text_area("Letra / Créditos", height=120, value="Producido en BASA Universal AI Studio.")
  kit = f"TÍTULO: {pub_title}\nARTISTA: {pub_artist}\nPLATAFORMAS: {', '.join(pub_plats)}\n\n{pub_notes}"
  st.text_area("Release Kit:", value=kit, height=140)
  c_l1, c_l2, c_l3 = st.columns(3)
  c_l1.link_button("▶️ YouTube Studio", "https://studio.youtube.com/")
  c_l2.link_button("🎧 Spotify for Artists", "https://artists.spotify.com/")
  c_l3.link_button("☁️ SoundCloud", "https://soundcloud.com/upload")
  if st.button("✅ Registrar Lanzamiento", type="primary"):
    save_release_record({"id": f"REL-{uuid.uuid4().hex[:8].upper()}", "title": pub_title, "artist": pub_artist, "platforms": pub_plats, "created_at": datetime.now().isoformat(), "kit": kit})
    st.success("Registrado.")
    st.rerun()

with tab_modules:
  st.subheader("🧩 Módulos Autónomos & GitHub Issues")
  issue_in = st.text_input("Issue de GitHub (URL o owner/repo#num)", placeholder="https://github.com/usuario/repo/issues/1")
  st.session_state.setdefault("mod_code_buf", "def estado_basa(ctx: dict):\n    return {'ok': True, 'user': ctx.get('user', 'Libre')}\n")
  st.session_state.setdefault("mod_name_buf", "Modulo_Autonomo_BASA")
  if st.button("📥 Extraer de GitHub Issue"):
    parsed = parse_github_issue_input(issue_in)
    if not parsed:
      st.error("Formato inválido.")
    else:
      ok, ititle, ctxt, emsg = fetch_github_issue_code(*parsed)
      if ok:
        st.session_state["mod_code_buf"] = ctxt
        st.session_state["mod_name_buf"] = f"{parsed[1]}_Issue_{parsed[2]}"
        st.success(f"Extraído: {ititle}")
      else:
        st.error(emsg)

  m_name_in = st.text_input("Nombre del módulo", key="mod_name_buf")
  m_code_in = st.text_area("Código Python:", key="mod_code_buf", height=200)
  ok_v, msg_v = validate_python_code(m_code_in)
  st.success(f"✅ {msg_v}") if ok_v else st.error(f"❌ {msg_v}")
  if st.button("🔌 Validar y Conectar Módulo", type="primary"):
    ok_r, msg_r = compile_and_register_module(m_name_in, m_code_in, issue_in or "Local")
    st.success(msg_r) if ok_r else st.error(msg_r)
    if ok_r:
      st.rerun()

  for m in modules:
    mn = m.get("name", "Mod")
    fns = m.get("callables", [])
    with st.expander(f"🧩 {mn} · Funciones: {', '.join(fns) or 'ninguna'}"):
      st.code(m.get("code", ""), language="python")
      if fns:
        cfn = st.selectbox("Función", options=fns, key=f"s_{m.get('id')}")
        if st.button("▶️ Ejecutar", key=f"r_{m.get('id')}"):
          _, out_c = run_registered_callable(f"{mn}.{cfn}", {"user": st.session_state.get("active_user")})
          st.info(str(out_c))

with tab_security_devices:
  st.subheader("🔐 Claves Privadas (Admin/Delegados) & Dispositivos")
  col1, col2 = st.columns(2)
  with col1:
    pin_in = st.text_input("Clave de autorización (Admin / Delegado)", type="password")
    if st.button("🔓 Desbloquear"):
      if pin_in == ADMIN_MASTER_PIN:
        st.session_state["admin_unlocked"] = True
        st.success("Desbloqueado.")
      else:
        st.error("Clave incorrecta.")
    if st.session_state.get("admin_unlocked"):
      for uname, uinfo in users_data.get("users", {}).items():
        with st.expander(f"Usuario: {uname} ({uinfo.get('last_device', 'N/D')})"):
          st.write(f"Clave guardada: {'Sí' if uinfo.get('key_saved') else 'No'}")
          if uinfo.get("key_saved"):
            st.code(reveal_key(uinfo.get("encoded_key", "")), language="text")
    else:
      st.info("Claves ocultas por seguridad.")
  with col2:
    st.markdown("### 📱 Historial por Dispositivo")
    for ev in users_data.get("device_history", [])[:25]:
      st.write(f"• **{ev.get('device')}** — *{ev.get('user')}* · {ev.get('action')} (`{ev.get('timestamp', '')[:19]}`)")

with tab_migrate:
  st.subheader("🌐 Migrar Links y Archivos")
  mig_t = st.text_input("Nombre", value="Pista Migrada")
  mig_u = st.text_input("URL", value="https://suno.com/discover")
  mig_f = st.file_uploader("Archivos", type=["wav", "mp3", "mp4", "png", "jpg", "txt", "md"], accept_multiple_files=True)
  if st.button("📥 Importar"):
    if mig_f:
      for f in mig_f:
        ext = f.name.split(".")[-1].lower() if "." in f.name else "bin"
        at = "audio" if ext in ("wav", "mp3", "ogg", "m4a") else ("video" if ext in ("mp4", "mov") else "script")
        save_asset_to_vault(f"{mig_t} ({f.name})", at, "Migración", duracion_extendida, f.getvalue(), ext, "", f"URL: {mig_u}")
    else:
      save_asset_to_vault(mig_t, "script", "Enlace", duracion_extendida, None, "txt", f"URL: {mig_u}", mig_u)
    st.success("Importado y respaldado.")
    st.rerun()

with tab_vault:
  st.subheader("📚 Boveda Multimedia")
  if not assets:
    st.info("Aún no hay activos en la bóveda.")
  else:
    users_opts = ["Todos"] + sorted({a.get("owner_user") or "Invitado Libre" for a in assets})
    devs_opts = ["Todos"] + sorted({a.get("device") or "No especificado" for a in assets})
    fc1, fc2, fc3 = st.columns(3)
    fu = fc1.selectbox("Usuario", users_opts)
    fd = fc2.selectbox("Dispositivo", devs_opts)
    ft = fc3.selectbox("Tipo", ["Todos", "audio", "video", "script"])
    filtrados = [
        it for it in assets
        if (fu == "Todos" or (it.get("owner_user") or "Invitado Libre") == fu)
        and (fd == "Todos" or (it.get("device") or "No especificado") == fd)
        and (ft == "Todos" or it.get("type") == ft)
    ]
    st.caption(f"Mostrando **{len(filtrados)}** de **{len(assets)}** activos.")
    for item in filtrados:
      with st.expander(f"[{item.get('type', '').upper()}] {item.get('title')} — {item.get('duration_sec', 0)}s ({item.get('id')})"):
        st.write(f"**Formato:** {item.get('genre_or_format')} | **Usuario:** {item.get('owner_user', 'Invitado Libre')} | **Dispositivo:** {item.get('device', 'No especificado')}")
        if item.get("script_text"):
          st.text_area("Guion / Letra", value=item["script_text"], height=90, key=f"sc_{item['id']}")
        if item.get("prompts_bundle"):
          st.text_area("Prompts / Enlace", value=item["prompts_bundle"], height=90, key=f"pr_{item['id']}")
        fp = item.get("file_path")
        if fp and Path(fp).exists():
          raw_m = Path(fp).read_bytes()
          if item.get("type") == "audio":
            st.audio(raw_m)
          elif item.get("type") == "video":
            st.video(raw_m)
          elif item.get("extension") in ("png", "jpg", "jpeg"):
            st.image(raw_m)
          st.download_button("⬇️ Descargar", data=raw_m, file_name=Path(fp).name, key=f"dl_{item['id']}")

if vigilante_3s:
  time.sleep(3)
  st.rerun()
