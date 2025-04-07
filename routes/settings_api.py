import logging # Add logging import
from flask import Blueprint, request, jsonify, session
import db_utils # Assuming db_utils is accessible
from db_utils import update_user_theme # Import the new function
import bcrypt
import config # Import the config module

log = logging.getLogger(__name__) # Get logger for this module
# Define the blueprint
settings_api_bp = Blueprint('settings_api', __name__, url_prefix='/api/settings')

@settings_api_bp.route('/profile', methods=['PUT'])
def update_profile():
    """API endpoint to update username, profile picture URL, and system prompt."""
    if 'user_id' not in session:
        return jsonify({"error": "Authentication required"}), 401
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    user_id = session['user_id']
    errors = {}
    success_messages = []
    updated_fields = {} # Track which fields were actually updated

    # --- Update Username ---
    if 'username' in data: # Check if username field was included
        new_username = data['username']
        current_details = db_utils.get_user_details(user_id)
        if new_username != current_details.get('username'): # Only update if changed
            # Use constants from config module
            if not (config.USERNAME_MIN_LENGTH <= len(new_username) <= config.USERNAME_MAX_LENGTH):
                 errors['username'] = f"Username must be between {config.USERNAME_MIN_LENGTH} and {config.USERNAME_MAX_LENGTH} characters."
            elif not config.USERNAME_REGEX.match(new_username):
                 errors['username'] = "Username can only contain letters, numbers, and underscores."
            else:
                success = db_utils.update_username(user_id, new_username)
                if success:
                    session['username'] = new_username # Update session username
                    success_messages.append("Username updated.")
                    updated_fields['username'] = new_username
                elif success is False: # Explicit check for False (username taken)
                     errors['username'] = "Username already taken."
                else: # Null indicates DB error
                     errors['username'] = "Database error updating username."

    # --- Update System Prompt ---
    if 'system_prompt' in data: # Check if field was included
         new_system_prompt = data['system_prompt']
         # Basic validation (e.g., length limit) could be added here
         success = db_utils.update_system_prompt(user_id, new_system_prompt)
         if success:
              success_messages.append("System prompt updated.")
              updated_fields['system_prompt'] = new_system_prompt
         else:
              errors['system_prompt'] = "Database error updating system prompt."

    # --- Update Profile Picture (URL only for now) ---
    if 'profile_picture_url' in data:
         new_profile_picture_url = data['profile_picture_url']
         # Add validation for URL format if needed
         success = db_utils.update_profile_picture(user_id, new_profile_picture_url)
         if success:
              success_messages.append("Profile picture URL updated.")
              updated_fields['profile_picture_url'] = new_profile_picture_url
         else:
              errors['profile_picture_url'] = "Database error updating profile picture URL." # Changed key

    # --- Update User Info (as JSON string) ---
    if 'user_info' in data:
        new_user_info = data['user_info']
        # Basic validation: Ensure it's a string (or null).
        # More complex validation (is it valid JSON?) could be added here or on the client-side.
        if isinstance(new_user_info, str) or new_user_info is None:
            success = db_utils.update_user_info(user_id, new_user_info)
            if success:
                success_messages.append("User info updated.")
                updated_fields['user_info'] = new_user_info
            else:
                errors['user_info'] = "Database error updating user info."
        else:
            errors['user_info'] = "User info must be provided as a string (JSON format)."

    if errors:
        # Log the specific validation errors encountered
        log.warning(f"Profile update validation failed for user {user_id}: {errors}")
        return jsonify({"errors": errors}), 400
    elif not updated_fields:
         # No errors, but nothing was actually updated (e.g., submitted same data)
         log.info(f"Profile update request for user {user_id} resulted in no changes.")
         # Return success but indicate no changes were made, or return a specific status?
         # 200 OK with a specific message seems reasonable.
         updated_details = db_utils.get_user_details(user_id) # Still fetch current details
         return jsonify({
             "message": "No profile information needed updating.",
             "user": updated_details
         }), 200
    else:
        # Errors is empty and updated_fields is not empty
        final_message = "Profile updated successfully." if len(success_messages) == 1 else " ".join(success_messages)
        log.info(f"Profile fields {list(updated_fields.keys())} updated successfully for user {user_id}.")
        # Fetch complete details to ensure frontend has latest state
        updated_details = db_utils.get_user_details(user_id)
        if not updated_details:
             log.error(f"Failed to fetch updated user details for user {user_id} after successful profile update.")
             # This is an unexpected state, return an error
             return jsonify({"error": "Profile updated, but failed to retrieve latest details."}), 500

        return jsonify({
            "message": final_message,
            "user": updated_details # Send back updated user info
        }), 200


@settings_api_bp.route('/password', methods=['PUT'])
def change_password():
    """API endpoint to change the user's password."""
    if 'user_id' not in session:
        return jsonify({"error": "Authentication required"}), 401
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    current_password = data.get('current_password')
    new_password = data.get('new_password')
    confirm_password = data.get('confirm_password')
    user_id = session['user_id']

    # Validation
    if not current_password or not new_password or not confirm_password:
        return jsonify({"errors": {"password-form": "All password fields are required."}}), 400 # Use form-id for general error
    if new_password != confirm_password:
        return jsonify({"errors": {"confirm_password": "New passwords do not match."}}), 400
    # Use constant from config module
    if len(new_password) < config.PASSWORD_MIN_LENGTH:
         return jsonify({"errors": {"new_password": f"Password must be at least {config.PASSWORD_MIN_LENGTH} characters long."}}), 400

    # Verify current password
    try:
        with db_utils.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT password_hash FROM users WHERE user_id = ?", (user_id,))
            user_data = cursor.fetchone()
            if not user_data or not bcrypt.checkpw(current_password.encode('utf-8'), user_data['password_hash']):
                return jsonify({"errors": {"current_password": "Current password incorrect."}}), 400
    except Exception as e:
         log.error(f"Error verifying current password hash for user {user_id}: {e}", exc_info=True)
         return jsonify({"errors": {"password-form": "Error verifying current password."}}), 500

    # Update to new password
    success = db_utils.update_password(user_id, new_password)
    if success:
        log.info(f"Password updated successfully for user {user_id}.")
        # Optionally force logout after password change for security
        # session.clear()
        # flash("Password changed. Please log in again.", "info")
        return jsonify({"message": "Password updated successfully."}), 200
    else:
        # db_utils logs the specific DB error
        log.error(f"Password update failed for user {user_id} at API level (db_utils returned False).")
        return jsonify({"errors": {"password-form": "Failed to update password due to a database error."}}), 500


@settings_api_bp.route('/theme', methods=['PUT'])
def update_theme():
    """API endpoint to update user theme settings."""
    if 'user_id' not in session:
        return jsonify({"error": "Authentication required"}), 401
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    user_id = session['user_id']
    errors = {}
    updated_fields = {}

    # Extract theme data (add validation as needed)
    font_family = data.get('font_family')
    font_size = data.get('font_size')
    line_spacing = data.get('line_spacing')

    # Call the database function to update theme settings
    success = update_user_theme(user_id, font_family, font_size, line_spacing)

    if success:
         log.info(f"Theme settings updated for user {user_id}.")
         # Fetch updated details to potentially reflect theme changes if needed by UI immediately
         # updated_details = db_utils.get_user_details(user_id) # Optional
         return jsonify({"message": "Theme settings updated successfully."}), 200
         # return jsonify({"message": "Theme settings updated successfully.", "user": updated_details}), 200 # If sending back details
    else:
         # db_utils logs the specific DB error
         log.error(f"Theme update failed for user {user_id} at API level (db_utils returned False).")
         return jsonify({"errors": {"theme-form": "Failed to update theme settings."}}), 500
@settings_api_bp.route('/delete_account', methods=['DELETE'])
def delete_account():
    """API endpoint to delete the user's account."""
    if 'user_id' not in session:
        return jsonify({"error": "Authentication required"}), 401

    user_id = session['user_id']

    # Optional: Add password confirmation for deletion here if needed

    success = db_utils.delete_user(user_id)
    if success:
        log.info(f"Account deleted successfully for user {user_id}.")
        # Clear session completely after deletion
        session.clear()
        # Flash message might not be seen if redirect happens via JS based on response
        # flash("Your account has been successfully deleted.", "success")
        return jsonify({"message": "Account deleted successfully."}), 200 # Client-side should handle redirect
    else:
        # db_utils logs the specific DB error
        log.error(f"Account deletion failed for user {user_id} at API level (db_utils returned False).")
        return jsonify({"error": "Failed to delete account due to a database error."}), 500

@settings_api_bp.route('/get_user_settings', methods=['GET']) # Moved from app.py
def get_user_settings():
    """API endpoint to fetch current user settings for the modal."""
    if 'user_id' not in session:
        return jsonify({"error": "Authentication required"}), 401

    user_id = session['user_id']
    user_details = db_utils.get_user_details(user_id)

    if not user_details:
        # This implies db_utils.get_user_details returned None
        log.error(f"Failed to retrieve user details for user {user_id} in get_user_settings.")
        # Return 404 as the user resource wasn't found by the ID in the session
        return jsonify({"error": "Failed to retrieve user details (user not found)"}), 404

    # Prepare config data to send to frontend using config module
    config_data = {
        'USERNAME_MIN_LENGTH': config.USERNAME_MIN_LENGTH,
        'USERNAME_MAX_LENGTH': config.USERNAME_MAX_LENGTH,
        'PASSWORD_MIN_LENGTH': config.PASSWORD_MIN_LENGTH,
    }

    return jsonify({"user": user_details, "config": config_data}), 200