import sqlite3
import os
import logging # Add logging import

# Basic Logging Configuration for standalone script execution
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__) # Get logger for this module

DATABASE_NAME = 'chat_history.db'
SCHEMA_FILE = 'schema.sql'

def initialize_database():
    """Initializes the SQLite database using the schema.sql file."""
    db_exists = os.path.exists(DATABASE_NAME)
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()

        # Always execute the schema to ensure it's up-to-date
        # This will drop existing tables and recreate them based on schema.sql
        log.info(f"Applying schema from '{SCHEMA_FILE}' to database '{DATABASE_NAME}'...")
        try:
            with open(SCHEMA_FILE, 'r') as f:
                schema_sql = f.read()
            cursor.executescript(schema_sql)
            conn.commit()
            log.info(f"Schema applied successfully.")
        except FileNotFoundError:
            log.critical(f"CRITICAL ERROR: Schema file '{SCHEMA_FILE}' not found. Cannot initialize database.")
            raise # Re-raise the exception to stop execution
        except sqlite3.Error as e:
            log.error(f"Error applying schema from '{SCHEMA_FILE}': {e}", exc_info=True)
            raise # Re-raise the exception

    except sqlite3.Error as e:
        # This might catch connection errors before schema application starts
        log.error(f"An error occurred during database initialization: {e}", exc_info=True)
    except FileNotFoundError:
        # This catch block might be redundant if the inner one re-raises, but keep for safety
        log.critical(f"CRITICAL ERROR: Schema file '{SCHEMA_FILE}' not found (caught in outer block).")
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    initialize_database()