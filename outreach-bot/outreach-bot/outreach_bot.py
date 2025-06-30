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
gemini_last_request_time = 0
gemini_daily_requests = 0
gemini_last_reset = time.time()
gemini_minute_requests = []  # Список временных меток запросов за последнюю минуту

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
def get_relevant_knowledge(query, max_chars=1000):
    """Возвращает релевантную информацию из базы знаний для запроса"""
    if not knowledge_base:
        return ""
    
    # Простой поиск по ключевым словам
    query_lower = query.lower()
    relevant_parts = []
    
    for content in knowledge_base:
        # Ищем совпадения ключевых слов
        if any(word in content.lower() for word in query_lower.split()):
            relevant_parts.append(content)
    
    if relevant_parts:
        # Объединяем релевантные части
        combined = "\n".join(relevant_parts)
        # Ограничиваем длину
        if len(combined) > max_chars:
            combined = combined[:max_chars] + "..."
        return f"\n\n📚 Релевантная информация из базы знаний:\n{combined}"
    
    return ""

# Функция для получения активного промпта из базы данных
def get_current_prompt():
    """Получает активный промпт из базы данных"""
    try:
        active_prompt = database_functions.get_active_prompt()
        if active_prompt:
            return active_prompt['content']
        else:
            # Возвращаем промпт по умолчанию
            return """
Всегда отвечай на русском языке. Ты Роллан — виртуальный менеджер по продажам в компании bored.kz. Мы разрабатываем сайты, интернет-магазины, веб-сервисы, порталы и делаем UX/UI-дизайн. Цены начинаются от 50 000 тенге.

Ты пишешь первым «холодному» контакту, который ничего о нас не знает. Твоя задача — вежливо представиться, кратко и понятно рассказать, чем занимается компания, и предложить сотрудничество.

💬 Правила:
- Пиши в дружелюбном, неформальном, но уважительном тоне.
- Используй emoji в начале или конце.
- Не перечисляй все услуги и не пиши длинный текст — будь лаконичным.
- Обязательно задай уточняющий вопрос: например, занимается ли человек бизнесом, интересен ли ему сайт, нужен ли новый визуал.
- Если человек отказывается — поблагодари за ответ и больше не пиши.
- Если заинтересован — уточни, какой сайт может понадобиться, и предложи передать его контакт менеджеру для консультации.
- Используй информацию из базы знаний для более точных и убедительных ответов.

✏️ Задача: сгенерируй ОДНО короткое и цепляющее приветственное сообщение для первого контакта с холодным клиентом. Включи:
1. Приветствие с именем (если есть),
2. Кто ты и чем занимается bored.kz,
3. Предложение сотрудничества (создание сайта, визуал, онлайн-платформа),
4. Вопрос для вовлечения (например, «занимаетесь бизнесом?» или «было бы актуально обсудить сайт?»).

Не повторяй примеры, просто выдай один готовый текст, как для отправки в Telegram.
"""
    except Exception as e:
        logging.error(f'Ошибка получения промпта из БД: {e}')
        return ""

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

# Загрузка уже обработанных номеров
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
        # Проверяем кэш
        cache_key = hash(prompt + context)
        if cache_key in llm_cache:
            logging.info('Используем кэшированный ответ LLM')
            return llm_cache[cache_key]
        
        # Добавляем релевантную информацию из базы знаний
        knowledge_context = get_relevant_knowledge(prompt + " " + context)
        enhanced_prompt = prompt + knowledge_context
        
        session = await get_session()
        
        if llm_provider == 'gemini':
            if not check_gemini_limits():
                return ""
            
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
                if response.status == 200:
                    result = await response.json()
                    try:
                        text = result["candidates"][0]["content"]["parts"][0]["text"]
                        logging.info(f'Gemini ответил: {text[:100]}...')
                        # Кэшируем ответ
                        if len(llm_cache) >= CACHE_SIZE:
                            llm_cache.pop(next(iter(llm_cache)))
                        llm_cache[cache_key] = text
                        update_gemini_limits()
                        return text
                    except Exception as e:
                        logging.error(f'Ошибка парсинга ответа Gemini: {e}, raw: {result}')
                        return ""
                else:
                    logging.error(f'Ошибка Gemini API: {response.status} - {await response.text()}')
                    return ""
                    
        elif llm_provider == 'ollama':
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
                if response.status == 200:
                    result = await response.json()
                    text = result.get('response', '').strip()
                    logging.info(f'Ollama ответил: {text[:100]}...')
                    # Кэшируем ответ
                    if len(llm_cache) >= CACHE_SIZE:
                        llm_cache.pop(next(iter(llm_cache)))
                    llm_cache[cache_key] = text
                    return text
                else:
                    logging.error(f'Ошибка Ollama API: {response.status} - {await response.text()}')
                    return ""
        # Можно добавить OpenAI аналогично
        else:
            logging.error(f'Неизвестный llm_provider: {llm_provider}')
            return ""
    except Exception as e:
        logging.error(f'Ошибка запроса к LLM ({llm_provider}): {e}')
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

    # Оптимизированная отправка сообщений с батчингом
    batch_size = 5  # Отправляем по 5 сообщений за раз
    for i in range(0, len(contacts), batch_size):
        batch = contacts[i:i+batch_size]
        tasks = []
        
        for contact in batch:
            if contact['phone'] not in sent_phones:
                task = process_contact(contact)
                tasks.append(task)
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
            print(f"Обработан батч {i//batch_size + 1}/{(len(contacts) + batch_size - 1)//batch_size}")

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
    """Проверяет лимиты Gemini"""
    global gemini_request_count, gemini_daily_requests, gemini_minute_requests
    reset_gemini_daily_limit()
    now = time.time()
    # Очищаем старые метки (старше 60 секунд)
    gemini_minute_requests = [t for t in gemini_minute_requests if now - t < 60]
    if len(gemini_minute_requests) >= gemini_rate_limit:
        logging.warning(f"Достигнут лимит Gemini по минуте: {len(gemini_minute_requests)}/{gemini_rate_limit}")
        # Уведомление в Telegram
        asyncio.create_task(client.send_message(notify_user_id, f'❗️Достигнут лимит Gemini: {len(gemini_minute_requests)}/{gemini_rate_limit} в минуту'))
        return False
    if gemini_daily_requests >= gemini_daily_limit:
        logging.warning(f"Достигнут дневной лимит Gemini: {gemini_daily_requests}")
        asyncio.create_task(client.send_message(notify_user_id, f'❗️Достигнут дневной лимит Gemini: {gemini_daily_requests}/{gemini_daily_limit}'))
        return False
    current_time = time.time()
    if current_time - gemini_last_request_time < gemini_cooldown_seconds:
        logging.warning("Слишком частые запросы к Gemini")
        return False
    return True

def update_gemini_limits():
    """Обновляет счетчики лимитов Gemini"""
    global gemini_request_count, gemini_last_request_time, gemini_daily_requests, gemini_minute_requests
    gemini_request_count += 1
    gemini_last_request_time = time.time()
    gemini_daily_requests += 1
    gemini_minute_requests.append(gemini_last_request_time)

async def process_contact(contact):
    """Обработать один контакт"""
    try:
        phone = contact['phone']
        name = contact.get('name', '')
        
        # Получаем актуальный промпт
        current_prompt = get_current_prompt()
        
        # Генерируем сообщение
        message = await send_to_llm(current_prompt, f"Имя: {name}")
        
        if message:
            # Отправляем сообщение
            await client.send_message(phone, message)
            
            # Сохраняем результат
            database_functions.add_result(phone, 'SENT', message, '', '')
            database_functions.update_contact_status(contact['id'], 'SENT')
            
            sent_phones.add(phone)
            print(f"✅ Отправлено {name} ({phone}): {message[:50]}...")
            
            # Задержка между сообщениями
            await asyncio.sleep(delay_seconds)
        else:
            print(f"❌ Не удалось сгенерировать сообщение для {name} ({phone})")
            
    except Exception as e:
        print(f"❌ Ошибка обработки контакта {contact.get('name', 'Unknown')} ({contact['phone']}): {e}")
        logging.error(f"Ошибка обработки контакта {contact['phone']}: {e}")

if __name__ == '__main__':
    # Восстанавливаем статусы при запуске
    parse_results_csv()
    
    # Запускаем бота
    asyncio.run(main())
