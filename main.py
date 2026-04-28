from fastapi import FastAPI
import requests
import os
import time
import threading

app = FastAPI()

BITRIX_WEBHOOK = os.getenv("BITRIX_WEBHOOK")
USER_ID = 100023
CHECK_INTERVAL = 10

processed_messages = set()


@app.get("/")
def root():
    return {"status": "MATKASYM AI BOT WORKING"}


def bitrix_call(method: str, payload: dict | None = None):
    url = f"{BITRIX_WEBHOOK}{method}"
    response = requests.post(url, data=payload or {}, timeout=20)
    try:
        return response.json()
    except Exception:
        return {"raw": response.text}


def get_latest_messages():
    result = bitrix_call("im.dialog.messages.get", {
        "DIALOG_ID": "chat1",
        "LIMIT": 10
    })
    return result


def make_reply(text: str):
    text_low = text.lower()

    if "антен" in text_low or "канал" in text_low or "телевиз" in text_low:
        return (
            "Саламатсызбы 😊\n\n"
            "Антенна боюнча жардам беребиз.\n\n"
            "1. Антеннанын штекерин телевизорго туура сайыңыз.\n"
            "2. Настройкага кириңиз.\n"
            "3. Каналы / Поиск каналов бөлүмүн тандаңыз.\n"
            "4. DTV же Цифровое ТВ тандаңыз.\n"
            "5. Автопоиск каналов басыңыз.\n\n"
            "Эгер чыкпай жатса, телевизордун менюсун сүрөткө тартып жибериңиз."
        )

    if "сушил" in text_low or "сын" in text_low or "слом" in text_low:
        return (
            "Саламатсызбы.\n\n"
            "Сураныч, сынган жердин сүрөтүн же кыска видео жибериңиз. "
            "Карап чыгып, алмаштыруу же оңдоо боюнча жооп беребиз."
        )

    if "цена" in text_low or "баа" in text_low or "опт" in text_low or "каталог" in text_low:
        return (
            "Саламатсызбы 😊\n\n"
            "Кайсы товар кызыктырып жатат?\n"
            "1. Сушилка\n"
            "2. Вешалка\n"
            "3. Полка\n"
            "4. Урна\n"
            "5. Щит\n\n"
            "Розница керекпи же оптовая цена керекпи?"
        )

    return None


def polling_loop():
    print("Polling started")

    while True:
        try:
            data = get_latest_messages()
            print("POLL RESULT:", data)

            messages = data.get("result", {}).get("messages", [])

            for msg in messages:
                msg_id = msg.get("id")
                author_id = msg.get("author_id")
                text = msg.get("text", "")
                chat_id = msg.get("chat_id")

                if not msg_id or msg_id in processed_messages:
                    continue

                processed_messages.add(msg_id)

                if str(author_id) == str(USER_ID):
                    continue

                reply = make_reply(text)

                if reply and chat_id:
                    bitrix_call("im.message.add", {
                        "DIALOG_ID": f"chat{chat_id}",
                        "MESSAGE": reply
                    })

                    print("Replied to chat:", chat_id)

        except Exception as e:
            print("POLL ERROR:", e)

        time.sleep(CHECK_INTERVAL)


@app.on_event("startup")
def start_polling():
    thread = threading.Thread(target=polling_loop, daemon=True)
    thread.start()
