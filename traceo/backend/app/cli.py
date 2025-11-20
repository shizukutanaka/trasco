#!/usr/bin/env python3
"""
Traceo CLI - Command-line interface for Traceo

Usage:
    python -m app.cli --help
"""

import asyncio
import click
from pathlib import Path
from datetime import datetime
from loguru import logger

from app.settings import settings
from app.database import SessionLocal, init_db
from app.models import Email as EmailModel, EmailStatus
from app.email_ingestion import ingester
from app.email_analyzer import analyzer
from app.domain_info import domain_lookup
from app.reporter import reporter

# Initialize database
init_db()

@click.group()
def cli():
    """Traceo CLI - Email Phishing Analysis Tool"""
    pass

@cli.command()
@click.option("--server", prompt="IMAP Server", help="IMAP server address")
@click.option("--user", prompt="Email address", help="Email address")
@click.option("--password", prompt=True, hide_input=True, help="Email password")
@click.option("--port", default=993, help="IMAP port")
def connect(server, user, password, port):
    """Connect to IMAP server and fetch emails"""
    click.echo(f"Connecting to {server}:{port}...")

    if ingester.connect(server, user, password, use_ssl=(port == 993)):
        click.echo("✓ Connected successfully")

        click.echo("Fetching emails...")
        emails = ingester.fetch_emails()

        click.echo(f"Fetched {len(emails)} emails")

        saved = 0
        for email in emails:
            if ingester.save_email(email):
                saved += 1

        click.echo(f"✓ Saved {saved} new emails")
    else:
        click.echo("✗ Connection failed", err=True)

@cli.command()
def analyze():
    """Analyze pending emails"""
    db = SessionLocal()

    pending = db.query(EmailModel).filter(
        EmailModel.status == EmailStatus.PENDING
    ).all()

    click.echo(f"Analyzing {len(pending)} pending emails...")

    analyzed = 0
    for email in pending:
        # Analyze
        analysis_result = analyzer.analyze({
            "raw_headers": email.raw_headers,
            "body": email.body,
            "urls": email.urls or [],
        })

        # Get domain info
        if email.urls:
            domain = email.urls[0].split("://")[-1].split("/")[0]
            domain_info = domain_lookup.get_domain_info(domain)
            email.domain_info = domain_info

        # Update email
        email.score = analysis_result["score"]
        email.status = EmailStatus.ANALYZED
        email.analyzed_at = datetime.utcnow()

        db.commit()
        analyzed += 1

        click.echo(f"  {email.subject[:50]:50} - Score: {email.score:3}/100", color='green' if email.score < 50 else 'red')

    click.echo(f"✓ Analyzed {analyzed} emails")

@cli.command()
@click.option("--filter", default="pending", help="Filter by status (pending, analyzed, reported)")
@click.option("--limit", default=10, help="Max results")
def list_emails(filter, limit):
    """List emails"""
    db = SessionLocal()

    query = db.query(EmailModel)

    if filter != "all":
        query = query.filter(EmailModel.status == filter)

    emails = query.order_by(EmailModel.received_date.desc()).limit(limit).all()

    click.echo(f"{'ID':<10} {'From':<30} {'Subject':<30} {'Score':<6} {'Status':<10}")
    click.echo("-" * 90)

    for email in emails:
        score_str = str(email.score) if email.score else "0"
        click.echo(
            f"{email.id[:8]:<10} {email.from_addr[:30]:<30} "
            f"{email.subject[:30]:<30} {score_str:<6} {email.status:<10}"
        )

    click.echo(f"\nTotal: {len(emails)} emails")

@cli.command()
@click.argument("email_id")
def show_email(email_id):
    """Show email details"""
    db = SessionLocal()

    email = db.query(EmailModel).filter(EmailModel.id == email_id).first()

    if not email:
        click.echo("Email not found", err=True)
        return

    click.echo(f"Email ID: {email.id}")
    click.echo(f"From: {email.from_addr}")
    click.echo(f"Subject: {email.subject}")
    click.echo(f"Date: {email.received_date}")
    click.echo(f"Score: {email.score}/100")
    click.echo(f"Status: {email.status}")

    if email.urls:
        click.echo(f"\nURLs:")
        for url in email.urls:
            click.echo(f"  - {url}")

    if email.domain_info:
        click.echo(f"\nDomain Info:")
        for key, value in email.domain_info.items():
            if key != "status":
                click.echo(f"  {key}: {value}")

@cli.command()
@click.argument("email_id")
@click.option("--lang", default="en", help="Report language")
async def report(email_id, lang):
    """Send phishing report"""
    db = SessionLocal()

    email = db.query(EmailModel).filter(EmailModel.id == email_id).first()

    if not email:
        click.echo("Email not found", err=True)
        return

    click.echo(f"Sending report for email {email_id}...")

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
            email_id,
            email_data,
            analysis_result,
            lang,
        )

        click.echo(f"✓ Report sent successfully")
        click.echo(f"Results: {result['results']}")

    except Exception as e:
        click.echo(f"✗ Report failed: {e}", err=True)

@cli.command()
def stats():
    """Show system statistics"""
    db = SessionLocal()

    from sqlalchemy import func

    total = db.query(EmailModel).count()
    analyzed = db.query(EmailModel).filter(EmailModel.status == EmailStatus.ANALYZED).count()
    reported = db.query(EmailModel).filter(EmailModel.status == EmailStatus.REPORTED).count()
    avg_score = db.query(func.avg(EmailModel.score)).scalar() or 0

    click.echo("Traceo Statistics")
    click.echo("=" * 40)
    click.echo(f"Total Emails: {total}")
    click.echo(f"Analyzed: {analyzed}")
    click.echo(f"Reported: {reported}")
    click.echo(f"Pending: {total - analyzed}")
    click.echo(f"Average Score: {avg_score:.1f}/100")

@cli.command()
def health():
    """Check system health"""
    try:
        db = SessionLocal()
        db.execute("SELECT 1")
        click.echo("✓ Database: OK")

        click.echo("✓ System: Healthy")
    except Exception as e:
        click.echo(f"✗ System error: {e}", err=True)

if __name__ == "__main__":
    cli()
