import streamlit as st
from openai import OpenAI
from audio_recorder_streamlit import audio_recorder
from datetime import datetime

st.set_page_config(page_title="Interprète FR ↔ EN (voix)", page_icon="🎙️", layout="centered")

client = OpenAI()

# ---------- Helpers ----------
def detect_lang(text: str) -> str:
    """Return 'fr' or 'en'."""
    resp = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": "Detect the language of the user text. Reply with only 'fr' or 'en'."},
            {"role": "user", "content": text.strip()},
        ],
        temperature=0,
        max_tokens=2,
    )
    out = resp.choices[0].message.content.strip().lower()
    return "fr" if out.startswith("fr") else "en"

def translate(text: str, source_lang: str, tone: str) -> str:
    target_lang = "English" if source_lang == "fr" else "French"
    style_line = {
        "Warm & polite": "Warm, polite, and welcoming.",
        "Professional": "Professional and clear.",
        "Friendly": "Friendly and natural.",
        "Short & direct": "Short, direct, and clear.",
    }[tone]

    resp = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    f"You are an interpreter. Output ONLY {target_lang}. "
                    "Do not add extra facts. Keep meaning the same. "
                    f"Style: {style_line}"
                ),
            },
            {"role": "user", "content": text.strip()},
        ],
        temperature=0.2,
    )
    return resp.choices[0].message.content.strip()

def tts(text: str, voice: str) -> bytes:
    speech = client.audio.speech.create(
        model="gpt-4o-mini-tts",
        voice=voice,
        input=text,
    )
    return speech.read()

def stt(audio_bytes: bytes) -> str:
    """
    Compatible PC + Android : essaie plusieurs formats.
    """
    candidates = [
        ("audio.webm", "audio/webm"),
        ("audio.wav", "audio/wav"),
        ("audio.mp4", "audio/mp4"),
        ("audio.m4a", "audio/mp4"),
        ("audio.ogg", "audio/ogg"),
    ]

    last_error = None
    for filename, mime in candidates:
        try:
            transcript = client.audio.transcriptions.create(
                model="gpt-4o-mini-transcribe",
                file=(filename, audio_bytes, mime),
            )
            text = (transcript.text or "").strip()
            if text:
                return text
        except Exception as e:
            last_error = e

    raise last_error

def add_history(item: dict):
    st.session_state.history.insert(0, item)
    st.session_state.history = st.session_state.history[:10]  # garder 10 dernières

# ---------- Session state ----------
if "history" not in st.session_state:
    st.session_state.history = []
if "mode" not in st.session_state:
    st.session_state.mode = "Mode simple"

# ---------- UI ----------
st.title("🎙️ Interprète FR ↔ EN (voix)")
st.caption("FR → EN (voix) • EN → FR (voix)")

with st.sidebar:
    st.subheader("⚙️ Réglages")
    st.session_state.mode = st.radio("Affichage", ["Mode simple", "Mode client (gros boutons)"])
    tone = st.selectbox("Style", ["Warm & polite", "Professional", "Friendly", "Short & direct"], index=0)
    voice_en = st.selectbox("Voix (anglais)", ["nova", "alloy", "shimmer", "echo", "fable", "onyx", "sage", "verse"], index=0)
    voice_fr = st.selectbox("Voix (français)", ["nova", "alloy", "shimmer", "echo", "fable", "onyx", "sage", "verse"], index=2)

    st.divider()
    if st.button("🧹 Effacer l’historique", use_container_width=True):
        st.session_state.history = []

# ---------- Main recorder ----------
if st.session_state.mode == "Mode client (gros boutons)":
    st.markdown("## 👇 Appuie et parle")
    st.markdown("### 🧑‍💼 Toi (FR) ➜ Client (EN)")
    audio_fr = audio_recorder(text="🎤 ENREGISTRER (FR)", icon_name="microphone", icon_size="3x")
    st.markdown("### 👤 Client (EN) ➜ Toi (FR)")
    audio_en = audio_recorder(text="🎤 RECORD (EN)", icon_name="microphone", icon_size="3x")

    audio_bytes = audio_fr if audio_fr else audio_en
else:
    st.markdown("### 🎤 Enregistre une phrase (toi ou le client)")
    audio_bytes = audio_recorder(text="🎤 Enregistrer", icon_name="microphone", icon_size="2x")

# ---------- Processing ----------
if audio_bytes:
    with st.spinner("Transcription..."):
        original = stt(audio_bytes)

    st.write("### ✍️ Texte détecté")
    st.text_area("Original", original, height=90)

    with st.spinner("Détection de langue..."):
        lang = detect_lang(original)

    st.write(f"Langue détectée : **{'Français' if lang == 'fr' else 'English'}**")

    with st.spinner("Traduction..."):
        translated = translate(original, source_lang=lang, tone=tone)

    st.write("### 🔁 Interprétation")
    st.text_area("Traduction", translated, height=110)

    with st.spinner("Voix..."):
        audio_out = tts(translated, voice=(voice_en if lang == "fr" else voice_fr))

    st.audio(audio_out, format="audio/mp3")

    add_history({
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source_lang": lang,
        "original": original,
        "translated": translated,
        "audio": audio_out,
    })

# ---------- History ----------
st.divider()
st.subheader("🕘 Historique (10 dernières)")
if not st.session_state.history:
    st.info("Aucune phrase pour l’instant.")
else:
    for i, h in enumerate(st.session_state.history, start=1):
        direction = "FR ➜ EN" if h["source_lang"] == "fr" else "EN ➜ FR"
        with st.expander(f"{i}. {direction} • {h['time']}"):
            st.markdown("**Original :**")
            st.write(h["original"])
            st.markdown("**Traduction :**")
            st.write(h["translated"])

            st.audio(h["audio"], format="audio/mp3")
