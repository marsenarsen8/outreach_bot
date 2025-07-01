import config
print("DEBUG: api_id   =", repr(config.api_id))
print("DEBUG: api_hash =", repr(config.api_hash))
print("DEBUG: phone    =", repr(config.phone))

import pandas as pd
import time
import requests
import logging
import os
import glob
from pathlib import Path
from telethon import TelegramClient, functions, types, events
from telethon.tl.types import User
from config import api_id, api_hash, phone, notify_user_id, ollama_api_url, model_name, delay_seconds, llm_provider, gemini_api_key, gemini_daily_limit, gemini_cooldown_seconds, audio_notification_enabled
import asyncio
import random
import re
import importlib
import aiohttp
import json
from functools import lru_cache
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import google.generativeai as genai
import sqlite3
from typing import List, Dict
from datetime import datetime

# Импортируем функции для работы с базой данных
import database_functions

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    filename='outreach_debug.log'
)
logger = logging.getLogger(__name__)

# Конфигурация
TOKEN = 'YOUR_BOT_TOKEN'
GOOGLE_API_KEY = 'YOUR_GOOGLE_API_KEY'
DB_PATH = 'outreach_bot.db'
KNOWLEDGE_BASE_DIR = 'knowledge_base'

# Инициализация Gemini
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('gemini-pro')

logging.info('--- Запуск outreach_bot.py ---')

# Импортируем бизнес-логику
import logic

# Кэш для LLM ответов
llm_cache = {}
CACHE_SIZE = 100

# Сессия для HTTP запросов
session = None

# Система защиты от лимитов Gemini
gemini_request_count = 0
gemini_last_request_time = time.time() - gemini_cooldown_seconds  # Инициализируем так, чтобы первый запрос прошел
gemini_daily_requests = 0
gemini_last_reset = time.time()
gemini_minute_requests = []  # Список временных меток запросов за последнюю минуту

# Глобальные переменные для памяти диалогов
dialog_memory = {}  # {telegram_id: [{"role": "user/bot", "message": "text", "timestamp": time}]}

async def get_session():
    """Получает или создает aiohttp сессию"""
    global session
    if session is None or session.closed:
        session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15))
    return session

# Функция для загрузки базы знаний из базы данных
def load_knowledge_base():
    """Загружает базу знаний из базы данных"""
    try:
        knowledge_content = database_functions.get_knowledge_base()
        if knowledge_content:
            logging.info(f'Загружено {len(knowledge_content)} элементов базы знаний из БД')
            return [f"=== {item['filename']} ===\n{item['content']}\n" for item in knowledge_content]
        else:
            logging.info('База знаний пуста, загружаем из файлов')
            return load_knowledge_from_files()
    except Exception as e:
        logging.error(f'Ошибка загрузки базы знаний из БД: {e}')
        return load_knowledge_from_files()

def load_knowledge_from_files():
    """Загружает базу знаний из файлов (fallback)"""
    knowledge_content = []
    
    if not os.path.exists(KNOWLEDGE_BASE_DIR):
        logging.info(f'Папка {KNOWLEDGE_BASE_DIR} не найдена, база знаний не загружена')
        return knowledge_content
    
    # Поддерживаемые форматы файлов
    supported_extensions = ['*.txt', '*.md', '*.csv']
    
    for extension in supported_extensions:
        pattern = os.path.join(KNOWLEDGE_BASE_DIR, '**', extension)
        files = glob.glob(pattern, recursive=True)
        
        for file_path in files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    filename = os.path.basename(file_path)
                    knowledge_content.append(f"=== {filename} ===\n{content}\n")
                    logging.info(f'Загружен файл базы знаний: {filename}')
            except Exception as e:
                logging.error(f'Ошибка чтения файла {file_path}: {e}')
    
    if knowledge_content:
        logging.info(f'Загружено {len(knowledge_content)} файлов базы знаний')
    else:
        logging.info('Файлы базы знаний не найдены')
    
    return knowledge_content

# Загружаем базу знаний при запуске
knowledge_base = load_knowledge_base()

# Функция для получения релевантной информации из базы знаний
def get_relevant_knowledge(query):
    """Получает релевантные знания из базы знаний на основе запроса"""
    try:
        knowledge_files = [
            'knowledge_base/services.md',
            'knowledge_base/sales_techniques.txt',
            'knowledge_base/faq.txt',
            'knowledge_base/dialogs_examples.txt'
        ]
        
        relevant_info = []
        
        for file_path in knowledge_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                # Простой поиск по ключевым словам
                query_words = query.lower().split()
                content_lower = content.lower()
                
                # Если найдены ключевые слова, добавляем контент
                if any(word in content_lower for word in query_words):
                    # Берем первые 200 символов
                    relevant_info.append(content[:200] + "...")
                    
            except FileNotFoundError:
                continue
            except Exception as e:
                print(f"Ошибка чтения {file_path}: {e}")
                continue
        
        if relevant_info:
            return "\n".join(relevant_info)
        else:
            return ""
            
    except Exception as e:
        print(f"Ошибка получения знаний: {e}")
        return ""

def get_knowledge_base():
    """Получает общую базу знаний"""
    try:
        knowledge_files = [
            'knowledge_base/services.md',
            'knowledge_base/sales_techniques.txt'
        ]
        
        knowledge = []
        
        for file_path in knowledge_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    knowledge.append(content[:300] + "...")
            except FileNotFoundError:
                continue
            except Exception as e:
                print(f"Ошибка чтения {file_path}: {e}")
                continue
        
        if knowledge:
            return "\n\n".join(knowledge)
        else:
            return ""
            
    except Exception as e:
        print(f"Ошибка получения базы знаний: {e}")
        return ""

# Функция для получения текущего промпта для LLM с учетом контекста и знаний
def get_current_prompt():
    """Получает текущий промпт для LLM с учетом контекста и знаний"""
    # Базовый промпт
    base_prompt = """Ты - профессиональный менеджер по продажам веб-разработки. Твоя задача - вести диалог с потенциальными клиентами, отвечать на их вопросы и помогать им заказать сайт.

Твои основные качества:
- Дружелюбность и профессионализм
- Глубокое понимание веб-разработки
- Умение выявлять потребности клиента
- Способность давать конкретные и полезные ответы

Твои услуги:
- Создание сайтов любой сложности
- Лендинги для бизнеса
- Интернет-магазины
- Корпоративные сайты
- Техническая поддержка

Цены (примерные):
- Лендинг: от 30,000 руб
- Сайт-визитка: от 50,000 руб
- Корпоративный сайт: от 100,000 руб
- Интернет-магазин: от 150,000 руб

ВАЖНО: Всегда отвечай по существу вопроса клиента. Если клиент спрашивает о заказе сайта - расскажи о процессе, сроках, ценах. Если спрашивает о технологиях - объясни доступно. Если просит примеры - предложи варианты.

Отвечай кратко, но информативно. Максимум 2-3 предложения."""
    
    # Добавляем знания из базы
    knowledge = get_relevant_knowledge("")
    if knowledge:
        base_prompt += f"\n\nДополнительная информация:\n{knowledge}"
    
    return base_prompt

def get_contextual_prompt(user_message, contact_info=None, telegram_id=None):
    """Создает контекстный промпт на основе сообщения пользователя и истории диалога"""
    base_prompt = get_current_prompt()
    
    # Получаем историю диалога
    dialog_history = []
    if telegram_id:
        dialog_history = get_dialog_history(telegram_id)
    
    # Анализируем сообщение пользователя
    message_lower = user_message.lower()
    
    # Определяем контекст
    context = ""
    if any(word in message_lower for word in ['заказать', 'сделать', 'создать', 'нужен сайт']):
        context = "КЛИЕНТ ХОЧЕТ ЗАКАЗАТЬ САЙТ"
    elif any(word in message_lower for word in ['цена', 'стоимость', 'сколько стоит']):
        context = "КЛИЕНТ СПРАШИВАЕТ О ЦЕНАХ"
    elif any(word in message_lower for word in ['время', 'срок', 'когда', 'долго']):
        context = "КЛИЕНТ СПРАШИВАЕТ О СРОКАХ"
    elif any(word in message_lower for word in ['пример', 'портфолио', 'работы']):
        context = "КЛИЕНТ ПРОСИТ ПРИМЕРЫ РАБОТ"
    elif any(word in message_lower for word in ['технология', 'что используется', 'на чем']):
        context = "КЛИЕНТ СПРАШИВАЕТ О ТЕХНОЛОГИЯХ"
    elif any(word in message_lower for word in ['спасибо', 'хорошо', 'понятно']):
        context = "КЛИЕНТ БЛАГОДАРИТ ИЛИ СОГЛАШАЕТСЯ"
    else:
        context = "ОБЩИЙ ВОПРОС"
    
    # Форматируем историю диалога
    history_text = format_dialog_history(dialog_history)
    
    # Создаем персонализированный промпт
    prompt = f"""{base_prompt}

КОНТЕКСТ: {context}
ТЕКУЩЕЕ СООБЩЕНИЕ КЛИЕНТА: "{user_message}"{history_text}

ВАЖНО: Учитывай историю диалога! Если клиент уже спрашивал о чем-то - не повторяй информацию, а развивай тему. Если это новый вопрос - отвечай по существу.

ОТВЕТЬ на сообщение клиента, учитывая контекст и историю диалога. Если клиент хочет заказать сайт - предложи обсудить детали. Если спрашивает о ценах - дай примерные цифры. Если просит примеры - предложи варианты.

Твой ответ:"""
    
    return prompt

# Функция для получения диалогового промпта из базы данных
def get_dialog_prompt():
    """Получает диалоговый промпт из базы данных"""
    try:
        prompts = database_functions.get_prompts()
        # Ищем промпт с именем "dialog" или содержащий "диалог"
        for prompt in prompts:
            if 'dialog' in prompt['name'].lower() or 'диалог' in prompt['name'].lower():
                return prompt['content']
        
        # Возвращаем промпт по умолчанию
        return """
Ты ведёшь переписку с потенциальными клиентами в Telegram от имени компании bored.kz. Мы делаем сайты, интернет-магазины, веб-сервисы и UX/UI-дизайн. Цены от 50 000 тенге.

Ты отвечаешь на «холодные» входящие сообщения. Люди часто присылают сразу несколько сообщений подряд. Не нужно реагировать на каждое — **дождись примерно минуты с момента последнего сообщения** и **ответь один раз, обобщив всю информацию**.

📌 В ответе:
- Пиши кратко и дружелюбно.
- Не повторяйся.
- Отвечай только одним сообщением.
- Не используй подпись или указание, кто ты (не пиши "Роллан:" и т.п.).
- Включи 1–2 вопроса по теме: например, какой сайт нужен, в какой сфере работает клиент, есть ли пожелания по дизайну.
- Если клиент заинтересован — предложи передать контакт менеджеру для консультации.
- Если клиент отказывается — поблагодари и больше не пиши.
- Используй техники продаж и аргументы из базы знаний для работы с возражениями.

💡 Цель: заинтересовать клиента и выяснить, нужен ли сайт или визуал. Общайся живо, уважительно и по делу.
"""
    except Exception as e:
        logging.error(f'Ошибка получения диалогового промпта из БД: {e}')
        return ""

# Загрузка базы
try:
    contacts = database_functions.get_contacts()
    logging.info(f'Загружено {len(contacts)} контактов из базы данных')
except Exception as e:
    logging.error(f'Ошибка загрузки контактов из БД: {e}')
    print(f'Ошибка загрузки контактов из БД:', e)
    exit(1)

# Фильтруем только контакты со статусом NOT_SENT
contacts_to_send = [contact for contact in contacts if contact['status'] == 'NOT_SENT']
logging.info(f'Контактов для рассылки: {len(contacts_to_send)} из {len(contacts)}')
print(f'📊 Контактов для рассылки: {len(contacts_to_send)} из {len(contacts)}')

if len(contacts_to_send) == 0:
    print("❌ Нет контактов для рассылки! Все контакты уже отправлены или имеют другой статус.")
    print("💡 Используйте кнопку 'Сбросить статусы' в панели управления для повторной рассылки.")
    exit(0)

# Загрузка уже обработанных номеров (для диалогов, не для рассылки)
try:
    results = database_functions.get_results()
    sent_phones = set(result['user_id'] for result in results)
    logging.info(f'Загружено {len(sent_phones)} уже обработанных номеров из БД')
except:
    sent_phones = set()
    logging.info('Результаты не найдены в БД, начинаем с чистого листа.')

# Авторизация
client = TelegramClient('outreach_session', api_id, api_hash)

# Текущий prompt (может меняться)
current_prompt = get_current_prompt()

# Диалоговый prompt (может меняться)
dialog_prompt = get_dialog_prompt()

# Словарь для хранения статуса диалогов (чтобы не продолжать диалог с отказавшимися)
dialog_status = {}
# Словарь для хранения истории диалогов
dialog_history = {}
# Буфер для входящих сообщений (user_id -> список сообщений)
dialog_buffer = {}
# Таймеры для отложенного ответа (user_id -> asyncio.Task)
dialog_timer = {}

REPLY_DELAY = 60  # секунд ожидания после последнего сообщения клиента

# Явные признаки отказа
REFUSAL_KEYWORDS = [
    'не интересно', 'не нужно', 'не сейчас', 'позже', 'спасибо, но нет', 'не планирую', 'я просто смотрю',
    'отстаньте', 'нет', 'no', 'not interested', 'fuck', 'соси', 'отказ', 'не беспокоить', 'stop', 'unsubscribe', 'хватит', 'не пишите'
]

# Короткие человечные реплики для разных ситуаций
SHORT_REPLIES = [
    'Понял вас! Если что — пишите 😉',
    'Спасибо за ответ! Если понадобится сайт — всегда на связи.',
    'Ок, если появятся вопросы — пишите!',
    'Спасибо, что ответили! Хорошего дня 😊',
    'Если что — обращайтесь!',
    'Буду рад помочь, если понадобится сайт или дизайн.'
]

# Проверка на английский язык
def is_english(text):
    return bool(re.search(r'[a-zA-Z]', text))

def is_refusal(text):
    text_low = text.lower()
    return any(kw in text_low for kw in REFUSAL_KEYWORDS)

async def send_to_llm(prompt, context=""):
    """Отправляет запрос к LLM с учетом выбранного провайдера (Gemini, Ollama, OpenAI)"""
    try:
        print(f"🤖 LLM запрос: {prompt[:100]}...")
        print(f"📝 Контекст: {context}")
        
        # Проверяем кэш
        cache_key = hash(prompt + context)
        if cache_key in llm_cache:
            print("✅ Используем кэшированный ответ LLM")
            return llm_cache[cache_key]
        
        # Добавляем релевантную информацию из базы знаний
        knowledge_context = get_relevant_knowledge(prompt + " " + context)
        enhanced_prompt = prompt + knowledge_context
        
        session = await get_session()
        
        if llm_provider == 'gemini':
            print("🔍 Проверяем лимиты Gemini...")
            if not check_gemini_limits():
                print("❌ Достигнут лимит Gemini, пропускаем LLM запрос")
                return ""
            
            print("✅ Лимиты в порядке, отправляем запрос к Gemini...")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={gemini_api_key}"
            headers = {"Content-Type": "application/json"}
            data = {
                "contents": [
                    {"parts": [{"text": enhanced_prompt}]}
                ],
                "generationConfig": {
                    "temperature": 0.7,
                    "maxOutputTokens": 500,
                    "topP": 0.8
                }
            }
            
            async with session.post(url, headers=headers, json=data) as response:
                print(f"📡 Статус ответа Gemini: {response.status}")
                
                if response.status == 200:
                    result = await response.json()
                    try:
                        text = result["candidates"][0]["content"]["parts"][0]["text"]
                        print(f"✅ Gemini ответил: {text[:100]}...")
                        # Кэшируем ответ
                        if len(llm_cache) >= CACHE_SIZE:
                            llm_cache.pop(next(iter(llm_cache)))
                        llm_cache[cache_key] = text
                        update_gemini_limits()
                        return text
                    except Exception as e:
                        print(f"❌ Ошибка парсинга ответа Gemini: {e}")
                        print(f"📄 Полный ответ: {result}")
                        return ""
                else:
                    error_text = await response.text()
                    print(f"❌ Ошибка Gemini API: {response.status} - {error_text}")
                    return ""
                    
        elif llm_provider == 'ollama':
            print("🔍 Отправляем запрос к Ollama...")
            payload = {
                "model": model_name,
                "prompt": enhanced_prompt,
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "num_predict": 500
                }
            }
            
            async with session.post(ollama_api_url, json=payload) as response:
                print(f"📡 Статус ответа Ollama: {response.status}")
                
                if response.status == 200:
                    result = await response.json()
                    text = result.get('response', '').strip()
                    print(f"✅ Ollama ответил: {text[:100]}...")
                    # Кэшируем ответ
                    if len(llm_cache) >= CACHE_SIZE:
                        llm_cache.pop(next(iter(llm_cache)))
                    llm_cache[cache_key] = text
                    return text
                else:
                    error_text = await response.text()
                    print(f"❌ Ошибка Ollama API: {response.status} - {error_text}")
                    return ""
        # Можно добавить OpenAI аналогично
        else:
            print(f"❌ Неизвестный llm_provider: {llm_provider}")
            return ""
    except Exception as e:
        print(f"❌ Ошибка запроса к LLM ({llm_provider}): {e}")
        return ""

async def analyze_response(client_response):
    """Анализирует ответ клиента: только явный отказ закрывает диалог"""
    return await logic.analyze_response(client_response)

async def handle_buffered_reply(user_id, event):
    await asyncio.sleep(REPLY_DELAY)
    all_text = "\n".join(dialog_buffer[user_id])
    if user_id not in dialog_history:
        dialog_history[user_id] = []
    dialog_history[user_id].append(f"Клиент: {all_text}")
    result = await analyze_response(all_text)
    logging.info(f'Результат анализа для {user_id}: {result}')
    if result == 'НЕТ':
        dialog_status[user_id] = 'REFUSED'
        reply = random.choice(SHORT_REPLIES)
        await event.respond(reply)
        await client.send_message(notify_user_id, f'❌ ОТКАЗ от {user_id}\nОтвет: {all_text}\nРезультат анализа: {result}')
        with open(RESULTS_FILE, 'a', encoding='utf-8') as f:
            f.write(f'{user_id},REFUSED,"{all_text}","{result}"\n')
        dialog_buffer[user_id] = []
        return
    if result == 'ДА':
        await client.send_message(notify_user_id, f'✅ ЗАИНТЕРЕСОВАН {user_id}\nОтвет: {all_text}\nРезультат анализа: {result}')
    # Краткие, человечные ответы для английского и оффтопа
    if result == 'ENGLISH':
        reply = 'Sorry, I can help only with website development and only in Russian 😊'
        await event.respond(reply)
        dialog_history[user_id].append(f"Роллан: {reply}")
        dialog_buffer[user_id] = []
        return
    if result == 'OFFTOP':
        reply = random.choice([
            'Я могу помочь только с созданием сайтов и дизайном. Если интересно — расскажите, какой проект планируете?',
            'Я занимаюсь только сайтами и дизайном. Если нужен сайт — с радостью помогу!',
            'Моя задача — помогать с сайтами. Если это актуально — пишите!'
        ])
        await event.respond(reply)
        dialog_history[user_id].append(f"Роллан: {reply}")
        dialog_buffer[user_id] = []
        return
    # Генерируем короткий, дружелюбный ответ через LLM
    history_text = "\n".join(dialog_history[user_id][-5:])
    dialog_prompt_enhanced = f"Ты Роллан, менеджер по продажам в компании bored.kz.\n\nКонтекст: {dialog_prompt}\n\nИстория диалога:\n{history_text}\n\nОтветь на последнее сообщение клиента очень коротко, дружелюбно, по-человечески, без формализма, не повторяйся, не используй длинные фразы."
    reply = await send_to_llm(dialog_prompt_enhanced)
    if not reply:
        reply = random.choice(SHORT_REPLIES)
    dialog_history[user_id].append(f"Роллан: {reply}")
    await event.respond(reply)
    logging.info(f'Бот ответил {user_id}: {reply}')
    with open(RESULTS_FILE, 'a', encoding='utf-8') as f:
        f.write(f'{user_id},REPLY,"{all_text}","{reply}","{result}"\n')
    dialog_buffer[user_id] = []

async def main():
    global current_prompt, dialog_prompt
    await client.start(phone=phone)
    logging.info('Клиент Telegram запущен!')
    print('Клиент Telegram запущен!')

    @client.on(events.NewMessage(incoming=True))
    async def handler(event):
        global current_prompt, dialog_prompt
        # Команды управления от вас
        if event.sender_id == notify_user_id:
            if event.text.startswith('/prompt '):
                new_prompt = event.text[len('/prompt '):].strip()
                current_prompt = new_prompt
                await event.respond(f'Промпт обновлён! Новый промпт:\n{current_prompt}')
                logging.info(f'Промпт обновлён пользователем: {current_prompt}')
            elif event.text.startswith('/dialogprompt '):
                new_dialog = event.text[len('/dialogprompt '):].strip()
                dialog_prompt = new_dialog
                await event.respond(f'Диалоговый промпт обновлён! Новый диалоговый промпт:\n{dialog_prompt}')
                logging.info(f'Диалоговый промпт обновлён пользователем: {dialog_prompt}')
            elif event.text == '/reload_kb':
                files_count = reload_knowledge_base()
                await event.respond(f'✅ База знаний перезагружена! Загружено {files_count} файлов.')
                logging.info(f'База знаний перезагружена пользователем, файлов: {files_count}')
            elif event.text == '/kb_status':
                files_count = len(knowledge_base)
                await event.respond(f'📚 Статус базы знаний: {files_count} файлов загружено.')
                logging.info(f'Запрос статуса базы знаний, файлов: {files_count}')
            elif event.text == '/reload_logic':
                importlib.reload(logic)
                await event.respond('Логика бота обновлена!')
            elif event.text == '/retry_wrong_closes':
                count = await retry_wrong_closes()
                await event.respond(f'Обработано {count} диалогов с неправильным закрытием.')
            elif event.text == '/clear_cache':
                llm_cache.clear()
                logic.clear_analysis_cache()
                await event.respond('Кэш LLM и анализа очищен!')
            elif event.text == '/cache_stats':
                llm_stats = f"LLM кэш: {len(llm_cache)} записей"
                analysis_stats = logic.get_cache_stats()
                analysis_text = f"Анализ кэш: {analysis_stats['cache_size']} записей (отказы: {analysis_stats['refusals']}, интересы: {analysis_stats['interests']})"
                await event.respond(f'📊 Статистика кэша:\n{llm_stats}\n{analysis_text}')
            elif event.text == '/status':
                # Статистика работы бота
                total_sent = len([s for s in sent_phones])
                total_dialogs = len(dialog_history)
                total_refused = len([s for s in dialog_status.values() if s == 'REFUSED'])
                await event.respond(f'📈 Статистика бота:\nОтправлено: {total_sent}\nАктивных диалогов: {total_dialogs}\nОтказов: {total_refused}')
            elif event.text == '/gemini_limits':
                # Проверка лимитов Gemini
                reset_gemini_daily_limit()
                remaining_daily = gemini_daily_limit - gemini_daily_requests
                time_since_last = time.time() - gemini_last_request_time
                cooldown_remaining = max(0, gemini_cooldown_seconds - time_since_last)
                
                status = f'🤖 Лимиты Gemini:\nДневных запросов: {gemini_daily_requests}/{gemini_daily_limit}\nОсталось сегодня: {remaining_daily}\nПоследний запрос: {time_since_last:.1f}с назад\nЗадержка до следующего: {cooldown_remaining:.1f}с'
                await event.respond(status)
            else:
                await event.respond('Неизвестная команда. Используйте:\n/prompt <текст> - обновить промпт\n/dialogprompt <текст> - обновить диалоговый промпт\n/reload_kb - перезагрузить базу знаний\n/kb_status - статус базы знаний\n/reload_logic - перезагрузить логику бота\n/retry_wrong_closes - повторная обработка диалогов с неправильным закрытием\n/clear_cache - очистить кэш LLM\n/cache_stats - статистика кэша\n/status - статус бота\n/gemini_limits - лимиты Gemini')
                logging.warning(f'Неизвестная команда от пользователя: {event.text}')
        else:
            # Если это не вы, значит это контакт — отвечаем автоматически
            user_id = event.sender_id
            incoming_text = ""
            
            # Обрабатываем разные типы сообщений
            if event.message.text:
                incoming_text = event.message.text
            elif event.message.voice or event.message.audio:
                # Аудио сообщения - отправляем уведомление и отвечаем стандартным сообщением
                incoming_text = "[АУДИО СООБЩЕНИЕ]"
                if audio_notification_enabled:
                    await client.send_message(notify_user_id, f'🎵 Получено аудио от {user_id}')
                logging.info(f'Получено аудио сообщение от {user_id}')
                
                # Отвечаем на аудио стандартным сообщением без использования LLM
                audio_replies = [
                    "Извините, я не могу прослушать аудио. Можете написать текстом? 😊",
                    "Не могу обработать голосовое сообщение. Напишите, пожалуйста, текстом!",
                    "Голосовые сообщения не поддерживаются. Отправьте текст, и я отвечу! 📝",
                    "Пожалуйста, напишите ваше сообщение текстом, чтобы я мог помочь! ✍️"
                ]
                await event.respond(random.choice(audio_replies))
                return  # Не обрабатываем дальше
            elif event.message.photo:
                incoming_text = "[ФОТО]"
                if audio_notification_enabled:
                    await client.send_message(notify_user_id, f'📷 Получено фото от {user_id}')
                logging.info(f'Получено фото от {user_id}')
                
                # Отвечаем на фото стандартным сообщением
                photo_replies = [
                    "Спасибо за фото! Можете рассказать, что вам нужно? 😊",
                    "Красивое фото! Расскажите, какой сайт вам нужен?",
                    "Понял! Теперь расскажите текстом, что вы хотите заказать? 📝"
                ]
                await event.respond(random.choice(photo_replies))
                return  # Не обрабатываем дальше
            elif event.message.document:
                incoming_text = "[ДОКУМЕНТ]"
                if audio_notification_enabled:
                    await client.send_message(notify_user_id, f'📄 Получен документ от {user_id}')
                logging.info(f'Получен документ от {user_id}')
                
                # Отвечаем на документ стандартным сообщением
                doc_replies = [
                    "Получил документ! Расскажите, что вам нужно сделать? 📋",
                    "Спасибо за документ! Опишите ваш проект текстом.",
                    "Документ получен! Теперь расскажите, какой сайт вам нужен? 😊"
                ]
                await event.respond(random.choice(doc_replies))
                return  # Не обрабатываем дальше
            elif event.message.sticker:
                incoming_text = "[СТИКЕР]"
                logging.info(f'Получен стикер от {user_id}')
                
                # Отвечаем на стикер стандартным сообщением
                sticker_replies = [
                    "😊 Расскажите, что вам нужно?",
                    "Привет! Какой сайт вас интересует?",
                    "Здорово! Теперь расскажите о вашем проекте текстом! 📝"
                ]
                await event.respond(random.choice(sticker_replies))
                return  # Не обрабатываем дальше
            else:
                incoming_text = "[НЕИЗВЕСТНЫЙ ТИП СООБЩЕНИЯ]"
                logging.info(f'Получено сообщение неизвестного типа от {user_id}')
                
                # Отвечаем стандартным сообщением
                await event.respond("Извините, не могу обработать этот тип сообщения. Напишите текстом! 📝")
                return  # Не обрабатываем дальше
            
            if incoming_text:
                logging.info(f'Входящее сообщение от {user_id}: {incoming_text}')
                
                # Проверяем, не отказался ли уже этот пользователь
                if user_id in dialog_status and dialog_status[user_id] == 'REFUSED':
                    logging.info(f'Пользователь {user_id} уже отказался, игнорируем сообщение')
                    return
                
                # Буферизация сообщений
                if user_id not in dialog_buffer:
                    dialog_buffer[user_id] = []
                dialog_buffer[user_id].append(incoming_text)
                # Если уже есть таймер — отменяем его
                if user_id in dialog_timer:
                    dialog_timer[user_id].cancel()
                # Запускаем новый таймер
                dialog_timer[user_id] = asyncio.create_task(handle_buffered_reply(user_id, event))

    # Отправка сообщений по одному с задержкой
    for i, contact in enumerate(contacts_to_send):
        try:
            await process_contact(contact)
            print(f"✅ Обработан контакт {i+1}/{len(contacts_to_send)}: {contact.get('name', 'Unknown')} ({contact['phone']})")
        except Exception as e:
            print(f"❌ Ошибка обработки контакта {contact.get('name', 'Unknown')} ({contact['phone']}): {e}")
            logging.error(f"Ошибка обработки контакта {contact['phone']}: {e}")
        
        # Задержка между сообщениями
        if i < len(contacts_to_send) - 1:  # Не ждем после последнего
            await asyncio.sleep(delay_seconds)

    # Ждем завершения всех диалогов
    await asyncio.sleep(2)
    
    # Обрабатываем неправильно закрытые диалоги
    await retry_wrong_closes()
    
    print("Рассылка завершена!")

def reload_knowledge_base():
    """Перезагружает базу знаний"""
    global knowledge_base
    knowledge_base = load_knowledge_base()
    return len(knowledge_base)

def parse_results_csv():
    """Парсит results.csv и восстанавливает статусы диалогов"""
    try:
        results_df = pd.read_csv(RESULTS_FILE, header=None, names=['user_id', 'status', 'text', 'reply', 'analysis'])
        for _, row in results_df.iterrows():
            if row['status'] == 'REFUSED':
                dialog_status[row['user_id']] = 'REFUSED'
        logging.info(f'Восстановлено {len([s for s in dialog_status.values() if s == "REFUSED"])} статусов отказа')
    except Exception as e:
        logging.error(f'Ошибка парсинга results.csv: {e}')

async def retry_wrong_closes():
    """Повторно обрабатывает диалоги с неправильным закрытием"""
    try:
        results_df = pd.read_csv(RESULTS_FILE, header=None, names=['user_id', 'status', 'text', 'reply', 'analysis'])
        refused_rows = results_df[results_df['status'] == 'REFUSED']
        count = 0
        for _, row in refused_rows.iterrows():
            # Проверяем, действительно ли это отказ
            if not is_refusal(row['text']):
                # Удаляем запись об отказе
                results_df = results_df.drop(results_df[(results_df['user_id'] == row['user_id']) & (results_df['status'] == 'REFUSED')].index)
                # Удаляем из статусов
                if row['user_id'] in dialog_status:
                    del dialog_status[row['user_id']]
                count += 1
        # Сохраняем обновленный файл
        results_df.to_csv(RESULTS_FILE, index=False, header=False)
        logging.info(f'Исправлено {count} неправильных отказов')
        return count
    except Exception as e:
        logging.error(f'Ошибка retry_wrong_closes: {e}')
        return 0

def reset_gemini_daily_limit():
    """Сбрасывает дневной лимит Gemini"""
    global gemini_daily_requests, gemini_last_reset
    current_time = time.time()
    if current_time - gemini_last_reset > 86400:  # 24 часа
        gemini_daily_requests = 0
        gemini_last_reset = current_time
        logging.info("Сброшен дневной лимит Gemini")

def check_gemini_limits():
    """Проверяет лимиты Gemini API"""
    current_time = time.time()
    
    # Инициализируем переменные при первом вызове
    if not hasattr(check_gemini_limits, 'last_request_time'):
        check_gemini_limits.last_request_time = 0
    if not hasattr(check_gemini_limits, 'requests_this_minute'):
        check_gemini_limits.requests_this_minute = 0
    if not hasattr(check_gemini_limits, 'requests_today'):
        check_gemini_limits.requests_today = 0
    if not hasattr(check_gemini_limits, 'minute_start'):
        check_gemini_limits.minute_start = current_time
    if not hasattr(check_gemini_limits, 'day_start'):
        check_gemini_limits.day_start = current_time
    
    # Проверяем, прошла ли минута с начала отсчета
    if current_time - check_gemini_limits.minute_start >= 60:
        check_gemini_limits.requests_this_minute = 0
        check_gemini_limits.minute_start = current_time
    
    # Проверяем, прошел ли день с начала отсчета
    if current_time - check_gemini_limits.day_start >= 86400:  # 24 часа
        check_gemini_limits.requests_today = 0
        check_gemini_limits.day_start = current_time
    
    # Проверяем лимиты
    if check_gemini_limits.requests_this_minute >= gemini_rate_limit:
        print(f"⚠️ Лимит запросов в минуту достигнут: {check_gemini_limits.requests_this_minute}/{gemini_rate_limit}")
        return False
    
    if check_gemini_limits.requests_today >= gemini_daily_limit:
        print(f"⚠️ Дневной лимит запросов достигнут: {check_gemini_limits.requests_today}/{gemini_daily_limit}")
        return False
    
    # Проверяем минимальный интервал между запросами
    if current_time - check_gemini_limits.last_request_time < gemini_cooldown_seconds:
        remaining = gemini_cooldown_seconds - (current_time - check_gemini_limits.last_request_time)
        print(f"⏳ Слишком частые запросы, ждем еще {remaining:.1f}с")
        return False
    
    return True

def update_gemini_limits():
    """Обновляет счетчики лимитов Gemini после успешного запроса"""
    current_time = time.time()
    
    # Инициализируем переменные при первом вызове
    if not hasattr(update_gemini_limits, 'last_request_time'):
        update_gemini_limits.last_request_time = 0
    if not hasattr(update_gemini_limits, 'requests_this_minute'):
        update_gemini_limits.requests_this_minute = 0
    if not hasattr(update_gemini_limits, 'requests_today'):
        update_gemini_limits.requests_today = 0
    if not hasattr(update_gemini_limits, 'minute_start'):
        update_gemini_limits.minute_start = current_time
    if not hasattr(update_gemini_limits, 'day_start'):
        update_gemini_limits.day_start = current_time
    
    # Обновляем счетчики
    update_gemini_limits.last_request_time = current_time
    update_gemini_limits.requests_this_minute += 1
    update_gemini_limits.requests_today += 1
    
    print(f"📊 Лимиты обновлены: {update_gemini_limits.requests_this_minute}/{gemini_rate_limit} в минуту, {update_gemini_limits.requests_today}/{gemini_daily_limit} за день")

async def process_contact(contact):
    """Обрабатывает один контакт"""
    try:
        phone = contact['phone']
        name = contact.get('name', '')
        telegram_id = contact.get('telegram_id')
        status = contact.get('status', 'NOT_SENT')
        
        print(f"📞 Обрабатываем контакт: {name} ({phone}) - статус: {status}")
        
        if not telegram_id:
            print(f"❌ У контакта {phone} нет Telegram ID")
            return False
        
        # Для тестового режима не меняем статус на SENT
        is_test_mode = status == 'TEST'
        
        # Создаем персонализированное приветственное сообщение
        welcome_prompt = f"""Ты - профессиональный менеджер по продажам веб-разработки. 

Твоя задача - написать ПЕРВОЕ приветственное сообщение клиенту {name} (если имя есть).

Твои услуги:
- Создание сайтов любой сложности
- Лендинги для бизнеса  
- Интернет-магазины
- Корпоративные сайты

Цены: от 30,000 руб

ПРАВИЛА:
- Обращайся по имени, если оно есть
- Будь дружелюбным и профессиональным
- Кратко представься и расскажи о услугах
- Задай вопрос для вовлечения (например, "занимаетесь бизнесом?" или "интересен ли сайт?")
- Используй 1-2 emoji
- Максимум 2-3 предложения

Напиши ОДНО приветственное сообщение:"""

        print(f"🤖 Генерируем приветственное сообщение для {name}...")
        
        # Получаем ответ от LLM
        llm_response = await send_to_llm(welcome_prompt, f"Контакт: {name} ({phone})")
        
        if llm_response and llm_response.strip():
            print(f"✅ LLM сгенерировал: {llm_response}")
            message_to_send = llm_response
        else:
            print(f"❌ LLM не ответил, используем fallback")
            # Fallback-сообщение
            if name:
                message_to_send = f"Привет, {name}! 👋 Мы создаем сайты для бизнеса - от лендингов до интернет-магазинов. Цены от 30,000 руб. Занимаетесь бизнесом? Было бы актуально обсудить сайт? 🚀"
            else:
                message_to_send = "Привет! 👋 Мы создаем сайты для бизнеса - от лендингов до интернет-магазинов. Цены от 30,000 руб. Занимаетесь бизнесом? Было бы актуально обсудить сайт? 🚀"
        
        # Добавляем приветственное сообщение в историю диалога
        add_to_dialog_history(telegram_id, "bot", message_to_send)
        
        # Отправляем сообщение
        print(f"📤 Отправляем сообщение: {message_to_send}")
        await client.send_message(telegram_id, message_to_send)
        
        # Обновляем статус (кроме тестового режима)
        if not is_test_mode:
            database_functions.update_contact_status(telegram_id, "MESSAGE_SENT")
            # Сохраняем в results
            database_functions.save_result(phone, "SENT", message_to_send)
        else:
            print(f"🔧 Тестовый режим: статус не изменяется")
        
        print(f"✅ Сообщение отправлено контакту {name}")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка обработки контакта {contact.get('phone', 'unknown')}: {e}")
        return False

def generate_fallback_message(name):
    """Генерирует fallback сообщение если LLM не работает"""
    fallback_messages = [
        f"Привет! Я Роллан из компании bored.kz. Мы создаем сайты, интернет-магазины и делаем дизайн. Цены от 50 000 тенге. Занимаетесь бизнесом? Может быть, нужен сайт? 😊",
        f"Здравствуйте! Я Роллан, менеджер bored.kz. Мы разрабатываем сайты и веб-сервисы. Интересно ли вам создать сайт для бизнеса? Цены от 50 000 тенге.",
        f"Привет! Роллан из bored.kz. Мы делаем сайты, интернет-магазины и UX/UI-дизайн. Цены от 50 000 тенге. Планируете ли вы сайт для бизнеса?",
        f"Добрый день! Я Роллан, компания bored.kz. Создаем сайты, порталы и веб-сервисы. Цены от 50 000 тенге. Нужен ли вам сайт или дизайн?",
        f"Привет! Роллан из bored.kz. Мы разрабатываем сайты и интернет-магазины. Цены от 50 000 тенге. Интересно ли вам создать сайт для бизнеса? 😊"
    ]
    
    # Если есть имя, персонализируем сообщение
    if name and name.strip():
        return f"Привет, {name}! " + random.choice(fallback_messages)
    else:
        return random.choice(fallback_messages)

async def handle_message(event):
    """Обрабатывает входящие сообщения"""
    try:
        message = event.message
        sender_id = event.sender_id
        
        print(f"📨 Получено сообщение от {sender_id}: {message.text}")
        
        # Добавляем сообщение пользователя в историю диалога
        add_to_dialog_history(sender_id, "user", message.text)
        
        # Получаем информацию о контакте
        contact_info = database_functions.get_contact_by_telegram_id(sender_id)
        if not contact_info:
            print(f"❌ Контакт {sender_id} не найден в базе")
            return
        
        # Создаем контекстный промпт на основе сообщения пользователя и истории
        contextual_prompt = get_contextual_prompt(message.text, contact_info, sender_id)
        
        print(f"🤖 Отправляем контекстный промпт в LLM...")
        print(f"📝 Промпт: {contextual_prompt[:200]}...")
        
        # Получаем ответ от LLM
        llm_response = await send_to_llm(contextual_prompt, message.text)
        
        if llm_response and llm_response.strip():
            print(f"✅ LLM ответил: {llm_response}")
            
            # Добавляем ответ бота в историю диалога
            add_to_dialog_history(sender_id, "bot", llm_response)
            
            # Отправляем ответ клиенту
            await client.send_message(sender_id, llm_response)
            
            # Обновляем статус в базе данных (кроме тестового режима)
            if contact_info.get('status') != 'TEST':
                database_functions.update_contact_status(sender_id, "IN_DIALOG")
            
            # Сохраняем диалог в базу
            database_functions.save_dialog(sender_id, message.text, llm_response)
            
            print(f"✅ Сообщение отправлено и диалог сохранен")
        else:
            print(f"❌ LLM не ответил, используем fallback")
            
            # Используем fallback-ответ
            fallback_response = get_fallback_response(message.text)
            
            # Добавляем fallback в историю диалога
            add_to_dialog_history(sender_id, "bot", fallback_response)
            
            await client.send_message(sender_id, fallback_response)
            
            # Обновляем статус (кроме тестового режима)
            if contact_info.get('status') != 'TEST':
                database_functions.update_contact_status(sender_id, "IN_DIALOG")
            
            # Сохраняем диалог
            database_functions.save_dialog(sender_id, message.text, fallback_response)
            
            print(f"✅ Fallback отправлен")
            
    except Exception as e:
        print(f"❌ Ошибка обработки сообщения: {e}")
        # Отправляем извинение клиенту
        try:
            await client.send_message(sender_id, "Извините, произошла техническая ошибка. Попробуйте написать позже.")
        except:
            pass

def get_dialog_history(telegram_id, max_messages=10):
    """Получает историю диалога для контакта"""
    if telegram_id in dialog_memory:
        # Возвращаем последние max_messages сообщений
        history = dialog_memory[telegram_id][-max_messages:]
        return history
    return []

def add_to_dialog_history(telegram_id, role, message):
    """Добавляет сообщение в историю диалога"""
    if telegram_id not in dialog_memory:
        dialog_memory[telegram_id] = []
    
    dialog_memory[telegram_id].append({
        "role": role,
        "message": message,
        "timestamp": time.time()
    })
    
    # Ограничиваем историю 20 сообщениями
    if len(dialog_memory[telegram_id]) > 20:
        dialog_memory[telegram_id] = dialog_memory[telegram_id][-20:]

def format_dialog_history(history):
    """Форматирует историю диалога для промпта"""
    if not history:
        return ""
    
    formatted = "\n\nИстория диалога:\n"
    for msg in history:
        role = "КЛИЕНТ" if msg["role"] == "user" else "БОТ"
        formatted += f"{role}: {msg['message']}\n"
    
    return formatted

if __name__ == '__main__':
    # Восстанавливаем статусы при запуске
    parse_results_csv()
    
    # Запускаем бота
    asyncio.run(main())
