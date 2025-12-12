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
import asyncio
import html
import hashlib
import streamlit as st
import streamlit.components.v1 as components
from pathlib import Path
from datetime import datetime

# Load environment variables from .env
from dotenv import load_dotenv
load_dotenv()

# Import the v2 pipeline
from consensus_prompt_optimizer.orchestrator import PromptimaV2
from consensus_prompt_optimizer.config import FREE_TIER_MONTHLY_LIMIT, PRO_TIER_MONTHLY_LIMIT

# Import multimodal preprocessor
from consensus_prompt_optimizer.multimodal_preprocessor import (
    check_multimodal_availability,
    preprocess_multimodal_input,
    validate_audio_file,
    validate_image_file,
    estimate_multimodal_cost,
)
from consensus_prompt_optimizer.config import MULTIMODAL_CREDIT_COST

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
# CUSTOM CSS - Modern Glassmorphism Theme
# ============================================================================
st.markdown("""
<style>
    /* Import fonts */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&display=swap');
    
    /* Main dark theme - Deep Blue/Purple Gradient with Grid */
    .stApp {
        background-color: #0f172a;
        background-image: 
            linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #312e81 100%),
            linear-gradient(rgba(255, 255, 255, 0.03) 1px, transparent 1px),
            linear-gradient(90deg, rgba(255, 255, 255, 0.03) 1px, transparent 1px);
        background-size: 100% 100%, 40px 40px, 40px 40px;
        background-blend-mode: normal, overlay, overlay;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    /* Sidebar styling - Dark transparent */
    [data-testid="stSidebar"] {
        background-color: rgba(15, 23, 42, 0.9);
        border-right: 1px solid rgba(255, 255, 255, 0.05);
    }
    
    [data-testid="stSidebar"] .stMarkdown {
        color: #cbd5e1;
    }
    
    /* Glassmorphism Card */
    .glass-card {
        background: rgba(30, 41, 59, 0.7);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 16px;
        padding: 40px;
        box-shadow: 0 4px 30px rgba(0, 0, 0, 0.1);
    }

    /* Primary Button - Green */
    .stButton > button {
        background: linear-gradient(90deg, #22c55e 0%, #16a34a 100%);
        color: white;
        border: none;
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.3s ease;
        padding: 0.5rem 1rem;
    }
    .stButton > button:hover {
        background: linear-gradient(90deg, #16a34a 0%, #15803d 100%);
        box-shadow: 0 0 15px rgba(34, 197, 94, 0.4);
        border: none;
        color: white;
    }
    
    /* Secondary Button (Ghost) */
    .stButton > button[kind="secondary"] {
        background: transparent;
        border: 1px solid rgba(255, 255, 255, 0.2);
        color: #e2e8f0;
    }
    
    /* Input fields */
    .stTextInput > div > div > input {
        background-color: rgba(15, 23, 42, 0.6);
        border: 1px solid rgba(255, 255, 255, 0.1);
        color: white;
        border-radius: 8px;
    }
    .stTextInput > div > div > input:focus {
        border-color: #22c55e;
        box-shadow: 0 0 0 1px #22c55e;
    }

    /* Header styling */
    .main-header {
        font-size: 3rem;
        font-weight: 800;
        color: white;
        margin-bottom: 0;
        padding: 20px 0;
        font-family: 'Inter', sans-serif;
        text-align: center;
    }
    
    /* Feature list styling */
    .feature-item {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 12px;
        color: #e2e8f0;
        font-size: 0.95rem;
    }
    .feature-icon {
        color: #22c55e;
        font-size: 1.2rem;
    }
    
    /* Card styling for output (legacy support) */
    .output-card {
        background: rgba(30, 41, 59, 0.5);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        padding: 24px;
        margin: 16px 0;
    }
    
    .output-card-title {
        font-size: 1.25rem;
        font-weight: 600;
        color: #22c55e;
        margin: 0;
    }
    
    /* Prompt output text area */
    .prompt-output {
        background-color: rgba(15, 23, 42, 0.8);
        color: #F8F8F8;
        padding: 20px;
        border-radius: 8px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.9rem;
        white-space: pre-wrap;
        line-height: 1.7;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }
    
    /* Input field styling */
    .stTextArea textarea {
        background-color: rgba(15, 23, 42, 0.6) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 8px !important;
        color: #FFFFFF !important;
        font-size: 0.95rem !important;
        font-family: 'JetBrains Mono', monospace !important;
    }
    
    .stTextArea textarea:focus {
        border-color: #00F0FF !important;
        box-shadow: 0 0 20px rgba(0, 240, 255, 0.2) !important;
    }
    
    /* Primary button - Lime Green for positive actions */
    .stButton > button[kind="primary"],
    .stFormSubmitButton > button[kind="primary"],
    [data-testid="stFormSubmitButton"] > button {
        background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%) !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 14px 28px !important;
        font-weight: 600 !important;
        font-size: 0.95rem !important;
        font-family: 'Inter', sans-serif !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 4px 20px rgba(34, 197, 94, 0.3) !important;
        letter-spacing: 0.5px !important;
    }
    
    .stButton > button[kind="primary"]:hover,
    .stFormSubmitButton > button[kind="primary"]:hover,
    [data-testid="stFormSubmitButton"] > button:hover {
        background: linear-gradient(135deg, #16a34a 0%, #22c55e 100%) !important;
        box-shadow: 0 6px 30px rgba(34, 197, 94, 0.5) !important;
        transform: translateY(-2px) !important;
    }
    
    /* Secondary buttons */
    .stButton > button {
        background: transparent !important;
        color: #00F0FF !important;
        border: 1px solid rgba(0, 240, 255, 0.3) !important;
        border-radius: 8px !important;
        font-family: 'Inter', sans-serif !important;
        transition: all 0.2s ease !important;
    }
    
    .stButton > button:hover {
        background: rgba(0, 240, 255, 0.1) !important;
        border-color: #00F0FF !important;
    }
    
    /* Premium upgrade button */
    .upgrade-premium .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #a855f7 0%, #7c3aed 50%, #00F0FF 100%) !important;
        color: #ffffff !important;
        font-weight: 600 !important;
        box-shadow: 0 4px 20px rgba(168, 85, 247, 0.4) !important;
    }
    
    .upgrade-premium .stButton > button[kind="primary"]:hover {
        box-shadow: 0 6px 30px rgba(168, 85, 247, 0.6), 0 0 40px rgba(0, 240, 255, 0.3) !important;
    }
    
    /* Landing page - style the first column directly */
    .landing-left-col {
        background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #0f172a 100%) !important;
        min-height: 85vh;
        padding: 40px 30px !important;
        border-radius: 0 24px 24px 0;
        position: relative;
    }
    
    .landing-left-col::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0; bottom: 0;
        background-image: 
            linear-gradient(rgba(0, 240, 255, 0.03) 1px, transparent 1px),
            linear-gradient(90deg, rgba(0, 240, 255, 0.03) 1px, transparent 1px);
        background-size: 40px 40px;
        pointer-events: none;
        border-radius: 0 24px 24px 0;
    }
    
    .landing-logo {
        font-size: 2.5rem;
        font-weight: 800;
        color: #00F0FF;
        text-shadow: 0 0 60px rgba(0, 240, 255, 0.5);
        font-family: 'Inter', sans-serif;
        letter-spacing: 0.25em;
        text-align: center;
        margin-bottom: 8px;
    }
    
    .landing-tagline {
        color: #94a3b8;
        font-size: 1rem;
        font-family: 'Inter', sans-serif;
        letter-spacing: 0.02em;
        text-align: center;
        margin-bottom: 24px;
    }
    
    .landing-hero {
        width: 100%;
        max-width: 500px;
        border-radius: 16px;
        margin: 0 auto 24px auto;
        display: block;
    }
    
    .landing-features {
        max-width: 380px;
        margin: 0 auto;
    }
    
    .landing-feature {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 14px;
        color: #64748b;
        font-size: 0.9rem;
    }
    
    /* Sidebar branding */
    .sidebar-brand {
        font-size: 1.4rem;
        font-weight: 700;
        color: #00F0FF;
        font-family: 'Inter', sans-serif;
        letter-spacing: 0.1em;
        margin-bottom: 4px;
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
    
    /* Split layout landing page */
    .landing-container {
        display: flex;
        min-height: 100vh;
        margin: -1rem -1rem;
    }
    
    .landing-visual {
        flex: 1.2;
        background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #0f172a 100%);
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        padding: 60px;
        position: relative;
        overflow: hidden;
    }
    
    .landing-visual::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background-image: 
            linear-gradient(rgba(0, 240, 255, 0.03) 1px, transparent 1px),
            linear-gradient(90deg, rgba(0, 240, 255, 0.03) 1px, transparent 1px);
        background-size: 40px 40px;
        pointer-events: none;
    }
    
    .landing-logo {
        font-size: 4rem;
        font-weight: 800;
        color: #00F0FF;
        text-shadow: 0 0 60px rgba(0, 240, 255, 0.5);
        font-family: 'Inter', sans-serif;
        letter-spacing: 0.3em;
        z-index: 1;
    }
    
    .landing-tagline {
        color: #94a3b8;
        font-size: 1.1rem;
        margin-top: 16px;
        font-family: 'Inter', sans-serif;
        letter-spacing: 0.05em;
        z-index: 1;
    }
    
    .landing-features {
        margin-top: 60px;
        z-index: 1;
    }
    
    .landing-feature {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 16px;
        color: #64748b;
        font-size: 0.95rem;
    }
    
    .landing-feature-icon {
        color: #00F0FF;
        font-size: 1.1rem;
    }
    
    .landing-auth {
        flex: 0.8;
        background: #000000;
        display: flex;
        flex-direction: column;
        justify-content: center;
        padding: 60px 80px;
    }
    
    .auth-brand {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 40px;
    }
    
    .auth-brand-icon {
        color: #00F0FF;
        font-size: 1.5rem;
    }
    
    .auth-brand-text {
        font-size: 1.3rem;
        font-weight: 700;
        color: #00F0FF;
        font-family: 'Inter', sans-serif;
        letter-spacing: 0.15em;
    }
    
    /* Auth form styling */
    .auth-container {
        max-width: 100%;
    }
    
    .auth-header {
        margin-bottom: 30px;
    }
    
    .auth-title {
        font-size: 1.75rem;
        font-weight: 600;
        color: #f1f5f9;
        font-family: 'Inter', sans-serif;
        margin-bottom: 8px;
    }
    
    .auth-subtitle {
        color: #64748b;
        font-size: 0.95rem;
        font-family: 'Inter', sans-serif;
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
    
    /* ============================================
       MULTIMODAL INPUT STYLES
       ============================================ */
    
    /* Multimodal expander container */
    .multimodal-expander {
        margin-top: 16px;
        margin-bottom: 16px;
    }
    
    .multimodal-expander .streamlit-expanderHeader {
        background: linear-gradient(135deg, rgba(34, 197, 94, 0.1) 0%, rgba(0, 240, 255, 0.1) 100%);
        border: 1px solid rgba(34, 197, 94, 0.3);
        border-radius: 12px;
        color: #22c55e;
        font-weight: 600;
    }
    
    .multimodal-expander .streamlit-expanderHeader:hover {
        background: linear-gradient(135deg, rgba(34, 197, 94, 0.15) 0%, rgba(0, 240, 255, 0.15) 100%);
        border-color: #22c55e;
    }
    
    .multimodal-expander .streamlit-expanderContent {
        background: rgba(15, 23, 42, 0.6);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-top: none;
        border-radius: 0 0 12px 12px;
        padding: 20px;
    }
    
    /* Audio input styling */
    .stAudioInput {
        background: rgba(30, 41, 59, 0.5);
        border: 2px dashed rgba(34, 197, 94, 0.3);
        border-radius: 12px;
        padding: 16px;
        transition: all 0.3s ease;
    }
    
    .stAudioInput:hover {
        border-color: #22c55e;
        background: rgba(34, 197, 94, 0.05);
    }
    
    .stAudioInput > label {
        color: #22c55e !important;
        font-weight: 600 !important;
        font-size: 0.95rem !important;
    }
    
    /* File uploader styling for images */
    .stFileUploader {
        background: rgba(30, 41, 59, 0.5);
        border: 2px dashed rgba(0, 240, 255, 0.3);
        border-radius: 12px;
        padding: 16px;
        transition: all 0.3s ease;
    }
    
    .stFileUploader:hover {
        border-color: #00F0FF;
        background: rgba(0, 240, 255, 0.05);
    }
    
    .stFileUploader > label {
        color: #00F0FF !important;
        font-weight: 600 !important;
        font-size: 0.95rem !important;
    }
    
    /* Drag and drop zone */
    [data-testid="stFileUploadDropzone"] {
        background: rgba(15, 23, 42, 0.4) !important;
        border: 2px dashed rgba(0, 240, 255, 0.3) !important;
        border-radius: 12px !important;
    }
    
    [data-testid="stFileUploadDropzone"]:hover {
        border-color: #00F0FF !important;
        background: rgba(0, 240, 255, 0.05) !important;
    }
    
    /* Multimodal status indicator */
    .multimodal-status {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 8px 16px;
        border-radius: 8px;
        font-size: 0.85rem;
        font-weight: 500;
        font-family: 'JetBrains Mono', monospace;
    }
    
    .multimodal-status-active {
        background: linear-gradient(135deg, rgba(34, 197, 94, 0.2) 0%, rgba(0, 240, 255, 0.2) 100%);
        color: #22c55e;
        border: 1px solid rgba(34, 197, 94, 0.4);
    }
    
    .multimodal-status-text-only {
        background: rgba(100, 116, 139, 0.2);
        color: #94a3b8;
        border: 1px solid rgba(100, 116, 139, 0.3);
    }
    
    /* Multimodal input preview cards */
    .multimodal-preview {
        background: rgba(30, 41, 59, 0.6);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 8px;
        padding: 12px;
        margin-top: 8px;
    }
    
    .multimodal-preview-title {
        color: #22c55e;
        font-size: 0.85rem;
        font-weight: 600;
        margin-bottom: 8px;
    }
    
    /* Credit cost indicator */
    .credit-cost-badge {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        font-family: 'JetBrains Mono', monospace;
    }
    
    .credit-cost-standard {
        background: rgba(34, 197, 94, 0.2);
        color: #22c55e;
        border: 1px solid rgba(34, 197, 94, 0.3);
    }
    
    .credit-cost-multimodal {
        background: linear-gradient(135deg, rgba(168, 85, 247, 0.2) 0%, rgba(0, 240, 255, 0.2) 100%);
        color: #a855f7;
        border: 1px solid rgba(168, 85, 247, 0.3);
    }
    
    /* Image preview styling */
    .multimodal-image-preview {
        max-width: 200px;
        max-height: 150px;
        border-radius: 8px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        object-fit: cover;
    }
    
    /* Audio player styling */
    .stAudio > audio {
        width: 100% !important;
        border-radius: 8px;
    }
    
    /* Processing status for multimodal */
    .multimodal-processing {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 16px;
        background: rgba(34, 197, 94, 0.1);
        border: 1px solid rgba(34, 197, 94, 0.3);
        border-radius: 8px;
        margin: 12px 0;
    }
    
    .multimodal-processing-icon {
        animation: pulse 1.5s ease-in-out infinite;
    }
    
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.5; }
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
    """Display elegant split-layout login/register page."""
    
    # Handle special views (forgot password, reset)
    if st.session_state.auth_view in ['forgot_password', 'reset_password']:
        st.markdown('<p class="main-header">CATALYZE</p>', unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.session_state.auth_view == 'forgot_password':
                show_forgot_password_form()
            else:
                show_reset_password_form()
        return
    
    # Split layout: Visual left, Auth right
    left_col, right_col = st.columns([1.2, 0.8], gap="large")
    
    with left_col:
        st.markdown('<div style="height: 40px;"></div>', unsafe_allow_html=True)
        
        # Hero image
        st.image("assets/hero_robots.png", use_container_width=True)
        
        # Product Label
        st.markdown('<p style="color: #94a3b8; font-size: 0.85rem; font-weight: 600; letter-spacing: 0.08em; margin-top: 24px; margin-bottom: 16px; text-transform: uppercase;">Product: Catalyze</p>', unsafe_allow_html=True)
        
        # Feature 1
        st.markdown('<p style="display: flex; align-items: center; gap: 12px; margin-bottom: 10px; color: #e2e8f0; font-size: 0.95rem;"><span style="color: #22c55e; font-size: 1rem;">◆</span> 5-stage AI pipeline with Judge-then-Generate</p>', unsafe_allow_html=True)
        
        # Feature 2
        st.markdown('<p style="display: flex; align-items: center; gap: 12px; margin-bottom: 10px; color: #e2e8f0; font-size: 0.95rem;"><span style="color: #22c55e; font-size: 1rem;">◆</span> Success Spec ensures intent preservation</p>', unsafe_allow_html=True)
        
        # Feature 3
        st.markdown('<p style="display: flex; align-items: center; gap: 12px; margin-bottom: 10px; color: #e2e8f0; font-size: 0.95rem;"><span style="color: #22c55e; font-size: 1rem;">◆</span> ~$0.02 per optimization with full transparency</p>', unsafe_allow_html=True)
        
        # Feature 4
        st.markdown('<p style="display: flex; align-items: center; gap: 12px; margin-bottom: 10px; color: #e2e8f0; font-size: 0.95rem;"><span style="color: #22c55e; font-size: 1rem;">◆</span> 40 free credits monthly on Flow tier</p>', unsafe_allow_html=True)
    
    with right_col:
        # Auth form section wrapped in glass card
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        
        # Auth tabs
        auth_tab1, auth_tab2 = st.tabs(["Sign in", "Sign up"])
        
        with auth_tab1:
            st.markdown("<h2 style='font-size: 2rem; font-weight: 700; color: white; font-family: Inter, sans-serif; margin-bottom: 8px;'>Welcome back</h2>", unsafe_allow_html=True)
            st.markdown("<p style='color: #94a3b8; font-size: 0.95rem; margin-bottom: 32px;'>Enter your credentials to access your account.</p>", unsafe_allow_html=True)
            
            with st.form("login_form"):
                email = st.text_input("Email", placeholder="you@example.com")
                password = st.text_input("Password", type="password", placeholder="••••••••")
                
                st.markdown("<div style='height: 16px'></div>", unsafe_allow_html=True)
                submitted = st.form_submit_button("Sign in", use_container_width=True, type="primary")
                
                if submitted:
                    user, token, error = auth_service.login(email, password)
                    if error:
                        st.error(f"{error}")
                    else:
                        st.session_state.session_token = token
                        st.session_state.current_user = user
                        st.success("Welcome back!")
                        time.sleep(0.5)
                        st.rerun()
            
            if st.button("Forgot your password?", type="secondary"):
                st.session_state.auth_view = 'forgot_password'
                st.rerun()
        
        with auth_tab2:
            st.markdown("<h2 style='font-size: 2rem; font-weight: 700; color: white; font-family: Inter, sans-serif; margin-bottom: 8px;'>Create account</h2>", unsafe_allow_html=True)
            st.markdown("<p style='color: #94a3b8; font-size: 0.95rem; margin-bottom: 32px;'>Start optimizing your prompts today.</p>", unsafe_allow_html=True)
            
            with st.form("register_form"):
                reg_email = st.text_input("Email", placeholder="you@example.com", key="reg_email")
                
                col_name1, col_name2 = st.columns(2)
                with col_name1:
                    first_name = st.text_input("First Name", placeholder="John")
                with col_name2:
                    last_name = st.text_input("Last Name", placeholder="Doe")
                
                reg_password = st.text_input("Password", type="password", placeholder="Min 8 characters", key="reg_pass")
                confirm_password = st.text_input("Confirm Password", type="password", placeholder="••••••••", key="confirm_pass")
                
                st.markdown("<div style='height: 16px'></div>", unsafe_allow_html=True)
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
                        st.success("Account created successfully!")
                        time.sleep(0.5)
                        st.rerun()
            
            st.markdown("<p style='color: #64748b; font-size: 0.85rem; text-align: center; margin-top: 16px;'>Flow tier includes 40 free Catalyze Credits/month</p>", unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)


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
    st.markdown('<p class="sidebar-brand">◆ CATALYZE</p>', unsafe_allow_html=True)
    st.markdown('<span style="color: #64748b; font-size: 0.8rem;">Prompt Transformation Engine</span>', unsafe_allow_html=True)
    
    st.markdown("---")
    
    # User - Just name
    st.markdown(f"**{current_user.full_name}**")

    # Admin-only diagnostics to quickly confirm deploy + env wiring on Railway
    if getattr(current_user, "tier", "") == "admin":
        with st.expander("Diagnostics", expanded=False):
            try:
                app_hash = hashlib.sha1(Path(__file__).read_bytes()).hexdigest()[:8]
            except Exception:
                app_hash = "unknown"

            groq_set = bool(os.getenv("GROQ_API_KEY", "").strip())
            deepseek_set = bool(os.getenv("DEEPSEEK_API_KEY", "").strip())
            gemini_set = bool(os.getenv("GEMINI_API_KEY", "").strip())
            openai_set = bool(os.getenv("OPENAI_API_KEY", "").strip())

            mm = check_multimodal_availability()

            st.write({
                "app_hash": app_hash,
                "streamlit_version": getattr(st, "__version__", "unknown"),
                "railway_public_domain": os.getenv("RAILWAY_PUBLIC_DOMAIN", ""),
                "keys_present": {
                    "GROQ_API_KEY": groq_set,
                    "DEEPSEEK_API_KEY": deepseek_set,
                    "GEMINI_API_KEY": gemini_set,
                    "OPENAI_API_KEY": openai_set,
                },
                "multimodal": {
                    "voice": mm.get("voice"),
                    "image": mm.get("image"),
                    "voice_reason": mm.get("voice_reason"),
                    "image_reason": mm.get("image_reason"),
                },
            })
    
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
            st.markdown('<div class="upgrade-premium">', unsafe_allow_html=True)
            if st.button("✨ Upgrade to Synapse", use_container_width=True, type="primary"):
                st.session_state.show_upgrade = True
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
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
    
    # ========================================================================
    # MULTIMODAL INPUT SECTION - Always visible for discoverability
    # ========================================================================
    
    # Check if multimodal is available
    multimodal_available = check_multimodal_availability()
    voice_available = multimodal_available.get(
        "voice",
        multimodal_available.get("voice_available", False)
    )
    image_available = multimodal_available.get(
        "image",
        multimodal_available.get("image_available", False)
    )
    voice_reason = multimodal_available.get("voice_reason", "Voice unavailable")
    image_reason = multimodal_available.get("image_reason", "Image unavailable")

    # Lightweight deploy/build indicator (helps confirm Railway is running latest code)
    build_sha = (os.getenv("RAILWAY_GIT_COMMIT_SHA") or os.getenv("GIT_COMMIT") or "").strip()
    if build_sha:
        st.caption(f"Build: {build_sha[:7]}")
    
    # Initialize multimodal session state
    if 'audio_input' not in st.session_state:
        st.session_state.audio_input = None
    if 'image_input' not in st.session_state:
        st.session_state.image_input = None
    
    # Multimodal section - always visible with proper styling
    st.markdown("""
    <div style="margin: 16px 0 8px 0; display: flex; align-items: center; gap: 8px;">
        <span style="color: #22c55e; font-size: 0.9rem; font-weight: 600;">✨ Enhanced Input</span>
        <span style="color: #64748b; font-size: 0.8rem;">— Add voice or image for richer prompts</span>
    </div>
    """, unsafe_allow_html=True)
    
    # Two-column layout for voice and image
    col_voice, col_image = st.columns(2)
    
    with col_voice:
        st.markdown("""
        <div style="background: rgba(34, 197, 94, 0.05); border: 2px dashed rgba(34, 197, 94, 0.3); border-radius: 12px; padding: 12px; text-align: center;">
            <span style="font-size: 1.5rem;">🎤</span>
            <p style="color: #22c55e; font-weight: 600; margin: 8px 0 4px 0; font-size: 0.9rem;">Voice Recording</p>
        </div>
        """, unsafe_allow_html=True)
        
        if voice_available:
            audio_bytes = st.audio_input(
                "Record your prompt idea",
                key="voice_recorder",
                help="Click to record, click again to stop. Your voice will be transcribed automatically.",
                label_visibility="collapsed"
            )
            if audio_bytes:
                st.session_state.audio_input = audio_bytes
                st.success("✓ Voice recorded successfully!")
                st.audio(audio_bytes, format="audio/wav")
        else:
            st.markdown("""
            <p style="color: #94a3b8; font-size: 0.75rem; text-align: center; margin-top: 8px;">
                ⚠️ {reason}
            </p>
            """.format(reason=voice_reason), unsafe_allow_html=True)
    
    with col_image:
        st.markdown("""
        <div style="background: rgba(0, 240, 255, 0.05); border: 2px dashed rgba(0, 240, 255, 0.3); border-radius: 12px; padding: 12px; text-align: center;">
            <span style="font-size: 1.5rem;">📷</span>
            <p style="color: #00F0FF; font-weight: 600; margin: 8px 0 4px 0; font-size: 0.9rem;">Image Upload</p>
        </div>
        """, unsafe_allow_html=True)
        
        if image_available:
            uploaded_image = st.file_uploader(
                "Upload an image for context",
                type=["png", "jpg", "jpeg", "webp", "gif"],
                key="image_uploader",
                help="Upload an image to analyze. Supports PNG, JPG, WebP, and GIF formats.",
                label_visibility="collapsed"
            )
            if uploaded_image:
                st.session_state.image_input = uploaded_image
                st.success(f"✓ {uploaded_image.name}")
                st.image(uploaded_image, width=150)
        else:
            st.markdown("""
            <p style="color: #94a3b8; font-size: 0.75rem; text-align: center; margin-top: 8px;">
                ⚠️ {reason}
            </p>
            """.format(reason=image_reason), unsafe_allow_html=True)
    
    # Show multimodal status and clear button
    has_multimodal = st.session_state.audio_input or st.session_state.image_input
    if has_multimodal:
        col_status, col_clear = st.columns([3, 1])
        with col_status:
            st.markdown(f"""
            <div style="padding: 10px; background: linear-gradient(135deg, rgba(168, 85, 247, 0.15) 0%, rgba(0, 240, 255, 0.15) 100%); border: 1px solid rgba(168, 85, 247, 0.4); border-radius: 8px; margin-top: 8px;">
                <span style="color: #a855f7; font-weight: 600;">💎 Multimodal Active</span>
                <span style="color: #cbd5e1; font-size: 0.85rem;"> — Uses {MULTIMODAL_CREDIT_COST} credits</span>
            </div>
            """, unsafe_allow_html=True)
        with col_clear:
            st.markdown("<div style='height: 8px'></div>", unsafe_allow_html=True)
            if st.button("🗑️ Clear", key="clear_multimodal", help="Remove voice and image inputs"):
                st.session_state.audio_input = None
                st.session_state.image_input = None
                st.rerun()
    
    st.markdown("")
    
    # Show credit cost based on multimodal state
    has_multimodal_inputs = st.session_state.get('audio_input') or st.session_state.get('image_input')
    credit_cost = MULTIMODAL_CREDIT_COST if has_multimodal_inputs else 1
    credit_label = "2 credits" if has_multimodal_inputs else "1 credit"
    
    # Optimize button - centered
    run_button = st.button(
        f"OPTIMIZE → ({credit_label})", 
        type="primary", 
        use_container_width=True
    )

# No context tags needed - simplify
context_tags = []

st.markdown("")

# ============================================================================
# PROCESSING & RESULTS
# ============================================================================

# Helper function to run async code in Streamlit
def run_async(coro):
    """Run async coroutine in sync context for Streamlit."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)

if run_button and (idea or st.session_state.get('audio_input') or st.session_state.get('image_input')):
    has_audio_input = bool(st.session_state.get('audio_input'))
    has_image_input = bool(st.session_state.get('image_input'))

    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    deepseek_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()

    missing: list[str] = []

    # Normal runs: Groq first, DeepSeek fallback.
    if not groq_key and not deepseek_key:
        missing.append("GROQ_API_KEY (preferred) or DEEPSEEK_API_KEY (fallback)")

    # Multimodal-only requirements
    if has_image_input and not gemini_key:
        missing.append("GEMINI_API_KEY (required for image analysis)")
    if has_audio_input and not openai_key:
        missing.append("OPENAI_API_KEY (required for voice transcription)")

    if missing:
        st.error("Missing API keys: " + ", ".join(missing))
    else:
        # Determine credit cost based on multimodal inputs
        has_multimodal_inputs = has_audio_input or has_image_input
        credit_cost = MULTIMODAL_CREDIT_COST if has_multimodal_inputs else 1
        
        # Check rate limit from database (with credit cost)
        is_within_limit, current_count, limit = usage_service.check_limit(current_user.id, current_user.tier)
        
        # Also check if we have enough credits for this operation
        # Note: limit is None for unlimited tiers (admin, enterprise)
        if limit is not None and current_count + credit_cost > limit:
            is_within_limit = False
        
        if not is_within_limit:
            st.error(f"Monthly limit reached ({current_count}/{limit} CCs). Resets on the 1st of next month.")
            if current_user.tier == "free":
                btn_text = "⚡ Upgrade to Synapse for 300 CCs/month" if stripe_service.is_configured else "🚀 Synapse Coming Soon - Join Waitlist"
                if st.button(btn_text):
                    st.session_state.show_upgrade = True
                    st.rerun()
        else:
            # Determine spinner message based on input type
            if has_multimodal_inputs:
                spinner_msg = "Processing multimodal inputs and optimizing your prompt... (this takes 15-45 seconds)"
            else:
                spinner_msg = "Optimizing your prompt... (this takes 10-30 seconds)"
            
            with st.spinner(spinner_msg):
                try:
                    start_time = time.time()
                    
                    # Get multimodal inputs
                    audio_data = st.session_state.get('audio_input')
                    image_data = st.session_state.get('image_input')
                    
                    # Preprocess multimodal inputs if present
                    if has_multimodal_inputs:
                        st.info("🔄 Preprocessing multimodal inputs...")
                        
                        # Convert audio/image to bytes format if present
                        audio_bytes_data = audio_data.getvalue() if audio_data else None
                        image_bytes_data = image_data.getvalue() if image_data else None
                        
                        # Call multimodal preprocessor (async)
                        preprocessed = run_async(preprocess_multimodal_input(
                            text_input=idea if idea else "",
                            audio_bytes=audio_bytes_data,
                            image_bytes=image_bytes_data
                        ))
                        
                        # Get the combined prompt from preprocessing
                        enhanced_idea = preprocessed.get("combined_prompt", idea)
                        
                        # Show what was processed
                        voice_result = preprocessed.get("voice_result")
                        if voice_result and voice_result.get("success"):
                            transcribed_text = voice_result.get("text", "")
                            if transcribed_text:
                                display_text = transcribed_text[:100] + "..." if len(transcribed_text) > 100 else transcribed_text
                                st.success(f"🎤 Voice transcribed: \"{display_text}\"")
                        
                        image_result = preprocessed.get("image_result")
                        if image_result and image_result.get("success"):
                            analysis_text = image_result.get("description", "")
                            if analysis_text:
                                display_text = analysis_text[:100] + "..." if len(analysis_text) > 100 else analysis_text
                                st.success(f"📷 Image analyzed: \"{display_text}\"")
                        
                        # Show any errors from preprocessing
                        preprocess_errors = preprocessed.get("errors", [])
                        for error in preprocess_errors:
                            st.warning(f"⚠️ {error}")
                    else:
                        enhanced_idea = idea
                    
                    # Add context tags if present
                    if context_tags:
                        enhanced_idea = f"{enhanced_idea}\n\nContext variables to include: {', '.join(context_tags)}"
                    
                    # Run the optimizer
                    optimizer = PromptimaV2(use_cache=use_cache, dry_run=dry_run)
                    result = optimizer.run(enhanced_idea)
                    
                    end_time = time.time()
                    latency = end_time - start_time
                    
                    # Store results
                    st.session_state['last_result'] = result
                    st.session_state['last_idea'] = idea
                    st.session_state['last_latency'] = latency
                    st.session_state['last_was_multimodal'] = has_multimodal_inputs
                    
                    # Increment usage counter in database (with correct credit cost)
                    if credit_cost > 1:
                        usage_service.increment_usage_by(current_user.id, credit_cost)
                    else:
                        usage_service.increment_usage(current_user.id)
                    
                    # Clear multimodal inputs after successful processing
                    if has_multimodal_inputs:
                        st.session_state.audio_input = None
                        st.session_state.image_input = None
                    
                    # Add to history
                    st.session_state.history.append({
                        'idea': idea,
                        'result': result.get('final_synthesis', {}).get('prompt', ''),
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M')
                    })
                    
                except Exception as e:
                    st.error(f"Error: {str(e)}")
                    st.exception(e)

elif run_button and not idea and not st.session_state.get('audio_input') and not st.session_state.get('image_input'):
    st.warning("Please enter a prompt idea, record a voice message, or upload an image first")


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
    
    # Escape HTML in prompt to prevent XSS/rendering issues
    escaped_prompt = html.escape(prompt_text)
    
    with col_output:
        st.markdown(f'<div class="prompt-output">{escaped_prompt}</div>', unsafe_allow_html=True)
    
    with col_actions:
        st.markdown("")
        st.markdown("")
        
        # Copy to Clipboard button with JavaScript
        if st.button("📋 Copy", use_container_width=True, key="copy_btn"):
            # Inject JavaScript to copy to clipboard
            escaped_for_js = prompt_text.replace('\\', '\\\\').replace('`', '\\`').replace('$', '\\$')
            components.html(f"""
                <script>
                    navigator.clipboard.writeText(`{escaped_for_js}`).then(function() {{
                        window.parent.postMessage({{type: 'streamlit:toast', message: 'Copied to clipboard!'}}, '*');
                    }}).catch(function(err) {{
                        console.error('Copy failed: ', err);
                    }});
                </script>
            """, height=0)
            st.toast("✅ Copied to clipboard!")
        
        # Direct download button (no nesting required)
        st.download_button(
            label="💾 Save",
            data=prompt_text,
            file_name=f"prompt_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            mime="text/plain",
            key="save_prompt",
            use_container_width=True
        )
        
        # Regenerate button
        if st.button("🔄 Regenerate", use_container_width=True, key="regen_btn"):
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
