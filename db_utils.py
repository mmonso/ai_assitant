import sqlite3
import bcrypt
import os
import logging # Add logging import
import config # Import config module
from contextlib import contextmanager

log = logging.getLogger(__name__) # Get logger for this module

# Custom Exceptions
class DatabaseError(Exception):
    """Base class for database-related errors."""
    pass

class UserNotFoundError(DatabaseError):
    """Raised when a user is not found."""
    pass

class DuplicateUserError(DatabaseError):
    """Raised when trying to create a user that already exists."""
    pass

class ConversationNotFoundError(DatabaseError):
    """Raised when a conversation is not found."""
    pass

class PermissionDeniedError(DatabaseError):
    """Raised when a user tries to access a resource they don't own."""
    pass

class FolderNotFoundError(DatabaseError):
    """Raised when a folder is not found."""
    pass

class DuplicateFolderError(DatabaseError):
    """Raised when trying to create a folder with a name that already exists for the user."""
    pass

class DatabaseOperationalError(DatabaseError):
    """Raised for general operational errors like connection issues, etc."""
    pass


# DATABASE_NAME = 'chat_history.db' # Moved to config.py
@contextmanager
def get_db_connection():
    """Provides a database connection context."""
    conn = None
    try:
        conn = sqlite3.connect(config.DATABASE_NAME) # Use config value
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
        raise DuplicateUserError(f"Username '{username}' already exists.")
    except sqlite3.OperationalError as e: # More specific error
        log.error(f"Database operational error during user creation for username '{username}': {e}", exc_info=True)
        raise DatabaseOperationalError(f"Operational error creating user '{username}'.") from e
    except sqlite3.Error as e: # Catch other potential SQLite errors
        log.error(f"Unexpected SQLite error during user creation for username '{username}': {e}", exc_info=True)
        raise DatabaseError(f"Unexpected database error creating user '{username}'.") from e

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
    except sqlite3.OperationalError as e: # More specific error
        log.error(f"Database operational error during authentication for user '{username}': {e}", exc_info=True)
        raise DatabaseOperationalError(f"Operational error authenticating user '{username}'.") from e
    except sqlite3.Error as e: # Catch other potential SQLite errors
        log.error(f"Unexpected SQLite error during authentication for user '{username}': {e}", exc_info=True)
        raise DatabaseError(f"Unexpected database error authenticating user '{username}'.") from e

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
    except sqlite3.OperationalError as e: # More specific error
        log.error(f"Database operational error retrieving user details for user_id {user_id}: {e}", exc_info=True)
        raise DatabaseOperationalError(f"Operational error retrieving details for user {user_id}.") from e
    except sqlite3.Error as e: # Catch other potential SQLite errors
        log.error(f"Unexpected SQLite error retrieving user details for user_id {user_id}: {e}", exc_info=True)
        raise DatabaseError(f"Unexpected database error retrieving details for user {user_id}.") from e

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
        raise DuplicateUserError(f"Username '{new_username}' is already taken.")
    except sqlite3.OperationalError as e: # More specific error
        log.error(f"Database operational error updating username for user_id {user_id} to '{new_username}': {e}", exc_info=True)
        raise DatabaseOperationalError(f"Operational error updating username for user {user_id}.") from e
    except sqlite3.Error as e: # Catch other potential SQLite errors
        log.error(f"Unexpected SQLite error updating username for user_id {user_id} to '{new_username}': {e}", exc_info=True)
        raise DatabaseError(f"Unexpected database error updating username for user {user_id}.") from e

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
    except sqlite3.OperationalError as e: # More specific error
        log.error(f"Database operational error updating password for user_id {user_id}: {e}", exc_info=True)
        raise DatabaseOperationalError(f"Operational error updating password for user {user_id}.") from e
    except sqlite3.Error as e: # Catch other potential SQLite errors
        log.error(f"Unexpected SQLite error updating password for user_id {user_id}: {e}", exc_info=True)
        raise DatabaseError(f"Unexpected database error updating password for user {user_id}.") from e

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
    except sqlite3.OperationalError as e: # More specific error
        log.error(f"Database operational error updating profile picture URL for user_id {user_id}: {e}", exc_info=True)
        raise DatabaseOperationalError(f"Operational error updating profile picture for user {user_id}.") from e
    except sqlite3.Error as e: # Catch other potential SQLite errors
        log.error(f"Unexpected SQLite error updating profile picture URL for user_id {user_id}: {e}", exc_info=True)
        raise DatabaseError(f"Unexpected database error updating profile picture for user {user_id}.") from e

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
    except sqlite3.OperationalError as e: # More specific error
        log.error(f"Database operational error updating system prompt for user_id {user_id}: {e}", exc_info=True)
        raise DatabaseOperationalError(f"Operational error updating system prompt for user {user_id}.") from e
    except sqlite3.Error as e: # Catch other potential SQLite errors
        log.error(f"Unexpected SQLite error updating system prompt for user_id {user_id}: {e}", exc_info=True)
        raise DatabaseError(f"Unexpected database error updating system prompt for user {user_id}.") from e
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
    except sqlite3.OperationalError as e: # More specific error
        log.error(f"Database operational error updating user info for user_id {user_id}: {e}", exc_info=True)
        raise DatabaseOperationalError(f"Operational error updating user info for user {user_id}.") from e
    except sqlite3.Error as e: # Catch other potential SQLite errors
        log.error(f"Unexpected SQLite error updating user info for user_id {user_id}: {e}", exc_info=True)
        raise DatabaseError(f"Unexpected database error updating user info for user {user_id}.") from e


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
    except sqlite3.OperationalError as e: # More specific error
        log.error(f"Database operational error updating theme settings for user_id {user_id}: {e}", exc_info=True)
        raise DatabaseOperationalError(f"Operational error updating theme for user {user_id}.") from e
    except sqlite3.Error as e: # Catch other potential SQLite errors
        log.error(f"Unexpected SQLite error updating theme settings for user_id {user_id}: {e}", exc_info=True)
        raise DatabaseError(f"Unexpected database error updating theme for user {user_id}.") from e
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
    except sqlite3.OperationalError as e: # More specific error
        log.error(f"Database operational error deleting user {user_id}: {e}", exc_info=True)
        raise DatabaseOperationalError(f"Operational error deleting user {user_id}.") from e
    except sqlite3.Error as e: # Catch other potential SQLite errors
        log.error(f"Unexpected SQLite error deleting user {user_id}: {e}", exc_info=True)
        raise DatabaseError(f"Unexpected database error deleting user {user_id}.") from e
    
    
# --- Folder Management ---

def create_folder(user_id, name):
    """Creates a new folder for a user."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # Check if folder with the same name already exists for this user
            cursor.execute("SELECT folder_id FROM folders WHERE user_id = ? AND name = ?", (user_id, name))
            if cursor.fetchone():
                log.warning(f"Attempted to create duplicate folder name '{name}' for user_id {user_id}.")
                raise DuplicateFolderError(f"Folder with name '{name}' already exists.")

            cursor.execute("INSERT INTO folders (user_id, name) VALUES (?, ?)", (user_id, name))
            conn.commit()
            folder_id = cursor.lastrowid
            log.info(f"Folder '{name}' created successfully with folder_id: {folder_id} for user_id: {user_id}.")
            return folder_id
    except sqlite3.OperationalError as e:
        log.error(f"Database operational error creating folder '{name}' for user_id {user_id}: {e}", exc_info=True)
        raise DatabaseOperationalError(f"Operational error creating folder '{name}' for user {user_id}.") from e
    except sqlite3.Error as e:
        log.error(f"Unexpected SQLite error creating folder '{name}' for user_id {user_id}: {e}", exc_info=True)
        raise DatabaseError(f"Unexpected database error creating folder '{name}' for user {user_id}.") from e

def get_folders(user_id):
    """Retrieves a list of folders (id, name) for a user."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT folder_id, name, created_at
                FROM folders
                WHERE user_id = ?
                ORDER BY name ASC
            """, (user_id,))
            folders = [dict(row) for row in cursor.fetchall()]
            # log.debug(f"Retrieved {len(folders)} folders for user_id {user_id}")
            return folders
    except sqlite3.OperationalError as e:
        log.error(f"Database operational error retrieving folders for user_id {user_id}: {e}", exc_info=True)
        raise DatabaseOperationalError(f"Operational error retrieving folders for user {user_id}.") from e
    except sqlite3.Error as e:
        log.error(f"Unexpected SQLite error retrieving folders for user_id {user_id}: {e}", exc_info=True)
        raise DatabaseError(f"Unexpected database error retrieving folders for user {user_id}.") from e

def update_folder_name(folder_id, user_id, new_name):
    """Updates the name of a specific folder, ensuring user owns it and name is unique for the user."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # 1. Verify ownership
            cursor.execute("SELECT user_id FROM folders WHERE folder_id = ?", (folder_id,))
            folder = cursor.fetchone()
            if not folder:
                log.warning(f"Attempt to update non-existent folder {folder_id} by user {user_id}.")
                raise FolderNotFoundError(f"Folder {folder_id} not found.")
            if folder['user_id'] != user_id:
                log.warning(f"Permission denied: User {user_id} attempted to update folder {folder_id} owned by user {folder['user_id']}.")
                raise PermissionDeniedError(f"User {user_id} does not own folder {folder_id}.")

            # 2. Check if new name already exists for this user (excluding the current folder)
            cursor.execute("SELECT folder_id FROM folders WHERE user_id = ? AND name = ? AND folder_id != ?", (user_id, new_name, folder_id))
            if cursor.fetchone():
                log.warning(f"Attempted to rename folder {folder_id} to duplicate name '{new_name}' for user_id {user_id}.")
                raise DuplicateFolderError(f"Folder with name '{new_name}' already exists.")

            # 3. Update the name
            cursor.execute("UPDATE folders SET name = ? WHERE folder_id = ?", (new_name, folder_id))
            conn.commit()

            if cursor.rowcount > 0:
                log.info(f"Folder {folder_id} renamed to '{new_name}' by user {user_id}")
                return True
            else:
                # Should not happen if ownership check passed, but log if it does
                log.error(f"Folder {folder_id} rename affected 0 rows after ownership check passed for user {user_id}.")
                # Re-raise FolderNotFoundError as the most likely cause if it got deleted concurrently
                raise FolderNotFoundError(f"Folder {folder_id} not found during update.")
    except sqlite3.OperationalError as e:
        log.error(f"Database operational error renaming folder {folder_id} for user {user_id}: {e}", exc_info=True)
        raise DatabaseOperationalError(f"Operational error renaming folder {folder_id}.") from e
    except sqlite3.Error as e:
        log.error(f"Unexpected SQLite error renaming folder {folder_id} for user {user_id}: {e}", exc_info=True)
        raise DatabaseError(f"Unexpected database error renaming folder {folder_id}.") from e


def delete_folder(folder_id, user_id):
    """Deletes a specific folder after verifying ownership. Conversations in the folder will have folder_id set to NULL."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # 1. Verify ownership
            cursor.execute("SELECT user_id FROM folders WHERE folder_id = ?", (folder_id,))
            folder = cursor.fetchone()
            if not folder:
                log.warning(f"Attempt to delete non-existent folder {folder_id} by user {user_id}.")
                raise FolderNotFoundError(f"Folder {folder_id} not found.")
            if folder['user_id'] != user_id:
                log.warning(f"Permission denied: User {user_id} attempted to delete folder {folder_id} owned by user {folder['user_id']}.")
                raise PermissionDeniedError(f"User {user_id} does not own folder {folder_id}.")

            # 2. Delete the folder (ON DELETE SET NULL handles conversations)
            cursor.execute("DELETE FROM folders WHERE folder_id = ?", (folder_id,))
            conn.commit()

            if cursor.rowcount > 0:
                log.info(f"Folder {folder_id} deleted successfully by user {user_id}.")
                # No return value needed on success
            else:
                # Should not happen if ownership check passed
                log.error(f"Folder {folder_id} deletion affected 0 rows after ownership check passed for user {user_id}.")
                raise DatabaseOperationalError(f"Failed to delete folder {folder_id} despite ownership check.")
    except sqlite3.OperationalError as e:
        log.error(f"Database operational error deleting folder {folder_id} for user {user_id}: {e}", exc_info=True)
        raise DatabaseOperationalError(f"Operational error deleting folder {folder_id}.") from e
    except sqlite3.Error as e:
        log.error(f"Unexpected SQLite error deleting folder {folder_id} for user {user_id}: {e}", exc_info=True)
        raise DatabaseError(f"Unexpected database error deleting folder {folder_id}.") from e
    
    
    # --- Conversation Management (Updated) ---

def create_conversation(user_id, title=None, folder_id=None):
    """Creates a new conversation for a user, optionally assigning it to a folder."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # Optional: Verify folder_id belongs to the user if provided
            if folder_id is not None:
                cursor.execute("SELECT folder_id FROM folders WHERE folder_id = ? AND user_id = ?", (folder_id, user_id))
                if not cursor.fetchone():
                    log.warning(f"User {user_id} attempted to create conversation in invalid or unowned folder {folder_id}.")
                    # Decide how to handle: raise error or silently ignore folder_id? Let's ignore for now.
                    folder_id = None # Set to None if invalid

            cursor.execute("INSERT INTO conversations (user_id, title, folder_id) VALUES (?, ?, ?)",
                           (user_id, title, folder_id))
            conn.commit()
            new_conversation_id = cursor.lastrowid
            log.info(f"Conversation created with ID: {new_conversation_id} for user_id: {user_id} (folder_id: {folder_id})")
            return new_conversation_id
    except sqlite3.OperationalError as e:
        log.error(f"Database operational error creating conversation for user_id {user_id}: {e}", exc_info=True)
        raise DatabaseOperationalError(f"Operational error creating conversation for user {user_id}.") from e
    except sqlite3.Error as e:
        log.error(f"Unexpected SQLite error creating conversation for user_id {user_id}: {e}", exc_info=True)
        raise DatabaseError(f"Unexpected database error creating conversation for user {user_id}.") from e

def get_conversations(user_id):
    """Retrieves a list of conversations (id, title, folder_id, created_at) for a user, newest first."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT conversation_id, title, folder_id, created_at
                FROM conversations
                WHERE user_id = ?
                ORDER BY created_at DESC
            """, (user_id,))
            conversations = [dict(row) for row in cursor.fetchall()]
            # log.debug(f"Retrieved {len(conversations)} conversations for user_id {user_id}")
            return conversations
    except sqlite3.OperationalError as e:
        log.error(f"Database operational error retrieving conversations for user_id {user_id}: {e}", exc_info=True)
        raise DatabaseOperationalError(f"Operational error retrieving conversations for user {user_id}.") from e
    except sqlite3.Error as e:
        log.error(f"Unexpected SQLite error retrieving conversations for user_id {user_id}: {e}", exc_info=True)
        raise DatabaseError(f"Unexpected database error retrieving conversations for user {user_id}.") from e

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
    except sqlite3.OperationalError as e:
        log.error(f"Database operational error setting title for conversation {conversation_id}: {e}", exc_info=True)
        raise DatabaseOperationalError(f"Operational error setting title for conversation {conversation_id}.") from e
    except sqlite3.Error as e:
        log.error(f"Unexpected SQLite error setting title for conversation {conversation_id}: {e}", exc_info=True)
        raise DatabaseError(f"Unexpected database error setting title for conversation {conversation_id}.") from e

def delete_conversation(conversation_id, user_id):
    """Deletes a specific conversation after verifying ownership. Raises exceptions on failure."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # 1. Verify ownership
            cursor.execute("SELECT user_id FROM conversations WHERE conversation_id = ?", (conversation_id,))
            conversation = cursor.fetchone()

            if not conversation:
                log.warning(f"Attempt to delete non-existent conversation {conversation_id} by user {user_id}.")
                raise ConversationNotFoundError(f"Conversation {conversation_id} not found.")
            if conversation['user_id'] != user_id:
                log.warning(f"Permission denied: User {user_id} attempted to delete conversation {conversation_id} owned by user {conversation['user_id']}.")
                raise PermissionDeniedError(f"User {user_id} does not own conversation {conversation_id}.")

            # 2. Delete conversation (CASCADE should handle messages)
            cursor.execute("DELETE FROM conversations WHERE conversation_id = ?", (conversation_id,))
            conn.commit()

            if cursor.rowcount > 0:
                log.info(f"Conversation {conversation_id} deleted successfully by user {user_id}.")
                # No return value needed on success, lack of exception implies success
            else:
                # Should not happen if ownership check passed, but raise an error if it does
                log.error(f"Conversation {conversation_id} deletion affected 0 rows after ownership check passed for user {user_id}.")
                raise DatabaseOperationalError(f"Failed to delete conversation {conversation_id} despite ownership check.")
    except sqlite3.OperationalError as e:
        log.error(f"Database operational error deleting conversation {conversation_id} for user {user_id}: {e}", exc_info=True)
        raise DatabaseOperationalError(f"Operational error deleting conversation {conversation_id}.") from e
    except sqlite3.Error as e:
        log.error(f"Unexpected SQLite error deleting conversation {conversation_id} for user {user_id}: {e}", exc_info=True)
        raise DatabaseError(f"Unexpected database error deleting conversation {conversation_id}.") from e
def move_conversation_to_folder(conversation_id, user_id, folder_id):
    """Moves a conversation to a different folder (or removes it from a folder if folder_id is None)."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # 1. Verify conversation ownership
            cursor.execute("SELECT user_id FROM conversations WHERE conversation_id = ?", (conversation_id,))
            conversation = cursor.fetchone()
            if not conversation:
                log.warning(f"Attempt to move non-existent conversation {conversation_id} by user {user_id}.")
                raise ConversationNotFoundError(f"Conversation {conversation_id} not found.")
            if conversation['user_id'] != user_id:
                log.warning(f"Permission denied: User {user_id} attempted to move conversation {conversation_id} owned by user {conversation['user_id']}.")
                raise PermissionDeniedError(f"User {user_id} does not own conversation {conversation_id}.")

            # 2. Verify folder ownership (if moving *to* a folder)
            if folder_id is not None:
                cursor.execute("SELECT user_id FROM folders WHERE folder_id = ?", (folder_id,))
                folder = cursor.fetchone()
                if not folder:
                    log.warning(f"Attempt to move conversation {conversation_id} to non-existent folder {folder_id} by user {user_id}.")
                    raise FolderNotFoundError(f"Folder {folder_id} not found.")
                if folder['user_id'] != user_id:
                    log.warning(f"Permission denied: User {user_id} attempted to move conversation {conversation_id} to folder {folder_id} owned by user {folder['user_id']}.")
                    raise PermissionDeniedError(f"User {user_id} does not own folder {folder_id}.")

            # 3. Update the conversation's folder_id
            cursor.execute("UPDATE conversations SET folder_id = ? WHERE conversation_id = ?", (folder_id, conversation_id))
            conn.commit()

            if cursor.rowcount > 0:
                log.info(f"Conversation {conversation_id} moved to folder {folder_id} by user {user_id}")
                return True
            else:
                # Should not happen if ownership checks passed
                log.error(f"Conversation {conversation_id} move to folder {folder_id} affected 0 rows after ownership checks passed for user {user_id}.")
                raise DatabaseOperationalError(f"Failed to move conversation {conversation_id} despite ownership checks.")

    except sqlite3.OperationalError as e:
        log.error(f"Database operational error moving conversation {conversation_id} for user {user_id}: {e}", exc_info=True)
        raise DatabaseOperationalError(f"Operational error moving conversation {conversation_id}.") from e
    except sqlite3.Error as e:
        log.error(f"Unexpected SQLite error moving conversation {conversation_id} for user {user_id}: {e}", exc_info=True)
        raise DatabaseError(f"Unexpected database error moving conversation {conversation_id}.") from e


# --- Message Management (largely unchanged) ---
# --- Message Management (largely unchanged) ---

def add_message(conversation_id, role, content, google_file_name=None, file_display_name=None, file_mime_type=None):
    """Adds a message to a specific conversation, optionally including file references."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO messages (conversation_id, role, content, google_file_name, file_display_name, file_mime_type)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (conversation_id, role, content, google_file_name, file_display_name, file_mime_type))
            conn.commit()
            msg_id = cursor.lastrowid
            # log.debug(f"Message added to conversation {conversation_id} with id {msg_id}, file: {google_file_name}")
            return msg_id
    except sqlite3.IntegrityError as e:
        log.error(f"Database integrity error adding message to conversation {conversation_id}: {e}", exc_info=True)
        # Reraise as a more specific operational error, as the conversation likely doesn't exist
        raise DatabaseOperationalError(f"Integrity error adding message to conversation {conversation_id} (likely conversation not found).") from e
    except sqlite3.OperationalError as e:
        log.error(f"Database operational error adding message to conversation {conversation_id}: {e}", exc_info=True)
        raise DatabaseOperationalError(f"Operational error adding message to conversation {conversation_id}.") from e
    except sqlite3.Error as e:
        log.error(f"Unexpected SQLite error adding message to conversation {conversation_id}: {e}", exc_info=True)
        raise DatabaseError(f"Unexpected database error adding message to conversation {conversation_id}.") from e

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
                SELECT role, content, google_file_name, file_display_name, file_mime_type
                FROM messages
                WHERE conversation_id = ?
                ORDER BY timestamp ASC
            """, (conversation_id,))
            # Convert rows to dictionaries to include all fetched columns
            history = [dict(row) for row in cursor.fetchall()]
            # log.debug(f"Retrieved {len(history)} messages for conversation {conversation_id}")
            return history
    except sqlite3.OperationalError as e:
        log.error(f"Database operational error retrieving messages for conversation {conversation_id}: {e}", exc_info=True)
        raise DatabaseOperationalError(f"Operational error retrieving messages for conversation {conversation_id}.") from e
    except sqlite3.Error as e:
        log.error(f"Unexpected SQLite error retrieving messages for conversation {conversation_id}: {e}", exc_info=True)
        raise DatabaseError(f"Unexpected database error retrieving messages for conversation {conversation_id}.") from e

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