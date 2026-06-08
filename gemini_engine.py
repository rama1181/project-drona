"""
gemini_engine.py
================
Gemini-First Resolution Engine for Smart Ticket Engine.

Behaviour:
  1. Build a structured prompt from ticket context + RAG historical matches.
  2. Call the Gemini API (google-generativeai).
  3. If Gemini responds with valid content → return structured result.
  4. On ANY failure (auth, rate-limit, timeout, network, empty response) →
     fall back to the RAG-based recommendation silently, no user intervention.
"""

import os
import re

# ── Gemini SDK import ──────────────────────────────────────────────────────────
try:
    import google.generativeai as genai
    _SDK_AVAILABLE = True
except ImportError:
    _SDK_AVAILABLE = False

# ── System prompt (verbatim from requirement) ──────────────────────────────────
_SYSTEM_PROMPT = """You are an experienced IT Service Desk Level 3 Support Engineer.

Analyze the ticket information and historical incidents.

Provide:
1. Likely Root Cause
2. Step-by-step Resolution Procedure
3. Escalation Recommendation (if required)

Rules:
- Be concise.
- Use numbered steps.
- Use enterprise IT support terminology.
- Do not invent unsupported technical details.
- Prefer historical incident evidence when available.
- Maximum 8 resolution steps.
- Output in professional service desk format.

Response format:

Root Cause: <root cause>

Resolution Steps:
1.
2.
3.

Escalation Required:
Yes/No

Recommended Team: <team>"""


def _build_user_prompt(ticket_subject, ticket_description, incident_type,
                       priority, department, rag_result):
    """Builds the user message sent to Gemini alongside the system prompt."""
    similar_summary = ""
    for i, match in enumerate(rag_result.get("similar_tickets", [])[:3], 1):
        t = match["ticket"]
        score = match["score"]
        similar_summary += (
            f"\nHistorical Ticket #{t.get('ticket_id', '?')} "
            f"(Similarity: {score:.1%})\n"
            f"  Subject      : {t.get('ticket_subject', 'N/A')}\n"
            f"  Root Cause   : {t.get('root_cause', 'N/A')}\n"
            f"  Resolution   : {t.get('resolution_steps', 'N/A')}\n"
        )
    if not similar_summary:
        similar_summary = "No historical matches found in the knowledge base."

    return f"""=== NEW TICKET ===
Subject      : {ticket_subject}
Description  : {ticket_description}
Incident Type: {incident_type}
Priority     : {priority}
Department   : {department}

=== HISTORICAL CONTEXT (RAG) ===
{similar_summary.strip()}

Based on the above, provide your root cause analysis and resolution steps."""


def _parse_gemini_response(raw_text):
    """
    Parses Gemini's plain-text response into a structured dict.
    Falls back gracefully if formatting is unexpected.
    """
    root_cause = "Undetermined"
    resolution_steps = raw_text.strip()
    escalation_required = "No"
    recommended_team = "Service Desk L1"

    # Root Cause
    rc_match = re.search(r"Root Cause\s*[:：]\s*(.+?)(?:\n|Resolution Steps)", raw_text, re.DOTALL | re.IGNORECASE)
    if rc_match:
        root_cause = rc_match.group(1).strip()

    # Resolution Steps block
    rs_match = re.search(r"Resolution Steps\s*[:：]?\s*((?:\n|\r\n?).+?)(?:Escalation Required|$)", raw_text, re.DOTALL | re.IGNORECASE)
    if rs_match:
        resolution_steps = rs_match.group(1).strip()

    # Escalation Required
    esc_match = re.search(r"Escalation Required\s*[:：]\s*(Yes|No)", raw_text, re.IGNORECASE)
    if esc_match:
        escalation_required = esc_match.group(1).strip()

    # Recommended Team
    rt_match = re.search(r"Recommended Team\s*[:：]\s*(.+)", raw_text, re.IGNORECASE)
    if rt_match:
        recommended_team = rt_match.group(1).strip()

    return {
        "root_cause": root_cause,
        "resolution_steps": resolution_steps,
        "full_response": raw_text.strip(),
        "escalation_required": escalation_required,
        "recommended_team": recommended_team,
        "source": "gemini"
    }


def get_gemini_resolution(ticket_subject, ticket_description, incident_type,
                          priority, department, rag_result):
    """
    Primary entry point.

    Returns a dict:
        {
            "root_cause"           : str,
            "resolution_steps"     : str,
            "full_response"        : str,
            "escalation_required"  : str,   # "Yes" / "No"
            "recommended_team"     : str,
            "source"               : "gemini" | "rag_fallback"
        }

    If Gemini succeeds → source == "gemini".
    On any failure      → source == "rag_fallback" with RAG content.
    """
    # ── Fallback builder (always available) ───────────────────────────────────
    def _rag_fallback(reason=""):
        return {
            "root_cause": rag_result.get("predicted_root_cause", "Undetermined"),
            "resolution_steps": rag_result.get("recommended_resolution", "1. Escalate to L1 Service Desk."),
            "full_response": rag_result.get("recommended_resolution", ""),
            "escalation_required": "No",
            "recommended_team": department,
            "source": "rag_fallback"
        }

    # ── Guard: SDK not installed ───────────────────────────────────────────────
    if not _SDK_AVAILABLE:
        return _rag_fallback("google-generativeai SDK not installed")

    # ── Guard: API key not set ─────────────────────────────────────────────────
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return _rag_fallback("GEMINI_API_KEY not set")

    # ── Call Gemini ────────────────────────────────────────────────────────────
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            model_name="gemini-3.5-flash",
            system_instruction=_SYSTEM_PROMPT
        )

        user_prompt = _build_user_prompt(
            ticket_subject, ticket_description,
            incident_type, priority, department, rag_result
        )

        response = model.generate_content(
            user_prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.3,
                max_output_tokens=1024
            ),
            request_options={"timeout": 15}  # 15-second timeout
        )

        # Validate response
        raw_text = ""
        if response and response.candidates:
            candidate = response.candidates[0]
            if candidate.content and candidate.content.parts:
                raw_text = "".join(p.text for p in candidate.content.parts if hasattr(p, "text"))

        if not raw_text.strip():
            return _rag_fallback("Empty response from Gemini")

        return _parse_gemini_response(raw_text)

    except Exception as e:
        # Catches: auth errors, rate limits, timeouts, network failures, etc.
        import traceback
        traceback.print_exc()
        return _rag_fallback("Gemini API exception: " + str(e))
