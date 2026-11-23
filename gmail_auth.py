import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

BASE_DIR = Path(__file__).resolve().parent
SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
]
TOKEN_PATH = BASE_DIR / "token.json"
CREDS_PATH = BASE_DIR / "credentials.json"


def get_credentials():
    """Load existing Google OAuth credentials or start a fresh OAuth flow."""
    if not CREDS_PATH.exists():
        raise FileNotFoundError(
            "credentials.json not found. Place your Google OAuth client secret file "
            f"in {CREDS_PATH} and rerun."
        )

    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    missing_scopes = not creds or not creds.has_scopes(SCOPES)
    if missing_scopes:
        flow = InstalledAppFlow.from_client_secrets_file(
            str(CREDS_PATH), SCOPES
        )
        creds = flow.run_local_server(port=0)
    elif not creds.valid:
        if creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDS_PATH), SCOPES
            )
            creds = flow.run_local_server(port=0)

    if not creds.valid:
        raise RuntimeError("Gmail OAuth credentials are not valid after authorization.")

    TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
    return creds


def get_gmail_service():
    """Create and return an authenticated Gmail API service."""
    creds = get_credentials()
    return build("gmail", "v1", credentials=creds)
