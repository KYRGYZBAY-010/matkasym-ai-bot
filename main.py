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
SALES_PHONE = "+996700244226"

processed_messages = set()
dialog_states = {}
initialized = False


@app.get("/")
def root():
    return {"status": "MATKASYM STABLE SUPPORT BOT ACTIVE"}


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
            chat_id = ch.get("CHAT_ID")
            if not chat_id:
                continue

            msg_result = bitrix_call(
                "im.dialog.messages.get",
                {
                    "DIALOG_ID": f"chat{chat_id}",
                    "LIMIT": 20
                }
            )

            messages = msg_result.get("result", {}).get("messages", [])

            for msg in messages:
                msg["deal_id"] = deal_id
                msg["openline_chat_id"] = chat_id

            all_messages.extend(messages)

    return all_messages


def set_state(chat_id, state):
    dialog_states[str(chat_id)] = state
    print("STATE SET:", chat_id, state)


def get_state(chat_id):
    return dialog_states.get(str(chat_id))


def clear_state(chat_id):
    if str(chat_id) in dialog_states:
        del dialog_states[str(chat_id)]
        print("STATE CLEARED:", chat_id)


def make_reply(text, chat_id):
    if not text:
        return None

    text_low = str(text).lower().strip()
    state = get_state(chat_id)

    print("TEXT LOW:", text_low)
    print("CURRENT STATE:", state)

    photo_words = [
        "мынаке", "сүрөт", "сурот", "фото", "видео",
        "жибердим", "отправил", "отправила", "вот", "посмотри"
    ]

    defect_words = [
        "сынды", "сынып", "сломался", "сломано", "сломал",
        "брак", "дефект", "кыйшай", "мыйрый", "винт",
        "полкасы", "сварка", "буту", "бут", "ножка"
    ]

    antenna_words = [
        "антен", "канал", "телевиз", "dtv", "atv", "сигнал",
        "иштеб", "чыкпай", "поиск", "табылбай", "настрой", "пульт"
    ]

    dryer_words = [
        "сушилка", "сушил", "кийим кургат"
    ]

    buy_words = [
        "цена", "баа", "канча", "сколько стоит",
        "заказ", "заказать", "сатып", "алам",
        "есть", "налич", "опт", "каталог", "алсам"
    ]

    continue_words = [
        "карап", "койосунарбы", "көрүп", "эмне кылабыз",
        "жооп", "бересизби", "текшерип", "макул", "рахмат"
    ]

    # 1. Если уже идёт дефект-сценарий — держим его жёстко
    if state == "defect_support":
        print("DEFECT STATE ACTIVE")

        if any(word in text_low for word in photo_words):
            return (
                "Рахмат. Сүрөт/видеону кабыл алдык. "
                "Карап чыгып, оңдоо же алмаштыруу боюнча жооп беребиз."
            )

        return (
            "Сураныч, көйгөй болгон жердин сүрөтүн же кыска видео жибериңиз. "
            "Ошондон кийин карап чыгып жооп беребиз."
        )

    # 2. Если уже идёт антенна-сценарий
    if state == "antenna_support":
        print("ANTENNA STATE ACTIVE")

        if any(word in text_low for word in photo_words):
            return (
                "Рахмат. Антенна боюнча карап көрөлү.\n"
                "SOURCE басып, TV/DTV режимин тандаңыз. "
                "Андан кийин DTV режиминде автопоиск кылыңыз."
            )

        if "atv" in text_low:
            return (
                "ATV эмес, DTV тандоо керек. "
                "SOURCE басып TV/DTV режимин тандаңыз."
            )

        if "сигнал" in text_low or "жок" in text_low:
            return (
                "Антеннаны терезеге жакын коюп, багытын акырын өзгөртүп көрүңүз. "
                "Андан кийин DTV автопоиск кылыңыз."
            )

        if "поиск" in text_low or "чыкпай" in text_low or "табылбай" in text_low:
            return (
                "DTV режимин тандап, автопоиск кылыңыз. "
                "Эгер канал чыкпаса, антеннаны терезеге жакын коюп, багытын өзгөртүп көрүңүз."
            )

        return (
            "Антенна боюнча түшүнүктүү болуш үчүн телевизордун менюсун "
            "же экрандагы билдирүүнү сүрөткө тартып жибериңиз."
        )

    # 3. Если уже идёт сушилка-сценарий
    if state == "dryer_support":
        print("DRYER STATE ACTIVE")

        if "потолоч" in text_low:
            clear_state(chat_id)
            return (
                "Потолочный сушилка боюнча сатып алуу жана наличиеси үчүн "
                f"менеджерге жазыңыз: {SALES_PHONE}"
            )

        if "настенн" in text_low:
            clear_state(chat_id)
            return (
                "Настенный сушилка боюнча сатып алуу жана наличиеси үчүн "
                f"менеджерге жазыңыз: {SALES_PHONE}"
            )

        if "наполь" in text_low:
            clear_state(chat_id)
            return (
                "Напольный сушилка боюнча сатып алуу жана наличиеси үчүн "
                f"менеджерге жазыңыз: {SALES_PHONE}"
            )

        return (
            "Кайсы түрү керек экенин тандаңыз:\n"
            "1. Настенный\n"
            "2. Напольный\n"
            "3. Потолочный"
        )

    # 4. Дефект — самый высокий приоритет
    if any(word in text_low for word in defect_words):
        set_state(chat_id, "defect_support")
        return (
            "Саламатсызбы. Сураныч, көйгөй болгон жердин сүрөтүн "
            "же кыска видео жибериңиз. Карап чыгып жардам беребиз."
        )

    # 5. Фото без состояния
    if any(word in text_low for word in photo_words):
        return (
            "Рахмат. Маалыматты кабыл алдык. "
            "Карап чыгып жооп беребиз."
        )

    # 6. Сушилка
    if any(word in text_low for word in dryer_words):
        set_state(chat_id, "dryer_support")
        return (
            "Саламатсызбы. Кайсы сушилка керек?\n"
            "1. Настенный\n"
            "2. Напольный\n"
            "3. Потолочный"
        )

    # 7. Антенна
    if any(word in text_low for word in antenna_words):
        set_state(chat_id, "antenna_support")
        return (
            "Саламатсызбы. Антенна боюнча жардам беребиз.\n"
            "Канал чыкпай жатабы же сигнал жокпу?\n"
            "Телевизордун менюсун сүрөткө тартып жибериңиз."
        )

    # 8. Продажа
    if any(word in text_low for word in buy_words):
        set_state(chat_id, "sales_transfer")
        return (
            "Саламатсызбы. Сатып алуу, баа же наличиеси боюнча "
            f"менеджер жардам берет: {SALES_PHONE}"
        )

    # 9. Нет в продаже
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

    # 10. Возврат
    if "кайтарып" in text_low or "вернуть" in text_low or "возврат" in text_low:
        set_state(chat_id, "return_support")
        return (
            "Саламатсызбы. Макул, текшерип көрөбүз. "
            "Сураныч, товарды жана көйгөйүн сүрөт/видео менен жибериңиз."
        )

    # 11. Ничего не поняли
    return (
        "Саламатсызбы. Сурооңузду тактап жазыңыз. "
        "Эгер көйгөй болсо, сүрөт же кыска видео жибериңиз."
    )


def should_skip_message(msg):
    msg_id = msg.get("id")
    author_id = msg.get("author_id")
    text = str(msg.get("text", "")).lower().strip()

    if not msg_id:
        return True

    if msg_id in processed_messages:
        return True

    if author_id == 0:
        return True

    if str(author_id) == str(USER_ID):
        return True

    if not text or len(text) < 2:
        return True

    blocked_phrases = [
        "system wz",
        "сообщение удалено",
        "сообщение не отправлено",
        "подозрения на спам",
        "создана новая сделка",
        "контактная информация сохранена",
        "обращение направлено",
        "начат новый диалог",
        "завершил работу",
        "переданы дополнительные данные",
        "отправлено автоматически"
    ]

    for phrase in blocked_phrases:
        if phrase in text:
            return True

    return False


def intercept_openline_chat(chat_id: int):
    result = bitrix_call(
        "imopenlines.session.intercept",
        {"CHAT_ID": chat_id}
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
    print("MATKASYM STABLE SUPPORT VERSION ACTIVE")

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
                    print("SKIPPED MESSAGE:", msg_id)
                    continue

                processed_messages.add(msg_id)

                reply = make_reply(text, chat_id)
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
