"""
Catalyze - Transform Ideas into Bulletproof Prompts
===================================================
A sophisticated prompt optimization engine.
Part of the Dysruption AI Suite.

Run with: streamlit run app.py
"""

import os
import json
import time
import streamlit as st
from pathlib import Path
from datetime import datetime

# Load environment variables from .env
from dotenv import load_dotenv
load_dotenv()

# Import the v2 pipeline
from consensus_prompt_optimizer.orchestrator import PromptimaV2
from consensus_prompt_optimizer.config import FREE_TIER_MONTHLY_LIMIT, PRO_TIER_MONTHLY_LIMIT

# Import authentication and Stripe
from auth import AuthService, UsageService, get_stripe_service

# Get base URL for redirects
# Railway provides RAILWAY_PUBLIC_DOMAIN automatically
def get_app_url():
    """Get the app URL, auto-detecting Railway deployment."""
    if os.getenv("APP_URL"):
        url = os.getenv("APP_URL")
    elif os.getenv("RAILWAY_PUBLIC_DOMAIN"):
        url = f"https://{os.getenv('RAILWAY_PUBLIC_DOMAIN')}"
    else:
        url = "http://localhost:8501"
    
    # Ensure URL has a scheme
    if not url.startswith("http://") and not url.startswith("https://"):
        url = f"https://{url}"
    
    return url.rstrip("/")

APP_URL = get_app_url()


# ============================================================================
# PAGE CONFIGURATION
# ============================================================================
st.set_page_config(
    page_title="Catalyze - Transform Ideas into Prompts",
    page_icon="🔷",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ============================================================================
# CUSTOM CSS - Neo-Brutalist Dark Theme with Cyan Accents
# ============================================================================
st.markdown("""
<style>
    /* Import fonts */
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&display=swap');
    
    /* Main dark theme - Pure Black */
    .stApp {
        background-color: #000000;
        font-family: 'JetBrains Mono', 'SF Mono', 'Consolas', monospace;
    }
    
    /* Sidebar styling - Dark charcoal */
    [data-testid="stSidebar"] {
        background-color: #0A0A0A;
        border-right: 1px solid rgba(0, 240, 255, 0.1);
    }
    
    [data-testid="stSidebar"] .stMarkdown {
        color: #c9d1d9;
    }
    
    /* Header with grid aesthetic - CATALYZE branding */
    .main-header {
        font-size: 4rem;
        font-weight: 800;
        color: #00F0FF;
        text-shadow: 0 0 40px rgba(0, 240, 255, 0.5), 0 0 80px rgba(0, 240, 255, 0.3);
        margin-bottom: 0;
        padding: 50px 0 15px 0;
        font-family: 'Inter', 'SF Pro Display', -apple-system, BlinkMacSystemFont, sans-serif;
        letter-spacing: 0.35em;
        text-align: center;
        position: relative;
        background: linear-gradient(180deg, transparent 0%, rgba(0, 240, 255, 0.02) 50%, transparent 100%);
    }
    
    /* Grid overlay effect behind header */
    .main-header::before {
        content: '';
        position: absolute;
        top: 0;
        left: 50%;
        transform: translateX(-50%);
        width: 700px;
        height: 100%;
        background-image: 
            linear-gradient(rgba(0, 240, 255, 0.04) 1px, transparent 1px),
            linear-gradient(90deg, rgba(0, 240, 255, 0.04) 1px, transparent 1px);
        background-size: 25px 25px;
        pointer-events: none;
        z-index: -1;
        mask-image: radial-gradient(ellipse 60% 80% at 50% 50%, black 40%, transparent 100%);
        -webkit-mask-image: radial-gradient(ellipse 60% 80% at 50% 50%, black 40%, transparent 100%);
    }
    
    .sub-header {
        font-size: 1rem;
        color: #64748b;
        margin-top: 12px;
        margin-bottom: 24px;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        text-align: center;
        letter-spacing: 0.05em;
        font-weight: 400;
    }
    
    /* Card styling for output */
    .output-card {
        background: #0A0A0A;
        border: 1px solid rgba(0, 240, 255, 0.2);
        border-radius: 8px;
        padding: 24px;
        margin: 16px 0;
    }
    
    .output-card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 16px;
        padding-bottom: 12px;
        border-bottom: 1px solid rgba(0, 240, 255, 0.1);
    }
    
    .output-card-title {
        font-size: 1.25rem;
        font-weight: 600;
        color: #00F0FF;
        margin: 0;
    }
    
    .output-card-actions {
        display: flex;
        gap: 8px;
    }
    
    .action-btn {
        background: transparent;
        border: 1px solid rgba(0, 240, 255, 0.3);
        color: #00F0FF;
        padding: 6px 12px;
        border-radius: 4px;
        font-size: 0.85rem;
        cursor: pointer;
        transition: all 0.2s;
        font-family: 'JetBrains Mono', monospace;
    }
    
    .action-btn:hover {
        background: rgba(0, 240, 255, 0.1);
        border-color: #00F0FF;
        box-shadow: 0 0 15px rgba(0, 240, 255, 0.3);
    }
    
    /* Prompt output text area */
    .prompt-output {
        background-color: #000000;
        color: #F8F8F8;
        padding: 20px;
        border-radius: 8px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.9rem;
        white-space: pre-wrap;
        line-height: 1.7;
        border: 1px solid rgba(0, 240, 255, 0.2);
    }
    
    /* Input field styling */
    .stTextArea textarea {
        background-color: rgba(255, 255, 255, 0.05) !important;
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
        border-radius: 8px !important;
        color: #FFFFFF !important;
        font-size: 0.95rem !important;
        font-family: 'JetBrains Mono', monospace !important;
    }
    
    .stTextArea textarea:focus {
        border-color: #00F0FF !important;
        box-shadow: 0 0 20px rgba(0, 240, 255, 0.2) !important;
    }
    
    /* Primary button with cyan - LARGE */
    .stButton > button[kind="primary"] {
        background: #00F0FF !important;
        color: #000000 !important;
        border: none !important;
        border-radius: 4px !important;
        padding: 16px 32px !important;
        font-weight: 700 !important;
        font-size: 1.1rem !important;
        font-family: 'JetBrains Mono', monospace !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 0 30px rgba(0, 240, 255, 0.5) !important;
        text-transform: uppercase !important;
        letter-spacing: 2px !important;
    }
    
    .stButton > button[kind="primary"]:hover {
        background: #FFFFFF !important;
        box-shadow: 0 0 50px rgba(0, 240, 255, 0.8) !important;
        transform: translateY(-3px) !important;
    }
    
    /* Secondary buttons */
    .stButton > button {
        background: transparent !important;
        color: #00F0FF !important;
        border: 1px solid rgba(0, 240, 255, 0.3) !important;
        border-radius: 4px !important;
        font-family: 'JetBrains Mono', monospace !important;
        transition: all 0.2s ease !important;
    }
    
    .stButton > button:hover {
        background: rgba(0, 240, 255, 0.1) !important;
        border-color: #00F0FF !important;
    }
    
    /* Metrics styling */
    .metric-card {
        background: #0A0A0A;
        border: 1px solid rgba(0, 240, 255, 0.2);
        border-radius: 8px;
        padding: 16px;
        text-align: center;
    }
    
    .metric-value {
        font-size: 1.5rem;
        font-weight: 700;
        color: #00F0FF;
        text-shadow: 0 0 10px rgba(0, 240, 255, 0.3);
    }
    
    .metric-label {
        font-size: 0.8rem;
        color: #718096;
        text-transform: uppercase;
        letter-spacing: 1px;
        font-family: 'JetBrains Mono', monospace;
    }
    
    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        background-color: #0A0A0A;
        border-radius: 4px;
        padding: 4px;
        gap: 4px;
        border: 1px solid rgba(0, 240, 255, 0.1);
    }
    
    .stTabs [data-baseweb="tab"] {
        background-color: transparent;
        color: #718096;
        border-radius: 4px;
        padding: 8px 16px;
        font-family: 'JetBrains Mono', monospace;
    }
    
    .stTabs [aria-selected="true"] {
        background-color: rgba(0, 240, 255, 0.1);
        color: #00F0FF;
    }
    
    /* Expander styling */
    .streamlit-expanderHeader {
        background-color: #0A0A0A;
        border: 1px solid rgba(0, 240, 255, 0.2);
        border-radius: 4px;
        color: #c9d1d9;
        font-family: 'JetBrains Mono', monospace;
    }
    
    /* Connected status badge */
    .status-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 4px 10px;
        border-radius: 4px;
        font-size: 0.8rem;
        font-weight: 500;
        font-family: 'JetBrains Mono', monospace;
    }
    
    .status-connected {
        background-color: rgba(0, 240, 255, 0.1);
        color: #00F0FF;
        border: 1px solid rgba(0, 240, 255, 0.3);
    }
    
    .status-disconnected {
        background-color: rgba(255, 0, 255, 0.1);
        color: #FF00FF;
        border: 1px solid rgba(255, 0, 255, 0.3);
    }
    
    /* Divider */
    hr {
        border-color: rgba(0, 240, 255, 0.1);
        margin: 20px 0;
    }
    
    /* Section headers in sidebar */
    .sidebar-section {
        color: #FFFFFF;
        font-size: 0.9rem;
        font-weight: 600;
        margin-bottom: 8px;
        display: flex;
        align-items: center;
        gap: 8px;
        font-family: 'JetBrains Mono', monospace;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    /* Footer */
    .footer {
        text-align: center;
        color: #718096;
        font-size: 0.85rem;
        padding: 20px;
        border-top: 1px solid rgba(0, 240, 255, 0.1);
        margin-top: 40px;
        font-family: 'JetBrains Mono', monospace;
    }
    
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Auth form styling */
    .auth-container {
        max-width: 400px;
        margin: 60px auto;
        padding: 40px;
        background: #0A0A0A;
        border: 1px solid rgba(0, 240, 255, 0.2);
        border-radius: 8px;
    }
    
    .auth-header {
        text-align: center;
        margin-bottom: 30px;
    }
    
    .auth-title {
        font-size: 1.5rem;
        font-weight: 700;
        color: #00F0FF;
        text-shadow: 0 0 20px rgba(0, 240, 255, 0.4);
        font-family: 'JetBrains Mono', monospace;
        margin-bottom: 8px;
    }
    
    .auth-subtitle {
        color: #718096;
        font-size: 0.9rem;
        font-family: 'JetBrains Mono', monospace;
    }
    
    .tier-badge {
        display: inline-block;
        padding: 3px 8px;
        border-radius: 4px;
        font-size: 0.7rem;
        font-weight: 600;
        text-transform: uppercase;
        font-family: 'JetBrains Mono', monospace;
    }
    
    .tier-free {
        background: rgba(0, 240, 255, 0.1);
        color: #00F0FF;
        border: 1px solid rgba(0, 240, 255, 0.3);
    }
    
    .tier-pro {
        background: rgba(255, 0, 255, 0.1);
        color: #FF00FF;
        border: 1px solid rgba(255, 0, 255, 0.3);
    }
    
    .tier-enterprise {
        background: rgba(0, 240, 255, 0.2);
        color: #00F0FF;
        border: 1px solid rgba(0, 240, 255, 0.5);
    }
    
    /* Circuit board background pattern */
    .stApp::before {
        content: '';
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background-image: 
            linear-gradient(rgba(0, 240, 255, 0.03) 1px, transparent 1px),
            linear-gradient(90deg, rgba(0, 240, 255, 0.03) 1px, transparent 1px);
        background-size: 40px 40px;
        pointer-events: none;
        z-index: 0;
    }
    
    /* Branding text */
    .dysruption-brand {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.7rem;
        color: #718096;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 20px;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================================
# INITIALIZE SERVICES
# ============================================================================
auth_service = AuthService()
usage_service = UsageService()
stripe_service = get_stripe_service()


# ============================================================================
# SESSION STATE INITIALIZATION
# ============================================================================
if 'history' not in st.session_state:
    st.session_state.history = []

# Authentication state
if 'session_token' not in st.session_state:
    st.session_state.session_token = None
if 'current_user' not in st.session_state:
    st.session_state.current_user = None

# Validate existing session
if st.session_state.session_token and not st.session_state.current_user:
    user = auth_service.validate_session(st.session_state.session_token)
    if user:
        st.session_state.current_user = user
    else:
        st.session_state.session_token = None


# ============================================================================
# AUTHENTICATION UI (if not logged in)
# ============================================================================

# Initialize auth UI state
if 'auth_view' not in st.session_state:
    st.session_state.auth_view = 'login'  # 'login', 'register', 'forgot_password', 'reset_password'
if 'reset_token' not in st.session_state:
    st.session_state.reset_token = None


def show_forgot_password_form():
    """Display forgot password form."""
    st.markdown("#### Forgot Password")
    st.markdown("Enter your email address and we'll send you a reset link.")
    
    with st.form("forgot_password_form"):
        email = st.text_input("Email", placeholder="you@example.com")
        submitted = st.form_submit_button("Send Reset Link", use_container_width=True, type="primary")
        
        if submitted:
            success, message, token = auth_service.request_password_reset(email)
            if success:
                st.success(message)
                # In development, show the token (remove in production)
                if token:
                    st.info(f"Dev Mode: Reset token = {token[:20]}...")
                    st.session_state.reset_token = token
                    st.session_state.auth_view = 'reset_password'
                    time.sleep(1)
                    st.rerun()
            else:
                st.error(message)
    
    if st.button("← Back to Login"):
        st.session_state.auth_view = 'login'
        st.rerun()


def show_reset_password_form():
    """Display password reset form."""
    st.markdown("#### Reset Your Password")
    st.markdown("Enter your new password below.")
    
    with st.form("reset_password_form"):
        new_password = st.text_input("New Password", type="password", placeholder="Min 8 characters")
        confirm_password = st.text_input("Confirm Password", type="password", placeholder="••••••••")
        submitted = st.form_submit_button("Reset Password", use_container_width=True, type="primary")
        
        if submitted:
            token = st.session_state.reset_token
            if not token:
                st.error("Invalid reset link. Please request a new one.")
            else:
                success, message = auth_service.reset_password(token, new_password, confirm_password)
                if success:
                    st.success(message)
                    st.session_state.reset_token = None
                    st.session_state.auth_view = 'login'
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(message)
    
    if st.button("← Back to Login"):
        st.session_state.reset_token = None
        st.session_state.auth_view = 'login'
        st.rerun()


def show_auth_page():
    """Display login/register page."""
    st.markdown('<p class="main-header">CATALYZE</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Transform your ideas into bulletproof prompts</p>', unsafe_allow_html=True)
    
    st.markdown("")
    
    # Center the auth form
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        # Handle special views
        if st.session_state.auth_view == 'forgot_password':
            show_forgot_password_form()
            return
        
        if st.session_state.auth_view == 'reset_password':
            show_reset_password_form()
            return
        
        # Normal login/register tabs
        auth_tab1, auth_tab2 = st.tabs(["Login", "Register"])
        
        with auth_tab1:
            st.markdown("#### Welcome back!")
            with st.form("login_form"):
                email = st.text_input("Email", placeholder="you@example.com")
                password = st.text_input("Password", type="password", placeholder="••••••••")
                
                submitted = st.form_submit_button("Login", use_container_width=True, type="primary")
                
                if submitted:
                    user, token, error = auth_service.login(email, password)
                    if error:
                        st.error(f"{error}")
                    else:
                        st.session_state.session_token = token
                        st.session_state.current_user = user
                        st.success("Login successful")
                        time.sleep(0.5)
                        st.rerun()
            
            # Forgot password link
            if st.button("Forgot your password?", type="secondary"):
                st.session_state.auth_view = 'forgot_password'
                st.rerun()
        
        with auth_tab2:
            st.markdown("#### Create your account")
            with st.form("register_form"):
                reg_email = st.text_input("Email", placeholder="you@example.com", key="reg_email")
                
                col_name1, col_name2 = st.columns(2)
                with col_name1:
                    first_name = st.text_input("First Name", placeholder="John")
                with col_name2:
                    last_name = st.text_input("Last Name", placeholder="Doe")
                
                reg_password = st.text_input("Password", type="password", placeholder="Min 8 characters", key="reg_pass")
                confirm_password = st.text_input("Confirm Password", type="password", placeholder="••••••••", key="confirm_pass")
                
                submitted = st.form_submit_button("Create Account", use_container_width=True, type="primary")
                
                if submitted:
                    user, token, error = auth_service.register(
                        reg_email, first_name, last_name, reg_password, confirm_password
                    )
                    if error:
                        st.error(f"{error}")
                    else:
                        st.session_state.session_token = token
                        st.session_state.current_user = user
                        st.success("Account created successfully")
                        time.sleep(0.5)
                        st.rerun()
            
            st.markdown("---")
            st.markdown('<p style="color: #8b949e; font-size: 0.85rem; text-align: center;">· Flow tier includes 40 Catalyze Credits/month</p>', unsafe_allow_html=True)
    
    # Footer
    st.markdown("""
    <div class="footer">
        Catalyze | AI-Powered Prompt Transformation | Secure & Private
    </div>
    """, unsafe_allow_html=True)


# Check if user is authenticated
if not st.session_state.current_user:
    show_auth_page()
    st.stop()  # Don't render the rest of the app

# User is authenticated - get current user
current_user = st.session_state.current_user

# Get user's usage from database
user_usage = usage_service.get_usage(current_user.id)
usage_limit = usage_service.get_limit_for_tier(current_user.tier)


# ============================================================================
# SIDEBAR - MINIMAL DESIGN
# ============================================================================

# Default configuration (no UI clutter)
use_cache = True
dry_run = False
show_details = False

with st.sidebar:
    # Logo/Brand
    st.markdown("### ◆ Catalyze")
    st.markdown('<span style="color: #8b949e; font-size: 0.85rem;">Prompt Transformation Engine</span>', unsafe_allow_html=True)
    
    st.markdown("---")
    
    # User - Just name
    st.markdown(f"**{current_user.full_name}**")
    
    st.markdown("")
    
    # Usage Counter - Simple
    usage_count = user_usage.count
    if usage_limit is None:
        st.markdown("**Unlimited** requests")
    else:
        remaining = max(0, usage_limit - usage_count)
        if usage_count >= usage_limit:
            st.markdown(f"**0** requests remaining")
        else:
            st.markdown(f"**{remaining}** requests remaining")
    
    st.markdown("")
    
    # Upgrade/Manage Subscription button
    if current_user.tier == "free":
        if stripe_service.is_configured:
            if st.button("⚡ Upgrade to Synapse", use_container_width=True, type="primary"):
                st.session_state.show_upgrade = True
                st.rerun()
        else:
            if st.button("🚀 Synapse - Coming Soon", use_container_width=True):
                st.session_state.show_upgrade = True
                st.rerun()
    elif current_user.is_pro and stripe_service.is_configured:
        subscription = stripe_service.get_active_subscription(current_user.id)
        if subscription:
            if st.button("📋 Manage Subscription", use_container_width=True):
                try:
                    portal_url = stripe_service.create_customer_portal_session(
                        user_id=current_user.id,
                        return_url=APP_URL
                    )
                    st.markdown(f'<meta http-equiv="refresh" content="0; url={portal_url}">', unsafe_allow_html=True)
                except Exception as e:
                    st.error(f"Error: {e}")
    
    st.markdown("")
    
    # History Section (Collapsible)
    with st.expander("History", expanded=False):
        if st.session_state.history:
            for i, item in enumerate(st.session_state.history[-5:]):
                st.markdown(f"**{i+1}.** {item['idea'][:40]}...")
        else:
            st.markdown("*No optimization history yet*")
    
    st.markdown("")
    
    # Logout button
    if st.button("Logout", use_container_width=True):
        auth_service.logout(st.session_state.session_token)
        st.session_state.session_token = None
        st.session_state.current_user = None
        st.session_state.auth_view = 'login'
        st.rerun()


# ============================================================================
# MAIN CONTENT AREA - CENTERED, MINIMAL DESIGN
# ============================================================================

# Centered header
st.markdown('<p class="main-header" style="text-align: center;">CATALYZE</p>', unsafe_allow_html=True)

st.markdown("")
st.markdown("")

# Centered input area
col_left, col_center, col_right = st.columns([1, 3, 1])

with col_center:
    # Input Section
    idea = st.text_area(
        "Enter your prompt idea:",
        placeholder="Describe what you want your prompt to do...\n\nExample: Write a prompt that helps an AI assistant explain complex scientific concepts to children aged 8-12",
        height=150,
        label_visibility="collapsed"
    )
    
    st.markdown("")
    
    # Optimize button - centered
    run_button = st.button(
        "OPTIMIZE →", 
        type="primary", 
        use_container_width=True
    )

# No context tags needed - simplify
context_tags = []

st.markdown("")

# ============================================================================
# PROCESSING & RESULTS
# ============================================================================
if run_button and idea:
    if not os.getenv("GEMINI_API_KEY") or not os.getenv("DEEPSEEK_API_KEY"):
        st.error("Please configure API keys in environment variables")
    else:
        # Check rate limit from database
        is_within_limit, current_count, limit = usage_service.check_limit(current_user.id, current_user.tier)
        
        if not is_within_limit:
            st.error(f"Monthly limit reached ({current_count}/{limit} CCs). Resets on the 1st of next month.")
            if current_user.tier == "free":
                btn_text = "⚡ Upgrade to Synapse for 300 CCs/month" if stripe_service.is_configured else "🚀 Synapse Coming Soon - Join Waitlist"
                if st.button(btn_text):
                    st.session_state.show_upgrade = True
                    st.rerun()
        else:
            with st.spinner("Optimizing your prompt... (this takes 10-30 seconds)"):
                try:
                    start_time = time.time()
                    
                    # Enhance idea with context tags
                    enhanced_idea = idea
                    if context_tags:
                        enhanced_idea = f"{idea}\n\nContext variables to include: {', '.join(context_tags)}"
                    
                    optimizer = PromptimaV2(use_cache=use_cache, dry_run=dry_run)
                    result = optimizer.run(enhanced_idea)
                    
                    end_time = time.time()
                    latency = end_time - start_time
                    
                    # Store results
                    st.session_state['last_result'] = result
                    st.session_state['last_idea'] = idea
                    st.session_state['last_latency'] = latency
                    
                    # Increment usage counter in database
                    usage_service.increment_usage(current_user.id)
                    
                    # Add to history
                    st.session_state.history.append({
                        'idea': idea,
                        'result': result.get('final_synthesis', {}).get('prompt', ''),
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M')
                    })
                    
                except Exception as e:
                    st.error(f"Error: {str(e)}")
                    st.exception(e)

elif run_button and not idea:
    st.warning("Please enter a prompt idea first")


# ============================================================================
# DISPLAY RESULTS
# ============================================================================
if 'last_result' in st.session_state:
    result = st.session_state['last_result']
    latency = st.session_state.get('last_latency', 0)
    
    # Output Card
    st.markdown("""
    <div class="output-card">
        <div class="output-card-header">
            <h3 class="output-card-title">Optimized Prompt Output</h3>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Get the prompt text
    final = result.get('final_synthesis', {})
    prompt_text = final.get('prompt', 'No prompt generated')
    
    # Display prompt with actions
    col_output, col_actions = st.columns([4, 1])
    
    with col_output:
        st.markdown(f'<div class="prompt-output">{prompt_text}</div>', unsafe_allow_html=True)
    
    with col_actions:
        st.markdown("")
        st.markdown("")
        if st.button("Copy", use_container_width=True):
            st.toast("Copied to clipboard!")
        if st.button("Save", use_container_width=True):
            st.download_button(
                label="Download",
                data=prompt_text,
                file_name=f"prompt_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                mime="text/plain",
                key="save_prompt"
            )
        if st.button("Regenerate", use_container_width=True):
            st.session_state.pop('last_result', None)
            st.rerun()
    
    st.markdown("")
    
    # ========================================================================
    # METRICS PANEL
    # ========================================================================
    st.markdown("#### Optimization Metrics")
    
    usage = result.get('usage', {})
    total_tokens = usage.get('total_input_tokens', 0) + usage.get('total_output_tokens', 0)
    cost = usage.get('total_cost_usd', 0)
    confidence = final.get('confidence', 0.85)
    prompt_score = int(confidence * 100)
    
    m1, m2, m3, m4 = st.columns(4)
    
    with m1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{total_tokens:,}</div>
            <div class="metric-label">Token Count</div>
        </div>
        """, unsafe_allow_html=True)
    
    with m2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">${cost:.4f}</div>
            <div class="metric-label">Est. Cost</div>
        </div>
        """, unsafe_allow_html=True)
    
    with m3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{latency:.1f}s</div>
            <div class="metric-label">Latency</div>
        </div>
        """, unsafe_allow_html=True)
    
    with m4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{prompt_score}/100</div>
            <div class="metric-label">Prompt Score</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("")
    
    # Additional Details (Collapsible)
    with st.expander("Detailed Analysis", expanded=False):
        detail_tab1, detail_tab2, detail_tab3 = st.tabs(["Variations", "Rubric", "Raw JSON"])
        
        with detail_tab1:
            variations = result.get('variations', {})
            for var_id in ['A', 'B', 'C']:
                var = variations.get(var_id, {})
                if var:
                    rank = var.get('rank', '?')
                    score = var.get('score', 0)
                    st.markdown(f"**Variation {var_id}** - Rank #{rank} (Score: {score:.2f})")
                    st.code(var.get('prompt', 'N/A'), language=None)
        
        with detail_tab2:
            rubric = result.get('rubric', {})
            if rubric.get('criteria'):
                st.markdown("**Criteria:**")
                for name, desc in rubric.get('criteria', {}).items():
                    st.markdown(f"- **{name}:** {desc[:100]}...")
            if rubric.get('checklist'):
                st.markdown("**Checklist:**")
                for item in rubric.get('checklist', [])[:5]:
                    st.markdown(f"- {item}")
        
        with detail_tab3:
            st.json(result)
            st.download_button(
                label="Download Full JSON",
                data=json.dumps(result, indent=2),
                file_name=f"catalyze_output_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )


# ============================================================================
# UPGRADE MODAL (Stripe Integration)
# ============================================================================
@st.dialog("Upgrade to Synapse" if stripe_service.is_configured else "Synapse Tier - Coming Soon")
def show_upgrade_dialog():
    if stripe_service.is_configured:
        st.markdown("""
        ### Unlock Full Power
        
        **Synapse** (Pro Tier) gives you:
        
        → **300 Catalyze Credits/month** (vs 40 Flow)  
        → A/B Strategy Output (2/3 depth)  
        → Direct link to **The Tribunal** for verification  
        → Priority processing  
        
        ---
        
        ### $19.99/month
        
        """)
        
        # Check if user already has an active subscription
        subscription = stripe_service.get_active_subscription(current_user.id)
        
        if subscription and subscription.get("status") == "active":
            st.success("✅ You already have an active Synapse subscription!")
            
            # Show manage subscription button
            if st.button("📋 Manage Subscription", use_container_width=True, type="primary"):
                try:
                    portal_url = stripe_service.create_customer_portal_session(
                        user_id=current_user.id,
                        return_url=APP_URL
                    )
                    st.markdown(f'<meta http-equiv="refresh" content="0; url={portal_url}">', unsafe_allow_html=True)
                    st.info("Redirecting to billing portal...")
                except Exception as e:
                    st.error(f"Error: {e}")
        else:
            # Create checkout session button
            if st.button("⚡ Subscribe Now", use_container_width=True, type="primary"):
                try:
                    checkout_url = stripe_service.create_checkout_session(
                        user_id=current_user.id,
                        email=current_user.email,
                        name=current_user.full_name,
                        success_url=f"{APP_URL}?upgrade=success",
                        cancel_url=f"{APP_URL}?upgrade=canceled"
                    )
                    # Redirect to Stripe Checkout
                    st.markdown(f'<meta http-equiv="refresh" content="0; url={checkout_url}">', unsafe_allow_html=True)
                    st.info("Redirecting to secure checkout...")
                except Exception as e:
                    st.error(f"Checkout error: {e}")
            
            st.markdown("---")
            st.markdown('<p style="color: #718096; font-size: 0.8rem; text-align: center;">🔒 Secure payment via Stripe</p>', unsafe_allow_html=True)
    else:
        # Stripe not configured - show Coming Soon with waitlist
        st.markdown("""
        ### 🚀 Synapse Tier Launching Soon!
        
        **Synapse** (Pro) will include:
        
        → **300 Catalyze Credits/month** (vs 40 Flow)  
        → A/B Strategy Output (2/3 depth)  
        → Direct link to **The Tribunal** for verification  
        → Priority processing  
        
        ---
        
        ### $19.99/month
        
        We're putting the finishing touches on our payment system.
        Join the waitlist to be notified when Synapse launches!
        """)
        
        st.markdown("#### 📧 Get Notified")
        
        waitlist_email = st.text_input("Email", value=current_user.email, key="waitlist_email")
        
        if st.button("🔔 Join Waitlist", use_container_width=True, type="primary"):
            success, message = auth_service.add_to_waitlist(waitlist_email)
            if success:
                st.success("🎉 " + message)
                st.balloons()
            else:
                st.error(message)

# Handle upgrade success/cancel from URL params
query_params = st.query_params
if query_params.get("upgrade") == "success":
    st.success("🎉 Welcome to Synapse! Your account has been upgraded.")
    # Refresh user from database to get updated tier
    updated_user = auth_service.get_user_by_id(current_user.id)
    if updated_user:
        st.session_state.current_user = updated_user
        current_user = updated_user
    st.query_params.clear()
    st.rerun()
elif query_params.get("upgrade") == "canceled":
    st.info("Upgrade canceled. You can upgrade anytime from the sidebar.")
    st.query_params.clear()

# Show upgrade dialog if triggered
if st.session_state.get('show_upgrade', False):
    st.session_state.show_upgrade = False
    show_upgrade_dialog()


# ============================================================================
# FOOTER
# ============================================================================
st.markdown("""
<div class="footer">
    Catalyze | Prompt Transformation Engine | Judge-then-Generate Pipeline
</div>
""", unsafe_allow_html=True)
