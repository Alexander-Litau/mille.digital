"""
Планировщик отложенных сообщений воронки.
Читает очередь из Firebase и отправляет сообщения по расписанию.
"""

import time
from apscheduler.schedulers.background import BackgroundScheduler
import api
import funnel


_scheduler = None


def process_funnel_queue():
    """Проверить очередь и отправить все сообщения, время которых наступило."""
    try:
        queue = api.firebase_get("funnel/queue")
        if not queue:
            return

        now = int(time.time() * 1000)

        for queue_id, item in queue.items():
            if not isinstance(item, dict):
                continue

            send_at = item.get("send_at", 0)
            if send_at > now:
                continue

            # Время наступило — отправляем
            user_id = item.get("user_id")
            chat_id = item.get("chat_id")
            step = item.get("step")

            if not user_id or not chat_id or not step:
                # Невалидная запись — удаляем
                api.firebase_delete(f"funnel/queue/{queue_id}")
                continue

            # Собираем контекст
            context = {
                "name": item.get("name", ""),
                "niche": item.get("niche", ""),
                "survey_answer": item.get("survey_answer"),
            }
            if item.get("_fallback"):
                context["_fallback"] = True

            try:
                funnel.send_step(user_id, chat_id, step, context)
            except Exception as e:
                print(f"[scheduler] Ошибка отправки {step} для {user_id}: {e}")

            # Удаляем обработанную запись
            api.firebase_delete(f"funnel/queue/{queue_id}")

    except Exception as e:
        print(f"[scheduler] Ошибка обработки очереди: {e}")


def start_scheduler():
    """Запустить фоновый планировщик."""
    global _scheduler
    _scheduler = BackgroundScheduler()
    # Проверяем очередь каждые 30 секунд
    _scheduler.add_job(process_funnel_queue, "interval", seconds=30)
    _scheduler.start()
    print("[scheduler] планировщик запущен (очередь воронки каждые 30с)")


def stop_scheduler():
    """Остановить планировщик."""
    global _scheduler
    if _scheduler:
        _scheduler.shutdown()
        print("[scheduler] планировщик остановлен")
