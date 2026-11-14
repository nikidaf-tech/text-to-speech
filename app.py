import os
import re
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


# Инициализиране на SQLite база данни с разширена структура
def init_db():
    conn = sqlite3.connect('tts_studio.db', check_same_thread=False)
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
    conn.commit()
    return conn


db_conn = init_db()

# Настройка на страницата
st.set_page_config(
    page_title="Text to Speech | Pro AI Studio Ultimate",
    page_icon="🎙️",
    layout="wide"
)

# Ултрамодерен CSS дизайн със стъклени панели и 3D елементи
st.markdown("""
    <style>
    .main {
        background-color: #0b0f19;
        color: #f8fafc;
    }
    .stButton>button {
        width: 100%;
        border-radius: 12px;
        background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
        color: white;
        font-weight: 600;
        border: none;
        padding: 0.7rem 1rem;
        transition: all 0.3s ease;
        box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
    }
    .stButton>button:hover {
        opacity: 0.95;
        transform: translateY(-2px);
        box-shadow: 0 6px 16px rgba(59, 130, 246, 0.4);
    }
    .stDownloadButton>button {
        width: 100%;
        border-radius: 12px;
        background: linear-gradient(135deg, #10b981 0%, #059669 100%);
        color: white;
        font-weight: 600;
        border: none;
        padding: 0.7rem 1rem;
        transition: all 0.3s ease;
        box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3);
    }
    .stDownloadButton>button:hover {
        opacity: 0.95;
        transform: translateY(-2px);
        box-shadow: 0 6px 16px rgba(16, 185, 129, 0.4);
    }
    .stTextArea textarea {
        border-radius: 12px;
        background-color: #1e293b;
        color: #f8fafc;
        border: 1px solid #334155;
    }

    .stRadio [role="radiogroup"] {
        background-color: #1e293b;
        padding: 16px;
        border-radius: 16px;
        border: 1px solid #334155;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
        display: flex;
        flex-direction: column;
        gap: 8px;
    }
    .stRadio label {
        font-weight: 500 !important;
        color: #e2e8f0 !important;
        padding: 8px 12px;
        border-radius: 10px;
        background: rgba(15, 23, 42, 0.6);
        border: 1px solid rgba(51, 65, 85, 0.5);
        transition: all 0.25s ease;
    }
    .stRadio label:hover {
        background: rgba(59, 130, 246, 0.15);
        border-color: #3b82f6;
        color: #60a5fa !important;
        cursor: pointer;
        transform: translateX(4px);
    }

    [data-testid="stSidebar"] {
        background-color: #0f172a;
        border-right: 1px solid #1e293b;
    }
    .footer {
        position: fixed;
        left: 0;
        bottom: 0;
        width: 100%;
        background-color: #0b0f19;
        color: #64748b;
        text-align: center;
        padding: 8px;
        font-size: 13px;
        border-top: 1px solid #1e293b;
        z-index: 999;
        line-height: 1.4;
    }
    </style>
""", unsafe_allow_html=True)

# Сесийни речници по категории
if "lexicon_profiles" not in st.session_state:
    st.session_state.lexicon_profiles = {
        "Технически": {"Vivacom": "Виваком", "AI": "Ей Ай", "Streamlit": "Стриймлит"},
        "Художествени": {"Mr.": "Мистър", "Mrs.": "Мисис"},
        "Общи": {}
    }

if "active_profile" not in st.session_state:
    st.session_state.active_profile = "Технически"

if "translated_text_cache" not in st.session_state:
    st.session_state.translated_text_cache = ""

# Заглавие на приложението
st.markdown(
    "<h1 style='text-align: center; background: linear-gradient(90deg, #3b82f6, #60a5fa); -webkit-background-clip: text; -webkit-text-fill-color: transparent;'>🎙️ Text to Speech AI Studio Ultimate</h1>",
    unsafe_allow_html=True)
st.markdown("---")

# СТРАНИЧНА ЛЕНТА С КОНТРОЛИ И НАСТРОЙКИ
with st.sidebar:
    st.markdown("### Възможности и настройки")
    st.markdown("---")

    st.markdown("#### 🗂️ Избор на работен режим")
    app_section = st.radio(
        "Изберете отдел:",
        options=["🎙️ Студио за генерация", "📦 Пакетен експорт на книги", "🌐 AI Преводач на текст",
                 "📚 Архив и библиотека"],
        help="Превключвайте между генерация, пакетен експорт, преводач и пълна библиотека с история."
    )

    st.markdown("---")

    # Избор на двигател
    st.markdown("#### ⚙️ TTS Двигател")
    tts_engine = st.selectbox("Изберете двигател:", ["Edge-TTS (Neural - Високо качество)", "gTTS (Google - Стандарт)"])

    st.markdown("#### 🌍 Език и Глас")
    lang_choice = st.selectbox("Изберете език:", ["Български (BG)", "Английски (EN)", "Немски (DE)"])

    if "Edge" in tts_engine:
        if "Български" in lang_choice:
            voice_choice = st.radio("Глас (BG):", ["👨 Борислав (Мъжки)", "👩 Калина (Женски)"])
            selected_voice = "bg-BG-BorislavNeural" if "Борислав" in voice_choice else "bg-BG-KalinaNeural"
        elif "Английски" in lang_choice:
            voice_choice = st.radio("Глас (EN):", ["👨 Guy (US)", "👩 Aria (US)"])
            selected_voice = "en-US-GuyNeural" if "Guy" in voice_choice else "en-US-AriaNeural"
        else:
            voice_choice = st.radio("Глас (DE):", ["👨 Killian (DE)", "👩 Katja (DE)"])
            selected_voice = "de-DE-KillianNeural" if "Killian" in voice_choice else "de-DE-KatjaNeural"
    else:
        selected_voice = "bg" if "Български" in lang_choice else ("en" if "Английски" in lang_choice else "de")

    st.markdown("---")
    st.markdown("#### 🎚️ Аудио Настройки")
    rate = st.slider("⚡ Скорост на говорене (%)", -50, 50, 0, 5)
    pitch = st.slider("🎵 Височина на тона (Hz)", -20, 20, 0, 1)
    volume = st.slider("🔊 Сила на звука (%)", 0, 100, 100, 5)

    st.markdown("---")
    st.markdown("#### 🎛️ Разширени аудио ефекти")
    add_silence = st.checkbox("🔇 Добавяне на пауза (0.5с) в началото/края", value=False)
    normalize_audio = st.checkbox("🎚️ Нормализация и изчистване на шумове", value=True)

    st.markdown("---")
    with st.expander("📖 Речници по профили", expanded=False):
        profile_choice = st.selectbox("Профил речник:", list(st.session_state.lexicon_profiles.keys()))
        st.session_state.active_profile = profile_choice

        current_lexicon = st.session_state.lexicon_profiles[profile_choice]
        nw = st.text_input("Дума за замяна")
        nr = st.text_input("Как да се чете")
        if st.button("➕ Добави в профила"):
            if nw and nr:
                current_lexicon[nw] = nr
                st.success("Добавено в речника!")
        st.json(current_lexicon)

    with st.expander("⚙️ Опции за изход", expanded=False):
        auto_play = st.checkbox("▶️ Автоматично пускане", value=True)
        show_stats = st.checkbox("📊 Показване на статистика", value=True)
        generate_srt = st.checkbox("📝 SRT субтитри", value=True)

rate_str = f"{rate:+d}%" if rate != 0 else "+0%"
pitch_str = f"{pitch:+d}Hz" if pitch != 0 else "+0Hz"
volume_str = f"{volume:+d}%" if volume != 100 else "+0%"

text_to_process = ""

LANG_CODES = {
    "Автоматично разпознаване": "auto",
    "Български (BG)": "bg",
    "Английски (EN)": "en",
    "Немски (DE)": "de",
    "Френски (FR)": "fr",
    "Испански (ES)": "es"
}


def extract_text_from_file(uploaded_file):
    file_extension = uploaded_file.name.split(".")[-1].lower()
    file_text = ""
    if file_extension == "txt":
        file_text = uploaded_file.getvalue().decode("utf-8")
    elif file_extension == "pdf":
        reader = PyPDF2.PdfReader(uploaded_file)
        for page in reader.pages:
            pt = page.extract_text()
            if pt:
                file_text += pt + "\n"
    elif file_extension in ["doc", "docx"]:
        doc = Document(uploaded_file)
        for p in doc.paragraphs:
            file_text += p.text + "\n"
    return file_text


def translate_long_text(text, src_code, tgt_code):
    from deep_translator import GoogleTranslator
    translator = GoogleTranslator(source=src_code, target=tgt_code)

    # Разделяне на текста на части до 4500 символа, за да не се надвишава лимитът на API-то
    paragraphs = text.split("\n")
    translated_parts = []
    current_chunk = ""

    for p in paragraphs:
        if len(current_chunk) + len(p) + 1 < 4500:
            current_chunk += p + "\n"
        else:
            if current_chunk.strip():
                translated_parts.append(translator.translate(current_chunk.strip()))
            # Ако един параграф е по-дълъг от 4500 символа
            if len(p) >= 4500:
                for i in range(0, len(p), 4500):
                    translated_parts.append(translator.translate(p[i:i + 4500]))
                current_chunk = ""
            else:
                current_chunk = p + "\n"

    if current_chunk.strip():
        translated_parts.append(translator.translate(current_chunk.strip()))

    return "\n\n".join(translated_parts)


def format_smart_time(total_seconds):
    total_seconds = int(round(total_seconds))
    if total_seconds < 1: return "1 сек."
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    parts = []
    if hours > 0: parts.append(f"{hours} ч.")
    if minutes > 0: parts.append(f"{minutes} мин.")
    if seconds > 0 or not parts: parts.append(f"{seconds} сек.")
    return " ".join(parts)


# Почистване на наклонени черти и излишни символи
def clean_and_optimize_speech(text):
    active_lexicon = st.session_state.lexicon_profiles[st.session_state.active_profile]
    for eng, bg in active_lexicon.items():
        text = text.replace(eng, bg)

    text = text.replace('/', ' ')
    text = re.sub(r'[\\|#_~^`]', ' ', text)
    text = re.sub(r'\bнай\s*-\s*', 'най', text, flags=re.IGNORECASE)
    text = re.sub(r'\bпо\s*-\s*', 'по', text, flags=re.IGNORECASE)
    text = re.sub(r'\bѝ\b', 'и́', text)
    text = re.sub(r'\bЍ\b', 'И́', text)
    return re.sub(r'\s+', ' ', text).strip()


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


async def generate_audio_bytes(text, voice, rate_s, pitch_s, volume_s, engine_choice):
    processed_text = clean_and_optimize_speech(text)

    if "Edge" in engine_choice:
        if "<break" in processed_text:
            ssml_text = f"<speak>{processed_text}</speak>"
            communicate = edge_tts.Communicate(ssml_text, voice, rate=rate_s, pitch=pitch_s, volume=volume_s)
        else:
            communicate = edge_tts.Communicate(processed_text, voice, rate=rate_s, pitch=pitch_s, volume=volume_s)
        audio_buffer = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_buffer.write(chunk["data"])
        audio_buffer.seek(0)
        return audio_buffer.read()
    else:
        tts = gTTS(text=processed_text, lang=voice, slow=False)
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        return fp.read()


def play_rich_notification():
    sample_rate = 22050
    duration = 0.65
    frames = int(sample_rate * duration)
    wav_buffer = io.BytesIO()
    frequencies = [523.25, 659.25, 783.99, 1046.50]
    with wave.open(wav_buffer, 'wb') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        data = bytearray()
        for i in range(frames):
            t = i / sample_rate
            sample_val = 0.0
            for idx, freq in enumerate(frequencies):
                start_t = idx * 0.08
                if t >= start_t:
                    local_t = t - start_t
                    envelope = math.exp(-5.0 * local_t)
                    sample_val += math.sin(2 * math.pi * freq * local_t) * envelope
            combined = int(32767 * 0.15 * (sample_val / len(frequencies)))
            data.extend(combined.to_bytes(2, byteorder='little', signed=True))
        wav_file.writeframes(data)
    wav_buffer.seek(0)
    b64 = base64.b64encode(wav_buffer.read()).decode()
    st.markdown(f"""
        <audio autoplay style="display:none;">
            <source src="data:audio/wav;base64,{b64}" type="audio/wav">
        </audio>
    """, unsafe_allow_html=True)


# Перфектно затворен и симетричен 3D плеър
def render_3d_audio_player(audio_bytes, paragraphs=None, should_autoplay=True):
    b64_audio = base64.b64encode(audio_bytes).decode()
    options_html = ""
    if paragraphs:
        options_html = "<select id='paraSelect' style='background:#0f172a; color:#f8fafc; border:1px solid #334155; border-radius:10px; padding:8px 12px; margin-bottom:14px; width:100%; font-size:14px; outline:none; box-shadow: inset 0 2px 4px rgba(0,0,0,0.3);'>"
        options_html += "<option value='0'>📑 Изберете абзац / секция за бърз скок...</option>"
        for idx, p in enumerate(paragraphs):
            snippet = (p[:50] + '...') if len(p) > 50 else p
            options_html += f"<option value='{idx}'>Абзац {idx + 1}: {snippet}</option>"
        options_html += "</select>"

    player_html = f"""
    <div style="background: linear-gradient(145deg, #1e293b, #0f172a); padding: 22px 24px; border-radius: 20px; border: 1px solid #334155; box-shadow: 0 10px 30px rgba(0,0,0,0.5), inset 0 1px 1px rgba(255,255,255,0.1); font-family: sans-serif; color: #f8fafc; margin: 0 auto; max-width: 100%;">
        {options_html}
        <audio id="customAudio" style="display:none;">
            <source src="data:audio/mp3;base64,{b64_audio}" type="audio/mp3">
        </audio>
        <div style="margin-bottom: 14px;">
            <input type="range" id="progressBar" value="0" min="0" max="100" step="0.1" style="width: 100%; accent-color: #3b82f6; cursor: pointer; height: 6px; border-radius: 3px;">
            <div style="display: flex; justify-content: space-between; font-size: 12px; color: #94a3b8; margin-top: 6px;">
                <span id="currentTime">0:00</span>
                <span id="durationTime">0:00</span>
            </div>
        </div>
        <div style="display: flex; gap: 12px; align-items: center; justify-content: center;">
            <button id="skipBackward" class="btn3d" title="Назад 10 сек.">⏪ -10с</button>
            <button id="playPauseBtn" class="btn3d" style="background: linear-gradient(135deg, #3b82f6, #1d4ed8); font-size: 15px; padding: 10px 22px;">▶ Пусни</button>
            <button id="skipForward" class="btn3d" title="Напред 10 сек.">10с ⏩</button>
        </div>
    </div>
    <style>
        .btn3d {{
            background: linear-gradient(145deg, #334155, #1e293b);
            color: #f8fafc;
            border: 1px solid #475569;
            padding: 8px 16px;
            border-radius: 12px;
            font-weight: 600;
            cursor: pointer;
            box-shadow: 0 6px 12px rgba(0,0,0,0.3), inset 0 1px 1px rgba(255,255,255,0.15);
            transition: all 0.15s ease;
        }}
        .btn3d:hover {{
            background: linear-gradient(145deg, #475569, #334155);
            box-shadow: 0 4px 8px rgba(0,0,0,0.4), inset 0 1px 1px rgba(255,255,255,0.2);
            transform: translateY(-1px);
        }}
        .btn3d:active {{
            transform: translateY(2px);
            box-shadow: 0 2px 4px rgba(0,0,0,0.4), inset 0 1px 1px rgba(0,0,0,0.2);
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
        const storageKey = 'tts_3d_audio_pos_{hash(audio_bytes)}';

        function formatTime(seconds) {{
            const m = Math.floor(seconds / 60);
            const s = Math.floor(seconds % 60);
            return m + ':' + (s < 10 ? '0' : '') + s;
        }}

        audio.addEventListener('loadedmetadata', () => {{
            durationEl.innerText = formatTime(audio.duration);
            const savedTime = localStorage.getItem(storageKey);
            if (savedTime) {{
                audio.currentTime = parseFloat(savedTime);
                progressBar.value = (audio.currentTime / audio.duration) * 100;
            }}
            if ({str(should_autoplay).lower()}) {{
                audio.play().then(() => {{
                    playBtn.innerText = '⏸ Пауза';
                }}).catch(e => console.log("Autoplay blocked:", e));
            }}
        }});

        playBtn.addEventListener('click', () => {{
            if (audio.paused) {{
                audio.play();
                playBtn.innerText = '⏸ Пауза';
            }} else {{
                audio.pause();
                playBtn.innerText = '▶ Пусни';
            }}
        }});

        audio.addEventListener('timeupdate', () => {{
            currentTimeEl.innerText = formatTime(audio.currentTime);
            if (!audio.paused && audio.duration) {{
                progressBar.value = (audio.currentTime / audio.duration) * 100;
            }}
            localStorage.setItem(storageKey, audio.currentTime);
        }});

        progressBar.addEventListener('input', () => {{
            if (audio.duration) {{
                audio.currentTime = (progressBar.value / 100) * audio.duration;
            }}
        }});

        skipBack.addEventListener('click', () => {{ audio.currentTime = Math.max(0, audio.currentTime - 10); }});
        skipFwd.addEventListener('click', () => {{ audio.currentTime = Math.min(audio.duration, audio.currentTime + 10); }});

        if (paraSelect) {{
            paraSelect.addEventListener('change', (e) => {{
                const val = parseInt(e.target.value);
                if (audio.duration) {{
                    const totalParas = {len(paragraphs) if paragraphs else 1};
                    audio.currentTime = (val / totalParas) * audio.duration;
                    audio.play();
                    playBtn.innerText = '⏸ Пауза';
                }}
            }});
        }}
    </script>
    """
    st.components.v1.html(player_html, height=205 if paragraphs else 165)


# ОСНОВНИ ОТДЕЛИ
if app_section == "🎙️ Студио за генерация":
    st.markdown("### 🎙️ Отдел: Генерация на аудио (Ръчен текст и файлове)")
    sub_tab1, sub_tab2 = st.tabs(["✍️ Ръчно въвеждане", "📁 Качване на файлове"])

    with sub_tab1:
        default_val = st.session_state.translated_text_cache if st.session_state.translated_text_cache else ""
        manual_text = st.text_area("Текстово поле", value=default_val,
                                   placeholder="Въведете текст тук или го преведете през преводача...", height=280,
                                   label_visibility="collapsed")
        if manual_text.strip(): text_to_process = manual_text

    with sub_tab2:
        uploaded_file = st.file_uploader("Изберете файл", type=["txt", "pdf", "docx"], label_visibility="collapsed")
        if uploaded_file is not None:
            try:
                file_text = extract_text_from_file(uploaded_file)
                if file_text.strip():
                    st.success(f"✅ Успешно извлечен текст от файла! ({len(file_text)} символа)")

                    # ОПЦИЯ ЗА АВТОМАТИЧЕН ПРЕВОД НА КАЧЕНИЯ ФАЙЛ
                    auto_translate_file = st.checkbox("🌐 Автоматичен превод на текста от файла преди озвучаване",
                                                      value=False)

                    if auto_translate_file:
                        col_f1, col_f2 = st.columns(2)
                        with col_f1:
                            f_src_lang = st.selectbox("Изходен език на файла:", list(LANG_CODES.keys()), index=0,
                                                      key="f_src")
                        with col_f2:
                            f_tgt_lang = st.selectbox("Преведи файла на:",
                                                      [k for k in LANG_CODES.keys() if k != "Автоматично разпознаване"],
                                                      index=0, key="f_tgt")

                        file_cache_key = f"trans_{uploaded_file.name}_{f_src_lang}_{f_tgt_lang}"

                        if file_cache_key not in st.session_state:
                            with st.spinner("🌐 Превеждане на документа..."):
                                st.session_state[file_cache_key] = translate_long_text(
                                    file_text, LANG_CODES[f_src_lang], LANG_CODES[f_tgt_lang]
                                )

                        translated_file_text = st.session_state[file_cache_key]
                        st.text_area("Преглед на преведения текст от файла", translated_file_text, height=200)

                        st.download_button(
                            label="📥 Изтегли преведения текст (.txt)",
                            data=translated_file_text,
                            file_name=f"translated_{uploaded_file.name.rsplit('.', 1)[0]}.txt",
                            mime="text/plain"
                        )
                        text_to_process = translated_file_text
                    else:
                        st.text_area("Преглед на извлечения текст", file_text, height=200)
                        text_to_process = file_text
            except ImportError:
                st.error("❌ Моля, инсталирайте deep_translator (pip install deep_translator) за превод на файлове.")
            except Exception as e:
                st.error(f"❌ Грешка при обработка на файла: {e}")

    if text_to_process.strip() and show_stats:
        words_count = len(text_to_process.split())
        chars_count = len(text_to_process)
        base_wpm = 138
        adjusted_wpm = base_wpm * (1 + rate / 100.0)
        total_audio_seconds = (words_count / adjusted_wpm) * 60

        audio_time_str = format_smart_time(total_audio_seconds)
        total_gen_seconds = max(1.5, (chars_count / 450) * 1.2)
        gen_time_str = format_smart_time(total_gen_seconds)

        st.info(
            f"📊 **Статистика:** {words_count} думи | {chars_count} символа\n\n"
            f"⏱️ **Приблизително време за слушане:** `~{audio_time_str}` | ⚡ **Очаквано време за генерация:** `~{gen_time_str}`"
        )

    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        generate_btn = st.button("🎙️ Генерирай аудио", use_container_width=True)

    if generate_btn:
        if not text_to_process.strip():
            st.error("⚠️ Моля, въведете текст.")
        else:
            with st.spinner(f"⏳ Обработка, генериране на аудио и SRT субтитри (очаквано време: ~{gen_time_str})..."):
                try:
                    audio_bytes = asyncio.run(
                        generate_audio_bytes(text_to_process, selected_voice, rate_str, pitch_str, volume_str,
                                             tts_engine))
                    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    c = db_conn.cursor()
                    c.execute("INSERT INTO history (text, voice, audio, timestamp) VALUES (?, ?, ?, ?)",
                              (text_to_process[:50], selected_voice, sqlite3.Binary(audio_bytes), current_time))
                    db_conn.commit()

                    play_rich_notification()
                    st.markdown("### 🎧 Готов аудио запис:")
                    paragraphs_list = [p.strip() for p in text_to_process.split("\n\n") if p.strip()]
                    render_3d_audio_player(audio_bytes, paragraphs=paragraphs_list, should_autoplay=auto_play)

                    st.download_button("📥 Свали MP3 файл", data=audio_bytes, file_name="generated_speech.mp3",
                                       mime="audio/mp3", use_container_width=True)
                    if generate_srt:
                        srt_content = generate_srt_subtitles(text_to_process)
                        st.download_button("📝 Изтегли SRT субтитри", data=srt_content, file_name="subtitles.srt",
                                           mime="text/plain", use_container_width=True)
                except Exception as e:
                    st.error(f"❌ Грешка: {e}")

elif app_section == "📦 Пакетен експорт на книги":
    st.markdown("### 📦 Отдел: Интелигентен пакетен експорт за книги")
    export_text = st.text_area("Голям текст", placeholder="Поставете цялата книга тук...", height=260,
                               label_visibility="collapsed")

    if export_text.strip(): text_to_process = export_text

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        batch_btn = st.button("📦 Интелигентен ZIP пакет", use_container_width=True)

    if batch_btn:
        if not text_to_process.strip():
            st.error("⚠️ Моля, въведете текст.")
        else:
            with st.spinner("📦 Разпознаване на глави и архивиране..."):
                try:
                    chapters = re.split(r'\n(?=Глава|Част|\b[ІVXLCM]+\b)', text_to_process)
                    if len(chapters) <= 1:
                        chapters = [p.strip() for p in text_to_process.split("\n\n") if p.strip()]
                    if not chapters: chapters = [text_to_process]

                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                        for idx, chap in enumerate(chapters, 1):
                            part_bytes = asyncio.run(
                                generate_audio_bytes(chap, selected_voice, rate_str, pitch_str, volume_str, tts_engine))
                            zip_file.writestr(f"glava_{idx:02d}.mp3", part_bytes)
                    zip_buffer.seek(0)

                    play_rich_notification()
                    st.success(f"✅ Успешно генерирани и архивирани {len(chapters)} глави в ZIP!")
                    st.download_button("📥 Изтегли ZIP архив с книги", data=zip_buffer, file_name="audio_book_batch.zip",
                                       mime="application/zip", use_container_width=True)
                except Exception as e:
                    st.error(f"❌ Грешка: {e}")

elif app_section == "🌐 AI Преводач на текст":
    st.markdown("### 🌐 AI Преводач и локализация на текст и файлове")
    st.markdown("Изберете посока на превод и въведете текст или качете файл за прецизен и естествен превод.")

    col_t1, col_t2 = st.columns(2)
    with col_t1:
        source_lang = st.selectbox("От език:", list(LANG_CODES.keys()), index=2)
    with col_t2:
        target_lang = st.selectbox("Към език:", [k for k in LANG_CODES.keys() if k != "Автоматично разпознаване"],
                                   index=0)

    tr_tab1, tr_tab2 = st.tabs(["✍️ Текст за превод", "📁 Качване на файл за превод"])

    text_to_translate = ""
    with tr_tab1:
        source_text = st.text_area("Текст за превод:", placeholder="Въведете текст тук...", height=180)
        if source_text.strip():
            text_to_translate = source_text

    with tr_tab2:
        tr_file = st.file_uploader("Качете документ за превод (.txt, .pdf, .docx)", type=["txt", "pdf", "docx"],
                                   key="tr_uploader")
        if tr_file is not None:
            try:
                extracted = extract_text_from_file(tr_file)
                if extracted.strip():
                    st.success(f"✅ Извлечен текст от {tr_file.name} ({len(extracted)} символа)")
                    st.text_area("Извлечен текст:", value=extracted, height=150, disabled=True)
                    text_to_translate = extracted
            except Exception as e:
                st.error(f"❌ Грешка при четене на файла: {e}")

    if st.button("🌐 Преведи"):
        if not text_to_translate.strip():
            st.warning("⚠️ Моля, въведете текст или качете файл за превод.")
        else:
            with st.spinner("⏳ Извършване на превод..."):
                try:
                    src_code = LANG_CODES[source_lang]
                    tgt_code = LANG_CODES[target_lang]

                    translated = translate_long_text(text_to_translate, src_code, tgt_code)
                    st.session_state.translated_text_cache = translated
                    st.success("✅ Успешен превод!")
                except ImportError:
                    st.error(
                        "❌ Моля, инсталирайте deep_translator (pip install deep_translator) за пълна функционалност на преводача.")
                except Exception as e:
                    st.error(f"❌ Грешка при превода: {e}")

    if st.session_state.translated_text_cache:
        st.text_area("Резултат от превода:", value=st.session_state.translated_text_cache, height=200)
        col_tr_btn1, col_tr_btn2 = st.columns(2)
        with col_tr_btn1:
            st.download_button(
                label="📥 Свали превода (.txt)",
                data=st.session_state.translated_text_cache,
                file_name="translated_document.txt",
                mime="text/plain",
                use_container_width=True
            )
        with col_tr_btn2:
            if st.button("🎙️ Изпрати в Студиото за генерация", use_container_width=True):
                st.success("✅ Текстът е готов в студиото! Изберете '🎙️ Студио за генерация' от менюто вляво.")

else:
    st.markdown("### 📚 Пълна архивна библиотека и любими")
    c = db_conn.cursor()

    search_query = st.text_input("🔍 Търсене в историята по текст:")
    if search_query:
        c.execute("SELECT id, text, timestamp, is_favorite FROM history WHERE text LIKE ? ORDER BY id DESC",
                  (f"%{search_query}%",))
    else:
        c.execute("SELECT id, text, timestamp, is_favorite FROM history ORDER BY id DESC")
    rows = c.fetchall()

    if rows:
        if st.button("🗑️ Изчисти цялата история"):
            c.execute("DELETE FROM history")
            db_conn.commit()
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
                fav_btn_text = "Премахни ⭐" if is_fav else "Маркирай ⭐"
                if st.button(fav_btn_text, key=f"fav_{rec_id}"):
                    new_fav = 0 if is_fav else 1
                    c.execute("UPDATE history SET is_favorite = ? WHERE id = ?", (new_fav, rec_id))
                    db_conn.commit()
                    st.rerun()
            st.markdown("---")
    else:
        st.info("Няма записи в архивната библиотека.")

# ФУТЕР
st.markdown("""
    <div class="footer">
        © 2026 Създадено от Никола Дафинкичов. Всички права запазени.<br>
        © 2026 Created by Nikola Dafinkichov. All rights reserved.
    </div>
""", unsafe_allow_html=True)