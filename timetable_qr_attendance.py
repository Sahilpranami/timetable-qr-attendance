from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import qrcode
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'secret-key'  # for sessions

DB_NAME = 'attendance.db'

# ---------- Database Setup ----------
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute('''CREATE TABLE IF NOT EXISTS faculty(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        department TEXT,
        role TEXT,
        username TEXT UNIQUE,
        password TEXT
    )''')

    cur.execute('''CREATE TABLE IF NOT EXISTS classroom(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE
    )''')

    cur.execute('''CREATE TABLE IF NOT EXISTS timetable(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        faculty_id INTEGER,
        classroom_id INTEGER,
        subject TEXT,
        day TEXT,
        time_slot TEXT,
        FOREIGN KEY(faculty_id) REFERENCES faculty(id),
        FOREIGN KEY(classroom_id) REFERENCES classroom(id)
    )''')

    cur.execute('''CREATE TABLE IF NOT EXISTS attendance(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        faculty_id INTEGER,
        classroom_id INTEGER,
        timestamp TEXT,
        status TEXT
    )''')

    conn.commit()
    conn.close()

# ---------- Utility ----------
def query_db(query, args=(), one=False):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(query, args)
    rv = cur.fetchall()
    conn.commit()
    conn.close()
    return (rv[0] if rv else None) if one else rv

# ---------- QR Code Generation ----------
def generate_qr_for_classrooms():
    os.makedirs('static/qrcodes', exist_ok=True)
    classrooms = query_db("SELECT * FROM classroom")
    for c in classrooms:
        qr_data = f"Classroom:{c[1]}"
        img = qrcode.make(qr_data)
        img.save(f"static/qrcodes/{c[1]}.png")

# ---------- Routes ----------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = query_db("SELECT * FROM faculty WHERE username=? AND password=?", (username, password), one=True)
        if user:
            session['user'] = {'id': user[0], 'name': user[1], 'role': user[3], 'dept': user[2]}
            if user[3] == 'faculty':
                return redirect(url_for('faculty_dashboard'))
            elif user[3] == 'hod':
                return redirect(url_for('hod_dashboard'))
            elif user[3] == 'dean':
                return redirect(url_for('dean_dashboard'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('index'))

# ---------- Faculty Dashboard ----------
@app.route('/faculty')
def faculty_dashboard():
    if 'user' not in session or session['user']['role'] != 'faculty':
        return redirect(url_for('login'))
    logs = query_db("SELECT * FROM attendance WHERE faculty_id=?", (session['user']['id'],))
    return render_template('faculty.html', logs=logs)

@app.route('/scan/<classroom_name>')
def scan(classroom_name):
    if 'user' not in session or session['user']['role'] != 'faculty':
        return redirect(url_for('login'))
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    classroom = query_db("SELECT * FROM classroom WHERE name=?", (classroom_name,), one=True)
    status = "Present"
    query_db("INSERT INTO attendance(faculty_id, classroom_id, timestamp, status) VALUES(?,?,?,?)", (session['user']['id'], classroom[0], now, status))
    return redirect(url_for('faculty_dashboard'))

# ---------- HOD Dashboard ----------
@app.route('/hod')
def hod_dashboard():
    if 'user' not in session or session['user']['role'] != 'hod':
        return redirect(url_for('login'))
    dept = session['user']['dept']
    logs = query_db("SELECT a.timestamp, a.status, f.name, c.name FROM attendance a JOIN faculty f ON a.faculty_id=f.id JOIN classroom c ON a.classroom_id=c.id WHERE f.department=?", (dept,))
    return render_template('hod.html', logs=logs, dept=dept)

# ---------- Dean Dashboard ----------
@app.route('/dean')
def dean_dashboard():
    if 'user' not in session or session['user']['role'] != 'dean':
        return redirect(url_for('login'))
    logs = query_db("SELECT f.department, COUNT(*) FROM attendance a JOIN faculty f ON a.faculty_id=f.id GROUP BY f.department")
    return render_template('dean.html', logs=logs)

# ---------- Seed Data ----------
@app.route('/init')
def init():
    init_db()
    query_db("INSERT OR IGNORE INTO faculty(name, department, role, username, password) VALUES('Prof. A','CSE','faculty','a','123')")
    query_db("INSERT OR IGNORE INTO faculty(name, department, role, username, password) VALUES('Prof. B','CSE','faculty','b','123')")
    query_db("INSERT OR IGNORE INTO faculty(name, department, role, username, password) VALUES('Dr. HOD','CSE','hod','hod','123')")
    query_db("INSERT OR IGNORE INTO faculty(name, department, role, username, password) VALUES('Dr. Dean','Admin','dean','dean','123')")

    query_db("INSERT OR IGNORE INTO classroom(name) VALUES('Room101')")
    query_db("INSERT OR IGNORE INTO classroom(name) VALUES('Room102')")

    generate_qr_for_classrooms()

    return "Database initialized and QR codes generated. Go to http://127.0.0.1:5000/login"

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
