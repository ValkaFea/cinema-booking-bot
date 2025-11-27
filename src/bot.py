from __future__ import annotations

import logging
import os

from dotenv import load_dotenv
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ----------------- настройки логирования -----------------
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ----------------- загрузка переменных окружения -----------------
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не найден в .env файле")


# ----------------- клавиатура главного меню -----------------
def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton("Записаться"), KeyboardButton("Отменить запись")],
        [KeyboardButton("Расписание"), KeyboardButton("Правила посещения")],
    ]
    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        one_time_keyboard=False,
    )


# ----------------- handlers -----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /start – приветствие и показ главного меню."""
    user = update.effective_user
    first_name = user.first_name if user else "друг"

    text = (
        f"Привет, {first_name}! 🎬\n\n"
        "Я бот кинопоказов.\n\n"
        "Что хочешь сделать?"
    )

    await update.message.reply_text(
        text,
        reply_markup=get_main_menu_keyboard(),
    )


async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик нажатий на кнопки главного меню (по тексту сообщения)."""
    text = (update.message.text or "").strip()

    if text == "Записаться":
        await update.message.reply_text(
            "Скоро здесь будет запись на конкретный показ 👀",
            reply_markup=get_main_menu_keyboard(),
        )
    elif text == "Отменить запись":
        await update.message.reply_text(
            "Здесь позже сделаем отмену записи.",
            reply_markup=get_main_menu_keyboard(),
        )
    elif text == "Расписание":
        schedule_text = (
            "🎞 Расписание ближайших показов:\n\n"
            "23.11 — Милая Френсис\n"
            "30.11 — Она\n"
            "07.12 — Перед рассветом\n"
            "14.12 — Амели\n"
            "21.12 — Вкус вишни\n"
            "28.12 — Париж, я люблю тебя\n\n"
            "Количество мест на каждый показ: 24"
        )
        await update.message.reply_text(
            schedule_text,
            reply_markup=get_main_menu_keyboard(),
        )
    elif text == "Правила посещения":
        # Пока поставим заглушку, потом сюда можно вставить реальные правила
        rules_text = (
            "📜 Правила посещения кинопоказов:\n"
            "1. Приходи вовремя, за 10–15 минут до начала.\n"
            "2. Если не сможешь прийти — пожалуйста, отмени запись.\n"
            "3. Уважай других зрителей: выключи звук на телефоне.\n"
            "4. Еду и напитки согласовать с организатором.\n\n"
            "Позже можем поменять этот текст 🙂"
        )
        await update.message.reply_text(
            rules_text,
            reply_markup=get_main_menu_keyboard(),
        )
    else:
        # Любое другое сообщение – мягко возвращаем в главное меню
        await update.message.reply_text(
            "Я тебя не понял 🧐\n\n"
            "Выбери действие из меню ниже:",
            reply_markup=get_main_menu_keyboard(),
        )


# ----------------- main -----------------
def main() -> None:
    """Точка входа в приложение."""
    application = Application.builder().token(BOT_TOKEN).build()

    # Команда /start
    application.add_handler(CommandHandler("start", start))

    # Обработчик текстовых сообщений (кнопки меню)
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_main_menu,
        )
    )

    logger.info("Бот запущен. Нажми Ctrl+C для остановки.")
    application.run_polling()


if __name__ == "__main__":
    main()
