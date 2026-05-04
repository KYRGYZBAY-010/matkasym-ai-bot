import os
import requests
from fastapi import FastAPI, Request

app = FastAPI()

BITRIX_WEBHOOK = os.getenv("BITRIX_WEBHOOK")

# ===== STATE STORAGE =====
user_states = {}
processed_messages = set()

def get_state(chat_id):
    return user_states.get(chat_id)

def set_state(chat_id, state):
    user_states[chat_id] = state


# ===== ОТПРАВКА СООБЩЕНИЯ =====
def send_message(chat_id, user_id, text):
    url = f"{BITRIX_WEBHOOK}im.message.add.json"
    payload = {
        "DIALOG_ID": chat_id,
        "MESSAGE": text
    }

    print("SEND:", payload)
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print("SEND ERROR:", e)


# ===== ОСНОВНАЯ ЛОГИКА =====
def handle_message(chat_id, user_id, author_id, message_id, text):

    # --- защита от дублей ---
    if message_id in processed_messages:
        print("SKIPPED MESSAGE:", message_id)
        return None
    processed_messages.add(message_id)

    # --- не отвечаем сами себе ---
    if str(author_id) == str(user_id):
        return None

    text_low = text.lower()
    state = get_state(chat_id)

    print("STATE:", state, "| TEXT:", text_low)

    # ===== ПРОДАЖА =====
    if any(x in text_low for x in ["цена", "сколько", "наличие", "барбы", "канча"]):
        return "Сатып алуу боюнча менеджер жардам берет:\n+996700244226"

    # ===== СУШИЛКА =====
    if "сушилка" in text_low or "сынып" in text_low:
        set_state(chat_id, "waiting_media")
        return "Сураныч, көйгөй болгон жердин сүрөтүн же видеосун жибериңиз."

    if state == "waiting_media":
        set_state(chat_id, "processing")
        return "Рахмат. Карап чыгып, оңдоо же алмаштыруу боюнча жооп беребиз."

    if state == "processing":
        return "Менеджер жакын арада сиз менен байланышат."

    # ===== АНТЕННА =====
    if "антенна" in text_low:
        set_state(chat_id, "antenna")
        return "Канал чыкпай жатабы же сигнал жокпу?"

    if state == "antenna":
        if any(x in text_low for x in ["поиск", "табылбай", "чыкпай"]):
            return "DTV режимине өтүп, автопоиск кылыңыз."
        return "SOURCE басып, TV/DTV режимин тандаңыз."

    # ===== ДЕФОЛТ =====
    return "Саламатсызбы 😊 Кантип жардам бере алабыз?"


# ===== WEBHOOK =====
@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()

    print("INCOMING:", data)

    try:
        message = data.get("data", {})

        chat_id = message.get("chat_id")
        author_id = message.get("author_id")
        message_id = message.get("id")
        text = message.get("text")

        user_id = data.get("auth", {}).get("user_id")

        if not text:
            return {"status": "no_text"}

        reply = handle_message(chat_id, user_id, author_id, message_id, text)

        if reply:
            send_message(chat_id, user_id, reply)

    except Exception as e:
        print("ERROR:", e)

    return {"status": "ok"}


# ===== HEALTH =====
@app.get("/")
def root():
    return {"status": "MATKASYM STABLE SUPPORT VERSION ACTIVE"}
