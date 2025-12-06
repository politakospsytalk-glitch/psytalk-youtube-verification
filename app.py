# app.py
# -*- coding: utf-8 -*-
"""
Minimal Flask app that verifies if a user is subscribed to your YouTube channel
(using YouTube Data API v3) and, if yes, allows them to download an e‑book.

Flow (OAuth 2.0):
1) User clicks "Sign in with Google".
2) App requests YouTube readonly scope.
3) After callback, we check via subscriptions.list(mine=true, forChannelId=YOUR_CHANNEL_ID).
4) If an item exists => user is subscribed => allow download.

NOTE: This checks using the *user's* own Google account (OAuth) and does not
access emails. This is the privacy‑compliant way.
"""

import os
import json
from pathlib import Path
from flask import Flask, redirect, request, url_for, session, send_from_directory, render_template, abort
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

# ------------------ CONFIG ------------------
# Replace with your Channel ID (canonical channel ID, e.g. "UCgJU1icAfnBJ_Nhfvm4WUGg")
YOUTUBE_CHANNEL_ID = os.getenv("YOUTUBE_CHANNEL_ID", "UCgJU1icAfnBJ_Nhfvm4WUGg")

# OAuth 2.0 client secrets JSON path (download from Google Cloud Console)
OAUTH_CLIENT_SECRETS = os.getenv("OAUTH_CLIENT_SECRETS", "client_secret.json")

# Where your e‑book file lives (place your ebook.pdf inside ./assets)
ASSETS_DIR = Path(__file__).parent / "assets"
EBOOK_FILENAME = os.getenv("EBOOK_FILENAME", "ebook.pdf")
# --- dynamic gifts ---
GIFTS_PATH = Path(__file__).parent / "gifts.json"

def _load_gifts():
    try:
        with open(GIFTS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return {
                "by_video_id": data.get("by_video_id", {}),
                "by_gift_key": data.get("by_gift_key", {})
            }
    except FileNotFoundError:
        return {"by_video_id": {}, "by_gift_key": {}}

GIFTS = _load_gifts()

def _resolve_gift_for_request():
    v = (request.args.get("v") or "").strip()
    if v:
        val = GIFTS["by_video_id"].get(v)
        if val:
            if val.startswith("http://") or val.startswith("https://"):
                return True, val
            return False, val

    key = (request.args.get("gift") or "").strip()
    if key:
        val = GIFTS["by_gift_key"].get(key)
        if val:
            if val.startswith("http://") or val.startswith("https://"):
                return True, val
            return False, val

    return False, EBOOK_FILENAME 
# Flask secret key
SESSION_SECRET = os.getenv("SESSION_SECRET", os.urandom(24).hex())

# OAuth scopes (YouTube readonly)
SCOPES = [
    "https://www.googleapis.com/auth/youtube.readonly"
]
# --------------------------------------------

app = Flask(__name__, template_folder='templates')
app.secret_key = SESSION_SECRET

# Basic templates inline for simplicity
BASE_HTML = """
<!doctype html>
<html lang="el">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Έλεγχος συνδρομής στο κανάλι</title>
  <style>
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif; margin: 2rem; }
    .card { max-width: 720px; margin: 0 auto; padding: 1.5rem; border: 1px solid #ddd; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,.06); }
    .btn { display:inline-block; padding: .75rem 1rem; border-radius: 10px; text-decoration: none; border: 1px solid #333; }
    .btn-primary { background: #111; color: #fff; border-color: #111; }
    .btn-outline { background: #fff; color: #111; }
    .muted { color: #666; font-size: .95rem; }
    .ok { color: #0a7f27; font-weight: 600; }
    .bad { color: #b00020; font-weight: 600; }
    code { background: #f4f4f4; padding: .2rem .4rem; border-radius: 6px; }
  </style>
</head>
<body>
  <div class="card">
    {% block content %}{% endblock %}
  </div>
</body>
</html>
"""

INDEX_HTML = """
{% extends base %}
{% block content %}
  <h1>Δώρο e‑book για συνδρομητές</h1>
  <p class="muted">Επιβεβαίωσε ότι έχεις κάνει <strong>Subscribe</strong> στο κανάλι. Μετά τον έλεγχο θα εμφανιστεί κουμπί για λήψη.</p>
  {% if not session.get('authed') %}
    <p><a class="btn btn-primary" href="{{ url_for('login') }}">Σύνδεση με Google</a></p>
  {% else %}
    <p class="ok">Σύνδεση επιτυχής.</p>
    {% if session.get('is_subscriber') %}
      <p class="ok">Επιβεβαιώθηκε ότι είσαι συνδρομητής του καναλιού ✅</p>
      <p><a class="btn btn-primary" href="{{ url_for('download') }}">Λήψη e‑book</a></p>
    {% else %}
      <p class="bad">Δεν βρέθηκε ενεργή συνδρομή στο κανάλι.</p>
      <p>Κάνε subscribe και ξαναδοκίμασε: <a class="btn btn-outline" href="{{ url_for('check_again') }}">Έλεγχος ξανά</a></p>
    {% endif %}
    <p><a class="btn btn-outline" href="{{ url_for('logout') }}">Αποσύνδεση</a></p>
  {% endif %}
  <hr/>
  <p class="muted">Channel ID στόχος: <code>{{ channel_id }}</code></p>
{% endblock %}
"""

from flask import render_template_string

@app.route("/")
def index():
    html = """
    <!doctype html>
    <html lang="el"><head><meta charset="utf-8"><title>Δώρο e-book για συνδρομητές</title></head>
    <body style="font-family:system-ui,Segoe UI,Roboto,Helvetica,Arial,sans-serif;margin:2rem;">
      <h1>Δώρο e-book για συνδρομητές</h1>
      {% if not session.get('authed') %}
        <p><a href="{{ url_for('login') }}">Σύνδεση με Google</a></p>
      {% else %}
        <p>Σύνδεση επιτυχής.</p>
        {% if session.get('is_subscriber') %}
          <p>Είσαι συνδρομήτρια/ης ✅</p>
          <p><a href="{{ url_for('download') }}">Λήψη e-book</a></p>
        {% else %}
          <p>Δεν βρέθηκε συνδρομή.</p>
          <p><a href="{{ url_for('check_again') }}">Έλεγχος ξανά</a></p>
        {% endif %}
        <p><a href="{{ url_for('logout') }}">Αποσύνδεση</a></p>
      {% endif %}
      <hr><p>Channel ID στόχος: <code>{{ channel_id }}</code></p>
    </body></html>
    """
    return render_template_string(html, channel_id=YOUTUBE_CHANNEL_ID)
@app.route("/login")
def login():
    flow = _build_flow()
    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent"
    )
    session['state'] = state
    return redirect(authorization_url)

@app.route("/oauth2callback")
def oauth2callback():
    if 'state' not in session:
        return redirect(url_for('index'))

    flow = _build_flow(state=session['state'])
    flow.fetch_token(authorization_response=request.url)

    creds = flow.credentials
    session['credentials'] = {
        'token': creds.token,
        'refresh_token': getattr(creds, 'refresh_token', None),
        'token_uri': creds.token_uri,
        'client_id': creds.client_id,
        'client_secret': creds.client_secret,
        'scopes': creds.scopes
    }
    session['authed'] = True

    # After sign‑in, immediately check subscription
    session['is_subscriber'] = _check_subscription(creds)

    return redirect(url_for('index'))

@app.route("/check")
def check_again():
    creds = _load_credentials_from_session()
    if not creds:
        return redirect(url_for('index'))
    session['is_subscriber'] = _check_subscription(creds)
    return redirect(url_for('index'))
@app.route("/download")
def download():
    # ασφάλεια: μόνο αν είναι συνδεδεμένος και συνδρομητής
    if not session.get("authed") or not session.get("is_subscriber"):
        abort(403)

    # απλή ανακατεύθυνση στο νέο e-book στο Drive
    return redirect(
        "https://drive.google.com/uc?export=download&id=1RJci-Hu2ggOfYFSvZ6ID1-0fFCduBpBZ"
    )

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for('index'))

# ------------------ helpers ------------------
@app.route("/admin/reload-gifts")
def admin_reload_gifts():
    global GIFTS
    GIFTS = _load_gifts()
    return {"status": "ok", "by_video_id": len(GIFTS["by_video_id"]), "by_gift_key": len(GIFTS["by_gift_key"])}

def _build_flow(state=None):
    OAUTH_CLIENT_SECRETS = "client_secret.json"
    if not Path(OAUTH_CLIENT_SECRETS).exists():
        raise FileNotFoundError(
            f"Λείπει το {OAUTH_CLIENT_SECRETS}. Κατέβασέ το από Google Cloud Console (OAuth 2.0 client secrets)."
        )

    redirect_uri = "https://politakospsytalk.com/oauth2callback"
    flow = Flow.from_client_secrets_file(
        OAUTH_CLIENT_SECRETS,
        scopes=SCOPES,
        redirect_uri=redirect_uri,
        state=state,
    )
    return flow


def _load_credentials_from_session():
    data = session.get('credentials')
    if not data:
        return None
    return Credentials(**data)


def _check_subscription(creds: Credentials) -> bool:
    """Return True if the signed‑in user is subscribed to YOUTUBE_CHANNEL_ID."""
    youtube = build('youtube', 'v3', credentials=creds)
    req = youtube.subscriptions().list(
        part='id',
        mine=True,
        forChannelId=YOUTUBE_CHANNEL_ID,
        maxResults=1
    )
    resp = req.execute()
    items = resp.get('items', [])
    return len(items) > 0

# ------------------ CLI entry ------------------
if __name__ == "__main__":
    # Create assets folder if missing
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    app.run(host="127.0.0.1", port=5000, debug=False)

"""
README (γρήγορα βήματα)
=======================
1) Δημιούργησε Project στο Google Cloud Console και ενεργοποίησε το YouTube Data API v3.
2) Φτιάξε OAuth 2.0 Client ID (τύπος: Web application) και βάλε Redirect URI:
   http://127.0.0.1:5000/oauth2callback  (ή http://localhost:5000/oauth2callback)
3) Κατέβασε το client_secret.json στο ριζικό φάκελο του έργου.
4) Βάλε το e‑book σου στο ./assets/ ως "ebook.pdf" (ή άλλαξε το όνομα στο env var EBOOK_FILENAME).
5) Βρες το Channel ID σου και βάλε το στο env var YOUTUBE_CHANNEL_ID ή άλλαξε την προεπιλογή στον κώδικα.

Dependencies / Εγκατάσταση
--------------------------
py -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt

Τρέξιμο
-------
set YOUTUBE_CHANNEL_ID=UCgJU1icAfnBJ_Nhfvm4WUGg   (ή το δικό σου ID)
set SESSION_SECRET=anythingrandom
py app.py

Χρήση
-----
1) Άνοιξε http://127.0.0.1:5000/
2) «Σύνδεση με Google» → δώσε δικαιώματα YouTube readonly.
3) Αν είσαι συνδρομητής του συγκεκριμένου καναλιού, θα εμφανιστεί κουμπί «Λήψη e‑book».
"""

