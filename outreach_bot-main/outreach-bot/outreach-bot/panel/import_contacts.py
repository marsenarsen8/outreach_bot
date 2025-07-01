import sys
import os
import pandas as pd
import sqlite3

# Добавляем родительскую директорию в путь для импорта
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import DB_PATH

def import_contacts_from_csv():
    """Импорт контактов из CSV файла в базу данных"""
    csv_file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'results.csv')
    
    if not os.path.exists(csv_file_path):
        print(f"Файл {csv_file_path} не найден!")
        return
    
    try:
        # Читаем CSV файл
        df = pd.read_csv(csv_file_path, header=None, 
                        names=['user_id', 'status', 'text', 'reply', 'analysis'],
                        quoting=1, escapechar='\\', on_bad_lines='skip')
        
        # Получаем уникальные номера телефонов
        unique_phones = df['user_id'].unique()
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        imported_count = 0
        
        for phone in unique_phones:
            phone = str(phone).strip()
            
            # Проверяем, есть ли уже контакт с таким номером
            cursor.execute('SELECT id FROM contacts WHERE phone = ?', (phone,))
            if not cursor.fetchone():
                cursor.execute('''
                    INSERT INTO contacts (phone, name, status)
                    VALUES (?, ?, ?)
                ''', (phone, '', 'NOT_SENT'))
                imported_count += 1
        
        conn.commit()
        conn.close()
        
        print(f"Импортировано {imported_count} контактов из {csv_file_path}")
        
    except Exception as e:
        print(f"Ошибка импорта контактов: {e}")

if __name__ == "__main__":
    import_contacts_from_csv() 