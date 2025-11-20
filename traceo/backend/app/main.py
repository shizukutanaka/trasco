import asyncio
import json
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from loguru import logger

from app.settings import settings
from app.database import get_db, init_db
from app.models import Email as EmailModel, EmailStatus, Report as ReportModel
from app.email_ingestion import ingester
from app.email_analyzer import analyzer
from app.domain_info import domain_lookup
from app.ip_info import ip_lookup
from app.reporter import reporter
from app import auth, user_profiles, export_routes, admin, email_rules, webhooks, audit, rbac

# Initialize FastAPI app
app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    debug=settings.debug,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(user_profiles.router)
app.include_router(export_routes.router)
app.include_router(admin.router)
app.include_router(email_rules.router)
app.include_router(webhooks.router)
app.include_router(audit.router)
app.include_router(rbac.router)

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    try:
        init_db()
        logger.info("Database initialized")

        # Initialize RBAC system roles
        from app.database import SessionLocal
        from app.rbac import RBACService

        db = SessionLocal()
        RBACService.init_system_roles(db)
        db.close()
        logger.info("RBAC system initialized")
    except Exception as e:
        logger.error(f"Startup initialization failed: {e}")

# Pydantic Models
class EmailResponse(BaseModel):
    id: str
    from_addr: str
    subject: str
    received_date: str
    urls: List[str]
    score: int
    status: str
    domain_info: Optional[dict] = None

    class Config:
        from_attributes = True

class ReportRequest(BaseModel):
    email_id: str
    lang: str = "en"
    custom_recipients: Optional[List[str]] = None

class ReportResponse(BaseModel):
    status: str
    email_id: str
    results: dict
    timestamp: str

# Helper Functions
def load_translation(lang: str = "en") -> dict:
    locales_dir = Path(__file__).parent / "locales"
    lang_file = locales_dir / f"{lang}.json"
    if lang_file.exists():
        with open(lang_file, "r", encoding="utf-8") as f:
            return json.load(f)
    default_file = locales_dir / "en.json"
    if default_file.exists():
        with open(default_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

# API Endpoints
@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "service": "traceo",
        "version": settings.api_version,
    }

@app.get("/config")
async def get_config():
    return {
        "name": settings.api_title,
        "version": settings.api_version,
        "languages": ["en", "ja"],
    }

@app.get("/translations/{lang}")
async def get_translations(lang: str = "en"):
    translations = load_translation(lang)
    if not translations:
        raise HTTPException(status_code=404, detail="Language not found")
    return translations

@app.get("/emails", response_model=List[EmailResponse])
async def list_emails(
    skip: int = 0,
    limit: int = 50,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(EmailModel)
    if status:
        query = query.filter(EmailModel.status == status)
    emails = query.order_by(EmailModel.received_date.desc()).offset(skip).limit(limit).all()
    return [
        EmailResponse(
            id=email.id,
            from_addr=email.from_addr,
            subject=email.subject,
            received_date=email.received_date.isoformat(),
            urls=email.urls or [],
            score=email.score,
            status=email.status,
            domain_info=email.domain_info,
        )
        for email in emails
    ]

@app.get("/emails/{email_id}", response_model=EmailResponse)
async def get_email(email_id: str, db: Session = Depends(get_db)):
    email = db.query(EmailModel).filter(EmailModel.id == email_id).first()
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    return EmailResponse(
        id=email.id,
        from_addr=email.from_addr,
        subject=email.subject,
        received_date=email.received_date.isoformat(),
        urls=email.urls or [],
        score=email.score,
        status=email.status,
        domain_info=email.domain_info,
    )

@app.delete("/emails/{email_id}")
async def delete_email(email_id: str, db: Session = Depends(get_db)):
    email = db.query(EmailModel).filter(EmailModel.id == email_id).first()
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    db.delete(email)
    db.commit()
    return {"status": "deleted", "email_id": email_id}

@app.post("/report", response_model=ReportResponse)
async def report_email(request: ReportRequest, db: Session = Depends(get_db)):
    email = db.query(EmailModel).filter(EmailModel.id == request.email_id).first()
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    
    email_data = {
        "from_addr": email.from_addr,
        "subject": email.subject,
        "received_date": email.received_date.isoformat(),
        "urls": email.urls or [],
        "domain_info": email.domain_info or {},
    }
    
    analysis_result = {"score": email.score}
    
    try:
        result = await reporter.send_report(
            request.email_id,
            email_data,
            analysis_result,
            request.lang,
            request.custom_recipients,
        )
        email.status = EmailStatus.REPORTED
        email.reported_at = datetime.utcnow()
        db.commit()
        return ReportResponse(
            status="success",
            email_id=request.email_id,
            results=result["results"],
            timestamp=result["timestamp"],
        )
    except Exception as e:
        logger.error(f"Report failed: {e}")
        raise HTTPException(status_code=500, detail="Report send failed")

@app.get("/reports")
async def list_reports(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    reports = db.query(ReportModel).order_by(ReportModel.created_at.desc()).offset(skip).limit(limit).all()
    return [
        {
            "id": r.id,
            "email_id": r.email_id,
            "recipient": r.recipient_email,
            "status": r.status,
            "created_at": r.created_at.isoformat(),
        }
        for r in reports
    ]

@app.get("/admin/stats")
async def get_statistics(db: Session = Depends(get_db)):
    from sqlalchemy import func
    total_emails = db.query(EmailModel).count()
    analyzed = db.query(EmailModel).filter(EmailModel.status == EmailStatus.ANALYZED).count()
    reported = db.query(EmailModel).filter(EmailModel.status == EmailStatus.REPORTED).count()
    avg_score = db.query(func.avg(EmailModel.score)).scalar() or 0
    return {
        "total_emails": total_emails,
        "analyzed": analyzed,
        "reported": reported,
        "avg_score": round(avg_score, 2),
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
