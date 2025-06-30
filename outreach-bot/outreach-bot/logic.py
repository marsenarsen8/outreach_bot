import random
import re
from typing import Dict, Set

# Кэш для анализа ответов
analysis_cache: Dict[str, str] = {}

REFUSAL_KEYWORDS = {
    'не интересно', 'не нужно', 'не сейчас', 'позже', 'спасибо, но нет', 'не планирую', 'я просто смотрю',
    'отстаньте', 'нет', 'no', 'not interested', 'fuck', 'соси', 'отказ', 'не беспокоить', 'stop', 'unsubscribe', 'хватит', 'не пишите'
}

INTEREST_KEYWORDS = {
    'нужен сайт', 'интересно', 'расскажите', 'интернет-магазин', 'лендинг', 'подробнее', 'хочу', 
    'сколько стоит', 'какие сроки', 'да', 'готов', 'номер', 'телефон', 'консультация', 'обсудить'
}

BOT_KEYWORDS = {
    'бот', 'memory', 'ai', 'openai', 'чатгпт', 'чат', 'робот', 'искусственный интеллект'
}

SHORT_REPLIES = [
    'Понял вас! Если что — пишите 😉',
    'Спасибо за ответ! Если понадобится сайт — всегда на связи.',
    'Ок, если появятся вопросы — пишите!',
    'Спасибо, что ответили! Хорошего дня 😊',
    'Если что — обращайтесь!',
    'Буду рад помочь, если понадобится сайт или дизайн.'
]

def is_english(text: str) -> bool:
    """Проверяет, содержит ли текст английские символы"""
    return bool(re.search(r'[a-zA-Z]', text))

def is_refusal(text: str) -> bool:
    """Проверяет, является ли текст отказом"""
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in REFUSAL_KEYWORDS)

def analyze_response_fast(client_response: str) -> str:
    """Быстрый анализ ответа клиента с кэшированием"""
    # Проверяем кэш
    if client_response in analysis_cache:
        return analysis_cache[client_response]
    
    text_lower = client_response.lower()
    
    # Проверяем отказ
    if any(keyword in text_lower for keyword in REFUSAL_KEYWORDS):
        result = 'НЕТ'
    # Проверяем английский
    elif is_english(client_response):
        result = 'ENGLISH'
    # Проверяем оффтоп
    elif any(keyword in text_lower for keyword in BOT_KEYWORDS):
        result = 'OFFTOP'
    # Проверяем интерес
    elif any(keyword in text_lower for keyword in INTEREST_KEYWORDS):
        result = 'ДА'
    else:
        result = 'CONTINUE'
    
    # Кэшируем результат
    analysis_cache[client_response] = result
    return result

async def analyze_response(client_response: str) -> str:
    """Асинхронная обертка для быстрого анализа"""
    return analyze_response_fast(client_response)

async def generate_human_reply(client_response: str) -> str:
    """Генерирует человечный ответ"""
    return random.choice(SHORT_REPLIES)

def clear_analysis_cache():
    """Очищает кэш анализа"""
    analysis_cache.clear()

def get_cache_stats() -> Dict[str, int]:
    """Возвращает статистику кэша"""
    return {
        'cache_size': len(analysis_cache),
        'refusals': sum(1 for v in analysis_cache.values() if v == 'НЕТ'),
        'interests': sum(1 for v in analysis_cache.values() if v == 'ДА'),
        'continues': sum(1 for v in analysis_cache.values() if v == 'CONTINUE')
    } 