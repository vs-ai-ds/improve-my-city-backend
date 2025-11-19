#app\services\notify_push.py
import json
from pywebpush import webpush, WebPushException
from app.core.config import settings

VAPID_PRIVATE = settings.vapid_private_key
VAPID_PUBLIC = settings.vapid_public_key
VAPID_CLAIMS = {"sub": settings.vapid_sub}

def send_push(subscription: dict, payload: dict):
    if not VAPID_PRIVATE or not VAPID_PUBLIC: return
    try:
        webpush(
            subscription_info=subscription,
            data=json.dumps(payload),
            vapid_private_key=VAPID_PRIVATE,
            vapid_public_key=VAPID_PUBLIC,
            vapid_claims=VAPID_CLAIMS
        )
    except WebPushException as e:
        print("push failed", e)