import os
import secrets # For generating secret key
from flask import Flask, request, jsonify, render_template, session, redirect, url_for, flash
import google.generativeai as genai
from dotenv import load_dotenv
import db_utils # Import our database utility functions

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
    # Clear active conversation on main page load? Or rely on "New Chat"?
    # session.pop('current_conversation_id', None) # Optional: Force new chat on load
    return render_template('index.html')

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

# --- API Routes for Chat Functionality ---

@app.route('/start_new_conversation', methods=['POST'])
def start_new_conversation():
    """Clears the current conversation context in the session."""
    if 'user_id' not in session:
        return jsonify({"error": "Authentication required"}), 401
    session.pop('current_conversation_id', None)
    print("Cleared current_conversation_id from session.")
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
        messages = db_utils.get_conversation_messages(conversation_id, user_id)
        if messages is None:
            # This handles cases where the conversation doesn't exist or user doesn't own it
            return jsonify({"error": "Conversation not found or access denied"}), 404
        return jsonify({"messages": messages})
    except Exception as e:
        print(f"Error fetching messages for conversation {conversation_id}: {e}")
        return jsonify({"error": "Failed to retrieve messages"}), 500


@app.route('/chat', methods=['POST'])
def chat():
    """Handles chatbot requests within a specific or new conversation."""
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
        model = genai.GenerativeModel(model_name)
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