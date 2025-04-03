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
        // Add 'system' class for potential system messages (like errors)
        messageElement.classList.add('message', `${sender}-message`);
        messageElement.textContent = message;
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
            listItem.textContent = conv.title || `Conversation ${conv.conversation_id}`; // Use title or ID
            listItem.dataset.conversationId = conv.conversation_id; // Store ID for click handling
            listItem.classList.add('conversation-item');
            if (conv.conversation_id === currentConversationId) {
                listItem.classList.add('active'); // Highlight active conversation
            }
            listItem.addEventListener('click', () => handleConversationSelect(conv.conversation_id));
            conversationList.appendChild(listItem);
        });
    }

    function setActiveConversationInSidebar(conversationId) {
        // Remove active class from all items
        document.querySelectorAll('#conversation-list li').forEach(item => {
            item.classList.remove('active');
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