import sqlite3
import bcrypt
import os
import logging # Add logging import
from contextlib import contextmanager

log = logging.getLogger(__name__) # Get logger for this module

DATABASE_NAME = 'chat_history.db'

@contextmanager
def get_db_connection():
    """Provides a database connection context."""
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        yield conn
    except sqlite3.Error as e:
        log.error(f"Database connection error: {e}", exc_info=True)
        raise # Re-raise the exception after logging
    finally:
        if conn:
            conn.close()

# --- User Management ---

def create_user(username, password):
    """Creates a new user with default settings."""
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # Insert user with null for new fields initially
            cursor.execute("""
                INSERT INTO users (username, password_hash, profile_picture_url, system_prompt, user_info)
                VALUES (?, ?, NULL, NULL, NULL)
            """, (username, hashed_password))
            conn.commit()
            user_id = cursor.lastrowid
            log.info(f"User '{username}' created successfully with user_id: {user_id}.")
            return user_id
    except sqlite3.IntegrityError:
        log.warning(f"Attempted to create user with existing username: '{username}'.")
        return None
    except sqlite3.Error as e:
        log.error(f"Database error during user creation for username '{username}': {e}", exc_info=True)
        return None

def authenticate_user(username, password):
    """Authenticates a user based on username and password."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # Fetch user_id and password_hash
            cursor.execute("SELECT user_id, password_hash FROM users WHERE username = ?", (username,))
            user_data = cursor.fetchone()

            if user_data and bcrypt.checkpw(password.encode('utf-8'), user_data['password_hash']):
                log.info(f"User '{username}' authenticated successfully (user_id: {user_data['user_id']}).")
                return user_data['user_id']
            else:
                log.warning(f"Authentication failed for user '{username}'. Invalid username or password.")
                return None
    except sqlite3.Error as e:
        log.error(f"Database error during authentication for user '{username}': {e}", exc_info=True)
        return None

def get_user_details(user_id):
    """Retrieves user details including settings."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT user_id, username, profile_picture_url, system_prompt, user_info
                FROM users
                WHERE user_id = ?
            """, (user_id,))
            user_details = cursor.fetchone()
            # log.debug(f"Retrieved details for user_id {user_id}") # Optional debug log
            return dict(user_details) if user_details else None
    except sqlite3.Error as e:
        log.error(f"Database error retrieving user details for user_id {user_id}: {e}", exc_info=True)
        return None

def update_username(user_id, new_username):
    """Updates the username for a user, checking for uniqueness."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET username = ? WHERE user_id = ?", (new_username, user_id))
            conn.commit()
            if cursor.rowcount > 0:
                log.info(f"Username updated to '{new_username}' for user_id {user_id}")
                return True
            else:
                # This could happen if user_id doesn't exist
                log.warning(f"Username update for user_id {user_id} to '{new_username}' affected 0 rows. User might not exist.")
                return False
    except sqlite3.IntegrityError:
        log.warning(f"Failed to update username for user_id {user_id}: New username '{new_username}' is already taken.")
        return False
    except sqlite3.Error as e:
        log.error(f"Database error updating username for user_id {user_id} to '{new_username}': {e}", exc_info=True)
        return False

def update_password(user_id, new_password):
    """Updates the password for a user."""
    new_hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET password_hash = ? WHERE user_id = ?", (new_hashed_password, user_id))
            conn.commit()
            if cursor.rowcount > 0:
                log.info(f"Password updated for user_id {user_id}")
                return True
            else:
                log.warning(f"Password update for user_id {user_id} affected 0 rows. User might not exist.")
                return False
    except sqlite3.Error as e:
        log.error(f"Database error updating password for user_id {user_id}: {e}", exc_info=True)
        return False

def update_profile_picture(user_id, picture_url):
    """Updates the profile picture URL for a user."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET profile_picture_url = ? WHERE user_id = ?", (picture_url, user_id))
            conn.commit()
            if cursor.rowcount > 0:
                log.info(f"Profile picture URL updated for user_id {user_id}")
                return True
            else:
                log.warning(f"Profile picture URL update for user_id {user_id} affected 0 rows. User might not exist.")
                return False
    except sqlite3.Error as e:
        log.error(f"Database error updating profile picture URL for user_id {user_id}: {e}", exc_info=True)
        return False

def update_system_prompt(user_id, prompt):
    """Updates the custom system prompt for a user."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET system_prompt = ? WHERE user_id = ?", (prompt, user_id))
            conn.commit()
            if cursor.rowcount > 0:
                log.info(f"System prompt updated for user_id {user_id}")
                return True
            else:
                 log.warning(f"System prompt update for user_id {user_id} affected 0 rows. User might not exist.")
                 return False
    except sqlite3.Error as e:
        log.error(f"Database error updating system prompt for user_id {user_id}: {e}", exc_info=True)
        return False
def update_user_info(user_id, user_info_json):
    """Updates the user_info JSON string for a user."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET user_info = ? WHERE user_id = ?", (user_info_json, user_id))
            conn.commit()
            if cursor.rowcount > 0:
                log.info(f"User info updated for user_id {user_id}")
                return True
            else:
                log.warning(f"User info update for user_id {user_id} affected 0 rows. User might not exist.")
                return False
    except sqlite3.Error as e:
        log.error(f"Database error updating user info for user_id {user_id}: {e}", exc_info=True)
        return False


def update_user_theme(user_id, font_family, font_size, line_spacing):
    """Updates the theme settings for a user."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # Update only the fields provided (assuming None means no change desired,
            # but the API currently sends all fields from the form)
            # A more robust approach might check if the values are actually different
            # from the current DB values before updating.
            cursor.execute("""
                UPDATE users
                SET font_family = ?, font_size = ?, line_spacing = ?
                WHERE user_id = ?
            """, (font_family, font_size, line_spacing, user_id))
            conn.commit()
            if cursor.rowcount > 0:
                log.info(f"Theme settings updated for user_id {user_id}")
                return True
            else:
                log.warning(f"Theme update for user_id {user_id} affected 0 rows. User might not exist.")
                return False
    except sqlite3.Error as e:
        log.error(f"Database error updating theme settings for user_id {user_id}: {e}", exc_info=True)
        return False
def delete_user(user_id):
    """Deletes a user and all associated data (conversations, messages) via CASCADE."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # Foreign key constraints with ON DELETE CASCADE handle conversations/messages
            cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
            conn.commit()
            if cursor.rowcount > 0:
                log.info(f"User {user_id} and associated data deleted successfully.")
                return True
            else:
                log.warning(f"Delete user for user_id {user_id} affected 0 rows. User might not exist.")
                return False
    except sqlite3.Error as e:
        log.error(f"Database error deleting user {user_id}: {e}", exc_info=True)
        return False


# --- Conversation Management (largely unchanged) ---

def create_conversation(user_id, title=None):
    """Creates a new conversation for a user."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO conversations (user_id, title) VALUES (?, ?)",
                           (user_id, title))
            conn.commit()
            new_conversation_id = cursor.lastrowid
            log.info(f"Conversation created with ID: {new_conversation_id} for user_id: {user_id}")
            return new_conversation_id
    except sqlite3.Error as e:
        log.error(f"Database error creating conversation for user_id {user_id}: {e}", exc_info=True)
        return None

def get_conversations(user_id):
    """Retrieves a list of conversations (id, title) for a user, newest first."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT conversation_id, title, created_at
                FROM conversations
                WHERE user_id = ?
                ORDER BY created_at DESC
            """, (user_id,))
            conversations = [dict(row) for row in cursor.fetchall()]
            # log.debug(f"Retrieved {len(conversations)} conversations for user_id {user_id}")
            return conversations
    except sqlite3.Error as e:
        log.error(f"Database error retrieving conversations for user_id {user_id}: {e}", exc_info=True)
        return [] # Return empty list on error, as before

def set_conversation_title(conversation_id, user_id, title):
    """Sets or updates the title of a specific conversation, ensuring user owns it."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE conversations SET title = ? WHERE conversation_id = ? AND user_id = ?",
                           (title, conversation_id, user_id))
            conn.commit()
            if cursor.rowcount > 0:
                log.info(f"Title set for conversation {conversation_id} by user {user_id}")
                return True
            else:
                # This is an expected case if the conversation doesn't exist or isn't owned by the user
                log.warning(f"Failed to set title for conversation {conversation_id}: Not found or not owned by user {user_id}.")
                return False
    except sqlite3.Error as e:
        log.error(f"Database error setting title for conversation {conversation_id}: {e}", exc_info=True)
        return False

def delete_conversation(conversation_id, user_id):
    """Deletes a specific conversation after verifying ownership. Returns status."""
    # Possible return values: True (success), 'not_found', 'permission_denied', False (db_error)
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # 1. Verify ownership
            cursor.execute("SELECT user_id FROM conversations WHERE conversation_id = ?", (conversation_id,))
            conversation = cursor.fetchone()

            if not conversation:
                log.warning(f"Attempt to delete non-existent conversation {conversation_id} by user {user_id}.")
                return 'not_found'
            if conversation['user_id'] != user_id:
                log.warning(f"Permission denied: User {user_id} attempted to delete conversation {conversation_id} owned by user {conversation['user_id']}.")
                return 'permission_denied'

            # 2. Delete conversation (CASCADE should handle messages)
            cursor.execute("DELETE FROM conversations WHERE conversation_id = ?", (conversation_id,))
            conn.commit()

            if cursor.rowcount > 0:
                log.info(f"Conversation {conversation_id} deleted successfully by user {user_id}.")
                return True
            else:
                # Should not happen if ownership check passed, but log just in case
                log.error(f"Conversation {conversation_id} deletion affected 0 rows after ownership check passed for user {user_id}.")
                return False # Indicate unexpected DB state
    except sqlite3.Error as e:
        log.error(f"Database error deleting conversation {conversation_id} for user {user_id}: {e}", exc_info=True)
        return False # Indicate general DB error

# --- Message Management (largely unchanged) ---

def add_message(conversation_id, role, content):
    """Adds a message to a specific conversation."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)",
                           (conversation_id, role, content))
            conn.commit()
            msg_id = cursor.lastrowid
            # log.debug(f"Message added to conversation {conversation_id} with id {msg_id}")
            return msg_id
    except sqlite3.Error as e:
        log.error(f"Database error adding message to conversation {conversation_id}: {e}", exc_info=True)
        return None

def get_conversation_messages(conversation_id, user_id):
    """Retrieves the message history for a specific conversation, ensuring user owns it."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM conversations WHERE conversation_id = ?", (conversation_id,))
            conversation_owner = cursor.fetchone()

            if not conversation_owner:
                 log.warning(f"Attempted to fetch messages for non-existent conversation {conversation_id} by user {user_id}.")
                 return None # Conversation not found
            if conversation_owner['user_id'] != user_id:
                 log.warning(f"Access denied: User {user_id} attempted to fetch messages for conversation {conversation_id} owned by user {conversation_owner['user_id']}.")
                 return None # Permission denied

            cursor.execute("""
                SELECT role, content
                FROM messages
                WHERE conversation_id = ?
                ORDER BY timestamp ASC
            """, (conversation_id,))
            history = [dict(row) for row in cursor.fetchall()]
            # log.debug(f"Retrieved {len(history)} messages for conversation {conversation_id}")
            return history
    except sqlite3.Error as e:
        log.error(f"Database error retrieving messages for conversation {conversation_id}: {e}", exc_info=True)
        return None

# --- Example Usage (Updated) ---
# --- Example Usage (Consider moving to a separate test suite) ---
# if __name__ == '__main__':
#     # Ensure logging is configured if running directly
#     logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
#     log.info("Running db_utils directly for testing...")
#     # It's generally better to initialize the DB separately before running tests
#     # os.system('python init_db.py')
#     log.info("-" * 20)
#
#     log.info("\n--- Testing Database Utilities (Settings Schema) ---")
#     # Test user creation
#     log.info("\nTesting user creation...")
#     user1_id = create_user("testuser1_log", "password123") # Use different username to avoid conflicts if run multiple times
#     user2_id = create_user("testuser2_log", "securepass")
#
#     if not user1_id or not user2_id:
#         log.error("User creation failed, stopping tests.")
#     else:
#         # Test getting details
#         log.info("\nTesting get user details...")
#         details1 = get_user_details(user1_id)
#         log.info(f"User 1 Details: {details1}")
#
#         # Test updates
#         log.info("\nTesting updates...")
#         update_username(user1_id, "testuser1_log_updated")
#         update_username(user1_id, "testuser2_log") # Test unique constraint fail
#         update_password(user1_id, "newpassword456")
#         update_profile_picture(user1_id, "/static/avatars/user1_log.png")
#         update_system_prompt(user1_id, "You are a helpful pirate assistant.")
#         update_user_info(user1_id, '{"role": "Captain", "ship": "The Black Pearl"}') # Test user_info
#
#         details1_updated = get_user_details(user1_id)
#         log.info(f"User 1 Details after update: {details1_updated}")
#
#         # Test authentication with new password
#         log.info("\nTesting authentication with new password...")
#         auth_success = authenticate_user("testuser1_log_updated", "newpassword456")
#         auth_fail = authenticate_user("testuser1_log_updated", "password123")
#         log.info(f"Auth success ID: {auth_success}")
#         log.info(f"Auth fail ID: {auth_fail}")
#
#         # Test conversation creation (still works)
#         conv1_id = create_conversation(user1_id, "Chat with Pirate Prompt")
#         if conv1_id:
#             add_message(conv1_id, "user", "Ahoy!")
#
#         # Test user deletion (will cascade delete conversations/messages)
#         log.info("\nTesting user deletion...")
#         delete_user(user2_id)
#         details2_deleted = get_user_details(user2_id)
#         log.info(f"User 2 Details after delete: {details2_deleted}")
#         convs2_deleted = get_conversations(user2_id)
#         log.info(f"User 2 Conversations after delete: {convs2_deleted}")
#
#         # Clean up the first test user if needed
#         # log.info("\nCleaning up test user 1...")
#         # delete_user(user1_id)
#
#     log.info("\n--- Testing Complete ---")