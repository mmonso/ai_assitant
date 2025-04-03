from flask import Blueprint, request, render_template, redirect, url_for, flash, session
import db_utils # Assuming db_utils is accessible

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
        user_id = db_utils.create_user(username, password)
        if user_id:
            flash("Registration successful! Please log in.", "success")
            return redirect(url_for('auth.login')) # Use blueprint name in url_for
        else:
            flash("Registration failed. Username might already exist.", "error")
            return render_template('register.html')
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
        user_id = db_utils.authenticate_user(username, password)
        if user_id:
            session['user_id'] = user_id
            session['username'] = username
            session.pop('current_conversation_id', None) # Clear active chat on login
            flash(f"Welcome back, {username}!", "success")
            return redirect(url_for('main.index')) # Assuming a 'main' blueprint for index
        else:
            flash("Invalid username or password.", "error")
            return render_template('login.html')
    # If GET request
    if 'user_id' in session: # Redirect if already logged in
        return redirect(url_for('main.index'))
    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    """Logs the user out."""
    session.pop('user_id', None)
    session.pop('username', None)
    session.pop('current_conversation_id', None) # Clear active chat on logout
    flash("You have been logged out.", "info")
    return redirect(url_for('auth.login')) # Redirect to login page after logout