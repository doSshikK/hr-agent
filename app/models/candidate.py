"""
app/models/candidate.py
Pydantic модель кандидата для HR Agent
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, field_validator


class Candidate(BaseModel):

    
    id: Optional[int] = Field(
        default=None,
        description="Уникальный идентификатор кандидата в БД"
    )
    
    name: Optional[str] = Field(
        default=None,
        description="ФИО кандидата",
        example="Иванов Иван Иванович"
    )
    
    email: Optional[EmailStr] = Field(
        default=None,
        description="Email адрес кандидата",
        example="ivan@example.com"
    )
    
    phone: Optional[str] = Field(
        default=None,
        description="Номер телефона кандидата",
        example="+79001234567"
    )

    
    telegram_id: Optional[int] = Field(
        default=None,
        description="Telegram ID кандидата"
    )
    
    source: Optional[str] = Field(
        default="telegram",
        description="Источник: telegram или email"
    )
    
    status: Optional[str] = Field(
        default="candidate",
        description="Статус кандидата: candidate, hired, rejected"
    )

    hired_position: Optional[str] = Field(
        default=None,
        description="Должность, на которую кандидат получил оффер"
    )

    salary: Optional[int] = Field(
        default=None,
        description="Зарплата в оффере"
    )

    hired_at: Optional[datetime] = Field(
        default=None,
        description="Дата выхода на работу"
    )
    
    interview_stage: Optional[str] = Field(
        default=None,
        description="Статус собеседования: invited, scheduled, completed, cancelled, declined"
    )
    
    
    skills: List[str] = Field(
        default_factory=list,
        description="Список навыков кандидата",
        example=["Python", "Django", "PostgreSQL", "Docker"]
    )
    
    experience_years: int = Field(
        default=0,
        description="Опыт работы в годах",
        ge=0,
        example=5
    )
    
    last_position: Optional[str] = Field(
        default=None,
        description="Последняя должность",
        example="Senior Python Developer"
    )
    
    last_company: Optional[str] = Field(
        default=None,
        description="Последняя компания",
        example="Яндекс"
    )
    
    
    file_name: Optional[str] = Field(
        default=None,
        description="Имя файла резюме",
        example="resume_ivanov.pdf"
    )
    
    file_hash: Optional[str] = Field(
        default=None,
        description="MD5 хеш файла для предотвращения дубликатов",
        example="5d41402abc4b2a76b9719d911017c592"
    )
    
    
    raw_data: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Сырые данные из резюме (JSON словарь)"
    )
    
    
    created_at: Optional[datetime] = Field(
        default=None,
        description="Дата и время создания записи"
    )
    
    updated_at: Optional[datetime] = Field(
        default=None,
        description="Дата и время последнего обновления"
    )
    
    
    match_percent: Optional[int] = Field(
        default=None,
        description="Процент совпадения с запросом/вакансией (0-100)",
        ge=0,
        le=100
    )
    
    matched_skills: Optional[List[str]] = Field(
        default=None,
        description="Список навыков, которые совпали с запросом"
    )
    
    skills_score: Optional[int] = Field(
        default=None,
        description="Оценка совпадения по навыкам (0-100)",
        ge=0,
        le=100
    )
    
    exp_score: Optional[int] = Field(
        default=None,
        description="Оценка совпадения по опыту (0-100)",
        ge=0,
        le=100
    )
    
    pos_score: Optional[int] = Field(
        default=None,
        description="Оценка совпадения по должности (0-100)",
        ge=0,
        le=100
    )
    
    
    @field_validator('experience_years', mode='before')
    @classmethod
    def validate_experience(cls, v: Any) -> int:
        """Валидация опыта работы"""
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
    
    @field_validator('phone', mode='before')
    @classmethod
    def validate_phone(cls, v: Any) -> Optional[str]:
        """Валидация телефона"""
        if v is None:
            return None
        if not isinstance(v, str):
            v = str(v)
        import re
        cleaned = re.sub(r'[^\d+]', '', v)
        return cleaned if cleaned else None
    
    
    def to_dict(self) -> Dict[str, Any]:
        """ Преобразует модель в словарь для сохранения в БД """
        data = self.model_dump(exclude_none=True, exclude={'created_at', 'updated_at'})
        
        if 'skills' in data and isinstance(data['skills'], list):
            data['skills'] = data['skills']  # skills хранятся через связную таблицу
        
        return data
    
    def to_db_dict(self) -> Dict[str, Any]:
        """ Преобразует модель в словарь для прямого сохранения в БД """
        return {
            'name': self.name,
            'email': self.email,
            'phone': self.phone,
            'experience_years': self.experience_years,
            'last_position': self.last_position,
            'last_company': self.last_company,
            'skills': self.skills,
            'file_name': self.file_name,
            'file_hash': self.file_hash,
            'raw_data': self.raw_data,
        }
    
    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> "Candidate":
        """
        Создаёт модель из строки БД
        """
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
            name=row.get('name'),
            email=row.get('email'),
            phone=row.get('phone'),
            skills=skills,
            experience_years=row.get('experience_years', 0),
            last_position=row.get('last_position'),
            last_company=row.get('last_company'),
            file_name=row.get('file_name'),
            file_hash=row.get('file_hash'),
            raw_data=row.get('raw_data'),
            created_at=row.get('created_at'),
            updated_at=row.get('updated_at'),
            telegram_id=row.get('telegram_id'),
            source=row.get('source', 'telegram'),
            status=row.get('status', 'candidate'),
            hired_position=row.get('hired_position'),
            salary=row.get('salary'),
            hired_at=row.get('hired_at'),
            interview_stage=row.get('interview_stage'),
        )
    
    @classmethod
    def from_parsed_resume(cls, parsed_data: Dict[str, Any], file_path: str = None) -> "Candidate":
        """ Создаёт модель из результата парсинга резюме """
        import os
        from pathlib import Path
        
        return cls(
            name=parsed_data.get('name'),
            email=parsed_data.get('email'),
            phone=parsed_data.get('phone'),
            skills=parsed_data.get('skills', []),
            experience_years=parsed_data.get('experience_years', 0),
            last_position=parsed_data.get('last_position'),
            last_company=parsed_data.get('last_company'),
            file_name=parsed_data.get('file_name') or (Path(file_path).name if file_path else None),
            file_hash=parsed_data.get('file_hash'),
            raw_data=parsed_data.get('raw_data'),
        )
    
    def get_search_score(self) -> int:
        """Возвращает процент совпадения для результатов поиска"""
        return self.match_percent or 0
    
    def has_skill(self, skill: str) -> bool:
        """Проверяет наличие навыка (регистронезависимо)"""
        skill_lower = skill.lower().strip()
        return any(s.lower() == skill_lower for s in self.skills)
    
    def add_skill(self, skill: str) -> None:
        """Добавляет навык (если ещё нет)"""
        if not self.has_skill(skill):
            self.skills.append(skill.strip())
    
    def remove_skill(self, skill: str) -> bool:
        """Удаляет навык (если есть)"""
        skill_lower = skill.lower().strip()
        for i, s in enumerate(self.skills):
            if s.lower() == skill_lower:
                self.skills.pop(i)
                return True
        return False
    
    
    def __str__(self) -> str:
        """Красивое строковое представление кандидата"""
        parts = []
        if self.name:
            parts.append(self.name)
        if self.email:
            parts.append(f"({self.email})")
        if self.experience_years:
            parts.append(f"{self.experience_years} лет опыта")
        if self.skills:
            skills_preview = ', '.join(self.skills[:3])
            if len(self.skills) > 3:
                skills_preview += f" +{len(self.skills) - 3}"
            parts.append(f"[{skills_preview}]")
        
        return f"Кандидат: {' '.join(parts)}" if parts else "Кандидат: без данных"
    
    def __repr__(self) -> str:
        """Представление для отладки"""
        return f"Candidate(id={self.id}, name={self.name!r}, email={self.email!r}, experience={self.experience_years})"


def dict_to_candidate(data: Dict[str, Any]) -> Candidate:
    """ Конвертирует словарь в модель Candidate """
    return Candidate.from_db_row(data)


if __name__ == "__main__":
    
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ МОДЕЛИ CANDIDATE")
    print("=" * 60)
    
    candidate = Candidate(
        name="Иванов Иван Иванович",
        email="ivan@example.com",
        phone="+7 (900) 123-45-67",
        skills=["Python", "Django", "PostgreSQL", "Docker"],
        experience_years=5,
        last_position="Senior Python Developer",
        last_company="Яндекс",
        file_name="resume_ivanov.pdf"
    )
    
    print("\n✅ Создан кандидат:")
    print(f"   {candidate}")
    print(f"   {repr(candidate)}")
    
    print("\n📋 Проверка методов:")
    print(f"   Есть навык 'python'? {candidate.has_skill('python')}")
    print(f"   Есть навык 'java'? {candidate.has_skill('java')}")
    
    candidate.add_skill("FastAPI")
    print(f"   Добавлен навык 'FastAPI'")
    print(f"   Навыки: {', '.join(candidate.skills)}")
    
    print("\n📦 Конвертация в словарь:")
    print(f"   to_dict(): {candidate.to_dict()}")
    print(f"   to_db_dict(): {candidate.to_db_dict()}")
    
    print("\n🔄 Создание из строки БД:")
    db_row = {
        'id': 1,
        'name': 'Петров Петр',
        'email': 'petr@example.com',
        'experience_years': 3,
        'last_position': 'Python Developer',
    }
    candidate_from_db = Candidate.from_db_row(db_row)
    print(f"   {candidate_from_db}")
    
    print("\n✅ Все тесты пройдены!")
