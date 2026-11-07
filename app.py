"""Apartment Rental Management System.

A small web app built with Python's standard library (http.server) and SQLite.
Owners list apartments, tenants are registered, and rental agreements are
created for available apartments. Renting an apartment marks it as rented.
"""

import datetime
import os
import sqlite3
from html import escape
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("RENTAL_DB", os.path.join(BASE_DIR, "rentals.db"))
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")
STATIC_DIR = os.path.join(BASE_DIR, "static")
STATUSES = ["Available", "Rented"]


# ---------- database helpers ----------

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_connection()
    try:
        with open(SCHEMA_PATH, encoding="utf-8") as f:
            conn.executescript(f.read())
        conn.commit()
    finally:
        conn.close()


def run_query(sql, params=()):
    conn = get_connection()
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def run_write(sql, params=()):
    conn = get_connection()
    try:
        cursor = conn.execute(sql, params)
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


# ---------- validation ----------

def validate_listing(form):
    title = form.get("title", "").strip()
    city = form.get("city", "").strip()
    rent_text = form.get("rent", "").strip()
    bedrooms_text = form.get("bedrooms", "").strip()
    status = form.get("status", "Available").strip()

    if not title:
        return None, "Please enter a title for the apartment."
    if not city:
        return None, "Please enter the city."
    if not rent_text.isdigit() or int(rent_text) <= 0:
        return None, "Monthly rent must be a whole number greater than 0."
    if not bedrooms_text.isdigit() or not (1 <= int(bedrooms_text) <= 10):
        return None, "Bedrooms must be between 1 and 10."
    if status not in STATUSES:
        return None, "Please choose a valid status."

    return {
        "title": title,
        "city": city,
        "rent": int(rent_text),
        "bedrooms": int(bedrooms_text),
        "status": status,
    }, None


def validate_tenant(form):
    name = form.get("full_name", "").strip()
    phone = form.get("phone", "").strip()
    email = form.get("email", "").strip()

    if not name:
        return None, "Please enter the tenant's full name."
    if not (phone.isdigit() and len(phone) == 10):
        return None, "Phone number must be exactly 10 digits."
    if email and "@" not in email:
        return None, "Please enter a valid email address."

    return {"full_name": name, "phone": phone, "email": email}, None


def parse_date(text):
    try:
        return datetime.date.fromisoformat(text)
    except (TypeError, ValueError):
        return None


def validate_agreement(form):
    listing_id = form.get("listing_id", "").strip()
    tenant_id = form.get("tenant_id", "").strip()
    start = parse_date(form.get("start_date", "").strip())
    end = parse_date(form.get("end_date", "").strip())

    if not listing_id.isdigit():
        return None, "Please choose an apartment."
    if not tenant_id.isdigit():
        return None, "Please choose a tenant."
    if start is None or end is None:
        return None, "Please enter valid start and end dates."
    if end <= start:
        return None, "The end date must be after the start date."

    listing = run_query("SELECT * FROM listings WHERE id = ?", (int(listing_id),))
    if not listing:
        return None, "That apartment does not exist."
    if listing[0]["status"] != "Available":
        return None, "That apartment is already rented."
    if not run_query("SELECT id FROM tenants WHERE id = ?", (int(tenant_id),)):
        return None, "That tenant does not exist."

    return {
        "listing_id": int(listing_id),
        "tenant_id": int(tenant_id),
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "monthly_rent": listing[0]["rent"],
    }, None


# ---------- HTML helpers ----------

NAV_LINKS = [
    ("/", "Home"),
    ("/listings", "Apartments"),
    ("/tenants", "Tenants"),
    ("/agreements", "Agreements"),
    ("/search", "Search"),
]


def page(title, content):
    nav = "".join(f'<a href="{href}">{label}</a>' for href, label in NAV_LINKS)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)} - Apartment Rental</title>
  <link rel="stylesheet" href="/static/style.css">
</head>
<body>
  <header>
    <h1>Apartment Rental Management</h1>
    <nav>{nav}</nav>
  </header>
  <main>
    <h2>{escape(title)}</h2>
    {content}
  </main>
</body>
</html>"""


def error_box(message):
    return f'<p class="error">{escape(message)}</p>' if message else ""


def status_options(selected):
    return "".join(
        f'<option value="{s}"{" selected" if s == selected else ""}>{s}</option>' for s in STATUSES
    )


def listing_options(selected=""):
    rows = run_query("SELECT id, title, city, rent FROM listings WHERE status = 'Available' ORDER BY title")
    options = ['<option value="">Select an apartment</option>']
    for r in rows:
        marker = " selected" if str(r["id"]) == str(selected) else ""
        options.append(
            f'<option value="{r["id"]}"{marker}>{escape(r["title"])} - {escape(r["city"])} (Rs. {r["rent"]})</option>'
        )
    return "".join(options)


def tenant_options(selected=""):
    rows = run_query("SELECT id, full_name FROM tenants ORDER BY full_name")
    options = ['<option value="">Select a tenant</option>']
    for r in rows:
        marker = " selected" if str(r["id"]) == str(selected) else ""
        options.append(f'<option value="{r["id"]}"{marker}>{escape(r["full_name"])}</option>')
    return "".join(options)


# ---------- page builders ----------

def home_page():
    return page("Home", """
    <p>Manage apartment listings, tenants and rental agreements in one place.</p>
    <ul>
      <li><a href="/listings/new">Add an apartment</a></li>
      <li><a href="/tenants/new">Register a tenant</a></li>
      <li><a href="/agreements/new">Create a rental agreement</a></li>
      <li><a href="/search">Search available apartments</a></li>
    </ul>
    """)


def listing_form(values=None, error="", editing=False):
    values = values or {}
    action = "/listings/update" if editing else "/listings/new"
    title = "Edit apartment" if editing else "Add an apartment"
    hidden = f'<input type="hidden" name="id" value="{escape(str(values.get("id", "")))}">' if editing else ""
    status_field = ""
    if editing:
        status_field = f"""
      <label>Status
        <select name="status">{status_options(values.get('status', 'Available'))}</select>
      </label>"""
    content = f"""
    {error_box(error)}
    <form method="post" action="{action}" class="form">
      {hidden}
      <label>Title
        <input type="text" name="title" value="{escape(str(values.get('title', '')))}" required>
      </label>
      <label>City
        <input type="text" name="city" value="{escape(str(values.get('city', '')))}" required>
      </label>
      <label>Monthly rent (Rs.)
        <input type="number" name="rent" min="1" value="{escape(str(values.get('rent', '')))}" required>
      </label>
      <label>Bedrooms
        <input type="number" name="bedrooms" min="1" max="10" value="{escape(str(values.get('bedrooms', '')))}" required>
      </label>
      {status_field}
      <button type="submit">Save apartment</button>
    </form>
    <p><a href="/listings">Back to apartments</a></p>
    """
    return page(title, content)


def listings_page():
    rows = run_query("SELECT * FROM listings ORDER BY id DESC")
    if not rows:
        table = "<p>No apartments added yet.</p>"
    else:
        lines = ['<table><thead><tr><th>Title</th><th>City</th><th>Rent (Rs.)</th>'
                 '<th>Bedrooms</th><th>Status</th><th></th></tr></thead><tbody>']
        for r in rows:
            lines.append(
                f"<tr><td>{escape(r['title'])}</td><td>{escape(r['city'])}</td>"
                f"<td>{r['rent']}</td><td>{r['bedrooms']}</td><td>{r['status']}</td>"
                f'<td><a href="/listings/edit?id={r["id"]}">Edit</a></td></tr>'
            )
        lines.append("</tbody></table>")
        table = "".join(lines)
    return page("Apartments", f'<p><a href="/listings/new">Add an apartment</a></p>{table}')


def tenant_form(values=None, error=""):
    values = values or {}
    content = f"""
    {error_box(error)}
    <form method="post" action="/tenants/new" class="form">
      <label>Full name
        <input type="text" name="full_name" value="{escape(values.get('full_name', ''))}" required>
      </label>
      <label>Phone (10 digits)
        <input type="tel" name="phone" pattern="[0-9]{{10}}" value="{escape(values.get('phone', ''))}" required>
      </label>
      <label>Email (optional)
        <input type="email" name="email" value="{escape(values.get('email', ''))}">
      </label>
      <button type="submit">Register tenant</button>
    </form>
    """
    return page("Register a tenant", content)


def tenants_page():
    rows = run_query("SELECT full_name, phone, email FROM tenants ORDER BY id DESC")
    if not rows:
        table = "<p>No tenants registered yet.</p>"
    else:
        lines = ['<table><thead><tr><th>Name</th><th>Phone</th><th>Email</th></tr></thead><tbody>']
        for r in rows:
            lines.append(
                f"<tr><td>{escape(r['full_name'])}</td><td>{escape(r['phone'])}</td>"
                f"<td>{escape(r['email'] or '')}</td></tr>"
            )
        lines.append("</tbody></table>")
        table = "".join(lines)
    return page("Tenants", f'<p><a href="/tenants/new">Register a tenant</a></p>{table}')


def agreement_form(values=None, error=""):
    values = values or {}
    content = f"""
    {error_box(error)}
    <form method="post" action="/agreements/new" class="form">
      <label>Apartment
        <select name="listing_id" required>{listing_options(values.get('listing_id', ''))}</select>
      </label>
      <label>Tenant
        <select name="tenant_id" required>{tenant_options(values.get('tenant_id', ''))}</select>
      </label>
      <label>Start date
        <input type="date" name="start_date" value="{escape(values.get('start_date', ''))}" required>
      </label>
      <label>End date
        <input type="date" name="end_date" value="{escape(values.get('end_date', ''))}" required>
      </label>
      <button type="submit">Create agreement</button>
    </form>
    """
    return page("Create a rental agreement", content)


def agreements_page():
    rows = run_query(
        """
        SELECT a.id, l.title, l.city, t.full_name, a.start_date, a.end_date, a.monthly_rent
        FROM agreements a
        JOIN listings l ON l.id = a.listing_id
        JOIN tenants t ON t.id = a.tenant_id
        ORDER BY a.id DESC
        """
    )
    if not rows:
        table = "<p>No rental agreements yet.</p>"
    else:
        lines = ['<table><thead><tr><th>Apartment</th><th>City</th><th>Tenant</th>'
                 '<th>Start</th><th>End</th><th>Rent (Rs.)</th></tr></thead><tbody>']
        for r in rows:
            lines.append(
                f"<tr><td>{escape(r['title'])}</td><td>{escape(r['city'])}</td>"
                f"<td>{escape(r['full_name'])}</td><td>{r['start_date']}</td>"
                f"<td>{r['end_date']}</td><td>{r['monthly_rent']}</td></tr>"
            )
        lines.append("</tbody></table>")
        table = "".join(lines)
    return page("Rental agreements", f'<p><a href="/agreements/new">Create an agreement</a></p>{table}')


def search_page(city="", max_rent=""):
    form = f"""
    <form method="get" action="/search" class="form">
      <label>City
        <input type="text" name="city" value="{escape(city)}">
      </label>
      <label>Maximum rent (Rs.)
        <input type="number" name="max_rent" min="1" value="{escape(max_rent)}">
      </label>
      <button type="submit">Search</button>
    </form>
    """
    results = ""
    if city or max_rent:
        sql = "SELECT * FROM listings WHERE status = 'Available'"
        params = []
        if city:
            sql += " AND city = ?"
            params.append(city)
        if max_rent.isdigit():
            sql += " AND rent <= ?"
            params.append(int(max_rent))
        sql += " ORDER BY rent"
        rows = run_query(sql, params)
        if not rows:
            results = "<p>No available apartments match your search.</p>"
        else:
            lines = ['<table><thead><tr><th>Title</th><th>City</th><th>Rent (Rs.)</th>'
                     '<th>Bedrooms</th></tr></thead><tbody>']
            for r in rows:
                lines.append(
                    f"<tr><td>{escape(r['title'])}</td><td>{escape(r['city'])}</td>"
                    f"<td>{r['rent']}</td><td>{r['bedrooms']}</td></tr>"
                )
            lines.append("</tbody></table>")
            results = "".join(lines)
    return page("Search apartments", form + results)


# ---------- HTTP handler ----------

class RentalHandler(BaseHTTPRequestHandler):
    def send_html(self, body, status=200):
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def redirect(self, location):
        self.send_response(303)
        self.send_header("Location", location)
        self.end_headers()

    def serve_static(self, path):
        relative = path[len("/static/"):]
        full_path = os.path.normpath(os.path.join(STATIC_DIR, relative))
        if not full_path.startswith(STATIC_DIR + os.sep) or not os.path.isfile(full_path):
            self.send_html(page("Not found", "<p>File not found.</p>"), status=404)
            return
        content_type = "text/css" if full_path.endswith(".css") else "application/octet-stream"
        with open(full_path, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def read_form(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8")
        parsed = parse_qs(body, keep_blank_values=True)
        return {key: values[0] for key, values in parsed.items()}

    def do_GET(self):
        url = urlparse(self.path)
        path = url.path
        query = {key: values[0] for key, values in parse_qs(url.query).items()}

        if path.startswith("/static/"):
            self.serve_static(path)
        elif path == "/":
            self.send_html(home_page())
        elif path == "/listings":
            self.send_html(listings_page())
        elif path == "/listings/new":
            self.send_html(listing_form())
        elif path == "/listings/edit":
            rows = run_query("SELECT * FROM listings WHERE id = ?", (query.get("id", ""),)) if query.get("id", "").isdigit() else []
            if rows:
                self.send_html(listing_form(values=dict(rows[0]), editing=True))
            else:
                self.send_html(page("Not found", "<p>Apartment not found.</p>"), status=404)
        elif path == "/tenants":
            self.send_html(tenants_page())
        elif path == "/tenants/new":
            self.send_html(tenant_form())
        elif path == "/agreements":
            self.send_html(agreements_page())
        elif path == "/agreements/new":
            self.send_html(agreement_form())
        elif path == "/search":
            self.send_html(search_page(query.get("city", "").strip(), query.get("max_rent", "").strip()))
        else:
            self.send_html(page("Not found", "<p>Page not found.</p>"), status=404)

    def do_POST(self):
        path = urlparse(self.path).path
        form = self.read_form()

        if path == "/listings/new":
            data, error = validate_listing(form)
            if error:
                self.send_html(listing_form(values=form, error=error), status=400)
                return
            run_write(
                "INSERT INTO listings (title, city, rent, bedrooms, status) VALUES (?, ?, ?, ?, ?)",
                (data["title"], data["city"], data["rent"], data["bedrooms"], data["status"]),
            )
            self.redirect("/listings")

        elif path == "/listings/update":
            if not form.get("id", "").isdigit():
                self.send_html(page("Not found", "<p>Apartment not found.</p>"), status=404)
                return
            data, error = validate_listing(form)
            if error:
                values = dict(form)
                values["id"] = form.get("id")
                self.send_html(listing_form(values=values, error=error, editing=True), status=400)
                return
            run_write(
                "UPDATE listings SET title = ?, city = ?, rent = ?, bedrooms = ?, status = ? WHERE id = ?",
                (data["title"], data["city"], data["rent"], data["bedrooms"], data["status"], int(form["id"])),
            )
            self.redirect("/listings")

        elif path == "/tenants/new":
            data, error = validate_tenant(form)
            if error:
                self.send_html(tenant_form(values=form, error=error), status=400)
                return
            run_write(
                "INSERT INTO tenants (full_name, phone, email) VALUES (?, ?, ?)",
                (data["full_name"], data["phone"], data["email"]),
            )
            self.redirect("/tenants")

        elif path == "/agreements/new":
            data, error = validate_agreement(form)
            if error:
                self.send_html(agreement_form(values=form, error=error), status=400)
                return
            conn = get_connection()
            try:
                conn.execute(
                    "INSERT INTO agreements (listing_id, tenant_id, start_date, end_date, monthly_rent) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (data["listing_id"], data["tenant_id"], data["start_date"], data["end_date"], data["monthly_rent"]),
                )
                conn.execute("UPDATE listings SET status = 'Rented' WHERE id = ?", (data["listing_id"],))
                conn.commit()
            finally:
                conn.close()
            self.redirect("/agreements")

        else:
            self.send_html(page("Not found", "<p>Page not found.</p>"), status=404)

    def log_message(self, format, *args):
        pass


def main():
    init_db()
    port = int(os.environ.get("PORT", "8001"))
    server = HTTPServer(("127.0.0.1", port), RentalHandler)
    print(f"Apartment Rental app running at http://127.0.0.1:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
