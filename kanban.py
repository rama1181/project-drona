import streamlit as st
from datetime import datetime

# ─── Constants ────────────────────────────────────────────────────────────────
PRIORITY_ORDER = {"Critical": 1, "High": 2, "Medium": 3, "Low": 4}
PRIORITY_UP    = {"Low": "Medium", "Medium": "High", "High": "Critical", "Critical": "Critical"}
SLA_FALLBACK   = {"Critical": 120, "High": 180, "Medium": 480, "Low": 960}

PRIORITY_COLORS = {
    "Critical": ("#FF4B4B", "rgba(255,75,75,0.18)"),
    "High":     ("#FF9F43", "rgba(255,159,67,0.18)"),
    "Medium":   ("#F3CB06", "rgba(243,203,6,0.18)"),
    "Low":      ("#2ECC71", "rgba(46,204,113,0.18)"),
}

STATUS_META = {
    "New":         ("🔵", "#4facfe", "#0d2035"),
    "In Progress": ("🟡", "#F3CB06", "#1e1a00"),
    "Escalated":   ("🔴", "#FF4B4B", "#260000"),
    "Done":        ("🟢", "#2ECC71", "#001a0d"),
}


# ─── SLA Helpers ──────────────────────────────────────────────────────────────
def compute_sla_remaining(ticket):
    """Returns (minutes_remaining, display_status)."""
    if ticket.get("status") == "Done":
        return None, "Done"
    try:
        created_dt  = datetime.strptime(ticket["created_date"], "%Y-%m-%d %H:%M:%S")
        elapsed_min = (datetime.now() - created_dt).total_seconds() / 60.0
        sla_mins    = ticket.get("sla_mins") or SLA_FALLBACK.get(ticket.get("final_priority", "Low"), 480)
        remaining   = sla_mins - elapsed_min
        status      = "Breached" if remaining < 0 else "In Progress"
        return round(remaining, 0), status
    except Exception:
        return None, ticket.get("sla_status", "Unknown")


def apply_priority_aging(tickets):
    """Display-only aging: bumps priority one level for SLA-exceeded open tickets."""
    aged = []
    for t in tickets:
        t = dict(t)
        if t.get("status") == "Done":
            t["_aged"] = False
            aged.append(t)
            continue
        try:
            created_dt  = datetime.strptime(t["created_date"], "%Y-%m-%d %H:%M:%S")
            elapsed_min = (datetime.now() - created_dt).total_seconds() / 60.0
            sla_mins    = t.get("sla_mins") or SLA_FALLBACK.get(t.get("final_priority", "Low"), 480)
            if elapsed_min > sla_mins:
                old_prio = t["final_priority"]
                new_prio = PRIORITY_UP.get(old_prio, old_prio)
                t["final_priority"] = new_prio
                t["_aged"] = (old_prio != new_prio)
            else:
                t["_aged"] = False
        except Exception:
            t["_aged"] = False
        aged.append(t)
    return aged


def _sort_key(t):
    prio_rank   = PRIORITY_ORDER.get(t.get("final_priority", "Low"), 4)
    is_breached = 0 if t.get("sla_status") == "Breached" else 1
    rem, st_    = compute_sla_remaining(t)
    sla_rem     = rem if rem is not None else 99999
    if st_ == "Breached":
        sla_rem     = -abs(sla_rem)
        is_breached = 0
    return (prio_rank, is_breached, sla_rem, t.get("created_date", ""))


def sort_tickets(tickets):
    return sorted(tickets, key=_sort_key)


# ─── Badge Helpers ────────────────────────────────────────────────────────────
def _sla_pill(remaining, status):
    if status == "Done":
        return "<span style='background:rgba(46,204,113,0.15);color:#2ECC71;padding:2px 8px;border-radius:4px;font-size:0.73rem;font-weight:600;'>✅ Closed</span>"
    if status == "Breached":
        late = int(abs(remaining)) if remaining is not None else 0
        return f"<span style='background:rgba(255,75,75,0.15);color:#FF4B4B;padding:2px 8px;border-radius:4px;font-size:0.73rem;font-weight:700;'>🔴 +{late}m overdue</span>"
    if remaining is not None:
        r = int(remaining)
        if r > 90:
            return f"<span style='background:rgba(46,204,113,0.13);color:#2ECC71;padding:2px 8px;border-radius:4px;font-size:0.73rem;font-weight:600;'>🟢 {r}m left</span>"
        return f"<span style='background:rgba(243,203,6,0.13);color:#F3CB06;padding:2px 8px;border-radius:4px;font-size:0.73rem;font-weight:600;'>🟡 {r}m left</span>"
    return "<span style='color:#555;font-size:0.73rem;'>—</span>"


def _prio_pill(prio, aged=False):
    fg, bg = PRIORITY_COLORS.get(prio, ("#888", "rgba(128,128,128,0.15)"))
    aged_mark = " ⬆" if aged else ""
    return (
        f"<span style='background:{bg};color:{fg};"
        f"padding:2px 9px;border-radius:4px;font-size:0.72rem;font-weight:700;"
        f"letter-spacing:0.3px;'>{prio}{aged_mark}</span>"
    )


# ─── Main Kanban Renderer ─────────────────────────────────────────────────────
def display_kanban(tickets, department_filter=None, current_user=None):
    """
    Renders a vertical-workflow Kanban board:
    - Each status group is a collapsible section stacked vertically.
    - Compact card-row per ticket with subject in readable dark text.
    - Priority pill, SLA countdown pill, engineer, Manage button per row.
    - Enterprise-sorted: Critical > Breached > SLA remaining > created date.
    """
    # Filter
    filtered = [t for t in tickets if t["department"] == department_filter] if department_filter else list(tickets)

    # Apply display-only aging
    filtered = apply_priority_aging(filtered)

    # Group
    groups = {"New": [], "In Progress": [], "Escalated": [], "Done": []}
    for t in filtered:
        s = t.get("status", "New")
        groups.setdefault(s if s in groups else "New", []).append(t)

    # Sort each group
    for k in groups:
        groups[k] = sort_tickets(groups[k])

    is_admin = current_user and current_user.get("role") == "Admin"

    # ── Kanban global CSS ──────────────────────────────────────────────────────
    st.markdown("""
        <style>
        .kb-row {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.55rem 0.8rem;
            border-radius: 8px;
            background: #1a1a22;
            border: 1px solid rgba(255, 255, 255, 0.08);
            margin-bottom: 6px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
        }
        .kb-id    { width: 44px; font-size: 0.75rem; color: #8a8a9a; flex-shrink: 0; font-weight: 600; }
        .kb-subj  { flex: 1; font-size: 0.84rem; font-weight: 600;
                    color: #ffffff; line-height: 1.3; overflow: hidden;
                    white-space: nowrap; text-overflow: ellipsis; }
        .kb-co    { width: 110px; font-size: 0.75rem; color: #c0c0d0; flex-shrink: 0;
                    overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
        .kb-prio  { width: 108px; flex-shrink: 0; }
        .kb-sla   { width: 130px; flex-shrink: 0; }
        .kb-eng   { width: 110px; font-size: 0.75rem; color: #c0c0d0; flex-shrink: 0;
                    overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
        .kb-hdr {
            display: flex; align-items: center; gap: 0.5rem;
            padding: 0 0.8rem 6px;
            font-size: 0.7rem; font-weight: 700; color: #6c757d;
            text-transform: uppercase; letter-spacing: 0.8px;
        }
        .kb-hdr .kb-id    { color: #6c757d; }
        .kb-hdr .kb-subj  { color: #6c757d; }
        .kb-hdr .kb-co    { color: #6c757d; }
        .kb-hdr .kb-prio  { color: #6c757d; }
        .kb-hdr .kb-sla   { color: #6c757d; }
        .kb-hdr .kb-eng   { color: #6c757d; }
        </style>
    """, unsafe_allow_html=True)

    order = [("New", True), ("In Progress", True), ("Escalated", True), ("Done", False)]

    for status_key, expanded in order:
        group = groups[status_key]
        count = len(group)
        emoji, accent, _ = STATUS_META.get(status_key, ("⚪", "#888", "#111"))

        with st.expander(
            f"{emoji} **{status_key}** — {count} ticket{'s' if count != 1 else ''}",
            expanded=expanded
        ):
            if not group:
                st.markdown(
                    f"<div style='text-align:center;padding:1rem;color:#444;font-size:0.82rem;'>"
                    f"No {status_key.lower()} tickets</div>",
                    unsafe_allow_html=True
                )
                continue

            # Column header
            st.markdown(f"""
                <div class="kb-hdr">
                    <span class="kb-id">#</span>
                    <span class="kb-subj">Subject</span>
                    <span class="kb-co">Company</span>
                    <span class="kb-prio">Priority</span>
                    <span class="kb-sla">SLA</span>
                    <span class="kb-eng">Engineer</span>
                </div>
                <div style="height:1px;background:{accent}33;margin:0 0.8rem 6px;"></div>
            """, unsafe_allow_html=True)

            for ticket in group:
                tid       = ticket['ticket_id']
                rem, sla_st = compute_sla_remaining(ticket)
                prio_pill = _prio_pill(ticket.get("final_priority", "Low"), ticket.get("_aged", False))
                sla_pill  = _sla_pill(rem, "Done" if status_key == "Done" else sla_st)
                subject   = (ticket.get("ticket_subject") or "")[:68]
                company   = (ticket.get("company_name") or "—")[:16]
                engineer  = (ticket.get("assigned_engineer") or "—")[:16]

                # Row HTML + manage button side by side
                row_col, btn_col = st.columns([10, 1.2])

                with row_col:
                    st.markdown(f"""
                        <div class="kb-row">
                            <span class="kb-id">#{tid}</span>
                            <span class="kb-subj" title="{ticket.get('ticket_subject','')}">
                                {subject}
                            </span>
                            <span class="kb-co">{company}</span>
                            <span class="kb-prio">{prio_pill}</span>
                            <span class="kb-sla">{sla_pill}</span>
                            <span class="kb-eng">{engineer}</span>
                        </div>
                    """, unsafe_allow_html=True)

                with btn_col:
                    can_manage = (status_key != "Done") or is_admin
                    if can_manage:
                        if st.button("Manage", key=f"kb_{tid}_{status_key}", width='stretch'):
                            st.session_state["selected_ticket_id"] = tid
                            st.session_state["manage_panel_anchor"] = True
                            st.rerun()
                    else:
                        st.markdown("<div style='padding-top:6px;font-size:0.75rem;color:#333;'>Closed</div>",
                                    unsafe_allow_html=True)
