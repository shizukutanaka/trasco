#!/usr/bin/env python
"""
Traceo CLI - Command-Line Interface
Administrative management tool for Traceo system.
"""

import click
import json
from datetime import datetime, timedelta
from sqlalchemy import func
from app.database import SessionLocal
from app.models import Email, EmailStatus, Report, ReportStatus
from app.user_profiles import UserProfile
from app.email_rules import EmailRule
from app.security import hash_password


@click.group()
def cli():
    """Traceo CLI - Email Phishing Detection System Management"""
    pass


@cli.group()
def user():
    """User management"""
    pass


@user.command()
@click.option('--username', prompt='Username')
@click.option('--email', prompt='Email')
@click.option('--password', prompt=True, hide_input=True)
def create(username, email, password):
    """Create new user"""
    db = SessionLocal()

    if db.query(UserProfile).filter_by(username=username).first():
        click.echo(click.style(f"User {username} already exists", fg='red'))
        return

    user_obj = UserProfile(username=username, email=email)
    db.add(user_obj)
    db.commit()
    click.echo(click.style(f"User {username} created", fg='green'))
    db.close()


@user.command()
def list():
    """List all users"""
    db = SessionLocal()
    users = db.query(UserProfile).all()

    for u in users:
        click.echo(f"{u.username} ({u.email})")

    db.close()


@cli.group()
def email():
    """Email management"""
    pass


@email.command()
def stats():
    """Email statistics"""
    db = SessionLocal()

    total = db.query(func.count(Email.id)).scalar()
    high_risk = db.query(func.count(Email.id)).filter(Email.score >= 60).scalar()
    avg_score = db.query(func.avg(Email.score)).scalar() or 0

    click.echo("\n📊 Email Statistics")
    click.echo("=" * 50)
    click.echo(f"Total emails: {total}")
    click.echo(f"High risk (60+): {high_risk}")
    click.echo(f"Average score: {avg_score:.2f}")
    click.echo("=" * 50)

    db.close()


@email.command()
@click.option('--days', default=90)
def cleanup(days):
    """Delete old emails"""
    if not click.confirm(f"Delete emails older than {days} days?"):
        return

    db = SessionLocal()
    cutoff = datetime.utcnow() - timedelta(days=days)
    deleted = db.query(Email).filter(Email.created_at < cutoff).delete()
    db.commit()

    click.echo(click.style(f"Deleted {deleted} emails", fg='green'))
    db.close()


@cli.group()
def analytics():
    """Analytics"""
    pass


@analytics.command()
def risklevels():
    """Risk level distribution"""
    db = SessionLocal()
    emails = db.query(Email.score).all()

    if not emails:
        click.echo("No emails")
        return

    critical = sum(1 for e in emails if e[0] >= 80)
    high = sum(1 for e in emails if 60 <= e[0] < 80)
    medium = sum(1 for e in emails if 40 <= e[0] < 60)
    low = sum(1 for e in emails if e[0] < 40)
    total = len(emails)

    click.echo("\n📈 Risk Distribution")
    click.echo("=" * 50)
    click.echo(f"Critical (80+): {critical}")
    click.echo(f"High (60-79): {high}")
    click.echo(f"Medium (40-59): {medium}")
    click.echo(f"Low (<40): {low}")
    click.echo(f"Total: {total}")
    click.echo("=" * 50)

    db.close()


@cli.group()
def system():
    """System operations"""
    pass


@system.command()
def status():
    """System status"""
    db = SessionLocal()

    try:
        db.execute("SELECT 1")
        db_status = "✅ Connected"
    except:
        db_status = "❌ Disconnected"

    emails = db.query(func.count(Email.id)).scalar()
    users = db.query(func.count(UserProfile.id)).scalar()
    rules = db.query(func.count(EmailRule.id)).scalar()

    click.echo("\n📊 System Status")
    click.echo("=" * 50)
    click.echo(f"Database: {db_status}")
    click.echo(f"Emails: {emails}")
    click.echo(f"Users: {users}")
    click.echo(f"Rules: {rules}")
    click.echo("=" * 50)

    db.close()


if __name__ == '__main__':
    cli()
