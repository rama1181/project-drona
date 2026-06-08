import re

# Keyword Lists
KEYWORDS = {
    "Critical": [
        "server down", "production down", "security breach", "ransomware", 
        "data loss", "payment failure", "database corruption", "complete outage"
    ],
    "High": [
        "urgent", "client call", "customer impacted", "unable to login", 
        "vpn down", "application unavailable", "certificate expired"
    ],
    "Medium": [
        "slow", "intermittent issue", "printer issue", "report issue", "email issue"
    ],
    "Low": [
        "installation request", "onboarding", "information request", "account creation"
    ]
}

PRIORITY_RANKS = {
    "Critical": 4,
    "High": 3,
    "Medium": 2,
    "Low": 1,
    "Unknown": 0
}

def predict_keyword_priority(text):
    """Analyzes text for key phrases and predicts keyword-based priority."""
    text_lower = text.lower()
    highest_rank = "Low"  # default baseline if no keywords found
    
    for level, kw_list in KEYWORDS.items():
        for kw in kw_list:
            # Match boundary word or exact phrase
            pattern = r'\b' + re.escape(kw) + r'\b'
            if re.search(pattern, text_lower):
                if PRIORITY_RANKS[level] > PRIORITY_RANKS[highest_rank]:
                    highest_rank = level
                    
    return highest_rank

def resolve_priority(text, ml_predicted_prio):
    """Combines ML Priority and Keyword Priority. Max wins."""
    kw_prio = predict_keyword_priority(text)
    
    # ML predicted priority validation
    if ml_predicted_prio not in PRIORITY_RANKS:
        ml_predicted_prio = "Low"
        
    # Hybrid Rule: Critical > High > Medium > Low
    if PRIORITY_RANKS[kw_prio] >= PRIORITY_RANKS[ml_predicted_prio]:
        final_prio = kw_prio
    else:
        final_prio = ml_predicted_prio
        
    return ml_predicted_prio, kw_prio, final_prio
