import sqlite3
import os
from datetime import datetime

DB_NAME = os.path.join(os.path.dirname(__file__), "smart_ticket_engine.db")

def get_connection():
    """Returns a connection to the SQLite database."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes the database schema (idempotent)."""
    conn = get_connection()
    cursor = conn.cursor()

    # 1. Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            department TEXT,
            company_name TEXT
        )
    """)

    # 2. Tickets table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT,
            employee_name TEXT,
            employee_email TEXT,
            ticket_subject TEXT,
            ticket_description TEXT,
            ticket_text TEXT,
            received_channel TEXT,
            incident_type TEXT,
            ml_priority TEXT,
            keyword_priority TEXT,
            final_priority TEXT,
            department TEXT,
            sentiment TEXT,
            root_cause TEXT,
            resolution_steps TEXT,
            ai_recommended_resolution TEXT,
            status TEXT DEFAULT 'New',
            assigned_engineer TEXT,
            engineer_remarks TEXT,
            created_date TEXT,
            closed_date TEXT,
            resolution_time_mins REAL,
            sla_mins INTEGER,
            sla_status TEXT,
            escalation_required INTEGER DEFAULT 0,
            failure_case_flag INTEGER DEFAULT 0
        )
    """)

    # 3. Ticket history table (with SLA columns)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ticket_history (
            history_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER NOT NULL,
            old_status TEXT,
            new_status TEXT,
            updated_by TEXT NOT NULL,
            updated_time TEXT NOT NULL,
            remarks TEXT,
            sla_mins_remaining REAL,
            sla_status_at_update TEXT,
            FOREIGN KEY (ticket_id) REFERENCES tickets (ticket_id)
        )
    """)

    # 4. Gmail inbox simulation table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gmail_inbox_simulation (
            email_id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_email TEXT,
            company_name TEXT,
            subject TEXT,
            email_body TEXT,
            received_time TEXT,
            converted_to_ticket INTEGER DEFAULT 0
        )
    """)

    # 5. Company SLA breach history table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS company_sla_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT,
            ticket_id INTEGER,
            breach_mins REAL,
            recorded_date TEXT
        )
    """)

    conn.commit()

    # Idempotent column additions for existing databases
    _safe_alter(cursor, conn, "ALTER TABLE users ADD COLUMN company_name TEXT")
    _safe_alter(cursor, conn, "ALTER TABLE ticket_history ADD COLUMN sla_mins_remaining REAL")
    _safe_alter(cursor, conn, "ALTER TABLE ticket_history ADD COLUMN sla_status_at_update TEXT")

    conn.close()


def _safe_alter(cursor, conn, sql):
    """Executes an ALTER TABLE statement, silently ignoring errors if the column already exists."""
    try:
        cursor.execute(sql)
        conn.commit()
    except Exception:
        pass


def seed_users():
    """Seeds the user credentials — Admin, Department Users, and Company Users."""
    users_data = [
        # (username, password, role, department, company_name)
        ("admin",          "admin123",      "Admin",          None,                  None),
        ("infra",          "infra123",      "Department User", "Infra Team",          None),
        ("desktop",        "desktop123",    "Department User", "Desktop Support",     None),
        ("app",            "app123",        "Department User", "Application Support", None),
        ("db",             "db123",         "Department User", "Database Team",       None),
        ("security",       "security123",   "Department User", "Security Team",       None),
        ("messaging",      "messaging123",  "Department User", "Messaging Team",      None),
        ("access",         "access123",     "Department User", "IT Access Team",      None),
        ("l1",             "l1123",         "Department User", "Service Desk L1",     None),
        ("hrit",           "hrit123",       "Department User", "HR IT Team",          None),
        # Company Users
        ("tcs_user",       "tcs123",        "Company User",   None, "TCS Global"),
        ("techcorp_user",  "techcorp123",   "Company User",   None, "TechCorp Services"),
        ("innotech_user",  "innotech123",   "Company User",   None, "InnoTech Ltd"),
        ("finbank_user",   "finbank123",    "Company User",   None, "FinBank Corp"),
        ("medsys_user",    "medsys123",     "Company User",   None, "MedSystems"),
        ("cloud_user",     "cloud123",      "Company User",   None, "CloudSphere"),
        ("edulearn_user",  "edulearn123",   "Company User",   None, "EduLearn Inc"),
        ("apex_user",      "apex123",       "Company User",   None, "Apex Retail"),
    ]

    conn = get_connection()
    cursor = conn.cursor()
    for username, password, role, dept, company in users_data:
        try:
            cursor.execute("""
                INSERT INTO users (username, password, role, department, company_name)
                VALUES (?, ?, ?, ?, ?)
            """, (username, password, role, dept, company))
        except sqlite3.IntegrityError:
            # User exists — ensure company_name is up to date for company users
            if company:
                cursor.execute(
                    "UPDATE users SET company_name = ? WHERE username = ? AND company_name IS NULL",
                    (company, username)
                )
    conn.commit()
    conn.close()


def add_ticket(ticket_dict):
    """Inserts a new ticket into the database."""
    conn = get_connection()
    cursor = conn.cursor()

    query = """
        INSERT INTO tickets (
            company_name, employee_name, employee_email, ticket_subject, ticket_description,
            ticket_text, received_channel, incident_type, ml_priority, keyword_priority,
            final_priority, department, sentiment, root_cause, resolution_steps,
            ai_recommended_resolution, status, assigned_engineer, engineer_remarks,
            created_date, closed_date, resolution_time_mins, sla_mins, sla_status,
            escalation_required, failure_case_flag
        ) VALUES (
            :company_name, :employee_name, :employee_email, :ticket_subject, :ticket_description,
            :ticket_text, :received_channel, :incident_type, :ml_priority, :keyword_priority,
            :final_priority, :department, :sentiment, :root_cause, :resolution_steps,
            :ai_recommended_resolution, :status, :assigned_engineer, :engineer_remarks,
            :created_date, :closed_date, :resolution_time_mins, :sla_mins, :sla_status,
            :escalation_required, :failure_case_flag
        )
    """
    cursor.execute(query, ticket_dict)
    ticket_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return ticket_id


def log_ticket_history(ticket_id, old_status, new_status, updated_by, remarks="",
                       sla_mins_remaining=None, sla_status_at_update=None):
    """Inserts an audit log entry for status changes, capturing SLA context."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO ticket_history
            (ticket_id, old_status, new_status, updated_by, updated_time, remarks,
             sla_mins_remaining, sla_status_at_update)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        ticket_id, old_status, new_status, updated_by,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        remarks, sla_mins_remaining, sla_status_at_update
    ))
    conn.commit()
    conn.close()


def get_company_breach_count(company_name):
    """Returns the number of SLA breaches recorded for a given company."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM company_sla_history WHERE company_name = ?",
        (company_name,)
    )
    count = cursor.fetchone()[0]
    conn.close()
    return count or 0


def check_and_apply_company_priority_escalation(company_name, current_priority):
    """
    If a company has >= 3 historical SLA breaches, bumps current_priority one level up.
    Returns (final_priority, escalation_reason | None).
    """
    PRIORITY_ESCALATION = {
        "Low":      "Medium",
        "Medium":   "High",
        "High":     "High"  # already max
    }
    breach_count = get_company_breach_count(company_name)
    if breach_count >= 3:
        new_priority = PRIORITY_ESCALATION.get(current_priority, current_priority)
        if new_priority != current_priority:
            reason = (
                f"Auto-escalated from {current_priority} to {new_priority}: "
                f"{company_name} has {breach_count} historical SLA breaches. "
                f"Higher priority enforced to prevent repeat SLA violations."
            )
            return new_priority, reason
    return current_priority, None


def update_ticket_workflow(ticket_id, status, remarks, engineer, updated_by):
    """Updates a ticket's workflow status, captures SLA data, and logs audit trail."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT status, created_date, sla_mins, failure_case_flag, company_name FROM tickets WHERE ticket_id = ?",
        (ticket_id,)
    )
    ticket = cursor.fetchone()
    if not ticket:
        conn.close()
        return False

    old_status = ticket['status']
    created_date_str = ticket['created_date']
    sla_mins = ticket['sla_mins']
    failure_case_flag = ticket['failure_case_flag']
    company_name = ticket['company_name']

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    closed_date = None
    resolution_time_mins = None
    sla_status = 'In Progress'

    # Calculate elapsed time for SLA
    try:
        created_dt = datetime.strptime(created_date_str, "%Y-%m-%d %H:%M:%S")
        now_dt = datetime.strptime(now_str, "%Y-%m-%d %H:%M:%S")
        elapsed_mins = (now_dt - created_dt).total_seconds() / 60.0
    except Exception:
        elapsed_mins = 0.0

    sla_mins_remaining = round(sla_mins - elapsed_mins, 1)

    if status == 'Done':
        closed_date = now_str
        resolution_time_mins = round(elapsed_mins, 1)
        sla_status = 'Met' if resolution_time_mins <= sla_mins else 'Breached'

        # Record breach in company_sla_history
        if sla_status == 'Breached':
            breach_mins = round(resolution_time_mins - sla_mins, 1)
            cursor.execute("""
                INSERT INTO company_sla_history (company_name, ticket_id, breach_mins, recorded_date)
                VALUES (?, ?, ?, ?)
            """, (company_name, ticket_id, breach_mins, now_str))
    else:
        sla_status = 'Breached' if elapsed_mins > sla_mins else 'In Progress'

    # Reopened ticket detection
    new_failure_flag = failure_case_flag
    if old_status == 'Done' and status in ('New', 'In Progress', 'Escalated'):
        new_failure_flag = 1
        remarks = f"[Reopened] {remarks}"

    escalation_required = 1 if status == 'Escalated' or sla_status == 'Breached' else 0

    cursor.execute("""
        UPDATE tickets
        SET status = ?,
            engineer_remarks = ?,
            assigned_engineer = ?,
            closed_date = ?,
            resolution_time_mins = ?,
            sla_status = ?,
            escalation_required = ?,
            failure_case_flag = ?
        WHERE ticket_id = ?
    """, (status, remarks, engineer, closed_date, resolution_time_mins,
          sla_status, escalation_required, new_failure_flag, ticket_id))

    conn.commit()
    conn.close()

    # Audit log with SLA context
    log_ticket_history(
        ticket_id, old_status, status, updated_by, remarks,
        sla_mins_remaining=sla_mins_remaining,
        sla_status_at_update=sla_status
    )
    return True


def get_all_tickets(filters=None, page=1, page_size=100):
    """
    Retrieves tickets with enterprise sort and PAGINATION for performance:
    High > Medium > Low, Breached first, then created_date ASC.
    
    Args:
        filters: Dict with optional filters (department, status, priority, search, company_name)
        page: Page number (1-indexed)
        page_size: Number of tickets per page (default 100)
    
    Returns:
        Dict with 'tickets', 'total_count', 'total_pages', 'current_page'
    """
    conn = get_connection()
    
    # Build WHERE clause
    where_clause = "WHERE 1=1"
    params = []

    if filters:
        if filters.get('department'):
            where_clause += " AND department = ?"
            params.append(filters['department'])
        if filters.get('status'):
            where_clause += " AND status = ?"
            params.append(filters['status'])
        if filters.get('priority'):
            where_clause += " AND final_priority = ?"
            params.append(filters['priority'])
        if filters.get('search'):
            where_clause += " AND (ticket_subject LIKE ? OR ticket_description LIKE ? OR company_name LIKE ?)"
            sp = f"%{filters['search']}%"
            params.extend([sp, sp, sp])
        if filters.get('company_name'):
            where_clause += " AND company_name = ?"
            params.append(filters['company_name'])

    # Count total matching tickets
    count_query = f"SELECT COUNT(*) FROM tickets {where_clause}"
    cursor = conn.cursor()
    cursor.execute(count_query, params)
    total_count = cursor.fetchone()[0]
    
    # Calculate pagination
    total_pages = (total_count + page_size - 1) // page_size  # Ceiling division
    offset = (page - 1) * page_size
    
    # Fetch paginated results
    query = f"""
        SELECT * FROM tickets {where_clause}
        ORDER BY
            CASE final_priority
                WHEN 'High'     THEN 1
                WHEN 'Medium'   THEN 2
                WHEN 'Low'      THEN 3
                ELSE 4
            END ASC,
            CASE sla_status WHEN 'Breached' THEN 1 ELSE 2 END ASC,
            created_date ASC
        LIMIT ? OFFSET ?
    """
    
    cursor.execute(query, params + [page_size, offset])
    tickets = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return {
        'tickets': tickets,
        'total_count': total_count,
        'total_pages': total_pages,
        'current_page': page,
        'page_size': page_size
    }


def get_workspace_stats(role, department=None, company_name=None):
    """Fast aggregate counts for sidebar stats (no full table scan into Python)."""
    conn = get_connection()
    cursor = conn.cursor()
    if role == 'Admin':
        cursor.execute(
            "SELECT COUNT(*), SUM(CASE WHEN status='Done' THEN 1 ELSE 0 END) FROM tickets"
        )
    elif role == 'Company User':
        cursor.execute(
            "SELECT COUNT(*), SUM(CASE WHEN status='Done' THEN 1 ELSE 0 END) "
            "FROM tickets WHERE company_name=?",
            (company_name,),
        )
    else:
        cursor.execute(
            "SELECT COUNT(*), SUM(CASE WHEN status='Done' THEN 1 ELSE 0 END) "
            "FROM tickets WHERE department=?",
            (department,),
        )
    t_total, t_closed = cursor.fetchone()
    conn.close()
    t_total = t_total or 0
    t_closed = t_closed or 0
    return t_total, t_closed, t_total - t_closed


def get_sla_dashboard_aggregates():
    """SQL-only aggregates for SLA dashboard — avoids loading 10k+ ticket rows."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN status != 'Done' THEN 1 ELSE 0 END) AS open_count,
            SUM(CASE WHEN status = 'Done' THEN 1 ELSE 0 END) AS closed_count,
            SUM(CASE WHEN sla_status = 'Breached' THEN 1 ELSE 0 END) AS breaches,
            AVG(CASE WHEN status = 'Done' THEN resolution_time_mins END) AS avg_res,
            SUM(CASE WHEN status = 'Done' AND sla_status = 'Met' THEN 1 ELSE 0 END) AS sla_met,
            SUM(CASE WHEN failure_case_flag = 1 THEN 1 ELSE 0 END) AS failure_count
        FROM tickets
    """)
    summary = dict(cursor.fetchone())

    cursor.execute("""
        SELECT department, status, COUNT(*) AS counts
        FROM tickets
        GROUP BY department, status
    """)
    workload = [dict(row) for row in cursor.fetchall()]

    cursor.execute("""
        SELECT incident_type, COUNT(*) AS count
        FROM tickets
        GROUP BY incident_type
    """)
    incident_dist = [dict(row) for row in cursor.fetchall()]

    cursor.execute("""
        SELECT final_priority, COUNT(*) AS count
        FROM tickets
        GROUP BY final_priority
    """)
    priority_dist = [dict(row) for row in cursor.fetchall()]

    cursor.execute("""
        SELECT sla_status, COUNT(*) AS count
        FROM tickets
        GROUP BY sla_status
    """)
    sla_dist = [dict(row) for row in cursor.fetchall()]

    cursor.execute("""
        SELECT
            department,
            SUM(CASE WHEN status != 'Done' THEN 1 ELSE 0 END) AS d_open,
            SUM(CASE WHEN status = 'Done' THEN 1 ELSE 0 END) AS d_closed,
            AVG(CASE WHEN status = 'Done' THEN resolution_time_mins END) AS d_avg_res
        FROM tickets
        GROUP BY department
    """)
    dept_capacity = [dict(row) for row in cursor.fetchall()]
    conn.close()

    closed = summary.get('closed_count') or 0
    sla_met = summary.get('sla_met') or 0
    summary['sla_compliance'] = (sla_met / closed * 100) if closed > 0 else 100.0
    summary['avg_res'] = summary.get('avg_res') or 0.0
    summary['workload'] = workload
    summary['incident_dist'] = incident_dist
    summary['priority_dist'] = priority_dist
    summary['sla_dist'] = sla_dist
    summary['dept_capacity'] = dept_capacity
    return summary


def get_audit_logs(page=1, page_size=200):
    """Paginated audit logs — avoids loading entire history table."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM ticket_history")
    total_count = cursor.fetchone()[0]
    total_pages = max(1, (total_count + page_size - 1) // page_size)
    offset = (page - 1) * page_size

    cursor.execute("""
        SELECT
            h.history_id,
            h.ticket_id,
            t.ticket_subject,
            t.company_name,
            t.created_date AS ticket_created_date,
            t.closed_date AS ticket_closed_date,
            t.resolution_time_mins,
            h.old_status,
            h.new_status,
            h.updated_by,
            h.updated_time AS action_time,
            h.remarks,
            h.sla_mins_remaining,
            h.sla_status_at_update
        FROM ticket_history h
        JOIN tickets t ON h.ticket_id = t.ticket_id
        ORDER BY h.history_id DESC
        LIMIT ? OFFSET ?
    """, (page_size, offset))
    logs = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return {
        'logs': logs,
        'total_count': total_count,
        'total_pages': total_pages,
        'current_page': page,
    }


def get_ticket_history(ticket_id):
    """Retrieves status history for a specific ticket."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM ticket_history
        WHERE ticket_id = ?
        ORDER BY history_id DESC
    """, (ticket_id,))
    history = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return history


def get_department_audit_logs(department, page=1, page_size=200):
    """Paginated audit logs for a specific department."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Count total logs for this department
    cursor.execute("""
        SELECT COUNT(*)
        FROM ticket_history h
        JOIN tickets t ON h.ticket_id = t.ticket_id
        WHERE t.department = ?
    """, (department,))
    total_count = cursor.fetchone()[0]
    total_pages = max(1, (total_count + page_size - 1) // page_size)
    offset = (page - 1) * page_size
    
    # Fetch paginated logs
    cursor.execute("""
        SELECT
            h.history_id,
            h.ticket_id,
            t.ticket_subject,
            t.created_date AS ticket_created_date,
            t.closed_date AS ticket_closed_date,
            t.resolution_time_mins,
            h.old_status,
            h.new_status,
            h.updated_by,
            h.updated_time AS action_time,
            h.remarks,
            h.sla_mins_remaining,
            h.sla_status_at_update
        FROM ticket_history h
        JOIN tickets t ON h.ticket_id = t.ticket_id
        WHERE t.department = ?
        ORDER BY h.history_id DESC
        LIMIT ? OFFSET ?
    """, (department, page_size, offset))
    logs = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return {
        'logs': logs,
        'total_count': total_count,
        'total_pages': total_pages,
        'current_page': page,
    }


def get_department_sla_aggregates(department):
    """SQL-only aggregates for department SLA dashboard — no large data loads."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN status != 'Done' THEN 1 ELSE 0 END) AS open_count,
            SUM(CASE WHEN status = 'Done' THEN 1 ELSE 0 END) AS closed_count,
            SUM(CASE WHEN sla_status = 'Breached' THEN 1 ELSE 0 END) AS breaches,
            AVG(CASE WHEN status = 'Done' THEN resolution_time_mins END) AS avg_res,
            SUM(CASE WHEN status = 'Done' AND sla_status = 'Met' THEN 1 ELSE 0 END) AS sla_met,
            SUM(CASE WHEN failure_case_flag = 1 THEN 1 ELSE 0 END) AS failure_count
        FROM tickets
        WHERE department = ?
    """, (department,))
    summary = dict(cursor.fetchone())

    cursor.execute("""
        SELECT incident_type, COUNT(*) AS count
        FROM tickets
        WHERE department = ?
        GROUP BY incident_type
    """, (department,))
    incident_dist = [dict(row) for row in cursor.fetchall()]

    cursor.execute("""
        SELECT final_priority, COUNT(*) AS count
        FROM tickets
        WHERE department = ?
        GROUP BY final_priority
    """, (department,))
    priority_dist = [dict(row) for row in cursor.fetchall()]

    cursor.execute("""
        SELECT sla_status, COUNT(*) AS count
        FROM tickets
        WHERE department = ?
        GROUP BY sla_status
    """, (department,))
    sla_dist = [dict(row) for row in cursor.fetchall()]

    conn.close()

    closed = summary.get('closed_count') or 0
    sla_met = summary.get('sla_met') or 0
    summary['sla_compliance'] = (sla_met / closed * 100) if closed > 0 else 100.0
    summary['avg_res'] = summary.get('avg_res') or 0.0
    summary['incident_dist'] = incident_dist
    summary['priority_dist'] = priority_dist
    summary['sla_dist'] = sla_dist
    return summary


def get_gmail_emails():
    """Retrieves the list of mock emails from the inbox simulation."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM gmail_inbox_simulation ORDER BY email_id DESC")
    emails = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return emails


def add_gmail_email(sender, company, subject, body):
    """Adds a simulated email to the gmail reader simulation."""
    conn = get_connection()
    cursor = conn.cursor()
    received_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT INTO gmail_inbox_simulation (sender_email, company_name, subject, email_body, received_time, converted_to_ticket)
        VALUES (?, ?, ?, ?, ?, 0)
    """, (sender, company, subject, body, received_time))
    conn.commit()
    conn.close()


def mark_email_converted(email_id):
    """Marks a simulated email as converted to ticket."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE gmail_inbox_simulation SET converted_to_ticket = 1 WHERE email_id = ?",
        (email_id,)
    )
    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    seed_users()
    print("Database initialized and users seeded successfully.")
