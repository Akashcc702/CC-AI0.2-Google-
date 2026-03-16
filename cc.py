import os
from openai import OpenAI
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes
from flask import Flask
from threading import Thread

# ---------------- WEB SERVER ----------------
app_web = Flask(__name__)

@app_web.route("/")
def home():
    return "CC AI Bot Running 🚀"

def run():
    port = int(os.environ.get("PORT", 10000))
    app_web.run(host="0.0.0.0", port=port)

def keep_alive():
    server = Thread(target=run)
    server.start()

# ---------------- API KEYS ----------------
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# ---------------- AI CLIENT ----------------
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY
)

# ---------------- MEMORY ----------------
user_memory = {}

# ---------------- START COMMAND ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Hello! I am CC AI Bot.\nAsk me anything."
    )

# ---------------- MESSAGE HANDLER ----------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.message.chat_id
    user_input = update.message.text

    if user_id not in user_memory:
        user_memory[user_id] = []

    user_memory[user_id].append({
        "role": "user",
        "content": user_input
    })

    try:

        response = client.chat.completions.create(
            model="google/gemma-3-4b-it",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful AI assistant."
                }
            ] + user_memory[user_id]
        )

        ai_reply = response.choices[0].message.content

    except Exception as e:
        ai_reply = f"⚠️ AI Error: {str(e)}"

    user_memory[user_id].append({
        "role": "assistant",
        "content": ai_reply
    })

    await update.message.reply_text(ai_reply)

# ---------------- RUN BOT ----------------
keep_alive()

app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

print("CC AI Bot Running...")

app.run_polling()
