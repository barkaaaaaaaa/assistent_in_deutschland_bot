import os
import asyncio
import logging
import httpx

logging.basicConfig(level=logging.INFO)

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
CLAUDE_API_KEY = os.environ["CLAUDE_API_KEY"]
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

SYSTEM_PROMPT = """Ты — дружелюбный помощник русскоязычного сообщества про жизнь в Германии. 
Твоя задача — помогать участникам группы с любыми вопросами, связанными с Германией.

Темы, в которых ты помогаешь:
- Визы, ВНЖ, гражданство и документы
- Поиск работы, трудоустройство, резюме, немецкий рынок труда
- Жильё: аренда, покупка, права арендатора
- Немецкий язык: советы по изучению, уровни, курсы
- Медицина: страховка, врачи, больницы
- Налоги: налоговые классы, декларации, льготы
- Образование: школы, университеты, признание дипломов
- Банки, финансы, пенсионная система
- Транспорт: машина, права, общественный транспорт
- Социальные пособия и господдержка

Дополнительная информация:
- Выплаты от джобцентра приходят в последний будний день месяца

Правила:
- Если вопрос был на русском языке - отвечай на русском, если вопрос был на украинском языке - отвечай на украинском, другие языки не используй
- Будь дружелюбным и конкретным
- Если не знаешь точного ответа — честно скажи и посоветуй куда обратиться
- Если вопрос не связан с Германией — не отправляй вообще никакого ответа, даже пустого. Просто игнорируй сообщение полностью"""

chat_histories = {}

async def ask_claude(chat_id: int, user_name: str, user_text: str) -> str:
    if chat_id not in chat_histories:
        chat_histories[chat_id] = []

    chat_histories[chat_id].append({
        "role": "user",
        "content": f"{user_name}: {user_text}"
    })

    if len(chat_histories[chat_id]) > 20:
        chat_histories[chat_id] = chat_histories[chat_id][-20:]

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": CLAUDE_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-sonnet-4-6",
                "max_tokens": 1000,
                "system": SYSTEM_PROMPT,
                "messages": chat_histories[chat_id],
            }
        )
        data = response.json()
        reply = data["content"][0]["text"]

    chat_histories[chat_id].append({
        "role": "assistant",
        "content": reply
    })

    return reply

async def send_message(chat_id: int, text: str, reply_to: int = None):
    payload = {"chat_id": chat_id, "text": text}
    if reply_to:
        payload["reply_to_message_id"] = reply_to
    async with httpx.AsyncClient(timeout=10) as client:
        await client.post(f"{TELEGRAM_API}/sendMessage", json={**payload, "parse_mode": "Markdown"})

async def send_typing(chat_id: int):
    async with httpx.AsyncClient(timeout=10) as client:
        await client.post(f"{TELEGRAM_API}/sendChatAction", json={
            "chat_id": chat_id, "action": "typing"
        })

async def process_update(update: dict):
    message = update.get("message")
    if not message:
        return
    text = message.get("text", "")
    if not text or text.startswith("/"):
        return

    chat_id = message["chat"]["id"]
    message_id = message["message_id"]
    user = message.get("from", {})
    user_name = user.get("first_name", "Участник")

    await send_typing(chat_id)
    try:
        reply = await ask_claude(chat_id, user_name, text)
        await send_message(chat_id, reply, reply_to=message_id)
    except Exception as e:
        logging.error(f"Ошибка: {e}")
        await send_message(chat_id, "Извини, произошла ошибка. Попробуй ещё раз!")

async def main():
    offset = None
    logging.info("Бот запущен!")

    async with httpx.AsyncClient(timeout=10) as client:
        await client.post(f"{TELEGRAM_API}/deleteWebhook")

    while True:
        try:
            params = {"timeout": 30, "allowed_updates": ["message"]}
            if offset:
                params["offset"] = offset

            async with httpx.AsyncClient(timeout=40) as client:
                resp = await client.get(f"{TELEGRAM_API}/getUpdates", params=params)
                data = resp.json()

            if data.get("ok"):
                for update in data.get("result", []):
                    offset = update["update_id"] + 1
                    asyncio.create_task(process_update(update))

        except Exception as e:
            logging.error(f"Ошибка polling: {e}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
