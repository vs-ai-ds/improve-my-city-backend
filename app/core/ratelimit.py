# File: app\core\ratelimit.py
# Project: improve-my-city-backend
# Auto-added for reference

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)