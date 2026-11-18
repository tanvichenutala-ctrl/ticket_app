import os
from flask import Flask, jsonify
from dotenv import load_dotenv

# Load environment variables if available
load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key")
app.config["DATABASE_URL"] = os.getenv("DATABASE_URL", "tickets.db")


@app.get("/health")
def health():
    return jsonify({"status": "ok"})
