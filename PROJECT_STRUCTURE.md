# Project File Structure

```
ticket-app/
├── .cursor/
│   └── rules/
│       └── project.mdc        # Cursor rules (from cursor-project-rules.mdc)
├── app/
│   ├── __init__.py            # Flask app factory, config
│   ├── models.py              # DB connection, ticket and comment queries
│   ├── auth.py                # login/logout, role decorators
│   ├── routes.py              # ticket and comment routes
│   ├── templates/
│   │   ├── base.html
│   │   ├── login.html
│   │   ├── tickets.html       # list (own tickets / all for staff)
│   │   ├── ticket_new.html
│   │   └── ticket_detail.html # details, status change, comments
│   └── static/
│       └── style.css
├── tests/
│   ├── conftest.py            # test client, temp database, demo users
│   ├── test_permissions.py    # status change, ticket visibility
│   ├── test_validation.py     # empty title/description, title > 100
│   ├── test_closed_ticket.py  # no edit, comments still allowed
│   └── test_comments.py
├── docs/
│   ├── product_prompt.md
│   ├── spec_ai_draft.md       # the AI's first draft
│   ├── spec_final.md          # your edited version
│   ├── plan.md
│   ├── defect_log.md
│   ├── review_notes.md
│   └── screenshots/
├── AGENTS.md                  # project rules for AI agents
├── README.md
├── schema.sql                 # tables
├── seed.py                    # demo users and the 5 sample tickets
├── run.py                     # entry point
├── requirements.txt
├── .env.example               # placeholder values only
├── .env                       # real values, NEVER committed
└── .gitignore
```

## Where each file goes
| File you have | Put it at |
|---|---|
| AGENTS.md | `ticket-app/AGENTS.md` |
| cursor-project-rules.mdc | `ticket-app/.cursor/rules/project.mdc` |
| .gitignore | `ticket-app/.gitignore` |
| .env.example | `ticket-app/.env.example` (then copy to `.env`) |
| requirements.txt | `ticket-app/requirements.txt` |

## Setup commands
```
mkdir -p ticket-app/.cursor/rules ticket-app/docs/screenshots
cd ticket-app
git init
cp ../cursor-project-rules.mdc .cursor/rules/project.mdc
cp .env.example .env
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
git add . && git commit -m "Initial commit: project rules and structure"
```

## Demo users (seed.py)
| Username | Role | Password |
|---|---|---|
| ravi | Employee | set via env var, not hard-coded |
| asha | Support staff | set via env var, not hard-coded |

## Sample tickets (seed.py)
| # | Title | Category | Priority | Status |
|---|---|---|---|---|
| 1 | Laptop not charging | Hardware | High | Open |
| 2 | Cannot log in to VPN | Network | High | In Progress |
| 3 | Need access to the shared project folder | Access | Medium | Open |
| 4 | Excel keeps crashing on startup | Software | Medium | Resolved |
| 5 | Request a second monitor | Hardware | Low | Closed |
