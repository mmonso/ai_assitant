import os
import secrets # For generating secret key
from flask import Flask, request, jsonify, render_template, session, redirect, url_for, flash
import google.generativeai as genai
from dotenv import load_dotenv
import db_utils # Import our database utility functions
import re # For username validation
import bcrypt # Needed for password check
# Load environment variables from .env file
load_dotenv()

# Configure Gemini API Key
try:
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
except KeyError:
    print("Error: GEMINI_API_KEY environment variable not set.")
    exit(1)

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', secrets.token_hex(16))

# Configuration (Consider moving to a config file)
USERNAME_MIN_LENGTH = 3
USERNAME_MAX_LENGTH = 20
USERNAME_REGEX = re.compile(r"^[a-zA-Z0-9_]+$") # Alphanumeric and underscore
PASSWORD_MIN_LENGTH = 8
# Profile picture upload settings (if implementing local storage)
# UPLOAD_FOLDER = 'static/avatars'
# ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
# app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Remove duplicate configuration block

# --- Helper Function ---
def generate_title_from_message(message):
    """Generates a short title from the first user message."""
    # Simple approach: take the first few words
    words = message.split()
    title = " ".join(words[:5])
    if len(words) > 5:
        title += "..."
    return title

# --- Routes ---

@app.route('/')
def index():
    """Serves the main chat page, requires login."""
    if 'user_id' not in session:
        flash("Please log in to access the chat.", "info")
        return redirect(url_for('login'))

    user_id = session['user_id']
    user_details = db_utils.get_user_details(user_id)
    if not user_details:
        # Handle case where user details might be missing (shouldn't happen if logged in)
        flash("Error retrieving user details. Please log in again.", "error")
        session.clear() # Clear potentially corrupted session
        return redirect(url_for('login'))

    # Pass configuration constants needed by index.html (including the modal)
    config = {
        'USERNAME_MIN_LENGTH': USERNAME_MIN_LENGTH,
        'USERNAME_MAX_LENGTH': USERNAME_MAX_LENGTH,
        'PASSWORD_MIN_LENGTH': PASSWORD_MIN_LENGTH,
        # Add other config values if needed by the modal in index.html
    }

    # Pass user and config to the main index template
    return render_template('index.html', user=user_details, config=config)

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Handles user registration."""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if not username or not password:
            flash("Username and password are required.", "error")
            return render_template('register.html')
        user_id = db_utils.create_user(username, password)
        if user_id:
            flash("Registration successful! Please log in.", "success")
            return redirect(url_for('login'))
        else:
            flash("Registration failed. Username might already exist.", "error")
            return render_template('register.html')
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handles user login."""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if not username or not password:
            flash("Username and password are required.", "error")
            return render_template('login.html')
        user_id = db_utils.authenticate_user(username, password)
        if user_id:
            session['user_id'] = user_id
            session['username'] = username
            session.pop('current_conversation_id', None) # Clear active chat on login
            flash(f"Welcome back, {username}!", "success")
            return redirect(url_for('index'))
        else:
            flash("Invalid username or password.", "error")
            return render_template('login.html')
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Logs the user out."""
    session.pop('user_id', None)
    session.pop('username', None)
    session.pop('current_conversation_id', None) # Clear active chat on logout
    flash("You have been logged out.", "info")
    return redirect(url_for('login'))

# Removed /settings GET route, modal is now part of index.html


# --- API Route to Fetch Settings Data ---

@app.route('/api/get_user_settings', methods=['GET'])
def get_user_settings():
    """API endpoint to fetch current user settings for the modal."""
    if 'user_id' not in session:
        return jsonify({"error": "Authentication required"}), 401

    user_id = session['user_id']
    user_details = db_utils.get_user_details(user_id)

    if not user_details:
        return jsonify({"error": "Failed to retrieve user details"}), 500

    # Prepare config data to send to frontend
    config_data = {
        'USERNAME_MIN_LENGTH': USERNAME_MIN_LENGTH,
        'USERNAME_MAX_LENGTH': USERNAME_MAX_LENGTH,
        'PASSWORD_MIN_LENGTH': PASSWORD_MIN_LENGTH,
    }

    return jsonify({"user": user_details, "config": config_data}), 200


# --- API Routes for Chat Functionality --- (Keep existing chat APIs)

@app.route('/start_new_conversation', methods=['POST'])
def start_new_conversation():
    """Clears the current conversation context in the session."""
    if 'user_id' not in session:
        return jsonify({"error": "Authentication required"}), 401
    session.pop('current_conversation_id', None)
    print("Cleared current_conversation_id from session.")
# --- Settings / Profile API Routes --- # Renamed comment slightly

# Note: The API routes below handle the actual saving of settings data.
# The /settings GET route above just displays the page.

@app.route('/api/settings/profile', methods=['PUT'])
def update_profile():
    """API endpoint to update username and system prompt."""
    if 'user_id' not in session:
        return jsonify({"error": "Authentication required"}), 401
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    user_id = session['user_id']
    errors = {}
    success_messages = []

    # --- Update Username ---
    new_username = data.get('username')
    if new_username is not None: # Check if username field was included
        current_details = db_utils.get_user_details(user_id)
        if new_username != current_details.get('username'): # Only update if changed
            if not (USERNAME_MIN_LENGTH <= len(new_username) <= USERNAME_MAX_LENGTH):
                 errors['username'] = f"Username must be between {USERNAME_MIN_LENGTH} and {USERNAME_MAX_LENGTH} characters."
            elif not USERNAME_REGEX.match(new_username):
                 errors['username'] = "Username can only contain letters, numbers, and underscores."
            else:
                success = db_utils.update_username(user_id, new_username)
                if success:
                    session['username'] = new_username # Update session username
                    success_messages.append("Username updated.")
                elif success is False: # Explicit check for False (username taken)
                     errors['username'] = "Username already taken."
                else: # Null indicates DB error
                     errors['username'] = "Database error updating username."

    # --- Update System Prompt ---
    new_system_prompt = data.get('system_prompt')
    if new_system_prompt is not None: # Check if field was included
         # Basic validation (e.g., length limit) could be added here
         success = db_utils.update_system_prompt(user_id, new_system_prompt)
         if success:
              success_messages.append("System prompt updated.")
         else:
              errors['system_prompt'] = "Database error updating system prompt."

    # --- Update Profile Picture (URL only for now) ---
    # For actual upload, need file handling logic (see commented config)
    new_profile_picture_url = data.get('profile_picture_url')
    if new_profile_picture_url is not None:
         # Add validation for URL format if needed
         success = db_utils.update_profile_picture(user_id, new_profile_picture_url)
         if success:
              success_messages.append("Profile picture URL updated.")
         else:
              errors['profile_picture'] = "Database error updating profile picture URL."


    if errors:
        return jsonify({"errors": errors}), 400
    else:
        # Fetch updated details to send back
        updated_details = db_utils.get_user_details(user_id)
        return jsonify({
            "message": "Profile updated successfully." if not success_messages else " ".join(success_messages),
            "user": updated_details # Send back updated user info
        }), 200


@app.route('/api/settings/password', methods=['PUT'])
def change_password():
    """API endpoint to change the user's password."""
    if 'user_id' not in session:
        return jsonify({"error": "Authentication required"}), 401
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    current_password = data.get('current_password')
    new_password = data.get('new_password')
    confirm_password = data.get('confirm_password')
    user_id = session['user_id']

    # Validation
    if not current_password or not new_password or not confirm_password:
        return jsonify({"errors": {"form": "All password fields are required."}}), 400
    if new_password != confirm_password:
        return jsonify({"errors": {"confirm_password": "New passwords do not match."}}), 400
    if len(new_password) < PASSWORD_MIN_LENGTH:
         return jsonify({"errors": {"new_password": f"Password must be at least {PASSWORD_MIN_LENGTH} characters long."}}), 400

    # Verify current password
    try:
        with db_utils.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT password_hash FROM users WHERE user_id = ?", (user_id,))
            user_data = cursor.fetchone()
            if not user_data or not bcrypt.checkpw(current_password.encode('utf-8'), user_data['password_hash']):
                return jsonify({"errors": {"current_password": "Current password incorrect."}}), 400
    except Exception as e:
         print(f"Error verifying current password for user {user_id}: {e}")
         return jsonify({"errors": {"form": "Error verifying current password."}}), 500

    # Update to new password
    success = db_utils.update_password(user_id, new_password)
    if success:
        # Optionally force logout after password change for security
        # session.pop('user_id', None)
        # session.pop('username', None)
        # session.pop('current_conversation_id', None)
        return jsonify({"message": "Password updated successfully."}), 200
    else:
        return jsonify({"errors": {"form": "Failed to update password due to a database error."}}), 500


@app.route('/api/settings/delete_account', methods=['DELETE'])
def delete_account():
    """API endpoint to delete the user's account."""
    if 'user_id' not in session:
        return jsonify({"error": "Authentication required"}), 401

    user_id = session['user_id']

    # Optional: Add password confirmation for deletion
    # if not request.is_json: return jsonify({"error": "Request must be JSON"}), 400
    # data = request.get_json()
    # password = data.get('password')
    # if not verify_password(user_id, password): # You'd need a verify_password helper
    #     return jsonify({"error": "Incorrect password"}), 403

    success = db_utils.delete_user(user_id)
    if success:
        # Clear session completely after deletion
        session.clear()
        return jsonify({"message": "Account deleted successfully."}), 200
    else:
        return jsonify({"error": "Failed to delete account due to a database error."}), 500

    return jsonify({"message": "Ready for new conversation"}), 200

@app.route('/set_active_conversation', methods=['POST'])
def set_active_conversation():
    """Sets the active conversation ID in the session."""
    if 'user_id' not in session:
        return jsonify({"error": "Authentication required"}), 401
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    conversation_id = data.get('conversation_id')

    if not conversation_id:
        return jsonify({"error": "Missing 'conversation_id'"}), 400

    # Optional: Verify the user actually owns this conversation ID
    user_id = session['user_id']
    user_convs = db_utils.get_conversations(user_id)
    if not any(conv['conversation_id'] == conversation_id for conv in user_convs):
         return jsonify({"error": "Conversation not found or access denied"}), 404

    session['current_conversation_id'] = conversation_id
    print(f"Set active conversation to: {conversation_id}")
    return jsonify({"message": f"Active conversation set to {conversation_id}"}), 200


@app.route('/get_conversation_list', methods=['GET'])
def get_conversation_list():
    """Fetches the list of conversations for the logged-in user."""
    if 'user_id' not in session:
        return jsonify({"error": "Authentication required"}), 401
    user_id = session['user_id']
    try:
        conversations = db_utils.get_conversations(user_id)
        # Convert datetime objects if needed, though usually JSON handles them
        return jsonify({"conversations": conversations})
    except Exception as e:
        print(f"Error fetching conversation list for user {user_id}: {e}")
        return jsonify({"error": "Failed to retrieve conversation list"}), 500

@app.route('/rename_conversation/<int:conversation_id>', methods=['PUT'])
def rename_conversation(conversation_id):
    """Renames a specific conversation."""
    if 'user_id' not in session:
        return jsonify({"error": "Authentication required"}), 401
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    new_title = data.get('title')

    if not new_title or len(new_title.strip()) == 0:
        return jsonify({"error": "New title cannot be empty"}), 400

    user_id = session['user_id']
    try:
        success = db_utils.set_conversation_title(conversation_id, user_id, new_title.strip())
        if success:
            return jsonify({"message": "Conversation renamed successfully"}), 200
        else:
            # Error message handled by db_utils or implies not found/not owned
            return jsonify({"error": "Failed to rename conversation. Not found or permission denied."}), 404
    except Exception as e:
        print(f"Error renaming conversation {conversation_id}: {e}")
        return jsonify({"error": "An internal error occurred during rename"}), 500

@app.route('/delete_conversation/<int:conversation_id>', methods=['DELETE'])
def delete_conversation(conversation_id):
    """Deletes a specific conversation."""
    if 'user_id' not in session:
        return jsonify({"error": "Authentication required"}), 401

    user_id = session['user_id']
    try:
        # Verify ownership before deleting (important!)
        with db_utils.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM conversations WHERE conversation_id = ?", (conversation_id,))
            conversation = cursor.fetchone()

            if not conversation:
                return jsonify({"error": "Conversation not found"}), 404
            if conversation['user_id'] != user_id:
                return jsonify({"error": "Permission denied"}), 403

            # If checks pass, delete the conversation (cascading delete handles messages)
            cursor.execute("DELETE FROM conversations WHERE conversation_id = ?", (conversation_id,))
            conn.commit()

            # Clear from session if it was the active one
            if session.get('current_conversation_id') == conversation_id:
                session.pop('current_conversation_id', None)

            return jsonify({"message": "Conversation deleted successfully"}), 200

    except Exception as e:
        print(f"Error deleting conversation {conversation_id}: {e}")
        return jsonify({"error": "An internal error occurred during deletion"}), 500


@app.route('/get_conversation_messages', methods=['GET'])
def get_conversation_messages():
    """Fetches messages for a specific conversation."""
    if 'user_id' not in session:
        return jsonify({"error": "Authentication required"}), 401

    conversation_id = request.args.get('conversation_id', type=int)
    if not conversation_id:
        return jsonify({"error": "Missing 'conversation_id' query parameter"}), 400

    user_id = session['user_id']
    try:
        # --- Get User's Custom System Prompt (if any) ---
        user_details = db_utils.get_user_details(user_id)
        system_instruction = None
        if user_details and user_details.get('system_prompt'):
            system_instruction = user_details['system_prompt']
            print(f"Using custom system prompt for user {user_id}") # Keep this line
        # Fetch messages (moved this down slightly, no functional change)
        messages = db_utils.get_conversation_messages(conversation_id, user_id)
        if messages is None:
            # This handles cases where the conversation doesn't exist or user doesn't own it
            return jsonify({"error": "Conversation not found or access denied"}), 404
        return jsonify({"messages": messages})
    except Exception as e:
        print(f"Error fetching messages for conversation {conversation_id}: {e}")
        return jsonify({"error": "Failed to retrieve messages"}), 500


@app.route('/chat', methods=['POST']) # This route definition should remain
def chat():
    """Handles chatbot requests, potentially using user's system prompt."""
    if 'user_id' not in session:
        return jsonify({"error": "Authentication required"}), 401

    user_id = session['user_id']

    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    user_message = data.get('message')

    if not user_message:
        return jsonify({"error": "Missing 'message' in request body"}), 400

    try:
        # --- Get User's Custom System Prompt (if any) ---
        # This needs to be fetched *before* initializing the model
        user_details_chat = db_utils.get_user_details(user_id) # Fetch user details once here
        system_instruction_chat = None
        if user_details_chat and user_details_chat.get('system_prompt'):
             system_instruction_chat = user_details_chat['system_prompt']
             print(f"Chat route: Using custom system prompt for user {user_id}")

        # --- Determine or Create Conversation ---
        conversation_id = session.get('current_conversation_id')
        is_new_conversation = False
        if not conversation_id:
            conversation_id = db_utils.create_conversation(user_id)
            if not conversation_id:
                return jsonify({"error": "Failed to create new conversation"}), 500
            session['current_conversation_id'] = conversation_id
            is_new_conversation = True
            print(f"Started new conversation: {conversation_id}")
            history_raw = [] # No history for new conversation
        else:
            # Fetch history for the existing conversation
            history_raw = db_utils.get_conversation_messages(conversation_id, user_id)
            if history_raw is None: # Check if fetch failed (e.g., access denied)
                 session.pop('current_conversation_id', None) # Clear invalid ID from session
                 return jsonify({"error": "Failed to load conversation history or access denied"}), 404

        # --- Prepare History for API ---
        gemini_history = []
        for msg in history_raw:
            role = 'model' if msg['role'] == 'assistant' else msg['role']
            gemini_history.append({'role': role, 'parts': [{'text': msg['content']}]})

        # --- Call Gemini API ---
        model_name = "gemini-1.5-flash"
        model_args = {}
        # Use the system prompt fetched earlier in this route's scope
        if system_instruction_chat:
             model_args['system_instruction'] = system_instruction_chat

        model = genai.GenerativeModel(model_name, **model_args)
        chat_session = model.start_chat(history=gemini_history)
        response = chat_session.send_message(user_message)
        bot_response = response.text

        # --- Save Messages to DB ---
        user_msg_id = db_utils.add_message(conversation_id, 'user', user_message)
        assistant_msg_id = db_utils.add_message(conversation_id, 'assistant', bot_response)

        # --- Auto-generate Title for New Conversation ---
        # Generate title based on the *first user message* of a *new* conversation
        if is_new_conversation and user_msg_id:
            title = generate_title_from_message(user_message)
            db_utils.set_conversation_title(conversation_id, user_id, title)
            print(f"Auto-generated title for conversation {conversation_id}: {title}")

        # Return response and potentially the new conversation ID if it was created
        response_data = {"response": bot_response}
        if is_new_conversation:
            response_data["new_conversation_id"] = conversation_id
            response_data["new_conversation_title"] = title # Send back generated title

        return jsonify(response_data)

    except Exception as e:
        print(f"Error in /chat endpoint: {e}")
        # import traceback
        # traceback.print_exc() # More detailed traceback for debugging
        return jsonify({"error": "An internal error occurred", "details": str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True) # Debug=True reloads on changes