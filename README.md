# Mini-CRM (Flask + MySQL/PostgreSQL)

Ein vollständiges CRM-System basierend auf Flask, SQLAlchemy, MySQL/PostgreSQL und TailwindCSS.
Dieses Projekt implementiert alle Muss-Kriterien der Aufgabenstellung und große Teile der Soll-Kriterien.

---

# 📦 Features

## ✅ Muss-Kriterien
- Dashboard mit drei Bereichen:
  - **Kunden** (Suche)
  - **Bestellungen** (global, chronologisch ↓, Suche)
  - **Kontakte** (global, chronologisch ↓, Filter nach Art)
- Kunden-Detailansicht:
  - Umsatz gesamt
  - Umsatz letztes Jahr
  - Datumsbereich-Filter
  - Letzte Bestellungen
  - Letzte Kontakte
- Alembic-Migrationen
- Seeder: 10+ Kunden, 50+ Bestellungen, 50+ Kontakte
- Moderne, responsive UI (Tailwind)
- Zwei-Faktor-Login per OTP

## ⭐ Soll-Kriterien
- Pagination überall
- Robuste Filter-/Suchparameter
- Authentifizierung & Kontakte mit user_id
- AT/DE Formatierung

---

# 📁 Projektstruktur

```
crm/
 ├── app.py
 ├── models.py
 ├── templates/
 │     ├── base.html
 │     ├── dashboard.html
 │     ├── customers.html
 │     ├── customer_detail.html
 │     ├── customer_form.html
 │     ├── orders.html
 │     ├── index.html
 │     ├── login.html
 │     ├── register.html
 │     ├── verify.html
 │     └── contacts.html
 ├── migrations/
 ├── .gitignore
 ├── README.md
 └── requirements.txt
```

---

# 🗄️ ER-Modell

- **customers (1) — (n) orders**
- **orders (1) — (n) order_items (n) — (1) products**
- **customers (1) — (n) contacts**
- **users (1) — (n) contacts**

---

# ⚙️ Installation (Lokales Setup)

## 1. Projekt klonen

```bash
git clone https://github.com/shzded/INFI_mini_crm
cd crm
```

## 2. Virtuelle Umgebung erstellen

```bash
python3 -m venv venv
source venv/bin/activate
```

## 3. Abhängigkeiten installieren

```bash
pip install -r requirements.txt
```

## 4. Umgebungsvariablen erstellen

```
DATABASE_URL=mysql+pymysql://nbodner:jethyf-vatka4-Dojzod@nbodner.mysql.pythonanywhere-services.com/nbodner$crm
SECRET_KEY=irgendein_geheimer_schlüssel
TZ=Europe/Vienna
```

## 5. Migrationen ausführen

```bash
flask --app app.py db init
flask --app app.py db migrate -m "initial schema"
flask --app app.py db upgrade
```

## 6. Seeder ausführen

```bash
flask --app app.py seed
```

## 7. App starten

```bash
flask --app app.py run
```

---

# ☁️ Deployment Anleitung (PythonAnywhere)

### 1. Dateien hochladen oder Git Clone

### 2. Virtualenv erstellen

```bash
python3.10 -m venv ~/crm-venv
source ~/crm-venv/bin/activate
pip install -r ~/crm/requirements.txt
```

### 3. WSGI konfigurieren

```
import sys
path = '/home/USER/crm'
if path not in sys.path:
    sys.path.append(path)

from app import app as application
```

### 4. Datenbank konfigurieren

```python
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
```

### 5. Migrationen anwenden

```bash
flask --app app.py db upgrade
```

### 6. Seeder einspielen

```bash
flask --app app.py seed
```

### 7. Web Interface → Reload

---

# 🔐 Login & Sicherheit

- Login mit E-Mail + Passwort
- Zwei-Faktor-Code per Nachricht im Server Log
- OTP gültig 5 min
- Passwörter gehasht
- LoginManager von Flask-Login schützt alle geschützten Views

---

# Anleitung für Zwei-Faktor-Code Verifizierung
- 5-stelligen Code anfragen
- In PythonAnywhere im Web Ansicht, die Server Konsole öffnen
- Eine Weile warten und dann die Server Konsole neu laden
- Code kopieren und in der Webseite eingeben

---

# 📊 Kunden-KPIs

Berechnet werden:

- Umsatz gesamt
- Umsatz letztes Jahr
- Umsatz im frei wählbaren Zeitraum

API:

```
/customers/<id>/revenue?from=YYYY-MM-DD&to=YYYY-MM-DD
```

---

# 📘 Route Übersicht

| Route | Beschreibung |
|-------|--------------|
| `/` | Dashboard |
| `/customers` | Kundenliste |
| `/customers/<id>` | Detailansicht |
| `/orders` | Globale Bestellungen |
| `/contacts` | Globale Kontakte |
| `/login` | Login |
| `/verify` | 2FA |
| `/logout` | Logout |

---

# 📈 Pagination

Verfügbar für:

- Kunden
- Bestellungen
- Kontakte

Parameter:

```
?page=2
```

---

# 👤 Beispiel Login (aus Seeder)

```
admin@example.com
Passwort: admin123
```

---

# 📸 Screenshots (für Abgabe)

> Bitte folgende Screenshots einfügen:
- Dashboard
- Kundenliste
- Kunden-Detail
- Bestellungen
- Kontakte
- Login + Verify

---

# 📝 Präsentation

Eine Präsentation sollte enthalten:

1. Titel & Technologies
2. ER-Modell
3. Screenshots
4. KPI-Berechnung
5. Migrationen & Seeder
6. Deployment Schritte
7. Fazit

---

# ✔️ Bewertungscheckliste

| Kriterium | Erfüllt |
|----------|---------|
| Datenbankdesign | ✔️ |
| Muss-Kriterien | ✔️ |
| UI/UX | ✔️ |
| Migrationen | ✔️ |
| Dokumentation | ✔️ |
| Präsentation | ✔️ |

---


