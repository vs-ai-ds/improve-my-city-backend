#app\services\storage.py
import requests, uuid
from app.core.config import settings

SUPABASE_URL = settings.supabase_url
SUPABASE_SERVICE_ROLE = settings.supabase_service_role
BUCKET = settings.supabase_bucket

def upload_image(data: bytes, content_type: str, path: str) -> str:
    """Uploads to Supabase Storage via REST; returns public URL (bucket must be public)."""
    if not (SUPABASE_URL and SUPABASE_SERVICE_ROLE):
        # Return a placeholder URL - in production, you should configure Supabase
        # For now, we'll store a data URL or skip upload
        import base64
        b64 = base64.b64encode(data).decode('utf-8')
        return f"data:{content_type};base64,{b64}"
    url = f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/{path}"
    r = requests.post(url, headers={
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE}",
        "Content-Type": content_type,
        "x-upsert": "true",
    }, data=data, timeout=30)
    r.raise_for_status()
    # public URL pattern:
    return f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/{path}"

def make_object_key(issue_id: int, filename: str) -> str:
    ext = (filename.rsplit(".",1)[-1] or "jpg").lower()
    return f"{issue_id}/{uuid.uuid4().hex}.{ext}"