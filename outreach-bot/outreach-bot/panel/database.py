import sqlite3
import os
import pandas as pd
from datetime import datetime
from typing import List, Dict, Optional
import json

# Путь к базе данных
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'outreach_bot.db')

def init_database():
    """Инициализация базы данных"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Создаем таблицу контактов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT UNIQUE NOT NULL,
            name TEXT,
            email TEXT,
            company TEXT,
            notes TEXT,
            status TEXT DEFAULT 'NOT_SENT',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Создаем таблицу результатов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            status TEXT NOT NULL,
            text TEXT,
            reply TEXT,
            analysis TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Создаем таблицу промптов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS prompts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            content TEXT NOT NULL,
            description TEXT,
            is_active BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Создаем таблицу базы знаний
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS knowledge_base (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            content TEXT NOT NULL,
            category TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Создаем индексы для быстрого поиска
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_contacts_phone ON contacts(phone)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_results_user_id ON results(user_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_results_status ON results(status)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_prompts_active ON prompts(is_active)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_knowledge_category ON knowledge_base(category)')
    
    conn.commit()
    conn.close()

def import_contacts_from_csv(csv_file_path: str) -> int:
    """Импорт контактов из CSV файла"""
    try:
        # Читаем CSV файл
        df = pd.read_csv(csv_file_path)
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        imported_count = 0
        
        for _, row in df.iterrows():
            phone = str(row['phone']).strip()
            
            # Проверяем, существует ли уже контакт с таким номером
            cursor.execute('SELECT id FROM contacts WHERE phone = ?', (phone,))
            if not cursor.fetchone():
                cursor.execute('''
                    INSERT INTO contacts (phone, name, status)
                    VALUES (?, ?, ?)
                ''', (phone, '', 'NOT_SENT'))
                imported_count += 1
        
        conn.commit()
        conn.close()
        
        return imported_count
    except Exception as e:
        print(f"Ошибка импорта контактов: {e}")
        return 0

def import_results_from_csv(csv_file_path: str) -> int:
    """Импорт результатов из CSV файла"""
    try:
        # Читаем CSV файл с правильными параметрами
        df = pd.read_csv(csv_file_path, header=None, 
                        names=['user_id', 'status', 'text', 'reply', 'analysis'],
                        quoting=1, escapechar='\\', on_bad_lines='skip')
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        imported_count = 0
        
        for _, row in df.iterrows():
            user_id = str(row['user_id']).strip()
            status = str(row['status']).strip()
            text = str(row.get('text', '')).strip()
            reply = str(row.get('reply', '')).strip()
            analysis = str(row.get('analysis', '')).strip()
            
            cursor.execute('''
                INSERT INTO results (user_id, status, text, reply, analysis)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, status, text, reply, analysis))
            imported_count += 1
        
        conn.commit()
        conn.close()
        
        return imported_count
    except Exception as e:
        print(f"Ошибка импорта результатов: {e}")
        return 0

def get_contacts() -> List[Dict]:
    """Получить все контакты с их статусами"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT c.id, c.phone, c.name, c.email, c.company, c.notes, c.status,
               r.text as last_text, r.analysis
        FROM contacts c
        LEFT JOIN (
            SELECT user_id, text, analysis, timestamp,
                   ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY timestamp DESC) as rn
            FROM results
        ) r ON c.phone = r.user_id AND r.rn = 1
        ORDER BY c.id
    ''')
    
    contacts = []
    for row in cursor.fetchall():
        contacts.append({
            'id': row[0],
            'phone': row[1],
            'name': row[2] or '',
            'email': row[3] or '',
            'company': row[4] or '',
            'notes': row[5] or '',
            'status': row[6],
            'last_text': row[7] or '',
            'analysis': row[8] or ''
        })
    
    conn.close()
    return contacts

def get_contact_by_id(contact_id: int) -> Optional[Dict]:
    """Получить контакт по ID"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM contacts WHERE id = ?', (contact_id,))
    row = cursor.fetchone()
    
    conn.close()
    
    if row:
        return {
            'id': row[0],
            'phone': row[1],
            'name': row[2],
            'email': row[3],
            'company': row[4],
            'notes': row[5],
            'status': row[6],
            'created_at': row[7],
            'updated_at': row[8]
        }
    return None

def create_contact(contact_data: Dict) -> Dict:
    """Создать новый контакт"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO contacts (phone, name, email, company, notes)
        VALUES (?, ?, ?, ?, ?)
    ''', (
        contact_data['phone'],
        contact_data.get('name', ''),
        contact_data.get('email', ''),
        contact_data.get('company', ''),
        contact_data.get('notes', '')
    ))
    
    contact_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return get_contact_by_id(contact_id)

def update_contact(contact_id: int, contact_data: Dict) -> Optional[Dict]:
    """Обновить контакт"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE contacts 
        SET phone = ?, name = ?, email = ?, company = ?, notes = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (
        contact_data.get('phone', ''),
        contact_data.get('name', ''),
        contact_data.get('email', ''),
        contact_data.get('company', ''),
        contact_data.get('notes', ''),
        contact_id
    ))
    
    conn.commit()
    conn.close()
    
    return get_contact_by_id(contact_id)

def delete_contact(contact_id: int) -> bool:
    """Удалить контакт"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM contacts WHERE id = ?', (contact_id,))
    deleted = cursor.rowcount > 0
    
    conn.commit()
    conn.close()
    
    return deleted

def get_dialog_history(user_id: str) -> List[Dict]:
    """Получить историю диалога для пользователя (по номеру или telegram_id)"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Получаем telegram_id для этого контакта
    cursor.execute('SELECT telegram_id FROM contacts WHERE phone = ?', (user_id,))
    row = cursor.fetchone()
    telegram_id = row[0] if row else None

    # Если есть telegram_id, ищем по обоим идентификаторам
    if telegram_id:
        cursor.execute('''
            SELECT status, text, reply, analysis, timestamp
            FROM results
            WHERE user_id = ? OR user_id = ?
            ORDER BY timestamp
        ''', (user_id, telegram_id))
    else:
        cursor.execute('''
            SELECT status, text, reply, analysis, timestamp
            FROM results
            WHERE user_id = ?
            ORDER BY timestamp
        ''', (user_id,))
    
    history = []
    for row in cursor.fetchall():
        status, text, reply, analysis, timestamp = row
        if status == 'SENT':
            history.append({
                'type': 'bot',
                'text': text or '',
                'reply': '',
                'analysis': '',
                'timestamp': timestamp
            })
        elif status in ['REPLY', 'REFUSED']:
            history.append({
                'type': 'client',
                'text': text or '',
                'reply': reply or '',
                'analysis': analysis or '',
                'timestamp': timestamp
            })
    conn.close()
    return history

def get_statistics() -> Dict:
    """Получить статистику"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Общее количество контактов
    cursor.execute('SELECT COUNT(*) FROM contacts')
    total_contacts = cursor.fetchone()[0]
    
    # Статистика по статусам
    cursor.execute('''
        SELECT status, COUNT(*) as count
        FROM results
        GROUP BY status
    ''')
    status_stats = dict(cursor.fetchall())
    
    # Количество заинтересованных
    cursor.execute('''
        SELECT COUNT(*) 
        FROM results 
        WHERE analysis = 'ДА'
    ''')
    total_interested = cursor.fetchone()[0]
    
    conn.close()
    
    return {
        'total_contacts': total_contacts,
        'total_sent': status_stats.get('SENT', 0),
        'total_replies': status_stats.get('REPLY', 0),
        'total_refused': status_stats.get('REFUSED', 0),
        'total_interested': total_interested,
        'daily_stats': status_stats
    }

def export_contacts_to_csv() -> str:
    """Экспорт контактов в CSV"""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query('SELECT phone, name, email, company, notes, status FROM contacts', conn)
    conn.close()
    
    export_path = os.path.join(os.path.dirname(DB_PATH), 'contacts_export.csv')
    df.to_csv(export_path, index=False)
    return export_path

def get_prompts() -> List[Dict]:
    """Получить все промпты"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM prompts ORDER BY id')
    prompts = []
    for row in cursor.fetchall():
        prompts.append({
            'id': row[0],
            'name': row[1],
            'content': row[2],
            'description': row[3],
            'is_active': bool(row[4]),
            'created_at': row[5],
            'updated_at': row[6]
        })
    
    conn.close()
    return prompts

def get_active_prompt() -> Optional[Dict]:
    """Получить активный промпт"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM prompts WHERE is_active = 1 LIMIT 1')
    row = cursor.fetchone()
    
    conn.close()
    
    if row:
        return {
            'id': row[0],
            'name': row[1],
            'content': row[2],
            'description': row[3],
            'is_active': bool(row[4]),
            'created_at': row[5],
            'updated_at': row[6]
        }
    return None

def create_prompt(prompt_data: Dict) -> Dict:
    """Создать новый промпт"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Если новый промпт активный, деактивируем остальные
    if prompt_data.get('is_active'):
        cursor.execute('UPDATE prompts SET is_active = 0')
    
    cursor.execute('''
        INSERT INTO prompts (name, content, description, is_active)
        VALUES (?, ?, ?, ?)
    ''', (
        prompt_data['name'],
        prompt_data['content'],
        prompt_data.get('description', ''),
        prompt_data.get('is_active', False)
    ))
    
    prompt_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return get_prompt_by_id(prompt_id)

def get_prompt_by_id(prompt_id: int) -> Optional[Dict]:
    """Получить промпт по ID"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM prompts WHERE id = ?', (prompt_id,))
    row = cursor.fetchone()
    
    conn.close()
    
    if row:
        return {
            'id': row[0],
            'name': row[1],
            'content': row[2],
            'description': row[3],
            'is_active': bool(row[4]),
            'created_at': row[5],
            'updated_at': row[6]
        }
    return None

def update_prompt(prompt_id: int, prompt_data: Dict) -> Optional[Dict]:
    """Обновить промпт"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Если промпт становится активным, деактивируем остальные
    if prompt_data.get('is_active'):
        cursor.execute('UPDATE prompts SET is_active = 0 WHERE id != ?', (prompt_id,))
    
    cursor.execute('''
        UPDATE prompts 
        SET name = ?, content = ?, description = ?, is_active = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (
        prompt_data['name'],
        prompt_data['content'],
        prompt_data.get('description', ''),
        prompt_data.get('is_active', False),
        prompt_id
    ))
    
    conn.commit()
    conn.close()
    
    return get_prompt_by_id(prompt_id)

def delete_prompt(prompt_id: int) -> bool:
    """Удалить промпт"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM prompts WHERE id = ?', (prompt_id,))
    success = cursor.rowcount > 0
    
    conn.commit()
    conn.close()
    
    return success

def set_active_prompt(prompt_id: int) -> bool:
    """Установить промпт как активный"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Деактивируем все промпты
    cursor.execute('UPDATE prompts SET is_active = 0')
    
    # Активируем выбранный
    cursor.execute('UPDATE prompts SET is_active = 1 WHERE id = ?', (prompt_id,))
    success = cursor.rowcount > 0
    
    conn.commit()
    conn.close()
    
    return success

def get_knowledge_base() -> List[Dict]:
    """Получить всю базу знаний"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM knowledge_base ORDER BY category, filename')
    knowledge = []
    for row in cursor.fetchall():
        knowledge.append({
            'id': row[0],
            'filename': row[1],
            'content': row[2],
            'category': row[3],
            'created_at': row[4],
            'updated_at': row[5]
        })
    
    conn.close()
    return knowledge

def import_knowledge_from_files(knowledge_dir: str) -> int:
    """Импорт базы знаний из файлов"""
    import os
    import glob
    
    if not os.path.exists(knowledge_dir):
        return 0
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Очищаем старую базу знаний
    cursor.execute('DELETE FROM knowledge_base')
    
    imported_count = 0
    supported_extensions = ['*.txt', '*.md', '*.csv']
    
    for extension in supported_extensions:
        pattern = os.path.join(knowledge_dir, '**', extension)
        files = glob.glob(pattern, recursive=True)
        
        for file_path in files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    filename = os.path.basename(file_path)
                    category = os.path.splitext(filename)[0]
                    
                    cursor.execute('''
                        INSERT INTO knowledge_base (filename, content, category)
                        VALUES (?, ?, ?)
                    ''', (filename, content, category))
                    imported_count += 1
            except Exception as e:
                print(f"Ошибка чтения файла {file_path}: {e}")
    
    conn.commit()
    conn.close()
    
    return imported_count

def update_knowledge_item(knowledge_id: int, knowledge_data: Dict) -> Optional[Dict]:
    """Обновить элемент базы знаний"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE knowledge_base 
        SET filename = ?, content = ?, category = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (
        knowledge_data['filename'],
        knowledge_data['content'],
        knowledge_data.get('category', ''),
        knowledge_id
    ))
    
    conn.commit()
    conn.close()
    
    return get_knowledge_item_by_id(knowledge_id)

def get_knowledge_item_by_id(knowledge_id: int) -> Optional[Dict]:
    """Получить элемент базы знаний по ID"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM knowledge_base WHERE id = ?', (knowledge_id,))
    row = cursor.fetchone()
    
    conn.close()
    
    if row:
        return {
            'id': row[0],
            'filename': row[1],
            'content': row[2],
            'category': row[3],
            'created_at': row[4],
            'updated_at': row[5]
        }
    return None

def delete_knowledge_item(knowledge_id: int) -> bool:
    """Удалить элемент базы знаний"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM knowledge_base WHERE id = ?', (knowledge_id,))
    success = cursor.rowcount > 0
    
    conn.commit()
    conn.close()
    
    return success

# Инициализируем базу данных при импорте модуля
init_database() 