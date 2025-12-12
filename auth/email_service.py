"""
Email service for Catalyze using SendGrid.
Handles transactional emails: verification, password reset, welcome, etc.
"""

import os
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
        
        subject = "Verify your Catalyze account"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 40px 20px; }}
                .header {{ text-align: center; margin-bottom: 30px; }}
                .logo {{ font-size: 28px; font-weight: bold; color: #00D4AA; }}
                .button {{ display: inline-block; background: linear-gradient(135deg, #00D4AA 0%, #00B894 100%); color: white; padding: 14px 32px; text-decoration: none; border-radius: 8px; font-weight: 600; margin: 20px 0; }}
                .button:hover {{ opacity: 0.9; }}
                .footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #eee; font-size: 12px; color: #666; text-align: center; }}
                .link {{ color: #00D4AA; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="logo">⚗️ CATALYZE</div>
                </div>
                
                <p>{greeting}</p>
                
                <p>Welcome to Catalyze! Please verify your email address to activate your account and start transforming your ideas into bulletproof prompts.</p>
                
                <p style="text-align: center;">
                    <a href="{verify_url}" class="button">Verify Email Address</a>
                </p>
                
                <p>Or copy and paste this link into your browser:</p>
                <p><a href="{verify_url}" class="link">{verify_url}</a></p>
                
                <p>This link expires in 24 hours.</p>
                
                <p>If you didn't create a Catalyze account, you can safely ignore this email.</p>
                
                <div class="footer">
                    <p>© 2025 Catalyze. Transform ideas into bulletproof prompts.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        text_content = f"""
{greeting}

Welcome to Catalyze! Please verify your email address to activate your account.

Verify your email: {verify_url}

This link expires in 24 hours.

If you didn't create a Catalyze account, you can safely ignore this email.

© 2025 Catalyze
        """
        
        return self._send_email(to_email, subject, html_content, text_content)
    
    def send_password_reset_email(self, to_email: str, token: str, first_name: str = "") -> bool:
        """Send password reset link."""
        reset_url = f"{APP_URL}?reset={token}"
        greeting = f"Hi {first_name}," if first_name else "Hi there,"
        
        subject = "Reset your Catalyze password"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 40px 20px; }}
                .header {{ text-align: center; margin-bottom: 30px; }}
                .logo {{ font-size: 28px; font-weight: bold; color: #00D4AA; }}
                .button {{ display: inline-block; background: linear-gradient(135deg, #00D4AA 0%, #00B894 100%); color: white; padding: 14px 32px; text-decoration: none; border-radius: 8px; font-weight: 600; margin: 20px 0; }}
                .footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #eee; font-size: 12px; color: #666; text-align: center; }}
                .warning {{ background: #fff3cd; border: 1px solid #ffc107; border-radius: 8px; padding: 12px; margin: 20px 0; }}
                .link {{ color: #00D4AA; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="logo">⚗️ CATALYZE</div>
                </div>
                
                <p>{greeting}</p>
                
                <p>We received a request to reset your password. Click the button below to create a new password:</p>
                
                <p style="text-align: center;">
                    <a href="{reset_url}" class="button">Reset Password</a>
                </p>
                
                <p>Or copy and paste this link into your browser:</p>
                <p><a href="{reset_url}" class="link">{reset_url}</a></p>
                
                <div class="warning">
                    ⚠️ This link expires in 1 hour for security reasons.
                </div>
                
                <p>If you didn't request a password reset, you can safely ignore this email. Your password won't be changed.</p>
                
                <div class="footer">
                    <p>© 2025 Catalyze. Transform ideas into bulletproof prompts.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        text_content = f"""
{greeting}

We received a request to reset your password.

Reset your password: {reset_url}

This link expires in 1 hour for security reasons.

If you didn't request a password reset, you can safely ignore this email.

© 2025 Catalyze
        """
        
        return self._send_email(to_email, subject, html_content, text_content)
    
    def send_welcome_email(self, to_email: str, first_name: str = "") -> bool:
        """Send welcome email after verification."""
        greeting = f"Hi {first_name}!" if first_name else "Welcome!"
        
        subject = "Welcome to Catalyze! 🎉"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 40px 20px; }}
                .header {{ text-align: center; margin-bottom: 30px; }}
                .logo {{ font-size: 28px; font-weight: bold; color: #00D4AA; }}
                .button {{ display: inline-block; background: linear-gradient(135deg, #00D4AA 0%, #00B894 100%); color: white; padding: 14px 32px; text-decoration: none; border-radius: 8px; font-weight: 600; margin: 20px 0; }}
                .feature {{ background: #f8f9fa; border-radius: 8px; padding: 16px; margin: 12px 0; }}
                .feature-title {{ font-weight: 600; color: #00D4AA; }}
                .footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #eee; font-size: 12px; color: #666; text-align: center; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="logo">⚗️ CATALYZE</div>
                </div>
                
                <h2>{greeting}</h2>
                
                <p>Your email is verified and your account is ready. You now have <strong>40 free Catalyze Credits</strong> to start transforming ideas into bulletproof prompts.</p>
                
                <div class="feature">
                    <div class="feature-title">🎯 How Catalyze Works</div>
                    <p>Just describe what you want a prompt to do. Our Judge-then-Generate pipeline builds scoring criteria <em>before</em> writing your prompt — delivering production-ready results in ~10 seconds.</p>
                </div>
                
                <div class="feature">
                    <div class="feature-title">⚡ Your Flow Tier Benefits</div>
                    <ul>
                        <li>40 Catalyze Credits per month</li>
                        <li>Full 5-stage optimization pipeline</li>
                        <li>Success Spec for intent preservation</li>
                    </ul>
                </div>
                
                <p style="text-align: center;">
                    <a href="{APP_URL}" class="button">Start Catalyzing →</a>
                </p>
                
                <p>Questions? Just reply to this email — we read every message.</p>
                
                <div class="footer">
                    <p>© 2025 Catalyze. Transform ideas into bulletproof prompts.</p>
                </div>
            </div>
        </body>
        </html>
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

Start Catalyzing: {APP_URL}

Questions? Just reply to this email — we read every message.

© 2025 Catalyze
        """
        
        return self._send_email(to_email, subject, html_content, text_content)
    
    def send_upgrade_confirmation(self, to_email: str, first_name: str = "") -> bool:
        """Send confirmation after upgrading to Synapse tier."""
        greeting = f"Hi {first_name}!" if first_name else "Hello!"
        
        subject = "Welcome to Catalyze Synapse! 🚀"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 40px 20px; }}
                .header {{ text-align: center; margin-bottom: 30px; }}
                .logo {{ font-size: 28px; font-weight: bold; color: #00D4AA; }}
                .badge {{ display: inline-block; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 6px 16px; border-radius: 20px; font-size: 14px; font-weight: 600; }}
                .button {{ display: inline-block; background: linear-gradient(135deg, #00D4AA 0%, #00B894 100%); color: white; padding: 14px 32px; text-decoration: none; border-radius: 8px; font-weight: 600; margin: 20px 0; }}
                .feature {{ background: #f8f9fa; border-radius: 8px; padding: 16px; margin: 12px 0; }}
                .feature-title {{ font-weight: 600; color: #764ba2; }}
                .footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #eee; font-size: 12px; color: #666; text-align: center; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="logo">⚗️ CATALYZE</div>
                    <div class="badge">SYNAPSE TIER</div>
                </div>
                
                <h2>{greeting}</h2>
                
                <p>Thank you for upgrading to <strong>Catalyze Synapse</strong>! Your account has been upgraded and you now have access to 300 Catalyze Credits per month.</p>
                
                <div class="feature">
                    <div class="feature-title">🧠 Your Synapse Benefits</div>
                    <ul>
                        <li><strong>300 Catalyze Credits</strong> per month</li>
                        <li>Priority processing</li>
                        <li>Full optimization pipeline</li>
                        <li>Success Spec for intent preservation</li>
                        <li>Email support</li>
                    </ul>
                </div>
                
                <p style="text-align: center;">
                    <a href="{APP_URL}" class="button">Start Catalyzing →</a>
                </p>
                
                <p>Your subscription renews monthly. You can manage your subscription anytime from your account settings.</p>
                
                <div class="footer">
                    <p>© 2025 Catalyze. Transform ideas into bulletproof prompts.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return self._send_email(to_email, subject, html_content)


# Global service instance
_email_service = None


def get_email_service() -> EmailService:
    """Get or create the global email service instance."""
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service
