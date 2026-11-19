from __future__ import annotations

import ast
import base64
import hashlib
import io
import json
import math
import re
import shutil
import struct
import subprocess
import urllib.error
import urllib.request
import uuid
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

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

ADMIN_MASTER_PIN = "BASA-ADMIN-2026"


def init_dirs() -> None:
  MEDIA_DIR.mkdir(parents=True, exist_ok=True)
  BACKUP_DIR.mkdir(parents=True, exist_ok=True)
  AUTO_EXPORT_DIR.mkdir(parents=True, exist_ok=True)


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
        "device_history": [],
    }
    ACCOUNTS_FILE.write_text(
        json.dumps(base, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return base
  try:
    data = json.loads(ACCOUNTS_FILE.read_text(encoding="utf-8"))
    data.setdefault("delegates", ["pedro.baldera"])
    data.setdefault("users", {})
    data.setdefault("device_history", [])
    return data
  except Exception:
    return {"delegates": ["pedro.baldera"], "users": {}, "device_history": []}


def save_users_vault(data: dict[str, Any]) -> None:
  init_dirs()
  ACCOUNTS_FILE.write_text(
      json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
  )


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
    username: str,
    device_type: str,
    action: str,
    access_mode: str,
) -> None:
  users_data = load_users_vault()
  users_data["device_history"].insert(
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
  users_data["device_history"] = users_data["device_history"][:200]
  save_users_vault(users_data)


def build_upload_ready_zip(
    title: str,
    media_bytes: bytes | None,
    media_ext: str,
    script_text: str,
    prompts_bundle: str,
    release_kit: str,
) -> bytes:
  """Crea un ZIP listo para subir/compartir con audio/video, letra/guion, prompts y release kit."""
  buf = io.BytesIO()
  safe = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in title)[:35]
  with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
    if media_bytes:
      zf.writestr(f"{safe}.{media_ext.lstrip('.')}", media_bytes)
    zf.writestr(f"{safe}_letra_guion.txt", script_text or "")
    zf.writestr(f"{safe}_prompts_multi_ia.txt", prompts_bundle or "")
    zf.writestr(f"{safe}_release_kit.txt", release_kit or "")
  return buf.getvalue()


def auto_export_bundle(reason: str, username: str, device_type: str) -> Path:
  init_dirs()
  ts = datetime.now().strftime("%Y%m%d_%H%M%S")
  zip_path = AUTO_EXPORT_DIR / f"basa_auto_export_{ts}.zip"

  vault_obj = init_vault()
  users_obj = load_users_vault()
  sanitized_users = {
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
        json.dumps(sanitized_users, indent=2, ensure_ascii=False),
    )
    for asset in vault_obj.get("assets", [])[:25]:
      fpath = asset.get("file_path")
      if fpath:
        p = Path(fpath)
        if p.exists() and p.is_file():
          zf.write(p, arcname=f"media/{p.name}")

  exports = sorted(AUTO_EXPORT_DIR.glob("basa_auto_export_*.zip"), reverse=True)
  for old_z in exports[20:]:
    try:
      old_z.unlink()
    except Exception:
      pass

  return zip_path


def save_vault_data(
    data: dict[str, Any],
    auto_export: bool = True,
    reason: str = "Actualización de bóveda",
) -> None:
  init_dirs()
  INDEX_FILE.write_text(
      json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
  )
  ts = datetime.now().strftime("%Y%m%d_%H%M%S")
  shutil.copy2(INDEX_FILE, BACKUP_DIR / f"vault_index_{ts}.json")
  bkps = sorted(BACKUP_DIR.glob("vault_index_*.json"), reverse=True)
  for old_b in bkps[25:]:
    try:
      old_b.unlink()
    except Exception:
      pass

  if auto_export:
    active_u = st.session_state.get("active_user", "Invitado Libre")
    active_dev = st.session_state.get("active_device", "Celular")
    exp_path = auto_export_bundle(
        reason=reason, username=active_u, device_type=active_dev
    )
    st.session_state["last_auto_export"] = str(exp_path)


def save_asset_to_vault(
    title: str,
    asset_type: str,
    genre_or_format: str,
    duration_sec: int,
    content_bytes: bytes | None = None,
    extension: str = "wav",
    script_text: str = "",
    prompts_bundle: str = "",
    metadata: dict[str, Any] | None = None,
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
      "metadata": metadata or {},
  }
  data["assets"].insert(0, record)
  save_vault_data(
      data, auto_export=True, reason=f"Nuevo activo guardado: {title}"
  )
  return record


def load_releases_log() -> list[dict[str, Any]]:
  init_dirs()
  if not RELEASES_FILE.exists():
    RELEASES_FILE.write_text("[]", encoding="utf-8")
    return []
  try:
    return json.loads(RELEASES_FILE.read_text(encoding="utf-8"))
  except Exception:
    return []


def save_release_record(record: dict[str, Any]) -> None:
  logs = load_releases_log()
  logs.insert(0, record)
  RELEASES_FILE.write_text(
      json.dumps(logs, indent=2, ensure_ascii=False), encoding="utf-8"
  )


# ==============================================================================
# MÓDULOS AUTÓNOMOS, AUDIO EXTENDIDO Y VIDEO (.MP4)
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
    name: str, code: str, source_ref: str = "Manual / Issue"
) -> tuple[bool, str, dict[str, Any] | None]:
  ok, msg = validate_python_code(code)
  if not ok:
    return False, msg, None

  sandbox_ns: dict[str, Any] = {
      "__name__": f"basa_plugin_{uuid.uuid4().hex[:8]}",
  }
  try:
    exec(compile(code, filename=f"{name}.py", mode="exec"), sandbox_ns)
  except Exception as exc:
    return False, f"Error al cargar módulo: {exc}", None

  callables = [
      k for k, v in sandbox_ns.items() if callable(v) and not k.startswith("_")
  ]
  data = init_vault()
  mod_entry = {
      "id": f"MOD-{uuid.uuid4().hex[:8].upper()}",
      "name": name.strip() or "Modulo_Autonomo",
      "source_ref": source_ref,
      "code": code,
      "valid_syntax": True,
      "active": True,
      "callables": callables,
      "updated_at": datetime.now().isoformat(),
  }
  existing = data.get("autonomous_modules", [])
  filtered = [m for m in existing if m.get("name") != mod_entry["name"]]
  filtered.insert(0, mod_entry)
  data["autonomous_modules"] = filtered
  save_vault_data(
      data, auto_export=True, reason=f"Módulo registrado: {mod_entry['name']}"
  )

  st.session_state.setdefault("loaded_callables", {})
  for fn_name in callables:
    st.session_state["loaded_callables"][f"{mod_entry['name']}.{fn_name}"] = (
        sandbox_ns[fn_name]
    )

  return (
      True,
      f"Módulo '{mod_entry['name']}' conectado. Funciones: {', '.join(callables) or 'ninguna'}.",
      mod_entry,
  )


def run_registered_callable(
    fq_name: str, payload: dict[str, Any]
) -> tuple[bool, Any]:
  fn: Callable[..., Any] | None = st.session_state.get(
      "loaded_callables", {}
  ).get(fq_name)
  if fn is None:
    data = init_vault()
    for m in data.get("autonomous_modules", []):
      ok, _, _ = compile_and_register_module(
          m.get("name", "Modulo"), m.get("code", ""), m.get("source_ref", "")
      )
      if ok:
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
      return False, f"Error al ejecutar '{fq_name}': {exc}"
  except Exception as exc:
    return False, f"Error al ejecutar '{fq_name}': {exc}"


def parse_github_issue_input(raw_input: str) -> tuple[str, str, int] | None:
  txt = raw_input.strip()
  m_url = re.search(
      r"github\.com/([^/\s]+)/([^/\s]+)/issues/(\d+)", txt, re.IGNORECASE
  )
  if m_url:
    return m_url.group(1), m_url.group(2).removesuffix(".git"), int(m_url.group(3))
  m_short = re.match(r"^([^/\s]+)/([^\s#]+)#(\d+)$", txt)
  if m_short:
    return m_short.group(1), m_short.group(2), int(m_short.group(3))
  return None


def fetch_github_issue_code(
    owner: str, repo: str, issue_number: int
) -> tuple[bool, str, str, str]:
  api_url = (
      f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}"
  )
  req = urllib.request.Request(
      api_url,
      headers={
          "User-Agent": "BASA-Universal-AI-Studio",
          "Accept": "application/vnd.github+json",
      },
  )
  try:
    with urllib.request.urlopen(req, timeout=15) as resp:
      payload = json.loads(resp.read().decode("utf-8"))
  except urllib.error.HTTPError as e:
    return False, "", "", f"Error HTTP {e.code} al consultar GitHub."
  except Exception as e:
    return False, "", "", f"No se pudo conectar a GitHub: {e}"

  title = payload.get("title", f"Issue #{issue_number}")
  body = payload.get("body") or ""
  blocks = re.findall(
      r"```(?:python|py)?\s*\n(.*?)```", body, flags=re.DOTALL | re.IGNORECASE
  )
  extracted = (
      "\n\n".join(b.strip() for b in blocks if b.strip())
      if blocks
      else body.strip()
  )
  if not extracted:
    return False, title, "", "El issue no contiene código en su cuerpo."
  return True, title, extracted, "OK"


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
  mix = np.clip((kick + pad) * fade_in * fade_out, -0.85, 0.85)

  pcm16 = (mix * 32767.0).astype(np.int16)
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


def stitch_audio_segments(
    segments_bytes: list[tuple[str, bytes]],
    crossfade_ms: int = 800,
    target_duration_sec: int | None = None,
) -> tuple[bytes, int]:
  if not segments_bytes:
    raise ValueError("No hay segmentos para unir.")

  loaded: list[AudioSegment] = []
  for _, raw in segments_bytes:
    seg = AudioSegment.from_file(io.BytesIO(raw))
    seg = seg.set_channels(2).set_frame_rate(44100)
    loaded.append(seg)

  combined = loaded[0]
  for nxt in loaded[1:]:
    safe_cf = max(0, min(crossfade_ms, len(combined) // 2, len(nxt) // 2))
    combined = combined.append(nxt, crossfade=safe_cf)

  if target_duration_sec is not None and target_duration_sec > 0:
    target_ms = int(target_duration_sec * 1000)
    if len(combined) < target_ms:
      while len(combined) < target_ms:
        faltante_ms = target_ms - len(combined)
        trozo = combined[: min(len(combined), faltante_ms + 1500)]
        cf = max(0, min(crossfade_ms, len(combined) // 2, len(trozo) // 2))
        combined = combined.append(trozo, crossfade=cf)
      combined = combined[:target_ms]
    elif len(combined) > target_ms:
      combined = combined[:target_ms].fade_out(min(1500, target_ms // 4))

  out_buf = io.BytesIO()
  combined.export(out_buf, format="wav")
  actual_sec = max(1, math.ceil(len(combined) / 1000.0))
  return out_buf.getvalue(), actual_sec


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
      f"BASA STUDIO ENTERPRISE  |  {project_title}",
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
  lines: list[str] = []
  current = ""
  for w in words:
    test = f"{current} {w}".strip()
    if len(test) > 85:
      lines.append(current)
      current = w
    else:
      current = test
  if current:
    lines.append(current)

  y_pos = 160
  for line in lines[:12]:
    draw.text((48, y_pos), line, fill=(210, 220, 235), font=font_title)
    y_pos += 26

  draw.text(
      (48, height - 52),
      "MASTER RENDER • 1280x720 • H.264 + AAC",
      fill=(160, 175, 200),
      font=font_title,
  )
  buf = io.BytesIO()
  img.save(buf, format="PNG")
  return buf.getvalue()


def render_video_mp4(
    audio_wav_bytes: bytes,
    image_png_bytes: bytes,
) -> tuple[bytes, str]:
  tmp_dir = VAULT_DIR / "tmp_render"
  tmp_dir.mkdir(parents=True, exist_ok=True)
  uid = uuid.uuid4().hex[:8]
  img_path = tmp_dir / f"frame_{uid}.png"
  aud_path = tmp_dir / f"audio_{uid}.wav"
  out_path = tmp_dir / f"render_{uid}.mp4"

  img_path.write_bytes(image_png_bytes)
  aud_path.write_bytes(audio_wav_bytes)

  cmd = [
      "ffmpeg",
      "-y",
      "-loop",
      "1",
      "-i",
      str(img_path),
      "-i",
      str(aud_path),
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
      str(out_path),
  ]

  try:
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0 or not out_path.exists():
      return (
          b"",
          f"FFmpeg no disponible o error en render: {proc.stderr[-300:]}",
      )
    return out_path.read_bytes(), "OK"
  finally:
    for p in (img_path, aud_path, out_path):
      if p.exists():
        try:
          p.unlink()
        except Exception:
          pass


# ==============================================================================
# INICIALIZACIÓN DE SESIÓN, DISPOSITIVO Y BARRA LATERAL
# ==============================================================================
vault_data = init_vault()
users_data = load_users_vault()
assets: list[dict[str, Any]] = vault_data.get("assets", [])
modules: list[dict[str, Any]] = vault_data.get("autonomous_modules", [])
station_cfg: dict[str, Any] = vault_data.setdefault(
    "station_config",
    {
        "station_name": "BASA Radio Autónoma 24/7",
        "autonomous_permission": True,
        "auto_advance": True,
        "active_track_id": None,
    },
)

st.session_state.setdefault("active_user", "Invitado Libre")
st.session_state.setdefault("active_device", "Celular")
st.session_state.setdefault("access_mode", "LIBRE")
st.session_state.setdefault("admin_unlocked", False)

with st.sidebar:
  st.header("🤖 Nucleo Autonomo")
  auto_refresh = st.checkbox("Auto-Actualizacion cada 30s", value=False)
  st.text_input(
      "Licencia Universal Libre", value="BASA-UNIV-C6D4D15AABCE"
  )

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
        "Usuario / Correo / Alias",
        value=st.session_state.get("active_user", ""),
        placeholder="Ej: pedro.baldera",
    )
    acc_key = st.text_input(
        "Clave privada (se guarda oculta, nunca pública)",
        type="password",
    )
    save_private_key = st.checkbox(
        "Guardar clave en historial privado (recuperable por Admin/Delegado)",
        value=True,
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
      log_device_event(
          username=clean_u,
          device_type=selected_device,
          action="Vinculación y carga automática",
          access_mode="REGISTRADA",
      )
      exp_zip = auto_export_bundle(
          reason=f"Vinculación de cuenta: {clean_u}",
          username=clean_u,
          device_type=selected_device,
      )
      st.session_state["last_auto_export"] = str(exp_zip)
      st.success(f"Cuenta '{clean_u}' enlazada.")
      st.rerun()

  st.divider()
  st.subheader("🎛️ Duración Extendida")
  duracion_extendida = st.slider(
      "Duracion pista libre (seg)",
      min_value=10,
      max_value=600,
      value=120,
      step=10,
  )
  st.caption(
      f"Tiempo activo: **{duracion_extendida // 60}:{duracion_extendida % 60:02d}**"
      f" ({duracion_extendida}s)"
  )
  crossfade_ms = st.slider("Crossfade entre tomas (ms)", 0, 3000, 800, 100)

  st.divider()
  st.subheader("📦 Exportación Automática")
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
total_scripts_videos = sum(
    1 for a in assets if a.get("type") in ("script", "video")
)

st.title("🤖 BASA Universal AI Studio · Produccion Online")
st.caption(
    f"Usuario: **{st.session_state.get('active_user')}** · Dispositivo: **{st.session_state.get('active_device')}** · Modo Autónomo 100/100"
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

# --- TAB 1: MÚSICA & CICLO AUTÓNOMO 100/100 ---
with tab_music:
  col_l, col_r = st.columns([1.2, 1])
  with col_l:
    project_title = st.text_input(
        "Titulo del proyecto", value="Himno de Navidad en Quisqueya"
    )
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
    master_prompt = st.text_area(
        "Escribe tu idea, letra o prompt maestro",
        height=190,
        placeholder="Escribe aquí tu letra o estructura musical...",
    )
    uploaded_segments = st.file_uploader(
        "Opcional: sube pistas o escenas para unir con crossfade",
        type=["wav", "mp3", "ogg", "m4a"],
        accept_multiple_files=True,
    )

    c_btn1, c_btn2 = st.columns(2)
    gen_clicked = c_btn1.button(
        "🎵 Generar Audio + Prompts Multi-IA", type="primary"
    )
    full_auto_clicked = c_btn2.button(
        "⚡ CICLO AUTÓNOMO 100/100 (Audio + Prompts + Kit ZIP)"
    )

    if gen_clicked or full_auto_clicked:
      if uploaded_segments:
        pairs = [(f.name, f.getvalue()) for f in uploaded_segments]
        wav_bytes, real_sec = stitch_audio_segments(
            pairs,
            crossfade_ms=crossfade_ms,
            target_duration_sec=duracion_extendida,
        )
      else:
        base_wav = generate_pulse_bed_wav(
            duration_sec=min(duracion_extendida, 60), bpm=bpm
        )
        wav_bytes, real_sec = stitch_audio_segments(
            [("base", base_wav)],
            crossfade_ms=crossfade_ms,
            target_duration_sec=duracion_extendida,
        )

      prompts_pack = (
          f"=== SUNO v6 ===\nStyle: {genre}, {bpm} BPM, extended arrangement, {real_sec}s\n{master_prompt}\n\n"
          f"=== GEMINI MUSIC / LYRIA 3.5 ===\nCreate a {genre} track at {bpm} BPM ({real_sec}s).\n{master_prompt}\n\n"
          f"=== MUREKA AI ===\nGenre: {genre} | Tempo: {bpm} BPM | Duration: {real_sec}s\n{master_prompt}\n\n"
          f"=== CHATGPT / IA ===\nActúa como productor de {genre} ({bpm} BPM, {real_sec}s):\n{master_prompt}"
      )
      release_kit_txt = (
          f"TÍTULO: {project_title}\nGÉNERO: {genre} ({bpm} BPM)\nDURACIÓN: {real_sec}s\n"
          f"USUARIO: {st.session_state.get('active_user')} · DISPOSITIVO: {st.session_state.get('active_device')}\n\n"
          f"LETRA / GUION:\n{master_prompt}"
      )

      saved_audio = save_asset_to_vault(
          title=project_title,
          asset_type="audio",
          genre_or_format=f"{genre} ({bpm} BPM)",
          duration_sec=real_sec,
          content_bytes=wav_bytes,
          extension="wav",
          script_text=master_prompt,
          prompts_bundle=prompts_pack,
      )
      st.session_state["last_audio"] = saved_audio

      if full_auto_clicked:
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
        save_release_record({
            "id": f"REL-{uuid.uuid4().hex[:8].upper()}",
            "title": project_title,
            "artist": "BASA Productions · El Forense de la Música",
            "platforms": [
                "YouTube / YouTube Music",
                "Spotify (vía distribuidor/agregador)",
                "SoundCloud / Audiomack",
            ],
            "created_at": datetime.now().isoformat(),
            "kit": release_kit_txt,
        })
        zip_pack = build_upload_ready_zip(
            title=project_title,
            media_bytes=wav_bytes,
            media_ext="wav",
            script_text=master_prompt,
            prompts_bundle=prompts_pack,
            release_kit=release_kit_txt,
        )
        st.session_state["ready_upload_zip"] = zip_pack
        st.session_state["ready_upload_name"] = (
            f"{project_title.replace(' ', '_')}_100_100.zip"
        )

      st.success(
          f"¡Ciclo completado ({real_sec}s)! Bóveda actualizada y paquete listo."
      )
      st.rerun()

  with col_r:
    st.subheader("Salida de Audio y Prompts")
    if st.session_state.get("ready_upload_zip"):
      st.download_button(
          "📦 Descargar Paquete 100/100 Listo para Subir (.ZIP)",
          data=st.session_state["ready_upload_zip"],
          file_name=st.session_state.get(
              "ready_upload_name", "basa_lanzamiento_100_100.zip"
          ),
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
      st.text_area(
          "Prompts listos para copiar:",
          value=last_audio.get("prompts_bundle", ""),
          height=240,
      )
    else:
      st.info(
          "Genera un audio o pulsa 'CICLO AUTÓNOMO 100/100' para producir, guardar y descargar tu paquete."
      )

# --- TAB 2: PELÍCULAS, SERIES & VIDEO ---
with tab_cinema:
  st.subheader("🎬 Estudio de Películas, Series y Ensamblaje de Video")
  c1, c2, c3 = st.columns(3)
  cine_title = c1.text_input(
      "Título de Película / Serie", value="El Lápiz Pesa Más que el Pico"
  )
  cine_ep = c2.text_input("Temporada / Episodio", value="T01 · E01")
  cine_scene = c3.text_input(
      "Escena / Secuencia", value="Escena 01 - De la Obra al Escritorio"
  )

  cine_dur = st.slider(
      "Duración de la escena / clip (seg)",
      min_value=10,
      max_value=600,
      value=max(30, min(duracion_extendida, 120)),
      step=10,
  )
  cine_script = st.text_area(
      "Guion / Diálogo / Narración",
      height=120,
      value="NARRADOR: Con esfuerzo, disciplina y visión, cada paso construye un nuevo horizonte.",
  )
  cine_vprompt = st.text_area(
      "Prompt Visual Cinematográfico (encuadre, iluminación, cámara, estilo)",
      height=110,
      value="Cinematic wide shot, golden hour sunlight, shallow depth of field, rich color grading, film grain, high detail.",
  )

  if st.button(
      "🎥 Renderizar Escena de Video (.MP4) y Guardar en Bóveda", type="primary"
  ):
    wav_clip = generate_pulse_bed_wav(duration_sec=cine_dur, bpm=110)
    poster_png = create_scene_poster_png(
        project_title=cine_title,
        episode_label=cine_ep,
        scene_title=cine_scene,
        visual_prompt=f"{cine_vprompt}\n\n{cine_script}",
    )
    mp4_bytes, status_msg = render_video_mp4(wav_clip, poster_png)
    if mp4_bytes:
      saved_vid = save_asset_to_vault(
          title=f"{cine_title} - {cine_scene}",
          asset_type="video",
          genre_or_format=f"Video MP4 ({cine_ep})",
          duration_sec=cine_dur,
          content_bytes=mp4_bytes,
          extension="mp4",
          script_text=cine_script,
          prompts_bundle=cine_vprompt,
      )
      st.success(f"¡Video renderizado y guardado ({saved_vid['id']})!")
      st.video(mp4_bytes)
      st.download_button(
          "⬇️ Descargar Video (.MP4)",
          data=mp4_bytes,
          file_name=f"{saved_vid['id']}.mp4",
          mime="video/mp4",
      )
      st.rerun()
    else:
      st.warning(status_msg)
      saved_sc = save_asset_to_vault(
          title=f"{cine_title} - {cine_scene}",
          asset_type="script",
          genre_or_format=f"Storyboard / Guion ({cine_ep})",
          duration_sec=cine_dur,
          content_bytes=poster_png,
          extension="png",
          script_text=cine_script,
          prompts_bundle=cine_vprompt,
      )
      st.image(
          poster_png, caption=f"Storyboard guardado ({saved_sc['id']})"
      )
      st.rerun()

# --- TAB 3: EMISORA AUTÓNOMA BASA ---
with tab_station:
  st.subheader("📡 Emisora Autónoma BASA · Programación y Reproducción")
  st_col1, st_col2 = st.columns(2)
  station_name = st_col1.text_input(
      "Nombre de la Emisora",
      value=station_cfg.get("station_name", "BASA Radio Autónoma 24/7"),
  )
  auto_perm = st_col2.checkbox(
      "Asignación de Permiso Autónomo Full (obras/pistas propias del estudio)",
      value=bool(station_cfg.get("autonomous_permission", True)),
  )

  if st.button("📻 Guardar Configuración de Emisora"):
    data_now = init_vault()
    data_now["station_config"] = {
        "station_name": station_name,
        "autonomous_permission": auto_perm,
        "auto_advance": True,
        "active_track_id": station_cfg.get("active_track_id"),
    }
    save_vault_data(
        data_now, auto_export=True, reason="Configuración de emisora"
    )
    st.success("Emisora configurada.")
    st.rerun()

  audio_assets = [
      a for a in assets if a.get("type") == "audio" and a.get("file_path")
  ]
  if not audio_assets:
    st.info("Aún no hay audios en la bóveda para transmitir.")
  else:
    track_labels = [
        f"{a.get('title')} ({a.get('duration_sec', 0)}s) [{a.get('id')}]"
        for a in audio_assets
    ]
    selected_idx = st.selectbox(
        "Selecciona pista para poner al aire",
        options=list(range(len(audio_assets))),
        format_func=lambda i: track_labels[i],
    )
    current_track = audio_assets[selected_idx]
    track_path = Path(current_track["file_path"])
    if track_path.exists():
      st.audio(
          track_path.read_bytes(),
          format=f"audio/{current_track.get('extension', 'wav')}",
      )

    if st.button(
        "🎶 Generar Maratón Continuo de Emisora (Unir Pistas con Crossfade)"
    ):
      pairs = []
      for a in audio_assets[:10]:
        tp = Path(a["file_path"])
        if tp.exists():
          pairs.append((a["title"], tp.read_bytes()))
      if pairs:
        marathon_wav, marathon_sec = stitch_audio_segments(
            pairs, crossfade_ms=crossfade_ms
        )
        saved_m = save_asset_to_vault(
            title=f"{station_name} - Maratón Continuo",
            asset_type="audio",
            genre_or_format="Emisora / Maratón",
            duration_sec=marathon_sec,
            content_bytes=marathon_wav,
            extension="wav",
            script_text=f"Maratón generado en {station_name} con {len(pairs)} pistas.",
        )
        st.success(
            f"¡Maratón de {marathon_sec}s creado y guardado ({saved_m['id']})!"
        )
        st.audio(marathon_wav, format="audio/wav")
        st.rerun()

# --- TAB 4: PUBLICAR EN REDES MUSICALES ---
with tab_publish:
  st.subheader("🚀 Publicación y Distribución Musical")
  pub_title = st.text_input(
      "Título oficial del lanzamiento",
      value="Himno de Navidad en Quisqueya (Versión Studio)",
  )
  pub_artist = st.text_input(
      "Intérprete / Proyecto / Sello",
      value="BASA Productions · El Forense de la Música",
  )
  pub_platforms = st.multiselect(
      "Plataformas destino",
      [
          "YouTube / YouTube Music",
          "Spotify (vía distribuidor/agregador)",
          "SoundCloud / Audiomack",
          "TikTok / Instagram / Facebook",
      ],
      default=[
          "YouTube / YouTube Music",
          "Spotify (vía distribuidor/agregador)",
          "SoundCloud / Audiomack",
      ],
  )
  pub_lyrics = st.text_area(
      "Descripción / Letra / Créditos",
      height=130,
      value="Producido en BASA Universal AI Studio. Arreglos y producción original.",
  )
  release_kit = (
      f"TÍTULO: {pub_title}\nARTISTA: {pub_artist}\n"
      f"PLATAFORMAS: {', '.join(pub_platforms)}\n\n{pub_lyrics}"
  )
  st.text_area("Release Kit:", value=release_kit, height=150)

  l1, l2, l3 = st.columns(3)
  l1.link_button("▶️ YouTube Studio", "https://studio.youtube.com/")
  l2.link_button("🎧 Spotify for Artists", "https://artists.spotify.com/")
  l3.link_button("☁️ SoundCloud", "https://soundcloud.com/upload")

  if st.button("✅ Registrar Lanzamiento", type="primary"):
    save_release_record({
        "id": f"REL-{uuid.uuid4().hex[:8].upper()}",
        "title": pub_title,
        "artist": pub_artist,
        "platforms": pub_platforms,
        "created_at": datetime.now().isoformat(),
        "kit": release_kit,
    })
    st.success("Lanzamiento registrado.")
    st.rerun()

# --- TAB 5: MÓDULOS AUTÓNOMOS & GITHUB ---
with tab_modules:
  st.subheader("🧩 Módulos Autónomos & GitHub Issues")
  issue_ref = st.text_input(
      "Importar desde Issue de GitHub (URL o owner/repo#numero)",
      placeholder="Ej: https://github.com/usuario/repo/issues/1",
  )
  if "mod_code_editor" not in st.session_state:
    st.session_state["mod_code_editor"] = (
        "def potenciar_motor(contexto: dict):\n"
        "    return {'estado': 'activo', 'usuario': contexto.get('usuario', 'Libre')}\n"
    )
  if "mod_name_input" not in st.session_state:
    st.session_state["mod_name_input"] = "Modulo_Autonomo_BASA"

  if st.button("📥 Extraer Código de GitHub Issue"):
    parsed = parse_github_issue_input(issue_ref)
    if not parsed:
      st.error("Formato inválido. Usa URL de issue o `owner/repo#1`.")
    else:
      owner, repo, num = parsed
      ok, issue_title, code_text, msg = fetch_github_issue_code(owner, repo, num)
      if not ok:
        st.error(msg)
      else:
        st.session_state["mod_code_editor"] = code_text
        st.session_state["mod_name_input"] = f"{repo}_Issue_{num}"
        st.success(f"Extraído de: **{issue_title}**")

  mod_name = st.text_input("Nombre del módulo", key="mod_name_input")
  code_text = st.text_area("Código Python:", key="mod_code_editor", height=220)
  is_valid, val_msg = validate_python_code(code_text)
  if is_valid:
    st.success(f"✅ {val_msg}")
  else:
    st.error(f"❌ {val_msg}")

  if st.button("🔌 Validar y Conectar Módulo", type="primary"):
    ok_reg, reg_msg, _ = compile_and_register_module(
        mod_name, code_text, issue_ref or "Manual"
    )
    if ok_reg:
      st.success(reg_msg)
      st.rerun()
    else:
      st.error(reg_msg)

  if modules:
    for m in modules:
      m_name = m.get("name", "Modulo")
      fn_list = m.get("callables", [])
      with st.expander(
          f"🧩 {m_name} · Funciones: {', '.join(fn_list) or 'ninguna'}"
      ):
        st.code(m.get("code", ""), language="python")
        if fn_list:
          chosen_fn = st.selectbox(
              "Ejecutar función", options=fn_list, key=f"sel_{m.get('id')}"
          )
          if st.button("▶️ Correr", key=f"run_{m.get('id')}"):
            ok_r, out_r = run_registered_callable(
                f"{m_name}.{chosen_fn}",
                {"usuario": st.session_state.get("active_user")},
            )
            st.info(str(out_r))

# --- TAB 6: CLAVES PRIVADAS (SOLO ADMIN / DELEGADOS) & HISTORIAL DE DISPOSITIVOS ---
with tab_security_devices:
  st.subheader("🔐 Claves Históricas Privadas y Historial por Dispositivo")
  st.caption(
      "Las claves guardadas por los usuarios permanecen ocultas por defecto; solo el Administrador o Delegados autorizados pueden verlas o recuperarlas."
  )

  col_sec1, col_sec2 = st.columns(2)
  with col_sec1:
    st.markdown("### 🛡️ Panel de Administrador / Delegados")
    admin_pin_input = st.text_input(
        "Clave de autorización (Admin / Delegado)", type="password"
    )
    if st.button("🔓 Desbloquear Vista Privada"):
      if admin_pin_input == ADMIN_MASTER_PIN:
        st.session_state["admin_unlocked"] = True
        st.success("Vista privada autorizada activa.")
      else:
        st.error("Clave de autorización incorrecta.")

    if st.session_state.get("admin_unlocked"):
      st.warning(
          "🔒 Vista Autorizada Activa — Maneja esta información con reserva."
      )
      users_map = users_data.get("users", {})
      if not users_map:
        st.info("No hay usuarios con credencial guardada todavía.")
      else:
        for uname, uinfo in users_map.items():
          with st.expander(
              f"Usuario: {uname} · Último dispositivo: {uinfo.get('last_device', 'N/D')}"
          ):
            st.write(
                f"**Clave guardada:** {'Sí' if uinfo.get('key_saved') else 'No'}"
            )
            st.write(
                f"**Última actualización:** {uinfo.get('updated_at', '')}"
            )
            if uinfo.get("key_saved"):
              recovered_secret = reveal_key(uinfo.get("encoded_key", ""))
              st.code(recovered_secret, language="text")

      st.markdown("#### Delegados Autorizados")
      delegates = users_data.get("delegates", [])
      new_del = st.text_input("Agregar alias de delegado")
      if st.button("➕ Añadir Delegado") and new_del.strip():
        if new_del.strip() not in delegates:
          delegates.append(new_del.strip())
          users_data["delegates"] = delegates
          save_users_vault(users_data)
          st.success("Delegado agregado.")
          st.rerun()
      st.write(", ".join(delegates) if delegates else "Ninguno")
    else:
      st.info(
          "Las claves de usuarios están ocultas. Ingresa la clave de Administrador/Delegado para recuperar o consultar."
      )

  with col_sec2:
    st.markdown("### 📱 Historial de Accesos por Dispositivo")
    dev_hist = users_data.get("device_history", [])
    if not dev_hist:
      st.info("Aún no se registran ingresos por dispositivo.")
    else:
      for ev in dev_hist[:25]:
        st.write(
            f"• **{ev.get('device')}** — *{ev.get('user')}* ({ev.get('access_mode')}) · {ev.get('action')} — `{ev.get('timestamp', '')[:19]}`"
        )

# --- TAB 7: MIGRAR LINKS Y ARCHIVOS ---
with tab_migrate:
  st.subheader("🌐 Migrar Links y Archivos (Suno/Mureka/ChatGPT)")
  mig_title = st.text_input(
      "Nombre del activo a migrar", value="Pista Migrada Suno"
  )
  mig_url = st.text_input(
      "URL de referencia", value="https://suno.com/discover"
  )
  mig_files = st.file_uploader(
      "Subir archivos de audio, video, imagen o guion",
      type=["wav", "mp3", "mp4", "png", "jpg", "txt", "md"],
      accept_multiple_files=True,
  )
  if st.button("📥 Importar a Boveda"):
    if mig_files:
      for f in mig_files:
        ext = f.name.split(".")[-1].lower() if "." in f.name else "bin"
        atype = (
            "audio"
            if ext in ("wav", "mp3", "ogg", "m4a")
            else ("video" if ext in ("mp4", "mov") else "script")
        )
        save_asset_to_vault(
            title=f"{mig_title} ({f.name})",
            asset_type=atype,
            genre_or_format="Migración Directa",
            duration_sec=duracion_extendida,
            content_bytes=f.getvalue(),
            extension=ext,
            prompts_bundle=f"Source URL: {mig_url}",
        )
      st.success("Archivos importados y exportados automáticamente.")
      st.rerun()
    else:
      save_asset_to_vault(
          title=mig_title,
          asset_type="script",
          genre_or_format="Enlace / Script",
          duration_sec=duracion_extendida,
          script_text=f"URL: {mig_url}",
          prompts_bundle=mig_url,
      )
      st.success("Referencia guardada y exportada automáticamente.")
      st.rerun()

# --- TAB 8: BÓVEDA MULTIMEDIA CON FILTRO POR USUARIO Y DISPOSITIVO ---
with tab_vault:
  st.subheader("📚 Boveda Multimedia")
  if not assets:
    st.info(
        "Aún no hay activos en la bóveda. Genera una pista, renderiza una escena de video o importa archivos."
    )
  else:
    usuarios_disponibles = sorted(
        {a.get("owner_user") or "Invitado Libre" for a in assets}
    )
    dispositivos_disponibles = sorted(
        {a.get("device") or "No especificado" for a in assets}
    )

    f_col1, f_col2, f_col3 = st.columns(3)
    filtro_usuario = f_col1.selectbox(
        "Filtrar por usuario",
        options=["Todos"] + usuarios_disponibles,
        index=0,
    )
    filtro_dispositivo = f_col2.selectbox(
        "Filtrar por dispositivo",
        options=["Todos"] + dispositivos_disponibles,
        index=0,
    )
    filtro_tipo = f_col3.selectbox(
        "Filtrar por tipo de activo",
        options=["Todos", "audio", "video", "script"],
        index=0,
    )

    activos_filtrados = [
        item
        for item in assets
        if (
            filtro_usuario == "Todos"
            or (item.get("owner_user") or "Invitado Libre") == filtro_usuario
        )
        and (
            filtro_dispositivo == "Todos"
            or (item.get("device") or "No especificado") == filtro_dispositivo
        )
        and (filtro_tipo == "Todos" or item.get("type") == filtro_tipo)
    ]

    st.caption(
        f"Mostrando **{len(activos_filtrados)}** de **{len(assets)}** activos guardados."
    )

    if not activos_filtrados:
      st.warning(
          "No hay activos que coincidan con los filtros seleccionados."
      )
    else:
      for item in activos_filtrados:
        with st.expander(
            f"[{item.get('type', '').upper()}] {item.get('title')} — {item.get('duration_sec', 0)}s ({item.get('id')})"
        ):
          st.write(
              f"**Formato:** {item.get('genre_or_format')} | **Usuario:** {item.get('owner_user', 'Invitado Libre')} | **Dispositivo:** {item.get('device', 'No especificado')}"
          )
          if item.get("script_text"):
            st.text_area(
                "Guion / Letra / Nota",
                value=item["script_text"],
                height=95,
                key=f"v_sc_{item['id']}",
            )
          if item.get("prompts_bundle"):
            st.text_area(
                "Prompts / Enlace",
                value=item["prompts_bundle"],
                height=95,
                key=f"v_pr_{item['id']}",
            )
          fpath = item.get("file_path")
          if fpath:
            p = Path(fpath)
            if p.exists():
              raw = p.read_bytes()
              if item.get("type") == "audio":
                st.audio(raw)
              elif item.get("type") == "video":
                st.video(raw)
              elif item.get("extension") in ("png", "jpg", "jpeg"):
                st.image(raw)
              st.download_button(
                  f"⬇️ Descargar ({item.get('extension', 'archivo').upper()})",
                  data=raw,
                  file_name=p.name,
                  key=f"v_dl_{item['id']}",
              )

if auto_refresh:
  import time

  time.sleep(30)
  st.rerun()
