import sqlite3
import os
import logging
import time
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()
# setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# database file path
DB_FILE = os.environ.get('DB_FILE', 'bot_data.db')


def get_db_connection():
    """Get a connection to the SQLite database"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row  # return rows as dictionaries
    return conn


def init_db():
    """Initialize the database schema if it doesn't exist"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # create users table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        language_code TEXT,
        is_bot INTEGER,
        chat_id INTEGER,
        chat_type TEXT,
        first_seen TEXT,
        last_seen TEXT,
        synced INTEGER DEFAULT 0
    )
    ''')

    # create ratings table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS ratings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        category TEXT,
        article_id TEXT,  
        article_title TEXT,
        rating TEXT,
        timestamp TEXT,
        synced INTEGER DEFAULT 0,
        UNIQUE(user_id, category, article_id)
    )
    ''')

    # create faq content table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS faq_content (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT,
        title TEXT,
        content TEXT,
        last_updated TEXT
    )
    ''')

    # create settings table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    ''')

    # initialize settings if not exist
    cursor.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)',
                   ('last_faq_sync', '0'))
    cursor.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)',
                   ('last_users_sync', '0'))
    cursor.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)',
                   ('last_ratings_sync', '0'))

    conn.commit()
    conn.close()

    logger.info("Database initialized")


# User methods
def save_user(user_data):
    """Save or update user in local database"""
    conn = get_db_connection()
    cursor = conn.cursor()

    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        # check if user exists
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_data['user_id'],))
        existing_user = cursor.fetchone()

        if existing_user:
            # update existing user
            cursor.execute('''
            UPDATE users 
            SET username = ?, first_name = ?, last_name = ?, language_code = ?,
                is_bot = ?, chat_id = ?, chat_type = ?, last_seen = ?, synced = 0
            WHERE user_id = ?
            ''', (
                user_data['username'], user_data['first_name'], user_data['last_name'],
                user_data['language_code'], 1 if user_data['is_bot'] else 0,
                user_data['chat_id'], user_data['chat_type'], current_time,
                user_data['user_id']
            ))
        else:
            # insert new user
            cursor.execute('''
            INSERT INTO users 
            (user_id, username, first_name, last_name, language_code, is_bot,
             chat_id, chat_type, first_seen, last_seen, synced)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_data['user_id'], user_data['username'], user_data['first_name'],
                user_data['last_name'], user_data['language_code'], 1 if user_data['is_bot'] else 0,
                user_data['chat_id'], user_data['chat_type'], current_time, current_time, 0
            ))

        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error saving user: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def get_unsynced_users():
    """Get users that haven't been synced to Google Sheets"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM users WHERE synced = 0')
    users = [dict(user) for user in cursor.fetchall()]

    conn.close()
    return users


def mark_users_synced(user_ids):
    """Mark users as synced to Google Sheets"""
    if not user_ids:
        return

    conn = get_db_connection()
    cursor = conn.cursor()

    # SQLite doesn't support multiple parameterized values in IN clause
    # so we create a parameterized query string
    placeholders = ','.join(['?'] * len(user_ids))

    cursor.execute(f'UPDATE users SET synced = 1 WHERE user_id IN ({placeholders})', user_ids)
    conn.commit()
    conn.close()


# Ratings methods
def save_rating(rating_data):
    """Save or update article rating in local database"""
    conn = get_db_connection()
    cursor = conn.cursor()

    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        # Using REPLACE to handle the UNIQUE constraint
        cursor.execute('''
        REPLACE INTO ratings 
        (user_id, category, article_id, article_title, rating, timestamp, synced)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            rating_data['user_id'], rating_data['category'], rating_data['article_id'],
            rating_data['article_title'], rating_data['rating'], current_time, 0
        ))

        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error saving rating: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def get_unsynced_ratings():
    """Get ratings that haven't been synced to Google Sheets"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM ratings WHERE synced = 0')
    ratings = [dict(rating) for rating in cursor.fetchall()]

    conn.close()
    return ratings


def mark_ratings_synced(rating_ids):
    """Mark ratings as synced to Google Sheets"""
    if not rating_ids:
        return

    conn = get_db_connection()
    cursor = conn.cursor()

    # SQLite doesn't support multiple parameterized values in IN clause
    placeholders = ','.join(['?'] * len(rating_ids))

    cursor.execute(f'UPDATE ratings SET synced = 1 WHERE id IN ({placeholders})', rating_ids)
    conn.commit()
    conn.close()


# FAQ content methods
def clear_faq_content():
    """Clear all FAQ content from local database"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('DELETE FROM faq_content')
    conn.commit()
    conn.close()


def save_faq_content(faq_data):
    """Save FAQ content to local database"""
    conn = get_db_connection()
    cursor = conn.cursor()

    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # first clear existing content
    clear_faq_content()

    try:
        # insert new content
        for category, articles in faq_data.items():
            for article in articles:
                cursor.execute('''
                INSERT INTO faq_content 
                (category, title, content, last_updated)
                VALUES (?, ?, ?, ?)
                ''', (category, article['title'], article['content'], current_time))

        # update last sync time
        cursor.execute('UPDATE settings SET value = ? WHERE key = ?',
                       (str(int(time.time())), 'last_faq_sync'))

        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error saving FAQ content: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def get_faq_data_from_db():
    """Get FAQ data from local database"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM faq_content ORDER BY category, id')
    rows = cursor.fetchall()

    # format data for bot
    formatted_data = {}
    for row in rows:
        category = row['category']

        if category not in formatted_data:
            formatted_data[category] = []

        formatted_data[category].append({
            'id': row['id'],
            'title': row['title'],
            'content': row['content']
        })

    conn.close()
    return formatted_data


def get_setting(key):
    """Get a setting value from the settings table"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
    result = cursor.fetchone()

    conn.close()

    if result:
        return result['value']
    return None


def set_setting(key, value):
    """Set a setting value in the settings table"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('UPDATE settings SET value = ? WHERE key = ?', (value, key))
    conn.commit()
    conn.close()


# Initialize database
init_db()