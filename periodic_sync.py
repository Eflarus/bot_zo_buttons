#!/usr/bin/env python
import time
import logging
from sync import perform_sync_if_needed
from dotenv import load_dotenv

# load environment variables
load_dotenv()

# setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def main():
    """run periodic sync as a standalone script"""
    logger.info("starting periodic sync service")

    try:
        while True:
            logger.info("running sync...")
            perform_sync_if_needed()

            # wait for next sync cycle
            logger.info("sleeping for 60 seconds before next sync")
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("sync service stopped by user")
    except Exception as e:
        logger.error(f"error in sync service: {e}")


if __name__ == "__main__":
    main()