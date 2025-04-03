import sqlite3
import bcrypt
import os
from contextlib import contextmanager

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
        print(f"Database connection error: {e}")
        raise
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
                INSERT INTO users (username, password_hash, profile_picture_url, system_prompt)
                VALUES (?, ?, NULL, NULL)
            """, (username, hashed_password))
            conn.commit()
            print(f"User '{username}' created successfully.")
            return cursor.lastrowid
    except sqlite3.IntegrityError:
        print(f"Error: Username '{username}' already exists.")
        return None
    except sqlite3.Error as e:
        print(f"Database error during user creation: {e}")
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
                print(f"User '{username}' authenticated successfully.")
                return user_data['user_id']
            else:
                print(f"Authentication failed for user '{username}'.")
                return None
    except sqlite3.Error as e:
        print(f"Database error during authentication: {e}")
        return None

def get_user_details(user_id):
    """Retrieves user details including settings."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT user_id, username, profile_picture_url, system_prompt
                FROM users
                WHERE user_id = ?
            """, (user_id,))
            user_details = cursor.fetchone()
            return dict(user_details) if user_details else None
    except sqlite3.Error as e:
        print(f"Database error retrieving user details for user_id {user_id}: {e}")
        return None

def update_username(user_id, new_username):
    """Updates the username for a user, checking for uniqueness."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET username = ? WHERE user_id = ?", (new_username, user_id))
            conn.commit()
            print(f"Username updated for user_id {user_id}")
            return True
    except sqlite3.IntegrityError:
        print(f"Error: New username '{new_username}' is already taken.")
        return False # Indicate username conflict
    except sqlite3.Error as e:
        print(f"Database error updating username for user_id {user_id}: {e}")
        return False # Indicate general error

def update_password(user_id, new_password):
    """Updates the password for a user."""
    new_hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET password_hash = ? WHERE user_id = ?", (new_hashed_password, user_id))
            conn.commit()
            print(f"Password updated for user_id {user_id}")
            return True
    except sqlite3.Error as e:
        print(f"Database error updating password for user_id {user_id}: {e}")
        return False

def update_profile_picture(user_id, picture_url):
    """Updates the profile picture URL for a user."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET profile_picture_url = ? WHERE user_id = ?", (picture_url, user_id))
            conn.commit()
            print(f"Profile picture URL updated for user_id {user_id}")
            return True
    except sqlite3.Error as e:
        print(f"Database error updating profile picture URL for user_id {user_id}: {e}")
        return False

def update_system_prompt(user_id, prompt):
    """Updates the custom system prompt for a user."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET system_prompt = ? WHERE user_id = ?", (prompt, user_id))
            conn.commit()
            print(f"System prompt updated for user_id {user_id}")
            return True
    except sqlite3.Error as e:
        print(f"Database error updating system prompt for user_id {user_id}: {e}")
        return False

def delete_user(user_id):
    """Deletes a user and all associated data (conversations, messages) via CASCADE."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # Foreign key constraints with ON DELETE CASCADE handle conversations/messages
            cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
            conn.commit()
            print(f"User {user_id} and associated data deleted successfully.")
            return True
    except sqlite3.Error as e:
        print(f"Database error deleting user {user_id}: {e}")
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
            print(f"Conversation created with ID: {new_conversation_id} for user_id: {user_id}")
            return new_conversation_id
    except sqlite3.Error as e:
        print(f"Database error creating conversation: {e}")
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
            return conversations
    except sqlite3.Error as e:
        print(f"Database error retrieving conversations: {e}")
        return []

def set_conversation_title(conversation_id, user_id, title):
    """Sets or updates the title of a specific conversation, ensuring user owns it."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE conversations SET title = ? WHERE conversation_id = ? AND user_id = ?",
                           (title, conversation_id, user_id))
            conn.commit()
            if cursor.rowcount > 0:
                print(f"Title set for conversation {conversation_id}")
                return True
            else:
                print(f"Error: Conversation {conversation_id} not found or not owned by user {user_id}.")
                return False
    except sqlite3.Error as e:
        print(f"Database error setting conversation title: {e}")
        return False

# --- Message Management (largely unchanged) ---

def add_message(conversation_id, role, content):
    """Adds a message to a specific conversation."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)",
                           (conversation_id, role, content))
            conn.commit()
            return cursor.lastrowid
    except sqlite3.Error as e:
        print(f"Database error adding message to conversation {conversation_id}: {e}")
        return None

def get_conversation_messages(conversation_id, user_id):
    """Retrieves the message history for a specific conversation, ensuring user owns it."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM conversations WHERE conversation_id = ?", (conversation_id,))
            conversation_owner = cursor.fetchone()

            if not conversation_owner or conversation_owner['user_id'] != user_id:
                 print(f"Error: User {user_id} does not own conversation {conversation_id}.")
                 return None

            cursor.execute("""
                SELECT role, content
                FROM messages
                WHERE conversation_id = ?
                ORDER BY timestamp ASC
            """, (conversation_id,))
            history = [dict(row) for row in cursor.fetchall()]
            return history
    except sqlite3.Error as e:
        print(f"Database error retrieving messages for conversation {conversation_id}: {e}")
        return None

# --- Example Usage (Updated) ---
# (Consider removing or commenting out the example usage for production)
if __name__ == '__main__':
    print("Running db_utils directly, ensuring schema is applied...")
    os.system('python init_db.py')
    print("-" * 20)

    print("\n--- Testing Database Utilities (Settings Schema) ---")
    # Test user creation
    print("\nTesting user creation...")
    user1_id = create_user("testuser1", "password123")
    user2_id = create_user("testuser2", "securepass")

    if not user1_id or not user2_id:
        print("User creation failed, stopping tests.")
    else:
        # Test getting details
        print("\nTesting get user details...")
        details1 = get_user_details(user1_id)
        print(f"User 1 Details: {details1}")

        # Test updates
        print("\nTesting updates...")
        update_username(user1_id, "testuser1_updated")
        update_username(user1_id, "testuser2") # Test unique constraint fail
        update_password(user1_id, "newpassword456")
        update_profile_picture(user1_id, "/static/avatars/user1.png")
        update_system_prompt(user1_id, "You are a helpful pirate assistant.")

        details1_updated = get_user_details(user1_id)
        print(f"User 1 Details after update: {details1_updated}")

        # Test authentication with new password
        print("\nTesting authentication with new password...")
        auth_success = authenticate_user("testuser1_updated", "newpassword456")
        auth_fail = authenticate_user("testuser1_updated", "password123")
        print(f"Auth success ID: {auth_success}")
        print(f"Auth fail ID: {auth_fail}")

        # Test conversation creation (still works)
        conv1_id = create_conversation(user1_id, "Chat with Pirate Prompt")
        add_message(conv1_id, "user", "Ahoy!")

        # Test user deletion (will cascade delete conversations/messages)
        print("\nTesting user deletion...")
        delete_user(user2_id)
        details2_deleted = get_user_details(user2_id)
        print(f"User 2 Details after delete: {details2_deleted}")
        convs2_deleted = get_conversations(user2_id)
        print(f"User 2 Conversations after delete: {convs2_deleted}")


    print("\n--- Testing Complete ---")