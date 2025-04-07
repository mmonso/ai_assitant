// --- UI Helper Functions ---

import { marked } from "https://cdn.jsdelivr.net/npm/marked/lib/marked.esm.js";
import DOMPurify from "https://cdn.jsdelivr.net/npm/dompurify/+esm";

// For syntax highlighting and sanitization (assuming libraries are loaded globally)
// Removed redundant declarations using window object
const hljs = window.hljs;

/**
 * Adds a message to the chatbox UI.
 * @param {string} message - The message content (text or markdown).
 * @param {string} sender - 'user', 'bot', or 'system'.
 * @param {HTMLElement} chatBox - The chatbox element to append to.
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

// Removed duplicated function definition (toggleConversationActionsPopover)

/**
 * Creates the HTML structure for the conversation actions popover.
 * @param {string} conversationId - The ID of the conversation.
 * @returns {HTMLElement} The popover element.
 */
function createConversationActionsPopover(conversationId) {
    const popover = document.createElement('div');
    popover.classList.add('actions-popover');
    popover.dataset.popoverFor = conversationId; // Link popover to conversation

    // This function seems duplicated by the one in displayConversations.
    // Keeping it for now, but ideally one source of truth for the popover HTML.
    popover.innerHTML = `
        <button class="popover-button" data-action="edit" data-conversation-id="${conversationId}" title="Rename conversation">
            <svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" fill="currentColor" class="bi bi-pencil-fill icon" viewBox="0 0 16 16" aria-hidden="true">
              <path d="M12.854.146a.5.5 0 0 0-.707 0L10.5 1.793 14.207 5.5l1.647-1.646a.5.5 0 0 0 0-.708zm.646 6.061L9.793 2.5 3.293 9H3.5a.5.5 0 0 1 .5.5v.5h.5a.5.5 0 0 1 .5.5v.5h.5a.5.5 0 0 1 .5.5v.5h.5a.5.5 0 0 1 .5.5v.207zm-7.468 7.468A.5.5 0 0 1 6 13.5V13h-.5a.5.5 0 0 1-.5-.5V12h-.5a.5.5 0 0 1-.5-.5V11h-.5a.5.5 0 0 1-.5-.5V10h-.5a.5.5 0 0 1-.175-.032l-.179.178a.5.5 0 0 0-.11.168l-2 5a.5.5 0 0 0 .65.65l5-2a.5.5 0 0 0 .168-.11z"/>
            </svg>
            Rename
        </button>
        <button class="popover-button delete-button" data-action="delete" data-conversation-id="${conversationId}" title="Delete conversation">
            <svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" fill="currentColor" class="bi bi-trash-fill icon" viewBox="0 0 16 16" aria-hidden="true">
              <path d="M2.5 1a1 1 0 0 0-1 1v1a1 1 0 0 0 1 1H3v9a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2V4h.5a1 1 0 0 0 1-1V2a1 1 0 0 0-1-1H10a1 1 0 0 0-1-1H7a1 1 0 0 0-1 1zm3 4a.5.5 0 0 1 .5.5v7a.5.5 0 0 1-1 0v-7a.5.5 0 0 1 .5-.5M8 5a.5.5 0 0 1 .5.5v7a.5.5 0 0 1-1 0v-7A.5.5 0 0 1 8 5m3 .5v7a.5.5 0 0 1-1 0v-7a.5.5 0 0 1 1 0"/>
            </svg>
            Delete
        </button>
    `;
    // Prevent clicks inside popover from propagating to the list item listener
    popover.addEventListener('click', (e) => e.stopPropagation());
    return popover;
}

/**
 * Positions a popover relative to a target button element.
 * Appends to body if not already there to avoid clipping issues.
 * @param {HTMLElement} popover - The popover element.
 * @param {HTMLElement} targetButton - The button the popover should appear near.
 */
function positionPopover(popover, targetButton) {
    if (!popover || !targetButton) return;

    // Append to body to avoid clipping issues within scrollable containers
    if (popover.parentElement !== document.body) {
        document.body.appendChild(popover);
    }

    const rect = targetButton.getBoundingClientRect();
    popover.style.top = `${rect.bottom + window.scrollY + 5}px`; // Position below button
    popover.style.left = `${rect.left + window.scrollX - popover.offsetWidth + rect.width}px`; // Align right edge
    popover.style.display = 'block'; // Ensure it's visible for positioning calculation if needed
}


// Removed duplicated function definition (hideAllPopovers)


// Removed duplicated function definitions (spinner/disable/enable)
// --- Spinner and Element Disabling ---

/**
 * Shows a loading spinner inside a target element (e.g., a button or div).
 * @param {HTMLElement} targetElement - The element where the spinner should appear.
 * @param {boolean} replaceContent - If true, replaces element content; otherwise appends.
 */
export function showSpinner(targetElement, replaceContent = false) {
    if (!targetElement) return;

    // Remove existing spinner first
    hideSpinner(targetElement);

    const spinner = document.createElement('span');
    spinner.className = 'loading-spinner'; // Use class from base.css
    spinner.setAttribute('aria-hidden', 'true'); // Hide decorative spinner from screen readers

    if (replaceContent) {
        // Add accessible text for screen readers
        const loadingText = document.createElement('span');
        loadingText.className = 'visually-hidden'; // Use class from base.css
        loadingText.textContent = 'Loading...';
        targetElement.innerHTML = ''; // Clear existing content
        targetElement.appendChild(loadingText);
        targetElement.appendChild(spinner);
    } else {
        targetElement.appendChild(spinner);
    }
}

/**
 * Hides/removes a loading spinner from a target element.
 * @param {HTMLElement} targetElement - The element containing the spinner.
 * @param {string | null} originalContent - Optional: HTML content to restore if content was replaced.
 */
export function hideSpinner(targetElement, originalContent = null) {
    if (!targetElement) return;
    const spinner = targetElement.querySelector('.loading-spinner');
    if (spinner) {
        spinner.remove();
    }
    // Remove accessible text if it exists
    const loadingText = targetElement.querySelector('.visually-hidden');
    if (loadingText && loadingText.textContent === 'Loading...') {
         loadingText.remove();
    }

    // Restore original content if provided (and if spinner was the only content)
    if (originalContent !== null && targetElement.innerHTML.trim() === '') {
        targetElement.innerHTML = originalContent;
    }
}

/**
 * Disables an element (e.g., button, input).
 * @param {HTMLElement} element - The element to disable.
 */
export function disableElement(element) {
    if (element) {
        element.disabled = true;
        // Optional: Add a class for visual styling (e.g., opacity)
        // element.classList.add('disabled-element');
    }
}

/**
 * Enables an element.
 * @param {HTMLElement} element - The element to enable.
 */
export function enableElement(element) {
    if (element) {
        element.disabled = false;
        // Optional: Remove the disabled styling class
        // element.classList.remove('disabled-element');
    }
}

/**
 * Adds a spinner element adjacent (before or after) to a target element.
 * Returns the spinner element or null.
 * @param {HTMLElement} targetElement - The element to add the spinner next to.
 * @param {'before' | 'after'} position - Where to insert the spinner relative to the target.
 * @returns {HTMLElement | null} The created spinner element or null if target doesn't exist.
 */
export function addSpinnerAdjacent(targetElement, position = 'after') {
    if (!targetElement || !targetElement.parentNode) return null;

    // Remove any existing adjacent spinner first
    removeAdjacentSpinner(targetElement);

    const spinner = document.createElement('span');
    spinner.className = 'loading-spinner adjacent-spinner'; // Add specific class
    spinner.setAttribute('aria-hidden', 'true');
    spinner.dataset.spinnerFor = targetElement.id || `target-${Math.random().toString(36).substring(2, 9)}`; // Link spinner to target

    if (position === 'before') {
        targetElement.parentNode.insertBefore(spinner, targetElement);
    } else {
        targetElement.parentNode.insertBefore(spinner, targetElement.nextSibling);
    }
    return spinner;
}

/**
 * Removes a spinner that was added adjacent to a target element.
 * @param {HTMLElement} targetElement - The element the spinner was added next to.
 */
export function removeAdjacentSpinner(targetElement) {
    if (!targetElement) return;
    const targetId = targetElement.id || `target-${targetElement.dataset.spinnerFor}`; // Try to find linked spinner
    const adjacentSpinners = targetElement.parentNode?.querySelectorAll('.adjacent-spinner');

    adjacentSpinners?.forEach(spinner => {
        // Basic check: is it immediately before or after?
        if (spinner.nextSibling === targetElement || spinner.previousSibling === targetElement) {
             // More specific check if IDs were used
             // if (spinner.dataset.spinnerFor === targetId) {
                 spinner.remove();
             // }
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
        // Use the same HTML structure as createConversationActionsPopover
        convPopover.innerHTML = createConversationActionsPopover(conv.conversation_id).innerHTML;

        itemContent.appendChild(titleSpan);
        itemContent.appendChild(actionsButton);
        listItem._popoverElement = convPopover; // Store reference for easy access later
        listItem.appendChild(itemContent);
        conversationListElement.appendChild(listItem);
    });

    // Global listener for closing popovers is NOT added here.
    // It should be added once in the main script.
}

/**
 * Displays a user-friendly error message in the chatbox and logs the original error.
 * @param {string} userMessage - The user-friendly message to display.
 * @param {Error | unknown} error - The original error object/data for logging.
 * @param {HTMLElement} chatBox - The chatbox element.
 */
export function displayErrorInChat(userMessage, error, chatBox) {
    console.error("An error occurred:", error); // Log the full error for debugging
    if (chatBox) {
        addMessageToChatbox(userMessage, 'system', chatBox); // Display user-friendly message
    }
}