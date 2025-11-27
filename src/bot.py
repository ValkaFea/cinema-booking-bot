from __future__ import annotations

import logging
import os

from dotenv import load_dotenv
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

from db import (
    init_db,
    get_screenings_with_stats,
    create_booking,
    get_user_bookings,
    cancel_booking,
    get_all_active_bookings,
    add_screening,
    update_screening,
    delete_screening,
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

# ----------------- админы -----------------
# Админы по username без @
ADMIN_USERNAMES = {"valkafea", "yurgya"}


def is_admin(user) -> bool:
    """Проверяем, является ли пользователь админом по username."""
    if user is None:
        return False
    if not user.username:
        return False
    return user.username in ADMIN_USERNAMES


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


# ----------------- текст расписания -----------------
def build_schedule_text() -> str:
    screenings = get_screenings_with_stats()
    if not screenings:
        return "🎞 Пока нет запланированных показов."

    lines = ["🎞 Расписание ближайших показов:\n"]
    for s in screenings:
        lines.append(
            f"{s.date} — {s.title} "
            f"(свободно {s.free_places} из {s.capacity})"
        )
    return "\n".join(lines)


# ----------------- handlers -----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /start – приветствие и показ главного меню."""
    user = update.effective_user
    first_name = user.first_name if user else "друг"

    text = (
        f"Привет, {first_name}! 🎬\n\n"
        "Я бот кинопоказов URBAN CINEMA.\n\n"
        "Выбери действие из меню ниже:"
    )

    await update.message.reply_text(
        text,
        reply_markup=get_main_menu_keyboard(),
    )


async def whoami(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Служебная команда — показать информацию о пользователе."""
    user = update.effective_user
    if not user:
        return
    text = (
        f"Твой Telegram ID: `{user.id}`\n"
        f"username: @{user.username}\n"
        f"Имя: {user.full_name}"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def show_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        build_schedule_text(),
        reply_markup=get_main_menu_keyboard(),
    )


async def show_rules(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    rules_text = (
        "📜 Правила посещения URBAN CINEMA ❄️\n\n"
        "• Посещение только по записи ☃️\n"
        "• Записаться можно по ссылке в шапке профиля 🔗\n"
        "• Вход на кинопоказ = любой заказ в кафе ☕️🍰\n"
        "• Запись даёт вам право занять любое свободное место в зале.\n"
        "  Чтобы выбрать самое уютное — приходите заранее (~30 мин) 🕒\n"
        "• Отменить участие можно за 3 часа до начала сеанса 🔁\n"
        "• Если вы дважды подряд не приходите и не отменяете запись —\n"
        "  доступ к кинопоказам временно закрывается 🚪\n\n"
        "Мы бережно относимся к атмосфере и комфорте гостей, поэтому\n"
        "просим приходить вовремя и выключать звук на телефонах 📵✨\n"
    )
    await update.message.reply_text(
        rules_text,
        reply_markup=get_main_menu_keyboard(),
    )


async def show_booking_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показ списка показов с количеством свободных мест."""
    screenings = get_screenings_with_stats()
    if not screenings:
        await update.message.reply_text(
            "Пока нет доступных показов.",
            reply_markup=get_main_menu_keyboard(),
        )
        return

    lines = ["Выбери показ, на который хочешь записаться:\n"]
    keyboard_buttons: list[list[InlineKeyboardButton]] = []

    for s in screenings:
        line = (
            f"{s.date} — {s.title} "
            f"({s.free_places} из {s.capacity} мест свободно)"
        )
        lines.append(line)
        keyboard_buttons.append(
            [
                InlineKeyboardButton(
                    text=line,
                    callback_data=f"book:{s.id}",
                )
            ]
        )

    text = "\n".join(lines)

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard_buttons),
    )


async def show_cancel_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показываем пользователю его активные записи."""
    user = update.effective_user
    if user is None:
        return

    bookings = get_user_bookings(user.id)
    if not bookings:
        await update.message.reply_text(
            "У тебя пока нет активных записей 🎟",
            reply_markup=get_main_menu_keyboard(),
        )
        return

    lines = ["Твои активные записи:\n"]
    keyboard_buttons: list[list[InlineKeyboardButton]] = []

    for b in bookings:
        line = f"{b.date} — {b.title}"
        lines.append(f"• {line}")
        keyboard_buttons.append(
            [
                InlineKeyboardButton(
                    text=f"Отменить: {line}",
                    callback_data=f"cancel:{b.id}",
                )
            ]
        )

    text = "\n".join(lines)
    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard_buttons),
    )


async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик нажатий на кнопки главного меню (по тексту сообщения)."""
    text = (update.message.text or "").strip()

    if text == "Записаться":
        await show_booking_menu(update, context)
    elif text == "Отменить запись":
        await show_cancel_menu(update, context)
    elif text == "Расписание":
        await show_schedule(update, context)
    elif text == "Правила посещения":
        await show_rules(update, context)
    else:
        # Любое другое сообщение – мягко возвращаем в главное меню
        await update.message.reply_text(
            "Я тебя не понял 🧐\n\n"
            "Выбери действие из меню ниже:",
            reply_markup=get_main_menu_keyboard(),
        )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка нажатий на inline-кнопки 'Записаться' / 'Отменить'."""
    query = update.callback_query
    if query is None:
        return

    await query.answer()
    data = (query.data or "").strip()
    user = query.from_user
    user_id = user.id

    if data.startswith("book:"):
        try:
            screening_id = int(data.split(":", 1)[1])
        except ValueError:
            await query.edit_message_text("Что-то пошло не так при выборе показа.")
            return

        status = create_booking(
            screening_id=screening_id,
            user_id=user_id,
            username=user.username,
            full_name=user.full_name,
        )

        if status == "no_screening":
            text = "Такой показ не найден 🙈"
        elif status == "already":
            text = "Ты уже записан на этот показ ✨"
        elif status == "full":
            text = "К сожалению, на этот показ уже нет свободных мест 😢"
        elif status == "ok":
            text = "Готово! Ты записан на показ 🎟✨"
        else:
            text = "Что-то пошло не так, попробуй ещё раз позже."

        await query.edit_message_text(text)

    elif data.startswith("cancel:"):
        try:
            booking_id = int(data.split(":", 1)[1])
        except ValueError:
            await query.edit_message_text("Не получилось понять, какую запись отменить.")
            return

        ok = cancel_booking(booking_id=booking_id, user_id=user_id)
        if ok:
            text = "Запись отменена. Будем рады видеть тебя в другой раз 💛"
        else:
            text = "Не удалось отменить запись — возможно, её уже нет."

        await query.edit_message_text(text)


async def admin_bookings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показываем все активные записи — только для админов."""
    user = update.effective_user
    if not is_admin(user):
        return

    rows = get_all_active_bookings()
    if not rows:
        await update.message.reply_text("Сейчас нет активных записей.")
        return

    # rows: (date, title, user_id, username, full_name, created_at)
    lines: list[str] = ["📋 Активные записи:\n"]
    current_show = None

    for date, title, user_id, username, full_name, created_at in rows:
        show_key = f"{date} — {title}"
        if show_key != current_show:
            current_show = show_key
            lines.append(f"\n🎞 *{show_key}*")
        user_part = full_name or ""
        if username:
            if user_part:
                user_part += " "
            user_part += f"(@{username})"
        if not user_part:
            user_part = f"ID {user_id}"
        lines.append(f"• {user_part} — ID {user_id} — {created_at}")

    text = "\n".join(lines)
    await update.message.reply_text(text, parse_mode="Markdown")


async def admin_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показываем текущее расписание и подсказки по редактированию — только для админов."""
    user = update.effective_user
    if not is_admin(user):
        return

    screenings = get_screenings_with_stats()
    if not screenings:
        msg = (
            "🎞 Сейчас нет ни одного показа.\n\n"
            "➕ Добавить показ:\n"
            "`/add_show 04.01 24 Название фильма`\n"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")
        return

    lines: list[str] = ["🎞 Текущее расписание:\n"]
    for s in screenings:
        lines.append(
            f"{s.id}) {s.date} — {s.title} "
            f"(мест всего: {s.capacity}, занято: {s.booked})"
        )

    lines.append(
        "\n➕ Добавить:\n"
        "`/add_show 04.01 24 Название фильма`\n"
        "✏️ Изменить:\n"
        "`/edit_show 1 04.01 24 Новое название`\n"
        "🗑 Удалить:\n"
        "`/del_show 1`"
    )

    msg = "\n".join(lines)
    await update.message.reply_text(msg, parse_mode="Markdown")


async def admin_add_show(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Добавить новый показ: /add_show ДД.ММ capacity Название фильма"""
    user = update.effective_user
    if not is_admin(user):
        return

    args = context.args
    if len(args) < 3:
        await update.message.reply_text(
            "Формат: `/add_show ДД.ММ capacity Название фильма`\n"
            "Например: `/add_show 04.01 24 Догма`",
            parse_mode="Markdown",
        )
        return

    date = args[0]
    try:
        capacity = int(args[1])
    except ValueError:
        await update.message.reply_text(
            "Второй аргумент должен быть числом (capacity).\n"
            "Пример: `/add_show 04.01 24 Догма`",
            parse_mode="Markdown",
        )
        return

    title = " ".join(args[2:])
    if not title:
        await update.message.reply_text(
            "Нужно указать название фильма после capacity.",
            parse_mode="Markdown",
        )
        return

    screening_id = add_screening(date, title, capacity)
    await update.message.reply_text(
        f"Добавлен показ: {screening_id}) {date} — {title} (мест: {capacity})"
    )


async def admin_edit_show(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Изменить показ: /edit_show id ДД.ММ capacity Новое название"""
    user = update.effective_user
    if not is_admin(user):
        return

    args = context.args
    if len(args) < 4:
        await update.message.reply_text(
            "Формат: `/edit_show id ДД.ММ capacity Новое название`\n"
            "Например: `/edit_show 1 04.01 24 Новое кино`",
            parse_mode="Markdown",
        )
        return

    try:
        screening_id = int(args[0])
    except ValueError:
        await update.message.reply_text(
            "Первый аргумент (id) должен быть числом.",
            parse_mode="Markdown",
        )
        return

    date = args[1]
    try:
        capacity = int(args[2])
    except ValueError:
        await update.message.reply_text(
            "Третий аргумент (capacity) должен быть числом.",
            parse_mode="Markdown",
        )
        return

    title = " ".join(args[3:])
    if not title:
        await update.message.reply_text(
            "Нужно указать название фильма после capacity.",
            parse_mode="Markdown",
        )
        return

    ok = update_screening(screening_id, date, title, capacity)
    if ok:
        await update.message.reply_text(
            f"Показ {screening_id} обновлён: {date} — {title} (мест: {capacity})"
        )
    else:
        await update.message.reply_text(
            f"Показ с id={screening_id} не найден."
        )


async def admin_del_show(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Удалить показ: /del_show id"""
    user = update.effective_user
    if not is_admin(user):
        return

    args = context.args
    if len(args) != 1:
        await update.message.reply_text(
            "Формат: `/del_show id`\nНапример: `/del_show 1`",
            parse_mode="Markdown",
        )
        return

    try:
        screening_id = int(args[0])
    except ValueError:
        await update.message.reply_text(
            "id должен быть числом.",
            parse_mode="Markdown",
        )
        return

    status = delete_screening(screening_id)
    if status == "not_found":
        await update.message.reply_text(
            f"Показ с id={screening_id} не найден."
        )
    elif status == "has_bookings":
        await update.message.reply_text(
            "Нельзя удалить показ, на который уже есть брони."
        )
    elif status == "ok":
        await update.message.reply_text(
            f"Показ с id={screening_id} удалён."
        )
    else:
        await update.message.reply_text(
            "Что-то пошло не так при удалении показа."
        )


# ----------------- main -----------------
def main() -> None:
    """Точка входа в приложение."""
    # инициализируем БД и расписание
    init_db()

    application = Application.builder().token(BOT_TOKEN).build()

    # Команды
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("whoami", whoami))
    application.add_handler(CommandHandler("admin_bookings", admin_bookings))
    application.add_handler(CommandHandler("admin_schedule", admin_schedule))
    application.add_handler(CommandHandler("add_show", admin_add_show))
    application.add_handler(CommandHandler("edit_show", admin_edit_show))
    application.add_handler(CommandHandler("del_show", admin_del_show))

    # Обработчик текстовых сообщений (кнопки меню)
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_main_menu,
        )
    )

    # Обработчик inline-кнопок
    application.add_handler(CallbackQueryHandler(button_handler))

    logger.info("Бот запущен. Нажми Ctrl+C для остановки.")
    application.run_polling()


if __name__ == "__main__":
    main()
