"""
installer/reset_superadmin.py
Emergency script to reset the superadmin password.
Run from the StockFlow root folder:
    python installer/reset_superadmin.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pymongo import MongoClient
import bcrypt
import getpass

print("\n StockFlow — Super Admin Password Reset")
print(" ────────────────────────────────────────")

uri = "mongodb://localhost:27017/stockflow"
client = MongoClient(uri)
db = client.stockflow

# Find super admin
admin = db.users.find_one({"role": "super_admin"})
if not admin:
    print(" [ERROR] No super admin found in database.")
    sys.exit(1)

print(f" Found super admin: {admin['username']}")
print()

new_password = getpass.getpass(" Enter new password (min 6 chars): ")
if len(new_password) < 6:
    print(" [ERROR] Password too short.")
    sys.exit(1)

confirm = getpass.getpass(" Confirm new password: ")
if new_password != confirm:
    print(" [ERROR] Passwords do not match.")
    sys.exit(1)

hashed = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
db.users.update_one({"_id": admin["_id"]}, {"$set": {"password_hash": hashed}})

print()
print(f" [OK] Password for '{admin['username']}' has been reset.")
print(" You can now log in with your new password.")
print()