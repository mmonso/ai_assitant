import os
from werkzeug.utils import secure_filename
import mimetypes
import logging
from flask import Blueprint, request, jsonify, session
import google.generativeai as genai
from google.generativeai.types import File # Import File type for type hinting/checking
from google.generativeai.types import GenerationConfig # Import GenerationConfig
import db_utils
import config
from db_utils import (
    DatabaseError, DatabaseOperationalError,
    ConversationNotFoundError, PermissionDeniedError
)
import time
import base64 # Import base64 for image data encoding

log = logging.getLogger(__name__)

# Define the blueprint
chat_api_bp = Blueprint('chat_api', __name__, url_prefix='/api/chat')

# --- Helper Functions ---

def _allowed_file(filename):
    """Checks if the file extension is allowed based on config."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in config.ALLOWED_EXTENSIONS

def _process_uploaded_file(file_storage):
    """Saves the uploaded file locally and returns its path and MIME type."""
    if not file_storage:
        return None, None, None

    if not _allowed_file(file_storage.filename):
        log.warning(f"File type not allowed: {file_storage.filename}")
        return None, None, f"File type not allowed: {file_storage.filename.rsplit('.', 1)[1].lower()}"

    try:
        filename = secure_filename(file_storage.filename)
        upload_folder_path = config.UPLOAD_FOLDER
        os.makedirs(upload_folder_path, exist_ok=True)
        filepath = os.path.join(upload_folder_path, filename)
        file_storage.save(filepath)

        mime_type, _ = mimetypes.guess_type(filepath)
        if not mime_type:
            mime_type = 'application/octet-stream'
            log.warning(f"Could not guess MIME type for {filename}, using fallback: {mime_type}")

        log.info(f"Local file saved: {filepath}, MIME type: {mime_type}")
        return filepath, mime_type, None
    except Exception as e:
        log.error(f"Failed to save file locally {filename}: {e}", exc_info=True)
        return None, None, f"Failed to save file locally {filename}"

def _upload_file_to_google(filepath, mime_type):
    """Uploads the file from the local path to the Google File API."""
    try:
        log.info(f"Uploading {filepath} ({mime_type}) to Google File API...")
        display_name = os.path.basename(filepath)
        google_file = genai.upload_file(path=filepath, display_name=display_name, mime_type=mime_type)
        log.info(f"File uploaded successfully to Google File API. Name: {google_file.name}, URI: {google_file.uri}")
        return google_file, None
    except Exception as e:
        log.error(f"Failed to upload file {filepath} to Google File API: {e}", exc_info=True)
        return None, f"Failed to upload file to Google: {os.path.basename(filepath)}"


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
        system_prompt_raw = user_details.get('system_prompt')
        if system_prompt_raw:
            system_instruction = system_prompt_raw.strip()
            if system_instruction:
                model_args['system_instruction'] = system_instruction
                if message_to_send:
                    message_to_send = f"IMPORTANT SYSTEM PROMPT (Follow these instructions carefully):\n{system_instruction}\n\nUSER MESSAGE:\n{original_user_message}"

        user_info_raw = user_details.get('user_info')
        if user_info_raw and user_info_raw.strip():
            formatted_user_info = f"\n\nADDITIONAL USER INFORMATION (Provided by User):\n{user_info_raw.strip()}\n"
            if message_to_send:
                 message_to_send = f"{formatted_user_info}\n{message_to_send}"

    return message_to_send, model_args


def _get_or_create_conversation_context(user_id):
    """Gets current conversation ID and history (including file refs), or creates a new one."""
    conversation_id = session.get('current_conversation_id')
    is_new_conversation = False
    history_raw = []

    if not conversation_id:
        try:
            conversation_id = db_utils.create_conversation(user_id)
            session['current_conversation_id'] = conversation_id
        except (DatabaseOperationalError, DatabaseError) as e:
            log.error(f"Failed to create new conversation for user {user_id}: {e}")
            return None, False, None, "Failed to create new conversation"
        is_new_conversation = True
    else:
        try:
            history_raw = db_utils.get_conversation_messages(conversation_id, user_id)
        except PermissionDeniedError:
             log.warning(f"Access denied for user {user_id} trying to load history for conversation {conversation_id}")
             session.pop('current_conversation_id', None)
             return None, False, None, "Conversation not found or access denied"
        except ConversationNotFoundError:
             log.warning(f"Conversation {conversation_id} not found when fetching history for user {user_id}")
             session.pop('current_conversation_id', None)
             return None, False, None, "Conversation not found or access denied"
        except (DatabaseOperationalError, DatabaseError) as e:
             log.error(f"Failed to load conversation history for conv {conversation_id}, user {user_id}: {e}")
             session.pop('current_conversation_id', None)
             return None, False, None, "Failed to load conversation history"

    return conversation_id, is_new_conversation, history_raw, None


def _format_history_for_gemini(history_raw):
    """Formats conversation history for the Gemini API, including file references."""
    gemini_history = []
    for msg in history_raw:
        role = 'model' if msg['role'] == 'assistant' else msg['role']
        parts = []
        if msg.get('content'):
            parts.append({'text': msg['content']})

        google_file_name = msg.get('google_file_name')
        if google_file_name:
            try:
                retrieved_file = genai.get_file(name=google_file_name)
                parts.append(retrieved_file)
            except Exception as e:
                log.warning(f"Could not retrieve file '{google_file_name}' from history (likely expired/deleted): {e}")
                parts.append({'text': f"[Previous file '{msg.get('file_display_name', 'file')}' is no longer available]"})

        if parts:
            gemini_history.append({'role': role, 'parts': parts})
        else:
             log.warning(f"Skipping message ID {msg.get('message_id')} in history reconstruction as it had no text and its file ('{google_file_name}') could not be retrieved.")

    return gemini_history


# MODIFIED Helper: Call Gemini API (adds generation config, processes image response)
def _call_gemini_api(parts_to_send, gemini_history, model_args):
    """Calls the Gemini API using the session's selected model, requesting image modality, and processes response."""
    # Use the default model defined in config
    model_name = config.GEMINI_MODEL_NAME
    log.debug(f"Using default model: {model_name}")
    response_text = ""
    response_image_data = None # To store base64 image data if generated

    # Define generation config to request image output
    # Initialize GenerationConfig without the unsupported 'response_modalities'
    generation_config = GenerationConfig(
        # Add other valid config like temperature, top_p etc. here if needed
    )

    try:
        log.info(f"Attempting to initialize GenerativeModel with model_name='{model_name}', args={model_args}")
        model = genai.GenerativeModel(
            model_name,
            **model_args,
            generation_config=generation_config # Apply config here if needed by model init
            )
        log.info(f"Model initialized. Starting chat session with history length: {len(gemini_history)}")
        chat_session = model.start_chat(history=gemini_history)
        log.info(f"Chat session started. Sending parts to Gemini: {[(type(p), p.name if hasattr(p, 'name') else p) for p in parts_to_send]}")

        # Apply generation config to the send_message call
        response = chat_session.send_message(
            parts_to_send
            # generation_config=generation_config # Apply config during model init instead
            )

        # Process response parts
        for part in response.candidates[0].content.parts:
            if part.text:
                response_text += part.text + "\n" # Concatenate text parts
            elif part.inline_data:
                # Assuming only one image part for now
                image_data = part.inline_data.data
                mime_type = part.inline_data.mime_type
                # Encode image data as base64 string with data URI prefix
                response_image_data = f"data:{mime_type};base64,{base64.b64encode(image_data).decode('utf-8')}"
                log.info(f"Received image data part (MIME: {mime_type}, Size: {len(image_data)} bytes)")

        return response_text.strip(), response_image_data, None # Return text, image_data, no error

    except Exception as e:
        # Log the specific exception type and message
        log.error(f"Error calling Gemini API ({type(e).__name__}): {e}", exc_info=True)
        # Return a slightly more specific error message if possible, otherwise generic
        error_message = f"Error communicating with AI model ({type(e).__name__}). Check server logs for details."
        return None, None, error_message


# MODIFIED Helper: Save messages (no change needed here, already handles file refs)
def _save_chat_messages(conversation_id, original_user_message, bot_response, google_file_object=None):
    """Saves user and assistant messages to the database, including file reference if provided."""
    # Note: Bot response currently only saves text. If bot generates image, it's not saved to DB history.
    try:
        user_msg_id = None
        if original_user_message or google_file_object:
            user_msg_id = db_utils.add_message(
                conversation_id=conversation_id,
                role='user',
                content=original_user_message or "",
                google_file_name=google_file_object.name if google_file_object else None,
                file_display_name=google_file_object.display_name if google_file_object else None,
                file_mime_type=google_file_object.mime_type if google_file_object else None
            )

        assistant_msg_id = db_utils.add_message(
            conversation_id=conversation_id,
            role='assistant',
            content=bot_response # Only saving text part of bot response
        )
        return user_msg_id, assistant_msg_id, None
    except (DatabaseOperationalError, DatabaseError) as e:
        return None, None, "Failed to save messages to database"
    except Exception as e:
        log.error(f"Unexpected error saving messages for conversation {conversation_id}: {e}", exc_info=True)
        return None, None, "Unexpected error saving messages"


def _handle_new_conversation_title(is_new_conversation, conversation_id, user_id, user_msg_id, title_source_message):
    """Generates and saves title for a new conversation based on provided text."""
    title = None
    if is_new_conversation and title_source_message:
        try:
            title = _generate_title_from_message(title_source_message)
            success = db_utils.set_conversation_title(conversation_id, user_id, title)
            if not success:
                 log.warning(f"Failed to set auto-generated title for new conversation {conversation_id} for user {user_id} (returned False).")
        except (DatabaseOperationalError, DatabaseError) as e:
             log.error(f"Database error setting title for new conversation {conversation_id}: {e}", exc_info=True)
        except Exception as e:
            log.error(f"Unexpected error generating/saving title for new conversation {conversation_id}: {e}", exc_info=True)
    return title

# --- API Routes ---

@chat_api_bp.route('/start_new', methods=['POST'])
def start_new_conversation():
    if 'user_id' not in session: return jsonify({"error": "Authentication required"}), 401
    session.pop('current_conversation_id', None)
    return jsonify({"message": "Ready for new conversation"}), 200

@chat_api_bp.route('/set_active', methods=['POST'])
def set_active_conversation():
    if 'user_id' not in session: return jsonify({"error": "Authentication required"}), 401
    if not request.is_json: return jsonify({"error": "Request must be JSON"}), 400
    data = request.get_json()
    conversation_id_str = data.get('conversation_id')
    if not conversation_id_str: return jsonify({"error": "Missing 'conversation_id'"}), 400
    try: conversation_id = int(conversation_id_str)
    except (ValueError, TypeError): return jsonify({"error": "Invalid 'conversation_id' format"}), 400
    user_id = session['user_id']
    try:
        user_convs = db_utils.get_conversations(user_id)
        if not any(conv['conversation_id'] == conversation_id for conv in user_convs):
             return jsonify({"error": "Conversation not found or access denied"}), 404
    except (DatabaseOperationalError, DatabaseError) as e:
        log.error(f"Failed to verify conversation ownership for user {user_id}, conv {conversation_id}: {e}")
        return jsonify({"error": "Failed to verify conversation details"}), 500
    session['current_conversation_id'] = conversation_id
    return jsonify({"message": f"Active conversation set to {conversation_id}"}), 200


@chat_api_bp.route('/list', methods=['GET'])
def get_conversation_list():
    if 'user_id' not in session: return jsonify({"error": "Authentication required"}), 401
    user_id = session['user_id']
    try:
        conversations = db_utils.get_conversations(user_id)
        return jsonify({"conversations": conversations})
    except (DatabaseOperationalError, DatabaseError) as e:
        return jsonify({"error": "Failed to retrieve conversation list"}), 500
    except Exception as e:
        log.error(f"Unexpected error fetching conversation list for user {user_id}: {e}", exc_info=True)
        return jsonify({"error": "An unexpected error occurred"}), 500

@chat_api_bp.route('/rename/<int:conversation_id>', methods=['PUT'])
def rename_conversation(conversation_id):
    if 'user_id' not in session: return jsonify({"error": "Authentication required"}), 401
    if not request.is_json: return jsonify({"error": "Request must be JSON"}), 400
    data = request.get_json()
    new_title = data.get('title')
    if not new_title or len(new_title.strip()) == 0: return jsonify({"error": "New title cannot be empty"}), 400
    user_id = session['user_id']
    try:
        success = db_utils.set_conversation_title(conversation_id, user_id, new_title.strip())
        if success: return jsonify({"message": "Conversation renamed successfully"}), 200
        else: return jsonify({"error": "Failed to rename conversation. Not found or permission denied."}), 404
    except (DatabaseOperationalError, DatabaseError) as e:
        return jsonify({"error": "An internal error occurred during rename"}), 500
    except Exception as e:
        log.error(f"Unexpected error renaming conversation {conversation_id} for user {user_id}: {e}", exc_info=True)
        return jsonify({"error": "An unexpected error occurred"}), 500

@chat_api_bp.route('/delete/<int:conversation_id>', methods=['DELETE'])
def delete_conversation(conversation_id):
    """Deletes a specific conversation and associated Google Files."""
    if 'user_id' not in session: return jsonify({"error": "Authentication required"}), 401
    user_id = session['user_id']

    try:
        messages_with_files = db_utils.get_conversation_messages(conversation_id, user_id)
        google_file_names_to_delete = [
            msg['google_file_name'] for msg in messages_with_files if msg.get('google_file_name')
        ]

        db_utils.delete_conversation(conversation_id, user_id)

        if google_file_names_to_delete:
            log.info(f"Deleting {len(google_file_names_to_delete)} Google Files associated with deleted conversation {conversation_id}")
            for file_name in google_file_names_to_delete:
                try:
                    log.info(f"Attempting to delete Google File: {file_name}")
                    genai.delete_file(name=file_name)
                    log.info(f"Successfully deleted Google File: {file_name}")
                except Exception as file_del_err:
                    log.error(f"Failed to delete Google File {file_name}: {file_del_err}")

        if session.get('current_conversation_id') == conversation_id:
            session.pop('current_conversation_id', None)
            log.info(f"Cleared active conversation {conversation_id} from session after deletion.")

        return jsonify({"message": "Conversation deleted successfully"}), 200

    except ConversationNotFoundError: return jsonify({"error": "Conversation not found"}), 404
    except PermissionDeniedError: return jsonify({"error": "Permission denied"}), 403
    except (DatabaseOperationalError, DatabaseError) as e: return jsonify({"error": "An internal error occurred during deletion"}), 500
    except Exception as e:
        log.error(f"Unexpected error in delete_conversation route for conv {conversation_id}, user {user_id}: {e}", exc_info=True)
        return jsonify({"error": "An unexpected internal error occurred"}), 500


@chat_api_bp.route('/messages', methods=['GET'])
def get_conversation_messages():
    """Fetches messages for a specific conversation, including file info."""
    if 'user_id' not in session: return jsonify({"error": "Authentication required"}), 401
    conversation_id = request.args.get('conversation_id', type=int)
    if not conversation_id: return jsonify({"error": "Missing 'conversation_id' query parameter"}), 400
    user_id = session['user_id']
    try:
        messages = db_utils.get_conversation_messages(conversation_id, user_id)
        return jsonify({"messages": messages})
    except ConversationNotFoundError: return jsonify({"error": "Conversation not found or access denied"}), 404
    except PermissionDeniedError: return jsonify({"error": "Conversation not found or access denied"}), 403
    except (DatabaseOperationalError, DatabaseError) as e: return jsonify({"error": "Failed to retrieve messages"}), 500
    except Exception as e:
        log.error(f"Unexpected error fetching messages for conversation {conversation_id} user {user_id}: {e}", exc_info=True)
        return jsonify({"error": "An unexpected error occurred"}), 500


# MODIFIED Route: /send (Handles image generation response)
@chat_api_bp.route('/send', methods=['POST'])
def chat():
    """Handles chatbot requests, uploads files via Google File API, saves file refs, handles image generation."""
    if 'user_id' not in session: return jsonify({"error": "Authentication required"}), 401
    user_id = session['user_id']
    if not request.form: return jsonify({"error": "Request must be form data"}), 400

    original_user_message = request.form.get('message', '')
    uploaded_file_storage = request.files.get('file')

    if not original_user_message and not uploaded_file_storage:
        return jsonify({"error": "Missing 'message' or file in request"}), 400

    google_file_object = None
    local_filepath_to_remove = None

    try:
        # 1. Process local file upload
        if uploaded_file_storage:
            local_filepath, mime_type, local_file_error = _process_uploaded_file(uploaded_file_storage)
            if local_file_error: return jsonify({"error": local_file_error}), 400
            local_filepath_to_remove = local_filepath

            # 2. Upload to Google File API
            if local_filepath and mime_type:
                google_file_object, google_upload_error = _upload_file_to_google(local_filepath, mime_type)
                if google_upload_error: return jsonify({"error": google_upload_error}), 500
                # Optional: Clean up local file
                try:
                    if local_filepath_to_remove and os.path.exists(local_filepath_to_remove):
                        log.info(f"Removing local temporary file: {local_filepath_to_remove}")
                        os.remove(local_filepath_to_remove)
                        local_filepath_to_remove = None
                except OSError as e:
                    log.warning(f"Could not remove local file {local_filepath_to_remove} after successful Google upload: {e}")

        # 3. Prepare message text and model arguments
        message_with_context, model_args = _prepare_message_and_model_args(user_id, original_user_message)

        # 4. Get conversation context
        conversation_id, is_new_conversation, history_raw, context_error = _get_or_create_conversation_context(user_id)
        if context_error:
            status_code = 500 if "create" in context_error else 404
            return jsonify({"error": context_error}), status_code

        # 5. Format history
        gemini_history = _format_history_for_gemini(history_raw)

        # 6. Construct parts for current message
        parts_to_send = []
        if message_with_context: parts_to_send.append(message_with_context)
        if google_file_object: parts_to_send.append(google_file_object)
        if not parts_to_send: return jsonify({"error": "No content to send"}), 400

        # 7. Call the Gemini API (now returns text and optional image data)
        bot_response_text, bot_response_image_data, api_error = _call_gemini_api(parts_to_send, gemini_history, model_args)
        if api_error:
            if google_file_object:
                try: genai.delete_file(google_file_object.name)
                except Exception as del_err: log.error(f"Failed to delete Google file {google_file_object.name} after API error: {del_err}")
            return jsonify({"error": api_error}), 500

        # 8. Save messages to the database
        user_msg_id, assistant_msg_id, db_save_error = _save_chat_messages(
            conversation_id, original_user_message, bot_response_text, google_file_object # Save only text part of bot response
        )
        if db_save_error:
            if google_file_object:
                try: genai.delete_file(google_file_object.name)
                except Exception as del_err: log.error(f"Failed to delete Google file {google_file_object.name} after DB error: {del_err}")
            return jsonify({"error": db_save_error}), 500

        # 9. Handle title generation
        title_source = original_user_message or (google_file_object.display_name if google_file_object else "File Upload")
        title = _handle_new_conversation_title(is_new_conversation, conversation_id, user_id, user_msg_id, title_source)

        # 10. Prepare and return the response (including image data if present)
        response_data = {"response": bot_response_text} # Always include text response
        if bot_response_image_data:
            response_data["image_data"] = bot_response_image_data # Add base64 image data if generated

        if is_new_conversation:
            response_data["new_conversation_id"] = conversation_id
            response_data["new_conversation_title"] = title

        return jsonify(response_data)

    except Exception as e:
        log.error(f"Unexpected error in /send endpoint for user {user_id}: {e}", exc_info=True)
        if google_file_object:
            try: genai.delete_file(google_file_object.name)
            except Exception as del_err: log.error(f"Failed to delete Google file {google_file_object.name} after unexpected error: {del_err}")
        try:
            if local_filepath_to_remove and os.path.exists(local_filepath_to_remove):
                os.remove(local_filepath_to_remove)
        except OSError as e:
             log.warning(f"Could not remove local file {local_filepath_to_remove} during exception handling: {e}")

        return jsonify({"error": "An unexpected internal error occurred"}), 500