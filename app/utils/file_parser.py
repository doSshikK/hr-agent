"""
app/utils/file_parser.py
Парсер резюме (PDF + DOCX) — улучшенная версия
"""

import sys
import re
import hashlib
import logging
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List
from difflib import get_close_matches


logger = logging.getLogger(__name__)

SKILLS_DB = [
    "Python", "Java", "JavaScript", "TypeScript", "C++", "C#", "Go", "Rust",
    "PHP", "Ruby", "Swift", "Kotlin", "Scala", "Dart", "R", "Perl",
    "Django", "Flask", "FastAPI", "Spring", "Spring Boot", "React", "Angular",
    "Vue.js", "ASP.NET", "Laravel", "Ruby on Rails", "Express.js", "Next.js",
    "Nuxt.js", "Svelte", "TensorFlow", "PyTorch", "Keras", "Pandas", "NumPy",
    "SQL", "PostgreSQL", "MySQL", "MongoDB", "Redis", "Cassandra", "Oracle",
    "SQLite", "MariaDB", "Elasticsearch", "DynamoDB", "Firebase",
    "Docker", "Kubernetes", "Git", "Linux", "CI/CD", "Jenkins", "Ansible",
    "Terraform", "AWS", "Azure", "GCP", "GitLab CI", "GitHub Actions", "Nginx",
    "Apache", "Prometheus", "Grafana", "Helm", "Istio",
    "RabbitMQ", "Apache Kafka", "Celery", "Redis Streams", "ActiveMQ",
    "Unit Testing", "pytest", "JUnit", "Selenium", "Cypress", "Jest", "Mocha",
    "REST", "GraphQL", "gRPC", "WebSocket", "Microservices", "Event-Driven",
    "Serverless", "SOAP", "MQTT", "Prometheus", "Grafana", "ELK Stack", "Datadog", "New Relic",
    "OAuth", "JWT", "SSL/TLS", "OWASP", "Penetration Testing",
    "Agile", "Scrum", "Kanban", "Jira", "Confluence", "Trello",
    
    "AutoCAD", "SolidWorks", "Компас-3D", "Компас", "ANSYS", "Simulink", "Matlab",
    "Engee", "APM FEM", "FEM", "CAD", "ЕСКД", "чертежи", "проектирование",
    "Технологический процесс", "Охрана труда", "Промышленная безопасность",
    "Станки с ЧПУ", "Фрезерные работы", "Токарные работы", "Сварочные работы",
    "Слесарные работы", "Монтаж", "Наладка", "Ремонт оборудования",
    "Материаловедение", "Метрология", "Сертификация", "Контроль качества",
    "Бережливое производство", "5S", "Кайдзен", "ТОиР", "Планово-предупредительный ремонт",
    
    "СНиП", "ГОСТ", "Проектная документация", "Сметное дело", "Гранд-Смета",
    "AutoCAD Civil", "Revit", "Archicad", "3ds Max", "SketchUp",
    "Геодезия", "Нивелир", "Тахеометр", "Теодолит", "Георадар",
    "Строительный контроль", "Технадзор", "Авторский надзор",
    "Кровельные работы", "Отделочные работы", "Бетонные работы", "Монтажные работы",
    
    "1С:Логистика", "WMS", "SAP Logistics", "Корпоративная логистика",
    "Управление запасами", "ABC-анализ", "XYZ-анализ", "ФИФО", "ЛИФО",
    "Транспортная логистика", "Складской учет", "Таможенное оформление",
    "Международные перевозки", "Грузоперевозки", "Маршрутизация",
    "Работа с TMS", "RFID", "Штрихкодирование", "Инвентаризация",
    
    "1С", "SAP", "CRM", "ERP", "Битрикс24", "Мегаплан", "AMO CRM",
    "MS Office", "Excel", "Word", "PowerPoint", "Outlook", "Visio",
    "Google Docs", "Google Sheets", "Гугл-диск",
    "Документооборот", "Делопроизводство", "Архивное дело",
    "Управление проектами", "MS Project", "Jira", "Asana", "Trello", "Wrike",
    "Бюджетирование", "Планирование", "Бизнес-планирование", "KPI",
    "Внутренние регламенты", "Стандарты работы", "Инструкции",
    
    "Холодные звонки", "Ведение переговоров", "Работа с возражениями",
    "CRM-система", "Salesforce", "amoCRM", "Bitrix24",
    "SEO", "SMM", "Контекстная реклама", "Таргетинг", "Яндекс.Директ", "Google Ads",
    "Email-маркетинг", "Инфлюенс-маркетинг", "Партнерский маркетинг",
    "Копирайтинг", "Контент-менеджмент", "Написание текстов",
    "Photoshop", "CorelDRAW", "Figma", "Adobe Illustrator", "Canva",
    "Анализ рынка", "Конкурентный анализ", "Сегментация аудитории",
    
    "1С:Бухгалтерия", "1С:ЗУП", "1С:Управление торговлей", "1С:УНФ",
    "Налоговый учет", "Бухгалтерский учет", "Управленческий учет",
    "НДС", "Налог на прибыль", "УСН", "ЕНВД", "ПСН",
    "Кадровый учет", "Налоговые вычеты", "Авансовые отчеты",
    "Банк-клиент", "Платежный календарь", "Кассовые операции",
    "Финансовый анализ", "МСФО", "Бюджетирование", "Планирование",
    
    "1С:ЗУП", "HR-метрики", "Оценка персонала", "Ассессмент-центр",
    "Подбор персонала", "Рекрутинг", "Адаптация персонала", "Онбординг",
    "Обучение персонала", "Развитие персонала", "Тренинги", "Вебинары",
    "Кадровое делопроизводство", "Трудовое право", "Трудовые договоры",
    "Мотивация персонала", "Грейдинг", "KPI для сотрудников",
    "Кадровый резерв", "Планирование карьеры", "Наставничество",
    "Корпоративная культура", "Team building", "Мероприятия",
    
    "Вождение автомобиля", "Водительские права", "Категория B", "Категория C", "Категория D",
    "Английский язык", "Немецкий язык", "Китайский язык", "Французский язык",
    "Деловая переписка", "Деловые переговоры", "Презентации", "Публичные выступления",
    "Тайм-менеджмент", "Самоменеджмент", "Стрессоустойчивость",
    "Работа в команде", "Лидерские качества", "Ответственность",
    "Клиентоориентированность", "Ориентация на результат",
    "Аналитическое мышление", "Креативное мышление", "Системное мышление",
    "MS Office", "Excel", "Word", "PowerPoint", "Outlook",
    "Google Workspace", "Zoom", "Teams", "Skype", "Telegram", "WhatsApp",
    "Этикет", "Телефонные переговоры", "Приём посетителей"
]

POSITIONS_KEYWORDS = [
    "developer", "разработчик", "программист", "engineer", "инженер",
    "data scientist", "data engineer", "qa", "quality assurance",
    "team lead", "tech lead", "project manager", "product manager",
    "analyst", "аналитик", "intern", "junior", "middle", "senior",
    "architect", "devops", "backend", "frontend", "fullstack", "full-stack",
    "sysadmin", "system administrator", "database administrator", "dba",
    "mobile developer", "ios", "android", "security engineer", "sre",
    "site reliability engineer", "ml engineer", "machine learning",
    
    "конструктор", "инженер-конструктор", "технолог", "инженер-технолог",
    "механик", "инженер-механик", "электрик", "инженер-электрик",
    "сварщик", "фрезеровщик", "токарь", "слесарь", "монтажник", "наладчик",
    "оператор", "оператор станка", "оператор ЧПУ", "мастер", "мастер цеха",
    "начальник цеха", "начальник производства", "производственный директор",
    "инженер по качеству", "контролер ОТК", "кладовщик", "комплектовщик",
    
    "строитель", "прораб", "инженер-строитель", "архитектор", "дизайнер",
    "проектировщик", "сметчик", "инженер-сметчик", "геодезист",
    "монтажник", "отделочник", "кровельщик", "бригадир", "производитель работ",
    "технический надзор", "авторский надзор", "главный инженер проекта",
    
    "логист", "менеджер по логистике", "диспетчер", "водитель", "экспедитор",
    "кладовщик", "комплектовщик", "заведующий складом", "начальник склада",
    "транспортный логист", "специалист по ВЭД", "таможенный брокер",
    
    "менеджер", "директор", "руководитель", "администратор", "секретарь",
    "офис-менеджер", "управляющий", "исполнительный директор",
    "генеральный директор", "коммерческий директор", "финансовый директор",
    "исполнительный ассистент", "помощник руководителя",
    
    "бухгалтер", "экономист", "финансист", "аудитор", "кассир",
    "главный бухгалтер", "заместитель главного бухгалтера",
    "финансовый аналитик", "финансовый менеджер", "казначей",
    
    "hr", "рекрутер", "кадровик", "специалист по кадрам", "инспектор по кадрам",
    "hr-менеджер", "hr-директор", "менеджер по персоналу",
    "специалист по адаптации", "специалист по обучению", "trainer", "коуч",
    
    "маркетолог", "продавец", "торговый представитель", "мерчендайзер",
    "копирайтер", "контент-менеджер", "SMM-менеджер", "таргетолог",
    "seo-специалист", "контекстолог", "маркетинг-директор",
    "руководитель отдела продаж", "аккаунт-менеджер", "менеджер по работе с клиентами",
    
    "врач", "медсестра", "фельдшер", "фармацевт", "провизор",
    "санитар", "лаборант", "рентгенолаборант", "анестезиолог",
    
    "учитель", "преподаватель", "воспитатель", "педагог", "репетитор",
    "методист", "завуч", "директор школы", "декан", "профессор"
]

PHONE_PATTERNS = [
    r'\+?\d[\d\s\-()]{9,}',
    r'8[\s\-()]?\d{3}[\s\-()]?\d{3}[\s\-()]?\d{2}[\s\-()]?\d{2}',
    r'\+\d{1,3}[\s\-()]?\d{3}[\s\-()]?\d{3}[\s\-()]?\d{2}[\s\-()]?\d{2}',
]

EXPERIENCE_PATTERNS = [
    r'(\d+)\s*г(?:ода|од|год|\.)?\s*(?:(\d+)\s*мес(?:яца|яцев|\.)?)?',
    r'(\d+)\s*year(?:s)?\s*(?:(\d+)\s*month(?:s)?)?',
    r'опыт\s*(?:работы)?:?\s*(\d+)\s*г(?:ода|од|год|\.)?\s*(?:(\d+)\s*мес(?:яца|яцев|\.)?)?',
    r'стаж:?\s*(\d+(?:[.,]\d+)?)\s*г(?:ода|од|год|\.)?',
]


def safe_import(module_name: str, package_name: str = None):
    """Безопасный импорт модуля"""
    try:
        return __import__(module_name)
    except ImportError:
        package = package_name or module_name
        logger.error(f"Модуль '{module_name}' не установлен. Выполните: pip install {package}")
        return None


def normalize_text(text: str) -> str:
    """Нормализация текста"""
    if not text:
        return ""
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def calculate_file_hash(file_path: Path) -> Optional[str]:
    """Вычисляет MD5 хеш файла"""
    try:
        with open(file_path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    except Exception as e:
        logger.error(f"Ошибка при вычислении хеша файла {file_path}: {e}")
        return None


def extract_text_from_pdf(pdf_path: Path) -> Optional[str]:
    """Извлечение текста из PDF файла с поддержкой русского языка"""
    
    try:
        import fitz  # PyMuPDF
        text_parts = []
        doc = fitz.open(pdf_path)
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            if text:
                text_parts.append(text)
        doc.close()
        if text_parts:
            logger.debug(f"PDF распарсен через PyMuPDF, {len(text_parts)} страниц")
            return '\n'.join(text_parts)
    except ImportError:
        logger.debug("PyMuPDF не установлен, пробуем другие методы")
    except Exception as e:
        logger.warning(f"Ошибка при парсинге PDF через PyMuPDF: {e}")
    
    pdfplumber = safe_import('pdfplumber')
    if pdfplumber:
        try:
            text_parts = []
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
            if text_parts:
                logger.debug(f"PDF распарсен через pdfplumber, {len(text_parts)} страниц")
                return '\n'.join(text_parts)
        except Exception as e:
            logger.warning(f"Ошибка при парсинге PDF через pdfplumber: {e}")
    
    try:
        from pypdf import PdfReader
        text_parts = []
        reader = PdfReader(pdf_path)
        for page in reader.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)
        if text_parts:
            logger.debug(f"PDF распарсен через pypdf, {len(text_parts)} страниц")
            return '\n'.join(text_parts)
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"Ошибка при парсинге PDF через pypdf: {e}")
    
    logger.error(f"Не удалось распарсить PDF {pdf_path} ни одним способом")
    return None


def extract_text_from_docx(docx_path: Path) -> Optional[str]:
    """Извлечение текста из DOCX файла"""
    docx_module = safe_import('docx', 'python-docx')
    if not docx_module:
        return None
    
    text_parts = []
    try:
        doc = docx_module.Document(docx_path)
        
        for para in doc.paragraphs:
            if para.text:
                text_parts.append(para.text)
        
        for table in doc.tables:
            for row in table.rows:
                row_text = ' | '.join(cell.text.strip() for cell in row.cells if cell.text)
                if row_text:
                    text_parts.append(row_text)
        
        if not text_parts:
            logger.warning(f"DOCX файл {docx_path} не содержит текста")
            return None
        
        return '\n'.join(text_parts)
    
    except Exception as e:
        logger.error(f"Ошибка при парсинге DOCX {docx_path}: {e}")
        return None


def extract_email(text: str) -> Optional[str]:
    """Извлечение email"""
    pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'
    matches = re.findall(pattern, text)
    return matches[0].lower() if matches else None


def extract_phone(text: str) -> Optional[str]:
    """Извлечение телефона"""
    for pattern in PHONE_PATTERNS:
        matches = re.findall(pattern, text)
        if matches:
            phone = re.sub(r'[\s\-()]', '', matches[0])
            if phone.startswith('8') and len(phone) == 11:
                phone = '+7' + phone[1:]
            return phone
    return None


def extract_name(text: str) -> Optional[str]:
    """Извлечение ФИО из первых строк резюме"""
    lines = text.split('\n')[:100]
    
    for i, line in enumerate(lines):
        line = line.strip()
        if not line or len(line) < 5:
            continue
        
        if '@' in line or 'http://' in line or 'https://' in line:
            continue
        if re.search(r'\d', line):  # есть цифры
            continue
        
        clean = re.sub(r'[^A-Za-zА-Яа-яЁё\s\-]', '', line)
        words = clean.split()
        
        if 2 <= len(words) <= 4:
            capitalized = all(w and w[0].isupper() for w in words)
            if capitalized and len(clean) > 10:
                return clean
    
    return None


def extract_skills(text: str) -> List[str]:
    """Извлечение навыков (только прямое совпадение, без нечёткого поиска)"""
    found = set()
    text_lower = text.lower()
    
    for skill in SKILLS_DB:
        if skill.lower() in text_lower:
            found.add(skill)
    
    return sorted([s for s in found if s])


def extract_experience(text: str) -> Optional[int]:
    """Улучшенное извлечение опыта работы в годах (суммирует все места)"""
    
    total_months = 0
    current_year = datetime.now().year
    
    date_patterns = [
        r'([А-Яа-я]+)\s*(\d{4})\s*[—\-–]\s*(настоящее время|present|current|now|н\.в\.|по настоящее время)',
        r'([А-Яа-я]+)\s*(\d{4})\s*[—\-–]\s*([А-Яа-я]+)\s*(\d{4})',
        r'(\d{4})\s*[—\-–]\s*(\d{4})',
        r'(\d{4})\s*[—\-–]\s*(настоящее время|present|current|now|н\.в\.|по настоящее время)',
    ]
    
    for pattern in date_patterns:
        matches = re.findall(pattern, text.lower())
        for match in matches:
            try:
                if len(match) == 3:  # Месяц ГГГГ — настоящее время
                    start_year = int(match[1])
                    if start_year <= current_year:
                        months = (current_year - start_year) * 12
                        total_months += months
                elif len(match) == 4:  # Месяц ГГГГ — Месяц ГГГГ
                    start_year = int(match[1])
                    end_year = int(match[3])
                    if start_year <= end_year <= current_year + 1:
                        months = (end_year - start_year) * 12
                        total_months += months
                elif len(match) == 2 and match[0].isdigit() and match[1].isdigit():  # ГГГГ — ГГГГ
                    start_year = int(match[0])
                    end_year = int(match[1])
                    if start_year <= end_year <= current_year + 1:
                        months = (end_year - start_year) * 12
                        total_months += months
                elif len(match) == 2 and 'настоящее' in match[1].lower():  # ГГГГ — настоящее время
                    start_year = int(match[0])
                    if start_year <= current_year:
                        months = (current_year - start_year) * 12
                        total_months += months
            except:
                continue
    
    if total_months == 0:
        duration_pattern = r'(\d+)\s*г(?:ода|од|год|\.)?\s*(?:(\d+)\s*мес(?:яца|яцев|\.)?)?'
        matches = re.findall(duration_pattern, text.lower())
        for match in matches:
            try:
                if match[0]:
                    total_months = int(match[0]) * 12 + int(match[1] or 0)
                    break  # Берём первое вхождение
            except:
                continue
    
    years_exp = total_months // 12
    return years_exp if years_exp > 0 else 0

def extract_last_position(text: str) -> Optional[str]:
    """Улучшенное извлечение последней должности (поддерживает любые профессии)"""
    lines = text.split('\n')
    
    for i, line in enumerate(lines[:50]):
        line_clean = line.strip()
        if not line_clean:
            continue
        
        line_lower = line_clean.lower()
        
        for keyword in POSITIONS_KEYWORDS:
            if keyword in line_lower:
                clean = re.sub(r'[^\w\s\-/]', '', line_clean)
                clean = re.sub(r'\s+', ' ', clean).strip()
                
                if len(clean) > 3 and len(clean) < 100:
                    if not re.search(r'@|\+?\d{10,}', clean):
                        return clean
    
    return None


def extract_last_company(text: str) -> Optional[str]:
    """Улучшенное извлечение последней компании"""
    
    company_markers = [
        r'(?:OOО|ООО|ЗАО|ПАО|АО|Inc|Ltd|LLC|ГК|НИИ|ТОО|ИП|ООО у нас есть аренда и т.д.)',
        r'(?:завод|фабрика|корпорация|компания|предприятие|центр|университет|фирма|агентство|студия|лаборатория|клиника|школа|лицей|гимназия|академия)',
    ]
    
    lines = text.split('\n')
    
    for i, line in enumerate(lines):
        line_clean = line.strip()
        if not line_clean:
            continue
        
        is_company = False
        for marker in company_markers:
            if re.search(marker, line_clean, re.IGNORECASE):
                is_company = True
                break
        
        if is_company:
            company = re.sub(r'[^\w\s\-/()]', '', line_clean)
            company = re.sub(r'\s+', ' ', company).strip()
            
            if 3 <= len(company) <= 60:
                if not any(word in company.lower() for word in ['инженер', 'разработчик', 'менеджер', 'специалист', 'врач', 'учитель', 'бухгалтер']):
                    return company
    
    alt_pattern = r'([А-Я][А-Яа-я\s\-()]{3,40})\s*[—\-–]\s*([А-Яа-я\s\-/]+)'
    matches = re.findall(alt_pattern, text)
    for match in matches:
        potential_company = match[0].strip()
        potential_position = match[1].strip()
        if any(p in potential_position.lower() for p in ['инженер', 'конструктор', 'разработчик', 'менеджер', 'врач', 'учитель', 'бухгалтер', 'продавец']):
            if 3 <= len(potential_company) <= 50:
                return potential_company
    
    return None


def parse_resume(file_path: str) -> Dict[str, Any]:
    """Основная функция парсинга резюме (универсальная)"""
    file_path = Path(file_path)
    
    if not file_path.exists():
        return {"error": f"Файл не найден: {file_path}"}
    
    suffix = file_path.suffix.lower()
    if suffix == '.pdf':
        logger.info(f"Начинаю парсинг PDF: {file_path.name}")
        text = extract_text_from_pdf(file_path)
    elif suffix == '.docx':
        logger.info(f"Начинаю парсинг DOCX: {file_path.name}")
        text = extract_text_from_docx(file_path)
    else:
        return {"error": f"Неподдерживаемый формат: {suffix}. Используйте .pdf или .docx"}
    
    if not text:
        return {"error": "Не удалось извлечь текст из файла."}
    
    text = normalize_text(text)
    logger.debug(f"Извлечено {len(text)} символов текста")
    
    name = extract_name(text)
    email = extract_email(text)
    phone = extract_phone(text)
    skills = extract_skills(text)
    experience = extract_experience(text)
    last_position = extract_last_position(text)
    last_company = extract_last_company(text)
    
    if not name and email:
        name = email.split('@')[0].replace('.', ' ').title()
    
    result = {
        "name": name,
        "email": email,
        "phone": phone,
        "skills": skills,
        "experience_years": experience,
        "last_position": last_position,
        "last_company": last_company,
        "file_name": file_path.name,
        "file_hash": calculate_file_hash(file_path)
    }
    
    logger.info(f"Парсинг завершен. Найдено: имя={name}, опыт={experience} лет, навыков={len(skills)}")
    
    return result


from app.utils.formatters import format_parsed_resume as format_resume_for_display

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("=" * 60)
        print("HR Agent - Парсер резюме")
        print("=" * 60)
        print("\nИспользование:")
        print("  python file_parser.py <путь_к_файлу>")
        print("\nПоддерживаемые форматы:")
        print("  - PDF (.pdf)")
        print("  - Word (.docx)")
        print("=" * 60)
        sys.exit(0)
    
    file_path = sys.argv[1]
    result = parse_resume(file_path)
    
    print("\n" + "=" * 60)
    print(format_resume_for_display(result))
    print("=" * 60)
    print("\n📋 JSON формат:")
    print(json.dumps(result, ensure_ascii=False, indent=2))
