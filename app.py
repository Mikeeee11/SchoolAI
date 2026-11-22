"""
School Bot — чат-інтерфейс у стилі ChatGPT.
Можливості: поле вводу зі скріпкою (фото), швидкі питання, історія чату.

Запуск:  streamlit run app.py
Потрібно: pip install -U streamlit   (версія 1.43 або новіша)
"""

import inspect
import time

import streamlit as st

from ai_functions import main_ai_function

# ---------------------------------------------------------------------------
# Налаштування
# ---------------------------------------------------------------------------
st.set_page_config(page_title="School Bot", page_icon="🎓", layout="centered")

USER_AVATAR = "🧑‍🎓"
BOT_AVATAR = "🎓"
IMAGE_TYPES = ["png", "jpg", "jpeg", "webp"]

SUBJECTS = [
    "Будь-який предмет",
    "Математика",
    "Українська мова",
    "Англійська мова",
    "Історія",
    "Фізика",
    "Хімія",
    "Біологія",
    "Інформатика",
]

# Швидкі питання: {x} — це тема, параграф, задача тощо
QUICK_TEMPLATES = {
    "💡 Поясни тему": "Поясни простими словами: {x}",
    "📖 Конспект параграфа": "Зроби короткий конспект: {x}",
    "📝 Склади тест": "Склади тест із 5 питань з відповідями за темою: {x}",
    "🧒 Поясни як п'ятикласнику": "Поясни так, щоб зрозумів п'ятикласник: {x}",
    "✅ Перевір мою відповідь": "Перевір мою відповідь і вкажи на помилки: {x}",
    "🗓️ План підготовки": "Склади план підготовки до контрольної з теми: {x}",
}

SUGGESTIONS = [
    ("📐", "Поясни теорему Піфагора простими словами"),
    ("📝", "Склади тест із 5 питань з історії України"),
    ("🧪", "Що таке хімічні реакції? Дай приклади"),
    ("📸", "Розв'яжи задачу з фото (натисни 📎 внизу)"),
]

# ---------------------------------------------------------------------------
# Стилі
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    #MainMenu, footer, header {visibility: hidden;}
    .block-container {padding-top: 2rem; padding-bottom: 7rem; max-width: 780px;}

    .hero {text-align: center; padding: 2.5rem 0 1.5rem;}
    .hero h1 {
        font-size: 2.6rem; margin: 0;
        background: linear-gradient(90deg, #4F46E5, #06B6D4);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    }
    .hero p {color: #6B7280; font-size: 1.05rem; margin-top: .4rem;}

    [data-testid="stChatMessage"] {
        border-radius: 16px; padding: 0.9rem 1rem; margin-bottom: .6rem;
    }
    [data-testid="stChatInput"] {border-radius: 24px;}
    [data-testid="stChatInput"] textarea {border-radius: 24px;}

    div.stButton > button {
        border-radius: 12px; border: 1px solid #E5E7EB;
        padding: .7rem 1rem; width: 100%; transition: all .15s ease;
    }
    div.stButton > button:hover {
        border-color: #4F46E5; color: #4F46E5; transform: translateY(-1px);
    }
    section[data-testid="stSidebar"] {border-right: 1px solid #E5E7EB;}
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Стан сесії
# ---------------------------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending" not in st.session_state:
    st.session_state.pending = None  # {"text": str, "images": list}


# ---------------------------------------------------------------------------
# Допоміжні функції
# ---------------------------------------------------------------------------
def render_message(msg):
    """Показує одне повідомлення (з картинками, якщо є)."""
    avatar = USER_AVATAR if msg["role"] == "user" else BOT_AVATAR
    with st.chat_message(msg["role"], avatar=avatar):
        for img in msg.get("images", []):
            st.image(img["data"], width=260)
        st.markdown(msg["content"])


def stream_text(text):
    """Ефект «друкування» відповіді, як у ChatGPT."""
    for word in text.split(" "):
        yield word + " "
        time.sleep(0.015)


def ask_ai(text, images, history):
    """
    Викликає main_ai_function. Якщо вона вміє приймати images / history —
    передає їх; якщо ні — працює лише з текстом.
    """
    params = inspect.signature(main_ai_function).parameters
    kwargs = {}
    if images and "images" in params:
        kwargs["images"] = images
    if history and "history" in params:
        kwargs["history"] = history
    if images and "images" not in params:
        st.warning(
            "Фото додано, але функція main_ai_function поки не приймає параметр "
            "`images`. Додай його в ai_functions.py — тоді бот бачитиме картинки."
        )
    return main_ai_function(text, **kwargs)


# ---------------------------------------------------------------------------
# Бічна панель
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## 🎓 School Bot")
    st.caption("Твій AI-помічник у навчанні")

    if st.button("➕ Новий чат"):
        st.session_state.messages = []
        st.rerun()

    st.divider()
    subject = st.selectbox("📚 Предмет", SUBJECTS)

    st.divider()
    st.markdown("### ⚡ Швидке питання")
    template_name = st.selectbox("Що зробити?", list(QUICK_TEMPLATES.keys()))
    topic = st.text_input("Тема / параграф (X)", placeholder="напр.: § 12 Теорема Піфагора")
    if st.button("Запитати"):
        if topic.strip():
            question = QUICK_TEMPLATES[template_name].format(x=topic.strip())
            st.session_state.pending = {"text": question, "images": []}
            st.rerun()
        else:
            st.warning("Впиши тему або параграф.")

# ---------------------------------------------------------------------------
# Привітальний екран
# ---------------------------------------------------------------------------
if not st.session_state.messages and not st.session_state.pending:
    st.markdown(
        """
        <div class="hero">
            <h1>School Bot</h1>
            <p>Запитуй що завгодно про школу — поясню, перевірю, допоможу підготуватись.<br>
            Можна прикріпити фото задачі чи конспекту 📎</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    cols = st.columns(2)
    for i, (icon, text) in enumerate(SUGGESTIONS):
        if cols[i % 2].button(f"{icon}  {text}", key=f"sug_{i}"):
            st.session_state.pending = {"text": text, "images": []}
            st.rerun()

# ---------------------------------------------------------------------------
# Історія
# ---------------------------------------------------------------------------
for msg in st.session_state.messages:
    render_message(msg)

# ---------------------------------------------------------------------------
# Поле вводу (текст + прикріплення фото)
# ---------------------------------------------------------------------------
chat_value = st.chat_input(
    "Напиши питання або прикріпи фото 📎",
    accept_file="multiple",
    file_type=IMAGE_TYPES,
)

submitted = None
if chat_value:
    images = [
        {"data": f.getvalue(), "media_type": f.type, "name": f.name}
        for f in (chat_value.files or [])
    ]
    text = (chat_value.text or "").strip()
    if not text and images:
        text = "Розбери це зображення і поясни, що на ньому."
    if text:
        submitted = {"text": text, "images": images}
elif st.session_state.pending:
    submitted = st.session_state.pending
st.session_state.pending = None

# ---------------------------------------------------------------------------
# Обробка запиту
# ---------------------------------------------------------------------------
if submitted:
    user_msg = {"role": "user", "content": submitted["text"], "images": submitted["images"]}
    history = list(st.session_state.messages)  # історія ДО цього повідомлення
    st.session_state.messages.append(user_msg)
    render_message(user_msg)

    ai_text = submitted["text"]
    if subject != "Будь-який предмет":
        ai_text = f"[Предмет: {subject}] {ai_text}"

    with st.chat_message("assistant", avatar=BOT_AVATAR):
        try:
            with st.spinner("School Bot думає..."):
                result = str(ask_ai(ai_text, submitted["images"], history))
            st.write_stream(stream_text(result))
            st.session_state.messages.append({"role": "assistant", "content": result})
        except Exception as e:
            st.error(f"Щось пішло не так: {e}")