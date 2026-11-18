# AGENTS.md: Employee Support Ticket App

## Project
Small training web app. Employees raise support tickets; support staff update them.
Training lab only. No real company or client data.

## Stack
- Python 3.11+, Flask, SQLite (via sqlite3 or SQLAlchemy)
- Tests: pytest
- Templates: Jinja2 (server-rendered HTML), minimal CSS

## Structure
- app/__init__.py   : Flask app factory
- app/models.py     : database access and schema
- app/auth.py       : login, logout, role checks
- app/routes.py     : ticket and comment routes
- app/templates/    : HTML templates
- app/static/       : CSS
- tests/            : pytest tests
- run.py            : entry point
- schema.sql / seed.py : tables and demo data

## Commands
- Install: pip install -r requirements.txt
- Run: flask --app run run --debug
- Test: pytest -v

## Roles and business rules (do not break these)
1. Employee: submits tickets, sees ONLY their own tickets, adds comments on own tickets.
2. Support staff: sees ALL tickets, changes status, comments on any ticket.
3. Only support staff can change a ticket's status. Enforce on the server, not only in the UI.
4. Status flow: Open -> In Progress -> Resolved -> Closed.
5. A Closed ticket cannot be edited, but comments can still be added.
6. Title and description are required. Title max 100 characters.
7. Category: Hardware, Software, Network, Access, Other.
8. Priority: Low, Medium, High.
9. Created by and created date are set by the app. Last updated date changes on every update.

## Coding rules
- Validate every input on the server. Reject bad input with a clear message.
- Use parameterised SQL queries only. Never build SQL with string formatting.
- Handle errors; never show raw stack traces to users.
- Never hard-code passwords, keys or secrets. Read them from environment variables (.env).
- Hash passwords (werkzeug.security). Never store plain text.
- Keep functions small and name things clearly.

## Working rules for the AI agent
- Only change the files named in the task. Ask before touching anything else.
- Show a plan first for any change bigger than one function.
- Read existing code before editing it.
- Never delete files, drop tables or run destructive commands without asking me.
- Never publish, deploy or install global packages without asking me.
- Never read, print or commit .env or any secret.
- Add or update tests for every change, then run pytest.
- Make small changes so each one can be reviewed and committed on its own.
- If a command is unclear or risky, stop and ask.