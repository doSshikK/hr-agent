"""
app/utils/email_sender.py
Отправка писем кандидатам (приглашения на собеседование, офферы, онбординг)
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

HR_PHONE = "+7 950 722-25-70"


def _candidate_bot_link(bot_username: str = None, candidate_id: int = None) -> str:
    """Возвращает универсальную ссылку кандидата в Telegram-бот."""
    if bot_username and candidate_id:
        return f"https://t.me/{bot_username}?start=candidate_{candidate_id}"
    return ""


def send_email(
    to_email: str,
    subject: str,
    html_content: str,
    text_content: str = None
) -> bool:
    """Отправляет email через SMTP"""
    
    if not settings.smtp_user or not settings.smtp_password:
        logger.warning("⚠️ SMTP не настроен. Добавьте SMTP_USER и SMTP_PASSWORD в .env")
        return False
    
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.smtp_user
        msg["To"] = to_email
        
        if text_content:
            part_text = MIMEText(text_content, "plain", "utf-8")
            msg.attach(part_text)
        
        part_html = MIMEText(html_content, "html", "utf-8")
        msg.attach(part_html)
        
        with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port) as server:
            server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(settings.smtp_user, to_email, msg.as_string())
        
        logger.info(f"✅ Письмо отправлено на {to_email}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка отправки письма: {e}")
        return False


def send_interview_invite_email(
    to_email: str,
    candidate_name: str,
    position: str = None,
    bot_username: str = None,
    candidate_id: int = None
) -> bool:
    """Отправляет приглашение на собеседование по email"""
    
    position_text = f" на должность {position}" if position else ""
    bot_link = _candidate_bot_link(bot_username, candidate_id)
    bot_link_html = (
        f"""
                <p><b>1. Через Telegram-бота:</b></p>
                <p><a href="{bot_link}" class="button">Выбрать время в Telegram</a></p>
        """
        if bot_link else ""
    )
    bot_link_text = f"1. Через Telegram-бота: {bot_link}\n" if bot_link else ""
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: #2c3e50; color: white; padding: 20px; text-align: center; }}
            .content {{ padding: 20px; }}
            .button {{ background: #3498db; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block; }}
            .footer {{ font-size: 12px; color: #777; text-align: center; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2>📅 Приглашение на собеседование</h2>
            </div>
            <div class="content">
                <p>Здравствуйте, <b>{candidate_name}</b>!</p>
                <p>Нам понравилось ваше резюме, и мы хотели бы пригласить вас на собеседование{position_text}.</p>
                <p><b>Вы можете выбрать удобный способ записи:</b></p>
                {bot_link_html}
                <p><b>{'2' if bot_link else '1'}. Ответным письмом:</b><br/>
                Напишите 2-3 удобных варианта даты и времени, и HR подтвердит запись.</p>
                <p><b>{'3' if bot_link else '2'}. По телефону HR:</b><br/>
                {HR_PHONE}</p>
                <p>С уважением,<br/>Команда HR</p>
            </div>
            <div class="footer">
                <p>Это автоматическое сообщение. Вы можете ответить на него, если хотите согласовать время вручную.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    text = f"""
Приглашение на собеседование

Здравствуйте, {candidate_name}!

Нам понравилось ваше резюме, и мы хотели бы пригласить вас на собеседование{position_text}.

Вы можете выбрать удобный способ записи:
{bot_link_text}{'2' if bot_link else '1'}. Ответным письмом: напишите 2-3 удобных варианта даты и времени.
{'3' if bot_link else '2'}. По телефону HR: {HR_PHONE}

С уважением, Команда HR
    """
    
    subject = f"Приглашение на собеседование{position_text}"
    return send_email(to_email, subject, html, text)


def send_offer_email(
    to_email: str,
    candidate_name: str,
    position: str,
    salary: int,
    bot_username: str = None,
    candidate_id: int = None
) -> bool:
    """Отправляет предложение работы по email"""

    bot_link = _candidate_bot_link(bot_username, candidate_id)
    bot_link_html = (
        f"""
                <p><b>1. Через Telegram-бота:</b></p>
                <p><a href="{bot_link}" class="button">Подтвердить в Telegram</a></p>
        """
        if bot_link else ""
    )
    bot_link_text = f"1. Через Telegram-бота: {bot_link}\n" if bot_link else ""
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: #27ae60; color: white; padding: 20px; text-align: center; }}
            .content {{ padding: 20px; }}
            .offer {{ background: #f9f9f9; padding: 15px; border-radius: 5px; margin: 15px 0; }}
            .button {{ background: #0088cc; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block; }}
            .footer {{ font-size: 12px; color: #777; text-align: center; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2>🎉 Предложение о работе!</h2>
            </div>
            <div class="content">
                <p>Здравствуйте, <b>{candidate_name}</b>!</p>
                <p>Мы рады предложить вам должность в нашей компании:</p>
                <div class="offer">
                    <p><b>🎯 Должность:</b> {position}</p>
                    <p><b>💰 Заработная плата:</b> {salary:,} руб.</p>
                </div>
                <p><b>Подтвердить решение можно одним из способов:</b></p>
                {bot_link_html}
                <p><b>{'2' if bot_link else '1'}. Ответным письмом:</b><br/>
                Напишите, принимаете ли вы предложение, и укажите удобную дату выхода.</p>
                <p><b>{'3' if bot_link else '2'}. По телефону HR:</b><br/>
                {HR_PHONE}</p>
                <p>С нетерпением ждём вас в нашей команде!</p>
                <p>С уважением,<br/>Команда HR</p>
            </div>
            <div class="footer">
                <p>Это автоматическое сообщение. Вы можете ответить на него, чтобы подтвердить решение вручную.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    text = f"""
Предложение о работе

Здравствуйте, {candidate_name}!

Мы рады предложить вам должность в нашей компании:

Должность: {position}
Заработная плата: {salary:,} руб.

Подтвердить решение можно:
{bot_link_text}{'2' if bot_link else '1'}. Ответным письмом: напишите, принимаете ли вы предложение, и укажите удобную дату выхода.
{'3' if bot_link else '2'}. По телефону HR: {HR_PHONE}

С уважением, Команда HR
    """
    
    subject = f"Предложение о работе: {position}"
    return send_email(to_email, subject, html, text)


def send_offer_with_onboarding_link(
    to_email: str,
    candidate_name: str,
    position: str,
    salary: int,
    bot_username: str,
    candidate_id: int
) -> bool:
    """
    Отправляет предложение работы с ссылкой на Telegram бота для прохождения онбординга
    """
    
    bot_link = _candidate_bot_link(bot_username, candidate_id)
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: #27ae60; color: white; padding: 20px; text-align: center; }}
            .content {{ padding: 20px; }}
            .offer {{ background: #f9f9f9; padding: 15px; border-radius: 5px; margin: 15px 0; }}
            .button {{
                background: #0088cc;
                color: white;
                padding: 12px 24px;
                text-decoration: none;
                border-radius: 5px;
                display: inline-block;
                margin: 15px 0;
                font-weight: bold;
            }}
            .button:hover {{ background: #006699; }}
            .footer {{ font-size: 12px; color: #777; text-align: center; margin-top: 20px; }}
            .steps {{
                background: #f0f0f0;
                padding: 15px;
                border-radius: 5px;
                margin: 15px 0;
            }}
            .steps ol {{ margin: 10px 0 10px 20px; }}
            .steps li {{ margin: 8px 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2>🎉 Поздравляем! Вы приняты на работу!</h2>
            </div>
            <div class="content">
                <p>Здравствуйте, <b>{candidate_name}</b>!</p>
                <p>Мы рады официально предложить вам должность в нашей компании:</p>
                <div class="offer">
                    <p><b>🎯 Должность:</b> {position}</p>
                    <p><b>💰 Заработная плата:</b> {salary:,} руб.</p>
                </div>
                
                <p><b>📋 Как подтвердить предложение?</b></p>
                <div class="steps">
                    <ol>
                        <li>Перейдите в Telegram-бота по кнопке ниже и подтвердите предложение</li>
                        <li>Выберите удобную дату выхода на работу</li>
                        <li>Получите персонализированный план онбординга</li>
                    </ol>
                </div>
                
                <div style="text-align: center;">
                    <a href="{bot_link}" class="button">🤖 Перейти в Telegram-бота</a>
                </div>
                
                <p style="font-size: 14px; margin-top: 20px;">
                    <b>Если Telegram неудобен:</b><br/>
                    Ответьте на это письмо: напишите, принимаете ли вы предложение, и укажите удобную дату выхода.<br/>
                    Также можно позвонить HR: {HR_PHONE}.
                </p>
                
                <p>С нетерпением ждём вас в нашей команде!</p>
                <p>С уважением,<br/>Команда HR</p>
            </div>
            <div class="footer">
                <p>Это автоматическое сообщение. Вы можете ответить на него, чтобы подтвердить решение вручную.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    text = f"""
🎉 ПОЗДРАВЛЯЕМ! ВЫ ПРИНЯТЫ НА РАБОТУ!

Должность: {position}
Зарплата: {salary:,} руб.

ЧТО ДАЛЬШЕ?

Подтвердить решение можно одним из способов:

1. Через Telegram-бота:
{bot_link}

2. Ответным письмом:
Напишите, принимаете ли вы предложение, и укажите удобную дату выхода.

3. По телефону HR:
{HR_PHONE}

С уважением, Команда HR
    """
    
    subject = f"🎉 Поздравляем! Вы приняты на работу: {position}"
    return send_email(to_email, subject, html, text)


def send_onboarding_start_email(
    to_email: str,
    candidate_name: str,
    bot_username: str,
    candidate_id: int
) -> bool:
    """
    Отправляет письмо со ссылкой на начало онбординга
    """
    
    bot_link = f"https://t.me/{bot_username}?start=onboarding_{candidate_id}"
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: #3498db; color: white; padding: 20px; text-align: center; }}
            .content {{ padding: 20px; }}
            .button {{
                background: #0088cc;
                color: white;
                padding: 12px 24px;
                text-decoration: none;
                border-radius: 5px;
                display: inline-block;
                margin: 15px 0;
                font-weight: bold;
            }}
            .footer {{ font-size: 12px; color: #777; text-align: center; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2>📋 Начало онбординга</h2>
            </div>
            <div class="content">
                <p>Здравствуйте, <b>{candidate_name}</b>!</p>
                <p>Ваш план адаптации готов. Для начала онбординга перейдите в Telegram-бота:</p>
                
                <div style="text-align: center;">
                    <a href="{bot_link}" class="button">🚀 Начать онбординг</a>
                </div>
                
                <p>В боте вас ждёт:</p>
                <ul>
                    <li>📋 Чек-лист задач на первую неделю</li>
                    <li>📅 Расписание встреч с командой</li>
                    <li>💡 Подробные инструкции по каждой задаче</li>
                    <li>⏰ Напоминания о дедлайнах</li>
                    <li>❓ Ответы на частые вопросы</li>
                </ul>
                
                <p>Добро пожаловать в команду! 🎉</p>
            </div>
            <div class="footer">
                <p>Если у вас возникли вопросы — напишите нам в Telegram или по email.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    text = f"""
НАЧАЛО ОНБОРДИНГА

Здравствуйте, {candidate_name}!

Ваш план адаптации готов. Для начала онбординга перейдите по ссылке:
{bot_link}

В боте вас ждёт чек-лист задач, расписание встреч и подробные инструкции.

Добро пожаловать в команду!
    """
    
    subject = "📋 Начало онбординга"
    return send_email(to_email, subject, html, text)
