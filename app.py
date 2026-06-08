import streamlit as st
import pandas as pd
import numpy as np
import os
import joblib
import sqlite3
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file (if present)
load_dotenv()

# Import Custom Modules
from database import (
    get_connection, init_db, seed_users, add_ticket, 
    update_ticket_workflow, get_all_tickets, get_ticket_history,
    add_gmail_email, mark_email_converted, get_gmail_emails
)
from auth import login, logout
from priority_engine import resolve_priority
from routing_engine import route_department
from sla_engine import evaluate_sla, get_sla_mins
from rag_engine import get_rag_recommendations
from gemini_engine import get_gemini_resolution
from gmail_simulator import get_all_simulated_emails
from kanban import display_kanban
from train_model import train_and_save_models
from generate_dataset import COMPANIES, DEPARTMENTS, ENGINEERS
import re

def get_resolution_details(ticket_dict):
    raw_ai = ticket_dict.get("ai_recommended_resolution") or ""
    
    # Defaults
    root_cause = ticket_dict.get("root_cause") or "Undetermined"
    resolution_steps = ticket_dict.get("resolution_steps") or "No resolution steps available."
    escalation_required = "Yes" if ticket_dict.get("escalation_required") == 1 else "No"
    recommended_team = ticket_dict.get("department") or "Service Desk L1"
    
    # Try parsing from raw_ai if it has the Gemini structured format
    if "Root Cause:" in raw_ai and "Resolution Steps:" in raw_ai:
        # Root Cause
        rc_match = re.search(r"Root Cause\s*[:：]\s*(.+?)(?:\n|Resolution Steps)", raw_ai, re.DOTALL | re.IGNORECASE)
        if rc_match:
            root_cause = rc_match.group(1).strip()
            
        # Resolution Steps
        rs_match = re.search(r"Resolution Steps\s*[:：]?\s*((?:\n|\r\n?).+?)(?:Escalation Required|$)", raw_ai, re.DOTALL | re.IGNORECASE)
        if rs_match:
            resolution_steps = rs_match.group(1).strip()
            
        # Escalation Required
        esc_match = re.search(r"Escalation Required\s*[:：]\s*(Yes|No)", raw_ai, re.IGNORECASE)
        if esc_match:
            escalation_required = esc_match.group(1).strip()
            
        # Recommended Team
        rt_match = re.search(r"Recommended Team\s*[:：]\s*(.+)", raw_ai, re.IGNORECASE)
        if rt_match:
            recommended_team = rt_match.group(1).strip()
            
    return {
        "root_cause": root_cause,
        "resolution_steps": resolution_steps,
        "escalation_required": escalation_required,
        "recommended_team": recommended_team
    }


# Page Configurations
st.set_page_config(
    page_title="Smart Ticket Understanding Engine",
    page_icon="🎫",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Global CSS for Modern dark theme aesthetics
st.markdown("""
    <style>
    .main .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
    }
    h1, h2, h3 {
        font-family: 'Inter', sans-serif;
        font-weight: 700;
        color: #F8F9FA;
    }
    .metric-card {
        background: #1E1E24;
        border-radius: 10px;
        padding: 1.2rem;
        border: 1px solid rgba(255, 255, 255, 0.05);
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        text-align: center;
    }
    .metric-title {
        font-size: 0.85rem;
        text-transform: uppercase;
        color: #888888;
        font-weight: bold;
        letter-spacing: 0.8px;
        margin-bottom: 0.3rem;
    }
    .metric-val {
        font-size: 1.8rem;
        font-weight: 700;
        color: #ffffff;
    }
    .metric-sub {
        font-size: 0.75rem;
        color: #888888;
        margin-top: 0.3rem;
    }
    </style>
""", unsafe_allow_html=True)

# Initialize Session State
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'user' not in st.session_state:
    st.session_state['user'] = None
if 'selected_ticket_id' not in st.session_state:
    st.session_state['selected_ticket_id'] = None

# Initialize Database Schema & Data
init_db()
seed_users()

# Load classification models helper
MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")

def predict_ticket_fields(ticket_text):
    """
    Predicts incident_type, priority, department, and sentiment 
    using the trained models inside models/. Falls back gracefully if models are missing.
    """
    preds = {
        "incident_type": "Access",
        "priority": "Low",
        "department": "Service Desk L1",
        "sentiment": "Neutral"
    }
    
    # Check if models are available
    vec_path = os.path.join(MODELS_DIR, "rag_vectorizer.pkl")
    inc_model_path = os.path.join(MODELS_DIR, "incident_type_model.pkl")
    prio_model_path = os.path.join(MODELS_DIR, "priority_model.pkl")
    dept_model_path = os.path.join(MODELS_DIR, "department_model.pkl")
    sent_model_path = os.path.join(MODELS_DIR, "sentiment_model.pkl")
    
    if all(os.path.exists(p) for p in [vec_path, inc_model_path, prio_model_path, dept_model_path, sent_model_path]):
        try:
            vec = joblib.load(vec_path)
            inc_model = joblib.load(inc_model_path)
            prio_model = joblib.load(prio_model_path)
            dept_model = joblib.load(dept_model_path)
            sent_model = joblib.load(sent_model_path)
            
            X = vec.transform([ticket_text])
            
            preds["incident_type"] = str(inc_model.predict(X)[0])
            preds["priority"] = str(prio_model.predict(X)[0])
            preds["department"] = str(dept_model.predict(X)[0])
            preds["sentiment"] = str(sent_model.predict(X)[0])
        except Exception as e:
            st.error(f"Error executing model predictions: {e}")
            
    return preds

# Main ticket pipeline processor
def execute_ticket_creation_pipeline(company, employee, email, subject, description, channel):
    """Executes the full AI ticket pipeline: ML classification, Priority, RAG, SLA, Routing & Saving."""
    ticket_text = f"{subject}. {description}"
    created_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 1. Classification (ML predictions)
    preds = predict_ticket_fields(ticket_text)
    
    # 2. Priority Engine (Hybrid logic)
    ml_prio, kw_prio, final_prio = resolve_priority(ticket_text, preds["priority"])
    
    # 2b. Check for historical SLA breaches and apply escalation
    from database import check_and_apply_company_priority_escalation
    escalated_prio, escalation_reason = check_and_apply_company_priority_escalation(company, final_prio)
    if escalation_reason:
        final_prio = escalated_prio
    
    # 3. Routing Engine (Department Assignment)
    routed_dept = route_department(preds["incident_type"], subject, description, preds["department"])
    
    # 4. RAG Engine Retrieval
    rag_rec = get_rag_recommendations(ticket_text)

    # 4b. Gemini-First Resolution Engine (falls back to RAG on any failure)
    gemini_rec = get_gemini_resolution(
        subject, description,
        preds["incident_type"], final_prio, routed_dept,
        rag_rec
    )
    # Merge: use Gemini root cause + resolution if Gemini succeeded
    if gemini_rec["source"] == "gemini":
        rag_rec["predicted_root_cause"]   = gemini_rec["root_cause"]
        rag_rec["recommended_resolution"] = gemini_rec["full_response"]
    rag_rec["gemini_source"] = gemini_rec["source"]

    # 5. SLA Engine
    sla_mins = get_sla_mins(final_prio)
    
    ticket_dict = {
        "company_name": company,
        "employee_name": employee,
        "employee_email": email,
        "ticket_subject": subject,
        "ticket_description": description,
        "ticket_text": ticket_text,
        "received_channel": channel,
        "incident_type": preds["incident_type"],
        "ml_priority": ml_prio,
        "keyword_priority": kw_prio,
        "final_priority": final_prio,
        "department": routed_dept,
        "sentiment": preds["sentiment"],
        "root_cause": rag_rec["predicted_root_cause"],
        "resolution_steps": gemini_rec["resolution_steps"] if gemini_rec["source"] == "gemini" else rag_rec["recommended_resolution"].split("### [Alternative Action")[0].replace("### [Recommended Resolution (Based on Similar Ticket ID", "").split(")]\n")[-1],
        "ai_recommended_resolution": rag_rec["recommended_resolution"],
        "status": "New",
        "assigned_engineer": None,
        "engineer_remarks": "",
        "created_date": created_date,
        "closed_date": None,
        "resolution_time_mins": None,
        "sla_mins": sla_mins,
        "sla_status": "In Progress",
        "escalation_required": 1 if (escalation_reason or (gemini_rec["source"] == "gemini" and gemini_rec["escalation_required"] == "Yes")) else 0,
        "failure_case_flag": 1 if rag_rec["is_outlier"] else 0
    }
    
    # Save to SQLite
    ticket_id = add_ticket(ticket_dict)
    
    # Audit log
    conn = get_connection()
    cursor = conn.cursor()
    audit_remarks = f"Ticket ingestion via {channel}. Auto-assigned to {routed_dept}."
    if escalation_reason:
        audit_remarks += f" | {escalation_reason}"
    cursor.execute("""
        INSERT INTO ticket_history (ticket_id, old_status, new_status, updated_by, updated_time, remarks, sla_mins_remaining, sla_status_at_update)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (ticket_id, "None", "New", "System Pipeline", created_date, audit_remarks, sla_mins, "In Progress"))
    conn.commit()
    conn.close()
    
    return ticket_id, ticket_dict, rag_rec

# Render Authentication Page if not logged in
if not st.session_state['logged_in']:
    login()
else:
    # Sidebar Navigation & Profile
    user = st.session_state['user']
    with st.sidebar:
        st.markdown(f"""
            <div style='background-color:#1E1E24; padding:1.2rem; border-radius:12px; margin-bottom:1.5rem; border:1px solid rgba(255,255,255,0.05)'>
                <h4 style='margin-top:0; color:#4facfe;'>🎫 Support Profile</h4>
                <div style='font-size:0.95rem; color:#DDD; margin-bottom:0.3rem;'>
                    <strong style='color:#FFF;'>{user['username']}</strong>
                </div>
                <div style='font-size:0.82rem; color:#777;'>Role: {user['role']}</div>
                {f"<div style='font-size:0.82rem; color:#777; margin-top:0.2rem;'>Dept: {user['department']}</div>" if user.get('department') else ""}
            </div>
        """, unsafe_allow_html=True)
        
        # Display Workspace Stats In Sidebar
        conn = get_connection()
        cursor = conn.cursor()
        if user['role'] == 'Admin':
            cursor.execute("SELECT count(*), sum(case when status='Done' then 1 else 0 end) from tickets")
            t_total, t_closed = cursor.fetchone()
        elif user['role'] == 'Company User':
            cursor.execute("SELECT count(*), sum(case when status='Done' then 1 else 0 end) from tickets WHERE company_name=?", (user['company_name'],))
            t_total, t_closed = cursor.fetchone()
        else:
            cursor.execute("SELECT count(*), sum(case when status='Done' then 1 else 0 end) from tickets WHERE department=?", (user['department'],))
            t_total, t_closed = cursor.fetchone()
        conn.close()
        
        t_total = t_total or 0
        t_closed = t_closed or 0
        t_open = t_total - t_closed
        
        st.markdown(f"""
            <div style='background-color:#1E1E24; padding:1rem; border-radius:12px; margin-bottom:1.5rem; border:1px solid rgba(255,255,255,0.05)'>
                <h5 style='margin-top:0; color:#00f2fe;'>Workspace Stats</h5>
                <div style='display:flex; justify-content:space-between; font-size:0.85rem; padding:0.2rem 0;'><span style='color:#AAA;'>Total Queue:</span><strong style='color:#FFF;'>{t_total}</strong></div>
                <div style='display:flex; justify-content:space-between; font-size:0.85rem; padding:0.2rem 0;'><span style='color:#AAA;'>Active Backlog:</span><strong style='color:#FFA500;'>{t_open}</strong></div>
                <div style='display:flex; justify-content:space-between; font-size:0.85rem; padding:0.2rem 0;'><span style='color:#AAA;'>Closed Tickets:</span><strong style='color:#2ECC71;'>{t_closed}</strong></div>
            </div>
        """, unsafe_allow_html=True)
        
        if st.button("Logout System", width='stretch', type="secondary"):
            logout()
            
    # Main Header
    st.markdown("<h1 style='text-align: left; background: linear-gradient(90deg, #4facfe 0%, #00f2fe 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent;'>Smart Ticket Understanding Engine</h1>", unsafe_allow_html=True)
    st.markdown("<div style='color:#888888; font-size:0.95rem; margin-top:-0.5rem; margin-bottom:2rem;'>Cognitive Service Desk Optimization & RAG Recommendation System</div>", unsafe_allow_html=True)
    
    # ----------------------------------------------------
    # ADMIN VIEW
    # ----------------------------------------------------
    if user['role'] == 'Admin':
        tabs = st.tabs([
            "Gmail Simulation Gateway",
            "All Support Tickets",
            "Unified Kanban Board",
            "Leadership SLA Dashboard",
            "Root Cause Knowledge Base",
            "Audit Logs",
            "Continuous Learning Loop",
            "Performance Metrics"
        ])
        
        # TAB 1: Simulated Gmail Reader
        with tabs[0]:
            st.header("Simulated Gmail Inbox Gateway")
            st.write("Convert incoming user emails into resolved IT service desk tickets. Gmail API comments and authentication hooks are defined within `gmail_simulator.py`.")
            
            emails = get_all_simulated_emails()
            if not emails:
                st.info("No messages in mailbox simulation.")
            else:
                for mail in emails:
                    is_conv = mail["converted_to_ticket"] == 1
                    status_badge = "✅ Converted to Ticket" if is_conv else "✉️ Unprocessed Email"
                    
                    with st.expander(f"[{status_badge}] {mail['sender_email']} - {mail['subject']}", expanded=not is_conv):
                        st.write(f"**From:** {mail['sender_email']} | **Company:** {mail['company_name']} | **Received:** {mail['received_time']}")
                        st.markdown("<hr style='margin:0.2rem 0 0.8rem 0; border-color:rgba(255,255,255,0.05)'>", unsafe_allow_html=True)
                        st.write(mail["email_body"])
                        
                        if not is_conv:
                            if st.button("Convert Email to Ticket", key=f"conv_email_{mail['email_id']}", type="primary"):
                                tid, t_dict, rag = execute_ticket_creation_pipeline(
                                    mail["company_name"], 
                                    mail["sender_email"].split("@")[0].replace(".", " ").title(),
                                    mail["sender_email"],
                                    mail["subject"],
                                    mail["email_body"],
                                    "Email"
                                )
                                mark_email_converted(mail["email_id"])
                                st.success(f"Email converted. Ticket #{tid} has been dispatched to {t_dict['department']}!")
                                st.rerun()
                                
        # TAB 2: All Tickets (with searching, filtering, editing, exporting)
        with tabs[1]:
            st.header("Unified Support Tickets Database")
            
            col_fs, col_fp, col_fd = st.columns(3)
            with col_fs:
                search_q = st.text_input("Search (Subject, Description, Company)", key="all_t_search")
            with col_fp:
                prio_q = st.selectbox("Filter Priority", ["All", "Critical", "High", "Medium", "Low"])
            with col_fd:
                dept_q = st.selectbox("Filter Department", ["All"] + DEPARTMENTS)
                
            filters = {
                "search": search_q,
                "priority": None if prio_q == "All" else prio_q,
                "department": None if dept_q == "All" else dept_q
            }
            
            tickets_list = get_all_tickets(filters)
            if not tickets_list:
                st.info("No tickets match current filtering guidelines.")
            else:
                # Apply priority aging and enterprise sorting dynamically
                from kanban import apply_priority_aging, sort_tickets, compute_sla_remaining
                
                aged_tickets = apply_priority_aging(tickets_list)
                sorted_tickets = sort_tickets(aged_tickets)
                
                # Format for display
                table_rows = []
                for t in sorted_tickets:
                    rem, st_val = compute_sla_remaining(t)
                    prio = t.get("final_priority", "Low")
                    if t.get("_aged"):
                        prio_display = f"{prio} ⬆️"
                    else:
                        prio_display = prio
                        
                    if st_val == "Done":
                        sla_display = "Closed"
                    elif st_val == "Breached":
                        late = int(abs(rem)) if rem is not None else 0
                        sla_display = f"🔴 Breached (+{late}m)"
                    elif rem is not None:
                        sla_display = f"⏳ {int(rem)}m left"
                    else:
                        sla_display = "—"
                        
                    table_rows.append({
                        "ID": f"#{t['ticket_id']}",
                        "Company": t.get("company_name", "—"),
                        "Employee": t.get("employee_name", "—"),
                        "Subject": t.get("ticket_subject", "—"),
                        "Category": t.get("incident_type", "—"),
                        "Priority": prio_display,
                        "Department": t.get("department", "—"),
                        "Status": t.get("status", "New"),
                        "Engineer": t.get("assigned_engineer") or "—",
                        "SLA Countdown": sla_display,
                        "SLA Status": t.get("sla_status", "—"),
                        "Created Date": t.get("created_date", "—")
                    })
                
                df_display = pd.DataFrame(table_rows)
                st.dataframe(df_display, use_container_width=True, hide_index=True)
                
                # Quick management selection
                col_sel, col_act = st.columns([3, 1])
                with col_sel:
                    ticket_ids = [t['ticket_id'] for t in sorted_tickets]
                    selected_id = st.selectbox("Select Ticket ID to Manage", [""] + [f"#{tid}" for tid in ticket_ids], key="all_t_select")
                with col_act:
                    st.markdown("<div style='height:1.7rem'></div>", unsafe_allow_html=True)
                    if st.button("Manage Selected Ticket", width='stretch', type="primary"):
                        if selected_id:
                            st.session_state["selected_ticket_id"] = int(selected_id.replace("#", ""))
                            st.rerun()
                
                df_tickets = pd.DataFrame(sorted_tickets)
                col_exp1, col_exp2 = st.columns(2)
                with col_exp1:
                    st.download_button(
                        label="Export Queue to CSV",
                        data=df_tickets.to_csv(index=False),
                        file_name=f"smart_tickets_{datetime.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv",
                        width='stretch'
                    )
                with col_exp2:
                    st.download_button(
                        label="Export Queue to JSON",
                        data=df_tickets.to_json(orient="records"),
                        file_name=f"smart_tickets_{datetime.now().strftime('%Y%m%d')}.json",
                        mime="application/json",
                        width='stretch'
                    )
                    
        # TAB 3: Unified Kanban Board
        with tabs[2]:
            st.header("Enterprise Kanban Workflow")
            
            selected_kanban_dept = st.selectbox("Kanban Department View", ["All Departments"] + DEPARTMENTS)
            dept_filter = None if selected_kanban_dept == "All Departments" else selected_kanban_dept
            
            all_tk = get_all_tickets()
            display_kanban(all_tk, dept_filter, user)
            
        # TAB 4: SLA Dashboard & Charts
        with tabs[3]:
            st.header("Executive Leadership SLA Dashboard")
            
            all_tk = get_all_tickets()
            if not all_tk:
                st.info("Ingest tickets first to review operational charts.")
            else:
                df = pd.DataFrame(all_tk)
                
                # Metrics Calculation
                total_tickets = len(df)
                open_tickets = len(df[df["status"] != "Done"])
                closed_tickets = len(df[df["status"] == "Done"])
                
                closed_df = df[df["status"] == "Done"]
                if len(closed_df) > 0:
                    sla_met = len(closed_df[closed_df["sla_status"] == "Met"])
                    sla_compliance = (sla_met / len(closed_df)) * 100
                    avg_res = closed_df["resolution_time_mins"].mean()
                else:
                    sla_compliance = 100.0
                    avg_res = 0.0
                    
                sla_breaches = len(df[df["sla_status"] == "Breached"])
                
                # Layout metric cards
                m1, m2, m3, m4, m5, m6 = st.columns(6)
                with m1:
                    st.markdown(f"<div class='metric-card'><div class='metric-title'>Total Volume</div><div class='metric-val'>{total_tickets}</div><div class='metric-sub'>Ingested tickets</div></div>", unsafe_allow_html=True)
                with m2:
                    st.markdown(f"<div class='metric-card'><div class='metric-title'>Active Backlog</div><div class='metric-val' style='color:#FF9F43;'>{open_tickets}</div><div class='metric-sub'>Needs engineering</div></div>", unsafe_allow_html=True)
                with m3:
                    st.markdown(f"<div class='metric-card'><div class='metric-title'>Resolved</div><div class='metric-val' style='color:#2ECC71;'>{closed_tickets}</div><div class='metric-sub'>Closed state</div></div>", unsafe_allow_html=True)
                with m4:
                    st.markdown(f"<div class='metric-card'><div class='metric-title'>SLA Met Rate</div><div class='metric-val' style='color:#00f2fe;'>{sla_compliance:.1f}%</div><div class='metric-sub'>Target SLA Met</div></div>", unsafe_allow_html=True)
                with m5:
                    st.markdown(f"<div class='metric-card'><div class='metric-title'>SLA Breaches</div><div class='metric-val' style='color:#FF4B4B;'>{sla_breaches}</div><div class='metric-sub'>Exceeded limits</div></div>", unsafe_allow_html=True)
                with m6:
                    st.markdown(f"<div class='metric-card'><div class='metric-title'>Avg Duration</div><div class='metric-val'>{avg_res:.1f}m</div><div class='metric-sub'>Mean closure time</div></div>", unsafe_allow_html=True)
                
                st.markdown("<br>", unsafe_allow_html=True)
                
                # Visual Charts Row 1
                col_chart1, col_chart2 = st.columns(2)
                
                with col_chart1:
                    st.subheader("Department Workload Allocation")
                    workload_df = df.groupby(["department", "status"]).size().reset_index(name="counts")
                    fig_w = px.bar(
                        workload_df, x="department", y="counts", color="status",
                        title="Workload Queue Status per Department",
                        color_discrete_map={"New": "#5398ff", "In Progress": "#FF9F43", "Escalated": "#FF4B4B", "Done": "#2ECC71"},
                        template="plotly_dark"
                    )
                    st.plotly_chart(fig_w, use_container_width=True)
                    
                with col_chart2:
                    st.subheader("Incident Types Distribution")
                    inc_dist = df["incident_type"].value_counts().reset_index()
                    fig_i = px.pie(
                        inc_dist, values="count", names="incident_type",
                        hole=0.4, title="Incident Category Breakdown",
                        template="plotly_dark",
                        color_discrete_sequence=px.colors.qualitative.Pastel
                    )
                    st.plotly_chart(fig_i, use_container_width=True)
                    
                # Visual Charts Row 2
                col_chart3, col_chart4 = st.columns(2)
                
                with col_chart3:
                    st.subheader("Ticket Priority Breakdown")
                    prio_dist = df["final_priority"].value_counts().reset_index()
                    fig_p = px.pie(
                        prio_dist, values="count", names="final_priority",
                        title="Resolved SLA Priorities",
                        color_discrete_map={"Critical": "#FF4B4B", "High": "#FF9F43", "Medium": "#F3CB06", "Low": "#2ECC71"},
                        template="plotly_dark"
                    )
                    st.plotly_chart(fig_p, use_container_width=True)
                    
                with col_chart4:
                    st.subheader("SLA Compliance Metrics")
                    sla_dist = df["sla_status"].value_counts().reset_index()
                    fig_s = px.pie(
                        sla_dist, values="count", names="sla_status",
                        hole=0.5, title="SLA Compliance Split",
                        color_discrete_map={"Met": "#2ECC71", "Breached": "#FF4B4B", "In Progress": "#3498DB"},
                        template="plotly_dark"
                    )
                    st.plotly_chart(fig_s, use_container_width=True)
                    
                # Radar KPI Chart & Capacity Planning
                col_radar, col_cap = st.columns(2)
                
                with col_radar:
                    st.subheader("Radar Service KPI Index")
                    
                    # Calculate Metrics for Radar
                    routing_accuracy = 1.0 - (len(df[df["failure_case_flag"] == 1]) / total_tickets if total_tickets > 0 else 0)
                    closure_rate = closed_tickets / total_tickets if total_tickets > 0 else 0.0
                    
                    # Estimate Knowledge Coverage (similarity score >= 0.15)
                    # We can use (1 - failure_case_flag/total) or read the similarity value if recorded
                    kb_coverage = len(df[df["failure_case_flag"] == 0]) / total_tickets if total_tickets > 0 else 1.0
                    
                    # Speed Score: 100 - (Avg Res / Mean SLA limits * 10)
                    speed_score = max(20.0, min(100.0, 100.0 - (avg_res / 10.0)))
                    
                    categories = ['SLA Met Rate', 'Ticket Closure Rate', 'Routing Precision', 'KB Reference Coverage', 'Resolution Speed']
                    values = [sla_compliance, closure_rate * 100, routing_accuracy * 100, kb_coverage * 100, speed_score]
                    
                    fig_radar = go.Figure(data=go.Scatterpolar(
                        r=values + [values[0]],
                        theta=categories + [categories[0]],
                        fill='toself',
                        name='Service Level Scorecard',
                        line_color='#00f2fe',
                        fillcolor='rgba(0, 242, 254, 0.2)'
                    ))
                    fig_radar.update_layout(
                        polar=dict(
                            radialaxis=dict(visible=True, range=[0, 100])
                        ),
                        showlegend=False,
                        template="plotly_dark",
                        title="Service Level Operational Radar"
                    )
                    st.plotly_chart(fig_radar, use_container_width=True)
                    
                with col_cap:
                    st.subheader("Queue Capacity & Staffing Planner")
                    st.write("Calculates average resolution speed and backlog load dynamically to balance team workload.")
                    
                    cap_data = []
                    for dept in DEPARTMENTS:
                        dept_t = df[df["department"] == dept]
                        d_total = len(dept_t)
                        d_open = len(dept_t[dept_t["status"] != "Done"])
                        d_closed = len(dept_t[dept_t["status"] == "Done"])
                        d_avg_res = dept_t[dept_t["status"] == "Done"]["resolution_time_mins"].mean()
                        d_avg_res = d_avg_res if not np.isnan(d_avg_res) else 0.0
                        
                        # Staff recommendation algorithm
                        if d_open > 6 and d_avg_res > 150:
                            rec = "⚠️ Additional Staff Recommended (High Load)"
                        elif d_open > 10:
                            rec = "⚠️ Backlog Bottleneck (Reallocate engineers)"
                        elif d_open < 2:
                            rec = "✅ Underutilized Capacity"
                        else:
                            rec = "✅ Optimally Staffed"
                            
                        cap_data.append({
                            "Department": dept,
                            "Backlog Queue": d_open,
                            "Closed Tickets": d_closed,
                            "Avg Resolution (m)": round(d_avg_res, 1),
                            "Operational Recommendation": rec
                        })
                        
                    df_cap = pd.DataFrame(cap_data)
                    st.dataframe(df_cap, use_container_width=True, hide_index=True)
                    
        # TAB 5: Root Cause & Resolution Knowledge Base
        with tabs[4]:
            st.header("Root Cause & Resolution Knowledge Base")
            
            col_kbd, col_kbt = st.columns(2)
            with col_kbd:
                kb_dept = st.selectbox("KB Department", ["All"] + DEPARTMENTS)
            with col_kbt:
                kb_type = st.selectbox("KB Incident Type", ["All", "Network", "Hardware", "Software", "Access", "Messaging", "Application", "Database", "Security", "HR"])
                
            conn = get_connection()
            query = "SELECT ticket_id, ticket_subject, incident_type, department, root_cause, resolution_steps, count(*) as reuse_count FROM tickets WHERE root_cause IS NOT NULL AND status='Done'"
            params = []
            
            if kb_dept != "All":
                query += " AND department = ?"
                params.append(kb_dept)
            if kb_type != "All":
                query += " AND incident_type = ?"
                params.append(kb_type)
                
            query += " GROUP BY root_cause, resolution_steps ORDER BY count(*) DESC"
            
            cursor = conn.cursor()
            cursor.execute(query, params)
            kb_list = [dict(row) for row in cursor.fetchall()]
            conn.close()
            
            if not kb_list:
                st.info("No resolved issues match the selected parameters.")
            else:
                for idx, item in enumerate(kb_list):
                    with st.container():
                        st.markdown(f"""
                            <div style='background-color:#1E1E24; padding:1.2rem; border-radius:10px; margin-bottom:1rem; border:1px solid rgba(255,255,255,0.05)'>
                                <div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:0.5rem;'>
                                    <strong style='color:#00f2fe; font-size:1.1rem;'>Root Cause: {item['root_cause']}</strong>
                                    <span style='background-color:rgba(0, 242, 254, 0.15); color:#00f2fe; padding:0.2rem 0.6rem; border-radius:6px; font-size:0.75rem; font-weight:700;'>
                                        🔄 RAG Reuse Frequency: {item['reuse_count']} times
                                    </span>
                                </div>
                                <div style='font-size:0.9rem; color:#888; margin-bottom:0.5rem;'>Incident Category: {item['incident_type']} | Department Owner: {item['department']}</div>
                                <div style='background-color:#141419; padding:0.8rem; border-radius:6px; font-size:0.85rem; color:#DDD; white-space: pre-wrap;'>{item['resolution_steps']}</div>
                            </div>
                        """, unsafe_allow_html=True)
                        
        # TAB 6: Audit Logs
        with tabs[5]:
            st.header("Service Desk Audit Logs")
            st.write("Full history of status transitions, SLA context, and user actions across all tickets.")

            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    h.history_id,
                    h.ticket_id,
                    t.ticket_subject,
                    t.company_name,
                    t.created_date          AS ticket_created_date,
                    t.closed_date           AS ticket_closed_date,
                    t.resolution_time_mins,
                    h.old_status,
                    h.new_status,
                    h.updated_by,
                    h.updated_time          AS action_time,
                    h.remarks,
                    h.sla_mins_remaining,
                    h.sla_status_at_update
                FROM ticket_history h
                JOIN tickets t ON h.ticket_id = t.ticket_id
                ORDER BY h.history_id DESC
            """)
            logs = [dict(row) for row in cursor.fetchall()]
            conn.close()

            if not logs:
                st.info("No audit logs recorded.")
            else:
                audit_rows = []
                for lg in logs:
                    rt = lg.get("resolution_time_mins")
                    rt_str = f"{rt:.0f}m" if rt is not None else "—"
                    sla_rem = lg.get("sla_mins_remaining")
                    sla_rem_str = f"{sla_rem:.0f}m" if sla_rem is not None else "—"
                    audit_rows.append({
                        "Log #":            lg["history_id"],
                        "Ticket #":         lg["ticket_id"],
                        "Subject":          (lg.get("ticket_subject") or "")[:50],
                        "Company":          lg.get("company_name") or "—",
                        "User Action":      lg.get("updated_by") or "—",
                        "Action Time":      lg.get("action_time") or "—",
                        "Status Change":    f"{lg['old_status']} → {lg['new_status']}",
                        "SLA at Action":    sla_rem_str,
                        "SLA Status":       lg.get("sla_status_at_update") or "—",
                        "Created Date":     lg.get("ticket_created_date") or "—",
                        "Completed Date":   lg.get("ticket_closed_date") or "—",
                        "Resolution Time":  rt_str,
                        "Remarks":          (lg.get("remarks") or "")[:80],
                    })
                df_audit = pd.DataFrame(audit_rows)
                st.dataframe(df_audit, use_container_width=True, hide_index=True)
                
        # TAB 7: Continuous Learning Loop
        with tabs[6]:
            st.header("Continuous Learning & Retraining Loop")
            
            st.subheader("1. System Outliers & Anomalies Review")
            st.write("These tickets triggered RAG similarity score < 0.15, meaning they are likely new incident templates that need to be incorporated into the knowledge base.")
            
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT ticket_id, ticket_subject, ticket_description, incident_type, department, final_priority, created_date 
                FROM tickets 
                WHERE failure_case_flag = 1 AND status != 'Done'
            """)
            outliers = [dict(row) for row in cursor.fetchall()]
            conn.close()
            
            if not outliers:
                st.success("✅ No active outlier tickets flagged. All incoming logs correlate cleanly with the historical corpus.")
            else:
                df_out = pd.DataFrame(outliers)
                st.dataframe(df_out, use_container_width=True, hide_index=True)
                
            st.markdown("<hr style='border-color:rgba(255,255,255,0.05)'>", unsafe_allow_html=True)
            
            st.subheader("2. Model Feedback & Dynamic Retraining")
            st.write("As engineers correct routing departments and incident categories, you can trigger active model retraining on the live SQLite database to improve classification precision.")
            
            col_ret1, col_ret2 = st.columns([1, 2])
            with col_ret1:
                if st.button("Trigger Full Model Retraining", type="primary", width='stretch'):
                    with st.spinner("Retraining classifiers on live SQLite transactions..."):
                        try:
                            summary = train_and_save_models()
                            st.success("Models retrained and compiled successfully!")
                            
                            for model_name, metrics in summary.items():
                                st.write(f"**{model_name.upper()} Model:** Accuracy: {metrics['accuracy']:.2%}")
                        except Exception as e:
                            st.error(f"Failed to retrain model: {e}")
            with col_ret2:
                st.info("💡 Clicking retrain reads all ticket records from SQLite, recalculates text TF-IDF tokens, refits Logistic Regression weights for all targets, and updates models in the `models/` directory instantly.")

        # TAB 8: Performance Metrics (Admin only)
        with tabs[7]:
            st.header("📊 Performance Metrics")
            st.write("Enterprise-level MTTR, MTTM, and resolution efficiency KPIs across all ticket categories and priorities.")

            all_tk_pm = get_all_tickets()
            if not all_tk_pm:
                st.info("No ticket data available yet. Ingest tickets to view performance metrics.")
            else:
                df_pm = pd.DataFrame(all_tk_pm)

                # ── Compute closed ticket subset ──────────────────────────
                closed_pm = df_pm[df_pm["status"] == "Done"].copy()

                # MTTR: avg minutes from created_date to closed_date
                def _safe_mttr(df_closed):
                    if df_closed.empty:
                        return 0.0
                    vals = []
                    for _, row in df_closed.iterrows():
                        try:
                            created = datetime.strptime(str(row["created_date"]), "%Y-%m-%d %H:%M:%S")
                            closed  = datetime.strptime(str(row["closed_date"]),  "%Y-%m-%d %H:%M:%S")
                            vals.append((closed - created).total_seconds() / 60.0)
                        except Exception:
                            if row.get("resolution_time_mins") is not None:
                                vals.append(float(row["resolution_time_mins"]))
                    return round(sum(vals) / len(vals), 1) if vals else 0.0

                overall_mttr = _safe_mttr(closed_pm)

                # Use resolution_time_mins as direct MTTR if datetime parse unavailable
                if overall_mttr == 0.0 and not closed_pm.empty:
                    col_res = pd.to_numeric(closed_pm["resolution_time_mins"], errors="coerce")
                    overall_mttr = round(col_res.dropna().mean(), 1) if not col_res.dropna().empty else 0.0

                # MTTM: avg time from creation to FIRST status change in ticket_history
                conn_pm = get_connection()
                cursor_pm = conn_pm.cursor()
                cursor_pm.execute("""
                    SELECT h.ticket_id, MIN(h.updated_time) as first_action, t.created_date
                    FROM ticket_history h
                    JOIN tickets t ON h.ticket_id = t.ticket_id
                    WHERE h.new_status != 'New'
                    GROUP BY h.ticket_id
                """)
                mttm_rows = cursor_pm.fetchall()
                conn_pm.close()

                mttm_vals = []
                for row in mttm_rows:
                    try:
                        created_dt = datetime.strptime(str(row[1]), "%Y-%m-%d %H:%M:%S")
                        action_dt  = datetime.strptime(str(row[2]), "%Y-%m-%d %H:%M:%S")
                        diff = abs((created_dt - action_dt).total_seconds() / 60.0)
                        if diff < 43200:  # ignore outliers > 30 days
                            mttm_vals.append(diff)
                    except Exception:
                        pass
                overall_mttm = round(sum(mttm_vals) / len(mttm_vals), 1) if mttm_vals else 0.0

                # Resolution Success Rate
                total_pm   = len(df_pm)
                closed_cnt = len(closed_pm)
                success_rate = round((closed_cnt / total_pm * 100), 1) if total_pm > 0 else 0.0

                # Average Resolution Time (from resolution_time_mins column)
                res_col = pd.to_numeric(closed_pm["resolution_time_mins"], errors="coerce").dropna()
                avg_res_time = round(res_col.mean(), 1) if not res_col.empty else 0.0

                # ── KPI Cards row ─────────────────────────────────────────
                pm_card_style = (
                    "background:#1E1E24;border-radius:12px;padding:1.4rem 1rem;"
                    "border:1px solid rgba(255,255,255,0.07);"
                    "box-shadow:0 4px 12px rgba(0,0,0,0.25);"
                    "text-align:center;"
                )

                kc1, kc2, kc3, kc4 = st.columns(4)
                with kc1:
                    st.markdown(f"""
                        <div style='{pm_card_style}'>
                            <div style='font-size:0.75rem;color:#888;text-transform:uppercase;
                                letter-spacing:0.7px;margin-bottom:0.4rem;'>Overall MTTR</div>
                            <div style='font-size:2rem;font-weight:800;color:#00f2fe;'>{overall_mttr:.1f}m</div>
                            <div style='font-size:0.72rem;color:#555;margin-top:0.3rem;'>Mean Time To Resolve</div>
                        </div>
                    """, unsafe_allow_html=True)
                with kc2:
                    st.markdown(f"""
                        <div style='{pm_card_style}'>
                            <div style='font-size:0.75rem;color:#888;text-transform:uppercase;
                                letter-spacing:0.7px;margin-bottom:0.4rem;'>Overall MTTM</div>
                            <div style='font-size:2rem;font-weight:800;color:#FF9F43;'>{overall_mttm:.1f}m</div>
                            <div style='font-size:0.72rem;color:#555;margin-top:0.3rem;'>Mean Time To Mitigate</div>
                        </div>
                    """, unsafe_allow_html=True)
                with kc3:
                    rate_color = "#2ECC71" if success_rate >= 70 else ("#F3CB06" if success_rate >= 40 else "#FF4B4B")
                    st.markdown(f"""
                        <div style='{pm_card_style}'>
                            <div style='font-size:0.75rem;color:#888;text-transform:uppercase;
                                letter-spacing:0.7px;margin-bottom:0.4rem;'>Resolution Success Rate</div>
                            <div style='font-size:2rem;font-weight:800;color:{rate_color};'>{success_rate:.1f}%</div>
                            <div style='font-size:0.72rem;color:#555;margin-top:0.3rem;'>Closed / Total × 100</div>
                        </div>
                    """, unsafe_allow_html=True)
                with kc4:
                    st.markdown(f"""
                        <div style='{pm_card_style}'>
                            <div style='font-size:0.75rem;color:#888;text-transform:uppercase;
                                letter-spacing:0.7px;margin-bottom:0.4rem;'>Avg Resolution Time</div>
                            <div style='font-size:2rem;font-weight:800;color:#4facfe;'>{avg_res_time:.1f}m</div>
                            <div style='font-size:0.72rem;color:#555;margin-top:0.3rem;'>Across completed tickets</div>
                        </div>
                    """, unsafe_allow_html=True)

                st.markdown("<br>", unsafe_allow_html=True)

                # ── MTTR by Incident Category ─────────────────────────────
                chart_col1, chart_col2 = st.columns(2)

                with chart_col1:
                    st.subheader("MTTR by Incident Category")
                    if closed_pm.empty:
                        st.info("No resolved tickets to compute MTTR by category.")
                    else:
                        # Compute MTTR per incident_type
                        mttr_by_cat = []
                        for cat, grp in closed_pm.groupby("incident_type"):
                            res_col_cat = pd.to_numeric(grp["resolution_time_mins"], errors="coerce").dropna()
                            if not res_col_cat.empty:
                                mttr_by_cat.append({"Incident Type": cat, "MTTR (mins)": round(res_col_cat.mean(), 1)})
                        if mttr_by_cat:
                            df_mttr_cat = pd.DataFrame(mttr_by_cat).sort_values("MTTR (mins)", ascending=True)
                            fig_cat = px.bar(
                                df_mttr_cat,
                                x="MTTR (mins)",
                                y="Incident Type",
                                orientation="h",
                                title="Average Resolution Time per Incident Category",
                                color="MTTR (mins)",
                                color_continuous_scale=[[0, "#2ECC71"], [0.5, "#F3CB06"], [1, "#FF4B4B"]],
                                template="plotly_dark"
                            )
                            fig_cat.update_layout(
                                margin=dict(t=50, b=20, l=10, r=10),
                                height=380,
                                coloraxis_showscale=False,
                                plot_bgcolor="rgba(0,0,0,0)",
                                paper_bgcolor="rgba(0,0,0,0)"
                            )
                            fig_cat.update_xaxes(gridcolor="rgba(255,255,255,0.05)")
                            fig_cat.update_yaxes(gridcolor="rgba(255,255,255,0.05)")
                            st.plotly_chart(fig_cat, use_container_width=True)
                        else:
                            st.info("Insufficient data to plot MTTR by category.")

                with chart_col2:
                    st.subheader("MTTR by Priority")
                    if closed_pm.empty:
                        st.info("No resolved tickets to compute MTTR by priority.")
                    else:
                        priority_order = ["Critical", "High", "Medium", "Low"]
                        prio_colors    = {"Critical": "#FF4B4B", "High": "#FF9F43", "Medium": "#F3CB06", "Low": "#2ECC71"}
                        mttr_by_prio = []
                        for prio in priority_order:
                            grp = closed_pm[closed_pm["final_priority"] == prio]
                            if grp.empty:
                                continue
                            res_col_prio = pd.to_numeric(grp["resolution_time_mins"], errors="coerce").dropna()
                            if not res_col_prio.empty:
                                mttr_by_prio.append({"Priority": prio, "MTTR (mins)": round(res_col_prio.mean(), 1)})
                        if mttr_by_prio:
                            df_mttr_prio = pd.DataFrame(mttr_by_prio)
                            fig_prio_pm = px.bar(
                                df_mttr_prio,
                                x="Priority",
                                y="MTTR (mins)",
                                title="Average Resolution Time per Priority Level",
                                color="Priority",
                                color_discrete_map=prio_colors,
                                template="plotly_dark"
                            )
                            fig_prio_pm.update_layout(
                                margin=dict(t=50, b=20, l=10, r=10),
                                height=380,
                                showlegend=False,
                                plot_bgcolor="rgba(0,0,0,0)",
                                paper_bgcolor="rgba(0,0,0,0)"
                            )
                            fig_prio_pm.update_xaxes(gridcolor="rgba(255,255,255,0.05)")
                            fig_prio_pm.update_yaxes(gridcolor="rgba(255,255,255,0.05)")
                            st.plotly_chart(fig_prio_pm, use_container_width=True)
                        else:
                            st.info("Insufficient data to plot MTTR by priority.")

                # ── Engineer Performance Table ────────────────────────────
                st.markdown("<br>", unsafe_allow_html=True)
                st.subheader("🧑‍💻 Engineer Performance Breakdown")

                # Only look at closed tickets with an assigned engineer
                eng_df = closed_pm[closed_pm["assigned_engineer"].notna() & (closed_pm["assigned_engineer"] != "")].copy()
                if eng_df.empty:
                    st.info("No resolved tickets with assigned engineers yet.")
                else:
                    eng_stats = []
                    for eng, grp in eng_df.groupby("assigned_engineer"):
                        res_col_eng = pd.to_numeric(grp["resolution_time_mins"], errors="coerce").dropna()
                        sla_met_eng = len(grp[grp["sla_status"] == "Met"])
                        sla_compliance_eng = round((sla_met_eng / len(grp)) * 100, 1) if len(grp) > 0 else 0.0
                        eng_stats.append({
                            "Engineer": eng,
                            "Tickets Resolved": len(grp),
                            "Avg Resolution (min)": round(res_col_eng.mean(), 1) if not res_col_eng.empty else 0.0,
                            "SLA Met %": sla_compliance_eng,
                            "SLA Breaches": len(grp[grp["sla_status"] == "Breached"])
                        })
                    df_eng_stats = pd.DataFrame(eng_stats).sort_values("Tickets Resolved", ascending=False)

                    eng_ch1, eng_ch2 = st.columns(2)
                    with eng_ch1:
                        fig_eng_bar = px.bar(
                            df_eng_stats,
                            x="Engineer",
                            y="Tickets Resolved",
                            color="SLA Met %",
                            color_continuous_scale=[[0, "#FF4B4B"], [0.5, "#F3CB06"], [1, "#2ECC71"]],
                            range_color=[0, 100],
                            title="Tickets Resolved per Engineer (color = SLA %)",
                            template="plotly_dark"
                        )
                        fig_eng_bar.update_layout(
                            margin=dict(t=50, b=60, l=10, r=10), height=360,
                            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)"
                        )
                        fig_eng_bar.update_xaxes(tickangle=-30, gridcolor="rgba(255,255,255,0.05)")
                        fig_eng_bar.update_yaxes(gridcolor="rgba(255,255,255,0.05)")
                        st.plotly_chart(fig_eng_bar, use_container_width=True)

                    with eng_ch2:
                        fig_eng_sla = px.bar(
                            df_eng_stats,
                            x="Engineer",
                            y="Avg Resolution (min)",
                            color="Avg Resolution (min)",
                            color_continuous_scale=[[0, "#2ECC71"], [0.5, "#F3CB06"], [1, "#FF4B4B"]],
                            title="Avg Resolution Time per Engineer (mins)",
                            template="plotly_dark"
                        )
                        fig_eng_sla.update_layout(
                            margin=dict(t=50, b=60, l=10, r=10), height=360,
                            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                            coloraxis_showscale=False
                        )
                        fig_eng_sla.update_xaxes(tickangle=-30, gridcolor="rgba(255,255,255,0.05)")
                        fig_eng_sla.update_yaxes(gridcolor="rgba(255,255,255,0.05)")
                        st.plotly_chart(fig_eng_sla, use_container_width=True)

                    st.dataframe(df_eng_stats, use_container_width=True, hide_index=True)

                # ── Monthly Resolution Trend ──────────────────────────────
                st.markdown("<br>", unsafe_allow_html=True)
                st.subheader("📅 Monthly Resolution Trend")

                if closed_pm.empty:
                    st.info("No closed tickets to plot monthly trend.")
                else:
                    trend_df = closed_pm.copy()
                    try:
                        trend_df["month"] = pd.to_datetime(trend_df["closed_date"], errors="coerce").dt.to_period("M").astype(str)
                        monthly = trend_df.groupby("month").agg(
                            Resolved=("ticket_id", "count"),
                            Avg_Resolution_Mins=("resolution_time_mins", "mean")
                        ).reset_index().rename(columns={"month": "Month"})
                        monthly["Avg_Resolution_Mins"] = monthly["Avg_Resolution_Mins"].round(1)

                        if len(monthly) > 0:
                            fig_trend = go.Figure()
                            fig_trend.add_trace(go.Bar(
                                x=monthly["Month"],
                                y=monthly["Resolved"],
                                name="Tickets Resolved",
                                marker_color="rgba(79,172,254,0.7)",
                                yaxis="y1"
                            ))
                            fig_trend.add_trace(go.Scatter(
                                x=monthly["Month"],
                                y=monthly["Avg_Resolution_Mins"],
                                name="Avg Resolution (mins)",
                                mode="lines+markers",
                                line=dict(color="#FF9F43", width=2),
                                marker=dict(size=6),
                                yaxis="y2"
                            ))
                            fig_trend.update_layout(
                                title="Monthly Ticket Volume & Avg Resolution Time",
                                template="plotly_dark",
                                plot_bgcolor="rgba(0,0,0,0)",
                                paper_bgcolor="rgba(0,0,0,0)",
                                height=380,
                                margin=dict(t=50, b=40, l=10, r=50),
                                yaxis=dict(title="Tickets Resolved", gridcolor="rgba(255,255,255,0.05)"),
                                yaxis2=dict(
                                    title="Avg Resolution (mins)",
                                    overlaying="y",
                                    side="right",
                                    gridcolor="rgba(255,255,255,0)"
                                ),
                                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                            )
                            st.plotly_chart(fig_trend, use_container_width=True)
                        else:
                            st.info("Not enough data for monthly trend.")
                    except Exception as trend_err:
                        st.warning(f"Could not render monthly trend: {trend_err}")

                # ── Gemini AI Engine Status ───────────────────────────────
                st.markdown("<br>", unsafe_allow_html=True)
                st.subheader("🤖 AI Engine Status")
                api_key_present = bool(os.environ.get("GEMINI_API_KEY", "").strip())
                gemini_col1, gemini_col2 = st.columns(2)
                with gemini_col1:
                    if api_key_present:
                        st.markdown("""
                            <div style='background:rgba(46,204,113,0.08);border:1px solid rgba(46,204,113,0.3);border-radius:10px;padding:1rem;text-align:center;'>
                                <div style='font-size:1.5rem;'>🟢</div>
                                <div style='font-weight:700;color:#2ECC71;margin:0.3rem 0;'>Gemini API Key Detected</div>
                                <div style='font-size:0.8rem;color:#888;'>AI-powered resolution engine is active</div>
                            </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.markdown("""
                            <div style='background:rgba(255,75,75,0.08);border:1px solid rgba(255,75,75,0.3);border-radius:10px;padding:1rem;text-align:center;'>
                                <div style='font-size:1.5rem;'>🔴</div>
                                <div style='font-weight:700;color:#FF4B4B;margin:0.3rem 0;'>No Gemini API Key</div>
                                <div style='font-size:0.8rem;color:#888;'>Add GEMINI_API_KEY to .env — falling back to RAG</div>
                            </div>
                        """, unsafe_allow_html=True)
                with gemini_col2:
                    ticket_count_val = len(df_pm)
                    closed_count_val = len(closed_pm)
                    gemini_tickets = len(df_pm[df_pm["ai_recommended_resolution"].str.contains("Root Cause:", na=False)]) if ticket_count_val > 0 else 0
                    gemini_pct = round((gemini_tickets / ticket_count_val) * 100, 1) if ticket_count_val > 0 else 0.0
                    st.markdown(f"""
                        <div style='background:#1E1E24;border:1px solid rgba(255,255,255,0.07);border-radius:10px;padding:1rem;text-align:center;'>
                            <div style='font-size:0.75rem;color:#888;text-transform:uppercase;letter-spacing:0.6px;'>AI-Resolved Tickets</div>
                            <div style='font-size:2rem;font-weight:800;color:#4facfe;'>{gemini_pct:.1f}%</div>
                            <div style='font-size:0.75rem;color:#555;'>{gemini_tickets} of {ticket_count_val} tickets used Gemini</div>
                        </div>
                    """, unsafe_allow_html=True)

    # ----------------------------------------------------
    # COMPANY USER VIEW
    # ----------------------------------------------------
    elif user['role'] == 'Company User':
        st.write(f"Company Portal for: **{user['company_name']}**")
        tabs = st.tabs(["Submit New Ticket", "Company Tickets Archive", "Company SLA Insights"])
        
        # TAB 1: Submit New Ticket
        with tabs[0]:
            st.header("Submit Support Ticket")
            st.write("Submit a request on behalf of your company. The cognitive engine will analyze and route it automatically.")
            
            with st.form("company_new_ticket_form", clear_on_submit=True):
                st.markdown(f"**Company Name:** `{user['company_name']}`")
                
                col_n, col_e = st.columns(2)
                with col_n:
                    employee_name = st.text_input("Employee Name", placeholder="e.g. Jane Smith")
                with col_e:
                    employee_email = st.text_input("Employee Email", placeholder="e.g. jane@tcs.com")
                    
                ticket_subject = st.text_input("Ticket Subject", placeholder="Short summary of the issue")
                ticket_description = st.text_area("Detailed Ticket Description", placeholder="Describe full symptoms...", height=150)
                
                submitted = st.form_submit_button("Submit Ticket", type="primary", use_container_width=True)
                
                if submitted:
                    if employee_name and employee_email and ticket_subject and ticket_description:
                        tid, t_dict, rag = execute_ticket_creation_pipeline(
                            user["company_name"], employee_name, employee_email, 
                            ticket_subject, ticket_description, "Service Portal"
                        )
                        st.success(f"Ticket #{tid} successfully created and processed!")
                        
                        # Show pipeline results instantly
                        st.markdown("### 🤖 Cognitive Analytics Summary")
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.info(f"**Routed Dept:**\n{t_dict['department']}")
                        with col2:
                            st.info(f"**ML Priority:** {t_dict['ml_priority']}\n**Keyword Priority:** {t_dict['keyword_priority']}\n**Final Priority:** {t_dict['final_priority']}")
                        with col3:
                            st.info(f"**Predicted Category:**\n{t_dict['incident_type']}")
                        with col4:
                            st.info(f"**Customer Sentiment:**\n{t_dict['sentiment']}")
                            
                        # Show RAG
                        st.markdown("#### 📖 Retrieval-Augmented Recommendations")
                        if rag["is_outlier"]:
                            st.warning(f"⚠️ Outlier Warning: Max Similarity Score is {rag['max_similarity']:.2%}. The issue doesn't match past templates.")
                        else:
                            st.success(f"✅ Similarity match high: {rag['max_similarity']:.2%}")
                            
                        res_details = get_resolution_details(t_dict)
                        st.markdown(f"**Root Cause:**  \n{res_details['root_cause']}")
                        st.markdown(f"**Resolution Steps:**  \n{res_details['resolution_steps']}")
                        st.markdown(f"**Escalation Required:**  \n{res_details['escalation_required']}")
                        st.markdown(f"**Recommended Team:**  \n{res_details['recommended_team']}")
                        
                        st.markdown("**Similar Tickets:**")
                        if rag.get("similar_tickets"):
                            similar_matches = [m for m in rag["similar_tickets"] if m["ticket"]["ticket_id"] != tid]
                            if similar_matches:
                                for match in similar_matches:
                                    st_t = match["ticket"]
                                    st_score = match["score"]
                                    st.markdown(
                                        f"- **Ticket #{st_t['ticket_id']}** (Match: {st_score:.1%}) - "
                                        f"**Subject:** {st_t['ticket_subject']} - "
                                        f"**Incident Type:** {st_t['incident_type']}"
                                    )
                                    with st.expander(f"View details for Ticket #{st_t['ticket_id']}"):
                                        st.write("**Root Cause:**", st_t.get("root_cause", "Undetermined"))
                                        st.write("**Resolution:**", st_t.get("resolution_steps", "No steps available."))
                            else:
                                st.write("No similar tickets found.")
                        else:
                            st.write("No similar tickets found.")
                    else:
                        st.error("Please fill in all mandatory fields.")
                        
        # TAB 2: Company Tickets Archive
        with tabs[1]:
            st.header("Company Tickets Archive")
            
            filters = {"company_name": user["company_name"]}
            tickets_list = get_all_tickets(filters)
            
            if not tickets_list:
                st.info("No tickets created by your company yet.")
            else:
                from kanban import apply_priority_aging, sort_tickets, compute_sla_remaining
                
                aged_tickets = apply_priority_aging(tickets_list)
                sorted_tickets = sort_tickets(aged_tickets)
                
                table_rows = []
                for t in sorted_tickets:
                    rem, st_val = compute_sla_remaining(t)
                    prio = t.get("final_priority", "Low")
                    if t.get("_aged"):
                        prio_display = f"{prio} ⬆️"
                    else:
                        prio_display = prio
                        
                    if st_val == "Done":
                        sla_display = "Closed"
                    elif st_val == "Breached":
                        late = int(abs(rem)) if rem is not None else 0
                        sla_display = f"🔴 Breached (+{late}m)"
                    elif rem is not None:
                        sla_display = f"⏳ {int(rem)}m left"
                    else:
                        sla_display = "—"
                        
                    table_rows.append({
                        "ID": f"#{t['ticket_id']}",
                        "Employee": t.get("employee_name", "—"),
                        "Subject": t.get("ticket_subject", "—"),
                        "Category": t.get("incident_type", "—"),
                        "Priority": prio_display,
                        "Department": t.get("department", "—"),
                        "Status": t.get("status", "New"),
                        "Engineer": t.get("assigned_engineer") or "—",
                        "SLA Countdown": sla_display,
                        "SLA Status": t.get("sla_status", "—"),
                        "Created Date": t.get("created_date", "—")
                    })
                
                df_display = pd.DataFrame(table_rows)
                st.dataframe(df_display, use_container_width=True, hide_index=True)
                
                # Interactive expander to view specific ticket details read-only
                st.markdown("### 🔍 View Ticket Details")
                ticket_ids = [t['ticket_id'] for t in sorted_tickets]
                view_id = st.selectbox("Select Ticket ID to View Details", [""] + [f"#{tid}" for tid in ticket_ids], key="comp_t_view")
                
                if view_id:
                    v_id = int(view_id.replace("#", ""))
                    t_detail = next((tk for tk in sorted_tickets if tk["ticket_id"] == v_id), None)
                    if t_detail:
                        st.markdown(f"#### Ticket #{v_id}: {t_detail['ticket_subject']}")
                        st.write("**Employee:**", t_detail["employee_name"], f"({t_detail['employee_email']})")
                        st.write("**Description:**", t_detail["ticket_description"])
                        st.write("**Sentiment:**", t_detail["sentiment"])
                        st.write("**Status:**", t_detail["status"])
                        st.write("**Priority:**", t_detail["final_priority"] + (" ⬆️ (Aged)" if t_detail.get("_aged") else ""))
                        st.write("**SLA Countdown:**", sla_display)
                        
                        st.markdown("**History Audit Trail:**")
                        history = get_ticket_history(v_id)
                        if not history:
                            st.info("No audit logs for this ticket.")
                        else:
                            hist_data = []
                            for h in history:
                                rem_val = h.get("sla_mins_remaining")
                                rem_str = f"{rem_val}m" if rem_val is not None else "—"
                                hist_data.append({
                                    "Time": h["updated_time"],
                                    "User": h["updated_by"],
                                    "Change": f"{h['old_status']} ➡️ {h['new_status']}",
                                    "Remarks": h["remarks"] or "—",
                                    "SLA Remaining": rem_str,
                                    "SLA Status": h.get("sla_status_at_update") or "—"
                                })
                            st.dataframe(hist_data, use_container_width=True, hide_index=True)

        # TAB 3: Company SLA Insights
        with tabs[2]:
            st.header("Company SLA Insights")
            st.write("Track whether your service commitments are being consistently met and identify recurring SLA violations.")

            from database import get_connection as _gc
            _conn = _gc()
            _cur  = _conn.cursor()
            company_nm = user["company_name"]

            _cur.execute("SELECT COUNT(*) FROM tickets WHERE company_name=?", (company_nm,))
            sla_total = _cur.fetchone()[0] or 0

            _cur.execute("SELECT COUNT(*) FROM tickets WHERE company_name=? AND status='Done'", (company_nm,))
            sla_closed = _cur.fetchone()[0] or 0

            _cur.execute("SELECT COUNT(*) FROM tickets WHERE company_name=? AND sla_status='Met'", (company_nm,))
            sla_met = _cur.fetchone()[0] or 0

            _cur.execute("SELECT COUNT(*) FROM company_sla_history WHERE company_name=?", (company_nm,))
            sla_breaches = _cur.fetchone()[0] or 0

            _cur.execute("SELECT AVG(resolution_time_mins) FROM tickets WHERE company_name=? AND status='Done'", (company_nm,))
            avg_res_row = _cur.fetchone()[0]
            avg_res = round(avg_res_row, 1) if avg_res_row else 0.0

            _conn.close()

            compliance_pct = round((sla_met / sla_closed * 100), 1) if sla_closed > 0 else 100.0
            risk_score = min(100, round((sla_breaches / max(sla_total, 1)) * 100 + (100 - compliance_pct) * 0.5))
            risk_label = "🔴 High" if risk_score >= 40 else ("🟡 Moderate" if risk_score >= 15 else "🟢 Low")
            repeated_breach = sla_breaches >= 3

            # KPI cards row
            c1, c2, c3, c4 = st.columns(4)
            card_style = "background:#1E1E24;border-radius:10px;padding:1rem;border:1px solid rgba(255,255,255,0.06);text-align:center;"
            with c1:
                st.markdown(f"<div style='{card_style}'><div style='font-size:0.72rem;color:#666;text-transform:uppercase;letter-spacing:0.6px;'>Total Tickets</div><div style='font-size:2rem;font-weight:700;color:#FFF;'>{sla_total}</div></div>", unsafe_allow_html=True)
            with c2:
                st.markdown(f"<div style='{card_style}'><div style='font-size:0.72rem;color:#666;text-transform:uppercase;letter-spacing:0.6px;'>Closed in SLA</div><div style='font-size:2rem;font-weight:700;color:#2ECC71;'>{sla_met}</div></div>", unsafe_allow_html=True)
            with c3:
                st.markdown(f"<div style='{card_style}'><div style='font-size:0.72rem;color:#666;text-transform:uppercase;letter-spacing:0.6px;'>SLA Breaches</div><div style='font-size:2rem;font-weight:700;color:#FF4B4B;'>{sla_breaches}</div></div>", unsafe_allow_html=True)
            with c4:
                st.markdown(f"<div style='{card_style}'><div style='font-size:0.72rem;color:#666;text-transform:uppercase;letter-spacing:0.6px;'>Compliance %</div><div style='font-size:2rem;font-weight:700;color:#4facfe;'>{compliance_pct:.0f}%</div></div>", unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            c5, c6 = st.columns(2)
            with c5:
                st.markdown(f"<div style='{card_style}'><div style='font-size:0.72rem;color:#666;text-transform:uppercase;letter-spacing:0.6px;'>Avg Resolution Time</div><div style='font-size:1.6rem;font-weight:700;color:#F3CB06;'>{avg_res}m</div></div>", unsafe_allow_html=True)
            with c6:
                risk_color = "#FF4B4B" if risk_score >= 40 else ("#F3CB06" if risk_score >= 15 else "#2ECC71")
                st.markdown(f"<div style='{card_style}'><div style='font-size:0.72rem;color:#666;text-transform:uppercase;letter-spacing:0.6px;'>Company Risk Score</div><div style='font-size:1.6rem;font-weight:700;color:{risk_color};'>{risk_score} — {risk_label}</div></div>", unsafe_allow_html=True)

            if repeated_breach:
                st.markdown("<br>", unsafe_allow_html=True)
                st.error(f"⚠️ Repeated Breach Warning: **{company_nm}** has {sla_breaches} recorded SLA violations. Service commitments are at risk. Escalation recommended.")
            else:
                st.markdown("<br>", unsafe_allow_html=True)
                st.success(f"✅ {company_nm} has maintained acceptable SLA performance. No repeated breach pattern detected.")

            # SLA Compliance progress bar
            st.markdown("### SLA Compliance Rate")
            compliance_bar_color = "#2ECC71" if compliance_pct >= 80 else ("#F3CB06" if compliance_pct >= 50 else "#FF4B4B")
            st.markdown(f"""
                <div style='background:rgba(255,255,255,0.05);border-radius:8px;height:18px;margin-bottom:0.5rem;overflow:hidden;'>
                    <div style='width:{compliance_pct:.0f}%;background:{compliance_bar_color};height:100%;border-radius:8px;
                    transition:width 0.6s ease;'></div>
                </div>
                <div style='font-size:0.8rem;color:#777;'>{compliance_pct:.1f}% of closed tickets met the SLA commitment</div>
            """, unsafe_allow_html=True)

    # ----------------------------------------------------
    # DEPARTMENT USER VIEW
    # ----------------------------------------------------
    else:
        st.write(f"Department Panel for: **{user['department']}**")
        tabs = st.tabs(["Active Kanban Board", "SLA Dashboard", "History Audit Trail"])
        
        # TAB 1: Kanban Board
        with tabs[0]:
            st.header(f"{user['department']} Kanban")
            all_tk = get_all_tickets()
            display_kanban(all_tk, user['department'], user)
            
        # TAB 2: Department SLA Dashboard with charts
        with tabs[1]:
            st.header("SLA & Performance Dashboard")

            all_tk = get_all_tickets()
            dept_tk = [t for t in all_tk if t["department"] == user["department"]]

            if not dept_tk:
                st.info("No tickets assigned to your department queue.")
            else:
                df = pd.DataFrame(dept_tk)
                total    = len(df)
                open_tk  = len(df[df["status"] != "Done"])
                closed_tk = len(df[df["status"] == "Done"])
                closed_df = df[df["status"] == "Done"]
                if len(closed_df) > 0:
                    sla_met    = len(closed_df[closed_df["sla_status"] == "Met"])
                    compliance = (sla_met / len(closed_df)) * 100
                    avg_speed  = closed_df["resolution_time_mins"].mean()
                else:
                    compliance = 100.0
                    avg_speed  = 0.0
                breaches = len(df[df["sla_status"] == "Breached"])

                # Metric cards
                m1, m2, m3, m4, m5 = st.columns(5)
                card_s = "background:#1E1E24;border-radius:10px;padding:1rem;border:1px solid rgba(255,255,255,0.06);text-align:center;"
                with m1: st.markdown(f"<div style='{card_s}'><div style='font-size:0.72rem;color:#666;text-transform:uppercase;'>Total</div><div style='font-size:1.7rem;font-weight:700;color:#FFF;'>{total}</div></div>", unsafe_allow_html=True)
                with m2: st.markdown(f"<div style='{card_s}'><div style='font-size:0.72rem;color:#666;text-transform:uppercase;'>Open</div><div style='font-size:1.7rem;font-weight:700;color:#FF9F43;'>{open_tk}</div></div>", unsafe_allow_html=True)
                with m3: st.markdown(f"<div style='{card_s}'><div style='font-size:0.72rem;color:#666;text-transform:uppercase;'>Resolved</div><div style='font-size:1.7rem;font-weight:700;color:#2ECC71;'>{closed_tk}</div></div>", unsafe_allow_html=True)
                with m4: st.markdown(f"<div style='{card_s}'><div style='font-size:0.72rem;color:#666;text-transform:uppercase;'>SLA Met %</div><div style='font-size:1.7rem;font-weight:700;color:#4facfe;'>{compliance:.0f}%</div></div>", unsafe_allow_html=True)
                with m5: st.markdown(f"<div style='{card_s}'><div style='font-size:0.72rem;color:#666;text-transform:uppercase;'>Avg Time</div><div style='font-size:1.7rem;font-weight:700;color:#F3CB06;'>{avg_speed:.0f}m</div></div>", unsafe_allow_html=True)

                st.markdown("<br>", unsafe_allow_html=True)

                # Three charts
                ch1, ch2, ch3 = st.columns(3)
                with ch1:
                    inc_dist = df["incident_type"].value_counts().reset_index()
                    fig_inc = px.pie(
                        inc_dist, values="count", names="incident_type",
                        title="Incident Types", hole=0.4,
                        template="plotly_dark",
                        color_discrete_sequence=px.colors.qualitative.Pastel
                    )
                    fig_inc.update_layout(margin=dict(t=40, b=10, l=10, r=10), height=300)
                    st.plotly_chart(fig_inc, use_container_width=True)

                with ch2:
                    prio_dist = df["final_priority"].value_counts().reset_index()
                    fig_prio = px.pie(
                        prio_dist, values="count", names="final_priority",
                        title="Priority Breakdown",
                        color_discrete_map={"Critical": "#FF4B4B", "High": "#FF9F43", "Medium": "#F3CB06", "Low": "#2ECC71"},
                        template="plotly_dark"
                    )
                    fig_prio.update_layout(margin=dict(t=40, b=10, l=10, r=10), height=300)
                    st.plotly_chart(fig_prio, use_container_width=True)

                with ch3:
                    sla_dist = df["sla_status"].value_counts().reset_index()
                    fig_sla = px.pie(
                        sla_dist, values="count", names="sla_status",
                        title="SLA Compliance", hole=0.5,
                        color_discrete_map={"Met": "#2ECC71", "Breached": "#FF4B4B", "In Progress": "#4facfe"},
                        template="plotly_dark"
                    )
                    fig_sla.update_layout(margin=dict(t=40, b=10, l=10, r=10), height=300)
                    st.plotly_chart(fig_sla, use_container_width=True)

        # TAB 3: Audit Trail (enhanced columns)
        with tabs[2]:
            st.header("Department Ticket Activity Logs")

            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    h.history_id,
                    h.ticket_id,
                    t.ticket_subject,
                    t.created_date          AS ticket_created_date,
                    t.closed_date           AS ticket_closed_date,
                    t.resolution_time_mins,
                    h.old_status,
                    h.new_status,
                    h.updated_by,
                    h.updated_time          AS action_time,
                    h.remarks,
                    h.sla_mins_remaining,
                    h.sla_status_at_update
                FROM ticket_history h
                JOIN tickets t ON h.ticket_id = t.ticket_id
                WHERE t.department = ?
                ORDER BY h.history_id DESC
            """, (user["department"],))
            logs = [dict(row) for row in cursor.fetchall()]
            conn.close()

            if not logs:
                st.info("No transitions logged.")
            else:
                audit_rows = []
                for lg in logs:
                    rt = lg.get("resolution_time_mins")
                    rt_str = f"{rt:.0f}m" if rt is not None else "—"
                    sla_rem = lg.get("sla_mins_remaining")
                    sla_rem_str = f"{sla_rem:.0f}m" if sla_rem is not None else "—"
                    audit_rows.append({
                        "Ticket #":         lg["ticket_id"],
                        "Subject":          (lg.get("ticket_subject") or "")[:45],
                        "User Action":      lg.get("updated_by") or "—",
                        "Action Time":      lg.get("action_time") or "—",
                        "Status Change":    f"{lg['old_status']} → {lg['new_status']}",
                        "SLA at Action":    sla_rem_str,
                        "SLA Status":       lg.get("sla_status_at_update") or "—",
                        "Created Date":     lg.get("ticket_created_date") or "—",
                        "Completed Date":   lg.get("ticket_closed_date") or "—",
                        "Resolution Time":  rt_str,
                        "Remarks":          (lg.get("remarks") or "")[:60],
                    })
                st.dataframe(pd.DataFrame(audit_rows), use_container_width=True, hide_index=True)

    # ----------------------------------------------------
    # PERSISTENT SELECTED TICKET PANEL (auto-scrolls into view)
    # ----------------------------------------------------
    if st.session_state["selected_ticket_id"] is not None:
        sel_id = st.session_state["selected_ticket_id"]

        # Auto-scroll JS — fires once when panel opens
        st.markdown("""
            <div id="ticket-panel-anchor"></div>
            <script>
                window.setTimeout(function() {
                    var el = document.getElementById('ticket-panel-anchor');
                    if (el) { el.scrollIntoView({behavior: 'smooth', block: 'start'}); }
                }, 200);
            </script>
        """, unsafe_allow_html=True)

        # Load ticket details
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tickets WHERE ticket_id = ?", (sel_id,))
        ticket = cursor.fetchone()
        conn.close()

        if ticket:
            ticket = dict(ticket)

            # Security check
            if user['role'] not in ('Admin', 'Department User') or (user['role'] == 'Department User' and ticket['department'] != user['department']):
                st.error("Access Denied: You are not authorized to edit this ticket.")
                st.session_state["selected_ticket_id"] = None
                st.rerun()

            st.markdown("<hr style='border-color:#00f2fe;border-width:2px;margin-top:1.5rem;'>", unsafe_allow_html=True)
            st.markdown(f"## 🛠️ Ticket Resolution Panel — Ticket #{sel_id}")
            
            # Historical SLA breach warning
            from database import get_company_breach_count
            breach_count = get_company_breach_count(ticket['company_name'])
            if breach_count > 0:
                st.warning(f"⚠️ SLA Violation Alert: {ticket['company_name']} has {breach_count} historical SLA breaches. Please prioritize this ticket accordingly!")
            
            col_d1, col_d2 = st.columns([2, 1])
            
            with col_d1:
                st.markdown(f"### **Subject:** {ticket['ticket_subject']}")
                st.markdown(f"**Company:** {ticket['company_name']} | **Employee:** {ticket['employee_name']} ({ticket['employee_email']})")
                st.markdown(f"**Description:** {ticket['ticket_description']}")
                st.markdown(f"**Created On:** {ticket['created_date']} | **Channel:** {ticket['received_channel']}")
                
                st.markdown("#### ⚙️ AI Resolution Insights")
                st.write("**Predicted Incident Type:**", ticket["incident_type"])
                st.write("**Sentiment:**", ticket["sentiment"])
                
                res_details = get_resolution_details(ticket)
                
                st.markdown(f"**Root Cause:**  \n{res_details['root_cause']}")
                st.markdown(f"**Resolution Steps:**  \n{res_details['resolution_steps']}")
                st.markdown(f"**Escalation Required:**  \n{res_details['escalation_required']}")
                st.markdown(f"**Recommended Team:**  \n{res_details['recommended_team']}")
                
                st.markdown("**Similar Tickets:**")
                from rag_engine import find_similar_tickets
                t_text = f"{ticket['ticket_subject']}. {ticket['ticket_description']}"
                similar_matches = find_similar_tickets(t_text)
                
                # Filter out the current ticket
                similar_matches = [m for m in similar_matches if m["ticket"]["ticket_id"] != ticket["ticket_id"]]
                
                if similar_matches:
                    for match in similar_matches:
                        st_t = match["ticket"]
                        st_score = match["score"]
                        st.markdown(
                            f"- **Ticket #{st_t['ticket_id']}** (Match: {st_score:.1%}) - "
                            f"**Subject:** {st_t['ticket_subject']} - "
                            f"**Incident Type:** {st_t['incident_type']}"
                        )
                        with st.expander(f"View details for Ticket #{st_t['ticket_id']}"):
                            st.write("**Root Cause:**", st_t.get("root_cause", "Undetermined"))
                            st.write("**Resolution:**", st_t.get("resolution_steps", "No steps available."))
                else:
                    st.write("No similar tickets found.")
                
            with col_d2:
                st.markdown("### 📝 Resolve / Update Case")
                
                # Form fields to edit ticket properties
                active_status = ticket["status"]
                active_engineer = ticket["assigned_engineer"] or ""
                active_remarks = ticket["engineer_remarks"] or ""
                
                status_opts = ["New", "In Progress", "Escalated", "Done"]
                new_status = st.selectbox("Update Status", status_opts, index=status_opts.index(active_status))
                
                # Choose engineer based on department lists
                t_dept = ticket["department"]
                dept_engineers = ENGINEERS.get(t_dept, ["Support Staff"])
                
                eng_opts = [""] + dept_engineers
                eng_index = eng_opts.index(active_engineer) if active_engineer in eng_opts else 0
                new_engineer = st.selectbox("Assign Engineer", eng_opts, index=eng_index)
                
                # Feedback loop: allow correction of department & category (Module 8)
                st.markdown("**Continuous Learning Review**")
                corr_dept = st.selectbox("Correct Department Routing", DEPARTMENTS, index=DEPARTMENTS.index(ticket["department"]))
                corr_cat = st.selectbox("Correct Incident Type", ["Network", "Hardware", "Software", "Access", "Messaging", "Application", "Database", "Security", "HR"], index=["Network", "Hardware", "Software", "Access", "Messaging", "Application", "Database", "Security", "HR"].index(ticket["incident_type"]))
                
                new_remarks = st.text_area("Engineer Remarks", value=active_remarks, height=100)
                
                col_b1, col_b2 = st.columns(2)
                with col_b1:
                    if st.button("Save Updates", type="primary", width='stretch'):
                        # Save continuous learning corrections if changed
                        if corr_dept != ticket["department"] or corr_cat != ticket["incident_type"]:
                            conn = get_connection()
                            cursor = conn.cursor()
                            cursor.execute("""
                                UPDATE tickets 
                                SET department = ?, incident_type = ?, failure_case_flag = 1
                                WHERE ticket_id = ?
                            """, (corr_dept, corr_cat, sel_id))
                            conn.commit()
                            conn.close()
                            
                        # Save workflow status updates
                        update_ticket_workflow(
                            sel_id, new_status, new_remarks, 
                            new_engineer if new_engineer != "" else None, 
                            user["username"]
                        )
                        st.success("Ticket details saved successfully!")
                        st.session_state["selected_ticket_id"] = None
                        st.rerun()
                with col_b2:
                    if st.button("Dismiss Panel", width='stretch'):
                        st.session_state["selected_ticket_id"] = None
                        st.rerun()
            
            # Display detailed history audit trail below
            st.markdown("### 📜 Ticket Audit Trail")
            history = get_ticket_history(sel_id)
            if not history:
                st.info("No audit logs for this ticket.")
            else:
                hist_data = []
                for h in history:
                    rem_val = h.get("sla_mins_remaining")
                    rem_str = f"{rem_val}m" if rem_val is not None else "—"
                    hist_data.append({
                        "Time": h["updated_time"],
                        "User": h["updated_by"],
                        "Change": f"{h['old_status']} ➡️ {h['new_status']}",
                        "Remarks": h["remarks"] or "—",
                        "SLA Remaining": rem_str,
                        "SLA Status": h.get("sla_status_at_update") or "—"
                    })
                st.dataframe(hist_data, use_container_width=True, hide_index=True)
