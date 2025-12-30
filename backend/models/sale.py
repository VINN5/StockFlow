from datetime import datetime

class Sale:
    def __init__(self, items, total_amount, payment_method="cash"):
        self.items = items  # list of dicts: {'product_id': str, 'quantity': int, 'selling_price': float}
        self.total_amount = float(total_amount)
        self.payment_method = payment_method
        self.date = datetime.utcnow()

    def to_dict(self):
        return {
            "items": self.items,
            "total_amount": self.total_amount,
            "payment_method": self.payment_method,
            "date": self.date
        }