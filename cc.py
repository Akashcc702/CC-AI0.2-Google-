import os
import base64
import random
import requests
import urllib.parse
from openai import OpenAI
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from flask import Flask
from threading import Thread

# ════════════════════════════════════════════════
#  WEB SERVER  (Render keep-alive)
# ════════════════════════════════════════════════

app_web = Flask(__name__)

@app_web.route("/")
def home():
    return "CC AI Bot v3.0 Running 🚀"

def _run_web():
    port = int(os.environ.get("PORT", 10000))
    app_web.run(host="0.0.0.0", port=port)

def keep_alive():
    Thread(target=_run_web, daemon=True).start()

# ════════════════════════════════════════════════
#  API KEYS
# ════════════════════════════════════════════════

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

# ════════════════════════════════════════════════
#  MODEL CHAINS  (primary → fallbacks)
# ════════════════════════════════════════════════

MODELS = {
    "general": [
        "google/gemma-3-4b-it:free",
        "meta-llama/llama-3.2-3b-instruct:free",
        "openrouter/auto",
    ],
    "coding": [
        "qwen/qwen-2.5-coder-32b-instruct:free",
        "qwen/qwen-2.5-coder-7b-instruct:free",
        "openrouter/auto",
    ],
    "research": [
        "perplexity/llama-3.1-sonar-small-128k-online",
        "google/gemini-2.5-flash-preview:free",
        "meta-llama/llama-3.3-70b-instruct:free",
        "openrouter/auto",
    ],
    "vision": [
        "qwen/qwen2.5-vl-7b-instruct:free",
        "meta-llama/llama-3.2-11b-vision-instruct:free",
        "google/gemini-2.0-flash-exp:free",
        "openrouter/auto",
    ],
}

# ════════════════════════════════════════════════
#  SYSTEM PROMPTS
# ════════════════════════════════════════════════

SYSTEM_PROMPTS = {
    "general": (
        "You are CC AI, a helpful, friendly, and intelligent assistant. "
        "Respond clearly and concisely."
    ),
    "coding": (
        "You are CC Coding AI — an expert software engineer powered by Qwen Coder.\n"
        "You specialise in:\n"
        "• Code generation in any language\n"
        "• Bug fixing and debugging\n"
        "• Auto-completion and code suggestions\n"
        "• Full website / app creation\n\n"
        "Always produce clean, well-commented, production-ready code. "
        "Use proper markdown code blocks with the correct language tag. "
        "Explain your approach briefly before the code."
    ),
    "research": (
        "You are CC Research AI — a deep search and research specialist.\n"
        "You specialise in:\n"
        "• Internet research and fact-finding\n"
        "• Latest news analysis\n"
        "• Article / PDF summarisation\n"
        "• Fact-checking and verification\n"
        "• Market research and competitor analysis\n\n"
        "Provide comprehensive, well-structured, and accurate information. "
        "Use numbered lists, sections, and bullet points for clarity. "
        "Always mention your confidence level and note if information may be outdated."
    ),
    "image_gen": (
        "You are an image prompt engineer. When given an idea, enhance it into a "
        "detailed, vivid Stable Diffusion / Flux prompt. Describe subject, style, "
        "lighting, mood, and quality modifiers."
    ),
    "vision": (
        "You are CC Vision AI. Analyse the provided image in detail: describe what you "
        "see, identify key objects, text, colours, context, and answer any user question "
        "about the image."
    ),
}

# ════════════════════════════════════════════════
#  USER STATE
# ════════════════════════════════════════════════

user_memory:  dict = {}
user_mode:    dict = {}
user_submode: dict = {}

def get_mode(uid): return user_mode.get(uid, "general")
def get_sub(uid):  return user_submode.get(uid, "")

# ════════════════════════════════════════════════
#  KEYBOARDS
# ════════════════════════════════════════════════

def main_kb():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💻 Coding",           callback_data="mode_coding"),
            InlineKeyboardButton("🔍 Research",         callback_data="mode_research"),
        ],
        [
            InlineKeyboardButton("🎨 Image Generation", callback_data="mode_image_gen"),
            InlineKeyboardButton("🤖 General AI",       callback_data="mode_general"),
        ],
    ])

def coding_kb():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚡ Code Generate",  callback_data="sub_codegen"),
            InlineKeyboardButton("🐛 Bug Fixing",     callback_data="sub_bugfix"),
        ],
        [
            InlineKeyboardButton("✨ Auto Complete",  callback_data="sub_autocomplete"),
            InlineKeyboardButton("🌐 Website / App",  callback_data="sub_webapp"),
        ],
        [InlineKeyboardButton("🔙 Back", callback_data="back_menu")],
    ])

def research_kb():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🌐 Internet Research",    callback_data="sub_research"),
            InlineKeyboardButton("📰 Latest News",          callback_data="sub_news"),
        ],
        [
            InlineKeyboardButton("📄 Article Summary",      callback_data="sub_summary"),
            InlineKeyboardButton("✅ Fact Checking",        callback_data="sub_factcheck"),
        ],
        [
            InlineKeyboardButton("📊 Market Research",      callback_data="sub_market"),
            InlineKeyboardButton("🏢 Competitor Analysis",  callback_data="sub_competitor"),
        ],
        [InlineKeyboardButton("🔙 Back", callback_data="back_menu")],
    ])

def imagegen_kb():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🖼️ Text → Image",          callback_data="sub_text2img"),
            InlineKeyboardButton("🎯 Logo Design",            callback_data="sub_logo"),
        ],
        [
            InlineKeyboardButton("📢 Poster / Banner",        callback_data="sub_poster"),
            InlineKeyboardButton("🎭 Anime / Realistic Art",  callback_data="sub_anime"),
        ],
        [InlineKeyboardButton("🔙 Back", callback_data="back_menu")],
    ])

# ════════════════════════════════════════════════
#  AI HELPERS
# ════════════════════════════════════════════════

def call_ai(messages, mode="general"):
    chain = MODELS.get(mode, MODELS["general"])
    last_err = "Unknown error"
    for model in chain:
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=2048,
            )
            return resp.choices[0].message.content
        except Exception as e:
            last_err = str(e)
    return f"⚠️ All AI models failed.\nError: {last_err}"


def call_vision_ai(image_b64, mime, user_text):
    question = user_text or "Analyse this image in detail. Describe everything you see."
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{image_b64}"},
                },
                {"type": "text", "text": question},
            ],
        }
    ]
    for model in MODELS["vision"]:
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=1024,
            )
            return resp.choices[0].message.content
        except Exception:
            continue
    return "⚠️ Vision AI unavailable. Please try again."


# ── Pollinations.ai ──
_POLL_URL = (
    "https://image.pollinations.ai/prompt/{prompt}"
    "?width=1024&height=1024&model=flux&seed={seed}&nologo=true&enhance=true"
)

_IMG_STYLE = {
    "sub_text2img": "",
    "sub_logo":     "professional minimal vector logo, clean white background, bold typography, flat design,",
    "sub_poster":   "high-quality poster design, vibrant colors, bold layout, professional graphic design,",
    "sub_anime":    "anime illustration, highly detailed, studio-quality, vibrant colors, sharp linework,",
}

def make_image(prompt, submode):
    style   = _IMG_STYLE.get(submode, "")
    full    = f"{style} {prompt}".strip() if style else prompt
    encoded = urllib.parse.quote(full)
    seed    = random.randint(1, 999_999)
    return _POLL_URL.format(prompt=encoded, seed=seed)


# ── Prompt prefixes ──
_RESEARCH_PREFIX = {
    "sub_research":   "Conduct thorough research and provide a detailed answer for: ",
    "sub_news":       "Find and summarise the LATEST news about: ",
    "sub_summary":    "Provide a comprehensive and structured summary of: ",
    "sub_factcheck":  "Fact-check the following step by step: ",
    "sub_market":     "Provide detailed market research analysis for: ",
    "sub_competitor": "Conduct a thorough competitor analysis for: ",
}

_CODING_PREFIX = {
    "sub_codegen":     "Generate complete, well-commented, production-ready code for: ",
    "sub_bugfix":      "Debug and fix the following code or error: ",
    "sub_autocomplete":"Complete and improve the following code snippet: ",
    "sub_webapp":      "Create a complete, working website/app with full code for: ",
}

def build_input(raw, mode, sub):
    if mode == "research":
        prefix = _RESEARCH_PREFIX.get(sub, "")
        return f"{prefix}{raw}" if prefix else raw
    if mode == "coding":
        prefix = _CODING_PREFIX.get(sub, "")
        return f"{prefix}{raw}" if prefix else raw
    return raw


# ════════════════════════════════════════════════
#  COMMAND HANDLERS
# ════════════════════════════════════════════════

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.chat_id
    user_mode[uid]    = "general"
    user_memory[uid]  = []
    user_submode[uid] = ""
    await update.message.reply_text(
        "🤖 *Welcome to CC AI Bot v3!*\n\n"
        "What I can do:\n"
        "💻 *Coding* — generate, debug & complete code\n"
        "🔍 *Research* — deep search & internet research\n"
        "🎨 *Image Gen* — create stunning AI images\n"
        "📷 *Vision* — send any photo to analyse it!\n\n"
        "Pick a mode below or just start chatting.",
        parse_mode="Markdown",
        reply_markup=main_kb(),
    )

async def cmd_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎛️ *Select Mode:*",
        parse_mode="Markdown",
        reply_markup=main_kb(),
    )

async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.chat_id
    user_memory[uid]  = []
    user_mode[uid]    = "general"
    user_submode[uid] = ""
    await update.message.reply_text("🔄 Memory & mode reset! Fresh start.")

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *CC AI Bot v3 — Commands*\n\n"
        "/start  — Welcome + mode selector\n"
        "/mode   — Open mode selector\n"
        "/reset  — Clear memory & reset mode\n"
        "/help   — This message\n\n"
        "*Modes:*\n"
        "💻 Coding AI   → qwen-2.5-coder-32b (free)\n"
        "🔍 Research    → Perplexity + Gemini + Llama\n"
        "🎨 Image Gen   → Pollinations.ai (Flux)\n"
        "🤖 General     → Gemma 3 / Llama\n\n"
        "📷 *Image Analysis:* just send any photo!\n"
        "📄 *Documents:* paste text content for analysis",
        parse_mode="Markdown",
    )


# ════════════════════════════════════════════════
#  CALLBACK (BUTTON) HANDLER
# ════════════════════════════════════════════════

_SUB_LABELS = {
    "sub_codegen":     "⚡ Code Generation",
    "sub_bugfix":      "🐛 Bug Fixing",
    "sub_autocomplete":"✨ Auto Complete",
    "sub_webapp":      "🌐 Website / App Creation",
    "sub_research":    "🌐 Internet Research",
    "sub_news":        "📰 Latest News",
    "sub_summary":     "📄 Article / PDF Summary",
    "sub_factcheck":   "✅ Fact Checking",
    "sub_market":      "📊 Market Research",
    "sub_competitor":  "🏢 Competitor Analysis",
    "sub_text2img":    "🖼️ Text → Image",
    "sub_logo":        "🎯 Logo Design",
    "sub_poster":      "📢 Poster / Banner",
    "sub_anime":       "🎭 Anime / Realistic Art",
}

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q   = update.callback_query
    uid = q.message.chat_id
    await q.answer()
    data = q.data

    if data == "back_menu":
        await q.edit_message_text(
            "🎛️ *Select Mode:*",
            parse_mode="Markdown",
            reply_markup=main_kb(),
        )
        return

    if data == "mode_general":
        user_mode[uid]    = "general"
        user_submode[uid] = ""
        await q.edit_message_text(
            "🤖 *General AI Mode*\n\nAsk me anything!",
            parse_mode="Markdown",
        )

    elif data == "mode_coding":
        user_mode[uid]    = "coding"
        user_submode[uid] = ""
        await q.edit_message_text(
            "💻 *Coding AI Mode*\n\nPowered by Qwen 2.5 Coder (32B). Choose a task:",
            parse_mode="Markdown",
            reply_markup=coding_kb(),
        )

    elif data == "mode_research":
        user_mode[uid]    = "research"
        user_submode[uid] = ""
        await q.edit_message_text(
            "🔍 *Research AI Mode*\n\nDeep-search with Perplexity + Gemini + Llama. What do you need?",
            parse_mode="Markdown",
            reply_markup=research_kb(),
        )

    elif data == "mode_image_gen":
        user_mode[uid]    = "image_gen"
        user_submode[uid] = ""
        await q.edit_message_text(
            "🎨 *Image Generation Mode*\n\nPowered by Pollinations.ai (Flux). Choose a style:",
            parse_mode="Markdown",
            reply_markup=imagegen_kb(),
        )

    elif data.startswith("sub_"):
        user_submode[uid] = data
        label = _SUB_LABELS.get(data, data)
        await q.edit_message_text(
            f"✅ *{label}* ready!\n\nType your request now and I'll get right to work.",
            parse_mode="Markdown",
        )


# ════════════════════════════════════════════════
#  TEXT MESSAGE HANDLER
# ════════════════════════════════════════════════

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid  = update.message.chat_id
    raw  = update.message.text
    mode = get_mode(uid)
    sub  = get_sub(uid)

    if uid not in user_memory:
        user_memory[uid] = []

    # ── IMAGE GENERATION ──────────────────────────
    if mode == "image_gen":
        status = await update.message.reply_text("🎨 Generating your image… please wait!")
        try:
            url  = make_image(raw, sub)
            resp = requests.get(url, timeout=90)
            await status.delete()
            if resp.status_code == 200:
                await update.message.reply_photo(
                    photo=resp.content,
                    caption=f"🎨 *Generated!*\n📝 _{raw[:200]}_",
                    parse_mode="Markdown",
                )
            else:
                await update.message.reply_text(
                    f"🖼️ [View Image]({url})\n_(tap to open)_",
                    parse_mode="Markdown",
                )
        except Exception as e:
            await status.delete()
            await update.message.reply_text(f"⚠️ Image generation failed: {e}")
        return

    # ── RESEARCH ──────────────────────────────────
    if mode == "research":
        status = await update.message.reply_text("🔍 Researching… please wait!")
        enhanced = build_input(raw, mode, sub)
        messages = (
            [{"role": "system", "content": SYSTEM_PROMPTS["research"]}]
            + user_memory[uid]
            + [{"role": "user", "content": enhanced}]
        )
        ai_reply = call_ai(messages, "research")
        await status.delete()

    # ── CODING ────────────────────────────────────
    elif mode == "coding":
        status = await update.message.reply_text("💻 Processing your code request…")
        enhanced = build_input(raw, mode, sub)
        messages = (
            [{"role": "system", "content": SYSTEM_PROMPTS["coding"]}]
            + user_memory[uid]
            + [{"role": "user", "content": enhanced}]
        )
        ai_reply = call_ai(messages, "coding")
        await status.delete()

    # ── GENERAL ───────────────────────────────────
    else:
        messages = (
            [{"role": "system", "content": SYSTEM_PROMPTS["general"]}]
            + user_memory[uid]
            + [{"role": "user", "content": raw}]
        )
        ai_reply = call_ai(messages, "general")

    # Memory update
    user_memory[uid].append({"role": "user",      "content": raw})
    user_memory[uid].append({"role": "assistant",  "content": ai_reply})
    if len(user_memory[uid]) > 20:
        user_memory[uid] = user_memory[uid][-20:]

    # Send (split at 4096)
    for chunk in [ai_reply[i:i+4096] for i in range(0, len(ai_reply), 4096)]:
        await update.message.reply_text(chunk)


# ════════════════════════════════════════════════
#  PHOTO (IMAGE UPLOAD) HANDLER
# ════════════════════════════════════════════════

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid     = update.message.chat_id
    caption = update.message.caption or ""

    status = await update.message.reply_text("📷 Analysing your image… please wait!")

    try:
        photo      = update.message.photo[-1]           # highest res
        photo_file = await context.bot.get_file(photo.file_id)
        raw_bytes  = await photo_file.download_as_bytearray()
        b64        = base64.b64encode(bytes(raw_bytes)).decode("utf-8")

        analysis = call_vision_ai(b64, "image/jpeg", caption)

        if uid not in user_memory:
            user_memory[uid] = []
        user_memory[uid].append({"role": "user",      "content": f"[Image sent] {caption}"})
        user_memory[uid].append({"role": "assistant",  "content": analysis})

        await status.delete()
        await update.message.reply_text(
            f"🔍 *Image Analysis:*\n\n{analysis}",
            parse_mode="Markdown",
        )

    except Exception as e:
        await status.delete()
        await update.message.reply_text(f"⚠️ Image analysis failed: {e}")


# ════════════════════════════════════════════════
#  DOCUMENT HANDLER
# ════════════════════════════════════════════════

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    await update.message.reply_text(
        f"📁 *File received:* `{doc.file_name}`\n\n"
        "For PDF / article analysis, paste the text content here "
        "and use *Research → Article Summary* mode.",
        parse_mode="Markdown",
    )


# ════════════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════════════

keep_alive()

bot_app = ApplicationBuilder().token(BOT_TOKEN).build()

bot_app.add_handler(CommandHandler("start", cmd_start))
bot_app.add_handler(CommandHandler("mode",  cmd_mode))
bot_app.add_handler(CommandHandler("reset", cmd_reset))
bot_app.add_handler(CommandHandler("help",  cmd_help))
bot_app.add_handler(CallbackQueryHandler(handle_callback))
bot_app.add_handler(MessageHandler(filters.PHOTO,        handle_photo))
bot_app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

print("✅ CC AI Bot v3.0 Running...")
bot_app.run_polling()
