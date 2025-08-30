from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from MySQLdb.cursors import DictCursor
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# MySQL configuration
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'Todoroki4'
app.config['MYSQL_DB'] = 'fixmysched'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

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

        if user and check_password_hash(user['password'], password_input):
            session['username'] = username
            session['is_admin'] = bool(user['is_admin'])
            flash("Login successful!", "success")
            return redirect(url_for('admin_dashboard' if session['is_admin'] else 'dashboard'))
        else:
            flash("Invalid username or password.", "danger")

    return render_template('login.html')

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
        is_admin = 'is_admin' in request.form

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

        cur.execute("""
            INSERT INTO users (username, password, full_name, email, phone, department, address, photo, is_admin)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (username, password, full_name, email, phone, department, address, photo_filename, is_admin))

        mysql.connection.commit()
        cur.close()
        flash("Registration successful! Please log in.", "success")
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/profile')
def profile():
    if 'username' not in session:
        flash('Please login first.', 'warning')
        return redirect(url_for('login'))

    username = session['username']  
    cur = mysql.connection.cursor()
    cur.execute("SELECT username, full_name, email, phone, department, address, photo FROM users WHERE username = %s", (username,))
    user = cur.fetchone()
    cur.close()

    return render_template('profile.html', user=user)

@app.route('/profile/<string:username>')
def view_profile(username):
    if 'username' not in session or not session.get('is_admin'):
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))

    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM users WHERE username = %s", (username,))
    user = cur.fetchone()
    cur.close()

    if not user:
        flash('User not found.', 'warning')
        return redirect(url_for('admin_dashboard'))

    return render_template('profile.html', user=user)


@app.route('/dashboard')
def dashboard():
    if 'username' in session:
        return render_template('dashboard.html', username=session['username'])
    else:
        flash('Please log in first.', 'warning')
        return redirect(url_for('login'))
@app.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    if 'username' not in session:
        flash("Please log in to edit your profile.", "warning")
        return redirect(url_for('login'))

    username = session['username']
    cur = mysql.connection.cursor()
    cur.execute("SELECT username, full_name, email, phone, department, address, photo FROM users WHERE username = %s", (username,))
    user = cur.fetchone()

    if request.method == 'POST':
        full_name = request.form['full_name']
        email = request.form['email']
        phone = request.form['phone']
        department = request.form['department']
        address = request.form['address']

        # Handle photo upload
        photo_file = request.files['photo']
        photo_filename = user['photo'] if user['photo'] else ''
        if photo_file and photo_file.filename:
            photo_filename = secure_filename(photo_file.filename)
            photo_file.save(os.path.join(app.config['UPLOAD_FOLDER'], photo_filename))

        cur.execute("""
            UPDATE users
            SET full_name=%s, email=%s, phone=%s, department=%s, address=%s, photo=%s
            WHERE username=%s
        """, (full_name, email, phone, department, address, photo_filename, username))
        mysql.connection.commit()
        cur.close()

        flash("Profile updated successfully!", "success")
        return redirect(url_for('profile'))

    cur.close()
    return render_template('edit_profile.html', user=user)

    
@app.route('/schedule')
def schedule():
    if 'username' not in session:
        flash("Please log in to view your schedule.", "warning")
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM schedules WHERE username = %s ORDER BY shift_date ASC", (session['username'],))
    user_schedule = cur.fetchall()
    cur.close()

    return render_template('schedule.html', schedule=user_schedule)

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
    if 'username' not in session or not session.get('is_admin'):
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

@app.route('/admin/edit_shift/<int:shift_id>', methods=['GET', 'POST'])
def admin_edit_shift(shift_id):
    if 'username' not in session or not session.get('is_admin'):
        flash("Access denied.", "danger")
        return redirect(url_for('dashboard'))

    cur = mysql.connection.cursor()

    if request.method == 'POST':
        shift_date = request.form['shift_date']
        shift_time = request.form['shift_time']
        department = request.form['department']
        notes = request.form['notes']

        cur.execute("""
            UPDATE schedules 
            SET shift_date = %s, shift_time = %s, department = %s, notes = %s 
            WHERE id = %s
        """, (shift_date, shift_time, department, notes, shift_id))
        mysql.connection.commit()
        cur.close()
        flash("Shift updated successfully.", "success")
        return redirect(url_for('admin_schedules'))

    cur.execute("SELECT * FROM schedules WHERE id = %s", (shift_id,))
    shift = cur.fetchone()
    cur.close()

    if not shift:
        flash("Shift not found.", "danger")
        return redirect(url_for('admin_schedules'))

    return render_template('admin_edit_shift.html', shift=shift)

@app.route('/admin/delete_user/<string:username>', methods=['POST'])
def delete_user(username):
    if 'username' not in session or not session.get('is_admin'):
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))

    cur = mysql.connection.cursor()
    try:
        cur.execute("DELETE FROM schedules WHERE username = %s", (username,))
        cur.execute("DELETE FROM users WHERE username = %s", (username,))
        mysql.connection.commit()
        flash(f"User '{username}' has been deleted.", "success")
    except Exception as e:
        mysql.connection.rollback()
        flash("Cannot delete user: " + str(e), "danger")
    finally:
        cur.close()

    return redirect(url_for('admin_dashboard'))

@app.route('/admin/add_shift/', methods=['GET', 'POST'])
def admin_add_shift():
    if 'username' not in session or not session.get('is_admin'):
        flash('Access denied', 'danger')
        return redirect(url_for('dashboard'))

    cur = mysql.connection.cursor()
    cur.execute("SELECT username FROM users")  # Make sure this returns all employees
    users = cur.fetchall()

    if request.method == 'POST':
        username = request.form['username']
        shift_date = request.form['shift_date']
        shift_time = request.form['shift_time']
        department = request.form['department']
        notes = request.form['notes']

        cur.execute("""
            INSERT INTO schedules (username, shift_date, shift_time, department, notes)
            VALUES (%s, %s, %s, %s, %s)
        """, (username, shift_date, shift_time, department, notes))

        mysql.connection.commit()
        cur.close()
        flash('Shift added successfully for employee.', 'success')
        return redirect(url_for('admin_schedules'))

    cur.close()
    return render_template('admin_add_shift.html', users=users)

@app.route('/admin/add_shift/<string:username>', methods=['GET', 'POST'])
def admin_add_shift_for_user(username):
    if 'username' not in session or not session.get('is_admin'):
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))

    # Check if the user exists
    cur = mysql.connection.cursor()
    cur.execute("SELECT username, full_name FROM users WHERE username = %s", (username,))
    user = cur.fetchone()

    if not user:
        flash("User not found.", "warning")
        return redirect(url_for('admin_dashboard'))

    # Handle form submission
    if request.method == 'POST':
        shift_date = request.form['shift_date']
        shift_time = request.form['shift_time']
        department = request.form['department']
        notes = request.form['notes']

        cur.execute("""
            INSERT INTO schedules (username, shift_date, shift_time, department, notes)
            VALUES (%s, %s, %s, %s, %s)
        """, (username, shift_date, shift_time, department, notes))
        mysql.connection.commit()
        cur.close()

        flash(f"Shift added successfully for {username}.", "success")
        return redirect(url_for('admin_schedules'))

    cur.close()
    return render_template('admin_add_shift_user.html', user=user)


@app.route('/calendar')
def calendar():
    if 'username' not in session:
        flash('Login required', 'danger')
        return redirect(url_for('login'))
    return render_template('calendar.html')
@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('is_admin', None)
    flash('Logged out.', 'info')
    return redirect(url_for('login'))
@app.route('/admin/edit_profile/<string:username>', methods=['GET', 'POST'])
def admin_edit_profile(username):
    if 'username' not in session or not session.get('is_admin'):
        flash("Access denied. Admins only.", "danger")
        return redirect(url_for('dashboard'))

    cur = mysql.connection.cursor()
    cur.execute("SELECT username, full_name, email, phone, department, address, photo FROM users WHERE username = %s", (username,))
    user = cur.fetchone()

    if not user:
        flash("User not found.", "warning")
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        full_name = request.form['full_name']
        email = request.form['email']
        phone = request.form['phone']
        department = request.form['department']
        address = request.form['address']

        # Handle photo upload
        photo_file = request.files['photo']
        photo_filename = user['photo'] if user['photo'] else ''
        if photo_file and photo_file.filename:
            photo_filename = secure_filename(photo_file.filename)
            photo_file.save(os.path.join(app.config['UPLOAD_FOLDER'], photo_filename))

        cur.execute("""
            UPDATE users
            SET full_name=%s, email=%s, phone=%s, department=%s, address=%s, photo=%s
            WHERE username=%s
        """, (full_name, email, phone, department, address, photo_filename, username))
        mysql.connection.commit()
        cur.close()

        flash("Profile updated successfully!", "success")
        return redirect(url_for('view_profile', username=username))

    cur.close()
    return render_template('edit_profile.html', user=user)

@app.route('/admin/auto_allocate_shifts', methods=['POST'])
def auto_allocate_shifts():
    if 'username' not in session or not session.get('is_admin'):
        flash("Access denied. Admins only.", "danger")
        return redirect(url_for('dashboard'))

    cur = mysql.connection.cursor()

    # Fetch all non-admin employees
    cur.execute("SELECT username FROM users WHERE is_admin = 0")
    employees = [row['username'] for row in cur.fetchall()]

    if not employees:
        flash("No employees found to allocate shifts.", "warning")
        return redirect(url_for('admin_dashboard'))

    # Shifts definition
    shifts = ["Morning", "Afternoon", "Night"]

    from datetime import datetime, timedelta
    start_date = datetime.now().date()
    days = 7  # next 7 days

    assignments = []
    emp_index = 0

    for day in range(days):
        shift_date = start_date + timedelta(days=day)
        for shift in shifts:
            username = employees[emp_index % len(employees)]
            assignments.append((username, shift, shift_date))
            emp_index += 1

    # Insert into DB
    for username, shift, shift_date in assignments:
        cur.execute("""
            INSERT INTO shifts (username, shift_type, shift_date)
            VALUES (%s, %s, %s)
        """, (username, shift, shift_date))

    mysql.connection.commit()
    cur.close()

    flash("Shifts auto-allocated successfully!", "success")
    return redirect(url_for('admin_schedules'))


if __name__ == '__main__':
    app.run(debug=True)
