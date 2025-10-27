#app\services\notify_push.py
import os, json
from pywebpush import webpush, WebPushException

VAPID_PRIVATE = os.getenv("VAPID_PRIVATE_KEY")
VAPID_PUBLIC = os.getenv("VAPID_PUBLIC_KEY")
VAPID_CLAIMS = {"sub": os.getenv("VAPID_SUB","mailto:noreply@example.com")}

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