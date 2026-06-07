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
            created  INTEGER NOT NULL,
            updated  INTEGER NOT NULL
        )
    """)
    db.commit()

    # Pre-populate if empty
    count = db.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    if count == 0:
        now = int(time.time())
        seeds = ["Dry cleaning", "Drop off charity", "Buy Maya's food", "Buy goldfish"]
        for text in seeds:
            db.execute(
                "INSERT INTO items (text, done, created, updated) VALUES (?, 0, ?, ?)",
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
    now = int(time.time())
    db = get_db()
    cur = db.execute(
        "INSERT INTO items (text, done, created, updated) VALUES (?, 0, ?, ?)",
        (text, now, now),
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
    db.execute(
        "UPDATE items SET done = ?, text = ?, updated = ? WHERE id = ?",
        (int(done), text, now, item_id),
    )
    db.commit()
    row = db.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    return jsonify(dict(row))


@app.route("/api/items/<int:item_id>", methods=["DELETE"])
def delete_item(item_id):
    db = get_db()
    db.execute("DELETE FROM items WHERE id = ?", (item_id,))
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/poll")
def poll():
    """Return the max `updated` timestamp so clients can detect changes cheaply."""
    db = get_db()
    row = db.execute("SELECT MAX(updated) as ts, COUNT(*) as n FROM items").fetchone()
    return jsonify({"ts": row["ts"] or 0, "n": row["n"]})


if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
