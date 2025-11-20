#!/usr/bin/env python3
"""
Generate demo/test data for Traceo

Usage:
    python scripts/generate_demo_data.py

This script creates sample emails in the database for testing purposes.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import hashlib
import random

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.database import SessionLocal, init_db
from app.models import Email as EmailModel, EmailStatus


# Sample phishing emails
DEMO_EMAILS = [
    {
        "subject": "【重要】アカウント検証 - 即座の対応が必要です",
        "from_addr": "verify@account-security.top",
        "body": """
            お客様のアカウントが侵害された可能性があります。
            直ちに以下のリンクからアカウントを確認してください。

            確認期間: 24時間以内

            https://verify-account.top/security/confirm
        """,
        "urls": ["https://verify-account.top/security/confirm"],
        "score": 88,
    },
    {
        "subject": "PayPal Security Alert: Confirm Your Account",
        "from_addr": "noreply@paypal-secure.click",
        "body": """
            Dear PayPal User,

            We detected unusual activity on your account.
            Please verify your identity immediately:

            Click: https://paypal-confirm.click/login

            Your account will be limited if not verified within 24 hours.
        """,
        "urls": ["https://paypal-confirm.click/login"],
        "score": 92,
    },
    {
        "subject": "【Amazon】緊急: お客様のアカウントが制限されました",
        "from_addr": "security@amazon-alerts.win",
        "body": """
            お客様のAmazonアカウントが一時的に制限されました。

            理由: 支払い情報の確認

            こちらをクリックして確認してください:
            https://amazon-account.win/verify
        """,
        "urls": ["https://amazon-account.win/verify"],
        "score": 85,
    },
    {
        "subject": "Your Bank Account Needs Attention",
        "from_addr": "alerts@banking-service.stream",
        "body": """
            Due to suspicious activity, we need to verify your account.

            Please update your information:
            https://bank-verify.stream/secure/login

            This is time-sensitive. Please act within 12 hours.
        """,
        "urls": ["https://bank-verify.stream/secure/login"],
        "score": 90,
    },
    {
        "subject": "【楽天】会員情報の更新が必要です",
        "from_addr": "noreply@rakuten-members.download",
        "body": """
            楽天会員の皆様へ

            セキュリティ向上のため、会員情報の更新をお願いします。

            更新手続き: https://rakuten-member.download/update
        """,
        "urls": ["https://rakuten-member.download/update"],
        "score": 80,
    },
    {
        "subject": "LinkedIn: Verify Your Password",
        "from_addr": "security@linkedin-verify.xyz",
        "body": """
            LinkedIn Security Notice

            Please verify your password for your LinkedIn account.

            Verify: https://linkedin-secure.xyz/confirm-password

            Keep your account safe.
        """,
        "urls": ["https://linkedin-secure.xyz/confirm-password"],
        "score": 75,
    },
    {
        "subject": "【Apple ID】サインインできませんでした",
        "from_addr": "noreply@apple-id-security.review",
        "body": """
            Apple ID のサインインに失敗しました。

            セキュリティのため、パスワードをリセットしてください:
            https://apple-id-reset.review/security
        """,
        "urls": ["https://apple-id-reset.review/security"],
        "score": 83,
    },
    {
        "subject": "Microsoft Account: Suspicious Activity",
        "from_addr": "security@microsoft-verify.review",
        "body": """
            We detected suspicious login attempts on your Microsoft account.

            Review activity: https://microsoft-account.review/security

            Secure your account now.
        """,
        "urls": ["https://microsoft-account.review/security"],
        "score": 87,
    },
    {
        "subject": "会員ID確認 - ご対応ください",
        "from_addr": "support@member-verify.download",
        "body": """
            いつもご利用ありがとうございます。

            会員ID確認のため、こちらから情報を更新してください:
            https://member-verify.download/confirm-id
        """,
        "urls": ["https://member-verify.download/confirm-id"],
        "score": 78,
    },
    {
        "subject": "Confirm Your Email Address",
        "from_addr": "verify@email-confirm.info",
        "body": """
            Please confirm your email address to keep your account active.

            Confirm email: https://email-confirm.info/verify-email

            If not completed within 24 hours, your account may be suspended.
        """,
        "urls": ["https://email-confirm.info/verify-email"],
        "score": 82,
    },
]

# Legitimate emails
LEGITIMATE_EMAILS = [
    {
        "subject": "Welcome to Traceo",
        "from_addr": "hello@traceo.org",
        "body": """
            Welcome to Traceo!

            We're glad you're using our email security platform.

            Website: https://traceo.org
            Documentation: https://traceo.org/docs
        """,
        "urls": ["https://traceo.org", "https://traceo.org/docs"],
        "score": 5,
    },
    {
        "subject": "Your GitHub Repository is Ready",
        "from_addr": "noreply@github.com",
        "body": """
            Your new repository has been created successfully.

            View: https://github.com/traceo-org/traceo

            Happy coding!
        """,
        "urls": ["https://github.com/traceo-org/traceo"],
        "score": 3,
    },
    {
        "subject": "Meeting Tomorrow at 10 AM",
        "from_addr": "organizer@company.com",
        "body": """
            Hi,

            Reminder: We have a team meeting tomorrow at 10 AM.

            Location: Conference Room B

            See you there!
        """,
        "urls": [],
        "score": 2,
    },
]


def generate_demo_data(count: int = 5):
    """Generate demo phishing and legitimate emails"""
    db = SessionLocal()

    try:
        print(f"Generating {count} demo emails...")

        # Mix of phishing and legitimate emails
        emails = []
        for i in range(count):
            if i % 2 == 0 and len(DEMO_EMAILS) > i // 2:
                # Phishing email
                sample = DEMO_EMAILS[i // 2 % len(DEMO_EMAILS)]
            else:
                # Legitimate email
                sample = LEGITIMATE_EMAILS[i % len(LEGITIMATE_EMAILS)]

            # Create email ID
            email_id = hashlib.md5(
                (sample["from_addr"] + sample["subject"] + str(i)).encode()
            ).hexdigest()

            # Randomize received date within last 7 days
            days_ago = random.randint(0, 7)
            received_date = datetime.utcnow() - timedelta(days=days_ago)

            email = EmailModel(
                id=email_id,
                from_addr=sample["from_addr"],
                to_addrs=["user@example.com"],
                subject=sample["subject"],
                received_date=received_date,
                score=sample["score"],
                status=EmailStatus.ANALYZED,
                raw_headers="",
                body=sample["body"],
                urls=sample["urls"],
                analyzed_at=datetime.utcnow(),
                domain_info={
                    "domain": sample["urls"][0].split("://")[1].split("/")[0]
                    if sample["urls"]
                    else "unknown",
                    "registrar": "Example Registrar",
                    "status": "success",
                },
            )

            emails.append(email)
            db.add(email)

        db.commit()
        print(f"✓ Generated {len(emails)} demo emails")

        # Print statistics
        print("\nDemo Email Statistics:")
        print(f"  High Risk (80+):    {sum(1 for e in emails if e.score >= 80)}")
        print(f"  Medium Risk (50-79): {sum(1 for e in emails if 50 <= e.score < 80)}")
        print(f"  Low Risk (<50):      {sum(1 for e in emails if e.score < 50)}")

        print("\nAccess the dashboard:")
        print("  Frontend: http://localhost:3000")
        print("  API:      http://localhost:8000/emails")

    except Exception as e:
        print(f"✗ Error: {e}")
        db.rollback()
    finally:
        db.close()


def main():
    """Main function"""
    import argparse

    parser = argparse.ArgumentParser(description="Generate demo data for Traceo")
    parser.add_argument(
        "--count", type=int, default=10, help="Number of emails to generate"
    )
    parser.add_argument(
        "--clean", action="store_true", help="Delete existing demo data first"
    )

    args = parser.parse_args()

    print("Traceo Demo Data Generator")
    print("=" * 40)
    print()

    # Initialize database
    try:
        init_db()
        print("✓ Database initialized")
    except Exception as e:
        print(f"✗ Database error: {e}")
        return

    # Clean existing data if requested
    if args.clean:
        print("Deleting existing demo data...")
        db = SessionLocal()
        db.query(EmailModel).delete()
        db.commit()
        db.close()
        print("✓ Existing data deleted")

    # Generate new data
    print()
    generate_demo_data(args.count)
    print()


if __name__ == "__main__":
    main()
