#app\services\storage.py
import os, requests, uuid

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE = os.getenv("SUPABASE_SERVICE_ROLE")
BUCKET = os.getenv("SUPABASE_BUCKET", "issue-photos")

def upload_image(data: bytes, content_type: str, path: str) -> str:
    """Uploads to Supabase Storage via REST; returns public URL (bucket must be public)."""
    if not (SUPABASE_URL and SUPABASE_SERVICE_ROLE):
        raise RuntimeError("Supabase env not configured")
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