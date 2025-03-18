from flask import Flask, render_template, request, redirect, url_for, session
import cv2
import sqlite3
import os
from datetime import datetime
import pandas as pd

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Required for session management

# Ensure necessary folders exist
if not os.path.exists('student_images'):
    os.makedirs('student_images')

# Database setup
def init_db():
    conn = sqlite3.connect('attendance.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, password TEXT, role TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS students
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, reg_number TEXT, year TEXT, course TEXT, face_image TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS attendance
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER, date TEXT, time TEXT)''')
    conn.commit()
    conn.close()

init_db()

# Face recognition setup
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

def capture_face(reg_number):
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Could not open camera.")
        return None

    ret, frame = cap.read()
    if not ret:
        print("Error: Could not capture frame.")
        cap.release()
        return None

    # Save the captured frame for debugging
    debug_filename = f"debug_{reg_number}.jpg"
    cv2.imwrite(debug_filename, frame)
    print(f"Debug image saved as {debug_filename}")

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.3, minNeighbors=5, minSize=(50, 50))

    if len(faces) > 0:
        (x, y, w, h) = faces[0]
        face = frame[y:y+h, x:x+w]
        face_filename = f"student_images/{reg_number}.jpg"
        cv2.imwrite(face_filename, face)
        print(f"Face captured and saved as {face_filename}")
        cap.release()
        return face_filename
    else:
        print("No face detected.")
        cap.release()
        return None

@app.route('/')
def index():
    return redirect(url_for('signup'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']  # 'student' or 'admin'
        conn = sqlite3.connect('attendance.db')
        c = conn.cursor()
        c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", (username, password, role))
        conn.commit()
        conn.close()
        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = sqlite3.connect('attendance.db')
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
        user = c.fetchone()
        conn.close()
        if user:
            session['username'] = user[1]
            session['role'] = user[3]  # 'student' or 'admin'
            if user[3] == 'student':
                return redirect(url_for('student'))
            else:
                return redirect(url_for('admin'))
        else:
            return "Invalid credentials"
    return render_template('login.html')

@app.route('/student', methods=['GET', 'POST'])
def student():
    if 'username' not in session or session['role'] != 'student':
        return redirect(url_for('login'))

    if request.method == 'POST':
        name = request.form['name']
        reg_number = request.form['reg_number']
        year = request.form['year']
        course = request.form['course']
        face_filename = capture_face(reg_number)
        if face_filename:
            conn = sqlite3.connect('attendance.db')
            c = conn.cursor()
            c.execute("INSERT INTO students (name, reg_number, year, course, face_image) VALUES (?, ?, ?, ?, ?)",
                      (name, reg_number, year, course, face_filename))
            conn.commit()
            conn.close()
            return "Student registered successfully"
        else:
            return "Face capture failed. Ensure your face is clearly visible and well-lit."
    return render_template('student.html')

@app.route('/mark_attendance', methods=['POST'])
def mark_attendance():
    if 'username' not in session or session['role'] != 'student':
        return redirect(url_for('login'))

    reg_number = request.form['reg_number']
    conn = sqlite3.connect('attendance.db')
    c = conn.cursor()
    c.execute("SELECT id FROM students WHERE reg_number = ?", (reg_number,))
    student = c.fetchone()
    if student:
        student_id = student[0]
        now = datetime.now()
        date = now.strftime("%Y-%m-%d")
        time = now.strftime("%H:%M:%S")
        c.execute("INSERT INTO attendance (student_id, date, time) VALUES (?, ?, ?)", (student_id, date, time))
        conn.commit()
        conn.close()

        # Save to Excel
        data = {
            "Student ID": [student_id],
            "Registration Number": [reg_number],
            "Date": [date],
            "Time": [time]
        }
        df = pd.DataFrame(data)
        if not os.path.exists('attendance.xlsx'):
            df.to_excel('attendance.xlsx', index=False)
        else:
            existing_df = pd.read_excel('attendance.xlsx')
            updated_df = pd.concat([existing_df, df], ignore_index=True)
            updated_df.to_excel('attendance.xlsx', index=False)

        return "Attendance marked successfully"
    else:
        return "Student not found"

@app.route('/admin')
def admin():
    if 'username' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    conn = sqlite3.connect('attendance.db')
    c = conn.cursor()
    c.execute('''SELECT students.name, students.reg_number, students.face_image, attendance.date, attendance.time
                 FROM attendance
                 INNER JOIN students ON attendance.student_id = students.id''')
    attendance_records = c.fetchall()
    conn.close()
    return render_template('admin.html', attendance_records=attendance_records)

@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('role', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)