from flask import (
    Blueprint,
    jsonify,
    redirect,
    render_template_string,
    request,
    session,
    url_for,
    abort,
)
from app.auth import login_required, role_required
from app.models import (
    CATEGORIES,
    PRIORITIES,
    STATUSES,
    STATUS_FLOW,
    create_ticket,
    get_tickets,
    get_ticket_by_id,
    update_ticket,
    update_ticket_status,
    add_comment,
    get_comments_by_ticket,
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


@tickets_bp.route("/tickets/<int:ticket_id>", methods=["GET"])
@login_required
def get_ticket_detail(ticket_id: int):
    """
    View ticket details and discussion history:
    - Support staff can view any ticket.
    - Employees can view only their own tickets (403 if unauthorized).
    """
    ticket_row = get_ticket_by_id(ticket_id)
    if ticket_row is None:
        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({"error": "Ticket not found"}), 404
        return "Ticket not found", 404

    ticket = row_to_dict(ticket_row)
    current_role = session.get("role")
    current_user_id = session.get("user_id")

    if current_role == "employee" and ticket["created_by"] != current_user_id:
        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({"error": "Forbidden: access denied to this ticket"}), 403
        abort(403)

    comment_rows = get_comments_by_ticket(ticket_id)
    comments = [row_to_dict(c) for c in comment_rows]

    if request.is_json or request.headers.get("Accept") == "application/json":
        return jsonify({"ticket": ticket, "comments": comments}), 200

    return render_ticket_detail_page(ticket=ticket, comments=comments, role=current_role)


@tickets_bp.route("/tickets/<int:ticket_id>/comments", methods=["POST"])
@login_required
def add_ticket_comment(ticket_id: int):
    """
    Add a comment to a ticket.
    - Employees can comment only on their own tickets (403 if unauthorized).
    - Support staff can comment on any ticket.
    - Comments are allowed even when the ticket is Closed.
    - Non-empty content is strictly required.
    """
    ticket = get_ticket_by_id(ticket_id)
    if ticket is None:
        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({"error": "Ticket not found"}), 404
        return "Ticket not found", 404

    current_role = session.get("role")
    current_user_id = session.get("user_id")

    # Employees can only comment on their own tickets
    if current_role == "employee" and ticket["created_by"] != current_user_id:
        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({"error": "Forbidden: you can only comment on your own tickets"}), 403
        abort(403)

    data = request.get_json(silent=True) or request.form
    content = (data.get("content") or "").strip()

    if not content:
        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({"error": "Comment content cannot be empty"}), 400
        return "Comment content cannot be empty", 400

    try:
        comment_id = add_comment(ticket_id=ticket_id, author_id=current_user_id, content=content)
    except Exception as e:
        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({"error": str(e)}), 400
        return str(e), 400

    if request.is_json or request.headers.get("Accept") == "application/json":
        return jsonify({"message": "Comment added successfully", "comment_id": comment_id}), 201

    return redirect(url_for("tickets.get_ticket_detail", ticket_id=ticket_id))


@tickets_bp.route("/tickets/<int:ticket_id>/status", methods=["POST"])
@login_required
def change_ticket_status(ticket_id: int):
    """
    Update ticket status.
    Strictly enforced on the server for support staff only.
    Closed tickets cannot be modified or reopened.
    """
    current_role = session.get("role")
    if current_role != "support":
        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({"error": "Only support staff can change a ticket's status"}), 403
        abort(403)

    ticket = get_ticket_by_id(ticket_id)
    if ticket is None:
        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({"error": "Ticket not found"}), 404
        return "Ticket not found", 404

    data = request.get_json(silent=True) or request.form
    new_status = data.get("status") or data.get("new_status")

    if not new_status:
        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({"error": "Status is required"}), 400
        return "Status is required", 400

    try:
        update_ticket_status(ticket_id, new_status=new_status, user_role=current_role)
    except PermissionError as e:
        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({"error": str(e)}), 403
        abort(403)
    except ValueError as e:
        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({"error": str(e)}), 400
        return str(e), 400

    if request.is_json or request.headers.get("Accept") == "application/json":
        return jsonify({"message": "Status updated successfully", "status": new_status}), 200

    return redirect(url_for("tickets.get_ticket_detail", ticket_id=ticket_id))


@tickets_bp.route("/tickets/<int:ticket_id>/edit", methods=["POST"])
@login_required
def edit_ticket(ticket_id: int):
    """
    Allow an employee to edit their own non-closed ticket.
    Closed tickets cannot be edited.
    """
    ticket = get_ticket_by_id(ticket_id)
    if ticket is None:
        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({"error": "Ticket not found"}), 404
        return "Ticket not found", 404

    current_user_id = session.get("user_id")
    current_role = session.get("role")

    if current_role != "employee" or ticket["created_by"] != current_user_id:
        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({"error": "Forbidden: you can only edit your own tickets"}), 403
        abort(403)

    if ticket["status"] == "Closed":
        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({"error": "A Closed ticket cannot be edited"}), 400
        return "A Closed ticket cannot be edited", 400

    data = request.get_json(silent=True) or request.form
    title = data.get("title")
    description = data.get("description")
    category = data.get("category")
    priority = data.get("priority")

    try:
        update_ticket(
            ticket_id,
            title=title,
            description=description,
            category=category,
            priority=priority,
        )
    except ValueError as e:
        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({"error": str(e)}), 400
        return str(e), 400

    if request.is_json or request.headers.get("Accept") == "application/json":
        return jsonify({"message": "Ticket updated successfully"}), 200

    return redirect(url_for("tickets.get_ticket_detail", ticket_id=ticket_id))


# ---------------------------------------------------------------------------
# Inline HTML Rendering Helpers
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
                            <th>Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for ticket in tickets %}
                        <tr>
                            <td>{{ ticket.id }}</td>
                            <td>{{ ticket.title }}</td>
                            <td>{{ ticket.category }}</td>
                            <td>{{ ticket.priority }}</td>
                            <td><strong>{{ ticket.status }}</strong></td>
                            <td>{{ ticket.author_username }}</td>
                            <td>{{ ticket.created_at }}</td>
                            <td><a href="{{ url_for('tickets.get_ticket_detail', ticket_id=ticket.id) }}">View Details</a></td>
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


def render_ticket_detail_page(ticket, comments, role):
    next_statuses = STATUS_FLOW.get(ticket["status"], [])
    template = """
    <!doctype html>
    <html lang="en">
    <head><meta charset="utf-8"><title>Ticket #{{ ticket.id }}</title></head>
    <body>
        <p><a href="{{ url_for('tickets.list_tickets') }}">← Back to Tickets</a></p>
        <h2>Ticket #{{ ticket.id }}: {{ ticket.title }}</h2>
        <p><strong>Status:</strong> {{ ticket.status }}</p>
        <p><strong>Category:</strong> {{ ticket.category }} | <strong>Priority:</strong> {{ ticket.priority }}</p>
        <p><strong>Created By:</strong> {{ ticket.author_username }} on {{ ticket.created_at }}</p>
        <p><strong>Last Updated:</strong> {{ ticket.updated_at }}</p>
        <hr>
        <h3>Description</h3>
        <p>{{ ticket.description }}</p>

        {% if role == 'support' and ticket.status != 'Closed' %}
            <hr>
            <h3>Update Status</h3>
            <form method="post" action="{{ url_for('tickets.change_ticket_status', ticket_id=ticket.id) }}">
                <label for="status">Next Status:</label>
                <select id="status" name="status" required>
                    {% for st in next_statuses %}
                        <option value="{{ st }}">{{ st }}</option>
                    {% endfor %}
                </select>
                <button type="submit">Update Status</button>
            </form>
        {% elif ticket.status == 'Closed' %}
            <p style="color: gray;"><em>This ticket is Closed and cannot be edited or reopened.</em></p>
        {% endif %}

        <hr>
        <h3>Comments ({{ comments|length }})</h3>
        {% if comments|length == 0 %}
            <p>No comments yet.</p>
        {% else %}
            {% for c in comments %}
                <div style="border: 1px solid #ddd; padding: 8px; margin-bottom: 8px; border-radius: 4px;">
                    <p style="margin: 0 0 4px 0;"><strong>{{ c.author_username }}</strong> (<em>{{ c.author_role }}</em>) &bull; <small>{{ c.created_at }}</small></p>
                    <p style="margin: 0;">{{ c.content }}</p>
                </div>
            {% endfor %}
        {% endif %}

        <hr>
        <h3>Add a Comment</h3>
        <p><small>Comments are allowed on active and closed tickets.</small></p>
        <form method="post" action="{{ url_for('tickets.add_ticket_comment', ticket_id=ticket.id) }}">
            <div>
                <textarea name="content" rows="3" cols="50" placeholder="Type your comment here..." required></textarea>
            </div>
            <br>
            <button type="submit">Submit Comment</button>
        </form>
    </body>
    </html>
    """
    return render_template_string(template, ticket=ticket, comments=comments, role=role, next_statuses=next_statuses)
