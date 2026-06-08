import re

# Rule-based department mappings for specific incident types or keywords
def route_department(incident_type, ticket_subject, ticket_description, ml_predicted_dept=None):
    """
    Intelligently routes a ticket to a department based on the incident type
    and text contents, with ML department prediction as a fallback.
    """
    text = f"{ticket_subject} {ticket_description}".lower()
    
    # Fine-grained keyword and category routing rules
    if incident_type == "Access":
        if any(w in text for w in ["password", "login", "locked", "reset"]):
            return "Service Desk L1"
        else:
            return "IT Access Team"
            
    if incident_type == "Network":
        return "Infra Team"
        
    if incident_type == "Hardware":
        return "Desktop Support"
        
    if incident_type == "Software":
        return "Application Support"
        
    if incident_type == "Application":
        return "Application Support"
        
    if incident_type == "Database":
        return "Database Team"
        
    if incident_type == "Security":
        return "Security Team"
        
    if incident_type == "Messaging":
        return "Messaging Team"
        
    if incident_type == "HR":
        return "HR IT Team"
        
    # If ML prediction was provided and is valid, use it as fallback
    VALID_DEPTS = [
        "Infra Team", "Desktop Support", "Application Support", "Database Team",
        "Security Team", "Messaging Team", "IT Access Team", "Service Desk L1", "HR IT Team"
    ]
    if ml_predicted_dept in VALID_DEPTS:
        return ml_predicted_dept
        
    # Default fallback
    return "Service Desk L1"
