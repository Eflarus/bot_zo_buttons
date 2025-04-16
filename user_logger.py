import logging
from datetime import datetime
from telegram import Update
import time
from database import save_user
from google_client import get_sheets_client
from dotenv import load_dotenv
load_dotenv()
# setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def log_user(update: Update):
    """
    Log user information to local database for later sync with Google Sheets
    """
    try:
        user = update.effective_user

        if not user:
            logger.warning("No user data available in update")
            return

        # prepare user data
        user_data = {
            'user_id': user.id,
            'username': user.username or "",
            'first_name': user.first_name or "",
            'last_name': user.last_name or "",
            'language_code': user.language_code or "",
            'is_bot': user.is_bot,
            'chat_id': update.effective_chat.id if update.effective_chat else None,
            'chat_type': update.effective_chat.type if update.effective_chat else None
        }

        # save to local database
        success = save_user(user_data)

        if success:
            logger.info(f"Logged user: {user.id} ({user.username or user.first_name})")
        else:
            logger.error(f"Failed to log user {user.id}")

    except Exception as e:
        logger.error(f"Error logging user data: {e}")