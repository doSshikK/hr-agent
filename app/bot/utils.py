"""Вспомогательные функции для Telegram бота"""

import re
from datetime import datetime
from typing import Tuple, Optional

from telegram.ext import ContextTypes


def extract_test_params(text: str) -> dict:
    """Извлекает параметры теста из текста (универсальная версия)"""
    text = text.lower()
    
    direction = None
    level = None
    
    if "производство" in text or "production" in text:
        direction = "production"
    elif "строительство" in text or "construction" in text:
        direction = "construction"
    elif "логистика" in text or "logistics" in text or "склад" in text:
        direction = "logistics"
    elif "офис" in text or "управление" in text or "office" in text or "администратор" in text:
        direction = "office"
    elif "продажи" in text or "sales" in text or "менеджер по продажам" in text:
        direction = "sales"
    elif "маркетинг" in text or "marketing" in text or "реклама" in text:
        direction = "marketing"
    elif "бухгалтерия" in text or "финансы" in text or "finance" in text or "бухгалтер" in text:
        direction = "finance"
    elif "hr" in text or "кадры" in text or "рекрутинг" in text or "персонал" in text:
        direction = "hr"
    elif "it" in text or "айти" in text or "программирование" in text or "разработка" in text:
        direction = "it"
    
    if not direction:
        if "backend" in text:
            direction = "backend"
        elif "frontend" in text:
            direction = "frontend"
        elif "fullstack" in text:
            direction = "fullstack"
        elif "devops" in text:
            direction = "devops"
        elif "mobile" in text:
            direction = "mobile"
    
    if "junior" in text:
        level = "junior"
    elif "middle" in text:
        level = "middle"
    elif "senior" in text:
        level = "senior"
    
    tech_stack = []
    
    known_techs = [
        "python", "django", "flask", "fastapi", "javascript", "react", "vue",
        "node", "docker", "kubernetes", "sql", "postgres", "mongodb", "redis",
        "aws", "azure", "gcp", "git", "linux"
    ]
    
    universal_skills = [
        "автокад", "autocad", "solidworks", "компас", "1с", "смета", "сметное дело",
        "логистика", "склад", "wms", "crm", "битрикс", "excel", "word", "powerpoint",
        "кадры", "рекрутинг", "подбор персонала", "продажи", "переговоры", "маркетинг",
        "smm", "seo", "контекстная реклама", "бухгалтерия", "налоги", "кадровый учет"
    ]
    
    all_skills = known_techs + universal_skills
    
    for skill in all_skills:
        if skill in text:
            tech_stack.append(skill)
    
    return {
        "direction": direction,
        "level": level,
        "tech_stack": tech_stack,
        "candidate_name": None
    }


def detect_direction_from_role(text: str) -> str:
    """Определяет направление деятельности по тексту должности (универсальная)"""
    text = text.lower()

    
    production_keywords = [
        "инженер", "конструктор", "технолог", "механик", "электрик", "сварщик",
        "фрезеровщик", "токарь", "слесарь", "монтажник", "наладчик", "оператор",
        "производство", "цех", "завод", "станок", "чпу", "технический", "прораб"
    ]
    
    construction_keywords = [
        "строитель", "архитектор", "проектировщик", "сметчик", "геодезист",
        "отделочник", "кровельщик", "строительство", "объект", "стройка", "ремонт"
    ]
    
    logistics_keywords = [
        "логист", "водитель", "кладовщик", "комплектовщик", "экспедитор",
        "диспетчер", "логистика", "склад", "доставка", "перевозки", "транспорт"
    ]
    
    office_keywords = [
        "менеджер", "администратор", "секретарь", "офис", "управление",
        "руководитель", "директор", "ассистент", "помощник", "управляющий", "начальник"
    ]
    
    sales_keywords = [
        "продажи", "sales", "торговый", "представитель", "мерчендайзер",
        "аккаунт", "клиент", "продавец", "коммерческий"
    ]
    
    marketing_keywords = [
        "маркетинг", "marketing", "smm", "seo", "реклама", "контент",
        "копирайтер", "таргетолог", "контекстолог", "бренд", "продвижение"
    ]
    
    finance_keywords = [
        "бухгалтер", "финансист", "экономист", "аудитор", "кассир", "налог",
        "бухгалтерия", "финансы", "accountant", "finance", "казначей"
    ]
    
    hr_keywords = [
        "hr", "рекрутер", "кадровик", "кадры", "персонал", "найм", "подбор",
        "адаптация", "обучение", "тренинг", "hr-менеджер", "кадровый"
    ]
    
    backend_keywords = [
        "backend", "back-end", "python", "django", "flask", "fastapi",
        "java", "spring", "node", "php", "laravel", "ruby", "golang",
        "c#", ".net", "api", "rest", "graphql", "server", "database",
        "sql", "postgres", "mysql", "mongodb", "бэкенд", "бекенд", "сервер"
    ]

    frontend_keywords = [
        "frontend", "front-end", "javascript", "typescript", "react", "vue",
        "angular", "html", "css", "web developer", "фронтенд", "фронт"
    ]

    fullstack_keywords = ["fullstack", "full-stack", "full stack", "фулстек"]
    devops_keywords = ["devops", "docker", "kubernetes", "ci/cd", "jenkins", "aws", "azure", "девопс"]
    mobile_keywords = ["mobile", "ios", "android", "swift", "kotlin", "react native", "flutter", "мобильный"]

    if any(word in text for word in production_keywords):
        return "production"
    if any(word in text for word in construction_keywords):
        return "construction"
    if any(word in text for word in logistics_keywords):
        return "logistics"
    if any(word in text for word in office_keywords):
        return "office"
    if any(word in text for word in sales_keywords):
        return "sales"
    if any(word in text for word in marketing_keywords):
        return "marketing"
    if any(word in text for word in finance_keywords):
        return "finance"
    if any(word in text for word in hr_keywords):
        return "hr"
    if any(word in text for word in fullstack_keywords):
        return "fullstack"
    if any(word in text for word in frontend_keywords):
        return "frontend"
    if any(word in text for word in backend_keywords):
        return "backend"
    if any(word in text for word in devops_keywords):
        return "devops"
    if any(word in text for word in mobile_keywords):
        return "mobile"
    
    return "it"


def extract_onboarding_params(text: str) -> dict:
    """Извлекает параметры онбординга из текста"""
    text = text.lower()
    
    department = "development"
    if "hr" in text or "кадры" in text:
        department = "hr"
    elif "marketing" in text or "маркетинг" in text:
        department = "marketing"
    elif "sales" in text or "продажи" in text:
        department = "sales"
    elif "финанс" in text or "бухгалтер" in text or "finance" in text:
        department = "finance"
    elif "юрист" in text or "legal" in text:
        department = "legal"
    elif "дизайн" in text or "design" in text:
        department = "design"
    elif "аналитик" in text or "analytics" in text:
        department = "analytics"
    elif "менеджер" in text or "руководитель" in text:
        department = "management"
    elif "производств" in text or "инженер" in text or "конструктор" in text:
        department = "development"
    
    level = "middle"
    if "junior" in text or "начальный" in text or "джуниор" in text:
        level = "junior"
    elif "senior" in text or "старший" in text or "сеньор" in text:
        level = "senior"
    
    return {
        "candidate_name": None,
        "candidate_email": None,
        "department": department,
        "level": level,
        "start_date": None
    }


def extract_name_from_text(text: str) -> str:
    """Извлекает имя из текста"""
    import re
    text = re.sub(r'[^\w\s\-]', '', text)
    text = text.strip()
    
    if not text:
        return None
    
    forbidden = ["онбординг", "тестирование", "отмена", "старт", "меню", "создай", "сделай", "создать"]
    if text.lower() in forbidden:
        return None
    
    words = text.split()
    if len(words) >= 2:
        if len(words[0]) > 2 and len(words[1]) > 2:
            return f"{words[0].capitalize()} {words[1].capitalize()}"
    elif len(words) == 1 and len(words[0]) > 2:
        return words[0].capitalize()
    
    return None


def format_years(years: int) -> str:
    """Правильное склонение слова 'год'"""
    if years is None:
        return ""
    if 11 <= years % 100 <= 14:
        return f"{years} лет"
    if years % 10 == 1:
        return f"{years} год"
    if years % 10 in [2, 3, 4]:
        return f"{years} года"
    return f"{years} лет"


def validate_date(date_str: str) -> Tuple[bool, Optional[datetime], Optional[str]]:
    """Проверяет и парсит дату"""
    date_str_clean = date_str.strip()
    
    match_short = re.match(r'^(\d{2})\.(\d{2})\.(\d{2})$', date_str_clean)
    if match_short:
        day, month, year_short = match_short.groups()
        year = 2000 + int(year_short)
        date_str_clean = f"{day}.{month}.{year}"
    
    try:
        date_obj = datetime.strptime(date_str_clean, "%d.%m.%Y")
        today = datetime.now().date()
        if date_obj.date() < today:
            return False, None, f"Дата не может быть раньше {today.strftime('%d.%m.%Y')}"
        return True, date_obj, None
    except ValueError:
        return False, None, "Неверный формат. Используйте ДД.ММ.ГГГГ или ДД.ММ.ГГ"


def clear_user_state(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Очищает состояние пользователя в context.user_data"""
    if context and hasattr(context, 'user_data'):
        if "user_state" in context.user_data:
            del context.user_data["user_state"]
        if "temp_data" in context.user_data:
            del context.user_data["temp_data"]
