import * as apiClient from './api_client.js';
// Assuming settings.js exposes populateSettingsForms globally for now
// import { populateSettingsForms } from './settings.js'; // This would require settings.js to be a module too

// --- State & Elements ---
let settingsPopoverLevel1 = null;
let settingsModalPlaceholder = null;
// Dynamically loaded elements
let settingsModalOverlay = null;
let settingsModalMain = null;
let closeSettingsButton = null;
// let accountSubLayoutMinHeight = 0; // Remove variable, use data attribute instead
let accountSubLayoutMinHeight = 0; // Variable to store the calculated min-height

/**
 * Initializes the settings manager with necessary DOM elements.
 * @param {HTMLElement} popoverEl - The level 1 settings popover element.
 * @param {HTMLElement} placeholderEl - The placeholder div for the modal.
 */
export function initSettingsManager(popoverEl, placeholderEl) {
    settingsPopoverLevel1 = popoverEl;
    settingsModalPlaceholder = placeholderEl;

    // Initial hide for popover
    if (settingsPopoverLevel1) {
        settingsPopoverLevel1.style.display = 'none';
        settingsPopoverLevel1.classList.remove('visible');
    }
}

/**
 * Toggles the visibility of the level 1 settings popover.
 */
export function toggleSettingsPopoverLevel1() {
    if (!settingsPopoverLevel1) return;
    const isVisible = settingsPopoverLevel1.classList.toggle('visible');
    settingsPopoverLevel1.style.display = isVisible ? 'block' : 'none';
}

/**
 * Fetches user settings data from the API and calls the form population function.
 * Assumes populateSettingsForms is available globally or imported.
 */
async function fetchAndPopulateSettings() {
    console.log("SettingsManager: Fetching user settings data...");
    try {
        const data = await apiClient.fetchUserSettingsData(); // { user, config }

        // Call the function in settings.js (or imported module) to populate the forms
        if (typeof window.populateSettingsForms === 'function') {
            window.populateSettingsForms(data.user, data.config);
        } else {
            console.error("populateSettingsForms function not found.");
        }
    } catch (error) {
        console.error("SettingsManager: Failed to fetch or populate settings:", error);
        // Optionally display an error in the modal
        if (settingsModalMain) {
             const errorElement = settingsModalMain.querySelector('#settings-load-error'); // Need an element for this
             if (errorElement) errorElement.textContent = `Error loading settings: ${error.message}`;
        }
    }
}

/**
 * Opens the settings modal, loading its content dynamically if needed.
 * @param {string} [targetTabId='account'] - The ID of the tab to activate initially.
 */
export async function openSettingsModal(targetTabId = 'account') {
    if (!settingsModalPlaceholder) {
        console.error("Settings modal placeholder not found!");
        return;
    }

    // Check if modal content is already loaded by looking for the overlay inside the placeholder
    let modalContentLoaded = settingsModalPlaceholder.querySelector('#settings-page-overlay');

    if (!modalContentLoaded) {
        console.log("Settings modal not loaded, fetching...");
        try {
            const modalHtml = await apiClient.fetchSettingsModalHtml();
            settingsModalPlaceholder.innerHTML = modalHtml; // Inject the HTML

            // Now that HTML is injected, query for the elements *within the placeholder*
            settingsModalOverlay = settingsModalPlaceholder.querySelector('#settings-page-overlay');
            settingsModalMain = settingsModalPlaceholder.querySelector('#settings-modal-main');
            closeSettingsButton = settingsModalPlaceholder.querySelector('#close-settings-button');

            if (!settingsModalOverlay || !settingsModalMain || !closeSettingsButton) {
                 console.error("Failed to find modal elements after loading!");
                 settingsModalPlaceholder.innerHTML = '<p style="color:red;">Error loading settings modal content.</p>';
                 return;
            }

            // Attach close button listener dynamically
            closeSettingsButton.addEventListener('click', closeSettingsModal);
            // Attach listener to close when clicking overlay background
             settingsModalOverlay.addEventListener('click', (event) => {
                 if (event.target === settingsModalOverlay) {
                     closeSettingsModal();
                 }
             });

            console.log("Settings modal HTML loaded and elements found.");

            // Trigger form event listeners setup in settings.js if needed.
            // This might require settings.js to expose an init function or be refactored.
            // For now, we assume settings.js listeners are attached via DOMContentLoaded
            // or delegated, and populateSettingsForms is sufficient.

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

    // Fetch/refresh data and populate forms
    await fetchAndPopulateSettings();

    // Activate the correct tab
    const tabs = settingsModalMain.querySelectorAll('.settings-tab');
    let activated = false;
    tabs.forEach(tab => {
        const isActive = tab.id === targetTabId;
        tab.classList.toggle('active', isActive);
        if (isActive) activated = true;
    });
    // Fallback if targetTabId doesn't match any tab
    if (!activated && tabs.length > 0) {
        tabs[0].classList.add('active');
        targetTabId = tabs[0].id; // Update targetTabId if fallback occurred
    }

    // --- Calculate and store min-height for account sub-layout as data attribute ---
    if (targetTabId === 'account' && settingsModalMain) {
        // Ensure styles are applied and layout is calculated
        requestAnimationFrame(() => { // Use rAF to wait for layout calculation
            const accountTab = settingsModalMain.querySelector('#account');
            const subLayout = accountTab?.querySelector('.settings-sub-layout');
            const profileSection = accountTab?.querySelector('#account-profile-section');

            if (subLayout && profileSection && profileSection.classList.contains('active')) {
                // Temporarily ensure the container is visible if needed for measurement
                // This might not be strictly necessary with rAF, but safer
                const initialDisplay = accountTab.style.display;
                const initialVisibility = accountTab.style.visibility;
                accountTab.style.display = 'flex'; // Ensure it's displayed for measurement
                accountTab.style.visibility = 'hidden'; // Keep it hidden visually during measurement

                const calculatedHeight = subLayout.offsetHeight;
                console.log(`Calculated account sub-layout height: ${calculatedHeight}px`);

                // Store height as data attribute if valid
                if (calculatedHeight > 0) {
                    subLayout.dataset.minHeight = calculatedHeight;
                    // Apply immediately as minHeight style as well
                    subLayout.style.minHeight = `${calculatedHeight}px`;
                } else {
                    console.warn("Calculated height was 0, not setting data attribute.");
                    delete subLayout.dataset.minHeight; // Remove potentially invalid attribute
                    subLayout.style.minHeight = ''; // Clear style
                }

                // Restore original display properties
                accountTab.style.display = initialDisplay;
                accountTab.style.visibility = initialVisibility;

            } else {
                 console.warn("Could not find account sub-layout or profile section wasn't active for height calculation.");
                 // Ensure attribute is removed if calculation fails
                 const existingSubLayout = settingsModalMain.querySelector('#account .settings-sub-layout');
                 if (existingSubLayout) {
                     delete existingSubLayout.dataset.minHeight;
                     existingSubLayout.style.minHeight = '';
                 }
            }
        });
    } else {
         // Ensure attribute is removed if not opening to account tab
         const existingSubLayout = settingsModalMain?.querySelector('#account .settings-sub-layout');
         if (existingSubLayout) {
             delete existingSubLayout.dataset.minHeight;
             existingSubLayout.style.minHeight = '';
         }
    }
    // --- End height calculation ---


    // Show the modal
    settingsModalOverlay.style.display = 'flex';
    setTimeout(() => {
         if (settingsModalOverlay) settingsModalOverlay.classList.add('visible');
    }, 10); // Small delay for transition
    document.body.classList.add('settings-modal-open');
}

/**
 * Closes the settings modal.
 */
export function closeSettingsModal() {
    if (settingsModalOverlay && settingsModalOverlay.classList.contains('visible')) {
         settingsModalOverlay.classList.remove('visible');
         // Use transitionend event to set display: none after fade out
         const handler = () => {
             if (settingsModalOverlay) { // Check if element still exists
                settingsModalOverlay.style.display = 'none';
             }
         };
         settingsModalOverlay.addEventListener('transitionend', handler, { once: true });
         document.body.classList.remove('settings-modal-open');
    } else if (settingsModalOverlay) {
         // If somehow called when not visible, just ensure it's hidden
         settingsModalOverlay.style.display = 'none';
         document.body.classList.remove('settings-modal-open');
    }
}