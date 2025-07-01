import asyncio
import aiohttp
import config

async def test_gemini():
    """Тестируем Gemini API"""
    print("🧪 Тестируем Gemini API...")
    
    api_key = config.gemini_api_key
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    
    headers = {"Content-Type": "application/json"}
    data = {
        "contents": [
            {"parts": [{"text": "Привет! Напиши короткое приветствие на русском языке."}]}
        ],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 100,
            "topP": 0.8
        }
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=data) as response:
                print(f"📡 Статус ответа: {response.status}")
                
                if response.status == 200:
                    result = await response.json()
                    print("✅ Ответ получен:")
                    print(result)
                    
                    try:
                        text = result["candidates"][0]["content"]["parts"][0]["text"]
                        print(f"📝 Текст ответа: {text}")
                        return True
                    except Exception as e:
                        print(f"❌ Ошибка парсинга: {e}")
                        return False
                else:
                    error_text = await response.text()
                    print(f"❌ Ошибка API: {error_text}")
                    return False
                    
    except Exception as e:
        print(f"❌ Ошибка запроса: {e}")
        return False

async def test_llm_function():
    """Тестируем функцию send_to_llm из outreach_bot.py"""
    print("\n🧪 Тестируем функцию send_to_llm...")
    
    # Импортируем функцию из outreach_bot.py
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    
    try:
        from outreach_bot import send_to_llm
        
        prompt = "Напиши короткое приветствие для клиента"
        result = await send_to_llm(prompt, "Тестовый контекст")
        
        if result:
            print(f"✅ LLM ответил: {result}")
            return True
        else:
            print("❌ LLM не ответил")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка тестирования: {e}")
        return False

async def main():
    print("🔍 Диагностика LLM...")
    print(f"📋 Конфигурация:")
    print(f"   - Провайдер: {config.llm_provider}")
    print(f"   - API ключ: {config.gemini_api_key[:20]}...")
    print(f"   - Лимит в минуту: {config.gemini_rate_limit}")
    print(f"   - Дневной лимит: {config.gemini_daily_limit}")
    print()
    
    # Тест 1: Прямой запрос к Gemini
    success1 = await test_gemini()
    
    # Тест 2: Функция из outreach_bot.py
    success2 = await test_llm_function()
    
    print(f"\n📊 Результаты:")
    print(f"   - Прямой Gemini API: {'✅' if success1 else '❌'}")
    print(f"   - Функция send_to_llm: {'✅' if success2 else '❌'}")
    
    if not success1:
        print("\n💡 Возможные причины:")
        print("   - Неверный API ключ")
        print("   - Превышен лимит запросов")
        print("   - Проблемы с сетью")
        print("   - API ключ заблокирован")

if __name__ == "__main__":
    asyncio.run(main()) 