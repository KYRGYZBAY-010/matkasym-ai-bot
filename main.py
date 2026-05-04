from fastapi import FastAPI
from openai import OpenAI
import requests
import os
import time
import threading

app = FastAPI()

client = OpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1"
)

BITRIX_WEBHOOK = os.getenv("BITRIX_WEBHOOK")
USER_ID = 100023
CHECK_INTERVAL = 10

DEALS = [284697]

SALES_PHONE = "+996700244226"

processed_messages = set()
initialized = False


SYSTEM_PROMPT = f"""
Сен MATKASYM / Зоркий глаз компаниясынын кардарларды колдоо операторусуң.

Маанилүү:
- Бул сатуу боту эмес, кардарларды колдоо боту.
- Сатып алуу, баа, заказ, барбы, наличиеси, оптом, каталог боюнча суроо болсо:
  кардарды сатуу менеджерине жөнөт: {SALES_PHONE}
- Өзүң баа айтпа.
- Өзүң заказ кабыл алба.
- Так эмес маалыматты ойлоп таппа.
- Эгер билбесең: "Так маалымат үчүн менеджерге жазыңыз" деп айт.
- Жооп кыргызча болсун.
- Жооп кыска, так, сылык болсун.
- 1 гана тактоочу суроо бер.
- Узун текст жазба.

Зоркий глаз товарлары:
- Антенналар: Smart10, Smart15, Smart20, Sanarip10, Sanarip15, Sanarip20, Compact, Tereze
- Кабель бар
- Усилитель бар
- Приставка жок
- Антенна кронштейни жок
- Ошондой эле: сушилка, гладильная доска, стеллаж, полка

Колдоо эрежелери:
- Антенна иштебесе: канал чыкпай жатабы же сигнал жокпу такта.
- DTV керек, ATV эмес.
- Канал чыкпаса: DTV режиминде автопоиск кылдыруу керек.
- Сигнал жок болсо: антеннаны терезеге жакын коюп, багытын өзгөртүүнү айт.
- Приставка болсо: TV/DTV режимине өтүүнү айт.
- Фото/видео келсе: карап чыгып жооп беребиз деп айт.
- Дефект, сынуу, брак болсо: сүрөт же кыска видео сура.
"""


@app.get("/")
def root():
    return {"status": "MATKASYM AI SUPPORT BOT ACTIVE"}


def bitrix_call(method: str, payload: dict | None = None):
    url = f"{BITRIX_WEBHOOK}{method}"
    response = requests.post(url, data=payload or {}, timeout=20)

    try:
        return response.json()
    except Exception:
        return {"raw": response.text}


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

            messages = msg_result.get("result", {}).get("messages", [])

            for msg in messages:
                msg["deal_id"] = deal_id
                msg["openline_chat_id"] = openline_chat_id

            all_messages.extend(messages)

    return all_messages


def generate_ai_reply(user_text: str):
    try:
        response = client.chat.completions.create(
            model="openrouter/free",
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": user_text
                }
            ],
            temperature=0.3,
            max_tokens=160
        )

        text = response.choices[0].message.content.strip()
        print("OPENROUTER RESPONSE:", text)
        return text

    except Exception as e:
        print("OPENROUTER ERROR:", e)
        return None


def make_reply(text):
    if not text:
        return None

    text_low = str(text).lower()
    print("TEXT LOW:", text_low)

    buy_words = [
        "цена", "баа", "канча", "сколько стоит",
        "заказ", "заказать", "сатып", "алам",
        "барбы", "есть", "налич", "опт", "каталог"
    ]

    if any(word in text_low for word in buy_words):
        return (
            "Саламатсызбы. Сатып алуу, баа же наличиеси боюнча "
            f"менеджер жардам берет: {SALES_PHONE}"
        )

    if "приставка" in text_low or "ресивер" in text_low:
        return (
            "Саламатсызбы. Бизде приставка жок. "
            f"Так маалымат үчүн менеджерге жазыңыз: {SALES_PHONE}"
        )

    if "кронштейн" in text_low and "антен" in text_low:
        return (
            "Саламатсызбы. Антенна үчүн кронштейн азыр жок. "
            f"Так маалымат үчүн менеджерге жазыңыз: {SALES_PHONE}"
        )

    if (
        "антен" in text_low
        or "канал" in text_low
        or "телевиз" in text_low
        or "dtv" in text_low
        or "atv" in text_low
        or "сигнал" in text_low
    ):
        return (
            "Саламатсызбы. Антенна боюнча жардам беребиз.\n"
            "Канал чыкпай жатабы же сигнал жокпу?\n"
            "Телевизордун менюсун сүрөткө тартып жибериңиз."
        )

    if (
        "сынды" in text_low
        or "сломался" in text_low
        or "сломано" in text_low
        or "брак" in text_low
        or "дефект" in text_low
        or "кыйшай" in text_low
        or "мыйрый" in text_low
        or "винт" in text_low
    ):
        return (
            "Саламатсызбы. Сураныч, көйгөй болгон жердин сүрөтүн "
            "же кыска видео жибериңиз. Карап чыгып жардам беребиз."
        )

    if (
        "кайтарып" in text_low
        or "вернуть" in text_low
        or "возврат" in text_low
    ):
        return (
            "Саламатсызбы. Макул, текшерип көрөбүз. "
            "Сураныч, товарды жана көйгөйүн сүрөт/видео менен жибериңиз."
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


def send_openline_message(chat_id: int, deal_id: int, message: str):
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
    print("MATKASYM SUPPORT AI VERSION ACTIVE")

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

                # Сначала жёсткие правила поддержки/покупки
                rule_reply = make_reply(text)

                if rule_reply:
                    reply = rule_reply
                    print("RULE REPLY:", reply)
                else:
                    # Потом AI, если правило не сработало
                    reply = generate_ai_reply(text)
                    print("AI REPLY:", reply)

                print("FINAL REPLY:", reply)

                if reply and chat_id and deal_id:
                    intercept_openline_chat(chat_id)
                    send_openline_message(chat_id, deal_id, reply)
                    print("REPLIED TO CHAT:", chat_id)

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
