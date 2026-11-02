
import os
import uuid
import sqlite3

from flask import Flask, render_template, request, redirect, session
from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)
from werkzeug.utils import secure_filename
from datetime import date, timedelta

app = Flask(__name__)
app.secret_key = "student_study_secret_key"

UPLOAD_FOLDER = "static/profile_uploads"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# Database Connection
def get_database():
    return sqlite3.connect("students.db")
@app.context_processor
def inject_top_profile():
    username = session.get("username")
    picture = None

    if username:
        con = get_database()
        cur = con.cursor()

        cur.execute(
            "SELECT profile_picture FROM profiles WHERE username=?",
            (username,)
        )

        result = cur.fetchone()
        con.close()

        if result:
            picture = result[0]

    return {
        "top_profile_picture": picture,
        "top_profile_username": username
    }

# Check Image Extension
def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


# Create Database
def create_database():

    con = get_database()
    cur = con.cursor()

    # Students Table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    # Timetable Table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS timetable (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            day TEXT NOT NULL,
            subject TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL
        )
    """)

    # Assignments Table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            title TEXT NOT NULL,
            subject TEXT NOT NULL,
            due_date TEXT NOT NULL,
            priority TEXT NOT NULL,
            status TEXT DEFAULT 'Pending'
        )
    """)

    # Subjects Table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            subject_name TEXT NOT NULL,
            subject_code TEXT
        )
    """)

    # Study Records Table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS study_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            subject TEXT NOT NULL,
            study_date TEXT NOT NULL,
            duration REAL NOT NULL
        )
    """)

    # Exams Table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS exams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            exam_name TEXT NOT NULL,
            subject TEXT NOT NULL,
            exam_date TEXT NOT NULL,
            syllabus TEXT,
            preparation_progress INTEGER DEFAULT 0
        )
    """)

    # Profile Table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS profiles (
            username TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            caption TEXT,
            profile_picture TEXT
        )
    """)

    con.commit()
    con.close()


# Home Page
@app.route("/")
def home():
    return render_template("login.html")


# Registration
@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form["name"]
        email = request.form["email"]
        username = request.form["username"]
        password = request.form["password"]

        hashed_password = generate_password_hash(password)

        con = get_database()
        cur = con.cursor()

        try:
            cur.execute("""
                INSERT INTO students
                (name, email, username, password)
                VALUES (?, ?, ?, ?)
            """, (name, email, username, hashed_password))

            con.commit()
            return redirect("/")

        except sqlite3.IntegrityError:
            return "Email or Username already exists!"

        finally:
            con.close()

    return render_template("register.html")


# Login
@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        con = get_database()
        cur = con.cursor()

        cur.execute(
            "SELECT name, password FROM students WHERE username = ?",
            (username,)
        )

        result = cur.fetchone()
        con.close()

        if result and check_password_hash(result[1], password):

            session["student_name"] = result[0]
            session["username"] = username

            return redirect("/dashboard")

        return "Invalid Username or Password!"

    return render_template("login.html")


# Dashboard
@app.route("/dashboard")
def dashboard():

    if "username" not in session:
        return redirect("/")

    today_day = date.today().strftime("%A")
    today = date.today()

    con = get_database()
    cur = con.cursor()

    # Today's Timetable
    cur.execute("""
        SELECT subject, start_time, end_time
        FROM timetable
        WHERE username = ? AND day = ?
        ORDER BY start_time
    """, (session["username"], today_day))

    timetable = cur.fetchall()

    # Dashboard Assignments
    cur.execute("""
        SELECT title, due_date
        FROM assignments
        WHERE username = ?
        ORDER BY due_date
    """, (session["username"],))

    assignments = cur.fetchall()

    # Assignment Reminders
    cur.execute("""
        SELECT title, due_date, status
        FROM assignments
        WHERE username = ?
        AND status != 'Completed'
        ORDER BY due_date
    """, (session["username"],))

    pending_assignments = cur.fetchall()

    reminders = []

    for item in pending_assignments:

        try:
            due = date.fromisoformat(item[1])
            days_left = (due - today).days

            if days_left <= 3:
                reminders.append((item[0], item[1], days_left))

        except (ValueError, TypeError):
            pass

    con.close()

    return render_template(
        "dashboard.html",
        student_name=session["student_name"],
        today_date=today.strftime("%d-%m-%Y"),
        timetable=timetable,
        assignments=assignments,
        reminders=reminders
    )


# Timetable
@app.route("/timetable", methods=["GET", "POST"])
def manage_timetable():

    if "username" not in session:
        return redirect("/")

    if request.method == "POST":

        day = request.form["day"]
        subject = request.form["subject"]
        start_time = request.form["start_time"]
        end_time = request.form["end_time"]

        con = get_database()
        cur = con.cursor()

        cur.execute("""
            INSERT INTO timetable
            (username, day, subject, start_time, end_time)
            VALUES (?, ?, ?, ?, ?)
        """, (
            session["username"],
            day,
            subject,
            start_time,
            end_time
        ))

        con.commit()
        con.close()

        return redirect("/timetable")

    con = get_database()
    cur = con.cursor()

    cur.execute("""
        SELECT id, day, subject, start_time, end_time
        FROM timetable
        WHERE username = ?
        ORDER BY
            CASE day
                WHEN 'Monday' THEN 1
                WHEN 'Tuesday' THEN 2
                WHEN 'Wednesday' THEN 3
                WHEN 'Thursday' THEN 4
                WHEN 'Friday' THEN 5
                WHEN 'Saturday' THEN 6
                WHEN 'Sunday' THEN 7
            END
    """, (session["username"],))

    timetable = cur.fetchall()
    con.close()

    return render_template("timetable.html", timetable=timetable)


# Edit Timetable
@app.route("/edit_timetable/<int:id>", methods=["GET", "POST"])
def edit_timetable(id):

    if "username" not in session:
        return redirect("/")

    con = get_database()
    cur = con.cursor()

    if request.method == "POST":

        day = request.form["day"]
        subject = request.form["subject"]
        start_time = request.form["start_time"]
        end_time = request.form["end_time"]

        cur.execute("""
            UPDATE timetable
            SET day=?, subject=?, start_time=?, end_time=?
            WHERE id=? AND username=?
        """, (
            day, subject, start_time, end_time,
            id, session["username"]
        ))

        con.commit()
        con.close()

        return redirect("/timetable")

    cur.execute("""
        SELECT *
        FROM timetable
        WHERE id=? AND username=?
    """, (id, session["username"]))

    item = cur.fetchone()
    con.close()

    if item is None:
        return redirect("/timetable")

    return render_template("edit_timetable.html", item=item)


# Delete Timetable
@app.route("/delete_timetable/<int:id>", methods=["POST"])
def delete_timetable(id):

    if "username" not in session:
        return redirect("/")

    con = get_database()
    cur = con.cursor()

    cur.execute("""
        DELETE FROM timetable
        WHERE id=? AND username=?
    """, (id, session["username"]))

    con.commit()
    con.close()

    return redirect("/timetable")


# Assignments
@app.route("/assignments", methods=["GET", "POST"])
def manage_assignments():

    if "username" not in session:
        return redirect("/")

    if request.method == "POST":

        title = request.form["title"]
        subject = request.form["subject"]
        due_date = request.form["due_date"]
        priority = request.form["priority"]

        con = get_database()
        cur = con.cursor()

        cur.execute("""
            INSERT INTO assignments
            (username, title, subject, due_date, priority)
            VALUES (?, ?, ?, ?, ?)
        """, (
            session["username"],
            title,
            subject,
            due_date,
            priority
        ))

        con.commit()
        con.close()

        return redirect("/assignments")

    con = get_database()
    cur = con.cursor()

    cur.execute("""
        SELECT id, title, subject, due_date, priority, status
        FROM assignments
        WHERE username = ?
        ORDER BY due_date
    """, (session["username"],))

    assignments = cur.fetchall()
    con.close()

    return render_template(
        "assignments.html",
        assignments=assignments
    )


# Edit Assignment
@app.route("/edit_assignment/<int:id>", methods=["GET", "POST"])
def edit_assignment(id):

    if "username" not in session:
        return redirect("/")

    con = get_database()
    cur = con.cursor()

    if request.method == "POST":

        title = request.form["title"]
        subject = request.form["subject"]
        due_date = request.form["due_date"]
        priority = request.form["priority"]

        cur.execute("""
            UPDATE assignments
            SET title=?, subject=?, due_date=?, priority=?
            WHERE id=? AND username=?
        """, (
            title, subject, due_date, priority,
            id, session["username"]
        ))

        con.commit()
        con.close()

        return redirect("/assignments")

    cur.execute("""
        SELECT *
        FROM assignments
        WHERE id=? AND username=?
    """, (id, session["username"]))

    item = cur.fetchone()
    con.close()

    if item is None:
        return redirect("/assignments")

    return render_template("edit_assignment.html", item=item)


# Delete Assignment
@app.route("/delete_assignment/<int:id>", methods=["POST"])
def delete_assignment(id):

    if "username" not in session:
        return redirect("/")

    con = get_database()
    cur = con.cursor()

    cur.execute("""
        DELETE FROM assignments
        WHERE id=? AND username=?
    """, (id, session["username"]))

    con.commit()
    con.close()

    return redirect("/assignments")


# Complete Assignment
@app.route("/complete_assignment/<int:id>", methods=["POST"])
def complete_assignment(id):

    if "username" not in session:
        return redirect("/")

    con = get_database()
    cur = con.cursor()

    cur.execute("""
        UPDATE assignments
        SET status = 'Completed'
        WHERE id=? AND username=?
    """, (id, session["username"]))

    con.commit()
    con.close()

    return redirect("/assignments")


# Subjects Page
@app.route("/subjects", methods=["GET", "POST"])
def subjects():

    if "username" not in session:
        return redirect("/")

    con = get_database()
    cur = con.cursor()

    if request.method == "POST":

        subject_name = request.form["subject_name"]
        subject_code = request.form.get("subject_code", "")

        cur.execute("""
            INSERT INTO subjects
            (username, subject_name, subject_code)
            VALUES (?, ?, ?)
        """, (
            session["username"],
            subject_name,
            subject_code
        ))

        con.commit()

    cur.execute("""
        SELECT * FROM subjects
        WHERE username = ?
        ORDER BY id DESC
    """, (session["username"],))

    subject_list = cur.fetchall()
    con.close()

    return render_template(
        "subjects.html",
        subjects=subject_list
    )


# Edit Subject
@app.route("/edit_subject/<int:id>", methods=["GET", "POST"])
def edit_subject(id):

    if "username" not in session:
        return redirect("/")

    con = get_database()
    cur = con.cursor()

    if request.method == "POST":

        subject_name = request.form["subject_name"]
        subject_code = request.form.get("subject_code", "")

        cur.execute("""
            UPDATE subjects
            SET subject_name=?, subject_code=?
            WHERE id=? AND username=?
        """, (
            subject_name,
            subject_code,
            id,
            session["username"]
        ))

        con.commit()
        con.close()

        return redirect("/subjects")

    cur.execute("""
        SELECT * FROM subjects
        WHERE id=? AND username=?
    """, (id, session["username"]))

    subject = cur.fetchone()
    con.close()

    if subject is None:
        return redirect("/subjects")

    return render_template(
        "edit_subject.html",
        subject=subject
    )


# Delete Subject
@app.route("/delete_subject/<int:id>", methods=["POST"])
def delete_subject(id):

    if "username" not in session:
        return redirect("/")

    con = get_database()
    cur = con.cursor()

    cur.execute("""
        DELETE FROM subjects
        WHERE id=? AND username=?
    """, (id, session["username"]))

    con.commit()
    con.close()

    return redirect("/subjects")


# Exams Page
@app.route("/exams", methods=["GET", "POST"])
def exams():

    if "username" not in session:
        return redirect("/")

    con = get_database()
    cur = con.cursor()

    if request.method == "POST":

        exam_name = request.form["exam_name"]
        subject = request.form["subject"]
        exam_date = request.form["exam_date"]
        syllabus = request.form.get("syllabus", "")

        preparation_progress = int(
            request.form.get("preparation_progress", 0)
        )

        preparation_progress = max(
            0, min(100, preparation_progress)
        )

        cur.execute("""
            INSERT INTO exams
            (username, exam_name, subject, exam_date,
             syllabus, preparation_progress)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            session["username"],
            exam_name,
            subject,
            exam_date,
            syllabus,
            preparation_progress
        ))

        con.commit()
        con.close()

        return redirect("/exams")

    cur.execute("""
        SELECT id, exam_name, subject, exam_date,
               syllabus, preparation_progress
        FROM exams
        WHERE username = ?
        ORDER BY exam_date
    """, (session["username"],))

    exams_list = cur.fetchall()
    today = date.today()

    exam_details = []

    for exam in exams_list:
        try:
            days_left = (
                date.fromisoformat(exam[3]) - today
            ).days
        except (ValueError, TypeError):
            days_left = None

        exam_details.append((exam, days_left))

    con.close()

    return render_template(
        "exams.html",
        exams=exam_details
    )


# Edit Exam
@app.route("/edit_exam/<int:id>", methods=["GET", "POST"])
def edit_exam(id):

    if "username" not in session:
        return redirect("/")

    con = get_database()
    cur = con.cursor()

    if request.method == "POST":

        exam_name = request.form["exam_name"]
        subject = request.form["subject"]
        exam_date = request.form["exam_date"]
        syllabus = request.form.get("syllabus", "")

        preparation_progress = int(
            request.form.get("preparation_progress", 0)
        )

        preparation_progress = max(
            0, min(100, preparation_progress)
        )

        cur.execute("""
            UPDATE exams
            SET exam_name=?, subject=?, exam_date=?,
                syllabus=?, preparation_progress=?
            WHERE id=? AND username=?
        """, (
            exam_name, subject, exam_date, syllabus,
            preparation_progress, id, session["username"]
        ))

        con.commit()
        con.close()

        return redirect("/exams")

    cur.execute("""
        SELECT *
        FROM exams
        WHERE id=? AND username=?
    """, (id, session["username"]))

    exam = cur.fetchone()
    con.close()

    if exam is None:
        return redirect("/exams")

    return render_template("edit_exam.html", exam=exam)


# Delete Exam
@app.route("/delete_exam/<int:id>", methods=["POST"])
def delete_exam(id):

    if "username" not in session:
        return redirect("/")

    con = get_database()
    cur = con.cursor()

    cur.execute("""
        DELETE FROM exams
        WHERE id=? AND username=?
    """, (id, session["username"]))

    con.commit()
    con.close()

    return redirect("/exams")


# Profile Page
@app.route("/profile", methods=["GET", "POST"])
def profile():

    if "username" not in session:
        return redirect("/")

    username = session["username"]

    con = get_database()
    cur = con.cursor()

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        caption = request.form.get("caption", "").strip()

        if not name:
            con.close()
            return "Name is required!"

        # Get existing profile picture
        cur.execute("""
            SELECT profile_picture
            FROM profiles
            WHERE username = ?
        """, (username,))

        existing = cur.fetchone()
        picture_name = existing[0] if existing else None

        # Upload new profile picture if selected
        uploaded_file = request.files.get("profile_picture")

        if uploaded_file and uploaded_file.filename:

            if not allowed_file(uploaded_file.filename):
                con.close()
                return "Please upload PNG, JPG, JPEG or WEBP image."

            safe_name = secure_filename(uploaded_file.filename)
            extension = safe_name.rsplit(".", 1)[1].lower()

            new_filename = (
                username + "_" + uuid.uuid4().hex + "." + extension
            )

            uploaded_file.save(
                os.path.join(UPLOAD_FOLDER, new_filename)
            )

            # Delete previous picture
            if picture_name:
                old_path = os.path.join(
                    UPLOAD_FOLDER, picture_name
                )

                if os.path.isfile(old_path):
                    os.remove(old_path)

            picture_name = new_filename

        # Save profile details
        cur.execute("""
            INSERT INTO profiles
            (username, name, email, phone, caption, profile_picture)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(username) DO UPDATE SET
                name=excluded.name,
                email=excluded.email,
                phone=excluded.phone,
                caption=excluded.caption,
                profile_picture=excluded.profile_picture
        """, (
            username,
            name,
            email,
            phone,
            caption,
            picture_name
        ))

        # Update student name also
        cur.execute("""
            UPDATE students
            SET name = ?
            WHERE username = ?
        """, (name, username))

        con.commit()

        session["student_name"] = name

        con.close()
        return redirect("/profile")

    # Get profile details
    cur.execute("""
        SELECT name, email
        FROM students
        WHERE username = ?
    """, (username,))

    student = cur.fetchone()

    cur.execute("""
        SELECT name, email, phone, caption, profile_picture
        FROM profiles
        WHERE username = ?
    """, (username,))

    saved_profile = cur.fetchone()

    if saved_profile:
        profile_data = {
            "name": saved_profile[0],
            "email": saved_profile[1],
            "phone": saved_profile[2],
            "caption": saved_profile[3],
            "profile_picture": saved_profile[4]
        }
    else:
        profile_data = {
            "name": student[0] if student else "",
            "email": student[1] if student else "",
            "phone": "",
            "caption": "",
            "profile_picture": None
        }

    con.close()

    return render_template(
        "profile.html",
        profile=profile_data
    )


# Delete Profile Picture
@app.route("/delete_profile_picture")
def delete_profile_picture():

    if "username" not in session:
        return redirect("/")

    username = session["username"]

    con = get_database()
    cur = con.cursor()

    cur.execute("""
        SELECT profile_picture
        FROM profiles
        WHERE username = ?
    """, (username,))

    result = cur.fetchone()

    if result and result[0]:

        picture_path = os.path.join(
            UPLOAD_FOLDER, result[0]
        )

        if os.path.isfile(picture_path):
            os.remove(picture_path)

        cur.execute("""
            UPDATE profiles
            SET profile_picture = NULL
            WHERE username = ?
        """, (username,))

        con.commit()

    con.close()

    return redirect("/profile")


# Study Progress Page - Manual Entry
@app.route("/progress", methods=["GET", "POST"])
def progress():

    if "username" not in session:
        return redirect("/")

    con = get_database()
    cur = con.cursor()

    if request.method == "POST":

        subject = request.form.get("subject", "").strip()
        study_date = request.form.get("study_date", "")
        duration_text = request.form.get("duration", "")

        try:
            duration = float(duration_text)
        except (ValueError, TypeError):
            con.close()
            return redirect("/progress")

        if not subject or not study_date or duration <= 0:
            con.close()
            return redirect("/progress")

        cur.execute("""
            INSERT INTO study_records
            (username, subject, study_date, duration)
            VALUES (?, ?, ?, ?)
        """, (
            session["username"],
            subject,
            study_date,
            duration
        ))

        con.commit()

    # Get all study records
    cur.execute("""
        SELECT id, subject, study_date, duration
        FROM study_records
        WHERE username = ?
        ORDER BY study_date DESC, id DESC
    """, (session["username"],))

    records = cur.fetchall()

    # Total study hours
    cur.execute("""
        SELECT COALESCE(SUM(duration), 0)
        FROM study_records
        WHERE username = ?
    """, (session["username"],))

    total_hours = cur.fetchone()[0]

    # Weekly study hours
    today = date.today()
    week_labels = []
    week_hours = []

    for i in range(6, -1, -1):

        day = today - timedelta(days=i)
        day_name = day.strftime("%a")

        cur.execute("""
            SELECT COALESCE(SUM(duration), 0)
            FROM study_records
            WHERE username = ? AND study_date = ?
        """, (
            session["username"],
            day.isoformat()
        ))

        hours = cur.fetchone()[0]

        week_labels.append(day_name)
        week_hours.append(hours)

    # Subject-wise study hours
    cur.execute("""
        SELECT subject, SUM(duration)
        FROM study_records
        WHERE username = ?
        GROUP BY subject
        ORDER BY SUM(duration) DESC
    """, (session["username"],))

    subject_data = cur.fetchall()

    subject_labels = [item[0] for item in subject_data]
    subject_hours = [item[1] for item in subject_data]

    con.close()

    return render_template(
        "progress.html",
        records=records,
        total_hours=total_hours,
        week_labels=week_labels,
        week_hours=week_hours,
        subject_labels=subject_labels,
        subject_hours=subject_hours
    )


# Delete Study Record
@app.route("/delete_study/<int:id>", methods=["POST"])
def delete_study(id):

    if "username" not in session:
        return redirect("/")

    con = get_database()
    cur = con.cursor()

    cur.execute("""
        DELETE FROM study_records
        WHERE id = ? AND username = ?
    """, (id, session["username"]))

    con.commit()
    con.close()

    # Logout
    @app.route("/logout")
    def logout():
        session.clear()
        return redirect("/")

# Logout
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# Main Program
if __name__ == "__main__":
    create_database()
    app.run(debug=True)
