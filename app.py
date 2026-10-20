from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from functools import wraps
from pathlib import Path
from flask import Flask, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("ECOMMERCE_DB", BASE_DIR / "ecommerce.db"))

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "playwright-practice-secret")
app.config["DATABASE"] = str(DB_PATH)

PRODUCTS = [
    ("Wireless Mouse", "Ergonomic wireless mouse with silent clicks.", 1299.00, "Electronics", "WM-001"),
    ("Mechanical Keyboard", "Compact mechanical keyboard with hot-swappable switches.", 3499.00, "Electronics", "KB-002"),
    ("USB-C Hub", "6-in-1 USB-C hub with HDMI and USB 3.0.", 1999.00, "Electronics", "HUB-003"),
    ("Noise Cancelling Headphones", "Over-ear headphones with active noise cancellation.", 7999.00, "Audio", "HP-004"),
    ("Webcam 1080p", "Full HD webcam with privacy shutter and dual microphones.", 2499.00, "Electronics", "WC-005"),
    ("Laptop Stand", "Aluminium adjustable stand for laptops up to 16 inches.", 1799.00, "Accessories", "LS-006"),
    ("Cotton Hoodie", "Soft everyday hoodie with a relaxed fit.", 1599.00, "Fashion", "HD-007"),
    ("Running Shoes", "Lightweight running shoes for daily training.", 4299.00, "Fashion", "RS-008"),
    ("Travel Backpack", "Water-resistant 25L backpack with laptop compartment.", 2899.00, "Accessories", "BP-009"),
    ("Stainless Steel Bottle", "750ml insulated bottle for hot and cold drinks.", 899.00, "Lifestyle", "BT-010"),
    ("Desk Lamp", "LED desk lamp with three brightness modes.", 1199.00, "Home", "DL-011"),
    ("Smart Plug", "Wi-Fi smart plug with timer and energy monitoring.", 999.00, "Home", "SP-012"),
]


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            price REAL NOT NULL,
            category TEXT NOT NULL,
            sku TEXT NOT NULL UNIQUE
        );
        CREATE TABLE IF NOT EXISTS cart_items (
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL CHECK(quantity > 0),
            PRIMARY KEY (user_id, product_id),
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            total REAL NOT NULL,
            status TEXT NOT NULL,
            payment_method TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            product_name TEXT NOT NULL,
            unit_price REAL NOT NULL,
            quantity INTEGER NOT NULL,
            FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE
        );
        """
    )
    if db.execute("SELECT COUNT(*) AS c FROM products").fetchone()["c"] == 0:
        db.executemany(
            "INSERT INTO products(name, description, price, category, sku) VALUES (?, ?, ?, ?, ?)",
            PRODUCTS,
        )
    db.commit()


def current_user():
    if "user_id" not in session:
        return None
    return get_db().execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user():
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def cart_rows(user_id):
    return get_db().execute(
        """
        SELECT p.id, p.name, p.description, p.price, p.category, p.sku, c.quantity,
               (p.price * c.quantity) AS line_total
        FROM cart_items c JOIN products p ON p.id = c.product_id
        WHERE c.user_id = ? ORDER BY p.id
        """,
        (user_id,),
    ).fetchall()


def cart_total(user_id):
    return sum(row["line_total"] for row in cart_rows(user_id))


def merge_guest_cart(user_id):
    guest = session.pop("guest_cart", {})
    if not guest:
        return
    db = get_db()
    for product_id, qty in guest.items():
        product = db.execute("SELECT id FROM products WHERE id = ?", (int(product_id),)).fetchone()
        if not product:
            continue
        existing = db.execute(
            "SELECT quantity FROM cart_items WHERE user_id = ? AND product_id = ?", (user_id, int(product_id))
        ).fetchone()
        if existing:
            db.execute(
                "UPDATE cart_items SET quantity = quantity + ? WHERE user_id = ? AND product_id = ?",
                (int(qty), user_id, int(product_id)),
            )
        else:
            db.execute(
                "INSERT INTO cart_items(user_id, product_id, quantity) VALUES (?, ?, ?)",
                (user_id, int(product_id), int(qty)),
            )
    db.commit()


@app.context_processor
def inject_globals():
    user = current_user()
    count = 0
    if user:
        count = sum(r["quantity"] for r in cart_rows(user["id"]))
    else:
        count = sum(session.get("guest_cart", {}).values())
    return {"user": user, "cart_count": count}


@app.cli.command("init-db")
def init_db_command():
    init_db()
    print("Database initialized.")


@app.route("/")
def home():
    query = request.args.get("q", "").strip()
    if query:
        products = get_db().execute(
            """SELECT * FROM products WHERE name LIKE ? OR description LIKE ? OR category LIKE ? ORDER BY name""",
            (f"%{query}%", f"%{query}%", f"%{query}%"),
        ).fetchall()
    else:
        products = get_db().execute("SELECT * FROM products ORDER BY id").fetchall()
    return render_template("home.html", products=products, query=query)


@app.route("/product/<int:product_id>")
def product_detail(product_id):
    product = get_db().execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    if not product:
        return render_template("404.html"), 404
    return render_template("product.html", product=product)


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not name or not email or not password:
            flash("Name, email and password are required.", "error")
            return render_template("signup.html")
        if len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
            return render_template("signup.html")
        db = get_db()
        try:
            cur = db.execute(
                "INSERT INTO users(name, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
                (name, email, generate_password_hash(password), datetime.utcnow().isoformat()),
            )
            db.commit()
        except sqlite3.IntegrityError:
            flash("An account with that email already exists.", "error")
            return render_template("signup.html")
        session.clear()
        session["user_id"] = cur.lastrowid
        merge_guest_cart(cur.lastrowid)
        flash("Account created successfully.", "success")
        return redirect(url_for("home"))
    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = get_db().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if not user or not check_password_hash(user["password_hash"], password):
            flash("Invalid email or password.", "error")
            return render_template("login.html")
        session.clear()
        session["user_id"] = user["id"]
        merge_guest_cart(user["id"])
        flash("Logged in successfully.", "success")
        next_url = request.args.get("next")
        return redirect(next_url if next_url and next_url.startswith("/") else url_for("home"))
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.pop("user_id", None)
    flash("You have been signed out. Your saved cart remains with your account.", "success")
    return redirect(url_for("home"))


@app.route("/cart")
def cart():
    user = current_user()
    if not user:
        # Guest cart is kept in the signed session for browser refresh/back navigation.
        items = []
        for product_id, qty in session.get("guest_cart", {}).items():
            p = get_db().execute("SELECT * FROM products WHERE id = ?", (int(product_id),)).fetchone()
            if p:
                items.append({**dict(p), "quantity": qty, "line_total": p["price"] * qty})
        total = sum(i["line_total"] for i in items)
    else:
        items = cart_rows(user["id"])
        total = cart_total(user["id"])
    return render_template("cart.html", items=items, total=total)


@app.post("/cart/add/<int:product_id>")
def add_to_cart(product_id):
    product = get_db().execute("SELECT id FROM products WHERE id = ?", (product_id,)).fetchone()
    if not product:
        return render_template("404.html"), 404
    quantity = max(1, int(request.form.get("quantity", 1)))
    user = current_user()
    if user:
        db = get_db()
        existing = db.execute("SELECT quantity FROM cart_items WHERE user_id = ? AND product_id = ?", (user["id"], product_id)).fetchone()
        if existing:
            db.execute("UPDATE cart_items SET quantity = quantity + ? WHERE user_id = ? AND product_id = ?", (quantity, user["id"], product_id))
        else:
            db.execute("INSERT INTO cart_items(user_id, product_id, quantity) VALUES (?, ?, ?)", (user["id"], product_id, quantity))
        db.commit()
    else:
        guest = session.setdefault("guest_cart", {})
        key = str(product_id)
        guest[key] = int(guest.get(key, 0)) + quantity
        session.modified = True
    flash("Product added to cart.", "success")
    return redirect(url_for("cart"))


@app.post("/cart/update/<int:product_id>")
def update_cart(product_id):
    try:
        quantity = int(request.form.get("quantity", 1))
    except ValueError:
        quantity = 1
    if quantity < 1:
        return remove_from_cart(product_id)
    user = current_user()
    if user:
        db = get_db()
        db.execute("UPDATE cart_items SET quantity = ? WHERE user_id = ? AND product_id = ?", (quantity, user["id"], product_id))
        db.commit()
    else:
        guest = session.setdefault("guest_cart", {})
        if str(product_id) in guest:
            guest[str(product_id)] = quantity
        session.modified = True
    flash("Cart quantity updated.", "success")
    return redirect(url_for("cart"))


@app.post("/cart/remove/<int:product_id>")
def remove_from_cart(product_id):
    user = current_user()
    if user:
        db = get_db()
        db.execute("DELETE FROM cart_items WHERE user_id = ? AND product_id = ?", (user["id"], product_id))
        db.commit()
    else:
        guest = session.get("guest_cart", {})
        guest.pop(str(product_id), None)
        session["guest_cart"] = guest
    flash("Product removed from cart.", "success")
    return redirect(url_for("cart"))


@app.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():
    user = current_user()
    items = cart_rows(user["id"])
    if not items:
        flash("Your cart is empty.", "warning")
        return redirect(url_for("cart"))
    if request.method == "POST":
        session["checkout"] = {"address": request.form.get("address", "").strip()}
        if not session["checkout"]["address"]:
            flash("Please enter a shipping address.", "error")
            return render_template("checkout.html", items=items, total=cart_total(user["id"]))
        return redirect(url_for("payment"))
    return render_template("checkout.html", items=items, total=cart_total(user["id"]))


@app.route("/payment", methods=["GET", "POST"])
@login_required
def payment():
    user = current_user()
    items = cart_rows(user["id"])
    if not items:
        return redirect(url_for("cart"))
    if "checkout" not in session:
        return redirect(url_for("checkout"))
    total = cart_total(user["id"])
    if request.method == "POST":
        card = request.form.get("card", "").replace(" ", "")
        if len(card) != 16 or not card.isdigit():
            flash("Enter a valid 16-digit mock card number.", "error")
            return render_template("payment.html", items=items, total=total)
        db = get_db()
        cur = db.execute(
            "INSERT INTO orders(user_id, total, status, payment_method, created_at) VALUES (?, ?, ?, ?, ?)",
            (user["id"], total, "Paid", "Mock Card", datetime.utcnow().isoformat()),
        )
        order_id = cur.lastrowid
        db.executemany(
            "INSERT INTO order_items(order_id, product_id, product_name, unit_price, quantity) VALUES (?, ?, ?, ?, ?)",
            [(order_id, r["id"], r["name"], r["price"], r["quantity"]) for r in items],
        )
        db.execute("DELETE FROM cart_items WHERE user_id = ?", (user["id"],))
        db.commit()
        session.pop("checkout", None)
        session["last_order_id"] = order_id
        return redirect(url_for("order_confirmation", order_id=order_id))
    return render_template("payment.html", items=items, total=total)


@app.route("/order-confirmation/<int:order_id>")
@login_required
def order_confirmation(order_id):
    order = get_db().execute("SELECT * FROM orders WHERE id = ? AND user_id = ?", (order_id, current_user()["id"])).fetchone()
    if not order:
        return render_template("404.html"), 404
    return render_template("confirmation.html", order=order)


@app.route("/orders")
@login_required
def orders():
    user = current_user()
    rows = get_db().execute("SELECT * FROM orders WHERE user_id = ? ORDER BY id DESC", (user["id"],)).fetchall()
    detailed = []
    for order in rows:
        items = get_db().execute("SELECT * FROM order_items WHERE order_id = ? ORDER BY id", (order["id"],)).fetchall()
        detailed.append((order, items))
    return render_template("orders.html", orders=detailed)


@app.errorhandler(404)
def not_found(_error):
    return render_template("404.html"), 404


with app.app_context():
    init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5001)), debug=True)
