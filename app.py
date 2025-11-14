from flask import Flask, redirect, request, session, url_for
import google.oauth2.credentials
import google_auth_oauthlib.flow
import googleapiclient.discovery
import os

app = Flask(__name__)
app.secret_key = "super_secret_key_change_this"

CLIENT_SECRETS_FILE = "client_secret.json"
SCOPES = ["https://www.googleapis.com/auth/youtube.readonly"]

# PSY-TALK κανάλι
CHANNEL_ID = "UCgJU1icAfnBJ_Nhfvm4WUGg"


@app.route("/")
def index():
    return """
    <h1>PSY-TALK Verification</h1>
    <a href="/authorize">Σύνδεση με Google</a>
    """


@app.route("/authorize")
def authorize():
    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
    )
    flow.redirect_uri = url_for("oauth2callback", _external=True)

    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
    )
    session["state"] = state
    return redirect(authorization_url)


@app.route("/oauth2callback")
def oauth2callback():
    # Παίρνουμε το state που αποθηκεύσαμε πριν
    state = session.get("state")

    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        state=state,
    )
    flow.redirect_uri = url_for("oauth2callback", _external=True)

    # Παίρνουμε το token από το URL που μας γύρισε η Google
    flow.fetch_token(authorization_response=request.url)

    credentials = flow.credentials

    # Φτιάχνουμε αντικείμενο YouTube με αυτά τα credentials
    youtube = googleapiclient.discovery.build(
        "youtube", "v3", credentials=credentials
    )

    # Ελέγχουμε αν ο χρήστης είναι συνδρομητής στο κανάλι PSY-TALK
    request_subs = youtube.subscriptions().list(
        part="snippet",
        mine=True,
        forChannelId=CHANNEL_ID,
    )
    response = request_subs.execute()

    if response.get("items"):
        # Είναι εγγεγραμμένος → δείξε μήνυμα + link download
        return """
            <h1>Είσαι εγγεγραμμένος! Κατέβασε το e-book.</h1>
            <a href="/download" style="font-size:22px;">
                ⬇️ Κατέβασε εδώ το e-book
            </a>
        """
    else:
        # Δεν είναι εγγεγραμμένος
        return "<h1>Δεν είστε εγγεγραμμένος στο κανάλι.</h1>"


@app.route("/download")
def download():
    return redirect(
        "https://drive.google.com/uc?export=download&id=1uKlsMLDw7PX3Jha6xSxuNK538jgghQk7"
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
