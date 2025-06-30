#!/usr/bin/env python3
"""
Тестовый скрипт для проверки запуска рассылки
"""

import subprocess
import sys
import os
import time
import sqlite3

def test_broadcast():
    """Тестирует запуск рассылки"""
    print("🧪 Тестирование рассылки...")
    
    # Проверяем количество контактов для рассылки
    conn = sqlite3.connect('outreach_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM contacts WHERE status = "NOT_SENT"')
    not_sent_count = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM contacts WHERE status = "SENT"')
    sent_count = cursor.fetchone()[0]
    conn.close()
    
    print(f"📊 Контакты для рассылки: {not_sent_count}")
    print(f"📊 Уже отправлено: {sent_count}")
    
    if not_sent_count == 0:
        print("❌ Нет контактов для рассылки!")
        return False
    
    # Запускаем бот
    print("🚀 Запускаем бот...")
    try:
        # Запускаем бот в фоновом режиме
        process = subprocess.Popen([sys.executable, 'outreach_bot.py'], 
                                 stdout=subprocess.PIPE, 
                                 stderr=subprocess.PIPE)
        
        print(f"✅ Бот запущен (PID: {process.pid})")
        
        # Ждем немного
        time.sleep(10)
        
        # Проверяем, работает ли процесс
        if process.poll() is None:
            print("✅ Бот работает")
            
            # Останавливаем бот
            process.terminate()
            process.wait()
            print("✅ Бот остановлен")
            return True
        else:
            stdout, stderr = process.communicate()
            print(f"❌ Бот завершился с ошибкой:")
            print(f"STDOUT: {stdout.decode()}")
            print(f"STDERR: {stderr.decode()}")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка запуска бота: {e}")
        return False

if __name__ == "__main__":
    test_broadcast() 