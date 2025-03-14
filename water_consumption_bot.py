import pytz
import apscheduler.util

# Monkey-patch APScheduler to force the timezone to a pytz timezone
_original_astimezone = apscheduler.util.astimezone

def patched_astimezone(tz):
    """
    This patch forces APScheduler to use pytz.UTC.
    """

    return pytz.UTC

apscheduler.util.astimezone = patched_astimezone

import logging
import sqlite3
import datetime
import os
import tzlocal

# Patch tzlocal to return a pytz timezone (pytz.UTC) as an extra precaution
tzlocal.get_localzone = lambda: pytz.UTC

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Set up logging for debugging and insights
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize SQLite database
conn = sqlite3.connect('water_consumption.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS consumption (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT,
        amount REAL,
        date TIMESTAMP
    )
''')
conn.commit()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a welcome message and basic instructions."""
    await update.message.reply_text(
        "Welcome to the Water Tracker Bot!\n"
        "Use /log <amount in liters> to record your water consumption.\n"
        "For example: /log 0.5 \n"
        "Use /leaderboard_daily or /leaderboard_weekly to see where you stand against your friends."
    )

async def log_water(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log water consumption sent by the user."""
    try:
        # Get the consumption amount from the command arguments
        amount = float(context.args[0])
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /log <amount in liters>")
        return
    
    user = update.message.from_user
    now = datetime.datetime.now()

    # Insert the record into the database
    cursor.execute(
        "INSERT INTO consumption (user_id, username, amount, date) VALUES (?, ?, ?, ?)",
        (user.id, user.username, amount, now)
    )
    conn.commit()
    
    await update.message.reply_text(f"Logged {amount} liters for {user.username}.")

async def leaderboard_daily(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show a daily leaderboard of water consumption."""
    today = datetime.datetime.now().date()
    start_day = datetime.datetime.combine(today, datetime.time.min)
    end_day = datetime.datetime.combine(today, datetime.time.max)
    
    cursor.execute('''
        SELECT username, SUM(amount) as total
        FROM consumption
        WHERE date BETWEEN ? AND ?
        GROUP BY user_id
        ORDER BY total DESC
    ''', (start_day, end_day))
    results = cursor.fetchall()
    
    if results:
        message = "Daily Leaderboard:\n"
        for rank, (username, total) in enumerate(results, start=1):
            message += f"{rank}. {username}: {total} liters\n"
    else:
        message = "No water consumption logged today."
    
    await update.message.reply_text(message)

async def leaderboard_weekly(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show a weekly leaderboard of water consumption (from Monday to today)."""
    today = datetime.datetime.now().date()
    # Calculate Monday of the current week
    start_of_week = today - datetime.timedelta(days=today.weekday())
    start_week = datetime.datetime.combine(start_of_week, datetime.time.min)
    end_week = datetime.datetime.combine(today, datetime.time.max)
    
    cursor.execute('''
        SELECT username, SUM(amount) as total
        FROM consumption
        WHERE date BETWEEN ? AND ?
        GROUP BY user_id
        ORDER BY total DESC
    ''', (start_week, end_week))
    results = cursor.fetchall()
    
    if results:
        message = "Weekly Leaderboard (since Monday):\n"
        for rank, (username, total) in enumerate(results, start=1):
            message += f"{rank}. {username}: {total} liters\n"
    else:
        message = "No water consumption logged this week."
    
    await update.message.reply_text(message)

def main():
    # Get the bot token from the environment variable
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("Please set the TELEGRAM_BOT_TOKEN environment variable.")
        exit(1)
    
    # Build the application using the new ApplicationBuilder API
    app = ApplicationBuilder().token(token).build()
    
    # Register command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("log", log_water))
    app.add_handler(CommandHandler("leaderboard_daily", leaderboard_daily))
    app.add_handler(CommandHandler("leaderboard_weekly", leaderboard_weekly))
    
    # Start the bot using polling (this call blocks until interrupted)
    app.run_polling()
    logger.info("Bot is running...")

if __name__ == '__main__':
    main()