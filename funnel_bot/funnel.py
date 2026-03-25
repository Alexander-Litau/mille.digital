"""
Логика воронки mil.le digital.
Стейт-машина, тексты всех сообщений, управление шагами.
"""

import time
import api
from config import (
    ADMIN_PROFILE_URL,
    ADMIN_USER_ID,
    DOC_PATHS,
    DOC_NAMES,
    FUNNEL_DELAYS,
)


# ─── Тексты сообщений воронки ───

WELCOME_TEXT = (
    "Привет! Рады видеть вас в боте mil.le digital — "
    "агентства комплексного digital-присутствия.\n\n"
    "Мы подготовили для вас 3 документа, которые дадут готовую систему "
    "продвижения в мессенджере MAX:\n\n"
    "1. Обзор рынка MAX с реальными цифрами + 5 ошибок, которые сливают бюджет\n"
    "2. Пошаговый план запуска канала из 14 шагов\n"
    "3. Шаблон контент-стратегии на 30 дней\n\n"
    "Первый документ — уже через минуту. Но сначала давайте познакомимся.\n\n"
    "Как вас зовут?"
)

ASK_NICHE_TEXT = (
    "{name}, приятно познакомиться!\n\n"
    "Чтобы наши материалы были максимально полезны — "
    "расскажите в двух словах, чем занимается ваш бизнес?"
)

DOC1_INTRO_TEXT = (
    "Отлично, {name}! Отправляю первый документ.\n\n"
    "Это обзор рынка MAX в 2026 году — реальные цифры, аудитория, "
    "возможности для бизнеса. Плюс бонус: 5 ошибок, из-за которых "
    "компании сливают бюджет на новых площадках.\n\n"
    "Изучите — завтра пришлю пошаговый план действий."
)

EXPERT_INSIGHT_TEXT = (
    "{name}, кстати, вот один важный момент, который мы видим на практике.\n\n"
    "Большинство бизнесов заходит в MAX и начинает просто постить контент в канал. "
    "Но аудитория здесь ведёт себя иначе — в MAX значительно выше вовлечённость "
    "в личные сообщения и ботов.\n\n"
    "Именно поэтому воронка через чат-бота (как эта, в которой вы сейчас находитесь) "
    "работает в 2–3 раза эффективнее, чем просто контент в канале.\n\n"
    "Канал нужен для доверия и прогрева. А бот — для конверсии в заявку."
)

SURVEY_TEXT = (
    "Доброе утро, {name}!\n\n"
    "Вы уже изучили первый документ?\n\n"
    "Подскажите, что для вас сейчас актуальнее — "
    "так мне будет проще давать полезные рекомендации:"
)

SURVEY_BUTTONS = [
    [{"type": "callback", "text": "Запустить канал с нуля", "payload": "survey_launch"}],
    [{"type": "callback", "text": "Уже есть канал, хочу больше заявок", "payload": "survey_leads"}],
    [{"type": "callback", "text": "Интересуют боты и автоматизация", "payload": "survey_bots"}],
]

SURVEY_ANSWERS = {
    "survey_launch": "launch_from_scratch",
    "survey_leads": "more_leads",
    "survey_bots": "bots_automation",
}

DOC2_INTRO_TEXT = {
    "launch_from_scratch": (
        "{name}, раз вы только начинаете — этот документ как раз для вас.\n\n"
        "14 конкретных шагов: от определения ЦА до запуска рекламы. "
        "Пошаговая «дорожная карта», которую можно внедрять сразу.\n\n"
        "В конце — чек-лист для самопроверки."
    ),
    "more_leads": (
        "{name}, раз канал уже есть — обратите внимание на фазы III и IV в этом документе.\n\n"
        "Там про воронку и трафик — именно то, что превращает подписчиков в заявки. "
        "Но рекомендую пройти и по первым шагам — возможно, найдёте точки роста.\n\n"
        "В конце — чек-лист для самопроверки."
    ),
    "bots_automation": (
        "{name}, шаги 7–9 в этом документе — как раз про ботов и воронки.\n\n"
        "Но начните с начала — без правильного фундамента (ЦА, позиционирование, контент) "
        "даже лучший бот не даст результата.\n\n"
        "В конце — чек-лист для самопроверки."
    ),
    None: (
        "{name}, отправляю второй документ — пошаговый план.\n\n"
        "14 конкретных шагов от нуля до первых заявок. "
        "Каждый шаг — конкретное действие, которое можно выполнить сегодня.\n\n"
        "В конце — чек-лист для самопроверки."
    ),
}

MINI_CASE_TEXT = (
    "{name}, хочу показать вам кое-что интересное.\n\n"
    "Вы сейчас находитесь внутри воронки, которую мы в mil.le digital "
    "построили для себя. Вот как она работает:\n\n"
    "1. Реклама в Яндекс Директ → мини-лендинг\n"
    "2. Мини-лендинг → подписка на канал в MAX\n"
    "3. Закреп-пост в канале → переход в этот бот\n"
    "4. Бот собирает данные + отправляет 3 документа\n"
    "5. После документов → предложение бесплатного аудита\n\n"
    "Каждый этап решает одну задачу. Ничего не дублируется. "
    "Прогрев происходит автоматически — без менеджера.\n\n"
    "Такую же систему мы делаем для наших клиентов."
)

TIP_TEXT = (
    "Доброе утро, {name}!\n\n"
    "Совет дня от mil.le digital:\n\n"
    "Первые 5 постов в канале MAX должны быть полезными, без продаж. "
    "Алгоритм продвигает каналы, где подписчики читают до конца и реагируют.\n\n"
    "Начните с ответов на 5 самых частых вопросов ваших клиентов. "
    "Это работает в любой нише — от фитнеса до IT.\n\n"
    "Через пару часов пришлю третий документ — "
    "готовый шаблон контент-стратегии на 30 дней. Останется только подставить свою нишу."
)

DOC3_INTRO_TEXT = (
    "{name}, третий и последний документ готов!\n\n"
    "Это шаблон контент-стратегии на 30 дней — с рубриками, форматами "
    "и темами-подсказками на каждый день. Плюс бонус: разбор воронки, "
    "внутри которой вы находитесь прямо сейчас.\n\n"
    "Подставьте свою нишу, сохранив структуру — и у вас будет готовый "
    "контент-план для канала в MAX."
)

OFFER_TEXT = (
    "{name}, вы получили все 3 документа:\n\n"
    "✓ Обзор рынка MAX + 5 ошибок\n"
    "✓ Пошаговый план из 14 шагов\n"
    "✓ Шаблон контент-стратегии на 30 дней\n\n"
    "Этого достаточно, чтобы запустить канал самостоятельно.\n\n"
    "Но если хотите получить результат быстрее и не тратить время "
    "на ошибки — мы готовы сделать всю работу за вас.\n\n"
    "Напишите мне лично — проведу бесплатный аудит вашего канала "
    "и составлю персональный план продвижения."
)

OFFER_BUTTON = [
    [{"type": "link", "text": "Написать Александру Литау", "url": ADMIN_PROFILE_URL}]
]

FOLLOWUP_TEXT = (
    "Доброе утро, {name}!\n\n"
    "Вы изучили все 3 документа. Если есть вопросы по запуску канала в MAX — "
    "напишите, разберём вашу ситуацию бесплатно.\n\n"
    "Мы берём не более 5 проектов в месяц, "
    "поэтому если тема актуальна — лучше написать сейчас."
)

FOLLOWUP_BUTTON = [
    [{"type": "link", "text": "Написать Александру Литау", "url": ADMIN_PROFILE_URL}]
]

AUDIT_RESPONSE_TEXT = (
    "{name}, заявка на аудит принята!\n\n"
    "Александр свяжется с вами в ближайшее время.\n\n"
    "А пока — если ещё не изучили все документы, рекомендуем посмотреть. "
    "Там много полезного, что пригодится при разборе вашей ситуации."
)


# ─── Порядок шагов воронки ───

FUNNEL_STEPS = [
    "welcome",
    "ask_niche",
    "doc1",
    "expert_insight",
    "survey",
    "doc2",
    "mini_case",
    "tip",
    "doc3",
    "offer",
    "followup",
]


def get_next_step(current_step):
    """Получить следующий шаг после текущего."""
    try:
        idx = FUNNEL_STEPS.index(current_step)
        if idx + 1 < len(FUNNEL_STEPS):
            return FUNNEL_STEPS[idx + 1]
    except ValueError:
        pass
    return None


# ─── Кеш токенов файлов ───

_file_tokens = {}


def ensure_file_tokens():
    """Загрузить PDF в MAX и закешировать токены. Делается один раз."""
    global _file_tokens

    # Проверяем кеш в Firebase
    cached = api.firebase_get("funnel/config/file_tokens")
    if cached and isinstance(cached, dict):
        for doc_key in ("doc1", "doc2", "doc3"):
            if doc_key in cached and cached[doc_key]:
                _file_tokens[doc_key] = cached[doc_key]

    # Загружаем недостающие
    for doc_key, path in DOC_PATHS.items():
        if doc_key in _file_tokens:
            print(f"[tokens] {doc_key} — из кеша: {_file_tokens[doc_key][:20]}...")
            continue
        try:
            print(f"[tokens] загружаю {doc_key} из {path}...")
            token = api.upload_file(path)
            _file_tokens[doc_key] = token
            api.firebase_set(f"funnel/config/file_tokens/{doc_key}", token)
            print(f"[tokens] {doc_key} загружен: {token[:20]}...")
        except Exception as e:
            print(f"[tokens] ОШИБКА загрузки {doc_key}: {e}")


def get_file_token(doc_key):
    """Получить token файла для отправки."""
    return _file_tokens.get(doc_key)


# ─── Обработка входящих сообщений ───

def handle_bot_started(user_id, chat_id):
    """Пользователь нажал Старт."""
    now = int(time.time() * 1000)

    # Проверяем, есть ли уже пользователь
    existing = api.firebase_get(f"funnel/users/{user_id}")
    if existing and existing.get("state") in ("funnel_active", "funnel_complete"):
        # Уже в воронке — не перезапускаем
        api.send_message(
            chat_id,
            "С возвращением! Если у вас есть вопросы — напишите, "
            "или используйте слово «Аудит» для заявки на бесплатный разбор."
        )
        return

    # Новый пользователь — создаём запись
    user_data = {
        "chat_id": chat_id,
        "state": "waiting_name",
        "current_step": "welcome",
        "created_at": now,
        "steps": {
            "welcome": {"sent_at": now},
        },
    }
    api.firebase_set(f"funnel/users/{user_id}", user_data)

    # Отправляем приветствие
    api.send_message(chat_id, WELCOME_TEXT)
    print(f"[funnel] Новый пользователь {user_id}, отправлено приветствие")


def handle_message(user_id, chat_id, text):
    """Обработать текстовое сообщение от пользователя в воронке."""
    user = api.firebase_get(f"funnel/users/{user_id}")
    if not user:
        return False  # Пользователь не в воронке

    state = user.get("state", "")

    # Проверка на слово "Аудит" — в любом состоянии
    if text.lower().strip() in ("аудит", "audit"):
        handle_audit_request(user_id, chat_id, user)
        return True

    # Ожидаем имя
    if state == "waiting_name":
        name = text.strip()
        if len(name) > 50:
            name = name[:50]
        now = int(time.time() * 1000)

        api.firebase_update(f"funnel/users/{user_id}", {
            "name": name,
            "state": "waiting_niche",
            "current_step": "ask_niche",
        })
        api.firebase_set(
            f"funnel/users/{user_id}/steps/ask_niche", {"sent_at": now}
        )

        api.send_message(chat_id, ASK_NICHE_TEXT.format(name=name))
        print(f"[funnel] {user_id} ввёл имя: {name}")
        return True

    # Ожидаем нишу
    if state == "waiting_niche":
        niche = text.strip()
        if len(niche) > 100:
            niche = niche[:100]
        name = user.get("name", "")
        now = int(time.time() * 1000)

        api.firebase_update(f"funnel/users/{user_id}", {
            "niche": niche,
            "state": "funnel_active",
            "current_step": "doc1",
        })
        api.firebase_set(
            f"funnel/users/{user_id}/steps/doc1", {"sent_at": now}
        )

        # Отправляем Документ 1
        send_doc(chat_id, "doc1", DOC1_INTRO_TEXT.format(name=name))

        # Ставим следующий шаг в очередь: expert_insight через 3 часа
        schedule_step(user_id, chat_id, "expert_insight", FUNNEL_DELAYS["expert_insight"], {
            "name": name,
            "niche": niche,
        })

        print(f"[funnel] {user_id} ввёл нишу: {niche}, отправлен doc1")
        return True

    # Пользователь в активной воронке — любое сообщение
    if state == "funnel_active":
        # Проверяем, не аудит ли (уже проверили выше, но на всякий)
        return True

    return False


def handle_callback(user_id, chat_id, payload, callback_id):
    """Обработать нажатие кнопки в воронке."""
    user = api.firebase_get(f"funnel/users/{user_id}")
    if not user:
        return False

    api.answer_callback(callback_id)

    # Ответ на опрос
    if payload in SURVEY_ANSWERS:
        answer = SURVEY_ANSWERS[payload]
        now = int(time.time() * 1000)

        api.firebase_update(f"funnel/users/{user_id}", {
            "survey_answer": answer,
        })
        api.firebase_update(f"funnel/users/{user_id}/steps/survey", {
            "answered_at": now,
            "answer": answer,
        })

        # Благодарим за ответ
        name = user.get("name", "")
        api.send_message(chat_id, f"Спасибо, {name}! Учту это.")

        # Ставим doc2 в очередь через 2 часа (вместо 3, т.к. ответил)
        schedule_step(user_id, chat_id, "doc2", FUNNEL_DELAYS["doc2"], {
            "name": name,
            "niche": user.get("niche", ""),
            "survey_answer": answer,
        })

        print(f"[funnel] {user_id} ответил на опрос: {answer}")
        return True

    return False


# ─── Отправка шагов воронки ───

def send_step(user_id, chat_id, step, context):
    """Отправить конкретный шаг воронки."""
    name = context.get("name", "")
    niche = context.get("niche", "")
    survey_answer = context.get("survey_answer")
    now = int(time.time() * 1000)

    if step == "expert_insight":
        api.send_message(chat_id, EXPERT_INSIGHT_TEXT.format(name=name))
        next_delay = FUNNEL_DELAYS["survey"]

    elif step == "survey":
        api.send_message_with_keyboard(
            chat_id, SURVEY_TEXT.format(name=name), SURVEY_BUTTONS
        )
        # doc2 ставится при ответе на опрос (handle_callback)
        # Но если не ответит — ставим doc2 через 3 часа
        schedule_step(user_id, chat_id, "doc2", FUNNEL_DELAYS["doc2_no_answer"], {
            "name": name, "niche": niche, "survey_answer": None,
            "_fallback": True,  # Маркер: отправлять только если survey не отвечен
        })
        # Обновляем данные и выходим (не ставим next_step стандартно)
        api.firebase_update(f"funnel/users/{user_id}", {"current_step": step})
        api.firebase_set(f"funnel/users/{user_id}/steps/{step}", {"sent_at": now})
        print(f"[funnel] {user_id} ← {step}")
        return

    elif step == "doc2":
        # Проверяем, не отправлен ли уже doc2 (защита от дубля fallback + ответ)
        existing_step = api.firebase_get(f"funnel/users/{user_id}/steps/doc2")
        if existing_step and existing_step.get("sent_at"):
            print(f"[funnel] {user_id} doc2 уже отправлен, пропускаем")
            return

        # Если это fallback и пользователь всё-таки ответил на опрос — пропускаем
        if context.get("_fallback"):
            user_data = api.firebase_get(f"funnel/users/{user_id}")
            if user_data and user_data.get("survey_answer"):
                print(f"[funnel] {user_id} doc2 fallback пропущен — опрос отвечен")
                return
            survey_answer = None

        intro = DOC2_INTRO_TEXT.get(survey_answer, DOC2_INTRO_TEXT[None])
        send_doc(chat_id, "doc2", intro.format(name=name))
        next_delay = FUNNEL_DELAYS["mini_case"]

    elif step == "mini_case":
        api.send_message(chat_id, MINI_CASE_TEXT.format(name=name))
        next_delay = FUNNEL_DELAYS["tip"]

    elif step == "tip":
        api.send_message(chat_id, TIP_TEXT.format(name=name))
        next_delay = FUNNEL_DELAYS["doc3"]

    elif step == "doc3":
        send_doc(chat_id, "doc3", DOC3_INTRO_TEXT.format(name=name))
        next_delay = FUNNEL_DELAYS["offer"]

    elif step == "offer":
        api.send_message_with_keyboard(
            chat_id, OFFER_TEXT.format(name=name), OFFER_BUTTON
        )
        next_delay = FUNNEL_DELAYS["followup"]

    elif step == "followup":
        api.send_message_with_keyboard(
            chat_id, FOLLOWUP_TEXT.format(name=name), FOLLOWUP_BUTTON
        )
        # Последний шаг — воронка завершена
        api.firebase_update(f"funnel/users/{user_id}", {
            "current_step": "followup",
            "state": "funnel_complete",
        })
        api.firebase_set(f"funnel/users/{user_id}/steps/{step}", {"sent_at": now})
        print(f"[funnel] {user_id} ← {step} (воронка завершена)")
        return

    else:
        print(f"[funnel] Неизвестный шаг: {step}")
        return

    # Обновляем состояние пользователя
    api.firebase_update(f"funnel/users/{user_id}", {"current_step": step})
    api.firebase_set(f"funnel/users/{user_id}/steps/{step}", {"sent_at": now})

    # Ставим следующий шаг в очередь
    next_step = get_next_step(step)
    if next_step and next_delay:
        schedule_step(user_id, chat_id, next_step, next_delay, {
            "name": name,
            "niche": niche,
            "survey_answer": survey_answer,
        })

    print(f"[funnel] {user_id} ← {step}")


def send_doc(chat_id, doc_key, intro_text):
    """Отправить PDF-документ с подводкой."""
    # Сначала текст-подводка
    api.send_message(chat_id, intro_text)

    # Затем сам файл
    token = get_file_token(doc_key)
    if token:
        api.send_file_message(
            chat_id, token, filename=DOC_NAMES.get(doc_key, f"{doc_key}.pdf")
        )
    else:
        api.send_message(
            chat_id,
            "К сожалению, не удалось отправить документ. "
            "Напишите нам — отправим вручную."
        )
        print(f"[funnel] НЕТ ТОКЕНА для {doc_key}!")


# ─── Планирование шагов ───

def schedule_step(user_id, chat_id, step, delay_seconds, context):
    """Поставить шаг в очередь на отправку через delay_seconds."""
    send_at = int(time.time() * 1000) + (delay_seconds * 1000)
    queue_item = {
        "user_id": str(user_id),
        "chat_id": chat_id,
        "step": step,
        "send_at": send_at,
    }
    queue_item.update(context)

    api.firebase_push("funnel/queue", queue_item)
    print(f"[funnel] Запланирован {step} для {user_id} через {delay_seconds}с")


# ─── Обработка заявки на аудит ───

def handle_audit_request(user_id, chat_id, user):
    """Обработать заявку на аудит."""
    name = user.get("name", "Пользователь")
    niche = user.get("niche", "не указана")
    now = int(time.time() * 1000)

    # Сохраняем заявку
    api.firebase_push("funnel/audit_requests", {
        "user_id": str(user_id),
        "name": name,
        "niche": niche,
        "chat_id": chat_id,
        "created_at": now,
    })

    # Обновляем пользователя
    api.firebase_update(f"funnel/users/{user_id}", {
        "audit_requested": True,
    })

    # Отвечаем пользователю
    api.send_message(chat_id, AUDIT_RESPONSE_TEXT.format(name=name))

    # Уведомляем администратора
    if ADMIN_USER_ID:
        admin_chat_id = api.firebase_get(f"funnel/admin/chat_id")
        if admin_chat_id:
            api.send_message(
                admin_chat_id,
                f"Новая заявка на аудит!\n\n"
                f"Имя: {name}\n"
                f"Ниша: {niche}\n"
                f"User ID: {user_id}",
            )

    print(f"[funnel] Заявка на аудит от {user_id} ({name}, {niche})")
