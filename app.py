from flask import Flask, render_template, request, redirect, send_from_directory
from datetime import date, timedelta
import sqlite3
import os
import uuid
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = "uploads"
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg"}

def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )
    
# Database connection
def get_db_connection():
    conn = sqlite3.connect("complitrack.db")
    conn.row_factory = sqlite3.Row
    return conn


# Create tasks table
def create_table():
    conn = get_db_connection()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
           task_id INTEGER,
            filename TEXT NOT NULL,
            filepath TEXT NOT NULL,
            upload_date TEXT,
            FOREIGN KEY (task_id) REFERENCES tasks(id)
        )
    """)

    conn.commit()
    conn.close()


# Dashboard
@app.route("/")
def home():
    conn = get_db_connection()

    tasks = conn.execute(
        "SELECT * FROM tasks ORDER BY due_date"
    ).fetchall()

    total_tasks = len(tasks)

    pending_tasks = conn.execute(
        "SELECT COUNT(*) FROM tasks WHERE status = 'Pending'"
    ).fetchone()[0]

    completed_tasks = conn.execute(
        "SELECT COUNT(*) FROM tasks WHERE status = 'Completed'"
    ).fetchone()[0]
    
    documents = conn.execute("""
    SELECT documents.*, tasks.title AS task_title
    FROM documents
    LEFT JOIN tasks
    ON documents.task_id = tasks.id
""").fetchall()

    conn.close()

    today = date.today().isoformat()
    
    seven_days_later = (date.today() + timedelta(days=7)).isoformat()

    overdue_tasks = [
        task for task in tasks
        if task["status"] == "Pending" and task["due_date"] < today
    ]

    due_soon_tasks = [
        task for task in tasks
        if task["status"] == "Pending"
        and today <= task["due_date"] <= seven_days_later
    ]

    upcoming_tasks = [
        task for task in tasks
        if task["status"] == "Pending"
        and task["due_date"] > seven_days_later
    ]
    
    return render_template(
        "index.html",
        tasks=tasks,
        documents=documents,
        total_tasks=total_tasks,
        pending_tasks=pending_tasks,
        completed_tasks=completed_tasks,
        today=today,
        seven_days_later=seven_days_later,
        overdue_tasks=overdue_tasks,
        due_soon_tasks=due_soon_tasks,
        upcoming_tasks=upcoming_tasks
    )
    
    


# Add a new task
@app.route("/add-task", methods=["POST"])
def add_task():
    title = request.form["title"].strip()
    due_date = request.form["due_date"]

    if not title or not due_date:
        return "Task name and due date are required.", 400

    conn = get_db_connection()

    conn.execute(
        "INSERT INTO tasks (title, due_date) VALUES (?, ?)",
        (title, due_date)
    )

    conn.commit()
    conn.close()

    return redirect("/")




# Update task status
@app.route("/update-status/<int:task_id>", methods=["POST"])
def update_status(task_id):
    conn = get_db_connection()

    conn.execute("""
        UPDATE tasks
        SET status = CASE
            WHEN status = 'Pending' THEN 'Completed'
            ELSE 'Pending'
        END
        WHERE id = ?
    """, (task_id,))

    conn.commit()
    conn.close()

    return redirect("/")

# Delete task
@app.route("/delete-task/<int:task_id>", methods=["POST"])
def delete_task(task_id):
    conn = get_db_connection()

    conn.execute(
        "DELETE FROM tasks WHERE id = ?",
        (task_id,)
    )

    conn.commit()
    conn.close()

    return redirect("/")

# Download document
@app.route("/download-document/<int:document_id>")
def download_document(document_id):
    conn = get_db_connection()

    document = conn.execute(
        "SELECT * FROM documents WHERE id = ?", (document_id,)
    ).fetchone()

    conn.close()

    if not document:
        return "Document not found.", 404

    return send_from_directory(
        app.config["UPLOAD_FOLDER"],
        os.path.basename(document["filepath"]),
        as_attachment=True,
        download_name=document["filename"]
    )
# Delete document
@app.route("/delete-document/<int:document_id>", methods=["POST"])
def delete_document(document_id):
    conn = get_db_connection()

    document = conn.execute(
        "SELECT * FROM documents WHERE id = ?", (document_id,)
    ).fetchone()

    if not document:
        conn.close()
        return "Document not found.", 404

    filepath = document["filepath"]

    conn.execute(
        "DELETE FROM documents WHERE id = ?", (document_id,)
    )

    conn.commit()
    conn.close()

    if os.path.exists(filepath):
        os.remove(filepath)

    return redirect("/")
    
# Upload document
@app.route("/upload-document", methods=["POST"])
def upload_document():
    file = request.files.get("document")
    task_id = request.form.get("task_id")

    if not file or file.filename == "":
        return "Please select a file.", 400

    if not allowed_file(file.filename):
        return "Only PDF, PNG, JPG and JPEG files are allowed.", 400

    conn = get_db_connection()

    task = conn.execute(
        "SELECT id FROM tasks WHERE id = ?", (task_id,)
    ).fetchone()

    if not task:
        conn.close()
        return "Invalid task selected.", 400

    original_filename = secure_filename(file.filename)

    unique_filename = str(uuid.uuid4()) + "_" + original_filename

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    filepath = os.path.join(app.config["UPLOAD_FOLDER"], unique_filename)
    file.save(filepath)

    conn.execute(
        """INSERT INTO documents (task_id, filename, filepath, upload_date)
           VALUES (?, ?, ?, ?)""",
        (task_id, original_filename, filepath, date.today().isoformat())
    )

    conn.commit()
    conn.close()

    return redirect("/")


if __name__ == "__main__":
    create_table()
    app.run(debug=True)