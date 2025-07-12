from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask import jsonify
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# MySQL configuration
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'Todoroki4'
app.config['MYSQL_DB'] = 'fixmysched'

# Upload configuration
UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

mysql = MySQL(app)

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password_input = request.form['password']

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cur.fetchone()
        cur.close()

        if user and check_password_hash(user[2], password_input):  # user[2] is password
            session['username'] = username
            session['is_admin'] = bool(user[-1])  # Assuming is_admin is the last column
            flash("Login successful!", "success")
            return redirect(url_for('admin_dashboard' if session['is_admin'] else 'dashboard'))
        else:
            flash("Invalid username or password.", "danger")

    return render_template('login.html')

@app.route('/admin')
def admin_dashboard():
    if 'username' not in session or not session.get('is_admin'):
        flash('Access denied. Admins only.', 'danger')
        return redirect(url_for('dashboard'))

    cur = mysql.connection.cursor()
    cur.execute("SELECT username, full_name, department FROM users")
    employees = cur.fetchall()
    cur.close()
    return render_template('admin_dashboard.html', employees=employees)

@app.route('/admin/schedules')
def admin_schedules():
    if not session.get('is_admin'):
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))

    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT s.id, s.username, u.full_name, s.shift_date, s.shift_time, s.department, s.notes
        FROM schedules s
        JOIN users u ON s.username = u.username
        ORDER BY s.shift_date ASC
    """)
    schedules = cur.fetchall()
    cur.close()
    return render_template('admin_schedules.html', schedules=schedules)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        full_name = request.form['full_name']
        email = request.form['email']
        phone = request.form['phone']
        department = request.form['department']
        address = request.form['address']
        is_admin = 'is_admin' in request.form  # Get checkbox value

        # Photo upload
        photo_file = request.files['photo']
        photo_filename = ''
        if photo_file and photo_file.filename:
            photo_filename = secure_filename(photo_file.filename)
            photo_path = os.path.join(app.config['UPLOAD_FOLDER'], photo_filename)
            photo_file.save(photo_path)

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        existing_user = cur.fetchone()

        if existing_user:
            flash("Username already taken.", "danger")
            return redirect(url_for('register'))

        # Insert new user with admin flag
        cur.execute("""
            INSERT INTO users (username, password, full_name, email, phone, department, address, photo, is_admin)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (username, password, full_name, email, phone, department, address, photo_filename, is_admin))
        
        mysql.connection.commit()
        cur.close()
        flash("Registration successful! Please log in.", "success")
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/dashboard')
def dashboard():
    if 'username' in session:
        return render_template('dashboard.html', username=session['username'])
    else:
        flash('Please log in first.', 'warning')
        return redirect(url_for('login'))

@app.route('/profile')
def profile():
    if 'username' not in session:
        flash("Login required", "danger")
        return redirect(url_for('login'))

    username = session['username']
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT full_name, email, phone, department, address, photo 
        FROM users WHERE username = %s
    """, (username,))
    user_data = cur.fetchone()
    cur.close()

    return render_template('profile.html', user=user_data, username=username)

@app.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    if 'username' not in session:
        flash('Please log in first.', 'warning')
        return redirect(url_for('login'))

    username = session['username']
    cur = mysql.connection.cursor()

    if request.method == 'POST':
        full_name = request.form['full_name']
        email = request.form['email']
        phone = request.form['phone']
        department = request.form['department']
        address = request.form['address']
        photo = request.files.get('photo')
        photo_filename = None

        if photo and photo.filename:
            photo_filename = secure_filename(photo.filename)
            photo.save(os.path.join(app.config['UPLOAD_FOLDER'], photo_filename))
            cur.execute("""
                UPDATE users SET full_name=%s, email=%s, phone=%s, department=%s, address=%s, photo=%s 
                WHERE username=%s
            """, (full_name, email, phone, department, address, photo_filename, username))
        else:
            cur.execute("""
                UPDATE users SET full_name=%s, email=%s, phone=%s, department=%s, address=%s 
                WHERE username=%s
            """, (full_name, email, phone, department, address, username))

        mysql.connection.commit()
        cur.close()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('profile'))

    # GET request: fetch current profile data
    cur.execute("SELECT full_name, email, phone, department, address, photo FROM users WHERE username = %s", (username,))
    user = cur.fetchone()
    cur.close()

    return render_template('edit_profile.html', user=user, username=username)

@app.route('/schedule')
def schedule():
    if 'username' not in session:
        flash("Login required", "danger")
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute("SELECT id, shift_date, shift_time, department, notes FROM schedules WHERE username = %s ORDER BY shift_date", (session['username'],))
    schedule_data = cur.fetchall()
    cur.close()
    return render_template('schedule.html', schedule=schedule_data)

@app.route('/add_shift', methods=['GET', 'POST'])
def add_shift():
    if 'username' not in session:
        flash("Login required", "danger")
        return redirect(url_for('login'))

    if request.method == 'POST':
        shift_date = request.form['shift_date']
        shift_time = request.form['shift_time']
        department = request.form['department']
        notes = request.form['notes']

        cur = mysql.connection.cursor()
        cur.execute("""
            INSERT INTO schedules (username, shift_date, shift_time, department, notes)
            VALUES (%s, %s, %s, %s, %s)
        """, (session['username'], shift_date, shift_time, department, notes))
        mysql.connection.commit()
        cur.close()
        flash('Shift added successfully!', 'success')
        return redirect(url_for('schedule'))

    return render_template('add_shift.html')
@app.route('/edit_shift/<int:shift_id>', methods=['GET', 'POST'])
def edit_shift(shift_id):
    if 'username' not in session:
        flash("Login required", "danger")
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()

    if request.method == 'POST':
        shift_date = request.form['shift_date']
        shift_time = request.form['shift_time']
        department = request.form['department']
        notes = request.form['notes']

        cur.execute("""
            UPDATE schedules 
            SET shift_date = %s, shift_time = %s, department = %s, notes = %s 
            WHERE id = %s AND username = %s
        """, (shift_date, shift_time, department, notes, shift_id, session['username']))
        mysql.connection.commit()
        cur.close()
        flash('Shift updated successfully.', 'success')
        return redirect(url_for('schedule'))

    cur.execute("SELECT * FROM schedules WHERE id = %s AND username = %s", (shift_id, session['username']))
    shift = cur.fetchone()
    cur.close()
    if not shift:
        flash("Shift not found.", "danger")
        return redirect(url_for('schedule'))

    return render_template('edit_shift.html', shift=shift)

@app.route('/delete_shift/<int:shift_id>')
def delete_shift(shift_id):
    if 'username' not in session:
        flash("Login required", "danger")
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM schedules WHERE id = %s AND username = %s", (shift_id, session['username']))
    mysql.connection.commit()
    cur.close()
    flash("Shift deleted successfully.", "info")
    return redirect(url_for('schedule'))

@app.route('/mark_unavailable/<int:shift_id>')
def mark_unavailable(shift_id):
    if 'username' not in session:
        flash("Login required", "danger")
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute("UPDATE schedules SET notes = CONCAT(COALESCE(notes, ''), ' [Marked Absent]') WHERE id = %s AND username = %s", (shift_id, session['username']))
    mysql.connection.commit()
    cur.close()
    flash("Shift marked as absent.", "warning")
    return redirect(url_for('schedule'))

@app.route('/api/schedule')
def api_schedule():
    if 'username' not in session:
        return jsonify([])

    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT shift_date, shift_time, department, notes 
        FROM schedules WHERE username = %s
    """, (session['username'],))
    shifts = cur.fetchall()
    cur.close()

    events = []
    for shift in shifts:
        date = shift[0].strftime('%Y-%m-%d')
        title = f"{shift[1]} Shift - {shift[2]}"
        if shift[3]:
            title += f" ({shift[3]})"
        events.append({"title": title, "start": date})

    return jsonify(events)

@app.route('/admin/delete_user/<string:username>', methods=['POST'])
def delete_user(username):
    if 'username' not in session or not session.get('is_admin'):
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))

    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM users WHERE username = %s", (username,))
    mysql.connection.commit()
    cur.close()
    flash(f"User '{username}' has been deleted.", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/calendar')
def calendar():
    if 'username' not in session:
        flash('Login required', 'danger')
        return redirect(url_for('login'))
    return render_template('calendar.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    flash('Logged out.', 'info')
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
