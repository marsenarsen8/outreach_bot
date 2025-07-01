import asyncio
import aiohttp
import config

async def test_gemini_simple():
    """Простой тест Gemini API"""
    print("🧪 Тестируем Gemini API...")
    
    api_key = config.gemini_api_key
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    
    headers = {"Content-Type": "application/json"}
    data = {
        "contents": [
            {"parts": [{"text": "Ты Роллан — виртуальный менеджер по продажам в компании bored.kz. Мы разрабатываем сайты, интернет-магазины, веб-сервисы, порталы и делаем UX/UI-дизайн. Цены начинаются от 50 000 тенге. Сгенерируй ОДНО короткое и цепляющее приветственное сообщение для первого контакта с холодным клиентом."}]}
        ],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 200,
            "topP": 0.8
        }
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=data) as response:
                print(f"📡 Статус ответа: {response.status}")
                
                if response.status == 200:
                    result = await response.json()
                    
                    try:
                        text = result["candidates"][0]["content"]["parts"][0]["text"]
                        print(f"✅ LLM ответил:")
                        print(f"📝 {text}")
                        return True
                    except Exception as e:
                        print(f"❌ Ошибка парсинга: {e}")
                        print(f"📄 Полный ответ: {result}")
                        return False
                else:
                    error_text = await response.text()
                    print(f"❌ Ошибка API: {error_text}")
                    return False
                    
    except Exception as e:
        print(f"❌ Ошибка запроса: {e}")
        return False

async def main():
    print("🔍 Диагностика LLM...")
    print(f"📋 Конфигурация:")
    print(f"   - Провайдер: {config.llm_provider}")
    print(f"   - API ключ: {config.gemini_api_key[:20]}...")
    print(f"   - Лимит в минуту: {config.gemini_rate_limit}")
    print(f"   - Дневной лимит: {config.gemini_daily_limit}")
    print()
    
    success = await test_gemini_simple()
    
    if success:
        print("\n✅ LLM работает корректно!")
        print("💡 Проблема может быть в:")
        print("   - Лимитах запросов в outreach_bot.py")
        print("   - Логике проверки лимитов")
        print("   - Кэшировании")
    else:
        print("\n❌ LLM не работает")

if __name__ == "__main__":
    asyncio.run(main()) 