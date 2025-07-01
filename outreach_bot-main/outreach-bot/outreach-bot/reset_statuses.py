import sqlite3

# Подключаемся к БД
conn = sqlite3.connect('outreach_bot.db')
cursor = conn.cursor()

# Сбрасываем статусы всех контактов
cursor.execute('UPDATE contacts SET status = "NOT_SENT"')
updated_count = cursor.rowcount

conn.commit()
conn.close()

print(f"✅ Сброшены статусы {updated_count} контактов")
print("Теперь можно запускать рассылку!") 