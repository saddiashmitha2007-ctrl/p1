# FixIt Campus &bull; Voice-Enabled Campus Maintenance Tracker

A complete, production-ready web application built with **Python, Flask, SQLite, HTML5, CSS3, and JavaScript**. Featuring the modern **FixIt Campus** technical forest green grid & warm safety orange UI theme with intelligent worker matching, real-time voice speech assistant, and duplicate complaint prevention.

---

## 🌟 Key Features

1. **🎙️ AI Voice Assistant & Speech Input**:
   - One-click microphone button using the browser's Web Speech API.
   - Converts spoken complaints directly into text in real time.
   - Automatically extracts complaint title, maintenance category, room/building location, and priority level.
   - Prompts the user if critical information (such as room number) is missing.
   - Graceful fallback to manual keyboard entry when speech is unavailable.

2. **🏷️ Intelligent Complaint Processing & Classification**:
   - Classifies complaints into 6 campus maintenance categories:
     - **Electrical**: Fans, lights, switches, fuses, wiring, tripped breakers.
     - **Plumbing**: Leaking taps, pipes, sinks, washrooms, flush tanks.
     - **IT and Networking**: Computers, Wi-Fi routers, printers, LAN cables.
     - **Furniture and Carpentry**: Broken chairs, desks, doors, hinges, locks.
     - **Cleaning and Sanitation**: Overflowing bins, spills, dusty corridors.
     - **Building Maintenance**: Damaged walls, ceiling leaks, cracked tiles, glass panes.
   - Evaluates urgency keywords into **Critical**, **High**, **Medium**, or **Low** priority.

3. **🔍 Real-Time Duplicate Complaint Detection**:
   - Compares incoming complaints with active open issues in the same room/building using semantic text similarity.
   - Displays potential duplicates with percentage match so staff can confirm if their issue is already reported, preventing redundant tickets.

4. **👷 Intelligent Worker Matching & Workload Balancing**:
   - Automatically matches the complaint to a technician specialized in that category.
   - Selects available workers with the lowest active workload to prevent bottlenecks.
   - If no specialized worker is available, flags the issue for Administrator assignment.
   - Allows Administrators to override or reassign at any time.

5. **💡 Automated Troubleshooting & Safety Tips**:
   - Recommends immediate safety precautions and preliminary troubleshooting steps (e.g. isolating water valves, switching off circuit breakers).

6. **📊 Administrator & Worker Portals**:
   - **Staff**: Voice/text submission, status tracking, notifications, complaint reopen capability.
   - **Worker**: View assigned jobs, acknowledge work in progress, submit repair notes, mark resolved, toggle availability (Available / Busy / On Leave).
   - **Administrator**: Comprehensive dashboard, master complaints log, technician onboarding and workload rebalancing, and interactive Chart.js analytics (Category distribution, status breakdown, technician resolution metrics, CSV export).

---

## 📂 Project Structure

```
d:\16/
├── app.py                     # Main Flask web application, routing, access controls, sessions, APIs
├── database.py                # SQLite schema creation, foreign keys, seeding initial workers & data
├── ai_engine.py               # Rule-based NLP classifier, priority evaluator, duplicate finder, worker matcher
├── requirements.txt           # Python dependencies (Flask, Werkzeug)
├── test_app.py                # Automated end-to-end unit test suite
├── campus_maintenance.db      # SQLite database (auto-created on startup)
├── README.md                  # Complete documentation and setup manual
├── static/
│   ├── css/
│   │   └── style.css          # Responsive, modern CSS styling with accessible badges and mic pulse
│   └── js/
│       ├── voice_assistant.js # Browser Web Speech API handler, live transcription & auto-filling
│       ├── tracker.js         # Real-time duplicate check with debouncing & interactive linking
│       └── charts.js          # Chart.js graphs for administrator analytics
└── templates/
    ├── base.html              # Core layout template with navigation, notifications dropdown, and footer
    ├── index.html             # Landing page with hero banner, live KPI counters, quick search
    ├── login.html             # Multi-role login page with test credential quick-links
    ├── register.html          # Staff registration form with validation and password hashing
    ├── submit_complaint.html  # Voice & text complaint submission with live duplicate warning
    ├── track.html             # Public / Staff complaint search and status filter page
    ├── complaint_detail.html  # Full ticket view with progress timeline, repair notes, and reopen form
    ├── admin_dashboard.html   # Administrator master control center and technician assign modal
    ├── admin_workers.html     # Worker management, availability toggle, and new technician onboarding
    ├── admin_reports.html     # Visual analytics charts and CSV report export
    ├── worker_dashboard.html  # Mobile-friendly technician dashboard for updating jobs
    └── 404.html               # User-friendly page not found template
```

---

## 🚀 Quick Start Guide

### Step 1: Install Python Dependencies
Open your terminal (PowerShell, Command Prompt, or Terminal) in the project directory:
```bash
pip install -r requirements.txt
```

*(Note: SQLite is already built into Python, so no external database installation is required!)*

### Step 2: Initialize Database & Seed Sample Records
Run `database.py` once (or simply start `app.py`, which initializes and seeds the database automatically if empty):
```bash
python database.py
```

### Step 3: Start the Flask Application
```bash
python app.py
```
You will see output in the terminal:
```
Starting Campus Maintenance Tracker Web App...
Open http://127.0.0.1:5000 in your browser.
 * Running on http://127.0.0.1:5000
```

### Step 4: Open in Your Browser
Open Chrome, Edge, Firefox, or Safari and navigate to:
```
http://127.0.0.1:5000
```

---

## 🔑 Demo Test Accounts

The database comes pre-seeded with accounts ready for immediate testing:

| Role | Username | Password | Purpose |
| :--- | :--- | :--- | :--- |
| **Administrator** | `admin` | `admin123` | Facilities Admin: View all tickets, reassign workers, view charts, export CSV |
| **Faculty Staff** | `prof_sharma` | `staff123` | Department Faculty: Report issues via voice/text, track tickets, reopen |
| **Lab Assistant** | `lab_asst` | `staff123` | Computer Lab Staff: Report network/hardware issues |
| **Worker (Electrical)** | `worker_elec1` | `worker123` | Rajesh Sharma: Electrical technician dashboard |
| **Worker (Plumbing)** | `worker_plumb` | `worker123` | Amit Kumar: Plumbing technician dashboard |
| **Worker (IT/Network)** | `worker_it` | `worker123` | Sunita Patel: IT and network technician dashboard |

---

## 🧪 Demonstration & Testing Workflow

You can verify the entire lifecycle from complaint creation to resolution in 5 simple steps:

### Test Case 1: Voice Complaint Submission
1. Navigate to **"Report Problem"** (`http://127.0.0.1:5000/submit-complaint`).
2. Click the **Microphone** icon. Speak clearly:
   > *"The fan in Room 204 is not working"*
3. Notice how the AI engine:
   - Sets Title to **"The fan in Room 204 is not working"**.
   - Selects Category as **Electrical**.
   - Extracts Location as **Room 204**.
   - Sets Priority according to urgency.
   - Shows recommended immediate safety/troubleshooting tips.
4. Click **"Submit Complaint"**.
5. The system automatically assigns the least busy available Electrical technician (`Rajesh Sharma`)!

### Test Case 2: Duplicate Detection
1. On the complaint submission page, type:
   > Location: `Science Block, Room 204`
   > Description: `Ceiling fan is not spinning and making noise in room 204`
2. Notice the yellow alert appears in real-time:
   > **⚠️ Similar Open Complaint Detected: CMP-1001 (90% Match)**
3. Click *"This is the same problem"* to link the ticket and avoid double-booking technician time.

### Test Case 3: Worker Job Execution
1. Sign in as `worker_elec1` with password `worker123`.
2. The technician dashboard displays your assigned active complaints.
3. Click **"Start Work"** &rarr; status updates to **In Progress**.
4. Enter repair notes: *"Replaced start capacitor and tested fan on high speed."*
5. Click **"Mark Resolved"** &rarr; complaint moves to **Resolved** status and technician workload decreases.

### Test Case 4: Reopening an Unresolved Problem
1. Log in as `prof_sharma` or `admin`.
2. View the resolved complaint detail page.
3. If the fan is still vibrating, fill in the Reopen box: *"Fan started rattling after 20 minutes"*.
4. Click **"Reopen Complaint"** &rarr; status becomes **Reopened**, technician active count increases, and technician receives an instant notification.

### Test Case 5: Administrator Reassignment & Analytics
1. Sign in as `admin` with password `admin123`.
2. Visit **"Admin Dashboard"** &rarr; filter complaints by Category, Priority, or Status.
3. Click **"Assign"** on any ticket to override the worker assignment.
4. Visit **"Reports & Stats"** to see live Chart.js visual graphs and click **"Export CSV"** to download the master maintenance spreadsheet.

---

## 🛠️ Automated Unit Tests
To run the full suite of automated end-to-end tests:
```bash
python test_app.py
```
Expected output:
```
........
----------------------------------------------------------------------
Ran 8 tests in 1.67s

OK
```

---

## ❓ Troubleshooting & FAQs

- **Microphone button does not start listening**:
  - The Web Speech API is supported natively in modern Chromium-based browsers (Google Chrome, Microsoft Edge, Brave, Opera) and Safari.
  - If your browser displays a permission prompt, click **"Allow"** to grant microphone access.
  - If voice recognition is unsupported or disabled in your browser, the system gracefully shows a clear notice and lets you type directly into the form.
- **Port 5000 is already in use**:
  - Run with an alternative port:
    ```bash
    flask run --port=5001
    ```
- **Where is the database stored?**:
  - All data is stored in the single self-contained file `campus_maintenance.db` in the project root. If you ever want to reset the database to sample data, simply delete `campus_maintenance.db` and run `python database.py`.
