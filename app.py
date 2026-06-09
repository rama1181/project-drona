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
    get_workspace_stats, get_sla_dashboard_aggregates, get_audit_logs,
    get_department_audit_logs, get_department_sla_aggregates,
)
from auth import login, logout, apply_authenticated_layout
from priority_engine import resolve_priority
from routing_engine import route_department
from sla_engine import evaluate_sla, get_sla_mins
from rag_engine import get_rag_recommendations
from kanban import display_kanban
from train_model import train_and_save_models
from generate_dataset import COMPANIES, DEPARTMENTS, ENGINEERS
import re
from ticket_processor import TicketProcessor

def get_resolution_details(ticket_dict):
    raw_ai = ticket_dict.get("ai_recommended_resolution") or ""
    
    # Defaults
    root_cause = ticket_dict.get("root_cause") or "Undetermined"
    resolution_steps = ticket_dict.get("resolution_steps") or "No resolution steps available."
    escalation_required = "Yes" if ticket_dict.get("escalation_required") == 1 else "No"
    recommended_team = ticket_dict.get("department") or "Service Desk L1"
    
    # Try parsing from raw_ai if it has the LLM structured format
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

# Initialize Session State with persistence
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
    st.session_state['_login_initialized'] = True
if 'user' not in st.session_state:
    st.session_state['user'] = None
if 'selected_ticket_id' not in st.session_state:
    st.session_state['selected_ticket_id'] = None

# Initialize Database Schema & Data (once per server process)
@st.cache_resource
def _ensure_db_ready():
    init_db()
    seed_users()

_ensure_db_ready()

ADMIN_TABS = [
    "All Support Tickets",
    "Unified Kanban Board",
    "Leadership SLA Dashboard",
    "Root Cause Knowledge Base",
    "Audit Logs",
    "Continuous Learning Loop",
    "Performance Metrics",
]


@st.cache_data(ttl=60, show_spinner=False)
def _cached_workspace_stats(role, department, company_name):
    return get_workspace_stats(role, department, company_name)


@st.cache_data(ttl=120, show_spinner=False)
def _cached_sla_dashboard():
    return get_sla_dashboard_aggregates()

# Load classification models helper
MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")

@st.cache_resource
def get_ticket_processor():
    try:
        # Load the Hybrid ML/LLM processor
        # Ensure we pass the groq key from env if available
        groq_key = os.environ.get("GROQ_API_KEY")
        processor = TicketProcessor(models_dir=MODELS_DIR, groq_api_key=groq_key, confidence_threshold=0.65)
        return processor
    except Exception as e:
        st.error(f"Failed to load TicketProcessor: {e}")
        return None

def predict_ticket_fields(ticket_text, processor=None):
    """
    Predicts incident_type, priority, department, and sentiment 
    using the Hybrid TicketProcessor. Falls back gracefully if models are missing.
    """
    preds = {
        "incident_type": "Access",
        "priority": "Low",
        "department": "Service Desk L1",
        "sentiment": "Neutral",
        "recommended_action": "",
        "classification_source": "default",
        "llm_fallback_used": False,
        "low_confidence_fields": [],
    }
    
    if processor is None:
        processor = get_ticket_processor()
    if processor is not None:
        try:
            result = processor.process_ticket(ticket_text)
            preds["incident_type"] = result.get('category', 'Access')
            preds["priority"] = result.get('priority', 'Low')
            preds["department"] = result.get('department', 'Service Desk L1')
            preds["sentiment"] = result.get('sentiment', 'Neutral')
            preds["recommended_action"] = result.get('recommended_action', '')
            preds["classification_source"] = result.get('classification_source', 'ml')
            preds["llm_fallback_used"] = result.get('llm_fallback_used', False)
            preds["low_confidence_fields"] = result.get('low_confidence_fields', [])
        except Exception as e:
            st.error(f"Error executing hybrid model predictions: {e}")
            
    return preds

# Main ticket pipeline processor
def execute_ticket_creation_pipeline(company, employee, email, subject, description, channel):
    """Executes the full AI ticket pipeline: ML classification, Priority, RAG, SLA, Routing & Saving."""
    ticket_text = f"{subject}. {description}"
    created_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 1. Classification (ML + LLM hybrid predictions)
    processor = get_ticket_processor()
    preds = predict_ticket_fields(ticket_text, processor=processor)
    
    # 2. Priority Engine (Hybrid logic)
    ml_prio, kw_prio, final_prio = resolve_priority(ticket_text, preds["priority"])
    
    # 2b. Check for historical SLA breaches and apply escalation
    from database import check_and_apply_company_priority_escalation
    escalated_prio, escalation_reason = check_and_apply_company_priority_escalation(company, final_prio)
    if escalation_reason:
        final_prio = escalated_prio
    
    # 3. Routing Engine (Department Assignment)
    routed_dept = route_department(preds["incident_type"], subject, description, preds["department"])
    
    # 4. RAG Engine Retrieval (with ML-based filtering for speed and accuracy)
    rag_rec = get_rag_recommendations(
        ticket_text,
        department=routed_dept,           # Filter by predicted department
        incident_type=preds["incident_type"],  # Filter by predicted incident type
        priority=final_prio               # Filter by priority level
    )

    # 5. Groq LLM Resolution Generation (RAG context + LLM synthesis)
    resolution_source = "rag"
    if processor and processor.llm_client:
        try:
            llm_resolution = processor.llm_client.generate_resolution(
                subject, description,
                preds["incident_type"], final_prio, routed_dept, preds["sentiment"],
                rag_similar_tickets=rag_rec.get("similar_tickets", [])
            )
            
            if llm_resolution['success']:
                # Use LLM-generated resolution
                rag_rec["predicted_root_cause"] = llm_resolution["root_cause"]
                rag_rec["recommended_resolution"] = llm_resolution["full_response"]
                resolution_source = llm_resolution["source"]
                resolution_steps = llm_resolution["resolution_steps"]
                escalation_required_llm = llm_resolution["escalation_required"]
            else:
                # LLM failed, use RAG fallback
                print(f"LLM Resolution failed: {llm_resolution.get('error')}")
                resolution_steps = rag_rec["recommended_resolution"]
                escalation_required_llm = "No"
        except Exception as e:
            print(f"LLM Resolution Error: {e}")
            resolution_steps = rag_rec["recommended_resolution"]
            escalation_required_llm = "No"
    else:
        # No LLM client available, use RAG only
        resolution_steps = rag_rec["recommended_resolution"]
        escalation_required_llm = "No"
    rag_rec["resolution_source"] = resolution_source
    rag_rec["classification_source"] = preds.get("classification_source", "ml")
    rag_rec["llm_fallback_used"] = preds.get("llm_fallback_used", False)
    rag_rec["low_confidence_fields"] = preds.get("low_confidence_fields", [])

    # 6. SLA Engine
    sla_mins = get_sla_mins(final_prio)
    
    # Merge Hybrid Engine Recommendation with LLM/RAG
    final_ai_resolution = rag_rec["recommended_resolution"]
    if preds.get("recommended_action"):
        final_ai_resolution = f"**[Hybrid Engine Recommendation]**\n{preds['recommended_action']}\n\n---\n{final_ai_resolution}"
    
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
        "resolution_steps": resolution_steps if 'resolution_steps' in locals() else rag_rec["recommended_resolution"],
        "ai_recommended_resolution": final_ai_resolution,
        "status": "New",
        "assigned_engineer": None,
        "engineer_remarks": "",
        "created_date": created_date,
        "closed_date": None,
        "resolution_time_mins": None,
        "sla_mins": sla_mins,
        "sla_status": "In Progress",
        "escalation_required": 1 if (escalation_reason or (escalation_required_llm == "Yes")) else 0,
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
# Debug: Show session state (remove after debugging)
if st.sidebar.checkbox("🐛 Debug Mode", value=False):
    st.sidebar.write("Session State:", {
        'logged_in': st.session_state.get('logged_in'),
        'user': st.session_state.get('user', {}).get('username') if st.session_state.get('user') else None
    })

if not st.session_state.get('logged_in', False):
    login()
    st.stop()

apply_authenticated_layout()
user = st.session_state['user']

if st.session_state.pop('_login_welcome', None):
    st.toast(f"Welcome {st.session_state['user']['username']}!", icon="✅")

# Sidebar Navigation & Profile
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

    t_total, t_closed, t_open = _cached_workspace_stats(
        user['role'],
        user.get('department'),
        user.get('company_name'),
    )

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
    # Initialize active tab in session state
    if 'admin_active_tab' not in st.session_state:
        st.session_state.admin_active_tab = ADMIN_TABS[0]
    
    # Radio navigation for lazy loading
    admin_tab = st.radio(
        "Admin Navigation",
        ADMIN_TABS,
        horizontal=True,
        label_visibility="collapsed",
        key="admin_active_tab",
    )

    # TAB 1: All Tickets (with searching, filtering, editing, exporting)
    if admin_tab == ADMIN_TABS[0]:
            st.header("Unified Support Tickets Database")
            
            # Initialize pagination state
            if 'current_page' not in st.session_state:
                st.session_state.current_page = 1
            if 'page_size' not in st.session_state:
                st.session_state.page_size = 100
            
            col_fs, col_fp, col_fd = st.columns(3)
            with col_fs:
                search_q = st.text_input("Search (Subject, Description, Company)", key="all_t_search")
            with col_fp:
                prio_q = st.selectbox("Filter Priority", ["All", "High", "Medium", "Low"])
            with col_fd:
                dept_q = st.selectbox("Filter Department", ["All"] + DEPARTMENTS)
                
            filters = {
                "search": search_q,
                "priority": None if prio_q == "All" else prio_q,
                "department": None if dept_q == "All" else dept_q
            }
            
            # Get paginated results
            result = get_all_tickets(filters, page=st.session_state.current_page, page_size=st.session_state.page_size)
            tickets_list = result['tickets']
            total_count = result['total_count']
            total_pages = result['total_pages']
            current_page = result['current_page']
            
            # Display pagination info
            st.markdown(f"""
                <div style='background:#1E1E24; padding:0.8rem; border-radius:8px; margin-bottom:1rem; border:1px solid rgba(255,255,255,0.05);'>
                    📊 Showing <strong>{len(tickets_list)}</strong> tickets (Page <strong>{current_page}</strong> of <strong>{total_pages}</strong>) | Total: <strong>{total_count:,}</strong> tickets
                </div>
            """, unsafe_allow_html=True)
            
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
                
                # Pagination Controls
                col_prev, col_info, col_next, col_size = st.columns([1, 2, 1, 1])
                with col_prev:
                    if st.button("⬅️ Previous", disabled=(current_page <= 1), key="prev_page"):
                        st.session_state.current_page = max(1, current_page - 1)
                        st.rerun()
                with col_info:
                    st.markdown(f"<div style='text-align:center; padding-top:0.3rem; color:#888;'>Page {current_page} / {total_pages}</div>", unsafe_allow_html=True)
                with col_next:
                    if st.button("Next ➡️", disabled=(current_page >= total_pages), key="next_page"):
                        st.session_state.current_page = min(total_pages, current_page + 1)
                        st.rerun()
                with col_size:
                    new_size = st.selectbox("Per Page", [50, 100, 200, 500], index=1, key="page_size_select")
                    if new_size != st.session_state.page_size:
                        st.session_state.page_size = new_size
                        st.session_state.current_page = 1  # Reset to first page
                        st.rerun()
                
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
                    
    # TAB 2: Unified Kanban Board
    elif admin_tab == ADMIN_TABS[1]:
            st.header("Enterprise Kanban Workflow")
            
            selected_kanban_dept = st.selectbox("Kanban Department View", ["All Departments"] + DEPARTMENTS)
            dept_filter = None if selected_kanban_dept == "All Departments" else selected_kanban_dept
            
            # Load only first 500 tickets for Kanban (performance)
            all_tk_result = get_all_tickets(page=1, page_size=500)
            all_tk = all_tk_result['tickets']
            display_kanban(all_tk, dept_filter, user)
            
    # TAB 3: SLA Dashboard & Charts
    elif admin_tab == ADMIN_TABS[2]:
            st.header("Executive Leadership SLA Dashboard")

            with st.spinner("Loading SLA dashboard..."):
                agg = _cached_sla_dashboard()

            if not agg.get('total'):
                st.info("Ingest tickets first to review operational charts.")
            else:
                total_tickets = agg['total']
                open_tickets = agg['open_count']
                closed_tickets = agg['closed_count']
                sla_compliance = agg['sla_compliance']
                avg_res = agg['avg_res']
                sla_breaches = agg['breaches']
                
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
                    workload_df = pd.DataFrame(agg['workload'])
                    fig_w = px.bar(
                        workload_df, x="department", y="counts", color="status",
                        title="Workload Queue Status per Department",
                        color_discrete_map={"New": "#5398ff", "In Progress": "#FF9F43", "Escalated": "#FF4B4B", "Done": "#2ECC71"},
                        template="plotly_dark"
                    )
                    st.plotly_chart(fig_w, use_container_width=True)
                    
                with col_chart2:
                    st.subheader("Incident Types Distribution")
                    inc_dist = pd.DataFrame(agg['incident_dist'])
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
                    prio_dist = pd.DataFrame(agg['priority_dist'])
                    fig_p = px.pie(
                        prio_dist, values="count", names="final_priority",
                        title="Resolved SLA Priorities",
                        color_discrete_map={"High": "#FF4B4B", "Medium": "#F3CB06", "Low": "#2ECC71"},
                        template="plotly_dark"
                    )
                    st.plotly_chart(fig_p, use_container_width=True)
                    
                with col_chart4:
                    st.subheader("SLA Compliance Metrics")
                    sla_dist = pd.DataFrame(agg['sla_dist'])
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
                    
                    failure_count = agg.get('failure_count') or 0
                    routing_accuracy = 1.0 - (failure_count / total_tickets if total_tickets > 0 else 0)
                    closure_rate = closed_tickets / total_tickets if total_tickets > 0 else 0.0
                    kb_coverage = 1.0 - (failure_count / total_tickets if total_tickets > 0 else 0)
                    
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
                    dept_stats = {row['department']: row for row in agg['dept_capacity']}
                    for dept in DEPARTMENTS:
                        row = dept_stats.get(dept, {})
                        d_open = int(row.get('d_open') or 0)
                        d_closed = int(row.get('d_closed') or 0)
                        d_avg_res = row.get('d_avg_res') or 0.0
                        d_avg_res = 0.0 if d_avg_res is None or (isinstance(d_avg_res, float) and np.isnan(d_avg_res)) else float(d_avg_res)

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
                    
    # TAB 4: Root Cause & Resolution Knowledge Base
    elif admin_tab == ADMIN_TABS[3]:
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
                        
    # TAB 5: Audit Logs
    elif admin_tab == ADMIN_TABS[4]:
            st.header("Service Desk Audit Logs")
            st.write("Full history of status transitions, SLA context, and user actions across all tickets.")

            if 'audit_page' not in st.session_state:
                st.session_state.audit_page = 1

            audit_result = get_audit_logs(page=st.session_state.audit_page, page_size=200)
            logs = audit_result['logs']

            st.caption(
                f"Showing page {audit_result['current_page']} of {audit_result['total_pages']} "
                f"({audit_result['total_count']:,} total log entries)"
            )
            col_ap, col_an = st.columns(2)
            with col_ap:
                if st.button("⬅️ Older logs", disabled=audit_result['current_page'] <= 1, key="audit_prev"):
                    st.session_state.audit_page = max(1, audit_result['current_page'] - 1)
                    st.rerun()
            with col_an:
                if st.button("Newer logs ➡️", disabled=audit_result['current_page'] >= audit_result['total_pages'], key="audit_next"):
                    st.session_state.audit_page = min(audit_result['total_pages'], audit_result['current_page'] + 1)
                    st.rerun()

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
                
    # TAB 6: Continuous Learning Loop
    elif admin_tab == ADMIN_TABS[5]:
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
                st.warning("XGBoost Hybrid Model Retraining is disabled in UI due to high memory/compute requirements.")
                st.code("python train_xgboost_model.py")
            with col_ret2:
                st.info("💡 Retraining the XGBoost models requires running the offline training script to re-embed tickets with SentenceTransformers and train gradient boosting trees.")


    # TAB 7: Performance Metrics (Admin only)
    elif admin_tab == ADMIN_TABS[6]:
            st.header("📊 Performance Metrics")
            st.write("Enterprise-level MTTR, MTTM, and resolution efficiency KPIs across all ticket categories and priorities.")

            all_tk_pm = get_all_tickets(page=1, page_size=5000)['tickets']
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
                        priority_order = ["High", "Medium", "Low"]
                        prio_colors    = {"High": "#FF4B4B", "Medium": "#F3CB06", "Low": "#2ECC71"}
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

                # ── Groq AI Engine Status ───────────────────────────────
                st.markdown("<br>", unsafe_allow_html=True)
                st.subheader("🤖 AI Engine Status")
                groq_key_present = bool(os.environ.get("GROQ_API_KEY", "").strip())
                ai_col1, ai_col2 = st.columns(2)
                with ai_col1:
                    if groq_key_present:
                        st.markdown("""
                            <div style='background:rgba(46,204,113,0.08);border:1px solid rgba(46,204,113,0.3);border-radius:10px;padding:1rem;text-align:center;'>
                                <div style='font-size:1.5rem;'>🟢</div>
                                <div style='font-weight:700;color:#2ECC71;margin:0.3rem 0;'>Groq API Key Detected</div>
                                <div style='font-size:0.8rem;color:#888;'>AI-powered resolution engine is active</div>
                            </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.markdown("""
                            <div style='background:rgba(255,181,71,0.08);border:1px solid rgba(255,181,71,0.3);border-radius:10px;padding:1rem;text-align:center;'>
                                <div style='font-size:1.5rem;'>🟡</div>
                                <div style='font-weight:700;color:#FFB547;margin:0.3rem 0;'>No Groq API Key</div>
                                <div style='font-size:0.8rem;color:#888;'>Add GROQ_API_KEY to .env for AI resolutions — falling back to RAG</div>
                            </div>
                        """, unsafe_allow_html=True)
                with ai_col2:
                    ticket_count_val = len(df_pm)
                    closed_count_val = len(closed_pm)
                    ai_tickets = len(df_pm[df_pm["ai_recommended_resolution"].str.contains("Root Cause:", na=False)]) if ticket_count_val > 0 else 0
                    ai_pct = round((ai_tickets / ticket_count_val) * 100, 1) if ticket_count_val > 0 else 0.0
                    st.markdown(f"""
                        <div style='background:#1E1E24;border:1px solid rgba(255,255,255,0.07);border-radius:10px;padding:1rem;text-align:center;'>
                            <div style='font-size:0.75rem;color:#888;text-transform:uppercase;letter-spacing:0.6px;'>AI-Resolved Tickets</div>
                            <div style='font-size:2rem;font-weight:800;color:#4facfe;'>{ai_pct:.1f}%</div>
                            <div style='font-size:0.75rem;color:#555;'>{ai_tickets} of {ticket_count_val} tickets used LLM AI</div>
                        </div>
                    """, unsafe_allow_html=True)

# ----------------------------------------------------
# COMPANY USER VIEW
# ----------------------------------------------------
elif user['role'] == 'Company User':
        st.write(f"Company Portal for: **{user['company_name']}**")
        
        # Initialize active tab in session state
        if 'company_active_tab' not in st.session_state:
            st.session_state.company_active_tab = "Submit New Ticket"
        
        # Radio navigation for lazy loading
        company_tab = st.radio(
            "Company Navigation",
            ["Submit New Ticket", "Company Tickets Archive", "Company SLA Insights"],
            horizontal=True,
            label_visibility="collapsed",
            key="company_active_tab",
        )
        
        # TAB 1: Submit New Ticket
        if company_tab == "Submit New Ticket":
            st.header("Submit Support Ticket")
            st.write("Submit a request on behalf of your company. The cognitive engine will analyze and route it automatically.")
            
            # Sample tickets dropdown for quick testing
            SAMPLE_TICKETS = {
                "-- Select a sample or create your own --": {
                    "subject": "",
                    "description": "",
                    "employee": "",
                    "email": ""
                },
                "🚨 Critical: Production Database Down": {
                    "subject": "URGENT: Production Database Server Completely Unresponsive",
                    "description": "CRITICAL INCIDENT - Our production database server crashed at 2:15 PM and is completely down. All customer-facing services are unavailable affecting approximately 50,000 active users. Error logs show: 'Fatal: Database connection pool exhausted'. Multiple connection timeout errors. This is causing massive revenue loss estimated at $10,000 per hour. Need immediate escalation to senior database team. All backup attempts have failed.",
                    "employee": "John Peterson",
                    "email": "john.peterson@company.com"
                },
                "🔒 VPN Connection Issues": {
                    "subject": "Unable to Connect to Company VPN - Timeout Errors",
                    "description": "I've been unable to connect to the company VPN since this morning. I've tried multiple troubleshooting steps: 1) Restarted my laptop 3 times, 2) Reinstalled the VPN client, 3) Tested on different WiFi networks, 4) Cleared VPN cache. Still getting 'Authentication failed - Connection timeout' error. I need access to internal systems urgently for client meetings scheduled today. This is blocking critical work.",
                    "employee": "Sarah Mitchell",
                    "email": "sarah.mitchell@company.com"
                },
                "🐌 Slow Computer Performance": {
                    "subject": "Laptop Running Extremely Slow - Productivity Impact",
                    "description": "My laptop has been running very slowly for the past week. Boot time takes over 10 minutes, applications freeze constantly, and even simple tasks like opening emails take 30+ seconds. I've tried: closing unnecessary programs, restarting multiple times, running Windows Update, and checking for malware. Nothing helps. CPU usage shows 100% constantly even with minimal programs open. This is severely affecting my productivity. Not blocking work completely but making everything take 3x longer.",
                    "employee": "Mike Anderson",
                    "email": "mike.anderson@company.com"
                },
                "👤 New Employee Access Request": {
                    "subject": "Access Request for New Employee - Shared Drives and Systems",
                    "description": "I'm a new employee who started last Monday. I need access to the following resources to complete my onboarding: 1) Marketing shared drive (read/write access), 2) Project management system (Jira), 3) Email distribution lists for my team, 4) Customer database (read-only), 5) VPN access for remote work. My manager is Jennifer Williams in the Marketing department. My employee ID is EMP-2847. Please grant appropriate permissions.",
                    "employee": "Lisa Chen",
                    "email": "lisa.chen@company.com"
                },
                "🔑 Password Reset - Account Locked": {
                    "subject": "Password Reset Needed - Account Locked After Failed Attempts",
                    "description": "I forgot my password and my account is now locked after multiple failed login attempts. I've tried using the self-service password reset portal but it says my account is locked and I need to contact IT support. I urgently need access to my email and internal systems to complete time-sensitive client deliverables. My employee ID is EMP-5829. Can you please unlock my account and help me reset the password?",
                    "employee": "Robert Davis",
                    "email": "robert.davis@company.com"
                },
                "🖨️ Printer Malfunction - Paper Jam": {
                    "subject": "3rd Floor Printer Jammed - Multiple Users Affected",
                    "description": "The HP LaserJet printer on the 3rd floor (east wing, near conference room B) is showing a 'Paper Jam' error and won't print anything. I've opened all the paper trays and checked inside but can't find any stuck paper. Multiple team members are waiting to print important documents for a client presentation this afternoon at 3 PM. About 8 people are affected. Can someone from IT come take a look as soon as possible?",
                    "employee": "David Park",
                    "email": "david.park@company.com"
                },
                "📧 Email Not Receiving Attachments": {
                    "subject": "Email Blocking All Attachments - Security Filter Issue",
                    "description": "For the past 2 days, I'm not receiving any email attachments. Emails arrive but show 'Attachment removed for security reasons' even for legitimate documents from known senders. This is blocking critical work as clients are sending contracts, invoices, and project documents that I need to review urgently. The documents are standard PDFs and Word files, nothing suspicious. Other colleagues can receive attachments fine. Need this investigated and fixed ASAP.",
                    "employee": "Jennifer Lee",
                    "email": "jennifer.lee@company.com"
                },
                "❓ Office 365 Features Question": {
                    "subject": "Questions About Office 365 Features and Capabilities",
                    "description": "I have a few questions about our Office 365 subscription and what features are available: 1) Can I use Microsoft Teams for external meetings with clients? What are the guest access limitations? 2) What's the storage limit for OneDrive and can it be increased? 3) Is there a way to schedule emails in Outlook to send at a specific time? 4) Can I access Office apps on my personal tablet? Not urgent, just want to understand our capabilities better to improve my workflow.",
                    "employee": "Emma Wilson",
                    "email": "emma.wilson@company.com"
                },
                "🔐 Security: Suspicious Email Received": {
                    "subject": "Potential Phishing Email - Security Concern",
                    "description": "I received a suspicious email this morning that appears to be a phishing attempt. The email claims to be from our IT department asking me to 'verify my credentials' by clicking a link and entering my password. The sender address looks similar to our domain but slightly different (example@comp4ny.com instead of company.com). The email has urgent language and threatens account suspension. I did NOT click the link or provide any information. Reporting this for security team awareness and in case other employees received similar emails.",
                    "employee": "Alex Turner",
                    "email": "alex.turner@company.com"
                },
                "💻 Software Installation Request": {
                    "subject": "Request to Install Adobe Creative Suite for Marketing Work",
                    "description": "I need Adobe Creative Suite (Photoshop, Illustrator, InDesign) installed on my laptop for upcoming marketing campaign work. My role requires creating graphics, editing images, and designing promotional materials. My manager (Karen Smith, Marketing Director) has approved this software installation. I have a project deadline next week so would appreciate if this could be installed within the next few days. My laptop model is Dell Latitude 5420. Let me know if you need any additional approvals or information.",
                    "employee": "Chris Martinez",
                    "email": "chris.martinez@company.com"
                }
            }
            
            # Dropdown for sample tickets
            st.markdown("### 🎯 Quick Test with Sample Tickets")
            sample_choice = st.selectbox(
                "Choose a pre-filled sample ticket to test the AI classification:",
                options=list(SAMPLE_TICKETS.keys()),
                key="sample_ticket_choice"
            )
            
            st.markdown("---")
            
            with st.form("company_new_ticket_form", clear_on_submit=True):
                st.markdown(f"**Company Name:** `{user['company_name']}`")
                
                # Get sample data if selected
                sample_data = SAMPLE_TICKETS[sample_choice]
                
                col_n, col_e = st.columns(2)
                with col_n:
                    employee_name = st.text_input(
                        "Employee Name", 
                        value=sample_data["employee"],
                        placeholder="e.g. Jane Smith"
                    )
                with col_e:
                    employee_email = st.text_input(
                        "Employee Email", 
                        value=sample_data["email"],
                        placeholder="e.g. jane@company.com"
                    )
                    
                ticket_subject = st.text_input(
                    "Ticket Subject", 
                    value=sample_data["subject"],
                    placeholder="Short summary of the issue"
                )
                ticket_description = st.text_area(
                    "Detailed Ticket Description", 
                    value=sample_data["description"],
                    placeholder="Describe full symptoms...", 
                    height=150
                )
                
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
                            
                        # Show RAG + LLM recommendations
                        st.markdown("#### 📖 AI Recommendations (RAG + LLM)")
                        if rag["is_outlier"]:
                            st.warning(f"⚠️ Outlier Warning: Max Similarity Score is {rag['max_similarity']:.2%}. The issue doesn't match past templates.")
                        else:
                            st.success(f"✅ Similarity match high: {rag['max_similarity']:.2%}")

                        res_source = rag.get("resolution_source", "rag")
                        if res_source == "groq_llm":
                            st.caption("Root cause & resolution: **Groq LLM** (informed by similar tickets below)")
                        else:
                            st.caption("Root cause & resolution: **RAG fallback** (copied from similar tickets — LLM was unavailable or failed)")

                        if rag.get("classification_source") == "hybrid":
                            st.caption(f"Classification: **ML + LLM hybrid** (LLM replaced low-confidence fields: {', '.join(rag.get('low_confidence_fields', []))})")
                        else:
                            st.caption("Classification: **ML models** (all fields above confidence threshold)")
                            
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
        elif company_tab == "Company Tickets Archive":
            st.header("Company Tickets Archive")
            
            # Initialize pagination for company view
            if 'company_page' not in st.session_state:
                st.session_state.company_page = 1
            
            filters = {"company_name": user["company_name"]}
            result = get_all_tickets(filters, page=st.session_state.company_page, page_size=100)
            tickets_list = result['tickets']
            total_count = result['total_count']
            total_pages = result['total_pages']
            current_page = result['current_page']
            
            # Display pagination info
            st.markdown(f"""
                <div style='background:#1E1E24; padding:0.8rem; border-radius:8px; margin-bottom:1rem; border:1px solid rgba(255,255,255,0.05);'>
                    📊 Your Company: <strong>{user["company_name"]}</strong> | Showing <strong>{len(tickets_list)}</strong> tickets (Page <strong>{current_page}/{total_pages}</strong>) | Total: <strong>{total_count:,}</strong>
                </div>
            """, unsafe_allow_html=True)
            
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
        elif company_tab == "Company SLA Insights":
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
# DEPARTMENT USER VIEW
# ----------------------------------------------------
else:
        st.write(f"Department Panel for: **{user['department']}**")
        
        # Initialize active tab in session state
        if 'dept_active_tab' not in st.session_state:
            st.session_state.dept_active_tab = "Active Kanban Board"
        
        # Radio navigation for lazy loading
        dept_tab = st.radio(
            "Department Navigation",
            ["Active Kanban Board", "SLA Dashboard", "History Audit Trail"],
            horizontal=True,
            label_visibility="collapsed",
            key="dept_active_tab",
        )
        
        # TAB 1: Kanban Board
        if dept_tab == "Active Kanban Board":
            st.header(f"{user['department']} Kanban")
            all_tk = get_all_tickets(
                filters={'department': user['department']},
                page=1,
                page_size=500,
            )['tickets']
            display_kanban(all_tk, user['department'], user)
            
        # TAB 2: Department SLA Dashboard with charts (SQL AGGREGATES - NO LARGE LOADS)
        elif dept_tab == "SLA Dashboard":
            st.header("SLA & Performance Dashboard")

            with st.spinner("Loading dashboard metrics..."):
                agg = get_department_sla_aggregates(user['department'])

            if not agg.get('total'):
                st.info("No tickets assigned to your department queue.")
            else:
                total = agg['total']
                open_tk = agg['open_count']
                closed_tk = agg['closed_count']
                compliance = agg['sla_compliance']
                avg_speed = agg['avg_res']
                breaches = agg['breaches']

                # Metric cards
                m1, m2, m3, m4, m5 = st.columns(5)
                card_s = "background:#1E1E24;border-radius:10px;padding:1rem;border:1px solid rgba(255,255,255,0.06);text-align:center;"
                with m1: st.markdown(f"<div style='{card_s}'><div style='font-size:0.72rem;color:#666;text-transform:uppercase;'>Total</div><div style='font-size:1.7rem;font-weight:700;color:#FFF;'>{total}</div></div>", unsafe_allow_html=True)
                with m2: st.markdown(f"<div style='{card_s}'><div style='font-size:0.72rem;color:#666;text-transform:uppercase;'>Open</div><div style='font-size:1.7rem;font-weight:700;color:#FF9F43;'>{open_tk}</div></div>", unsafe_allow_html=True)
                with m3: st.markdown(f"<div style='{card_s}'><div style='font-size:0.72rem;color:#666;text-transform:uppercase;'>Resolved</div><div style='font-size:1.7rem;font-weight:700;color:#2ECC71;'>{closed_tk}</div></div>", unsafe_allow_html=True)
                with m4: st.markdown(f"<div style='{card_s}'><div style='font-size:0.72rem;color:#666;text-transform:uppercase;'>SLA Met %</div><div style='font-size:1.7rem;font-weight:700;color:#4facfe;'>{compliance:.0f}%</div></div>", unsafe_allow_html=True)
                with m5: st.markdown(f"<div style='{card_s}'><div style='font-size:0.72rem;color:#666;text-transform:uppercase;'>Avg Time</div><div style='font-size:1.7rem;font-weight:700;color:#F3CB06;'>{avg_speed:.0f}m</div></div>", unsafe_allow_html=True)

                st.markdown("<br>", unsafe_allow_html=True)

                # Three charts from SQL aggregates
                ch1, ch2, ch3 = st.columns(3)
                with ch1:
                    inc_dist = pd.DataFrame(agg['incident_dist'])
                    if not inc_dist.empty:
                        fig_inc = px.pie(
                            inc_dist, values="count", names="incident_type",
                            title="Incident Types", hole=0.4,
                            template="plotly_dark",
                            color_discrete_sequence=px.colors.qualitative.Pastel
                        )
                        fig_inc.update_layout(margin=dict(t=40, b=10, l=10, r=10), height=300)
                        st.plotly_chart(fig_inc, use_container_width=True)

                with ch2:
                    prio_dist = pd.DataFrame(agg['priority_dist'])
                    if not prio_dist.empty:
                        fig_prio = px.pie(
                            prio_dist, values="count", names="final_priority",
                            title="Priority Breakdown",
                            color_discrete_map={"High": "#FF4B4B", "Medium": "#F3CB06", "Low": "#2ECC71"},
                            template="plotly_dark"
                        )
                        fig_prio.update_layout(margin=dict(t=40, b=10, l=10, r=10), height=300)
                        st.plotly_chart(fig_prio, use_container_width=True)

                with ch3:
                    sla_dist = pd.DataFrame(agg['sla_dist'])
                    if not sla_dist.empty:
                        fig_sla = px.pie(
                            sla_dist, values="count", names="sla_status",
                            title="SLA Compliance", hole=0.5,
                            color_discrete_map={"Met": "#2ECC71", "Breached": "#FF4B4B", "In Progress": "#4facfe"},
                            template="plotly_dark"
                        )
                        fig_sla.update_layout(margin=dict(t=40, b=10, l=10, r=10), height=300)
                        st.plotly_chart(fig_sla, use_container_width=True)

        # TAB 3: Audit Trail with PAGINATION
        elif dept_tab == "History Audit Trail":
            st.header("Department Ticket Activity Logs")

            # Initialize pagination
            if 'dept_audit_page' not in st.session_state:
                st.session_state.dept_audit_page = 1

            audit_result = get_department_audit_logs(
                user['department'],
                page=st.session_state.dept_audit_page,
                page_size=200
            )
            logs = audit_result['logs']

            st.caption(
                f"Showing page {audit_result['current_page']} of {audit_result['total_pages']} "
                f"({audit_result['total_count']:,} total log entries)"
            )
            
            col_ap, col_an = st.columns(2)
            with col_ap:
                if st.button("⬅️ Older logs", disabled=audit_result['current_page'] <= 1, key="dept_audit_prev"):
                    st.session_state.dept_audit_page = max(1, audit_result['current_page'] - 1)
                    st.rerun()
            with col_an:
                if st.button("Newer logs ➡️", disabled=audit_result['current_page'] >= audit_result['total_pages'], key="dept_audit_next"):
                    st.session_state.dept_audit_page = min(audit_result['total_pages'], audit_result['current_page'] + 1)
                    st.rerun()

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
