// Note: This script is now included in index.html and operates on the modal elements within it.

// --- Helper Functions (Keep these) ---
function clearErrors(form) {
    if (!form) return;
    form.querySelectorAll('.form-error').forEach(el => el.textContent = '');
    form.querySelectorAll('.form-success').forEach(el => el.textContent = ''); // Clear success too
}

function displayErrors(form, errors) {
    if (!form) return;
    clearErrors(form); // Clear previous errors first
    for (const field in errors) {
        const errorElement = form.querySelector(`#${field}-error`);
        if (errorElement) {
            errorElement.textContent = errors[field];
        } else {
            // Display general form errors if specific field element not found
            let generalErrorElement = form.querySelector(`#${form.id}-error`); // Try specific form error span
            if (!generalErrorElement) {
                generalErrorElement = form.querySelector('.form-error'); // Fallback to first general error span
            }
             if (generalErrorElement) generalErrorElement.textContent = errors[field];
        }
    }
}

 function displaySuccess(form, message) {
     if (!form) return;
     clearErrors(form);
     const successElement = form.querySelector('.form-success');
     if (successElement) {
         successElement.textContent = message;
         // Optionally clear after a few seconds
         setTimeout(() => { if (successElement) successElement.textContent = ''; }, 5000);
     }
 }

// --- Function to Populate Forms (Called indirectly via settings_manager.js) ---
function populateSettingsForms(userData, configData) {
    console.log("Populating settings forms with data:", userData, configData);
    const profileForm = document.getElementById('profile-form');
    const promptForm = document.getElementById('prompt-form');
    const themeForm = document.getElementById('theme-form'); // Get theme form
    // Password form doesn't need pre-population

    if (!userData || !configData) {
        console.error("Missing user or config data for populating settings.");
        // Optionally display an error message in the modal
        return;
    }

    // Populate Profile Form
    if (profileForm) {
        const usernameInput = profileForm.querySelector('#username');
        const profilePicInput = profileForm.querySelector('#profile_picture_url');
        const userInfoInput = profileForm.querySelector('#user_info'); // Get the new textarea

        if (usernameInput) {
            usernameInput.value = userData.username || '';
            // Update length attributes if they come from config
            usernameInput.minLength = configData.USERNAME_MIN_LENGTH || 3;
            usernameInput.maxLength = configData.USERNAME_MAX_LENGTH || 20;
            // Update help text dynamically
            const usernameHelp = profileForm.querySelector('label[for="username"] + input + .form-error + .help-text');
            if (usernameHelp) {
                 usernameHelp.textContent = `Allowed characters: letters, numbers, underscore. Length: ${configData.USERNAME_MIN_LENGTH || 3}-${configData.USERNAME_MAX_LENGTH || 20}.`;
            }
        }
        if (profilePicInput) {
            profilePicInput.value = userData.profile_picture_url || '';
        }
        if (userInfoInput) { // Populate the user_info textarea
            userInfoInput.value = userData.user_info || '';
        }
    }

    // Populate Password Form Help Text (Min Length)
    const passwordForm = document.getElementById('password-form');
     if (passwordForm) {
         const newPasswordHelp = passwordForm.querySelector('label[for="new_password"] + input + .form-error + .help-text');
         if (newPasswordHelp) {
             newPasswordHelp.textContent = `Minimum length: ${configData.PASSWORD_MIN_LENGTH || 8} characters.`;
         }
         const newPasswordInput = passwordForm.querySelector('#new_password');
         if (newPasswordInput) {
             newPasswordInput.minLength = configData.PASSWORD_MIN_LENGTH || 8;
         }
     }


    // Populate Prompt Form
    if (promptForm) {
        const systemPromptInput = promptForm.querySelector('#system_prompt');
        if (systemPromptInput) {
            systemPromptInput.value = userData.system_prompt || '';
        }
    }

    // Clear any previous success/error messages when populating
    document.querySelectorAll('#settings-modal-main .form-error, #settings-modal-main .form-success').forEach(el => {
        el.textContent = '';
    });

    // Populate Theme Form (Placeholder - assumes theme settings are in userData or configData)
    if (themeForm) {
        const fontSelector = themeForm.querySelector('#font-selector');
        const sizeSelector = themeForm.querySelector('#font-size-selector');
        const spacingSelector = themeForm.querySelector('#line-spacing-selector');

        // Example: Assuming settings are stored like userData.theme_settings.font_family
        // if (fontSelector && userData?.theme_settings?.font_family) {
        //     fontSelector.value = userData.theme_settings.font_family;
        // }
        // if (sizeSelector && userData?.theme_settings?.font_size) {
        //     sizeSelector.value = userData.theme_settings.font_size;
        // }
        // if (spacingSelector && userData?.theme_settings?.line_spacing) {
        //     spacingSelector.value = userData.theme_settings.line_spacing;
        // }
        // console.log("Populated theme form (placeholders active)"); // Add console log if needed
    }
}
// Expose the function to the global scope (for settings_manager.js)
window.populateSettingsForms = populateSettingsForms;


// --- Event Listener using Event Delegation ---
document.addEventListener('DOMContentLoaded', () => {
    // Attach one listener to a static parent (e.g., document.body or a modal container)
    document.body.addEventListener('submit', async (e) => {
        // Check if the submitted element is one of our forms
        const submittedForm = e.target;

        // Profile Form Submission
        if (submittedForm.id === 'profile-form') {
            e.preventDefault();
            clearErrors(submittedForm);
            const formData = new FormData(submittedForm);
            const data = Object.fromEntries(formData.entries());

            try {
                const response = await fetch('/api/settings/profile', {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data),
                });
                const result = await response.json();
                if (!response.ok) {
                    displayErrors(submittedForm, result.errors || { form: result.error || 'An unknown error occurred.' });
                } else {
                    displaySuccess(submittedForm, result.message || 'Profile updated successfully.');
                    // Optionally update username display elsewhere if needed
                }
            } catch (error) {
                console.error('Error updating profile:', error);
                displayErrors(submittedForm, { form: 'Failed to connect to server.' });
            }
        }

        // Password Form Submission
        else if (submittedForm.id === 'password-form') {
            e.preventDefault();
            clearErrors(submittedForm);
            const formData = new FormData(submittedForm);
            const data = Object.fromEntries(formData.entries());

             if (data.new_password !== data.confirm_password) {
                 displayErrors(submittedForm, { confirm_password: "New passwords do not match." });
                 return;
             }

            try {
                const response = await fetch('/api/settings/password', {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data),
                });
                const result = await response.json();
                if (!response.ok) {
                    displayErrors(submittedForm, result.errors || { 'password-form': result.error || 'An unknown error occurred.' });
                } else {
                    displaySuccess(submittedForm, result.message || 'Password updated successfully.');
                    submittedForm.reset(); // Clear password fields on success
                }
            } catch (error) {
                console.error('Error changing password:', error);
                displayErrors(submittedForm, { 'password-form': 'Failed to connect to server.' });
            }
        }

         // Prompt Form Submission
         else if (submittedForm.id === 'prompt-form') {
             e.preventDefault();
             clearErrors(submittedForm);
             const formData = new FormData(submittedForm);
             const data = Object.fromEntries(formData.entries());
             console.log("Submitting prompt form data:", data); // Add log here

             try {
                 const response = await fetch('/api/settings/profile', { // Uses profile endpoint
                     method: 'PUT',
                     headers: { 'Content-Type': 'application/json' },
                     body: JSON.stringify(data),
                 });
                 const result = await response.json();
                 if (!response.ok) {
                     displayErrors(submittedForm, result.errors || { form: result.error || 'An unknown error occurred.' });
                 } else {
                     displaySuccess(submittedForm, result.message || 'System prompt updated successfully.');
                 }
             } catch (error) {
                 console.error('Error updating prompt:', error);
                 displayErrors(submittedForm, { form: 'Failed to connect to server.' });
             }
         }

        // Delete Account Form Submission
        else if (submittedForm.id === 'delete-form') {
            e.preventDefault();
            clearErrors(submittedForm);

            if (!confirm('ARE YOU ABSOLUTELY SURE?\n\nDeleting your account is permanent and cannot be undone. All your conversations and messages will be lost.')) {
                return;
            }

            try {
                const response = await fetch('/api/settings/delete_account', { method: 'DELETE' });
                const result = await response.json();
                if (!response.ok) {
                     displayErrors(submittedForm, { form: result.error || 'Failed to delete account.' });
                } else {
                    alert(result.message || 'Account deleted successfully.');
                    window.location.href = '/login'; // Redirect on success
                }
            } catch (error) {
                console.error('Error deleting account:', error);
                displayErrors(submittedForm, { form: 'Failed to connect to server.' });
            }
        }
        // Removed extra closing brace here

        // Theme Form Submission
        else if (submittedForm.id === 'theme-form') {
            e.preventDefault();
            clearErrors(submittedForm);
            const formData = new FormData(submittedForm);
            const data = Object.fromEntries(formData.entries());
            console.log("Submitting theme form data:", data);

            try {
                // Assuming a PUT request to a new endpoint
                const response = await fetch('/api/settings/theme', {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data),
                });
                const result = await response.json();
                if (!response.ok) {
                    displayErrors(submittedForm, result.errors || { 'theme-form': result.error || 'An unknown error occurred.' });
                } else {
                    displaySuccess(submittedForm, result.message || 'Theme settings updated successfully.');
                    // Optionally: Apply theme changes immediately without page reload
                    // applyThemeSettings(data); // You would need to implement this function
                }
            } catch (error) {
                console.error('Error updating theme settings:', error);
                displayErrors(submittedForm, { 'theme-form': 'Failed to connect to server.' });
            }
        }
    });

    // --- Account Sub-Navigation Click Handler ---
    document.body.addEventListener('click', (e) => {
        const button = e.target.closest('.sub-nav-button');
        // Ensure the click is on a sub-nav button AND within the account tab
        if (button && button.closest('#account')) {
            const targetId = button.dataset.target;
            const targetSection = document.getElementById(targetId);
            const subNavContainer = button.closest('.settings-sub-nav');
            const subLayout = button.closest('.settings-sub-layout'); // Get the sub-layout container
            const subContentContainer = subLayout?.querySelector('.settings-sub-content');

            if (!targetSection || !subNavContainer || !subLayout || !subContentContainer) { // Check subLayout too
                console.error("Could not find target section or containers for sub-navigation.");
                return;
            }

            // Apply the minimum height stored in the data attribute
            const storedMinHeight = subLayout.dataset.minHeight;
            if (storedMinHeight && parseInt(storedMinHeight, 10) > 0) {
                subLayout.style.minHeight = `${storedMinHeight}px`;
                console.log(`Applied min-height: ${storedMinHeight}px`);
            } else {
                // Fallback or remove existing minHeight if attribute is missing/invalid
                subLayout.style.minHeight = ''; // Or set to a default like '300px' if preferred
                console.log("Applied fallback min-height (cleared).");
            }

            // Remove active class from all buttons in this nav
            subNavContainer.querySelectorAll('.sub-nav-button').forEach(btn => btn.classList.remove('active'));
            // Remove active class from all sections in this content area
            subContentContainer.querySelectorAll('.account-section').forEach(sec => sec.classList.remove('active'));

            // Add active class to the clicked button and target section
            button.classList.add('active');
            targetSection.classList.add('active');
        }
    });



    // Function to apply theme settings dynamically (Example - Implement as needed)
    /*
    function applyThemeSettings(settings) {
        if (settings.font_family) {
            document.documentElement.style.setProperty('--font-family-base', settings.font_family);
        }
        if (settings.font_size) {
            document.documentElement.style.setProperty('--font-size-base', settings.font_size);
        }
        if (settings.line_spacing) {
            // Assuming you have a CSS variable for chat line height, e.g., --chat-line-height
            document.documentElement.style.setProperty('--chat-line-height', settings.line_spacing);
        }
        console.log("Applied theme settings dynamically:", settings);
    }
    */

    // Tab switching and close button logic removed - handled by settings_manager.js

});