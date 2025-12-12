"""
Email service for Catalyze using SendGrid.
Handles transactional emails: verification, password reset, welcome, etc.
"""

import os
from datetime import datetime
from typing import Optional
from .logger import logger

# SendGrid configuration
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
SENDGRID_FROM_EMAIL = os.getenv("SENDGRID_FROM_EMAIL", "noreply@catalyze.app")
SENDGRID_FROM_NAME = os.getenv("SENDGRID_FROM_NAME", "Catalyze")

# App URL for links in emails
APP_URL = os.getenv("APP_URL", "")
if not APP_URL and os.getenv("RAILWAY_PUBLIC_DOMAIN"):
    APP_URL = f"https://{os.getenv('RAILWAY_PUBLIC_DOMAIN')}"

# SendGrid is optional - only import if configured
sg = None
if SENDGRID_API_KEY:
    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail, Email, To, Content, Substitution
        sg = SendGridAPIClient(SENDGRID_API_KEY)
    except ImportError:
        logger.warning("SendGrid package not installed. Run: pip install sendgrid")


# =============================================================================
# BRANDED EMAIL TEMPLATE
# =============================================================================

def _get_email_template(subject: str, content_html: str, show_unsubscribe: bool = False) -> str:
    """
    Generate a branded Catalyze email using the premium dark theme.
    
    Args:
        subject: Email subject (for title tag)
        content_html: The main content HTML to insert
        show_unsubscribe: Whether to show unsubscribe link (for marketing emails)
    
    Returns:
        Complete HTML email string
    """
    year = datetime.now().year
    unsubscribe_html = f' • <a href="{APP_URL}?unsubscribe=true" style="color:#64748b;">Unsubscribe</a>' if show_unsubscribe else ''
    
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{subject}</title>
  <style>
    body {{ 
      margin: 0; 
      padding: 0; 
      background: #0f172a; 
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
    }}
    .wrapper {{
      padding: 40px 20px;
      background: #0f172a;
    }}
    .container {{ 
      max-width: 600px; 
      margin: 0 auto; 
      background: #1e293b; 
      border-radius: 16px; 
      overflow: hidden; 
      box-shadow: 0 20px 40px rgba(0,0,0,0.6); 
    }}
    .header {{ 
      background: linear-gradient(135deg, #00d4aa 0%, #7c3aed 100%); 
      padding: 40px 30px; 
      text-align: center; 
    }}
    .logo {{ 
      font-size: 36px; 
      font-weight: 800; 
      color: white; 
      letter-spacing: 2px; 
      text-shadow: 0 2px 10px rgba(0,0,0,0.3);
    }}
    .tagline {{
      color: rgba(255,255,255,0.9);
      font-size: 14px;
      margin-top: 8px;
      letter-spacing: 1px;
    }}
    .content {{ 
      padding: 40px 30px; 
      color: #cbd5e1; 
      line-height: 1.7; 
      font-size: 16px; 
    }}
    .content h2 {{
      color: #f1f5f9;
      margin-top: 0;
      font-size: 24px;
    }}
    .content p {{
      margin: 16px 0;
    }}
    .button {{ 
      display: inline-block; 
      background: linear-gradient(135deg, #00d4aa 0%, #00b894 100%); 
      color: white !important; 
      padding: 16px 40px; 
      text-decoration: none; 
      border-radius: 8px; 
      font-weight: 700; 
      font-size: 16px;
      margin: 24px 0;
      box-shadow: 0 4px 15px rgba(0,212,170,0.4);
      transition: transform 0.2s;
    }}
    .button:hover {{
      transform: translateY(-2px);
    }}
    .button-secondary {{
      background: linear-gradient(135deg, #7c3aed 0%, #a855f7 100%);
      box-shadow: 0 4px 15px rgba(124,58,237,0.4);
    }}
    .feature-box {{
      background: #0f172a;
      border: 1px solid #334155;
      border-radius: 12px;
      padding: 20px;
      margin: 20px 0;
    }}
    .feature-title {{
      color: #00d4aa;
      font-weight: 700;
      font-size: 16px;
      margin-bottom: 12px;
    }}
    .feature-box ul {{
      margin: 0;
      padding-left: 20px;
    }}
    .feature-box li {{
      margin: 8px 0;
      color: #94a3b8;
    }}
    .warning-box {{
      background: rgba(251,191,36,0.1);
      border: 1px solid #fbbf24;
      border-radius: 8px;
      padding: 16px;
      margin: 20px 0;
      color: #fbbf24;
    }}
    .link {{
      color: #00d4aa;
      text-decoration: none;
    }}
    .link:hover {{
      text-decoration: underline;
    }}
    .muted {{
      color: #64748b;
      font-size: 14px;
    }}
    .divider {{
      height: 1px;
      background: linear-gradient(90deg, transparent, #334155, transparent);
      margin: 30px 0;
    }}
    .badge {{
      display: inline-block;
      background: linear-gradient(135deg, #7c3aed 0%, #a855f7 100%);
      color: white;
      padding: 6px 16px;
      border-radius: 20px;
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 1px;
      margin-top: 12px;
    }}
    .footer {{ 
      padding: 30px; 
      text-align: center; 
      font-size: 12px; 
      color: #64748b;
      border-top: 1px solid #334155;
    }}
    .footer a {{ 
      color: #00d4aa; 
      text-decoration: none;
    }}
    .footer a:hover {{
      text-decoration: underline;
    }}
    .social-links {{
      margin: 16px 0;
    }}
    .social-links a {{
      display: inline-block;
      margin: 0 8px;
      color: #64748b;
    }}
  </style>
</head>
<body>
  <div class="wrapper">
    <div class="container">
      <div class="header">
        <div class="logo">⚗️ CATALYZE</div>
        <div class="tagline">Transform ideas into bulletproof prompts</div>
      </div>
      <div class="content">
        {content_html}
      </div>
      <div class="footer">
        © {year} Catalyze • Built for prompt engineers<br>
        <a href="{APP_URL}">catalyze.app</a>{unsubscribe_html}
      </div>
    </div>
  </div>
</body>
</html>"""


class EmailService:
    """Service for sending transactional emails via SendGrid."""
    
    def __init__(self):
        """Initialize email service."""
        self._sendgrid_available = sg is not None and bool(SENDGRID_API_KEY)
    
    @property
    def is_configured(self) -> bool:
        """Check if SendGrid is properly configured."""
        return self._sendgrid_available
    
    def _send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> bool:
        """
        Send an email via SendGrid.
        
        Returns:
            True if sent successfully, False otherwise
        """
        if not self._sendgrid_available:
            logger.warning(f"SendGrid not configured. Would send to {to_email}: {subject}")
            return False
        
        try:
            message = Mail(
                from_email=(SENDGRID_FROM_EMAIL, SENDGRID_FROM_NAME),
                to_emails=to_email,
                subject=subject,
                html_content=html_content
            )
            
            if text_content:
                message.add_content(Content("text/plain", text_content))
            
            response = sg.send(message)
            
            if response.status_code in (200, 201, 202):
                logger.info(f"Email sent to {to_email}: {subject}")
                return True
            else:
                logger.error(f"SendGrid error {response.status_code}: {response.body}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return False
    
    # =========================================================================
    # EMAIL TEMPLATES
    # =========================================================================
    
    def send_verification_email(self, to_email: str, token: str, first_name: str = "") -> bool:
        """Send email verification link."""
        verify_url = f"{APP_URL}?verify={token}"
        greeting = f"Hi {first_name}," if first_name else "Hi there,"
        
        subject = "Verify your Catalyze account ✓"
        
        content_html = f"""
        <h2>{greeting}</h2>
        
        <p>Welcome to Catalyze! You're one click away from transforming your ideas into bulletproof prompts.</p>
        
        <p>Please verify your email address to activate your account:</p>
        
        <p style="text-align: center;">
            <a href="{verify_url}" class="button">Verify Email Address →</a>
        </p>
        
        <p class="muted">Or copy and paste this link into your browser:</p>
        <p><a href="{verify_url}" class="link" style="word-break: break-all;">{verify_url}</a></p>
        
        <div class="divider"></div>
        
        <p class="muted">⏰ This link expires in 24 hours.<br>
        If you didn't create a Catalyze account, you can safely ignore this email.</p>
        """
        
        text_content = f"""
{greeting}

Welcome to Catalyze! You're one click away from transforming your ideas into bulletproof prompts.

Verify your email: {verify_url}

This link expires in 24 hours.

If you didn't create a Catalyze account, you can safely ignore this email.

© {datetime.now().year} Catalyze
        """
        
        html = _get_email_template(subject, content_html)
        return self._send_email(to_email, subject, html, text_content)
    
    def send_password_reset_email(self, to_email: str, token: str, first_name: str = "") -> bool:
        """Send password reset link."""
        reset_url = f"{APP_URL}?reset={token}"
        greeting = f"Hi {first_name}," if first_name else "Hi there,"
        
        subject = "Reset your Catalyze password 🔐"
        
        content_html = f"""
        <h2>{greeting}</h2>
        
        <p>We received a request to reset your password. No worries — it happens to the best of us!</p>
        
        <p>Click the button below to create a new password:</p>
        
        <p style="text-align: center;">
            <a href="{reset_url}" class="button">Reset Password →</a>
        </p>
        
        <p class="muted">Or copy and paste this link into your browser:</p>
        <p><a href="{reset_url}" class="link" style="word-break: break-all;">{reset_url}</a></p>
        
        <div class="warning-box">
            ⚠️ <strong>Security Notice:</strong> This link expires in 1 hour for your protection.
        </div>
        
        <p class="muted">If you didn't request a password reset, you can safely ignore this email. Your password won't be changed.</p>
        """
        
        text_content = f"""
{greeting}

We received a request to reset your password.

Reset your password: {reset_url}

This link expires in 1 hour for security reasons.

If you didn't request a password reset, you can safely ignore this email.

© {datetime.now().year} Catalyze
        """
        
        html = _get_email_template(subject, content_html)
        return self._send_email(to_email, subject, html, text_content)
    
    def send_welcome_email(self, to_email: str, first_name: str = "") -> bool:
        """Send welcome email after verification."""
        greeting = f"Welcome aboard, {first_name}! 🎉" if first_name else "Welcome aboard! 🎉"
        
        subject = "You're in! Welcome to Catalyze ⚗️"
        
        content_html = f"""
        <h2>{greeting}</h2>
        
        <p>Your email is verified and your account is ready. You now have <strong style="color:#00d4aa;">40 free Catalyze Credits</strong> to start transforming ideas into bulletproof prompts.</p>
        
        <div class="feature-box">
            <div class="feature-title">🎯 How Catalyze Works</div>
            <p style="margin:0; color:#94a3b8;">Just describe what you want a prompt to do. Our <strong>Judge-then-Generate</strong> pipeline builds scoring criteria <em>before</em> writing your prompt — delivering production-ready results in ~10 seconds.</p>
        </div>
        
        <div class="feature-box">
            <div class="feature-title">⚡ Your Flow Tier Benefits</div>
            <ul>
                <li><strong>40 Catalyze Credits</strong> per month</li>
                <li>Full 5-stage optimization pipeline</li>
                <li>Success Spec for intent preservation</li>
                <li>Anti-hallucination guardrails</li>
            </ul>
        </div>
        
        <p style="text-align: center;">
            <a href="{APP_URL}" class="button">Start Catalyzing →</a>
        </p>
        
        <div class="divider"></div>
        
        <p class="muted">Questions? Just reply to this email — we read every message.</p>
        """
        
        text_content = f"""
{greeting}

Your email is verified and your account is ready. You now have 40 free Catalyze Credits to start transforming ideas into bulletproof prompts.

How Catalyze Works:
Just describe what you want a prompt to do. Our Judge-then-Generate pipeline builds scoring criteria before writing your prompt — delivering production-ready results in ~10 seconds.

Your Flow Tier Benefits:
- 40 Catalyze Credits per month
- Full 5-stage optimization pipeline
- Success Spec for intent preservation
- Anti-hallucination guardrails

Start Catalyzing: {APP_URL}

Questions? Just reply to this email — we read every message.

© {datetime.now().year} Catalyze
        """
        
        html = _get_email_template(subject, content_html)
        return self._send_email(to_email, subject, html, text_content)
    
    def send_upgrade_confirmation(self, to_email: str, first_name: str = "") -> bool:
        """Send confirmation after upgrading to Synapse tier."""
        greeting = f"Congratulations, {first_name}! 🚀" if first_name else "Congratulations! 🚀"
        
        subject = "Welcome to Catalyze Synapse 🧠"
        
        content_html = f"""
        <h2>{greeting}</h2>
        
        <div class="badge">SYNAPSE TIER</div>
        
        <p style="margin-top: 24px;">Thank you for upgrading to <strong style="color:#a855f7;">Catalyze Synapse</strong>! You've just unlocked the full power of AI-driven prompt engineering.</p>
        
        <div class="feature-box">
            <div class="feature-title" style="color:#a855f7;">🧠 Your Synapse Benefits</div>
            <ul>
                <li><strong>300 Catalyze Credits</strong> per month (7.5× more!)</li>
                <li>Priority processing queue</li>
                <li>Full optimization pipeline</li>
                <li>Success Spec for intent preservation</li>
                <li>Priority email support</li>
            </ul>
        </div>
        
        <p style="text-align: center;">
            <a href="{APP_URL}" class="button button-secondary">Start Catalyzing →</a>
        </p>
        
        <div class="divider"></div>
        
        <p class="muted">Your subscription renews monthly. Manage your subscription anytime from your account settings.</p>
        
        <p class="muted">Need help? Reply to this email and our team will get back to you within 24 hours.</p>
        """
        
        text_content = f"""
{greeting}

Thank you for upgrading to Catalyze Synapse!

Your Synapse Benefits:
- 300 Catalyze Credits per month (7.5× more!)
- Priority processing queue
- Full optimization pipeline
- Success Spec for intent preservation
- Priority email support

Start Catalyzing: {APP_URL}

Your subscription renews monthly. Manage your subscription anytime from your account settings.

© {datetime.now().year} Catalyze
        """
        
        html = _get_email_template(subject, content_html)
        return self._send_email(to_email, subject, html, text_content)
    
    def send_usage_warning(self, to_email: str, first_name: str = "", credits_remaining: int = 0) -> bool:
        """Send warning when user is running low on credits."""
        greeting = f"Hi {first_name}," if first_name else "Hi there,"
        
        subject = f"⚠️ You have {credits_remaining} Catalyze Credits remaining"
        
        content_html = f"""
        <h2>{greeting}</h2>
        
        <p>Heads up! You're running low on Catalyze Credits this month.</p>
        
        <div class="feature-box" style="text-align: center;">
            <div style="font-size: 48px; font-weight: 800; color: #fbbf24;">{credits_remaining}</div>
            <div style="color: #94a3b8; margin-top: 8px;">Credits Remaining</div>
        </div>
        
        <p>Want to keep catalyzing? Upgrade to <strong style="color:#a855f7;">Synapse</strong> for 300 credits/month — that's 7.5× more prompts to perfect.</p>
        
        <p style="text-align: center;">
            <a href="{APP_URL}" class="button button-secondary">Upgrade to Synapse →</a>
        </p>
        
        <div class="divider"></div>
        
        <p class="muted">Your credits reset on the 1st of each month. Current usage resets in the next billing cycle.</p>
        """
        
        text_content = f"""
{greeting}

Heads up! You have {credits_remaining} Catalyze Credits remaining this month.

Want to keep catalyzing? Upgrade to Synapse for 300 credits/month.

Upgrade: {APP_URL}

© {datetime.now().year} Catalyze
        """
        
        html = _get_email_template(subject, content_html)
        return self._send_email(to_email, subject, html, text_content)
    
    def send_custom_email(
        self, 
        to_email: str, 
        subject: str, 
        content_html: str,
        text_content: Optional[str] = None,
        show_unsubscribe: bool = False
    ) -> bool:
        """
        Send a custom branded email.
        
        Args:
            to_email: Recipient email
            subject: Email subject
            content_html: Main content (will be wrapped in branded template)
            text_content: Plain text fallback
            show_unsubscribe: Show unsubscribe link (for marketing)
        
        Returns:
            True if sent successfully
        """
        html = _get_email_template(subject, content_html, show_unsubscribe)
        return self._send_email(to_email, subject, html, text_content)


# Global service instance
_email_service = None


def get_email_service() -> EmailService:
    """Get or create the global email service instance."""
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service
