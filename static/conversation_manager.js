import * as apiClient from './api_client.js';
import * as uiHelpers from './ui_helpers.js';

// --- State ---
let currentConversationId = null;
let conversationListElement = null; // Reference to the <ul> element
let chatBoxElement = null; // Reference to the chatbox div
let userInputElement = null; // Reference to the user input field

/**
 * Initializes the conversation manager with necessary DOM elements.
 * @param {HTMLElement} convListEl - The <ul> element for the conversation list.
 * @param {HTMLElement} chatBoxEl - The chatbox <div> element.
 * @param {HTMLElement} userInputEl - The user input <input> element.
 */
export function initConversationManager(convListEl, chatBoxEl, userInputEl) {
    conversationListElement = convListEl;
    chatBoxElement = chatBoxEl;
    userInputElement = userInputEl;
    // Load initial state or list if needed (can also be done in main script)
    // loadAndDisplayConversations(); // Example
}

/**
 * Sets the current active conversation ID.
 * @param {string | null} id - The new conversation ID, or null.
 */
export function setCurrentConversationId(id) {
    currentConversationId = id;
}

/**
 * Gets the current active conversation ID.
 * @returns {string | null} The current conversation ID.
 */
export function getCurrentConversationId() {
    return currentConversationId;
}

/**
 * Loads the conversation list from the API and displays it using uiHelpers.
 */
export async function loadAndDisplayConversations() {
    if (!conversationListElement || !chatBoxElement) return;
    console.log("Manager: Loading and displaying conversations...");
    try {
        const conversations = await apiClient.loadConversationList();
        uiHelpers.displayConversations(conversations, conversationListElement, currentConversationId);
    } catch (error) {
        console.error('Manager: Failed to load conversation list:', error);
        uiHelpers.addMessageToChatbox('Could not load conversation list.', 'system', chatBoxElement);
        uiHelpers.displayConversations([], conversationListElement, currentConversationId); // Display empty state
    }
}

/**
 * Handles the selection of a conversation.
 * @param {string} conversationId - The ID of the conversation to select.
 */
export async function handleConversationSelect(conversationId) {
    if (!chatBoxElement || !conversationListElement) return;
    if (conversationId === currentConversationId) return; // Already selected
    console.log(`Manager: Switching to conversation: ${conversationId}`);
    uiHelpers.clearChatbox(chatBoxElement);
    uiHelpers.addMessageToChatbox('Loading messages...', 'system', chatBoxElement);
    const loadingIndicator = chatBoxElement.lastChild;

    try {
        await apiClient.setActiveConversation(conversationId); // Tell backend
        const messages = await apiClient.loadConversationMessages(conversationId); // Fetch messages

        if (loadingIndicator && chatBoxElement.contains(loadingIndicator)) {
            chatBoxElement.removeChild(loadingIndicator);
        }

        messages.forEach(message => {
            const sender = message.role === 'assistant' ? 'bot' : message.role;
            uiHelpers.addMessageToChatbox(message.content, sender, chatBoxElement);
        });
        setCurrentConversationId(conversationId);
        uiHelpers.setActiveConversationInSidebar(conversationId, conversationListElement);

    } catch(error) {
         if (loadingIndicator && chatBoxElement.contains(loadingIndicator)) {
            chatBoxElement.removeChild(loadingIndicator);
         }
         console.error("Manager: Error setting/loading active conversation:", error);
         uiHelpers.addMessageToChatbox(`Failed to switch conversation: ${error.message}`, 'system', chatBoxElement);
         setCurrentConversationId(null); // Reset if switch failed
         uiHelpers.setActiveConversationInSidebar(null, conversationListElement);
    }
}

/**
 * Handles the initiation of editing a conversation title.
 * @param {HTMLElement} listItem - The list item element being edited.
 */
export function handleEditConversation(listItem) {
    if (!listItem || !chatBoxElement) return;
    const titleSpan = listItem.querySelector('.conversation-title');
    const conversationId = listItem.dataset.conversationId;
    if (!titleSpan || !conversationId) return;

    listItem.classList.add('editing');
    const currentTitle = titleSpan.textContent;
    const input = document.createElement('input');
    input.type = 'text';
    input.value = currentTitle;
    input.classList.add('edit-conversation-input');
    titleSpan.replaceWith(input);
    input.focus();
    input.select();

    const saveChanges = async () => {
        const newTitle = input.value.trim();
        listItem.classList.remove('editing'); // Remove editing class regardless of outcome

        // Restore original if title is empty or unchanged
        if (!newTitle || newTitle === currentTitle) {
            input.replaceWith(titleSpan); // Put the original span back
            titleSpan.textContent = currentTitle; // Ensure text is correct
            return;
        }

        // Optimistically update UI
        titleSpan.textContent = newTitle;
        input.replaceWith(titleSpan);

        // Attempt to save to backend
        try {
            await apiClient.renameConversation(conversationId, newTitle);
            console.log(`Manager: Conversation ${conversationId} renamed to "${newTitle}"`);
        } catch (error) {
            console.error("Manager: Error renaming conversation:", error);
            // Revert UI on error
            titleSpan.textContent = currentTitle;
            uiHelpers.addMessageToChatbox(`Error renaming conversation: ${error.message}`, 'system', chatBoxElement);
        }
    };

    // Use 'blur' and 'keydown' listeners for saving or canceling
    input.addEventListener('blur', saveChanges, { once: true }); // Save on blur
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            input.blur(); // Trigger blur to save
        } else if (e.key === 'Escape') {
            listItem.classList.remove('editing');
            input.replaceWith(titleSpan); // Put original span back
            titleSpan.textContent = currentTitle; // Restore original text
            // Remove the blur listener to prevent saving on escape->blur
            input.removeEventListener('blur', saveChanges);
        }
    });
}

/**
 * Handles the deletion of a conversation.
 * @param {HTMLElement} listItem - The list item element to delete.
 */
export async function handleDeleteConversation(listItem) {
     if (!listItem || !chatBoxElement || !conversationListElement || !userInputElement) return;
     const conversationId = listItem.dataset.conversationId;
     const conversationTitle = listItem.querySelector('.conversation-title')?.textContent || `Conversation ${conversationId}`;
     if (!conversationId) return;

    if (!confirm(`Are you sure you want to delete "${conversationTitle}"?\nThis action cannot be undone.`)) {
        return;
    }

    console.log(`Manager: Attempting to delete conversation: ${conversationId}`);
    try {
        await apiClient.deleteConversation(conversationId);
        console.log(`Manager: Conversation ${conversationId} deleted.`);
        listItem.remove(); // Remove from UI

        // If the deleted conversation was the active one, start a new chat
        if (currentConversationId === conversationId) {
            await handleNewChat(); // Use the new chat handler
        }
        // Check if list is now empty
        if (conversationListElement.children.length === 0) {
            uiHelpers.displayConversations([], conversationListElement, null); // Show empty state
        }
    } catch (error) {
        console.error("Manager: Error deleting conversation:", error);
        uiHelpers.addMessageToChatbox(`Error deleting conversation: ${error.message}`, 'system', chatBoxElement);
    }
}

/**
 * Handles starting a new chat session.
 */
export async function handleNewChat() {
    if (!chatBoxElement || !conversationListElement || !userInputElement) return;
    console.log("Manager: Starting new chat...");
    try {
         await apiClient.startNewConversation(); // Signal backend
         setCurrentConversationId(null);
         uiHelpers.clearChatbox(chatBoxElement);
         uiHelpers.setActiveConversationInSidebar(null, conversationListElement);
         userInputElement.focus();
    } catch (error) {
         console.error("Manager: Error starting new chat:", error);
         uiHelpers.addMessageToChatbox(`Error starting new chat: ${error.message}`, 'system', chatBoxElement);
    }
}