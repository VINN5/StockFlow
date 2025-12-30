from datetime import datetime

class Product:
    def __init__(self, name, description="", unit="piece", purchase_price=0.0, 
                 selling_price=0.0, min_stock=0, max_stock=None, current_quantity=0):
        self.name = name
        self.description = description
        self.unit = unit
        self.purchase_price = float(purchase_price)
        self.selling_price = float(selling_price)
        self.min_stock = int(min_stock)
        self.max_stock = int(max_stock) if max_stock is not None else None
        self.current_quantity = int(current_quantity)
        self.created_at = datetime.utcnow()

    def to_dict(self):
        return {
            "name": self.name,
            "description": self.description,
            "unit": self.unit,
            "purchase_price": self.purchase_price,
            "selling_price": self.selling_price,
            "min_stock": self.min_stock,
            "max_stock": self.max_stock,
            "current_quantity": self.current_quantity,
            "created_at": self.created_at
        }

    @staticmethod
    def from_dict(data):
        return Product(
            name=data["name"],
            description=data.get("description", ""),
            unit=data.get("unit", "piece"),
            purchase_price=data.get("purchase_price", 0.0),
            selling_price=data.get("selling_price", 0.0),
            min_stock=data.get("min_stock", 0),
            max_stock=data.get("max_stock"),
            current_quantity=data.get("current_quantity", 0)
        )