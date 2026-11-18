# Code & Security Review Notes

## 1. Secrets & `.gitignore` Check
- **Verified:** `.env` and `*.db` are listed in `.gitignore` and excluded from `git ls-files`.
- **Verified:** Searched codebase for `password`, `secret`, and `key`; credentials are loaded via environment variables (`os.environ.get`).

## 2. Unvalidated Inputs
- [List any confirmed missing validation—e.g., comment max length or whitespace-only input—or note that title <= 100, required description, and non-empty comment checks are enforced.]

## 3. Missing Error Handling
- [List any confirmed missing error handling—e.g., non-existent ticket ID returning 500 instead of 404, or missing database error handling—or note confirmed clean paths.]

## 4. Unused Files
- [List any unused/duplicate files found in the repo—e.g., leftover `app.py` or empty directories—or confirm none exist.]