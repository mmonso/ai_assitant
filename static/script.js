import * as ui from './ui_helpers.js';
import * as api from './api_client.js';
import * as convManager from './conversation_manager.js';
import * as settingsManager from './settings_manager.js';

document.addEventListener('DOMContentLoaded', async () => { // Make async
    console.log("Main script loaded.");

    // --- Get Main Element References ---
    const chatBox = document.getElementById('chat-box');
    const userInput = document.getElementById('user-input');
    const fileInput = document.getElementById('file-input'); // Hidden file input
    const attachFileButton = document.getElementById('attach-file-button'); // Attach button (+)
    const attachPopover = document.getElementById('attach-popover'); // Attach popover menu
    const sendButton = document.getElementById('send-button'); // Send button (^)
    const filePreviewContainer = document.getElementById('file-preview-container'); // Preview container ref
    const modelSelector = document.getElementById('model-selector'); // <<< ADDED Model selector ref
    const conversationList = document.getElementById('conversation-list');
    const newChatButton = document.getElementById('new-chat-button');
    const openSettingsButton = document.getElementById('open-settings-button');
    const createFolderButton = document.getElementById('create-folder-button'); // Add reference for create folder button
    const settingsPopoverLevel1 = document.getElementById('settings-popover-level1');
    const settingsModalPlaceholder = document.getElementById('settings-modal-placeholder');
    const fontSelector = document.getElementById('font-selector');
    const sidebarSpinner = document.getElementById('sidebar-loading-spinner');
    const sidebarToggleButton = document.getElementById('sidebar-toggle-button');
    const sidebar = document.getElementById('sidebar');
    const sidebarOverlay = document.querySelector('.sidebar-overlay');

    // --- Initialize Managers ---
    convManager.initConversationManager(conversationList, chatBox, userInput);
    settingsManager.initSettingsManager(settingsPopoverLevel1, settingsModalPlaceholder);

    // --- Helper Functions ---

    // Update Send Button State based on input/file
    function updateSendButtonState() {
        if (!userInput || !fileInput || !sendButton) return; // Ensure elements exist
        const hasText = userInput.value.trim().length > 0;
        const hasFile = fileInput.files.length > 0;

        if (hasText || hasFile) {
            ui.enableElement(sendButton); // Enable if text OR file exists
        } else {
            ui.disableElement(sendButton); // Disable if neither exists
        }
    }

    // Generate and display file preview
    function displayFilePreview(file) {
        if (!filePreviewContainer || !file) {
            clearFilePreview(); // Clear if no file
            return;
        }

        const reader = new FileReader();
        const isImage = file.type.startsWith('image/');
        const fileType = file.type.split('/')[1]?.toUpperCase() || 'FILE';

        // Generic file icon (Bootstrap Icons)
        let thumbnailHTML = `
            <svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" fill="currentColor" class="bi bi-file-earmark" viewBox="0 0 16 16">
              <path d="M14 4.5V14a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V2a2 2 0 0 1 2-2h5.5zM11.5 1A1.5 1.5 0 0 0 10 2.5V5h4a.5.5 0 0 1 .5.5v8.5a.5.5 0 0 1-.5.5H4a.5.5 0 0 1-.5-.5V2a.5.5 0 0 1 .5-.5z"/>
              <path d="M10.854 7.146a.5.5 0 0 1 0 .708l-3 3a.5.5 0 0 1-.708 0l-1.5-1.5a.5.5 0 1 1 .708-.708L7.5 9.793l2.646-2.647a.5.5 0 0 1 .708 0"/>
            </svg>
        `;

        // Function to update the preview container once thumbnail is ready
        const updatePreview = (thumbnailContent) => {
            filePreviewContainer.innerHTML = `
                <div class="file-preview-thumbnail">${thumbnailContent}</div>
                <div class="file-preview-info">
                    <span class="file-preview-name" title="${file.name}">${file.name}</span>
                    <span class="file-preview-type">${fileType}</span>
                </div>
                <button class="file-preview-remove-button" title="Remover arquivo">
                    <svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" fill="currentColor" class="bi bi-x-lg" viewBox="0 0 16 16">
                      <path d="M2.146 2.854a.5.5 0 1 1 .708-.708L8 7.293l5.146-5.147a.5.5 0 0 1 .708.708L8.707 8l5.147 5.146a.5.5 0 0 1-.708.708L8 8.707l-5.146 5.147a.5.5 0 0 1-.708-.708L7.293 8z"/>
                    </svg>
                </button>
            `;
            filePreviewContainer.style.display = 'flex'; // Show the container

            // Add event listener to the new remove button
            const removeButton = filePreviewContainer.querySelector('.file-preview-remove-button');
            if (removeButton) {
                removeButton.addEventListener('click', handleRemoveFile);
            }
        };

        if (isImage) {
            reader.onload = function(e) {
                thumbnailHTML = `<img src="${e.target.result}" alt="Preview">`;
                updatePreview(thumbnailHTML);
            }
            reader.readAsDataURL(file); // Read image for preview
        } else {
            // For non-images, just use the generic icon immediately
            updatePreview(thumbnailHTML);
        }
    }

    // Clear file preview and reset file input
    function clearFilePreview() {
        if (filePreviewContainer) {
            filePreviewContainer.innerHTML = '';
            filePreviewContainer.style.display = 'none';
        }
    }

    // Handle remove file button click
    function handleRemoveFile() {
        fileInput.value = ''; // Clear the file input
        clearFilePreview();
        updateSendButtonState(); // Update send button state
    }


    // --- Main Send Message Logic ---
    async function handleSendMessage() {
        let messageText = userInput.value.trim(); // Use let to allow modification
        const file = fileInput.files[0];
        const intendedAction = fileInput.dataset.intendedAction; // Get the stored action

        if (sendButton.disabled) return;
        if ((!messageText && !file) || !chatBox || !userInput || !fileInput) return;

        // Determine the message to display and send
        let messageToSend = messageText;
        let displayMessage = messageText;

        if (file && intendedAction === 'transcribe-audio') {
            messageToSend = "Transcreva este áudio."; // Override message for transcription
            // Optionally display a different message in the chat for the user
            displayMessage = `(Solicitação de transcrição para: ${file.name})`;
            // Clear the intended action after use
            delete fileInput.dataset.intendedAction;
        } else if (file && !messageText) {
            // If only a file is sent (not for transcription), display file name
            displayMessage = `(Arquivo enviado: ${file.name})`;
        }

        // Add the user's message/action to the chatbox
        if (displayMessage || file) { // Add if there's text to display OR a file was involved
            ui.addMessageToChatbox(displayMessage || `(Arquivo: ${file.name})`, 'user', chatBox);
        }

        userInput.value = '';
        fileInput.value = '';
        clearFilePreview();
        resetTextareaHeight(userInput);
        updateSendButtonState();

        ui.disableElement(userInput);
        ui.disableElement(fileInput);
        ui.disableElement(attachFileButton);
        ui.disableElement(sendButton);

        ui.addMessageToChatbox('<span>.</span><span>.</span><span>.</span>', 'bot', chatBox);

        try {
            const formData = new FormData();
            formData.append('message', messageToSend); // Send the potentially overridden message
            if (file) formData.append('file', file);

            const data = await api.sendMessage(formData); // API response might contain { response, image_data?, ... }

            const indicatorElement = chatBox.querySelector('.typing-indicator');
            if (indicatorElement) chatBox.removeChild(indicatorElement);

            // Display bot response (text and potentially image)
            ui.addMessageToChatbox(data.response, 'bot', chatBox, data.image_data); // <<< Pass image_data

            if (data.new_conversation_id) {
                console.log(`Main: New conversation ${data.new_conversation_id} created.`);
                convManager.setCurrentConversationId(data.new_conversation_id);
                await convManager.loadAndDisplayConversations();
                ui.setActiveConversationInSidebar(data.new_conversation_id, conversationList);
            }

        } catch (error) {
            console.error('Main: Error sending message/file:', error);
            const indicatorElementOnError = chatBox.querySelector('.typing-indicator');
            if (indicatorElementOnError) chatBox.removeChild(indicatorElementOnError);
            ui.displayErrorInChat('Desculpe, não foi possível enviar sua mensagem/arquivo...', error, chatBox);
        } finally {
            ui.enableElement(userInput);
            ui.enableElement(fileInput);
            ui.enableElement(attachFileButton);
            updateSendButtonState();
        }
    }

    // --- Helper Functions (Popovers) ---

    function toggleAttachPopover() {
        if (!attachPopover) return;
        const isVisible = attachPopover.style.display === 'block';
        attachPopover.style.display = isVisible ? 'none' : 'block';
        attachFileButton.setAttribute('aria-expanded', !isVisible);
        if (!isVisible && settingsPopoverLevel1 && settingsPopoverLevel1.style.display === 'block') {
            settingsManager.toggleSettingsPopoverLevel1();
        }
    }

    function hideAttachPopover() {
        if (attachPopover && attachPopover.style.display === 'block') {
            attachPopover.style.display = 'none';
            attachFileButton.setAttribute('aria-expanded', 'false');
        }
    }

    // --- Event Listeners ---

    function autoResizeTextarea(textarea) {
        textarea.style.height = 'auto';
        textarea.style.height = textarea.scrollHeight + 'px';
    }

    function resetTextareaHeight(textarea) {
        textarea.style.height = 'auto';
    }

    if (userInput) {
        userInput.addEventListener('input', () => {
            autoResizeTextarea(userInput);
            updateSendButtonState();
        });
    }

    if (attachFileButton && fileInput) {
        attachFileButton.addEventListener('click', (e) => {
            e.stopPropagation();
            toggleAttachPopover();
        });
    }

    if (attachPopover) {
        attachPopover.addEventListener('click', (e) => {
            const button = e.target.closest('button[data-action]');
            if (!button) return;
            const action = button.dataset.action;
            e.stopPropagation();
            // Trigger file input for regular file, image, or transcription
            if (action === 'trigger-file-input' || action === 'upload-image' || action === 'transcribe-audio') {
                // Store the intended action (optional, but good for clarity later)
                fileInput.dataset.intendedAction = action; // Store 'transcribe-audio' or others
                fileInput.click();
                hideAttachPopover();
            }
        });
    }

    if (fileInput) {
        fileInput.addEventListener('change', () => {
            const file = fileInput.files[0];
            if (file) {
                console.log(`File selected: ${file.name}`);
                displayFilePreview(file);
            } else {
                console.log("File selection cancelled.");
                clearFilePreview();
            }
            updateSendButtonState();
        });
    }

    if (sendButton) {
        sendButton.addEventListener('click', handleSendMessage);
    }

    if (userInput && sendButton) {
        userInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                if (!sendButton.disabled) {
                    sendButton.click();
                }
            }
        });
    }

    // Model Selector Listener Removed
    /*
    if (modelSelector) {
        modelSelector.addEventListener('change', async () => {
            // ... listener code removed ...
        });
    }
    */

    if (newChatButton) newChatButton.addEventListener('click', () => {
        hideAttachPopover();
        clearFilePreview();
        convManager.handleNewChat();
    });

    if (openSettingsButton) {
        openSettingsButton.addEventListener('click', (e) => {
            e.stopPropagation();
            hideAttachPopover();
            settingsManager.toggleSettingsPopoverLevel1();
        });
    }

    if (settingsPopoverLevel1) {
        settingsPopoverLevel1.addEventListener('click', (e) => {
            if (e.target.tagName === 'A') {
                const targetModal = e.target.dataset.targetModal;
                const targetTab = e.target.dataset.targetTab;
                if (targetModal === 'settings-modal-main') {
                    e.preventDefault();
                    settingsManager.toggleSettingsPopoverLevel1();
                    settingsManager.openSettingsModal(targetTab);
                }
            }
        });
    }

    // Updated Sidebar Click Listener (Handles Folders and Conversations)
    if (conversationList) {
        conversationList.addEventListener('click', (e) => {
            const target = e.target;
            const actionTarget = target.closest('[data-action]');
            if (!actionTarget) return;

            const action = actionTarget.dataset.action;
            const convItem = target.closest('.conversation-item');
            const folderItem = target.closest('.folder-item'); // Check if click is within a folder item

            if (action === 'select' && convItem) {
                const conversationId = convItem.dataset.conversationId;
                hideAttachPopover();
                clearFilePreview(); // Clear file preview when switching convos
                convManager.handleConversationSelect(conversationId);
            } else if (action === 'toggle-conversation-popover' && convItem) {
                e.stopPropagation();
                ui.toggleActionsPopover(convItem, 'conversation');
            } else if (action === 'toggle-folder-popover' && folderItem) {
                e.stopPropagation();
                ui.toggleActionsPopover(folderItem, 'folder');
            } else if (action === 'toggle-folder' && folderItem) {
                // Toggle folder open/closed state
                const contents = folderItem.querySelector('.folder-contents');
                const icon = folderItem.querySelector('.folder-toggle-icon');
                const isOpen = folderItem.classList.toggle('folder-open');
                if (contents) contents.style.display = isOpen ? 'block' : 'none';
                if (icon) icon.innerHTML = isOpen ? '&#9660;' : '&#9654;'; // Down or Right arrow
            }
        });
    }

    // Updated Body Click Listener (Handles Popover Actions for Folders and Conversations)
    document.body.addEventListener('click', (e) => {
        const target = e.target;
        const popoverButton = target.closest('.actions-popover button[data-action]');

        if (popoverButton) {
            e.stopPropagation(); // Prevent body listener from immediately closing the popover
            const action = popoverButton.dataset.action;
            const conversationId = popoverButton.dataset.conversationId;
            const folderId = popoverButton.dataset.folderId;

            // Find the corresponding list item
            let listItem = null;
            if (conversationId) {
                listItem = conversationList?.querySelector(`.conversation-item[data-conversation-id="${conversationId}"]`);
            } else if (folderId) {
                listItem = conversationList?.querySelector(`.folder-item[data-folder-id="${folderId}"]`);
            }

            if (!listItem) {
                console.warn("Could not find list item for popover action:", action, conversationId || folderId);
            } else {
                // Handle actions
                if (action === 'edit' && conversationId) {
                    convManager.handleEditConversation(listItem);
                } else if (action === 'delete' && conversationId) {
                    convManager.handleDeleteConversation(listItem);
                } else if (action === 'edit-folder' && folderId) {
                    convManager.handleEditFolder(listItem);
                } else if (action === 'delete-folder' && folderId) {
                    convManager.handleDeleteFolder(listItem);
                }
            }

            // Always hide popovers after an action is triggered
            ui.hideAllPopovers(null, settingsPopoverLevel1);
            hideAttachPopover(); // Also hide attach popover if open
        }
        // No 'else' here, the general click listener below handles clicks outside popovers
    });

    document.addEventListener('click', (e) => {
        if (settingsPopoverLevel1 && settingsPopoverLevel1.style.display === 'block' && !settingsPopoverLevel1.contains(e.target) && e.target !== openSettingsButton && !openSettingsButton.contains(e.target)) {
             settingsManager.toggleSettingsPopoverLevel1();
        }
        if (attachPopover && attachPopover.style.display === 'block' && !attachPopover.contains(e.target) && e.target !== attachFileButton && !attachFileButton.contains(e.target)) {
            hideAttachPopover();
        }
        const removeButton = filePreviewContainer?.querySelector('.file-preview-remove-button');
        if (!removeButton || !removeButton.contains(e.target)) {
             ui.hideAllPopovers(e, settingsPopoverLevel1);
        }
    });

    if (sidebarToggleButton && sidebar && sidebarOverlay) {
        const toggleSidebar = () => {
            const isVisible = sidebar.classList.toggle('sidebar-mobile-visible');
            sidebarOverlay.classList.toggle('active', isVisible);
            sidebarToggleButton.setAttribute('aria-expanded', isVisible);
            if (!isVisible) {
                hideAttachPopover();
                settingsManager.hideSettingsPopoverLevel1();
            }
        };
        sidebarToggleButton.addEventListener('click', (e) => {
            e.stopPropagation();
            toggleSidebar();
        });
        sidebarOverlay.addEventListener('click', () => {
            if (sidebar.classList.contains('sidebar-mobile-visible')) {
                toggleSidebar();
            }
        });
        document.addEventListener('click', (e) => {
             if (window.innerWidth <= 768 &&
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

    // Create Folder Button Listener
    if (createFolderButton) {
        createFolderButton.addEventListener('click', () => {
            convManager.handleCreateFolder();
        });
    }

    // --- Drag and Drop ---
    let draggedItem = null; // To store the element being dragged
    let originalFolderId = null; // To store the original folder ID for revert

    if (conversationList) {
        // Drag Start: Identify the conversation being dragged
        conversationList.addEventListener('dragstart', (e) => {
            const target = e.target.closest('.conversation-item');
            if (target && target.draggable) {
                draggedItem = target; // Store the element being dragged
                // No need to store originalFolderId here, get it from draggedItem on drop
                e.dataTransfer.setData('text/plain', target.dataset.conversationId);
                e.dataTransfer.effectAllowed = 'move';
                setTimeout(() => { // Make item semi-transparent during drag
                    if (draggedItem) draggedItem.classList.add('dragging'); // Check if draggedItem still exists
                }, 0);
                console.log(`Drag Start: Conv ${target.dataset.conversationId}`);
            } else {
                e.preventDefault(); // Prevent dragging non-draggable items
            }
        });

        // Drag Over: Indicate valid drop targets
        conversationList.addEventListener('dragover', (e) => {
            // console.log('Drag Over Target:', e.target); // Log the raw target
            const dropTarget = e.target.closest('[data-drop-target]');
            // console.log('Closest Drop Target:', dropTarget); // Log the identified drop target
            if (dropTarget && draggedItem) {
                // console.log('Allowing drop on:', dropTarget.dataset.dropTarget, dropTarget.dataset.folderId);
                e.preventDefault(); // Allow drop
                e.dataTransfer.dropEffect = 'move';
                // Add visual cue to the target area
                dropTarget.classList.add('drag-over');
            } else {
                // console.log('Drop not allowed on this element.');
            }
        });

        // Drag Leave: Remove visual cue when leaving a drop target
        conversationList.addEventListener('dragleave', (e) => {
            const dropTarget = e.target.closest('[data-drop-target]');
            // Only remove the class from the specific target being left
            if (dropTarget && !dropTarget.contains(e.relatedTarget)) {
                 dropTarget.classList.remove('drag-over');
            }
            // If leaving the main list container entirely, ensure all drag-over classes are removed
            if (!conversationList.contains(e.relatedTarget)) {
                conversationList.querySelectorAll('.drag-over').forEach(el => el.classList.remove('drag-over'));
            }
        });

        // Drag End: Clean up regardless of drop success
        conversationList.addEventListener('dragend', (e) => {
            if (draggedItem) {
                draggedItem.classList.remove('dragging');
            }
            conversationList.querySelectorAll('.drag-over').forEach(el => el.classList.remove('drag-over'));
            draggedItem = null;
            // originalFolderId = null; // No longer stored globally
            console.log("Drag End");
        });

        // Drop: Handle the actual move
        conversationList.addEventListener('drop', async (e) => {
            e.preventDefault(); // Prevent default browser drop behavior
            console.log('Drop Event Raw Target:', e.target); // Log the actual element clicked
            const dropTargetElement = e.target.closest('[data-drop-target]');
            console.log('Closest Drop Target on Drop:', dropTargetElement);

            if (!dropTargetElement || !draggedItem) {
                console.log("Drop ignored: Outside target or no dragged item.");
                // Ensure cleanup even if drop is invalid
                if (draggedItem) draggedItem.classList.remove('dragging');
                conversationList.querySelectorAll('.drag-over').forEach(el => el.classList.remove('drag-over'));
                draggedItem = null;
                // originalFolderId = null; // No longer used here
                return;
            }

            dropTargetElement.classList.remove('drag-over'); // Remove visual cue

            const conversationId = e.dataTransfer.getData('text/plain');
            const targetType = dropTargetElement.dataset.dropTarget; // 'root' or 'folder'
            const targetFolderId = targetType === 'folder' ? dropTargetElement.dataset.folderId : null;

            // Determine current folder by checking the direct parent element
            let currentFolderId = null;
            const directParent = draggedItem.parentElement;
            console.log('Dragged Item Parent:', directParent); // Log the parent

            if (directParent && directParent.classList.contains('folder-contents')) {
                console.log('Parent is folder-contents. Finding parent folder item...'); // Log entry
                const parentFolderItem = directParent.closest('.folder-item');
                console.log('Found Parent Folder Item:', parentFolderItem); // Log found item
                if (parentFolderItem) {
                    currentFolderId = parentFolderItem.dataset.folderId || null;
                }
            } else {
                console.log('Parent is NOT folder-contents. Assuming root.'); // Log else case
            }

            console.log(`Drop: Conv ${conversationId} onto Target Type: ${targetType}, Target Folder: ${targetFolderId}, Current Folder (determined): ${currentFolderId}`);

            // Add specific logging before comparison
            console.log(`Values before comparison: targetFolderId=${targetFolderId} (type: ${typeof targetFolderId}), currentFolderId=${currentFolderId} (type: ${typeof currentFolderId})`);

            // Only proceed if the target folder is different from the item's current folder
            if (targetFolderId !== currentFolderId) {
                await convManager.handleMoveConversation(conversationId, targetFolderId, draggedItem, dropTargetElement);
            } else {
                console.log("Dropped in the same location (no change needed).");
            }
            // Cleanup happens in dragend
        });
    }


    // --- Initialization ---
    console.log("Initializing conversation list, folders, and model selector..."); // Updated log
    if (sidebarSpinner) sidebarSpinner.style.display = 'flex';

    try {
        // Load conversations and model selector in parallel for faster loading
        await Promise.all([
            // Load conversations
            // Load conversations and folders
            (async () => {
                // This function now handles both conversations and folders internally
                await convManager.loadAndDisplayConversations();
                console.log("Conversation and folder list initialized.");
            })()
            // Model selector loading removed
            /*
            , // Comma removed as this is now the last item
            (async () => {
                if (modelSelector) {
                    // ... model selector init code removed ...
                }
            })()
            */
        ]);
    } catch (error) {
        console.error("Error initializing conversation list:", error);
        if (conversationList) {
             const errorItem = document.createElement('li');
             errorItem.textContent = 'Error loading conversations.';
             errorItem.style.color = 'red';
             conversationList.appendChild(errorItem);
        }
    } finally {
        if (sidebarSpinner) sidebarSpinner.style.display = 'none';
        console.log("Finished conversation list initialization attempt.");
        updateSendButtonState();
        clearFilePreview();
    }

}); // End DOMContentLoaded