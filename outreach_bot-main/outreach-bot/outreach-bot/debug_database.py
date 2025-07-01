import sqlite3

def debug_database():
    """Диагностика базы данных"""
    try:
        conn = sqlite3.connect('outreach_bot.db')
        cursor = conn.cursor()
        
        print("🔍 Диагностика базы данных...")
        
        # Проверяем таблицу contacts
        print("\n📋 Таблица contacts:")
        cursor.execute("SELECT * FROM contacts")
        contacts = cursor.fetchall()
        
        if contacts:
            for contact in contacts:
                print(f"   ID: {contact[0]}, Phone: {contact[1]}, Name: {contact[2]}, Telegram: {contact[3]}, Status: {contact[4]}")
        else:
            print("   ❌ Контакты не найдены")
        
        # Проверяем таблицу results
        print("\n📋 Таблица results:")
        cursor.execute("SELECT * FROM results")
        results = cursor.fetchall()
        
        if results:
            for result in results:
                print(f"   Phone: {result[0]}, Status: {result[1]}, Message: {result[2][:50]}...")
        else:
            print("   ✅ Таблица results пуста")
        
        # Проверяем функцию get_contacts_for_broadcast
        print("\n📋 Тестируем get_contacts_for_broadcast:")
        cursor.execute("""
            SELECT id, phone, name, telegram_id, status 
            FROM contacts 
            WHERE status IN ('NOT_SENT', 'TEST')
            ORDER BY id
        """)
        
        broadcast_contacts = cursor.fetchall()
        if broadcast_contacts:
            for contact in broadcast_contacts:
                print(f"   ID: {contact[0]}, Phone: {contact[1]}, Name: {contact[2]}, Telegram: {contact[3]}, Status: {contact[4]}")
        else:
            print("   ❌ Контакты для рассылки не найдены")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    debug_database() 