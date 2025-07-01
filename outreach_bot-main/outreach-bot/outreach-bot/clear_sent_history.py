import sqlite3
import os

def clear_and_setup_test():
    """Очищает базу и настраивает тестовый режим"""
    db_path = 'outreach_bot.db'
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("🧹 Очищаем базу данных...")
        
        # Очищаем таблицу results (включая записи для тестового номера)
        cursor.execute("DELETE FROM results WHERE user_id = '77474582511'")
        print("✅ Записи SENT для тестового номера удалены")
        
        # Очищаем таблицу contacts, оставляем только тестовый номер
        cursor.execute("DELETE FROM contacts WHERE phone != '77474582511'")
        print("✅ Контакты очищены, оставлен только тестовый номер")
        
        # Проверяем, есть ли тестовый контакт
        cursor.execute("SELECT * FROM contacts WHERE phone = '77474582511'")
        test_contact = cursor.fetchone()
        
        if test_contact:
            # Обновляем статус на TEST
            cursor.execute("UPDATE contacts SET status = 'TEST' WHERE phone = '77474582511'")
            print("✅ Статус тестового контакта установлен в TEST")
        else:
            # Добавляем тестовый контакт
            cursor.execute("""
                INSERT INTO contacts (phone, name, telegram_id, status) 
                VALUES ('77474582511', 'Тестовый контакт', '77474582511', 'TEST')
            """)
            print("✅ Тестовый контакт добавлен")
        
        # Очищаем таблицу dialogs (если существует)
        try:
            cursor.execute("DELETE FROM dialogs")
            print("✅ Таблица dialogs очищена")
        except:
            print("ℹ️ Таблица dialogs не существует")
        
        # Очищаем таблицу prompts (если существует)
        try:
            cursor.execute("DELETE FROM prompts")
            print("✅ Таблица prompts очищена")
            
            # Добавляем базовый промпт
            cursor.execute("""
                INSERT INTO prompts (name, content, is_active) 
                VALUES ('Базовый промпт', 'Ты - профессиональный менеджер по продажам веб-разработки. Отвечай кратко и по делу.', 1)
            """)
            print("✅ Базовый промпт добавлен")
        except:
            print("ℹ️ Таблица prompts не существует")
        
        conn.commit()
        conn.close()
        
        print("\n✅ База данных настроена для тестирования!")
        print("📱 Тестовый номер: 77474582511")
        print("🔧 Статус: TEST (не меняется на SENT)")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    clear_and_setup_test() 