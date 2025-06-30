# Инструкция по автоматическому деплою

## 1. Деплой дашборда на Railway

### Шаг 1: Создайте аккаунт на Railway
1. Зайдите на [railway.app](https://railway.app)
2. Войдите через GitHub
3. Создайте новый проект

### Шаг 2: Настройте GitHub Secrets
В вашем репозитории GitHub:
1. Settings → Secrets and variables → Actions
2. Добавьте секрет `RAILWAY_TOKEN` с токеном из Railway

### Шаг 3: Настройте Railway
1. Подключите ваш GitHub репозиторий
2. Укажите путь к папке: `outreach-bot/panel`
3. Установите переменные окружения:
   ```
   PORT=8000
   ```

### Шаг 4: Деплой
При каждом push в ветку `main` дашборд будет автоматически обновляться!

## 2. Автоматическое обновление сервера

### Шаг 1: Настройте webhook на сервере
1. Скопируйте `update_server.py` на ваш сервер
2. Установите зависимости:
   ```bash
   pip install flask
   ```
3. Измените `PROJECT_PATH` в скрипте на путь к вашему проекту
4. Запустите webhook сервер:
   ```bash
   python update_server.py
   ```

### Шаг 2: Настройте GitHub Webhook
1. В репозитории: Settings → Webhooks → Add webhook
2. Payload URL: `http://your-server-ip:5000/webhook`
3. Content type: `application/json`
4. Secret: создайте секретный ключ и добавьте в `WEBHOOK_SECRET`
5. Events: выберите "Just the push event"

### Шаг 3: Настройте автозапуск webhook
Создайте systemd сервис:
```bash
sudo nano /etc/systemd/system/github-webhook.service
```

Содержимое:
```ini
[Unit]
Description=GitHub Webhook Server
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/path/to/update_server.py
ExecStart=/usr/bin/python3 /path/to/update_server.py
Restart=always
Environment=WEBHOOK_SECRET=your-secret-key

[Install]
WantedBy=multi-user.target
```

Запустите:
```bash
sudo systemctl enable github-webhook
sudo systemctl start github-webhook
```

## 3. Альтернативные варианты деплоя

### Render (бесплатно)
1. Зайдите на [render.com](https://render.com)
2. Подключите GitHub репозиторий
3. Выберите "Web Service"
4. Укажите путь: `outreach-bot/panel`
5. Build Command: `pip install -r requirements.txt`
6. Start Command: `python app.py`

### Heroku (есть бесплатный план)
1. Создайте аккаунт на [heroku.com](https://heroku.com)
2. Установите Heroku CLI
3. Создайте `Procfile` в папке `panel`:
   ```
   web: python app.py
   ```
4. Деплой через GitHub Actions

## 4. Мониторинг и логи

### Проверка статуса webhook
```bash
curl http://your-server-ip:5000/health
```

### Просмотр логов
```bash
# Логи webhook сервера
sudo journalctl -u github-webhook -f

# Логи вашего приложения
tail -f outreach_debug.log
```

## 5. Безопасность

### Рекомендации:
1. Используйте HTTPS для webhook (настройте SSL)
2. Регулярно меняйте секретные ключи
3. Ограничьте доступ к webhook endpoint
4. Настройте firewall

### Настройка SSL с Let's Encrypt:
```bash
sudo apt install certbot
sudo certbot certonly --standalone -d your-domain.com
```

## 6. Troubleshooting

### Проблемы с деплоем:
1. Проверьте логи GitHub Actions
2. Убедитесь, что все зависимости установлены
3. Проверьте переменные окружения

### Проблемы с webhook:
1. Проверьте доступность порта 5000
2. Убедитесь, что webhook сервер запущен
3. Проверьте правильность секретного ключа
4. Посмотрите логи webhook сервера

### Проблемы с обновлением:
1. Проверьте права доступа к папке проекта
2. Убедитесь, что git настроен правильно
3. Проверьте, что процесс перезапускается корректно 