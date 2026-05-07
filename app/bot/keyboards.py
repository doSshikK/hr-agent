"""Клавиатуры для Telegram бота"""

from telegram import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup

from app.services.hr_facade import HRAgentFacade


def get_main_keyboard():
    """Главная клавиатура"""
    keyboard = [
        [KeyboardButton("📋 Вакансии"), KeyboardButton("👥 Кандидаты")],
        [KeyboardButton("📝 Создать тестирование"), KeyboardButton("📋 Создать онбординг")],
        [KeyboardButton("📊 Опросы"), KeyboardButton("📈 Показать статистику")],
        [KeyboardButton("📅 Управление собеседованиями")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_vacancies_keyboard():
    """Клавиатура для вакансий"""
    keyboard = [
        [KeyboardButton("📋 Показать все вакансии"), KeyboardButton("➕ Добавить новую вакансию")],
        [KeyboardButton("📦 Архив вакансий")],
        [KeyboardButton("◀️ Назад в главное меню")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_candidates_keyboard():
    """Клавиатура для кандидатов"""
    keyboard = [
        [KeyboardButton("👥 Показать всех кандидатов"), KeyboardButton("➕ Добавить нового кандидата")],
        [KeyboardButton("🔍 Поиск кандидатов"), KeyboardButton("📦 Архив кандидатов")],
        [KeyboardButton("◀️ Назад в главное меню")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_surveys_keyboard():
    """Клавиатура для опросов"""
    keyboard = [
        [KeyboardButton("📋 Все опросы"), KeyboardButton("📊 Создать NPS опрос")],
        [KeyboardButton("💓 Создать Pulse опрос")],
        [KeyboardButton("◀️ Назад в главное меню")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_slots_management_keyboard():
    """Клавиатура для управления слотами собеседований (для HR)"""
    keyboard = [
        [KeyboardButton("📅 Добавить день")],
        [KeyboardButton("📋 Мои слоты"), KeyboardButton("🗑️ Удалить слот")],
        [KeyboardButton("🗑️ Очистить дату")],
        [KeyboardButton("◀️ Назад в главное меню")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_slots_calendar_inline_keyboard(year: int = None, month: int = None, hr_id: int = None) -> InlineKeyboardMarkup:
    """Создаёт inline-календарь для выбора даты с эмодзи-статусами (для HR)"""
    from datetime import date, timedelta
    
    today = date.today()
    if year is None or month is None:
        year = today.year
        month = today.month
    
    keyboard = []
    
    month_names = ["Янв", "Фев", "Мар", "Апр", "Май", "Июн", "Июл", "Авг", "Сен", "Окт", "Ноя", "Дек"]
    
    nav_row = []
    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1
    
    nav_row.append(InlineKeyboardButton("◀️", callback_data=f"slots_cal_prev_{prev_year}_{prev_month}"))
    nav_row.append(InlineKeyboardButton(f"{month_names[month-1]} {year}", callback_data="ignore"))
    nav_row.append(InlineKeyboardButton("▶️", callback_data=f"slots_cal_next_{next_year}_{next_month}"))
    keyboard.append(nav_row)
    
    weekdays = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    weekday_row = []
    for wd in weekdays:
        weekday_row.append(InlineKeyboardButton(wd, callback_data="ignore"))
    keyboard.append(weekday_row)
    
    first_day = date(year, month, 1)
    start_weekday = first_day.weekday()  # 0 = понедельник
    
    if month == 12:
        last_day = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = date(year, month + 1, 1) - timedelta(days=1)
    
    days_in_month = last_day.day
    
    row = []
    for _ in range(start_weekday):
        row.append(InlineKeyboardButton(" ", callback_data="ignore"))
    
    for day in range(1, days_in_month + 1):
        current_date = date(year, month, day)
        
        if current_date < today:
            button_text = f"⚫ {day}"
            callback = "ignore"
        else:
            if hr_id:
                date_str = current_date.isoformat()
                slots = HRAgentFacade.get_interview_slots_by_date(date_str, hr_id)
                
                if not slots:
                    button_text = f"📅 {day}"
                elif HRAgentFacade.is_date_fully_booked(date_str, hr_id):
                    button_text = f"🔴 {day}"
                elif HRAgentFacade.has_free_slots(date_str, hr_id):
                    button_text = f"🟢 {day}"
                else:
                    button_text = f"📅 {day}"
            else:
                button_text = f"📅 {day}"
            
            callback = f"slots_add_date_{current_date.isoformat()}"
        
        row.append(InlineKeyboardButton(button_text, callback_data=callback))
        
        if len(row) == 7:
            keyboard.append(row)
            row = []
    
    if row:
        while len(row) < 7:
            row.append(InlineKeyboardButton(" ", callback_data="ignore"))
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="slots_back_to_menu")])
    
    return InlineKeyboardMarkup(keyboard)


def get_slots_time_keyboard(date: str, start_hour: int = 9, end_hour: int = 18, step_hours: int = 1) -> InlineKeyboardMarkup:
    """Создаёт inline-клавиатуру с выбором времени для слотов"""
    keyboard = []
    row = []
    
    for hour in range(start_hour, end_hour):
        time_str = f"{hour:02d}:00"
        row.append(InlineKeyboardButton(time_str, callback_data=f"slots_add_time_{date}_{time_str}"))
        
        if len(row) == 4:
            keyboard.append(row)
            row = []
    
    if row:
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("➕ Добавить все слоты на день", callback_data=f"slots_add_full_day_{date}")])
    keyboard.append([InlineKeyboardButton("◀️ Назад к календарю", callback_data="slots_back_to_calendar_hr")])
    
    return InlineKeyboardMarkup(keyboard)


def get_test_actions_keyboard():
    """Inline-кнопки для действий с тестом (PDF, редактирование)"""
    keyboard = [
        [
            InlineKeyboardButton("📄 Сохранить в PDF", callback_data="export_test_pdf"),
            InlineKeyboardButton("✏️ Редактировать", callback_data="edit_test"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_onboarding_actions_keyboard():
    """Inline-кнопки для действий с онбордингом (PDF, редактирование)"""
    keyboard = [
        [
            InlineKeyboardButton("📄 Сохранить в PDF", callback_data="export_onboarding_pdf"),
            InlineKeyboardButton("✏️ Редактировать", callback_data="edit_onboarding"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_onboarding_interactive_keyboard():
    """Интерактивная клавиатура для онбординга (для кандидата)"""
    keyboard = [
        [
            InlineKeyboardButton("📋 Мои задачи", callback_data="onb_tasks"),
            InlineKeyboardButton("📅 Мои встречи", callback_data="onb_meetings"),
        ],
        [
            InlineKeyboardButton("❓ Задать вопрос", callback_data="onb_help"),
            InlineKeyboardButton("📊 Мой прогресс", callback_data="onb_progress"),
        ],
        [
            InlineKeyboardButton("🏠 В главное меню", callback_data="onb_exit"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_task_navigation_keyboard(current_task: int, total_tasks: int, task_text: str = "") -> InlineKeyboardMarkup:
    """Клавиатура для навигации по задачам онбординга"""
    keyboard = []
    
    nav_row = []
    if current_task > 1:
        nav_row.append(InlineKeyboardButton("◀️ Предыдущая", callback_data=f"onb_task_prev_{current_task}"))
    if current_task < total_tasks:
        nav_row.append(InlineKeyboardButton("Следующая ▶️", callback_data=f"onb_task_next_{current_task}"))
    if nav_row:
        keyboard.append(nav_row)
    
    keyboard.append([
        InlineKeyboardButton("✅ Отметить готовым", callback_data=f"onb_complete_{current_task}"),
        InlineKeyboardButton("❓ Как сделать?", callback_data=f"onb_howto_{current_task}"),
    ])
    
    keyboard.append([
        InlineKeyboardButton("◀️ Назад в меню", callback_data="onb_back_to_menu"),
    ])
    
    return InlineKeyboardMarkup(keyboard)


def get_onboarding_meetings_keyboard(meetings: list, current_index: int = 0) -> InlineKeyboardMarkup:
    """Клавиатура для просмотра встреч онбординга"""
    keyboard = []
    
    if len(meetings) > 1:
        nav_row = []
        if current_index > 0:
            nav_row.append(InlineKeyboardButton("◀️ Предыдущая", callback_data=f"onb_meeting_prev_{current_index}"))
        if current_index < len(meetings) - 1:
            nav_row.append(InlineKeyboardButton("Следующая ▶️", callback_data=f"onb_meeting_next_{current_index}"))
        if nav_row:
            keyboard.append(nav_row)
    
    keyboard.append([InlineKeyboardButton("◀️ Назад в меню", callback_data="onb_back_to_menu")])
    
    return InlineKeyboardMarkup(keyboard)


def get_cancel_keyboard():
    """Клавиатура с кнопкой отмены"""
    keyboard = [[KeyboardButton("❌ Отмена")]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_back_keyboard():
    """Клавиатура с кнопкой назад"""
    keyboard = [[KeyboardButton("◀️ Назад")]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_candidate_keyboard():
    """Клавиатура для кандидата (соискателя)"""
    keyboard = [
        [KeyboardButton("📋 Смотреть вакансии")],
        [KeyboardButton("📄 Отправить резюме")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
