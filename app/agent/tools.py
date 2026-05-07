"""
app/agent/tools.py
Описания инструментов для function calling в LLM
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "parse_resume",
            "description": "Извлекает структурированные данные из резюме (PDF/DOCX) и проверяет, есть ли кандидат в базе.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Путь к файлу резюме"
                    }
                },
                "required": ["file_path"]
            }
        }
    },
    
    {
        "type": "function",
        "function": {
            "name": "save_candidate_to_db",
            "description": "Сохраняет или обновляет кандидата в базе данных после парсинга резюме.",
            "parameters": {
                "type": "object",
                "properties": {
                    "candidate_data": {
                        "type": "object",
                        "description": "Данные кандидата из parse_resume"
                    },
                    "file_path": {
                        "type": "string",
                        "description": "Путь к файлу резюме"
                    }
                },
                "required": ["candidate_data", "file_path"]
            }
        }
    },
    
    {
        "type": "function",
        "function": {
            "name": "search_candidates",
            "description": "Поиск кандидатов в базе по навыкам, опыту и должности. Поддерживает любые профессии (не только IT). Возвращает список с % совпадения.",
            "parameters": {
                "type": "object",
                "properties": {
                    "skills": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Список требуемых навыков (например, ['AutoCAD', '1С', 'Управление проектами', 'Python'])"
                    },
                    "min_experience": {
                        "type": "integer",
                        "description": "Минимальный опыт в годах"
                    },
                    "position": {
                        "type": "string",
                        "description": "Должность (например, 'инженер-конструктор', 'бухгалтер', 'менеджер по продажам')"
                    },
                    "min_match_percent": {
                        "type": "integer",
                        "description": "Минимальный процент совпадения для отображения",
                        "default": 20
                    }
                }
            }
        }
    },
    
    {
        "type": "function",
        "function": {
            "name": "match_candidates_to_job",
            "description": "Подбирает кандидатов под конкретную вакансию по её ID. Работает для любых сфер деятельности.",
            "parameters": {
                "type": "object",
                "properties": {
                    "job_id": {
                        "type": "integer",
                        "description": "ID вакансии из базы"
                    },
                    "top_n": {
                        "type": "integer",
                        "description": "Количество кандидатов в результате",
                        "default": 5
                    }
                },
                "required": ["job_id"]
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "prepare_interview_invite",
            "description": "Подготавливает приглашение кандидата на собеседование, но НЕ отправляет его сразу. Используй после выбора кандидата, чтобы запросить подтверждение HR.",
            "parameters": {
                "type": "object",
                "properties": {
                    "candidate_id": {
                        "type": "integer",
                        "description": "ID кандидата из базы. Предпочтительный способ указать кандидата."
                    },
                    "candidate_name": {
                        "type": "string",
                        "description": "Имя кандидата, если ID неизвестен"
                    },
                    "position": {
                        "type": "string",
                        "description": "Должность, на которую приглашают кандидата"
                    }
                }
            }
        }
    },
    
    {
        "type": "function",
        "function": {
            "name": "generate_test_task",
            "description": "Генерирует тестовое задание для кандидата на основе направления деятельности компании и уровня специалиста. Поддерживает любые сферы: IT, производство, строительство, логистику, офис/управление, продажи, маркетинг, финансы, HR и другие.",
            "parameters": {
                "type": "object",
                "properties": {
                    "direction": {
                        "type": "string",
                        "enum": ["it", "production", "construction", "logistics", "office", "sales", "marketing", "finance", "hr", "custom", "backend", "frontend", "fullstack", "devops", "mobile"],
                        "description": "Направление деятельности: it - IT, production - производство, construction - строительство, logistics - логистика, office - офис/управление, sales - продажи, marketing - маркетинг, finance - бухгалтерия/финансы, hr - кадры, custom - другое (а также legacy: backend/frontend и т.д.)"
                    },
                    "level": {
                        "type": "string",
                        "enum": ["junior", "middle", "senior"],
                        "description": "Уровень кандидата: junior (начальный), middle (средний), senior (опытный)"
                    },
                    "tech_stack": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Ключевые навыки/технологии/инструменты (например, для производства: 'AutoCAD, SolidWorks, чтение чертежей')"
                    },
                    "candidate_name": {
                        "type": "string",
                        "description": "Имя кандидата для персонализации"
                    }
                },
                "required": ["direction", "level"]
            }
        }
    },
    
    {
        "type": "function",
        "function": {
            "name": "create_onboarding_plan",
            "description": "Создаёт план онбординга для нового сотрудника с учётом отдела и уровня. Поддерживает 9 отделов: разработка, аналитика, менеджмент, маркетинг, продажи, HR, финансы, юридический отдел, дизайн.",
            "parameters": {
                "type": "object",
                "properties": {
                    "candidate_name": {
                        "type": "string",
                        "description": "Имя сотрудника"
                    },
                    "candidate_email": {
                        "type": "string",
                        "description": "Email сотрудника"
                    },
                    "department": {
                        "type": "string",
                        "description": "Отдел: development, analytics, management, marketing, sales, hr, finance, legal, design",
                        "enum": ["development", "analytics", "management", "marketing", "sales", "hr", "finance", "legal", "design"]
                    },
                    "level": {
                        "type": "string",
                        "description": "Уровень (только для отдела development): junior, middle, senior",
                        "enum": ["junior", "middle", "senior"]
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Дата начала работы в формате YYYY-MM-DD"
                    }
                },
                "required": ["candidate_name"]
            }
        }
    },
    
    {
        "type": "function",
        "function": {
            "name": "create_survey",
            "description": "Создаёт NPS или Pulse опрос для сотрудников.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Название опроса"
                    },
                    "survey_type": {
                        "type": "string",
                        "enum": ["nps", "pulse"],
                        "description": "Тип опроса: nps (Net Promoter Score) или pulse (быстрый опрос)"
                    },
                    "department": {
                        "type": "string",
                        "description": "Отдел (опционально)"
                    }
                },
                "required": ["title", "survey_type"]
            }
        }
    },
    
    {
        "type": "function",
        "function": {
            "name": "analyze_survey",
            "description": "Анализирует результаты опроса по ID и возвращает NPS score или статистику.",
            "parameters": {
                "type": "object",
                "properties": {
                    "survey_id": {
                        "type": "integer",
                        "description": "ID опроса"
                    }
                },
                "required": ["survey_id"]
            }
        }
    },
    
    {
        "type": "function",
        "function": {
            "name": "list_jobs",
            "description": "Показывает список всех вакансий с их ID, названием, уровнем и требованиями.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    
    {
        "type": "function",
        "function": {
            "name": "list_candidates",
            "description": "Показывает список всех кандидатов в базе с их ID, именем, опытом и должностью.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    
    {
        "type": "function",
        "function": {
            "name": "get_statistics",
            "description": "Возвращает общую статистику: количество кандидатов, вакансий, опросов.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    }
]


def get_tool_names() -> list:

    return [tool["function"]["name"] for tool in TOOLS]


def get_tool_by_name(tool_name: str) -> dict:

    for tool in TOOLS:
        if tool["function"]["name"] == tool_name:
            return tool
    return None


def get_tools_summary() -> str:

    output = []
    output.append("📋 **Доступные инструменты HR Agent:**")
    output.append("=" * 40)
    
    for tool in TOOLS:
        name = tool["function"]["name"]
        description = tool["function"]["description"]
        output.append(f"• **{name}** — {description}")
    
    return "\n".join(output)


def is_valid_tool(tool_name: str) -> bool:

    return tool_name in get_tool_names()


TOOLS_BY_CATEGORY = {
    "Кандидаты": ["parse_resume", "save_candidate_to_db", "search_candidates", "list_candidates"],
    "Вакансии": ["match_candidates_to_job", "list_jobs"],
    "Собеседования": ["prepare_interview_invite"],
    "Тестирование": ["generate_test_task"],
    "Адаптация": ["create_onboarding_plan"],
    "Опросы": ["create_survey", "analyze_survey"],
    "Аналитика": ["get_statistics"]
}


def get_tools_by_category(category: str) -> list:

    return TOOLS_BY_CATEGORY.get(category, [])


def get_all_categories() -> list:

    return list(TOOLS_BY_CATEGORY.keys())


def get_category_for_tool(tool_name: str) -> str:

    for category, tools in TOOLS_BY_CATEGORY.items():
        if tool_name in tools:
            return category
    return "Прочее"


if __name__ == "__main__":
    print("=" * 60)
    print("ОПИСАНИЕ ИНСТРУМЕНТОВ HR AGENT")
    print("=" * 60)
    
    print(f"\n📊 Всего инструментов: {len(TOOLS)}")
    
    print("\n📂 Инструменты по категориям:")
    for category, tools in TOOLS_BY_CATEGORY.items():
        print(f"\n   **{category}** ({len(tools)}):")
        for tool in tools:
            print(f"      • {tool}")
    
    print("\n" + "=" * 60)
    print(get_tools_summary())
    
    print("\n" + "=" * 60)
    print("ПРОВЕРКА ВАЛИДНОСТИ:")
    
    test_tools = ["parse_resume", "search_candidates", "unknown_tool"]
    for tool in test_tools:
        is_valid = is_valid_tool(tool)
        status = "✅" if is_valid else "❌"
        print(f"   {status} {tool}: {'существует' if is_valid else 'не существует'}")
    
    print("\n✅ Все инструменты загружены и готовы к использованию!")
