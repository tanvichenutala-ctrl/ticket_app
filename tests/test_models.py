import sqlite3
import pytest
from werkzeug.security import check_password_hash
from app.models import (
    CATEGORIES,
    PRIORITIES,
    STATUSES,
    ROLES,
    get_db,
    init_db,
    create_user,
    get_user_by_id,
    get_user_by_username,
    create_ticket,
    get_ticket_by_id,
    get_tickets,
    update_ticket,
    update_ticket_status,
    add_comment,
    get_comments_by_ticket,
)


@pytest.fixture
def db_path(tmp_path):
    """Provides a fresh isolated database file for each test."""
    db_file = tmp_path / "test_tickets.db"
    init_db(db_path=str(db_file))
    return str(db_file)


@pytest.fixture
def conn(db_path):
    """Provides an active database connection for the test database."""
    connection = get_db(db_path)
    yield connection
    connection.close()


def test_init_db_creates_tables_and_indexes(conn):
    cursor = conn.execute(
        "SELECT name, type FROM sqlite_master WHERE type IN ('table', 'index')"
    )
    names = {row["name"] for row in cursor.fetchall()}
    assert "users" in names
    assert "tickets" in names
    assert "comments" in names
    assert "idx_tickets_created_by" in names
    assert "idx_tickets_status" in names
    assert "idx_comments_ticket_id" in names


def test_create_user_hashes_password(conn):
    user_id = create_user("alice", "secret123", "employee", db=conn)
    assert user_id is not None

    user = get_user_by_id(user_id, db=conn)
    assert user["username"] == "alice"
    assert user["role"] == "employee"
    assert user["password_hash"] != "secret123"
    assert check_password_hash(user["password_hash"], "secret123")

    by_username = get_user_by_username("alice", db=conn)
    assert by_username["id"] == user_id


def test_create_user_validation(conn):
    with pytest.raises(ValueError, match="Username cannot be empty"):
        create_user("", "pass", "employee", db=conn)

    with pytest.raises(ValueError, match="Password cannot be empty"):
        create_user("alice", "", "employee", db=conn)

    with pytest.raises(ValueError, match="Invalid role"):
        create_user("alice", "pass", "admin", db=conn)


def test_create_ticket_success(conn):
    user_id = create_user("employee_test", "pass", "employee", db=conn)
    ticket_id = create_ticket(
        title="Laptop broken",
        description="Screen does not turn on",
        category="Hardware",
        priority="High",
        created_by=user_id,
        db=conn,
    )
    assert ticket_id is not None

    ticket = get_ticket_by_id(ticket_id, db=conn)
    assert ticket["title"] == "Laptop broken"
    assert ticket["description"] == "Screen does not turn on"
    assert ticket["category"] == "Hardware"
    assert ticket["priority"] == "High"
    assert ticket["status"] == "Open"
    assert ticket["created_by"] == user_id
    assert ticket["author_username"] == "employee_test"
    assert ticket["created_at"] is not None
    assert ticket["updated_at"] is not None


def test_create_ticket_validation_failures(conn):
    user_id = create_user("bob", "pass", "employee", db=conn)

    # Empty title
    with pytest.raises(ValueError, match="Title cannot be empty"):
        create_ticket("   ", "Desc", "Hardware", created_by=user_id, db=conn)

    # Title exceeds 100 characters
    long_title = "a" * 101
    with pytest.raises(ValueError, match="Title must be at most 100 characters"):
        create_ticket(long_title, "Desc", "Hardware", created_by=user_id, db=conn)

    # Empty description
    with pytest.raises(ValueError, match="Description cannot be empty"):
        create_ticket("Title", "   ", "Hardware", created_by=user_id, db=conn)

    # Invalid category
    with pytest.raises(ValueError, match="Invalid category"):
        create_ticket("Title", "Desc", "NotACategory", created_by=user_id, db=conn)

    # Invalid priority
    with pytest.raises(ValueError, match="Invalid priority"):
        create_ticket("Title", "Desc", "Hardware", priority="Critical", created_by=user_id, db=conn)

    # Missing created_by
    with pytest.raises(ValueError, match="created_by is required"):
        create_ticket("Title", "Desc", "Hardware", created_by=None, db=conn)


def test_get_tickets_role_isolation(conn):
    user1_id = create_user("user1", "pass", "employee", db=conn)
    user2_id = create_user("user2", "pass", "employee", db=conn)

    t1 = create_ticket("User 1 ticket", "Desc 1", "Hardware", created_by=user1_id, db=conn)
    t2 = create_ticket("User 2 ticket", "Desc 2", "Software", created_by=user2_id, db=conn)

    user1_tickets = get_tickets(user_id=user1_id, role="employee", db=conn)
    user1_ticket_ids = [t["id"] for t in user1_tickets]
    assert t1 in user1_ticket_ids
    assert t2 not in user1_ticket_ids

    user2_tickets = get_tickets(user_id=user2_id, role="employee", db=conn)
    user2_ticket_ids = [t["id"] for t in user2_tickets]
    assert t2 in user2_ticket_ids
    assert t1 not in user2_ticket_ids

    support_tickets = get_tickets(role="support", db=conn)
    support_ticket_ids = [t["id"] for t in support_tickets]
    assert t1 in support_ticket_ids
    assert t2 in support_ticket_ids


def test_update_ticket_and_closed_rule(conn):
    user_id = create_user("charlie", "pass", "employee", db=conn)
    ticket_id = create_ticket("Old title", "Old desc", "Hardware", created_by=user_id, db=conn)

    update_ticket(
        ticket_id=ticket_id,
        title="New title",
        description="New desc",
        category="Software",
        priority="High",
        db=conn,
    )

    updated = get_ticket_by_id(ticket_id, db=conn)
    assert updated["title"] == "New title"
    assert updated["description"] == "New desc"
    assert updated["category"] == "Software"
    assert updated["priority"] == "High"

    # Now close the ticket
    update_ticket_status(ticket_id, "In Progress", user_role="support", db=conn)
    update_ticket_status(ticket_id, "Resolved", user_role="support", db=conn)
    update_ticket_status(ticket_id, "Closed", user_role="support", db=conn)

    # Editing a closed ticket must be rejected
    with pytest.raises(ValueError, match="A Closed ticket cannot be edited"):
        update_ticket(ticket_id=ticket_id, title="Try edit", db=conn)


def test_update_ticket_status_by_support_staff(conn):
    user_id = create_user("david", "pass", "employee", db=conn)
    ticket_id = create_ticket("Issue", "Desc", "Network", created_by=user_id, db=conn)

    # Employee cannot change status
    with pytest.raises(PermissionError, match="Only support staff can change a ticket's status"):
        update_ticket_status(ticket_id, "In Progress", user_role="employee", db=conn)

    # Valid support status flow: Open -> In Progress -> Resolved -> Closed
    update_ticket_status(ticket_id, "In Progress", user_role="support", db=conn)
    assert get_ticket_by_id(ticket_id, db=conn)["status"] == "In Progress"

    update_ticket_status(ticket_id, "Resolved", user_role="support", db=conn)
    assert get_ticket_by_id(ticket_id, db=conn)["status"] == "Resolved"

    update_ticket_status(ticket_id, "Closed", user_role="support", db=conn)
    assert get_ticket_by_id(ticket_id, db=conn)["status"] == "Closed"

    # From Closed, no further transitions allowed
    with pytest.raises(ValueError, match="Invalid status transition"):
        update_ticket_status(ticket_id, "Open", user_role="support", db=conn)


def test_comments_on_open_and_closed_tickets(conn):
    emp_id = create_user("emma", "pass", "employee", db=conn)
    sup_id = create_user("sam", "pass", "support", db=conn)
    ticket_id = create_ticket("Problem", "Details", "Access", created_by=emp_id, db=conn)

    # Empty comment rejected
    with pytest.raises(ValueError, match="Comment content cannot be empty"):
        add_comment(ticket_id, emp_id, "   ", db=conn)

    # Comment on Open ticket
    c1 = add_comment(ticket_id, emp_id, "Please hurry", db=conn)
    assert c1 is not None

    # Advance ticket to Closed
    update_ticket_status(ticket_id, "In Progress", user_role="support", db=conn)
    update_ticket_status(ticket_id, "Resolved", user_role="support", db=conn)
    update_ticket_status(ticket_id, "Closed", user_role="support", db=conn)

    # Comment on Closed ticket (must succeed per spec/rules)
    c2 = add_comment(ticket_id, sup_id, "Issue verified and resolved.", db=conn)
    assert c2 is not None

    comments = get_comments_by_ticket(ticket_id, db=conn)
    assert len(comments) == 2
    assert comments[0]["content"] == "Please hurry"
    assert comments[0]["author_username"] == "emma"
    assert comments[1]["content"] == "Issue verified and resolved."
    assert comments[1]["author_username"] == "sam"


def test_foreign_key_enforcement(conn):
    # Non-existent user cannot create ticket
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO tickets (title, description, category, priority, status, created_by) VALUES (?, ?, ?, ?, ?, ?)",
            ("Test", "Desc", "Hardware", "Low", "Open", 999999)
        )

    # Deleting ticket cascades to comments
    emp_id = create_user("frank", "pass", "employee", db=conn)
    ticket_id = create_ticket("Cascade test", "Desc", "Hardware", created_by=emp_id, db=conn)
    add_comment(ticket_id, emp_id, "Comment to be deleted", db=conn)

    conn.execute("DELETE FROM tickets WHERE id = ?", (ticket_id,))
    conn.commit()

    cursor = conn.execute("SELECT * FROM comments WHERE ticket_id = ?", (ticket_id,))
    assert cursor.fetchall() == []
