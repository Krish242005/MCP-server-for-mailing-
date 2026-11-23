
import base64
from email.mime.text import MIMEText
from typing import Any

import uvicorn
from googleapiclient.errors import HttpError
from mcp.server.mcpserver import MCPServer

from gmail_auth import get_gmail_service

server = MCPServer("gmail-ai-assistant")


def _normalize_list(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()]


def _validate_email(email: str) -> str:
    if not email or "@" not in email:
        raise ValueError(f"Invalid email address: {email!r}")
    local, domain = email.rsplit("@", 1)
    if not local or not domain or "." not in domain:
        raise ValueError(f"Invalid email address: {email!r}")
    return email.strip()


def _validate_email_list(value: Any, field_name: str) -> list[str]:
    items = []
    for item in _normalize_list(value):
        items.append(_validate_email(item))
    return items


def _build_email_body(recipient_name: str, subject: str, body: str, tone: str, sender_name: str) -> str:
    salutation = "Hello" if tone.lower() != "formal" else "Dear"
    greeting = f"{salutation} {recipient_name},\n\n"
    closing = "Best regards,\n" if tone.lower() not in {"casual", "friendly"} else "Thanks,\n"
    closing += sender_name
    return f"{greeting}{body.strip()}\n\n{closing}\n"


def _decode_message_body(payload: dict[str, Any]) -> dict[str, str]:
    bodies = {"text/plain": [], "text/html": []}

    def collect(part: dict[str, Any]) -> None:
        mime_type = part.get("mimeType", "")
        body = part.get("body", {})
        data = body.get("data")
        if data and not part.get("filename") and mime_type in bodies:
            padding = "=" * (-len(data) % 4)
            decoded = base64.urlsafe_b64decode(data + padding).decode(
                "utf-8", errors="replace"
            )
            bodies[mime_type].append(decoded)

        for child in part.get("parts", []):
            collect(child)

    collect(payload)
    return {mime_type: "\n".join(parts) for mime_type, parts in bodies.items()}


def _message_headers(message: dict[str, Any]) -> dict[str, str]:
    return {
        header["name"].lower(): header["value"]
        for header in message.get("payload", {}).get("headers", [])
    }


@server.tool(name="search_emails")
def search_emails(
    query: str = "",
    max_results: int = 20,
    page_token: str | None = None,
) -> dict[str, Any]:
    """Search Gmail and return message headers, snippets, and pagination information."""
    if not isinstance(query, str):
        raise ValueError("query must be a string.")
    if not 1 <= max_results <= 100:
        raise ValueError("max_results must be between 1 and 100.")

    service = get_gmail_service()
    request = service.users().messages().list(
        userId="me",
        q=query.strip(),
        maxResults=max_results,
        pageToken=page_token,
    )
    listing = request.execute()
    emails = []
    for item in listing.get("messages", []):
        message = (
            service.users()
            .messages()
            .get(
                userId="me",
                id=item["id"],
                format="metadata",
                metadataHeaders=["From", "To", "Cc", "Subject", "Date"],
            )
            .execute()
        )
        headers = _message_headers(message)
        emails.append(
            {
                "message_id": message["id"],
                "thread_id": message.get("threadId", ""),
                "from": headers.get("from", ""),
                "to": headers.get("to", ""),
                "cc": headers.get("cc", ""),
                "subject": headers.get("subject", ""),
                "date": headers.get("date", ""),
                "snippet": message.get("snippet", ""),
                "labels": message.get("labelIds", []),
            }
        )

    return {
        "emails": emails,
        "next_page_token": listing.get("nextPageToken"),
        "result_size_estimate": listing.get("resultSizeEstimate", 0),
    }


@server.tool(name="get_email")
def get_email(message_id: str) -> dict[str, Any]:
    """Read the headers and body of a Gmail message by its message ID."""
    if not message_id or not message_id.strip():
        raise ValueError("message_id is required.")

    message = (
        get_gmail_service()
        .users()
        .messages()
        .get(userId="me", id=message_id.strip(), format="full")
        .execute()
    )
    headers = _message_headers(message)
    body = _decode_message_body(message.get("payload", {}))
    return {
        "message_id": message["id"],
        "thread_id": message.get("threadId", ""),
        "from": headers.get("from", ""),
        "to": headers.get("to", ""),
        "cc": headers.get("cc", ""),
        "subject": headers.get("subject", ""),
        "date": headers.get("date", ""),
        "snippet": message.get("snippet", ""),
        "text_body": body["text/plain"],
        "html_body": body["text/html"],
        "labels": message.get("labelIds", []),
    }


@server.tool(name="create_email_draft")
def create_email_draft(
    recipient_name: str,
    recipient_email: str,
    subject: str,
    body: str,
    tone: str = "Professional",
    cc: str | None = None,
    bcc: str | None = None,
    sender_name: str = "AI Assistant",
) -> dict[str, str | list[str]]:
    """Prepare and validate an email draft before sending it."""
    if not recipient_name or not recipient_email or not subject or not body:
        raise ValueError("recipient_name, recipient_email, subject, and body are required.")

    validated_recipient = _validate_email(recipient_email)
    validated_cc = _validate_email_list(cc, "cc")
    validated_bcc = _validate_email_list(bcc, "bcc")

    draft_body = _build_email_body(recipient_name, subject, body, tone, sender_name)
    preview = (
        f"RECIPIENT: {recipient_name} <{validated_recipient}>\n"
        f"CC: {', '.join(validated_cc) if validated_cc else 'None'}\n"
        f"BCC: {', '.join(validated_bcc) if validated_bcc else 'None'}\n"
        f"SUBJECT: {subject}\n\n"
        f"EMAIL BODY:\n{draft_body.strip()}"
    )

    return {
        "recipient_name": recipient_name,
        "recipient_email": validated_recipient,
        "cc": validated_cc,
        "bcc": validated_bcc,
        "subject": subject,
        "body": draft_body.strip(),
        "tone": tone,
        "preview": preview,
    }


@server.tool(name="send_email")
def send_email(
    recipient: str,
    subject: str,
    body: str,
    approved: bool = False,
    cc: str | None = None,
    bcc: str | None = None,
    sender_name: str = "AI Assistant",
) -> dict[str, str | bool]:
    """Send an explicitly approved email through the authenticated Gmail account."""
    if not approved:
        raise ValueError("Email was not approved. Approval must be explicitly set to True before sending.")
    if not recipient or not subject or not body:
        raise ValueError("recipient, subject, and body are required.")

    recipient_email = _validate_email(recipient)
    cc_list = _validate_email_list(cc, "cc")
    bcc_list = _validate_email_list(bcc, "bcc")

    try:
        service = get_gmail_service()
        message = MIMEText(body)
        message["To"] = recipient_email
        message["Subject"] = subject
        message["From"] = sender_name

        if cc_list:
            message["Cc"] = ", ".join(cc_list)
        if bcc_list:
            message["Bcc"] = ", ".join(bcc_list)

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
        result = (
            service.users()
            .messages()
            .send(userId="me", body={"raw": raw})
            .execute()
        )

        return {
            "sending_status": "sent",
            "recipient_email": recipient_email,
            "subject": subject,
            "gmail_message_id": str(result.get("id") or ""),
            "error_details": "",
            "approved": approved,
        }
    except HttpError as exc:
        error = exc.error_details if hasattr(exc, "error_details") else str(exc)
        return {
            "sending_status": "failed",
            "recipient_email": recipient_email,
            "subject": subject,
            "gmail_message_id": "",
            "error_details": str(error),
            "approved": approved,
        }
    except Exception as exc:  # pragma: no cover - auth/environment dependent
        return {
            "sending_status": "failed",
            "recipient_email": recipient_email,
            "subject": subject,
            "gmail_message_id": "",
            "error_details": str(exc),
            "approved": approved,
        }


app = server.streamable_http_app(host="0.0.0.0")


if __name__ == "__main__":
    print("Starting Gmail MCP server on http://0.0.0.0:8000/mcp")
    uvicorn.run(app, host="0.0.0.0", port=8000)
