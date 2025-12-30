from flask_bcrypt import generate_password_hash, check_password_hash
from datetime import datetime

class User:
    def __init__(self, username, password, role="cashier"):
        self.username = username
        self.password_hash = generate_password_hash(password).decode('utf-8')
        self.role = role
        self.created_at = datetime.utcnow()

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            "username": self.username,
            "role": self.role,
            "created_at": self.created_at,
            "password_hash": self.password_hash
        }