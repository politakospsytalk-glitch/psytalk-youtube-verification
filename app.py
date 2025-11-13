from flask import Flask, redirect, request, session, url_for
import google.oauth2.credentials
import google_auth_oauthlib.flow
import googleapiclient.discovery
import os

app = Flask(__name__)
app.secret_key = "super_secret_key_change_this"

CLIENT_SECRETS_FILE = "client_secret.json"
SCOPES = ["https://www.googleapis.com/auth/youtube.readonly"]

CHANNEL_ID = "YOUR_CHANNEL_ID_HERE"  # βάλε το δικό σου κανάλι

@app.route("/")
def index():
    return """
    <h1>PSY-TALK Verification</h1>
    <a href="/authorize">Σύνδεση με Google</a>
    """

@app.route("/authorize")
def authorize():
    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, scopes=SCOPES)
    flow.redirect_uri = url_for("oauth2callback", _external=True)

    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true"
    )
    session["state"] = state
    return redirect(authorization_url)

@app.route("/oauth2callback")
def oauth2callback():
    state = session["state"]

    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, scopes=SCOPES, state=state
    )
    flow.redirect_uri = url_for("oauth2callback", _external=True)

    flow.fetch_token(authorization_response=request.url)
    credentials = flow.credentials

    youtube = googleapiclient.discovery.build(
        "youtube", "v3", credentials=credentials
    )

    request_subs = youtube.subscriptions().list(
        part="snippet",
        mine=True,
        forChannelId=CHANNEL_ID
    )
    response = request_subs.execute()

    if response.get("items"):
        return "<h1>Είσαι εγγεγραμμένος! Κατέβασε το e-book.</h1>"
    else:
        return "<h1>Δεν είστε εγγεγραμμένος στο κανάλι.</h1>"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
