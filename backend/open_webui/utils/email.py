"""
Email utilities for Autotech AI.

Uses SMTP to send emails via the aurora-sentient mail server on poweredge2.
"""

import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

log = logging.getLogger(__name__)

# Email configuration from environment
SMTP_HOST = os.environ.get("SMTP_HOST", "poweredge2")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_FROM_EMAIL = os.environ.get("SMTP_FROM_EMAIL", "noreply@aurora-sentient.net")
SMTP_FROM_NAME = os.environ.get("SMTP_FROM_NAME", "Autotech AI")
SMTP_USE_TLS = os.environ.get("SMTP_USE_TLS", "true").lower() == "true"

# Feature flag to enable/disable email sending
EMAIL_ENABLED = os.environ.get("EMAIL_ENABLED", "false").lower() == "true"


def send_email(
    to_email: str,
    subject: str,
    html_body: str,
    text_body: Optional[str] = None,
) -> bool:
    """Send an email via SMTP.
    
    Returns True if successful, False otherwise.
    """
    if not EMAIL_ENABLED:
        log.info(f"Email disabled - would have sent to {to_email}: {subject}")
        return True
    
    if not SMTP_HOST or not SMTP_FROM_EMAIL:
        log.warning("SMTP not configured, skipping email")
        return False
    
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_FROM_EMAIL}>"
        msg["To"] = to_email
        
        # Add text version (for email clients that don't support HTML)
        if text_body:
            msg.attach(MIMEText(text_body, "plain"))
        
        # Add HTML version
        msg.attach(MIMEText(html_body, "html"))
        
        # Connect and send
        if SMTP_USE_TLS:
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
            server.starttls()
        else:
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
        
        if SMTP_USER and SMTP_PASSWORD:
            server.login(SMTP_USER, SMTP_PASSWORD)
        
        server.sendmail(SMTP_FROM_EMAIL, to_email, msg.as_string())
        server.quit()
        
        log.info(f"Email sent to {to_email}: {subject}")
        return True
        
    except Exception as e:
        log.exception(f"Failed to send email to {to_email}: {e}")
        return False


def send_welcome_email(user_name: str, user_email: str) -> bool:
    """Send welcome email when user is approved (pending → user).
    
    Returns True if successful, False otherwise.
    """
    subject = "Welcome to Autotech AI! Your Account is Ready"
    
    html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            line-height: 1.6;
            color: #e5e7eb;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
            background: #0a0f1a;
        }}
        .email-container {{
            background: #111827;
            border-radius: 16px;
            overflow: hidden;
            box-shadow: 0 4px 30px rgba(0,0,0,0.5);
            border: 1px solid #1f2937;
        }}
        .header {{
            background: linear-gradient(180deg, #0a0f1a 0%, #111827 100%);
            color: white;
            padding: 40px 30px;
            text-align: center;
            border-bottom: 1px solid #1f2937;
        }}
        .logo-text {{
            font-size: 24px;
            font-weight: 600;
            margin-bottom: 25px;
        }}
        .header h1 {{
            margin: 0;
            font-size: 32px;
            font-weight: 700;
            color: white;
        }}
        .header h1 span {{
            color: #14b8a6;
        }}
        .header .tagline {{
            margin: 15px 0 0 0;
            color: #9ca3af;
            font-size: 16px;
        }}
        .content {{
            padding: 40px 30px;
        }}
        .greeting {{
            font-size: 18px;
            color: #f1f5f9;
        }}
        .highlight-box {{
            background: linear-gradient(135deg, rgba(20, 184, 166, 0.15) 0%, rgba(20, 184, 166, 0.05) 100%);
            border: 1px solid rgba(20, 184, 166, 0.3);
            padding: 25px;
            border-radius: 12px;
            margin: 25px 0;
        }}
        .highlight-box p {{
            margin: 0;
            font-size: 16px;
            color: #ccfbf1;
        }}
        .cta-button {{
            display: inline-block;
            background: #14b8a6;
            color: white !important;
            padding: 16px 36px;
            text-decoration: none;
            border-radius: 8px;
            font-weight: 600;
            font-size: 16px;
            margin: 15px 0;
        }}
        .value-badge {{
            background: #0a0f1a;
            border: 1px solid #1f2937;
            border-radius: 12px;
            padding: 30px;
            margin: 35px 0;
            text-align: center;
        }}
        .value-badge h2 {{
            color: #fbbf24;
            font-size: 14px;
            text-transform: uppercase;
            letter-spacing: 2px;
            margin: 0 0 15px 0;
        }}
        .value-badge p {{
            color: #9ca3af;
            font-size: 15px;
            margin: 0;
            line-height: 1.7;
        }}
        .value-badge .highlight {{
            color: #14b8a6;
            font-weight: 600;
        }}
        .features {{
            background: #0a0f1a;
            padding: 30px;
            border-radius: 12px;
            margin: 30px 0;
            border: 1px solid #1f2937;
        }}
        .features h3 {{
            margin: 0 0 25px 0;
            color: #f1f5f9;
            font-size: 20px;
            text-align: center;
        }}
        .feature {{
            padding: 18px 0;
            border-bottom: 1px solid #1f2937;
        }}
        .feature:last-child {{
            border-bottom: none;
            padding-bottom: 0;
        }}
        .feature strong {{
            display: block;
            color: #f1f5f9;
            margin-bottom: 6px;
            font-size: 16px;
        }}
        .feature span {{
            color: #9ca3af;
            font-size: 14px;
            line-height: 1.5;
        }}
        .steps {{
            margin: 35px 0;
        }}
        .steps h3 {{
            color: #f1f5f9;
            margin-bottom: 25px;
            font-size: 18px;
        }}
        .step {{
            margin-bottom: 20px;
            color: #d1d5db;
        }}
        .step a {{
            color: #14b8a6;
        }}
        .signature {{
            margin-top: 35px;
            padding-top: 30px;
            border-top: 1px solid #1f2937;
            color: #9ca3af;
        }}
        .signature p {{
            margin: 5px 0;
        }}
        .signature strong {{
            color: #f1f5f9;
        }}
        .footer {{
            background: #0a0f1a;
            color: #6b7280;
            text-align: center;
            padding: 25px;
            font-size: 13px;
            border-top: 1px solid #1f2937;
        }}
        .footer-brand {{
            color: #9ca3af;
            font-weight: 600;
            letter-spacing: 1px;
        }}
    </style>
</head>
<body>
    <div class="email-container">
        <div class="header">
            <div class="logo-text">
                <span style="color: #14b8a6;">Autotech</span> <span style="color: #14b8a6;">AI</span>
            </div>
            <h1>AI-Powered<br><span>Expert Diagnosis</span></h1>
            <p class="tagline">Like having a 30-year master tech in your pocket</p>
        </div>
        <div class="content">
            <p class="greeting">Hi <strong>{user_name}</strong>,</p>
            
            <div class="highlight-box">
                <p>&#10024; <strong>Your account is approved!</strong> You now have access to the most advanced AI diagnostic platform built for professional technicians.</p>
            </div>
            
            <div class="value-badge">
                <h2>&#9889; Cut Your Diagnostic Time in Half</h2>
                <p>Our AI thinks through problems <span class="highlight">the way a master tech does</span> — analyzing patterns, ruling out causes, and pointing you to the fix. Diagnose faster, fix it right the first time, and move on to the next job.</p>
            </div>
            
            <div style="text-align: center;">
                <a href="https://automotive.aurora-sentient.net" class="cta-button">
                    &#9889; Start Diagnosis
                </a>
            </div>
            
            <div class="features">
                <h3>What You Get</h3>
                <div class="feature">
                    <strong>&#129504; Expert-Level Guidance</strong>
                    <span>Describe symptoms in plain English. Get the diagnostic approach a 30-year master tech would use.</span>
                </div>
                <div class="feature">
                    <strong>&#127919; Vehicle-Specific Answers</strong>
                    <span>Every response is tailored to the exact year, make, model, and engine you're working on.</span>
                </div>
                <div class="feature">
                    <strong>&#9889; Instant Results</strong>
                    <span>No more searching through forums or manuals. Get expert guidance in seconds.</span>
                </div>
            </div>
            
            <div class="steps">
                <h3>Get Started</h3>
                <div class="step"><strong>1.</strong> <strong>Log in</strong> at <a href="https://automotive.aurora-sentient.net">automotive.aurora-sentient.net</a></div>
                <div class="step"><strong>2.</strong> <strong>Choose your plan</strong> to activate your diagnostic tokens</div>
                <div class="step"><strong>3.</strong> <strong>Ask anything</strong> — "2019 F-150 3.5L misfires when cold"</div>
            </div>
            
            <div class="signature">
                <p>Welcome aboard,</p>
                <p><strong>The Autotech AI Team</strong></p>
            </div>
        </div>
        <div class="footer">
            <p class="footer-brand">AUTOTECH AI</p>
            <p style="margin: 8px 0;">Trusted by professional technicians nationwide</p>
        </div>
    </div>
</body>
</html>
"""

    text_body = f"""
Welcome to Autotech AI!

Hi {user_name},

Your account is approved! You now have access to the most advanced AI diagnostic platform built for professional technicians.

CUT YOUR DIAGNOSTIC TIME IN HALF
Our AI thinks through problems the way a master tech does — analyzing patterns, ruling out causes, and pointing you to the fix. Diagnose faster, fix it right the first time, and move on to the next job.

WHAT YOU GET:
- Expert-Level Guidance: Describe symptoms in plain English. Get the diagnostic approach a 30-year master tech would use.
- Vehicle-Specific Answers: Every response is tailored to the exact year, make, model, and engine you're working on.
- Instant Results: No more searching through forums or manuals. Get expert guidance in seconds.

GET STARTED:
1. Log in at automotive.aurora-sentient.net
2. Choose your plan to activate your diagnostic tokens
3. Ask anything — "2019 F-150 3.5L misfires when cold"

Welcome aboard,
The Autotech AI Team
"""

    return send_email(user_email, subject, html_body, text_body)
