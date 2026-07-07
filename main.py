import asyncio
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.models import init_db, Scrape, Lead, Message, Setting, TaskProgress
from app.scraper import run_apify_scraper, fetch_apify_results
from app.generator import validate_openrouter_model
from app.sender import test_brevo_connection
from app.tasks import run_scrape_task, run_generate_task, run_send_batch_task
from config import APIFY_ACTOR_ID

DB_URL = "sqlite:///./outreach.db"
engine = None
SessionLocal = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global engine, SessionLocal
    engine = init_db()
    SessionLocal = sessionmaker(bind=engine)
    yield
    if engine:
        engine.dispose()

app = FastAPI(title="Business Outreach", lifespan=lifespan)
templates = Jinja2Templates(directory="templates")

def get_session():
    return SessionLocal()

# ---- Page ----

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# ---- Settings ----

@app.get("/api/settings")
async def get_settings():
    session = get_session()
    rows = session.query(Setting).all()
    data = {r.key: r.value for r in rows}
    session.close()
    return data

@app.post("/api/settings")
async def save_settings(req: Request):
    body = await req.json()
    session = get_session()
    for key, value in body.items():
        existing = session.query(Setting).filter_by(key=key).first()
        if existing:
            existing.value = str(value)
        else:
            session.add(Setting(key=key, value=str(value)))
    session.commit()
    session.close()
    return {"success": True}

@app.get("/api/settings/apify-actor")
async def get_apify_actor():
    return {"actor_id": APIFY_ACTOR_ID}

# ---- Test Connections ----

@app.post("/api/test/openrouter")
async def test_openrouter(req: Request):
    body = await req.json()
    key = body.get("key", "")
    if not key:
        return {"success": False, "error": "No key provided"}
    import httpx
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://openrouter.ai/api/v1/models",
                headers={"Authorization": f"Bearer {key}"},
            )
            if resp.status_code == 200:
                return {"success": True, "error": ""}
            return {"success": False, "error": f"Status {resp.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/api/test/apify")
async def test_apify(req: Request):
    body = await req.json()
    key = body.get("key", "")
    if not key:
        return {"success": False, "error": "No key provided"}
    import httpx
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://api.apify.com/v2/acts",
                params={"token": key, "my": "true", "limit": 1},
            )
            if resp.status_code == 200:
                return {"success": True, "error": ""}
            return {"success": False, "error": f"Status {resp.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/api/test/brevo")
async def test_brevo(req: Request):
    body = await req.json()
    key = body.get("key", "")
    result = await test_brevo_connection()
    if key:
        import httpx
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    "https://api.brevo.com/v3/account",
                    headers={"api-key": key, "Accept": "application/json"},
                )
                return {"success": resp.status_code == 200, "error": "" if resp.status_code == 200 else f"Status {resp.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    return result

@app.post("/api/test/n8n")
async def test_n8n(req: Request):
    body = await req.json()
    webhook_url = body.get("url", "")
    if not webhook_url:
        return {"success": False, "error": "No URL provided"}
    import httpx
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(webhook_url, json={"test": True, "lead": {"name": "Test Business"}})
            if resp.status_code < 500:
                return {"success": True, "error": ""}
            return {"success": False, "error": f"Status {resp.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ---- Models (OpenRouter) ----

@app.get("/api/models")
async def list_models():
    session = get_session()
    setting = session.query(Setting).filter_by(key="openrouter_api_key").first()
    session.close()
    key = setting.value if setting else ""
    if not key:
        return {"models": []}
    import httpx
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://openrouter.ai/api/v1/models",
                headers={"Authorization": f"Bearer {key}"},
            )
            if resp.status_code == 200:
                data = resp.json().get("data", [])
                free = [m for m in data if ":free" in m.get("id", "")]
                paid = [m for m in data if ":free" not in m.get("id", "")]
                return {"models": free + paid}
            return {"models": []}
    except:
        return {"models": []}

@app.post("/api/validate-model")
async def validate_model(req: Request):
    body = await req.json()
    model_id = body.get("model_id", "")
    return await validate_openrouter_model(model_id)

# ---- Scrapes ----

@app.post("/api/scrape")
async def start_scrape(req: Request):
    body = await req.json()
    category = body.get("category", "").strip()
    city = body.get("city", "").strip()
    country = body.get("country", "").strip()
    max_results = int(body.get("max_results", 20))

    if not category or not city or not country:
        raise HTTPException(status_code=400, detail="category, city, and country are required")

    session = get_session()
    scrape = Scrape(category=category, city=city, country=country, max_results=max_results)
    session.add(scrape)
    session.commit()
    scrape_id = scrape.id
    session.close()

    asyncio.create_task(run_scrape_task(scrape_id, category, city, country, max_results))

    return {"success": True, "scrape_id": scrape_id}

@app.get("/api/scrapes")
async def list_scrapes():
    session = get_session()
    scrapes = session.query(Scrape).order_by(Scrape.created_at.desc()).all()
    result = []
    for s in scrapes:
        result.append({
            "id": s.id, "status": s.status, "category": s.category,
            "city": s.city, "country": s.country, "max_results": s.max_results,
            "total_leads": s.total_leads, "apify_run_id": s.apify_run_id,
            "created_at": s.created_at.isoformat() if s.created_at else "",
        })
    session.close()
    return {"scrapes": result}

@app.get("/api/scrapes/{scrape_id}")
async def get_scrape(scrape_id: int):
    session = get_session()
    scrape = session.query(Scrape).filter_by(id=scrape_id).first()
    if not scrape:
        session.close()
        raise HTTPException(status_code=404, detail="Scrape not found")

    leads = session.query(Lead).filter_by(scrape_id=scrape_id).all()
    messages = session.query(Message).filter_by(scrape_id=scrape_id).all()
    task = session.query(TaskProgress).filter_by(ref_id=scrape_id).order_by(TaskProgress.id.desc()).first()
    session.close()

    return {
        "scrape": {
            "id": scrape.id, "status": scrape.status, "category": scrape.category,
            "city": scrape.city, "country": scrape.country, "max_results": scrape.max_results,
            "total_leads": scrape.total_leads, "apify_run_id": scrape.apify_run_id,
            "created_at": scrape.created_at.isoformat() if scrape.created_at else "",
        },
        "leads": [{"id": l.id, "name": l.name, "email": l.email, "phone": l.phone,
                    "website": l.website, "rating": l.rating, "address": l.address} for l in leads],
        "messages": [{"id": m.id, "lead_id": m.lead_id, "provider": m.provider,
                       "model_used": m.model_used, "content": m.content, "subject": m.subject,
                       "status": m.status, "error": m.error} for m in messages],
        "task": {"status": task.status if task else "", "total": task.total if task else 0,
                  "completed": task.completed if task else 0, "failed": task.failed if task else 0},
    }

# ---- Generate ----

@app.post("/api/generate/{scrape_id}")
async def generate_messages(scrape_id: int, req: Request):
    body = await req.json()
    provider = body.get("provider", "openrouter")
    model = body.get("model", "")
    webhook_url = body.get("webhook_url", "")
    instructions = body.get("instructions", "")

    asyncio.create_task(run_generate_task(scrape_id, provider, model, webhook_url, instructions))
    return {"success": True}

# ---- Messages ----

@app.get("/api/messages")
async def list_messages(scrape_id: int = 0, status: str = ""):
    session = get_session()
    query = session.query(Message)
    if scrape_id:
        query = query.filter_by(scrape_id=scrape_id)
    if status:
        query = query.filter_by(status=status)
    messages = query.order_by(Message.id.desc()).all()
    session.close()
    return {"messages": [{"id": m.id, "lead_id": m.lead_id, "scrape_id": m.scrape_id,
                           "provider": m.provider, "content": m.content, "subject": m.subject,
                           "status": m.status, "error": m.error} for m in messages]}

# ---- Send ----

@app.post("/api/send/{message_id}")
async def send_single(message_id: int, req: Request):
    body = await req.json()
    sender_name = body.get("sender_name", "")
    sender_email = body.get("sender_email", "")

    session = get_session()
    msg = session.query(Message).filter_by(id=message_id).first()
    if not msg:
        session.close()
        raise HTTPException(status_code=404, detail="Message not found")

    lead = session.query(Lead).filter_by(id=msg.lead_id).first()
    session.close()

    if not lead or not lead.email:
        raise HTTPException(status_code=400, detail="Lead has no email")

    from app.sender import send_email_via_brevo
    result = await send_email_via_brevo(lead.email, lead.name, msg.subject or "Hello", msg.content, sender_name, sender_email)

    session = get_session()
    msg = session.query(Message).filter_by(id=message_id).first()
    if result.get("success"):
        msg.status = "sent"
    else:
        msg.status = "failed"
        msg.error = result.get("error", "")
    session.commit()
    session.close()

    return result

@app.post("/api/send-batch/{scrape_id}")
async def send_batch(scrape_id: int, req: Request):
    body = await req.json()
    sender_name = body.get("sender_name", "")
    sender_email = body.get("sender_email", "")

    asyncio.create_task(run_send_batch_task(scrape_id, sender_name, sender_email))
    return {"success": True}

# ---- Delete ----

@app.delete("/api/messages/{message_id}")
async def delete_message(message_id: int):
    session = get_session()
    msg = session.query(Message).filter_by(id=message_id).first()
    if msg:
        session.delete(msg)
        session.commit()
    session.close()
    return {"success": True}

@app.post("/api/clear-data")
async def clear_data():
    session = get_session()
    session.execute(text("DELETE FROM messages"))
    session.execute(text("DELETE FROM leads"))
    session.execute(text("DELETE FROM scrapes"))
    session.execute(text("DELETE FROM task_progress"))
    session.commit()
    session.close()
    return {"success": True}

# ---- Tasks ----

@app.get("/api/task/{task_type}/{ref_id}")
async def get_task(task_type: str, ref_id: int):
    session = get_session()
    task = session.query(TaskProgress).filter_by(task_type=task_type, ref_id=ref_id).order_by(TaskProgress.id.desc()).first()
    session.close()
    if task:
        return {"status": task.status, "total": task.total, "completed": task.completed,
                "failed": task.failed, "error": task.error}
    return {"status": "", "total": 0, "completed": 0, "failed": 0}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
