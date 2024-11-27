from functools import wraps
from flask import flash, redirect, url_for
from flask_login import current_user

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('You need to be an admin to access this page.')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

def agent_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'agent':
            flash('You need to be an agent to access this page.')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

def client_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'client':
            flash('You need to be a client to access this page.')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function
