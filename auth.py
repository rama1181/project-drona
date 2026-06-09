import streamlit as st
from database import get_connection


def verify_credentials(username, password):
    """Checks the database for a matching username/password and returns the user dict."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT user_id, username, role, department, company_name
        FROM users
        WHERE username = ? AND password = ?
    """, (username, password))
    user = cursor.fetchone()
    conn.close()
    if user:
        return dict(user)
    return None


def apply_authenticated_layout():
    """Reset layout styles after login so dashboard tabs are not trapped in login-card CSS."""
    st.markdown("""
        <style>
        #MainMenu, header, footer { visibility: visible !important; }
        [data-testid="stAppViewContainer"] {
            background: #0f0f1a !important;
            height: auto !important;
            overflow: auto !important;
        }
        [data-testid="stAppViewBlockContainer"], .main .block-container {
            width: 100% !important;
            max-width: 100% !important;
            background: transparent !important;
            border: none !important;
            border-radius: 0 !important;
            box-shadow: none !important;
            padding: 1.5rem 2rem 2rem !important;
            text-align: left !important;
            backdrop-filter: none !important;
            position: static !important;
            top: auto !important;
            left: auto !important;
            transform: none !important;
            margin: 0 auto !important;
        }
        </style>
        <script>document.body.removeAttribute('data-login-page');</script>
    """, unsafe_allow_html=True)


def login():
    """
    Renders a compact, modern SaaS-style login page.
    No scrolling required on standard desktop/laptop screens.
    ONLY renders when user is NOT logged in (prevents style conflicts).
    """
    # CRITICAL: Stop rendering if already logged in
    if st.session_state.get('logged_in', False):
        return
    
    st.markdown("""
        <style>
        /* ── LOGIN PAGE ONLY STYLES (scoped — does not affect dashboard) ── */
        body[data-login-page="true"] #MainMenu { visibility: hidden; }
        body[data-login-page="true"] header { visibility: hidden; }
        body[data-login-page="true"] footer { visibility: hidden; }

        body[data-login-page="true"] [data-testid="stAppViewContainer"] {
            background: radial-gradient(ellipse at 60% 30%,
                rgba(79,172,254,0.08) 0%, transparent 60%),
                linear-gradient(160deg, #0a0a12 0%, #0f0f1a 100%) !important;
            height: 100vh !important;
            overflow: hidden !important;
        }

        body[data-login-page="true"] [data-testid="stAppViewBlockContainer"],
        body[data-login-page="true"] .block-container {
            width: 380px !important;
            max-width: 380px !important;
            background: rgba(255,255,255,0.04) !important;
            border: 1px solid rgba(255,255,255,0.09) !important;
            border-radius: 18px !important;
            box-shadow: 0 20px 60px rgba(0,0,0,0.55),
                        inset 0 1px 0 rgba(255,255,255,0.07) !important;
            padding: 1.8rem 2rem 1.2rem !important;
            text-align: center !important;
            backdrop-filter: blur(20px) !important;
            position: absolute !important;
            top: 50% !important;
            left: 50% !important;
            transform: translate(-50%, -50%) !important;
            margin: 0 !important;
        }

        .lc-icon {
            font-size: 2.4rem;
            line-height: 1;
            margin-bottom: 0.4rem;
        }

        .lc-title {
            font-size: 1.25rem;
            font-weight: 700;
            background: linear-gradient(90deg, #4facfe, #00f2fe);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin: 0 0 0.15rem;
            font-family: 'Inter', sans-serif;
        }

        .lc-sub {
            font-size: 0.75rem;
            color: #888;
            margin: 0 0 1.0rem;
            letter-spacing: 0.2px;
            font-family: 'Inter', sans-serif;
        }

        .lc-divider {
            border: none;
            border-top: 1px solid rgba(255,255,255,0.07);
            margin: 0 0 1.0rem;
        }

        /* ── Input field styling tweaks ── */
        div[data-testid="stTextInput"] input {
            background-color: rgba(255, 255, 255, 0.92) !important;
            border: 1px solid rgba(255, 255, 255, 0.3) !important;
            color: #1a1a2e !important;
            border-radius: 8px !important;
            font-size: 0.9rem !important;
            padding: 0.5rem 0.7rem !important;
        }
        div[data-testid="stTextInput"] input::placeholder {
            color: #888 !important;
            opacity: 1 !important;
        }
        div[data-testid="stTextInput"] input:focus {
            border-color: #00f2fe !important;
            box-shadow: 0 0 0 2px rgba(0, 242, 254, 0.3) !important;
            background-color: #ffffff !important;
        }
        
        /* ── Button styling tweaks ── */
        button[kind="primary"] {
            background: linear-gradient(90deg, #4facfe 0%, #00f2fe 100%) !important;
            border: none !important;
            color: #ffffff !important;
            font-weight: 600 !important;
            border-radius: 8px !important;
            transition: all 0.3s ease !important;
            font-size: 0.9rem !important;
            padding: 0.4rem 1rem !important;
        }
        button[kind="primary"]:hover {
            box-shadow: 0 0 12px rgba(0, 242, 254, 0.5) !important;
            transform: translateY(-1px) !important;
        }

        .lc-hint {
            font-size: 0.7rem;
            color: #6a6a7a;
            margin-top: 0.9rem;
            line-height: 1.5;
            font-family: 'Inter', sans-serif;
        }
        .lc-hint strong { color: #8a8a9a; }
        </style>
        <script>document.body.setAttribute('data-login-page', 'true');</script>
    """, unsafe_allow_html=True)

    # Header block: icon → title → subtitle → divider
    st.markdown("""
        <div class="lc-icon">🎫</div>
        <div class="lc-title">Smart Ticket Engine</div>
        <div class="lc-sub">Intelligent AI Service Desk Platform</div>
        <hr class="lc-divider">
    """, unsafe_allow_html=True)

    username = st.text_input(
        "Username", placeholder="Username",
        key="login_username", label_visibility="collapsed"
    )
    password = st.text_input(
        "Password", type="password", placeholder="Password",
        key="login_password", label_visibility="collapsed"
    )

    st.markdown("<div style='height:0.2rem'></div>", unsafe_allow_html=True)

    if st.button("Sign In", width='stretch', type="primary", key="login_btn"):
        if username and password:
            user = verify_credentials(username, password)
            if user:
                # Store in session state
                st.session_state['logged_in'] = True
                st.session_state['user'] = user
                st.session_state['_authenticated'] = True
                st.session_state['_login_welcome'] = user['username']
                st.rerun()
            else:
                st.error("Invalid credentials. Please try again.")
        else:
            st.warning("Enter both username and password.")

    # Demo credentials hint
    st.markdown("""
        <div class="lc-hint">
            <strong>Admin:</strong> admin / admin123 &nbsp;|&nbsp;
            <strong>Company:</strong> tcs_user / tcs123<br>
            <strong>Dept:</strong> infra / infra123 &nbsp;·&nbsp;
            desktop / desktop123 &nbsp;·&nbsp; app / app123
        </div>
    """, unsafe_allow_html=True)


def logout():
    """Logs out the user and clears session state."""
    st.session_state['logged_in'] = False
    st.session_state['user'] = None
    st.rerun()
