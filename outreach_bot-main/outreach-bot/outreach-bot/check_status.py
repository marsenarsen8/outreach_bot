import sqlite3

# Подключаемся к БД
conn = sqlite3.connect('outreach_bot.db')
cursor = conn.cursor()

# Проверяем статусы контактов
print("=== СТАТУСЫ КОНТАКТОВ ===")
cursor.execute('SELECT status, COUNT(*) FROM contacts GROUP BY status')
for status, count in cursor.fetchall():
    print(f"{status}: {count}")

# Проверяем номера в sent_phones
print("\n=== НОМЕРА В SENT_PHONES ===")
cursor.execute('SELECT DISTINCT user_id FROM results WHERE status = "SENT"')
sent_phones = [row[0] for row in cursor.fetchall()]
print(f"Всего номеров в sent_phones: {len(sent_phones)}")
for phone in sorted(sent_phones):
    print(f"  {phone}")

# Проверяем номера контактов
print("\n=== НОМЕРА КОНТАКТОВ ===")
cursor.execute('SELECT phone FROM contacts')
contact_phones = [row[0] for row in cursor.fetchall()]
print(f"Всего контактов: {len(contact_phones)}")
for phone in contact_phones:
    print(f"  {phone}")

# Проверяем пересечение
print("\n=== ПЕРЕСЕЧЕНИЕ ===")
intersection = set(contact_phones) & set(sent_phones)
print(f"Контакты, которые уже отправлялись: {len(intersection)}")
for phone in intersection:
    print(f"  {phone}")

not_sent = set(contact_phones) - set(sent_phones)
print(f"Контакты, которые НЕ отправлялись: {len(not_sent)}")
for phone in not_sent:
    print(f"  {phone}")

conn.close() 