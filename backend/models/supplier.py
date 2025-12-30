from datetime import datetime

class Supplier:
    def __init__(self, name, contact_person="", phone="", email="", address=""):
        self.name = name
        self.contact_person = contact_person
        self.phone = phone
        self.email = email
        self.address = address
        self.created_at = datetime.utcnow()

    def to_dict(self):
        return {
            "name": self.name,
            "contact_person": self.contact_person,
            "phone": self.phone,
            "email": self.email,
            "address": self.address,
            "created_at": self.created_at
        }