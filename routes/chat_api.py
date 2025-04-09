import os
from werkzeug.utils import secure_filename
import mimetypes
import logging
import asyncio # Adicionado para MCP
import json    # Adicionado para processar JSON da SerpApi
from flask import Blueprint, request, jsonify, session
import google.generativeai as genai
# Remover 'Part' e 'Content' da importação direta, pois causam erro. Usar dicts onde necessário.
from google.generativeai.types import File, Tool, FunctionDeclaration
from google.generativeai.types import GenerationConfig # Import GenerationConfig
from mcp import ClientSession, StdioServerParameters # Adicionado para MCP
from mcp.client.stdio import stdio_client           # Adicionado para MCP
import db_utils
import config
from db_utils import (
    DatabaseError, DatabaseOperationalError,
    ConversationNotFoundError, PermissionDeniedError,
    FolderNotFoundError, DuplicateFolderError # Import new exceptions
)
import time
import base64 # Import base64 for image data encoding

log = logging.getLogger(__name__)

# Define the blueprint
chat_api_bp = Blueprint('chat_api', __name__, url_prefix='/api/chat')

# --- Constantes e Configurações MCP ---
# Caminho para o script do servidor MCP (ajuste conforme necessário)
# Usar raw string para evitar problemas com barras invertidas no Windows
SERPAPI_SERVER_SCRIPT_PATH = r"C:\mcp_servers\serpapi-server\build\index.js"

# Parâmetros para conectar ao servidor MCP via stdio
mcp_server_params = StdioServerParameters(
    command="node",
    args=[SERPAPI_SERVER_SCRIPT_PATH],
    # env={} # Não precisamos passar env aqui, pois o servidor lê do .env ou foi passado via mcp_settings.json
)

# --- Helper Functions (Non-Route Specific) ---

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

    # Remover completamente o prompt do sistema para testar
    model_args['system_instruction'] = None
    message_to_send = original_user_message # Usar apenas a mensagem do usuário


    return message_to_send, model_args


def _get_or_create_conversation_context(user_id):
    """Gets current conversation ID and history (including file refs), or creates a new one."""
    conversation_id = session.get('current_conversation_id')
    is_new_conversation = False
    history_raw = []

    if not conversation_id:
        try:
            conversation_id = db_utils.create_conversation(user_id, folder_id=None)
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


# MODIFIED Helper: Save messages (agora salva apenas uma mensagem por vez)
def _save_single_message(conversation_id, role, content=None, google_file_object=None):
    """Saves a single message (user or assistant) to the database."""
    if not content and not google_file_object:
        log.warning(f"Tentativa de salvar mensagem vazia para conv {conversation_id}, role {role}. Pulando.")
        return None, "Cannot save empty message"

    try:
        message_id = db_utils.add_message(
            conversation_id=conversation_id,
            role=role,
            content=content or "",
            google_file_name=google_file_object.name if google_file_object else None,
            file_display_name=google_file_object.display_name if google_file_object else None,
            file_mime_type=google_file_object.mime_type if google_file_object else None
        )
        return message_id, None
    except (DatabaseOperationalError, DatabaseError) as e:
        log.error(f"Erro DB ao salvar msg ({role}) para conv {conversation_id}: {e}", exc_info=True)
        return None, f"Failed to save {role} message to database"
    except Exception as e:
        log.error(f"Erro inesperado ao salvar msg ({role}) para conv {conversation_id}: {e}", exc_info=True)
        return None, f"Unexpected error saving {role} message"


def _handle_new_conversation_title(is_new_conversation, conversation_id, user_id, user_msg_id, title_source_message):
    """Generates and saves title for a new conversation based on provided text."""
    title = None
    if is_new_conversation and title_source_message and user_msg_id: # Precisa do user_msg_id
        try:
            title = _generate_title_from_message(title_source_message)
            success = db_utils.set_conversation_title(conversation_id, user_id, title)
            if not success:
                 log.warning(f"Failed to set auto-generated title for new conversation {conversation_id} for user {user_id} (returned False).")
        except (DatabaseOperationalError, DatabaseError) as e:
             log.error(f"Database error setting title for new conversation {conversation_id}: {e}", exc_info=True)
        except Exception as e:
            log.error(f"Unexpected error generating/saving title for new conversation {conversation_id}: {e}", exc_info=True)
    elif is_new_conversation and not user_msg_id:
         log.warning(f"Cannot generate title for new conversation {conversation_id} because user message ID is missing.")
    return title

# --- Funções Auxiliares MCP ---

def _convert_mcp_tool_to_gemini(mcp_tool) -> Tool | None:
    """Converte um schema de ferramenta MCP para o formato Gemini Tool."""
    try:
        properties = mcp_tool.inputSchema.get('properties', {})
        cleaned_properties = {k: v for k, v in properties.items() if k not in ['$schema', 'additionalProperties']}

        parameters = {
            'type': mcp_tool.inputSchema.get('type', 'object'),
            'properties': cleaned_properties,
            'required': mcp_tool.inputSchema.get('required', [])
        }

        declaration = FunctionDeclaration(
            name=mcp_tool.name,
            description=mcp_tool.description or "",
            parameters=parameters
        )
        return Tool(function_declarations=[declaration])
    except Exception as e:
        log.error(f"Erro ao converter ferramenta MCP '{mcp_tool.name}': {e}", exc_info=True)
        return None

def _extract_serpapi_summary(json_string: str) -> str:
    """Extrai um resumo útil da resposta JSON (string) da SerpApi."""
    try:
        data = json.loads(json_string)
        summary_parts = []

        # Prioridade: Answer Box
        if data.get('answer_box'):
            box = data['answer_box']
            if box.get('title'): summary_parts.append(f"**{box['title']}**")
            if box.get('snippet'): summary_parts.append(box['snippet'])
            elif box.get('answer'): summary_parts.append(box['answer'])
            if box.get('result'): summary_parts.append(box['result'])
            if box.get('link'): summary_parts.append(f"(Fonte: {box['link']})")
            if summary_parts: return "\n".join(summary_parts).strip()

        # Segunda Prioridade: Knowledge Graph
        if data.get('knowledge_graph'):
            kg = data['knowledge_graph']
            if kg.get('title'): summary_parts.append(f"**{kg['title']}**")
            if kg.get('description'): summary_parts.append(kg['description'])
            if kg.get('source', {}).get('link'): summary_parts.append(f"(Fonte: {kg['source']['link']})")
            if summary_parts: return "\n".join(summary_parts).strip()

        # Terceira Prioridade: Top Organic Result Snippet
        if data.get('organic_results') and len(data['organic_results']) > 0:
            top_result = data['organic_results'][0]
            if top_result.get('snippet'):
                 summary_parts.append(f"'{top_result['snippet']}'")
                 if top_result.get('link'): summary_parts.append(f"(Fonte: {top_result['link']})")
                 if summary_parts: return "\n".join(summary_parts).strip()

        # Fallback: JSON bruto (limitado)
        log.info("Não foi possível extrair resumo estruturado da SerpApi, retornando JSON bruto.")
        return f"Resultado da busca (JSON): {json_string[:1000]}{'...' if len(json_string) > 1000 else ''}"

    except json.JSONDecodeError:
        log.warning("Não foi possível parsear a resposta JSON da SerpApi.")
        return f"A busca retornou dados não-JSON: {json_string[:500]}{'...' if len(json_string) > 500 else ''}"
    except Exception as e:
        log.error(f"Erro ao extrair resumo da SerpApi: {e}", exc_info=True)
        return "Erro ao processar os resultados da busca na web."


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
        conversations_raw = db_utils.get_conversations(user_id)
        folders_raw = db_utils.get_folders(user_id)

        conversations = []
        for conv in conversations_raw:
            conv_dict = dict(conv)
            if 'created_at' in conv_dict and conv_dict['created_at']:
                 try:
                     if not isinstance(conv_dict['created_at'], str):
                         conv_dict['created_at'] = conv_dict['created_at'].isoformat()
                 except AttributeError:
                     log.warning(f"Could not format created_at for conversation {conv_dict.get('conversation_id')}: {conv_dict.get('created_at')}")
                     conv_dict['created_at'] = str(conv_dict['created_at'])
            conversations.append(conv_dict)

        folders = []
        for folder in folders_raw:
            folder_dict = dict(folder)
            if 'created_at' in folder_dict and folder_dict['created_at']:
                 try:
                     if not isinstance(folder_dict['created_at'], str):
                         folder_dict['created_at'] = folder_dict['created_at'].isoformat()
                 except AttributeError:
                     log.warning(f"Could not format created_at for folder {folder_dict.get('folder_id')}: {folder_dict.get('created_at')}")
                     folder_dict['created_at'] = str(folder_dict['created_at'])
            folders.append(folder_dict)

        response_data = {
            "conversations": conversations,
            "folders": folders
        }
        return jsonify(response_data)
    except (DatabaseOperationalError, DatabaseError) as e:
        log.error(f"Database error fetching conversation/folder list for user {user_id}: {e}", exc_info=True)
        return jsonify({"error": "Failed to retrieve conversation list or folders"}), 500
    except Exception as e:
        log.exception(f"UNEXPECTED error in /list route for user {user_id}: {e}")
        return jsonify({"error": "An unexpected server error occurred while fetching data."}), 500

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


# --- Folder API Routes ---

@chat_api_bp.route('/folders', methods=['POST'])
def create_folder():
    if 'user_id' not in session: return jsonify({"error": "Authentication required"}), 401
    if not request.is_json: return jsonify({"error": "Request must be JSON"}), 400
    data = request.get_json()
    name = data.get('name')
    if not name or len(name.strip()) == 0: return jsonify({"error": "Folder name cannot be empty"}), 400
    user_id = session['user_id']
    try:
        folder_id = db_utils.create_folder(user_id, name.strip())
        return jsonify({"message": "Folder created successfully", "folder_id": folder_id, "name": name.strip()}), 201
    except DuplicateFolderError as e:
        return jsonify({"error": str(e)}), 409 # Conflict
    except (DatabaseOperationalError, DatabaseError) as e:
        return jsonify({"error": "An internal error occurred creating the folder"}), 500
    except Exception as e:
        log.exception(f"UNEXPECTED error in POST /folders route for user {user_id}: {e}")
        return jsonify({"error": "An unexpected server error occurred while creating the folder."}), 500

@chat_api_bp.route('/folders', methods=['GET'])
def get_folders():
    if 'user_id' not in session: return jsonify({"error": "Authentication required"}), 401
    user_id = session['user_id']
    try:
        folders = db_utils.get_folders(user_id)
        return jsonify({"folders": folders})
    except (DatabaseOperationalError, DatabaseError) as e:
        return jsonify({"error": "Failed to retrieve folder list"}), 500
    except Exception as e:
        log.error(f"Unexpected error fetching folder list for user {user_id}: {e}", exc_info=True)
        return jsonify({"error": "An unexpected error occurred"}), 500

@chat_api_bp.route('/folders/<int:folder_id>', methods=['PUT'])
def rename_folder(folder_id):
    if 'user_id' not in session: return jsonify({"error": "Authentication required"}), 401
    if not request.is_json: return jsonify({"error": "Request must be JSON"}), 400
    data = request.get_json()
    new_name = data.get('name')
    if not new_name or len(new_name.strip()) == 0: return jsonify({"error": "New folder name cannot be empty"}), 400
    user_id = session['user_id']
    try:
        success = db_utils.update_folder_name(folder_id, user_id, new_name.strip())
        if success: return jsonify({"message": "Folder renamed successfully"}), 200
        else: return jsonify({"error": "Folder not found or permission denied"}), 404
    except FolderNotFoundError: return jsonify({"error": "Folder not found"}), 404
    except PermissionDeniedError: return jsonify({"error": "Permission denied"}), 403
    except DuplicateFolderError as e: return jsonify({"error": str(e)}), 409
    except (DatabaseOperationalError, DatabaseError) as e: return jsonify({"error": "An internal error occurred during rename"}), 500
    except Exception as e:
        log.error(f"Unexpected error renaming folder {folder_id} for user {user_id}: {e}", exc_info=True)
        return jsonify({"error": "An unexpected error occurred"}), 500

@chat_api_bp.route('/folders/<int:folder_id>', methods=['DELETE'])
def delete_folder(folder_id):
    if 'user_id' not in session: return jsonify({"error": "Authentication required"}), 401
    user_id = session['user_id']
    try:
        db_utils.delete_folder(folder_id, user_id)
        return jsonify({"message": "Folder deleted successfully"}), 200
    except FolderNotFoundError: return jsonify({"error": "Folder not found"}), 404
    except PermissionDeniedError: return jsonify({"error": "Permission denied"}), 403
    except (DatabaseOperationalError, DatabaseError) as e: return jsonify({"error": "An internal error occurred during deletion"}), 500
    except Exception as e:
        log.error(f"Unexpected error deleting folder {folder_id} for user {user_id}: {e}", exc_info=True)
        return jsonify({"error": "An unexpected internal error occurred"}), 500

@chat_api_bp.route('/conversations/<int:conversation_id>/move', methods=['PUT'])
def move_conversation(conversation_id):
    if 'user_id' not in session: return jsonify({"error": "Authentication required"}), 401
    if not request.is_json: return jsonify({"error": "Request must be JSON"}), 400
    data = request.get_json()
    folder_id = data.get('folder_id')
    if folder_id is not None:
        try:
            folder_id = int(folder_id)
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid 'folder_id' format"}), 400

    user_id = session['user_id']
    try:
        success = db_utils.move_conversation_to_folder(conversation_id, user_id, folder_id)
        if success: return jsonify({"message": "Conversation moved successfully"}), 200
        else: return jsonify({"error": "Failed to move conversation"}), 500
    except ConversationNotFoundError: return jsonify({"error": "Conversation not found"}), 404
    except FolderNotFoundError: return jsonify({"error": "Target folder not found"}), 404
    except PermissionDeniedError: return jsonify({"error": "Permission denied"}), 403
    except (DatabaseOperationalError, DatabaseError) as e: return jsonify({"error": "An internal error occurred during move"}), 500
    except Exception as e:
        log.error(f"Unexpected error moving conversation {conversation_id} to folder {folder_id} for user {user_id}: {e}", exc_info=True)
        return jsonify({"error": "An unexpected error occurred"}), 500


# --- Message Routes ---

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


# --- Rota de Chat Principal (com MCP e Function Calling) ---
@chat_api_bp.route('/send', methods=['POST'])
async def chat(): # Função agora é async
    if 'user_id' not in session:
        return jsonify({"error": "Authentication required"}), 401

    user_id = session['user_id']
    original_user_message = request.form.get('message', '') # Garantir default ''
    uploaded_file_storage = request.files.get('file')

    if not original_user_message and not uploaded_file_storage:
        return jsonify({"error": "Missing 'message' or file in request"}), 400

    # --- Variáveis para o fluxo ---
    conversation_id = None
    is_new_conversation = False
    history_raw = []
    google_file_object = None
    local_filepath_to_remove = None
    bot_response_text = "Desculpe, ocorreu um erro inesperado." # Default error
    bot_response_image = None
    final_title = None
    user_msg_id = None
    error_message = None
    mcp_session_active = None # Para rastrear a sessão MCP

    try:
        # --- 1. Processar Upload (se houver) ---
        if uploaded_file_storage:
            local_filepath, mime_type, local_file_error = _process_uploaded_file(uploaded_file_storage)
            if local_file_error: return jsonify({"error": local_file_error}), 400
            local_filepath_to_remove = local_filepath # Marcar para remoção posterior

            if local_filepath and mime_type:
                google_file_object, google_upload_error = _upload_file_to_google(local_filepath, mime_type)
                if google_upload_error: return jsonify({"error": google_upload_error}), 500
                # Limpar arquivo local imediatamente após upload para Google bem-sucedido
                try:
                    if local_filepath_to_remove and os.path.exists(local_filepath_to_remove):
                        log.info(f"Removing local temporary file: {local_filepath_to_remove}")
                        os.remove(local_filepath_to_remove)
                        local_filepath_to_remove = None # Resetar após remoção
                except OSError as e:
                    log.warning(f"Could not remove local file {local_filepath_to_remove} after successful Google upload: {e}")
                    # Não resetar local_filepath_to_remove para tentar no finally

        # --- 2. Obter Contexto da Conversa ---
        conversation_id, is_new_conversation, history_raw, context_error = _get_or_create_conversation_context(user_id)
        if context_error:
             status_code = 500 if "create" in context_error else 404 # Ajustar status code
             return jsonify({"error": context_error}), status_code

        # Formatar histórico para Gemini (lista de dicts representando Content)
        gemini_history_contents = []
        for msg in history_raw:
             role = 'model' if msg['role'] == 'assistant' else msg['role']
             # Usar dict para parts
             parts = []
             if msg.get('content'): parts.append({'text': msg['content']})
             # TODO: Lidar com arquivos no histórico se necessário
             if parts:
                  # Usar dict em vez de objeto Content
                  gemini_history_contents.append({'role': role, 'parts': parts})

        # --- 3. Preparar Mensagem e Argumentos do Modelo ---
        message_base, model_args = _prepare_message_and_model_args(user_id, original_user_message)

        # --- 4. Conectar ao MCP e Obter Ferramentas ---
        gemini_tools = []
        async with stdio_client(mcp_server_params) as (read, write):
            async with ClientSession(read, write) as mcp_session:
                mcp_session_active = mcp_session # Guardar referência
                await mcp_session.initialize()
                log.info("Conectado ao servidor MCP.")
                mcp_tools_response = await mcp_session.list_tools()
                if mcp_tools_response and mcp_tools_response.tools:
                    for mcp_tool in mcp_tools_response.tools:
                        converted_tool = _convert_mcp_tool_to_gemini(mcp_tool)
                        if converted_tool:
                            gemini_tools.append(converted_tool)
                            log.info(f"Ferramenta MCP '{mcp_tool.name}' preparada para Gemini.")
                else:
                    log.warning("Nenhuma ferramenta encontrada no servidor MCP.")

                # --- 5. Preparar 'parts' e Configuração para Gemini ---
                current_message_parts = []
                if message_base:
                    current_message_parts.append({'text': message_base}) # Usar dict
                if google_file_object:
                    # Enviar como texto placeholder por enquanto
                    current_message_parts.append({'text': f"[Arquivo anexado: {google_file_object.display_name}]"}) # Usar dict
                    log.warning("Anexo de arquivo via referência não totalmente implementado/testado.")

                if not current_message_parts:
                     if google_file_object:
                          current_message_parts.append({'text': f"Analise o arquivo: {google_file_object.display_name}"}) # Usar dict
                     else:
                          return jsonify({"error": "Conteúdo da mensagem vazio."}), 400

                # Usar dict em vez de objeto Content
                current_content = {'role': "user", 'parts': current_message_parts}
                contents_to_send = gemini_history_contents + [current_content]

                generation_config = GenerationConfig() # Configuração padrão
                # Voltar para o modo padrão AUTO para permitir resposta textual após function call
                tool_config = {'function_calling_config': {'mode': 'AUTO'}}
                # log.info("Configurando Gemini para forçar chamada de função (mode: ANY).") # Remover log antigo

                # --- 6. Primeira Chamada ao Gemini ---
                log.info(f"Chamando Gemini com {len(gemini_tools)} ferramentas.")
                model = genai.GenerativeModel(
                    config.GEMINI_MODEL_NAME,
                    **model_args,
                    generation_config=generation_config,
                    tools=gemini_tools,
                    tool_config=tool_config # Passar tool_config aqui
                )

                response = await asyncio.to_thread(
                    model.generate_content,
                    contents=contents_to_send,
                )

                # --- 7. Lidar com Function Calling ---
                candidate = response.candidates[0]
                # A resposta pode não ter 'parts' se for bloqueada, etc.
                first_part = candidate.content.parts[0] if candidate.content and candidate.content.parts else None

                # Verificar se 'function_call' existe no objeto 'part'
                if first_part and hasattr(first_part, 'function_call') and first_part.function_call:
                    function_call = first_part.function_call
                    tool_name = function_call.name
                    tool_args = dict(function_call.args)
                    log.info(f"Gemini solicitou chamada de função: {tool_name} com args: {tool_args}")

                    tool_response_content = "Erro ao chamar a ferramenta."
                    try:
                        tool_result = await mcp_session_active.call_tool(tool_name, arguments=tool_args)
                        if tool_result.content and tool_result.content[0].text:
                            tool_response_content = _extract_serpapi_summary(tool_result.content[0].text)
                            log.info(f"Resumo extraído da ferramenta '{tool_name}': {tool_response_content[:100]}...")
                        else:
                            log.warning(f"Ferramenta MCP '{tool_name}' não retornou conteúdo de texto.")
                            tool_response_content = "A ferramenta foi chamada, mas não retornou informações."
                    except Exception as mcp_call_err:
                        log.error(f"Erro ao chamar ferramenta MCP '{tool_name}': {mcp_call_err}", exc_info=True)
                        tool_response_content = f"Erro ao executar a ferramenta '{tool_name}'."

                    # Preparar FunctionResponse para Gemini - Construir o dict esperado diretamente
                    function_response_part_dict = {
                        'function_response': {
                             'name': tool_name,
                             'response': {
                                 'result': tool_response_content
                             }
                        }
                    }

                    # Adicionar a chamada da IA e a resposta da ferramenta ao histórico
                    contents_for_next_call = contents_to_send + [
                        # Adicionar a resposta do modelo que continha a function_call (como dict)
                        {'role': candidate.content.role, 'parts': candidate.content.parts},
                        # Adicionar a resposta da ferramenta como um novo 'content' com role 'function' (como dict)
                        {'role': "function", 'parts': [function_response_part_dict]}
                    ]


                    log.info("Enviando resposta da função de volta ao Gemini.")
                    final_response = await asyncio.to_thread(
                        model.generate_content,
                        contents=contents_for_next_call, # Enviar histórico atualizado
                        tools=gemini_tools,
                        tool_config=tool_config
                    )

                    # Tentar extrair texto iterando pelas partes, em vez de usar .text diretamente
                    extracted_text = ""
                    try:
                        if final_response.candidates and final_response.candidates[0].content and final_response.candidates[0].content.parts:
                            for part in final_response.candidates[0].content.parts:
                                # Verificar se a parte tem o atributo 'text' antes de acessar
                                if hasattr(part, 'text'):
                                     extracted_text += part.text + "\n"
                        bot_response_text = extracted_text.strip() if extracted_text else None # Define como None se vazio

                        if not bot_response_text:
                             # Se não extraiu texto, verificar se houve erro/bloqueio
                             try:
                                  # Tentar acessar .prompt_feedback pode indicar bloqueio
                                  _ = final_response.prompt_feedback
                             except Exception as final_call_err:
                                  log.error(f"Erro/Bloqueio na segunda chamada Gemini após function call: {final_call_err}")
                                  bot_response_text = f"Houve um problema ao processar o resultado da ferramenta '{tool_name}'."
                                  error_message = f"Erro na segunda chamada Gemini: {final_call_err}"
                             else:
                                  # Se não houve erro mas não há texto, usar mensagem padrão
                                  bot_response_text = f"Ok, a ação '{tool_name}' foi executada."
                                  log.warning("Resposta final do Gemini após function call não continha texto.")

                    except Exception as text_extract_err:
                         # Erro ao tentar extrair texto das partes
                         log.error(f"Erro ao extrair texto da resposta final do Gemini: {text_extract_err}", exc_info=True)
                         bot_response_text = f"Houve um problema ao processar o resultado da ferramenta '{tool_name}'."
                         error_message = f"Erro ao processar resposta final Gemini: {text_extract_err}"


                    bot_response_image = None

                else:
                    # Nenhuma FunctionCall
                    # Tentar extrair texto iterando pelas partes
                    extracted_text = ""
                    try:
                        if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
                             for part in response.candidates[0].content.parts:
                                 if hasattr(part, 'text'):
                                      extracted_text += part.text + "\n"
                        bot_response_text = extracted_text.strip() if extracted_text else None

                        if not bot_response_text:
                             try:
                                  _ = response.prompt_feedback
                             except Exception as first_call_err:
                                  log.error(f"Erro/Bloqueio na primeira chamada Gemini: {first_call_err}")
                                  bot_response_text = "Desculpe, não consegui processar sua solicitação devido a um problema interno."
                                  error_message = f"Erro na primeira chamada Gemini: {first_call_err}"
                             else:
                                  bot_response_text = "Não consegui processar sua solicitação."
                                  log.warning("Resposta inicial do Gemini não continha texto nem function call.")
                    except Exception as text_extract_err:
                         log.error(f"Erro ao extrair texto da resposta inicial do Gemini: {text_extract_err}", exc_info=True)
                         bot_response_text = "Desculpe, ocorreu um erro ao processar a resposta inicial."
                         error_message = f"Erro ao processar resposta inicial Gemini: {text_extract_err}"


                    # Verificar se há imagem na primeira resposta
                    if first_part and hasattr(first_part, 'inline_data') and first_part.inline_data:
                         image_data = first_part.inline_data.data
                         mime_type = first_part.inline_data.mime_type
                         bot_response_image = f"data:{mime_type};base64,{base64.b64encode(image_data).decode('utf-8')}"
                         log.info(f"Recebida imagem na primeira resposta (MIME: {mime_type})")

    except Exception as e:
        log.error(f"Erro inesperado no fluxo principal do chat para user {user_id}: {e}", exc_info=True)
        error_message = f"Erro inesperado no servidor: {e}"
        # Tentar limpar arquivo do Google se foi criado
        if google_file_object:
            try: genai.delete_file(google_file_object.name)
            except Exception as del_err: log.error(f"Falha ao deletar arquivo Google {google_file_object.name} durante handling de erro: {del_err}")

    finally:
        # --- 8. Limpeza Final ---
        try:
            if local_filepath_to_remove and os.path.exists(local_filepath_to_remove):
                log.info(f"Removendo arquivo local temporário no finally: {local_filepath_to_remove}")
                os.remove(local_filepath_to_remove)
        except OSError as e:
            log.warning(f"Não foi possível remover arquivo temporário {local_filepath_to_remove} no finally: {e}")
        # A sessão MCP é fechada automaticamente pelo 'async with'

    # --- 9. Salvar Mensagens no DB ---
    if conversation_id:
        user_msg_to_save = original_user_message or (f"Arquivo: {google_file_object.display_name}" if google_file_object else "")
        # Salvar msg usuário
        saved_user_msg_id, db_save_error_user = _save_single_message(conversation_id, 'user', user_msg_to_save, google_file_object)
        if db_save_error_user:
             log.error(f"Falha ao salvar msg USUÁRIO no DB para conv {conversation_id}: {db_save_error_user}")
             error_message = f"{error_message}\n{db_save_error_user}" if error_message else db_save_error_user
        else:
             user_msg_id = saved_user_msg_id

        # Salvar msg assistente (se não for None)
        if bot_response_text is not None:
             _, db_save_error_assistant = _save_single_message(conversation_id, 'assistant', bot_response_text, None)
             if db_save_error_assistant:
                  log.error(f"Falha ao salvar msg ASSISTENTE no DB para conv {conversation_id}: {db_save_error_assistant}")
                  error_message = f"{error_message}\n{db_save_error_assistant}" if error_message else db_save_error_assistant
        else:
             log.warning(f"bot_response_text era None para conv {conversation_id}, não salvando resposta do assistente.")

    # --- 10. Gerar Título ---
    if conversation_id and is_new_conversation and user_msg_id:
         title_source = original_user_message or (f"Arquivo: {google_file_object.display_name}" if google_file_object else "Nova Conversa")
         final_title = _handle_new_conversation_title(
              is_new_conversation, conversation_id, user_id, user_msg_id, title_source
         )

    # --- 11. Preparar Resposta JSON Final ---
    response_data = {
        "response": bot_response_text,
        "conversation_id": conversation_id,
        "new_title": final_title if is_new_conversation else None,
        "image_data": bot_response_image
    }
    if error_message:
        response_data["error"] = error_message
        log.error(f"Retornando erro para o cliente: {error_message}")
        if not bot_response_text or bot_response_text == "Desculpe, ocorreu um erro inesperado.":
             response_data["response"] = f"Erro: {error_message}"
        return jsonify(response_data), 500

    return jsonify(response_data), 200