import logging # Add logging import
from flask import Blueprint, request, render_template, redirect, url_for, flash, session
import db_utils
from db_utils import DuplicateUserError, DatabaseOperationalError, DatabaseError # Import custom exceptions

log = logging.getLogger(__name__) # Get logger for this module

# Define the blueprint
auth_bp = Blueprint('auth', __name__, template_folder='../templates') # Point to the main templates folder

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Handles user registration."""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if not username or not password:
            flash("Username and password are required.", "error")
            return render_template('register.html') # Renders template from the main folder
        try:
            user_id = db_utils.create_user(username, password)
            log.info(f"User '{username}' registered successfully.")
            flash("Registration successful! Please log in.", "success")
            return redirect(url_for('auth.login'))
        except DuplicateUserError:
            # Specific error for existing username
            flash("Username already exists. Please choose another.", "error")
            return render_template('register.html'), 409 # 409 Conflict
        except (DatabaseOperationalError, DatabaseError) as e:
            # Catch specific DB errors raised from db_utils
            log.error(f"Registration failed for '{username}' due to database error: {e}")
            flash("Registration failed due to a server error. Please try again later.", "error")
            return render_template('register.html'), 500 # Internal Server Error
        except Exception as e:
            # Catch any other unexpected errors
            log.error(f"Unexpected error during registration for '{username}': {e}", exc_info=True)
            flash("An unexpected error occurred during registration.", "error")
            return render_template('register.html'), 500
    # If GET request
    if 'user_id' in session: # Redirect if already logged in
        return redirect(url_for('main.index')) # Assuming a 'main' blueprint for index
    return render_template('register.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Handles user login."""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if not username or not password:
            flash("Username and password are required.", "error")
            return render_template('login.html')
        try:
            user_id = db_utils.authenticate_user(username, password)
            if user_id:
                # Login successful (already logged by db_utils)
                session['user_id'] = user_id
                session['username'] = username
                session.pop('current_conversation_id', None) # Clear active chat on login
                log.info(f"User '{username}' (ID: {user_id}) logged in.")
                flash(f"Welcome back, {username}!", "success")
                return redirect(url_for('main.index')) # Assuming a 'main' blueprint for index
            else:
                # db_utils.authenticate_user returns None for failed auth (wrong user/pass)
                flash("Invalid username or password.", "error")
                return render_template('login.html'), 401 # Unauthorized
        except (DatabaseOperationalError, DatabaseError) as e:
            # Catch specific DB errors raised from db_utils
            log.error(f"Login failed for '{username}' due to database error: {e}")
            flash("Login failed due to a server error. Please try again later.", "error")
            return render_template('login.html'), 500 # Internal Server Error
        except Exception as e:
            # Catch any other unexpected errors
            log.error(f"Unexpected error during login for '{username}': {e}", exc_info=True)
            flash("An unexpected error occurred during login.", "error")
            return render_template('login.html'), 500
    # If GET request
    if 'user_id' in session: # Redirect if already logged in
        return redirect(url_for('main.index'))
    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    """Logs the user out."""
    user_id = session.get('user_id')
    username = session.get('username', 'Unknown User') # Get username before popping session

    # Clear session data
    session.pop('user_id', None)
    session.pop('username', None)
    session.pop('current_conversation_id', None) # Clear active chat on logout

    flash("You have been logged out.", "info")
    if user_id:
        log.info(f"User '{username}' (ID: {user_id}) logged out.")
    else:
        # This case might occur if the logout URL is accessed directly without being logged in
        log.warning("Logout route called without active user session.")
    return redirect(url_for('auth.login')) # Redirect to login page after logout