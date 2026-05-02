from fastapi import FastAPI
import requests
import os
import time
import threading

app = FastAPI()

BITRIX_WEBHOOK = os.getenv("BITRIX_WEBHOOK")
USER_ID = 100023
CHECK_INTERVAL = 10

DEALS = [284697]

processed_messages = set()
initialized = False


@app.get("/")
def root():
    return {"status": "MATKASYM AI BOT SAFE ACTIVE"}


def bitrix_call(method: str, payload: dict | None = None):
    url = f"{BITRIX_WEBHOOK}{method}"
    response = requests.post(url, data=payload or {}, timeout=20)

    try:
        return response.json()
    except Exception:
        return {"raw": response.text}


def get_latest_messages():
    all_messages = []

    for deal_id in DEALS:
        chat_result = bitrix_call("imopenlines.crm.chat.get", {
            "CRM_ENTITY_TYPE": "DEAL",
            "CRM_ENTITY": deal_id,
            "ACTIVE_ONLY": "N"
        })

        print("CHAT RESULT:", chat_result)

        chats = chat_result.get("result", [])

        for ch in chats:
            openline_chat_id = ch.get("CHAT_ID")

            if not openline_chat_id:
                continue

            msg_result = bitrix_call("im.dialog.messages.get", {
                "DIALOG_ID": f"chat{openline_chat_id}",
                "LIMIT": 20
            })

            messages = msg_result.get("result", {}).get("messages", [])

            for msg in messages:
                msg["deal_id"] = deal_id
                msg["openline_chat_id"] = openline_chat_id

            all_messages.extend(messages)

    return all_messages


def make_reply(text):
    if not text:
        return None

    text_low = str(text).lower()
    print("TEXT LOW:", text_low)

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

    if (
            "сынды" in text_low
            or "сломался" in text_low
            or "сломано" in text_low
            or "брак" in text_low
        ):
            return (
                "Саламатсызбы.\n\n"
                "Сураныч, сынган жердин сүрөтүн же кыска видео жибериңиз. "
                "Карап чыгып, алмаштыруу же оңдоо боюнча жооп беребиз."
            )

    if "сушилка" in text_low or "сушил" in text_low:
        return (
            "Саламатсызбы 😊\n\n"
            "Сушилка бар.\n"
            "Кайсы размер кызыктырып жатат?\n\n"
            "1. Настенный\n"
            "2. Напольный\n"
            "3. Потолочный\n\n"
            "Розница керекпи же оптомбу?"
        )

    if "цена" in text_low or "баа" in text_low or "baa" in text_low or "опт" in text_low or "каталог" in text_low:
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


def should_skip_message(msg):
    msg_id = msg.get("id")
    author_id = msg.get("author_id")
    text = str(msg.get("text", "")).lower()

    if not msg_id:
        return True

    if msg_id in processed_messages:
        return True

    if author_id == 0:
        return True

    if str(author_id) == str(USER_ID):
        return True

    blocked_phrases = [
        "отправлено автоматически",
        "system wz",
        "сообщение не отправлено",
        "подозрения на спам",
        "создана новая сделка",
        "обращение направлено",
        "начат новый диалог",
    ]

    for phrase in blocked_phrases:
        if phrase in text:
            return True

    return False


def send_openline_message(chat_id: int, deal_id: int, message: str):
    payload = {
        "CRM_ENTITY_TYPE": "DEAL",
        "CRM_ENTITY": deal_id,
        "USER_ID": USER_ID,
        "CHAT_ID": chat_id,
        "MESSAGE": message
    }

    result = bitrix_call("imopenlines.crm.message.add", payload)
    print("SEND PAYLOAD:", payload)
    print("SEND RESULT:", result)
    return result


def polling_loop():
    global initialized

    print("Polling started")
    print("SAFE FINAL VERSION LOADED")

    while True:
        try:
            messages = get_latest_messages()
            print("MESSAGES COUNT:", len(messages))

            if not initialized:
                for msg in messages:
                    msg_id = msg.get("id")
                    if msg_id:
                        processed_messages.add(msg_id)

                initialized = True
                print("INITIAL HISTORY SKIPPED")
                time.sleep(CHECK_INTERVAL)
                continue

            for msg in messages:
                msg_id = msg.get("id")
                author_id = msg.get("author_id")
                text = msg.get("text", "")
                chat_id = msg.get("openline_chat_id")
                deal_id = msg.get("deal_id")

                print("MSG CHECK:", {
                    "id": msg_id,
                    "author_id": author_id,
                    "chat_id": chat_id,
                    "deal_id": deal_id,
                    "text": text
                })

                if should_skip_message(msg):
                    continue

                processed_messages.add(msg_id)

                reply = make_reply(text)
                print("REPLY GENERATED:", reply)

                if reply and chat_id and deal_id:
                    send_openline_message(chat_id, deal_id, reply)
                    print("Replied to OpenLine chat:", chat_id)

        except Exception as e:
            print("POLL ERROR:", e)

        time.sleep(CHECK_INTERVAL)


@app.on_event("startup")
def start_polling():
    thread = threading.Thread(target=polling_loop, daemon=True)
    thread.start()
