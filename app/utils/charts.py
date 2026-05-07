"""
app/utils/charts.py
Генерация графиков для аналитики опросов
"""

import matplotlib.pyplot as plt
import matplotlib
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

matplotlib.rcParams['font.family'] = 'DejaVu Sans'

def create_nps_chart(
    promoters: int,
    passives: int,
    detractors: int,
    survey_title: str = "NPS Опрос",
    save_path: str = None
) -> str:

    """  Создаёт столбчатую диаграмму распределения NPS """
    categories = ["Промоутеры\n(9-10)", "Нейтралы\n(7-8)", "Критики\n(0-6)"]
    values = [promoters, passives, detractors]
    colors = ["#2ecc71", "#f39c12", "#e74c3c"]
    
    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.bar(categories, values, color=colors, edgecolor='black', linewidth=1.5)
    
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                str(val), ha='center', va='bottom', fontsize=12, fontweight='bold')
    
    total = promoters + passives + detractors
    nps_score = int(((promoters - detractors) / total) * 100) if total > 0 else 0
    
    if nps_score >= 70:
        grade = "Отлично! 🏆"
        color = "#2ecc71"
    elif nps_score >= 50:
        grade = "Хорошо 📊"
        color = "#f39c12"
    elif nps_score >= 30:
        grade = "Средне ⚠️"
        color = "#e67e22"
    else:
        grade = "Требует внимания 🔴"
        color = "#e74c3c"
    
    ax.set_title(f"{survey_title}\nNPS Score: {nps_score} — {grade}",
                 fontsize=14, fontweight='bold', color=color)
    ax.set_ylabel("Количество ответов", fontsize=12)
    ax.set_ylim(0, max(values) * 1.2 if values else 10)
    ax.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    
    if save_path is None:
        save_path = f"temp/nps_chart_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    
    Path(save_path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    plt.close()
    
    return save_path


def create_pulse_chart(
    satisfaction_scores: List[float],
    energy_scores: List[float],
    dates: List[str],
    survey_title: str = "Pulse Опрос",
    save_path: str = None
) -> str:

    """ Создаёт линейный график динамики Pulse опроса """
    fig, ax = plt.subplots(figsize=(12, 6))
    
    x = range(len(dates))
    
    ax.plot(x, satisfaction_scores, 'o-', label="Удовлетворённость",
            color="#3498db", linewidth=2, markersize=8)
    ax.plot(x, energy_scores, 's-', label="Энергия",
            color="#e74c3c", linewidth=2, markersize=8)
    
    avg_sat = sum(satisfaction_scores) / len(satisfaction_scores)
    avg_eng = sum(energy_scores) / len(energy_scores)
    ax.axhline(y=avg_sat, color="#3498db", linestyle='--', alpha=0.5, label=f"Ср. удовлетворённость: {avg_sat:.1f}")
    ax.axhline(y=avg_eng, color="#e74c3c", linestyle='--', alpha=0.5, label=f"Ср. энергия: {avg_eng:.1f}")
    
    ax.set_xlabel("Дата", fontsize=12)
    ax.set_ylabel("Оценка (1-5)", fontsize=12)
    ax.set_title(f"{survey_title}\nДинамика самочувствия команды", fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(dates, rotation=45, ha='right')
    ax.set_ylim(0, 5.5)
    ax.legend(loc='best')
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    if save_path is None:
        save_path = f"temp/pulse_chart_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    
    Path(save_path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    plt.close()
    
    return save_path


def create_survey_summary_chart(
    surveys_data: List[Dict[str, Any]],
    save_path: str = None
) -> str:

    """  Создаёт сводную диаграмму по всем опросам """
    titles = [s.get('title', f"Опрос {s['id']}")[:20] for s in surveys_data]
    response_counts = [s.get('response_count', 0) for s in surveys_data]
    
    if len(titles) > 10:
        titles = titles[:10]
        response_counts = response_counts[:10]
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    colors = plt.cm.viridis(range(len(titles)))
    bars = ax.barh(titles, response_counts, color=colors, edgecolor='black')
    
    for bar, val in zip(bars, response_counts):
        ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height()/2,
                str(val), ha='left', va='center', fontsize=10)
    
    ax.set_xlabel("Количество ответов", fontsize=12)
    ax.set_title("Активность участия в опросах", fontsize=14, fontweight='bold')
    ax.grid(axis='x', alpha=0.3)
    
    plt.tight_layout()
    
    if save_path is None:
        save_path = f"temp/survey_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    
    Path(save_path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    plt.close()
    
    return save_path


def create_response_timeline_chart(
    responses_by_date: Dict[str, int],
    survey_title: str = "Динамика ответов",
    save_path: str = None
) -> str:

    """ Создаёт график динамики ответов по дням """
    dates = list(responses_by_date.keys())
    counts = list(responses_by_date.values())
    
    fig, ax = plt.subplots(figsize=(12, 5))
    
    ax.fill_between(dates, counts, color="#3498db", alpha=0.3)
    ax.plot(dates, counts, 'o-', color="#2980b9", linewidth=2, markersize=6)
    
    ax.set_xlabel("Дата", fontsize=12)
    ax.set_ylabel("Количество ответов", fontsize=12)
    ax.set_title(f"{survey_title}\nДинамика поступления ответов", fontsize=14, fontweight='bold')
    ax.tick_params(axis='x', rotation=45)
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    if save_path is None:
        save_path = f"temp/timeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    
    Path(save_path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    plt.close()
    
    return save_path
