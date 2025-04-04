import * as ui from './ui_helpers.js';
import * as api from './api_client.js';
import * as convManager from './conversation_manager.js';
import * as settingsManager from './settings_manager.js';

document.addEventListener('DOMContentLoaded', () => {
    console.log("Main script loaded.");

    // --- Get Main Element References ---
    const chatBox = document.getElementById('chat-box');
    const userInput = document.getElementById('user-input');
    const sendButton = document.getElementById('send-button');
    const conversationList = document.getElementById('conversation-list');
    const newChatButton = document.getElementById('new-chat-button');
    const openSettingsButton = document.getElementById('open-settings-button');
    const settingsPopoverLevel1 = document.getElementById('settings-popover-level1');
    const settingsModalPlaceholder = document.getElementById('settings-modal-placeholder');
    const fontSelector = document.getElementById('font-selector'); // Added font selector
    const fontSizeSelector = document.getElementById('font-size-selector'); // New
    const lineSpacingSelector = document.getElementById('line-spacing-selector'); // New

    // --- Initialize Managers ---
    convManager.initConversationManager(conversationList, chatBox, userInput);
    settingsManager.initSettingsManager(settingsPopoverLevel1, settingsModalPlaceholder);

    // --- Main Send Message Logic ---
    async function handleSendMessage() {
        const messageText = userInput.value.trim();
        if (!messageText || !chatBox || !userInput) return;

        ui.addMessageToChatbox(messageText, 'user', chatBox);
        userInput.value = '';
        ui.addMessageToChatbox('...', 'bot', chatBox); // Typing indicator
        const typingIndicator = chatBox.lastChild;

        try {
            const data = await api.sendMessage(messageText); // API call

            if (typingIndicator && chatBox.contains(typingIndicator)) {
                chatBox.removeChild(typingIndicator);
            }

            ui.addMessageToChatbox(data.response, 'bot', chatBox); // Display bot response

            // If it was a new conversation, update state and UI
            if (data.new_conversation_id) {
                console.log(`Main: New conversation ${data.new_conversation_id} created.`);
                convManager.setCurrentConversationId(data.new_conversation_id);
                // No need to call set_active API here, backend handles it on creation
                await convManager.loadAndDisplayConversations(); // Reload list to show new one
                ui.setActiveConversationInSidebar(data.new_conversation_id, conversationList); // Highlight it
            }

        } catch (error) {
            console.error('Main: Error sending message:', error);
            if (typingIndicator && chatBox.contains(typingIndicator)) {
                chatBox.removeChild(typingIndicator);
            }
            // Display error in chatbox
            ui.addMessageToChatbox(`Error: ${error.message}`, 'system', chatBox);
        }
    }

    // --- Event Listeners ---

    // Send Button and Enter Key
    if (sendButton) sendButton.addEventListener('click', handleSendMessage);
    if (userInput) userInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') handleSendMessage();
    });

    // New Chat Button
    if (newChatButton) newChatButton.addEventListener('click', convManager.handleNewChat);

    // Settings Button (Level 1 Popover Toggle)
    if (openSettingsButton) {
        openSettingsButton.addEventListener('click', (e) => {
            e.stopPropagation(); // Prevent document click listener
            settingsManager.toggleSettingsPopoverLevel1();
        });
    }

    // Settings Popover (Level 1 Links - Logout or Open Modal)
    if (settingsPopoverLevel1) {
        settingsPopoverLevel1.addEventListener('click', (e) => {
            if (e.target.tagName === 'A') {
                const targetModal = e.target.dataset.targetModal;
                const targetTab = e.target.dataset.targetTab;

                // If it's a link to open the main settings modal
                if (targetModal === 'settings-modal-main') {
                    e.preventDefault();
                    settingsManager.toggleSettingsPopoverLevel1(); // Hide level 1
                    settingsManager.openSettingsModal(targetTab); // Open level 2
                }
                // Allow default behavior for other links (like the actual logout link)
            }
        });
    }

    // Conversation List Event Delegation
    if (conversationList) {
        conversationList.addEventListener('click', (e) => {
            const target = e.target;
            const listItem = target.closest('.conversation-item');
            if (!listItem) return; // Clicked outside a list item

            const conversationId = listItem.dataset.conversationId;
            const action = target.dataset.action || target.closest('[data-action]')?.dataset.action;

            console.log(`Action: ${action}, ConvID: ${conversationId}`); // Debugging

            if (action === 'select') {
                convManager.handleConversationSelect(conversationId);
            } else if (action === 'toggle-popover') {
                e.stopPropagation(); // Prevent closing immediately
                ui.toggleConversationActionsPopover(listItem);
            }
            // Popover actions (edit/delete) are handled via delegation on the body
        });
    }

    // Body Event Delegation for Conversation Popover Actions
    document.body.addEventListener('click', (e) => {
        const target = e.target;
        const popoverButton = target.closest('.actions-popover button[data-action]');
        if (popoverButton) {
            e.stopPropagation(); // Prevent other listeners
            const action = popoverButton.dataset.action;
            const conversationId = popoverButton.dataset.conversationId;
            if (!conversationId) {
                console.warn("Could not find conversation ID on popover button.");
                ui.hideAllPopovers(null, settingsPopoverLevel1); // Close popovers
                return;
            }

            // Find the corresponding list item using the conversation ID
            const listItem = conversationList?.querySelector(`.conversation-item[data-conversation-id="${conversationId}"]`);

            if (!listItem) {
                console.warn(`Could not find list item for conversation ID: ${conversationId}`);
                ui.hideAllPopovers(null, settingsPopoverLevel1); // Close popovers
                return;
            }

            console.log(`Popover Action: ${action}, ConvID: ${conversationId}`); // Debugging

            if (action === 'edit') {
                convManager.handleEditConversation(listItem);
            } else if (action === 'delete') {
                convManager.handleDeleteConversation(listItem);
            }

            ui.hideAllPopovers(null, settingsPopoverLevel1); // Close popovers after action
        }
    });


    // Global Click Listener to Hide Popovers
    document.addEventListener('click', (e) => {
        // Pass the event and settings popover element to the helper
        ui.hideAllPopovers(e, settingsPopoverLevel1);
    });

    // Font Selector Logic
    if (fontSelector) {
        fontSelector.addEventListener('change', (e) => {
            const selectedFont = e.target.value;
            document.body.style.fontFamily = selectedFont;
            console.log(`Font changed to: ${selectedFont}`);
            // TODO: Implement dynamic loading for Google Fonts if needed
            // Example: Check if font needs loading and add a <link> element to <head>
        });

        // Optional: Apply initial font from selector if it's not the default
        // This could also be handled by setting the default font in base.css
        // document.body.style.fontFamily = fontSelector.value;
    }

    // Font Size Selector Logic
    if (fontSizeSelector) {
        fontSizeSelector.addEventListener('change', (e) => {
            const selectedSize = e.target.value;
            document.body.style.fontSize = selectedSize;
            console.log(`Font size changed to: ${selectedSize}`);
            // Optional: Save this preference (e.g., localStorage or backend)
        });
        // Optional: Apply initial size
        // document.body.style.fontSize = fontSizeSelector.value;
    }

    // Line Spacing Selector Logic
    if (lineSpacingSelector) {
        lineSpacingSelector.addEventListener('change', (e) => {
            const selectedSpacing = e.target.value;
            if (chatBox) chatBox.style.setProperty('--chat-line-height', selectedSpacing); // Use CSS variable
            console.log(`CSS variable --chat-line-height set to: ${selectedSpacing}`);
            // Optional: Save this preference
        });
        // Optional: Apply initial spacing
        // document.body.style.lineHeight = lineSpacingSelector.value; // Old way
        // Apply initial spacing to chatBox
        if (chatBox) chatBox.style.setProperty('--chat-line-height', lineSpacingSelector.value); // Use CSS variable
    }


    // --- Initialization ---
    console.log("Initializing conversation list...");
    convManager.loadAndDisplayConversations();

}); // End DOMContentLoaded