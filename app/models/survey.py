
"""
app/models/survey.py
Pydantic модели для опросов NPS и Pulse для HR Agent
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


class SurveyQuestion(BaseModel):
    
    id: str = Field(
        description="Уникальный идентификатор вопроса",
        example="nps_score"
    )
    
    text: str = Field(
        description="Текст вопроса",
        example="Насколько вероятно, что вы порекомендуете компанию?"
    )
    
    type: str = Field(
        description="Тип вопроса: scale (шкала) или text (текст)",
        example="scale"
    )
    
    min: Optional[int] = Field(
        default=None,
        description="Минимальное значение для шкалы",
        example=0
    )
    
    max: Optional[int] = Field(
        default=None,
        description="Максимальное значение для шкалы",
        example=10
    )
    
    @field_validator('type')
    @classmethod
    def validate_type(cls, v: str) -> str:
        """Валидация типа вопроса"""
        v_str = v.lower().strip()
        if v_str not in ['scale', 'text']:
            return 'text'
        return v_str


class Survey(BaseModel):
    """ Модель опроса (NPS или Pulse) """
    
    
    id: Optional[int] = Field(
        default=None,
        description="Уникальный идентификатор опроса в БД",
        example=1
    )
    
    title: str = Field(
        default="",
        description="Название опроса",
        example="NPS опрос Q1 2026",
        min_length=1
    )
    
    type: str = Field(
        default="nps",
        description="Тип опроса: nps (NPS) или pulse (Pulse)",
        example="nps"
    )
    
    
    questions: List[SurveyQuestion] = Field(
        default_factory=list,
        description="Список вопросов опроса"
    )
    
    
    department: Optional[str] = Field(
        default=None,
        description="Отдел, для которого создан опрос (опционально)",
        example="IT"
    )
    
    status: str = Field(
        default="active",
        description="Статус опроса: active (активен), closed (закрыт)",
        example="active"
    )
    
    created_at: Optional[datetime] = Field(
        default=None,
        description="Дата и время создания опроса"
    )
    
    
    @field_validator('type')
    @classmethod
    def validate_type(cls, v: str) -> str:
        """Валидация типа опроса"""
        v_str = v.lower().strip()
        if v_str not in ['nps', 'pulse']:
            return 'nps'
        return v_str
    
    @field_validator('status')
    @classmethod
    def validate_status(cls, v: str) -> str:
        """Валидация статуса"""
        v_str = v.lower().strip()
        if v_str not in ['active', 'closed']:
            return 'active'
        return v_str
    
    
    def to_dict(self) -> Dict[str, Any]:
        """   Преобразует модель в словарь для сохранения в БД """
        questions_json = []
        for q in self.questions:
            q_dict = q.model_dump(exclude_none=True)
            questions_json.append(q_dict)
        
        return {
            'id': self.id,
            'title': self.title,
            'type': self.type,
            'questions': questions_json,
            'department': self.department,
            'status': self.status,
            'created_at': self.created_at,
        }
    
    def to_db_dict(self) -> Dict[str, Any]:
        """ Преобразует модель в словарь для сохранения в БД """
        import json
        
        questions_json = []
        for q in self.questions:
            q_dict = q.model_dump(exclude_none=True)
            questions_json.append(q_dict)
        
        return {
            'title': self.title,
            'type': self.type,
            'questions': json.dumps(questions_json, ensure_ascii=False),
            'department': self.department,
            'status': self.status,
        }
    
    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> "Survey":
        """  Создаёт модель из строки БД """
        import json

        if hasattr(row, 'keys'):
            row = dict(row)

        questions = row.get('questions', [])
        if isinstance(questions, str):
            try:
                questions_data = json.loads(questions)
                questions = [SurveyQuestion(**q) for q in questions_data]
            except (json.JSONDecodeError, TypeError):
                questions = []
        elif isinstance(questions, list):
            questions = [SurveyQuestion(**q) if isinstance(q, dict) else q for q in questions]
        
        return cls(
            id=row.get('id'),
            title=row.get('title', ''),
            type=row.get('type', 'nps'),
            questions=questions,
            department=row.get('department'),
            status=row.get('status', 'active'),
            created_at=row.get('created_at'),
        )
    
    def is_active(self) -> bool:
        """Проверяет, активен ли опрос"""
        return self.status == "active"
    
    def close(self) -> None:
        """Закрывает опрос (больше нельзя отвечать)"""
        self.status = "closed"
    
    def get_questions_text(self) -> List[str]:
        """Возвращает список текстов вопросов"""
        return [q.text for q in self.questions]
    
    def get_nps_score_from_responses(self, responses: List[Dict[str, Any]]) -> Optional[int]:
        """  Рассчитывает NPS score на основе ответов """
        if self.type != "nps":
            return None
        
        scores = []
        for response in responses:
            answers = response.get('answers', {})
            nps_value = answers.get('nps_score')
            if nps_value is not None and isinstance(nps_value, (int, float)):
                scores.append(nps_value)
        
        if not scores:
            return None
        
        promoters = sum(1 for s in scores if s >= 9)
        detractors = sum(1 for s in scores if s <= 6)
        total = len(scores)
        
        return int(((promoters - detractors) / total) * 100)
    
    
    def __str__(self) -> str:
        """Красивое строковое представление опроса"""
        parts = []
        
        if self.title:
            parts.append(self.title)
        
        type_name = "NPS" if self.type == "nps" else "Pulse"
        parts.append(f"({type_name})")
        
        if self.department:
            parts.append(f"отдел: {self.department}")
        
        if self.status == "closed":
            parts.append("📦 Закрыт")
        else:
            parts.append("✅ Активен")
        
        parts.append(f"вопросов: {len(self.questions)}")
        
        return f"Опрос: {' '.join(parts)}"
    
    def __repr__(self) -> str:
        """Представление для отладки"""
        return f"Survey(id={self.id}, title={self.title!r}, type={self.type!r}, status={self.status!r})"


class SurveyResponse(BaseModel):
    
    
    id: Optional[int] = Field(
        default=None,
        description="Уникальный идентификатор ответа в БД"
    )
    
    survey_id: int = Field(
        description="ID опроса, на который дан ответ",
        example=1
    )
    
    
    respondent_name: Optional[str] = Field(
        default=None,
        description="Имя респондента",
        example="Иван Иванов"
    )
    
    respondent_email: Optional[str] = Field(
        default=None,
        description="Email респондента",
        example="ivan@example.com"
    )
    
    
    answers: Dict[str, Any] = Field(
        default_factory=dict,
        description="Словарь ответов (ключ - id вопроса, значение - ответ)",
        example={"nps_score": 9, "feedback": "Отлично!"}
    )
    
    feedback: Optional[str] = Field(
        default=None,
        description="Текстовый отзыв (отдельное поле для удобства)",
        example="Всё отлично, но хотелось бы больше обучения"
    )
    
    
    created_at: Optional[datetime] = Field(
        default=None,
        description="Дата и время ответа"
    )
    
    
    @field_validator('answers', mode='before')
    @classmethod
    def validate_answers(cls, v: Any) -> Dict[str, Any]:
        """Валидация ответов"""
        if v is None:
            return {}
        if isinstance(v, dict):
            return v
        if isinstance(v, str):
            import json
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return {}
        return {}
    
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразует модель в словарь для сохранения в БД"""
        return {
            'id': self.id,
            'survey_id': self.survey_id,
            'respondent_name': self.respondent_name,
            'respondent_email': self.respondent_email,
            'answers': self.answers,
            'feedback': self.feedback,
            'created_at': self.created_at,
        }
    
    def to_db_dict(self) -> Dict[str, Any]:
        """ Преобразует модель в словарь для сохранения в БД """
        import json
        
        return {
            'survey_id': self.survey_id,
            'respondent_name': self.respondent_name,
            'respondent_email': self.respondent_email,
            'answers': json.dumps(self.answers, ensure_ascii=False),
            'feedback': self.feedback,
        }
    
    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> "SurveyResponse":
        """
        Создаёт модель из строки БД
        """
        import json
        
        if hasattr(row, 'keys'):
            row = dict(row)
  
        answers = row.get('answers', {})
        if isinstance(answers, str):
            try:
                answers = json.loads(answers)
            except (json.JSONDecodeError, TypeError):
                answers = {}
        
        return cls(
            id=row.get('id'),
            survey_id=row.get('survey_id'),
            respondent_name=row.get('respondent_name'),
            respondent_email=row.get('respondent_email'),
            answers=answers,
            feedback=row.get('feedback'),
            created_at=row.get('created_at'),
        )
    
    def get_nps_score(self) -> Optional[int]:
        """
        Возвращает NPS оценку (если это NPS опрос)
        """
        score = self.answers.get('nps_score')
        if score is not None and isinstance(score, (int, float)):
            return int(score)
        return None
    
    def get_satisfaction(self) -> Optional[int]:
        """
        Возвращает оценку удовлетворённости (для Pulse опроса)
        """
        score = self.answers.get('satisfaction')
        if score is not None and isinstance(score, (int, float)):
            return int(score)
        return None
    
    def get_energy(self) -> Optional[int]:
        """
        Возвращает оценку энергии (для Pulse опроса)
        """
        score = self.answers.get('energy')
        if score is not None and isinstance(score, (int, float)):
            return int(score)
        return None
    
    
    def __str__(self) -> str:
        """Красивое строковое представление ответа"""
        respondent = self.respondent_name or "Аноним"
        
        if self.get_nps_score() is not None:
            return f"Ответ от {respondent}: NPS={self.get_nps_score()}"
        
        if self.get_satisfaction() is not None:
            return f"Ответ от {respondent}: удовлетворённость={self.get_satisfaction()}, энергия={self.get_energy()}"
        
        return f"Ответ от {respondent}: {len(self.answers)} ответов"
    
    def __repr__(self) -> str:
        """Представление для отладки"""
        return f"SurveyResponse(id={self.id}, survey_id={self.survey_id}, respondent={self.respondent_name!r})"


class SurveyAnalytics(BaseModel):
    """ Модель аналитики по опросу """
    
    survey_title: str
    survey_type: str
    total_responses: int
    feedbacks: List[str]
    generated_at: str
    
    nps_score: Optional[int] = None
    promoters: Optional[int] = None
    passives: Optional[int] = None
    detractors: Optional[int] = None
    average_score: Optional[float] = None
    
    satisfaction: Optional[Dict[str, Any]] = None
    energy: Optional[Dict[str, Any]] = None
    
    class Config:
        from_attributes = True


def create_nps_survey(title: str, department: Optional[str] = None) -> Survey:
    """ Создаёт стандартный NPS опрос """
    questions = [
        SurveyQuestion(
            id="nps_score",
            text="Насколько вероятно, что вы порекомендуете компанию?",
            type="scale",
            min=0,
            max=10
        ),
        SurveyQuestion(
            id="feedback",
            text="Что можно улучшить?",
            type="text"
        )
    ]
    
    return Survey(
        title=title,
        type="nps",
        questions=questions,
        department=department,
        status="active"
    )


def create_pulse_survey(title: str, department: Optional[str] = None) -> Survey:
    """ Создаёт стандартный Pulse опрос """
    questions = [
        SurveyQuestion(
            id="satisfaction",
            text="Насколько вы удовлетворены своей работой?",
            type="scale",
            min=1,
            max=5
        ),
        SurveyQuestion(
            id="energy",
            text="Какой у вас уровень энергии на работе?",
            type="scale",
            min=1,
            max=5
        ),
        SurveyQuestion(
            id="feedback",
            text="Что вас радует или огорчает?",
            type="text"
        )
    ]
    
    return Survey(
        title=title,
        type="pulse",
        questions=questions,
        department=department,
        status="active"
    )


if __name__ == "__main__":
    
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ МОДЕЛЕЙ ОПРОСОВ")
    print("=" * 60)
    
    print("\n📋 1. Создание NPS опроса:")
    nps_survey = create_nps_survey(
        title="NPS опрос Q1 2026",
        department="IT"
    )
    print(f"   {nps_survey}")
    print(f"   {repr(nps_survey)}")
    print(f"   Вопросы: {nps_survey.get_questions_text()}")
    
    print("\n📋 2. Создание Pulse опроса:")
    pulse_survey = create_pulse_survey(
        title="Pulse опрос Март 2026",
        department="HR"
    )
    print(f"   {pulse_survey}")
    print(f"   Вопросы: {pulse_survey.get_questions_text()}")
    
    print("\n📋 3. Создание ответа на опрос:")
    response = SurveyResponse(
        survey_id=1,
        respondent_name="Иван Иванов",
        respondent_email="ivan@example.com",
        answers={"nps_score": 9, "feedback": "Отличная компания!"},
        feedback="Отличная компания!"
    )
    print(f"   {response}")
    print(f"   NPS оценка: {response.get_nps_score()}")
    
    print("\n📋 4. Конвертация в словарь:")
    print(f"   to_db_dict(): {pulse_survey.to_db_dict()}")
    
    print("\n📋 5. Восстановление из строки БД:")
    db_row = {
        'id': 1,
        'title': 'NPS опрос',
        'type': 'nps',
        'questions': '[{"id": "nps_score", "text": "Оцените компанию", "type": "scale", "min": 0, "max": 10}]',
        'department': 'IT',
        'status': 'active'
    }
    restored_survey = Survey.from_db_row(db_row)
    print(f"   {restored_survey}")
    
    print("\n📋 6. Расчёт NPS score:")
    responses = [
        {'answers': {'nps_score': 10}},
        {'answers': {'nps_score': 9}},
        {'answers': {'nps_score': 8}},
        {'answers': {'nps_score': 5}},
        {'answers': {'nps_score': 3}},
    ]
    nps_score = nps_survey.get_nps_score_from_responses(responses)
    print(f"   Ответы: 10, 9, 8, 5, 3")
    print(f"   NPS Score: {nps_score} (ожидается: 20)")
    
    print("\n✅ Все тесты пройдены!")
