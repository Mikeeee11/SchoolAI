
import base64
import io
import os
import re

from dotenv import load_dotenv
from openai import OpenAI
from PIL import Image, ImageOps

load_dotenv()  # читає OPENAI_API_KEY з файлу .env (якщо він є)

SYSTEM_PROMPT = """Ти — дружелюбний помічник для школярів.
Правила:
- Пояснюй простою мовою, крок за кроком, з короткими прикладами.
- Не просто видавай готову відповідь: покажи хід розв'язання, щоб учень зрозумів тему.
- Наприкінці став одне коротке запитання для перевірки розуміння.
- Якщо питання не про навчання або неприйнятне для дітей — чемно переведи розмову на навчання.
- Усі формули записуй у форматі LaTeX: короткі (в рядку) — між одинарними доларами, наприклад $\\frac{3}{4}$, $x^{2}$, $\\vec{a}$; великі або важливі — окремим рядком між подвійними доларами $$ ... $$.
- Для дробів використовуй \\frac{a}{b}, для степенів x^{n}, для коренів \\sqrt{x}, для векторів \\vec{a} і \\vec{AB}, координат — $\\vec{a}(x; y)$, довжини вектора — $|\\vec{a}|$, скалярного добутку — \\cdot, множення — \\cdot або \\times, ділення — \\div.
- Не пиши формули звичайним текстом (на кшталт 3/4, x^2, sqrt(x)) і не використовуй \\( \\) та \\[ \\]. Числа без дій можна писати як звичайний текст.
- Відповідай тією мовою, якою пише учень (українською, російською чи іншою). Якщо мова незрозуміла — відповідай українською."""

IMAGE_PROMPT_HINT = (
    "До повідомлення додано фото завдання. Уважно прочитай текст і формули "
    "на фото, спершу коротко перепиши умову, а потім поясни розв'язання."
)

# Фрази, за якими видно, що модель НЕ побачила картинку
_NO_VISION_MARKERS = (
    "не можу бачити", "не бачу зображ", "не бачу фото", "не можу переглян",
    "не можу побачити", "не вдається побачити", "не могу видеть",
    "не вижу изображ", "не вижу фото", "не могу просмотреть",
    "can't see the image", "cannot see the image", "can't view the image",
    "cannot view the image", "unable to view", "unable to see",
    "don't see any image", "do not see any image", "no image attached",
)


def _providers():
    """Список провайдерів за пріоритетом: (назва, base_url, ключ, модель, vision_модель)."""
    result = []
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        result.append(("OpenAI", None, api_key, "gpt-4o-mini", "gpt-4o-mini"))
    # Безкоштовний сервіс без ключа (будь-який рядок як "ключ" — просто заглушка)
    free_model = os.getenv("FREE_API_MODEL", "openai")
    result.append((
        "Pollinations",
        os.getenv("FREE_API_URL", "https://text.pollinations.ai/openai"),
        "no-key-needed",
        free_model,
        os.getenv("FREE_API_VISION_MODEL", free_model),
    ))
    # Локальна модель, якщо встановлена Ollama.
    # gemma3:4b вміє працювати з картинками; можна замінити на llava, qwen2.5vl тощо.
    result.append((
        "Ollama",
        os.getenv("OLLAMA_URL", "http://localhost:11434/v1"),
        "ollama",
        os.getenv("OLLAMA_MODEL", "gemma3:4b"),
        os.getenv("OLLAMA_VISION_MODEL", "gemma3:4b"),
    ))
    return result


def _image_to_data_url(image):
    """Готує картинку: виправляє поворот, прибирає прозорість, зменшує, кодує в base64."""
    if not isinstance(image, Image.Image):
        if hasattr(image, "seek"):
            image.seek(0)  # файл зі Streamlit міг уже бути прочитаний
        image = Image.open(image)
    image = ImageOps.exif_transpose(image)  # фото з телефона часто «лежать» набік

    if image.mode in ("RGBA", "LA", "P"):
        image = image.convert("RGBA")
        background = Image.new("RGB", image.size, (255, 255, 255))
        background.paste(image, mask=image.split()[-1])
        image = background
    else:
        image = image.convert("RGB")

    image.thumbnail((1024, 1024))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=85)
    b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/jpeg;base64,{b64}"


def _fix_math(text):
    """Приводить формули до виду, який Streamlit вміє малювати: $...$ та $$...$$.

    Моделі часто пишуть \\( ... \\) і \\[ ... \\] — Streamlit їх не розуміє,
    тому замінюємо на $ і $$.
    """
    text = re.sub(r"\\\[(.+?)\\\]", lambda m: f"\n$$\n{m.group(1).strip()}\n$$\n", text, flags=re.S)
    text = re.sub(r"\\\((.+?)\\\)", lambda m: f"${m.group(1).strip()}$", text, flags=re.S)
    return text


def _looks_blind(text):
    """True, якщо відповідь схожа на «я не бачу зображення»."""
    low = text.lower()
    return any(marker in low for marker in _NO_VISION_MARKERS)


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

    has_image = image is not None
    data_url = None
    if has_image:
        try:
            data_url = _image_to_data_url(image)
        except Exception as e:
            return f"⚠️ Не вдалося відкрити зображення: {e}\nСпробуй інший файл (JPG або PNG)."

    base_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if history:
        # у історію беремо лише текст, щоб не тягнути старі картинки
        for m in history[-10:]:
            if isinstance(m.get("content"), str):
                base_messages.append({"role": m["role"], "content": m["content"]})

    errors = []
    for name, base_url, key, model, vision_model in _providers():
        if has_image:
            if not vision_model:
                errors.append(f"{name}: немає моделі з підтримкою фото")
                continue
            use_model = vision_model
            question = user_input or "Допоможи розібратися з цим завданням."
            content = [
                {"type": "text", "text": f"{question}\n\n{IMAGE_PROMPT_HINT}"},
                {"type": "image_url", "image_url": {"url": data_url}},
            ]
        else:
            use_model = model
            content = user_input

        messages = base_messages + [{"role": "user", "content": content}]

        try:
            client = OpenAI(
                api_key=key,
                base_url=base_url,
                timeout=120 if has_image else 60,
                max_retries=0,
            )
            response = client.chat.completions.create(
                model=use_model,
                messages=messages,
                temperature=0.5,
                max_tokens=1000,
            )
            text = response.choices[0].message.content
            if not text:
                errors.append(f"{name}: порожня відповідь")
                continue
            if has_image and _looks_blind(text):
                errors.append(f"{name} ({use_model}): модель не побачила зображення")
                continue
            return _fix_math(text)
        except Exception as e:  # пробуємо наступного провайдера
            errors.append(f"{name}: {e}")

    if has_image:
        head = (
            "⚠️ Жоден ШІ-сервіс не зміг прочитати фото.\n"
            "Спробуй чіткіше фото або перепиши умову завдання текстом.\n"
            "Для роботи з фото локально встанови модель: `ollama pull gemma3:4b`.\n\n"
        )
    else:
        head = (
            "⚠️ Не вдалося отримати відповідь від жодного ШІ-сервісу.\n"
            "Перевір інтернет і спробуй ще раз.\n\n"
        )
    return head + "Подробиці:\n- " + "\n- ".join(errors)


if __name__ == "__main__":
    print(main_ai_function("Поясни, що таке дріб, для 5 класу"))