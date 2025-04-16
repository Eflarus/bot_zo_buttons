import logging
from telegram import Update
from database import save_rating
from dotenv import load_dotenv
load_dotenv()
# setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def log_article_rating(update: Update, category: str, article_index: int, rating_type: str):
    """
    log article rating to local database

    args:
        update: the telegram update
        category: article category
        article_index: article index in the faq data
        rating_type: either 'up' for 👍 or 'down' for 👎
    """
    try:
        user = update.effective_user

        if not user:
            logger.warning("no user data available in update")
            return

        # prepare rating data
        rating_value = "👍 Полезно" if rating_type == "up" else "👎 Не полезно"

        # convert index to string id
        article_id = str(article_index)

        # we'll get the actual title from callback data in the main bot
        # this is just a placeholder, the actual title will be set in bot.py
        article_title = f"Article {article_id}"

        # prepare rating data
        rating_data = {
            'user_id': user.id,
            'username': user.username or user.first_name or "Unknown",
            'category': category,
            'article_id': article_id,
            'article_title': article_title,
            'rating': rating_value
        }

        # save to local database
        success = save_rating(rating_data)

        if success:
            logger.info(f"added rating '{rating_type}' for article in category '{category}' by user {user.id}")
        else:
            logger.error(f"failed to save rating for user {user.id}, article {article_id}")

    except Exception as e:
        logger.error(f"error logging article rating: {e}")