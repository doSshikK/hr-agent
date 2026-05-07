"""
app/utils/email_parser.py
Парсинг резюме из писем на почте
"""

import imaplib
import email
from email.header import decode_header
import time
import hashlib
from pathlib import Path
import tempfile
import os
import re

from app.core.config import settings
from app.core.logger import get_logger
from app.utils.file_parser import parse_resume
from app.db.candidate_db import save_candidate, add_to_notification_queue, is_candidate_already_in_queue

logger = get_logger(__name__)

EMAIL_HOST = settings.email_host
EMAIL_PORT = settings.email_port
EMAIL_USER = settings.email_user
EMAIL_PASSWORD = settings.email_password
CHECK_INTERVAL = 60  # проверять каждые 60 секунд


def connect_to_mailbox():
    """Подключается к почтовому ящику"""
    if not EMAIL_USER or not EMAIL_PASSWORD:
        logger.error("❌ Почта не настроена. Добавьте EMAIL_USER и EMAIL_PASSWORD в .env")
        return None
    
    try:
        mail = imaplib.IMAP4_SSL(EMAIL_HOST, EMAIL_PORT)
        mail.login(EMAIL_USER, EMAIL_PASSWORD)
        mail.select("INBOX")
        logger.info(f"📧 Подключено к почте {EMAIL_USER}")
        return mail
    except Exception as e:
        logger.error(f"❌ Ошибка подключения к почте: {e}")
        return None


def get_unseen_emails(mail):
    """Возвращает ID непрочитанных писем"""
    try:
        result, data = mail.search(None, "UNSEEN")
        if result != "OK":
            return []
        return data[0].split()
    except Exception as e:
        logger.error(f"Ошибка поиска писем: {e}")
        return []


def decode_mime_string(encoded_string):
    """Декодирует заголовки письма (тема, отправитель)"""
    if encoded_string is None:
        return ""
    decoded_parts = decode_header(encoded_string)
    result = ""
    for part, encoding in decoded_parts:
        if isinstance(part, bytes):
            if encoding:
                result += part.decode(encoding, errors="ignore")
            else:
                result += part.decode("utf-8", errors="ignore")
        else:
            result += str(part)
    return result


def get_sender_and_subject(mail, email_id):
    """Получает отправителя и тему письма"""
    try:
        result, data = mail.fetch(email_id, "(RFC822)")
        if result != "OK":
            return None, None
        
        raw_email = data[0][1]
        msg = email.message_from_bytes(raw_email)
        
        sender = decode_mime_string(msg.get("From"))
        subject = decode_mime_string(msg.get("Subject"))
        
        return sender, subject
    except Exception as e:
        logger.error(f"Ошибка получения отправителя: {e}")
        return None, None


def download_attachments(mail, email_id, temp_dir):
    """Скачивает вложения из письма"""
    try:
        result, data = mail.fetch(email_id, "(RFC822)")
        if result != "OK":
            return []
        
        raw_email = data[0][1]
        msg = email.message_from_bytes(raw_email)
        
        attachments = []
        
        if msg.is_multipart():
            for part in msg.walk():
                content_disposition = str(part.get("Content-Disposition"))
                filename = part.get_filename()
                
                if filename and ("attachment" in content_disposition or filename):
                    filename = decode_mime_string(filename)
                    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
                    ext = Path(filename).suffix.lower()
                    
                    if ext in ['.pdf', '.docx']:
                        filepath = os.path.join(temp_dir, filename)
                        with open(filepath, 'wb') as f:
                            f.write(part.get_payload(decode=True))
                        attachments.append(filepath)
                        logger.info(f"📎 Скачан файл: {filename}")
        
        return attachments
    except Exception as e:
        logger.error(f"Ошибка скачивания вложений: {e}")
        return []


def process_email(email_id):
    """Обрабатывает одно письмо: скачивает вложения, парсит, сохраняет"""
    mail = None
    try:
        mail = connect_to_mailbox()
        if not mail:
            logger.error("Не удалось подключиться к почте")
            return
        
        sender, subject = get_sender_and_subject(mail, email_id)
        logger.info(f"📧 Обработка письма от {sender}, тема: {subject}")
        
        if "security@id.mail.ru" in str(sender) or "noreply" in str(sender):
            logger.info(f"⏭️ Пропускаем служебное письмо")
            mail.store(email_id, '+FLAGS', '\\Seen')
            return
        
        with tempfile.TemporaryDirectory() as temp_dir:
            attachments = download_attachments(mail, email_id, temp_dir)
            
            if not attachments:
                logger.warning(f"Нет вложений PDF/DOCX в письме от {sender}")
                mail.store(email_id, '+FLAGS', '\\Seen')
                return
            
            for filepath in attachments:
                parsed = parse_resume(filepath)
                
                if "error" in parsed:
                    logger.error(f"Ошибка парсинга: {parsed['error']}")
                    continue
                
                parsed['source'] = 'email'
                
                candidate_id = save_candidate(parsed, filepath)
                candidate_name = parsed.get('name', 'Не указано')
                last_position = parsed.get('last_position', '')
                
                logger.info(f"✅ Сохранён кандидат из письма: ID={candidate_id}, имя={candidate_name}, source=email")
                
                if not is_candidate_already_in_queue(candidate_id):
                    add_to_notification_queue(candidate_id, candidate_name, last_position)
                    logger.info(f"📨 Кандидат {candidate_id} добавлен в очередь уведомлений")
                else:
                    logger.info(f"⏭️ Кандидат {candidate_id} уже есть в очереди, пропускаем")
                
                try:
                    os.unlink(filepath)
                except:
                    pass
        
        mail.store(email_id, '+FLAGS', '\\Seen')
        
    except Exception as e:
        logger.error(f"Ошибка обработки письма {email_id}: {e}")
    finally:
        if mail:
            try:
                mail.close()
                mail.logout()
            except:
                pass


def check_emails_once():
    """Однократная проверка почты (для ручного вызова)"""
    logger.info("📧 Проверка почты...")
    mail = connect_to_mailbox()
    if not mail:
        return
    
    try:
        unseen_ids = get_unseen_emails(mail)
        logger.info(f"📬 Найдено непрочитанных писем: {len(unseen_ids)}")
        
        for email_id in unseen_ids:
            process_email(email_id)
    except Exception as e:
        logger.error(f"Ошибка при проверке почты: {e}")
    finally:
        try:
            mail.close()
            mail.logout()
        except:
            pass


def check_emails_loop():
    """Бесконечный цикл проверки почты"""
    CHECK_INTERVAL = 300
    
    logger.info(f"📧 Запущен мониторинг почты {EMAIL_USER}, проверка каждые {CHECK_INTERVAL} сек")
    
    while True:
        try:
            mail = connect_to_mailbox()
            if not mail:
                logger.warning("Не удалось подключиться к почте, повтор через 30 секунд")
                time.sleep(30)
                continue
            
            unseen_ids = get_unseen_emails(mail)
            
            if unseen_ids:
                logger.info(f"📬 Найдено новых писем: {len(unseen_ids)}")
            
            for email_id in unseen_ids:
                process_email(email_id)
            
            try:
                mail.close()
                mail.logout()
            except:
                pass
            
        except Exception as e:
            logger.error(f"Ошибка при проверке почты: {e}")
        
        time.sleep(CHECK_INTERVAL)


def start_email_monitoring():
    """Запускает мониторинг почты в отдельном потоке"""
    if not EMAIL_USER or not EMAIL_PASSWORD:
        logger.warning("⚠️ Почта не настроена. Мониторинг не запущен.")
        return False
    
    import threading
    thread = threading.Thread(target=check_emails_loop, daemon=True)
    thread.start()
    logger.info("📧 Мониторинг почты запущен в фоновом потоке")
    return True


def stop_email_monitoring():
    """Останавливает мониторинг почты (при завершении приложения)"""
    logger.info("📧 Мониторинг почты остановлен")


if __name__ == "__main__":
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ ПАРСЕРА ПОЧТЫ")
    print("=" * 60)
    
    if not EMAIL_USER or not EMAIL_PASSWORD:
        print("❌ Настройки почты не заданы в .env")
        print("   Добавьте: EMAIL_USER, EMAIL_PASSWORD")
    else:
        print(f"📧 Почта: {EMAIL_USER}")
        print(f"📧 Хост: {EMAIL_HOST}:{EMAIL_PORT}")
        print("\n🔄 Проверяем почту...")
        check_emails_once()
        print("\n✅ Готово!")
