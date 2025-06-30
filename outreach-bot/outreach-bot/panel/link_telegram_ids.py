import sys
import os
import sqlite3
from datetime import datetime, timedelta

# Добавляем родительскую директорию в путь для импорта
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import DB_PATH

def link_telegram_ids():
    """Связать номера телефонов с Telegram ID на основе диалогов"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Получаем все уникальные номера телефонов (SENT сообщения)
    # Номера телефонов обычно 11-12 цифр
    cursor.execute('''
        SELECT DISTINCT user_id 
        FROM results 
        WHERE status = 'SENT' 
        AND LENGTH(user_id) >= 10 
        AND LENGTH(user_id) <= 12
        AND user_id NOT LIKE '%,%'
        ORDER BY user_id
    ''')
    phone_numbers = [row[0] for row in cursor.fetchall()]
    
    # Получаем все уникальные Telegram ID (REPLY/REFUSED сообщения)
    # Telegram ID обычно 7-10 цифр
    cursor.execute('''
        SELECT DISTINCT user_id 
        FROM results 
        WHERE status IN ('REPLY', 'REFUSED') 
        AND LENGTH(user_id) >= 7 
        AND LENGTH(user_id) <= 10
        AND user_id NOT LIKE '%,%'
        ORDER BY user_id
    ''')
    telegram_ids = [row[0] for row in cursor.fetchall()]
    
    print(f"Найдено {len(phone_numbers)} номеров телефонов и {len(telegram_ids)} Telegram ID")
    
    # Для каждого номера телефона ищем соответствующий Telegram ID
    # по временной близости сообщений
    linked_count = 0
    
    for phone in phone_numbers:
        # Получаем время последнего SENT сообщения для этого номера
        cursor.execute('''
            SELECT timestamp 
            FROM results 
            WHERE user_id = ? AND status = 'SENT'
            ORDER BY timestamp DESC 
            LIMIT 1
        ''', (phone,))
        
        sent_time_row = cursor.fetchone()
        if not sent_time_row:
            continue
            
        try:
            sent_time = datetime.fromisoformat(sent_time_row[0].replace('Z', '+00:00'))
        except:
            # Если не удается распарсить время, пропускаем
            continue
        
        # Ищем REPLY/REFUSED сообщения в течение 24 часов после SENT
        search_start = sent_time - timedelta(hours=24)
        search_end = sent_time + timedelta(hours=24)
        
        cursor.execute('''
            SELECT user_id, timestamp 
            FROM results 
            WHERE status IN ('REPLY', 'REFUSED') 
            AND LENGTH(user_id) >= 7 
            AND LENGTH(user_id) <= 10
            AND user_id NOT LIKE '%,%'
            AND timestamp BETWEEN ? AND ?
            ORDER BY timestamp
        ''', (search_start.isoformat(), search_end.isoformat()))
        
        replies = cursor.fetchall()
        
        if replies:
            # Берем первый ответ как наиболее вероятный
            telegram_id = replies[0][0]
            
            # Обновляем контакт с этим номером телефона
            cursor.execute('''
                UPDATE contacts 
                SET telegram_id = ? 
                WHERE phone = ?
            ''', (telegram_id, phone))
            
            print(f"Связал {phone} с Telegram ID {telegram_id}")
            linked_count += 1
    
    conn.commit()
    conn.close()
    
    print(f"Всего связано {linked_count} контактов")
    return linked_count

if __name__ == "__main__":
    link_telegram_ids() 