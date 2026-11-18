import os
from pathlib import Path
from flask import Flask, jsonify
from dotenv import load_dotenv

# Load environment variables (.env or env)
env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    alt_env = Path(__file__).resolve().parent.parent / "env"
    if alt_env.exists():
        load_dotenv(dotenv_path=alt_env)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key")
app.config["DATABASE_URL"] = os.getenv("DATABASE_URL") or os.getenv("DATABASE_PATH") or "tickets.db"

# Register Blueprints
from app.auth import auth_bp
app.register_blueprint(auth_bp)

from app.routes import tickets_bp
app.register_blueprint(tickets_bp)


@app.get("/health")
def health():
    return jsonify({"status": "ok"})
