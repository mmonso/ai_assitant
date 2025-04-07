import os
import secrets # Still needed if default secret key generation is desired fallback
from flask import Flask
import google.generativeai as genai
from dotenv import load_dotenv
import logging

# Basic Logging Configuration
# TODO: Consider more advanced configuration (e.g., file handler, rotation) for production
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__) # Get logger for this module

# Import configurations from config.py
import config

# Load environment variables from .env file (can be done in config.py too)
load_dotenv()

# Configure Gemini API Key (Needs to happen before model is used in blueprints)
try:
    # Optionally get key from config: genai.configure(api_key=config.GEMINI_API_KEY)
    # Or keep loading directly from env here:
    gemini_api_key = os.environ["GEMINI_API_KEY"]
    genai.configure(api_key=gemini_api_key)
    log.info("Gemini API Key configured successfully.")
except KeyError:
    log.critical("CRITICAL ERROR: GEMINI_API_KEY environment variable not set.")
    # Depending on deployment, might exit or just log error
    # exit(1) # Uncomment if startup should fail without key

# --- Removed Global Configuration Constants (Moved to config.py) ---

# --- Flask App Initialization ---
app = Flask(__name__)
# Use the secret key from the config file
app.secret_key = config.SECRET_KEY

# --- Import and Register Blueprints ---
# Import blueprint objects AFTER app is created
# Note: Blueprints will now import config constants from 'config' module
from routes.auth import auth_bp
from routes.main import main_bp
from routes.chat_api import chat_api_bp
from routes.settings_api import settings_api_bp

app.register_blueprint(auth_bp)
app.register_blueprint(main_bp)
app.register_blueprint(chat_api_bp) # Prefix is defined in the blueprint file
app.register_blueprint(settings_api_bp) # Prefix is defined in the blueprint file

# --- Main Execution ---
if __name__ == '__main__':
    # Ensure db is initialized before running
    # Consider adding a check or command here if needed:
    # from init_db import init_db_command
    # init_db_command() # Or run manually before starting
    log.info("Starting Flask app...")
    # Use debug=False for production logging, True enables Flask's reloader which can interfere
    # with some logging setups if not handled carefully. For development, debug=True is fine.
    app.run(host='0.0.0.0', port=5000, debug=True)