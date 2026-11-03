import unittest
import json
from app import app
from database import get_db_connection, init_db, seed_sample_data
import ai_engine

class CampusMaintenanceTrackerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        seed_sample_data()
        cls.client = app.test_client()
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False

    def test_01_home_page(self):
        """Test home landing page renders successfully."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"FixIt Campus", response.data)
        self.assertIn(b"Quick Complaint Lookup", response.data)

    def test_02_voice_processing_api(self):
        """Test voice transcript parsing and AI extraction."""
        payload = {"speech_text": "The ceiling fan in Room 204 of Science Block is sparking and not working"}
        response = self.client.post('/api/voice-process',
                                  data=json.dumps(payload),
                                  content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data.decode('utf-8'))
        self.assertEqual(data['category'], 'Electrical')
        self.assertEqual(data['priority'], 'Critical')
        self.assertIn("Room 204", data['location'])
        self.assertTrue(len(data['troubleshooting']) > 0)

    def test_03_duplicate_detection_api(self):
        """Test similarity matching against existing complaints."""
        payload = {
            "title": "Ceiling fan making noise",
            "description": "Fan in Room 204 not working and humming",
            "location": "Science Block, Room 204",
            "category": "Electrical"
        }
        response = self.client.post('/api/check-duplicates',
                                  data=json.dumps(payload),
                                  content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data.decode('utf-8'))
        self.assertGreaterEqual(len(data['duplicates']), 1)
        self.assertEqual(data['duplicates'][0]['complaint_code'], 'CMP-1001')

    def test_04_staff_registration_and_login(self):
        """Test registering a new staff member and logging in."""
        import time
        uname = f"staff_test_{int(time.time())}"
        reg_data = {
            "full_name": "Test Faculty Member",
            "username": uname,
            "email": "faculty99@campus.edu",
            "phone": "9876500099",
            "department": "Mechanical Engineering",
            "password": "password123",
            "confirm_password": "password123"
        }
        response = self.client.post('/register', data=reg_data, follow_redirects=True)
        self.assertEqual(response.status_code, 200)

        # Logout
        self.client.get('/logout')

        # Login
        login_data = {
            "username": uname,
            "password": "password123",
            "role": "staff"
        }
        res_login = self.client.post('/login', data=login_data, follow_redirects=True)
        self.assertEqual(res_login.status_code, 200)
        self.assertIn(b"Welcome back, Test Faculty Member!", res_login.data)

    def test_05_complaint_submission_and_auto_worker_matching(self):
        """Test submitting a new plumbing complaint and auto-matching to available plumber."""
        submission_data = {
            "staff_name": "Dr. Anita Roy",
            "staff_contact": "9876543102",
            "title": "Severe Water Pipe Burst in Chemistry Lab",
            "description": "Main water supply line burst near basin 4 flooding the lab with water.",
            "category": "Plumbing",
            "location": "Chemistry Block, Ground Floor Lab 2",
            "priority": "Critical",
            "is_voice_submitted": 1,
            "is_duplicate_confirmed": 0
        }
        response = self.client.post('/submit-complaint', data=submission_data, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"submitted successfully", response.data)

        # Check DB for assignment
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM complaints WHERE title LIKE '%Severe Water Pipe Burst%'")
        c = cursor.fetchone()
        self.assertIsNotNone(c)
        self.assertEqual(c['category'], 'Plumbing')
        self.assertEqual(c['priority'], 'Critical')
        self.assertEqual(c['status'], 'Assigned')
        self.assertIsNotNone(c['assigned_worker_id'])
        conn.close()

    def test_06_worker_status_update_and_resolution(self):
        """Test worker login, viewing assigned tasks, and resolving with notes."""
        # Login as electrical worker
        self.client.post('/login', data={"username": "worker_elec1", "password": "worker123", "role": "worker"}, follow_redirects=True)

        res = self.client.get('/worker/dashboard')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Technician Service Portal", res.data)

        # Fetch complaint CMP-1001 ID
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM complaints WHERE complaint_code = 'CMP-1001'")
        cmp_id = cursor.fetchone()['id']
        conn.close()

        # Update to Resolved with note
        res_update = self.client.post('/worker/update-status', data={
            "complaint_id": cmp_id,
            "status": "Resolved",
            "repair_note": "Replaced faulty start capacitor and re-tightened blade brackets. Operating quietly now."
        }, follow_redirects=True)
        self.assertEqual(res_update.status_code, 200)

        # Verify in DB
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM complaints WHERE id = ?", (cmp_id,))
        self.assertEqual(cursor.fetchone()['status'], 'Resolved')
        conn.close()

    def test_07_reopen_complaint(self):
        """Test staff reopening a resolved complaint."""
        # Login as admin to reopen
        self.client.post('/login', data={"username": "admin", "password": "admin123", "role": "admin"}, follow_redirects=True)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM complaints WHERE complaint_code = 'CMP-1001'")
        cmp_id = cursor.fetchone()['id']
        conn.close()

        res_reopen = self.client.post(f'/complaint/{cmp_id}/reopen', data={
            "reason": "The fan started vibrating loudly again after 20 minutes of continuous running."
        }, follow_redirects=True)
        self.assertEqual(res_reopen.status_code, 200)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM complaints WHERE id = ?", (cmp_id,))
        self.assertEqual(cursor.fetchone()['status'], 'Reopened')
        conn.close()

    def test_08_admin_dashboard_and_worker_management(self):
        """Test admin dashboard, reports, worker onboarding, and CSV export."""
        import time
        # Login as admin
        self.client.post('/login', data={"username": "admin", "password": "admin123", "role": "admin"}, follow_redirects=True)

        # Admin dashboard
        res_dash = self.client.get('/admin/dashboard')
        self.assertEqual(res_dash.status_code, 200)
        self.assertIn(b"Facilities Administrator Dashboard", res_dash.data)

        # Admin reports
        res_rep = self.client.get('/admin/reports')
        self.assertEqual(res_rep.status_code, 200)
        self.assertIn(b"Maintenance Analytics & Reports", res_rep.data)

        # Admin CSV export
        res_csv = self.client.get('/admin/export-csv')
        self.assertEqual(res_csv.status_code, 200)
        self.assertEqual(res_csv.mimetype, 'text/csv')
        self.assertIn(b"Complaint Code,Title,Category", res_csv.data)

        # Admin add worker with unique username
        uname = f"w_test_{int(time.time())}"
        worker_data = {
            "name": "Kailash Chand",
            "specialization": "Building Maintenance",
            "phone": "9876543299",
            "email": "kailash.civil@campus.edu",
            "username": uname,
            "password": "worker123"
        }
        res_w = self.client.post('/admin/workers', data=worker_data, follow_redirects=True)
        self.assertEqual(res_w.status_code, 200)
        self.assertIn(b"Worker Kailash Chand successfully added", res_w.data)

if __name__ == '__main__':
    unittest.main()
