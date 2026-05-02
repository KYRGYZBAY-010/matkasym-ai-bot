from fastapi import FastAPI
from openai import OpenAI
import requests
import os
import time
import threading

app = FastAPI()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)

BITRIX_WEBHOOK = os.getenv("BITRIX_WEBHOOK")

USER_ID = 100023
CHECK_INTERVAL = 10

DEALS = [284697]

processed_messages = set()
initialized = False


@app.get("/")
def root():
    return {
        "status": "MATKASYM AI BOT ACTIVE"
    }


def bitrix_call(method: str, payload: dict | None = None):

    url = f"{BITRIX_WEBHOOK}{method}"

    response = requests.post(
        url,
        data=payload or {},
        timeout=20
    )

    try:
        return response.json()

    except Exception:
        return {
            "raw": response.text
        }


def get_deal_chats(deal_id: int):

    result = bitrix_call(
        "imopenlines.crm.chat.get",
        {
            "CRM_ENTITY_TYPE": "DEAL",
            "CRM_ENTITY": deal_id,
            "ACTIVE_ONLY": "Y"
        }
    )

    print("ACTIVE CHAT RESULT:", result)

    return result.get("result", [])


def get_latest_messages():

    all_messages = []

    for deal_id in DEALS:

        chats = get_deal_chats(deal_id)

        for ch in chats:

            openline_chat_id = ch.get("CHAT_ID")

            if not openline_chat_id:
                continue

            msg_result = bitrix_call(
                "im.dialog.messages.get",
                {
                    "DIALOG_ID": f"chat{openline_chat_id}",
                    "LIMIT": 20
                }
            )

            messages = (
                msg_result
                .get("result", {})
                .get("messages", [])
            )

            for msg in messages:
                msg["deal_id"] = deal_id
                msg["openline_chat_id"] = openline_chat_id

            all_messages.extend(messages)

    return all_messages


def generate_ai_reply(user_text: str):

    try:

        response = client.responses.create(
            model="gpt-5-mini",
            input=f"""
Ты менеджер компании MATKASYM.

Правила:
- отвечай коротко
- отвечай как живой менеджер
- язык ответа = кыргызский
- без длинных текстов
- без markdown
- без звёздочек
- если клиент спрашивает цену:
  сначала уточни товар
- если клиент пишет про поломку:
  попроси фото или видео
- если клиент пишет про сушилку:
  уточни какой тип нужен

Сообщение клиента:
{user_text}
"""
        )

        text = response.output_text.strip()

        print("OPENAI RESPONSE:", text)

        return text

    except Exception as e:

        print("OPENAI ERROR:", e)

        return None


def make_reply(text):

    if not text:
        return None

    text_low = str(text).lower()

    print("TEXT LOW:", text_low)

    if (
        "антен" in text_low
        or "канал" in text_low
        or "телевиз" in text_low
    ):

        return (
            "Саламатсызбы 😊\n\n"
            "Антенна боюнча жардам беребиз.\n\n"
            "Телевизордун менюсун сүрөткө тартып жибериңиз."
        )

    if (
        "сынды" in text_low
        or "сломался" in text_low
        or "сломано" in text_low
        or "брак" in text_low
    ):

        return (
            "Саламатсызбы.\n\n"
            "Сураныч, сүрөт же видео жибериңиз.\n"
            "Карап чыгып жардам беребиз."
        )

    if (
        "сушилка" in text_low
        or "сушил" in text_low
    ):

        return (
            "Саламатсызбы 😊\n\n"
            "Кайсы сушилка керек?\n\n"
            "1. Настенный\n"
            "2. Напольный\n"
            "3. Потолочный"
        )

    if (
        "цена" in text_low
        or "баа" in text_low
        or "baa" in text_low
        or "опт" in text_low
        or "каталог" in text_low
    ):

        return (
            "Кайсы товар кызыктырып жатат?"
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


def intercept_openline_chat(chat_id: int):

    result = bitrix_call(
        "imopenlines.session.intercept",
        {
            "CHAT_ID": chat_id
        }
    )

    print("INTERCEPT RESULT:", result)

    return result


def send_openline_message(
    chat_id: int,
    deal_id: int,
    message: str
):

    payload = {
        "CRM_ENTITY_TYPE": "DEAL",
        "CRM_ENTITY": deal_id,
        "USER_ID": USER_ID,
        "CHAT_ID": chat_id,
        "MESSAGE": message
    }

    result = bitrix_call(
        "imopenlines.crm.message.add",
        payload
    )

    print("SEND PAYLOAD:", payload)
    print("SEND RESULT:", result)

    return result


def polling_loop():

    global initialized

    print("POLLING STARTED")
    print("GPT VERSION ACTIVE")

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

                reply = generate_ai_reply(text)

                print("AI REPLY:", reply)

                if not reply:
                    reply = make_reply(text)

                print("FINAL REPLY:", reply)

                if reply and chat_id and deal_id:

                    intercept_openline_chat(chat_id)

                    send_openline_message(
                        chat_id,
                        deal_id,
                        reply
                    )

                    print(
                        "REPLIED TO CHAT:",
                        chat_id
                    )

        except Exception as e:

            print("POLL ERROR:", e)

        time.sleep(CHECK_INTERVAL)


@app.on_event("startup")
def start_polling():

    thread = threading.Thread(
        target=polling_loop,
        daemon=True
    )

    thread.start()
