"""Microsoft identity (MSAL) device-code login for Outlook calendar."""

from __future__ import annotations

import threading
from pathlib import Path

from app.config import DATA_DIR, get_settings

CACHE_PATH = DATA_DIR / "msal_token.json"
GRAPH_SCOPES = ["Calendars.Read"]

_cache_lock = threading.Lock()
_pending: dict | None = None
_pending_error: str | None = None


def _cache_path() -> Path:
    return CACHE_PATH


def _load_cache():
    import msal

    cache = msal.SerializableTokenCache()
    path = _cache_path()
    if path.exists():
        cache.deserialize(path.read_text())
    return cache


def _save_cache(cache) -> None:
    if cache.has_state_changed:
        _cache_path().parent.mkdir(parents=True, exist_ok=True)
        _cache_path().write_text(cache.serialize())


def _app():
    import msal

    settings = get_settings()
    cache = _load_cache()
    client = msal.PublicClientApplication(
        settings.azure_ad_client_id,
        authority=f"https://login.microsoftonline.com/{settings.azure_ad_tenant_id}",
        token_cache=cache,
    )
    return client, cache


def graph_configured() -> bool:
    return bool(get_settings().azure_ad_client_id.strip())


def graph_connected() -> bool:
    return get_graph_token() is not None


def get_graph_token() -> str | None:
    if not graph_configured():
        return None
    with _cache_lock:
        app, cache = _app()
        accounts = app.get_accounts()
        if not accounts:
            return None
        result = app.acquire_token_silent(GRAPH_SCOPES, account=accounts[0])
        _save_cache(cache)
        if result and "access_token" in result:
            return result["access_token"]
        return None


def start_device_login() -> dict:
    """Begin device-code flow. Polls in a background thread until the user signs in."""
    global _pending, _pending_error
    if not graph_configured():
        raise RuntimeError("AZURE_AD_CLIENT_ID is not set")

    with _cache_lock:
        app, cache = _app()
        flow = app.initiate_device_flow(scopes=GRAPH_SCOPES)
        if "user_code" not in flow:
            raise RuntimeError("Could not start Outlook device login")
        _pending = flow
        _pending_error = None

    def _poll() -> None:
        global _pending, _pending_error
        try:
            with _cache_lock:
                app, cache = _app()
            result = app.acquire_token_by_device_flow(flow)
            with _cache_lock:
                if result and "access_token" in result:
                    _save_cache(cache)
                    _pending_error = None
                else:
                    _pending_error = (result or {}).get("error_description") or "login failed"
                _pending = None
        except Exception as exc:  # noqa: BLE001 — surface to status endpoint
            _pending_error = str(exc)
            _pending = None

    threading.Thread(target=_poll, daemon=True).start()
    return {
        "user_code": flow["user_code"],
        "verification_uri": flow.get("verification_uri") or "https://microsoft.com/devicelogin",
        "message": flow.get("message", ""),
        "expires_in": int(flow.get("expires_in") or 900),
    }


def login_pending() -> dict | None:
    if not _pending:
        return None
    return {
        "user_code": _pending.get("user_code"),
        "verification_uri": _pending.get("verification_uri"),
        "message": _pending.get("message"),
    }


def last_login_error() -> str | None:
    return _pending_error


def logout_graph() -> None:
    global _pending, _pending_error
    with _cache_lock:
        _pending = None
        _pending_error = None
        path = _cache_path()
        if path.exists():
            path.unlink()
