"""
Promptly 3.0 - AI-Powered Prompt Engineering Platform
=====================================================
A sophisticated web UI for the Consensus Prompt Optimizer.
Transform your ideas into bulletproof prompts.

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

# Import authentication
from auth import AuthService, UsageService


# ============================================================================
# PAGE CONFIGURATION
# ============================================================================
st.set_page_config(
    page_title="Promptly - AI Prompt Engineering",
    page_icon="⚡",
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
    
    /* Header with cyan glow */
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #00F0FF;
        text-shadow: 0 0 30px rgba(0, 240, 255, 0.5), 0 0 60px rgba(0, 240, 255, 0.3);
        margin-bottom: 0;
        padding: 0;
        font-family: 'JetBrains Mono', monospace;
        letter-spacing: 2px;
    }
    
    .sub-header {
        font-size: 0.95rem;
        color: #718096;
        margin-top: 4px;
        margin-bottom: 20px;
        font-family: 'JetBrains Mono', monospace;
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
    
    /* Primary button with cyan gradient */
    .stButton > button[kind="primary"] {
        background: #00F0FF !important;
        color: #000000 !important;
        border: none !important;
        border-radius: 4px !important;
        padding: 12px 24px !important;
        font-weight: 700 !important;
        font-size: 0.95rem !important;
        font-family: 'JetBrains Mono', monospace !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 0 20px rgba(0, 240, 255, 0.4) !important;
        text-transform: uppercase !important;
        letter-spacing: 1px !important;
    }
    
    .stButton > button[kind="primary"]:hover {
        background: #FFFFFF !important;
        box-shadow: 0 0 30px rgba(0, 240, 255, 0.6) !important;
        transform: translateY(-2px) !important;
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
                st.success(f"✅ {message}")
                # In development, show the token (remove in production)
                if token:
                    st.info(f"🔧 Dev Mode: Reset token = {token[:20]}...")
                    st.session_state.reset_token = token
                    st.session_state.auth_view = 'reset_password'
                    time.sleep(1)
                    st.rerun()
            else:
                st.error(f"❌ {message}")
    
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
                st.error("❌ Invalid reset link. Please request a new one.")
            else:
                success, message = auth_service.reset_password(token, new_password, confirm_password)
                if success:
                    st.success(f"✅ {message}")
                    st.session_state.reset_token = None
                    st.session_state.auth_view = 'login'
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(f"❌ {message}")
    
    if st.button("← Back to Login"):
        st.session_state.reset_token = None
        st.session_state.auth_view = 'login'
        st.rerun()


def show_auth_page():
    """Display login/register page."""
    st.markdown('<p class="main-header">⚡ Promptly</p>', unsafe_allow_html=True)
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
        auth_tab1, auth_tab2 = st.tabs(["🔐 Login", "📝 Register"])
        
        with auth_tab1:
            st.markdown("#### Welcome back!")
            with st.form("login_form"):
                email = st.text_input("Email", placeholder="you@example.com")
                password = st.text_input("Password", type="password", placeholder="••••••••")
                
                submitted = st.form_submit_button("Login", use_container_width=True, type="primary")
                
                if submitted:
                    user, token, error = auth_service.login(email, password)
                    if error:
                        st.error(f"❌ {error}")
                    else:
                        st.session_state.session_token = token
                        st.session_state.current_user = user
                        st.success("✅ Login successful!")
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
                        st.error(f"❌ {error}")
                    else:
                        st.session_state.session_token = token
                        st.session_state.current_user = user
                        st.success("✅ Account created successfully!")
                        time.sleep(0.5)
                        st.rerun()
            
            st.markdown("---")
            st.markdown('<p style="color: #8b949e; font-size: 0.85rem; text-align: center;">🎁 Free tier includes 100 optimizations/month</p>', unsafe_allow_html=True)
    
    # Footer
    st.markdown("""
    <div class="footer">
        Promptly 3.0 | AI-Powered Prompt Engineering | Secure & Private
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
# SIDEBAR - CONFIGURATION
# ============================================================================
with st.sidebar:
    # Logo/Brand
    st.markdown("### ⚡ Promptly")
    st.markdown('<span style="color: #8b949e; font-size: 0.85rem;">AI-Powered Prompt Engineering</span>', unsafe_allow_html=True)
    
    st.markdown("---")
    
    # User Profile Section
    tier_class = f"tier-{current_user.tier}"
    st.markdown(f"👤 **{current_user.full_name}**")
    st.markdown(f'<span style="color: #8b949e; font-size: 0.8rem;">{current_user.email}</span>', unsafe_allow_html=True)
    
    # Email verification status
    if current_user.email_verified:
        st.markdown(f'<span style="color: #3fb950; font-size: 0.75rem;">✓ Email verified</span>', unsafe_allow_html=True)
    else:
        st.markdown(f'<span style="color: #d29922; font-size: 0.75rem;">⚠ Email not verified</span>', unsafe_allow_html=True)
        if st.button("📧 Resend verification", use_container_width=True, type="secondary"):
            success, message, token = auth_service.resend_verification_email(current_user.id)
            if success:
                st.success(message)
                if token:
                    st.info(f"🔧 Dev: Verification token = {token[:20]}...")
            else:
                st.error(message)
    
    st.markdown(f'<span class="tier-badge {tier_class}">{current_user.tier.upper()}</span>', unsafe_allow_html=True)
    
    if st.button("🚪 Logout", use_container_width=True):
        auth_service.logout(st.session_state.session_token)
        st.session_state.session_token = None
        st.session_state.current_user = None
        st.session_state.auth_view = 'login'
        st.rerun()
    
    st.markdown("---")
    
    # Configuration Section (Collapsible)
    with st.expander("⚙️ Configuration", expanded=False):
        st.markdown("Configure your optimization settings")
        use_cache = st.checkbox("Use cache", value=True, help="Cache results to avoid re-running")
        dry_run = st.checkbox("Dry run mode", value=False, help="Test without API calls")
        show_details = st.checkbox("Show stage details", value=True, help="Display intermediate outputs")
    
    # API Keys Section (Collapsible)
    with st.expander("🔑 API Keys", expanded=True):
        gemini_key = os.getenv("GEMINI_API_KEY", "")
        deepseek_key = os.getenv("DEEPSEEK_API_KEY", "")
        
        if gemini_key and deepseek_key:
            st.markdown('<div class="status-badge status-connected">● Connected</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="status-badge status-disconnected">● Disconnected</div>', unsafe_allow_html=True)
        
        st.markdown("")
        
        if not gemini_key:
            gemini_key = st.text_input("Gemini API Key:", type="password", key="gemini_input")
            if gemini_key:
                os.environ["GEMINI_API_KEY"] = gemini_key
        else:
            st.markdown("✓ Gemini: `***" + gemini_key[-4:] + "`")
        
        if not deepseek_key:
            deepseek_key = st.text_input("DeepSeek API Key:", type="password", key="deepseek_input")
            if deepseek_key:
                os.environ["DEEPSEEK_API_KEY"] = deepseek_key
        else:
            st.markdown("✓ DeepSeek: `***" + deepseek_key[-4:] + "`")
    
    # Usage Section - Rate Limiting Display
    st.markdown("#### 📊 Usage")
    usage_count = user_usage.count
    
    # Handle unlimited tier
    if usage_limit is None:
        st.markdown("✅ **Unlimited** requests")
        st.markdown(f'<span style="color: #8b949e; font-size: 0.75rem;">Enterprise tier - no limits</span>', unsafe_allow_html=True)
    else:
        remaining = max(0, usage_limit - usage_count)
        usage_pct = min(1.0, usage_count / usage_limit) if usage_limit > 0 else 0
        
        # Progress bar with color coding
        if usage_count >= usage_limit:
            st.error(f"❌ Monthly limit reached ({usage_count}/{usage_limit})")
            # Upgrade button
            if current_user.tier == "free":
                if st.button("⬆️ Upgrade to Pro", use_container_width=True, type="primary"):
                    st.session_state.show_upgrade = True
        elif usage_pct >= 0.8:
            st.warning(f"⚠️ {remaining} requests remaining this month")
            st.progress(usage_pct)
        else:
            st.markdown(f"✅ **{remaining}** requests remaining")
            st.progress(usage_pct)
        
        st.markdown(f'<span style="color: #8b949e; font-size: 0.75rem;">Resets on the 1st of each month</span>', unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Options Section (Collapsible)
    with st.expander("🛠️ Options", expanded=False):
        st.selectbox("Model Preference", ["Balanced", "Speed", "Quality"], index=0)
        st.slider("Creativity", 0.0, 1.0, 0.7, help="Higher = more creative variations")
    
    # History Section (Collapsible)
    with st.expander("📜 History", expanded=False):
        if st.session_state.history:
            for i, item in enumerate(st.session_state.history[-5:]):
                st.markdown(f"**{i+1}.** {item['idea'][:40]}...")
        else:
            st.markdown("*No optimization history yet*")
    
    st.markdown("---")
    
    # About Section (Collapsible at bottom)
    with st.expander("ℹ️ About", expanded=False):
        st.markdown("""
**Promptly 3.0** uses a 5-stage pipeline:

1. 🔍 **Discerner** - Analyze intent
2. 📋 **CriticFirst** - Generate rubric  
3. 🎨 **Expander** - Create variations
4. 🏆 **Ranker** - Rank variations
5. ✨ **Synthesizer** - Final prompt

Cost: ~$0.0005/run (mostly free!)
        """)


# ============================================================================
# MAIN CONTENT AREA
# ============================================================================

# Header
st.markdown('<p class="main-header">⚡ Promptly</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Transform your ideas into bulletproof prompts</p>', unsafe_allow_html=True)

# Main tabs: Input / Examples / History
main_tab1, main_tab2, main_tab3 = st.tabs(["📝 Input", "📚 Examples", "📜 History"])

with main_tab1:
    # Context Tags Section
    st.markdown("#### 🏷️ Variables / Context Tags")
    context_tags = st.multiselect(
        "Add dynamic placeholders:",
        options=[
            "{user_name}", "{company}", "{industry}", "{product}",
            "{tone}", "{audience}", "{language}", "{format}",
            "{constraints}", "{examples}", "{persona}", "{goal}"
        ],
        default=[],
        label_visibility="collapsed",
        help="These variables will be included in your optimized prompt"
    )
    
    st.markdown("")
    
    # Input Section
    st.markdown("#### 💡 Your Prompt Idea")
    idea = st.text_area(
        "Enter your prompt idea:",
        placeholder="Example: Write a prompt that helps an AI assistant explain complex scientific concepts to children aged 8-12",
        height=120,
        label_visibility="collapsed"
    )
    
    st.markdown("")
    
    # Run button - centered
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        run_button = st.button(
            "🔧 Optimize Prompt", 
            type="primary", 
            use_container_width=True
        )

with main_tab2:
    st.markdown("#### 📚 Example Prompt Ideas")
    st.markdown("Click any example to use it as your starting point:")
    
    examples = [
        ("Blog Titles", "Create a prompt for generating creative blog post titles that are SEO-friendly"),
        ("Code Debug", "Write a prompt that helps debug Python code with clear, step-by-step explanations"),
        ("Document Summary", "Design a prompt for summarizing long documents while preserving key insights"),
        ("SQL Generator", "Create a prompt for generating SQL queries from natural language descriptions"),
        ("Startup Ideas", "Write a prompt that helps brainstorm innovative startup ideas in a specific domain"),
    ]
    
    for title, example in examples:
        if st.button(f"💡 {title}", key=f"ex_{title}", use_container_width=True):
            st.session_state['selected_example'] = example
            st.rerun()

with main_tab3:
    st.markdown("#### 📜 Optimization History")
    if st.session_state.history:
        for i, item in enumerate(reversed(st.session_state.history[-10:])):
            with st.expander(f"**{item['idea'][:50]}...** - {item['timestamp']}"):
                st.code(item['result'], language=None)
    else:
        st.info("No optimization history yet. Run your first prompt optimization!")


# Check for selected example
if 'selected_example' in st.session_state:
    idea = st.session_state.pop('selected_example')

st.markdown("---")

# ============================================================================
# PROCESSING & RESULTS
# ============================================================================
if run_button and idea:
    if not os.getenv("GEMINI_API_KEY") or not os.getenv("DEEPSEEK_API_KEY"):
        st.error("⚠️ Please configure API keys in the sidebar first!")
    else:
        # Check rate limit from database
        is_within_limit, current_count, limit = usage_service.check_limit(current_user.id, current_user.tier)
        
        if not is_within_limit:
            st.error(f"❌ Monthly usage limit reached ({current_count}/{limit} requests). Resets on the 1st of next month.")
            if current_user.tier == "free":
                st.info("💡 Upgrade to Pro for 500 requests/month!")
        else:
            with st.spinner("🔄 Optimizing your prompt... (this takes 10-30 seconds)"):
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
                    st.error(f"❌ Error: {str(e)}")
                    st.exception(e)

elif run_button and not idea:
    st.warning("⚠️ Please enter a prompt idea first!")


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
        if st.button("📋 Copy", use_container_width=True):
            st.toast("Copied to clipboard!", icon="✅")
        if st.button("💾 Save", use_container_width=True):
            st.download_button(
                label="📥 Download",
                data=prompt_text,
                file_name=f"prompt_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                mime="text/plain",
                key="save_prompt"
            )
        if st.button("🔄 Regenerate", use_container_width=True):
            st.session_state.pop('last_result', None)
            st.rerun()
    
    st.markdown("")
    
    # ========================================================================
    # METRICS PANEL
    # ========================================================================
    st.markdown("#### 📊 Optimization Metrics")
    
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
    with st.expander("📋 Detailed Analysis", expanded=False):
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
                label="📥 Download Full JSON",
                data=json.dumps(result, indent=2),
                file_name=f"promptly_output_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )


# ============================================================================
# UPGRADE MODAL (Placeholder for Stripe)
# ============================================================================
@st.dialog("⬆️ Upgrade to Promptly Pro")
def show_upgrade_dialog():
    st.markdown("""
    ### Unlock More Power
    
    **Promptly Pro** gives you:
    
    ✅ **500 optimizations/month** (vs 100 free)  
    ✅ Priority processing  
    ✅ Advanced analytics  
    ✅ Email support  
    
    ---
    
    ### $9.99/month
    
    """)
    
    st.info("🚧 **Coming Soon!** Stripe integration is in development.")
    
    st.markdown("#### Join the Waitlist")
    st.markdown("Be the first to know when Pro launches:")
    
    waitlist_email = st.text_input("Email", value=current_user.email, key="waitlist_email")
    
    if st.button("📬 Notify Me", use_container_width=True, type="primary"):
        success, message = auth_service.add_to_waitlist(waitlist_email)
        if success:
            st.success(message)
        else:
            st.error(message)

# Show upgrade dialog if triggered
if st.session_state.get('show_upgrade', False):
    st.session_state.show_upgrade = False
    show_upgrade_dialog()


# ============================================================================
# FOOTER
# ============================================================================
st.markdown("""
<div class="footer">
    Promptly 3.0 | AI-Powered Prompt Engineering | Judge-then-Generate Pipeline
</div>
""", unsafe_allow_html=True)
