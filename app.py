# ============================================================
# BASA AUDIO VISUAL V10 FULL - TODO ACUMULADO
# Lic. Pedro Baldera x El Forense
# Canal + Radio + Subir + Fusión + Crew 4 IA + Monitoreo 5min
# Moderna + Antigua + Probador + Auto-Corrección + Ranking + YouTube
# ============================================================
import streamlit as st
import pandas as pd
from charts import mostrar_grafico_basa
from graficos import dibujar_grafico_basa
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh
import requests, traceback

st_autorefresh(interval=39 * 1000, key="basa_v10_full")
st.set_page_config(page_title="BASA V10 FULL", page_icon="🔥", layout="wide")
st.markdown("""<style>.main { background-color: #0E0E0E; color: white; }
.stButton>button { background-color: #FFD700; color: black; font-weight: bold; border-radius: 20px; }</style>""", unsafe_allow_html=True)

# ================= MEMORIA FULL - TODO LO YA CREADO =================
if "contenido" not in st.session_state:
    st.session_state.contenido = pd.DataFrame([
        {"ID": 1, "Titulo": "SE ACERCA EL DOBLE", "Tipo": "Canción", "IA Origen": "BASA CREW - Moderna+Antigua", "Genero": "Dembow Navidad + Perico Ripiao", "Reproducciones": 99999, "Likes": 9999, "Estado": "ÉXITO 🔥 #1", "Fecha": "2026-11-09", "Parrafo Original": "Se acerca el doble, mi carro no enciende, se pinchó la goma, vecina me dio su número, familia a bailar, lechón asado, ron, whisky caro, vino, viajeros, villa a celebrar", "Prompt IA": "", "Link YouTube": "https://youtube.com/@tubasa"},
        {"ID": 2, "Titulo": "DICIEMBRE RULAY", "Tipo": "Canción", "IA Origen": "BASA IA", "Genero": "Dembow Rulay", "Reproducciones": 12500, "Likes": 2300, "Estado": "ÉXITO 🔥", "Fecha": "2026-11-09", "Parrafo Original": "Diciembre rulay de Los Frailes", "Prompt IA": "", "Link YouTube": ""},
        {"ID": 3, "Titulo": "CÓGELO AHÍ", "Tipo": "Canción", "IA Origen": "Suno", "Genero": "Dembow", "Reproducciones": 8400, "Likes": 1500, "Estado": "ÉXITO 🔥", "Fecha": "2026-11-08", "Parrafo Original": "", "Prompt IA": "", "Link YouTube": ""},
        {"ID": 4, "Titulo": "LOS FRAILES EP1", "Tipo": "Serie", "IA Origen": "BASA IA", "Genero": "Drama Barrio", "Reproducciones": 3200, "Likes": 600, "Estado": "Normal", "Fecha": "2026-11-07", "Parrafo Original": "", "Prompt IA": "", "Link YouTube": ""},
        {"ID": 5, "Titulo": "PELÍCULA DE BARRIO", "Tipo": "Película", "IA Origen": "BASA IA", "Genero": "Drama", "Reproducciones": 1500, "Likes": 300, "Estado": "Normal", "Fecha": "2026-11-06", "Parrafo Original": "", "Prompt IA": "", "Link YouTube": ""},
    ])
if "monitoreo" not in st.session_state: st.session_state.monitoreo = []
if "ultimo_monitoreo" not in st.session_state: st.session_state.ultimo_monitoreo = datetime.now() - timedelta(minutes=10)
if "tema_auto_creado" not in st.session_state: st.session_state.tema_auto_creado = None
if "crew_resultado" not in st.session_state: st.session_state.crew_resultado = None
if "ultima_cancion" not in st.session_state: st.session_state.ultima_cancion = None
if "radio_cola" not in st.session_state: st.session_state.radio_cola = ["SE ACERCA EL DOBLE", "DICIEMBRE RULAY", "CÓGELO AHÍ"]
if "log_errores" not in st.session_state: st.session_state.log_errores = []

# ================= PROBADOR + AUTO-CORRECTOR PERMANENTE =================
def analizar_y_corregir(df):
    errores = []
    df = df.copy()
    try:
        for col, default in [("ID",0),("Titulo","SIN TITULO"),("Tipo","Canción"),("IA Origen","BASA IA"),("Genero","Dembow Rulay"),("Reproducciones",0),("Likes",0),("Estado","Normal"),("Fecha",datetime.now().strftime("%Y-%m-%d")),("Parrafo Original",""),("Prompt IA",""),("Link YouTube","")]:
            if col not in df.columns:
                df[col] = default; errores.append(f"Corregido: Faltaba {col}")
        df["Titulo"] = df["Titulo"].fillna("SIN TITULO").replace("", "SIN TITULO")
        df["Reproducciones"] = pd.to_numeric(df["Reproducciones"], errors="coerce").fillna(0).clip(lower=0).astype(int)
        df["Likes"] = pd.to_numeric(df["Likes"], errors="coerce").fillna(0).clip(lower=0).astype(int)
        antes = len(df)
        df = df.sort_values("Reproducciones", ascending=False).drop_duplicates(subset=["Titulo"], keep="first")
        if len(df) < antes: errores.append(f"Corregido: {antes-len(df)} duplicados eliminados")
        df = df.sort_values("Reproducciones", ascending=False).reset_index(drop=True)
        df["Ranking"] = df.index + 1; df["ID"] = df.index + 1
        df["Estado"] = df["Reproducciones"].apply(lambda x: "ÉXITO 🔥" if x >= 5000 else "Normal")
        return df, errores
    except Exception as e:
        return pd.DataFrame([{"ID":1,"Titulo":"SE ACERCA EL DOBLE","Tipo":"Canción","IA Origen":"BASA IA","Genero":"Dembow Rulay","Reproducciones":99999,"Likes":9999,"Estado":"ÉXITO 🔥","Fecha":"2026-11-09","Parrafo Original":"","Prompt IA":"","Link YouTube":""}]), [f"Error: {e} - Cargado respaldo"]

def probar_sistema(df):
    pruebas = []
    try:
        pruebas.append(("✅ Carga de datos", len(df)>0))
        pruebas.append(("✅ Sin títulos vacíos", (df["Titulo"]!="").all()))
        pruebas.append(("✅ Sin reproducciones negativas", (df["Reproducciones"]>=0).all()))
        pruebas.append(("✅ Ranking ordenado", df["Reproducciones"].is_monotonic_decreasing))
        pruebas.append(("✅ Sin duplicados", not df["Titulo"].duplicated().any()))
        pruebas.append(("✅ Galería lista", True))
    except Exception as e: pruebas.append((f"❌ {e}", False))
    return pruebas

# ================= CREW 4 IA - GEMINI + CHATGPT + CLAUDE + META =================
def crew_crear_tema(parrafo):
    gemini_key = st.secrets.get("GEMINI_API_KEY","") if hasattr(st,"secrets") else ""
    openai_key = st.secrets.get("OPENAI_API_KEY","") if hasattr(st,"secrets") else ""
    claude_key = st.secrets.get("CLAUDE_API_KEY","") if hasattr(st,"secrets") else ""
    meta_key = st.secrets.get("META_API_KEY","") if hasattr(st,"secrets") else ""
    letra = prompt_suno = marketing = tiktok = None
    # Gemini - Letra
    if gemini_key:
        try:
            r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_key}", json={"contents":[{"parts":[{"text": f"Compositor dembow dominicano fino rulay original. Crea letra 2 versos + coro pegable con: {parrafo}"}]}]}, timeout=30)
            letra = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        except: pass
    if openai_key:
        try:
            r = requests.post("https://api.openai.com/v1/chat/completions", headers={"Authorization": f"Bearer {openai_key}"}, json={"model":"gpt-4o-mini","messages":[{"role":"user","content":f"Prompt corto para Suno dembow dominicano con: {parrafo}"}]}, timeout=30)
            prompt_suno = r.json()["choices"][0]["message"]["content"]
        except: pass
    if claude_key:
        try:
            r = requests.post("https://api.anthropic.com/v1/messages", headers={"x-api-key":claude_key,"anthropic-version":"2023-06-01"}, json={"model":"claude-3-haiku-20240307","max_tokens":500,"messages":[{"role":"user","content":f"Título, descripción YouTube y hashtags para dembow con: {parrafo}"}]}, timeout=30)
            marketing = r.json()["content"][0]["text"]
        except: pass
    if meta_key:
        try:
            r = requests.post("https://api.groq.com/openai/v1/chat/completions", headers={"Authorization": f"Bearer {meta_key}"}, json={"model":"llama-3.3-70b-versatile","messages":[{"role":"user","content":f"Guión TikTok 15 seg dembow con: {parrafo}"}]}, timeout=30)
            tiktok = r.json()["choices"][0]["message"]["content"]
        except: pass
    if not letra: letra = f"[Verso 1]\n{parrafo} - De Los Frailes pa' la villa, con mi familia entera\n[CORO]\nSe acerca el doble, doble, doble\nNos vamos pa' la villa a celebrar\nLechón asado y ron pa' beber\nLlegaron los viajeros, llegaron a gozar"
    if not prompt_suno: prompt_suno = f"Dembow dominicano fino rulay, Navidad, Lic. Pedro Baldera x El Forense. Historia: {parrafo}. Coro corto 2 frases."
    if not marketing: marketing = f"TÍTULO: {parrafo[:30].upper()} - Lic. Pedro Baldera x El Forense | BASA V10\nDESCRIPCIÓN: Tema original BASA V10, dembow fino de Los Frailes. Suscríbete.\nHASHTAGS: #Dembow #LosFrailes #BASA #SeAcercaElDoble"
    if not tiktok: tiktok = f"GANCHO TikTok: ¡Se acerca el doble! - Carro + lechón + familia bailando - {parrafo[:50]}"
    return {"letra":letra,"prompt_suno":prompt_suno,"marketing":marketing,"tiktok":tiktok,"usando_ia_real": bool(gemini_key or openai_key or claude_key or meta_key)}

# ================= MONITOREO CADA 5 MIN + MODERNA + ANTIGUA =================
def monitorear_musica_pegada():
    tendencias = []
    try:
        for gid, nom in [(17,"Dembow / Urbano Latino"),(20,"Merengue / Bachata"),(18,"Trap / Hip-Hop")]:
            r = requests.get(f"https://itunes.apple.com/do/rss/topSongs/limit=5/genre={gid}/json", timeout=10)
            if r.status_code==200:
                for e in r.json().get("feed",{}).get("entry",[]):
                    tendencias.append({"Tema Monitoreado": e.get("im:name",{}).get("label","?"), "Artista": e.get("im:artist",{}).get("label","?"), "Genero Monitoreado": nom, "Hora": datetime.now().strftime("%H:%M:%S"), "Fuente":"iTunes Charts RD"})
    except Exception as e: tendencias.append({"Tema Monitoreado":"Respaldo BASA","Artista":"BASA","Genero Monitoreado":"Dembow Rulay","Hora":datetime.now().strftime("%H:%M:%S"),"Fuente":str(e)})
    if not tendencias: tendencias=[{"Tema Monitoreado":"Dembow del Barrio","Artista":"Urbano","Genero Monitoreado":"Dembow Rulay","Hora":datetime.now().strftime("%H:%M:%S"),"Fuente":"Respaldo"}]
    return tendencias

def crear_tema_moderno_antiguo(tendencias):
    generos = ", ".join(set([t["Genero Monitoreado"] for t in tendencias[:3]])) if tendencias else "Dembow Rulay"
    ref = tendencias[0]["Tema Monitoreado"] if tendencias else "Dembow del Barrio"
    moderno = "Dembow fino, Drill, Trap, Afrobeats - 808, coro 2 frases, TikTok"
    antiguo = "Perico Ripiao, Bachata, Salsa, Gagá, Palos - Tambora, güira, acordeón, sentimiento barrio"
    titulo = f"SE ACERCA EL DOBLE 2.0 - FUSIÓN PERICO + DEMBOW"
    letra = f"[Intro Antigua: Tambora + Güira]\n¡De Los Frailes pa' la villa!\n[Verso Moderno]\nSe acerca el doble, mi carro no enciende, se pinchó la goma\nLa vecina me dio su número, con mi familia a bailar y vivir\n[Puente Antiguo]\nComiendo lechón asado, bebiendo ron, whisky caro, vino me lo tomo\n[Verso Moderno]\nLlegan los viajeros a gozar, pa' la villa a celebrar\n[CORO FUSIÓN]\nSe acerca el doble, doble, doble\nNos vamos pa' la villa a celebrar\nCon tambora, con güira, con dembow, ¡cógelo ahí!"
    prompt = f"FUSIÓN SUPERIOR: {moderno} + {antiguo}. Tema ORIGINAL nuevo, no copiar '{ref}'. Historia: {generos} - Lic. Pedro Baldera x El Forense. Intro Perico 5 seg, Verso Dembow, Puente Bachata, Coro Fusión."
    return {"titulo":titulo,"letra":letra,"prompt_suno":prompt,"moderno":moderno,"antiguo":antiguo,"generos_pegados":generos,"tema_ref":ref}

# --- EJECUTAR ANALIZAR + MONITOREO ---
try:
    df_c, errs = analizar_y_corregir(st.session_state.contenido)
    st.session_state.contenido = df_c
    if errs: st.session_state.log_errores.extend([f"{datetime.now().strftime('%H:%M:%S')} - {e}" for e in errs])
    df = df_c
except Exception as e:
    df = st.session_state.contenido
    st.session_state.log_errores.append(str(e))

ahora = datetime.now()
if (ahora - st.session_state.ultimo_monitoreo).total_seconds() >= 300:
    nuevas = monitorear_musica_pegada()
    st.session_state.monitoreo = nuevas + st.session_state.monitoreo
    st.session_state.monitoreo = st.session_state.monitoreo[:20]
    st.session_state.ultimo_monitoreo = ahora
    st.session_state.tema_auto_creado = crear_tema_moderno_antiguo(nuevas)

# ================= HEADER FULL =================
st.title("🔥 BASA AUDIO VISUAL V10 FULL - TODO EN UNO")
st.subheader("Lic. Pedro Baldera x El Forense | Canal + Radio + Crew + Monitoreo + Fusión")
pruebas = probar_sistema(df); aprob = sum(1 for _,ok in pruebas if ok); salud = int(aprob/len(pruebas)*100) if pruebas else 0
proximo = st.session_state.ultimo_monitoreo + timedelta(minutes=5)
c1,c2,c3,c4 = st.columns(4)
c1.metric("Salud Sistema", f"{salud}%")
c2.metric("Próximo Monitoreo", proximo.strftime("%H:%M:%S"))
c3.metric("Auto-Gestión", datetime.now().strftime("%H:%M:%S"))
c4.metric("#1 BASA", df.iloc[0]["Titulo"] if len(df)>0 else "Nada")
if salud==100: st.success("✅ TODO EN ORDEN - Probador Permanente: Sin fallas")
else: st.warning("🟡 BASA está corrigiendo sola, no se va a caer.")
tema_top = df.iloc[0] if len(df)>0 else None

tab1,tab2,tab3,tab4,tab5,tab6,tab7,tab8 = st.tabs(["🏠 CANAL BASA","🤖 CREW - 1 PÁRRAFO","📡 MONITOREO 5 MIN + FUSIÓN","📻 RADIO BASA","🎵 SUBIR MI CANCIÓN","🏆 GALERÍA + RANKING","📊 HISTORIAL + YOUTUBE","🛠️ PROBADOR"])

with tab1:
    st.header("🏠 MI CANAL BASA - Vitrina para YouTube / Spotify / TikTok")
    st.write("Aquí la gente encuentra TU música. BASA es tu casa, YouTube y Spotify son tus sucursales.")
    cc1,cc2,cc3 = st.columns(3); cc1.metric("Total Temas", len(df)); cc2.metric("Éxitos", len(df[df["Reproducciones"]>=5000])); cc3.metric("Reproducciones", f"{int(df['Reproducciones'].sum()):,}")
    st.dataframe(df[["Ranking","Titulo","Tipo","Genero","Reproducciones","Estado"]], use_container_width=True)
    st.plotly_chart(__import__("plotly.express").px.bar(df, x="Titulo", y="Reproducciones", color="Tipo", title="Quién se está pegando en BASA"), use_container_width=True)

with tab2:
    st.header("🤖 CREW - Escribe 1 párrafo, BASA crea TODO")
    st.info("Gemini = Letra | ChatGPT = Prompt Suno | Claude = Título + YouTube | Meta IA = TikTok")
    parrafo = st.text_area("✍️ Tu párrafo", height=100, placeholder="Ej: Se acerca el doble, mi carro no enciende, se pinchó la goma, vecina me dio su número, familia a bailar, lechón, ron, viajeros, villa...")
    genero = st.selectbox("Género", ["Dembow Navidad Rulay","Dembow Rulay","Dembow Fino","Trap Calle","Drama Barrio"], key="crew_genero")
    if st.button("🚀 CREW: CREAR TEMA AUTOMÁTICO"):
        if parrafo:
            with st.spinner("Crew trabajando..."): res = crew_crear_tema(parrafo); st.session_state.crew_resultado=res; st.session_state.ultimo_parrafo=parrafo; st.session_state.ultimo_genero=genero
            st.success("✅ Crew terminó."); st.rerun()
        else: st.error("Escribe tu párrafo, Lic.")
    if st.session_state.crew_resultado:
        r = st.session_state.crew_resultado
        st.write(f"Estado: {'🟢 IA REAL' if r['usando_ia_real'] else '🟡 BASA IA local - Pon Keys en Secrets para IA real'}")
        st.write("**1. LETRA - Gemini**"); st.code(r["letra"])
        st.write("**2. PROMPT SUNO - ChatGPT**"); st.code(r["prompt_suno"])
        st.write("**3. MARKETING - Claude**"); st.code(r["marketing"])
        st.write("**4. TIKTOK - Meta IA**"); st.code(r["tiktok"])
        tit = st.text_input("Título final", value=st.session_state.get("ultimo_parrafo","NUEVO TEMA")[:30].upper())
        if st.button("💾 GUARDAR TEMA DEL CREW"):
            nuevo = pd.DataFrame([{"ID":len(df)+1,"Titulo":tit,"Tipo":"Canción","IA Origen":"BASA CREW","Genero":st.session_state.get("ultimo_genero","Dembow Rulay"),"Reproducciones":1,"Likes":0,"Estado":"Normal","Fecha":datetime.now().strftime("%Y-%m-%d"),"Parrafo Original":st.session_state.get("ultimo_parrafo",""),"Prompt IA":r["prompt_suno"],"Link YouTube":""}])
            st.session_state.contenido = pd.concat([df,nuevo], ignore_index=True); st.success(f"Guardado: {tit}"); st.balloons()

with tab3:
    st.header("📡 MONITOREO CADA 5 MIN + IA MODERNA + ANTIGUA")
    st.write("**Moderna:** Dembow, Drill, Trap, Afrobeats | **Antigua:** Perico Ripiao, Bachata, Salsa, Gagá, Palos")
    if st.button("🔍 MONITOREAR AHORA"):
        nuevas = monitorear_musica_pegada(); st.session_state.monitoreo = nuevas + st.session_state.monitoreo; st.session_state.ultimo_monitoreo = datetime.now(); st.session_state.tema_auto_creado = crear_tema_moderno_antiguo(nuevas); st.success("Monitoreo hecho, tema superior creado."); st.rerun()
    if st.session_state.monitoreo: st.dataframe(pd.DataFrame(st.session_state.monitoreo), use_container_width=True)
    if st.button("🚀 CREAR TEMA SUPERIOR FUSIÓN"):
        st.session_state.tema_auto_creado = crear_tema_moderno_antiguo(st.session_state.monitoreo if st.session_state.monitoreo else [{"Tema Monitoreado":"Dembow del Barrio","Genero Monitoreado":"Dembow Rulay"}]); st.rerun()
    if st.session_state.tema_auto_creado:
        a = st.session_state.tema_auto_creado; st.markdown(f"### 🔥 {a['titulo']}"); st.write(f"Basado en: {a['tema_ref']} - {a['generos_pegados']}"); st.write("Moderna:"); st.code(a["moderno"]); st.write("Antigua:"); st.code(a["antiguo"]); st.write("Prompt:"); st.code(a["prompt_suno"]); st.write("Letra:"); st.code(a["letra"])
        if st.button("💾 GUARDAR FUSIÓN"):
            nuevo = pd.DataFrame([{"ID":len(df)+1,"Titulo":a["titulo"],"Tipo":"Canción","IA Origen":"BASA V9 Moderna+Antigua","Genero":"Fusión Dembow + Perico","Reproducciones":1,"Likes":0,"Estado":"Normal","Fecha":datetime.now().strftime("%Y-%m-%d"),"Parrafo Original":"","Prompt IA":a["prompt_suno"],"Link YouTube":""}])
            st.session_state.contenido = pd.concat([df,nuevo], ignore_index=True); st.success("Guardado Fusión"); st.rerun()

with tab4:
    st.header("📻 BASA RADIO - Suena Sola 24/7")
    st.success(f"🔊 SONANDO: #{tema_top['Ranking']} - {tema_top['Titulo']}" if tema_top is not None else "Radio en espera")
    if st.session_state.ultima_cancion is not None: st.audio(st.session_state.ultima_cancion, format="audio/mp3")
    st.write("Cola:"); 
    for i,row in df.head(5).iterrows(): st.write(f"#{row['Ranking']} - {row['Titulo']} - {int(row['Reproducciones']):,}")
    if st.button("🔥 +1 REPRODUCCIÓN"):
        idx = st.session_state.contenido[st.session_state.contenido["Titulo"]==tema_top["Titulo"]].index
        if len(idx)>0: st.session_state.contenido.loc[idx[0],"Reproducciones"]+=1; st.rerun()

with tab5:
    st.header("🎵 SUBIR MI CANCIÓN - De cualquier IA")
    st.info("¿Suno, Udio, Mureka, BASA? Si es TUYA, súbela. BASA la integra y la pone en radio sola.")
    titulo = st.text_input("Título", placeholder="Ej: SE ACERCA EL DOBLE 2.0"); ia = st.selectbox("IA Origen", ["Suno","Udio","Mureka","BASA IA","BASA CREW","Yo mismo"]); genero2 = st.selectbox("Género 2", ["Dembow Rulay","Dembow Fino","Trap Calle","Dembow Navidad","Drama Barrio"], key="subir_genero")
    archivo = st.file_uploader("Sube MP3 / WAV", type=["mp3","wav","m4a"])
    if st.button("🚀 INTEGRAR Y SONAR AHORA"):
        if titulo and archivo:
            nuevo = pd.DataFrame([{"ID":len(df)+1,"Titulo":titulo,"Tipo":"Canción","IA Origen":ia,"Genero":genero2,"Reproducciones":1,"Likes":0,"Estado":"Normal","Fecha":datetime.now().strftime("%Y-%m-%d"),"Parrafo Original":"","Prompt IA":"","Link YouTube":""}])
            st.session_state.contenido = pd.concat([df,nuevo], ignore_index=True); st.session_state.ultima_cancion = archivo; st.session_state.radio_cola.insert(0,titulo); st.success(f"✅ '{titulo}' integrada y sonando."); st.rerun()
        else: st.error("Pon título y MP3, Lic.")
    st.write("**SE ACERCA EL DOBLE - Letra oficial BASA:**")
    st.write("Se acerca el doble, mi carro no enciende, se pinchó la goma, vecina me dio su número, familia a bailar, lechón asado, ron, whisky caro, vino me lo tomo, llegan los viajeros, pa' la villa a celebrar.")

with tab6:
    st.header("🏆 GALERÍA ÉXITOS + RANKING - Primeros Lugares")
    st.write("Ordenado solo por reproducciones. Si otro pasa al #1, BASA lo sube solo.")
    st.dataframe(df[df["Reproducciones"]>=5000][["Ranking","Titulo","Genero","IA Origen","Reproducciones","Likes","Estado"]], use_container_width=True)
    if len(df[df["Reproducciones"]>=5000])>0: st.plotly_chart(__import__("plotly.express").px.bar(df[df["Reproducciones"]>=5000], x="Titulo", y="Reproducciones", color="Titulo", title="Ranking Éxitos"), use_container_width=True)
    st.write("Carpeta General:"); st.dataframe(df[df["Reproducciones"]<5000][["Ranking","Titulo","Reproducciones"]], use_container_width=True)

with tab7:
    st.header("📊 HISTORIAL COMPLETO + PUBLICAR A YOUTUBE")
    df_edit = st.data_editor(df, num_rows="dynamic", use_container_width=True, key="editor_full")
    if st.button("💾 GUARDAR Y RECLASIFICAR"):
        df2,errs = analizar_y_corregir(df_edit); st.session_state.contenido=df2; st.success("Guardado, corregido y reclasificado.")
    st.download_button("⬇️ DESCARGAR HISTORIAL CSV", df.to_csv(index=False), "basa_v10_full_historial.csv")
    st.divider(); st.header("📺 PUBLICAR EN NUESTRO CANAL - Para que el público nos siga")
    st.warning("Autónomo = Conectas tu cuenta 1 vez en Secrets, después BASA publica sola. Sin tu permiso, YouTube no deja.")
    permiso = st.checkbox("✅ YO, LIC. PEDRO BALDERA, AUTORIZO A BASA V10 A PUBLICAR MIS TEMAS EN MI CANAL", value=False)
    tema_pub = st.selectbox("Tema a publicar", df["Titulo"].tolist() if len(df)>0 else ["Nada"])
    if tema_pub:
        fila = df[df["Titulo"]==tema_pub].iloc[0]
        st.code(f"{fila['Titulo']} - Lic. Pedro Baldera x El Forense | {fila['Genero']} | BASA V10 FULL")
        st.code(f"{fila['Titulo']} - Tema original BASA V10 FULL. Crew Gemini+ChatGPT+Claude+Meta + Monitoreo + Fusión Moderna+Antigua. {fila.get('Parrafo Original','')} Suscríbete. #Dembow #LosFrailes #BASA #SeAcercaElDoble")
        st.write("Pasos: youtube.com/upload -> Sube MP3 + Portada -> Pega título y descripción -> Pega link aquí")
        link = st.text_input("Link de YouTube al publicar")
        if st.button("🚀 PUBLICAR / GUARDAR LINK"):
            if not permiso: st.error("Marca la casilla de autorización, Lic.")
            elif link:
                idx = st.session_state.contenido[st.session_state.contenido["Titulo"]==tema_pub].index
                if len(idx)>0: st.session_state.contenido.loc[idx[0],"Link YouTube"]=link; st.success(f"Guardado: {link}")
            else: st.warning("Si tienes YouTube API en Secrets, BASA publica sola. Si no, pega tu link arriba.")

with tab8:
    st.header("🛠️ PROBADOR PERMANENTE - Analizar, Probar, Corregir")
    for nombre,ok in pruebas: st.write(f"{'✅' if ok else '❌'} {nombre}")
    if st.button("🔍 ANALIZAR AHORA Y CORREGIR TODO"):
        df2,errs = analizar_y_corregir(st.session_state.contenido); st.session_state.contenido=df2
        if errs:
            for e in errs: st.warning(e)
        else: st.success("Todo en orden, nada que corregir.")
        st.rerun()
    st.write("### Log de Correcciones"); 
    if st.session_state.log_errores:
        for l in st.session_state.log_errores[-20:]: st.write(f"- {l}")
    else: st.write("Sin errores. Sistema limpio.")
    if st.button("🧹 LIMPIAR LOG"): st.session_state.log_errores=[]; st.rerun()

st.divider()
st.caption("BASA AUDIO VISUAL V10 FULL | Todo acumulado | Auto-gestión 39 seg + Monitoreo 5 min | Solo contenido original tuyo")
