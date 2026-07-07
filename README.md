# Business Outreach

Scrape business leads from Google Maps via Apify, generate personalized outreach messages using AI (OpenRouter or n8n), and send them via Brevo email.

---

## 🚀 Quick Start

```bash
git clone https://github.com/Switdeveloper/business-outreach.git
cd business-outreach
pip install -r requirements.txt
python main.py
```

Open **http://localhost:8000** in your browser.

---

## ⚙️ Setup

### 1. Get API Keys

| Service | What for | Where to get |
|---------|----------|-------------|
| **Apify** | Scrapes Google Maps business leads | [apify.com](https://console.apify.com/integrations) |
| **OpenRouter** | AI message generation (free models available) | [openrouter.ai/keys](https://openrouter.ai/keys) |
| **Brevo** | Send email outreach | [brevo.com](https://app.brevo.com/settings/keys/api) |

### 2. Configure in Web UI

Go to the **Settings** tab and paste your keys. Click **Test** next to each to verify. Keys are saved permanently (no need to re-enter on restart).

### 3. Start Scraping

Go to the **Scrape** tab → enter category, city, country → click **Start Scrape**.

---

## 📋 Usage

### Scrape

```
Category: bakery
City: florida
Country: US
Max Results: 20
```

The app runs the Apify actor `xmiso_scrapers/millions-us-businesses-leads-with-emails-from-google-maps` and stores all leads in the database.

### Generate Messages

Two AI providers:

**OpenRouter** — select a model from the dropdown or type a custom model ID. Free models available:

- `mistralai/mistral-7b-instruct:free`
- `meta-llama/llama-3-8b-instruct:free`
- `google/gemma-2-2b-it:free`

Custom model IDs are validated against OpenRouter's API before use.

**n8n Webhook** — send lead data to your own n8n workflow and receive a generated message back. The app sends:

```json
{
  "lead": { "name": "", "email": "", "phone": "", "website": "", "rating": 0, "address": "", "category": "", "city": "" },
  "instructions": "your custom instructions"
}
```

Your webhook must return:

```json
{ "message": "Generated email body here", "subject": "Optional subject" }
```

### Send Emails

- **Individual** — click "Send" next to any message
- **Batch** — click "Send All Drafts" to send all messages for a scrape via Brevo

---

## 🌐 API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/settings` | Get all settings |
| POST | `/api/settings` | Save settings |
| GET | `/api/models` | List OpenRouter models |
| POST | `/api/validate-model` | Check if model ID exists on OpenRouter |
| POST | `/api/scrape` | Start a new scrape |
| GET | `/api/scrapes` | List all scrapes |
| GET | `/api/scrapes/{id}` | Get scrape + leads + messages |
| POST | `/api/generate/{id}` | Generate messages for a scrape |
| GET | `/api/messages` | List messages (filter by `scrape_id`, `status`) |
| POST | `/api/send/{id}` | Send one email |
| POST | `/api/send-batch/{id}` | Send all draft messages |
| DELETE | `/api/messages/{id}` | Delete a message |
| POST | `/api/clear-data` | Delete all data |
| GET | `/api/task/{type}/{ref_id}` | Poll task progress |
| POST | `/api/test/openrouter` | Test OpenRouter API key |
| POST | `/api/test/apify` | Test Apify API key |
| POST | `/api/test/brevo` | Test Brevo API key |
| POST | `/api/test/n8n` | Test n8n webhook URL |

---

## 📁 Project Structure

```
business-outreach/
├── main.py              ← FastAPI app + all routes
├── config.py            ← Default config values
├── requirements.txt     ← Python dependencies
├── .env.example         ← Template for env vars
├── templates/
│   └── index.html       ← Single-page web UI
├── app/
│   ├── __init__.py
│   ├── models.py        ← SQLite tables (scrapes, leads, messages, settings)
│   ├── scraper.py       ← Apify API integration
│   ├── generator.py     ← OpenRouter + n8n webhook message generation
│   ├── sender.py        ← Brevo email sending
│   └── tasks.py         ← Background task runner
└── README.md
```

---

## 🗄️ Database

SQLite (`outreach.db`) — created automatically on first run.

### Tables

- **scrapes** — scrape jobs (category, city, country, status, Apify run ID)
- **leads** — business leads scraped from Google Maps
- **messages** — generated AI messages with status (draft/sent/failed)
- **settings** — key-value store for API keys and preferences
- **task_progress** — background task progress tracking

---

## 🆓 Free Tier Limits

| Service | Free tier |
|---------|-----------|
| **Apify** | $5 free credit (one-time). ~$0.50 per 1000 results |
| **OpenRouter** | Free models: Mistral 7B, Llama 3 8B, Gemma 2B. No key required for free models |
| **Brevo** | 300 emails/day free |

---

## 🔧 Running on a Server

```bash
pip install -r requirements.txt
nohup python main.py > outreach.log 2>&1 &
```

Then access via `http://your-server-ip:8000`.

### Reverse Proxy (Nginx)

```nginx
server {
    listen 80;
    server_name outreach.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## 🛑 Stopping

```bash
# If running in foreground: Ctrl+C
# If running with nohup: kill $(pgrep -f "python main.py")
```

---

## 📝 Requirements

- Python 3.10+
- Internet connection (for API calls)

---

## License

MIT
