import * as ui from './ui_helpers.js';
import * as api from './api_client.js';
import * as convManager from './conversation_manager.js';
import * as settingsManager from './settings_manager.js';

document.addEventListener('DOMContentLoaded', async () => { // Make async
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
    // const fontSizeSelector = document.getElementById('font-size-selector'); // Moved to settings_manager
    // const lineSpacingSelector = document.getElementById('line-spacing-selector'); // Moved to settings_manager
    const sidebarSpinner = document.getElementById('sidebar-loading-spinner'); // Added spinner reference
    const sidebarToggleButton = document.getElementById('sidebar-toggle-button'); // Added sidebar toggle button reference
    const sidebar = document.getElementById('sidebar'); // Added sidebar reference
    const sidebarOverlay = document.querySelector('.sidebar-overlay'); // Added overlay reference

    // --- Initialize Managers ---
    convManager.initConversationManager(conversationList, chatBox, userInput);
    settingsManager.initSettingsManager(settingsPopoverLevel1, settingsModalPlaceholder);

    // --- Main Send Message Logic ---
    async function handleSendMessage(fromEnterKey = false) { // Added flag
        const messageText = userInput.value.trim();
        if (!messageText || !chatBox || !userInput) return;

        ui.addMessageToChatbox(messageText, 'user', chatBox);
        userInput.value = '';

        // Reset textarea height after sending if sent via Enter key
        if (fromEnterKey) {
            resetTextareaHeight(userInput);
        }
        // Disable input while processing
        ui.disableElement(userInput);
        // Optional: Show spinner on send button if it existed
        // if (sendButton) ui.showSpinner(sendButton, true);

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
        } finally {
            // Re-enable input regardless of success or failure
            ui.enableElement(userInput);
            // Optional: Hide spinner on send button if it existed
            // if (sendButton) ui.hideSpinner(sendButton, 'Send'); // Assuming 'Send' was original text
        }
    }

    // --- Event Listeners ---

    // Auto-resize Textarea
    function autoResizeTextarea(textarea) {
        // Temporarily reset height to calculate scrollHeight accurately
        textarea.style.height = 'auto';
        // Set height based on content, respecting max-height from CSS
        textarea.style.height = textarea.scrollHeight + 'px';
    }

    // Reset Textarea Height (e.g., after sending)
    function resetTextareaHeight(textarea) {
        textarea.style.height = 'auto'; // Let CSS determine initial height based on rows=1
    }

    if (userInput) {
        userInput.addEventListener('input', () => {
            autoResizeTextarea(userInput);
        });
    }

    // Send Button and Enter Key
    // if (sendButton) sendButton.addEventListener('click', handleSendMessage); // Listener removed as button is removed
    if (userInput) {
        userInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault(); // Prevent newline in textarea
                handleSendMessage(true); // Pass flag indicating sent via Enter
            }
            // Shift+Enter will naturally add a newline and trigger the 'input' event for resizing
        });
    }

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

    // Theme selector logic (font, size, spacing) moved to settings_manager.js

    // Sidebar Toggle Logic for Mobile
    if (sidebarToggleButton && sidebar && sidebarOverlay) {
        const toggleSidebar = () => {
            const isVisible = sidebar.classList.toggle('sidebar-mobile-visible');
            sidebarOverlay.classList.toggle('active', isVisible); // Sync overlay with sidebar
            sidebarToggleButton.setAttribute('aria-expanded', isVisible);
        };

        sidebarToggleButton.addEventListener('click', (e) => {
            e.stopPropagation(); // Prevent triggering document click listener immediately
            toggleSidebar();
        });

        sidebarOverlay.addEventListener('click', () => {
            if (sidebar.classList.contains('sidebar-mobile-visible')) {
                toggleSidebar(); // Close sidebar if overlay is clicked
            }
        });

        // Close sidebar if user clicks outside of it on mobile (but not on the toggle button)
        document.addEventListener('click', (e) => {
             if (window.innerWidth <= 768 && // Only on mobile view
                 sidebar.classList.contains('sidebar-mobile-visible') &&
                 !sidebar.contains(e.target) &&
                 e.target !== sidebarToggleButton &&
                 !sidebarToggleButton.contains(e.target))
             {
                 toggleSidebar();
             }
         });
    } else {
        console.warn("Sidebar toggle button, sidebar, or overlay element not found.");
    }

    // --- Initialization ---
    console.log("Initializing conversation list...");
    if (sidebarSpinner) sidebarSpinner.style.display = 'flex'; // Ensure spinner is visible initially (flex for centering)

    try {
        await convManager.loadAndDisplayConversations(); // Wait for conversations to load
        console.log("Conversation list initialized.");
    } catch (error) {
        console.error("Error initializing conversation list:", error);
        // Optionally display an error message to the user in the sidebar
        if (conversationList) {
             const errorItem = document.createElement('li');
             errorItem.textContent = 'Error loading conversations.';
             errorItem.style.color = 'red'; // Basic styling
             conversationList.appendChild(errorItem);
        }
    } finally {
        // Hide spinner regardless of success or error
        if (sidebarSpinner) sidebarSpinner.style.display = 'none';
        console.log("Finished conversation list initialization attempt.");
    }

}); // End DOMContentLoaded