# Gmail MCP Assistant

This project exposes Gmail search, reading, drafting, and sending tools through an MCP server powered by Python and Google OAuth.

## Features

- Gmail OAuth authentication using `credentials.json` and `token.json`
- Gmail search and message-reading tools
- Draft-generation tool for email preparation and validation
- Approved-only send tool that uses Gmail API `messages().send()`
- Streamable HTTP MCP endpoint at `/mcp`

## Setup

1. Create a Google Cloud OAuth client and download `credentials.json`.
2. Install dependencies:
   ```bash
   python3 -m pip install -r requirements.txt
   ```
3. Start the server:
   ```bash
   python3 main.py
   ```
4. Connect your MCP client to `http://localhost:8000/mcp`.

The first authorization requests Gmail read-only access and send access. The resulting
OAuth token is saved in `token.json` and refreshed automatically for later use; sign-in
is needed again only if Google revokes the token or requires reauthorization.

Use `search_emails` with a Gmail search query to find messages, then pass a result's
`message_id` to `get_email` to read its headers and text or HTML body. Search results
are paginated, with up to 100 messages per call.

## Example prompts

- "Draft an email to Rahul about tomorrow's meeting."
- "Send an email to rahul@example.com with subject 'Project update' and body 'Hi Rahul...' but only after my approval."

## Security note

- Keep `credentials.json` and `token.json` out of source control.
- Use authentication before exposing the server publicly.
