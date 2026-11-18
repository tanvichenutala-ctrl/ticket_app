import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Try loading from .env first, then fallback to env if present
env_path = Path(__file__).resolve().parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    alt_env = Path(__file__).resolve().parent / "env"
    if alt_env.exists():
        load_dotenv(dotenv_path=alt_env)

from app.models import (
    init_db,
    get_db,
    create_user,
    get_user_by_username,
    create_ticket,
    get_tickets,
)

SAMPLE_TICKETS = [
    {
        "title": "Laptop not charging",
        "description": "Laptop battery drains quickly and fails to charge when plugged into the docking station or wall adapter.",
        "category": "Hardware",
        "priority": "High",
        "status": "Open",
    },
    {
        "title": "Cannot log in to VPN",
        "description": "Receiving an authentication handshake timeout error when attempting to connect to the corporate VPN from home.",
        "category": "Network",
        "priority": "High",
        "status": "In Progress",
    },
    {
        "title": "Need access to the shared project folder",
        "description": "Requesting read and write permissions to the Shared Drive / Project Alpha folder for quarterly planning.",
        "category": "Access",
        "priority": "Medium",
        "status": "Open",
    },
    {
        "title": "Excel keeps crashing on startup",
        "description": "Microsoft Excel immediately crashes upon opening any workbook. Reinstallation has not resolved the issue.",
        "category": "Software",
        "priority": "Medium",
        "status": "Resolved",
    },
    {
        "title": "Request a second monitor",
        "description": "Requesting a second 24-inch monitor for desk workstation setup to improve multitasking workflow.",
        "category": "Hardware",
        "priority": "Low",
        "status": "Closed",
    },
]


def seed_database(db_path: str = None) -> None:
    """Seed the database with 2 demo users and 5 sample tickets."""
    employee_password = os.getenv("EMPLOYEE_PASSWORD") or os.getenv("DEMO_EMPLOYEE_PASSWORD")
    support_password = os.getenv("SUPPORT_PASSWORD") or os.getenv("DEMO_STAFF_PASSWORD") or os.getenv("DEMO_SUPPORT_PASSWORD")

    missing = []
    if not employee_password:
        missing.append("EMPLOYEE_PASSWORD or DEMO_EMPLOYEE_PASSWORD")
    if not support_password:
        missing.append("SUPPORT_PASSWORD or DEMO_STAFF_PASSWORD")

    if missing:
        raise ValueError(
            f"Missing required environment variable(s): {', '.join(missing)}. "
            "Set these in your environment or .env file before seeding."
        )

    # Initialize schema
    init_db(db_path=db_path)

    conn = get_db(db_path=db_path)
    try:
        # 1. Seed Demo Users
        employee_user = get_user_by_username("employee1", db=conn)
        if employee_user is None:
            employee_id = create_user("employee1", employee_password, "employee", db=conn)
        else:
            employee_id = employee_user["id"]

        support_user = get_user_by_username("support1", db=conn)
        if support_user is None:
            support_id = create_user("support1", support_password, "support", db=conn)
        else:
            support_id = support_user["id"]

        # 2. Seed Sample Tickets
        existing_tickets = get_tickets(role="support", db=conn)
        if not existing_tickets:
            for ticket_data in SAMPLE_TICKETS:
                create_ticket(
                    title=ticket_data["title"],
                    description=ticket_data["description"],
                    category=ticket_data["category"],
                    priority=ticket_data["priority"],
                    status=ticket_data["status"],
                    created_by=employee_id,
                    db=conn,
                )
    finally:
        conn.close()


if __name__ == "__main__":
    try:
        seed_database()
        print("Database seeded successfully with demo users and sample tickets.")
    except Exception as e:
        print(f"Error seeding database: {e}", file=sys.stderr)
        sys.exit(1)
