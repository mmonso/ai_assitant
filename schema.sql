-- schema.sql

-- Drop tables in reverse order of dependency
DROP TABLE IF EXISTS messages;
DROP TABLE IF EXISTS conversations;
DROP TABLE IF EXISTS folders; -- Add drop for folders
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

-- Create the folders table
CREATE TABLE folders (
    folder_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE -- Delete folders if user is deleted
);

-- Create the conversations table (unchanged)
CREATE TABLE conversations (
    conversation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    folder_id INTEGER, -- Nullable foreign key to folders
    title TEXT, -- Can be NULL initially, set later
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE, -- Delete conversations if user is deleted
    FOREIGN KEY(folder_id) REFERENCES folders(folder_id) ON DELETE SET NULL -- If folder is deleted, set conversation's folder_id to NULL
);

-- Create the messages table (modified for file references)
CREATE TABLE messages (
    message_id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('user', 'assistant')), -- Keep 'assistant' for DB consistency
    content TEXT NOT NULL, -- Stores the text part of the message
    google_file_name TEXT,    -- Stores the 'name' from Google File API (e.g., 'files/abc-123'), NULL if no file
    file_display_name TEXT,   -- Stores the original uploaded filename (e.g., 'image.png'), NULL if no file
    file_mime_type TEXT,      -- Stores the MIME type (e.g., 'image/png'), NULL if no file
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(conversation_id) REFERENCES conversations(conversation_id) ON DELETE CASCADE -- Delete messages if conversation is deleted
);

-- Optional: Add indexes for performance
CREATE INDEX IF NOT EXISTS idx_folders_user_id ON folders (user_id); -- Index for folders
CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations (user_id);
CREATE INDEX IF NOT EXISTS idx_conversations_folder_id ON conversations (folder_id); -- Index for conversation folders
CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages (conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages (timestamp);