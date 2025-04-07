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
    // Optional: Show a spinner somewhere global or in the sidebar header?
    // uiHelpers.showSpinner(sidebarHeaderElement); // Example
    try {
        // Disable new chat button while loading
        const newChatBtn = document.getElementById('new-chat-button');
        uiHelpers.disableElement(newChatBtn);

        const conversations = await apiClient.loadConversationList();
        uiHelpers.displayConversations(conversations, conversationListElement, currentConversationId);

        // Re-enable button after loading
        uiHelpers.enableElement(newChatBtn);
    } catch (error) {
        // Use the new helper to display a user-friendly message and log the error
        uiHelpers.displayErrorInChat('Oops! Não foi possível carregar suas conversas. Tente recarregar a página.', error, chatBoxElement);
        uiHelpers.displayConversations([], conversationListElement, currentConversationId); // Display empty state
    } finally {
        // Optional: Hide global/sidebar spinner
        // uiHelpers.hideSpinner(sidebarHeaderElement);
        // Ensure button is enabled even if there was an error
        const newChatBtn = document.getElementById('new-chat-button');
        uiHelpers.enableElement(newChatBtn);
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
    // No explicit loading indicator here anymore, as per user feedback
    // uiHelpers.addMessageToChatbox('Loading messages...', 'system', chatBoxElement);
    // const loadingIndicator = chatBoxElement.lastChild;

    try { // <-- Início do try
        await apiClient.setActiveConversation(conversationId); // Tell backend
        const messages = await apiClient.loadConversationMessages(conversationId); // Fetch messages

        // Remove potential old indicator if logic changes back
        // if (loadingIndicator && chatBoxElement.contains(loadingIndicator)) {
        //     chatBoxElement.removeChild(loadingIndicator);
        // }

        messages.forEach(message => {
            const sender = message.role === 'assistant' ? 'bot' : message.role;
            uiHelpers.addMessageToChatbox(message.content, sender, chatBoxElement);
        });
        setCurrentConversationId(conversationId);
        uiHelpers.setActiveConversationInSidebar(conversationId, conversationListElement);

    } catch(error) { // <-- Fim do try, início do catch
         // Remove potential old indicator on error
         // if (loadingIndicator && chatBoxElement.contains(loadingIndicator)) {
         //    chatBoxElement.removeChild(loadingIndicator);
         // }
         // Use the new helper
         uiHelpers.displayErrorInChat('Erro ao carregar a conversa selecionada. Por favor, tente novamente.', error, chatBoxElement);
         setCurrentConversationId(null); // Reset if switch failed
         uiHelpers.setActiveConversationInSidebar(null, conversationListElement);
    } // <-- Fim do catch
} // <-- Fim da função

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
        // Add visual feedback: disable input and show spinner
        uiHelpers.disableElement(input); // Use helper for disabling
        uiHelpers.addSpinnerAdjacent(input, 'after'); // Show spinner next to input
        try {
            await apiClient.renameConversation(conversationId, newTitle);
            console.log(`Manager: Conversation ${conversationId} renamed to "${newTitle}"`);
            // Success: UI already updated optimistically
        } catch (error) {
            // Revert UI on error first
            titleSpan.textContent = currentTitle;
            // Use the new helper
            uiHelpers.displayErrorInChat('Não foi possível renomear a conversa. Por favor, tente novamente.', error, chatBoxElement);
        } finally {
             // Always remove spinner and re-enable input (though it gets replaced)
             uiHelpers.removeAdjacentSpinner(input);
             uiHelpers.enableElement(input); // Re-enable in case it wasn't replaced
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
    // Optional: Add visual feedback (e.g., dim the list item, show spinner)
    listItem.style.opacity = '0.5';
    listItem.style.pointerEvents = 'none'; // Prevent further interaction
    try {
        await apiClient.deleteConversation(conversationId);
        console.log(`Manager: Conversation ${conversationId} deleted.`);
        listItem.remove(); // Remove from UI on success

        // If the deleted conversation was the active one, start a new chat
        if (currentConversationId === conversationId) {
            await handleNewChat(); // Use the new chat handler
        }
        // Check if list is now empty
        if (conversationListElement.children.length === 0) {
            uiHelpers.displayConversations([], conversationListElement, null); // Show empty state
        }
    } catch (error) {
        // Use the new helper
        uiHelpers.displayErrorInChat('Erro ao excluir a conversa. Por favor, tente novamente.', error, chatBoxElement);
        // Restore item appearance on error
        listItem.style.opacity = '1';
        listItem.style.pointerEvents = 'auto';
    }
}

/**
 * Handles starting a new chat session.
 */
export async function handleNewChat() {
    if (!chatBoxElement || !conversationListElement || !userInputElement) return;
    console.log("Manager: Starting new chat...");
    // Optional: Disable New Chat button briefly
    const newChatBtn = document.getElementById('new-chat-button');
    uiHelpers.disableElement(newChatBtn);
    try {
         await apiClient.startNewConversation(); // Signal backend
         setCurrentConversationId(null);
         uiHelpers.clearChatbox(chatBoxElement);
         uiHelpers.setActiveConversationInSidebar(null, conversationListElement);
         userInputElement.focus();
         // Reset textarea height
         userInputElement.style.height = 'auto';
    } catch (error) {
         // Use the new helper
         uiHelpers.displayErrorInChat('Não foi possível iniciar uma nova conversa. Por favor, tente novamente.', error, chatBoxElement);
    } finally {
        // Re-enable New Chat button
        uiHelpers.enableElement(newChatBtn);
    }
}