import sqlite3
import os
import pandas as pd
from datetime import datetime
from typing import List, Dict, Optional

# Путь к базе данных
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'outreach_bot.db')

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
    
    # Создаем индексы для быстрого поиска (с проверкой существования)
    try:
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_contacts_phone ON contacts(phone)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_results_user_id ON results(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_results_status ON results(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_prompts_active ON prompts(is_active)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_knowledge_category ON knowledge_base(category)')
    except Exception as e:
        print(f"Предупреждение при создании индексов: {e}")
    
    conn.commit()
    conn.close()

def get_contacts() -> List[Dict]:
    """Получить все контакты"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM contacts ORDER BY id')
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
            'created_at': row[7],
            'updated_at': row[8]
        })
    
    conn.close()
    return contacts

def get_contacts_not_sent() -> List[Dict]:
    """Получить контакты, которым еще не отправляли сообщения"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM contacts WHERE status = "NOT_SENT" ORDER BY id')
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
            'created_at': row[7],
            'updated_at': row[8]
        })
    
    conn.close()
    return contacts

def update_contact_status(contact_id: int, status: str):
    """Обновить статус контакта"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE contacts 
        SET status = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (status, contact_id))
    
    conn.commit()
    conn.close()

def add_result(user_id: str, status: str, text: str = '', reply: str = '', analysis: str = ''):
    """Добавить результат диалога"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO results (user_id, status, text, reply, analysis)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, status, text, reply, analysis))
    
    conn.commit()
    conn.close()

def get_results() -> List[Dict]:
    """Получить все результаты"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM results ORDER BY timestamp')
    results = []
    for row in cursor.fetchall():
        results.append({
            'id': row[0],
            'user_id': row[1],
            'status': row[2],
            'text': row[3] or '',
            'reply': row[4] or '',
            'analysis': row[5] or '',
            'timestamp': row[6]
        })
    
    conn.close()
    return results

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

def get_contacts_for_broadcast():
    """Получает контакты для рассылки (включая тестовые)"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Получаем контакты со статусом NOT_SENT или TEST
        cursor.execute("""
            SELECT id, phone, name, telegram_id, status 
            FROM contacts 
            WHERE status IN ('NOT_SENT', 'TEST')
            ORDER BY id
        """)
        
        contacts = []
        for row in cursor.fetchall():
            contact = {
                'id': row[0],
                'phone': row[1],
                'name': row[2],
                'telegram_id': row[3],
                'status': row[4]
            }
            contacts.append(contact)
        
        conn.close()
        return contacts
        
    except Exception as e:
        print(f"Ошибка получения контактов для рассылки: {e}")
        return []

# Инициализируем базу данных при импорте модуля
init_database() 