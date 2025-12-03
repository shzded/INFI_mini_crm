from datetime import datetime

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


# ---------- Auth / User ----------

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)

    # NEU: Rolle (CHEF / STAFF)
    role = db.Column(db.String(20), nullable=False, default="STAFF")

    # Beziehung zu Kontakten (optional, aber nice)
    contacts = db.relationship("Contact", back_populates="user", lazy="dynamic")

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def is_chef(self) -> bool:
        return (self.role or "").upper() == "CHEF"

    def __repr__(self) -> str:
        return f"<User {self.username} ({self.role})>"

class LoginCode(db.Model):
    __tablename__ = "login_codes"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    code = db.Column(db.String(5), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)


# ---------- CRM-Modelle ----------

class Customer(db.Model):
    __tablename__ = "customers"

    id = db.Column(db.Integer, primary_key=True)
    company = db.Column(db.String(120), nullable=False)
    contact_name = db.Column(db.String(120))
    email = db.Column(db.String(120))
    phone = db.Column(db.String(50))
    notes = db.Column(db.Text)

    street = db.Column(db.String(120))
    zip_code = db.Column(db.String(20))
    city = db.Column(db.String(80))

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Beziehungen
    orders = db.relationship("Order", back_populates="customer", lazy="dynamic")
    contacts = db.relationship("Contact", back_populates="customer", lazy="dynamic")

    def __repr__(self) -> str:
        return f"<Customer {self.company}>"


from datetime import datetime
from sqlalchemy import Numeric

class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)

    # NEU: Artikelnummer (aus Migration & Seed)
    sku = db.Column(db.String(50), unique=True, nullable=False)

    name = db.Column(db.String(120), nullable=False)

    # Preis
    unit_price = db.Column(db.Numeric(10, 2), nullable=False, default=0)

    # Erzeugungsdatum (aus Migration)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Beziehung zu OrderItems (optional, aber konsistent mit Orders)
    order_items = db.relationship("OrderItem", back_populates="product", lazy="dynamic")

    def __repr__(self):
        return f"<Product {self.sku} {self.name} €{self.unit_price}>"


class Order(db.Model):
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False, index=True)

    order_number = db.Column(db.String(50), unique=True, nullable=False)
    order_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    status = db.Column(db.String(20), default="offen", nullable=False)
    total_amount = db.Column(db.Numeric(10, 2), default=0, nullable=False)
    currency = db.Column(db.String(3), default="EUR", nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Beziehungen
    customer = db.relationship("Customer", back_populates="orders")
    items = db.relationship("OrderItem", back_populates="order", lazy="dynamic")

    def __repr__(self) -> str:
        return f"<Order {self.order_number} customer={self.customer_id}>"

    @property
    def positions_count(self) -> int:
        """Anzahl der Positionen (für Tabelle 'Positionen')."""
        return self.items.count()


class OrderItem(db.Model):
    __tablename__ = "order_items"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)

    order = db.relationship("Order", back_populates="items")
    product = db.relationship("Product", back_populates="order_items")


class Contact(db.Model):
    __tablename__ = "contacts"

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    channel = db.Column(db.String(20), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    notes = db.Column(db.Text)

    # NEU: Bewertung (1–5), optional
    rating = db.Column(db.Integer, nullable=True)

    contact_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    customer = db.relationship("Customer", back_populates="contacts")
    user = db.relationship("User", back_populates="contacts")

    def __repr__(self):
        return f"<Contact customer={self.customer_id} channel={self.channel} rating={self.rating}>"
