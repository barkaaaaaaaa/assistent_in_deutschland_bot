import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
import anthropic

# Настройка логов
logging.basicConfig(level=logging.INFO)

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
CLAUDE_API_KEY = os.environ["CLAUDE_API_KEY"]

client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)

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
- Культура, традиции, жизнь в разных городах Германии
- Транспорт: машина, права, общественный транспорт
- Социальные пособия и господдержка

Правила общения:
- Всегда отвечай на русском языке
- Будь дружелюбным, понятным и конкретным
- Если не знаешь точного ответа — честно скажи и посоветуй куда обратиться
- Если вопрос совсем не связан с Германией — вежливо объясни, что ты специализируешься на теме Германии
- Не давай юридических или медицинских гарантий, советуй консультироваться со специалистами в важных случаях
- Отвечай кратко и по делу, без лишней воды"""

# История сообщений для каждого чата (последние 10)
chat_histories = {}

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    chat_id = update.message.chat_id
    user_text = update.message.text
    user_name = update.message.from_user.first_name or "Участник"

    # Инициализируем историю чата
    if chat_id not in chat_histories:
        chat_histories[chat_id] = []

    # Добавляем сообщение пользователя в историю
    chat_histories[chat_id].append({
        "role": "user",
        "content": f"{user_name}: {user_text}"
    })

    # Ограничиваем историю последними 10 сообщениями
    if len(chat_histories[chat_id]) > 10:
        chat_histories[chat_id] = chat_histories[chat_id][-10:]

    # Показываем что бот печатает
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1000,
            system=SYSTEM_PROMPT,
            messages=chat_histories[chat_id]
        )

        reply = response.content[0].text

        # Добавляем ответ бота в историю
        chat_histories[chat_id].append({
            "role": "assistant",
            "content": reply
        })

        await update.message.reply_text(reply)

    except Exception as e:
        logging.error(f"Ошибка: {e}")
        await update.message.reply_text("Извини, произошла ошибка. Попробуй ещё раз!")

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    # Отвечает на все текстовые сообщения (в группе и в личке)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()
