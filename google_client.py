import os
import logging
import time
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv
load_dotenv()
# setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# google sheets credentials
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]
SPREADSHEET_ID = os.environ.get('SPREADSHEET_ID')
CREDENTIALS_FILE = 'credentials.json'
USERS_SHEET_NAME = os.environ.get('USERS_SHEET_NAME', 'Users')
RATINGS_SHEET_NAME = os.environ.get('RATINGS_SHEET_NAME', 'Ratings')

# reusable sheets client
sheets_client = None
last_client_refresh = 0
CLIENT_REFRESH_INTERVAL = 1800  # refresh client every 30 minutes


def get_sheets_client():
    """Get and reuse gspread client to avoid repeated authorization"""
    global sheets_client, last_client_refresh

    current_time = time.time()

    # reuse existing client if valid and not expired
    if sheets_client is not None and current_time - last_client_refresh < CLIENT_REFRESH_INTERVAL:
        try:
            # quick check if client is still valid
            sheets_client.list_spreadsheet_files(1)
            return sheets_client
        except Exception:
            # token expired or other error, will reinitialize
            pass

    # initialize new client
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, SCOPES)
        sheets_client = gspread.authorize(creds)
        last_client_refresh = current_time
        logger.info("created new google sheets client")
        return sheets_client
    except Exception as e:
        logger.error(f"error creating google sheets client: {e}")
        return None


def ensure_sheet_exists(spreadsheet, sheet_name, headers):
    """ensure that a sheet exists with the given headers"""
    try:
        # try to get the sheet
        sheet = spreadsheet.worksheet(sheet_name)

        # check if headers match
        existing_headers = sheet.row_values(1)
        if existing_headers != headers:
            # update headers if they don't match
            for i, header in enumerate(headers, start=1):
                sheet.update_cell(1, i, header)

        return sheet
    except gspread.exceptions.WorksheetNotFound:
        # create new sheet
        sheet = spreadsheet.add_worksheet(title=sheet_name, rows=1000, cols=len(headers))

        # add header row
        sheet.append_row(headers)
        logger.info(f"created new sheet '{sheet_name}'")

        return sheet