#app\services\notify_email.py
import os
import resend

resend.api_key = os.getenv("RESEND_API_KEY")

FROM_NAME = os.getenv("EMAIL_FROM_NAME", "Improve My City")
FROM_ADDR = os.getenv("EMAIL_FROM_ADDRESS", "noreply@example.com")

EMAIL_REDIRECT_TO = os.getenv("EMAIL_REDIRECT_TO", "vs.tech094@gmail.com")
EMAIL_DOMAIN_VERIFIED = os.getenv("EMAIL_DOMAIN_VERIFIED", "false").lower() == "true"

TPL_BASE = """<table width="100%%" cellpadding="0" cellspacing="0" style="background:#f5f7fb;padding:24px;">
<tr><td align="center">
  <table width="560" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;padding:24px;font-family:Arial,sans-serif;color:#111827;">
    <tr><td style="font-size:18px;font-weight:700;color:#1f2937;">Improve My City</td></tr>
    <tr><td style="padding-top:8px;">%s</td></tr>
    <tr><td style="font-size:12px;color:#6b7280;padding-top:16px;">This is an automated message. If you didn't request this, you can ignore it.</td></tr>
  </table>
</td></tr></table>"""

def _get_recipient_and_note(original_email: str) -> tuple[str, str]:
    """Get the actual recipient and a note about redirection if needed."""
    if EMAIL_DOMAIN_VERIFIED:
        return original_email, ""
    
    note = f"<p style='color:#dc2626;font-size:12px;padding:8px;background:#fef2f2;border-radius:4px;margin-bottom:16px;'><strong>Note:</strong> This email was redirected to {EMAIL_REDIRECT_TO} for testing. Original recipient: {original_email}</p>"
    return EMAIL_REDIRECT_TO, note

def send_email_verification(to_email: str, token: str):
    if not resend.api_key:
        return
    actual_recipient, redirect_note = _get_recipient_and_note(to_email)
    link = f"{os.getenv('FRONTEND_BASE_URL','')}/verify-email?token={token}"
    html_content = f"<p>Please verify your email by clicking <a href='{link}'>this link</a> or use the 6-digit code sent to you.</p>"
    html = TPL_BASE % (redirect_note + html_content)
    resend.Emails.send({"from": f"{FROM_NAME} <{FROM_ADDR}>","to":[actual_recipient],"subject":"Verify your email","html": html})

def send_reset_password(to_email: str, token: str):
    if not resend.api_key:
        return
    actual_recipient, redirect_note = _get_recipient_and_note(to_email)
    link = f"{os.getenv('FRONTEND_BASE_URL','')}/reset-password?token={token}"
    html_content = f"<p>Reset your password by clicking <a href='{link}'>this link</a>. The link expires in 60 minutes.</p>"
    html = TPL_BASE % (redirect_note + html_content)
    resend.Emails.send({"from": f"{FROM_NAME} <{FROM_ADDR}>","to":[actual_recipient],"subject":"Reset your password","html": html})

def send_status_update(to_email: str, issue_id: int, status: str):
    if not resend.api_key:
        return
    actual_recipient, redirect_note = _get_recipient_and_note(to_email)
    html_content = f"<p>Your issue <b>#{issue_id}</b> status is now <b>{status.replace('_',' ')}</b>.</p>"
    html = TPL_BASE % (redirect_note + html_content)
    resend.Emails.send({"from": f"{FROM_NAME} <{FROM_ADDR}>","to":[actual_recipient],"subject":f"Issue #{issue_id} status update","html": html})

def send_report_confirmation(to_email: str, issue_id: int, title: str):
    """Send confirmation email when a report is submitted."""
    if not resend.api_key:
        return
    actual_recipient, redirect_note = _get_recipient_and_note(to_email)
    link = f"{os.getenv('FRONTEND_BASE_URL','')}/issues/{issue_id}"
    html_content = (
        f"<p>Thank you for reporting an issue!</p>"
        f"<p><b>Ticket #:</b> {issue_id}</p>"
        f"<p><b>Title:</b> {title}</p>"
        f"<p>We've received your report and will keep you updated on its progress. "
        f"You can view it <a href='{link}'>here</a>.</p>"
    )
    html = TPL_BASE % (redirect_note + html_content)
    resend.Emails.send({
        "from": f"{FROM_NAME} <{FROM_ADDR}>",
        "to": [actual_recipient],
        "subject": f"Report submitted - Ticket #{issue_id}",
        "html": html
    })