import logging
import requests
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    MessageHandler,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from telegram.constants import ChatType
import threading
import time
import os
import json

# =========================
# НАСТРОЙКИ
# =========================

BOT_TOKEN = os.getenv("BOT_TOKEN")  # токен бота из Render (Env vars)
SHEET_ID = "тут_твой_ID_таблицы_из_URL"  # пример: "1Q0wDfT0sU4eSdsNn2spVsQb7oY... и т.д."
SHEET_NAME = "Имя листа в таблице"  # пример: "Лист1"

WAKE_URL = "https://chatbaza-bot-1.onrender.com"  # <-- ССЫЛКА ТВОЕГО СЕРВИСА В RENDER

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# =========================
# GOOGLE SHEETS КЛИЕНТ
# =========================

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
service_account_info = json.loads(os.getenv("GOOGLE_SERVICE_KEY"))  # ключ сервисного аккаунта из Render
creds = Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
GS = gspread.authorize(creds)
WS = GS.open_by_key(SHEET_ID).worksheet(SHEET_NAME)


# =========================
# УТИЛИТЫ
# =========================

def ts():
    # текущая дата/время как строка
    return datetime.now().strftime("%Y-%m-%d %H:%M")

def find_row_by_chat_id(chat_id: int | str):
    cid = str(chat_id)
    for i, v in enumerate(WS.col_values(1), start=1):
        if v.strip() == cid:
            return i
    return None

def get_status(chat_id: int | str) -> str:
    row = find_row_by_chat_id(chat_id)
    if not row:
        return "Наблюдатель"
    # статус хранится в колонке D (4)
    return (WS.cell(row, 4).value or "Наблюдатель").strip()

def upsert_user(user):
    """
    Сохраняем/обновляем юзера в гугл-таблицу:
    A: chat_id
    B: username
    C: full_name
    D: статус
    E: created_at
    F: updated_at
    """
    chat_id = user.id
    username = (user.username or "").strip()
    full_name = (user.first_name or "") + " " + (user.last_name or "")
    full_name = full_name.strip()

    row = find_row_by_chat_id(chat_id)

    now = ts()

    if row:
        # обновляем существующую строку (кроме created_at)
        WS.update(
            f"A{row}:F{row}",
            [[
                str(chat_id),
                username,
                full_name,
                get_status(chat_id),
                WS.cell(row, 5).value or now,
                now
            ]]
        )
    else:
        # добавляем новую строку
        WS.append_row([
            str(chat_id),
            username,
            full_name,
            "Наблюдатель",
            now,
            now
        ])


# =========================
# ХЕНДЛЕРЫ КОМАНД
# =========================

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    upsert_user(user)

    kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Получить доступ", callback_data="get_access")]]
    )

    await update.message.reply_text(
        "Привет! Это БАЗА. Статус по умолчанию — «Наблюдатель».",
        reply_markup=kb
    )

    text_lines = [
        "1/5. Всем новым — «Наблюдатель».",
        "2/5. Писать могут: «Участник», «Партнёр», «Резидент».",
        "3/5. Тарифы: Участник 2 000₽/мес; Партнёр 10 000₽/мес.",
        "4/5. Напиши «Хочу доступ» — пришлём оплату и включим права.",
        "5/5. Раз в неделю — дайджест мероприятий.",
    ]
    for m in text_lines:
        try:
            await update.message.reply_text(m)
        except:
            pass

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    st = get_status(update.effective_user.id)
    await update.message.reply_text(f"Текущий статус: {st}")


# =========================
# КНОПКА «ПОЛУЧИТЬ ДОСТУП»
# =========================
