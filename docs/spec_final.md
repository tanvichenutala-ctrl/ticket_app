# Specification: Employee Support Ticket App

## 1. Overview
The Employee Support Ticket App is a lightweight internal web application designed to allow employees to submit and track IT support requests, while enabling IT support staff to view, manage, comment on, and resolve tickets through a defined status lifecycle.

---

## 2. Target Users & Roles
- **Employee**: Can submit new support tickets, view and edit their own tickets, and add comments to their own tickets. Cannot view other employees' tickets and cannot change ticket statuses.
- **Support Staff**: Can view all tickets submitted across the organization, update ticket statuses, and post comments on any ticket.

---

## 3. Data Model & Field Specifications

### 3.1 Ticket Entity
- **ID**: Unique identifier (integer, auto-increment primary key).
- **Title**: Required string, maximum 100 characters, cannot be empty or whitespace only.
- **Description**: Required text, cannot be empty or whitespace only.
- **Category**: Required enum: `Hardware`, `Software`, `Network`, `Access`, `Other`.
- **Priority**: Required enum: `Low`, `Medium`, `High`. Default: `Medium`.
- **Status**: Lifecycle enum: `Open` → `In Progress` → `Resolved` → `Closed`. Initial state is `Open`. Editable solely by Support Staff.
- **Created By**: User ID / Username of the submitting employee (set automatically by the system).
- **Created Date**: Timestamp set automatically upon creation.
- **Last Updated Date**: Timestamp updated automatically upon any modification to the ticket or its status.

### 3.2 Comment Entity
- **ID**: Unique identifier (integer, auto-increment primary key).
- **Ticket ID**: Foreign key referencing the parent ticket.
- **Author ID**: Foreign key referencing the user who wrote the comment.
- **Content**: Required text, cannot be empty or whitespace only.
- **Created Date**: Timestamp set automatically upon submission.

### 3.3 User Entity
- **ID**: Unique identifier.
- **Username**: Unique identifier for login.
- **Password Hash**: Securely hashed password (via `werkzeug.security`).
- **Role**: `employee` or `support`.

---

## 4. User Stories

- **US1: Authentication & Role Session**
  - *As a* user (Employee or Support Staff),
  - *I want to* log in with my credentials,
  - *So that* I can access the system with permissions matching my role.

- **US2: Ticket Submission**
  - *As an* Employee,
  - *I want to* submit a support ticket with a title, description, category, and priority,
  - *So that* the IT support team can assist me with my issue.

- **US3: View My Tickets**
  - *As an* Employee,
  - *I want to* see a list of tickets I have created along with their current status,
  - *So that* I can track the progress of my requests without seeing tickets raised by other employees.

- **US4: View All Tickets**
  - *As a* Support Staff member,
  - *I want to* see all tickets submitted by any employee,
  - *So that* I can triage, prioritize, and manage the team's IT support queue.

- **US5: Ticket Details Inspection**
  - *As a* user,
  - *I want to* view the complete details and conversation history of an authorized ticket,
  - *So that* I can understand the context and progress of the issue.

- **US6: Change Ticket Status**
  - *As a* Support Staff member,
  - *I want to* advance or update the ticket status (`Open` → `In Progress` → `Resolved` → `Closed`),
  - *So that* all parties know the current resolution stage.

- **US7: Edit Ticket Details**
  - *As an* Employee,
  - *I want to* edit the title, description, category, or priority of my own non-closed ticket,
  - *So that* I can provide corrections or additional information before it is resolved.

- **US8: Comment on Tickets**
  - *As an* Employee or Support Staff member,
  - *I want to* post comments on a ticket (including Closed tickets),
  - *So that* follow-up details, instructions, or resolution notes can be recorded.

---

## 5. Acceptance Criteria (Given / When / Then)

### AC1: User Login & Role Assignment
- **Given** seeded demo users exist (`employee1` with role `employee` and `support1` with role `support`),
- **When** a user submits valid login credentials,
- **Then** the application authenticates the user, starts a secure session, and redirects them to their respective ticket dashboard reflecting their role permissions.

### AC2: Unauthorized / Unauthenticated Access
- **Given** an unauthenticated visitor,
- **When** they attempt to access any ticket dashboard or ticket action URL,
- **Then** the application redirects them to the login page with an error or informational message.

### AC3: Ticket Creation - Happy Path
- **Given** a logged-in Employee on the "New Ticket" page,
- **When** they fill in a valid Title (1-100 characters), Description, Category (`Hardware`, `Software`, `Network`, `Access`, or `Other`), and Priority (`Low`, `Medium`, or `High`), and click submit,
- **Then** a new ticket is saved with Status `Open`, `Created By` set to the employee's ID, `Created Date` and `Last Updated Date` set to the current timestamp, and the user is redirected to the ticket view or list with a success notification.

### AC4: Ticket Creation - Validation Failure
- **Given** a logged-in Employee on the "New Ticket" page,
- **When** they submit the form with an empty Title, whitespace-only Title, empty Description, or Title exceeding 100 characters,
- **Then** the ticket is not created, the database state remains unchanged, and the form re-renders displaying a clear, descriptive validation error.

### AC5: Ticket List Isolation for Employees
- **Given** a logged-in Employee,
- **When** they navigate to the ticket list view,
- **Then** only tickets created by their own user account are displayed, and no tickets from other employees appear.

### AC6: Ticket List Queue for Support Staff
- **Given** a logged-in Support Staff member,
- **When** they navigate to the ticket list view,
- **Then** all tickets across all employees are displayed with their ID, Title, Category, Priority, Status, Creator, and Created/Updated timestamps.

### AC7: Ticket Detail Authorization
- **Given** a logged-in Employee,
- **When** they attempt to view a ticket detail page (`/tickets/<id>`) belonging to another employee,
- **Then** the server responds with a 403 Forbidden or 404 Not Found error and does not reveal the ticket data.

### AC8: Status Update by Support Staff
- **Given** a logged-in Support Staff member viewing any ticket,
- **When** they change the status following the lifecycle flow (`Open` → `In Progress` → `Resolved` → `Closed`) and submit,
- **Then** the status is updated in the database, the `Last Updated Date` is updated to the current timestamp, and the page reflects the new status.

### AC9: Status Update Prevention for Employees
- **Given** a logged-in Employee,
- **When** they attempt to change the status of a ticket (either via form manipulation or direct POST request),
- **Then** the server rejects the request with a 403 Forbidden error, and the status remains unchanged.

### AC10: Edit Ticket Restrictions on Closed Tickets
- **Given** a ticket marked with Status `Closed`,
- **When** an Employee attempts to update the title, description, category, or priority,
- **Then** the server rejects the update with an error stating that Closed tickets cannot be edited, preserving the existing ticket data.

### AC11: Adding Comments to Active and Closed Tickets
- **Given** an authorized user (an Employee viewing their own ticket, or Support Staff viewing any ticket),
- **When** they enter non-empty text in the comment box and submit (regardless of whether the ticket status is `Open`, `In Progress`, `Resolved`, or `Closed`),
- **Then** the comment is saved with the user's ID and current timestamp, appended to the ticket conversation history, and displayed in chronological order.

### AC12: Comment Validation
- **Given** an authorized user on a ticket page,
- **When** they attempt to submit a blank or whitespace-only comment,
- **Then** the submission is rejected with a validation error message and no comment record is created.

### AC13: Employee Comment Isolation
- **Given** a logged-in Employee,
- **When** they attempt to submit a comment on a ticket created by another employee,
- **Then** the server rejects the request with a 403 Forbidden error and no comment record is created.

---

## 6. Non-Functional Requirements

### 6.1 Architecture & Stack
- **Framework**: Python 3.11+ with Flask.
- **Database**: SQLite3 accessed via standard parameterized queries or lightweight ORM (e.g., SQLAlchemy).
- **Templates**: Jinja2 server-rendered templates with clean, semantic HTML5 and minimal CSS styling.
- **Testing**: Automated test suite using `pytest` covering models, authorization, and route endpoints.

### 6.2 Security & Data Protection
- **No Secrets in Code**: Secret keys and configuration must be loaded from environment variables (`.env`).
- **Password Security**: Passwords must be hashed using secure hashing algorithms (e.g., `werkzeug.security.generate_password_hash`); never store plain-text passwords.
- **SQL Injection Prevention**: All database interactions must use parameterized SQL queries or ORM queries. String interpolation or concatenation for SQL commands is strictly forbidden.
- **Server-Side Authorization**: Role-based access control must be strictly enforced on the server for all routes and mutations, not merely obscured in the client template.
- **Error Handling**: Graceful error handling with user-friendly error views; under no circumstances should raw database errors or stack traces be exposed to the client.

### 6.3 Performance & Reliability
- **Response Times**: Simple queries against local SQLite database should execute in < 50ms under typical local development load.
- **Data Integrity**: Foreign key constraints enabled in SQLite to maintain referential integrity between users, tickets, and comments.

---

## 7. Task List

- [ ] **Task 1: Environment & Project Setup**
  - Create directory structure (`app/`, `app/templates/`, `app/static/`, `tests/`).
  - Set up `requirements.txt` with Flask, pytest, and python-dotenv.
  - Implement Flask application factory in `app/__init__.py`.
  - Configure environment variable handling for `SECRET_KEY` and database path.

- [ ] **Task 2: Database Schema & Seeding**
  - Define database schema for `users`, `tickets`, and `comments` in `schema.sql` (or `app/models.py`).
  - Create `seed.py` to initialize tables and seed:
    - 2 demo users: one employee (`employee1`), one support staff (`support1`) with hashed passwords.
    - 5 sample tickets as specified in documentation (Hardware, Network, Access, Software tickets across Open, In Progress, Resolved, and Closed states).

- [ ] **Task 3: Authentication & Role-Based Access Control**
  - Implement login and logout routes in `app/auth.py`.
  - Implement session management with user identity and role stored securely in session.
  - Build helper decorators/functions (`@login_required`, `@role_required('support')`).

- [ ] **Task 4: Ticket Creation & Employee Views**
  - Implement `GET /tickets` for employees (filtered to display only `current_user` tickets).
  - Implement `GET /tickets/new` and `POST /tickets/new` with server-side validation (title max 100 chars, required fields).
  - Implement `GET /tickets/<id>` showing ticket details, author, timestamps, and comments for authorized employees.
  - Implement `POST /tickets/<id>/edit` allowing employees to update non-closed tickets.

- [ ] **Task 5: Support Staff Ticket Queue & Status Transitions**
  - Implement `GET /tickets` for support staff showing all tickets with filtering/sorting capabilities.
  - Implement `POST /tickets/<id>/status` route restricted to support staff.
  - Enforce status flow (`Open` → `In Progress` → `Resolved` → `Closed`) and auto-update `last_updated` timestamp.
  - Enforce server-side rejection if an employee attempts to trigger status modification.

- [x] **Task 6: Commenting System**
  - Implement `POST /tickets/<id>/comments` route for adding comments.
  - Ensure comments can be added by the owner employee or support staff, including on `Closed` tickets.
  - Validate non-empty comment content on the server.

- [ ] **Task 7: User Interface & Templates**
  - Create base template `base.html` with navigation (showing logged-in user, role, and logout link) and flash message container.
  - Create `login.html`, `ticket_list.html`, `ticket_new.html`, and `ticket_detail.html`.
  - Add minimal CSS in `app/static/style.css` for clean table views, badge styling for status/priority, and form layouts.

- [ ] **Task 8: Automated Testing Suite**
  - Write unit and integration tests in `tests/`:
    - `test_auth.py`: Login, logout, session persistence.
    - `test_tickets.py`: Ticket creation, validation checks (title length, missing fields), role-based list filtering, detail view authorization.
    - `test_status_flow.py`: Support staff status updates, employee status change prohibition, closed ticket edit restrictions.
    - `test_comments.py`: Comment creation on active and closed tickets, comment validation.

title length at most 100 characters and ticket list loads in under 2 seconds