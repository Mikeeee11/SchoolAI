"""
MVP — AI-функції: ШІ-помічник для школярів.
Уся робота з AI живе тут, окремо від інтерфейсу (app.py).
"""

import base64
import io
import os

from dotenv import load_dotenv
from openai import OpenAI
from PIL import Image

load_dotenv()  # читає OPENAI_API_KEY з файлу .env

MODEL = "gpt-4o-mini"  # дешева модель, яка вміє і текст, і картинки

SYSTEM_PROMPT = """Ты — дружелюбный помощник для школьников.
Правила:
- Объясняй простым языком, шаг за шагом, с короткими примерами.
- Не просто выдавай готовый ответ: покажи ход решения, чтобы ученик понял тему.
- В конце задай один короткий вопрос для проверки понимания.
- Если вопрос не по учёбе или неподходящий для детей — вежливо переведи разговор на учёбу.
- Отвечай на том языке, на котором пишет ученик."""

_client = None


def _get_client():
    """Создаём клиента один раз и проверяем, что ключ есть."""
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("Не найден OPENAI_API_KEY. Добавь его в файл .env")
        _client = OpenAI(api_key=api_key)
    return _client


def _image_to_data_url(image):
    if not isinstance(image, Image.Image):
        image = Image.open(image)
    image = image.convert("RGB")
    image.thumbnail((1280, 1280))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=85)
    b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/jpeg;base64,{b64}"


def main_ai_function(user_input, history=None, image=None):
    """Главная AI-функция.

    user_input: текст вопроса ученика.
    history:    список прошлых сообщений [{"role": "user"/"assistant", "content": "..."}]
                (в Streamlit это st.session_state.messages).
    image:      необязательно — фото задания (файл или PIL.Image).
    Возвращает: текст ответа (str).
    """
    user_input = (user_input or "").strip()
    if not user_input and image is None:
        return "Напиши вопрос или загрузи фото задания 🙂"

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if history:
        messages.extend(history[-10:])  # последние 10 сообщений, чтобы не раздувать запрос

    if image is not None:
        content = [
            {"type": "text", "text": user_input or "Помоги разобраться с этим заданием."},
            {"type": "image_url", "image_url": {"url": _image_to_data_url(image)}},
        ]
    else:
        content = user_input
    messages.append({"role": "user", "content": content})

    try:
        response = _get_client().chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=0.5,
            max_tokens=800,
        )
        return response.choices[0].message.content
    except RuntimeError as e:
        return f"⚠️ {e}"
    except Exception as e:
        return f"⚠️ Не удалось получить ответ от ИИ: {e}"


if __name__ == "__main__":
    print(main_ai_function("Объясни, что такое дробь, для 5 класса"))