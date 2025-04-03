document.addEventListener('DOMContentLoaded', () => {
    // Get element references
    const chatBox = document.getElementById('chat-box');
    const userInput = document.getElementById('user-input');
    const sendButton = document.getElementById('send-button');
    const conversationList = document.getElementById('conversation-list');
    const newChatButton = document.getElementById('new-chat-button');
    const openSettingsButton = document.getElementById('open-settings-button'); // Gear Icon Button
    const settingsPopoverLevel1 = document.getElementById('settings-popover-level1'); // Level 1 Popover
    // Modal elements will be queried dynamically after loading
    let settingsModalOverlay = null;
    let settingsModalMain = null;
    let closeSettingsButton = null;
    const settingsModalPlaceholder = document.getElementById('settings-modal-placeholder'); // Placeholder Div

    // --- Force Hide Modal & Popover on Load ---
    // Initial hide is not needed as the placeholder is empty
    if (settingsPopoverLevel1) {
        settingsPopoverLevel1.style.display = 'none';
        settingsPopoverLevel1.classList.remove('visible');
    }

    let currentConversationId = null; // Track the active conversation

    // --- UI Update Functions ---

    function addMessageToChatbox(message, sender) {
        const messageElement = document.createElement('div');
        messageElement.classList.add('message', `${sender}-message`);

        if (sender === 'bot') {
            const rawHtml = marked.parse(message, { gfm: true, breaks: true });
            const cleanHtml = DOMPurify.sanitize(rawHtml);
            messageElement.innerHTML = cleanHtml;
            messageElement.querySelectorAll('pre code').forEach((block) => {
                hljs.highlightElement(block);
            });
        } else {
            messageElement.textContent = message;
        }
        chatBox.appendChild(messageElement);
        chatBox.scrollTop = chatBox.scrollHeight;
    }

    function clearChatbox() {
        chatBox.innerHTML = '';
    }

    function displayConversations(conversations) {
        conversationList.innerHTML = '';
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

            const itemContent = document.createElement('div');
            itemContent.classList.add('conversation-item-content');

            const titleSpan = document.createElement('span');
            titleSpan.classList.add('conversation-title');
            titleSpan.textContent = conv.title || `Conversation ${conv.conversation_id}`;
            titleSpan.addEventListener('click', (e) => {
                if (!listItem.classList.contains('editing')) {
                    handleConversationSelect(conv.conversation_id);
                }
                e.stopPropagation();
            });

            const actionsButton = document.createElement('button');
            actionsButton.classList.add('conversation-actions-button');
            actionsButton.innerHTML = '&#8943;';
            actionsButton.title = "More options";
            actionsButton.addEventListener('click', (e) => {
                e.stopPropagation();
                // *** FIX: Call the renamed function ***
                toggleConversationActionsPopover(listItem);
            });

            // Conversation Actions Popover (initially hidden)
            const convPopover = document.createElement('div');
            convPopover.classList.add('actions-popover'); // Use existing class for conversation actions
            convPopover.innerHTML = `
                <button class="popover-button edit-button" title="Edit title">
                    <span class="icon">&#x270E;</span> Edit
                </button>
                <button class="popover-button delete-button" title="Delete conversation">
                    <span class="icon">&#x2715;</span> Delete
                </button>
            `;
            convPopover.querySelector('.edit-button').addEventListener('click', (e) => {
                e.stopPropagation();
                handleEditConversation(listItem, titleSpan, conv.conversation_id);
                hideAllPopovers();
            });
            convPopover.querySelector('.delete-button').addEventListener('click', (e) => {
                e.stopPropagation();
                handleDeleteConversation(listItem, conv.conversation_id, titleSpan.textContent);
                hideAllPopovers();
            });

            itemContent.appendChild(titleSpan);
            itemContent.appendChild(actionsButton);
            listItem._popoverElement = convPopover; // Store reference for conversation actions
            listItem.appendChild(itemContent);
            conversationList.appendChild(listItem);
        });

        // Add global listener to close popovers when clicking outside
        document.addEventListener('click', hideAllPopovers);
    }

     function hideAllPopovers(event) {
        let clickedInsidePopover = false;
        let clickedOnActionsButton = false;
        let clickedOnGearButton = false;

        if (event) {
            clickedInsidePopover = event.target.closest('.actions-popover, .settings-popover');
            clickedOnActionsButton = event.target.closest('.conversation-actions-button');
            clickedOnGearButton = event.target.closest('#open-settings-button');
        }

        // Hide Conversation Actions Popovers
        const visibleConvPopovers = document.querySelectorAll('body > .actions-popover.visible');
        visibleConvPopovers.forEach(popover => {
            // Don't hide if the click was inside this specific popover or on its corresponding button
            const ownerButton = document.querySelector(`.conversation-actions-button[aria-describedby="${popover.id}"]`); // Assuming we add aria later
            const ownerLi = ownerButton ? ownerButton.closest('.conversation-item') : null;
            if (!clickedInsidePopover && !(clickedOnActionsButton && ownerLi && ownerLi._popoverElement === popover)) {
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

    // Renamed from toggleActionsPopover to avoid confusion
    function toggleConversationActionsPopover(listItem) {
        const popover = listItem._popoverElement;
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
        let top = btnRect.bottom + buffer;
        let left = btnRect.left; // Align left edge of popover with left edge of button

        // Adjust if it goes off-screen BOTTOM
        if (top + popoverRect.height > window.innerHeight - buffer) {
            top = btnRect.top - popoverRect.height - buffer; // Try placing ABOVE instead
            if (top < buffer) top = buffer; // Place near top edge as last resort
        }
        // Adjust if it goes off-screen right (popover left + width > viewport width)
        if (left + popoverRect.width > window.innerWidth) {
            left = window.innerWidth - popoverRect.width - 5; // Position from right edge with 5px margin
        }
         // Adjust if it goes off-screen left (shouldn't happen often with left alignment, but check)
        if (left < 0) left = 5; // Position from left edge with 5px margin

        popover.style.top = `${top}px`;
        popover.style.left = `${left}px`;
    }


    function setActiveConversationInSidebar(conversationId) {
        document.querySelectorAll('#conversation-list li').forEach(item => {
            item.classList.remove('active', 'editing');
        });
        const activeItem = document.querySelector(`#conversation-list li[data-conversation-id="${conversationId}"]`);
        if (activeItem) {
            activeItem.classList.add('active');
        }
    }

    // --- API Interaction Functions ---

    async function loadConversationList() {
        console.log("Loading conversation list...");
        try {
            const response = await fetch('/api/chat/list');
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            const data = await response.json();
            displayConversations(data.conversations || []);
        } catch (error) {
            console.error('Failed to fetch conversation list:', error);
            addMessageToChatbox('Could not load conversation list.', 'system');
            displayConversations([]);
        }
    }

    async function loadConversationMessages(conversationId) {
        console.log(`Loading messages for conversation: ${conversationId}`);
        clearChatbox();
        addMessageToChatbox('Loading messages...', 'system');
        const loadingIndicator = chatBox.lastChild;

        try {
            const response = await fetch(`/api/chat/messages?conversation_id=${conversationId}`);
            if (loadingIndicator && chatBox.contains(loadingIndicator)) chatBox.removeChild(loadingIndicator);

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(`HTTP error! status: ${response.status}, message: ${errorData.error || 'Unknown error'}`);
            }

            const data = await response.json();
            if (data.messages && Array.isArray(data.messages)) {
                data.messages.forEach(message => {
                    const sender = message.role === 'assistant' ? 'bot' : message.role;
                    addMessageToChatbox(message.content, sender);
                });
                currentConversationId = conversationId;
                setActiveConversationInSidebar(conversationId);
            } else {
                console.log("No messages found for this conversation.");
            }
        } catch (error) {
            if (loadingIndicator && chatBox.contains(loadingIndicator)) chatBox.removeChild(loadingIndicator);
            console.error('Failed to fetch messages:', error);
            addMessageToChatbox(`Could not load messages: ${error.message}`, 'system');
            currentConversationId = null;
            setActiveConversationInSidebar(null);
        }
    }

    async function sendMessage() {
        const messageText = userInput.value.trim();
        if (!messageText) return;

        addMessageToChatbox(messageText, 'user');
        userInput.value = '';
        addMessageToChatbox('...', 'bot');
        const typingIndicator = chatBox.lastChild;

        try {
            const response = await fetch('/api/chat/send', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: messageText }),
            });

            if (typingIndicator && chatBox.contains(typingIndicator)) chatBox.removeChild(typingIndicator);

            if (!response.ok) {
                let errorMsg = `Error: ${response.status}`;
                try { errorMsg = (await response.json()).error || errorMsg; } catch (e) {}
                throw new Error(errorMsg);
            }

            const data = await response.json();

            if (data.response) {
                addMessageToChatbox(data.response, 'bot');
            } else if (data.error) {
                throw new Error(data.error);
            }

            if (data.new_conversation_id) {
                currentConversationId = data.new_conversation_id;
                console.log(`Backend created new conversation: ${currentConversationId}`);
                await fetch('/api/chat/set_active', {
                     method: 'POST',
                     headers: { 'Content-Type': 'application/json' },
                     body: JSON.stringify({ conversation_id: currentConversationId }),
                });
                await loadConversationList();
                setActiveConversationInSidebar(currentConversationId);
            }

        } catch (error) {
            if (typingIndicator && chatBox.contains(typingIndicator)) chatBox.removeChild(typingIndicator);
            addMessageToChatbox(`Error: ${error.message}`, 'bot');
            console.error('Error sending message:', error);
        }
    }

    // --- Edit/Delete Handling ---

    function handleEditConversation(listItem, titleSpan, conversationId) {
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
            listItem.classList.remove('editing');
            if (newTitle === currentTitle || !newTitle) {
                input.replaceWith(titleSpan);
                titleSpan.textContent = currentTitle;
                return;
            }
            titleSpan.textContent = newTitle;
            input.replaceWith(titleSpan);
            try {
                const response = await fetch(`/api/chat/rename/${conversationId}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ title: newTitle }),
                });
                if (!response.ok) {
                    console.error("Failed to rename conversation on backend");
                    titleSpan.textContent = currentTitle;
                    addMessageToChatbox(`Error renaming conversation: ${await response.text()}`, 'system');
                } else {
                    console.log(`Conversation ${conversationId} renamed to "${newTitle}"`);
                }
            } catch (error) {
                console.error("Error renaming conversation:", error);
                titleSpan.textContent = currentTitle;
                addMessageToChatbox('Error connecting to server for rename.', 'system');
            }
        };

        input.addEventListener('blur', saveChanges);
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') input.blur();
            else if (e.key === 'Escape') {
                listItem.classList.remove('editing');
                input.replaceWith(titleSpan);
                titleSpan.textContent = currentTitle;
            }
        });
    }

    function handleDeleteConversation(listItem, conversationId, conversationTitle) {
        if (!confirm(`Are you sure you want to delete "${conversationTitle}"?\nThis action cannot be undone.`)) return;
        console.log(`Attempting to delete conversation: ${conversationId}`);
        fetch(`/api/chat/delete/${conversationId}`, { method: 'DELETE' })
            .then(response => {
                if (!response.ok) return response.json().then(err => { throw new Error(err.error || 'Failed to delete'); });
                return response.json();
            })
            .then(data => {
                console.log(data.message);
                listItem.remove();
                if (currentConversationId === conversationId) handleNewChat();
                if (conversationList.children.length === 0) displayConversations([]);
            })
            .catch(error => {
                console.error("Error deleting conversation:", error);
                addMessageToChatbox(`Error deleting conversation: ${error.message}`, 'system');
            });
    }

    // --- Event Handlers ---

    async function handleConversationSelect(conversationId) {
        if (conversationId === currentConversationId) return;
        console.log(`Switching to conversation: ${conversationId}`);
        try {
            const response = await fetch('/api/chat/set_active', {
                 method: 'POST',
                 headers: { 'Content-Type': 'application/json' },
                 body: JSON.stringify({ conversation_id: conversationId }),
            });
            if (!response.ok) throw new Error("Failed to set active conversation on backend");
            await loadConversationMessages(conversationId);
        } catch(error) {
             console.error("Error setting active conversation:", error);
             addMessageToChatbox('Failed to switch conversation.', 'system');
        }
    }

    async function handleNewChat() {
        console.log("Starting new chat...");
        try {
             const response = await fetch('/api/chat/start_new', { method: 'POST' });
             if (!response.ok) throw new Error("Failed to signal new conversation to backend");
             currentConversationId = null;
             clearChatbox();
             setActiveConversationInSidebar(null);
             userInput.focus();
        } catch (error) {
             console.error("Error starting new chat:", error);
             addMessageToChatbox('Error starting new chat.', 'system');
        }
    }

    // --- Settings Menu/Modal Logic ---

    function toggleSettingsPopoverLevel1() {
        if (!settingsPopoverLevel1) return;
        const isVisible = settingsPopoverLevel1.classList.toggle('visible');
        settingsPopoverLevel1.style.display = isVisible ? 'block' : 'none';
        // *** FIX: Removed hideAllPopovers() call from here ***
    }

    async function fetchAndPopulateSettings() {
        console.log("Fetching user settings data...");
        try {
            const response = await fetch('/api/settings/get_user_settings'); // Use settings API blueprint
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();

            // Call the function in settings.js to populate the forms
            if (typeof window.populateSettingsForms === 'function') {
                window.populateSettingsForms(data.user, data.config);
            } else {
                console.error("populateSettingsForms function not found in settings.js");
            }
        } catch (error) {
            console.error("Failed to fetch or populate settings:", error);
            // Optionally display an error in the modal or as a system message
            if (settingsModalMain) {
                 const errorElement = settingsModalMain.querySelector('#settings-load-error'); // Add an element for this
                 if (errorElement) errorElement.textContent = `Error loading settings: ${error.message}`;
            }
        }
    }


    async function openSettingsModal(targetTabId = 'account') { // Default to account tab
        if (!settingsModalPlaceholder) {
            console.error("Settings modal placeholder not found!");
            return;
        }

        // Check if modal content is already loaded
        let modalContentLoaded = settingsModalPlaceholder.querySelector('#settings-page-overlay');

        if (!modalContentLoaded) {
            console.log("Settings modal not loaded, fetching...");
            try {
                const response = await fetch('/get_settings_modal'); // Fetch the partial HTML
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                const modalHtml = await response.text();
                settingsModalPlaceholder.innerHTML = modalHtml; // Inject the HTML

                // Now that HTML is injected, query for the elements
                settingsModalOverlay = settingsModalPlaceholder.querySelector('#settings-page-overlay');
                settingsModalMain = settingsModalPlaceholder.querySelector('#settings-modal-main');
                closeSettingsButton = settingsModalPlaceholder.querySelector('#close-settings-button');

                if (!settingsModalOverlay || !settingsModalMain || !closeSettingsButton) {
                     console.error("Failed to find modal elements after loading!");
                     settingsModalPlaceholder.innerHTML = '<p style="color:red;">Error loading settings modal content.</p>';
                     return;
                }

                // Re-attach close button listener (important!)
                closeSettingsButton.addEventListener('click', closeSettingsModal);

                console.log("Settings modal HTML loaded and elements found.");

                // Note: Event listeners inside settings.js for forms might need adjustment
                // if they rely on running only once at initial DOMContentLoaded.
                // Calling populateSettingsForms should be sufficient for now.

            } catch (error) {
                console.error("Failed to fetch or inject settings modal:", error);
                settingsModalPlaceholder.innerHTML = `<p style="color:red;">Error loading settings: ${error.message}</p>`;
                return; // Stop if loading failed
            }
        } else {
             // Modal already loaded, just ensure elements are referenced
             settingsModalOverlay = modalContentLoaded;
             settingsModalMain = settingsModalOverlay.querySelector('#settings-modal-main');
             closeSettingsButton = settingsModalOverlay.querySelector('#close-settings-button');
             console.log("Settings modal already loaded.");
        }

        // Ensure elements are valid before proceeding
        if (!settingsModalOverlay || !settingsModalMain) {
             console.error("Cannot proceed, settings modal elements are missing.");
             return;
        }

        // Fetch/refresh data and populate forms (now happens *after* HTML is potentially loaded)
        await fetchAndPopulateSettings(); // Make sure this awaits if needed

        // Activate the correct tab
        const tabs = settingsModalMain.querySelectorAll('.settings-tab');
        let activated = false;
        tabs.forEach(tab => {
            if (tab.id === targetTabId) {
                tab.classList.add('active');
                activated = true;
            } else {
                tab.classList.remove('active');
            }
        });
        // Fallback if targetTabId doesn't match any tab
        if (!activated && tabs.length > 0) {
            tabs[0].classList.add('active');
        }

        // Show the modal
        settingsModalOverlay.style.display = 'flex';
        // Use setTimeout to allow the browser to render the display change before adding the class for transition
        setTimeout(() => {
             settingsModalOverlay.classList.add('visible');
        }, 10); // Small delay
        document.body.classList.add('settings-modal-open');
    }

    function closeSettingsModal() {
        // Now references the dynamically loaded element
        if (settingsModalOverlay && settingsModalOverlay.classList.contains('visible')) {
             settingsModalOverlay.classList.remove('visible');
             // Wait for transition to finish before hiding completely
             settingsModalOverlay.addEventListener('transitionend', () => {
                 settingsModalOverlay.style.display = 'none';
             }, { once: true }); // Remove listener after it runs once
             document.body.classList.remove('settings-modal-open');
        } else if (settingsModalOverlay) {
             // If somehow called when not visible, just ensure it's hidden
             settingsModalOverlay.style.display = 'none';
             document.body.classList.remove('settings-modal-open');
        }
    }

    // --- Event Listener Setup ---

    // Existing Chat Listeners
    if (sendButton) sendButton.addEventListener('click', sendMessage);
    if (userInput) userInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') sendMessage();
    });
    if (newChatButton) newChatButton.addEventListener('click', handleNewChat);

    // Settings Listeners
    if (openSettingsButton) {
        openSettingsButton.addEventListener('click', (e) => {
            e.stopPropagation(); // Prevent document click listener from closing it immediately
            toggleSettingsPopoverLevel1();
        });
    }
    if (settingsPopoverLevel1) {
        settingsPopoverLevel1.addEventListener('click', (e) => {
            if (e.target.tagName === 'A') {
                const targetModal = e.target.dataset.targetModal;
                const targetTab = e.target.dataset.targetTab;

                if (targetModal === 'settings-modal-main') {
                    e.preventDefault(); // Prevent default link behavior only if opening modal
                    toggleSettingsPopoverLevel1(); // Hide level 1 popover
                    openSettingsModal(targetTab); // Open level 2 modal, passing target tab
                }
                // Allow default behavior for other links (like logout)
            }
        });
    }

    if (closeSettingsButton) {
    }
    if (settingsModalOverlay) {
        // Close modal if clicking directly on the overlay background
        settingsModalOverlay.addEventListener('click', (event) => {
            if (event.target === settingsModalOverlay) {
                closeSettingsModal();
            }
        });
    }

    // --- Initialization ---
    loadConversationList();

});