import pytest
from app import app as flask_app
from app.models import init_db, create_user, create_ticket, get_ticket_by_id


@pytest.fixture
def app_with_db(tmp_path, monkeypatch):
    """Sets up an isolated database for status transition testing."""
    db_file = str(tmp_path / "test_status.db")
    init_db(db_path=db_file)
    monkeypatch.setenv("DATABASE_URL", db_file)
    flask_app.config["DATABASE_URL"] = db_file
    flask_app.config["TESTING"] = True
    flask_app.config["SECRET_KEY"] = "test-secret"

    # Seed users
    emp_id = create_user("employee1", "EmpPass123!", "employee")
    sup_id = create_user("support1", "SupPass123!", "support")

    # Seed sample open ticket
    ticket_id = create_ticket(
        title="Sample Network Issue",
        description="Cannot connect to office Wi-Fi network.",
        category="Network",
        priority="High",
        created_by=emp_id,
    )

    return {
        "app": flask_app,
        "emp_id": emp_id,
        "sup_id": sup_id,
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
# Support Staff Status Updates
# ---------------------------------------------------------------------------

def test_support_staff_can_advance_status(client, app_with_db):
    ticket_id = app_with_db["ticket_id"]
    login(client, "support1", "SupPass123!")

    # 1. Open -> In Progress
    r1 = client.post(
        f"/tickets/{ticket_id}/status",
        json={"status": "In Progress"},
        headers={"Accept": "application/json"}
    )
    assert r1.status_code == 200
    assert r1.get_json()["status"] == "In Progress"
    assert get_ticket_by_id(ticket_id)["status"] == "In Progress"

    # 2. In Progress -> Resolved
    r2 = client.post(
        f"/tickets/{ticket_id}/status",
        json={"status": "Resolved"},
        headers={"Accept": "application/json"}
    )
    assert r2.status_code == 200
    assert r2.get_json()["status"] == "Resolved"
    assert get_ticket_by_id(ticket_id)["status"] == "Resolved"

    # 3. Resolved -> Closed
    r3 = client.post(
        f"/tickets/{ticket_id}/status",
        json={"status": "Closed"},
        headers={"Accept": "application/json"}
    )
    assert r3.status_code == 200
    assert r3.get_json()["status"] == "Closed"
    assert get_ticket_by_id(ticket_id)["status"] == "Closed"


def test_support_status_invalid_transition(client, app_with_db):
    ticket_id = app_with_db["ticket_id"]
    login(client, "support1", "SupPass123!")

    # Cannot jump from Open directly to Closed
    response = client.post(
        f"/tickets/{ticket_id}/status",
        json={"status": "Closed"},
        headers={"Accept": "application/json"}
    )
    assert response.status_code == 400
    assert "Invalid status transition" in response.get_json()["error"]
    assert get_ticket_by_id(ticket_id)["status"] == "Open"


# ---------------------------------------------------------------------------
# Employee Status Change Prohibition (Server-Enforced 403)
# ---------------------------------------------------------------------------

def test_employee_cannot_update_status(client, app_with_db):
    ticket_id = app_with_db["ticket_id"]
    login(client, "employee1", "EmpPass123!")

    response = client.post(
        f"/tickets/{ticket_id}/status",
        json={"status": "In Progress"},
        headers={"Accept": "application/json"}
    )
    assert response.status_code == 403
    assert "Only support staff can change a ticket's status" in response.get_json()["error"]
    assert get_ticket_by_id(ticket_id)["status"] == "Open"


def test_unauthenticated_cannot_update_status(client, app_with_db):
    ticket_id = app_with_db["ticket_id"]
    response = client.post(
        f"/tickets/{ticket_id}/status",
        json={"status": "In Progress"},
        headers={"Accept": "application/json"}
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Closed Ticket Modification & Reopening Restrictions
# ---------------------------------------------------------------------------

def test_closed_ticket_cannot_be_reopened(client, app_with_db):
    ticket_id = app_with_db["ticket_id"]
    login(client, "support1", "SupPass123!")

    # Advance to Closed
    client.post(f"/tickets/{ticket_id}/status", json={"status": "In Progress"}, headers={"Accept": "application/json"})
    client.post(f"/tickets/{ticket_id}/status", json={"status": "Resolved"}, headers={"Accept": "application/json"})
    client.post(f"/tickets/{ticket_id}/status", json={"status": "Closed"}, headers={"Accept": "application/json"})
    assert get_ticket_by_id(ticket_id)["status"] == "Closed"

    # Attempt to reopen to Open
    r_open = client.post(
        f"/tickets/{ticket_id}/status",
        json={"status": "Open"},
        headers={"Accept": "application/json"}
    )
    assert r_open.status_code == 400
    assert "Closed ticket cannot be edited or reopened" in r_open.get_json()["error"]
    assert get_ticket_by_id(ticket_id)["status"] == "Closed"

    # Attempt to set to In Progress
    r_prog = client.post(
        f"/tickets/{ticket_id}/status",
        json={"status": "In Progress"},
        headers={"Accept": "application/json"}
    )
    assert r_prog.status_code == 400
    assert "Closed ticket cannot be edited or reopened" in r_prog.get_json()["error"]


def test_closed_ticket_cannot_be_edited(client, app_with_db):
    ticket_id = app_with_db["ticket_id"]

    # Close ticket as support staff
    login(client, "support1", "SupPass123!")
    client.post(f"/tickets/{ticket_id}/status", json={"status": "In Progress"}, headers={"Accept": "application/json"})
    client.post(f"/tickets/{ticket_id}/status", json={"status": "Resolved"}, headers={"Accept": "application/json"})
    client.post(f"/tickets/{ticket_id}/status", json={"status": "Closed"}, headers={"Accept": "application/json"})

    # Log in as the owner employee and attempt to edit
    client.post("/logout")
    login(client, "employee1", "EmpPass123!")

    response = client.post(
        f"/tickets/{ticket_id}/edit",
        json={
            "title": "Modified Title After Close",
            "description": "Trying to modify description",
            "category": "Software",
            "priority": "Low"
        },
        headers={"Accept": "application/json"}
    )
    assert response.status_code == 400
    assert "A Closed ticket cannot be edited" in response.get_json()["error"]

    # Ensure ticket data remained unchanged
    ticket = get_ticket_by_id(ticket_id)
    assert ticket["title"] == "Sample Network Issue"
    assert ticket["status"] == "Closed"


def test_ticket_status_not_found(client):
    login(client, "support1", "SupPass123!")
    response = client.post(
        "/tickets/99999/status",
        json={"status": "In Progress"},
        headers={"Accept": "application/json"}
    )
    assert response.status_code == 404
