import json
import os
import hashlib
from pathlib import Path

USERS_FILE = "metadata/users.json"

def _load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    try:
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def _save_users(users):
    os.makedirs(os.path.dirname(USERS_FILE), exist_ok=True)
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)

def hash_password(password: str) -> str:
    """Hash a password with a basic SHA-256 for hackathon purposes."""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_login(email: str, password: str) -> bool:
    """Verify email and password match."""
    users = _load_users()
    email = email.lower().strip()
    if email not in users:
        return False
    return users[email]["password_hash"] == hash_password(password)

def register_user(email: str, password: str) -> bool:
    """Register a new user. Returns True if successful, False if email already exists."""
    users = _load_users()
    email = email.lower().strip()
    if email in users:
        return False
    
    users[email] = {
        "password_hash": hash_password(password)
    }
    _save_users(users)
    return True
