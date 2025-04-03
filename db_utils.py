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
        conn.row_factory = sqlite3.Row # Return rows as dictionary-like objects
        # Enable foreign key constraints for this connection
        conn.execute("PRAGMA foreign_keys = ON")
        yield conn
    except sqlite3.Error as e:
        print(f"Database connection error: {e}")
        raise
    finally:
        if conn:
            conn.close()

# --- User Management (largely unchanged) ---

def create_user(username, password):
    """Creates a new user in the database."""
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)",
                           (username, hashed_password))
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

# --- Conversation Management ---

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
            # Verify the user owns the conversation before updating
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

# --- Message Management ---

def add_message(conversation_id, role, content):
    """Adds a message to a specific conversation."""
    # Note: We assume conversation_id is valid and belongs to the logged-in user
    # (checked in the Flask route before calling this)
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
            # First, verify the user owns the conversation
            cursor.execute("SELECT user_id FROM conversations WHERE conversation_id = ?", (conversation_id,))
            conversation_owner = cursor.fetchone()

            if not conversation_owner or conversation_owner['user_id'] != user_id:
                 print(f"Error: User {user_id} does not own conversation {conversation_id}.")
                 return None # Return None or empty list to indicate access denied/not found

            # If owner verified, fetch messages
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
        return None # Indicate error

# --- Example Usage (Updated) ---
if __name__ == '__main__':
    # Re-initialize DB if running directly (useful for testing)
    print("Running db_utils directly, ensuring schema is applied...")
    # This requires init_db.py to be runnable and apply schema
    os.system('python init_db.py') # Or call initialize_database() if defined here
    print("-" * 20)


    print("\n--- Testing Database Utilities (New Schema) ---")
    # Test user creation
    print("\nTesting user creation...")
    user1_id = create_user("testuser1", "password123")
    user2_id = create_user("testuser2", "securepass")

    if not user1_id or not user2_id:
        print("User creation failed, stopping tests.")
    else:
        # Test conversation creation
        print("\nTesting conversation creation...")
        conv1_id = create_conversation(user1_id, "First Chat")
        conv2_id = create_conversation(user1_id) # No initial title
        conv3_id = create_conversation(user2_id, "User 2 Chat")

        if not conv1_id or not conv2_id or not conv3_id:
            print("Conversation creation failed, stopping tests.")
        else:
            # Test adding messages
            print("\nTesting message adding...")
            add_message(conv1_id, "user", "Hello in Conv 1")
            add_message(conv1_id, "assistant", "Hi back in Conv 1")
            add_message(conv2_id, "user", "Message for Conv 2")
            add_message(conv3_id, "user", "User 2 says hi")
            add_message(conv3_id, "assistant", "Assistant for User 2")

            # Test retrieving messages
            print("\nTesting message retrieval...")
            messages1 = get_conversation_messages(conv1_id, user1_id)
            print(f"Conv 1 Messages (User 1): {messages1}")
            messages2 = get_conversation_messages(conv2_id, user1_id)
            print(f"Conv 2 Messages (User 1): {messages2}")
            messages3 = get_conversation_messages(conv3_id, user2_id)
            print(f"Conv 3 Messages (User 2): {messages3}")

            # Test retrieving messages for wrong user
            messages_wrong_user = get_conversation_messages(conv1_id, user2_id)
            print(f"Conv 1 Messages (User 2 - should fail): {messages_wrong_user}")


            # Test getting conversation list
            print("\nTesting conversation list retrieval...")
            user1_convs = get_conversations(user1_id)
            print(f"User 1 Conversations: {user1_convs}")
            user2_convs = get_conversations(user2_id)
            print(f"User 2 Conversations: {user2_convs}")

            # Test setting title
            print("\nTesting setting title...")
            set_conversation_title(conv2_id, user1_id, "Second Chat Renamed")
            set_conversation_title(conv1_id, user2_id, "Trying to rename wrong chat") # Should fail
            user1_convs_after_rename = get_conversations(user1_id)
            print(f"User 1 Conversations after rename: {user1_convs_after_rename}")


    print("\n--- Testing Complete ---")