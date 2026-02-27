import time
import threading
from azure.identity import DefaultAzureCredential

class TokenProvider:
    def __init__(self, scope: str):
        self._cred = DefaultAzureCredential()
        self._scope = scope
        self._token = None
        self._expires_at = 0
        self._lock = threading.Lock()

    def get_token(self) -> str:
        now = int(time.time())
        
        # First check without lock (optimization for common case)
        if self._token and now + 60 < self._expires_at:
            return self._token
        
        # Need to refresh - acquire lock
        with self._lock:
            # Double-check pattern: another thread might have refreshed while we waited
            if self._token and now + 60 < self._expires_at:
                return self._token
            
            # Actually refresh the token
            tok = self._cred.get_token(self._scope)
            self._token = tok.token
            self._expires_at = int(getattr(tok, "expires_on", now + 300))
            
        return self._token