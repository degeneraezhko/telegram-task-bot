import logging
import os
import sqlite3
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, ConversationHandler, ContextTypes
)

# States
CHOOSING, ADDING_TASK, SETTING_DATE, SETTING_PRIORITY = range(4)

DB_PATH = "tasks.db"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            text TEXT,
            due_date TEXT,
            priority TEXT DEFAULT 'medium',
            done INTEGER DEFAULT 0,
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()


def get_tasks(user_id: int, show_all: bool = False) -> list:
    conn = sqlite3.connect(DB_PATH)
    if show_all:
        rows = conn.execute(
            "SELECT id, text, due_date, priority, done FROM tasks WHERE user_id = ? ORDER BY priority, due_date",
            (user_id,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, text, due_date, priority, done FROM tasks WHERE user_id = ? AND done = 0 ORDER BY priority, due_date",
            (user_id,)
        ).fetchall()
    conn.close()
    return rows


PRIORITY_EMOJI = {"high": "🔴", "medium": "🟡", "low": "🟢"}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ["📋 Мои задачи", "➕ Добавить задачу"],
        ["✅ Завершить", "🗑 Удалить"],
        ["📊 Статистика"]
    ]
    await update.message.reply_text(
        "👋 Привет! Я бот-планировщик задач.\n\n"
        "Что хочешь сделать?",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return CHOOSING


async def show_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tasks = get_tasks(update.effective_user.id)
    if not tasks:
        await update.message.reply_text("📭 У тебя пока нет задач. Добавь первую!")
        return CHOOSING

    lines = ["📋 *Твои задачи:*\n"]
    for tid, text, due, priority, done in tasks:
        status = "✅" if done else "⬜"
        p = PRIORITY_EMOJI.get(priority, "🟡")
        due_str = f" (до {due})" if due else ""
        lines.append(f"{status} {p} `{tid}.` {text}{due_str}")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
    return CHOOSING


async def add_task_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📝 Опиши задачу:",
        reply_markup=ReplyKeyboardRemove()
    )
    return ADDING_TASK


async def add_task_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_task"] = update.message.text
    await update.message.reply_text(
        "📅 Укажи дедлайн (ДД.ММ.ГГГГ) или отправь /skip:",
    )
    return SETTING_DATE


async def set_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["due_date"] = update.message.text
    keyboard = [["🔴 Высокий", "🟡 Средний", "🟢 Низкий"]]
    await update.message.reply_text(
        "⚡ Приоритет:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    )
    return SETTING_PRIORITY


async def skip_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["due_date"] = None
    keyboard = [["🔴 Высокий", "🟡 Средний", "🟢 Низкий"]]
    await update.message.reply_text(
        "⚡ Приоритет:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    )
    return SETTING_PRIORITY


async def set_priority(update: Update, context: ContextTypes.DEFAULT_TYPE):
    priority_map = {"🔴 Высокий": "high", "🟡 Средний": "medium", "🟢 Низкий": "low"}
    priority = priority_map.get(update.message.text, "medium")

    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO tasks (user_id, text, due_date, priority, created_at) VALUES (?, ?, ?, ?, ?)",
        (update.effective_user.id, context.user_data["new_task"],
         context.user_data.get("due_date"), priority, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

    keyboard = [
        ["📋 Мои задачи", "➕ Добавить задачу"],
        ["✅ Завершить", "🗑 Удалить"],
        ["📊 Статистика"]
    ]
    await update.message.reply_text(
        "✅ Задача добавлена!",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return CHOOSING


async def complete_task_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tasks = get_tasks(update.effective_user.id)
    if not tasks:
        await update.message.reply_text("📭 Нет активных задач.")
        return CHOOSING
    lines = ["Отправь номер задачи для завершения:\n"]
    for tid, text, due, priority, done in tasks:
        if not done:
            p = PRIORITY_EMOJI.get(priority, "🟡")
            lines.append(f"`{tid}.` {p} {text}")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
    context.user_data["action"] = "complete"
    return CHOOSING


async def delete_task_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отправь номер задачи для удаления:")
    context.user_data["action"] = "delete"
    return CHOOSING


async def handle_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.text.isdigit():
        await update.message.reply_text("Отправь номер задачи.")
        return CHOOSING

    tid = int(update.message.text)
    conn = sqlite3.connect(DB_PATH)
    action = context.user_data.get("action", "complete")

    if action == "complete":
        conn.execute("UPDATE tasks SET done = 1 WHERE id = ? AND user_id = ?", (tid, update.effective_user.id))
        msg = "✅ Задача завершена!"
    else:
        conn.execute("DELETE FROM tasks WHERE id = ? AND user_id = ?", (tid, update.effective_user.id))
        msg = "🗑 Задача удалена!"

    conn.commit()
    conn.close()
    await update.message.reply_text(msg)
    return CHOOSING


async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect(DB_PATH)
    uid = update.effective_user.id
    total = conn.execute("SELECT COUNT(*) FROM tasks WHERE user_id = ?", (uid,)).fetchone()[0]
    done = conn.execute("SELECT COUNT(*) FROM tasks WHERE user_id = ? AND done = 1", (uid,)).fetchone()[0]
    high = conn.execute("SELECT COUNT(*) FROM tasks WHERE user_id = ? AND priority = 'high' AND done = 0", (uid,)).fetchone()[0]
    conn.close()

    active = total - done
    await update.message.reply_text(
        f"📊 *Статистика:*\n\n"
        f"Всего задач: {total}\n"
        f"Активных: {active}\n"
        f"Завершено: {done}\n"
        f"Срочных (высокий приоритет): {high}",
        parse_mode="Markdown"
    )
    return CHOOSING


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отмена.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


def main():
    init_db()
    token = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TOKEN_HERE")
    app = Application.builder().token(token).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING: [
                MessageHandler(filters.Regex("📋 Мои задачи"), show_tasks),
                MessageHandler(filters.Regex("➕ Добавить задачу"), add_task_start),
                MessageHandler(filters.Regex("✅ Завершить"), complete_task_prompt),
                MessageHandler(filters.Regex("🗑 Удалить"), delete_task_prompt),
                MessageHandler(filters.Regex("📊 Статистика"), show_stats),
                MessageHandler(filters.Regex(r"^\d+$"), handle_number),
            ],
            ADDING_TASK: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_task_text)],
            SETTING_DATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, set_date),
                CommandHandler("skip", skip_date),
            ],
            SETTING_PRIORITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_priority)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv)
    app.run_polling()


if __name__ == "__main__":
    main()
