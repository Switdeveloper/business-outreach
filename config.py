import os
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
APIFY_API_KEY = os.getenv("APIFY_API_KEY", "")
BREVO_API_KEY = os.getenv("BREVO_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
APIFY_BASE_URL = "https://api.apify.com/v2"
BREVO_BASE_URL = "https://api.brevo.com/v3"
DEFAULT_MODEL = "mistralai/mistral-7b-instruct:free"
APIFY_ACTOR_ID = "xmiso_scrapers/millions-us-businesses-leads-with-emails-from-google-maps"
