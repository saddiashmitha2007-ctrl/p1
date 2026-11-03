"""
AI & Intelligent Complaint Processing Engine for Campus Maintenance Tracker.
Provides:
1. Category Classification (Rule-based keyword NLP)
2. Priority Assessment
3. Information Extraction (Location, Title, Category, Priority) for Voice Assistant
4. Duplicate Complaint Detection (Text similarity + Location overlap)
5. Intelligent Worker Matching (Specialization, Availability, Workload Balancing)
6. Preliminary Troubleshooting & Safety Recommendations
"""

import re
from difflib import SequenceMatcher
from database import get_db_connection

CATEGORIES = [
    'Electrical',
    'Plumbing',
    'IT and Networking',
    'Furniture and Carpentry',
    'Cleaning and Sanitation',
    'Building Maintenance'
]

# Keyword dictionaries with weights for accurate categorization
CATEGORY_KEYWORDS = {
    'Electrical': {
        'keywords': [
            'fan', 'light', 'bulb', 'tube', 'tubelight', 'switch', 'socket', 'plug',
            'wire', 'wiring', 'spark', 'short circuit', 'mcb', 'breaker', 'power',
            'electricity', 'current', 'shock', 'fuse', 'inverter', 'voltage',
            'ac', 'air conditioner', 'generator', 'flickering', 'tripped', 'humming'
        ],
        'weight': 1.0
    },
    'Plumbing': {
        'keywords': [
            'water', 'leak', 'leaking', 'leakage', 'tap', 'pipe', 'pipes', 'sink',
            'washbasin', 'drain', 'drainage', 'toilet', 'flush', 'urinal', 'sewage',
            'clog', 'clogged', 'geyser', 'faucet', 'valve', 'dampness', 'overflow',
            'tank', 'washroom', 'restroom', 'drip', 'dripping', 'supply'
        ],
        'weight': 1.0
    },
    'IT and Networking': {
        'keywords': [
            'computer', 'pc', 'laptop', 'wifi', 'wi-fi', 'internet', 'network',
            'router', 'lan', 'cable', 'ethernet', 'printer', 'printing', 'scanner',
            'projector', 'screen', 'keyboard', 'mouse', 'monitor', 'cpu', 'server',
            'software', 'port', 'access point', 'ip address', 'offline', 'firewall'
        ],
        'weight': 1.0
    },
    'Furniture and Carpentry': {
        'keywords': [
            'chair', 'table', 'desk', 'bench', 'door', 'window', 'hinge', 'lock',
            'latch', 'cupboard', 'almirah', 'drawer', 'shelf', 'shelves', 'wood',
            'wooden', 'furniture', 'whiteboard', 'blackboard', 'podium', 'screws',
            'broken leg', 'wheel', 'armrest', 'knob'
        ],
        'weight': 1.0
    },
    'Cleaning and Sanitation': {
        'keywords': [
            'clean', 'cleaning', 'dirty', 'dust', 'dusty', 'trash', 'garbage', 'bin',
            'dustbin', 'overflowing', 'spill', 'sweep', 'mop', 'odor', 'smell',
            'stink', 'spider', 'cobweb', 'pest', 'cockroach', 'insects', 'unhygienic',
            'litter', 'waste', 'sanitizer', 'soap'
        ],
        'weight': 1.0
    },
    'Building Maintenance': {
        'keywords': [
            'wall', 'ceiling', 'roof', 'plaster', 'paint', 'cracks', 'tile', 'tiles',
            'floor', 'flooring', 'glass', 'windowpane', 'stair', 'stairs', 'railing',
            'balcony', 'pillar', 'concrete', 'seepage', 'brick', 'doorframe',
            'blinds', 'curtain', 'structure', 'facade'
        ],
        'weight': 1.0
    }
}

# Priority indicators
PRIORITY_TRIGGERS = {
    'Critical': [
        'fire', 'spark', 'smoke', 'short circuit', 'electric shock', 'burst pipe',
        'flooding', 'flood', 'collapse', 'server down', 'gas leak', 'urgent emergency',
        'severe danger', 'hazard', 'bleeding', 'explosion'
    ],
    'High': [
        'not working', 'completely stopped', 'exam', 'lab class', 'all computers',
        'power outage', 'main switch', 'washroom unusable', 'water overflow',
        'door locked stuck', 'projector dead', 'urgent', 'asap', 'high'
    ],
    'Medium': [
        'leaking', 'broken', 'flickering', 'fan slow', 'loose', 'noisy',
        'dirty', 'smell', 'dustbin full', 'drawer stuck'
    ],
    'Low': [
        'minor', 'paint', 'scratched', 'squeaky', 'dust', 'extra chair',
        'low priority', 'whenever free', 'when possible'
    ]
}

TROUBLESHOOTING_GUIDE = {
    'Electrical': (
        "1. Check if the localized switch or sub-meter MCB has tripped.\n"
        "2. If sparks, smoking, or burning smells occur, immediately turn off the main room switch and do not touch any wiring.\n"
        "3. Test other appliances on the same board to identify if it is an individual unit failure or general circuit outage."
    ),
    'Plumbing': (
        "1. In case of active flooding or heavy pipe leaks, turn the local angle/isolating valve clockwise to shut off the water supply immediately.\n"
        "2. Place a temporary bucket or towel beneath the leak to protect floor surfaces and prevent slipping.\n"
        "3. For clogged sinks or basins, avoid pouring harsh unauthorized chemicals into institutional drains."
    ),
    'IT and Networking': (
        "1. Check if both the power cable and Ethernet LAN cable are firmly seated in their ports.\n"
        "2. Verify if the Wi-Fi router or switch port shows a green link light.\n"
        "3. Try power-cycling the device once (wait 15 seconds before powering on). Avoid pressing hardware factory reset buttons on campus network equipment."
    ),
    'Furniture and Carpentry': (
        "1. If a chair or desk is unstable or has loose screws, place it aside with a 'Do Not Use' tag to prevent injury.\n"
        "2. For jammed locks or doors, do not force the handle with excessive leverage to avoid snapping the internal cylinder."
    ),
    'Cleaning and Sanitation': (
        "1. If chemical or liquid spillage has occurred on tiled flooring, mark off the area or place a wet floor sign.\n"
        "2. For overflowing bins, place an additional temporary liner bag if available until housekeeping staff arrives."
    ),
    'Building Maintenance': (
        "1. For cracked glass panes or loose ceiling plaster, cordon off the area underneath immediately.\n"
        "2. Keep windows closed during stormy conditions to prevent further structural or moisture intrusion."
    )
}

def classify_complaint(text):
    """
    Classifies complaint text into one of the 6 maintenance categories.
    Returns: (category, confidence_score)
    """
    if not text:
        return 'Building Maintenance', 0.1

    text_lower = text.lower()
    scores = {cat: 0 for cat in CATEGORIES}

    for cat, data in CATEGORY_KEYWORDS.items():
        for kw in data['keywords']:
            # Search as word boundary or exact phrase
            pattern = r'\b' + re.escape(kw) + r'\b'
            matches = len(re.findall(pattern, text_lower))
            if matches > 0:
                scores[cat] += matches * data['weight']

    best_category = max(scores, key=scores.get)
    max_score = scores[best_category]

    if max_score == 0:
        # Default fallback
        return 'Building Maintenance', 0.2

    # Calculate approximate confidence
    total_score = sum(scores.values())
    confidence = min(0.95, round(max_score / total_score, 2)) if total_score > 0 else 0.5
    return best_category, confidence

def determine_priority(text):
    """
    Assesses urgency based on trigger keywords and stems.
    Returns: 'Critical' | 'High' | 'Medium' | 'Low'
    """
    text_lower = text.lower()

    for prio in ['Critical', 'High', 'Low']:
        for trigger in PRIORITY_TRIGGERS[prio]:
            # Allow matching root stem with common word boundaries or endings
            pattern = r'\b' + re.escape(trigger) + r'(?:s|ing|ed|es)?\b'
            if re.search(pattern, text_lower):
                return prio

    # If no explicit critical/high/low keywords matched, default to Medium
    return 'Medium'

def extract_location(text):
    """
    Extracts room numbers, block names, labs, departments from spoken or written text.
    Examples: 'Room 204', 'Lab 3', 'Science Block Room 102', 'Library 2nd Floor'
    """
    patterns = [
        r'(?:in|at|near|inside|around)?\s*([A-Za-z0-9\s]+(?:Block|Building|Hall|Lab|Laboratory|Library|Canteen|Auditorium|Complex|Wing|Floor|Restroom|Washroom)\s*(?:Room\s*[0-9A-Za-z\-]+)?)',
        r'(?:Room|Rm\.?|Cabin|Cabin no\.?)\s*#?\s*([0-9A-Za-z\-]+)',
        r'(?:Lab|Laboratory)\s*#?\s*([0-9A-Za-z\-]+)',
        r'(?:Floor)\s*#?\s*([0-9A-Za-z\-]+)',
    ]

    for pat in patterns:
        match = re.search(pat, text, re.IGNORECASE)
        if match:
            extracted = match.group(0).strip()
            # Clean up leading prepositions
            extracted = re.sub(r'^(in|at|near|inside|around)\s+', '', extracted, flags=re.IGNORECASE)
            if len(extracted) >= 3:
                return extracted.title()

    return ""

def parse_voice_complaint(voice_text):
    """
    Processes raw text captured from speech recognition into structured complaint fields.
    Returns:
    {
        'transcript': original text,
        'title': generated concise summary title,
        'category': classified category,
        'priority': assessed priority level,
        'location': extracted location or empty string,
        'troubleshooting': suggested initial steps,
        'missing_fields': list of fields user should confirm or provide
    }
    """
    voice_text = (voice_text or "").strip()
    category, confidence = classify_complaint(voice_text)
    priority = determine_priority(voice_text)
    location = extract_location(voice_text)

    # Generate a clean title
    cleaned = re.sub(r'^(hi|hello|please note that|i want to report that|there is an issue with)\s*', '', voice_text, flags=re.IGNORECASE)
    cleaned_words = cleaned.split()
    if len(cleaned_words) > 10:
        title = " ".join(cleaned_words[:10]) + "..."
    else:
        title = cleaned.capitalize()

    missing_fields = []
    if not location:
        missing_fields.append('location')
    if len(voice_text) < 10:
        missing_fields.append('description')

    return {
        'transcript': voice_text,
        'title': title,
        'category': category,
        'priority': priority,
        'location': location,
        'confidence': confidence,
        'troubleshooting': TROUBLESHOOTING_GUIDE.get(category, "Please await maintenance inspection."),
        'missing_fields': missing_fields
    }

def calculate_similarity(text1, text2):
    """
    Calculates composite text similarity using SequenceMatcher and token overlap.
    """
    if not text1 or not text2:
        return 0.0

    t1 = text1.lower()
    t2 = text2.lower()

    # Sequence matcher ratio
    seq_ratio = SequenceMatcher(None, t1, t2).ratio()

    # Word set Jaccard similarity
    words1 = set(re.findall(r'\b\w{3,}\b', t1))
    words2 = set(re.findall(r'\b\w{3,}\b', t2))

    if not words1 or not words2:
        jaccard = 0.0
    else:
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        jaccard = intersection / union if union > 0 else 0.0

    # Composite similarity weighted
    return round((0.45 * seq_ratio) + (0.55 * jaccard), 3)

def check_for_duplicates(category, location, description, title="", exclude_id=None):
    """
    Scans the database for active/pending complaints in the same or similar location
    and calculates semantic text similarity.
    Returns: list of dicts with match details, ordered by highest similarity.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
        SELECT c.*, w.name as worker_name
        FROM complaints c
        LEFT JOIN workers w ON c.assigned_worker_id = w.id
        WHERE c.status NOT IN ('Closed', 'Resolved')
    """
    params = []
    if exclude_id:
        query += " AND c.id != ?"
        params.append(exclude_id)

    cursor.execute(query, params)
    active_complaints = cursor.fetchall()
    conn.close()

    duplicates = []
    new_text = f"{title} {description}".strip()
    new_loc = (location or "").lower().strip()

    for row in active_complaints:
        existing_text = f"{row['title']} {row['description']}".strip()
        existing_loc = (row['location'] or "").lower().strip()

        # Text similarity
        sim_score = calculate_similarity(new_text, existing_text)

        # Location similarity boost
        loc_match = False
        if new_loc and existing_loc:
            # Check for common room numbers or building matches
            loc_sim = SequenceMatcher(None, new_loc, existing_loc).ratio()
            if loc_sim > 0.6 or new_loc in existing_loc or existing_loc in new_loc:
                loc_match = True
                sim_score = min(1.0, sim_score + 0.25)

        # Category match boost
        if row['category'] == category:
            sim_score = min(1.0, sim_score + 0.1)

        # Candidate threshold: >= 45% similarity
        if sim_score >= 0.45:
            duplicates.append({
                'complaint_id': row['id'],
                'complaint_code': row['complaint_code'],
                'title': row['title'],
                'description': row['description'],
                'category': row['category'],
                'location': row['location'],
                'status': row['status'],
                'priority': row['priority'],
                'assigned_worker': row['worker_name'] or 'Unassigned',
                'created_at': row['created_at'],
                'similarity_score': int(sim_score * 100),
                'location_match': loc_match
            })

    # Sort descending by similarity
    duplicates.sort(key=lambda x: x['similarity_score'], reverse=True)
    return duplicates

def find_best_worker(category):
    """
    Finds the most suitable maintenance worker based on:
    1. Specialization matching the complaint category
    2. Availability ('Available' preferred over 'Busy', skips 'On Leave')
    3. Workload balancing: Worker with lowest active_count
    Returns: worker sqlite3.Row or None
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # First attempt: Matching specialization and 'Available' status, sorted by active_count ASC
    cursor.execute("""
        SELECT * FROM workers
        WHERE specialization = ? AND availability = 'Available'
        ORDER BY active_count ASC, id ASC
        LIMIT 1
    """, (category,))
    worker = cursor.fetchone()

    # Second attempt: If no 'Available' worker, pick 'Busy' worker with lowest load
    if not worker:
        cursor.execute("""
            SELECT * FROM workers
            WHERE specialization = ? AND availability = 'Busy'
            ORDER BY active_count ASC, id ASC
            LIMIT 1
        """, (category,))
        worker = cursor.fetchone()

    conn.close()
    return worker

def get_troubleshooting_tips(category):
    """Returns recommended troubleshooting steps for a category."""
    return TROUBLESHOOTING_GUIDE.get(category, "Notify maintenance team if unsafe.")
