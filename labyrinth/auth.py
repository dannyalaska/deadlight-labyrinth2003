"""
Auth helpers for the dreams_and_static beta.

BETA_USERS env var format:
    BETA_USERS=alice:tok_abc123,bob:tok_def456

Each token is the invite token for that user.  The invite URL is:
    https://yoursite.com/?invite=tok_abc123

After first use the token is invalidated and the user logs in
with their chosen password thereafter.
"""
from __future__ import annotations

import os
import secrets
from typing import Dict, Optional

import bcrypt

from . import db


def parse_beta_users() -> Dict[str, str]:
    """
    Parse BETA_USERS env var.
    Returns {invite_token: username}.
    """
    raw = os.environ.get("BETA_USERS", "").strip()
    if not raw:
        return {}
    mapping: Dict[str, str] = {}
    for entry in raw.split(","):
        entry = entry.strip()
        if ":" not in entry:
            continue
        username, token = entry.split(":", 1)
        username = username.strip()
        token = token.strip()
        if username and token:
            mapping[token] = username
    return mapping


# Module-level cache — populated once at startup via init_auth().
_token_to_user: Dict[str, str] = {}


def init_auth() -> None:
    """
    Call once at startup.  Parses BETA_USERS, ensures all users exist in
    the database, and caches the token→username mapping in memory.
    """
    db.init_db()
    global _token_to_user
    _token_to_user = parse_beta_users()
    for username in _token_to_user.values():
        db.ensure_user(username)


def validate_invite_token(token: str) -> Optional[str]:
    """
    Return the username for a valid, unused invite token.
    Returns None if the token is unknown or already consumed.
    """
    username = _token_to_user.get(token)
    if not username:
        return None
    if db.is_invite_used(username):
        return None
    return username


def set_password(username: str, plain: str) -> None:
    """Hash and store a new password, then mark the invite as used."""
    hashed = bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()
    db.set_password_hash(username, hashed)
    db.mark_invite_used(username)


def verify_password(username: str, plain: str) -> bool:
    """Return True if the password matches the stored hash."""
    stored = db.get_password_hash(username)
    if not stored:
        return False
    return bcrypt.checkpw(plain.encode(), stored.encode())


def create_session(username: str) -> str:
    """Generate a new auth-session token, persist it, and return it."""
    token = secrets.token_urlsafe(32)
    db.create_auth_session(token, username)
    return token


def validate_session(token: Optional[str]) -> Optional[str]:
    """Return the username for a valid cookie token, else None."""
    if not token:
        return None
    return db.get_auth_session_user(token)


def revoke_session(token: str) -> None:
    db.delete_auth_session(token)


# ── HTML page templates ───────────────────────────────────────────────────────
# Minimal, monospace aesthetic that fits the game without loading any JS.

_BASE_STYLE = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  background: #111;
  color: #aaa;
  font-family: 'Courier New', Courier, monospace;
  font-size: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
}
.box {
  width: 360px;
  border: 1px solid #2a2a2a;
  padding: 36px 32px;
}
.site-name {
  font-size: 11px;
  color: #555;
  letter-spacing: 0.10em;
  margin-bottom: 6px;
}
h1 {
  font-size: 13px;
  color: #777;
  font-weight: normal;
  margin-bottom: 28px;
  border-bottom: 1px solid #222;
  padding-bottom: 14px;
}
label {
  display: block;
  font-size: 10px;
  color: #555;
  letter-spacing: 0.06em;
  margin-bottom: 5px;
}
input[type=text],
input[type=password] {
  display: block;
  width: 100%;
  background: #0d0d0d;
  border: 1px solid #2a2a2a;
  color: #bbb;
  font-family: inherit;
  font-size: 12px;
  padding: 7px 9px;
  margin-bottom: 18px;
}
input:focus { outline: none; border-color: #444; }
button {
  background: none;
  border: 1px solid #3a3a3a;
  color: #888;
  font-family: inherit;
  font-size: 12px;
  padding: 7px 18px;
  cursor: pointer;
  letter-spacing: 0.04em;
}
button:hover { border-color: #666; color: #aaa; }
.error {
  color: #b05555;
  font-size: 11px;
  margin-bottom: 16px;
  border-left: 2px solid #7a2020;
  padding-left: 10px;
}
.note {
  color: #3a3a3a;
  font-size: 10px;
  margin-top: 22px;
  line-height: 1.6;
}
"""


def login_page(error: str = "") -> str:
    error_html = f'<p class="error">{error}</p>' if error else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>dreams_and_static</title>
  <style>{_BASE_STYLE}</style>
</head>
<body>
<div class="box">
  <p class="site-name">dreams_and_static</p>
  <h1>member access</h1>
  {error_html}
  <form method="post" action="/auth/login">
    <label>username</label>
    <input type="text" name="username" autocomplete="username" autofocus spellcheck="false">
    <label>password</label>
    <input type="password" name="password" autocomplete="current-password">
    <button type="submit">[ enter ]</button>
  </form>
  <p class="note">
    this board is in private beta.<br>
    if you received an invite link, open it to set your password first.
  </p>
</div>
</body>
</html>"""


def set_password_page(username: str, token: str, error: str = "") -> str:
    error_html = f'<p class="error">{error}</p>' if error else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>dreams_and_static — welcome</title>
  <style>{_BASE_STYLE}</style>
</head>
<body>
<div class="box">
  <p class="site-name">dreams_and_static</p>
  <h1>welcome, {username}</h1>
  {error_html}
  <p style="font-size:11px;color:#555;margin-bottom:24px;line-height:1.7">
    set a password to access the forum.<br>
    your invite link will stop working after this.
  </p>
  <form method="post" action="/auth/set-password">
    <input type="hidden" name="username" value="{username}">
    <input type="hidden" name="invite_token" value="{token}">
    <label>choose a password</label>
    <input type="password" name="password" autofocus minlength="6"
           autocomplete="new-password">
    <button type="submit">[ set password ]</button>
  </form>
</div>
</body>
</html>"""
