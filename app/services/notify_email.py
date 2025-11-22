# app/services/notify_email.py

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

import resend

from app.core.config import settings

FROM_NAME = settings.email_from_name
FROM_ADDR = settings.email_from_address

EMAIL_REDIRECT_TO = settings.email_redirect_to
EMAIL_DOMAIN_VERIFIED = settings.email_domain_verified
EMAIL_PROVIDER = settings.email_provider.lower()

SMTP_HOST = settings.smtp_host
SMTP_PORT = settings.smtp_port
SMTP_USERNAME = settings.smtp_username
SMTP_PASSWORD = settings.smtp_password
SMTP_USE_SSL = settings.smtp_use_ssl
RESEND_API_KEY = settings.resend_api_key

# ===================================================================
# BASE TEMPLATE - official city look, compact spacing
# ===================================================================

TPL_BASE = """
<table width="100%%" cellpadding="0" cellspacing="0" style="background:#eef2f7;padding:24px;">
  <tr><td align="center">

    <table width="600" cellpadding="0" cellspacing="0"
           style="background:#ffffff;border-radius:12px;
                  padding:24px;font-family:Arial,Helvetica,sans-serif;
                  color:#111827;border:1px solid #e5e7eb;">
      <!-- HEADER -->
      <tr>
        <td align="center" style="padding-bottom:16px;">
          <div style="width:60px;height:60px;border-radius:50%%;
                      background:#1e40af;color:#ffffff;font-size:24px;
                      display:flex;align-items:center;justify-content:center;
                      font-weight:700;letter-spacing:1px;">
            IC
          </div>
          <div style="margin-top:8px;font-size:20px;font-weight:700;">
            Improve My City
          </div>
          <div style="margin-top:2px;font-size:12px;color:#6b7280;">
            Working together for a better community
          </div>
        </td>
      </tr>

      <!-- MAIN CONTENT -->
      <tr>
        <td style="font-size:14px;line-height:1.6;">
          %s
        </td>
      </tr>

      <!-- FOOTER -->
      <tr>
        <td style="padding-top:16px;font-size:11px;color:#6b7280;line-height:1.5;border-top:1px solid #e5e7eb;margin-top:16px;">
          <div>
            This is an automated message from <strong>Improve My City</strong>.
            If you did not request this, you can safely ignore this email.
          </div>
          {CONTACT_SECTION}
          <div style="margin-top:4px;">
            © {YEAR} Improve My City — All rights reserved.
          </div>
        </td>
      </tr>

    </table>
  </td></tr>
</table>
"""

def _get_template_base():
    """Get the email template with proper replacements."""
    contact_section = ""
    if FROM_ADDR:
        contact_section = f"""
          <div style="margin-top:4px;">
            For help, contact us at
            <a href="mailto:{FROM_ADDR}" style="color:#1e3a8a;text-decoration:none;">
              {FROM_ADDR}
            </a>.
          </div>
        """
    return TPL_BASE.replace("{CONTACT_SECTION}", contact_section).replace("{YEAR}", "2025")


# ===================================================================
# Helper: send email via SMTP
# ===================================================================

def _send_email_via_smtp(to_email: str, subject: str, html_content: str):
    """Send an email using SMTP with proper SSL/TLS handling."""
    if not SMTP_HOST or not SMTP_USERNAME or not SMTP_PASSWORD or not FROM_ADDR:
        return

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{FROM_NAME} <{FROM_ADDR}>" if FROM_NAME else FROM_ADDR
        msg["To"] = to_email
        
        html_part = MIMEText(html_content, "html")
        msg.attach(html_part)

        if SMTP_USE_SSL:
            server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=15)
        else:
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15)
            server.starttls()

        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
    except Exception as e:
        print(f"Failed to send email via SMTP: {e}")


# ===================================================================
# Helper: send email via Resend API
# ===================================================================

def _send_email_via_resend(to_email: str, subject: str, html_content: str):
    """Send an email using Resend API."""
    if not RESEND_API_KEY or not FROM_ADDR:
        return

    try:
        resend.api_key = RESEND_API_KEY
        params = {
            "from": f"{FROM_NAME} <{FROM_ADDR}>" if FROM_NAME else FROM_ADDR,
            "to": [to_email],
            "subject": subject,
            "html": html_content,
        }
        resend.Emails.send(params)
    except Exception as e:
        import logging
        logging.error(f"Failed to send email via Resend: {e}", exc_info=True)


# ===================================================================
# Main email sending function (routes to appropriate provider)
# ===================================================================

def _send_email(to_email: str, subject: str, html_content: str):
    """Send an email using the configured provider (SMTP or Resend)."""
    if EMAIL_PROVIDER == "resend":
        _send_email_via_resend(to_email, subject, html_content)
    else:
        _send_email_via_smtp(to_email, subject, html_content)


# ===================================================================
# Helper: redirection note for non-verified domains
# ===================================================================

def _get_recipient_and_note(original_email: str) -> tuple[str, str]:
    """
    If EMAIL_DOMAIN_VERIFIED is False, send all mail to EMAIL_REDIRECT_TO
    but clearly mention original recipient in the email body.
    """
    if EMAIL_DOMAIN_VERIFIED:
        return original_email, ""

    note = f"""
    <div style="background:#fef2f2;color:#b91c1c;
                padding:8px 10px;border-radius:6px;
                font-size:11px;margin-bottom:12px;
                border:1px solid #fecaca;">
      <strong>Test mode:</strong> This email was redirected to
      <strong>{EMAIL_REDIRECT_TO}</strong> for testing.<br/>
      Original recipient: {original_email}
    </div>
    """
    return EMAIL_REDIRECT_TO, note


# ===================================================================
# Helper: build URL (with sensible fallback)
# ===================================================================

def _build_url(path: str) -> str:
    """
    Build a full URL using frontend_base_url when available.
    If not configured, fall back to a site-relative path (still shown
    as a copy-paste URL in the email).
    """
    base = (settings.frontend_base_url or "").strip().rstrip("/")
    path = path.lstrip("/")

    if base:
        if not base.startswith("http://") and not base.startswith("https://"):
            base = f"https://{base}"
        return f"{base}/{path}" if path else base

    # Fallback: relative path, still visible + copy-pastable
    return f"/{path}" if path else "/"


# ===================================================================
# Helper: button + full URL block
# ===================================================================

def _format_link_section(link: str, link_text: str = "Open link") -> str:
    """
    Show a primary button AND the full URL for copy-paste.
    This should always render something meaningful, even if link is a
    relative path (when base URL is not configured).
    """
    if not link:
        # extreme case, should not happen with _build_url fallback
        return """
        <p style="margin-top:12px;font-size:12px;color:#b91c1c;">
          We were unable to generate a link. Please contact support or try again.
        </p>
        """

    return f"""
    <div style="margin:12px 0 8px 0;text-align:left;">
      <a href="{link}"
         style="display:inline-block;padding:10px 20px;background:#1d4ed8;
                color:#ffffff;border-radius:6px;font-weight:600;
                text-decoration:none;font-size:14px;">
        {link_text}
      </a>
    </div>
    <div style="margin:6px 0 0 0;font-size:11px;color:#374151;
                background:#f3f4f6;padding:8px 10px;border-radius:4px;
                word-break:break-all;font-family:monospace;">
      <strong>Or copy and paste this link:</strong><br/>{link}
    </div>
    """


# ===================================================================
# 1) Email verification
# ===================================================================

def send_email_verification(to_email: str, token: str, code: Optional[str] = None):
    actual_recipient, redirect_note = _get_recipient_and_note(to_email)
    link = _build_url(f"verify-email?token={token}")

    if code:
        html_content = f"""
        {redirect_note}
        <p>Hello,</p>
        <p>Thank you for creating an account with <strong>Improve My City</strong>.</p>
        <p>Please verify your email address using the code below:</p>
        <p style="margin:6px 0 10px 0;">
          <span style="display:inline-block;font-size:24px;font-weight:800;
                       color:#1d4ed8;letter-spacing:4px;">
            {code}
          </span>
        </p>
        <p>If you prefer, you can also verify your email using this link:</p>
        {_format_link_section(link, "Verify email")}
        """
    else:
        html_content = f"""
        {redirect_note}
        <p>Hello,</p>
        <p>Thank you for creating an account with <strong>Improve My City</strong>.</p>
        <p>Please verify your email address by using the link below:</p>
        {_format_link_section(link, "Verify email")}
        """

    html = _get_template_base() % html_content
    _send_email(actual_recipient, "Verify your email address", html)


# ===================================================================
# 2) Reset password
# ===================================================================

def send_reset_password(to_email: str, token: str):
    actual_recipient, redirect_note = _get_recipient_and_note(to_email)
    link = _build_url(f"reset-password?token={token}")

    html_content = f"""
    {redirect_note}
    <p>Hello,</p>
    <p>We received a request to reset the password for your
       <strong>Improve My City</strong> account.</p>
    <p>To create a new password, please use the link below:</p>
    {_format_link_section(link, "Reset password")}
    <p style="margin-top:8px;font-size:12px;color:#6b7280;">
      For your security, this link is valid for <strong>60 minutes</strong>.
      If you did not request a password reset, you can ignore this email.
    </p>
    """

    html = _get_template_base() % html_content
    _send_email(actual_recipient, "Reset your password", html)


# ===================================================================
# 3) Status update on an issue
# ===================================================================

def send_status_update(to_email: str, issue_id: int, status: str):
    actual_recipient, redirect_note = _get_recipient_and_note(to_email)

    readable_status = status.replace("_", " ").title()
    issue_link = _build_url(f"issues/{issue_id}")

    html_content = f"""
    {redirect_note}
    <p>Hello,</p>
    <p>This is an update on your reported issue
       <strong>#{issue_id}</strong> in <strong>Improve My City</strong>.</p>
    <p>The current status is now:</p>
    <p style="margin:4px 0 10px 0;">
      <span style="display:inline-block;font-size:16px;font-weight:700;color:#1d4ed8;">
        {readable_status}
      </span>
    </p>
    {_format_link_section(issue_link, "View issue details")}
    <p style="margin-top:8px;font-size:12px;color:#6b7280;">
      Thank you for helping us keep the city informed and responsive.
    </p>
    """

    html = _get_template_base() % html_content
    _send_email(actual_recipient, f"Issue #{issue_id} status update", html)


# ===================================================================
# 4) Report confirmation
# ===================================================================

def send_report_confirmation(to_email: str, issue_id: int, title: str):
    """Send confirmation email when a report is submitted."""
    actual_recipient, redirect_note = _get_recipient_and_note(to_email)
    link = _build_url(f"issues/{issue_id}")

    html_content = f"""
    {redirect_note}
    <p>Hello,</p>
    <p>Thank you for submitting a report to <strong>Improve My City</strong>.</p>
    <p style="margin:6px 0;">
      <strong>Issue number:</strong> #{issue_id}<br/>
      <strong>Title:</strong> {title}
    </p>
    <p>Our team has received your report and will keep you updated
       as the status changes.</p>
    {_format_link_section(link, "View reported issue")}
    """

    html = _get_template_base() % html_content
    _send_email(actual_recipient, f"Report submitted – Ticket #{issue_id}", html)


# ===================================================================
# 5) Comment notification
# ===================================================================

def send_comment_notification(to_email: str, issue_id: int, issue_title: str, comment_author: str, comment_body: str):
    """Send notification email when a comment is posted on an issue."""
    actual_recipient, redirect_note = _get_recipient_and_note(to_email)
    link = _build_url(f"issues/{issue_id}")

    html_content = f"""
    {redirect_note}
    <p>Hello,</p>
    <p>A new comment has been added to issue <strong>#{issue_id}</strong> in <strong>Improve My City</strong>.</p>
    <p style="margin:6px 0;">
      <strong>Issue:</strong> {issue_title}<br/>
      <strong>Comment by:</strong> {comment_author}<br/>
      <strong>Comment:</strong> {comment_body[:200]}{'...' if len(comment_body) > 200 else ''}
    </p>
    {_format_link_section(link, "View issue and comment")}
    <p style="margin-top:8px;font-size:12px;color:#6b7280;">
      You are receiving this notification because you are involved with this issue.
    </p>
    """

    html = _get_template_base() % html_content
    _send_email(actual_recipient, f"New comment on Issue #{issue_id}", html)


# ===================================================================
# 6) Assignment notification
# ===================================================================

def send_assignment_notification(to_email: str, issue_id: int, issue_title: str, assigned_by: str):
    """Send notification email when an issue is assigned to staff."""
    actual_recipient, redirect_note = _get_recipient_and_note(to_email)
    link = _build_url(f"issues/{issue_id}")

    html_content = f"""
    {redirect_note}
    <p>Hello,</p>
    <p>You have been assigned to issue <strong>#{issue_id}</strong> in <strong>Improve My City</strong>.</p>
    <p style="margin:6px 0;">
      <strong>Issue:</strong> {issue_title}<br/>
      <strong>Assigned by:</strong> {assigned_by}
    </p>
    <p>Please review the issue and take appropriate action.</p>
    {_format_link_section(link, "View assigned issue")}
    <p style="margin-top:8px;font-size:12px;color:#6b7280;">
      You can update the status and add comments to keep the reporter informed.
    </p>
    """

    html = _get_template_base() % html_content
    _send_email(actual_recipient, f"Issue #{issue_id} assigned to you", html)