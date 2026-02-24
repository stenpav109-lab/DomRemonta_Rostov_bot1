import logging
import asyncio
import threading
import time
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
    ContextTypes
)
import os
from pathlib import Path

import config
from states import *
from keyboards import *
from database import Database

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализация базы данных
db = Database("leads.db")

# ID менеджера
MANAGER_ID = config.ADMIN_ID

# Путь к фото для приветствия
MEDIA_DIR = Path(__file__).parent / "media"
WELCOME_PHOTO_PATH = MEDIA_DIR / "welcome.jpg"

# Глобальные флаги для рассылок (добавить после импортов)
broadcast_first_sent = False
broadcast_second_sent = False


# ================== СТАРТ ==================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало опроса с фото"""
    user = update.effective_user

    # Получаем источник
    args = context.args
    source = args[0] if args else 'direct'
    context.user_data['source'] = source

    # Очищаем старые данные
    context.user_data.clear()
    context.user_data['source'] = source
    context.user_data['waiting_for_question'] = False

    # Сохраняем время старта
    db.update_start_time(user.id)

    # Проверяем, существует ли файл с фото
    if WELCOME_PHOTO_PATH.exists():
        try:
            # Отправляем фото из локального файла
            with open(WELCOME_PHOTO_PATH, 'rb') as photo_file:
                await context.bot.send_photo(
                    chat_id=user.id,
                    photo=photo_file,
                    caption=(
                        f"👋 Здравствуйте, {user.first_name}!\n\n"
                        "Вас приветствует команда **Дом Ремонта**\n\n"
                        "Поможем за 2 минуты:\n"
                        "1️⃣ рассчитать стоимость работ\n"
                        "2️⃣ понять, где у Вас риск *вылезти* по бюджету\n\n"
                        "Начнём❓"
                    ),
                    parse_mode='Markdown',
                    reply_markup=get_start_keyboard()
                )
        except Exception as e:
            print(f"Ошибка отправки фото: {e}")
            await update.message.reply_text(
                f"👋 Здравствуйте, {user.first_name}!\n\n"
                "Вас приветствует команда **Дом Ремонта**\n\n"
                "Поможем за 2 минуты:\n"
                "1️⃣ рассчитать стоимость работ\n"
                "2️⃣ понять, где у Вас риск *вылезти* по бюджету\n\n"
                "Начнём❓",
                reply_markup=get_start_keyboard(),
                parse_mode='Markdown'
            )
    else:
        await update.message.reply_text(
            f"👋 Здравствуйте, {user.first_name}!\n\n"
            "Вас приветствует команда **Дом Ремонта**\n\n"
            "Поможем за 2 минуты:\n"
            "1️⃣ рассчитать стоимость работ\n"
            "2️⃣ понять, где у Вас риск *вылезти* по бюджету\n\n"
            "Начнём❓",
            reply_markup=get_start_keyboard(),
            parse_mode='Markdown'
        )

    return GEOGRAPHY


# ================== ОБРАБОТЧИК СТАРТОВЫХ КНОПОК ==================

async def handle_start_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора на старте"""
    text = update.message.text
    user = update.effective_user

    if text == "✅ Начать тест":
        await update.message.reply_text(
            "🗺 **Где находится объект?**",
            reply_markup=get_geography_keyboard(),
            parse_mode='Markdown'
        )
        return GEOGRAPHY

    elif text == "📞 Сразу записаться на бесплатный замер":
        db.update_start_time(user.id)
        context.user_data['survey_completed'] = 1

        await update.message.reply_text(
            "📱 **Отлично! Давайте сразу запишем вас на замер**\n\n"
            "Нажмите кнопку ниже, чтобы поделиться контактом:",
            reply_markup=get_contact_keyboard(),
            parse_mode='Markdown'
        )
        return CONTACT

    elif text == "🔄 Начать заново":
        return await start(update, context)

    return GEOGRAPHY


# ================== ГЕОГРАФИЯ ==================

async def geography_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка географии"""
    text = update.message.text

    if text == "🔄 Начать заново":
        return await start(update, context)

    city = text.replace("🏙 ", "").replace("🏙", "").strip()
    context.user_data['geography'] = city

    if city not in config.ALLOWED_CITIES and text != "Другой город":
        await update.message.reply_text(
            f"❌ Мы работаем только в городах:\n"
            f"{' • '.join(config.ALLOWED_CITIES)}\n\n"
            "Выберите из списка:",
            reply_markup=get_geography_keyboard()
        )
        return GEOGRAPHY

    if text == "Другой город":
        await update.message.reply_text(
            "😔 Понял, извините, мы работаем по Ростову‑на‑Дону, Аксаю и Батайску.\n\n"
            "Выберите город из списка:",
            reply_markup=get_geography_keyboard()
        )
        return GEOGRAPHY

    await update.message.reply_text(
        "**Объект в каком варианте?**",
        reply_markup=get_object_type_keyboard(),
        parse_mode='Markdown'
    )
    return OBJECT_TYPE


# ================== ТИП ОБЪЕКТА ==================

async def object_type_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка типа объекта"""
    text = update.message.text

    if text == "🔄 Начать заново":
        return await start(update, context)

    context.user_data['object_type'] = text

    await update.message.reply_text(
        "🛁 **В каком состоянии квартира сейчас?**",
        reply_markup=get_condition_keyboard(),
        parse_mode='Markdown'
    )
    return CONDITION


# ================== СОСТОЯНИЕ ==================

async def condition_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка состояния квартиры"""
    text = update.message.text

    if text == "🔄 Начать заново":
        return await start(update, context)

    context.user_data['condition'] = text

    await update.message.reply_text(
        "✏️ **Напишите метраж квартиры** (например: 72)",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode='Markdown'
    )
    return METRAGE


# ================== МЕТРАЖ ==================

async def metrage_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка метража"""
    text = update.message.text

    if text == "🔄 Начать заново":
        return await start(update, context)

    try:
        metrage = int(text)
        context.user_data['metrage'] = metrage

        if metrage < config.MIN_METRAGE:
            await update.message.reply_text(
                f"🙏 Спасибо! Мы берём объекты от {config.MIN_METRAGE} м², "
                "чтобы отвечать за сроки и результат *под ключ*.\n\n"
                "Но вы можете оставить заявку - обсудим индивидуально.",
                parse_mode='Markdown'
            )

        await update.message.reply_text(
            "**Какой ремонт Вам нужен?**",
            reply_markup=get_repair_format_keyboard(),
            parse_mode='Markdown'
        )
        return REPAIR_FORMAT

    except ValueError:
        await update.message.reply_text(
            "❌ Пожалуйста, введите число (например: 72)"
        )
        return METRAGE


# ================== ФОРМАТ РЕМОНТА ==================

async def repair_format_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка формата ремонта"""
    text = update.message.text

    if text == "🔄 Начать заново":
        return await start(update, context)

    context.user_data['repair_format'] = text

    if "Частичный" in text or "Переделка" in text:
        await update.message.reply_text(
            "🤝 Понял Вас. Мы делаем только полный ремонт под ключ, "
            "чтобы не зависеть от чужих работ и отвечать за итог.\n\n"
            "Но вы можете оставить заявку - обсудим варианты.",
            parse_mode='Markdown'
        )

    await update.message.reply_text(
        "🔑 **Ключи уже на руках?**",
        reply_markup=get_keys_ready_keyboard(),
        parse_mode='Markdown'
    )
    return KEYS_READY


# ================== НАЛИЧИЕ КЛЮЧЕЙ ==================

async def keys_ready_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка наличия ключей"""
    text = update.message.text

    if text == "🔄 Начать заново":
        return await start(update, context)

    context.user_data['keys_ready'] = text

    await update.message.reply_text(
        "📌 **Когда хотите заехать в готовую квартиру?**",
        reply_markup=get_deadline_keyboard(),
        parse_mode='Markdown'
    )
    return DEADLINE


# ================== ДЕДЛАЙН ==================

async def deadline_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка дедлайна"""
    text = update.message.text

    if text == "🔄 Начать заново":
        return await start(update, context)

    context.user_data['deadline'] = text

    await update.message.reply_text(
        "😟 **Честно: что тревожит больше всего?**",
        reply_markup=get_main_fear_keyboard(),
        parse_mode='Markdown'
    )
    return MAIN_FEAR


# ================== ГЛАВНАЯ ТРЕВОГА ==================

async def main_fear_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка главной тревоги"""
    text = update.message.text

    if text == "🔄 Начать заново":
        return await start(update, context)

    context.user_data['main_fear'] = text

    await update.message.reply_text(
        "💸 **Чтобы не гадать *на кофейной гуще*: какой ориентир по бюджету на работы Вы рассматриваете?**",
        reply_markup=get_budget_keyboard(),
        parse_mode='Markdown'
    )
    return BUDGET


# ================== БЮДЖЕТ ==================

async def budget_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка бюджета"""
    text = update.message.text

    if text == "🔄 Начать заново":
        return await start(update, context)

    context.user_data['budget'] = text

    # Определяем, какое сообщение отправить в зависимости от страха
    fear = context.user_data.get('main_fear', '')

    if "смета вырастет" in fear:
        message = (
            "Понял. Ваш главный риск — *сюрпризы по ходу*.\n\n"
            "Обычно смета улетает не из‑за *плохих людей*, а из‑за двух вещей:\n"
            "— начали без чёткого состава работ\n"
            "— изменения по ходу (*а давайте по‑другому…*) не фиксировали заранее\n\n"
            "Если хотите, мы сделаем так, чтобы у Вас было понятно по шагам: что делаем, "
            "что может поменять сумму и как это согласуется заранее.\n\n"
            "Готовы записаться на бесплатный замер?"
        )
    elif "сроки" in fear:
        message = (
            "Понял. Ваш главный риск — *ремонт растянется*.\n\n"
            "Чаще всего сроки *плывут*, когда нет нормальной этапности и контроля: "
            "сегодня одно, завтра другое, послезавтра *мы не успели*.\n\n"
            "На замере мы фиксируем объём, и даём реальный план по этапам, "
            "чтобы Вы понимали, когда сможете заехать.\n\n"
            "Записать Вас на бесплатный замер?"
        )
    elif "качество" in fear or "скрытые" in fear:
        message = (
            "Понимаю Вас. Самое обидное в ремонте — когда *с виду красиво*, "
            "а потом вылезает то, что было скрыто.\n\n"
            "Поэтому мы делаем акцент на этапах, которые обычно не видно, "
            "но они решают всё: сантехника, электрика, подготовка, узлы.\n\n"
            "На замере расскажем, где у Вашего объекта *зона риска*, "
            "и что нужно проконтролировать, чтобы не платить дважды.\n\n"
            "Записать Вас на бесплатный замер?"
        )
    elif "Всё сразу" in fear or "всё сразу" in fear:
        message = (
            "Честно — это нормальное состояние после *ключей*.\n"
            "Голова шумит, все советуют разное, и Вы просто не хотите встрять.\n\n"
            "Хорошая новость: это решается системой — понятный объём, "
            "план этапов и прозрачные согласования.\n\n"
            "Давайте сделаем первый спокойный шаг: бесплатный замер."
        )
    else:
        message = (
            "Спасибо за ответы! Теперь давайте определимся со следующим шагом.\n\n"
            "Готовы записаться на бесплатный замер?"
        )

    await update.message.reply_text(
        message,
        reply_markup=get_final_choice_keyboard(),
        parse_mode='Markdown'
    )
    return RESULT


# ================== ФИНАЛЬНЫЙ ВЫБОР ==================

async def final_choice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка финального выбора"""
    text = update.message.text

    if text == "🔄 Начать заново":
        return await start(update, context)

    if text == "✅ Записаться на бесплатный замер":
        await update.message.reply_text(
            "📱 **Отлично! Оставьте ваш номер телефона**\n\n"
            "Нажмите кнопку ниже, чтобы поделиться контактом:",
            reply_markup=get_contact_keyboard(),
            parse_mode='Markdown'
        )
        return CONTACT

    elif text == "❓ Часто задаваемые вопросы (FAQ)":
        await update.message.reply_text(
            "❓ **Часто задаваемые вопросы**\n\n"
            "Выберите интересующий вас вопрос:",
            reply_markup=get_faq_keyboard(),
            parse_mode='Markdown'
        )
        # Выходим из диалога для обработки FAQ отдельно
        return ConversationHandler.END

    elif text == "👀 Посмотреть примеры работ":
        await update.message.reply_text(
            "👀 **Примеры наших работ:**\n\n"
            "Наш Telegram-канал: https://t.me/remontkvartirRND61\n\n"
            "Там вы найдете:\n"
            "• Фото готовых объектов\n"
            "• Видео процессов\n"
            "• Отзывы клиентов\n"
            "• Идеи для ремонта",
            disable_web_page_preview=False
        )
        await update.message.reply_text(
            "Готовы записаться на замер?",
            reply_markup=get_final_choice_keyboard()
        )
        return RESULT

    return RESULT


# ================== ОБРАБОТЧИК КОНТАКТА ==================

async def contact_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка контакта"""
    if update.message.text and update.message.text == "🔄 Начать заново":
        return await start(update, context)

    contact = update.message.contact
    user = update.effective_user

    if not contact:
        await update.message.reply_text(
            "❌ Пожалуйста, нажмите кнопку **'Отправить номер телефона'**",
            reply_markup=get_contact_keyboard()
        )
        return CONTACT

    # Сохраняем данные пользователя
    context.user_data['user_id'] = user.id
    context.user_data['name'] = f"{user.first_name} {user.last_name or ''}".strip()
    context.user_data['phone'] = contact.phone_number
    context.user_data['survey_completed'] = 1
    context.user_data['appointment_time'] = "ожидает подтверждения"

    # Заполняем пропущенные поля
    default_values = {
        'geography': "Не указан (прямая запись)",
        'object_type': "Не указан",
        'condition': "Не указано",
        'metrage': 0,
        'repair_format': "Не указан",
        'keys_ready': "Не указано",
        'deadline': "Не указан",
        'main_fear': "Не указан",
        'budget': "Не указан"
    }

    for key, value in default_values.items():
        if key not in context.user_data:
            context.user_data[key] = value

    lead_data = {key: context.user_data.get(key) for key in default_values}
    lead_data.update({
        'user_id': user.id,
        'name': context.user_data.get('name', ''),
        'phone': contact.phone_number,
        'source': context.user_data.get('source', 'direct'),
        'appointment_time': 'ожидает подтверждения',
        'appointment_status': 'pending',
        'survey_completed': 1,
        'start_time': db.get_user_start_time(user.id)
    })

    db.save_lead(lead_data)

    await update.message.reply_text(
        "✅ **Принято!**\n\n"
        "Мы получили заявку на бесплатный замер:\n\n"
        "📞 Менеджер свяжется с Вами и подтвердит точное время.\n\n"
        "Спасибо за обращение!\n\n"
        "📌 Если у вас есть вопросы - загляните в **FAQ**",
        reply_markup=get_final_keyboard(),
        parse_mode='Markdown'
    )

    await notify_manager(context, lead_data)
    # Выходим из диалога
    return ConversationHandler.END


# ================== ОБРАБОТЧИК FAQ (ВНЕ ДИАЛОГА) ==================

# ================== ОБРАБОТЧИК FAQ (ПРОСТОЙ, КАК В РАБОЧЕМ ВАРИАНТЕ) ==================

async def faq_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Простой обработчик для FAQ (как в рабочем варианте)"""
    text = update.message.text
    user_id = update.effective_user.id

    logger.info(f"📚 FAQ handler: {text} от пользователя {user_id}")

    if text == "📋 Какие этапы ремонта?":
        await update.message.reply_text(
            "📋 **Этапы ремонта:**\n\n"
            "1️⃣ **Демонтаж** - удаление старых покрытий\n"
            "2️⃣ **Черновые работы** - стяжка, штукатурка\n"
            "3️⃣ **Инженерные системы** - электрика, сантехника\n"
            "4️⃣ **Чистовая отделка** - плитка, обои, покраска\n"
            "5️⃣ **Меблировка** - установка дверей, мебели",
            reply_markup=get_faq_keyboard()
        )

    elif text == "💰 Как формируется смета?":
        await update.message.reply_text(
            "💰 **Как формируется смета:**\n\n"
            "• **Замер и ТЗ** — бесплатно\n"
            "• **Детальная смета** по этапам\n"
            "• **Фиксированная цена** до начала работ",
            reply_markup=get_faq_keyboard()
        )

    elif text == "⏱️ Сколько длится ремонт?":
        await update.message.reply_text(
            "⏱️ **Сроки ремонта:**\n\n"
            "• **1-к квартира:** 2-3 месяца\n"
            "• **2-к квартира:** 3-4 месяца\n"
            "• **3-к квартира:** 4-5 месяцев",
            reply_markup=get_faq_keyboard()
        )

    elif text == "🫵 Задать свой вопрос":
        await update.message.reply_text(
            "❓ **Напишите ваш вопрос**",
            reply_markup=ReplyKeyboardRemove()
        )
        context.user_data['waiting_for_question'] = True
        # ВАЖНО: не возвращаем ConversationHandler.END, а просто выходим
        return

    elif text == "🔙 Назад в меню":
        if context.user_data.get('survey_completed'):
            await update.message.reply_text(
                "Чем еще могу помочь?",
                reply_markup=get_final_keyboard()
            )
        else:
            await update.message.reply_text(
                "Готовы записаться на замер?",
                reply_markup=get_final_choice_keyboard()
            )



# ================== ОБРАБОТЧИК ВОПРОСОВ ==================

async def waiting_question_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка состояния ожидания вопроса"""
    user = update.effective_user
    text = update.message.text

    if text == "🔄 Начать заново":
        return await start(update, context)

    if context.user_data.get('waiting_for_question'):
        context.user_data['waiting_for_question'] = False

        # Отправляем вопрос менеджеру
        await notify_manager_question(context, user, text)

        # Отправляем подтверждение пользователю
        await update.message.reply_text(
            "✅ **Ваш вопрос получен и передан менеджеру!**\n\n"
            "Ответ придет в ближайшее время."
        )

        # Возвращаемся в FAQ
        await update.message.reply_text(
            "❓ **Часто задаваемые вопросы**\n\n"
            "Выберите интересующий вас вопрос:",
            reply_markup=get_faq_keyboard(),
            parse_mode='Markdown'
        )
        return

    return


# ================== УВЕДОМЛЕНИЯ МЕНЕДЖЕРА ==================

async def notify_manager(context, lead_data):
    """Уведомление менеджера о новой заявке"""
    message = (
        f"🔔 **НОВАЯ ЗАЯВКА** 🔔\n\n"
        f"👤 **Имя:** {lead_data['name']}\n"
        f"📞 **Телефон:** {lead_data['phone']}\n"
        f"🏙 **Город:** {lead_data.get('geography', 'Не указан')}\n"
        f"🏠 **Тип объекта:** {lead_data.get('object_type', 'Не указан')}\n"
        f"🛁 **Состояние:** {lead_data.get('condition', 'Не указано')}\n"
        f"📐 **Метраж:** {lead_data.get('metrage', 0)} м²\n"
        f"🔨 **Формат ремонта:** {lead_data.get('repair_format', 'Не указан')}\n"
        f"🔑 **Ключи:** {lead_data.get('keys_ready', 'Не указано')}\n"
        f"📅 **Заезд:** {lead_data.get('deadline', 'Не указан')}\n"
        f"😟 **Страх:** {lead_data.get('main_fear', 'Не указан')}\n"
        f"💰 **Бюджет:** {lead_data.get('budget', 'Не указан')}\n"
        f"📱 **Источник:** {lead_data.get('source', 'direct')}\n"
        f"⏰ **Время:** {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    )

    try:
        await context.bot.send_message(
            chat_id=config.ADMIN_ID,
            text=message,
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Ошибка уведомления: {e}")


# ================== УВЕДОМЛЕНИЕ МЕНЕДЖЕРА О ВОПРОСЕ ==================

async def notify_manager_question(context, user, question):
    """Уведомление менеджера о новом вопросе"""
    message = (
        f"❓ **НОВЫЙ ВОПРОС** ❓\n\n"
        f"👤 **Имя:** {user.first_name} {user.last_name or ''}\n"
        f"🆔 **ID:** {user.id}\n"
        f"📱 **Username:** @{user.username if user.username else 'нет'}\n"
        f"📝 **Вопрос:** \n\n{question}"
    )

    try:
        await context.bot.send_message(
            chat_id=config.ADMIN_ID,
            text=message,
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Ошибка уведомления о вопросе: {e}")


# ================== РАССЫЛКИ (ТОЛЬКО ДЛЯ НЕ ЗАПОЛНИВШИХ АНКЕТУ) ==================

async def send_broadcast_first(app):
    """Отправка первой рассылки (фото с подписью) - ТОЛЬКО ОДИН РАЗ"""
    global broadcast_first_sent

    if broadcast_first_sent:
        logger.info("⏭️ Первая рассылка уже была отправлена, пропускаем")
        return

    # Получаем пользователей, которые НЕ заполнили анкету
    users = db.get_all_users_without_survey()

    if not users:
        logger.info("📭 Нет пользователей для первой рассылки (все заполнили анкету)")
        return

    # Путь к фото для первой рассылки
    MEDIA_DIR = Path(__file__).parent / "media"
    FIRST_PHOTO_PATH = MEDIA_DIR / "broadcast_first.jpg"

    if not FIRST_PHOTO_PATH.exists():
        logger.error(f"❌ Фото для первой рассылки не найдено: {FIRST_PHOTO_PATH}")
        return

    first_caption = (
        "🎁 **Дарим бесплатный дизайн проект от нашего дизайнера** "
        "([смотреть](https://t.me/remontkvartirRND61/497)), "
        "за расчет стоимости ремонта до конца дня 👇"
    )

    success_count = 0
    for user_id in users:
        try:
            with open(FIRST_PHOTO_PATH, 'rb') as photo:
                await app.bot.send_photo(
                    chat_id=user_id,
                    photo=photo,
                    caption=first_caption,
                    parse_mode='Markdown'
                )
            success_count += 1
            await asyncio.sleep(0.1)
        except Exception as e:
            logger.error(f"Ошибка первой рассылки пользователю {user_id}: {e}")

    logger.info(f"✅ Первая рассылка (фото) завершена. Отправлено: {success_count}/{len(users)}")
    broadcast_first_sent = True


async def send_broadcast_second(app):
    """Отправка второй рассылки (файл с подписью) - ТОЛЬКО ОДИН РАЗ"""
    global broadcast_second_sent

    if broadcast_second_sent:
        logger.info("⏭️ Вторая рассылка уже была отправлена, пропускаем")
        return

    # Получаем пользователей, которые НЕ заполнили анкету
    users = db.get_all_users_without_survey()

    if not users:
        logger.info("📭 Нет пользователей для второй рассылки (все заполнили анкету)")
        return

    # Путь к файлу для второй рассылки
    MEDIA_DIR = Path(__file__).parent / "media"
    SECOND_FILE_PATH = MEDIA_DIR / "broadcast_second.pdf"

    if not SECOND_FILE_PATH.exists():
        logger.error(f"❌ Файл для второй рассылки не найден: {SECOND_FILE_PATH}")
        return

    second_caption = (
        "☝️ **Абсолютно бесплатно забирайте гид по выбору материалов** "
        "от нашей команды."
    )

    success_count = 0
    for user_id in users:
        try:
            with open(SECOND_FILE_PATH, 'rb') as file:
                await app.bot.send_document(
                    chat_id=user_id,
                    document=file,
                    caption=second_caption,
                    parse_mode='Markdown'
                )
            success_count += 1
            await asyncio.sleep(0.1)
        except Exception as e:
            logger.error(f"Ошибка второй рассылки пользователю {user_id}: {e}")

    logger.info(f"✅ Вторая рассылка (файл) завершена. Отправлено: {success_count}/{len(users)}")
    broadcast_second_sent = True


def broadcast_scheduler(app):
    """Планировщик рассылок в отдельном потоке"""
    logger.info("🚀 Планировщик рассылок запущен")

    # Запоминаем время СТАРТА бота
    start_time = datetime.now()

    # Создаем свой цикл событий
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    while True:
        try:
            now = datetime.now()
            minutes_passed = (now - start_time).total_seconds() / 60

            # Первая рассылка (фото)
            if not broadcast_first_sent and minutes_passed >= config.AUTO_MESSAGE_DELAYS['first']:
                logger.info("📸 Запуск первой рассылки (фото)")
                loop.run_until_complete(send_broadcast_first(app))

            # Вторая рассылка (файл)
            if not broadcast_second_sent and minutes_passed >= config.AUTO_MESSAGE_DELAYS['second']:
                logger.info("📎 Запуск второй рассылки (файл)")
                loop.run_until_complete(send_broadcast_second(app))

            # Если обе отправлены - можно выйти или продолжать проверять (оставим для надежности)
            if broadcast_first_sent and broadcast_second_sent:
                logger.info("✅ Все рассылки выполнены")
                # Можно break, но оставим для проверки

            time.sleep(60)  # Проверка каждую минуту

        except Exception as e:
            logger.error(f"Ошибка в планировщике: {e}")
            time.sleep(60)


# ================== ВСПОМОГАТЕЛЬНЫЕ КОМАНДЫ ==================

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена диалога"""
    await update.message.reply_text(
        "❌ Диалог отменен. Если захотите начать заново - напишите /start",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Справка"""
    await update.message.reply_text(
        "🤖 **Команды бота:**\n\n"
        "/start - начать опрос\n"
        "/cancel - отменить текущий диалог\n"
        "/help - показать эту справку"
    )


# ================== ОБРАБОТЧИК INLINE КНОПОК ==================

async def inline_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатий на inline-кнопки"""
    query = update.callback_query
    await query.answer()

    if query.data == "back_to_menu":
        # Удаляем сообщение с inline-кнопками
        await query.message.delete()

        # Возвращаемся в обычное меню
        if context.user_data.get('survey_completed'):
            await query.message.reply_text(
                "Чем еще могу помочь?",
                reply_markup=get_final_keyboard()
            )
        else:
            await query.message.reply_text(
                "Готовы записаться на замер?",
                reply_markup=get_final_choice_keyboard()
            )

# ================== ЗАПУСК ==================

def main(inline_callback_handler=None):
    """Главная функция"""
    application = Application.builder().token(config.BOT_TOKEN).build()

    # Создаем обработчик диалога (БЕЗ FAQ)
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start),
            MessageHandler(filters.Regex('^(✅ Начать тест)$'), handle_start_choice),
            MessageHandler(filters.Regex('^(📞 Сразу записаться на бесплатный замер)$'), handle_start_choice)
        ],
        states={
            GEOGRAPHY: [MessageHandler(filters.TEXT & ~filters.COMMAND, geography_handler)],
            OBJECT_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, object_type_handler)],
            CONDITION: [MessageHandler(filters.TEXT & ~filters.COMMAND, condition_handler)],
            METRAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, metrage_handler)],
            REPAIR_FORMAT: [MessageHandler(filters.TEXT & ~filters.COMMAND, repair_format_handler)],
            KEYS_READY: [MessageHandler(filters.TEXT & ~filters.COMMAND, keys_ready_handler)],
            DEADLINE: [MessageHandler(filters.TEXT & ~filters.COMMAND, deadline_handler)],
            MAIN_FEAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, main_fear_handler)],
            BUDGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, budget_handler)],
            RESULT: [MessageHandler(filters.TEXT & ~filters.COMMAND, final_choice_handler)],
            CONTACT: [MessageHandler(filters.CONTACT, contact_handler)],
            'WAITING_QUESTION': [MessageHandler(filters.TEXT & ~filters.COMMAND, waiting_question_handler)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        per_message=False,
        per_chat=True,
        per_user=True,
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler('help', help_command))

    # ОТДЕЛЬНЫЙ ОБРАБОТЧИК ДЛЯ FAQ (работает всегда)
    application.add_handler(MessageHandler(
        filters.Regex(
            '^(📋 Какие этапы ремонта|💰 Как формируется смета|⏱️ Сколько длится ремонт|🫵 Задать свой вопрос|🔙 Назад в меню)$'),
        faq_handler
    ))

    # Обработчик для inline-кнопок
    application.add_handler(CallbackQueryHandler(inline_callback_handler, pattern="^(back_to_menu)$"))

    # Планировщик рассылок
    thread = threading.Thread(target=broadcast_scheduler, args=(application,), daemon=True)
    thread.start()

    print("=" * 70)
    print("🚀 БОТ ДЛЯ ЗАПИСИ НА ЗАМЕР ЗАПУЩЕН!")
    print("=" * 70)
    print(f"📱 Менеджер ID: {MANAGER_ID}")
    print(f"📸 Первая рассылка через: {config.AUTO_MESSAGE_DELAYS['first']} мин")
    print(f"📎 Вторая рассылка через: {config.AUTO_MESSAGE_DELAYS['second']} мин")
    print("🛑 Нажмите Ctrl+C для остановки")
    print("=" * 70)

    application.run_polling()


if __name__ == '__main__':
    main()