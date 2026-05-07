"""
app/utils/export.py
Экспорт данных в PDF с помощью reportlab 
"""

from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib import colors
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    print("⚠️ reportlab не установлен. Установите: pip install reportlab")

try:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False


def safe_text(text: Any, default: str = "—") -> str:
    """Безопасное преобразование текста в строку"""
    if text is None:
        return default
    if isinstance(text, (int, float)):
        return str(text)
    if isinstance(text, list):
        return ', '.join([safe_text(t) for t in text])
    return str(text)


def register_fonts():
    """Регистрирует шрифты с поддержкой кириллицы"""
    font_paths = [
        "/System/Library/Fonts/Helvetica.ttc",  # macOS
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # Linux
        "C:\\Windows\\Fonts\\Arial.ttf",  # Windows
        "/System/Library/Fonts/Supplemental/Arial.ttf",  # macOS alternative
    ]
    
    for font_path in font_paths:
        if Path(font_path).exists():
            try:
                pdfmetrics.registerFont(TTFont('RussianFont', font_path))
                return 'RussianFont'
            except Exception:
                continue
    
    return 'Helvetica'

FONT_NAME = None


def get_font_name():
    """Возвращает имя зарегистрированного шрифта"""
    global FONT_NAME
    if FONT_NAME is None:
        FONT_NAME = register_fonts()
    return FONT_NAME


def export_candidate_to_pdf(candidate: Dict[str, Any], filename: str = None) -> Optional[str]:
    """Экспортирует информацию о кандидате в PDF"""
    if not REPORTLAB_AVAILABLE:
        print("❌ reportlab не установлен. Установите: pip install reportlab")
        return None
    
    if filename is None:
        name = candidate.get('name', 'candidate').replace(' ', '_')
        filename = f"candidate_{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    
    try:
        doc = SimpleDocTemplate(filename, pagesize=A4)
        story = []
        
        styles = getSampleStyleSheet()
        font_name = get_font_name()
        
        title_style = ParagraphStyle(
            'RussianTitle',
            parent=styles['Title'],
            fontName=font_name,
            fontSize=16,
            alignment=1,
            spaceAfter=20
        )
        
        heading_style = ParagraphStyle(
            'RussianHeading',
            parent=styles['Heading1'],
            fontName=font_name,
            fontSize=12,
            spaceBefore=10,
            spaceAfter=5
        )
        
        normal_style = ParagraphStyle(
            'RussianNormal',
            parent=styles['Normal'],
            fontName=font_name,
            fontSize=10,
            spaceAfter=3
        )
        
        story.append(Paragraph("Карточка кандидата", title_style))
        story.append(Spacer(1, 10))
        
        story.append(Paragraph("Личные данные:", heading_style))
        story.append(Paragraph(f"ФИО: {safe_text(candidate.get('name', '—'))}", normal_style))
        story.append(Paragraph(f"Email: {safe_text(candidate.get('email', '—'))}", normal_style))
        story.append(Paragraph(f"Телефон: {safe_text(candidate.get('phone', '—'))}", normal_style))
        story.append(Spacer(1, 10))
        
        story.append(Paragraph("Профессиональные данные:", heading_style))
        story.append(Paragraph(f"Опыт: {safe_text(candidate.get('experience_years', 0))} лет", normal_style))
        story.append(Paragraph(f"Последняя должность: {safe_text(candidate.get('last_position', '—'))}", normal_style))
        story.append(Paragraph(f"Последняя компания: {safe_text(candidate.get('last_company', '—'))}", normal_style))
        story.append(Spacer(1, 10))
        
        skills = candidate.get('skills', [])
        if skills:
            story.append(Paragraph("Навыки:", heading_style))
            story.append(Paragraph(', '.join([safe_text(s) for s in skills]), normal_style))
        
        doc.build(story)
        print(f"✅ PDF сохранён: {filename}")
        return filename
        
    except Exception as e:
        print(f"Ошибка при сохранении PDF: {e}")
        return None


def export_job_to_pdf(job: Dict[str, Any], filename: str = None) -> Optional[str]:
    """Экспортирует информацию о вакансии в PDF"""
    if not REPORTLAB_AVAILABLE:
        return None
    
    if filename is None:
        title = job.get('title', 'job').replace(' ', '_')
        filename = f"job_{title}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    
    try:
        doc = SimpleDocTemplate(filename, pagesize=A4)
        story = []
        
        styles = getSampleStyleSheet()
        font_name = get_font_name()
        
        title_style = ParagraphStyle(
            'RussianTitle',
            parent=styles['Title'],
            fontName=font_name,
            fontSize=16,
            alignment=1,
            spaceAfter=20
        )
        
        heading_style = ParagraphStyle(
            'RussianHeading',
            parent=styles['Heading1'],
            fontName=font_name,
            fontSize=12,
            spaceBefore=10,
            spaceAfter=5
        )
        
        normal_style = ParagraphStyle(
            'RussianNormal',
            parent=styles['Normal'],
            fontName=font_name,
            fontSize=10,
            spaceAfter=3
        )
        
        story.append(Paragraph("Карточка вакансии", title_style))
        story.append(Spacer(1, 10))
        
        story.append(Paragraph("Информация о вакансии:", heading_style))
        story.append(Paragraph(f"Название: {safe_text(job.get('title', '—'))}", normal_style))
        story.append(Paragraph(f"Уровень: {safe_text(job.get('level', '—'))}", normal_style))
        story.append(Paragraph(f"Требуемый опыт: {safe_text(job.get('experience', 0))} лет", normal_style))
        story.append(Paragraph(f"Статус: {safe_text(job.get('status', '—'))}", normal_style))
        story.append(Spacer(1, 10))
        
        skills = job.get('skills', [])
        if skills:
            story.append(Paragraph("Требуемые навыки:", heading_style))
            story.append(Paragraph(', '.join([safe_text(s) for s in skills]), normal_style))
            story.append(Spacer(1, 10))
        
        description = job.get('description', '')
        if description and description != 'None':
            story.append(Paragraph("Описание:", heading_style))
            story.append(Paragraph(safe_text(description), normal_style))
        
        doc.build(story)
        print(f"✅ PDF сохранён: {filename}")
        return filename
        
    except Exception as e:
        print(f"Ошибка при сохранении PDF: {e}")
        return None


def export_test_to_pdf(test: Dict[str, Any], filename: str = None) -> Optional[str]:
    """Экспортирует тестовое задание в PDF"""
    if not REPORTLAB_AVAILABLE:
        print("❌ reportlab не установлен. Установите: pip install reportlab")
        return None
    
    if filename is None:
        title = test.get('title', 'test')
        import re
        safe_title = re.sub(r'[<>:"/\\|?*]', '_', title)
        safe_title = safe_title.replace(' ', '_')
        if len(safe_title) > 100:
            safe_title = safe_title[:100]
        filename = f"test_{safe_title}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    
    try:
        doc = SimpleDocTemplate(filename, pagesize=A4)
        story = []
        
        styles = getSampleStyleSheet()
        font_name = get_font_name()
        
        title_style = ParagraphStyle(
            'RussianTitle',
            parent=styles['Title'],
            fontName=font_name,
            fontSize=16,
            alignment=1,
            spaceAfter=20
        )
        
        heading_style = ParagraphStyle(
            'RussianHeading',
            parent=styles['Heading1'],
            fontName=font_name,
            fontSize=12,
            spaceBefore=10,
            spaceAfter=5
        )
        
        normal_style = ParagraphStyle(
            'RussianNormal',
            parent=styles['Normal'],
            fontName=font_name,
            fontSize=10,
            spaceAfter=3
        )
        
        story.append(Paragraph(safe_text(test.get('title', 'Тестовое задание')), title_style))
        story.append(Spacer(1, 10))
        
        story.append(Paragraph("Информация о задании:", heading_style))
        story.append(Paragraph(f"Направление: {safe_text(test.get('direction_name', test.get('direction', '—')))}", normal_style))
        story.append(Paragraph(f"Уровень: {safe_text(test.get('level', '—')).upper()}", normal_style))
        story.append(Paragraph(f"Срок выполнения: {safe_text(test.get('deadline', '—'))}", normal_style))
        story.append(Paragraph(f"Тип проекта: {safe_text(test.get('project_type', '—'))}", normal_style))
        
        if test.get('theme'):
            story.append(Paragraph(f"Тема: {safe_text(test['theme'])}", normal_style))
        
        story.append(Spacer(1, 10))
        
        story.append(Paragraph("Задачи:", heading_style))
        tasks = test.get('tasks', [])
        for i, task in enumerate(tasks, 1):
            story.append(Paragraph(f"{i}. {safe_text(task)}", normal_style))
        story.append(Spacer(1, 10))
        
        story.append(Paragraph("Технические требования:", heading_style))
        for req in test.get('requirements', []):
            story.append(Paragraph(f"• {safe_text(req)}", normal_style))
        story.append(Spacer(1, 10))
        
        stack = test.get('stack', [])
        if stack:
            story.append(Paragraph("Стек технологий:", heading_style))
            story.append(Paragraph(', '.join([safe_text(s) for s in stack]), normal_style))
            story.append(Spacer(1, 10))
        
        story.append(Paragraph(f"Сгенерировано: {safe_text(test.get('generated_at', datetime.now().strftime('%Y-%m-%d %H:%M:%S')))}", normal_style))
        
        doc.build(story)
        print(f"✅ Тест сохранён в PDF: {filename}")
        return filename
        
    except Exception as e:
        print(f"Ошибка при сохранении теста в PDF: {e}")
        return None


def export_onboarding_to_pdf(plan: Dict[str, Any], filename: str = None) -> Optional[str]:
    """Экспортирует план онбординга в PDF"""
    if not REPORTLAB_AVAILABLE:
        print("❌ reportlab не установлен. Установите: pip install reportlab")
        return None
    
    if filename is None:
        name = plan.get('candidate_name', 'onboarding').replace(' ', '_')
        filename = f"onboarding_{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    
    try:
        doc = SimpleDocTemplate(filename, pagesize=A4)
        story = []
        
        styles = getSampleStyleSheet()
        font_name = get_font_name()
        
        title_style = ParagraphStyle(
            'RussianTitle',
            parent=styles['Title'],
            fontName=font_name,
            fontSize=16,
            alignment=1,
            spaceAfter=20
        )
        
        heading_style = ParagraphStyle(
            'RussianHeading',
            parent=styles['Heading1'],
            fontName=font_name,
            fontSize=12,
            spaceBefore=10,
            spaceAfter=5
        )
        
        normal_style = ParagraphStyle(
            'RussianNormal',
            parent=styles['Normal'],
            fontName=font_name,
            fontSize=10,
            spaceAfter=3
        )
        
        story.append(Paragraph(f"План онбординга для {safe_text(plan.get('candidate_name', 'Сотрудника'))}", title_style))
        story.append(Spacer(1, 10))
        
        story.append(Paragraph("Основная информация:", heading_style))
        story.append(Paragraph(f"Сотрудник: {safe_text(plan.get('candidate_name', '—'))}", normal_style))
        
        if plan.get('role_text'):
            story.append(Paragraph(f"Должность: {safe_text(plan.get('role_text', '—'))}", normal_style))
        
        story.append(Paragraph(f"Отдел: {safe_text(plan.get('department', '—'))}", normal_style))
        
        if plan.get('level') and plan.get('level') != 'default':
            story.append(Paragraph(f"Уровень: {safe_text(plan.get('level', '—')).upper()}", normal_style))
        
        story.append(Paragraph(f"Дата начала: {safe_text(plan.get('start_date_readable', '—'))}", normal_style))
        story.append(Spacer(1, 10))
        
        story.append(Paragraph("Чек-лист задач:", heading_style))
        for task in plan.get('checklist', []):
            story.append(Paragraph(f"  • День {task.get('planned_day', '?')} ({task.get('deadline_readable', '—')}): {safe_text(task.get('task', '—'))}", normal_style))
        story.append(Spacer(1, 10))
        
        story.append(Paragraph("План встреч:", heading_style))
        for meeting in plan.get('meetings', []):
            story.append(Paragraph(f"  • {meeting.get('date_readable', '—')} {meeting.get('time', '—')} — {meeting.get('with', '—')}: {meeting.get('topic', '—')}", normal_style))
        story.append(Spacer(1, 10))
        
        recommendations = plan.get('recommendations', [])
        if recommendations:
            story.append(Paragraph("Рекомендации:", heading_style))
            for rec in recommendations:
                story.append(Paragraph(f"  • {safe_text(rec)}", normal_style))
        
        doc.build(story)
        print(f"✅ План онбординга сохранён в PDF: {filename}")
        return filename
        
    except Exception as e:
        print(f"Ошибка при сохранении плана онбординга в PDF: {e}")
        return None
