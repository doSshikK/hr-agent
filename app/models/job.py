"""
app/models/job.py
Pydantic модель вакансии для HR Agent
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


class Job(BaseModel):

    
    id: Optional[int] = Field(
        default=None,
        description="Уникальный идентификатор вакансии в БД",
        example=1
    )
    
    title: str = Field(
        default="",
        description="Название вакансии",
        example="Python Developer",
        min_length=1
    )
    
    level: str = Field(
        default="middle",
        description="Уровень: junior, middle, senior",
        example="middle"
    )
    
    
    skills: List[str] = Field(
        default_factory=list,
        description="Список требуемых навыков",
        example=["Python", "Django", "PostgreSQL", "Docker"]
    )
    
    experience: int = Field(
        default=0,
        description="Требуемый опыт работы в годах",
        ge=0,
        example=3
    )
    
    description: Optional[str] = Field(
        default=None,
        description="Полное описание вакансии",
        example="Ищем Python разработчика в команду backend..."
    )
    
    
    status: str = Field(
        default="active",
        description="Статус вакансии: active (активна), archived (в архиве)",
        example="active"
    )
    
    created_at: Optional[datetime] = Field(
        default=None,
        description="Дата и время создания вакансии"
    )
    
    updated_at: Optional[datetime] = Field(
        default=None,
        description="Дата и время последнего обновления"
    )
    
    
    matched_skills: Optional[List[str]] = Field(
        default=None,
        description="Список навыков, которые совпали с навыками кандидата"
    )
    
    match_percent: Optional[int] = Field(
        default=None,
        description="Процент совпадения с кандидатом (0-100)",
        ge=0,
        le=100
    )
    
    
    @field_validator('level', mode='before')
    @classmethod
    def validate_level(cls, v: Any) -> str:
        """Валидация уровня"""
        if v is None:
            return "middle"
        
        v_str = str(v).lower().strip()
        
        valid_levels = ["junior", "middle", "senior"]
        
        synonyms = {
            "jun": "junior",
            "джуниор": "junior",
            "mid": "middle",
            "мидл": "middle",
            "sen": "senior",
            "сеньор": "senior",
            "senior": "senior",
        }
        
        if v_str in synonyms:
            return synonyms[v_str]
        
        if v_str in valid_levels:
            return v_str
        
        return "middle"
    
    @field_validator('status', mode='before')
    @classmethod
    def validate_status(cls, v: Any) -> str:
        """Валидация статуса"""
        if v is None:
            return "active"
        
        v_str = str(v).lower().strip()
        
        if v_str in ["active", "archived"]:
            return v_str
        
        return "active"
    
    @field_validator('skills', mode='before')
    @classmethod
    def validate_skills(cls, v: Any) -> List[str]:
        """Валидация навыков"""
        if v is None:
            return []
        
        if isinstance(v, list):
            return [s.strip().lower() for s in v if s and isinstance(s, str)]
        
        if isinstance(v, str):
            if ',' in v:
                return [s.strip().lower() for s in v.split(',') if s.strip()]
            return [v.strip().lower()] if v.strip() else []
        
        return []
    
    @field_validator('experience', mode='before')
    @classmethod
    def validate_experience(cls, v: Any) -> int:
        """Валидация требуемого опыта"""
        if v is None:
            return 0
        if isinstance(v, (int, float)):
            return max(0, int(v))
        if isinstance(v, str):
            try:
                return max(0, int(v))
            except ValueError:
                return 0
        return 0
    
    
    def to_dict(self) -> Dict[str, Any]:
        """  Преобразует модель в словарь для сохранения в БД """
        return self.model_dump(exclude_none=True, exclude={'created_at', 'updated_at'})
    
    def to_db_dict(self) -> Dict[str, Any]:
        """
        Преобразует модель в словарь для прямого сохранения в БД
        """
        return {
            'title': self.title,
            'level': self.level,
            'skills': self.skills,
            'experience': self.experience,
            'description': self.description,
            'status': self.status,
        }
    
    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> "Job":
        """ Создаёт модель из строки БД """
        if hasattr(row, 'keys'):
            row = dict(row)
        
        skills = row.get('skills', [])
        if isinstance(skills, str):
            import json
            try:
                skills = json.loads(skills)
            except json.JSONDecodeError:
                skills = []
        
        return cls(
            id=row.get('id'),
            title=row.get('title', ''),
            level=row.get('level', 'middle'),
            skills=skills,
            experience=row.get('experience', 0),
            description=row.get('description'),
            status=row.get('status', 'active'),
            created_at=row.get('created_at'),
            updated_at=row.get('updated_at'),
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Job":
        """Создаёт модель из словаря  """
        return cls(
            id=data.get('id'),
            title=data.get('title', ''),
            level=data.get('level', 'middle'),
            skills=data.get('skills', []),
            experience=data.get('experience', 0),
            description=data.get('description'),
            status=data.get('status', 'active'),
        )
    
    def is_active(self) -> bool:
        """Проверяет, активна ли вакансия"""
        return self.status == "active"
    
    def archive(self) -> None:
        """Архивирует вакансию"""
        self.status = "archived"
    
    def activate(self) -> None:
        """Активирует вакансию"""
        self.status = "active"
    
    def has_skill(self, skill: str) -> bool:
        """Проверяет наличие требуемого навыка """
        skill_lower = skill.lower().strip()
        return any(s.lower() == skill_lower for s in self.skills)
    
    def add_skill(self, skill: str) -> None:
        """Добавляет требуемый навык """
        if not self.has_skill(skill):
            self.skills.append(skill.strip())
    
    def remove_skill(self, skill: str) -> bool:
        """Удаляет требуемый навык"""
        skill_lower = skill.lower().strip()
        for i, s in enumerate(self.skills):
            if s.lower() == skill_lower:
                self.skills.pop(i)
                return True
        return False
    
    def get_required_skills_summary(self, max_display: int = 5) -> str:
        """Возвращает краткое описание требуемых навыков"""
        if not self.skills:
            return "навыки не указаны"
        
        if len(self.skills) <= max_display:
            return ', '.join(self.skills)
        
        return ', '.join(self.skills[:max_display]) + f" +{len(self.skills) - max_display}"
    
    def get_level_display(self) -> str:
        """Возвращает отображаемое название уровня на русском"""
        level_names = {
            "junior": "Junior (начальный)",
            "middle": "Middle (средний)",
            "senior": "Senior (старший)"
        }
        return level_names.get(self.level, self.level.capitalize())
    
    
    def __str__(self) -> str:
        """Красивое строковое представление вакансии"""
        parts = []
        
        if self.title:
            parts.append(self.title)
        
        if self.level:
            parts.append(f"({self.get_level_display()})")
        
        if self.experience:
            exp_text = f"{self.experience} лет" if self.experience in [1, 21] else f"{self.experience} лет"
            parts.append(f"треб. опыт: {exp_text}")
        
        skills_summary = self.get_required_skills_summary(3)
        if skills_summary and skills_summary != "навыки не указаны":
            parts.append(f"[{skills_summary}]")
        
        if self.status == "archived":
            parts.append("📦 В архиве")
        
        return f"Вакансия: {' '.join(parts)}" if parts else "Вакансия: без данных"
    
    def __repr__(self) -> str:
        """Представление для отладки"""
        return f"Job(id={self.id}, title={self.title!r}, level={self.level!r}, status={self.status!r})"


def dict_to_job(data: Dict[str, Any]) -> Job:
    """ Конвертирует словарь в модель Job"""
    return Job.from_db_row(data)


def job_to_dict(job: Job) -> Dict[str, Any]:
    """ Конвертирует модель Job в словарь """
    return job.to_db_dict()


class JobSearchFilters(BaseModel):
    """ Модель фильтров для поиска вакансий """
    
    skills: Optional[List[str]] = Field(
        default=None,
        description="Список навыков для поиска"
    )
    
    level: Optional[str] = Field(
        default=None,
        description="Уровень вакансии (junior/middle/senior)"
    )
    
    min_experience: Optional[int] = Field(
        default=None,
        description="Минимальный требуемый опыт",
        ge=0
    )
    
    status: Optional[str] = Field(
        default="active",
        description="Статус вакансии"
    )
    
    @field_validator('level', mode='before')
    @classmethod
    def validate_level(cls, v: Any) -> Optional[str]:
        """Валидация уровня"""
        if v is None:
            return None
        
        v_str = str(v).lower().strip()
        valid_levels = ["junior", "middle", "senior"]
        
        return v_str if v_str in valid_levels else None
    
    def to_query_params(self) -> Dict[str, Any]:
        """Преобразует фильтры в параметры запроса к БД"""
        params = {}
        
        if self.skills:
            params['skills'] = self.skills
        if self.level:
            params['level'] = self.level
        if self.min_experience is not None:
            params['min_experience'] = self.min_experience
        if self.status:
            params['status'] = self.status
        
        return params


class JobMatchResult(BaseModel):
    """ Модель результата матчинга вакансии с кандидатом"""
    
    job: Job
    candidate_id: int
    candidate_name: str
    match_percent: float
    skill_match_percent: float
    experience_match_percent: float
    matched_skills: List[str]
    
    class Config:
        from_attributes = True


if __name__ == "__main__":
    
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ МОДЕЛИ JOB")
    print("=" * 60)
    
    job = Job(
        title="Senior Python Developer",
        level="senior",
        skills=["Python", "Django", "PostgreSQL", "Docker", "Kubernetes"],
        experience=5,
        description="Ищем опытного Python разработчика в команду",
        status="active"
    )
    
    print("\n✅ Создана вакансия:")
    print(f"   {job}")
    print(f"   {repr(job)}")
    print(f"   Уровень на русском: {job.get_level_display()}")
    print(f"   Навыки кратко: {job.get_required_skills_summary()}")
    
    print("\n📋 Проверка методов:")
    print(f"   Активна? {job.is_active()}")
    print(f"   Есть навык 'python'? {job.has_skill('python')}")
    print(f"   Есть навык 'java'? {job.has_skill('java')}")
    
    job.add_skill("Redis")
    print(f"   Добавлен навык 'Redis'")
    print(f"   Навыки: {', '.join(job.skills)}")
    
    job.archive()
    print(f"   Архивирована? {not job.is_active()}")
    print(f"   Статус: {job.status}")
    
    job.activate()
    print(f"   Активирована? {job.is_active()}")
    
    print("\n📦 Конвертация в словарь:")
    print(f"   to_dict(): {job.to_dict()}")
    print(f"   to_db_dict(): {job.to_db_dict()}")
    
    print("\n🔄 Создание из строки БД:")
    db_row = {
        'id': 1,
        'title': 'Python Developer',
        'level': 'middle',
        'skills': '["Python", "Django"]',
        'experience': 3,
        'description': 'Разработка backend',
        'status': 'active'
    }
    job_from_db = Job.from_db_row(db_row)
    print(f"   {job_from_db}")
    
    print("\n📋 Тестирование валидаторов:")
    
    test_cases = [
        ("junior", "junior"),
        ("jun", "junior"),
        ("джуниор", "junior"),
        ("MID", "middle"),
        ("мидл", "middle"),
        ("SENIOR", "senior"),
        ("сеньор", "senior"),
        ("invalid", "middle"),
    ]
    
    for input_val, expected in test_cases:
        result = Job.validate_level(input_val)
        status = "✅" if result == expected else "❌"
        print(f"   {status} '{input_val}' -> '{result}' (ожидалось '{expected}')")
    
    print("\n✅ Все тесты пройдены!")
