import asyncio
import sqlite3
import os
import logging
from datetime import datetime
from typing import List, Dict
import config
from database_functions import get_contacts, update_contact_status, add_result, get_contacts_for_broadcast
from outreach_bot import process_contact, get_current_prompt, send_to_llm
import time

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    filename='broadcast_debug.log'
)
logger = logging.getLogger(__name__)

# Глобальные переменные для статуса рассылки
broadcast_status = "stopped"
broadcast_progress = {"total": 0, "sent": 0}
broadcast_message = "Рассылка не запущена"

class BroadcastManager:
    def __init__(self):
        self.status = "stopped"
        self.progress = {"total": 0, "sent": 0}
        self.message = "Рассылка не запущена"
        self.task = None
        self.client = None
        
    async def start_broadcast(self):
        """Запустить рассылку"""
        if self.status == "running":
            return {"success": False, "message": "Рассылка уже запущена"}
        
        try:
            print("🚀 Запуск рассылки...")
            
            # Получаем контакты для рассылки (включая тестовые)
            contacts = get_contacts_for_broadcast()
            
            if not contacts:
                print("❌ Нет контактов для рассылки!")
                return False
            
            print(f"📊 Найдено {len(contacts)} контактов для рассылки:")
            for contact in contacts:
                status = contact.get('status', 'NOT_SENT')
                print(f"   - {contact.get('name', 'Без имени')} ({contact.get('phone')}) - {status}")
            
            self.status = "running"
            self.progress = {"total": len(contacts), "sent": 0}
            self.message = f"Рассылка запущена. Всего контактов для отправки: {len(contacts)}"
            
            # Запускаем рассылку в отдельной задаче
            self.task = asyncio.create_task(self._run_broadcast(contacts))
            
            return {"success": True, "message": "Рассылка запущена"}
            
        except Exception as e:
            self.status = "stopped"
            self.message = f"Ошибка запуска: {str(e)}"
            logger.error(f"Ошибка запуска рассылки: {e}")
            return {"success": False, "message": f"Ошибка запуска: {str(e)}"}
    
    async def stop_broadcast(self):
        """Остановить рассылку"""
        self.status = "stopped"
        self.message = "Рассылка остановлена"
        if self.task:
            self.task.cancel()
        return {"success": True, "message": "Рассылка остановлена"}
    
    async def pause_broadcast(self):
        """Приостановить рассылку"""
        if self.status == "running":
            self.status = "paused"
            self.message = "Рассылка приостановлена"
            return {"success": True, "message": "Рассылка приостановлена"}
        return {"success": False, "message": "Рассылка не запущена"}
    
    async def resume_broadcast(self):
        """Возобновить рассылку"""
        if self.status == "paused":
            self.status = "running"
            self.message = "Рассылка возобновлена"
            return {"success": True, "message": "Рассылка возобновлена"}
        return {"success": False, "message": "Рассылка не приостановлена"}
    
    def reset_contacts(self):
        """Сбросить статусы всех контактов"""
        try:
            conn = sqlite3.connect('outreach_bot.db')
            cursor = conn.cursor()
            cursor.execute('UPDATE contacts SET status = "NOT_SENT"')
            updated_count = cursor.rowcount
            conn.commit()
            conn.close()
            
            return {"success": True, "message": f"Сброшены статусы {updated_count} контактов"}
        except Exception as e:
            logger.error(f"Ошибка сброса статусов: {e}")
            return {"success": False, "message": f"Ошибка сброса: {str(e)}"}
    
    def get_status(self):
        """Получить текущий статус рассылки"""
        return {
            "status": self.status,
            "progress": self.progress,
            "message": self.message
        }
    
    async def _run_broadcast(self, contacts: List[Dict]):
        """Выполнить рассылку"""
        try:
            logger.info(f"Начинаем рассылку для {len(contacts)} контактов")
            
            success_count = 0
            for i, contact in enumerate(contacts, 1):
                print(f"\n📞 [{i}/{len(contacts)}] Обрабатываем контакт...")
                
                if self.status == "stopped":
                    logger.info("Рассылка остановлена пользователем")
                    break
                
                while self.status == "paused":
                    await asyncio.sleep(1)
                    if self.status == "stopped":
                        break
                
                if self.status == "stopped":
                    break
                
                try:
                    # Обрабатываем контакт
                    success = await self._process_contact(contact)
                    if success:
                        success_count += 1
                    self.progress["sent"] += 1
                    self.message = f"Отправлено {self.progress['sent']} из {self.progress['total']}"
                    
                    # Пауза между сообщениями (30 секунд)
                    if i < len(contacts):  # Не ждем после последнего сообщения
                        print(f"⏳ Ждем 30 секунд перед следующим сообщением...")
                        await asyncio.sleep(30)
                    
                except Exception as e:
                    logger.error(f"Ошибка обработки контакта {contact.get('name', 'Unknown')}: {e}")
                    continue
            
            if self.status != "stopped":
                self.status = "completed"
                self.message = f"Рассылка завершена. Успешно отправлено: {success_count}/{len(contacts)}"
                logger.info("Рассылка завершена успешно")
            
            return success_count > 0
            
        except Exception as e:
            self.status = "error"
            self.message = f"Ошибка рассылки: {str(e)}"
            logger.error(f"Критическая ошибка рассылки: {e}")
            return False
    
    async def _process_contact(self, contact: Dict):
        """Обработать один контакт"""
        try:
            phone = contact['phone']
            name = contact.get('name', '')
            
            # Получаем актуальный промпт
            current_prompt = get_current_prompt()
            
            # Генерируем сообщение
            message = await send_to_llm(current_prompt, f"Имя: {name}")
            
            if message:
                # Здесь должна быть отправка через Telegram клиент
                # Пока что просто обновляем статус
                update_contact_status(contact['id'], 'SENT')
                add_result(phone, 'SENT', message, '', '')
                
                logger.info(f"✅ Отправлено {name} ({phone}): {message[:50]}...")
                return True
            else:
                logger.error(f"❌ Не удалось сгенерировать сообщение для {name} ({phone})")
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка обработки контакта {contact.get('name', 'Unknown')} ({contact['phone']}): {e}")
            return False

# Глобальный экземпляр менеджера
broadcast_manager = BroadcastManager()

# Функции для интеграции с панелью
async def start_broadcast():
    """Запустить рассылку (для панели)"""
    return await broadcast_manager.start_broadcast()

async def stop_broadcast():
    """Остановить рассылку (для панели)"""
    return await broadcast_manager.stop_broadcast()

async def pause_broadcast():
    """Приостановить рассылку (для панели)"""
    return await broadcast_manager.pause_broadcast()

async def resume_broadcast():
    """Возобновить рассылку (для панели)"""
    return await broadcast_manager.resume_broadcast()

def reset_contacts():
    """Сбросить статусы контактов (для панели)"""
    return broadcast_manager.reset_contacts()

def get_broadcast_status():
    """Получить статус рассылки (для панели)"""
    return broadcast_manager.get_status()

if __name__ == "__main__":
    asyncio.run(start_broadcast()) 