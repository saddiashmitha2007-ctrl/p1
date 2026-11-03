import sqlite3
import os
from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "campus_maintenance.db")

def get_db_connection():
    """Returns a SQLite connection with row access by column name."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    """Initializes the database schema and seeds initial sample records."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Users Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        full_name TEXT NOT NULL,
        email TEXT,
        phone TEXT,
        department TEXT,
        role TEXT NOT NULL CHECK(role IN ('staff', 'admin', 'worker')),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 2. Workers Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS workers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        name TEXT NOT NULL,
        specialization TEXT NOT NULL,
        phone TEXT NOT NULL,
        email TEXT,
        availability TEXT NOT NULL DEFAULT 'Available' CHECK(availability IN ('Available', 'Busy', 'On Leave')),
        active_count INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL
    )
    """)

    # 3. Complaints Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS complaints (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        complaint_code TEXT UNIQUE NOT NULL,
        staff_id INTEGER,
        staff_name TEXT NOT NULL,
        staff_contact TEXT,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        category TEXT NOT NULL,
        location TEXT NOT NULL,
        priority TEXT NOT NULL DEFAULT 'Medium' CHECK(priority IN ('Critical', 'High', 'Medium', 'Low')),
        status TEXT NOT NULL DEFAULT 'Submitted' CHECK(status IN ('Submitted', 'Assigned', 'In Progress', 'Resolved', 'Closed', 'Reopened')),
        assigned_worker_id INTEGER,
        troubleshooting_tips TEXT,
        is_voice_submitted INTEGER DEFAULT 0,
        is_duplicate_confirmed INTEGER DEFAULT 0,
        duplicate_of_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        resolved_at TIMESTAMP,
        FOREIGN KEY(staff_id) REFERENCES users(id) ON DELETE SET NULL,
        FOREIGN KEY(assigned_worker_id) REFERENCES workers(id) ON DELETE SET NULL,
        FOREIGN KEY(duplicate_of_id) REFERENCES complaints(id) ON DELETE SET NULL
    )
    """)

    # 4. Repair Notes Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS repair_notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        complaint_id INTEGER NOT NULL,
        author_id INTEGER,
        author_name TEXT NOT NULL,
        author_role TEXT NOT NULL,
        note TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(complaint_id) REFERENCES complaints(id) ON DELETE CASCADE,
        FOREIGN KEY(author_id) REFERENCES users(id) ON DELETE SET NULL
    )
    """)

    # 5. Status History Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS status_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        complaint_id INTEGER NOT NULL,
        changed_by_id INTEGER,
        changed_by_name TEXT NOT NULL,
        old_status TEXT,
        new_status TEXT NOT NULL,
        remarks TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(complaint_id) REFERENCES complaints(id) ON DELETE CASCADE,
        FOREIGN KEY(changed_by_id) REFERENCES users(id) ON DELETE SET NULL
    )
    """)

    # 6. Notifications Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        link TEXT,
        is_read INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    conn.commit()
    conn.close()

def seed_sample_data():
    """Seeds default administrators, workers, staff members, and initial complaints."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Check if admin already exists
    cursor.execute("SELECT id FROM users WHERE username = 'admin'")
    if cursor.fetchone():
        conn.close()
        return

    # Seed Admin Account
    admin_pw = generate_password_hash("admin123")
    cursor.execute("""
        INSERT INTO users (username, password_hash, full_name, email, phone, department, role)
        VALUES ('admin', ?, 'Campus Facilities Administrator', 'facilities.admin@campus.edu', '9876543000', 'Estate & Facilities', 'admin')
    """, (admin_pw,))
    admin_id = cursor.lastrowid

    # Seed Staff Accounts
    staff_pw = generate_password_hash("staff123")
    staff_members = [
        ('prof_sharma', 'Dr. Ramesh Sharma', 'r.sharma@campus.edu', '9876543101', 'Computer Science & Engineering', 'staff'),
        ('dr_anita', 'Dr. Anita Roy', 'anita.roy@campus.edu', '9876543102', 'Department of Physics', 'staff'),
        ('lab_asst', 'Priya Nair', 'priya.nair@campus.edu', '9876543103', 'Electronics Hardware Lab', 'staff'),
    ]

    staff_ids = {}
    for uname, fname, email, phone, dept, role in staff_members:
        cursor.execute("""
            INSERT INTO users (username, password_hash, full_name, email, phone, department, role)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (uname, staff_pw, fname, email, phone, dept, role))
        staff_ids[uname] = cursor.lastrowid

    # Seed Workers and their user accounts
    worker_pw = generate_password_hash("worker123")
    workers_data = [
        ('worker_elec1', 'Rajesh Sharma', 'Electrical', '9876543201', 'rajesh.elec@campus.edu', 'Available'),
        ('worker_elec2', 'Suresh Rao', 'Electrical', '9876543202', 'suresh.elec@campus.edu', 'Available'),
        ('worker_plumb', 'Amit Kumar', 'Plumbing', '9876543203', 'amit.plumb@campus.edu', 'Available'),
        ('worker_it', 'Sunita Patel', 'IT and Networking', '9876543204', 'sunita.it@campus.edu', 'Available'),
        ('worker_furn', 'Mohan Verma', 'Furniture and Carpentry', '9876543205', 'mohan.carpentry@campus.edu', 'Available'),
        ('worker_clean', 'Lakshmi Devi', 'Cleaning and Sanitation', '9876543206', 'lakshmi.sanitation@campus.edu', 'Available'),
        ('worker_bldg', 'Vikram Singh', 'Building Maintenance', '9876543207', 'vikram.civil@campus.edu', 'Available')
    ]

    worker_ids = {}
    for uname, name, spec, phone, email, avail in workers_data:
        # Create user account for worker login
        cursor.execute("""
            INSERT INTO users (username, password_hash, full_name, email, phone, department, role)
            VALUES (?, ?, ?, ?, ?, 'Maintenance Services', 'worker')
        """, (uname, worker_pw, name, email, phone))
        uid = cursor.lastrowid

        # Insert worker profile
        cursor.execute("""
            INSERT INTO workers (user_id, name, specialization, phone, email, availability, active_count)
            VALUES (?, ?, ?, ?, ?, ?, 0)
        """, (uid, name, spec, phone, email, avail))
        worker_ids[spec] = cursor.lastrowid

    # Seed Some Initial Real-world Complaints
    sample_complaints = [
        (
            'CMP-1001', staff_ids['prof_sharma'], 'Dr. Ramesh Sharma', '9876543101',
            'Ceiling Fan Not Working in Room 204',
            'The regulator is turned on full speed, but the ceiling fan makes a humming noise and fails to spin in Science Block Room 204.',
            'Electrical', 'Science Block, Room 204', 'High', 'Assigned',
            1, # Assigned to Rajesh Sharma (Electrical)
            'Check circuit breaker MCB 4 in floor sub-panel. Test capacitor on fan motor.',
            0
        ),
        (
            'CMP-1002', staff_ids['dr_anita'], 'Dr. Anita Roy', '9876543102',
            'Water Leakage Under Washbasin',
            'Constant high-pressure water leaking from the cold water inlet pipe under the sink in 2nd Floor Staff Restroom.',
            'Plumbing', 'Main Admin Building, 2nd Floor Washroom', 'Critical', 'In Progress',
            3, # Amit Kumar (Plumbing)
            'Turn the angle valve clockwise to shut off supply immediately to prevent flooding.',
            0
        ),
        (
            'CMP-1003', staff_ids['lab_asst'], 'Priya Nair', '9876543103',
            'Lab Wi-Fi Access Point Dropping Connections',
            'Wi-Fi router AP-CS-02 restarts repeatedly. All 30 student desktop machines in Computer Lab 3 cannot connect to the campus network.',
            'IT and Networking', 'Technology Block, Computer Lab 3', 'High', 'Assigned',
            4, # Sunita Patel (IT)
            'Check POE switch port LED status. Verify uplink cable connection.',
            1
        ),
        (
            'CMP-1004', staff_ids['prof_sharma'], 'Dr. Ramesh Sharma', '9876543101',
            'Broken Desk Hinge and Loose Chair Legs',
            'Two student chairs have loose screws and one desk front hinge is detached, posing a safety hazard.',
            'Furniture and Carpentry', 'Academic Block B, Lecture Hall 102', 'Medium', 'Resolved',
            5, # Mohan Verma
            'Secure area and keep defective furniture aside.',
            0
        ),
        (
            'CMP-1005', staff_ids['dr_anita'], 'Dr. Anita Roy', '9876543102',
            'Overflowing Trash Bins in Central Corridor',
            'Trash bins near elevator lobby are completely full and waste is spilling over onto the floor.',
            'Cleaning and Sanitation', 'Library Complex, Ground Floor Corridor', 'Medium', 'Submitted',
            None,
            'Request housekeeping staff to deploy temporary heavy-duty bin liners.',
            0
        ),
    ]

    for code, sid, sname, scontact, title, desc, cat, loc, prio, stat, wid, tips, is_voice in sample_complaints:
        cursor.execute("""
            INSERT INTO complaints (
                complaint_code, staff_id, staff_name, staff_contact,
                title, description, category, location, priority,
                status, assigned_worker_id, troubleshooting_tips, is_voice_submitted
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (code, sid, sname, scontact, title, desc, cat, loc, prio, stat, wid, tips, is_voice))
        cid = cursor.lastrowid

        # Insert status history
        cursor.execute("""
            INSERT INTO status_history (complaint_id, changed_by_id, changed_by_name, old_status, new_status, remarks)
            VALUES (?, ?, 'System', NULL, ?, 'Initial complaint logging')
        """, (cid, admin_id, stat))

        # If assigned, update worker active_count and add repair note or notification
        if wid:
            cursor.execute("UPDATE workers SET active_count = active_count + 1 WHERE id = ?", (wid,))
            # Fetch worker user_id to notify
            cursor.execute("SELECT user_id, name FROM workers WHERE id = ?", (wid,))
            w_row = cursor.fetchone()
            if w_row and w_row['user_id']:
                cursor.execute("""
                    INSERT INTO notifications (user_id, title, message, link)
                    VALUES (?, 'New Task Assigned', ?, ?)
                """, (w_row['user_id'], f"You have been assigned complaint {code}: {title}", f"/complaints/{cid}"))

        if stat == 'Resolved':
            cursor.execute("""
                INSERT INTO repair_notes (complaint_id, author_id, author_name, author_role, note)
                VALUES (?, ?, 'Mohan Verma', 'worker', 'Replaced 4 screws with heavy duty anchors and welded the hinge bracket. Tested for weight support.')
            """, (cid, admin_id))
            cursor.execute("UPDATE complaints SET resolved_at = CURRENT_TIMESTAMP WHERE id = ?", (cid,))

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    seed_sample_data()
    print("Database successfully initialized and seeded with sample workers, users, and complaints.")
