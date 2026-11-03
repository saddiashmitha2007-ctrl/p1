import os
import csv
import io
from datetime import datetime
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, session, jsonify, Response, abort
)
from werkzeug.security import generate_password_hash, check_password_hash

from database import get_db_connection, init_db, seed_sample_data
import ai_engine

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "campus-maintenance-secret-key-2026-secure-random")

# Ensure database is created on startup
with app.app_context():
    init_db()
    seed_sample_data()

# ---------------------------------------------------------
# AUTHENTICATION & ACCESS CONTROL HELPERS
# ---------------------------------------------------------

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please sign in to access this page.", "warning")
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash("Please sign in to access this page.", "warning")
                return redirect(url_for('login', next=request.url))
            if session.get('role') not in roles:
                flash("Access denied: You do not have permissions for this page.", "danger")
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@app.context_processor
def inject_global_data():
    """Injects notifications and current user details to all templates."""
    notifications = []
    unread_count = 0
    if 'user_id' in session:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM notifications
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT 5
            """, (session['user_id'],))
            notifications = cursor.fetchall()

            cursor.execute("""
                SELECT COUNT(*) as count FROM notifications
                WHERE user_id = ? AND is_read = 0
            """, (session['user_id'],))
            unread_count = cursor.fetchone()['count']
            conn.close()
        except Exception:
            pass

    return {
        'current_user': {
            'id': session.get('user_id'),
            'username': session.get('username'),
            'full_name': session.get('full_name'),
            'role': session.get('role'),
            'worker_id': session.get('worker_id')
        },
        'categories': ai_engine.CATEGORIES,
        'notifications': notifications,
        'unread_count': unread_count,
        'now_year': datetime.now().year
    }

# ---------------------------------------------------------
# PUBLIC & HOME ROUTES
# ---------------------------------------------------------

@app.route('/')
def index():
    conn = get_db_connection()
    cursor = conn.cursor()

    # High-level statistics for hero section
    cursor.execute("SELECT COUNT(*) as total FROM complaints")
    total_complaints = cursor.fetchone()['total']

    cursor.execute("SELECT COUNT(*) as pending FROM complaints WHERE status IN ('Submitted', 'Assigned')")
    pending_complaints = cursor.fetchone()['pending']

    cursor.execute("SELECT COUNT(*) as in_progress FROM complaints WHERE status = 'In Progress'")
    in_progress_complaints = cursor.fetchone()['in_progress']

    cursor.execute("SELECT COUNT(*) as resolved FROM complaints WHERE status IN ('Resolved', 'Closed')")
    resolved_complaints = cursor.fetchone()['resolved']

    # 5 most recent complaints
    cursor.execute("""
        SELECT c.*, w.name as worker_name
        FROM complaints c
        LEFT JOIN workers w ON c.assigned_worker_id = w.id
        ORDER BY c.created_at DESC
        LIMIT 5
    """)
    recent_complaints = cursor.fetchall()
    conn.close()

    return render_template(
        'index.html',
        total=total_complaints,
        pending=pending_complaints,
        in_progress=in_progress_complaints,
        resolved=resolved_complaints,
        recent_complaints=recent_complaints
    )

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        selected_role = request.form.get('role', '')

        if not username or not password:
            flash("Please enter both username and password.", "danger")
            return render_template('login.html', selected_role=selected_role)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ? OR email = ?", (username, username))
        user = cursor.fetchone()

        if user and check_password_hash(user['password_hash'], password):
            # If role was selected, verify it matches
            if selected_role and user['role'] != selected_role:
                flash(f"Account '{username}' is registered as {user['role'].capitalize()}, not {selected_role.capitalize()}.", "warning")
                conn.close()
                return render_template('login.html', selected_role=selected_role)

            session['user_id'] = user['id']
            session['username'] = user['username']
            session['full_name'] = user['full_name']
            session['role'] = user['role']

            # If worker, store worker_id in session
            if user['role'] == 'worker':
                cursor.execute("SELECT id FROM workers WHERE user_id = ?", (user['id'],))
                w = cursor.fetchone()
                if w:
                    session['worker_id'] = w['id']

            conn.close()
            flash(f"Welcome back, {user['full_name']}!", "success")

            next_url = request.args.get('next')
            if next_url:
                return redirect(next_url)

            if user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif user['role'] == 'worker':
                return redirect(url_for('worker_dashboard'))
            else:
                return redirect(url_for('submit_complaint'))
        else:
            conn.close()
            flash("Invalid username or password. Please try again.", "danger")

    role_param = request.args.get('role', '')
    return render_template('login.html', selected_role=role_param)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        department = request.form.get('department', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not username or not full_name or not password:
            flash("Username, Full Name, and Password are required.", "danger")
            return render_template('register.html')

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template('register.html')

        if len(password) < 6:
            flash("Password must be at least 6 characters long.", "warning")
            return render_template('register.html')

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
        if cursor.fetchone():
            conn.close()
            flash("Username is already taken. Please choose another.", "danger")
            return render_template('register.html')

        hashed_pw = generate_password_hash(password)
        cursor.execute("""
            INSERT INTO users (username, password_hash, full_name, email, phone, department, role)
            VALUES (?, ?, ?, ?, ?, ?, 'staff')
        """, (username, hashed_pw, full_name, email, phone, department))
        conn.commit()

        # Automatically sign them in
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        session['user_id'] = user['id']
        session['username'] = user['username']
        session['full_name'] = user['full_name']
        session['role'] = user['role']
        conn.close()

        flash("Registration successful! Welcome to Campus Maintenance Tracker.", "success")
        return redirect(url_for('submit_complaint'))

    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been signed out successfully.", "info")
    return redirect(url_for('index'))

# ---------------------------------------------------------
# COMPLAINT SUBMISSION & STAFF VIEWS
# ---------------------------------------------------------

@app.route('/submit-complaint', methods=['GET', 'POST'])
def submit_complaint():
    if request.method == 'POST':
        staff_name = request.form.get('staff_name', '').strip()
        staff_contact = request.form.get('staff_contact', '').strip()
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        category = request.form.get('category', '').strip()
        location = request.form.get('location', '').strip()
        priority = request.form.get('priority', 'Medium')
        is_voice = int(request.form.get('is_voice_submitted', 0))
        duplicate_confirmed = int(request.form.get('is_duplicate_confirmed', 0))
        duplicate_of_id = request.form.get('duplicate_of_id') or None

        # Validation
        if not title or not description or not location:
            flash("Please provide a Title, Description, and Location.", "danger")
            return render_template('submit_complaint.html')

        # If category wasn't picked, let AI engine classify it
        if not category or category not in ai_engine.CATEGORIES:
            category, _ = ai_engine.classify_complaint(description + " " + title)

        # Re-check priority if default Medium
        if priority not in ['Critical', 'High', 'Medium', 'Low']:
            priority = ai_engine.determine_priority(description + " " + title)

        # Troubleshoot recommendation
        troubleshooting = ai_engine.get_troubleshooting_tips(category)

        # Match Worker intelligently
        assigned_worker = ai_engine.find_best_worker(category)
        assigned_worker_id = assigned_worker['id'] if assigned_worker else None
        status = 'Assigned' if assigned_worker_id else 'Submitted'

        staff_id = session.get('user_id')
        if not staff_name:
            staff_name = session.get('full_name', 'Campus Staff')

        # Generate unique complaint code
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM complaints")
        total = cursor.fetchone()['count'] + 1001
        complaint_code = f"CMP-{total}"

        # Insert complaint
        cursor.execute("""
            INSERT INTO complaints (
                complaint_code, staff_id, staff_name, staff_contact,
                title, description, category, location, priority,
                status, assigned_worker_id, troubleshooting_tips,
                is_voice_submitted, is_duplicate_confirmed, duplicate_of_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            complaint_code, staff_id, staff_name, staff_contact,
            title, description, category, location, priority,
            status, assigned_worker_id, troubleshooting,
            is_voice, duplicate_confirmed, duplicate_of_id
        ))
        complaint_id = cursor.lastrowid

        # Insert status history
        cursor.execute("""
            INSERT INTO status_history (complaint_id, changed_by_id, changed_by_name, old_status, new_status, remarks)
            VALUES (?, ?, ?, NULL, ?, ?)
        """, (
            complaint_id, staff_id, staff_name, status,
            f"Complaint registered via {'Voice Assistant' if is_voice else 'Text Form'}."
        ))

        # If assigned, update worker active count and notify worker
        if assigned_worker_id:
            cursor.execute("UPDATE workers SET active_count = active_count + 1 WHERE id = ?", (assigned_worker_id,))
            if assigned_worker['user_id']:
                cursor.execute("""
                    INSERT INTO notifications (user_id, title, message, link)
                    VALUES (?, 'New Task Assigned', ?, ?)
                """, (
                    assigned_worker['user_id'],
                    f"New {priority} priority complaint ({complaint_code}) at {location}: {title}",
                    url_for('complaint_detail', complaint_id=complaint_id)
                ))
        else:
            # Notify admins that a complaint is unassigned
            cursor.execute("SELECT id FROM users WHERE role = 'admin'")
            admin_rows = cursor.fetchall()
            for a in admin_rows:
                cursor.execute("""
                    INSERT INTO notifications (user_id, title, message, link)
                    VALUES (?, 'Unassigned Complaint Alert', ?, ?)
                """, (
                    a['id'],
                    f"No worker available for {category} complaint ({complaint_code}). Manual assignment needed.",
                    url_for('complaint_detail', complaint_id=complaint_id)
                ))

        conn.commit()
        conn.close()

        flash(f"Complaint {complaint_code} submitted successfully! Our maintenance system has logged your request.", "success")
        return redirect(url_for('complaint_detail', complaint_id=complaint_id))

    return render_template('submit_complaint.html')

@app.route('/track')
def track():
    query_code = request.args.get('code', '').strip()
    status_filter = request.args.get('status', '').strip()
    category_filter = request.args.get('category', '').strip()

    conn = get_db_connection()
    cursor = conn.cursor()

    sql = """
        SELECT c.*, w.name as worker_name, w.phone as worker_phone
        FROM complaints c
        LEFT JOIN workers w ON c.assigned_worker_id = w.id
        WHERE 1=1
    """
    params = []

    if query_code:
        sql += " AND (c.complaint_code LIKE ? OR c.title LIKE ? OR c.location LIKE ?)"
        params.extend([f"%{query_code}%", f"%{query_code}%", f"%{query_code}%"])

    if status_filter:
        sql += " AND c.status = ?"
        params.append(status_filter)

    if category_filter:
        sql += " AND c.category = ?"
        params.append(category_filter)

    # If logged in as staff (not admin/worker), prioritize their complaints first
    if session.get('role') == 'staff' and not query_code:
        sql += " ORDER BY (c.staff_id = ?) DESC, c.created_at DESC"
        params.append(session['user_id'])
    else:
        sql += " ORDER BY c.created_at DESC"

    cursor.execute(sql, params)
    complaints = cursor.fetchall()
    conn.close()

    return render_template(
        'track.html',
        complaints=complaints,
        query_code=query_code,
        status_filter=status_filter,
        category_filter=category_filter
    )

@app.route('/complaint/<int:complaint_id>')
def complaint_detail(complaint_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT c.*, w.name as worker_name, w.phone as worker_phone, w.specialization as worker_spec
        FROM complaints c
        LEFT JOIN workers w ON c.assigned_worker_id = w.id
        WHERE c.id = ?
    """, (complaint_id,))
    complaint = cursor.fetchone()

    if not complaint:
        conn.close()
        flash("Complaint not found.", "warning")
        return redirect(url_for('track'))

    # Fetch status history
    cursor.execute("""
        SELECT * FROM status_history
        WHERE complaint_id = ?
        ORDER BY timestamp ASC
    """, (complaint_id,))
    history = cursor.fetchall()

    # Fetch repair notes
    cursor.execute("""
        SELECT * FROM repair_notes
        WHERE complaint_id = ?
        ORDER BY created_at ASC
    """, (complaint_id,))
    notes = cursor.fetchall()

    # Fetch all workers for admin reassignment modal
    cursor.execute("SELECT * FROM workers ORDER BY specialization, name")
    all_workers = cursor.fetchall()

    conn.close()
    return render_template(
        'complaint_detail.html',
        complaint=complaint,
        history=history,
        notes=notes,
        all_workers=all_workers
    )

@app.route('/complaint/<int:complaint_id>/reopen', methods=['POST'])
@login_required
def reopen_complaint(complaint_id):
    reopen_reason = request.form.get('reason', '').strip()
    if not reopen_reason:
        flash("Please provide a reason explaining why the issue is not fixed.", "warning")
        return redirect(url_for('complaint_detail', complaint_id=complaint_id))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM complaints WHERE id = ?", (complaint_id,))
    c = cursor.fetchone()

    if not c:
        conn.close()
        flash("Complaint not found.", "danger")
        return redirect(url_for('track'))

    # Only creator staff or admin can reopen
    if session.get('role') != 'admin' and c['staff_id'] != session.get('user_id'):
        conn.close()
        flash("You are not authorized to reopen this complaint.", "danger")
        return redirect(url_for('complaint_detail', complaint_id=complaint_id))

    # Update complaint status to 'Reopened'
    cursor.execute("""
        UPDATE complaints
        SET status = 'Reopened', updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (complaint_id,))

    # Insert status history
    cursor.execute("""
        INSERT INTO status_history (complaint_id, changed_by_id, changed_by_name, old_status, new_status, remarks)
        VALUES (?, ?, ?, ?, 'Reopened', ?)
    """, (complaint_id, session['user_id'], session['full_name'], c['status'], reopen_reason))

    # If worker was assigned, increment active count and notify
    if c['assigned_worker_id']:
        cursor.execute("UPDATE workers SET active_count = active_count + 1 WHERE id = ?", (c['assigned_worker_id'],))
        cursor.execute("SELECT user_id FROM workers WHERE id = ?", (c['assigned_worker_id'],))
        w = cursor.fetchone()
        if w and w['user_id']:
            cursor.execute("""
                INSERT INTO notifications (user_id, title, message, link)
                VALUES (?, 'Complaint Reopened', ?, ?)
            """, (
                w['user_id'],
                f"Complaint {c['complaint_code']} was reopened: {reopen_reason}",
                url_for('complaint_detail', complaint_id=complaint_id)
            ))

    conn.commit()
    conn.close()

    flash(f"Complaint {c['complaint_code']} has been reopened. The maintenance team has been alerted.", "info")
    return redirect(url_for('complaint_detail', complaint_id=complaint_id))

# ---------------------------------------------------------
# WORKER DASHBOARD & ACTIONS
# ---------------------------------------------------------

@app.route('/worker/dashboard')
@role_required('worker', 'admin')
def worker_dashboard():
    worker_id = session.get('worker_id')
    conn = get_db_connection()
    cursor = conn.cursor()

    # If admin viewing, allow picking a worker or defaulting to first worker
    if session.get('role') == 'admin' and not worker_id:
        cursor.execute("SELECT id FROM workers LIMIT 1")
        w_first = cursor.fetchone()
        worker_id = w_first['id'] if w_first else 1

    # Fetch worker details
    cursor.execute("SELECT * FROM workers WHERE id = ?", (worker_id,))
    worker = cursor.fetchone()

    # Assigned active complaints
    cursor.execute("""
        SELECT * FROM complaints
        WHERE assigned_worker_id = ? AND status IN ('Assigned', 'In Progress', 'Reopened')
        ORDER BY
            CASE priority
                WHEN 'Critical' THEN 1
                WHEN 'High' THEN 2
                WHEN 'Medium' THEN 3
                WHEN 'Low' THEN 4
            END,
            created_at ASC
    """, (worker_id,))
    active_tasks = cursor.fetchall()

    # Resolved history
    cursor.execute("""
        SELECT * FROM complaints
        WHERE assigned_worker_id = ? AND status IN ('Resolved', 'Closed')
        ORDER BY resolved_at DESC
        LIMIT 10
    """, (worker_id,))
    completed_tasks = cursor.fetchall()

    conn.close()
    return render_template(
        'worker_dashboard.html',
        worker=worker,
        active_tasks=active_tasks,
        completed_tasks=completed_tasks
    )

@app.route('/worker/update-status', methods=['POST'])
@role_required('worker', 'admin')
def worker_update_status():
    complaint_id = request.form.get('complaint_id')
    new_status = request.form.get('status')
    repair_note = request.form.get('repair_note', '').strip()

    if not complaint_id or new_status not in ['In Progress', 'Resolved', 'Closed']:
        flash("Invalid status update request.", "danger")
        return redirect(url_for('worker_dashboard'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM complaints WHERE id = ?", (complaint_id,))
    c = cursor.fetchone()

    if not c:
        conn.close()
        flash("Complaint not found.", "danger")
        return redirect(url_for('worker_dashboard'))

    # If resolving, require repair note
    if new_status == 'Resolved' and not repair_note:
        conn.close()
        flash("A repair note detailing actions taken is required to mark as Resolved.", "warning")
        return redirect(url_for('complaint_detail', complaint_id=complaint_id))

    old_status = c['status']

    # Update complaint
    if new_status == 'Resolved':
        cursor.execute("""
            UPDATE complaints
            SET status = ?, resolved_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (new_status, complaint_id))

        # Decrement active count on worker
        if c['assigned_worker_id']:
            cursor.execute("""
                UPDATE workers
                SET active_count = MAX(0, active_count - 1)
                WHERE id = ?
            """, (c['assigned_worker_id'],))
    else:
        cursor.execute("""
            UPDATE complaints
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (new_status, complaint_id))

    # Add repair note if provided
    if repair_note:
        cursor.execute("""
            INSERT INTO repair_notes (complaint_id, author_id, author_name, author_role, note)
            VALUES (?, ?, ?, ?, ?)
        """, (complaint_id, session['user_id'], session['full_name'], session['role'], repair_note))

    # Add status history
    cursor.execute("""
        INSERT INTO status_history (complaint_id, changed_by_id, changed_by_name, old_status, new_status, remarks)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        complaint_id, session['user_id'], session['full_name'], old_status, new_status,
        repair_note or f"Status changed from {old_status} to {new_status}"
    ))

    # Notify staff member who filed it
    if c['staff_id']:
        cursor.execute("""
            INSERT INTO notifications (user_id, title, message, link)
            VALUES (?, ?, ?, ?)
        """, (
            c['staff_id'],
            f"Complaint {c['complaint_code']} is now {new_status}",
            f"Status updated to {new_status} by {session['full_name']}. {repair_note}",
            url_for('complaint_detail', complaint_id=complaint_id)
        ))

    conn.commit()
    conn.close()

    flash(f"Complaint {c['complaint_code']} status updated to {new_status}.", "success")
    return redirect(url_for('worker_dashboard') if session['role'] == 'worker' else url_for('complaint_detail', complaint_id=complaint_id))

@app.route('/worker/toggle-availability', methods=['POST'])
@role_required('worker', 'admin')
def toggle_worker_availability():
    worker_id = request.form.get('worker_id') or session.get('worker_id')
    new_avail = request.form.get('availability')

    if new_avail not in ['Available', 'Busy', 'On Leave']:
        flash("Invalid availability status.", "danger")
        return redirect(request.referrer or url_for('worker_dashboard'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE workers SET availability = ? WHERE id = ?", (new_avail, worker_id))
    conn.commit()
    conn.close()

    flash(f"Availability updated to {new_avail}.", "info")
    return redirect(request.referrer or url_for('worker_dashboard'))

# ---------------------------------------------------------
# ADMINISTRATOR DASHBOARD & WORKER MANAGEMENT
# ---------------------------------------------------------

@app.route('/admin/dashboard')
@role_required('admin')
def admin_dashboard():
    status_filter = request.args.get('status', '').strip()
    category_filter = request.args.get('category', '').strip()
    priority_filter = request.args.get('priority', '').strip()
    search = request.args.get('q', '').strip()

    conn = get_db_connection()
    cursor = conn.cursor()

    # KPI counts
    cursor.execute("SELECT COUNT(*) as total FROM complaints")
    total_count = cursor.fetchone()['total']

    cursor.execute("SELECT COUNT(*) as pending FROM complaints WHERE status IN ('Submitted', 'Assigned')")
    pending_count = cursor.fetchone()['pending']

    cursor.execute("SELECT COUNT(*) as in_progress FROM complaints WHERE status = 'In Progress'")
    in_progress_count = cursor.fetchone()['in_progress']

    cursor.execute("SELECT COUNT(*) as resolved FROM complaints WHERE status IN ('Resolved', 'Closed')")
    resolved_count = cursor.fetchone()['resolved']

    cursor.execute("SELECT COUNT(*) as high_prio FROM complaints WHERE priority IN ('High', 'Critical') AND status NOT IN ('Resolved', 'Closed')")
    high_prio_count = cursor.fetchone()['high_prio']

    cursor.execute("SELECT COUNT(*) as unassigned FROM complaints WHERE assigned_worker_id IS NULL AND status NOT IN ('Resolved', 'Closed')")
    unassigned_count = cursor.fetchone()['unassigned']

    # Filtered complaints query
    sql = """
        SELECT c.*, w.name as worker_name, w.specialization as worker_spec
        FROM complaints c
        LEFT JOIN workers w ON c.assigned_worker_id = w.id
        WHERE 1=1
    """
    params = []

    if status_filter:
        sql += " AND c.status = ?"
        params.append(status_filter)
    if category_filter:
        sql += " AND c.category = ?"
        params.append(category_filter)
    if priority_filter:
        sql += " AND c.priority = ?"
        params.append(priority_filter)
    if search:
        sql += " AND (c.complaint_code LIKE ? OR c.title LIKE ? OR c.location LIKE ? OR c.staff_name LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%", f"%{search}%"])

    sql += " ORDER BY c.created_at DESC"
    cursor.execute(sql, params)
    complaints = cursor.fetchall()

    # Fetch all workers for reassignment dropdowns
    cursor.execute("SELECT * FROM workers ORDER BY specialization, name")
    workers = cursor.fetchall()

    conn.close()

    return render_template(
        'admin_dashboard.html',
        complaints=complaints,
        workers=workers,
        total_count=total_count,
        pending_count=pending_count,
        in_progress_count=in_progress_count,
        resolved_count=resolved_count,
        high_prio_count=high_prio_count,
        unassigned_count=unassigned_count,
        status_filter=status_filter,
        category_filter=category_filter,
        priority_filter=priority_filter,
        search=search
    )

@app.route('/admin/assign-worker', methods=['POST'])
@role_required('admin')
def admin_assign_worker():
    complaint_id = request.form.get('complaint_id')
    worker_id = request.form.get('worker_id')
    remarks = request.form.get('remarks', 'Assigned by Administrator').strip()

    if not complaint_id or not worker_id:
        flash("Complaint and Worker must be selected.", "danger")
        return redirect(url_for('admin_dashboard'))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM complaints WHERE id = ?", (complaint_id,))
    c = cursor.fetchone()
    cursor.execute("SELECT * FROM workers WHERE id = ?", (worker_id,))
    w = cursor.fetchone()

    if not c or not w:
        conn.close()
        flash("Invalid complaint or worker selected.", "danger")
        return redirect(url_for('admin_dashboard'))

    old_worker_id = c['assigned_worker_id']

    # Update complaint
    cursor.execute("""
        UPDATE complaints
        SET assigned_worker_id = ?, status = 'Assigned', updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (worker_id, complaint_id))

    # Update workload counts
    if old_worker_id and int(old_worker_id) != int(worker_id):
        cursor.execute("UPDATE workers SET active_count = MAX(0, active_count - 1) WHERE id = ?", (old_worker_id,))
    cursor.execute("UPDATE workers SET active_count = active_count + 1 WHERE id = ?", (worker_id,))

    # Status history
    cursor.execute("""
        INSERT INTO status_history (complaint_id, changed_by_id, changed_by_name, old_status, new_status, remarks)
        VALUES (?, ?, ?, ?, 'Assigned', ?)
    """, (complaint_id, session['user_id'], session['full_name'], c['status'], f"Assigned to {w['name']} ({w['specialization']}). {remarks}"))

    # Notify worker
    if w['user_id']:
        cursor.execute("""
            INSERT INTO notifications (user_id, title, message, link)
            VALUES (?, 'New Task Assigned by Admin', ?, ?)
        """, (
            w['user_id'],
            f"Admin assigned you complaint {c['complaint_code']}: {c['title']} at {c['location']}",
            url_for('complaint_detail', complaint_id=complaint_id)
        ))

    conn.commit()
    conn.close()

    flash(f"Complaint {c['complaint_code']} assigned to {w['name']} successfully.", "success")
    return redirect(request.referrer or url_for('admin_dashboard'))

@app.route('/admin/workers', methods=['GET', 'POST'])
@role_required('admin')
def admin_workers():
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        # Add a new worker
        name = request.form.get('name', '').strip()
        specialization = request.form.get('specialization', '').strip()
        phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip()
        username = request.form.get('username', '').strip()
        password = request.form.get('password', 'worker123')

        if not name or not specialization or not phone or not username:
            flash("Name, Specialization, Phone, and Username are required.", "danger")
        else:
            # Check unique username
            cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
            if cursor.fetchone():
                flash("Username is already in use.", "danger")
            else:
                hashed_pw = generate_password_hash(password)
                cursor.execute("""
                    INSERT INTO users (username, password_hash, full_name, email, phone, department, role)
                    VALUES (?, ?, ?, ?, ?, 'Maintenance Services', 'worker')
                """, (username, hashed_pw, name, email, phone))
                user_id = cursor.lastrowid

                cursor.execute("""
                    INSERT INTO workers (user_id, name, specialization, phone, email, availability, active_count)
                    VALUES (?, ?, ?, ?, ?, 'Available', 0)
                """, (user_id, name, specialization, phone, email))
                conn.commit()
                flash(f"Worker {name} successfully added to the system.", "success")

    # Fetch workers list
    cursor.execute("""
        SELECT w.*, u.username
        FROM workers w
        LEFT JOIN users u ON w.user_id = u.id
        ORDER BY w.specialization, w.name
    """)
    workers = cursor.fetchall()
    conn.close()

    return render_template('admin_workers.html', workers=workers)

@app.route('/admin/reports')
@role_required('admin')
def admin_reports():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Category breakdown
    cursor.execute("""
        SELECT category, COUNT(*) as count
        FROM complaints
        GROUP BY category
        ORDER BY count DESC
    """)
    category_counts = cursor.fetchall()

    # Status breakdown
    cursor.execute("""
        SELECT status, COUNT(*) as count
        FROM complaints
        GROUP BY status
    """)
    status_counts = cursor.fetchall()

    # Priority breakdown
    cursor.execute("""
        SELECT priority, COUNT(*) as count
        FROM complaints
        GROUP BY priority
    """)
    priority_counts = cursor.fetchall()

    # Worker performance and workload
    cursor.execute("""
        SELECT
            w.name,
            w.specialization,
            w.active_count,
            COUNT(c.id) as total_assigned,
            SUM(CASE WHEN c.status IN ('Resolved', 'Closed') THEN 1 ELSE 0 END) as resolved_count
        FROM workers w
        LEFT JOIN complaints c ON w.id = c.assigned_worker_id
        GROUP BY w.id
        ORDER BY resolved_count DESC
    """)
    worker_stats = cursor.fetchall()

    conn.close()

    return render_template(
        'admin_reports.html',
        category_counts=category_counts,
        status_counts=status_counts,
        priority_counts=priority_counts,
        worker_stats=worker_stats
    )

@app.route('/admin/export-csv')
@role_required('admin')
def export_csv():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            c.complaint_code, c.title, c.category, c.location,
            c.priority, c.status, c.staff_name, w.name as worker_name,
            c.created_at, c.resolved_at
        FROM complaints c
        LEFT JOIN workers w ON c.assigned_worker_id = w.id
        ORDER BY c.created_at DESC
    """)
    rows = cursor.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Complaint Code", "Title", "Category", "Location",
        "Priority", "Status", "Reported By", "Assigned Worker",
        "Created At", "Resolved At"
    ])
    for r in rows:
        writer.writerow([
            r['complaint_code'], r['title'], r['category'], r['location'],
            r['priority'], r['status'], r['staff_name'], r['worker_name'] or 'Unassigned',
            r['created_at'], r['resolved_at'] or 'Pending'
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=campus_maintenance_report.csv"}
    )

# ---------------------------------------------------------
# AJAX / REST APIS (VOICE ASSISTANT & REAL-TIME CHECKS)
# ---------------------------------------------------------

@app.route('/api/voice-process', methods=['POST'])
def api_voice_process():
    data = request.get_json() or {}
    speech_text = data.get('speech_text', '').strip()

    if not speech_text:
        return jsonify({'error': 'No speech text provided.'}), 400

    parsed = ai_engine.parse_voice_complaint(speech_text)
    return jsonify(parsed)

@app.route('/api/check-duplicates', methods=['POST'])
def api_check_duplicates():
    data = request.get_json() or {}
    category = data.get('category', '')
    location = data.get('location', '')
    description = data.get('description', '')
    title = data.get('title', '')
    exclude_id = data.get('exclude_id')

    if not description and not title:
        return jsonify({'duplicates': []})

    duplicates = ai_engine.check_for_duplicates(category, location, description, title, exclude_id)
    return jsonify({'duplicates': duplicates})

@app.route('/api/notifications/mark-read/<int:notif_id>', methods=['POST'])
@login_required
def mark_notification_read(notif_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE notifications SET is_read = 1 WHERE id = ? AND user_id = ?", (notif_id, session['user_id']))
    conn.commit()
    conn.close()
    return jsonify({'status': 'ok'})

# ---------------------------------------------------------
# ERROR HANDLERS
# ---------------------------------------------------------

@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return "<h3>Internal Server Error</h3><p>An unexpected error occurred. Please contact the administrator.</p>", 500

if __name__ == '__main__':
    print("Starting Campus Maintenance Tracker Web App...")
    print("Open http://127.0.0.1:5000 in your browser.")
    app.run(host='127.0.0.1', port=5000, debug=True)
