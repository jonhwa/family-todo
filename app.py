import os
import sqlite3
import time
from flask import Flask, g, jsonify, request, render_template

app = Flask(__name__)
DATABASE = os.environ.get("DATABASE_PATH", "todo.db")


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DATABASE)
    db.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            text     TEXT    NOT NULL,
            done     INTEGER NOT NULL DEFAULT 0,
            deadline TEXT    DEFAULT NULL,
            created  INTEGER NOT NULL,
            updated  INTEGER NOT NULL
        )
    """)
    db.commit()

    # Migrate existing table: add deadline column if missing
    cols = [row[1] for row in db.execute("PRAGMA table_info(items)").fetchall()]
    if "deadline" not in cols:
        db.execute("ALTER TABLE items ADD COLUMN deadline TEXT DEFAULT NULL")
        db.commit()

    # Pre-populate if empty
    count = db.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    if count == 0:
        now = int(time.time())
        seeds = ["Dry cleaning", "Drop off charity", "Buy Maya's food", "Buy goldfish"]
        for text in seeds:
            db.execute(
                "INSERT INTO items (text, done, deadline, created, updated) VALUES (?, 0, NULL, ?, ?)",
                (text, now, now),
            )
        db.commit()
    db.close()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/items", methods=["GET"])
def list_items():
    db = get_db()
    rows = db.execute("SELECT * FROM items ORDER BY done ASC, created DESC").fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/items", methods=["POST"])
def add_item():
    data = request.get_json(force=True)
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "text required"}), 400
    deadline = (data.get("deadline") or "").strip() or None
    # Validate ISO date format YYYY-MM-DD if provided
    if deadline:
        import re
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", deadline):
            return jsonify({"error": "deadline must be YYYY-MM-DD"}), 400
    now = int(time.time())
    db = get_db()
    cur = db.execute(
        "INSERT INTO items (text, done, deadline, created, updated) VALUES (?, 0, ?, ?, ?)",
        (text, deadline, now, now),
    )
    db.commit()
    row = db.execute("SELECT * FROM items WHERE id = ?", (cur.lastrowid,)).fetchone()
    return jsonify(dict(row)), 201


@app.route("/api/items/<int:item_id>", methods=["PATCH"])
def update_item(item_id):
    data = request.get_json(force=True)
    now = int(time.time())
    db = get_db()
    row = db.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    if row is None:
        return jsonify({"error": "not found"}), 404
    done = data.get("done", row["done"])
    text = data.get("text", row["text"])
    # Allow explicitly clearing deadline by passing null/empty string
    if "deadline" in data:
        deadline = (data["deadline"] or "").strip() or None
    else:
        deadline = row["deadline"]
    db.execute(
        "UPDATE items SET done = ?, text = ?, de