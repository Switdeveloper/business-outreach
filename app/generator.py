import httpx
import openai
from ..config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, DEFAULT_MODEL

openai_client = openai.AsyncOpenAI(
    api_key=OPENROUTER_API_KEY or "sk-placeholder",
    base_url=OPENROUTER_BASE_URL,
)

async def generate_via_openrouter(lead, model: str = DEFAULT_MODEL, instructions: str = ""):
    if not OPENROUTER_API_KEY:
        return {"content": "", "error": "OpenRouter API key not configured"}

    prompt = _build_prompt(lead, instructions)

    try:
        response = await openai_client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            timeout=30,
        )
        content = response.choices[0].message.content or ""
        return {"content": content.strip(), "error": ""}
    except Exception as e:
        return {"content": "", "error": str(e)}

async def generate_via_n8n(lead, webhook_url: str, instructions: str = ""):
    if not webhook_url:
        return {"content": "", "error": "n8n webhook URL not configured"}

    payload = {
        "lead": {
            "name": lead.get("name", ""),
            "email": lead.get("email", ""),
            "phone": lead.get("phone", ""),
            "website": lead.get("website", ""),
            "rating": lead.get("rating", 0),
            "address": lead.get("address", ""),
            "category": lead.get("category", ""),
            "city": lead.get("city", ""),
        },
        "instructions": instructions,
    }

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(webhook_url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            message = data.get("message", data.get("content", ""))
            subject = data.get("subject", "")
            return {"content": message.strip(), "subject": subject.strip(), "error": ""}
    except Exception as e:
        return {"content": "", "error": str(e)}

def _build_prompt(lead, instructions: str = ""):
    base = f"""Write a professional cold outreach email to the following business:

Business Name: {lead.get('name', 'N/A')}
Email: {lead.get('email', 'N/A')}
Website: {lead.get('website', 'N/A')}
Rating: {lead.get('rating', 'N/A')}
Address: {lead.get('address', 'N/A')}
Category: {lead.get('category', '')}
City: {lead.get('city', '')}

The email should be concise, personalized, and include a clear call to action.
Do not include placeholders in brackets. Write the email body only, no subject line."""

    if instructions:
        base = f"{instructions}\n\n{base}"

    return base

async def validate_openrouter_model(model_id: str):
    if not OPENROUTER_API_KEY:
        return {"valid": False, "error": "API key not configured"}

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{OPENROUTER_BASE_URL}/models",
                headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
            )
            resp.raise_for_status()
            models = resp.json().get("data", [])
            for m in models:
                if m.get("id") == model_id:
                    return {"valid": True, "error": ""}
            return {"valid": False, "error": f"Model '{model_id}' not found on OpenRouter"}
    except Exception as e:
        return {"valid": False, "error": str(e)}
