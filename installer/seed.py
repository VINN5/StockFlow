"""
installer/seed.py
Seeds a fresh StockFlow database with one business, admin user and sample data.
Run ONCE on fresh install only — safe because install.bat/sh only calls it when IS_UPDATE=false.
"""
import sys
import os

# Allow running from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pymongo import MongoClient
from datetime import datetime, timedelta
import bcrypt
import random

MONGO_URI = "mongodb://localhost:27017/stockflow"

client = MongoClient(MONGO_URI)
db = client.stockflow

# ── Guard: skip if data already exists ───────────────────────────────────────
if db.users.count_documents({}) > 0:
    print("[seed] Database already has data. Skipping.")
    sys.exit(0)

print("[seed] Seeding sample data...")

# ── Business ──────────────────────────────────────────────────────────────────
biz = db.businesses.insert_one({
    "name": "Demo Shop",
    "location": "Nairobi, Kenya",
    "created_at": datetime.utcnow()
})
biz_id = biz.inserted_id

# ── Super admin ───────────────────────────────────────────────────────────────
hashed = bcrypt.hashpw(b"admin123", bcrypt.gensalt()).decode()
db.users.insert_one({
    "username": "superadmin",
    "password_hash": hashed,
    "role": "super_admin",
    "created_at": datetime.utcnow()
})

# ── Branch admin ──────────────────────────────────────────────────────────────
hashed2 = bcrypt.hashpw(b"demo1234", bcrypt.gensalt()).decode()
db.users.insert_one({
    "username": "demoadmin",
    "password_hash": hashed2,
    "role": "admin",
    "business_id": biz_id,
    "created_at": datetime.utcnow()
})

# ── Suppliers ─────────────────────────────────────────────────────────────────
supplier_ids = []
suppliers = [
    {"name": "Bidco Africa", "contact_person": "Jane Wanjiru", "phone": "0712000001", "email": "jane@bidco.co.ke", "address": "Industrial Area, Nairobi"},
    {"name": "Unga Group", "contact_person": "Peter Kamau", "phone": "0722000002", "email": "peter@unga.co.ke", "address": "Westlands, Nairobi"},
    {"name": "Procter & Gamble KE", "contact_person": "Mary Akinyi", "phone": "0733000003", "email": "mary@pg.co.ke", "address": "Upper Hill, Nairobi"},
]
for s in suppliers:
    s["business_id"] = biz_id
    s["created_at"] = datetime.utcnow()
    r = db.suppliers.insert_one(s)
    supplier_ids.append(r.inserted_id)

# ── Products ──────────────────────────────────────────────────────────────────
products_data = [
    {"name": "Maize Flour 2kg",    "unit": "bag",   "purchase_price": 95,  "selling_price": 120, "current_quantity": 80,  "min_stock": 20},
    {"name": "Cooking Oil 1L",     "unit": "piece", "purchase_price": 180, "selling_price": 220, "current_quantity": 60,  "min_stock": 15},
    {"name": "Sugar 1kg",          "unit": "kg",    "purchase_price": 120, "selling_price": 150, "current_quantity": 100, "min_stock": 25},
    {"name": "Bread",              "unit": "piece", "purchase_price": 45,  "selling_price": 60,  "current_quantity": 30,  "min_stock": 10},
    {"name": "Milk 500ml",         "unit": "piece", "purchase_price": 50,  "selling_price": 65,  "current_quantity": 3,   "min_stock": 20},  # low stock
    {"name": "Washing Powder 1kg", "unit": "pack",  "purchase_price": 140, "selling_price": 180, "current_quantity": 45,  "min_stock": 10},
    {"name": "Bar Soap",           "unit": "piece", "purchase_price": 40,  "selling_price": 55,  "current_quantity": 70,  "min_stock": 15},
    {"name": "Rice 2kg",           "unit": "bag",   "purchase_price": 160, "selling_price": 200, "current_quantity": 2,   "min_stock": 10},  # low stock
]
product_ids = []
for p in products_data:
    p["business_id"]  = biz_id
    p["description"]  = ""
    p["max_stock"]    = None
    p["created_at"]   = datetime.utcnow()
    r = db.products.insert_one(p)
    product_ids.append(r.inserted_id)

# ── Clients ───────────────────────────────────────────────────────────────────
client_ids = []
clients = [
    {"name": "John Kamau",   "contact": "0722111001", "kra_pin": "", "balance": 350.0},
    {"name": "Grace Otieno", "contact": "0733222002", "kra_pin": "", "balance": 0.0},
    {"name": "Supermarket A","contact": "0700333003", "kra_pin": "A001234567B", "balance": 1200.0},
]
for c in clients:
    c["business_id"] = biz_id
    c["created_at"]  = datetime.utcnow()
    r = db.clients.insert_one(c)
    client_ids.append(r.inserted_id)

# ── Purchases ─────────────────────────────────────────────────────────────────
db.purchases.insert_many([
    {
        "business_id": biz_id,
        "supplier_id": supplier_ids[0],
        "items": [
            {"product_id": str(product_ids[0]), "quantity": 50, "cost_price": 95},
            {"product_id": str(product_ids[2]), "quantity": 40, "cost_price": 120},
        ],
        "total_cost": 50*95 + 40*120,
        "date": datetime.utcnow() - timedelta(days=5)
    },
    {
        "business_id": biz_id,
        "supplier_id": supplier_ids[1],
        "items": [
            {"product_id": str(product_ids[1]), "quantity": 30, "cost_price": 180},
        ],
        "total_cost": 30*180,
        "date": datetime.utcnow() - timedelta(days=2)
    }
])

# ── Sales (last 7 days) ───────────────────────────────────────────────────────
payment_methods = ["cash", "mpesa", "credit"]
for i in range(14):
    day_offset = random.randint(0, 6)
    sale_date  = datetime.utcnow().replace(hour=random.randint(8,18), minute=random.randint(0,59)) - timedelta(days=day_offset)
    pid_index  = random.randint(0, len(product_ids)-1)
    prod       = products_data[pid_index]
    qty        = random.randint(1, 4)
    method     = random.choice(payment_methods)
    client_id  = client_ids[0] if method == "credit" else None

    sale = {
        "business_id":    biz_id,
        "cashier_name":   "demoadmin",
        "items": [{
            "product_id":   str(product_ids[pid_index]),
            "quantity":     qty,
            "selling_price": prod["selling_price"],
            "line_total":   qty * prod["selling_price"]
        }],
        "total_amount":   qty * prod["selling_price"],
        "payment_method": method,
        "date":           sale_date
    }
    if client_id:
        sale["client_id"] = client_id

    db.sales.insert_one(sale)

print("[seed] Done. Sample credentials:")
print("       Super Admin — username: superadmin  password: admin123")
print("       Branch Admin — username: demoadmin  password: demo1234")