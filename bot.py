import os
import logging
import time
import asyncio
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)
from user_logger import log_user
from article_ratings import log_article_rating
from google_client import get_sheets_client, SPREADSHEET_ID
from database import init_db

# load environment variables from .env file
load_dotenv()

# setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# global variables
faq_data = {}
last_update_time = 0
UPDATE_INTERVAL = int(os.environ.get('FAQ_UPDATE_INTERVAL', '300'))  # refresh faq data every 5 minutes by default


def get_faq_data():
    """get data from google sheets and format it for the bot"""
    global faq_data, last_update_time

    # check if we need to update
    current_time = time.time()
    if current_time - last_update_time < UPDATE_INTERVAL and faq_data:
        return faq_data

    try:
        # get reusable client
        client = get_sheets_client()

        # open the spreadsheet and get the first sheet
        sheet = client.open_by_key(SPREADSHEET_ID).sheet1

        # get all data
        data = sheet.get_all_values()

        # skip header row if it exists
        if data and len(data) > 0:
            data = data[1:] if data[0][0].lower() in ['группа', 'category', 'group'] else data

        # format data for bot
        formatted_data = {}
        for row in data:
            if len(row) >= 3:  # ensure we have 3 columns
                category, title, content = row[0], row[1], row[2]

                if category not in formatted_data:
                    formatted_data[category] = []

                formatted_data[category].append({
                    'title': title,
                    'content': content
                })

        # update cache
        faq_data = formatted_data
        last_update_time = current_time

        logger.info(f"faq data updated. {len(formatted_data)} categories loaded.")
        return formatted_data

    except Exception as e:
        logger.error(f"error fetching faq data: {e}")
        # return existing data if available, otherwise empty dict
        return faq_data if faq_data else {}


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, edit_message=False):
    """show main menu with categories"""
    data = get_faq_data()

    if not data:
        message_text = "Информация пока не загружена. Пожалуйста, попробуйте позже."
        if edit_message and update.callback_query:
            await update.callback_query.edit_message_text(message_text)
        else:
            await update.message.reply_text(message_text)
        return

    # create keyboard with categories
    keyboard = []
    for category in data.keys():
        keyboard.append([InlineKeyboardButton(category, callback_data=f"cat_{category}")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    message_text = "Выберите категорию вопроса:"

    if edit_message and update.callback_query:
        await update.callback_query.edit_message_text(message_text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(message_text, reply_markup=reply_markup)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """start command handler"""
    # log user information when they start dialog
    log_user(update)

    await show_main_menu(update, context)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """handle button press"""
    query = update.callback_query
    await query.answer()

    data = get_faq_data()
    callback_data = query.data

    # handle category selection
    if callback_data.startswith("cat_"):
        category = callback_data[4:]  # remove 'cat_' prefix

        if category in data:
            articles = data[category]
            keyboard = []

            # create article buttons
            for i, article in enumerate(articles):
                keyboard.append([InlineKeyboardButton(article['title'], callback_data=f"art_{category}_{i}")])

            # add back button
            keyboard.append([InlineKeyboardButton("« Назад", callback_data="main_menu")])

            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(f"Вопросы в категории '{category}':", reply_markup=reply_markup)
        else:
            await query.edit_message_text(f"Категория не найдена. Пожалуйста, вернитесь в главное меню.")

    # handle article selection
    elif callback_data.startswith("art_"):
        parts = callback_data[4:].split("_")
        if len(parts) >= 2:
            category, index = parts[0], int(parts[1])

            if category in data and 0 <= index < len(data[category]):
                article = data[category][index]

                # navigation and rating buttons
                keyboard = [
                    # rating buttons
                    [
                        InlineKeyboardButton("👍 Полезно", callback_data=f"rate_up_{category}_{index}"),
                        InlineKeyboardButton("👎 Не полезно", callback_data=f"rate_down_{category}_{index}")
                    ],
                    # back button
                    [InlineKeyboardButton("« Назад к списку", callback_data=f"cat_{category}")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                # display article
                await query.edit_message_text(
                    f"<b>{article['title']}</b>\n\n{article['content']}",
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
            else:
                await query.edit_message_text("Статья не найдена. Пожалуйста, вернитесь в главное меню.")

    # handle rating
    elif callback_data.startswith("rate_"):
        parts = callback_data.split("_")
        if len(parts) >= 4:
            rating_type = parts[1]  # "up" or "down"
            category = parts[2]
            index = int(parts[3])

            # log the rating
            await log_article_rating(update, category, index, rating_type)

            # show confirmation and return to article
            await query.edit_message_text(
                f"Спасибо за вашу оценку! {'👍' if rating_type == 'up' else '👎'}\n\n"
                f"Через 2 секунды вы вернетесь к статье...",
                parse_mode='HTML'
            )

            # wait briefly
            await asyncio.sleep(2)

            # return to article
            if category in data and 0 <= index < len(data[category]):
                article = data[category][index]

                # navigation and rating buttons
                keyboard = [
                    # rating buttons with disabled state
                    [
                        InlineKeyboardButton("✅ Оценено", callback_data="rated_already")
                    ],
                    # back button
                    [InlineKeyboardButton("« Назад к списку", callback_data=f"cat_{category}")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                # display article again
                await query.edit_message_text(
                    f"<b>{article['title']}</b>\n\n{article['content']}",
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )

    # handle "already rated" button - do nothing
    elif callback_data == "rated_already":
        await query.answer("Вы уже оценили эту статью")

    # handle main menu navigation
    elif callback_data == "main_menu":
        await show_main_menu(update, context, edit_message=True)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """help command handler"""
    await update.message.reply_text(
        "Этот бот предоставляет справочную информацию.\n"
        "Используйте /start для начала работы и навигации по категориям."
    )


def main():
    """start the bot"""
    # wait a bit for services to start if needed
    time.sleep(5)

    # create application
    token = os.environ.get('TELEGRAM_TOKEN')
    if not token:
        logger.error("TELEGRAM_TOKEN not set!")
        return

    # initialize database
    init_db()

    # start application
    application = Application.builder().token(token).build()

    # add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(button_handler))

    # run periodic sync in background
    from sync import perform_sync_if_needed

    # check if job queue is available
    if application.job_queue:
        async def periodic_sync(context: ContextTypes.DEFAULT_TYPE):
            perform_sync_if_needed()

        application.job_queue.run_repeating(periodic_sync, interval=60, first=10)
    else:
        logger.warning("job queue not available, periodic sync will not run automatically")
        logger.warning("install python-telegram-bot[job-queue] for automated sync")

    # start bot
    application.run_polling()


if __name__ == '__main__':
    main()