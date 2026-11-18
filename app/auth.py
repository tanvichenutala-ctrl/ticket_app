import functools
from flask import (
    Blueprint,
    g,
    jsonify,
    redirect,
    render_template_string,
    request,
    session,
    url_for,
    abort,
)
from werkzeug.security import check_password_hash
from app.models import get_user_by_id, get_user_by_username, ROLES

auth_bp = Blueprint("auth", __name__)

ALLOWED_ROLES = ("employee", "support")


@auth_bp.before_app_request
def load_logged_in_user():
    """Load user record into Flask's `g` object for each request."""
    user_id = session.get("user_id")
    if user_id is None:
        g.user = None
    else:
        g.user = get_user_by_id(user_id)


def login_required(view):
    """Decorator ensuring that the user is authenticated."""
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if session.get("user_id") is None:
            if request.is_json or request.headers.get("Accept") == "application/json":
                return jsonify({"error": "Authentication required"}), 401
            return redirect(url_for("auth.login", next=request.path))
        return view(**kwargs)

    return wrapped_view


def role_required(*allowed_roles):
    """Decorator ensuring that the user is authenticated and possesses an allowed role."""
    def decorator(view):
        @functools.wraps(view)
        def wrapped_view(**kwargs):
            if session.get("user_id") is None:
                if request.is_json or request.headers.get("Accept") == "application/json":
                    return jsonify({"error": "Authentication required"}), 401
                return redirect(url_for("auth.login", next=request.path))

            user_role = session.get("role")
            if user_role not in allowed_roles:
                if request.is_json or request.headers.get("Accept") == "application/json":
                    return jsonify({"error": "Forbidden: insufficient permissions"}), 403
                abort(403)
            return view(**kwargs)

        return wrapped_view

    return decorator


def employee_required(view):
    """Convenience decorator for employee-only endpoints."""
    return role_required("employee")(view)


def support_required(view):
    """Convenience decorator for support-only endpoints."""
    return role_required("support")(view)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Handle user login for employees and support staff."""
    if request.method == "POST":
        data = request.get_json(silent=True) or request.form
        username = (data.get("username") or "").strip()
        password = data.get("password") or ""

        if not username or not password:
            error = "Username and password are required"
            if request.is_json or request.headers.get("Accept") == "application/json":
                return jsonify({"error": error}), 400
            return render_login_page(error=error), 400

        user = get_user_by_username(username)
        if user is None or not check_password_hash(user["password_hash"], password):
            error = "Invalid username or password"
            if request.is_json or request.headers.get("Accept") == "application/json":
                return jsonify({"error": error}), 401
            return render_login_page(error=error), 401

        # Restrict login to employees and support staff only
        if user["role"] not in ALLOWED_ROLES:
            error = "Access denied: unauthorized role"
            if request.is_json or request.headers.get("Accept") == "application/json":
                return jsonify({"error": error}), 403
            return render_login_page(error=error), 403

        # Clear any prior session data and set new credentials
        session.clear()
        session["user_id"] = user["id"]
        session["username"] = user["username"]
        session["role"] = user["role"]

        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({
                "message": "Login successful",
                "user": {
                    "id": user["id"],
                    "username": user["username"],
                    "role": user["role"],
                }
            }), 200

        next_url = request.args.get("next") or url_for("tickets.list_tickets") if "tickets.list_tickets" in auth_bp.root_path else "/tickets"
        return redirect(next_url)

    # GET request: render simple login form
    return render_login_page()


@auth_bp.route("/logout", methods=["GET", "POST"])
def logout():
    """Clear session data and log out the user."""
    session.clear()
    if request.is_json or request.headers.get("Accept") == "application/json":
        return jsonify({"message": "Logout successful"}), 200
    return redirect(url_for("auth.login"))


def render_login_page(error: str = None) -> str:
    """Minimal inline HTML fallback for login page before full templates are added."""
    template = """
    <!doctype html>
    <html lang="en">
    <head><meta charset="utf-8"><title>Login - Support Ticket App</title></head>
    <body>
        <h2>Login</h2>
        {% if error %}<p style="color: red;">{{ error }}</p>{% endif %}
        <form method="post" action="{{ url_for('auth.login') }}">
            <div>
                <label for="username">Username:</label>
                <input id="username" name="username" type="text" required>
            </div>
            <div>
                <label for="password">Password:</label>
                <input id="password" name="password" type="password" required>
            </div>
            <button type="submit">Log In</button>
        </form>
    </body>
    </html>
    """
    return render_template_string(template, error=error)
