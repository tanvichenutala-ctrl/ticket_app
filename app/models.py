import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional
from werkzeug.security import generate_password_hash

CATEGORIES = ("Hardware", "Software", "Network", "Access", "Other")
PRIORITIES = ("Low", "Medium", "High")
STATUSES = ("Open", "In Progress", "Resolved", "Closed")
STATUS_FLOW = {
    "Open": ["In Progress"],
    "In Progress": ["Resolved"],
    "Resolved": ["Closed"],
    "Closed": []
}
ROLES = ("employee", "support")

DEFAULT_DB_PATH = os.getenv("DATABASE_URL", "tickets.db")


def get_db(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Establish and return a connection to the SQLite database."""
    target_path = db_path or os.getenv("DATABASE_URL") or DEFAULT_DB_PATH
    conn = sqlite3.connect(target_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path: Optional[str] = None, schema_path: Optional[str] = None) -> None:
    """Initialize the database schema from schema.sql."""
    if schema_path is None:
        schema_path = str(Path(__file__).resolve().parent.parent / "schema.sql")

    with open(schema_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    conn = get_db(db_path)
    try:
        conn.executescript(schema_sql)
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# User Helpers
# ---------------------------------------------------------------------------

def create_user(username: str, password: str, role: str, db: Optional[sqlite3.Connection] = None) -> int:
    """Create a new user with a hashed password."""
    if not username or not username.strip():
        raise ValueError("Username cannot be empty")
    username = username.strip()

    if not password:
        raise ValueError("Password cannot be empty")

    if role not in ROLES:
        raise ValueError(f"Invalid role '{role}'. Allowed roles: {', '.join(ROLES)}")

    password_hash = generate_password_hash(password)
    should_close = False
    if db is None:
        db = get_db()
        should_close = True

    try:
        cursor = db.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            (username, password_hash, role)
        )
        db.commit()
        return cursor.lastrowid
    finally:
        if should_close:
            db.close()


def get_user_by_id(user_id: int, db: Optional[sqlite3.Connection] = None) -> Optional[sqlite3.Row]:
    """Retrieve a user by their unique ID."""
    should_close = False
    if db is None:
        db = get_db()
        should_close = True

    try:
        cursor = db.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        return cursor.fetchone()
    finally:
        if should_close:
            db.close()


def get_user_by_username(username: str, db: Optional[sqlite3.Connection] = None) -> Optional[sqlite3.Row]:
    """Retrieve a user by their username."""
    if not username:
        return None

    should_close = False
    if db is None:
        db = get_db()
        should_close = True

    try:
        cursor = db.execute("SELECT * FROM users WHERE username = ?", (username.strip(),))
        return cursor.fetchone()
    finally:
        if should_close:
            db.close()


# ---------------------------------------------------------------------------
# Ticket Helpers
# ---------------------------------------------------------------------------

def create_ticket(
    title: str,
    description: str,
    category: str,
    priority: str = "Medium",
    created_by: Optional[int] = None,
    status: str = "Open",
    db: Optional[sqlite3.Connection] = None
) -> int:
    """Create a new ticket and validate inputs on the server."""
    if not title or not title.strip():
        raise ValueError("Title cannot be empty")
    title = title.strip()
    if len(title) > 100:
        raise ValueError("Title must be at most 100 characters")

    if not description or not description.strip():
        raise ValueError("Description cannot be empty")
    description = description.strip()

    if category not in CATEGORIES:
        raise ValueError(f"Invalid category '{category}'. Allowed: {', '.join(CATEGORIES)}")

    if priority not in PRIORITIES:
        raise ValueError(f"Invalid priority '{priority}'. Allowed: {', '.join(PRIORITIES)}")

    if status not in STATUSES:
        raise ValueError(f"Invalid status '{status}'. Allowed: {', '.join(STATUSES)}")

    if created_by is None:
        raise ValueError("created_by is required")

    should_close = False
    if db is None:
        db = get_db()
        should_close = True

    try:
        cursor = db.execute(
            """
            INSERT INTO tickets (title, description, category, priority, status, created_by, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (title, description, category, priority, status, created_by)
        )
        db.commit()
        return cursor.lastrowid
    finally:
        if should_close:
            db.close()


def get_ticket_by_id(ticket_id: int, db: Optional[sqlite3.Connection] = None) -> Optional[sqlite3.Row]:
    """Retrieve a single ticket by its ID, including creator username."""
    should_close = False
    if db is None:
        db = get_db()
        should_close = True

    try:
        cursor = db.execute(
            """
            SELECT t.*, u.username AS author_username
            FROM tickets t
            JOIN users u ON t.created_by = u.id
            WHERE t.id = ?
            """,
            (ticket_id,)
        )
        return cursor.fetchone()
    finally:
        if should_close:
            db.close()


def get_tickets(
    user_id: Optional[int] = None,
    role: Optional[str] = None,
    db: Optional[sqlite3.Connection] = None
) -> List[sqlite3.Row]:
    """
    Retrieve tickets according to user role:
    - Support staff sees all tickets.
    - Employees see only their own tickets.
    """
    should_close = False
    if db is None:
        db = get_db()
        should_close = True

    try:
        if role == "support":
            cursor = db.execute(
                """
                SELECT t.*, u.username AS author_username
                FROM tickets t
                JOIN users u ON t.created_by = u.id
                ORDER BY t.created_at DESC
                """
            )
        else:
            if user_id is None:
                return []
            cursor = db.execute(
                """
                SELECT t.*, u.username AS author_username
                FROM tickets t
                JOIN users u ON t.created_by = u.id
                WHERE t.created_by = ?
                ORDER BY t.created_at DESC
                """,
                (user_id,)
            )
        return cursor.fetchall()
    finally:
        if should_close:
            db.close()


def update_ticket(
    ticket_id: int,
    title: Optional[str] = None,
    description: Optional[str] = None,
    category: Optional[str] = None,
    priority: Optional[str] = None,
    db: Optional[sqlite3.Connection] = None
) -> None:
    """
    Update ticket details.
    A Closed ticket cannot be edited (raises ValueError).
    """
    should_close = False
    if db is None:
        db = get_db()
        should_close = True

    try:
        current = get_ticket_by_id(ticket_id, db=db)
        if current is None:
            raise ValueError(f"Ticket with ID {ticket_id} not found")

        if current["status"] == "Closed":
            raise ValueError("A Closed ticket cannot be edited")

        new_title = current["title"] if title is None else title.strip()
        new_desc = current["description"] if description is None else description.strip()
        new_cat = current["category"] if category is None else category
        new_prio = current["priority"] if priority is None else priority

        if not new_title:
            raise ValueError("Title cannot be empty")
        if len(new_title) > 100:
            raise ValueError("Title must be at most 100 characters")

        if not new_desc:
            raise ValueError("Description cannot be empty")

        if new_cat not in CATEGORIES:
            raise ValueError(f"Invalid category '{new_cat}'. Allowed: {', '.join(CATEGORIES)}")

        if new_prio not in PRIORITIES:
            raise ValueError(f"Invalid priority '{new_prio}'. Allowed: {', '.join(PRIORITIES)}")

        db.execute(
            """
            UPDATE tickets
            SET title = ?, description = ?, category = ?, priority = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (new_title, new_desc, new_cat, new_prio, ticket_id)
        )
        db.commit()
    finally:
        if should_close:
            db.close()


def update_ticket_status(
    ticket_id: int,
    new_status: str,
    user_role: str,
    db: Optional[sqlite3.Connection] = None
) -> None:
    """
    Update the status of a ticket.
    Only support staff can change status.
    Transitions follow Open -> In Progress -> Resolved -> Closed.
    """
    if user_role != "support":
        raise PermissionError("Only support staff can change a ticket's status")

    if new_status not in STATUSES:
        raise ValueError(f"Invalid status '{new_status}'. Allowed: {', '.join(STATUSES)}")

    should_close = False
    if db is None:
        db = get_db()
        should_close = True

    try:
        current = get_ticket_by_id(ticket_id, db=db)
        if current is None:
            raise ValueError(f"Ticket with ID {ticket_id} not found")

        current_status = current["status"]
        if current_status == "Closed":
            raise ValueError("A Closed ticket cannot be edited or reopened")

        if new_status != current_status:
            allowed = STATUS_FLOW.get(current_status, [])
            if new_status not in allowed:
                raise ValueError(
                    f"Invalid status transition from '{current_status}' to '{new_status}'. "
                    f"Allowed transition(s): {', '.join(allowed) or 'None'}"
                )

        db.execute(
            """
            UPDATE tickets
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (new_status, ticket_id)
        )
        db.commit()
    finally:
        if should_close:
            db.close()


# ---------------------------------------------------------------------------
# Comment Helpers
# ---------------------------------------------------------------------------

def add_comment(
    ticket_id: int,
    author_id: int,
    content: str,
    db: Optional[sqlite3.Connection] = None
) -> int:
    """
    Add a comment to a ticket.
    Comments can be added to any ticket, including Closed tickets.
    """
    if not content or not content.strip():
        raise ValueError("Comment content cannot be empty")
    content = content.strip()

    should_close = False
    if db is None:
        db = get_db()
        should_close = True

    try:
        ticket = get_ticket_by_id(ticket_id, db=db)
        if ticket is None:
            raise ValueError(f"Ticket with ID {ticket_id} not found")

        author = get_user_by_id(author_id, db=db)
        if author is None:
            raise ValueError(f"User with ID {author_id} not found")

        cursor = db.execute(
            """
            INSERT INTO comments (ticket_id, author_id, content, created_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (ticket_id, author_id, content)
        )
        db.commit()
        return cursor.lastrowid
    finally:
        if should_close:
            db.close()


def get_comments_by_ticket(
    ticket_id: int,
    db: Optional[sqlite3.Connection] = None
) -> List[sqlite3.Row]:
    """Retrieve all comments for a ticket in chronological order."""
    should_close = False
    if db is None:
        db = get_db()
        should_close = True

    try:
        cursor = db.execute(
            """
            SELECT c.*, u.username AS author_username, u.role AS author_role
            FROM comments c
            JOIN users u ON c.author_id = u.id
            WHERE c.ticket_id = ?
            ORDER BY c.created_at ASC
            """,
            (ticket_id,)
        )
        return cursor.fetchall()
    finally:
        if should_close:
            db.close()
