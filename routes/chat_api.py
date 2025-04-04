import os
from flask import Blueprint, request, jsonify, session
# import json # Removed, no longer parsing user_info
import google.generativeai as genai
import db_utils

# Define the blueprint
chat_api_bp = Blueprint('chat_api', __name__, url_prefix='/api/chat') # Optional prefix for API routes

# --- Helper Function (Consider moving to a utils file if used elsewhere) ---
def generate_title_from_message(message):
    """Generates a short title from the first user message."""
    words = message.split()
    title = " ".join(words[:5])
    if len(words) > 5:
        title += "..."
    return title

# --- API Routes ---

@chat_api_bp.route('/start_new', methods=['POST']) # Renamed route slightly for clarity
def start_new_conversation():
    """Clears the current conversation context in the session."""
    if 'user_id' not in session:
        return jsonify({"error": "Authentication required"}), 401
    session.pop('current_conversation_id', None)
    # print("Cleared current_conversation_id from session.") # Removed log
    return jsonify({"message": "Ready for new conversation"}), 200 # Return success

@chat_api_bp.route('/set_active', methods=['POST']) # Renamed route slightly
def set_active_conversation():
    """Sets the active conversation ID in the session."""
    if 'user_id' not in session:
        return jsonify({"error": "Authentication required"}), 401
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    conversation_id_str = data.get('conversation_id') # Get potential string from JSON

    if not conversation_id_str:
        return jsonify({"error": "Missing 'conversation_id'"}), 400

    try:
        # Explicitly convert to integer for comparison and session storage
        conversation_id = int(conversation_id_str)
    except (ValueError, TypeError):
         return jsonify({"error": "Invalid 'conversation_id' format"}), 400

    # Verify the user actually owns this conversation ID
    user_id = session['user_id']
    user_convs = db_utils.get_conversations(user_id)
    # Compare int to int (conv['conversation_id'] is int from DB)
    if not any(conv['conversation_id'] == conversation_id for conv in user_convs):
         return jsonify({"error": "Conversation not found or access denied"}), 404

    session['current_conversation_id'] = conversation_id # Store as integer
    # print(f"Set active conversation to: {conversation_id}") # Removed log
    return jsonify({"message": f"Active conversation set to {conversation_id}"}), 200


@chat_api_bp.route('/list', methods=['GET']) # Renamed route slightly
def get_conversation_list():
    """Fetches the list of conversations for the logged-in user."""
    if 'user_id' not in session:
        return jsonify({"error": "Authentication required"}), 401
    user_id = session['user_id']
    try:
        conversations = db_utils.get_conversations(user_id)
        return jsonify({"conversations": conversations})
    except Exception as e:
        print(f"Error fetching conversation list for user {user_id}: {e}")
        return jsonify({"error": "Failed to retrieve conversation list"}), 500

@chat_api_bp.route('/rename/<int:conversation_id>', methods=['PUT']) # Renamed route slightly
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
            return jsonify({"error": "Failed to rename conversation. Not found or permission denied."}), 404
    except Exception as e:
        print(f"Error renaming conversation {conversation_id}: {e}")
        return jsonify({"error": "An internal error occurred during rename"}), 500

@chat_api_bp.route('/delete/<int:conversation_id>', methods=['DELETE']) # Renamed route slightly
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


@chat_api_bp.route('/messages', methods=['GET']) # Renamed route slightly
def get_conversation_messages():
    """Fetches messages for a specific conversation."""
    if 'user_id' not in session:
        return jsonify({"error": "Authentication required"}), 401

    conversation_id = request.args.get('conversation_id', type=int)
    if not conversation_id:
        return jsonify({"error": "Missing 'conversation_id' query parameter"}), 400

    user_id = session['user_id']
    try:
        # Fetch messages (moved this down slightly, no functional change)
        messages = db_utils.get_conversation_messages(conversation_id, user_id)
        if messages is None:
            # This handles cases where the conversation doesn't exist or user doesn't own it
            return jsonify({"error": "Conversation not found or access denied"}), 404
        return jsonify({"messages": messages})
    except Exception as e:
        print(f"Error fetching messages for conversation {conversation_id}: {e}")
        return jsonify({"error": "Failed to retrieve messages"}), 500


@chat_api_bp.route('/send', methods=['POST']) # Renamed route slightly
def chat():
    """Handles chatbot requests, potentially using user's system prompt."""
    if 'user_id' not in session:
        return jsonify({"error": "Authentication required"}), 401

    user_id = session['user_id']

    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    original_user_message = data.get('message') # Store original message

    if not original_user_message:
        return jsonify({"error": "Missing 'message' in request body"}), 400

    try:
        # --- Get User's Custom System Prompt (if any) ---
        user_details_chat = db_utils.get_user_details(user_id)
        system_instruction_chat = None
        model_args = {} # Initialize model args
        message_to_send = original_user_message # Start with original message

        if user_details_chat and user_details_chat.get('system_prompt'):
             system_instruction_chat = user_details_chat['system_prompt'].strip() # Ensure no extra whitespace
             if system_instruction_chat: # Check if not empty after stripping
                 model_args['system_instruction'] = system_instruction_chat
                 # Prepend system prompt to the user message for reinforcement
                 message_to_send = f"IMPORTANT SYSTEM PROMPT (Follow these instructions carefully):\n{system_instruction_chat}\n\nUSER MESSAGE:\n{original_user_message}"
                 # print(f"Chat route: Using custom system prompt: '{system_instruction_chat}' (Prepended to message)") # Removed log
             # else: # Removed log
                 # print("Chat route: Custom system prompt is empty after stripping.")
        # else: # Removed log
             # print("Chat route: No custom system prompt found for user.")

        # --- Add User Info (if available) ---
        user_info_str = user_details_chat.get('user_info')
        user_info_str = user_details_chat.get('user_info')
        if user_info_str and user_info_str.strip(): # Check if not None and not empty after stripping whitespace
            formatted_user_info = f"\n\nADDITIONAL USER INFORMATION (Provided by User):\n{user_info_str.strip()}\n"
            message_to_send = f"{formatted_user_info}\n{message_to_send}" # Prepend user info
            # print(f"Chat route: Prepended user info: {formatted_user_info}") # Removed log


        # --- Determine or Create Conversation ---
        conversation_id = session.get('current_conversation_id')
        is_new_conversation = False
        if not conversation_id:
            conversation_id = db_utils.create_conversation(user_id)
            if not conversation_id:
                return jsonify({"error": "Failed to create new conversation"}), 500
            session['current_conversation_id'] = conversation_id
            is_new_conversation = True
            # print(f"Started new conversation: {conversation_id}") # Removed log
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
        model_name = "gemini-1.5-flash" # Consider making this configurable

        # Ensure API key is configured (it should be from app.py, but double-check context)
        if not os.environ.get("GEMINI_API_KEY"):
             print("Error: Gemini API Key not configured.")
             return jsonify({"error": "Chat service not configured"}), 500
        # genai.configure should have been called in app.py

        # print(f"Chat route: Initializing model with args: {model_args}") # Removed log

        # Instantiate the model *inside* the request with latest system prompt
        model = genai.GenerativeModel(model_name, **model_args)
        chat_session = model.start_chat(history=gemini_history)

        # Send the potentially modified message (with prepended prompt)
        # print(f"Chat route: Sending message to Gemini:\n---\n{message_to_send}\n---") # Removed log
        response = chat_session.send_message(message_to_send)
        bot_response = response.text
        # print(f"Chat route: Received response from Gemini:\n---\n{bot_response}\n---") # Removed log

        # --- Save Messages to DB (Save the *original* user message) ---
        user_msg_id = db_utils.add_message(conversation_id, 'user', original_user_message)
        assistant_msg_id = db_utils.add_message(conversation_id, 'assistant', bot_response)

        # --- Auto-generate Title for New Conversation ---
        title = None # Initialize title
        if is_new_conversation and user_msg_id:
            title = generate_title_from_message(original_user_message) # Use original for title
            db_utils.set_conversation_title(conversation_id, user_id, title)
            # print(f"Auto-generated title for conversation {conversation_id}: {title}") # Removed log

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