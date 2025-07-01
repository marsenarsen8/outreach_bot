import asyncio
import aiohttp
import config
import time

async def debug_llm_step_by_step():
    """Пошаговая диагностика LLM"""
    print("🔍 Детальная диагностика LLM...")
    
    # Шаг 1: Проверяем конфигурацию
    print("\n📋 Шаг 1: Конфигурация")
    print(f"   - Провайдер: {config.llm_provider}")
    print(f"   - API ключ: {config.gemini_api_key[:20]}...")
    print(f"   - Лимит в минуту: {config.gemini_rate_limit}")
    print(f"   - Дневной лимит: {config.gemini_daily_limit}")
    print(f"   - Задержка между запросами: {config.gemini_cooldown_seconds}с")
    
    # Шаг 2: Тестируем простой запрос
    print("\n📋 Шаг 2: Простой запрос к Gemini")
    api_key = config.gemini_api_key
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    
    headers = {"Content-Type": "application/json"}
    data = {
        "contents": [
            {"parts": [{"text": "Привет! Напиши короткое приветствие."}]}
        ],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 100,
            "topP": 0.8
        }
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            print(f"   📡 Отправляем запрос к: {url}")
            print(f"   📤 Данные: {data}")
            
            async with session.post(url, headers=headers, json=data) as response:
                print(f"   📡 Статус ответа: {response.status}")
                
                if response.status == 200:
                    result = await response.json()
                    print(f"   ✅ Ответ получен успешно")
                    
                    try:
                        text = result["candidates"][0]["content"]["parts"][0]["text"]
                        print(f"   📝 Текст ответа: {text}")
                        print("   ✅ LLM работает!")
                        return True
                    except Exception as e:
                        print(f"   ❌ Ошибка парсинга: {e}")
                        print(f"   📄 Полный ответ: {result}")
                        return False
                else:
                    error_text = await response.text()
                    print(f"   ❌ Ошибка API: {error_text}")
                    return False
                    
    except Exception as e:
        print(f"   ❌ Ошибка запроса: {e}")
        return False

    # Шаг 3: Тестируем промпт из outreach_bot.py
    print("\n📋 Шаг 3: Тестируем промпт из бота")
    
    # Импортируем функцию get_current_prompt
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    
    try:
        from outreach_bot import get_current_prompt
        
        prompt = get_current_prompt()
        print(f"   📝 Промпт из бота:")
        print(f"   {prompt[:200]}...")
        
        # Тестируем этот промпт
        data = {
            "contents": [
                {"parts": [{"text": prompt}]}
            ],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 200,
                "topP": 0.8
            }
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=data) as response:
                print(f"   📡 Статус ответа: {response.status}")
                
                if response.status == 200:
                    result = await response.json()
                    try:
                        text = result["candidates"][0]["content"]["parts"][0]["text"]
                        print(f"   ✅ LLM ответил на промпт бота:")
                        print(f"   📝 {text}")
                        return True
                    except Exception as e:
                        print(f"   ❌ Ошибка парсинга: {e}")
                        return False
                else:
                    error_text = await response.text()
                    print(f"   ❌ Ошибка API: {error_text}")
                    return False
                    
    except Exception as e:
        print(f"   ❌ Ошибка тестирования промпта: {e}")
        return False

async def main():
    success = await debug_llm_step_by_step()
    
    if success:
        print("\n✅ LLM работает корректно!")
        print("💡 Проблема может быть в:")
        print("   - Логике лимитов в outreach_bot.py")
        print("   - Обработке ответов")
        print("   - Промптах для диалогов")
    else:
        print("\n❌ LLM не работает")
        print("💡 Нужно проверить:")
        print("   - API ключ")
        print("   - Лимиты")
        print("   - Сетевые настройки")

if __name__ == "__main__":
    asyncio.run(main()) 