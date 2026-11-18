import pytest
from werkzeug.security import check_password_hash
from seed import seed_database, SAMPLE_TICKETS
from app.models import get_db, get_user_by_username, get_tickets


def test_seed_database_success(tmp_path, monkeypatch):
    test_db = str(tmp_path / "test_seed.db")
    monkeypatch.setenv("EMPLOYEE_PASSWORD", "EmpSecurePass123!")
    monkeypatch.setenv("SUPPORT_PASSWORD", "SupSecurePass456!")

    # Run seed script
    seed_database(db_path=test_db)

    conn = get_db(test_db)
    try:
        # Verify demo users
        emp = get_user_by_username("employee1", db=conn)
        assert emp is not None
        assert emp["role"] == "employee"
        assert emp["password_hash"] != "EmpSecurePass123!"
        assert check_password_hash(emp["password_hash"], "EmpSecurePass123!")

        sup = get_user_by_username("support1", db=conn)
        assert sup is not None
        assert sup["role"] == "support"
        assert sup["password_hash"] != "SupSecurePass456!"
        assert check_password_hash(sup["password_hash"], "SupSecurePass456!")

        # Verify 5 sample tickets
        tickets = get_tickets(role="support", db=conn)
        assert len(tickets) == 5

        # Order of tickets by created_at DESC or verify by title
        ticket_map = {t["title"]: t for t in tickets}
        for sample in SAMPLE_TICKETS:
            title = sample["title"]
            assert title in ticket_map
            assert ticket_map[title]["category"] == sample["category"]
            assert ticket_map[title]["priority"] == sample["priority"]
            assert ticket_map[title]["status"] == sample["status"]
            assert ticket_map[title]["created_by"] == emp["id"]
    finally:
        conn.close()


def test_seed_missing_password_env_var(tmp_path, monkeypatch):
    test_db = str(tmp_path / "test_seed_fail.db")
    monkeypatch.delenv("EMPLOYEE_PASSWORD", raising=False)
    monkeypatch.delenv("SUPPORT_PASSWORD", raising=False)
    monkeypatch.delenv("DEMO_EMPLOYEE_PASSWORD", raising=False)
    monkeypatch.delenv("DEMO_STAFF_PASSWORD", raising=False)
    monkeypatch.delenv("DEMO_SUPPORT_PASSWORD", raising=False)

    with pytest.raises(ValueError, match="Missing required environment variable"):
        seed_database(db_path=test_db)


def test_seed_idempotency(tmp_path, monkeypatch):
    test_db = str(tmp_path / "test_seed_idempotent.db")
    monkeypatch.setenv("EMPLOYEE_PASSWORD", "EmpSecurePass123!")
    monkeypatch.setenv("SUPPORT_PASSWORD", "SupSecurePass456!")

    # Run twice
    seed_database(db_path=test_db)
    seed_database(db_path=test_db)

    conn = get_db(test_db)
    try:
        tickets = get_tickets(role="support", db=conn)
        assert len(tickets) == 5
    finally:
        conn.close()
