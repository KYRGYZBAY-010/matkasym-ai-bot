from fastapi import FastAPI
import requests
import os
import time
import threading

app = FastAPI()

BITRIX_WEBHOOK = os.getenv("BITRIX_WEBHOOK")
USER_ID = 100023
CHECK_INTERVAL = 30
DEALS = [284457]

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
                "LIMIT": 50
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

    text = str(text)
    text_low = text.lower()

    print("TEXT LOW:", text_low)

    if "антен" in text_low or "канал" in text_low or "телевиз" in text_low:
        return (
            "Саламатсызбы 😊\n\n"
            "Антенна боюнча жардам беребиз."
        )

    if "сушил" in text_low or "сын" in text_low or "слом" in text_low:
        return (
            "Саламатсызбы.\n\n"
            "Сураныч, сынган жерин сүрөтүн жибериңиз."
        )

    if "цена" in text_low or "баа" in text_low or "опт" in text_low or "каталог" in text_low:
        return (
            "Саламатсызбы 😊\n\n"
            "Кайсы товар кызыктырып жатат?"
        )

    return None

def send_openline_message(chat_id: int, deal_id: int, message: str):
    result = bitrix_call("imopenlines.crm.message.add", {
        "CRM_ENTITY_TYPE": "DEAL",
        "CRM_ENTITY": deal_id,
        "USER_ID": USER_ID,
        "CHAT_ID": chat_id,
        "MESSAGE": message
    })

    print("SEND RESULT:", result)
    return result


def polling_loop():
    print("Polling started")
    print("NEW CLEAN VERSION LOADED")

    while True:
        try:
            messages = get_latest_messages()
            print("MESSAGES COUNT:", len(messages))

            for msg in messages:
                msg_id = msg.get("id")
                author_id = msg.get("author_id")
                text = msg.get("text", "")
                chat_id = msg.get("openline_chat_id")
                deal_id = msg.get("deal_id")

                if not msg_id:
                    continue

                print("MSG CHECK:", {
                    "id": msg_id,
                    "author_id": author_id,
                    "chat_id": chat_id,
                    "deal_id": deal_id,
                    "text": text
                })

                if msg_id in processed_messages:
                    continue

                processed_messages.add(msg_id)

                if author_id == 0:
                    continue

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
