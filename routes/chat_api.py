import os
from flask import Blueprint, request, jsonify, session
# import json # Removed, no longer parsing user_info
import google.generativeai as genai
import db_utils

# Define the blueprint
chat_api_bp = Blueprint('chat_api', __name__, url_prefix='/api/chat') # Optional prefix for API routes

# --- Helper Functions ---

def _generate_title_from_message(message):
    """Generates a short title from the first user message."""
    words = message.split()
    title = " ".join(words[:5])
    if len(words) > 5:
        title += "..."
    return title

def _prepare_message_and_model_args(user_id, original_user_message):
    """Fetches user details and prepares the message string and model arguments."""
    user_details = db_utils.get_user_details(user_id)
    system_instruction = None
    model_args = {}
    message_to_send = original_user_message

    if user_details:
        # Prepare system prompt
        system_prompt_raw = user_details.get('system_prompt')
        if system_prompt_raw:
            system_instruction = system_prompt_raw.strip()
            if system_instruction:
                model_args['system_instruction'] = system_instruction
                # Prepend system prompt for reinforcement
                message_to_send = f"IMPORTANT SYSTEM PROMPT (Follow these instructions carefully):\n{system_instruction}\n\nUSER MESSAGE:\n{original_user_message}"

        # Prepare user info
        user_info_raw = user_details.get('user_info')
        if user_info_raw and user_info_raw.strip():
            formatted_user_info = f"\n\nADDITIONAL USER INFORMATION (Provided by User):\n{user_info_raw.strip()}\n"
            # Prepend user info (potentially after system prompt)
            message_to_send = f"{formatted_user_info}\n{message_to_send}"

    return message_to_send, model_args


def _get_or_create_conversation_context(user_id):
    """Gets current conversation ID and history, or creates a new one."""
    conversation_id = session.get('current_conversation_id')
    is_new_conversation = False
    history_raw = []

    if not conversation_id:
        conversation_id = db_utils.create_conversation(user_id)
        if not conversation_id:
            # Failed to create conversation
            return None, False, None, "Failed to create new conversation"
        session['current_conversation_id'] = conversation_id
        is_new_conversation = True
    else:
        history_raw = db_utils.get_conversation_messages(conversation_id, user_id)
        if history_raw is None:
            # Failed to load history or access denied
            session.pop('current_conversation_id', None) # Clear invalid ID
            return None, False, None, "Failed to load conversation history or access denied"

    return conversation_id, is_new_conversation, history_raw, None # No error


def _format_history_for_gemini(history_raw):
    """Formats conversation history for the Gemini API."""
    gemini_history = []
    for msg in history_raw:
        role = 'model' if msg['role'] == 'assistant' else msg['role']
        gemini_history.append({'role': role, 'parts': [{'text': msg['content']}]})
    return gemini_history


def _call_gemini_api(message_to_send, gemini_history, model_args):
    """Calls the Gemini API and returns the response text."""
    # TODO: Move model_name to config
    model_name = "gemini-1.5-flash"

    # API key check (consider if still needed after app.py setup)
    if not os.environ.get("GEMINI_API_KEY"):
         print("Error: Gemini API Key not configured.") # Use logging
         return None, "Chat service not configured"

    try:
        # Instantiate the model *inside* the request with latest system prompt
        model = genai.GenerativeModel(model_name, **model_args)
        chat_session = model.start_chat(history=gemini_history)
        response = chat_session.send_message(message_to_send)
        return response.text, None # No error
    except Exception as e:
        print(f"Error calling Gemini API: {e}") # Use logging
        # import traceback; traceback.print_exc() # For detailed debug
        return None, f"Error communicating with AI model: {str(e)}"


def _save_chat_messages(conversation_id, original_user_message, bot_response):
    """Saves user and assistant messages to the database."""
    try:
        user_msg_id = db_utils.add_message(conversation_id, 'user', original_user_message)
        assistant_msg_id = db_utils.add_message(conversation_id, 'assistant', bot_response)
        if not user_msg_id or not assistant_msg_id:
            # Handle potential DB error where add_message returns None
             print(f"Error saving messages to DB for conversation {conversation_id}") # Use logging
             return None, None, "Failed to save messages to database"
        return user_msg_id, assistant_msg_id, None # No error
    except Exception as e:
        print(f"Database error saving messages: {e}") # Use logging
        return None, None, "Database error while saving messages"


def _handle_new_conversation_title(is_new_conversation, conversation_id, user_id, user_msg_id, original_user_message):
    """Generates and saves title for a new conversation."""
    title = None
    if is_new_conversation and user_msg_id:
        try:
            title = _generate_title_from_message(original_user_message)
            success = db_utils.set_conversation_title(conversation_id, user_id, title)
            if not success:
                 print(f"Failed to set title for new conversation {conversation_id}") # Use logging
                 # Non-critical error, proceed without title maybe? Or return an error?
                 # For now, just log it.
        except Exception as e:
            print(f"Error generating/saving title for conversation {conversation_id}: {e}") # Use logging
            # Non-critical error
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


@chat_api_bp.route('/send', methods=['POST'])
def chat():
    """Handles chatbot requests by orchestrating helper functions."""
    if 'user_id' not in session:
        return jsonify({"error": "Authentication required"}), 401

    user_id = session['user_id']

    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    original_user_message = data.get('message')

    if not original_user_message:
        return jsonify({"error": "Missing 'message' in request body"}), 400

    try:
        # 1. Prepare message and model arguments based on user settings
        message_to_send, model_args = _prepare_message_and_model_args(user_id, original_user_message)

        # 2. Get conversation context (ID, history) or create a new one
        conversation_id, is_new_conversation, history_raw, context_error = _get_or_create_conversation_context(user_id)
        if context_error:
            status_code = 500 if "create" in context_error else 404
            return jsonify({"error": context_error}), status_code

        # 3. Format history for the Gemini API
        gemini_history = _format_history_for_gemini(history_raw)

        # 4. Call the Gemini API
        bot_response, api_error = _call_gemini_api(message_to_send, gemini_history, model_args)
        if api_error:
            return jsonify({"error": api_error}), 500 # Internal server error for API issues

        # 5. Save messages to the database
        user_msg_id, assistant_msg_id, db_save_error = _save_chat_messages(conversation_id, original_user_message, bot_response)
        if db_save_error:
            return jsonify({"error": db_save_error}), 500

        # 6. Handle title generation for new conversations
        title = _handle_new_conversation_title(is_new_conversation, conversation_id, user_id, user_msg_id, original_user_message)

        # 7. Prepare and return the response
        response_data = {"response": bot_response}
        if is_new_conversation:
            response_data["new_conversation_id"] = conversation_id
            response_data["new_conversation_title"] = title # Send back generated title

        return jsonify(response_data)

    except Exception as e:
        # Catch-all for unexpected errors during orchestration
        print(f"Unexpected error in /send endpoint: {e}") # Use logging
        # import traceback; traceback.print_exc() # For detailed debug
        return jsonify({"error": "An unexpected internal error occurred"}), 500