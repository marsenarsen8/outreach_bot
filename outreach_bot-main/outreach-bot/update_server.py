#!/usr/bin/env python3
"""
Скрипт для автоматического обновления сервера при push в GitHub
Запускается как webhook endpoint
"""

import os
import subprocess
import logging
import hmac
import hashlib
from flask import Flask, request, jsonify

app = Flask(__name__)

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Секретный ключ для верификации webhook (добавьте в GitHub secrets)
WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET', 'your-secret-key')

# Путь к проекту на сервере
PROJECT_PATH = '/path/to/your/project'  # Измените на ваш путь

def verify_signature(payload, signature):
    """Проверяет подпись webhook от GitHub"""
    expected_signature = 'sha256=' + hmac.new(
        WEBHOOK_SECRET.encode('utf-8'),
        payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected_signature, signature)

def update_server():
    """Обновляет код на сервере и перезапускает приложение"""
    try:
        logger.info("Начинаем обновление сервера...")
        
        # Переходим в директорию проекта
        os.chdir(PROJECT_PATH)
        
        # Получаем изменения из GitHub
        subprocess.run(['git', 'fetch', 'origin'], check=True)
        subprocess.run(['git', 'reset', '--hard', 'origin/main'], check=True)
        
        # Устанавливаем зависимости (если нужно)
        if os.path.exists('requirements.txt'):
            subprocess.run(['pip', 'install', '-r', 'requirements.txt'], check=True)
        
        # Перезапускаем приложение (замените на вашу команду)
        # Например, для systemd:
        # subprocess.run(['sudo', 'systemctl', 'restart', 'outreach-bot'], check=True)
        
        # Или для PM2:
        # subprocess.run(['pm2', 'restart', 'outreach-bot'], check=True)
        
        # Или просто перезапускаем процесс
        subprocess.run(['pkill', '-f', 'outreach_bot.py'], check=False)
        subprocess.Popen(['python', 'outreach_bot.py'], cwd=PROJECT_PATH)
        
        logger.info("Сервер успешно обновлен и перезапущен")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка при обновлении сервера: {e}")
        return False

@app.route('/webhook', methods=['POST'])
def webhook():
    """Обработчик webhook от GitHub"""
    
    # Проверяем подпись
    signature = request.headers.get('X-Hub-Signature-256')
    if not signature or not verify_signature(request.data, signature):
        return jsonify({'error': 'Invalid signature'}), 401
    
    # Проверяем, что это push в main ветку
    payload = request.get_json()
    if payload.get('ref') != 'refs/heads/main':
        return jsonify({'message': 'Not main branch'}), 200
    
    # Обновляем сервер
    success = update_server()
    
    if success:
        return jsonify({'message': 'Server updated successfully'}), 200
    else:
        return jsonify({'error': 'Failed to update server'}), 500

@app.route('/health', methods=['GET'])
def health():
    """Проверка здоровья сервиса"""
    return jsonify({'status': 'healthy'}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000) 