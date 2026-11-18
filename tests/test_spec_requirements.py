import pytest
from app import app as flask_app
from app.models import (
    init_db,
    create_user,
    create_ticket,
    update_ticket_status,
    get_ticket_by_id,
    get_comments_by_ticket,
)


@pytest.fixture
def app_with_db(tmp_path, monkeypatch):
    """Sets up an isolated database for spec requirement verification."""
    db_file = str(tmp_path / "test_spec_reqs.db")
    init_db(db_path=db_file)
    monkeypatch.setenv("DATABASE_URL", db_file)
    flask_app.config["DATABASE_URL"] = db_file
    flask_app.config["TESTING"] = True
    flask_app.config["SECRET_KEY"] = "test-secret"

    # Seed demo users
    emp1_id = create_user("employee1", "EmpPass123!", "employee")
    emp2_id = create_user("employee2", "EmpPass123!", "employee")
    sup1_id = create_user("support1", "SupPass123!", "support")

    return {
        "app": flask_app,
        "emp1_id": emp1_id,
        "emp2_id": emp2_id,
        "sup1_id": sup1_id,
    }


@pytest.fixture
def client(app_with_db):
    return app_with_db["app"].test_client()


def login(client, username, password):
    """Helper to authenticate a test user via JSON."""
    return client.post(
        "/login",
        json={"username": username, "password": password},
        headers={"Accept": "application/json"}
    )


# ===========================================================================
# 1. Status Change Permission
# ===========================================================================

def test_status_change_permission(client, app_with_db):
    """
    Verify:
    - Support staff can update status.
    - Employees receive 403 Forbidden on status change attempts.
    - Unauthenticated requests receive 401 Unauthorized.
    """
    emp1_id = app_with_db["emp1_id"]
    ticket_id = create_ticket("Network issue", "VPN drops", "Network", created_by=emp1_id)

    # 1. Unauthenticated attempt -> 401
    r_unauth = client.post(
        f"/tickets/{ticket_id}/status",
        json={"status": "In Progress"},
        headers={"Accept": "application/json"}
    )
    assert r_unauth.status_code == 401

    # 2. Employee attempt -> 403 Forbidden
    login(client, "employee1", "EmpPass123!")
    r_emp = client.post(
        f"/tickets/{ticket_id}/status",
        json={"status": "In Progress"},
        headers={"Accept": "application/json"}
    )
    assert r_emp.status_code == 403
    assert "Only support staff can change a ticket's status" in r_emp.get_json()["error"]
    assert get_ticket_by_id(ticket_id)["status"] == "Open"

    # 3. Support staff attempt -> 200 OK
    client.post("/logout")
    login(client, "support1", "SupPass123!")
    r_sup = client.post(
        f"/tickets/{ticket_id}/status",
        json={"status": "In Progress"},
        headers={"Accept": "application/json"}
    )
    assert r_sup.status_code == 200
    assert r_sup.get_json()["status"] == "In Progress"
    assert get_ticket_by_id(ticket_id)["status"] == "In Progress"


# ===========================================================================
# 2. Ticket Visibility (Role-Filtered)
# ===========================================================================

def test_ticket_visibility(client, app_with_db):
    """
    Verify:
    - Employees see only their own tickets.
    - Support staff see all tickets across all employees.
    """
    emp1_id = app_with_db["emp1_id"]
    emp2_id = app_with_db["emp2_id"]

    t1_id = create_ticket("Employee 1 Monitor", "Display broken", "Hardware", created_by=emp1_id)
    t2_id = create_ticket("Employee 2 Keyboard", "Keys stuck", "Hardware", created_by=emp2_id)

    # Employee 1 sees only t1
    login(client, "employee1", "EmpPass123!")
    r1 = client.get("/tickets", headers={"Accept": "application/json"})
    assert r1.status_code == 200
    t1_ids = [t["id"] for t in r1.get_json()["tickets"]]
    assert t1_id in t1_ids
    assert t2_id not in t1_ids

    # Employee 2 sees only t2
    client.post("/logout")
    login(client, "employee2", "EmpPass123!")
    r2 = client.get("/tickets", headers={"Accept": "application/json"})
    assert r2.status_code == 200
    t2_ids = [t["id"] for t in r2.get_json()["tickets"]]
    assert t2_id in t2_ids
    assert t1_id not in t2_ids

    # Support staff sees both t1 and t2
    client.post("/logout")
    login(client, "support1", "SupPass123!")
    r3 = client.get("/tickets", headers={"Accept": "application/json"})
    assert r3.status_code == 200
    all_ids = [t["id"] for t in r3.get_json()["tickets"]]
    assert t1_id in all_ids
    assert t2_id in all_ids


# ===========================================================================
# 3. Closed-Ticket Editing Prohibition
# ===========================================================================

def test_closed_ticket_editing_prohibited(client, app_with_db):
    """
    Verify:
    - A Closed ticket cannot be edited.
    - Attempting to update title/description/category/priority returns 400.
    """
    emp1_id = app_with_db["emp1_id"]
    ticket_id = create_ticket("Initial Title", "Initial Description", "Software", created_by=emp1_id)

    # Close ticket as support staff
    update_ticket_status(ticket_id, "In Progress", user_role="support")
    update_ticket_status(ticket_id, "Resolved", user_role="support")
    update_ticket_status(ticket_id, "Closed", user_role="support")
    assert get_ticket_by_id(ticket_id)["status"] == "Closed"

    # Employee attempts to edit closed ticket
    login(client, "employee1", "EmpPass123!")
    response = client.post(
        f"/tickets/{ticket_id}/edit",
        json={
            "title": "Altered Title",
            "description": "Altered Description",
            "category": "Hardware",
            "priority": "High"
        },
        headers={"Accept": "application/json"}
    )
    assert response.status_code == 400
    assert "A Closed ticket cannot be edited" in response.get_json()["error"]

    # Verify database state remained unchanged
    ticket = get_ticket_by_id(ticket_id)
    assert ticket["title"] == "Initial Title"
    assert ticket["description"] == "Initial Description"
    assert ticket["status"] == "Closed"


# ===========================================================================
# 4. Empty Title and Description Validation
# ===========================================================================

def test_empty_title_and_description_rejected(client):
    """
    Verify:
    - Empty or whitespace-only title is rejected with 400 and clear message.
    - Empty or whitespace-only description is rejected with 400 and clear message.
    """
    login(client, "employee1", "EmpPass123!")

    # 1. Empty title
    r_empty_title = client.post(
        "/tickets/new",
        json={"title": "", "description": "Valid description", "category": "Hardware"},
        headers={"Accept": "application/json"}
    )
    assert r_empty_title.status_code == 400
    assert "Title is required and cannot be empty" in r_empty_title.get_json()["error"]

    # 2. Whitespace title
    r_ws_title = client.post(
        "/tickets/new",
        json={"title": "     ", "description": "Valid description", "category": "Hardware"},
        headers={"Accept": "application/json"}
    )
    assert r_ws_title.status_code == 400
    assert "Title is required and cannot be empty" in r_ws_title.get_json()["error"]

    # 3. Empty description
    r_empty_desc = client.post(
        "/tickets/new",
        json={"title": "Valid Title", "description": "", "category": "Hardware"},
        headers={"Accept": "application/json"}
    )
    assert r_empty_desc.status_code == 400
    assert "Description is required and cannot be empty" in r_empty_desc.get_json()["error"]

    # 4. Whitespace description
    r_ws_desc = client.post(
        "/tickets/new",
        json={"title": "Valid Title", "description": "    \t  \n  ", "category": "Hardware"},
        headers={"Accept": "application/json"}
    )
    assert r_ws_desc.status_code == 400
    assert "Description is required and cannot be empty" in r_ws_desc.get_json()["error"]


# ===========================================================================
# 5. Title Length Over 100 Characters
# ===========================================================================

def test_title_length_over_100_rejected(client):
    """
    Verify:
    - Title exceeding 100 characters is rejected with 400.
    - Title with exactly 100 characters is accepted.
    """
    login(client, "employee1", "EmpPass123!")

    # 1. 101 characters -> Rejected
    title_101 = "T" * 101
    r_101 = client.post(
        "/tickets/new",
        json={"title": title_101, "description": "Valid description", "category": "Hardware"},
        headers={"Accept": "application/json"}
    )
    assert r_101.status_code == 400
    assert "Title must be at most 100 characters" in r_101.get_json()["error"]

    # 2. Exactly 100 characters -> Accepted
    title_100 = "T" * 100
    r_100 = client.post(
        "/tickets/new",
        json={"title": title_100, "description": "Valid description", "category": "Hardware"},
        headers={"Accept": "application/json"}
    )
    assert r_100.status_code == 201
    assert r_100.get_json()["message"] == "Ticket created successfully"


# ===========================================================================
# 6. Comments on Closed Tickets
# ===========================================================================

def test_comments_on_closed_tickets(client, app_with_db):
    """
    Verify:
    - Both owner employee and support staff can post comments on Closed tickets.
    - Comments are appended and displayed in chronological order.
    """
    emp1_id = app_with_db["emp1_id"]
    ticket_id = create_ticket("Printer Offline", "Cannot print invoices", "Hardware", created_by=emp1_id)

    # Advance ticket to Closed
    update_ticket_status(ticket_id, "In Progress", user_role="support")
    update_ticket_status(ticket_id, "Resolved", user_role="support")
    update_ticket_status(ticket_id, "Closed", user_role="support")
    assert get_ticket_by_id(ticket_id)["status"] == "Closed"

    # 1. Employee posts comment on Closed ticket
    login(client, "employee1", "EmpPass123!")
    r_emp_comment = client.post(
        f"/tickets/{ticket_id}/comments",
        json={"content": "Employee comment: Problem re-occurred briefly but is now fine."},
        headers={"Accept": "application/json"}
    )
    assert r_emp_comment.status_code == 201

    # 2. Support staff posts comment on Closed ticket
    client.post("/logout")
    login(client, "support1", "SupPass123!")
    r_sup_comment = client.post(
        f"/tickets/{ticket_id}/comments",
        json={"content": "Support comment: Logged in vendor portal for tracking."},
        headers={"Accept": "application/json"}
    )
    assert r_sup_comment.status_code == 201

    # 3. Verify comments in detail response
    detail_res = client.get(f"/tickets/{ticket_id}", headers={"Accept": "application/json"})
    assert detail_res.status_code == 200
    comments = detail_res.get_json()["comments"]
    assert len(comments) == 2
    assert comments[0]["content"] == "Employee comment: Problem re-occurred briefly but is now fine."
    assert comments[0]["author_username"] == "employee1"
    assert comments[1]["content"] == "Support comment: Logged in vendor portal for tracking."
    assert comments[1]["author_username"] == "support1"
