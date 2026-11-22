"""
MVP — AI-функції: ШІ-помічник для школярів.
Уся робота з AI живе тут, окремо від інтерфейсу (app.py).

Ключ API НЕ обов'язковий. Провайдери пробуються по черзі:
1. OpenAI        — тільки якщо в .env є OPENAI_API_KEY (необов'язково).
2. Pollinations  — безкоштовний публічний сервіс, ключ не потрібен.
3. Ollama        — локальна модель на твоєму ПК (якщо встановлена).
"""

import base64
import io
import os

from dotenv import load_dotenv
from openai import OpenAI
from PIL import Image

load_dotenv()  # читає OPENAI_API_KEY з файлу .env (якщо він є)

SYSTEM_PROMPT = """Ти — дружелюбний помічник для школярів.
Правила:
- Пояснюй простою мовою, крок за кроком, з короткими прикладами.
- Не просто видавай готову відповідь: покажи хід розв'язання, щоб учень зрозумів тему.
- Наприкінці став одне коротке запитання для перевірки розуміння.
- Якщо питання не про навчання або неприйнятне для дітей — чемно переведи розмову на навчання.
- Відповідай тією мовою, якою пише учень (українською, російською чи іншою). Якщо мова незрозуміла — відповідай українською."""


def _providers():
    """Список провайдерів за пріоритетом: (назва, base_url, ключ, модель)."""
    result = []
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        result.append(("OpenAI", None, api_key, "gpt-4o-mini"))
    # Безкоштовний сервіс без ключа (будь-який рядок як "ключ" — просто заглушка)
    result.append((
        "Pollinations",
        os.getenv("FREE_API_URL", "https://text.pollinations.ai/openai"),
        "no-key-needed",
        os.getenv("FREE_API_MODEL", "openai"),
    ))
    # Локальна модель, якщо встановлена Ollama
    result.append((
        "Ollama",
        os.getenv("OLLAMA_URL", "http://localhost:11434/v1"),
        "ollama",
        os.getenv("OLLAMA_MODEL", "gemma3:4b"),
    ))
    return result


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
    """Головна AI-функція.

    user_input: текст запитання учня.
    history:    список попередніх повідомлень [{"role": "user"/"assistant", "content": "..."}]
                (у Streamlit це st.session_state.messages).
    image:      необов'язково — фото завдання (файл або PIL.Image).
    Повертає: текст відповіді (str).
    """
    user_input = (user_input or "").strip()
    if not user_input and image is None:
        return "Напиши запитання або завантаж фото завдання 🙂"

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if history:
        messages.extend(history[-10:])  # останні 10 повідомлень, щоб не роздувати запит

    if image is not None:
        content = [
            {"type": "text", "text": user_input or "Допоможи розібратися з цим завданням."},
            {"type": "image_url", "image_url": {"url": _image_to_data_url(image)}},
        ]
    else:
        content = user_input
    messages.append({"role": "user", "content": content})

    errors = []
    for name, base_url, key, model in _providers():
        try:
            client = OpenAI(api_key=key, base_url=base_url, timeout=60, max_retries=0)
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.5,
                max_tokens=800,
            )
            text = response.choices[0].message.content
            if text:
                return text
            errors.append(f"{name}: порожня відповідь")
        except Exception as e:  # пробуємо наступного провайдера
            errors.append(f"{name}: {e}")

    return (
        "⚠️ Не вдалося отримати відповідь від жодного ШІ-сервісу.\n"
        "Перевір інтернет і спробуй ще раз.\n\n"
        "Подробиці:\n- " + "\n- ".join(errors)
    )


if __name__ == "__main__":
    print(main_ai_function("Поясни, що таке дріб, для 5 класу"))