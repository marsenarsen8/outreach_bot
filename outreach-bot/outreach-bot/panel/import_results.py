import sys
import os
import pandas as pd
import sqlite3

# Добавляем родительскую директорию в путь для импорта
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import DB_PATH

def import_results_from_csv():
    """Импорт результатов из CSV файла в базу данных"""
    csv_file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'results.csv')
    
    if not os.path.exists(csv_file_path):
        print(f"Файл {csv_file_path} не найден!")
        return
    
    try:
        # Читаем CSV файл
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
            
            # Проверяем, есть ли уже такая запись
            cursor.execute('''
                SELECT id FROM results 
                WHERE user_id = ? AND status = ? AND text = ? AND timestamp = CURRENT_TIMESTAMP
            ''', (user_id, status, text))
            
            if not cursor.fetchone():
                cursor.execute('''
                    INSERT INTO results (user_id, status, text, reply, analysis)
                    VALUES (?, ?, ?, ?, ?)
                ''', (user_id, status, text, reply, analysis))
                imported_count += 1
        
        conn.commit()
        conn.close()
        
        print(f"Импортировано {imported_count} записей из {csv_file_path}")
        
    except Exception as e:
        print(f"Ошибка импорта результатов: {e}")

if __name__ == "__main__":
    import_results_from_csv() 