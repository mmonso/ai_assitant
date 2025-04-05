from flask import Blueprint, request, jsonify, session
import db_utils # Assuming db_utils is accessible
import bcrypt
import config # Import the config module

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
        return jsonify({"errors": errors}), 400
    else:
        # Fetch updated details only if something actually changed
        # Although the current implementation fetches regardless, this is conceptually better
        final_message = "Profile updated successfully." if not success_messages else " ".join(success_messages)
        # Fetch complete details to ensure frontend has latest state
        updated_details = db_utils.get_user_details(user_id)
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
         print(f"Error verifying current password for user {user_id}: {e}")
         return jsonify({"errors": {"password-form": "Error verifying current password."}}), 500

    # Update to new password
    success = db_utils.update_password(user_id, new_password)
    if success:
        # Optionally force logout after password change for security
        # session.pop('user_id', None) ... etc
        return jsonify({"message": "Password updated successfully."}), 200
    else:
        return jsonify({"errors": {"password-form": "Failed to update password due to a database error."}}), 500


@settings_api_bp.route('/delete_account', methods=['DELETE'])
def delete_account():
    """API endpoint to delete the user's account."""
    if 'user_id' not in session:
        return jsonify({"error": "Authentication required"}), 401

    user_id = session['user_id']

    # Optional: Add password confirmation for deletion here if needed

    success = db_utils.delete_user(user_id)
    if success:
        # Clear session completely after deletion
        session.clear()
        return jsonify({"message": "Account deleted successfully."}), 200
    else:
        return jsonify({"error": "Failed to delete account due to a database error."}), 500

@settings_api_bp.route('/get_user_settings', methods=['GET']) # Moved from app.py
def get_user_settings():
    """API endpoint to fetch current user settings for the modal."""
    if 'user_id' not in session:
        return jsonify({"error": "Authentication required"}), 401

    user_id = session['user_id']
    user_details = db_utils.get_user_details(user_id)

    if not user_details:
        return jsonify({"error": "Failed to retrieve user details"}), 500

    # Prepare config data to send to frontend using config module
    config_data = {
        'USERNAME_MIN_LENGTH': config.USERNAME_MIN_LENGTH,
        'USERNAME_MAX_LENGTH': config.USERNAME_MAX_LENGTH,
        'PASSWORD_MIN_LENGTH': config.PASSWORD_MIN_LENGTH,
    }

    return jsonify({"user": user_details, "config": config_data}), 200