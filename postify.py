from flask import Flask, request, render_template, redirect, url_for, session, abort
import sqlite3
import uuid
import requests
import json
import os
from werkzeug.security import generate_password_hash, check_password_hash

# Load or generate a secure secret key
SECRET_KEY_FILE = "config.json"

def load_secret_key():
    """Load or generate a secure secret key for Flask session management."""
    try:
        if os.path.exists(SECRET_KEY_FILE):
            with open(SECRET_KEY_FILE, "r") as f:
                config = json.load(f)
                if "secret_key" in config:
                    return config["secret_key"]
        # Generate new secret key if missing or corrupted
        secret_key = os.urandom(24).hex()
        with open(SECRET_KEY_FILE, "w") as f:
            json.dump({"secret_key": secret_key}, f)
        return secret_key
    except Exception as e:
        print(f"Error loading secret key: {e}")
        return "fallbacksecretkey123"  # Prevent crashing if something goes wrong


app = Flask(__name__)
app.secret_key = load_secret_key()
WEBHOOK_URL = "https://discord.com/api/webhooks/1343195395085435020/x0ifLcXROAn6yYes2UQCKl8yVEyOUnYDILUquHxlzUHJDwaTIO4KBvJJCloeGxBgpkex"

def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL CHECK(LENGTH(name) < 50),
            author TEXT NOT NULL,
            content TEXT NOT NULL CHECK(LENGTH(content) < 5000)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS replies (
            id TEXT PRIMARY KEY,
            post_id TEXT NOT NULL,
            author TEXT NOT NULL,
            content TEXT NOT NULL,
            FOREIGN KEY (post_id) REFERENCES posts (id)
        )
    """)
    conn.commit()
    conn.close()

def validate_ascii(text):
    try:
        text.encode("ascii")
        return True
    except UnicodeEncodeError:
        return False

@app.route("/")
def index():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, author FROM posts")
    posts = cursor.fetchall()
    conn.close()
    return render_template("index.html", posts=posts, user=session.get("user"), title="Postify")

@app.route("/post/<post_id>")
def view_post(post_id):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, author, content FROM posts WHERE id = ?", (post_id,))
    post = cursor.fetchone()
    if not post:
        abort(404)
    cursor.execute("SELECT author, content FROM replies WHERE post_id = ?", (post_id,))
    replies = cursor.fetchall()
    conn.close()
    return render_template("post.html", post=post, replies=replies)

@app.route("/report", methods=["POST"])
def report_post():
    post_id = request.form.get("post_id")
    reason = request.form.get("reason", "No reason provided")
    
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, author, content FROM posts WHERE id = ?", (post_id,))
    post = cursor.fetchone()
    conn.close()
    
    if post:
        report_data = {
            "post_id": post[0],
            "post_name": post[1],
            "author": post[2],
            "content": post[3],
            "reason": reason
        }
        print("Sending report data:", json.dumps(report_data, indent=4))
        response = requests.post(WEBHOOK_URL, json=report_data, headers={'Content-Type': 'application/json'})
        print("Webhook response:", response.status_code, response.text)
    
    return redirect(url_for("view_post", post_id=post_id))

@app.route("/post", methods=["POST"])
def create_post():
    name = request.form.get("name")
    author = request.form.get("author")
    content = request.form.get("content")
    
    if not all([name, author, content]) or not validate_ascii(content) or len(name) >= 50 or len(content) >= 5000:
        return redirect(url_for("index"))
    
    post_id = str(uuid.uuid4())
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO posts (id, name, author, content) VALUES (?, ?, ?, ?)", (post_id, name, author, content))
    conn.commit()
    conn.close()
    
    return redirect(url_for("index"))

@app.route("/reply", methods=["POST"])
def reply_post():
    post_id = request.form.get("post_id")
    author = request.form.get("author")
    content = request.form.get("content")
    
    if not all([post_id, author, content]) or not validate_ascii(content):
        return redirect(url_for("view_post", post_id=post_id))
    
    reply_id = str(uuid.uuid4())
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO replies (id, post_id, author, content) VALUES (?, ?, ?, ?)", (reply_id, post_id, author, content))
    conn.commit()
    conn.close()
    
    return redirect(url_for("view_post", post_id=post_id))

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("index"))

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
