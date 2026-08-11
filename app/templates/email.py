"""
Email HTML and text templates for verification
"""

from typing import Tuple


def get_registration_template(code: str) -> Tuple[str, str, str]:
    """
    Returns (subject, text_content, html_content) for registration verification.
    """
    subject = "Verify your email - WattTipid"

    text_content = (
        f"Welcome to WattTipid!\n\n"
        f"Your verification code is: {code}\n\n"
        f"This code will expire in 5 minutes. If you did not request this, please ignore this email.\n"
    )

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333333;
                background-color: #f9f9f9;
                margin: 0;
                padding: 20px;
            }}
            .container {{
                max-width: 600px;
                margin: 0 auto;
                background-color: #ffffff;
                padding: 30px;
                border-radius: 8px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.05);
            }}
            .header {{
                text-align: center;
                border-bottom: 2px solid #eeeeee;
                padding-bottom: 20px;
                margin-bottom: 30px;
            }}
            .logo {{
                font-size: 24px;
                font-weight: bold;
                color: #2e7d32;
            }}
            .code-box {{
                font-size: 32px;
                font-weight: bold;
                text-align: center;
                letter-spacing: 5px;
                background-color: #f1f8e9;
                color: #2e7d32;
                padding: 15px;
                border-radius: 6px;
                margin: 30px 0;
                border: 1px dashed #a5d6a7;
            }}
            .footer {{
                margin-top: 30px;
                font-size: 12px;
                color: #777777;
                text-align: center;
                border-top: 1px solid #eeeeee;
                padding-top: 20px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <span class="logo">WattTipid</span>
            </div>
            <h2>Verify Your Email Address</h2>
            <p>Salamat sa pag-register sa WattTipid! Gamitin ang verification code sa ibaba para makumpleto ang iyong registration:</p>
            <div class="code-box">{code}</div>
            <p>Ang code na ito ay may bisa sa loob ng <strong>5 minuto</strong>. Kung hindi ikaw ang nag-request nito, maaari mo itong balewalain.</p>
            <div class="footer">
                &copy; 2026 WattTipid · Smart GenAI Energy Advisory
            </div>
        </div>
    </body>
    </html>
    """

    return subject, text_content, html_content


def get_email_change_template(code: str) -> Tuple[str, str, str]:
    """
    Returns (subject, text_content, html_content) for email change verification.
    """
    subject = "Verify your email change - WattTipid"

    text_content = (
        f"Confirm your email update on WattTipid.\n\n"
        f"Your verification code is: {code}\n\n"
        f"This code will expire in 5 minutes. If you did not request this, please change your password immediately.\n"
    )

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333333;
                background-color: #f9f9f9;
                margin: 0;
                padding: 20px;
            }}
            .container {{
                max-width: 600px;
                margin: 0 auto;
                background-color: #ffffff;
                padding: 30px;
                border-radius: 8px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.05);
            }}
            .header {{
                text-align: center;
                border-bottom: 2px solid #eeeeee;
                padding-bottom: 20px;
                margin-bottom: 30px;
            }}
            .logo {{
                font-size: 24px;
                font-weight: bold;
                color: #2e7d32;
            }}
            .code-box {{
                font-size: 32px;
                font-weight: bold;
                text-align: center;
                letter-spacing: 5px;
                background-color: #f1f8e9;
                color: #2e7d32;
                padding: 15px;
                border-radius: 6px;
                margin: 30px 0;
                border: 1px dashed #a5d6a7;
            }}
            .footer {{
                margin-top: 30px;
                font-size: 12px;
                color: #777777;
                text-align: center;
                border-top: 1px solid #eeeeee;
                padding-top: 20px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <span class="logo">WattTipid</span>
            </div>
            <h2>Verify Your Email Update</h2>
            <p>Upang palitan ang iyong WattTipid email address, gamitin ang verification code sa ibaba:</p>
            <div class="code-box">{code}</div>
            <p>Ang code na ito ay may bisa sa loob ng <strong>5 minuto</strong>. Kung hindi ikaw ang nag-request nito, mangyaring magpalit ng iyong password kaagad.</p>
            <div class="footer">
                &copy; 2026 WattTipid · Smart GenAI Energy Advisory
            </div>
        </div>
    </body>
    </html>
    """

    return subject, text_content, html_content


def get_contact_form_template(
    full_name: str, sender_email: str, message: str
) -> Tuple[str, str, str]:
    """
    Returns (subject, text_content, html_content) for incoming contact form submissions.
    """
    subject = f"[WattTipid Contact Form] Message from {full_name}"

    text_content = (
        f"New Contact Form Submission\n\n"
        f"Sender Name: {full_name}\n"
        f"Sender Email: {sender_email}\n\n"
        f"Message:\n{message}\n"
    )

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333333;
                background-color: #f9f9f9;
                margin: 0;
                padding: 20px;
            }}
            .container {{
                max-width: 600px;
                margin: 0 auto;
                background-color: #ffffff;
                padding: 30px;
                border-radius: 8px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.05);
            }}
            .header {{
                text-align: center;
                border-bottom: 2px solid #eeeeee;
                padding-bottom: 15px;
                margin-bottom: 20px;
            }}
            .logo {{
                font-size: 24px;
                font-weight: bold;
                color: #2e7d32;
            }}
            .field-label {{
                font-weight: bold;
                color: #555555;
                margin-top: 15px;
                font-size: 13px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }}
            .field-value {{
                font-size: 15px;
                color: #111111;
                margin-bottom: 10px;
            }}
            .message-box {{
                background-color: #f4f6f8;
                border-left: 4px solid #2e7d32;
                padding: 15px;
                margin-top: 10px;
                border-radius: 4px;
                white-space: pre-wrap;
                font-size: 14px;
            }}
            .footer {{
                margin-top: 30px;
                font-size: 12px;
                color: #777777;
                text-align: center;
                border-top: 1px solid #eeeeee;
                padding-top: 15px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <span class="logo">WattTipid</span>
                <p style="margin: 5px 0 0 0; font-size: 14px; color: #666666;">Incoming Contact Form Inquiry</p>
            </div>
            <div class="field-label">Sender Name</div>
            <div class="field-value">{full_name}</div>

            <div class="field-label">Sender Email</div>
            <div class="field-value"><a href="mailto:{sender_email}">{sender_email}</a></div>

            <div class="field-label">Message Content</div>
            <div class="message-box">{message}</div>

            <div class="footer">
                &copy; 2025 WattTipid · Sent to paulcorsino.work@gmail.com
            </div>
        </div>
    </body>
    </html>
    """

    return subject, text_content, html_content
