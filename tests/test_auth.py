import pytest
from flask import jsonify
from app import app as flask_app
from app.models import init_db, create_user
from app.auth import login_required, role_required, employee_required, support_required


# Define mock endpoints to test decorators
@flask_app.get("/test/login-required")
@login_required
def mock_login_required_endpoint():
    return jsonify({"message": "authenticated"})


@flask_app.get("/test/employee-only")
@employee_required
def mock_employee_only_endpoint():
    return jsonify({"message": "employee area"})


@flask_app.get("/test/support-only")
@support_required
def mock_support_only_endpoint():
    return jsonify({"message": "support area"})


@pytest.fixture
def app_with_db(tmp_path, monkeypatch):
    """Sets up an isolated test database for Flask app."""
    db_file = str(tmp_path / "test_auth.db")
    init_db(db_path=db_file)
    monkeypatch.setenv("DATABASE_URL", db_file)
    flask_app.config["DATABASE_URL"] = db_file
    flask_app.config["TESTING"] = True
    flask_app.config["SECRET_KEY"] = "test-secret"

    # Pre-seed users
    create_user("emp_test", "EmpSecret123!", "employee", db=None)
    create_user("sup_test", "SupSecret123!", "support", db=None)

    return flask_app


@pytest.fixture
def client(app_with_db):
    """Returns a test client with an isolated database."""
    return app_with_db.test_client()


def test_get_login_page(client):
    response = client.get("/login")
    assert response.status_code == 200
    assert b"Login" in response.data


def test_valid_login_employee(client):
    response = client.post(
        "/login",
        json={"username": "emp_test", "password": "EmpSecret123!"},
        headers={"Accept": "application/json"}
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["message"] == "Login successful"
    assert data["user"]["username"] == "emp_test"
    assert data["user"]["role"] == "employee"

    with client.session_transaction() as sess:
        assert sess.get("username") == "emp_test"
        assert sess.get("role") == "employee"
        assert sess.get("user_id") is not None


def test_valid_login_support(client):
    response = client.post(
        "/login",
        json={"username": "sup_test", "password": "SupSecret123!"},
        headers={"Accept": "application/json"}
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["message"] == "Login successful"
    assert data["user"]["username"] == "sup_test"
    assert data["user"]["role"] == "support"

    with client.session_transaction() as sess:
        assert sess.get("username") == "sup_test"
        assert sess.get("role") == "support"
        assert sess.get("user_id") is not None


def test_invalid_login_wrong_password(client):
    response = client.post(
        "/login",
        json={"username": "emp_test", "password": "WrongPassword!"},
        headers={"Accept": "application/json"}
    )
    assert response.status_code == 401
    data = response.get_json()
    assert data["error"] == "Invalid username or password"

    with client.session_transaction() as sess:
        assert "user_id" not in sess


def test_invalid_login_unknown_user(client):
    response = client.post(
        "/login",
        json={"username": "non_existent_user", "password": "Password123!"},
        headers={"Accept": "application/json"}
    )
    assert response.status_code == 401
    data = response.get_json()
    assert data["error"] == "Invalid username or password"

    with client.session_transaction() as sess:
        assert "user_id" not in sess


def test_invalid_login_missing_fields(client):
    # Missing password
    r1 = client.post(
        "/login",
        json={"username": "emp_test"},
        headers={"Accept": "application/json"}
    )
    assert r1.status_code == 400

    # Missing username
    r2 = client.post(
        "/login",
        json={"password": "Password123!"},
        headers={"Accept": "application/json"}
    )
    assert r2.status_code == 400


def test_logout(client):
    # Log in first
    client.post(
        "/login",
        json={"username": "emp_test", "password": "EmpSecret123!"},
        headers={"Accept": "application/json"}
    )
    with client.session_transaction() as sess:
        assert sess.get("user_id") is not None

    # Log out
    response = client.post("/logout", headers={"Accept": "application/json"})
    assert response.status_code == 200
    assert response.get_json() == {"message": "Logout successful"}

    with client.session_transaction() as sess:
        assert "user_id" not in sess


def test_role_enforcement_unauthenticated(client):
    # Unauthenticated access to protected routes
    r1 = client.get("/test/login-required", headers={"Accept": "application/json"})
    assert r1.status_code == 401

    r2 = client.get("/test/employee-only", headers={"Accept": "application/json"})
    assert r2.status_code == 401

    r3 = client.get("/test/support-only", headers={"Accept": "application/json"})
    assert r3.status_code == 401


def test_role_enforcement_employee(client):
    # Log in as employee
    client.post(
        "/login",
        json={"username": "emp_test", "password": "EmpSecret123!"},
        headers={"Accept": "application/json"}
    )

    # Allowed in general protected
    r1 = client.get("/test/login-required", headers={"Accept": "application/json"})
    assert r1.status_code == 200

    # Allowed in employee area
    r2 = client.get("/test/employee-only", headers={"Accept": "application/json"})
    assert r2.status_code == 200
    assert r2.get_json() == {"message": "employee area"}

    # Forbidden in support area
    r3 = client.get("/test/support-only", headers={"Accept": "application/json"})
    assert r3.status_code == 403
    assert r3.get_json() == {"error": "Forbidden: insufficient permissions"}


def test_role_enforcement_support(client):
    # Log in as support staff
    client.post(
        "/login",
        json={"username": "sup_test", "password": "SupSecret123!"},
        headers={"Accept": "application/json"}
    )

    # Allowed in general protected
    r1 = client.get("/test/login-required", headers={"Accept": "application/json"})
    assert r1.status_code == 200

    # Forbidden in employee area
    r2 = client.get("/test/employee-only", headers={"Accept": "application/json"})
    assert r2.status_code == 403
    assert r2.get_json() == {"error": "Forbidden: insufficient permissions"}

    # Allowed in support area
    r3 = client.get("/test/support-only", headers={"Accept": "application/json"})
    assert r3.status_code == 200
    assert r3.get_json() == {"message": "support area"}
