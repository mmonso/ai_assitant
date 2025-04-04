// --- UI Helper Functions ---

// For syntax highlighting and sanitization (assuming libraries are loaded globally)
const marked = window.marked;
const DOMPurify = window.DOMPurify;
const hljs = window.hljs;

/**
 * Adds a message to the chatbox UI.
 * @param {string} message - The message content (text or markdown).
 * @param {string} sender - 'user', 'bot', or 'system'.
 * @param {HTMLElement} chatBox - The chatbox DOM element.
 */
export function addMessageToChatbox(message, sender, chatBox) {
    if (!chatBox) return;
    const messageElement = document.createElement('div');
    messageElement.classList.add('message', `${sender}-message`);

    if (sender === 'bot' && marked && DOMPurify && hljs) {
        try {
            const rawHtml = marked.parse(message, { gfm: true, breaks: true });
            const cleanHtml = DOMPurify.sanitize(rawHtml);
            messageElement.innerHTML = cleanHtml;
            messageElement.querySelectorAll('pre code').forEach((block) => {
                hljs.highlightElement(block);
            });
        } catch (e) {
            console.error("Error parsing/highlighting markdown:", e);
            messageElement.textContent = message; // Fallback to text
        }
    } else {
        messageElement.textContent = message;
    }
    chatBox.appendChild(messageElement);
    chatBox.scrollTop = chatBox.scrollHeight; // Auto-scroll
}

/**
 * Clears all messages from the chatbox UI.
 * @param {HTMLElement} chatBox - The chatbox DOM element.
 */
export function clearChatbox(chatBox) {
    if (chatBox) {
        chatBox.innerHTML = '';
    }
}

/**
 * Highlights the active conversation in the sidebar.
 * @param {string | null} conversationId - The ID of the conversation to activate, or null.
 * @param {HTMLElement} conversationListElement - The conversation list DOM element.
 */
export function setActiveConversationInSidebar(conversationId, conversationListElement) {
    if (!conversationListElement) return;
    conversationListElement.querySelectorAll('li').forEach(item => {
        item.classList.remove('active', 'editing'); // Remove editing class too
        if (item.dataset.conversationId === conversationId) {
            item.classList.add('active');
        }
    });
}

/**
 * Hides all currently visible popovers (conversation actions and settings level 1).
 * @param {Event | null} event - The click event that triggered the check (optional).
 * @param {HTMLElement | null} settingsPopoverLevel1 - The settings popover element.
 */
export function hideAllPopovers(event, settingsPopoverLevel1) {
    let clickedInsidePopover = false;
    let clickedOnActionsButton = false;
    let clickedOnGearButton = false;

    if (event) {
        clickedInsidePopover = event.target.closest('.actions-popover, .settings-popover');
        clickedOnActionsButton = event.target.closest('.conversation-actions-button');
        clickedOnGearButton = event.target.closest('#open-settings-button');
    }

    // Hide Conversation Actions Popovers attached to body
    const visibleConvPopovers = document.querySelectorAll('body > .actions-popover.visible');
    visibleConvPopovers.forEach(popover => {
        // A simple check: if the click wasn't inside *any* popover, hide.
        // More robust check would involve tracking the owner button.
        if (!clickedInsidePopover) {
             popover.remove();
        }
    });

    // Hide Settings Level 1 Popover
    if (settingsPopoverLevel1 && settingsPopoverLevel1.classList.contains('visible')) {
        if (!clickedInsidePopover && !clickedOnGearButton) {
            settingsPopoverLevel1.classList.remove('visible');
            settingsPopoverLevel1.style.display = 'none';
        }
    }
}


/**
 * Toggles the visibility and position of a conversation item's action popover.
 * @param {HTMLElement} listItem - The conversation list item element.
 */
export function toggleConversationActionsPopover(listItem) {
    const popover = listItem._popoverElement; // Assumes popover HTML is stored here
    if (!popover) return;

    const button = listItem.querySelector('.conversation-actions-button');
    const currentlyVisiblePopover = document.querySelector('body > .actions-popover.visible');

    // If this popover is already visible, hide and remove it
    if (currentlyVisiblePopover === popover) {
        popover.remove();
        return;
    }
    // If another popover is visible, hide and remove it first
    if (currentlyVisiblePopover) {
        currentlyVisiblePopover.remove();
    }

    // Append the new popover to the body and calculate position
    document.body.appendChild(popover);
    popover.classList.add('visible'); // Make visible before measuring

    const btnRect = button.getBoundingClientRect();
    const popoverRect = popover.getBoundingClientRect(); // Measure after visible
    const buffer = 4; // Gap between button and popover
    let top = btnRect.bottom + window.scrollY + buffer; // Add scrollY for correct positioning in body
    let left = btnRect.left + window.scrollX; // Add scrollX

    // Adjust if it goes off-screen BOTTOM
    if (top + popoverRect.height > window.innerHeight + window.scrollY - buffer) {
        top = btnRect.top + window.scrollY - popoverRect.height - buffer; // Try placing ABOVE instead
        if (top < window.scrollY + buffer) top = window.scrollY + buffer; // Place near top edge as last resort
    }
    // Adjust if it goes off-screen right
    if (left + popoverRect.width > window.innerWidth + window.scrollX) {
        left = window.innerWidth + window.scrollX - popoverRect.width - 5; // Position from right edge
    }
     // Adjust if it goes off-screen left
    if (left < window.scrollX) left = window.scrollX + 5; // Position from left edge

    popover.style.position = 'absolute'; // Ensure position is absolute when attached to body
    popover.style.top = `${top}px`;
    popover.style.left = `${left}px`;
}

/**
 * Displays the list of conversations in the sidebar.
 * Event listeners should be attached separately using delegation.
 * @param {Array} conversations - Array of conversation objects { conversation_id, title }.
 * @param {HTMLElement} conversationListElement - The <ul> element to populate.
 * @param {string | null} currentConversationId - The ID of the currently active conversation.
 */
export function displayConversations(conversations, conversationListElement, currentConversationId) {
    if (!conversationListElement) return;
    conversationListElement.innerHTML = ''; // Clear existing list

    if (!conversations || conversations.length === 0) {
        const noConvItem = document.createElement('li');
        noConvItem.textContent = 'No conversations yet.';
        noConvItem.style.fontStyle = 'italic';
        conversationListElement.appendChild(noConvItem);
        return;
    }

    conversations.forEach(conv => {
        const listItem = document.createElement('li');
        listItem.dataset.conversationId = conv.conversation_id;
        listItem.classList.add('conversation-item');
        if (conv.conversation_id === currentConversationId) {
            listItem.classList.add('active');
        }

        const itemContent = document.createElement('div');
        itemContent.classList.add('conversation-item-content');

        const titleSpan = document.createElement('span');
        titleSpan.classList.add('conversation-title');
        titleSpan.textContent = conv.title || `Conversation ${conv.conversation_id}`;
        // Add data-action for event delegation
        titleSpan.dataset.action = 'select';

        const actionsButton = document.createElement('button');
        actionsButton.classList.add('conversation-actions-button');
        actionsButton.innerHTML = '&#8943;';
        actionsButton.title = "More options";
        // Add data-action for event delegation
        actionsButton.dataset.action = 'toggle-popover';

        // Conversation Actions Popover (initially hidden, built but not attached to body)
        // Event listeners removed, will use delegation based on data-action
        const convPopover = document.createElement('div');
        convPopover.classList.add('actions-popover');
        // Add conversation ID to the popover buttons for delegation
        convPopover.innerHTML = `
            <button class="popover-button edit-button" data-action="edit" data-conversation-id="${conv.conversation_id}" title="Edit title">
                <span class="icon">&#x270E;</span> Edit
            </button>
            <button class="popover-button delete-button" data-action="delete" data-conversation-id="${conv.conversation_id}" title="Delete conversation">
                <span class="icon">&#x2715;</span> Delete
            </button>
        `;

        itemContent.appendChild(titleSpan);
        itemContent.appendChild(actionsButton);
        listItem._popoverElement = convPopover; // Store reference for easy access later
        listItem.appendChild(itemContent);
        conversationListElement.appendChild(listItem);
    });

    // Global listener for closing popovers is NOT added here.
    // It should be added once in the main script.
}