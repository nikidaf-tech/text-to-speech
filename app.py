import os
import re
import time
import html
import asyncio
import io
import zipfile
import sqlite3
from datetime import datetime
import streamlit as st
import edge_tts
from gtts import gTTS
import PyPDF2
from docx import Document
import wave
import math
import base64
from pydub import AudioSegment
from num2words import num2words


# --- 1. ОПТИМИЗИРАНА БАЗА ДАННИ И КЕШИРАНЕ ---
def get_db_connection():
    conn = sqlite3.connect('tts_studio_pro.db', check_same_thread=False)
    return conn


@st.cache_resource
def init_db():
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute('''
                  CREATE TABLE IF NOT EXISTS history
                  (
                      id
                      INTEGER
                      PRIMARY
                      KEY
                      AUTOINCREMENT,
                      text
                      TEXT,
                      voice
                      TEXT,
                      audio
                      BLOB,
                      timestamp
                      TEXT,
                      is_favorite
                      INTEGER
                      DEFAULT
                      0,
                      tags
                      TEXT
                      DEFAULT
                      ''
                  )
                  ''')
        c.execute('''
                  CREATE TABLE IF NOT EXISTS lexicon
                  (
                      profile
                      TEXT,
                      word
                      TEXT,
                      replacement
                      TEXT,
                      PRIMARY
                      KEY
                  (
                      profile,
                      word
                  )
                      )
                  ''')
        conn.commit()


init_db()


@st.cache_data
def load_lexicons_from_db():
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT profile, word, replacement FROM lexicon")
        rows = c.fetchall()

    profiles = {
        "Технически": {"Vivacom": "Виваком", "AI": "Ей Ай", "Streamlit": "Стриймлит"},
        "Художествени": {"Mr.": "Мистър", "Mrs.": "Мисис"},
        "Общи": {}
    }

    for prof, w, r in rows:
        if prof not in profiles:
            profiles[prof] = {}
        profiles[prof][w] = r
    return profiles


def save_word_to_db(profile, word, replacement):
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO lexicon (profile, word, replacement) VALUES (?, ?, ?)",
                  (profile, word, replacement))
        conn.commit()
    st.cache_data.clear()


def delete_word_from_db(profile, word):
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM lexicon WHERE profile = ? AND word = ?", (profile, word))
        conn.commit()
    st.cache_data.clear()


# --- 2. НАСТРОЙКА НА СТРАНИЦАТА И НЕОНОВО-ЧЕРВЕН ДИЗАЙН ---
st.set_page_config(
    page_title="Text to Speech | Pro AI Studio Ultimate",
    page_icon="🎙️",
    layout="wide"
)

st.markdown("""
<style>
.main {
    background: linear-gradient(135deg, #050505 0%, #0a0a0a 100%);
    color: #f8fafc;
}
.stButton>button {
    width: 100%;
    border-radius: 14px;
    background: linear-gradient(135deg, #ef4444 0%, #991b1b 100%);
    color: white;
    font-weight: 600;
    border: none;
    padding: 0.75rem 1rem;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    box-shadow: 0 4px 14px rgba(239, 68, 68, 0.4);
}
.stButton>button:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(239, 68, 68, 0.7);
}
.stDownloadButton>button {
    width: 100%;
    border-radius: 14px;
    background: linear-gradient(135deg, #dc2626 0%, #7f1d1d 100%);
    color: white;
    font-weight: 600;
    border: none;
    padding: 0.75rem 1rem;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    box-shadow: 0 4px 14px rgba(220, 38, 38, 0.4);
}
.stDownloadButton>button:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(220, 38, 38, 0.7);
}
.stTextArea textarea {
    border-radius: 14px;
    background-color: #0a0a0a;
    color: #f8fafc;
    border: 1px solid #262626;
    box-shadow: inset 0 2px 4px rgba(0,0,0,0.5);
}
.stTextArea textarea:focus {
    border-color: #ef4444;
    box-shadow: 0 0 0 2px rgba(239, 68, 68, 0.4);
}
[data-testid="stSidebar"] {
    background-color: #020202;
    border-right: 1px solid #171717;
}
.footer {
    position: fixed;
    left: 0;
    bottom: 0;
    width: 100%;
    background-color: #020202;
    color: #a3a3a3;
    text-align: center;
    padding: 10px;
    font-size: 12px;
    border-top: 1px solid #171717;
    z-index: 999;
}
</style>
""", unsafe_allow_html=True)

# Инициализация на Session State
if "lexicon_profiles" not in st.session_state:
    st.session_state.lexicon_profiles = load_lexicons_from_db()

if "active_profile" not in st.session_state:
    st.session_state.active_profile = "Технически"

if "translated_text_cache" not in st.session_state:
    st.session_state.translated_text_cache = ""

if "last_generated_audio" not in st.session_state:
    st.session_state.last_generated_audio = None

if "last_paragraphs" not in st.session_state:
    st.session_state.last_paragraphs = []

# Заглавие
st.markdown(
    "<h1 style='text-align: center; background: linear-gradient(90deg, #f87171, #ef4444, #b91c1c); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-weight: 800;'>🎙️ Text to Speech AI Studio Ultimate Pro</h1>",
    unsafe_allow_html=True)
st.markdown(
    "<p style='text-align: center; color: #a3a3a3; margin-top: -10px;'>Професионална студийна система за генерация на реч, подкасти, дублаж и аудиокниги</p>",
    unsafe_allow_html=True)
st.markdown("---")

# --- 3. СТРАНИЧНА ЛЕНТА С КОНТРОЛИ ---
with st.sidebar:
    st.markdown("### 🎛️ Контролен панел")
    st.markdown("---")

    st.markdown("#### 🚀 Режим на работа:")
    app_section = st.radio(
        "Изберете режим:",
        options=[
            "Текст към аудио",
            "Пакетен експорт",
            "🌐 AI Преводач на текст",
            "📝 SRT Субтитри",
            "🎭 Аудио драма (Multi-Voice)",
            "🎵 Аудио миксер и фонове",
            "📚 Архив и библиотека"
        ],
        label_visibility="collapsed"
    )

    st.markdown("---")
    tts_engine = st.selectbox("🤖 Избор на AI двигател:",
                              ["Edge-TTS (Neural - Високо качество)", "gTTS (Google - Стандарт)"])

    LANG_CODES = {
        "Автоматично разпознаване": "auto",
        "Български (BG)": "bg",
        "Английски (EN)": "en",
        "Немски (DE)": "de",
        "Френски (FR)": "fr",
        "Испански (ES)": "es"
    }

    lang_choice = st.selectbox("🌍 Основен език:", ["Български (BG)", "Английски (EN)", "Немски (DE)"])
    current_lang_code = "bg" if "Български" in lang_choice else ("en" if "Английски" in lang_choice else "de")

    if "Edge" in tts_engine:
        if "Български" in lang_choice:
            voice_choice = st.radio("🎙️ Глас (BG):", ["👨 Борислав (Мъжки)", "👩 Калина (Женски)"])
            selected_voice = "bg-BG-BorislavNeural" if "Борислав" in voice_choice else "bg-BG-KalinaNeural"
        elif "Английски" in lang_choice:
            voice_choice = st.radio("🎙️ Глас (EN):", ["👨 Guy (US)", "👩 Aria (US)"])
            selected_voice = "en-US-GuyNeural" if "Guy" in voice_choice else "en-US-AriaNeural"
        else:
            voice_choice = st.radio("🎙️ Глас (DE):", ["👨 Killian (DE)", "👩 Katja (DE)"])
            selected_voice = "de-DE-KillianNeural" if "Killian" in voice_choice else "de-DE-KatjaNeural"
    else:
        selected_voice = current_lang_code

    st.markdown("---")
    st.markdown("#### 🎚️ Аудио Настройки")
    rate = st.slider("⚡ Скорост на говорене (%)", -50, 50, 0, 5)
    pitch = st.slider("🎵 Височина на тона (Hz)", -20, 20, 0, 1)
    volume = st.slider("🔊 Сила на звука (%)", 0, 100, 100, 5)

    st.markdown("---")
    with st.expander("📖 Речници и произношение", expanded=False):
        profile_choice = st.selectbox("Профил речник:", list(st.session_state.lexicon_profiles.keys()))
        st.session_state.active_profile = profile_choice
        current_lexicon = st.session_state.lexicon_profiles[profile_choice]

        if current_lexicon:
            for w, r in list(current_lexicon.items()):
                col_w1, col_w2 = st.columns([3, 1])
                with col_w1:
                    st.text(f"{w} ➔ {r}")
                with col_w2:
                    if st.button("🗑️", key=f"del_w_{profile_choice}_{w}"):
                        delete_word_from_db(profile_choice, w)
                        del st.session_state.lexicon_profiles[profile_choice][w]
                        st.rerun()
        else:
            st.info("Няма записани думи.")

        nw = st.text_input("Оригинална дума")
        nr = st.text_input("Фонетично произношение")
        if st.button("➕ Запази в речника"):
            if nw and nr:
                save_word_to_db(profile_choice, nw, nr)
                st.session_state.lexicon_profiles[profile_choice][nw] = nr
                st.success("Запазено успешно!")
                st.rerun()

    with st.expander("⚙️ Допълнителни опции", expanded=False):
        auto_play = st.checkbox("▶️ Автоматично пускане", value=True)
        show_stats = st.checkbox("📊 Показване на статистика", value=True)
        enable_bg_notify = st.checkbox("🔔 Браузърни известия", value=True)

rate_str = f"{rate:+d}%" if rate != 0 else "+0%"
pitch_str = f"{pitch:+d}Hz" if pitch != 0 else "+0Hz"
volume_str = f"{volume:+d}%" if volume != 100 else "+0%"

text_to_process = ""


# --- 4. ПОМОЩНИ ФУНКЦИИ И ДИНАМИЧЕН ПРОГРЕС БАР ---
def format_smart_time(total_seconds):
    total_seconds = int(round(total_seconds))
    if total_seconds < 1:
        return "1 сек."
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    parts = []
    if hours > 0:
        parts.append(f"{hours} ч.")
    if minutes > 0:
        parts.append(f"{minutes} мин.")
    if seconds > 0 or not parts:
        parts.append(f"{seconds} сек.")
    return " ".join(parts)


class DynamicProgressTracker:
    def __init__(self, total_steps, title="Обработка..."):
        self.total_steps = max(1, total_steps)
        self.title = title
        self.start_time = time.time()
        self.placeholder = st.empty()
        self.update(0, "Инициализиране...")

    def update(self, current_step, status_text=""):
        elapsed = time.time() - self.start_time
        pct = min(100.0, (current_step / self.total_steps) * 100)

        if current_step > 0:
            avg_time_per_step = elapsed / current_step
            remaining_steps = self.total_steps - current_step
            eta_seconds = remaining_steps * avg_time_per_step
            eta_str = format_smart_time(eta_seconds) if remaining_steps > 0 else "0 сек."
        else:
            eta_str = "Изчисляване..."

        elapsed_str = format_smart_time(elapsed)

        html_code = (
            f'<style>@keyframes redGlow {{ 0% {{ background-position: 100% 0%; }} 100% {{ background-position: -100% 0%; }} }}</style>'
            f'<div style="background: #0d0d0d; border: 1px solid #262626; border-radius: 16px; padding: 18px; margin: 12px 0; box-shadow: 0 4px 20px rgba(239, 68, 68, 0.15); font-family: sans-serif;">'
            f'<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">'
            f'<span style="color: #f8fafc; font-weight: 600; font-size: 15px;">{html.escape(self.title)}</span>'
            f'<span style="color: #ef4444; font-weight: 700; font-size: 15px;">{pct:.1f}%</span>'
            f'</div>'
            f'<div style="width: 100%; background-color: #171717; border-radius: 10px; height: 14px; overflow: hidden; box-shadow: inset 0 1px 3px rgba(0,0,0,0.8);">'
            f'<div style="width: {pct}%; height: 100%; background: linear-gradient(90deg, #ef4444, #dc2626, #b91c1c); background-size: 200% 100%; animation: redGlow 2s linear infinite; transition: width 0.3s ease; border-radius: 10px; box-shadow: 0 0 10px rgba(239, 68, 68, 0.7);"></div>'
            f'</div>'
            f'<div style="display: flex; justify-content: space-between; font-size: 12px; color: #a3a3a3; margin-top: 10px;">'
            f'<span>📌 {html.escape(status_text)} ({current_step}/{self.total_steps})</span>'
            f'<span>⏱️ Изминало: <b>{elapsed_str}</b> | ⏳ Оставащо: <b style="color: #f87171;">~{eta_str}</b></span>'
            f'</div>'
            f'</div>'
        )
        self.placeholder.markdown(html_code, unsafe_allow_html=True)

    def clear(self):
        self.placeholder.empty()


def extract_text_from_file(uploaded_file):
    if uploaded_file.size > 15 * 1024 * 1024:
        st.error("⚠️ Файлът е твърде голям! Максималният размер е 15 MB.")
        return ""
    ext = uploaded_file.name.split(".")[-1].lower()
    text = ""
    try:
        if ext == "txt":
            text = uploaded_file.getvalue().decode("utf-8")
        elif ext == "pdf":
            reader = PyPDF2.PdfReader(uploaded_file)
            for page in reader.pages:
                pt = page.extract_text()
                if pt:
                    text += pt + "\n"
        elif ext in ["doc", "docx"]:
            doc = Document(uploaded_file)
            for p in doc.paragraphs:
                text += p.text + "\n"
    except Exception as e:
        st.error(f"❌ Грешка при четене на файла: {e}")
    return text


def translate_long_text(text, src_code, tgt_code):
    try:
        from deep_translator import GoogleTranslator
        translator = GoogleTranslator(source=src_code, target=tgt_code)
        paragraphs = text.split("\n")
        chunks = []
        current_chunk = ""

        for p in paragraphs:
            if len(current_chunk) + len(p) + 1 < 4500:
                current_chunk += p + "\n"
            else:
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())
                if len(p) >= 4500:
                    for i in range(0, len(p), 4500):
                        chunks.append(p[i:i + 4500])
                    current_chunk = ""
                else:
                    current_chunk = p + "\n"

        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        if not chunks:
            return text

        tracker = DynamicProgressTracker(len(chunks), title="🌐 Превод на текст")
        translated_parts = []
        for idx, ch in enumerate(chunks, 1):
            translated_parts.append(translator.translate(ch))
            tracker.update(idx, status_text="Превеждане на сегмент")
        tracker.clear()

        return "\n\n".join(translated_parts)
    except ImportError:
        st.error("❌ Моля, инсталирайте библиотеката deep-translator: `pip install deep-translator`")
        return text
    except Exception as e:
        st.error(f"❌ Грешка при превод: {e}")
        return text


def convert_numbers_to_words(text, lang_code='bg'):
    decimal_joiner = {"bg": "цяло и", "en": "point", "de": "Komma"}.get(lang_code, "цяло и")

    def replace_match(match):
        num_str = match.group(0)
        try:
            if '.' in num_str or ',' in num_str:
                parts = num_str.replace(',', '.').split('.')
                whole = num2words(int(parts[0]), lang=lang_code)
                decimal = num2words(int(parts[1]), lang=lang_code)
                return f"{whole} {decimal_joiner} {decimal}"
            else:
                return num2words(int(num_str), lang=lang_code)
        except Exception:
            return num_str

    return re.sub(r'\b\d+(?:[.,]\d+)?\b', replace_match, text)


def clean_and_optimize_speech(text, lang_code='bg'):
    text = re.sub(r'<[^>]+>', '', text)
    text = convert_numbers_to_words(text, lang_code=lang_code)
    active_lexicon = st.session_state.lexicon_profiles[st.session_state.active_profile]
    for eng, bg in active_lexicon.items():
        text = text.replace(eng, bg)
    text = text.replace('/', ' ')
    text = re.sub(r'[\\|#_~^`]', ' ', text)
    if lang_code == 'bg':
        text = re.sub(r'\bнай\s*-\s*', 'най', text, flags=re.IGNORECASE)
        text = re.sub(r'\bпо\s*-\s*', 'по', text, flags=re.IGNORECASE)
        text = re.sub(r'\bѝ\b', 'и́', text)
        text = re.sub(r'\bЍ\b', 'И́', text)
    return re.sub(r'[ \t]+', ' ', text).strip()


def generate_srt_subtitles(text):
    sentences = [s.strip() for s in re.split(r'[.!?]+', text) if s.strip()]
    srt_output = ""
    start_time = 0.0
    for i, sentence in enumerate(sentences, 1):
        duration = max(2.0, len(sentence.split()) * 0.4)
        end_time = start_time + duration

        def format_time(seconds):
            h = int(seconds // 3600)
            m = int((seconds % 3600) // 60)
            s = int(seconds % 60)
            ms = int((seconds - int(seconds)) * 1000)
            return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

        srt_output += f"{i}\n{format_time(start_time)} --> {format_time(end_time)}\n{sentence}\n\n"
        start_time = end_time
    return srt_output


def run_async_safe(coro):
    try:
        return asyncio.run(coro)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


def _gtts_sync_generate(clean_text, lang):
    tts = gTTS(text=clean_text, lang=lang, slow=False)
    fp = io.BytesIO()
    tts.write_to_fp(fp)
    fp.seek(0)
    return fp.read()


async def generate_audio_bytes_async(text, voice, rate_s, pitch_s, volume_s, engine_choice, lang_code='bg'):
    clean_base_text = clean_and_optimize_speech(text, lang_code=lang_code)
    if "Edge" in engine_choice:
        communicate = edge_tts.Communicate(clean_base_text, voice, rate=rate_s, pitch=pitch_s, volume=volume_s)
        audio_buffer = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_buffer.write(chunk["data"])
        audio_buffer.seek(0)
        return audio_buffer.read()
    else:
        return await asyncio.to_thread(_gtts_sync_generate, clean_base_text, voice)


def generate_audio_bytes(text, voice, rate_s, pitch_s, volume_s, engine_choice, lang_code='bg'):
    return run_async_safe(
        generate_audio_bytes_async(text, voice, rate_s, pitch_s, volume_s, engine_choice, lang_code=lang_code)
    )


async def generate_audio_with_progress_async(text, voice, rate_s, pitch_s, volume_s, engine_choice, lang_code='bg'):
    clean_base_text = clean_and_optimize_speech(text, lang_code=lang_code)
    if "Edge" not in engine_choice:
        tracker = DynamicProgressTracker(1, title="🎙️ Синтезиране на реч (gTTS)")
        tracker.update(0, status_text="Изпращане към Google TTS...")
        res = await asyncio.to_thread(_gtts_sync_generate, clean_base_text, voice)
        tracker.update(1, status_text="Завършено")
        tracker.clear()
        return res

    chunks = [c.strip() for c in re.split(r'(?<=[.!?])\s+', clean_base_text) if c.strip()]
    if not chunks:
        chunks = [clean_base_text]

    tracker = DynamicProgressTracker(len(chunks), title="🎙️ Синтезиране на реч")
    audio_buffer = io.BytesIO()

    for idx, chunk_text in enumerate(chunks, 1):
        communicate = edge_tts.Communicate(chunk_text, voice, rate=rate_s, pitch=pitch_s, volume=volume_s)
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_buffer.write(chunk["data"])
        tracker.update(idx, status_text="Обработка на сегмент")

    tracker.clear()
    audio_buffer.seek(0)
    return audio_buffer.read()


def play_rich_notification(msg="Готово!"):
    sample_rate = 22050
    duration = 0.5
    frames = int(sample_rate * duration)
    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, 'wb') as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(sample_rate)
        data = bytearray()
        for i in range(frames):
            t = i / sample_rate
            val = int(32767 * 0.1 * math.sin(2 * math.pi * 659.25 * t) * math.exp(-4 * t))
            data.extend(val.to_bytes(2, byteorder='little', signed=True))
        f.writeframes(data)
    wav_buffer.seek(0)
    b64 = base64.b64encode(wav_buffer.read()).decode()
    st.components.v1.html(f"""
        <audio autoplay style="display:none;"><source src="data:audio/wav;base64,{b64}" type="audio/wav"></audio>
    """, height=0)


def render_3d_audio_player(audio_bytes, paragraphs=None, should_autoplay=True):
    b64_audio = base64.b64encode(audio_bytes).decode()
    options_html = ""
    if paragraphs:
        options_html = "<select id='paraSelect' style='background:#0a0a0a; color:#f8fafc; border:1px solid #262626; border-radius:10px; padding:10px; margin-bottom:14px; width:100%; font-size:14px; outline:none;'>"
        options_html += "<option value='0'>📑 Бърз скок по абзаци...</option>"
        for idx, p in enumerate(paragraphs):
            snippet = (p[:45] + '...') if len(p) > 45 else p
            safe_snippet = html.escape(snippet)
            options_html += f"<option value='{idx}'>Абзац {idx + 1}: {safe_snippet}</option>"
        options_html += "</select>"

    player_html = f"""
    <div style="background: linear-gradient(145deg, #0d0d0d, #020202); padding: 24px; border-radius: 20px; border: 1px solid #262626; box-shadow: 0 10px 25px rgba(239, 68, 68, 0.15); font-family: sans-serif; color: #f8fafc;">
        {options_html}
        <audio id="customAudio" style="display:none;"><source src="data:audio/mp3;base64,{b64_audio}" type="audio/mp3"></audio>

        <!-- Прогрес бар и време -->
        <div style="margin-bottom: 12px;">
            <input type="range" id="progressBar" value="0" min="0" max="100" step="0.1" style="width: 100%; accent-color: #ef4444; cursor: pointer; height: 6px; border-radius: 3px;">
            <div style="display: flex; justify-content: space-between; font-size: 12px; color: #a3a3a3; margin-top: 6px;">
                <span id="currentTime">0:00</span>
                <span id="durationTime">0:00</span>
            </div>
        </div>

        <!-- Контролни бутони, бутон за мютване и плъзгач за сила на звука -->
        <div style="display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap;">
            <div style="display: flex; gap: 8px; align-items: center; flex: 1; justify-content: center;">
                <button id="skipBackward" class="btn3d">⏪ -10с</button>
                <button id="playPauseBtn" class="btn3d" style="background: linear-gradient(135deg, #ef4444, #991b1b); padding: 10px 20px;">▶ Пусни</button>
                <button id="skipForward" class="btn3d">10с ⏩</button>
            </div>

            <!-- Секция за звук и мют -->
            <div style="display: flex; align-items: center; gap: 8px; background: #171717; padding: 6px 12px; border-radius: 10px; border: 1px solid #262626;">
                <button id="muteBtn" style="background: transparent; border: none; cursor: pointer; font-size: 16px; padding: 0;" title="Заглуши / Включи звук">🔊</button>
                <input type="range" id="volumeBar" value="100" min="0" max="100" step="1" style="width: 75px; accent-color: #ef4444; cursor: pointer; height: 4px;">
                <span id="volumeText" style="font-size: 11px; color: #a3a3a3; width: 30px; text-align: right;">100%</span>
            </div>
        </div>
    </div>
    <style>
        .btn3d {{
            background: linear-gradient(145deg, #171717, #0a0a0a);
            color: #f8fafc;
            border: 1px solid #383838;
            padding: 8px 16px;
            border-radius: 10px;
            font-weight: 600;
            cursor: pointer;
            box-shadow: 0 4px 10px rgba(0,0,0,0.5);
            transition: all 0.2s ease;
        }}
        .btn3d:hover {{
            background: linear-gradient(145deg, #262626, #171717);
            border-color: #ef4444;
            transform: translateY(-1px);
        }}
    </style>
    <script>
        const audio = document.getElementById('customAudio');
        const playBtn = document.getElementById('playPauseBtn');
        const progressBar = document.getElementById('progressBar');
        const currentTimeEl = document.getElementById('currentTime');
        const durationEl = document.getElementById('durationTime');
        const skipBack = document.getElementById('skipBackward');
        const skipFwd = document.getElementById('skipForward');
        const paraSelect = document.getElementById('paraSelect');
        const volumeBar = document.getElementById('volumeBar');
        const volumeText = document.getElementById('volumeText');
        const muteBtn = document.getElementById('muteBtn');

        let lastVolume = 100;

        function formatTime(sec) {{
            const m = Math.floor(sec / 60);
            const s = Math.floor(sec % 60);
            return m + ':' + (s < 10 ? '0' : '') + s;
        }}

        audio.addEventListener('loadedmetadata', () => {{
            durationEl.innerText = formatTime(audio.duration);
            audio.volume = volumeBar.value / 100;
            if ({str(should_autoplay).lower()}) {{
                audio.play().then(() => {{ playBtn.innerText = '⏸ Пауза'; }}).catch(e => console.log(e));
            }}
        }});

        playBtn.addEventListener('click', () => {{
            if (audio.paused) {{ audio.play(); playBtn.innerText = '⏸ Пауза'; }}
            else {{ audio.pause(); playBtn.innerText = '▶ Пусни'; }}
        }});

        audio.addEventListener('timeupdate', () => {{
            currentTimeEl.innerText = formatTime(audio.currentTime);
            if (audio.duration) progressBar.value = (audio.currentTime / audio.duration) * 100;
        }});

        progressBar.addEventListener('input', () => {{
            if (audio.duration) audio.currentTime = (progressBar.value / 100) * audio.duration;
        }});

        volumeBar.addEventListener('input', () => {{
            audio.volume = volumeBar.value / 100;
            volumeText.innerText = volumeBar.value + '%';
            if (audio.volume > 0) {{
                muteBtn.innerText = '🔊';
                lastVolume = volumeBar.value;
            }} else {{
                muteBtn.innerText = '🔇';
            }}
        }});

        muteBtn.addEventListener('click', () => {{
            if (audio.volume > 0) {{
                lastVolume = volumeBar.value;
                audio.volume = 0;
                volumeBar.value = 0;
                volumeText.innerText = '0%';
                muteBtn.innerText = '🔇';
            }} else {{
                const restoreVal = lastVolume > 0 ? lastVolume : 80;
                audio.volume = restoreVal / 100;
                volumeBar.value = restoreVal;
                volumeText.innerText = restoreVal + '%';
                muteBtn.innerText = '🔊';
            }}
        }});

        skipBack.addEventListener('click', () => {{ audio.currentTime = Math.max(0, audio.currentTime - 10); }});
        skipFwd.addEventListener('click', () => {{ audio.currentTime = Math.min(audio.duration, audio.currentTime + 10); }});

        if (paraSelect) {{
            paraSelect.addEventListener('change', (e) => {{
                const val = parseInt(e.target.value);
                if (audio.duration) {{
                    audio.currentTime = (val / {len(paragraphs) if paragraphs else 1}) * audio.duration;
                    audio.play();
                    playBtn.innerText = '⏸ Пауза';
                }}
            }});
        }}
    </script>
    """
    st.components.v1.html(player_html, height=210 if paragraphs else 170)


# --- 5. ОСНОВНИ РЕЖИМИ НА ПРИЛОЖЕНИЕТО ---
if app_section == "Текст към аудио":
    st.markdown("### 🎙️ Режим: Текст към аудио")
    tab_manual, tab_file, tab_templates = st.tabs(["✍️ Ръчен текст", "📁 Качване на файл", "✨ Бързи шаблони"])

    with tab_manual:
        default_val = st.session_state.translated_text_cache if st.session_state.translated_text_cache else ""
        manual_text = st.text_area("Въведете текст...", value=default_val, height=260, label_visibility="collapsed")
        if manual_text.strip():
            text_to_process = manual_text

    with tab_file:
        uploaded_file = st.file_uploader("Качете файл (.txt, .pdf, .docx)", type=["txt", "pdf", "docx"],
                                         label_visibility="collapsed")
        if uploaded_file is not None:
            extracted_text = extract_text_from_file(uploaded_file)
            if extracted_text.strip():
                st.success(f"✅ Успешно извлечени {len(extracted_text)} символа.")
                st.text_area("Преглед:", value=extracted_text, height=200, disabled=True)
                text_to_process = extracted_text

    with tab_templates:
        template_choice = st.selectbox("Изберете готов шаблон:", [
            "Подкаст интро",
            "Рекламен спот",
            "Медитативен текст",
            "Техническа статия"
        ])
        if st.button("Зареди шаблон"):
            if template_choice == "Подкаст интро":
                text_to_process = "Здравейте, скъпи слушатели! Днес в нашия подкаст ще разгледаме най-вълнуващите технологии и иновации в света на изкуствения интелект."
            elif template_choice == "Рекламен спот":
                text_to_process = "Търсите перфектното решение за вашия бизнес? Открийте новите ни предложения с несравнимо качество и топ цени!"
            elif template_choice == "Медитативен текст":
                text_to_process = "Вдишайте дълбоко... отпуснете се и се оставете на спокойствието да завладее всяка клетка от вашето тяло."
            else:
                text_to_process = "Системата работи стабилно. Стриймлит и Пайчарм осигуряват перфектна среда за бърза и надеждна разработка."
            st.success("Шаблонът е зареден в паметта!")

    if text_to_process.strip() and show_stats:
        words = len(text_to_process.split())
        chars = len(text_to_process)
        est_time = (words / 138) * 60
        st.info(
            f"📊 **Статистика:** {words} думи | {chars} символа | ⏱️ **Време за четене:** ~{format_smart_time(est_time)}")

    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        generate_btn = st.button("🎙️ Генерирай аудио запис", use_container_width=True)

    if generate_btn:
        if not text_to_process.strip():
            st.error("⚠️ Моля, въведете текст за обработка.")
        else:
            try:
                audio_bytes = run_async_safe(
                    generate_audio_with_progress_async(
                        text_to_process, selected_voice, rate_str, pitch_str, volume_str, tts_engine,
                        lang_code=current_lang_code
                    )
                )
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                with get_db_connection() as conn:
                    c = conn.cursor()
                    c.execute("INSERT INTO history (text, voice, audio, timestamp) VALUES (?, ?, ?, ?)",
                              (text_to_process[:50], selected_voice, sqlite3.Binary(audio_bytes), timestamp))
                    conn.commit()

                st.session_state.last_generated_audio = audio_bytes
                st.session_state.last_paragraphs = [p.strip() for p in text_to_process.split("\n\n") if p.strip()]
                play_rich_notification("Аудио записът е готов!")
            except Exception as e:
                st.error(f"❌ Грешка: {e}")

    if st.session_state.last_generated_audio is not None:
        st.markdown("### 🎧 Резултат:")
        render_3d_audio_player(
            st.session_state.last_generated_audio,
            paragraphs=st.session_state.last_paragraphs,
            should_autoplay=auto_play if generate_btn else False
        )

        st.markdown("#### 💾 Експорт на файл:")
        export_format = st.selectbox("Изберете аудио формат:", ["mp3", "wav", "ogg", "flac"])

        if export_format == "mp3":
            export_data = st.session_state.last_generated_audio
            mime_type = "audio/mp3"
            file_name = "speech.mp3"
        else:
            seg = AudioSegment.from_file(io.BytesIO(st.session_state.last_generated_audio), format="mp3")
            buf = io.BytesIO()
            seg.export(buf, format=export_format)
            export_data = buf.getvalue()
            mime_type = f"audio/{export_format}"
            file_name = f"speech.{export_format}"

        st.download_button(f"📥 Свали файл ({export_format.upper()})", data=export_data, file_name=file_name,
                           mime=mime_type, use_container_width=True)

elif app_section == "Пакетен експорт":
    st.markdown("### 📦 Режим: Пакетен експорт и разделяне на книги/учебници")
    st.markdown(
        "Поставете текст от книга или учебник. По подразбиране целият текст се третира като един документ, но можете да изберете разделяне по глави само при нужда.")

    batch_input_file = st.file_uploader("📂 Качете цяла книга/учебник (.txt, .pdf, .docx)", type=["txt", "pdf", "docx"])

    file_extracted_text = ""
    if batch_input_file is not None:
        file_extracted_text = extract_text_from_file(batch_input_file)

    batch_text = st.text_area("Или поставете текста на книгата тук...", value=file_extracted_text, height=240)

    if batch_text.strip():
        # Превключвател: Дали да се дели автоматично или целият текст да е един файл
        split_mode = st.radio(
            "Режим на обработка на текста:",
            ["📄 Третирай целия текст като един документ", "📑 Раздели го на глави / части (по заглавия)"]
        )

        if "Третирай целия текст" in split_mode:
            chapters = [batch_text]
        else:
            # Търсим само реални заглавия (напр. нов ред, последван от 'Глава X' или 'Част X')
            raw_chapters = re.split(r'\n(?=(?:Глава|Част|Chapter|Раздел)\s+\d+)', batch_text, flags=re.IGNORECASE)
            chapters = [c.strip() for c in raw_chapters if c.strip()]
            if not chapters:
                chapters = [batch_text]

        st.markdown(f"📖 **Общ брой документи/части за генерация: {len(chapters)}**")

        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            batch_btn = st.button("🚀 Генерирай пакета", use_container_width=True)

        if batch_btn:
            total_parts = len(chapters)
            tracker = DynamicProgressTracker(total_parts, title="📦 Пакетна генерация")
            semaphore = asyncio.Semaphore(4)


            async def process_all_parts():
                async def process_single(order_num, chap_text):
                    async with semaphore:
                        b = await generate_audio_bytes_async(
                            chap_text, selected_voice, rate_str, pitch_str, volume_str, tts_engine,
                            lang_code=current_lang_code
                        )
                        return order_num, b

                tasks = [process_single(i, ch) for i, ch in enumerate(chapters, 1)]
                results = []
                completed = 0

                for f in asyncio.as_completed(tasks):
                    order_num, b = await f
                    results.append((order_num, b))
                    completed += 1
                    tracker.update(completed, status_text=f"Генерация на част {order_num} от {total_parts}")
                return results


            try:
                loop_results = run_async_safe(process_all_parts())
                valid_results = [r for r in loop_results if r is not None]

                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                    for part_num, part_bytes in valid_results:
                        zf.writestr(f"chast_{part_num:02d}.mp3", part_bytes)
                zip_buffer.seek(0)

                tracker.clear()
                play_rich_notification("Пакетът е готов!")
                st.success(f"✅ Успешно генерирани и архивирани {len(valid_results)} файла!")

                st.download_button("📥 Изтегли всички части в ZIP архив", data=zip_buffer,
                                   file_name="audiobook_export.zip",
                                   mime="application/zip", use_container_width=True)

                st.markdown("#### 📂 Индивидуално сваляне:")
                for part_num, part_bytes in sorted(valid_results):
                    st.download_button(f"📥 Свали Част {part_num} (.mp3)", data=part_bytes,
                                       file_name=f"chast_{part_num:02d}.mp3", mime="audio/mp3",
                                       key=f"dl_part_{part_num}")

            except Exception as e:
                tracker.clear()
                st.error(f"❌ Грешка: {e}")

elif app_section == "🌐 AI Преводач на текст":
    st.markdown("### 🌐 Режим: AI Преводач и Локализация")
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        source_lang = st.selectbox("От език:", list(LANG_CODES.keys()), index=2)
    with col_t2:
        target_lang = st.selectbox("Към език:", [k for k in LANG_CODES.keys() if k != "Автоматично разпознаване"],
                                   index=0)

    tr_text = st.text_area("Текст за превод:", height=180)
    if st.button("🌐 Преведи текста"):
        if not tr_text.strip():
            st.warning("⚠️ Моля, въведете текст.")
        else:
            translated = translate_long_text(tr_text, LANG_CODES[source_lang], LANG_CODES[target_lang])
            st.session_state.translated_text_cache = translated
            st.success("✅ Преводът е готов!")

    if st.session_state.translated_text_cache:
        st.text_area("Резултат:", value=st.session_state.translated_text_cache, height=200)
        st.download_button("📥 Свали превода (.txt)", data=st.session_state.translated_text_cache,
                           file_name="translated.txt", mime="text/plain", use_container_width=True)

elif app_section == "📝 SRT Субтитри":
    st.markdown("### 📝 Режим: Генериране на SRT субтитри")
    srt_input = st.text_area("Текст за субтитри:", height=240)
    if st.button("📝 Създай SRT субтитри", use_container_width=True):
        if not srt_input.strip():
            st.warning("⚠️ Въведете текст.")
        else:
            srt_content = generate_srt_subtitles(srt_input)
            st.success("✅ Успешно генерирани субтитри!")
            st.text_area("SRT код:", value=srt_content, height=200)
            st.download_button("📥 Свали .srt файл", data=srt_content, file_name="subtitles.srt", mime="text/plain",
                               use_container_width=True)

elif app_section == "🎭 Аудио драма (Multi-Voice)":
    st.markdown("### 🎭 Режим: Аудио драма с редуване на гласове (Асинхронен)")
    st.markdown("Пример: `[Борислав]: Здравей!` или `[Калина]: Здрасти!`")
    drama_input = st.text_area("Сценарий:", value="[Борислав]: Здравей, Калина!\n[Калина]: Здрасти, как си?",
                               height=220)

    col_d1, col_d2 = st.columns(2)
    with col_d1:
        v_a = st.selectbox("Глас 1 ([Борислав]):", ["bg-BG-BorislavNeural", "en-US-GuyNeural"])
    with col_d2:
        v_b = st.selectbox("Глас 2 ([Калина]):", ["bg-BG-KalinaNeural", "en-US-AriaNeural"])

    if st.button("🎭 Генерирай аудио драма", use_container_width=True):
        if not drama_input.strip():
            st.warning("⚠️ Въведете сценарий.")
        else:
            lines = [l.strip() for l in drama_input.split("\n") if l.strip()]
            tracker = DynamicProgressTracker(len(lines), title="🎭 Синтезиране на аудио драма")
            semaphore = asyncio.Semaphore(4)


            async def process_drama():
                async def process_line(idx, line):
                    async with semaphore:
                        curr_v = v_a
                        spoken = line
                        if line.startswith("[Борислав]"):
                            curr_v = v_a
                            spoken = line.replace("[Борислав]:", "").replace("[Борислав]", "")
                        elif line.startswith("[Калина]"):
                            curr_v = v_b
                            spoken = line.replace("[Калина]:", "").replace("[Калина]", "")

                        line_lang = "en" if "en-US" in curr_v else "bg"
                        chunk_bytes = await generate_audio_bytes_async(
                            spoken, curr_v, rate_str, pitch_str, volume_str, "Edge-TTS", lang_code=line_lang
                        )
                        return idx, chunk_bytes

                tasks = [process_line(i, l) for i, l in enumerate(lines)]
                results = [None] * len(lines)
                completed = 0

                for f in asyncio.as_completed(tasks):
                    idx, chunk_bytes = await f
                    results[idx] = chunk_bytes
                    completed += 1
                    tracker.update(completed, status_text=f"Реплика {completed} от {len(lines)}")
                return results


            try:
                line_bytes_list = run_async_safe(process_drama())
                combined = AudioSegment.empty()
                for cb in line_bytes_list:
                    seg = AudioSegment.from_file(io.BytesIO(cb), format="mp3")
                    combined += seg + AudioSegment.silent(duration=400)

                buf = io.BytesIO()
                combined.export(buf, format="mp3")
                res_bytes = buf.getvalue()

                tracker.clear()
                play_rich_notification("Драмата е готова!")
                st.success("✅ Готово!")
                render_3d_audio_player(res_bytes, should_autoplay=auto_play)
                st.download_button("📥 Свали драмата (.mp3)", data=res_bytes, file_name="drama.mp3", mime="audio/mp3",
                                   use_container_width=True)
            except Exception as e:
                tracker.clear()
                st.error(f"❌ Грешка: {e}")

elif app_section == "🎵 Аудио миксер и фонове":
    st.markdown("### 🎵 Режим: Аудио миксер (Реч + Фонова музика)")
    mix_text = st.text_area("Текст за речта:", height=140)
    bg_file = st.file_uploader("🎵 Качи фонова музика (.mp3, .wav)", type=["mp3", "wav"])
    bg_vol = st.slider("🔊 Сила на музиката спрямо речта (dB)", -30, 0, -12)

    if st.button("🎵 Генерирай смесен запис", use_container_width=True):
        if not mix_text.strip() or not bg_file:
            st.warning("⚠️ Моля, въведете текст и качете фонова музика.")
        else:
            tracker = DynamicProgressTracker(3, title="🎵 Миксиране на аудио")
            try:
                tracker.update(0, status_text="Синтезиране на реч...")
                speech_b = generate_audio_bytes(
                    mix_text, selected_voice, rate_str, pitch_str, volume_str, tts_engine, lang_code=current_lang_code
                )
                tracker.update(1, status_text="Обработка на фоновата музика...")
                speech_seg = AudioSegment.from_file(io.BytesIO(speech_b), format="mp3")
                music_seg = AudioSegment.from_file(bg_file)

                if len(music_seg) < len(speech_seg):
                    music_seg = music_seg * math.ceil(len(speech_seg) / len(music_seg))
                music_seg = music_seg[:len(speech_seg)] + bg_vol

                tracker.update(2, status_text="Смесване и експорт...")
                mixed = speech_seg.overlay(music_seg)
                buf = io.BytesIO()
                mixed.export(buf, format="mp3")
                mixed_bytes = buf.getvalue()

                tracker.update(3, status_text="Готово!")
                tracker.clear()
                play_rich_notification("Готово!")
                st.success("✅ Успешен микс!")
                render_3d_audio_player(mixed_bytes, should_autoplay=auto_play)
                st.download_button("📥 Свали микса (.mp3)", data=mixed_bytes, file_name="mixed.mp3",
                                   mime="audio/mp3", use_container_width=True)
            except Exception as e:
                tracker.clear()
                st.error(f"❌ Грешка: {e}")

else:
    st.markdown("### 📚 Режим: Архив и библиотека")
    with get_db_connection() as conn:
        c = conn.cursor()
        search_q = st.text_input("🔍 Търсене в историята:")
        if search_q:
            c.execute("SELECT id, text, timestamp, is_favorite FROM history WHERE text LIKE ? ORDER BY id DESC",
                      (f"%{search_q}%",))
        else:
            c.execute("SELECT id, text, timestamp, is_favorite FROM history ORDER BY id DESC")
        rows = c.fetchall()

        if rows:
            if st.button("🗑️ Изчисти цялата история"):
                c.execute("DELETE FROM history")
                conn.commit()
                st.rerun()

            for row in rows:
                rec_id, rec_text, rec_time, is_fav = row
                col_a, col_b, col_c = st.columns([4, 1, 1])
                with col_a:
                    fav_icon = "⭐" if is_fav else "☆"
                    st.markdown(f"**#{rec_id}** ({rec_time}) {fav_icon}\n_{rec_text}_")
                with col_b:
                    if st.button(f"📥 Зареди", key=f"lib_load_{rec_id}"):
                        c.execute("SELECT audio FROM history WHERE id = ?", (rec_id,))
                        audio_blob = c.fetchone()[0]
                        render_3d_audio_player(audio_blob, should_autoplay=False)
                with col_c:
                    fav_txt = "Премахни ⭐" if is_fav else "Маркирай ⭐"
                    if st.button(fav_txt, key=f"fav_{rec_id}"):
                        new_fav = 0 if is_fav else 1
                        c.execute("UPDATE history SET is_favorite = ? WHERE id = ?", (new_fav, rec_id))
                        conn.commit()
                        st.rerun()
                st.markdown("---")
        else:
            st.info("Няма записи в архива.")

# --- 6. ФУТЕР ---
st.markdown(
    '<div class="footer">© 2026 Създадено от Никола Дафинкичов. Всички права запазени.<br>© 2026 Created by Nikola Dafinkichov. All rights reserved.</div>',
    unsafe_allow_html=True
)
