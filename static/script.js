document.addEventListener('DOMContentLoaded', () => {
    const chatBox = document.getElementById('chat-box');
    const userInput = document.getElementById('user-input');
    const sendButton = document.getElementById('send-button');
    const conversationList = document.getElementById('conversation-list'); // Updated ID
    const newChatButton = document.getElementById('new-chat-button');

    let currentConversationId = null; // Track the active conversation

    // --- UI Update Functions ---

    function addMessageToChatbox(message, sender) {
        const messageElement = document.createElement('div');
        messageElement.classList.add('message', `${sender}-message`);

        if (sender === 'bot') {
            // 1. Parse Markdown using marked
            const rawHtml = marked.parse(message, { gfm: true, breaks: true }); // Enable GitHub Flavored Markdown & line breaks

            // 2. Sanitize HTML using DOMPurify
            const cleanHtml = DOMPurify.sanitize(rawHtml);

            // 3. Set innerHTML
            messageElement.innerHTML = cleanHtml;

            // 4. Apply Syntax Highlighting to code blocks within this message
            messageElement.querySelectorAll('pre code').forEach((block) => {
                hljs.highlightElement(block);
            });
        } else {
            // For user or system messages, just set text content
            messageElement.textContent = message;
        }
        chatBox.appendChild(messageElement);
        chatBox.scrollTop = chatBox.scrollHeight; // Scroll down
    }

    function clearChatbox() {
        chatBox.innerHTML = '';
    }

    function displayConversations(conversations) {
        conversationList.innerHTML = ''; // Clear existing list
        if (!conversations || conversations.length === 0) {
            const noConvItem = document.createElement('li');
            noConvItem.textContent = 'No conversations yet.';
            noConvItem.style.fontStyle = 'italic';
            conversationList.appendChild(noConvItem);
            return;
        }

        conversations.forEach(conv => {
            const listItem = document.createElement('li');
            listItem.dataset.conversationId = conv.conversation_id;
            listItem.classList.add('conversation-item');
            if (conv.conversation_id === currentConversationId) {
                listItem.classList.add('active');
            }

            // Container for title and actions
            const itemContent = document.createElement('div');
            itemContent.classList.add('conversation-item-content');

            // Title Span (for potential editing)
            const titleSpan = document.createElement('span');
            titleSpan.classList.add('conversation-title');
            titleSpan.textContent = conv.title || `Conversation ${conv.conversation_id}`;
            titleSpan.addEventListener('click', (e) => {
                // Prevent triggering edit/delete when clicking title to select
                if (!listItem.classList.contains('editing')) {
                    handleConversationSelect(conv.conversation_id);
                }
                e.stopPropagation(); // Prevent li click handler if needed
            });

            // Actions Button (...)
            const actionsButton = document.createElement('button');
            actionsButton.classList.add('conversation-actions-button');
            actionsButton.innerHTML = '&#8943;'; // Horizontal ellipsis HTML entity
            actionsButton.title = "More options";
            actionsButton.addEventListener('click', (e) => {
                e.stopPropagation(); // Prevent li click handler
                toggleActionsPopover(listItem);
            });

            // Actions Popover (initially hidden)
            const popover = document.createElement('div');
            popover.classList.add('actions-popover');
            popover.innerHTML = `
                <button class="popover-button edit-button" title="Edit title">
                    <span class="icon">&#x270E;</span> Edit <!-- Unicode Lower Right Pencil -->
                </button>
                <button class="popover-button delete-button" title="Delete conversation">
                    <span class="icon">&#x2715;</span> Delete <!-- Unicode Multiplication X -->
                </button>
            `;
            // Add event listeners inside the popover creation
            popover.querySelector('.edit-button').addEventListener('click', (e) => {
                e.stopPropagation();
                handleEditConversation(listItem, titleSpan, conv.conversation_id);
                hideAllPopovers();
            });
            popover.querySelector('.delete-button').addEventListener('click', (e) => {
                e.stopPropagation();
                handleDeleteConversation(listItem, conv.conversation_id, titleSpan.textContent);
                hideAllPopovers();
            });


            itemContent.appendChild(titleSpan);
            itemContent.appendChild(actionsButton);
            // Don't append popover here initially
            // Store popover element reference on the list item for later use
            listItem._popoverElement = popover;
            listItem.appendChild(itemContent);
            conversationList.appendChild(listItem);
        });

        // Add global listener to close popovers when clicking outside
        document.addEventListener('click', hideAllPopovers); // Remove capture phase (true)
    }

     function hideAllPopovers(event) {
        // If the click was specifically on an actions button, let its handler manage toggling
        if (event && event.target.closest('.conversation-actions-button')) {
             // Check if the click was on the button that *owns* the currently visible popover
             const currentVisiblePopover = document.querySelector('.actions-popover.visible');
             if (currentVisiblePopover && event.target.closest('.conversation-item')._popoverElement === currentVisiblePopover) {
                 // Allow the toggle function to handle closing it
                 return;
             }
        }

        // Hide and remove any popovers attached to the body
        const visiblePopovers = document.querySelectorAll('body > .actions-popover.visible');
        visiblePopovers.forEach(popover => {
            popover.remove(); // Remove from body
        });
    }

    function toggleActionsPopover(listItem) {
        const popover = listItem._popoverElement;
        if (!popover) return;

        const button = listItem.querySelector('.conversation-actions-button');
        const currentlyVisiblePopover = document.querySelector('body > .actions-popover.visible');

        // If this popover is already visible, hide and remove it
        if (currentlyVisiblePopover === popover) {
            popover.remove();
            console.log("Popover removed (toggle off)");
            return;
        }

        // If another popover is visible, hide and remove it first
        if (currentlyVisiblePopover) {
            currentlyVisiblePopover.remove();
            console.log("Previous popover removed");
        }

        // Append the new popover to the body and calculate position
        document.body.appendChild(popover);
        popover.classList.add('visible'); // Make visible before measuring

        const btnRect = button.getBoundingClientRect();
        const popoverRect = popover.getBoundingClientRect(); // Measure after visible

        console.log("Button Rect:", btnRect); // Debugging
        console.log("Popover Rect:", popoverRect); // Debugging

        // --- Position Calculation ---
        const buffer = 4; // Gap between button and popover

        // Default: Position BELOW the button, aligned left
        let top = btnRect.bottom + buffer;
        let left = btnRect.left; // Align left edge of popover with left edge of button

        console.log(`[Popover] Initial calculated top (below): ${top}, left: ${left}`);

        // Adjust if it goes off-screen BOTTOM
        if (top + popoverRect.height > window.innerHeight - buffer) {
            top = btnRect.top - popoverRect.height - buffer; // Try placing ABOVE instead
            console.log(`[Popover] Adjusting top (too low): placing ABOVE button at ${top}`);
            // Double-check if placing ABOVE now goes off-screen top
            if (top < buffer) {
                 top = buffer; // Place near top edge as last resort
                 console.log(`[Popover] Adjusting top (ABOVE too high): placing near top edge at ${top}`);
            }
        }
        // Adjust if it goes off-screen right (popover left + width > viewport width)
        if (left + popoverRect.width > window.innerWidth) {
            left = window.innerWidth - popoverRect.width - 5; // Position from right edge with 5px margin
             console.log("Adjusting left: preventing right overflow");
        }
         // Adjust if it goes off-screen left (shouldn't happen often with left alignment, but check)
        if (left < 0) {
            left = 5; // Position from left edge with 5px margin
            console.log("Adjusting left: preventing left overflow");
        }
        // --- End Position Calculation ---

        popover.style.top = `${top}px`;
        popover.style.left = `${left}px`;
        console.log(`Popover positioned at top: ${top}px, left: ${left}px`); // Debugging
    }


    function setActiveConversationInSidebar(conversationId) {
        // Remove active/editing class from all items
        document.querySelectorAll('#conversation-list li').forEach(item => {
            item.classList.remove('active', 'editing'); // Also remove editing class
        });
        // Add active class to the selected one
        const activeItem = document.querySelector(`#conversation-list li[data-conversation-id="${conversationId}"]`);
        if (activeItem) {
            activeItem.classList.add('active');
        }
    }

    // --- API Interaction Functions ---

    async function loadConversationList() {
        console.log("Loading conversation list...");
        try {
            const response = await fetch('/get_conversation_list');
            if (!response.ok) {
                console.error(`Error loading conversation list: ${response.status}`);
                // Handle error display if needed
                displayConversations([]); // Show empty state
                return;
            }
            const data = await response.json();
            displayConversations(data.conversations || []);
            // Optionally load the most recent conversation automatically?
            // if (data.conversations && data.conversations.length > 0) {
            //    handleConversationSelect(data.conversations[0].conversation_id);
            // }
        } catch (error) {
            console.error('Failed to fetch conversation list:', error);
            addMessageToChatbox('Could not load conversation list.', 'system');
            displayConversations([]); // Show empty state
        }
    }

    async function loadConversationMessages(conversationId) {
        console.log(`Loading messages for conversation: ${conversationId}`);
        clearChatbox(); // Clear chat before loading new messages
        addMessageToChatbox('Loading messages...', 'system'); // Loading indicator

        try {
            const response = await fetch(`/get_conversation_messages?conversation_id=${conversationId}`);
            const loadingIndicator = chatBox.lastChild; // Get indicator element
            if (loadingIndicator && loadingIndicator.textContent === 'Loading messages...') {
                 chatBox.removeChild(loadingIndicator); // Remove indicator
            }

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                const errorMsg = `Error loading messages: ${response.status} ${errorData.error || ''}`;
                console.error(errorMsg);
                addMessageToChatbox(errorMsg, 'system');
                currentConversationId = null; // Reset if loading failed
                setActiveConversationInSidebar(null);
                return;
            }

            const data = await response.json();
            if (data.messages && Array.isArray(data.messages)) {
                data.messages.forEach(message => {
                    const sender = message.role === 'assistant' ? 'bot' : message.role;
                    addMessageToChatbox(message.content, sender);
                });
                currentConversationId = conversationId; // Update current ID after successful load
                setActiveConversationInSidebar(conversationId);
            } else {
                console.log("No messages found for this conversation.");
                // Keep chatbox clear or add a message like "Start typing..."
            }
        } catch (error) {
            const loadingIndicator = chatBox.lastChild; // Try removing indicator again on error
            if (loadingIndicator && loadingIndicator.textContent === 'Loading messages...') {
                 chatBox.removeChild(loadingIndicator);
            }
            console.error('Failed to fetch messages:', error);
            addMessageToChatbox('Could not load messages for this conversation.', 'system');
            currentConversationId = null; // Reset on error
            setActiveConversationInSidebar(null);
        }
    }

    async function sendMessage() {
        const messageText = userInput.value.trim();
        if (!messageText) return;

        addMessageToChatbox(messageText, 'user');
        userInput.value = '';
        addMessageToChatbox('...', 'bot'); // Typing indicator
        const typingIndicator = chatBox.lastChild;

        try {
            const response = await fetch('/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                // Send message *without* conversation_id if currentConversationId is null
                // Backend will create a new one
                body: JSON.stringify({ message: messageText }),
            });

            if (typingIndicator) chatBox.removeChild(typingIndicator); // Remove indicator

            if (!response.ok) {
                let errorMsg = `Error: ${response.status}`;
                try { errorMsg = (await response.json()).error || errorMsg; } catch (e) {}
                addMessageToChatbox(errorMsg, 'bot');
                console.error('Chat request failed:', errorMsg);
                return;
            }

            const data = await response.json();

            if (data.response) {
                addMessageToChatbox(data.response, 'bot');
            } else if (data.error) {
                addMessageToChatbox(`Error: ${data.error}`, 'bot');
            }

            // If a new conversation was created by the backend
            if (data.new_conversation_id) {
                currentConversationId = data.new_conversation_id;
                console.log(`Backend created new conversation: ${currentConversationId}`);
                // Update the session on the backend to track this new ID
                await fetch('/set_active_conversation', {
                     method: 'POST',
                     headers: { 'Content-Type': 'application/json' },
                     body: JSON.stringify({ conversation_id: currentConversationId }),
                });
                // Reload the conversation list to show the new one
                await loadConversationList();
                setActiveConversationInSidebar(currentConversationId); // Highlight the new one
            }

        } catch (error) {
            if (typingIndicator && chatBox.contains(typingIndicator)) {
                chatBox.removeChild(typingIndicator);
            }
            addMessageToChatbox('Failed to connect. Please try again.', 'bot');
            console.error('Error sending message:', error);
        }
    }

    // --- Edit/Delete Handling ---

    function handleEditConversation(listItem, titleSpan, conversationId) {
        listItem.classList.add('editing');
        const currentTitle = titleSpan.textContent;

        // Replace span with input field
        const input = document.createElement('input');
        input.type = 'text';
        input.value = currentTitle;
        input.classList.add('edit-conversation-input');

        // Replace titleSpan with input
        titleSpan.replaceWith(input);
        input.focus(); // Focus the input field
        input.select(); // Select existing text

        // Save on Enter or Blur
        const saveChanges = async () => {
            const newTitle = input.value.trim();
            listItem.classList.remove('editing'); // Exit editing mode visually

            // If title hasn't changed or is empty, revert without API call
            if (newTitle === currentTitle || !newTitle) {
                input.replaceWith(titleSpan); // Put the original span back
                titleSpan.textContent = currentTitle; // Ensure original text is there
                return;
            }

            // Optimistically update UI
            titleSpan.textContent = newTitle;
            input.replaceWith(titleSpan);

            // Call API to save changes
            try {
                const response = await fetch(`/rename_conversation/${conversationId}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ title: newTitle }),
                });
                if (!response.ok) {
                    console.error("Failed to rename conversation on backend");
                    // Revert UI on failure
                    titleSpan.textContent = currentTitle;
                    addMessageToChatbox(`Error renaming conversation: ${await response.text()}`, 'system');
                } else {
                    console.log(`Conversation ${conversationId} renamed to "${newTitle}"`);
                    // Optionally refresh list if order might change, but likely not needed
                    // await loadConversationList();
                }
            } catch (error) {
                console.error("Error renaming conversation:", error);
                titleSpan.textContent = currentTitle; // Revert UI
                addMessageToChatbox('Error connecting to server for rename.', 'system');
            }
        };

        input.addEventListener('blur', saveChanges);
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                input.blur(); // Trigger saveChanges via blur
            } else if (e.key === 'Escape') {
                listItem.classList.remove('editing');
                input.replaceWith(titleSpan); // Revert on Escape
                titleSpan.textContent = currentTitle;
            }
        });
    }

    function handleDeleteConversation(listItem, conversationId, conversationTitle) {
        // Simple confirmation dialog (replace with a styled modal later if desired)
        if (!confirm(`Are you sure you want to delete "${conversationTitle}"?\nThis action cannot be undone.`)) {
            return;
        }

        console.log(`Attempting to delete conversation: ${conversationId}`);

        // Call API to delete
        fetch(`/delete_conversation/${conversationId}`, { method: 'DELETE' })
            .then(response => {
                if (!response.ok) {
                    return response.json().then(err => { throw new Error(err.error || 'Failed to delete'); });
                }
                return response.json(); // Contains success message
            })
            .then(data => {
                console.log(data.message);
                // Remove item from UI
                listItem.remove();
                // If the deleted conversation was the active one, start a new chat context
                if (currentConversationId === conversationId) {
                    handleNewChat(); // Clears chatbox and resets currentConversationId
                }
                // Check if list is now empty
                if (conversationList.children.length === 0) {
                     displayConversations([]); // Show "No conversations" message
                }
            })
            .catch(error => {
                console.error("Error deleting conversation:", error);
                addMessageToChatbox(`Error deleting conversation: ${error.message}`, 'system');
            });
    }

    // --- Event Handlers ---

    async function handleConversationSelect(conversationId) {
        if (conversationId === currentConversationId) {
            console.log("Conversation already selected.");
            return; // Don't reload if already active
        }
        console.log(`Switching to conversation: ${conversationId}`);
        // Update backend session first
        try {
            const response = await fetch('/set_active_conversation', {
                 method: 'POST',
                 headers: { 'Content-Type': 'application/json' },
                 body: JSON.stringify({ conversation_id: conversationId }),
            });
            if (!response.ok) {
                 console.error("Failed to set active conversation on backend");
                 // Handle error display?
                 return;
            }
             // If backend update is successful, load messages
            await loadConversationMessages(conversationId);
        } catch(error) {
             console.error("Error setting active conversation:", error);
             addMessageToChatbox('Failed to switch conversation.', 'system');
        }
    }

    async function handleNewChat() {
        console.log("Starting new chat...");
        try {
             const response = await fetch('/start_new_conversation', { method: 'POST' });
             if (!response.ok) {
                 console.error("Failed to signal new conversation to backend");
                 addMessageToChatbox('Could not start a new chat session.', 'system');
                 return;
             }
             // If backend is ready, clear frontend state
             currentConversationId = null;
             clearChatbox();
             setActiveConversationInSidebar(null); // De-highlight sidebar
             userInput.focus(); // Focus input for new message
             // Optional: Add a placeholder message
             // addMessageToChatbox("New chat started. Ask me anything!", 'system');
        } catch (error) {
             console.error("Error starting new chat:", error);
             addMessageToChatbox('Error starting new chat.', 'system');
        }
    }

    // --- Initial Setup ---

    sendButton.addEventListener('click', sendMessage);
    userInput.addEventListener('keypress', (event) => {
        if (event.key === 'Enter') {
            sendMessage();
        }
    });
    newChatButton.addEventListener('click', handleNewChat);

    // Load the list of conversations when the page loads
    loadConversationList();

});