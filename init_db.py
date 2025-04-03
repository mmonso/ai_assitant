import sqlite3
import os

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
        print(f"Applying schema from '{SCHEMA_FILE}' to database '{DATABASE_NAME}'...")
        try:
            with open(SCHEMA_FILE, 'r') as f:
                schema_sql = f.read()
            cursor.executescript(schema_sql)
            conn.commit()
            print(f"Schema applied successfully.")
        except FileNotFoundError:
            print(f"Error: Schema file '{SCHEMA_FILE}' not found.")
            raise # Re-raise the exception to stop execution
        except sqlite3.Error as e:
            print(f"Error applying schema: {e}")
            raise # Re-raise the exception

    except sqlite3.Error as e:
        print(f"An error occurred during database initialization: {e}")
    except FileNotFoundError:
        print(f"Error: Schema file '{SCHEMA_FILE}' not found.")
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    initialize_database()