import base64
import mimetypes
import os
import time
from pathlib import Path
import socket

import requests
import urllib3.util.connection as urllib3_cn
from dotenv import load_dotenv

urllib3_cn.allowed_gai_family = lambda: socket.AF_INET


load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

print("DEBUG OPENROUTER_API_KEY exists:", bool(OPENROUTER_API_KEY), flush=True)
print("DEBUG TELEGRAM_BOT_TOKEN exists:", bool(TELEGRAM_BOT_TOKEN), flush=True)
print("DEBUG OPENROUTER_MODEL:", OPENROUTER_MODEL, flush=True)

if not OPENROUTER_API_KEY:
    raise RuntimeError("OPENROUTER_API_KEY not found in environment")

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN not found in environment")

SESSION_HTTP = requests.Session()
SESSION_HTTP.trust_env = False

TG_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
TG_FILE_API = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}"

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

SESSION = {
    "photos": [],
    "text": "",
    "mode": "first"
}


def log(*args):
    print(*args, flush=True)


def image_to_data_url(image_path: str) -> str:
    mime_type, _ = mimetypes.guess_type(image_path)
    if mime_type is None:
        mime_type = "image/jpeg"

    with open(image_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")

    return f"data:{mime_type};base64,{encoded}"


def tg_send_message(chat_id: int, text: str) -> None:
    log("Отправляю сообщение в Telegram:", text[:120])

    response = SESSION_HTTP.post(
        f"{TG_API}/sendMessage",
        json={"chat_id": chat_id, "text": text},
        timeout=60,
    )
    response.raise_for_status()
    log("sendMessage ok")


def tg_get_updates(offset: int | None) -> dict:
    params = {"timeout": 10}
    if offset is not None:
        params["offset"] = offset

    log("Запрашиваю updates, offset =", offset)

    response = SESSION_HTTP.get(
        f"{TG_API}/getUpdates",
        params=params,
        timeout=40,
    )
    response.raise_for_status()

    data = response.json()
    log("Ответ Telegram getUpdates:", data)
    return data


def tg_get_file(file_id: str) -> dict:
    response = SESSION_HTTP.get(
        f"{TG_API}/getFile",
        params={"file_id": file_id},
        timeout=60,
        proxies={"http": None, "https": None},
    )
    response.raise_for_status()
    return response.json()


def tg_download_file(file_path: str, save_path: str) -> None:
    response = SESSION_HTTP.get(
        f"{TG_FILE_API}/{file_path}",
        timeout=120,
        proxies={"http": None, "https": None},
    )
    response.raise_for_status()

    with open(save_path, "wb") as f:
        f.write(response.content)


def choose_best_photo(message: dict) -> str | None:
    photos = message.get("photo", [])
    if not photos:
        return None
    return photos[-1]["file_id"]


def call_openrouter(user_text: str, image_paths: list[str], mode: str) -> str:
    log("Отправляю запрос в OpenRouter")

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    content = [
        {
            "type": "text",
            "text": (
            		"Ты помощник по переписке в дейтинге. "
    			"Ты помогаешь взрослому мужчине писать женщинам естественно, живо и уверенно. "
   			"Стиль пользователя: спокойный, мягкий, уверенный, без пафоса, без кринжа, без манипуляций. "
    			"Юмор допустим на уровне 4 из 10: легкий, уместный, не клоунский, не вымученный. "
    			"Твоя задача — не писать как нейросеть, а предлагать сообщение, которое реально можно отправить без стыда.\n\n"

    			"Правила стиля:\n"
    			"- не пиши сухо, канцелярски или шаблонно;\n"
    			"- не пиши как ассистент, коуч или психолог;\n"
    			"- не используй фразы вроде: 'интересно узнать', 'чувствуется вайб', 'ты кажешься', 'энергия', 'небанально', 'впечатление', если можно сказать проще;\n"
    			"- не пиши 'привет, как дела' и похожие пустые заходы;\n"
    			"- не делай сообщение слишком умным, слишком длинным или слишком идеальным;\n"
    			"- не используй пошлость, давление, манипуляции, пикап-клише;\n"
    			"- не делай 2-3 вопроса сразу;\n"
    			"- лучше одно живое сообщение, чем умная простыня;\n"
    			"- если можно сказать проще и человечнее — говори проще и человечнее.\n\n"
			"- избегай фраз, которые звучат как текст из нейросети;\n"
			"- не делай сообщение слишком вылизанным;\n"
			"- допускается легкая шероховатость живой речи;\n"
			"- лучше чуть проще, чем слишком литературно;\n"
			"- не объясняй очевидное и не звучь как эксперт;\n"

    			"Тон:\n"
    			"- живой;\n"
    			"- естественный;\n"
    			"- взрослый;\n"
    			"- с легкой иронией, если уместно;\n"
    			"- без лишней серьезности;\n"
    			"- без липкости.\n\n"

    			"Задачи по режимам:\n"
    			"- first: придумай одно первое сообщение по фото/био;\n"
    			"- reply: придумай один лучший ответ на ее последнее сообщение;\n"
    			"- followup: придумай одно короткое и достойное сообщение после паузы;\n"
    			"- invite: придумай одно легкое приглашение на встречу без пафоса.\n\n"

    			"Если возраст девушки не подтвержден явно как 18+, не предлагай романтический заход и кратко скажи об этом.\n\n"

    			"Формат ответа:\n"
    			"1. Сначала строка: Режим: ...\n"
    			"2. Потом строка: Лучший вариант:\n"
    			"3. Потом только один готовый текст сообщения.\n"
    			"4. Потом строка: Почему это работает:\n"
    			"5. Потом 1-2 коротких предложения простым языком.\n\n"
			
			f"Текущий режим: {mode}\n\n"
    			"Контекст пользователя:\n"
    			f"{user_text}"
		  )
    	
        }
    ]

    for image_path in image_paths:
        content.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": image_to_data_url(image_path)
                },
            }
        )

    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {
                "role": "user",
                "content": content,
            }
        ],
    }

    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=180,
        proxies={"http": None, "https": None},
    )
    response.raise_for_status()

    data = response.json()
    result = data["choices"][0]["message"]["content"]
    log("Ответ OpenRouter получен")
    return result


def handle_text(chat_id: int, text: str) -> None:
    log("Текст от пользователя:", text)
    text = text.strip()

    if text == "/start":
        tg_send_message(
            chat_id,
            "Бот запущен.\n\n"
            "Как пользоваться:\n"
            "1. Отправь /new\n"
            "2. Пришли фото анкеты, скрины переписки или текст\n"
            "3. Выбери режим:\n"
            "/first — первое сообщение\n"
            "/reply — ответ на переписку\n"
            "/followup — сообщение после паузы\n"
            "/invite — приглашение на встречу\n\n"
            "Дополнительно:\n"
            "/clear — очистить сессию"
        )
        return

    if text == "/new":
        SESSION["photos"] = []
        SESSION["text"] = ""
        SESSION["mode"] = "first"
        tg_send_message(
            chat_id,
            "Новая сессия создана. Пришли фото и/или текст, потом выбери режим: /first /reply /followup /invite"
        )
        return

    if text == "/clear":
        SESSION["photos"] = []
        SESSION["text"] = ""
        SESSION["mode"] = "first"
        tg_send_message(chat_id, "Сессия очищена.")
        return

    if text in ["/first", "/reply", "/followup", "/invite"]:
        mode_map = {
            "/first": "first",
            "/reply": "reply",
            "/followup": "followup",
            "/invite": "invite",
        }

        SESSION["mode"] = mode_map[text]

        if not SESSION["photos"] and not SESSION["text"]:
            tg_send_message(chat_id, "Сначала пришли фото анкеты, переписку или текст.")
            return

        try:
            result = call_openrouter(
                user_text=SESSION["text"],
                image_paths=SESSION["photos"],
                mode=SESSION["mode"]
            )
            tg_send_message(chat_id, result)
        except Exception as e:
            tg_send_message(chat_id, f"Ошибка при запросе к модели:\n{e}")
        return

    SESSION["text"] += ("\n" + text if SESSION["text"] else text)
    tg_send_message(
        chat_id,
        "Текст сохранен. Можешь прислать еще фото или выбрать режим: /first /reply /followup /invite"
    )


def handle_photo(chat_id: int, message: dict) -> None:
    log("Получено фото")
    file_id = choose_best_photo(message)
    if not file_id:
        tg_send_message(chat_id, "Фото сохранено. Можешь прислать еще фото, текст или выбрать режим: /first /reply /followup /invite")
        return

    file_info = tg_get_file(file_id)
    file_path = file_info["result"]["file_path"]

    ext = os.path.splitext(file_path)[1] or ".jpg"
    save_path = DATA_DIR / f"{int(time.time())}_{file_id}{ext}"

    tg_download_file(file_path, str(save_path))
    SESSION["photos"].append(str(save_path))

    tg_send_message(
        chat_id,
        "Фото сохранено. Можешь прислать еще фото, текст или выбрать режим: /first /reply /followup /invite"
    )


def process_update(update: dict) -> None:
    log("Получен update:", update)

    message = update.get("message")
    if not message:
        return

    chat_id = message["chat"]["id"]

    if "text" in message:
        handle_text(chat_id, message["text"])
        return

    if "photo" in message:
        handle_photo(chat_id, message)
        return


def main() -> None:
    log("Бот запущен...")
    offset = None

    while True:
        try:
            updates = tg_get_updates(offset)
            results = updates.get("result", [])

            for item in results:
                offset = item["update_id"] + 1
                process_update(item)

            time.sleep(1)

        except Exception as e:
            log("Ошибка polling:", e)
            time.sleep(3)

if __name__ == "__main__":
    main()
