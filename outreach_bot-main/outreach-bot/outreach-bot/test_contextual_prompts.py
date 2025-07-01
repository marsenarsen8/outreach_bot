import asyncio
import sys
import os
import config

# Добавляем путь к модулям
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Импортируем только нужные функции
from outreach_bot import get_contextual_prompt, get_current_prompt, get_relevant_knowledge

async def test_contextual_prompts():
    """Тестирует контекстные промпты"""
    print("🧪 Тестирование контекстных промптов...")
    
    test_messages = [
        "Хочу заказать сайт",
        "Сколько стоит лендинг?",
        "За какое время сделаете?",
        "Покажите примеры работ",
        "Спасибо, понятно",
        "Какие технологии используете?"
    ]
    
    for message in test_messages:
        print(f"\n📝 Тестируем: '{message}'")
        
        # Создаем контекстный промпт
        prompt = get_contextual_prompt(message)
        print(f"🤖 Промпт создан:")
        print(f"   {prompt[:200]}...")
        
        # Проверяем, что промпт содержит контекст
        if "КЛИЕНТ ХОЧЕТ ЗАКАЗАТЬ САЙТ" in prompt:
            print("✅ Контекст: ЗАКАЗ САЙТА")
        elif "КЛИЕНТ СПРАШИВАЕТ О ЦЕНАХ" in prompt:
            print("✅ Контекст: ЦЕНЫ")
        elif "КЛИЕНТ СПРАШИВАЕТ О СРОКАХ" in prompt:
            print("✅ Контекст: СРОКИ")
        elif "КЛИЕНТ ПРОСИТ ПРИМЕРЫ РАБОТ" in prompt:
            print("✅ Контекст: ПРИМЕРЫ")
        elif "КЛИЕНТ БЛАГОДАРИТ" in prompt:
            print("✅ Контекст: БЛАГОДАРНОСТЬ")
        elif "КЛИЕНТ СПРАШИВАЕТ О ТЕХНОЛОГИЯХ" in prompt:
            print("✅ Контекст: ТЕХНОЛОГИИ")
        else:
            print("✅ Контекст: ОБЩИЙ ВОПРОС")

async def test_knowledge_base():
    """Тестирует базу знаний"""
    print("\n📚 Тестирование базы знаний...")
    
    knowledge = get_relevant_knowledge("сайт")
    if knowledge:
        print(f"✅ Найдены знания: {knowledge[:100]}...")
    else:
        print("❌ Знания не найдены")

async def main():
    await test_contextual_prompts()
    await test_knowledge_base()

if __name__ == "__main__":
    asyncio.run(main()) 