import pytest
from app import app as flask_app
from app.models import init_db, create_user, create_ticket, update_ticket_status, get_comments_by_ticket


@pytest.fixture
def app_with_db(tmp_path, monkeypatch):
    """Sets up an isolated database for commenting tests."""
    db_file = str(tmp_path / "test_comments.db")
    init_db(db_path=db_file)
    monkeypatch.setenv("DATABASE_URL", db_file)
    flask_app.config["DATABASE_URL"] = db_file
    flask_app.config["TESTING"] = True
    flask_app.config["SECRET_KEY"] = "test-secret"

    # Pre-seed users
    emp1_id = create_user("employee1", "EmpPass123!", "employee")
    emp2_id = create_user("employee2", "EmpPass123!", "employee")
    sup1_id = create_user("support1", "SupPass123!", "support")

    # Pre-seed ticket for employee1
    ticket_id = create_ticket(
        title="VPN Connection Failure",
        description="Cannot authenticate with VPN gateway.",
        category="Network",
        priority="High",
        created_by=emp1_id,
    )

    return {
        "app": flask_app,
        "emp1_id": emp1_id,
        "emp2_id": emp2_id,
        "sup1_id": sup1_id,
        "ticket_id": ticket_id,
    }


@pytest.fixture
def client(app_with_db):
    return app_with_db["app"].test_client()


def login(client, username, password):
    return client.post(
        "/login",
        json={"username": username, "password": password},
        headers={"Accept": "application/json"}
    )


# ---------------------------------------------------------------------------
# Comment Tests
# ---------------------------------------------------------------------------

def test_employee_can_comment_on_own_ticket(client, app_with_db):
    ticket_id = app_with_db["ticket_id"]
    login(client, "employee1", "EmpPass123!")

    response = client.post(
        f"/tickets/{ticket_id}/comments",
        json={"content": "Here is additional info: error code 403."},
        headers={"Accept": "application/json"}
    )
    assert response.status_code == 201
    data = response.get_json()
    assert data["message"] == "Comment added successfully"
    assert "comment_id" in data

    # Verify comments via GET
    get_res = client.get(f"/tickets/{ticket_id}", headers={"Accept": "application/json"})
    assert get_res.status_code == 200
    comments = get_res.get_json()["comments"]
    assert len(comments) == 1
    assert comments[0]["content"] == "Here is additional info: error code 403."
    assert comments[0]["author_username"] == "employee1"
    assert comments[0]["author_role"] == "employee"


def test_support_staff_can_comment_on_any_ticket(client, app_with_db):
    ticket_id = app_with_db["ticket_id"]
    login(client, "support1", "SupPass123!")

    response = client.post(
        f"/tickets/{ticket_id}/comments",
        json={"content": "Support team has received this. Please restart your client."},
        headers={"Accept": "application/json"}
    )
    assert response.status_code == 201

    get_res = client.get(f"/tickets/{ticket_id}", headers={"Accept": "application/json"})
    assert get_res.status_code == 200
    comments = get_res.get_json()["comments"]
    assert len(comments) == 1
    assert comments[0]["author_username"] == "support1"
    assert comments[0]["author_role"] == "support"


def test_employee_cannot_comment_on_other_employee_ticket(client, app_with_db):
    ticket_id = app_with_db["ticket_id"]  # Created by employee1
    login(client, "employee2", "EmpPass123!")

    response = client.post(
        f"/tickets/{ticket_id}/comments",
        json={"content": "Employee 2 trying to comment on employee 1 ticket."},
        headers={"Accept": "application/json"}
    )
    assert response.status_code == 403
    assert "Forbidden: you can only comment on your own tickets" in response.get_json()["error"]

    # Verify no comment was saved
    comments = get_comments_by_ticket(ticket_id)
    assert len(comments) == 0


def test_comments_allowed_on_closed_ticket(client, app_with_db):
    ticket_id = app_with_db["ticket_id"]

    # Close the ticket as support staff
    update_ticket_status(ticket_id, "In Progress", user_role="support")
    update_ticket_status(ticket_id, "Resolved", user_role="support")
    update_ticket_status(ticket_id, "Closed", user_role="support")

    # 1. Employee comments on their Closed ticket
    login(client, "employee1", "EmpPass123!")
    r1 = client.post(
        f"/tickets/{ticket_id}/comments",
        json={"content": "Employee follow-up note after ticket was closed."},
        headers={"Accept": "application/json"}
    )
    assert r1.status_code == 201

    # 2. Support staff comments on the Closed ticket
    client.post("/logout")
    login(client, "support1", "SupPass123!")
    r2 = client.post(
        f"/tickets/{ticket_id}/comments",
        json={"content": "Support staff post-closure confirmation note."},
        headers={"Accept": "application/json"}
    )
    assert r2.status_code == 201

    # Verify both comments exist on closed ticket in chronological order
    detail_res = client.get(f"/tickets/{ticket_id}", headers={"Accept": "application/json"})
    assert detail_res.status_code == 200
    comments = detail_res.get_json()["comments"]
    assert len(comments) == 2
    assert comments[0]["content"] == "Employee follow-up note after ticket was closed."
    assert comments[1]["content"] == "Support staff post-closure confirmation note."


def test_empty_comment_validation(client, app_with_db):
    ticket_id = app_with_db["ticket_id"]
    login(client, "employee1", "EmpPass123!")

    # Empty string
    r1 = client.post(
        f"/tickets/{ticket_id}/comments",
        json={"content": ""},
        headers={"Accept": "application/json"}
    )
    assert r1.status_code == 400
    assert "Comment content cannot be empty" in r1.get_json()["error"]

    # Whitespace only
    r2 = client.post(
        f"/tickets/{ticket_id}/comments",
        json={"content": "     "},
        headers={"Accept": "application/json"}
    )
    assert r2.status_code == 400
    assert "Comment content cannot be empty" in r2.get_json()["error"]


def test_unauthenticated_cannot_comment(client, app_with_db):
    ticket_id = app_with_db["ticket_id"]
    response = client.post(
        f"/tickets/{ticket_id}/comments",
        json={"content": "Anonymous comment"},
        headers={"Accept": "application/json"}
    )
    assert response.status_code == 401


def test_comment_on_non_existent_ticket(client):
    login(client, "support1", "SupPass123!")
    response = client.post(
        "/tickets/999999/comments",
        json={"content": "Comment on ghost ticket"},
        headers={"Accept": "application/json"}
    )
    assert response.status_code == 404
