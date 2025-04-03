document.addEventListener('DOMContentLoaded', () => {
    const chatBox = document.getElementById('chat-box');
    const userInput = document.getElementById('user-input');
    const sendButton = document.getElementById('send-button');

    function addMessageToChatbox(message, sender) {
        const messageElement = document.createElement('div');
        messageElement.classList.add('message', `${sender}-message`);
        messageElement.textContent = message;
        chatBox.appendChild(messageElement);
        // Scroll to the bottom of the chat box
        chatBox.scrollTop = chatBox.scrollHeight;
    }

    async function sendMessage() {
        const messageText = userInput.value.trim();
        if (!messageText) return; // Don't send empty messages

        // Display user message immediately
        addMessageToChatbox(messageText, 'user');
        userInput.value = ''; // Clear input field

        try {
            // Add a temporary "typing..." indicator for the bot
            addMessageToChatbox('...', 'bot');
            const typingIndicator = chatBox.lastChild; // Keep track of the indicator

            const response = await fetch('/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ message: messageText }),
            });

            // Remove the typing indicator
            chatBox.removeChild(typingIndicator);

            if (!response.ok) {
                // Try to get error details from the response body
                let errorMsg = `Error: ${response.status} ${response.statusText}`;
                try {
                    const errorData = await response.json();
                    errorMsg = `Error: ${errorData.error || 'Failed to fetch'}${errorData.details ? ' - ' + errorData.details : ''}`;
                } catch (e) {
                    // Ignore if response body is not JSON or empty
                }
                addMessageToChatbox(errorMsg, 'bot');
                console.error('Chat request failed:', errorMsg);
                return;
            }

            const data = await response.json();
            if (data.response) {
                addMessageToChatbox(data.response, 'bot');
            } else if (data.error) {
                addMessageToChatbox(`Error: ${data.error}`, 'bot');
                console.error('Chat API Error:', data.error);
            } else {
                 addMessageToChatbox('Received an empty response.', 'bot');
            }

        } catch (error) {
             // Remove the typing indicator if it exists and an error occurs
            const typingIndicator = Array.from(chatBox.children).find(el => el.textContent === '...' && el.classList.contains('bot-message'));
            if (typingIndicator) {
                chatBox.removeChild(typingIndicator);
            }
            addMessageToChatbox('Failed to connect to the server. Please try again.', 'bot');
            console.error('Error sending message:', error);
        }
    }

    sendButton.addEventListener('click', sendMessage);

    userInput.addEventListener('keypress', (event) => {
        // Send message if Enter key is pressed
        if (event.key === 'Enter') {
            sendMessage();
        }
    });

    // Add an initial bot message (optional)
    // addMessageToChatbox("Hello! How can I help you today?", 'bot');
});