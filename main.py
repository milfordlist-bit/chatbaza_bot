import logging, requests
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, MessageHandler, CommandHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.constants import ChatType

BOT_TOKEN  = "8126274660:AAEEA6x8QUJWVOnM7eZs1mPSVLVxWEVoc2g"
SHEET_ID   = "1qqWJ_DTnGSLdeSd5kni2pSvG17O7yvMSRJ4mWYDlTkk"   # <-- твой ID таблицы между /d/ и /edit
SHEET_NAME = "СТИЛЬ"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# --- Google Sheets ---
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
import json, os
service_account_info = json.loads(os.getenv('GOOGLE_SERVICE_KEY'))
creds = Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
GS     = gspread.authorize(creds)
WS     = GS.open_by_key(SHEET_ID).worksheet(SHEET_NAME)

def ts(): return datetime.now().strftime("%Y-%m-%d %H:%M")

def find_row_by_chat_id(chat_id:int):
    for i, v in enumerate(WS.col_values(1), start=1):
        if str(chat_id)==str(v).strip(): return i
    return None

def upsert_user(user):
    chat_id   = user.id
    username  = (user.username or "").lstrip("@")
    full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
    row = find_row_by_chat_id(chat_id)
    if row:
        WS.update(f"C{row}:H{row}", [[full_name, "", "", "", ts(), ""]])
    else:
        WS.append_row([str(chat_id), username, full_name, "Наблюдатель", "Наблюдатель", ts(), ts(), ""])

def get_status(chat_id:int)->str:
    row = find_row_by_chat_id(chat_id)
    if not row: return "Наблюдатель"
    return (WS.cell(row, 4).value or "Наблюдатель").strip()

# --- Команды ---
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    upsert_user(update.effective_user)
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("Получить доступ", callback_data="get_access")]])
    await update.message.reply_text("Привет! Это БАZА. Статус по умолчанию — «Наблюдатель».", reply_markup=kb)

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Текущий статус: {get_status(update.effective_user.id)}")

async def on_get_access(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    for m in [
        "1/5. Всем новым — «Наблюдатель».",
        "2/5. Писать могут: «Участник», «Партнёр», «Резидент».",
        "3/5. Тарифы: Участник 2 000₽/мес; Партнёр 10 000₽/мес.",
        "4/5. Напиши «Хочу доступ» — пришлём оплату и включим права.",
        "5/5. Раз в неделю — дайджест мероприятий."
    ]:
        try: await q.message.chat.send_message(m)
        except: pass

# --- Фильтр в группе ---
async def on_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP): return
    upsert_user(update.effective_user)
    if get_status(update.effective_user.id) not in ("Участник","Партнёр","Резидент"):
        try: await context.bot.delete_message(update.effective_chat.id, update.effective_message.message_id)
        except: pass
        try:
            await context.bot.send_message(
                chat_id=update.effective_user.id,
                text=("Пока статус «Наблюдатель», писать в чат нельзя.\n"
                      "Нажми «Получить доступ» в /start — пришлю инструкцию.")
            )
        except: pass

def main():
    # Быстрая проверка токена
    r = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getMe").json()
    if not r.get("ok"): raise SystemExit(f"Токен не прошёл проверку: {r}")
    print(f"✅ Telegram OK: @{r['result']['username']}")
    print(f"✅ Sheets OK: лист «{SHEET_NAME}» подключён")
    
keep_awake()  # запуск анти-сна

        app = Application.builder().token(BOT_TOKEN).build()
        app.add_handler(CommandHandler("start", cmd_start))
        app.add_handler(CommandHandler("status", cmd_status))
        app.add_handler(CallbackQueryHandler(on_get_access, pattern="get_access"))
        app.add_handler(MessageHandler(filters.ALL, on_group_message))

    print("🚀 Бот запущен. Ожидаю сообщения.")
    app.run_polling()


# === Антисон ===
import threading
import time
import requests

WAKE_URL = "https://chatbaza-bot-1.onrender.com"  # вставь сюда ссылку из Render

def keep_awake():
    def ping():
        while True:
            try:
                requests.get(WAKE_URL, timeout=5)
            except Exception:
                pass
            time.sleep(60)  # пингуем каждые 60 секунд
    t = threading.Thread(target=ping, daemon=True)
    t.start()


if name == "__main__":
    main()
