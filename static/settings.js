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
    });

    // Tab switching and close button logic removed - handled by settings_manager.js

});