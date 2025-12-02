import os
import random
from datetime import datetime, timedelta
from sqlalchemy import or_

from flask import (
    Flask, render_template, request, redirect, url_for, flash, session
)

from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, PasswordField, BooleanField
from wtforms.validators import DataRequired, Email, Optional, Length, EqualTo
from flask_login import (
    LoginManager, login_user, login_required, logout_user, current_user
)
from flask_mail import Mail, Message
from flask_migrate import Migrate

from models import db, User, LoginCode, Customer, Product, Order, OrderItem, Contact


# ------------------ Basis ------------------
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "crm.sqlite3")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")

# --- Datenbank-Config ---
# Bevorzugt MySQL/MariaDB über Umgebungsvariable, sonst SQLite als Fallback (lokale Entwicklung)
db_url = os.environ.get("DATABASE_URL")
if db_url:
    # Beispiel für MySQL: mysql+pymysql://user:pass@host/dbname
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)
migrate = Migrate(app, db)

# --- Mail-Settings ---
app.config.update(
    MAIL_SERVER=os.environ.get("MAIL_SERVER", "smtp.gmail.com"),
    MAIL_PORT=int(os.environ.get("MAIL_PORT", "587")),
    MAIL_USE_TLS=os.environ.get("MAIL_USE_TLS", "True") == "True",
    MAIL_USERNAME=os.environ.get("MAIL_USER"),
    MAIL_PASSWORD=os.environ.get("MAIL_PASS"),
    MAIL_DEFAULT_SENDER=os.environ.get(
        "MAIL_SENDER",
        os.environ.get("MAIL_USER", "noreply@example.com"),
    ),
)
mail = Mail(app)

# ------------------ Login-Manager ------------------
login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.login_message = "Bitte melde dich an, um fortzufahren."
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ------------------ Forms ------------------
class CustomerForm(FlaskForm):
    company = StringField("Firma", validators=[DataRequired()])
    contact_name = StringField("Ansprechperson", validators=[Optional()])
    email = StringField("E-Mail", validators=[Optional(), Email(message="Ungültige E-Mail")])
    phone = StringField("Telefon", validators=[Optional()])
    notes = TextAreaField("Notizen", validators=[Optional()])

class LoginForm(FlaskForm):
    # Username wird als E-Mail verwendet
    username = StringField("E-Mail", validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField("Passwort", validators=[DataRequired(), Length(min=6)])
    remember = BooleanField("Angemeldet bleiben")

class RegisterForm(FlaskForm):
    username = StringField("E-Mail", validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField("Passwort", validators=[DataRequired(), Length(min=6)])
    confirm = PasswordField("Passwort wiederholen", validators=[
        DataRequired(), EqualTo("password", "Passwörter stimmen nicht überein")
    ])

# ------------------ Hilfsfunktionen ------------------
def generate_code() -> str:
    """Erzeuge 5-stelligen Code (mit führenden Nullen möglich)."""
    return f"{random.randint(0, 99999):05d}"

def send_login_code(email: str, code: str):
    """Sende Code per E-Mail. Fallback: Log-Ausgabe, wenn Senden scheitert (z. B. Free-Plan)."""
    try:
        # Wenn MAIL_USERNAME nicht gesetzt ist, schicken wir nicht und loggen nur
        if not app.config.get("MAIL_USERNAME"):
            raise RuntimeError("MAIL_USERNAME nicht gesetzt – Debug-Fallback aktiv.")
        msg = Message("Dein Anmeldecode", recipients=[email])
        msg.body = f"Dein Login-Code lautet: {code}\nEr ist 5 Minuten gültig."
        mail.send(msg)
    except Exception as e:
        # Fallback: Code im Log ausgeben
        print(f"[WARN] Mail konnte nicht gesendet werden: {e}")
        print(f"[DEBUG] Login-Code fuer {email}: {code}")

def start_2fa_flow(user: User):
    """Erzeugt Code, speichert ihn und leitet den Verify-Flow ein."""
    # Alte Codes des Users invalidieren (optional: löschen)
    LoginCode.query.filter_by(user_id=user.id).delete()

    code = generate_code()
    expires = datetime.utcnow() + timedelta(minutes=5)
    db.session.add(LoginCode(user_id=user.id, code=code, expires_at=expires))
    db.session.commit()

    send_login_code(user.username, code)

    # Merke pending user in Session (nicht eingeloggt!)
    session["pending_user_id"] = user.id
    session["pending_next"] = request.args.get("next") if request.args.get("next", "").startswith("/") else None

# ------------------ Routes (Auth) ------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("customers"))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data.strip()).first()
        if user and user.check_password(form.password.data):
            # Schritt 1: 2FA-Code erzeugen und senden
            start_2fa_flow(user)
            flash("Wir haben dir einen 5-stelligen Code geschickt. Bitte gib ihn ein.", "info")
            return redirect(url_for("verify"))
        flash("Ungültige E-Mail oder Passwort.", "error")
    return render_template("login.html", form=form)

@app.route("/verify", methods=["GET", "POST"])
def verify():
    pending_id = session.get("pending_user_id")
    if not pending_id:
        flash("Sitzung ist abgelaufen. Bitte erneut anmelden.", "error")
        return redirect(url_for("login"))

    user = User.query.get_or_404(pending_id)

    if request.method == "POST":
        code_input = (request.form.get("code") or "").strip()
        record = (
            LoginCode.query.filter_by(user_id=user.id, code=code_input)
            .order_by(LoginCode.id.desc())
            .first()
        )
        now = datetime.utcnow()

        if record and record.expires_at > now:
            # Gültig -> Code nur einmal verwendbar
            db.session.delete(record)
            db.session.commit()

            remember = bool(request.form.get("remember") == "y")
            login_user(user, remember=remember)

            # Aufräumen der Session
            next_page = session.pop("pending_next", None)
            session.pop("pending_user_id", None)

            flash("Login erfolgreich!", "success")
            return redirect(next_page or url_for("customers"))
        else:
            flash("Ungültiger oder abgelaufener Code.", "error")

    # Optional: erneuten Versand ermöglichen
    if request.args.get("resend") == "1":
        start_2fa_flow(user)
        flash("Neuer Code gesendet.", "info")
        return redirect(url_for("verify"))

    return render_template("verify.html", user=user)

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Abgemeldet.", "info")
    return redirect(url_for("login"))

@app.route("/register", methods=["GET", "POST"])
def register():
    # Hinweis: Für Produktion ggf. deaktivieren oder absichern!
    if current_user.is_authenticated:
        return redirect(url_for("customers"))
    form = RegisterForm()
    if form.validate_on_submit():
        username = form.username.data.strip().lower()
        if User.query.filter_by(username=username).first():
            flash("E-Mail bereits registriert.", "error")
        else:
            u = User(username=username)
            u.set_password(form.password.data)
            db.session.add(u)
            db.session.commit()
            flash("Benutzer angelegt. Bitte anmelden.", "success")
            return redirect(url_for("login"))
    return render_template("register.html", form=form)

# ------------------ Routes (CRM) ------------------
@app.route("/")
@login_required
def index():
    # --- Kunden-Sektion ---
    q_customers = (request.args.get("q") or "").strip()
    cust_query = Customer.query

    if q_customers:
        like = f"%{q_customers}%"
        cust_query = cust_query.filter(
            or_(
                Customer.company.ilike(like),
                Customer.contact_name.ilike(like),
                Customer.email.ilike(like),
                Customer.phone.ilike(like),
            )
        )

    cust_query = cust_query.order_by(Customer.company.asc())
    customer_list = cust_query.limit(10).all()

    # Aktivität: Tage seit letztem Kontakt
    now = datetime.utcnow()
    customer_rows = []
    for c in customer_list:
        last_contact = (
            Contact.query.filter_by(customer_id=c.id)
            .order_by(Contact.contact_at.desc())
            .first()
        )
        if last_contact:
            days = (now - last_contact.contact_at).days
        else:
            days = None
        customer_rows.append((c, days))

    # --- Bestellungen-Sektion ---
    q_orders = (request.args.get("q_orders") or "").strip()
    order_query = Order.query.join(Customer)

    if q_orders:
        like = f"%{q_orders}%"
        order_query = order_query.filter(
            or_(
                Order.order_number.ilike(like),
                Customer.company.ilike(like),
            )
        )

    order_query = order_query.order_by(Order.order_date.desc())
    orders = order_query.limit(10).all()

    # --- Kontakte-Sektion ---
    channel = (request.args.get("channel") or "all").strip().lower()
    contact_query = Contact.query.join(Customer)

    if channel and channel != "all":
        contact_query = contact_query.filter(Contact.channel == channel)

    contact_query = contact_query.order_by(Contact.contact_at.desc())
    contacts = contact_query.limit(10).all()

    return render_template(
        "index.html",
        customers=customer_rows,
        q_customers=q_customers,
        orders=orders,
        q_orders=q_orders,
        contacts=contacts,
        channel=channel,
    )

@app.route("/customers")
@login_required
def customers():
    q = request.args.get("q", "", type=str).strip()
    page = request.args.get("page", 1, type=int)
    per_page = 10

    query = Customer.query
    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(
                Customer.company.ilike(like),
                Customer.contact_name.ilike(like),
                Customer.email.ilike(like),
                Customer.phone.ilike(like),
                Customer.notes.ilike(like),
            )
        )

    pagination = query.order_by(Customer.company.asc()).paginate(page=page, per_page=per_page)
    return render_template("customers.html", pagination=pagination, q=q)

@app.route("/contacts")
@login_required
def contacts():
    channel = (request.args.get("channel") or "all").strip().lower()
    page = request.args.get("page", 1, type=int)
    per_page = 20

    query = Contact.query.join(Customer).order_by(Contact.contact_at.desc())

    if channel and channel != "all":
        query = query.filter(Contact.channel == channel)

    pagination = query.paginate(page=page, per_page=per_page)

    return render_template(
        "contacts.html",
        pagination=pagination,
        channel=channel,
    )

@app.route("/orders")
@login_required
def orders():
    q = (request.args.get("q") or "").strip()
    page = request.args.get("page", 1, type=int)
    per_page = 20

    query = Order.query.join(Customer)

    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                Order.order_number.ilike(like),
                Customer.company.ilike(like),
            )
        )

    query = query.order_by(Order.order_date.desc())

    pagination = query.paginate(page=page, per_page=per_page)

    return render_template(
        "orders.html",
        pagination=pagination,
        q=q,
    )

@app.route("/customers/<int:customer_id>")
@login_required
def customer_detail(customer_id):
    customer = Customer.query.get_or_404(customer_id)

    # Letzter Kontakt (für Header)
    last_contact = (
        Contact.query.filter_by(customer_id=customer.id)
        .order_by(Contact.contact_at.desc())
        .first()
    )
    now = datetime.utcnow()
    days_since_last_contact = None
    if last_contact:
        days_since_last_contact = (now - last_contact.contact_at).days

    # KPI: Basis-Query für Umsatz (ohne stornierte)
    base_orders = (
        Order.query.filter_by(customer_id=customer.id)
        .filter(Order.status != "storniert")
    )

    # Umsatz gesamt
    revenue_total = (
        base_orders.with_entities(db.func.sum(Order.total_amount)).scalar() or 0
    )

    # Umsatz letztes Jahr (Kalenderjahr)
    today = now.date()
    last_year = today.year - 1
    jan1 = datetime(last_year, 1, 1)
    dec31 = datetime(last_year, 12, 31, 23, 59, 59)

    revenue_last_year = (
        base_orders.filter(Order.order_date >= jan1, Order.order_date <= dec31)
        .with_entities(db.func.sum(Order.total_amount))
        .scalar()
        or 0
    )

    # Datumsbereich aus Query-Parametern
    date_from_str = (request.args.get("from") or "").strip()
    date_to_str = (request.args.get("to") or "").strip()
    date_from = None
    date_to = None

    if date_from_str:
        try:
            date_from = datetime.strptime(date_from_str, "%Y-%m-%d")
        except ValueError:
            date_from_str = ""
            date_from = None

    if date_to_str:
        try:
            date_to = datetime.strptime(date_to_str, "%Y-%m-%d")
            date_to = date_to.replace(hour=23, minute=59, second=59)
        except ValueError:
            date_to_str = ""
            date_to = None

    # Bestellungen-Liste
    orders_query = Order.query.filter_by(customer_id=customer.id).order_by(
        Order.order_date.desc()
    )
    # Kontakte-Liste
    contacts_query = Contact.query.filter_by(customer_id=customer.id).order_by(
        Contact.contact_at.desc()
    )

    if date_from:
        orders_query = orders_query.filter(Order.order_date >= date_from)
        contacts_query = contacts_query.filter(Contact.contact_at >= date_from)
    if date_to:
        orders_query = orders_query.filter(Order.order_date <= date_to)
        contacts_query = contacts_query.filter(Contact.contact_at <= date_to)

    orders = orders_query.limit(10).all()
    contacts = contacts_query.limit(10).all()

    return render_template(
        "customer_detail.html",
        customer=customer,
        last_contact=last_contact,
        days_since_last_contact=days_since_last_contact,
        revenue_total=revenue_total,
        revenue_last_year=revenue_last_year,
        last_year=last_year,
        date_from=date_from_str,
        date_to=date_to_str,
        orders=orders,
        contacts=contacts,
    )

@app.route("/customers/new", methods=["GET", "POST"])
@login_required
def customer_new():
    form = CustomerForm()
    if form.validate_on_submit():
        c = Customer(
            company=form.company.data,
            contact_name=form.contact_name.data,
            email=form.email.data,
            phone=form.phone.data,
            notes=form.notes.data,
        )
        db.session.add(c)
        db.session.commit()
        flash("Kunde angelegt.", "success")
        return redirect(url_for("customers"))
    return render_template("customer_form.html", form=form, title="Neuer Kunde")

@app.route("/customers/<int:customer_id>/edit", methods=["GET", "POST"])
@login_required
def customer_edit(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    form = CustomerForm(obj=customer)
    if form.validate_on_submit():
        form.populate_obj(customer)
        db.session.commit()
        flash("Kunde aktualisiert.", "success")
        return redirect(url_for("customer_detail", customer_id=customer.id))
    return render_template("customer_form.html", form=form, title="Kunde bearbeiten")

@app.route("/customers/<int:customer_id>/delete", methods=["POST"])
@login_required
def customer_delete(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    db.session.delete(customer)
    db.session.commit()
    flash("Kunde gelöscht.", "info")
    return redirect(url_for("customers"))

# ------------------ CLI / Seeder ------------------
@app.cli.command("seed-db")
def seed_db():
    """Beispieldaten: 1 Demo-User, >=10 Kunden, Produkte, >=50 Bestellungen, >=50 Kontakte."""

    print("Starte Seeding ...")

    # Demo-User anlegen (für contacts.user_id)
    user = User.query.filter_by(username="demo@example.com").first()
    if not user:
        user = User(username="demo@example.com")
        user.set_password("demo1234")
        db.session.add(user)
        db.session.commit()
        print("Demo-User angelegt: demo@example.com / demo1234")
    else:
        print("Demo-User existiert bereits.")

    # Produkte anlegen
    if Product.query.count() == 0:
        products_data = [
            ("P-1001", "Beratungspaket S", 250.00),
            ("P-1002", "Beratungspaket M", 500.00),
            ("P-1003", "Beratungspaket L", 900.00),
            ("P-2001", "Software-Lizenz Basic", 120.00),
            ("P-2002", "Software-Lizenz Pro", 290.00),
            ("P-3001", "Supportvertrag", 75.00),
        ]
        for sku, name, price in products_data:
            p = Product(sku=sku, name=name, price=price)
            db.session.add(p)
        db.session.commit()
        print(f"{len(products_data)} Produkte angelegt.")
    else:
        print("Produkte existieren bereits.")

    # Kunden anlegen (>=10)
    if Customer.query.count() == 0:
        customers_data = [
            ("Acme GmbH", "Max Mustermann", "max@acme.example", "+43 1 234567"),
            ("Blue Widgets OG", "Anna Blau", "anna@blue.example", "+43 699 111"),
            ("Green Solutions KG", "Lisa Grün", "lisa@green.example", "+43 1 555555"),
            ("Red Tech AG", "Peter Rot", "peter@red.example", "+43 1 999999"),
            ("Sunrise Consulting", "Johannes Licht", "johannes@sunrise.example", "+43 660 1111111"),
            ("Nordwind GmbH", "Sophie Nord", "sophie@nordwind.example", "+43 670 2222222"),
            ("Alpen IT", "Markus Berg", "markus@alpenit.example", "+43 699 3333333"),
            ("City Logistics", "Julia Stadt", "julia@citylog.example", "+43 1 7777777"),
            ("Future Media", "Nina Neu", "nina@futuremedia.example", "+43 1 8888888"),
            ("Kaffeehaus Huber", "Thomas Huber", "thomas@kaffeehuber.example", "+43 1 1231234"),
            ("Müller & Partner", "Sabine Müller", "sabine@muellerpartner.example", "+43 1 4321432"),
        ]
        for company, contact_name, email, phone in customers_data:
            c = Customer(
                company=company,
                contact_name=contact_name,
                email=email,
                phone=phone,
                city="Wien",
            )
            db.session.add(c)
        db.session.commit()
        print(f"{len(customers_data)} Kunden angelegt.")
    else:
        print("Kunden existieren bereits.")

    products = Product.query.all()
    customers = Customer.query.all()

    # Hilfsfunktion: zufälliges Datum in den letzten 3 Jahren
    def random_date_within_last_years(years: int = 3):
        now = datetime.utcnow()
        days_back = random.randint(0, 365 * years)
        return now - timedelta(days=days_back)

    # Bestellungen erzeugen (>=50 global)
    orders_count_before = Order.query.count()
    if orders_count_before < 50:
        print("Erzeuge Bestellungen ...")
        for customer in customers:
            # pro Kunde 3–8 Bestellungen
            for _ in range(random.randint(3, 8)):
                order_date = random_date_within_last_years()
                order_number = f"O-{customer.id}-{random.randint(10000, 99999)}"

                order = Order(
                    customer=customer,
                    order_number=order_number,
                    order_date=order_date,
                    status=random.choice(["offen", "bezahlt", "storniert"]),
                    currency="EUR",
                )
                db.session.add(order)
                db.session.flush()  # damit order.id vorhanden ist

                # Order-Items: 1–4 Positionen
                positions = random.randint(1, 4)
                total = 0
                for _ in range(positions):
                    product = random.choice(products)
                    qty = random.randint(1, 5)
                    unit_price = product.price
                    subtotal = qty * float(unit_price)
                    item = OrderItem(
                        order_id=order.id,
                        product_id=product.id,
                        quantity=qty,
                        unit_price=unit_price,
                        subtotal=subtotal,
                    )
                    total += subtotal
                    db.session.add(item)

                order.total_amount = total

        db.session.commit()
        print(f"Bestellungen jetzt gesamt: {Order.query.count()}")
    else:
        print(f"Es existieren bereits {orders_count_before} Bestellungen – kein Seeding nötig.")

    # Kontakte erzeugen (>=50 global)
    contacts_count_before = Contact.query.count()
    if contacts_count_before < 50:
        print("Erzeuge Kontakte ...")
        channels = ["phone", "email", "meeting", "chat"]
        subjects = [
            "Anfrage Angebot",
            "Rückruf erbeten",
            "Status Projekt",
            "Supportanfrage",
            "Jahresgespräch",
        ]

        for customer in customers:
            # pro Kunde 3–8 Kontakte
            for _ in range(random.randint(3, 8)):
                contact_date = random_date_within_last_years()
                channel = random.choice(channels)
                subject = random.choice(subjects)

                contact = Contact(
                    customer=customer,
                    user=user,
                    channel=channel,
                    subject=subject,
                    notes="Kurzer Beispielkontakt für Demodaten.",
                    contact_at=contact_date,
                )
                db.session.add(contact)

        db.session.commit()
        print(f"Kontakte jetzt gesamt: {Contact.query.count()}")
    else:
        print(f"Es existieren bereits {contacts_count_before} Kontakte – kein Seeding nötig.")

    print("Seeding abgeschlossen.")

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True, host="0.0.0.0", port=5000)
