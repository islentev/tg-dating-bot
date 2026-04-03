import base64
import json
import mimetypes
import os

import httpx
from dotenv import load_dotenv


load_dotenv()

api_key = os.getenv("OPENROUTER_API_KEY")
model = os.getenv("OPENROUTER_MODEL", "openrouter/free")

print("API key loaded:", bool(api_key))
if api_key:
    print("API key starts with:", api_key[:10])
print("Model:", model)

if not api_key:
    raise RuntimeError("В файле .env не найден OPENROUTER_API_KEY")


def image_to_data_url(image_path: str) -> str:
    mime_type, _ = mimetypes.guess_type(image_path)
    if mime_type is None:
        mime_type = "image/jpeg"

    with open(image_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")

    return f"data:{mime_type};base64,{encoded}"


image_path_jpg = "screen.jpg"
image_path_png = "screen.png"

if os.path.exists(image_path_jpg):
    image_path = image_path_jpg
elif os.path.exists(image_path_png):
    image_path = image_path_png
else:
    raise FileNotFoundError(
        "Не найден файл screen.jpg или screen.png. Положи скрин в папку проекта."
    )

url = "https://openrouter.ai/api/v1/chat/completions"

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

payload = {
    "model": model,
    "messages": [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": (
                        "Посмотри на этот скрин анкеты или переписки. "
                        "Кратко опиши, что ты видишь. "
                        "Потом предложи одно спокойное первое сообщение на русском языке. "
                        "Если возраст на скрине не подтвержден явно, так и скажи."
                    )
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": image_to_data_url(image_path)
                    }
                }
            ]
        }
    ]
}

response = httpx.post(url, headers=headers, json=payload, timeout=120)

print("HTTP status:", response.status_code)
print("Raw response:")
print(response.text)

if response.status_code == 200:
    data = response.json()
    print("\n----- RESULT -----\n")
    print(data["choices"][0]["message"]["content"])