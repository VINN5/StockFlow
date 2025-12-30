from datetime import datetime

class Purchase:
    def __init__(self, supplier_id, items, total_cost):
        self.supplier_id = supplier_id
        self.items = items  
        self.total_cost = float(total_cost)
        self.date = datetime.utcnow()

    def to_dict(self):
        return {
            "supplier_id": self.supplier_id,
            "items": self.items,
            "total_cost": self.total_cost,
            "date": self.date
        }