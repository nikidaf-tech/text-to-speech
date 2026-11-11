import asyncio
import os
import streamlit as st
import edge_tts

st.set_page_config(page_title="Текст към Реч (Български)", page_icon="🎙️", layout="centered")

st.title("🎙️ Български текст към говор")
st.write("Напишете текст или качете текстов файл, изберете глас и генерирайте реалистично аудио.")

# Избор на режим на въвеждане
input_method = st.radio("Изберете как да въведете текст:", ["Писане на текст", "Качване на текстов файл (.txt)"])

text_content = ""

if input_method == "Писане на текст":
    text_content = st.text_area("Въведете вашия текст тук:",
                                "Здравейте! Това е уеб приложение за генериране на българска реч.")
else:
    uploaded_file = st.file_uploader("Качете текстов файл", type=["txt"])
    if uploaded_file is not None:
        text_content = uploaded_file.read().decode("utf-8")
        st.text_area("Прочетен текст от файла:", text_content, height=150)

# Избор на глас
voice_choice = st.selectbox(
    "Изберете глас:",
    ("bg-BG-BorislavNeural (Мъжки)", "bg-BG-KalinaNeural (Женски)")
)

# Извличане на точния идентификатор на гласа
voice_id = voice_choice.split(" ")[0]

if st.button("🎵 Генерирай аудио", type="primary"):
    if not text_content.strip():
        st.warning("Моля, въведете или качете текст преди да генерирате аудио.")
    else:
        output_file = "output.mp3"

        with st.spinner("Генериране на аудио, моля изчакайте..."):
            async def generate():
                communicate = edge_tts.Communicate(text_content, voice_id)
                await communicate.save(output_file)


            asyncio.run(generate())

        st.success("Аудиото е готово!")

        # Възпроизвеждане в браузъра
        st.audio(output_file, format="audio/mp3")

        # Бутон за изтегляне
        with open(output_file, "rb") as f:
            st.download_button(
                label="📥 Изтегли MP3 файл",
                data=f,
                file_name="bulgarian_speech.mp3",
                mime="audio/mp3"
            )
