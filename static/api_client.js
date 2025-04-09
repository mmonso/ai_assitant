// --- API Client Functions ---

/**
 * Fetches the list of conversations and folders from the backend.
 * @returns {Promise<{conversations: Array, folders: Array}>} A promise that resolves with an object containing lists of conversations and folders.
 * @throws {Error} If the fetch fails or the response is not ok.
 */
export async function loadConversationList() {
    console.log("API: Loading conversation list...");
    const response = await fetch('/api/chat/list');
    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }
    const data = await response.json();
    // Return both conversations and folders, defaulting to empty arrays if missing
    return {
        conversations: data.conversations || [],
        folders: data.folders || []
    };
}

/**
 * Fetches messages for a specific conversation.
 * @param {string} conversationId - The ID of the conversation.
 * @returns {Promise<Array>} A promise that resolves with the list of messages.
 * @throws {Error} If the fetch fails, response is not ok, or conversation not found/access denied.
 */
export async function loadConversationMessages(conversationId) {
    console.log(`API: Loading messages for conversation: ${conversationId}`);
    const response = await fetch(`/api/chat/messages?conversation_id=${conversationId}`);
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({})); // Try to get error details
        const message = errorData.error || `HTTP error! status: ${response.status}`;
        throw new Error(message); // Throw specific error from backend if available
    }
    const data = await response.json();
    return data.messages || []; // Return messages or empty array
}

/**
 * Sends a user message and/or file to the backend and gets the bot's response.
 * Handles creation of new conversations if necessary.
 * @param {FormData} formData - The FormData object containing the message text and/or file.
 * @returns {Promise<object>} A promise that resolves with the response data (including 'response' and potentially 'new_conversation_id').
 * @throws {Error} If the fetch fails or the backend returns an error.
 */
export async function sendMessage(formData) { // Changed parameter to formData
    console.log("API: Sending message/file...");
    const response = await fetch('/api/chat/send', {
        method: 'POST',
        // Remove 'Content-Type' header; browser sets it for FormData
        body: formData, // Send FormData directly
    });

    if (!response.ok) {
        let errorMsg = `Error: ${response.status}`;
        try { errorMsg = (await response.json()).error || errorMsg; } catch (e) {}
        throw new Error(errorMsg);
    }

    const data = await response.json();
    if (data.error) { // Check for application-level errors returned in JSON
        throw new Error(data.error);
    }
    // Contains { response, new_conversation_id?, new_conversation_title?, new_conversation_folder_id? }
    return data;
}

/**
 * Tells the backend to set the currently active conversation in the session.
 * @param {string} conversationId - The ID of the conversation to set as active.
 * @returns {Promise<object>} A promise that resolves with the success message.
 * @throws {Error} If the fetch fails or the backend returns an error.
 */
export async function setActiveConversation(conversationId) {
    console.log(`API: Setting active conversation to ${conversationId}`);
    const response = await fetch('/api/chat/set_active', {
         method: 'POST',
         headers: { 'Content-Type': 'application/json' },
         body: JSON.stringify({ conversation_id: conversationId }),
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || "Failed to set active conversation on backend");
    }
    return await response.json();
}

/**
 * Tells the backend to prepare for a new conversation (clears session state).
 * @returns {Promise<object>} A promise that resolves with the success message.
 * @throws {Error} If the fetch fails or the backend returns an error.
 */
export async function startNewConversation() {
    console.log("API: Signaling start of new conversation...");
     const response = await fetch('/api/chat/start_new', { method: 'POST' });
     if (!response.ok) {
         const errorData = await response.json().catch(() => ({}));
         throw new Error(errorData.error || "Failed to signal new conversation to backend");
     }
     return await response.json();
}

/**
 * Renames a conversation via the API.
 * @param {string} conversationId - The ID of the conversation to rename.
 * @param {string} newTitle - The desired new title.
 * @returns {Promise<object>} A promise that resolves with the success message.
 * @throws {Error} If the fetch fails or the backend returns an error.
 */
export async function renameConversation(conversationId, newTitle) {
    console.log(`API: Renaming conversation ${conversationId} to "${newTitle}"`);
    const response = await fetch(`/api/chat/rename/${conversationId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: newTitle }),
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `Failed to rename conversation: ${response.statusText}`);
    }
    return await response.json();
}

/**
 * Deletes a conversation via the API.
 * @param {string} conversationId - The ID of the conversation to delete.
 * @returns {Promise<object>} A promise that resolves with the success message.
 * @throws {Error} If the fetch fails or the backend returns an error.
 */
export async function deleteConversation(conversationId) {
    console.log(`API: Deleting conversation ${conversationId}`);
    const response = await fetch(`/api/chat/delete/${conversationId}`, { method: 'DELETE' });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `Failed to delete conversation: ${response.statusText}`);
    }
    return await response.json();
}


// --- Folder API Functions ---

/**
 * Creates a new folder via the API.
 * @param {string} name - The desired name for the new folder.
 * @returns {Promise<object>} A promise that resolves with the success message and new folder details.
 * @throws {Error} If the fetch fails or the backend returns an error (e.g., duplicate name).
 */
export async function createFolder(name) {
    console.log(`API: Creating folder "${name}"`);
    const response = await fetch(`/api/chat/folders`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: name }),
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `Failed to create folder: ${response.statusText}`);
    }
    return await response.json(); // Returns { message, folder_id, name }
}

/**
 * Renames a folder via the API.
 * @param {string|number} folderId - The ID of the folder to rename.
 * @param {string} newName - The desired new name.
 * @returns {Promise<object>} A promise that resolves with the success message.
 * @throws {Error} If the fetch fails or the backend returns an error.
 */
export async function renameFolder(folderId, newName) {
    console.log(`API: Renaming folder ${folderId} to "${newName}"`);
    const response = await fetch(`/api/chat/folders/${folderId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newName }),
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `Failed to rename folder: ${response.statusText}`);
    }
    return await response.json();
}

/**
 * Deletes a folder via the API.
 * @param {string|number} folderId - The ID of the folder to delete.
 * @returns {Promise<object>} A promise that resolves with the success message.
 * @throws {Error} If the fetch fails or the backend returns an error.
 */
export async function deleteFolder(folderId) {
    console.log(`API: Deleting folder ${folderId}`);
    const response = await fetch(`/api/chat/folders/${folderId}`, { method: 'DELETE' });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `Failed to delete folder: ${response.statusText}`);
    }
    return await response.json();
}

/**
 * Moves a conversation to a specific folder (or removes it from folders).
 * @param {string|number} conversationId - The ID of the conversation to move.
 * @param {string|number|null} folderId - The ID of the target folder, or null to remove from any folder.
 * @returns {Promise<object>} A promise that resolves with the success message.
 * @throws {Error} If the fetch fails or the backend returns an error.
 */
export async function moveConversationToFolder(conversationId, folderId) {
    console.log(`API: Moving conversation ${conversationId} to folder ${folderId}`);
    const response = await fetch(`/api/chat/conversations/${conversationId}/move`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ folder_id: folderId }), // Send null if folderId is null
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `Failed to move conversation: ${response.statusText}`);
    }
    return await response.json();
}


// --- Settings Related API Functions ---

/**
 * Fetches the settings modal HTML partial.
 * @returns {Promise<string>} A promise that resolves with the HTML string.
 * @throws {Error} If the fetch fails or the response is not ok.
 */
export async function fetchSettingsModalHtml() {
    console.log("API: Fetching settings modal HTML...");
    const response = await fetch('/get_settings_modal'); // Endpoint from main blueprint
    if (!response.ok) {
        throw new Error(`HTTP error fetching modal! status: ${response.status}`);
    }
    return await response.text();
}

/**
 * Fetches user details and config needed for settings modal population.
 * @returns {Promise<object>} A promise that resolves with { user, config }.
 * @throws {Error} If the fetch fails or the response is not ok.
 */
export async function fetchUserSettingsData() {
    console.log("API: Fetching user settings data...");
    const response = await fetch('/api/settings/get_user_settings');
    if (!response.ok) {
        throw new Error(`HTTP error fetching settings data! status: ${response.status}`);
    }
    return await response.json(); // Should return { user: {...}, config: {...} }
}

// Note: Functions from settings.js (updateProfile, changePassword, deleteAccount)
// are NOT moved here as they are directly tied to form submissions within settings.js.
// However, settings.js *could* be refactored to import and use functions from here
// if we wanted to centralize all fetch calls. For now, keeping them separate is acceptable.


/**
 * Fetches the currently selected model and available models from the backend session.
 * @returns {Promise<object>} A promise resolving to { selected_model: string, available_models: string[] }.
 * @throws {Error} If the fetch fails or the backend returns an error.
 */
export async function getSelectedModel() {
    console.log("API: Getting selected model...");
    const response = await fetch('/api/settings/get_selected_model');
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || "Failed to get selected model");
    }
    return await response.json();
}

/**
 * Sets the selected model in the backend session.
 * @param {string} modelName - The name of the model to select.
 * @returns {Promise<object>} A promise resolving to the success message.
 * @throws {Error} If the fetch fails or the backend returns an error.
 */
export async function setSelectedModel(modelName) {
    console.log(`API: Setting selected model to ${modelName}`);
    const response = await fetch('/api/settings/set_selected_model', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model_name: modelName }),
    });
     if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || "Failed to set selected model");
    }
    return await response.json();
}