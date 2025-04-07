-- schema.sql

-- Drop tables in reverse order of dependency
DROP TABLE IF EXISTS messages;
DROP TABLE IF EXISTS conversations;
DROP TABLE IF EXISTS users;

-- Create the users table (modified)
CREATE TABLE users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    profile_picture_url TEXT, -- URL to the profile picture (nullable)
    system_prompt TEXT,       -- Custom system prompt for the user (nullable)
    user_info TEXT,           -- JSON object containing user-specific info (nullable)
    font_family TEXT,         -- User's preferred font family (nullable)
    font_size TEXT,           -- User's preferred font size (e.g., '14px', '1rem') (nullable)
    line_spacing TEXT,        -- User's preferred line spacing (e.g., '1.5') (nullable)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create the conversations table (unchanged)
CREATE TABLE conversations (
    conversation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    title TEXT, -- Can be NULL initially, set later
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE -- Delete conversations if user is deleted
);

-- Create the messages table (unchanged)
CREATE TABLE messages (
    message_id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('user', 'assistant')), -- Keep 'assistant' for DB consistency
    content TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(conversation_id) REFERENCES conversations(conversation_id) ON DELETE CASCADE -- Delete messages if conversation is deleted
);

-- Optional: Add indexes for performance
CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations (user_id);
CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages (conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages (timestamp);