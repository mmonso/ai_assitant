from flask import Blueprint, render_template, session, redirect, url_for, flash
import db_utils # Assuming db_utils is accessible
import config # Import the config module

# Define the blueprint
main_bp = Blueprint('main', __name__, template_folder='../templates')

@main_bp.route('/')
def index():
    """Serves the main chat page, requires login."""
    if 'user_id' not in session:
        flash("Please log in to access the chat.", "info")
        return redirect(url_for('auth.login')) # Redirect to auth blueprint's login

    user_id = session['user_id']
    user_details = db_utils.get_user_details(user_id)
    if not user_details:
        # Handle case where user details might be missing
        flash("Error retrieving user details. Please log in again.", "error")
        session.clear()
        return redirect(url_for('auth.login'))

    # Pass configuration constants needed by index.html (including the modal)
    # Now using the config module
    config_data = {
        'USERNAME_MIN_LENGTH': config.USERNAME_MIN_LENGTH,
        'USERNAME_MAX_LENGTH': config.USERNAME_MAX_LENGTH,
        'PASSWORD_MIN_LENGTH': config.PASSWORD_MIN_LENGTH,
        # Add other config values if needed by the modal in index.html
    }

    # Pass user and config to the main index template
    return render_template('index.html', user=user_details, config=config_data) # Pass config_data as 'config'

@main_bp.route('/get_settings_modal')
def get_settings_modal():
    """Renders the settings modal HTML partial."""
    if 'user_id' not in session:
        # Although JS should prevent unauthorized access, add server-side check
        return "Unauthorized", 401

    user_id = session['user_id']
    user_details = db_utils.get_user_details(user_id)
    if not user_details:
        # Handle case where user details might be missing
        return "Error retrieving user details", 500

    # Prepare config data needed by the modal template
    config_data = {
        'USERNAME_MIN_LENGTH': config.USERNAME_MIN_LENGTH,
        'USERNAME_MAX_LENGTH': config.USERNAME_MAX_LENGTH,
        'PASSWORD_MIN_LENGTH': config.PASSWORD_MIN_LENGTH,
    }

    # Render the partial template
    # Note: We return the rendered HTML string directly, not a full response object
    # The JS will inject this HTML into the DOM.
    return render_template('_settings_modal.html', user=user_details, config=config_data)