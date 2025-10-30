import logging
import requests
from datetime import datetime
import os
import json
import threading
import time

from google.oauth2.service_account import Credentials
import gspread

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.ext import (
    Application,
    MessageHandler,
    CommandHandler,
    CallbackQueryHandler,
    ChatMemberHandler,
    ContextTypes,
    filters,
)
from telegram.constants import ChatType

# ======================
# НАСТРОЙКИ
# ======================

BOT_TOKEN = os.getenv("BOT_TOKEN")  # Токен бота из Render (Env vars)

SHEET_ID = "1qqWJ_DTnGSLdeSd5kni2pSvG17O7yvMSRJ4mWYDlTkk"  # ID гугл-таблицы
SHEET_NAME = "СТИЛЬ"  # имя листа (вкладки) в таблице

ADMIN_USERNAME = "@biznesclub_baza"  # куда писать, если хочет оплатить
PARTICIPANT_PRICE = "1 000₽/мес"
PARTNER_PRICE = "10 000₽/мес"

# Антисон пингует бота, чтобы Render не глушил
WAKE_URL = "https://chatbaza-bot-1.onrender.com/"  # адрес твоего сервиса на Render


# ======================
# ЛОГИРОВАНИЕ
# ======================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# ======================
# GOOGLE SHEETS
# ======================

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
service_account_info = json.loads(os.getenv("GOOGLE_SERVICE_KEY"))
creds = Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
gs = gspread.authorize(creds)
WS = gs.open_by_key(SHEET_ID).worksheet(SHEET_NAME)


def tstr():
    return datetime.now().strftime("%d.%m.%Y %H:%M")


def find_row_by_chat_id(chat_id: int):
    """Ищем строку пользователя по chat_id, если есть в таблице"""
    chat_id = str(chat_id)
    col_values = WS.col_values(1)  # допустим, в колонке A лежит chat_id
    for i, v in enumerate(col_values, start=1):
        if v.strip() == chat_id:
            return i
    return None


def get_status(chat_id: int) -> str:
    """Статус человека из таблицы.
       Если нет строки — значит новый (наблюдатель)."""
    row = find_row_by_chat_id(chat_id)
    if not row:
        return "Наблюдатель"
    # допустим, статус в колонке D (четвёртая)
    val = WS.cell(row, 4).value or ""
    return val.strip() or "Наблюдатель"


def upsert_user(user):
    """Записываем / обновляем человека в таблицу"""
    chat_id = user.id
    username = (user.username or "").strip()
    full_name = (user.first_name or "") + " " + (user.last_name or "")
    full_name = full_name.strip()

    row = find_row_by_chat_id(chat_id)
    if row:
        # Обновляем существующую строку
        WS.update(
            f"A{row}:H{row}",
            [[
                str(chat_id),
                username,
                full_name,
                get_status(chat_id),
                tstr(),
                "", "",  # запас под будущее
            ]],
        )
    else:
        # Добавляем новую строку
        WS.append_row([
            str(chat_id),
            username,
            full_name,
            "Наблюдатель",
            tstr(),
            "",
            "",
            "",
        ])


# ======================
# ТЕКСТЫ / КНОПКИ
# ======================

def build_start_message():
    return (
        "Привет! Это БАЗА.\n"
        "Статус по умолчанию — «Наблюдатель».\n\n"
        "Вот как устроено:\n\n"
        "1/5. Всем новым — «Наблюдатель».\n"
        "2/5. Писать могут: «Участник», «Партнёр», «Резидент».\n"
        f"3/5. Тарифы:\n"
        f"   • Участник — {PARTICIPANT_PRICE}\n"
        f"   • Партнёр — {PARTNER_PRICE}\n"
        "4/5. Напиши «Хочу доступ» — пришлём оплату и включим права.\n"
        "5/5. Раз в неделю — дайджест мероприятий.\n\n"
        "Выбери, что хочешь сделать 👇"
    )


def start_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 Написать администратору", url=f"https://t.me/{ADMIN_USERNAME.lstrip('@')}")],
        [InlineKeyboardButton("📝 Хочу стать Участником", callback_data="role_participant")],
        [InlineKeyboardButton("🤝 Хочу стать Партнёром", callback_data="role_partner")],
    ])


def build_upgrade_text(role: str):
    if role == "participant":
        price = PARTICIPANT_PRICE
        role_name = "Участник"
    else:
        price = PARTNER_PRICE
        role_name = "Партнёр"

    return (
        f"Статус «{role_name}».\n\n"
        f"Стоимость: {price}.\n\n"
        f"Напиши админу {ADMIN_USERNAME} фразу:\n"
        f"«Хочу стать {role_name}» — тебе пришлют оплату и включат права."
    )


# ======================
# ХЕНДЛЕРЫ КОМАНД
# ======================

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start в ЛС с ботом."""
    user = update.effective_user
    upsert_user(user)

    await update.message.reply_text(
        build_start_message(),
        reply_markup=start_keyboard()
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /status в ЛС с ботом."""
    st = get_status(update.effective_user.id)
    await update.message.reply_text(f"Текущий статус: {st}")


# ======================
# ОБРАБОТКА КНОПОК (CallbackQuery)
# ======================

async def on_get_access(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ЭТО УЖЕ НЕ НУЖНО В ТАКОМ ВИДЕ, но оставим чтобы не падало,
    если у кого-то висит старая кнопка 'get_access'."""
    q = update.callback_query
    await q.answer()
    try:
        await q.message.reply_text(
            f"Напиши админу {ADMIN_USERNAME} «Хочу доступ» — пришлём оплату и включим права."
        )
    except Exception:
        pass


async def on_role_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Новые кнопки role_participant / role_partner."""
    q = update.callback_query
    data = q.data
    await q.answer()

    if data == "role_participant":
        txt = build_upgrade_text("participant")
    elif data == "role_partner":
        txt = build_upgrade_text("partner")
    else:
        txt = (
            f"Если хочешь права — напиши {ADMIN_USERNAME}.\n"
            "Мы пришлём оплату и подключим тебя."
        )

    try:
        await q.message.reply_text(txt)
    except Exception:
        pass


# ======================
# СООБЩЕНИЯ В ГРУППЕ
# ======================

async def on_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Проверка прав на отправку сообщений.
    Если статус пользователя не 'Участник', 'Партнёр' или 'Резидент',
    сообщение удаляется, а в ЛС отправляется уведомление.
    """

    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    # Игнорируем, если это не групповое сообщение
    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return

    # Получаем chat_id
    user_chat_id = user.id

    # Проверяем статус пользователя из Google Sheets
    st = get_status(user_chat_id)  # ✅ убедись, что функция get_status уже есть выше в коде

    # Разрешённые статусы
    allowed_statuses = {"Участник", "Партнёр", "Партнер", "Резидент"}

    # Если статус не в списке разрешённых
    if st not in allowed_statuses:
        try:
            await context.bot.delete_message(chat.id, msg.message_id)
        except Exception as e:
            print("Ошибка при удалении сообщения:", e)

        # Отправляем предупреждение пользователю
        text_for_user = (
            "Пока статус «Наблюдатель», писать в чат нельзя.\n\n"
            "Что дальше?\n"
            "1️⃣ Нажми /start у бота — там условия участия.\n"
            "2️⃣ Или сразу напиши @biznesclub_baza фразу «Хочу доступ».\n"
            "Мы пришлём оплату и включим права."
        )
        try:
            await context.bot.send_message(user_chat_id, text_for_user)
        except Exception as e:
            print("Ошибка при отправке личного сообщения:", e)

        return
        
# === Реакция на вступление нового участника в группу ===
async def on_user_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("on_user_join: chat_member =", update.chat_member)
    """
    Срабатывает на статус-ивенты (ChatMemberHandler).
    Добавляем в таблицу ТОЛЬКО когда пользователь реально стал member.
    """
    cm = update.chat_member
    if not cm or cm.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return

    try:
        new = cm.new_chat_member
        if not new or new.status != "member":
            return
        member = new.user
    except Exception:
        return

    # ВАЖНО: передаём ОБЪЕКТ user, НЕ .id
    upsert_user(member)

    try:
        await context.bot.send_message(
            chat_id=member.id,
            text=(
                "👋 Добро пожаловать в БАZА!\n\n"
                "Сейчас у тебя статус «Наблюдатель»: читать можно, писать нельзя.\n\n"
                "Чтобы получить право писать:\n"
                "1️⃣ Открой @chatbazabot и нажми /start.\n"
                "2️⃣ Выбери формат участия — «Участник» или «Партнёр».\n"
                "3️⃣ Или сразу напиши администратору @biznesclub_baza «Хочу доступ»."
            )
        )
    except Exception:
        pass
        # ======================
# АНТИСОН (Flask-сервер для Render)
# ======================
from flask import Flask

flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "Bot is alive", 200
def run_flask():
    # маленький HTTP-сервер на отдельном потоке
    flask_app.run(host="0.0.0.0", port=10000)


def ping_forever():
    # локальный пинг самого Render-URL, чтобы инстанс не выгружался
    while True:
        try:
            requests.get(WAKE_URL, timeout=5)
        except Exception:
            pass
        time.sleep(60)  # каждые 60 секунд

async def on_new_chat_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("on_new_chat_members: new members =", getattr(update.message, "new_chat_members", None))
    """
    Срабатывает, когда приходит service-message с new_chat_members.
    Добавляем каждого нового участника в таблицу.
    """
    if update.effective_chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return
    if not update.message or not update.message.new_chat_members:
        return

    for u in update.message.new_chat_members:
        try:
            upsert_user(u)  # важно: передаём объект User
        except Exception:
            logging.exception("Sheets error (new_chat_members)")
# ======================
# ЗАПУСК ПРИЛОЖЕНИЯ
# ======================

def main():
    # Быстрая проверка токена
    r = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getMe").json()
    if not r.get("ok"):
        raise SystemExit(f"Токен не прошёл проверку: {r}")

    print(f"✅ Telegram OK: @{r['result']['username']}")
    print(f"✅ Sheets OK: лист ({SHEET_NAME}) подключён")

    # стартуем антисоновые потоки ДО запуска бота
    threading.Thread(target=run_flask, daemon=True).start()
    threading.Thread(target=ping_forever, daemon=True).start()

    # Telegram приложение
    app = Application.builder().token(BOT_TOKEN).build()

    # Команды
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))

    # Старый колбэк (чтобы не упасть на старых кнопках)
    app.add_handler(CallbackQueryHandler(on_get_access, pattern="get_access"))

    # Новые колбэки (тарифы)
    app.add_handler(CallbackQueryHandler(on_role_choice, pattern="role_"))

    # Сообщения в группе
    app.add_handler(MessageHandler(filters.ALL, on_group_message))
    app.add_handler(ChatMemberHandler(on_user_join, ChatMemberHandler.CHAT_MEMBER))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, on_new_chat_members))
    print("🤖 Бот запущен. Ожидаю сообщения.")
    app.run_polling()


if __name__ == "__main__":
    main()
