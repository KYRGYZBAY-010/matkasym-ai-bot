import os
import time
import requests

BITRIX_WEBHOOK = os.getenv("BITRIX_WEBHOOK")

# ===== STATE =====
user_states = {}
processed_ids = set()

def get_state(chat_id):
    return user_states.get(chat_id)

def set_state(chat_id, state):
    user_states[chat_id] = state


# ===== SEND =====
def send_message(chat_id, text):
    url = f"{BITRIX_WEBHOOK}im.message.add.json"
    payload = {
        "DIALOG_ID": chat_id,
        "MESSAGE": text
    }
    print("SEND:", payload)
    requests.post(url, json=payload)


# ===== LOGIC =====
def handle(chat_id, text):
    text_low = text.lower()
    state = get_state(chat_id)

    print("STATE:", state, "| TEXT:", text_low)

    # ===== ПРОДАЖА =====
    if any(x in text_low for x in ["цена", "канча", "сколько", "наличие", "барбы"]):
        return "Сатып алуу боюнча менеджер жардам берет:\n+996700244226"

    # ===== СУШИЛКА =====
    if "сушилка" in text_low or "сынып" in text_low:
        set_state(chat_id, "waiting_media")
        return "Сураныч, көйгөй болгон жердин сүрөтүн же видеосун жибериңиз."

    if state == "waiting_media":
        set_state(chat_id, "processing")
        return "Рахмат. Карап чыгып жооп беребиз."

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

    # ===== DEFAULT =====
    return "Саламатсызбы 😊 Кантип жардам бере алабыз?"


# ===== GET MESSAGES =====
def get_messages():
    url = f"{BITRIX_WEBHOOK}im.dialog.messages.get.json"
    params = {
        "DIALOG_ID": "chat0",
        "LIMIT": 20
    }
    r = requests.get(url, params=params)
    return r.json()


# ===== MAIN LOOP =====
def run():
    print("POLLING STARTED")

    while True:
        try:
            data = get_messages()

            if "result" not in data:
                time.sleep(5)
                continue

            messages = data["result"]["messages"]

            for msg in messages:
                msg_id = msg["id"]

                if msg_id in processed_ids:
                    continue

                processed_ids.add(msg_id)

                text = msg.get("text", "")
                chat_id = msg.get("chat_id")

                if not text:
                    continue

                print("NEW MSG:", text)

                reply = handle(chat_id, text)

                if reply:
                    send_message(chat_id, reply)

        except Exception as e:
            print("ERROR:", e)

        time.sleep(5)


# ===== START =====
if __name__ == "__main__":
    run()
