from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
BASE_DIR = Path(__file__).resolve().parents[1]
SECRETS = BASE_DIR / "secrets"

flow = InstalledAppFlow.from_client_secrets_file(
    str(SECRETS / "gmail_credentials.json"), SCOPES
)
creds = flow.run_local_server(port=0)

(SECRETS / "gmail_token.json").write_text(creds.to_json())
print("Saved secrets/gmail_token.json")