from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import pandas as pd
import os
import json
import csv
from datetime import datetime
import aiofiles
from pathlib import Path
from celery.result import AsyncResult
from redis import Redis
import sys
import sqlite3
import subprocess

# Добавляем родительскую директорию в путь для импорта
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from celery_worker import send_broadcast
from database import (
    get_contacts, get_contact_by_id, create_contact, update_contact, delete_contact,
    get_dialog_history, get_statistics, export_contacts_to_csv, import_contacts_from_csv,
    get_prompts, get_active_prompt, create_prompt, update_prompt, delete_prompt, set_active_prompt,
    get_knowledge_base, import_knowledge_from_files, update_knowledge_item, delete_knowledge_item,
    get_knowledge_item_by_id, DB_PATH
)
from pydantic import BaseModel
from typing import List, Optional

app = FastAPI(title="Outreach Bot Panel")

# Подключаем статические файлы и шаблоны
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Модели для контактов
class ContactCreate(BaseModel):
    name: Optional[str] = None
    phone: str
    email: Optional[str] = None
    company: Optional[str] = None
    notes: Optional[str] = None

class ContactUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    company: Optional[str] = None
    notes: Optional[str] = None

class Contact(BaseModel):
    id: int
    name: Optional[str] = None
    phone: str
    email: Optional[str] = None
    company: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None

# Модели для промптов
class PromptUpdate(BaseModel):
    content: str

class Prompt(BaseModel):
    name: str
    content: str
    description: Optional[str] = None

# Пути к файлам
KNOWLEDGE_BASE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'knowledge_base')
PROMPTS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'prompts.json')

redis_client = Redis(host='localhost', port=6379, db=0)
BROADCAST_TASK_KEY = 'broadcast_task_id'
BROADCAST_PAUSE_KEY = 'broadcast_paused'
BROADCAST_STOP_KEY = 'broadcast_stopped'

# Глобальные переменные для статуса рассылки
broadcast_status = "stopped"
broadcast_progress = {"total": 0, "sent": 0}
broadcast_message = "Рассылка не запущена"
broadcast_process = None  # Процесс бота

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Главная страница с дашбордом"""
    try:
        # Получаем статистику из базы данных
        stats = get_statistics()
        
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "total_sent": stats['total_sent'],
            "total_replies": stats['total_replies'],
            "total_refused": stats['total_refused'],
            "total_interested": stats['total_interested'],
            "total_contacts": stats['total_contacts'],
            "daily_stats": stats['daily_stats']
        })
    except Exception as e:
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "error": str(e),
            "total_sent": 0,
            "total_replies": 0,
            "total_refused": 0,
            "total_interested": 0,
            "total_contacts": 0,
            "daily_stats": {}
        })

@app.get("/contacts", response_class=HTMLResponse)
async def contacts_page(request: Request):
    """Страница с таблицей контактов"""
    try:
        # Получаем контакты из базы данных
        contacts = get_contacts()
        
        return templates.TemplateResponse("contacts.html", {
            "request": request,
            "contacts": contacts
        })
    except Exception as e:
        return templates.TemplateResponse("contacts.html", {
            "request": request,
            "error": str(e),
            "contacts": []
        })

@app.get("/dialogs", response_class=HTMLResponse)
def dialogs_list(request: Request):
    # Получаем все контакты, у которых есть сообщения
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT c.phone, c.name, c.telegram_id, MAX(r.timestamp), r.text, r.status
        FROM contacts c
        LEFT JOIN results r ON c.phone = r.user_id OR c.telegram_id = r.user_id
        GROUP BY c.phone
        HAVING MAX(r.timestamp) IS NOT NULL
        ORDER BY MAX(r.timestamp) DESC
    ''')
    dialogs = []
    for row in cursor.fetchall():
        phone, name, telegram_id, last_time, last_text, last_status = row
        dialogs.append({
            'phone': phone,
            'name': name or phone,
            'telegram_id': telegram_id,
            'last_time': last_time,
            'last_text': last_text,
            'last_status': last_status
        })
    conn.close()
    return templates.TemplateResponse("dialogs.html", {"request": request, "dialogs": dialogs})

@app.get("/dialogs/{user_id}", response_class=HTMLResponse)
def dialog_page(request: Request, user_id: str):
    try:
        dialog_history = get_dialog_history(user_id)
        return templates.TemplateResponse("dialog.html", {
            "request": request,
            "user_id": user_id,
            "dialog_history": dialog_history
        })
    except Exception as e:
        return templates.TemplateResponse("dialog.html", {
            "request": request,
            "user_id": user_id,
            "error": str(e),
            "dialog_history": []
        })

@app.get("/prompts", response_class=HTMLResponse)
async def prompts_page(request: Request):
    """Страница управления промптами"""
    try:
        # Загружаем текущие промпты
        if os.path.exists(PROMPTS_FILE):
            with open(PROMPTS_FILE, 'r', encoding='utf-8') as f:
                prompts_data = json.load(f)
                current_prompt = prompts_data.get("first_prompt", "")
                dialog_prompt = prompts_data.get("dialog_prompt", "")
        else:
            current_prompt = ""
            dialog_prompt = ""
        
        return templates.TemplateResponse("prompts.html", {
            "request": request,
            "current_prompt": current_prompt,
            "dialog_prompt": dialog_prompt
        })
    except Exception as e:
        return templates.TemplateResponse("prompts.html", {
            "request": request,
            "error": str(e),
            "current_prompt": "",
            "dialog_prompt": ""
        })

@app.post("/prompts/update")
async def update_prompts(request: Request, first_prompt: str = Form(...), dialog_prompt: str = Form(...)):
    """Обновить промпты"""
    try:
        prompts_data = {
            "first_prompt": first_prompt,
            "dialog_prompt": dialog_prompt
        }
        
        with open(PROMPTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(prompts_data, f, ensure_ascii=False, indent=2)
        
        return RedirectResponse(url="/prompts", status_code=303)
    except Exception as e:
        return templates.TemplateResponse("prompts.html", {
            "request": request,
            "error": str(e),
            "current_prompt": first_prompt,
            "dialog_prompt": dialog_prompt
        })

@app.get("/knowledge", response_class=HTMLResponse)
async def knowledge_page(request: Request):
    """Страница базы знаний"""
    try:
        knowledge_files = []
        if os.path.exists(KNOWLEDGE_BASE_DIR):
            for filename in os.listdir(KNOWLEDGE_BASE_DIR):
                if filename.endswith(('.txt', '.md')):
                    file_path = os.path.join(KNOWLEDGE_BASE_DIR, filename)
                    file_size = os.path.getsize(file_path)
                    knowledge_files.append({
                        'name': filename,
                        'size': file_size,
                        'path': file_path
                    })
        
        return templates.TemplateResponse("knowledge.html", {
            "request": request,
            "knowledge_files": knowledge_files
        })
    except Exception as e:
        return templates.TemplateResponse("knowledge.html", {
            "request": request,
            "error": str(e),
            "knowledge_files": []
        })

@app.post("/knowledge/upload")
async def upload_knowledge_file(file: UploadFile = File(...)):
    """Загрузить файл в базу знаний"""
    try:
        if not os.path.exists(KNOWLEDGE_BASE_DIR):
            os.makedirs(KNOWLEDGE_BASE_DIR)
        
        file_path = os.path.join(KNOWLEDGE_BASE_DIR, file.filename)
        with open(file_path, 'wb') as f:
            content = await file.read()
            f.write(content)
        
        return RedirectResponse(url="/knowledge", status_code=303)
    except Exception as e:
        return templates.TemplateResponse("knowledge.html", {
            "request": Request,
            "error": str(e),
            "knowledge_files": []
        })

@app.get("/knowledge/view/{filename}")
async def view_knowledge_file(request: Request, filename: str):
    """Просмотр файла базы знаний"""
    try:
        file_path = os.path.join(KNOWLEDGE_BASE_DIR, filename)
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            return templates.TemplateResponse("knowledge_view.html", {
                "request": request,
                "filename": filename,
                "content": content
            })
        else:
            return templates.TemplateResponse("knowledge_view.html", {
                "request": request,
                "filename": filename,
                "error": "Файл не найден",
                "content": ""
            })
    except Exception as e:
        return templates.TemplateResponse("knowledge_view.html", {
            "request": request,
            "filename": filename,
            "error": str(e),
            "content": ""
        })

# Простые функции для управления broadcast
@app.get("/api/broadcast/status")
def get_broadcast_status():
    """Получить статус рассылки"""
    global broadcast_status, broadcast_progress, broadcast_message, broadcast_process
    
    # Проверяем, работает ли процесс бота
    if broadcast_process:
        if broadcast_process.poll() is not None:
            # Процесс завершился
            broadcast_status = "stopped"
            broadcast_message = "Рассылка завершена"
            broadcast_process = None
    
    # Получаем реальный прогресс из базы данных
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Общее количество контактов
        cursor.execute('SELECT COUNT(*) FROM contacts WHERE status = "NOT_SENT"')
        remaining = cursor.fetchone()[0]
        
        # Количество отправленных
        cursor.execute('SELECT COUNT(*) FROM contacts WHERE status = "SENT"')
        sent = cursor.fetchone()[0]
        
        total = remaining + sent
        
        if total > 0:
            broadcast_progress["total"] = total
            broadcast_progress["sent"] = sent
            
            if broadcast_status == "running":
                broadcast_message = f"Рассылка выполняется. Отправлено {sent} из {total}"
        
        conn.close()
    except Exception as e:
        pass  # Игнорируем ошибки при получении статуса
    
    return {
        "status": broadcast_status,
        "progress": broadcast_progress,
        "message": broadcast_message
    }

@app.post("/api/broadcast/start")
def start_broadcast():
    """Запустить рассылку - просто запускаем outreach_bot.py"""
    global broadcast_status, broadcast_message, broadcast_process
    try:
        # Проверяем, не запущен ли уже процесс
        if broadcast_process and broadcast_process.poll() is None:
            return {"success": False, "message": "Рассылка уже запущена"}
        
        # Получаем количество контактов для рассылки
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM contacts WHERE status = "NOT_SENT"')
        total_contacts = cursor.fetchone()[0]
        conn.close()
        
        if total_contacts == 0:
            return {"success": False, "message": "Нет контактов для рассылки (все уже отправлены)"}
        
        broadcast_status = "running"
        broadcast_progress["total"] = total_contacts
        broadcast_progress["sent"] = 0
        broadcast_message = f"Рассылка запущена. Всего контактов для отправки: {total_contacts}"
        
        # Запускаем основной бот в отдельном процессе
        try:
            # Путь к основному боту
            bot_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'outreach_bot.py')
            
            # Запускаем бот в фоновом режиме
            broadcast_process = subprocess.Popen([sys.executable, bot_path], 
                           stdout=subprocess.PIPE, 
                           stderr=subprocess.PIPE,
                           cwd=os.path.dirname(bot_path))
            
            broadcast_message += " (бот запущен)"
            
        except Exception as e:
            broadcast_message += f" (ошибка запуска бота: {str(e)})"
            broadcast_status = "stopped"
        
        return {"success": True, "message": "Рассылка запущена"}
    except Exception as e:
        return {"success": False, "message": f"Ошибка запуска: {str(e)}"}

@app.post("/api/broadcast/stop")
def stop_broadcast():
    """Остановить рассылку - просто убиваем процесс"""
    global broadcast_status, broadcast_message, broadcast_process
    broadcast_status = "stopped"
    broadcast_message = "Рассылка остановлена"
    
    # Останавливаем процесс бота
    if broadcast_process:
        try:
            broadcast_process.terminate()
            broadcast_process = None
            broadcast_message += " (бот остановлен)"
        except Exception as e:
            broadcast_message += f" (ошибка остановки бота: {str(e)})"
    
    return {"success": True, "message": "Рассылка остановлена"}

@app.post("/api/broadcast/reset")
def reset_contacts():
    """Сбросить статусы всех контактов для повторной рассылки"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('UPDATE contacts SET status = "NOT_SENT"')
        updated_count = cursor.rowcount
        conn.commit()
        conn.close()
        
        return {"success": True, "message": f"Сброшены статусы {updated_count} контактов"}
    except Exception as e:
        return {"success": False, "message": f"Ошибка сброса: {str(e)}"}

# API эндпоинты для контактов
@app.get("/api/contacts", response_model=List[Contact])
async def get_contacts_api():
    """API для получения всех контактов"""
    try:
        contacts = get_contacts()
        return [Contact(**contact) for contact in contacts]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/contacts", response_model=Contact)
async def create_contact_api(contact: ContactCreate):
    """API для создания нового контакта"""
    try:
        contact_data = contact.dict()
        new_contact = create_contact(contact_data)
        return Contact(**new_contact)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/contacts/{contact_id}", response_model=Contact)
async def get_contact_api(contact_id: int):
    """API для получения контакта по ID"""
    try:
        contact = get_contact_by_id(contact_id)
        if not contact:
            raise HTTPException(status_code=404, detail="Контакт не найден")
        return Contact(**contact)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/contacts/{contact_id}", response_model=Contact)
async def update_contact_api(contact_id: int, contact_update: ContactUpdate):
    """API для обновления контакта"""
    try:
        contact_data = contact_update.dict(exclude_unset=True)
        updated_contact = update_contact(contact_id, contact_data)
        if not updated_contact:
            raise HTTPException(status_code=404, detail="Контакт не найден")
        return Contact(**updated_contact)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/contacts/{contact_id}")
async def delete_contact_api(contact_id: int):
    """API для удаления контакта"""
    try:
        deleted = delete_contact(contact_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Контакт не найден")
        return {"message": "Контакт удален"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/contacts/import")
async def import_contacts_api(file: UploadFile = File(...)):
    """API для импорта контактов из CSV"""
    try:
        # Сохраняем временный файл
        temp_file_path = f"temp_import_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        async with aiofiles.open(temp_file_path, 'wb') as f:
            content = await file.read()
            await f.write(content)
        
        # Импортируем данные
        imported_count = import_contacts_from_csv(temp_file_path)
        
        # Удаляем временный файл
        os.remove(temp_file_path)
        
        return {"message": f"Импортировано {imported_count} контактов"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/contacts/export")
async def export_contacts_api():
    """API для экспорта контактов в CSV"""
    try:
        export_path = export_contacts_to_csv()
        
        # Читаем файл и возвращаем как ответ
        with open(export_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Удаляем временный файл
        os.remove(export_path)
        
        return Response(
            content=content,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=contacts_export.csv"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# API эндпоинты для промптов
@app.get("/api/prompts")
async def get_prompts_api():
    """Получить все промпты"""
    try:
        prompts = get_prompts()
        return {"success": True, "prompts": prompts}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/api/prompts/active")
async def get_active_prompt_api():
    """Получить активный промпт"""
    try:
        prompt = get_active_prompt()
        return {"success": True, "prompt": prompt}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/api/prompts")
async def create_prompt_api(prompt: dict):
    """Создать новый промпт"""
    try:
        new_prompt = create_prompt(prompt)
        return {"success": True, "prompt": new_prompt}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.put("/api/prompts/{prompt_id}")
async def update_prompt_api(prompt_id: int, prompt: dict):
    """Обновить промпт"""
    try:
        updated_prompt = update_prompt(prompt_id, prompt)
        if updated_prompt:
            return {"success": True, "prompt": updated_prompt}
        else:
            return {"success": False, "error": "Промпт не найден"}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.delete("/api/prompts/{prompt_id}")
async def delete_prompt_api(prompt_id: int):
    """Удалить промпт"""
    try:
        success = delete_prompt(prompt_id)
        return {"success": success}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/api/prompts/{prompt_id}/activate")
async def activate_prompt_api(prompt_id: int):
    """Активировать промпт"""
    try:
        success = set_active_prompt(prompt_id)
        return {"success": success}
    except Exception as e:
        return {"success": False, "error": str(e)}

# API для базы знаний
@app.get("/api/knowledge")
async def get_knowledge_base_api():
    """Получить всю базу знаний"""
    try:
        knowledge = get_knowledge_base()
        return {"success": True, "knowledge": knowledge}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/api/knowledge/{knowledge_id}")
async def get_knowledge_item_api(knowledge_id: int):
    """Получить элемент базы знаний по ID"""
    try:
        knowledge = get_knowledge_item_by_id(knowledge_id)
        if knowledge:
            return {"success": True, "knowledge": knowledge}
        else:
            return {"success": False, "error": "Элемент не найден"}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/api/knowledge/import")
async def import_knowledge_api():
    """Импорт базы знаний из файлов"""
    try:
        knowledge_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'knowledge_base')
        imported_count = import_knowledge_from_files(knowledge_dir)
        return {"success": True, "imported_count": imported_count}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.put("/api/knowledge/{knowledge_id}")
async def update_knowledge_item_api(knowledge_id: int, knowledge: dict):
    """Обновить элемент базы знаний"""
    try:
        updated_knowledge = update_knowledge_item(knowledge_id, knowledge)
        if updated_knowledge:
            return {"success": True, "knowledge": updated_knowledge}
        else:
            return {"success": False, "error": "Элемент не найден"}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.delete("/api/knowledge/{knowledge_id}")
async def delete_knowledge_item_api(knowledge_id: int):
    """Удалить элемент базы знаний"""
    try:
        success = delete_knowledge_item(knowledge_id)
        return {"success": success}
    except Exception as e:
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001) 