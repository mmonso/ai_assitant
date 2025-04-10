import re
import os
from dotenv import load_dotenv

load_dotenv() # Load .env file to make environment variables available if needed

# --- Configuration Constants ---

# User Config
USERNAME_MIN_LENGTH = 3
USERNAME_MAX_LENGTH = 20
USERNAME_REGEX = re.compile(r"^[a-zA-Z0-9_]+$") # Alphanumeric and underscore
PASSWORD_MIN_LENGTH = 8

# Flask Config
SECRET_KEY = os.environ.get('FLASK_SECRET_KEY', 'a_default_secret_key_for_development_only') # Provide a default

# Gemini Config (Optional: Keep here or load directly in app.py)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") # Keep API key loading here for clarity
GEMINI_MODEL_NAME = os.environ.get("GEMINI_MODEL_NAME", "gemini-1.5-flash")

# Database Config
DATABASE_NAME = os.environ.get('DATABASE_NAME', 'chat_history.db')

# Upload Config
UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'uploads')
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'webp', 'wav', 'mp3', 'aiff', 'aac', 'ogg', 'flac'} # Added audio formats

# Add other configurations as needed