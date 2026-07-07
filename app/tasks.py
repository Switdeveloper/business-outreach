from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .models import TaskProgress, Lead, Message, Scrape
from .scraper import run_apify_scraper, poll_apify_run, fetch_apify_results
from .generator import generate_via_openrouter, generate_via_n8n
from .sender import send_email_via_brevo
from ..config import DEFAULT_MODEL
from datetime import datetime, timezone

DATABASE_URL = "sqlite+aiosqlite:///./outreach.db"

async def _get_session():
    engine = create_engine(DATABASE_URL.replace("+aiosqlite", ""), echo=False)
    Session = sessionmaker(bind=engine)
    return Session()

async def run_scrape_task(scrape_id: int, category: str, city: str, country: str, max_results: int):
    session = await _get_session()
    try:
        session.query(TaskProgress).filter_by(ref_id=scrape_id, task_type="scrape").delete()
        task = TaskProgress(task_type="scrape", ref_id=scrape_id, status="running")
        session.add(task)
        session.commit()

        run_id = await run_apify_scraper(category, city, country, max_results)
        scrape = session.query(Scrape).filter_by(id=scrape_id).first()
        if scrape:
            scrape.apify_run_id = run_id
            scrape.status = "running"
            session.commit()

        while True:
            status_data = await poll_apify_run(run_id)
            status = status_data.get("status", "")
            if status in ("SUCCEEDED", "FAILED", "TIMED-OUT", "ABORTED"):
                break
            task.completed += 1
            session.commit()
            await asyncio.sleep(5)

        if status == "SUCCEEDED":
            results = await fetch_apify_results(run_id)
            for item in results:
                profile = item if isinstance(item, dict) else {}
                lead = Lead(
                    scrape_id=scrape_id,
                    name=profile.get("name", profile.get("title", "")),
                    email=profile.get("email", profile.get("website", "")),
                    phone=profile.get("phone", ""),
                    website=profile.get("website", ""),
                    rating=float(profile.get("rating", profile.get("totalScore", 0)) or 0),
                    address=profile.get("address", ""),
                    profile_json=profile,
                )
                session.add(lead)

            session.commit()
            lead_count = session.query(Lead).filter_by(scrape_id=scrape_id).count()
            if scrape:
                scrape.status = "completed"
                scrape.total_leads = lead_count
            task.status = "completed"
            task.total = lead_count
        else:
            if scrape:
                scrape.status = "failed"
            task.status = "failed"
            task.error = f"Apify run {status}"

        session.commit()
    except Exception as e:
        if scrape:
            scrape.status = "failed"
        task.status = "failed"
        task.error = str(e)
        session.commit()
    finally:
        session.close()

async def run_generate_task(scrape_id: int, provider: str, model: str, webhook_url: str, instructions: str):
    session = await _get_session()
    try:
        session.query(TaskProgress).filter_by(ref_id=scrape_id, task_type="generate").delete()
        task = TaskProgress(task_type="generate", ref_id=scrape_id, status="running")
        session.add(task)
        session.commit()

        leads = session.query(Lead).filter_by(scrape_id=scrape_id).all()
        task.total = len(leads)
        session.commit()

        for lead in leads:
            lead_data = {
                "name": lead.name,
                "email": lead.email,
                "phone": lead.phone,
                "website": lead.website,
                "rating": lead.rating,
                "address": lead.address,
                "category": "",
                "city": "",
            }
            scrape = session.query(Scrape).filter_by(id=scrape_id).first()
            if scrape:
                lead_data["category"] = scrape.category
                lead_data["city"] = scrape.city

            if provider == "n8n":
                result = await generate_via_n8n(lead_data, webhook_url, instructions)
            else:
                result = await generate_via_openrouter(lead_data, model or DEFAULT_MODEL, instructions)

            msg = Message(
                lead_id=lead.id,
                scrape_id=scrape_id,
                provider=provider,
                model_used=model if provider == "openrouter" else "",
                webhook_url=webhook_url if provider == "n8n" else "",
                custom_instructions=instructions,
                content=result.get("content", ""),
                subject=result.get("subject", ""),
                status="draft" if result.get("content") else "failed",
                error=result.get("error", ""),
            )
            session.add(msg)

            if result.get("content"):
                task.completed += 1
            else:
                task.failed += 1
            session.commit()

        task.status = "completed"
        if task.failed > 0:
            task.status = "completed_with_errors"
        session.commit()
    except Exception as e:
        task.status = "failed"
        task.error = str(e)
        session.commit()
    finally:
        session.close()

async def run_send_batch_task(scrape_id: int, sender_name: str, sender_email: str):
    session = await _get_session()
    try:
        session.query(TaskProgress).filter_by(ref_id=scrape_id, task_type="send").delete()
        task = TaskProgress(task_type="send", ref_id=scrape_id, status="running")
        session.add(task)
        session.commit()

        messages = session.query(Message).filter_by(scrape_id=scrape_id, status="draft").all()
        task.total = len(messages)
        session.commit()

        for msg in messages:
            lead = session.query(Lead).filter_by(id=msg.lead_id).first()
            if not lead or not lead.email:
                msg.status = "failed"
                msg.error = "No email address"
                task.failed += 1
                session.commit()
                continue

            subject = msg.subject or "Hello"
            result = await send_email_via_brevo(
                to_email=lead.email,
                to_name=lead.name,
                subject=subject,
                html_content=msg.content,
                sender_name=sender_name,
                sender_email=sender_email,
            )

            if result.get("success"):
                msg.status = "sent"
                task.completed += 1
            else:
                msg.status = "failed"
                msg.error = result.get("error", "")
                task.failed += 1
            session.commit()

        task.status = "completed"
        if task.failed > 0:
            task.status = "completed_with_errors"
        session.commit()
    except Exception as e:
        task.status = "failed"
        task.error = str(e)
        session.commit()
    finally:
        session.close()

import asyncio
