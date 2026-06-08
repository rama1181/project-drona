from datetime import datetime

# SLA Limits in minutes
SLA_LIMITS = {
    "Critical": 120,    # 2 Hours
    "High": 180,        # 3 Hours
    "Medium": 480,      # 8 Hours
    "Low": 960          # 16 Hours
}

def get_sla_mins(priority):
    """Returns the SLA limit in minutes for a given priority."""
    return SLA_LIMITS.get(priority, 480) # Default to Medium (8 Hours) if unknown

def calculate_duration_mins(start_str, end_str):
    """Calculates the time difference in minutes between two ISO/string datetimes."""
    try:
        fmt = "%Y-%m-%d %H:%M:%S"
        start_dt = datetime.strptime(start_str, fmt)
        end_dt = datetime.strptime(end_str, fmt)
        diff = end_dt - start_dt
        return max(0.0, diff.total_seconds() / 60.0)
    except Exception:
        return 0.0

def evaluate_sla(created_date_str, closed_date_str, priority):
    """
    Evaluates resolution time and SLA status.
    For closed tickets: returns resolution_time, SLA status (Met/Breached), and delay.
    For open tickets: returns elapsed time, status (In Progress or Breached), and delay.
    """
    sla_mins = get_sla_mins(priority)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    is_closed = closed_date_str is not None and closed_date_str != ""
    comparison_date = closed_date_str if is_closed else now_str
    
    duration = calculate_duration_mins(created_date_str, comparison_date)
    duration_rounded = round(duration, 1)
    
    if is_closed:
        if duration <= sla_mins:
            return duration_rounded, "Met", 0.0
        else:
            delay = round(duration - sla_mins, 1)
            return duration_rounded, "Breached", delay
    else:
        # Open ticket
        if duration <= sla_mins:
            return duration_rounded, "In Progress", 0.0
        else:
            delay = round(duration - sla_mins, 1)
            return duration_rounded, "Breached", delay
