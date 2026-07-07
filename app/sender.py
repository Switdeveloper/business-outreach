import httpx
from ..config import BREVO_API_KEY, BREVO_BASE_URL

async def send_email_via_brevo(to_email: str, to_name: str, subject: str, html_content: str, sender_name: str = "", sender_email: str = ""):
    if not BREVO_API_KEY:
        return {"success": False, "error": "Brevo API key not configured"}

    payload = {
        "sender": {
            "name": sender_name or "Business Outreach",
            "email": sender_email or "outreach@yourdomain.com",
        },
        "to": [{"email": to_email, "name": to_name}],
        "subject": subject,
        "htmlContent": html_content.replace("\n", "<br>"),
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{BREVO_BASE_URL}/smtp/email",
                headers={
                    "api-key": BREVO_API_KEY,
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                json=payload,
            )
            if resp.status_code in (200, 201):
                return {"success": True, "error": ""}
            else:
                error_body = resp.text
                return {"success": False, "error": f"Brevo error ({resp.status_code}): {error_body}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

async def test_brevo_connection():
    if not BREVO_API_KEY:
        return {"success": False, "error": "API key not configured"}

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{BREVO_BASE_URL}/account",
                headers={"api-key": BREVO_API_KEY, "Accept": "application/json"},
            )
            if resp.status_code == 200:
                return {"success": True, "error": ""}
            return {"success": False, "error": f"Invalid key ({resp.status_code})"}
    except Exception as e:
        return {"success": False, "error": str(e)}
