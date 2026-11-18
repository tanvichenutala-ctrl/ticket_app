import time
import pytest
from app import app as flask_app
from app.models import init_db, create_user, create_ticket, get_ticket_by_id


@pytest.fixture
def app_with_db(tmp_path, monkeypatch):
    """Sets up an isolated database for ticket testing."""
    db_file = str(tmp_path / "test_tickets.db")
    init_db(db_path=db_file)
    monkeypatch.setenv("DATABASE_URL", db_file)
    flask_app.config["DATABASE_URL"] = db_file
    flask_app.config["TESTING"] = True
    flask_app.config["SECRET_KEY"] = "test-secret"

    # Pre-seed demo users
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


def login_client(client, username, password):
    """Helper function to log in a test user."""
    return client.post(
        "/login",
        json={"username": username, "password": password},
        headers={"Accept": "application/json"}
    )


# ---------------------------------------------------------------------------
# Ticket Creation Tests
# ---------------------------------------------------------------------------

def test_create_ticket_success(client, app_with_db):
    login_client(client, "employee1", "EmpPass123!")

    response = client.post(
        "/tickets/new",
        json={
            "title": "Broken Monitor",
            "description": "Screen flickers continuously when turned on.",
            "category": "Hardware",
            "priority": "High"
        },
        headers={"Accept": "application/json"}
    )
    assert response.status_code == 201
    data = response.get_json()
    assert data["message"] == "Ticket created successfully"
    assert "ticket_id" in data

    ticket = get_ticket_by_id(data["ticket_id"])
    assert ticket["title"] == "Broken Monitor"
    assert ticket["description"] == "Screen flickers continuously when turned on."
    assert ticket["category"] == "Hardware"
    assert ticket["priority"] == "High"
    assert ticket["status"] == "Open"
    assert ticket["created_by"] == app_with_db["emp1_id"]


def test_create_ticket_form_submit(client):
    login_client(client, "employee1", "EmpPass123!")

    response = client.post(
        "/tickets/new",
        data={
            "title": "Form Submit Ticket",
            "description": "Submitted via HTML form.",
            "category": "Software",
            "priority": "Medium"
        },
        follow_redirects=True
    )
    assert response.status_code == 200
    assert b"Form Submit Ticket" in response.data


def test_create_ticket_support_staff_prohibited(client):
    login_client(client, "support1", "SupPass123!")

    response = client.post(
        "/tickets/new",
        json={
            "title": "Support Created Ticket",
            "description": "Support trying to submit.",
            "category": "Hardware"
        },
        headers={"Accept": "application/json"}
    )
    assert response.status_code == 403
    assert response.get_json()["error"] == "Forbidden: insufficient permissions"


def test_create_ticket_unauthenticated(client):
    response = client.post(
        "/tickets/new",
        json={
            "title": "Unauthenticated Ticket",
            "description": "Should fail.",
            "category": "Hardware"
        },
        headers={"Accept": "application/json"}
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Validation Failure Tests
# ---------------------------------------------------------------------------

def test_validation_empty_title(client):
    login_client(client, "employee1", "EmpPass123!")

    response = client.post(
        "/tickets/new",
        json={
            "title": "   ",
            "description": "Valid description",
            "category": "Hardware"
        },
        headers={"Accept": "application/json"}
    )
    assert response.status_code == 400
    assert "Title is required and cannot be empty" in response.get_json()["error"]


def test_validation_title_too_long(client):
    login_client(client, "employee1", "EmpPass123!")

    long_title = "A" * 101
    response = client.post(
        "/tickets/new",
        json={
            "title": long_title,
            "description": "Valid description",
            "category": "Hardware"
        },
        headers={"Accept": "application/json"}
    )
    assert response.status_code == 400
    assert "Title must be at most 100 characters" in response.get_json()["error"]


def test_validation_empty_description(client):
    login_client(client, "employee1", "EmpPass123!")

    response = client.post(
        "/tickets/new",
        json={
            "title": "Valid Title",
            "description": "   ",
            "category": "Hardware"
        },
        headers={"Accept": "application/json"}
    )
    assert response.status_code == 400
    assert "Description is required and cannot be empty" in response.get_json()["error"]


def test_validation_invalid_category(client):
    login_client(client, "employee1", "EmpPass123!")

    response = client.post(
        "/tickets/new",
        json={
            "title": "Valid Title",
            "description": "Valid description",
            "category": "InvalidCategory"
        },
        headers={"Accept": "application/json"}
    )
    assert response.status_code == 400
    assert "Invalid category" in response.get_json()["error"]


def test_validation_invalid_priority(client):
    login_client(client, "employee1", "EmpPass123!")

    response = client.post(
        "/tickets/new",
        json={
            "title": "Valid Title",
            "description": "Valid description",
            "category": "Hardware",
            "priority": "Urgent"
        },
        headers={"Accept": "application/json"}
    )
    assert response.status_code == 400
    assert "Invalid priority" in response.get_json()["error"]


# ---------------------------------------------------------------------------
# Role-Filtered Ticket Listing Tests
# ---------------------------------------------------------------------------

def test_list_tickets_unauthenticated(client):
    response = client.get("/tickets", headers={"Accept": "application/json"})
    assert response.status_code == 401


def test_list_tickets_employee_isolation(client, app_with_db):
    emp1_id = app_with_db["emp1_id"]
    emp2_id = app_with_db["emp2_id"]

    t1_id = create_ticket("Emp1 Ticket", "Desc 1", "Hardware", created_by=emp1_id)
    t2_id = create_ticket("Emp2 Ticket", "Desc 2", "Software", created_by=emp2_id)

    # Employee 1 list
    login_client(client, "employee1", "EmpPass123!")
    r1 = client.get("/tickets", headers={"Accept": "application/json"})
    assert r1.status_code == 200
    t1_list = r1.get_json()["tickets"]
    t1_ids = [t["id"] for t in t1_list]
    assert t1_id in t1_ids
    assert t2_id not in t1_ids

    # Employee 2 list
    client.post("/logout")
    login_client(client, "employee2", "EmpPass123!")
    r2 = client.get("/tickets", headers={"Accept": "application/json"})
    assert r2.status_code == 200
    t2_list = r2.get_json()["tickets"]
    t2_ids = [t["id"] for t in t2_list]
    assert t2_id in t2_ids
    assert t1_id not in t2_ids


def test_list_tickets_support_sees_all(client, app_with_db):
    emp1_id = app_with_db["emp1_id"]
    emp2_id = app_with_db["emp2_id"]

    t1_id = create_ticket("Emp1 Hardware Issue", "Desc 1", "Hardware", created_by=emp1_id)
    t2_id = create_ticket("Emp2 Software Issue", "Desc 2", "Software", created_by=emp2_id)

    login_client(client, "support1", "SupPass123!")
    response = client.get("/tickets", headers={"Accept": "application/json"})
    assert response.status_code == 200
    all_tickets = response.get_json()["tickets"]
    all_ids = [t["id"] for t in all_tickets]

    assert t1_id in all_ids
    assert t2_id in all_ids

    # Also verify creator username is included
    ticket_map = {t["id"]: t for t in all_tickets}
    assert ticket_map[t1_id]["author_username"] == "employee1"
    assert ticket_map[t2_id]["author_username"] == "employee2"


def test_ticket_list_loads_under_2_seconds(client, app_with_db):
    login_client(client, "support1", "SupPass123!")

    start_time = time.time()
    response = client.get("/tickets")
    elapsed = time.time() - start_time

    assert response.status_code == 200
    assert elapsed < 2.0, f"Ticket list took {elapsed:.2f}s, expected < 2.0s"
