import smtplib
from email.message import EmailMessage
from email.utils import formataddr, parseaddr
from pathlib import Path

import config


APP_URL = config.FRONTEND_APP_URL


def _sender_header():
    name, address = parseaddr(config.SMTP_FROM)
    if not address:
        return config.SMTP_USER
    return formataddr((name or "Educator Tools", address))


def _logo_bytes():
    email_logo = Path(__file__).resolve().parent / "email_logo.png"
    if email_logo.exists():
        return email_logo.read_bytes(), "png", "educator-tools-logo.png"

    source_logo = Path(__file__).resolve().parents[1] / "frontend" / "dist" / "assets"
    candidates = list(source_logo.glob("logo-*.svg"))
    if candidates:
        return candidates[0].read_bytes(), "svg+xml", "educator-tools-logo.svg"

    fallback_logo = Path(__file__).resolve().parents[1] / "frontend" / "dist" / "favicon.svg"
    if fallback_logo.exists():
        return fallback_logo.read_bytes(), "svg+xml", "educator-tools-logo.svg"

    repo_logo = Path(__file__).resolve().parents[1] / "frontend" / "src" / "assets" / "logo.svg"
    if repo_logo.exists():
        return repo_logo.read_bytes(), "svg+xml", "educator-tools-logo.svg"

    return None


def _email_shell(title: str, preheader: str, content: str):
    return f"""<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
  </head>
  <body style="margin:0;padding:0;background:#f1f5f9;font-family:Arial,Helvetica,sans-serif;color:#0f172a;">
    <div style="display:none;max-height:0;overflow:hidden;color:transparent;">{preheader}</div>
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f1f5f9;padding:24px 12px;">
      <tr>
        <td align="center">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:620px;background:#ffffff;border:1px solid #e2e8f0;border-radius:14px;overflow:hidden;">
            <tr>
              <td style="padding:24px 26px;border-bottom:1px solid #e2e8f0;">
                <table role="presentation" cellspacing="0" cellpadding="0">
                  <tr>
                    <td style="vertical-align:middle;padding-right:12px;">
                      <img src="cid:educator-tools-logo" width="42" height="42" alt="EducatorTools logo" style="display:block;border-radius:10px;">
                    </td>
                    <td style="vertical-align:middle;">
                      <div style="font-size:24px;font-weight:800;letter-spacing:-0.4px;color:#0f172a;">Educator<span style="color:#16a34a;">Tools</span></div>
                      <div style="font-size:13px;color:#64748b;margin-top:3px;">PDF to Word tools for South African educators</div>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
            <tr>
              <td style="padding:28px 26px;">
                <h1 style="margin:0 0 14px 0;font-size:24px;line-height:1.25;color:#0f172a;">{title}</h1>
                {content}
              </td>
            </tr>
            <tr>
              <td style="padding:18px 26px;background:#f8fafc;border-top:1px solid #e2e8f0;font-size:12px;line-height:1.5;color:#64748b;">
                EducatorTools processes documents temporarily and deletes conversion files after download.
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""


def send_email(to_email: str, subject: str, body: str, html_body: str | None = None) -> bool:
    if not config.SMTP_HOST or not config.SMTP_USER or not config.SMTP_PASSWORD:
        print("Email not sent: SMTP configuration is incomplete.")
        return False

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = _sender_header()
    message["To"] = to_email
    message.set_content(body)
    if html_body:
        message.add_alternative(html_body, subtype="html")
        logo = _logo_bytes()
        if logo:
            logo_bytes, subtype, filename = logo
            html_part = message.get_payload()[-1]
            html_part.add_related(
                logo_bytes,
                maintype="image",
                subtype=subtype,
                cid="<educator-tools-logo>",
                filename=filename,
            )

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

How to continue:
1. Go back to EducatorTools.
2. Enter this 6-digit code on the verification screen.
3. Sign in and use your free trial conversions.
4. When you need more conversion credits, click "Email Me Credit Details" in your dashboard.

If you did not create this account, you can ignore this email.
"""
    html_body = _email_shell(
        "Verify your email",
        "Enter your EducatorTools verification code.",
        f"""
        <p style="margin:0 0 18px 0;font-size:15px;line-height:1.6;color:#334155;">Use this code to confirm your email address and finish setting up your account.</p>
        <div style="margin:22px 0;padding:18px 20px;background:#f0f9ff;border:1px solid #bae6fd;border-radius:10px;text-align:center;">
          <div style="font-size:13px;text-transform:uppercase;letter-spacing:1.2px;color:#0369a1;font-weight:700;">Verification Code</div>
          <div style="font-size:34px;letter-spacing:7px;font-weight:800;color:#0f172a;margin-top:8px;">{code}</div>
          <div style="font-size:13px;color:#64748b;margin-top:8px;">Expires in 15 minutes</div>
        </div>
        <h2 style="margin:22px 0 10px 0;font-size:17px;color:#0f172a;">What to do next</h2>
        <ol style="margin:0 0 18px 20px;padding:0;font-size:15px;line-height:1.7;color:#334155;">
          <li>Return to <a href="{APP_URL}" style="color:#0284c7;font-weight:700;">EducatorTools</a>.</li>
          <li>Enter the code on the verification screen.</li>
          <li>Sign in and use your free trial conversions.</li>
          <li>When you need more conversion credits, click <strong>Email Me Credit Details</strong> in your dashboard.</li>
        </ol>
        <p style="margin:0;font-size:13px;line-height:1.5;color:#64748b;">If you did not create this account, you can ignore this email.</p>
        """,
    )
    return send_email(to_email, "Verify your EducatorTools email", body, html_body)


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

After sending proof of payment:
1. Wait for administrator approval.
2. Go back to EducatorTools and sign in.
3. Your account will be active once approved.
"""
    package_cards = "".join(
        f"""
        <tr>
          <td style="padding:14px 16px;border:1px solid #e2e8f0;border-radius:10px;background:#ffffff;">
            <div style="font-size:16px;font-weight:800;color:#0f172a;">{item['name']}</div>
            <div style="font-size:14px;color:#334155;margin-top:4px;"><strong>R{item['price_zar']}</strong> / {item['billing_period']}</div>
            <div style="font-size:13px;color:#64748b;margin-top:4px;">{item['monthly_pages']} conversion pages</div>
          </td>
        </tr>
        <tr><td style="height:10px;"></td></tr>
        """
        for item in config.PACKAGES
    )
    html_body = _email_shell(
        "Conversion credit details",
        "Choose a page package, pay by EFT, then reply with proof of payment.",
        f"""
        <p style="margin:0 0 18px 0;font-size:15px;line-height:1.6;color:#334155;">Choose the page package that fits your monthly conversion needs.</p>
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border-collapse:separate;border-spacing:0;">{package_cards}</table>
        <h2 style="margin:22px 0 10px 0;font-size:17px;color:#0f172a;">EFT banking details</h2>
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:12px 14px;font-size:14px;line-height:1.8;color:#334155;">
          <tr><td style="font-weight:700;">Bank Name</td><td>{config.BANK_NAME}</td></tr>
          <tr><td style="font-weight:700;">Account Number</td><td>{config.BANK_ACCOUNT_NUMBER}</td></tr>
          <tr><td style="font-weight:700;">Branch Code</td><td>{config.BANK_BRANCH_CODE}</td></tr>
          <tr><td style="font-weight:700;">Account Type</td><td>{config.BANK_ACCOUNT_TYPE}</td></tr>
          <tr><td style="font-weight:700;">Reference</td><td>Your registered email address</td></tr>
        </table>
        <h2 style="margin:22px 0 10px 0;font-size:17px;color:#0f172a;">How activation works</h2>
        <ol style="margin:0 0 18px 20px;padding:0;font-size:15px;line-height:1.7;color:#334155;">
          <li>Pay by EFT using your registered email address as the reference.</li>
          <li>Reply to this email with proof of payment.</li>
          <li>You may attach a screenshot/photo of the payment confirmation or forward the bank payment confirmation email.</li>
          <li>Wait for administrator approval.</li>
          <li>Go back to <a href="{APP_URL}" style="color:#0284c7;font-weight:700;">EducatorTools</a> and sign in. Your account will be active once approved.</li>
        </ol>
        <p style="margin:0;font-size:13px;line-height:1.5;color:#64748b;">Need help? Reply to this email and we will assist.</p>
        """,
    )
    return send_email(to_email, "EducatorTools conversion credit details", body, html_body)


def notify_admin_new_registration(user_email: str, profession: str) -> bool:
    body = f"""A new EducatorTools account was registered.

Email: {user_email}
Profession: {profession}

The user must verify their email before signing in. After trial usage, activate them from the admin dashboard once payment is confirmed.
"""
    html_body = _email_shell(
        "New educator registration",
        "A new EducatorTools account has been created.",
        f"""
        <p style="margin:0 0 16px 0;font-size:15px;line-height:1.6;color:#334155;">A new educator account was registered.</p>
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:12px 14px;font-size:14px;line-height:1.8;color:#334155;">
          <tr><td style="font-weight:700;">Email</td><td>{user_email}</td></tr>
          <tr><td style="font-weight:700;">Profession</td><td>{profession}</td></tr>
        </table>
        <p style="margin:16px 0 0 0;font-size:14px;line-height:1.6;color:#64748b;">The user must verify their email before signing in. Activate them from the admin dashboard once proof of payment has been confirmed.</p>
        """,
    )
    return send_email(config.ADMIN_EMAIL, "New EducatorTools registration", body, html_body)
