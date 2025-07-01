# Ваши настройки для Telegram и LLM

api_id = 24669464 # Замените на ваш api_id
api_hash = '882b8170c1b5f3482734face52c775cc'
phone = '+77778090282'  # Телефон аккаунта для рассылки
notify_user_id = 424969207  # Ваш user_id для уведомлений
ollama_api_url = 'http://localhost:11434/api/generate'  # URL Ollama/LM Studio
model_name = 'mistral:instruct'  # Название модели для Ollama/OpenAI
llm_provider = 'gemini'  # 'gemini', 'ollama' или 'openai'
gemini_api_key = 'AIzaSyA4ZtwvuTtZAFacW5Mx96FCQUuWctkyrSs'  # Ваш Gemini API-ключ

# Если понадобится OpenAI:
# openai_api_key = 'sk-...'
# openai_model = 'gpt-4o-mini'

delay_seconds = 30  # Задержка между сообщениями (30 секунд)
batch_size = 5  # Размер батча для параллельной обработки
max_retries = 3  # Максимальное количество попыток для LLM запросов
timeout_seconds = 15  # Таймаут для HTTP запросов

# Защита от лимитов Google Gemini
gemini_rate_limit = 15  # Запросов в минуту (обновлено)
gemini_daily_limit = 200  # Запросов в день (обновлено)
gemini_cooldown_seconds = 4  # Задержка между запросами к Gemini (чтобы не превышать 15/мин)

# Настройки для обработки аудио
enable_audio_processing = False  # Отключено для экономии лимитов
audio_notification_enabled = True  # Уведомления о получении аудио 