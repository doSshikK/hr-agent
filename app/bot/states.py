"""Константы и состояния для Telegram бота"""


CANCEL_WORDS = ["отмена", "cancel", "стоп", "прервать", "отменить"]
CANDIDATE_ADD_WORDS = ["добавить нового кандидата", "новый кандидат", "создать кандидата", "добавить кандидата", "завести кандидата"]
JOB_ADD_WORDS = ["добавить вакансию", "новая вакансия", "создать вакансию", "добавить новую вакансию"]


TEST_TRIGGERS = ["создай тест", "сгенерируй тест", "тестовое задание", "сделай тест", "тест для", "генерация теста", "напиши тест", "составь тест", "сформируй тест", "тестирование"]

ONBOARDING_TRIGGERS = ["сделай онбординг", "план онбординга", "онбординг", "создай онбординг", "создай план адаптации", "адаптация", "план адаптации", "сделай адаптацию", "онбординг для", "адаптация для", "план для"]

SURVEY_CREATE_TRIGGERS = ["создай nps опрос", "создай pulse опрос", "nps опрос", "pulse опрос"]
SURVEY_ANALYZE_TRIGGERS = ["проанализируй опрос", "анализ опроса", "результаты опроса"]
SURVEY_DELETE_TRIGGERS = ["удалить опрос", "удали опрос"]
SURVEY_DELETE_ALL_TRIGGERS = ["удалить все опросы", "очистить опросы"]
SURVEY_LIST_TRIGGERS = ["покажи опросы", "список опросов", "все опросы", "опросы"]

CHART_TRIGGERS = ["график опроса", "покажи график опроса"]
SURVEY_NPS_CHART_TRIGGERS = ["nps график", "nps диаграмма"]
SURVEY_PULSE_CHART_TRIGGERS = ["pulse график", "динамика опроса", "pulse диаграмма"]

JOB_EXPORT_PDF_TRIGGERS = ["экспорт вакансии в pdf", "сохранить вакансию в pdf","экспортируй вакансию в pdf", "сохрани вакансию в pdf", "экспорт вакансии в пдф", "сохранить вакансию в пдф","экспортируй вакансию в пдф", "сохрани вакансию в пдф"]
CANDIDATE_EXPORT_PDF_TRIGGERS = ["экспорт кандидата в pdf", "сохранить кандидата в pdf", "сохрани кандидата в pdf","экспортируй кандидата в pdf","экспорт кандидата в пдф", "сохранить кандидата в пдф", "сохрани кандидата в пдф","экспортируй кандидата в пдф"]

CANDIDATE_LIST_TRIGGERS = ["покажи кандидатов", "список кандидатов", "все кандидаты", "кандидаты"]
CANDIDATE_INFO_TRIGGERS = ["инфо кандидат", "покажи кандидата"]
CANDIDATE_DELETE_TRIGGERS = ["удалить кандидата", "удали кандидата"]
CANDIDATE_DELETE_ALL_TRIGGERS = ["удалить всех кандидатов", "очистить кандидатов"]
CANDIDATE_EDIT_TRIGGERS = ["редактировать кандидата", "ред кандидата"]
CANDIDATE_RESTORE_TRIGGERS = ["восстановить кандидата", "вернуть кандидата", "restore"]

CANDIDATE_ARCHIVE_TRIGGERS = ["архивировать кандидата", "в архив", "отказ"]
CANDIDATE_ARCHIVE_SHOW_TRIGGERS = ["показать архив", "архив", "архивированные", "список архива"]
CANDIDATE_ARCHIVE_RESTORE_TRIGGERS = ["восстановить из архива", "вернуть из архива"]

JOB_LIST_TRIGGERS = ["покажи вакансии", "список вакансий", "все вакансии", "вакансии"]
JOB_INFO_TRIGGERS = ["инфо вакансия", "покажи вакансию"]
JOB_DELETE_TRIGGERS = ["удалить вакансию", "удали вакансию"]
JOB_DELETE_ALL_TRIGGERS = ["удалить все вакансии", "очистить вакансии", "очисти вакансии", "удали все вакансии"]
JOB_EDIT_TRIGGERS = ["редактировать вакансию", "ред вакансию"]

JOB_ARCHIVE_TRIGGERS = ["архивировать вакансию", "архив вакансии", "в архив", "отправить в архив"]
JOB_ACTIVATE_TRIGGERS = ["активировать вакансию", "восстановить вакансию", "актив вакансии"]

TEST_EXPORT_PDF_TRIGGERS = ["экспорт теста в pdf", "сохранить тест в pdf"]
ONBOARDING_EXPORT_PDF_TRIGGERS = ["экспорт онбординга в pdf", "сохранить онбординг в pdf"]

TEST_EDIT_TRIGGERS = ["редактировать тест", "ред тест"]
ONBOARDING_EDIT_TRIGGERS = ["редактировать онбординг", "ред онбординг"]

STATISTICS_TRIGGERS = ["статистика", "стата", "stats", "покажи статистику"]

PARSING_YES_WORDS = ["да", "+", "добавить", "save", "add", "давай", "ок", "yes"]
PARSING_NO_WORDS = ["нет", "no", "n", "не надо", "пропустить"]
PARSING_UPDATE_WORDS = ["обновить", "update", "replace"]

CANDIDATE_EXPORT_EXCEL_TRIGGERS = ["выгрузить кандидатов", "экспорт в эксель", "сохранить в excel", "скачать эксель", "выгрузи кандидатов", "экспортируй кандидатов в эксель","создай эксель","сохрани в эксель","сохрани кандидатов в эксель","скачай в эксель","эксель"]


DIRECTION_NAMES = {
    "frontend": "Frontend",
    "backend": "Backend",
    "fullstack": "Fullstack",
    "devops": "DevOps",
    "mobile": "Mobile",
    "it": "IT и разработка",
    "production": "Производство",
    "construction": "Строительство",
    "logistics": "Логистика и склад",
    "office": "Офис и управление",
    "sales": "Продажи",
    "marketing": "Маркетинг и реклама",
    "finance": "Бухгалтерия и финансы",
    "hr": "HR и управление персоналом",
    "custom": "Другая сфера"
}

LEVEL_RU = {"junior": "Junior (начальный)", "middle": "Middle (средний)", "senior": "Senior (старший)"}

DEPARTMENT_MAP = {
    "разработчик": "development", "программист": "development", "developer": "development",
    "devops": "development", "backend": "development", "frontend": "development",
    "fullstack": "development", "engineer": "development", "qa": "development",
    "тестировщик": "development", "mobile": "development", "ios": "development",
    "android": "development", "data engineer": "development", "сисадмин": "development",
    "системный администратор": "development", "системный аналитик": "analytics",
    
    "конструктор": "development", "инженер": "development", "технолог": "development",
    "механик": "development", "электрик": "development", "сварщик": "development",
    "фрезеровщик": "development", "токарь": "development", "слесарь": "development",
    "монтажник": "development", "наладчик": "development", "оператор": "development",
    "мастер": "management", "начальник цеха": "management", "прораб": "management",
    "инженер-конструктор": "development", "инженер-технолог": "development",
    "инженер-механик": "development", "инженер-электрик": "development",
    
    "строитель": "development", "архитектор": "design", "проектировщик": "development",
    "сметчик": "finance", "геодезист": "development", "отделочник": "development",
    "кровельщик": "development", "бригадир": "management",
    
    "логист": "analytics", "водитель": "development", "кладовщик": "development",
    "комплектовщик": "development", "экспедитор": "development", "диспетчер": "analytics",
    "менеджер по логистике": "management", "начальник склада": "management",
    
    "менеджер": "management", "manager": "management", "руководитель": "management",
    "тимлид": "management", "team lead": "management", "project manager": "management",
    "product manager": "management", "pm": "management", "product owner": "management",
    "администратор": "management", "секретарь": "development", "офис-менеджер": "management",
    "управляющий": "management", "исполнительный директор": "management",
    "генеральный директор": "management", "коммерческий директор": "management",
    "финансовый директор": "finance", "исполнительный ассистент": "management",
    "помощник руководителя": "management",
    
    "аналитик": "analytics", "analyst": "analytics", "data analyst": "analytics",
    "бизнес-аналитик": "analytics", "системный аналитик": "analytics",
    "финансовый аналитик": "finance", "экономист": "finance",
    
    "маркетолог": "marketing", "marketing": "marketing", "smm": "marketing",
    "seo": "marketing", "pr": "marketing", "контент-менеджер": "marketing",
    "таргетолог": "marketing", "контекстолог": "marketing", "копирайтер": "marketing",
    "маркетинг-директор": "management",
    
    "продавец": "sales", "sales": "sales", "менеджер по продажам": "sales",
    "аккаунт-менеджер": "sales", "торговый представитель": "sales",
    "мерчендайзер": "sales", "руководитель отдела продаж": "management",
    
    "hr": "hr", "рекрутер": "hr", "recruiter": "hr", "кадровик": "hr",
    "специалист по кадрам": "hr", "инспектор по кадрам": "hr",
    "hr-менеджер": "hr", "менеджер по персоналу": "hr", "hr-директор": "management",
    
    "бухгалтер": "finance", "финансист": "finance", "accountant": "finance",
    "главный бухгалтер": "finance", "аудитор": "finance", "кассир": "finance",
    "финансовый менеджер": "finance", "казначей": "finance",
    
    "юрист": "legal", "legal": "legal", "адвокат": "legal",
    "юрисконсульт": "legal", "юридический консультант": "legal",
    
    "дизайнер": "design", "designer": "design", "ui": "design", "ux": "design",
    "графический дизайнер": "design", "product designer": "design",
    "веб-дизайнер": "design", "иллюстратор": "design",
    
    "врач": "development", "медсестра": "development", "фельдшер": "development",
    "фармацевт": "development", "провизор": "development",
    
    "учитель": "development", "преподаватель": "development", "воспитатель": "development",
    "педагог": "development", "методист": "analytics", "завуч": "management",
    "директор школы": "management"
}

DEPT_NAMES = {
    "development": "Разработка / Производство / Технический отдел",
    "analytics": "Аналитика",
    "management": "Менеджмент и управление",
    "marketing": "Маркетинг и реклама",
    "sales": "Продажи и работа с клиентами",
    "hr": "HR и управление персоналом",
    "finance": "Бухгалтерия / Финансы",
    "legal": "Юридический отдел",
    "design": "Дизайн и проектирование"
}

PAGINATION_TYPES = {"candidates": "candidates", "jobs": "jobs", "surveys": "surveys", "search": "search"}


STATE_WAITING_FOR_NAME = "waiting_for_name"
STATE_WAITING_FOR_EMAIL = "waiting_for_email"
STATE_WAITING_FOR_PHONE = "waiting_for_phone"
STATE_WAITING_FOR_EXPERIENCE = "waiting_for_experience"
STATE_WAITING_FOR_POSITION = "waiting_for_position"
STATE_WAITING_FOR_COMPANY = "waiting_for_company"
STATE_WAITING_FOR_SKILLS = "waiting_for_skills"

STATE_JOB_WAITING_FOR_TITLE = "job_waiting_for_title"
STATE_JOB_WAITING_FOR_LEVEL = "job_waiting_for_level"
STATE_JOB_WAITING_FOR_SKILLS = "job_waiting_for_skills"
STATE_JOB_WAITING_FOR_EXPERIENCE = "job_waiting_for_experience"
STATE_JOB_WAITING_FOR_DESCRIPTION = "job_waiting_for_description"

STATE_TEST_WAITING_FOR_DIRECTION = "test_waiting_for_direction"
STATE_TEST_WAITING_FOR_LEVEL = "test_waiting_for_level"

STATE_ONBOARDING_WAITING_FOR_NAME = "onboarding_waiting_for_name"
STATE_ONBOARDING_WAITING_FOR_ROLE = "onboarding_waiting_for_role"
STATE_ONBOARDING_WAITING_FOR_LEVEL = "onboarding_waiting_for_level"
STATE_ONBOARDING_WAITING_FOR_DATE = "onboarding_waiting_for_date"

STATE_SURVEY_WAITING_FOR_SCORE = "survey_waiting_for_score"
STATE_SURVEY_WAITING_FOR_ENERGY = "survey_waiting_for_energy"
STATE_SURVEY_WAITING_FOR_FEEDBACK = "survey_waiting_for_feedback"

STATE_EDITING_CANDIDATE = "editing_candidate"
STATE_EDITING_JOB = "editing_job"
STATE_EDITING_TEST = "editing_test"
STATE_EDITING_ONBOARDING = "editing_onboarding"

STATE_CONFIRM_DELETE_CANDIDATE = "confirm_delete_candidate"
STATE_CONFIRM_DELETE_ALL_CANDIDATES = "confirm_delete_all_candidates"
STATE_CONFIRM_DELETE_ALL_JOBS = "confirm_delete_all_jobs"
STATE_CONFIRM_DELETE_ALL_SURVEYS = "confirm_delete_all_surveys"

STATE_AWAITING_ROLE = "awaiting_role"
STATE_AWAITING_HR_NAME = "awaiting_hr_name"
STATE_CANDIDATE_WAITING_FOR_RESUME = "candidate_waiting_for_resume"
