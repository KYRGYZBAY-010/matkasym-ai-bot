from fastapi import FastAPI, Request
import requests
import os

app = FastAPI()

BITRIX_WEBHOOK = os.getenv("BITRIX_WEBHOOK")

@app.get("/")
def root():
    return {"status": "MATKASYM AI BOT WORKING"}

@app.post("/webhook")
async def webhook(request: Request):

    try:
        form_data = await request.form()

        print("FORM DATA:")
        print(dict(form_data))

        data = dict(form_data)

        message = str(data.get("data[MESSAGE]", "")).lower()

        chat_id = data.get("data[CHAT_ID]")
        crm_entity = data.get("data[CRM_ENTITY]")
        user_id = 100023

        reply = None

        if "антен" in message or "канал" in message:
            reply = (
                "Саламатсызбы 😊\n\n"
                "1. Настройкага кириңиз\n"
                "2. DTV же Цифровое ТВ тандаңыз\n"
                "3. Автопоиск каналов басыңыз\n\n"
                "Эгер жардам керек болсо менюну сүрөткө тартып жибериңиз."
            )

        elif "сушилка" in message or "сломал" in message:
            reply = (
                "Саламатсызбы.\n"
                "Сураныч сынган жердин сүрөтүн жибериңиз 😊"
            )

        if reply:
            url = f"{BITRIX_WEBHOOK}imopenlines.crm.message.add"

            payload = {
                "CRM_ENTITY_TYPE": "DEAL",
                "CRM_ENTITY": crm_entity,
                "CHAT_ID": chat_id,
                "USER_ID": user_id,
                "MESSAGE": reply
            }

            response = requests.post(url, data=payload)

            print(response.text)

    except Exception as e:
        print("ERROR:")
        print(e)

    return {"ok": True}
