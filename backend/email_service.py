import smtplib
from email.message import EmailMessage
from email.utils import formataddr, parseaddr

import config


def _sender_header():
    name, address = parseaddr(config.SMTP_FROM)
    if not address:
        return config.SMTP_USER
    return formataddr((name or "Educator Tools", address))


def send_email(to_email: str, subject: str, body: str) -> bool:
    if not config.SMTP_HOST or not config.SMTP_USER or not config.SMTP_PASSWORD:
        print("Email not sent: SMTP configuration is incomplete.")
        return False

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = _sender_header()
    message["To"] = to_email
    message.set_content(body)

    if config.SMTP_SECURE:
        server = smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT, timeout=20)
    else:
        server = smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=20)

    try:
        if not config.SMTP_SECURE:
            server.starttls()
        server.login(config.SMTP_USER, config.SMTP_PASSWORD)
        server.send_message(message)
        return True
    except Exception as exc:
        print(f"Email send failed: {exc}")
        return False
    finally:
        server.quit()


def send_verification_code(to_email: str, code: str) -> bool:
    body = f"""Welcome to EducatorTools.

Your email verification code is: {code}

This code expires in 15 minutes.

If you did not create this account, you can ignore this email.
"""
    return send_email(to_email, "Verify your EducatorTools email", body)


def send_credit_details(to_email: str) -> bool:
    package_lines = "\n".join(
        f"- {item['name']}: R{item['price_zar']}/{item['billing_period']} "
        f"for {item['monthly_pages']} pages"
        for item in config.PACKAGES
    )
    body = f"""EducatorTools conversion credit details

Available page packages:
{package_lines}

EFT banking details:
Bank Name: {config.BANK_NAME}
Account Number: {config.BANK_ACCOUNT_NUMBER}
Branch Code: {config.BANK_BRANCH_CODE}
Account Type: {config.BANK_ACCOUNT_TYPE}
Reference: Your registered email address

To activate or top up your account, please reply to this email with proof of payment.
You can attach a screenshot/photo of the payment confirmation or forward the bank payment confirmation email.
Keep your registered email address as the payment reference so we can match it quickly.
"""
    return send_email(to_email, "EducatorTools conversion credit details", body)


def notify_admin_new_registration(user_email: str, profession: str) -> bool:
    body = f"""A new EducatorTools account was registered.

Email: {user_email}
Profession: {profession}

The user must verify their email before signing in. After trial usage, activate them from the admin dashboard once payment is confirmed.
"""
    return send_email(config.ADMIN_EMAIL, "New EducatorTools registration", body)
