import logging
import time
import os
from google_client import get_sheets_client, ensure_sheet_exists, SPREADSHEET_ID, USERS_SHEET_NAME, RATINGS_SHEET_NAME
from database import (
    get_unsynced_users, mark_users_synced,
    get_unsynced_ratings, mark_ratings_synced,
    get_setting, set_setting
)


# setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)
from dotenv import load_dotenv
load_dotenv()
# sync intervals
SYNC_INTERVAL = int(os.environ.get('SYNC_INTERVAL', '300'))  # 5 minutes by default


def sync_users_to_sheets():
    """sync local users to google sheets"""
    # get unsynced users
    users = get_unsynced_users()
    if not users:
        return

    logger.info(f"syncing {len(users)} users to google sheets")

    # get sheets client
    client = get_sheets_client()
    if not client:
        logger.error("failed to get google sheets client, can't sync users")
        return

    try:
        # open spreadsheet
        spreadsheet = client.open_by_key(SPREADSHEET_ID)

        # ensure users sheet exists
        headers = [
            "User ID", "Username", "First Name", "Last Name",
            "Language Code", "Is Bot", "Chat ID", "Chat Type",
            "First Seen", "Last Seen"
        ]
        users_sheet = ensure_sheet_exists(spreadsheet, USERS_SHEET_NAME, headers)

        # sync each user
        synced_user_ids = []
        for user in users:
            try:
                # try to find user in sheet
                try:
                    cell = users_sheet.find(str(user['user_id']), in_column=1)
                    row_num = cell.row

                    # update existing user
                    users_sheet.update_cell(row_num, 2, user['username'] or "")
                    users_sheet.update_cell(row_num, 3, user['first_name'] or "")
                    users_sheet.update_cell(row_num, 4, user['last_name'] or "")
                    users_sheet.update_cell(row_num, 5, user['language_code'] or "")
                    users_sheet.update_cell(row_num, 6, "Yes" if user['is_bot'] else "No")
                    users_sheet.update_cell(row_num, 7, str(user['chat_id']) if user['chat_id'] else "")
                    users_sheet.update_cell(row_num, 8, user['chat_type'] or "")
                    # First seen stays the same
                    users_sheet.update_cell(row_num, 10, user['last_seen'])

                except Exception:
                    # user not found, add new row
                    users_sheet.append_row([
                        str(user['user_id']),
                        user['username'] or "",
                        user['first_name'] or "",
                        user['last_name'] or "",
                        user['language_code'] or "",
                        "Yes" if user['is_bot'] else "No",
                        str(user['chat_id']) if user['chat_id'] else "",
                        user['chat_type'] or "",
                        user['first_seen'],
                        user['last_seen']
                    ])

                synced_user_ids.append(user['user_id'])

            except Exception as e:
                logger.error(f"error syncing user {user['user_id']}: {e}")

        # mark users as synced
        if synced_user_ids:
            mark_users_synced(synced_user_ids)
            logger.info(f"successfully synced {len(synced_user_ids)} users")

    except Exception as e:
        logger.error(f"error during user sync: {e}")


def sync_ratings_to_sheets():
    """sync local ratings to google sheets"""
    # get unsynced ratings
    ratings = get_unsynced_ratings()
    if not ratings:
        return

    logger.info(f"syncing {len(ratings)} ratings to google sheets")

    # get sheets client
    client = get_sheets_client()
    if not client:
        logger.error("failed to get google sheets client, can't sync ratings")
        return

    try:
        # open spreadsheet
        spreadsheet = client.open_by_key(SPREADSHEET_ID)

        # ensure ratings sheet exists
        headers = [
            "Timestamp", "User ID", "Username", "Category",
            "Article ID", "Article Title", "Rating"
        ]
        ratings_sheet = ensure_sheet_exists(spreadsheet, RATINGS_SHEET_NAME, headers)

        # sync each rating
        synced_rating_ids = []

        for rating in ratings:
            try:
                # try to find rating for this user and article
                matching_rows = []
                try:
                    user_cells = ratings_sheet.findall(str(rating['user_id']), in_column=2)
                    for cell in user_cells:
                        row = cell.row
                        # check if category and article_id match
                        if (ratings_sheet.cell(row, 4).value == rating['category'] and
                                ratings_sheet.cell(row, 5).value == rating['article_id']):
                            matching_rows.append(row)
                except Exception:
                    # no matching cells found
                    pass

                if matching_rows:
                    # update existing rating (update first found, delete others if any)
                    row_num = matching_rows[0]
                    ratings_sheet.update_cell(row_num, 1, rating['timestamp'])
                    ratings_sheet.update_cell(row_num, 7, rating['rating'])

                    # delete any duplicate ratings for this user and article
                    for row in matching_rows[1:]:
                        ratings_sheet.delete_row(row)

                else:
                    # add new rating
                    ratings_sheet.append_row([
                        rating['timestamp'],
                        str(rating['user_id']),
                        rating.get('username', "Unknown"),
                        rating['category'],
                        rating['article_id'],
                        rating['article_title'],
                        rating['rating']
                    ])

                synced_rating_ids.append(rating['id'])

            except Exception as e:
                logger.error(f"error syncing rating {rating['id']}: {e}")

        # mark ratings as synced
        if synced_rating_ids:
            mark_ratings_synced(synced_rating_ids)
            logger.info(f"successfully synced {len(synced_rating_ids)} ratings")

    except Exception as e:
        logger.error(f"error during ratings sync: {e}")


def should_sync():
    """check if it's time to sync data to google sheets"""
    last_sync_time = int(get_setting('last_users_sync') or '0')
    current_time = int(time.time())

    return current_time - last_sync_time >= SYNC_INTERVAL


def update_last_sync_time():
    """update the last sync time in the database"""
    current_time = str(int(time.time()))
    set_setting('last_users_sync', current_time)
    set_setting('last_ratings_sync', current_time)


def perform_sync_if_needed():
    """check if sync is needed and perform it"""
    if should_sync():
        logger.info("syncing data to google sheets")
        sync_users_to_sheets()
        sync_ratings_to_sheets()
        update_last_sync_time()
        logger.info("sync complete")