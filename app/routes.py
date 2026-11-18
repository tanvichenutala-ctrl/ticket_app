from flask import (
    Blueprint,
    jsonify,
    redirect,
    render_template_string,
    request,
    session,
    url_for,
)
from app.auth import login_required, role_required
from app.models import (
    CATEGORIES,
    PRIORITIES,
    create_ticket,
    get_tickets,
)

tickets_bp = Blueprint("tickets", __name__)


def row_to_dict(row):
    """Convert an sqlite3.Row object into a standard dictionary."""
    return {key: row[key] for key in row.keys()}


@tickets_bp.route("/")
def index():
    """Redirect home to ticket listing or login."""
    if "user_id" in session:
        return redirect(url_for("tickets.list_tickets"))
    return redirect(url_for("auth.login"))


@tickets_bp.route("/tickets", methods=["GET"])
@login_required
def list_tickets():
    """
    List tickets according to role:
    - Employees see only their own tickets.
    - Support staff see all tickets across the organization.
    """
    user_id = session.get("user_id")
    role = session.get("role")

    ticket_rows = get_tickets(user_id=user_id, role=role)
    tickets = [row_to_dict(t) for t in ticket_rows]

    if request.is_json or request.headers.get("Accept") == "application/json":
        return jsonify({"tickets": tickets}), 200

    return render_ticket_list_page(tickets=tickets, role=role, username=session.get("username"))


@tickets_bp.route("/tickets/new", methods=["GET", "POST"])
@login_required
@role_required("employee")
def create_new_ticket():
    """
    Allow employees to submit a new ticket.
    Validates title (1-100 characters) and description on the server.
    """
    if request.method == "POST":
        data = request.get_json(silent=True) or request.form
        title = (data.get("title") or "").strip()
        description = (data.get("description") or "").strip()
        category = (data.get("category") or "").strip()
        priority = (data.get("priority") or "Medium").strip()

        # Input Validations
        errors = []
        if not title:
            errors.append("Title is required and cannot be empty")
        elif len(title) > 100:
            errors.append("Title must be at most 100 characters")

        if not description:
            errors.append("Description is required and cannot be empty")

        if not category:
            errors.append("Category is required")
        elif category not in CATEGORIES:
            errors.append(f"Invalid category '{category}'. Allowed: {', '.join(CATEGORIES)}")

        if priority not in PRIORITIES:
            errors.append(f"Invalid priority '{priority}'. Allowed: {', '.join(PRIORITIES)}")

        if errors:
            error_message = "; ".join(errors)
            if request.is_json or request.headers.get("Accept") == "application/json":
                return jsonify({"error": error_message, "errors": errors}), 400
            return render_ticket_create_page(
                errors=errors,
                form_data={"title": title, "description": description, "category": category, "priority": priority}
            ), 400

        # Create ticket in database
        user_id = session.get("user_id")
        try:
            ticket_id = create_ticket(
                title=title,
                description=description,
                category=category,
                priority=priority,
                created_by=user_id,
            )
        except Exception as e:
            if request.is_json or request.headers.get("Accept") == "application/json":
                return jsonify({"error": str(e)}), 400
            return render_ticket_create_page(errors=[str(e)]), 400

        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({
                "message": "Ticket created successfully",
                "ticket_id": ticket_id
            }), 201

        return redirect(url_for("tickets.list_tickets"))

    # GET request: render the creation form
    return render_ticket_create_page()


# ---------------------------------------------------------------------------
# Inline HTML Rendering Helpers (until full Jinja templates are integrated)
# ---------------------------------------------------------------------------

def render_ticket_list_page(tickets, role, username):
    template = """
    <!doctype html>
    <html lang="en">
    <head><meta charset="utf-8"><title>Support Tickets</title></head>
    <body>
        <header>
            <p>Logged in as: <strong>{{ username }}</strong> (Role: {{ role }}) | <a href="{{ url_for('auth.logout') }}">Logout</a></p>
            {% if role == 'employee' %}
                <p><a href="{{ url_for('tickets.create_new_ticket') }}">+ Create New Ticket</a></p>
            {% endif %}
        </header>
        <main>
            <h2>Support Tickets</h2>
            {% if tickets|length == 0 %}
                <p>No tickets found.</p>
            {% else %}
                <table border="1" cellpadding="6" cellspacing="0">
                    <thead>
                        <tr>
                            <th>#</th>
                            <th>Title</th>
                            <th>Category</th>
                            <th>Priority</th>
                            <th>Status</th>
                            <th>Created By</th>
                            <th>Created Date</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for ticket in tickets %}
                        <tr>
                            <td>{{ ticket.id }}</td>
                            <td>{{ ticket.title }}</td>
                            <td>{{ ticket.category }}</td>
                            <td>{{ ticket.priority }}</td>
                            <td>{{ ticket.status }}</td>
                            <td>{{ ticket.author_username }}</td>
                            <td>{{ ticket.created_at }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            {% endif %}
        </main>
    </body>
    </html>
    """
    return render_template_string(template, tickets=tickets, role=role, username=username)


def render_ticket_create_page(errors=None, form_data=None):
    form_data = form_data or {}
    template = """
    <!doctype html>
    <html lang="en">
    <head><meta charset="utf-8"><title>Create Support Ticket</title></head>
    <body>
        <h2>Create Support Ticket</h2>
        {% if errors %}
            <div style="color: red;">
                <ul>
                {% for err in errors %}
                    <li>{{ err }}</li>
                {% endfor %}
                </ul>
            </div>
        {% endif %}
        <form method="post" action="{{ url_for('tickets.create_new_ticket') }}">
            <div>
                <label for="title">Title (max 100 characters):</label><br>
                <input id="title" name="title" type="text" maxlength="100" value="{{ form_data.get('title', '') }}" required>
            </div>
            <div>
                <label for="category">Category:</label><br>
                <select id="category" name="category" required>
                    <option value="">-- Select Category --</option>
                    {% for cat in categories %}
                        <option value="{{ cat }}" {% if form_data.get('category') == cat %}selected{% endif %}>{{ cat }}</option>
                    {% endfor %}
                </select>
            </div>
            <div>
                <label for="priority">Priority:</label><br>
                <select id="priority" name="priority">
                    {% for prio in priorities %}
                        <option value="{{ prio }}" {% if form_data.get('priority', 'Medium') == prio %}selected{% endif %}>{{ prio }}</option>
                    {% endfor %}
                </select>
            </div>
            <div>
                <label for="description">Description:</label><br>
                <textarea id="description" name="description" rows="5" cols="40" required>{{ form_data.get('description', '') }}</textarea>
            </div>
            <button type="submit">Submit Ticket</button>
            <a href="{{ url_for('tickets.list_tickets') }}">Cancel</a>
        </form>
    </body>
    </html>
    """
    return render_template_string(
        template,
        errors=errors,
        form_data=form_data,
        categories=CATEGORIES,
        priorities=PRIORITIES
    )
