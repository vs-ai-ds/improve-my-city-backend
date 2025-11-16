#app\services\notify_email.py
import os
import resend  

resend.api_key = os.getenv("RESEND_API_KEY")

FROM_NAME = os.getenv("EMAIL_FROM_NAME", "Improve My City")
FROM_ADDR = os.getenv("EMAIL_FROM_ADDRESS", "noreply@example.com")

TPL_BASE = """<table width="100%%" cellpadding="0" cellspacing="0" style="background:#f5f7fb;padding:24px;">
<tr><td align="center">
  <table width="560" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;padding:24px;font-family:Arial,sans-serif;color:#111827;">
    <tr><td style="font-size:18px;font-weight:700;color:#1f2937;">Improve My City</td></tr>
    <tr><td style="padding-top:8px;">%s</td></tr>
    <tr><td style="font-size:12px;color:#6b7280;padding-top:16px;">This is an automated message. If you didn’t request this, you can ignore it.</td></tr>
  </table>
</td></tr></table>"""

def send_email_verification(to_email: str, token: str):
    if not resend.api_key: return
    link = f"{os.getenv('FRONTEND_BASE_URL','')}/verify-email?token={token}"
    html = TPL_BASE % (f"<p>Please verify your email by clicking <a href='{link}'>this link</a> or use the 6-digit code sent to you.</p>")
    resend.Emails.send({"from": f"{FROM_NAME} <{FROM_ADDR}>","to":[to_email],"subject":"Verify your email","html": html})

def send_reset_password(to_email: str, token: str):
    if not resend.api_key: return
    link = f"{os.getenv('FRONTEND_BASE_URL','')}/reset-password?token={token}"
    html = TPL_BASE % (f"<p>Reset your password by clicking <a href='{link}'>this link</a>. The link expires in 60 minutes.</p>")
    resend.Emails.send({"from": f"{FROM_NAME} <{FROM_ADDR}>","to":[to_email],"subject":"Reset your password","html": html})

def send_status_update(to_email: str, issue_id: int, status: str):
    if not resend.api_key: return
    html = TPL_BASE % (f"<p>Your issue <b>#{issue_id}</b> status is now <b>{status.replace('_',' ')}</b>.</p>")
    resend.Emails.send({"from": f"{FROM_NAME} <{FROM_ADDR}>","to":[to_email],"subject":f"Issue #{issue_id} status update","html": html})

def send_report_confirmation(to_email: str, issue_id: int, title: str):
    """Send confirmation email when a report is submitted."""
    if not resend.api_key: return
    link = f"{os.getenv('FRONTEND_BASE_URL','')}/issues/{issue_id}"
    html = TPL_BASE % (
        f"<p>Thank you for reporting an issue!</p>"
        f"<p><b>Ticket #:</b> {issue_id}</p>"
        f"<p><b>Title:</b> {title}</p>"
        f"<p>We've received your report and will keep you updated on its progress. "
        f"You can view it <a href='{link}'>here</a>.</p>"
    )
    resend.Emails.send({
        "from": f"{FROM_NAME} <{FROM_ADDR}>",
        "to": [to_email],
        "subject": f"Report submitted - Ticket #{issue_id}",
        "html": html
    })