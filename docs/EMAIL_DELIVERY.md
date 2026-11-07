# Kairos email delivery

Kairos sends two kinds of messages through the backend's SMTP configuration:

- A workspace invitation email containing a seven-day acceptance link.
- A welcome email after a confirmed account signs in. One message is sent per
  login session; page reloads reuse the same idempotency id.

Configure these values in the backend environment (never in browser code):

| Variable | Example | Secret |
|---|---|---|
| `SMTP_HOST` | `smtp.gmail.com` | No |
| `SMTP_PORT` | `587` | No |
| `KAIROS_EMAIL_SECURITY` | `starttls` (`ssl` is also supported) | No |
| `SMTP_USER` | Sending Gmail address | Treat as private configuration |
| `SMTP_PASSWORD` | Google App Password | Yes |
| `SMTP_FROM` | Sending Gmail address | No |
| `SMTP_APP_NAME` | `Kairos` | No |
| `KAIROS_PUBLIC_APP_URL` | `https://kairos.example.com` | No |

For Gmail, set `SMTP_USER` and `SMTP_FROM` to the same sending Gmail address,
and use its Google App Password as `SMTP_PASSWORD`. Do not use the recipient's password. The
`KAIROS_PUBLIC_APP_URL` must be a reachable HTTPS deployment URL for recipients;
localhost is suitable only for testing on the same machine.

If SMTP is not configured, invite creation still returns a copyable link and
clearly reports that no email was sent. The invitation row is not evidence of
delivery. Login welcome-email attempts likewise return a visible error to the
signed-in user when the SMTP service is unavailable. No secrets or message
bodies are stored in the delivery-status table.
