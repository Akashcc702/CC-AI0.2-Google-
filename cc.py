import os
import base64
import random
import requests
import urllib.parse
from datetime import datetime, timedelta
from openai import OpenAI
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
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
    return "CC AI Bot v3.1 Running 🚀"

def _run_web():
    port = int(os.environ.get("PORT", 10000))
    app_web.run(host="0.0.0.0", port=port)

def keep_alive():
    Thread(target=_run_web, daemon=True).start()

# ════════════════════════════════════════════════
#  API KEYS
# ════════════════════════════════════════════════

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
BOT_TOKEN          = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID           = int(os.getenv("ADMIN_ID", "0"))

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

# ════════════════════════════════════════════════
#  MODEL CHAINS
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
        "Specialise in: code generation, bug fixing, auto-completion, website/app creation.\n"
        "Always produce clean, well-commented, production-ready code with markdown code blocks."
    ),
    "research": (
        "You are CC Research AI — a deep search and research specialist.\n"
        "Specialise in: internet research, latest news, article summaries, fact-checking, "
        "market research, and competitor analysis.\n"
        "Provide comprehensive, well-structured, accurate information with numbered lists and sections."
    ),
}

# ════════════════════════════════════════════════
#  BUTTON LABELS  (used for both display & detection)
# ════════════════════════════════════════════════

# ── Main menu ──
BTN_CODING   = "💻 Coding"
BTN_RESEARCH = "🔍 Research"
BTN_IMAGEGEN = "🎨 Image Gen"
BTN_GENERAL  = "🤖 General AI"
BTN_HELP     = "ℹ️ Help"
BTN_RESET    = "🔄 Reset"

# ── Coding sub ──
BTN_CODEGEN  = "⚡ Code Generate"
BTN_BUGFIX   = "🐛 Bug Fixing"
BTN_AUTOCMP  = "✨ Auto Complete"
BTN_WEBAPP   = "🌐 Website / App"

# ── Research sub ──
BTN_INTERNET = "🌐 Internet Research"
BTN_NEWS     = "📰 Latest News"
BTN_SUMMARY  = "📄 Article Summary"
BTN_FACT     = "✅ Fact Checking"
BTN_MARKET   = "📊 Market Research"
BTN_COMPETE  = "🏢 Competitor Analysis"

# ── Image gen sub ──
BTN_T2I      = "🖼️ Text → Image"
BTN_LOGO     = "🎯 Logo Design"
BTN_POSTER   = "📢 Poster / Banner"
BTN_ANIME    = "🎭 Anime / Art"

# ── Common ──
BTN_BACK     = "🔙 Main Menu"

# All navigation buttons (won't be treated as AI input)
NAV_BUTTONS = {
    BTN_CODING, BTN_RESEARCH, BTN_IMAGEGEN, BTN_GENERAL,
    BTN_HELP, BTN_RESET, BTN_CODEGEN, BTN_BUGFIX, BTN_AUTOCMP,
    BTN_WEBAPP, BTN_INTERNET, BTN_NEWS, BTN_SUMMARY, BTN_FACT,
    BTN_MARKET, BTN_COMPETE, BTN_T2I, BTN_LOGO, BTN_POSTER,
    BTN_ANIME, BTN_BACK,
}

# ════════════════════════════════════════════════
#  KEYBOARDS  (ReplyKeyboardMarkup — like Image 1)
# ════════════════════════════════════════════════

def main_kb():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(BTN_CODING),   KeyboardButton(BTN_RESEARCH)],
            [KeyboardButton(BTN_IMAGEGEN), KeyboardButton(BTN_GENERAL)],
            [KeyboardButton(BTN_HELP),     KeyboardButton(BTN_RESET)],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )

def coding_kb():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(BTN_CODEGEN), KeyboardButton(BTN_BUGFIX)],
            [KeyboardButton(BTN_AUTOCMP), KeyboardButton(BTN_WEBAPP)],
            [KeyboardButton(BTN_BACK)],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )

def research_kb():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(BTN_INTERNET), KeyboardButton(BTN_NEWS)],
            [KeyboardButton(BTN_SUMMARY),  KeyboardButton(BTN_FACT)],
            [KeyboardButton(BTN_MARKET),   KeyboardButton(BTN_COMPETE)],
            [KeyboardButton(BTN_BACK)],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )

def imagegen_kb():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(BTN_T2I),    KeyboardButton(BTN_LOGO)],
            [KeyboardButton(BTN_POSTER), KeyboardButton(BTN_ANIME)],
            [KeyboardButton(BTN_BACK)],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )

# ════════════════════════════════════════════════
#  USER STATE
# ════════════════════════════════════════════════

user_memory:  dict = {}   # {uid: [messages]}
user_mode:    dict = {}   # {uid: "general"|"coding"|"research"|"image_gen"}
user_submode: dict = {}   # {uid: sub-label string}
all_users:    set  = set()

# Stats per user: name, chat count, first seen, last active
user_stats:   dict = {}   # {uid: {name, username, chat_count, first_seen, last_active}}

ACTIVE_MINUTES = 5   # consider "currently active" if last msg < 5 min ago

def get_mode(uid): return user_mode.get(uid, "general")
def get_sub(uid):  return user_submode.get(uid, "")

def register_user(uid, update=None):
    all_users.add(uid)
    now = datetime.now()
    if uid not in user_stats:
        user_stats[uid] = {
            "name":       "",
            "username":   "",
            "chat_count": 0,
            "first_seen": now,
            "last_active": now,
        }
    if update and update.message and update.message.from_user:
        fu = update.message.from_user
        user_stats[uid]["name"]     = fu.first_name or fu.username or str(uid)
        user_stats[uid]["username"] = f"@{fu.username}" if fu.username else ""
    user_stats[uid]["last_active"] = now

def bump_chat(uid):
    """Increment chat count and update last_active."""
    if uid in user_stats:
        user_stats[uid]["chat_count"]  += 1
        user_stats[uid]["last_active"]  = datetime.now()

# ════════════════════════════════════════════════
#  AI HELPERS
# ════════════════════════════════════════════════

def call_ai(messages, mode="general"):
    chain = MODELS.get(mode, MODELS["general"])
    last_err = "Unknown error"
    for model in chain:
        try:
            resp = client.chat.completions.create(
                model=model, messages=messages, max_tokens=2048,
            )
            return resp.choices[0].message.content
        except Exception as e:
            last_err = str(e)
    return f"⚠️ All AI models failed.\nError: {last_err}"


def call_vision_ai(image_b64, mime, user_text):
    question = user_text or "Analyse this image in detail. Describe everything you see."
    messages = [{
        "role": "user",
        "content": [
            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{image_b64}"}},
            {"type": "text", "text": question},
        ],
    }]
    for model in MODELS["vision"]:
        try:
            resp = client.chat.completions.create(
                model=model, messages=messages, max_tokens=1024,
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
    BTN_T2I:    "",
    BTN_LOGO:   "professional minimal vector logo, clean white background, bold typography, flat design,",
    BTN_POSTER: "high-quality poster design, vibrant colors, bold layout, professional graphic design,",
    BTN_ANIME:  "anime illustration, highly detailed, studio-quality, vibrant colors, sharp linework,",
}

def make_image(prompt, submode):
    style   = _IMG_STYLE.get(submode, "")
    full    = f"{style} {prompt}".strip() if style else prompt
    encoded = urllib.parse.quote(full)
    seed    = random.randint(1, 999_999)
    return _POLL_URL.format(prompt=encoded, seed=seed)


# ── Prompt prefixes ──
_RESEARCH_PREFIX = {
    BTN_INTERNET: "Conduct thorough research and provide a detailed answer for: ",
    BTN_NEWS:     "Find and summarise the LATEST news about: ",
    BTN_SUMMARY:  "Provide a comprehensive and structured summary of: ",
    BTN_FACT:     "Fact-check the following step by step, citing evidence: ",
    BTN_MARKET:   "Provide detailed market research analysis including size, trends, key players for: ",
    BTN_COMPETE:  "Conduct a thorough competitor analysis including strengths, weaknesses, strategy for: ",
}
_CODING_PREFIX = {
    BTN_CODEGEN: "Generate complete, well-commented, production-ready code for: ",
    BTN_BUGFIX:  "Debug and fix the following code or error (explain issue + provide fix): ",
    BTN_AUTOCMP: "Complete and improve the following code snippet (explain additions): ",
    BTN_WEBAPP:  "Create a complete, working website/app with full code for: ",
}

def build_input(raw, mode, sub):
    if mode == "research":
        p = _RESEARCH_PREFIX.get(sub, "")
        return f"{p}{raw}" if p else raw
    if mode == "coding":
        p = _CODING_PREFIX.get(sub, "")
        return f"{p}{raw}" if p else raw
    return raw

# ════════════════════════════════════════════════
#  COMMANDS
# ════════════════════════════════════════════════

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.chat_id
    register_user(uid, update)
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
        "Choose a mode from the buttons below 👇",
        parse_mode="Markdown",
        reply_markup=main_kb(),
    )

async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.chat_id
    register_user(uid, update)
    user_memory[uid]  = []
    user_mode[uid]    = "general"
    user_submode[uid] = ""
    await update.message.reply_text(
        "🔄 Memory & mode reset! Back to General AI.",
        reply_markup=main_kb(),
    )

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    register_user(update.message.chat_id, update)
    await update.message.reply_text(
        "📖 *CC AI Bot v3 — Help*\n\n"
        "*Commands:*\n"
        "/start — Welcome screen\n"
        "/reset — Clear memory & reset mode\n"
        "/help  — This message\n\n"
        "*Modes (use buttons):*\n"
        "💻 Coding   → Qwen 2.5 Coder 32B\n"
        "🔍 Research → Perplexity + Gemini + Llama\n"
        "🎨 Image Gen → Pollinations.ai (Flux)\n"
        "🤖 General  → Gemma 3 / Llama\n\n"
        "📷 *Image Analysis:* send any photo!\n\n"
        "🔐 *Admin:*\n"
        "/message `<text>` — Broadcast to all users\n"
        "/users — User count\n"
        "/status — Full usage stats",
        parse_mode="Markdown",
        reply_markup=main_kb(),
    )

# ════════════════════════════════════════════════
#  ADMIN COMMANDS
# ════════════════════════════════════════════════

async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.chat_id
    if uid != ADMIN_ID:
        await update.message.reply_text("⛔ Not authorised.")
        return
    text = " ".join(context.args).strip() if context.args else ""
    if not text:
        await update.message.reply_text(
            "⚠️ *Usage:* `/message Your text here`",
            parse_mode="Markdown",
        )
        return
    if not all_users:
        await update.message.reply_text("ℹ️ No users yet.")
        return

    broadcast_text = (
        f"📢 *Message from Admin*\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"{text}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"_— CC AI Bot_"
    )
    status_msg = await update.message.reply_text(f"📤 Broadcasting to {len(all_users)} users…")
    success, failed, blocked = 0, 0, []
    for u in list(all_users):
        try:
            await context.bot.send_message(chat_id=u, text=broadcast_text, parse_mode="Markdown")
            success += 1
        except Exception as e:
            failed += 1
            if any(x in str(e).lower() for x in ["blocked", "deactivated", "forbidden"]):
                blocked.append(u)
    for b in blocked:
        all_users.discard(b)
    await status_msg.edit_text(
        f"✅ *Broadcast Done!*\n\n"
        f"📨 Sent: {success}\n❌ Failed: {failed}\n"
        f"🚫 Blocked: {len(blocked)} (removed)\n"
        f"👥 Active users: {len(all_users)}",
        parse_mode="Markdown",
    )


async def cmd_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.chat_id
    if uid != ADMIN_ID:
        await update.message.reply_text("⛔ Not authorised.")
        return
    await update.message.reply_text(
        f"👥 *Total Users:* {len(all_users)}",
        parse_mode="Markdown",
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.chat_id
    if uid != ADMIN_ID:
        await update.message.reply_text("⛔ Not authorised.")
        return

    now        = datetime.now()
    cutoff     = now - timedelta(minutes=ACTIVE_MINUTES)
    total      = len(all_users)
    active_now = [u for u in all_users if user_stats.get(u, {}).get("last_active", datetime.min) >= cutoff]

    # Build user list (sort by last_active desc, show top 30)
    sorted_users = sorted(
        user_stats.items(),
        key=lambda x: x[1].get("last_active", datetime.min),
        reverse=True,
    )[:30]

    lines = []
    for i, (u, s) in enumerate(sorted_users, 1):
        name      = s.get("name", "") or str(u)
        uname     = s.get("username", "")
        chats     = s.get("chat_count", 0)
        la        = s.get("last_active", datetime.min)
        fs        = s.get("first_seen", datetime.min)

        # Format times
        la_str = la.strftime("%d/%m %H:%M") if la != datetime.min else "—"
        fs_str = fs.strftime("%d/%m/%y")    if fs != datetime.min else "—"

        # Active indicator
        dot = "🟢" if la >= cutoff else "⚫"

        display = f"{uname}" if uname else f"ID:{u}"
        lines.append(
            f"{dot} {i}. {name} ({display})\n"
            f"   💬 {chats} chats | 🕐 {la_str} | 📅 Since {fs_str}"
        )

    user_list = "\n".join(lines) if lines else "_No data yet_"

    msg = (
        f"📊 *CC AI Bot — Status*\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"👥 *Total Users:*   {total}\n"
        f"🟢 *Active Now* (≤{ACTIVE_MINUTES}min): {len(active_now)}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"*Recent Users (latest 30):*\n\n"
        f"{user_list}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🟢 = active now  ⚫ = inactive\n"
        f"_Updated: {now.strftime('%d/%m/%Y %H:%M:%S')}_"
    )

    # Split if too long
    for chunk in [msg[i:i+4096] for i in range(0, len(msg), 4096)]:
        await update.message.reply_text(chunk, parse_mode="Markdown")

# ════════════════════════════════════════════════
#  TEXT HANDLER — handles both button taps & real input
# ════════════════════════════════════════════════

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid  = update.message.chat_id
    text = update.message.text.strip()
    register_user(uid, update)

    if uid not in user_memory:
        user_memory[uid] = []

    # ════ NAVIGATION BUTTON TAPS ════════════════

    if text == BTN_BACK:
        user_mode[uid]    = "general"
        user_submode[uid] = ""
        await update.message.reply_text(
            "🏠 Back to main menu. Choose a mode:",
            reply_markup=main_kb(),
        )
        return

    if text == BTN_RESET:
        user_memory[uid]  = []
        user_mode[uid]    = "general"
        user_submode[uid] = ""
        await update.message.reply_text("🔄 Memory cleared! Back to General AI.", reply_markup=main_kb())
        return

    if text == BTN_HELP:
        await update.message.reply_text(
            "📖 Use the buttons below to switch modes.\n\n"
            "💻 *Coding* — code gen, bug fix, autocomplete, webapp\n"
            "🔍 *Research* — news, summary, fact check, market research\n"
            "🎨 *Image Gen* — text→image, logo, poster, anime\n"
            "🤖 *General* — open-ended chat\n"
            "📷 *Vision* — just send any photo!\n\n"
            "After selecting a mode, pick a sub-type then type your request.",
            parse_mode="Markdown",
            reply_markup=main_kb(),
        )
        return

    # ── Mode switches ──
    if text == BTN_CODING:
        user_mode[uid]    = "coding"
        user_submode[uid] = ""
        await update.message.reply_text(
            "💻 *Coding AI Mode*\nPowered by Qwen 2.5 Coder 32B.\nChoose a task 👇",
            parse_mode="Markdown",
            reply_markup=coding_kb(),
        )
        return

    if text == BTN_RESEARCH:
        user_mode[uid]    = "research"
        user_submode[uid] = ""
        await update.message.reply_text(
            "🔍 *Research AI Mode*\nPerplexity + Gemini + Llama online.\nChoose a type 👇",
            parse_mode="Markdown",
            reply_markup=research_kb(),
        )
        return

    if text == BTN_IMAGEGEN:
        user_mode[uid]    = "image_gen"
        user_submode[uid] = ""
        await update.message.reply_text(
            "🎨 *Image Generation Mode*\nPowered by Pollinations.ai (Flux).\nChoose a style 👇",
            parse_mode="Markdown",
            reply_markup=imagegen_kb(),
        )
        return

    if text == BTN_GENERAL:
        user_mode[uid]    = "general"
        user_submode[uid] = ""
        await update.message.reply_text(
            "🤖 *General AI Mode*\nAsk me anything!",
            parse_mode="Markdown",
            reply_markup=main_kb(),
        )
        return

    # ── Sub-mode selections ──
    if text in (BTN_CODEGEN, BTN_BUGFIX, BTN_AUTOCMP, BTN_WEBAPP):
        user_submode[uid] = text
        await update.message.reply_text(
            f"✅ *{text}* ready!\nNow type your request 👇",
            parse_mode="Markdown",
        )
        return

    if text in (BTN_INTERNET, BTN_NEWS, BTN_SUMMARY, BTN_FACT, BTN_MARKET, BTN_COMPETE):
        user_submode[uid] = text
        await update.message.reply_text(
            f"✅ *{text}* ready!\nNow type your request 👇",
            parse_mode="Markdown",
        )
        return

    if text in (BTN_T2I, BTN_LOGO, BTN_POSTER, BTN_ANIME):
        user_submode[uid] = text
        await update.message.reply_text(
            f"✅ *{text}* ready!\nDescribe what you want to generate 👇",
            parse_mode="Markdown",
        )
        return

    # ════ REAL AI INPUT ════════════════════════

    mode = get_mode(uid)
    sub  = get_sub(uid)
    bump_chat(uid)

    # ── IMAGE GENERATION ──
    if mode == "image_gen":
        status = await update.message.reply_text("🎨 Generating your image… please wait!")
        try:
            url  = make_image(text, sub)
            resp = requests.get(url, timeout=90)
            await status.delete()
            if resp.status_code == 200:
                await update.message.reply_photo(
                    photo=resp.content,
                    caption=f"🎨 *Generated!*\n📝 _{text[:200]}_",
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

    # ── RESEARCH ──
    if mode == "research":
        status = await update.message.reply_text("🔍 Researching… please wait!")
        enhanced = build_input(text, mode, sub)
        messages = (
            [{"role": "system", "content": SYSTEM_PROMPTS["research"]}]
            + user_memory[uid]
            + [{"role": "user", "content": enhanced}]
        )
        ai_reply = call_ai(messages, "research")
        await status.delete()

    # ── CODING ──
    elif mode == "coding":
        status = await update.message.reply_text("💻 Processing your code request…")
        enhanced = build_input(text, mode, sub)
        messages = (
            [{"role": "system", "content": SYSTEM_PROMPTS["coding"]}]
            + user_memory[uid]
            + [{"role": "user", "content": enhanced}]
        )
        ai_reply = call_ai(messages, "coding")
        await status.delete()

    # ── GENERAL ──
    else:
        messages = (
            [{"role": "system", "content": SYSTEM_PROMPTS["general"]}]
            + user_memory[uid]
            + [{"role": "user", "content": text}]
        )
        ai_reply = call_ai(messages, "general")

    # Update memory
    user_memory[uid].append({"role": "user",      "content": text})
    user_memory[uid].append({"role": "assistant",  "content": ai_reply})
    if len(user_memory[uid]) > 20:
        user_memory[uid] = user_memory[uid][-20:]

    for chunk in [ai_reply[i:i+4096] for i in range(0, len(ai_reply), 4096)]:
        await update.message.reply_text(chunk)

# ════════════════════════════════════════════════
#  PHOTO HANDLER
# ════════════════════════════════════════════════

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid     = update.message.chat_id
    caption = update.message.caption or ""
    register_user(uid, update)
    bump_chat(uid)

    status = await update.message.reply_text("📷 Analysing your image… please wait!")
    try:
        photo      = update.message.photo[-1]
        photo_file = await context.bot.get_file(photo.file_id)
        raw_bytes  = await photo_file.download_as_bytearray()
        b64        = base64.b64encode(bytes(raw_bytes)).decode("utf-8")
        analysis   = call_vision_ai(b64, "image/jpeg", caption)

        if uid not in user_memory:
            user_memory[uid] = []
        user_memory[uid].append({"role": "user",      "content": f"[Image] {caption}"})
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
    register_user(update.message.chat_id, update)
    doc = update.message.document
    await update.message.reply_text(
        f"📁 *File received:* `{doc.file_name}`\n\n"
        "Paste the text content here and use *Research → Article Summary* mode for analysis.",
        parse_mode="Markdown",
    )

# ════════════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════════════

keep_alive()

bot_app = ApplicationBuilder().token(BOT_TOKEN).build()

bot_app.add_handler(CommandHandler("start",   cmd_start))
bot_app.add_handler(CommandHandler("reset",   cmd_reset))
bot_app.add_handler(CommandHandler("help",    cmd_help))
bot_app.add_handler(CommandHandler("message", cmd_broadcast))
bot_app.add_handler(CommandHandler("users",   cmd_users))
bot_app.add_handler(CommandHandler("status",  cmd_status))
bot_app.add_handler(MessageHandler(filters.PHOTO,        handle_photo))
bot_app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

print("✅ CC AI Bot v3.1 Running...")
bot_app.run_polling()
