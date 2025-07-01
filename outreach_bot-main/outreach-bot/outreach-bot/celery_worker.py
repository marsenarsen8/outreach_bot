from celery import Celery
import time
from redis import Redis

celery_app = Celery(
    'outreach',
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/0'
)

redis_client = Redis(host='localhost', port=6379, db=0)
BROADCAST_PAUSE_KEY = 'broadcast_paused'
BROADCAST_STOP_KEY = 'broadcast_stopped'

@celery_app.task(bind=True)
def send_broadcast(self):
    for i in range(10):
        if int(redis_client.get(BROADCAST_STOP_KEY) or 0):
            print('Рассылка остановлена!')
            break
        while int(redis_client.get(BROADCAST_PAUSE_KEY) or 0):
            print('Пауза...')
            time.sleep(1)
        print(f"Отправка сообщения {i+1}/10")
        time.sleep(2)
    return 'Рассылка завершена' 