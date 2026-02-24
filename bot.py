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

# ID менеджеров (список)
MANAGER_IDS = config.ADMIN_IDS

# Путь к фото для приветствия
MEDIA_DIR = Path(__file__).parent / "media"
WELCOME_PHOTO_PATH = MEDIA_DIR / "welcome.jpg"

# Глобальные флаги для рассылок
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

    # Очищаем старые данные, но сохраняем survey_completed если был
    survey_completed = context.user_data.get('survey_completed', 0)
    context.user_data.clear()
    context.user_data['source'] = source
    context.user_data['waiting_for_question'] = False
    context.user_data['survey_completed'] = survey_completed

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
                        "2️⃣ понять, *уложитесь* ли вы в бюджет\n\n"
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
                "2️⃣ понять, *уложитесь* ли вы в бюджет\n\n"
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
            "2️⃣ понять, *уложитесь* ли вы в бюджет\n\n"
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

    # Сохраняем тип объекта
    context.user_data['object_type'] = text

    # Если выбрана вторичка, показываем дополнительные опции
    if text == "🏚 Вторичка":
        await update.message.reply_text(
            "🔨 **Уточните по вторичке:**\n\n"
            "Что требуется сделать?",
            reply_markup=get_secondary_options_keyboard(),
            parse_mode='Markdown'
        )
        return SECONDARY_OPTIONS

    # Для новостройки и дома - спрашиваем состояние
    await update.message.reply_text(
        "🛁 **В каком состоянии квартира сейчас?**",
        reply_markup=get_condition_keyboard(),
        parse_mode='Markdown'
    )
    return CONDITION


# Добавьте новый обработчик для опций вторички
async def secondary_options_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка дополнительных опций для вторички"""
    text = update.message.text
    user = update.effective_user

    if text == "🔄 Начать заново":
        return await start(update, context)

    if text == "🔙 Назад к типам объектов":
        await update.message.reply_text(
            "**Объект в каком варианте?**",
            reply_markup=get_object_type_keyboard(),
            parse_mode='Markdown'
        )
        return OBJECT_TYPE

    # Сохраняем выбранную опцию
    context.user_data['secondary_options'] = text

    # Для вторички устанавливаем состояние по умолчанию
    context.user_data['condition'] = "Вторичка (специфика)"

    # Сразу переходим к метражу (пропускаем вопрос о состоянии)
    await update.message.reply_text(
        "✏️ **Напишите метраж квартиры** (например: 72)",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode='Markdown'
    )
    return METRAGE

# ================== СОСТОЯНИЕ ==================

async def condition_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка состояния квартиры"""
    text = update.message.text

    if text == "🔄 Начать заново":
        return await start(update, context)

    # Проверяем, не вторичка ли это (на всякий случай)
    if context.user_data.get('object_type') == "🏚 Вторичка":
        # Если это вторичка, но мы почему-то попали сюда - пропускаем
        await update.message.reply_text(
            "✏️ **Напишите метраж квартиры** (например: 72)",
            reply_markup=ReplyKeyboardRemove(),
            parse_mode='Markdown'
        )
        return METRAGE

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

    # Убираем сообщение для "Переделка после мастеров"
    # Оставляем только для "Частичный"
    if "Частичный" in text:
        await update.message.reply_text(
            "🤝 Понял Вас. Мы делаем только полный ремонт под ключ, "
            "чтобы не зависеть от чужих работ и отвечать за итог.\n\n"
            "Но вы можете оставить заявку - обсудим варианты.",
            parse_mode='Markdown'
        )
    # Для "Переделка после мастеров" ничего не отправляем

    # Сразу переходим к вопросу о ключах для всех вариантов
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
        "📌 **Когда планируете завершить ремонт?**",
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
            "— изменения по ходу (а давайте по‑другому…) не фиксировали заранее\n\n"
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

    elif text == "❓У вас есть вопрос":
        await update.message.reply_text(
            "❓ Часто задаваемые вопросы \n\n"
            "Выберите категорию вопросов:",
            reply_markup=get_faq_categories_keyboard(),
            parse_mode='Markdown'
        )
        return RESULT

    elif text == "👀 Посмотреть примеры работ":
        await update.message.reply_text(
            "👀 Примеры наших работ: \n\n"
            "Наш Telegram-канал: https://t.me/remontkvartirRND61\n\n"
            "Там вы найдете:\n"
            "• Фото готовых объектов\n"
            "• Видео процессов\n"
            "• Отзывы клиентов\n"
            "• Идеи для ремонта",
            disable_web_page_preview=False
        )
        # Сразу возвращаемся к выбору
        await update.message.reply_text(
            "Готовы записаться на замер?",
            reply_markup=get_final_choice_keyboard()
        )
        return RESULT

    # ===== ОБРАБОТКА FAQ ВНУТРИ RESULT =====

    # Категории FAQ
    elif text == "💰 Бюджет и смета":
        await update.message.reply_text(
            "💰 **Вопросы по бюджету и смете**\n\n"
            "Выберите интересующий вопрос:",
            reply_markup=get_budget_faq_keyboard(),
            parse_mode='Markdown'
        )
        return RESULT

    elif text == "⏳ Сроки ремонта":
        await update.message.reply_text(
            "⏳ **Вопросы по срокам ремонта**\n\n"
            "Выберите интересующий вопрос:",
            reply_markup=get_timing_faq_keyboard(),
            parse_mode='Markdown'
        )
        return RESULT

    elif text == "🧱 Объем работ":
        await update.message.reply_text(
            "🧱 **Вопросы по объему работ**\n\n"
            "Выберите интересующий вопрос:",
            reply_markup=get_scope_faq_keyboard(),
            parse_mode='Markdown'
        )
        return RESULT

    elif text == "🎨 Дизайн-проект":
        await update.message.reply_text(
            "🎨 **Вопросы по дизайн-проекту**\n\n"
            "Выберите интересующий вопрос:",
            reply_markup=get_design_faq_keyboard(),
            parse_mode='Markdown'
        )
        return RESULT

    elif text == "🧰 Материалы":
        await update.message.reply_text(
            "🧰 **Вопросы по материалам**\n\n"
            "Выберите интересующий вопрос:",
            reply_markup=get_materials_faq_keyboard(),
            parse_mode='Markdown'
        )
        return RESULT

    elif text == "📸 Контроль и отчетность":
        await update.message.reply_text(
            "📸 **Вопросы по контролю и отчетности**\n\n"
            "Выберите интересующий вопрос:",
            reply_markup=get_control_faq_keyboard(),
            parse_mode='Markdown'
        )
        return RESULT

    elif text == "📄 Договор и гарантии":
        await update.message.reply_text(
            "📄 **Вопросы по договору и гарантиям**\n\n"
            "Выберите интересующий вопрос:",
            reply_markup=get_contract_faq_keyboard(),
            parse_mode='Markdown'
        )
        return RESULT

    elif text == "🚪 Начало ремонта":
        await update.message.reply_text(
            "🚪 **Вопросы по началу ремонта**\n\n"
            "Выберите интересующий вопрос:",
            reply_markup=get_start_faq_keyboard(),
            parse_mode='Markdown'
        )
        return RESULT

    # Конкретные вопросы по бюджету
    elif text == "💸 Смета может вырасти в процессе?":
        await update.message.reply_text(
            "💸 **Смета может вырасти в процессе?**\n\n"
            "Может измениться только если меняется объём работ или Ваши решения.\n\n"
            "Мы делаем так: любые изменения согласуем заранее, до выполнения, чтобы не было сюрпризов “в конце”.",
            reply_markup=get_budget_faq_keyboard(),
            parse_mode='Markdown'
        )
        return RESULT

    elif text == "💸 Почему нельзя назвать цену без замера?":
        await update.message.reply_text(
            "💸 **Почему нельзя назвать цену без замера?**\n\n"
            "Потому что “на глаз” в ремонте чаще всего = ошибка и потом переделки/доплаты.\n\n"
            "Замер нужен, чтобы зафиксировать объём работ, пожелания и нюансы квартиры.",
            reply_markup=get_budget_faq_keyboard(),
            parse_mode='Markdown'
        )
        return RESULT

    elif text == "💸 У вас есть цена за м²?":
        await update.message.reply_text(
            "💸 **У вас есть цена за м²?**\n\n"
            "У нас расчёт индивидуальный, потому что на стоимость влияет состояние квартиры, инженерия и Ваши пожелания.",
            reply_markup=get_budget_faq_keyboard(),
            parse_mode='Markdown'
        )
        return RESULT

    # Вопросы по срокам
    elif text == "⏳ Сколько длится ремонт под ключ?":
        await update.message.reply_text(
            "⏳ **Сколько длится ремонт под ключ?**\n\n"
            "В среднем 3–4 месяца, но точный срок зависит от метража, состояния квартиры и сложности проекта.",
            reply_markup=get_timing_faq_keyboard(),
            parse_mode='Markdown'
        )
        return RESULT

    elif text == "⏳ Как вы контролируете сроки?":
        await update.message.reply_text(
            "⏳ **Как вы контролируете сроки?**\n\n"
            "Мы ведём ремонт по этапам и ежедневно фиксируем прогресс.\n\n"
            "Плюс даём понятную последовательность работ, чтобы не было хаоса.",
            reply_markup=get_timing_faq_keyboard(),
            parse_mode='Markdown'
        )
        return RESULT

    # Вопросы по объему работ
    elif text == "🧱 Что входит в ремонт под ключ?":
        await update.message.reply_text(
            "🧱 **Что входит в ремонт под ключ?**\n\n"
            "Это полный цикл работ: черновые + чистовые работы, инженерка (электрика/сантехника), отделка.",
            reply_markup=get_scope_faq_keyboard(),
            parse_mode='Markdown'
        )
        return RESULT

    elif text == "🧱 Вы делаете частичный ремонт?":
        await update.message.reply_text(
            "🧱 **Вы делаете частичный ремонт?**\n\n"
            "Нет. Мы берём только полный ремонт квартиры под ключ.\n\n"
            "Так мы отвечаем за результат и сроки, без зависимости от чужих работ.",
            reply_markup=get_scope_faq_keyboard(),
            parse_mode='Markdown'
        )
        return RESULT

    # Вопросы по дизайну
    elif text == "🎨 Дизайн-проект входит?":
        await update.message.reply_text(
            "🎨 **Дизайн-проект входит?**\n\n"
            "Да, дизайн-проект входит (обсуждаем на старте).\n\n"
            "Это снижает переделки и помогает заранее продумать свет, розетки, функциональность.",
            reply_markup=get_design_faq_keyboard(),
            parse_mode='Markdown'
        )
        return RESULT

    elif text == "🎨 Если у нас есть дизайн-проект?":
        await update.message.reply_text(
            "🎨 **Если у нас есть дизайн-проект?**\n\n"
            "Да, конечно. Мы посмотрим проект, уточним нюансы на замере и дальше работаем по нему.",
            reply_markup=get_design_faq_keyboard(),
            parse_mode='Markdown'
        )
        return RESULT

    # Вопросы по материалам
    elif text == "🧰 Кто закупает материалы?":
        await update.message.reply_text(
            "🧰 **Кто закупает материалы?**\n\n"
            "Обычно материалы закупаем мы — так проще по логистике и срокам.\n\n"
            "Но если Вам спокойнее — Вы можете закупать сами или частично.",
            reply_markup=get_materials_faq_keyboard(),
            parse_mode='Markdown'
        )
        return RESULT

    elif text == "🧰 Можно выбрать материалы с вами?":
        await update.message.reply_text(
            "🧰 **Можно выбрать материалы с вами?**\n\n"
            "Да. Мы помогаем подобрать материалы под Ваш бюджет и задачи, чтобы не переплачивать и не ошибаться.",
            reply_markup=get_materials_faq_keyboard(),
            parse_mode='Markdown'
        )
        return RESULT

    # Вопросы по контролю
    elif text == "📸 Как увидеть что работы идут?":
        await update.message.reply_text(
            "📸 **Как увидеть что работы идут?**\n\n"
            "Вы будете видеть прогресс: фото/видео с объектов + отчётность по этапам.\n\n"
            "Никакой “мы работали, но показать нечего”.",
            reply_markup=get_control_faq_keyboard(),
            parse_mode='Markdown'
        )
        return RESULT

    elif text == "📸 Можно посмотреть ваши объекты?":
        await update.message.reply_text(
            "📸 **Можно посмотреть ваши объекты?**\n\n"
            "Да, по согласованию можем показать реальные объекты (в процессе или готовые).",
            reply_markup=get_control_faq_keyboard(),
            parse_mode='Markdown'
        )
        return RESULT

    # Вопросы по договору
    elif text == "📄 Вы работаете по договору?":
        await update.message.reply_text(
            "📄 **Вы работаете по договору?**\n\n"
            "Да, работаем по договору на юрлицо.\n\n"
            "Это фиксирует обязательства, условия и порядок работ.",
            reply_markup=get_contract_faq_keyboard(),
            parse_mode='Markdown'
        )
        return RESULT

    elif text == "📄 Какая гарантия?":
        await update.message.reply_text(
            "📄 **Какая гарантия?**\n\n"
            "Гарантия прописывается в договоре.\n\n"
            "На замере/созвоне менеджер пояснит сроки и что именно покрывает гарантия.",
            reply_markup=get_contract_faq_keyboard(),
            parse_mode='Markdown'
        )
        return RESULT

    elif text == "👷 Кто делает ремонт?":
        await update.message.reply_text(
            "👷 **Кто делает ремонт?**\n\n"
            "Работает наша бригада под руководством прораба.\n\n"
            "Ответственность не “размывается” между разными исполнителями.",
            reply_markup=get_contract_faq_keyboard(),
            parse_mode='Markdown'
        )
        return RESULT

    # Вопросы по началу
    elif text == "🚪 Замер платный?":
        await update.message.reply_text(
            "🚪 **Замер платный?**\n\n"
            "Нет, замер бесплатный.",
            reply_markup=get_start_faq_keyboard(),
            parse_mode='Markdown'
        )
        return RESULT

    elif text == "🚪 Что подготовить к замеру?":
        await update.message.reply_text(
            "🚪 **Что подготовить к замеру?**\n\n"
            "• планировку/план БТИ (фото или файл)\n"
            "• 2–3 примера “как нравится” (скриншоты)\n"
            "• ориентир по сроку заезда и бюджету",
            reply_markup=get_start_faq_keyboard(),
            parse_mode='Markdown'
        )
        return RESULT

    elif text == "🚪 Как быстро начать ремонт?":
        await update.message.reply_text(
            "🚪 **Как быстро начать ремонт?**\n\n"
            "Зависит от загрузки и готовности проекта/ТЗ.\n\n"
            "На созвоне/замере скажем ближайшие окна старта.",
            reply_markup=get_start_faq_keyboard(),
            parse_mode='Markdown'
        )
        return RESULT

    # Кому не подойдём
    elif text == "🚫 Кому вы не подойдёте?":
        await update.message.reply_text(
            "🚫 **Кому мы не подойдём**\n\n"
            "Мы не подойдём, если:\n\n"
            "• метраж меньше 40 м²\n"
            "• нужен частичный ремонт\n"
            "• объект не в Ростове/Аксае/Батайске",
            reply_markup=get_faq_categories_keyboard(),
            parse_mode='Markdown'
        )
        return RESULT

    # Свой вопрос
    elif text == "❓ Задать свой вопрос":
        await update.message.reply_text(
            "❓ **Задайте свой вопрос** \n\n"
            "Напишите ваш вопрос в ответном сообщении, и мы обязательно ответим вам 👇",
            reply_markup=ReplyKeyboardRemove()
        )
        context.user_data['waiting_for_question'] = True
        # ВАЖНО: переходим в состояние 999
        return 999

    # Назад в категории
    elif text == "🔙 Назад в категории":
        await update.message.reply_text(
            "❓ Часто задаваемые вопросы \n\n"
            "Выберите категорию вопросов:",
            reply_markup=get_faq_categories_keyboard(),
            parse_mode='Markdown'
        )
        return RESULT

    # Назад в меню
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
        return RESULT

    return RESULT


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
        'secondary_options': "Не указано",  # Добавлено
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

    # НЕ выходим из диалога, а возвращаемся в RESULT
    await update.message.reply_text(
        "Чем еще могу помочь?",
        reply_markup=get_final_keyboard()
    )
    return RESULT


# ================== ОБРАБОТЧИК ВОПРОСОВ ==================

async def waiting_question_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка состояния ожидания вопроса"""
    user = update.effective_user
    text = update.message.text

    # Логируем для отладки
    logger.info(
        f"waiting_question_handler: '{text}', waiting_for_question={context.user_data.get('waiting_for_question')}")

    # ===== 1. ПРОВЕРЯЕМ, ЖДЕМ ЛИ МЫ ВОПРОС =====
    if context.user_data.get('waiting_for_question'):
        # Это вопрос менеджеру
        context.user_data['waiting_for_question'] = False

        # Отправляем вопрос менеджеру
        await notify_manager_question(context, user, text)

        # Отправляем подтверждение пользователю
        await update.message.reply_text(
            "✅ **Ваш вопрос получен и передан менеджеру!**\n\n"
            "Ответ придет в ближайшее время.",
            parse_mode='Markdown'
        )

        # Возвращаем в меню
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

        return RESULT

    # ===== 2. ЕСЛИ НЕ ЖДЕМ ВОПРОС - ЭТО НАВИГАЦИЯ ПО FAQ =====

    # Категории FAQ
    if text == "💰 Бюджет и смета":
        await update.message.reply_text(
            "💰 **Вопросы по бюджету и смете**\n\n"
            "Выберите интересующий вопрос:",
            reply_markup=get_budget_faq_keyboard(),
            parse_mode='Markdown'
        )
        return 999

    elif text == "⏳ Сроки ремонта":
        await update.message.reply_text(
            "⏳ **Вопросы по срокам ремонта**\n\n"
            "Выберите интересующий вопрос:",
            reply_markup=get_timing_faq_keyboard(),
            parse_mode='Markdown'
        )
        return 999

    elif text == "🧱 Объем работ":
        await update.message.reply_text(
            "🧱 **Вопросы по объему работ**\n\n"
            "Выберите интересующий вопрос:",
            reply_markup=get_scope_faq_keyboard(),
            parse_mode='Markdown'
        )
        return 999

    elif text == "🎨 Дизайн-проект":
        await update.message.reply_text(
            "🎨 **Вопросы по дизайн-проекту**\n\n"
            "Выберите интересующий вопрос:",
            reply_markup=get_design_faq_keyboard(),
            parse_mode='Markdown'
        )
        return 999

    elif text == "🧰 Материалы":
        await update.message.reply_text(
            "🧰 **Вопросы по материалам**\n\n"
            "Выберите интересующий вопрос:",
            reply_markup=get_materials_faq_keyboard(),
            parse_mode='Markdown'
        )
        return 999

    elif text == "📸 Контроль и отчетность":
        await update.message.reply_text(
            "📸 **Вопросы по контролю и отчетности**\n\n"
            "Выберите интересующий вопрос:",
            reply_markup=get_control_faq_keyboard(),
            parse_mode='Markdown'
        )
        return 999

    elif text == "📄 Договор и гарантии":
        await update.message.reply_text(
            "📄 **Вопросы по договору и гарантиям**\n\n"
            "Выберите интересующий вопрос:",
            reply_markup=get_contract_faq_keyboard(),
            parse_mode='Markdown'
        )
        return 999

    elif text == "🚪 Начало ремонта":
        await update.message.reply_text(
            "🚪 **Вопросы по началу ремонта**\n\n"
            "Выберите интересующий вопрос:",
            reply_markup=get_start_faq_keyboard(),
            parse_mode='Markdown'
        )
        return 999

    # Конкретные вопросы по бюджету
    elif text == "💸 Смета может вырасти в процессе?":
        await update.message.reply_text(
            "💸 **Смета может вырасти в процессе?**\n\n"
            "Может измениться только если меняется объём работ или Ваши решения.\n\n"
            "Мы делаем так: любые изменения согласуем заранее, до выполнения, чтобы не было сюрпризов “в конце”.",
            reply_markup=get_budget_faq_keyboard(),
            parse_mode='Markdown'
        )
        return 999

    elif text == "💸 Почему нельзя назвать цену без замера?":
        await update.message.reply_text(
            "💸 **Почему нельзя назвать цену без замера?**\n\n"
            "Потому что “на глаз” в ремонте чаще всего = ошибка и потом переделки/доплаты.\n\n"
            "Замер нужен, чтобы зафиксировать объём работ, пожелания и нюансы квартиры.",
            reply_markup=get_budget_faq_keyboard(),
            parse_mode='Markdown'
        )
        return 999

    elif text == "💸 У вас есть цена за м²?":
        await update.message.reply_text(
            "💸 **У вас есть цена за м²?**\n\n"
            "У нас расчёт индивидуальный, потому что на стоимость влияет состояние квартиры, инженерия и Ваши пожелания.",
            reply_markup=get_budget_faq_keyboard(),
            parse_mode='Markdown'
        )
        return 999

    # Вопросы по срокам
    elif text == "⏳ Сколько длится ремонт под ключ?":
        await update.message.reply_text(
            "⏳ **Сколько длится ремонт под ключ?**\n\n"
            "В среднем 3–4 месяца, но точный срок зависит от метража, состояния квартиры и сложности проекта.",
            reply_markup=get_timing_faq_keyboard(),
            parse_mode='Markdown'
        )
        return 999

    elif text == "⏳ Как вы контролируете сроки?":
        await update.message.reply_text(
            "⏳ **Как вы контролируете сроки?**\n\n"
            "Мы ведём ремонт по этапам и ежедневно фиксируем прогресс.\n\n"
            "Плюс даём понятную последовательность работ, чтобы не было хаоса.",
            reply_markup=get_timing_faq_keyboard(),
            parse_mode='Markdown'
        )
        return 999

    # Вопросы по объему работ
    elif text == "🧱 Что входит в ремонт под ключ?":
        await update.message.reply_text(
            "🧱 **Что входит в ремонт под ключ?**\n\n"
            "Это полный цикл работ: черновые + чистовые работы, инженерка (электрика/сантехника), отделка.",
            reply_markup=get_scope_faq_keyboard(),
            parse_mode='Markdown'
        )
        return 999

    elif text == "🧱 Вы делаете частичный ремонт?":
        await update.message.reply_text(
            "🧱 **Вы делаете частичный ремонт?**\n\n"
            "Нет. Мы берём только полный ремонт квартиры под ключ.\n\n"
            "Так мы отвечаем за результат и сроки, без зависимости от чужих работ.",
            reply_markup=get_scope_faq_keyboard(),
            parse_mode='Markdown'
        )
        return 999

    # Вопросы по дизайну
    elif text == "🎨 Дизайн-проект входит?":
        await update.message.reply_text(
            "🎨 **Дизайн-проект входит?**\n\n"
            "Да, дизайн-проект входит (обсуждаем на старте).\n\n"
            "Это снижает переделки и помогает заранее продумать свет, розетки, функциональность.",
            reply_markup=get_design_faq_keyboard(),
            parse_mode='Markdown'
        )
        return 999

    elif text == "🎨 Если у нас есть дизайн-проект?":
        await update.message.reply_text(
            "🎨 **Если у нас есть дизайн-проект?**\n\n"
            "Да, конечно. Мы посмотрим проект, уточним нюансы на замере и дальше работаем по нему.",
            reply_markup=get_design_faq_keyboard(),
            parse_mode='Markdown'
        )
        return 999

    # Вопросы по материалам
    elif text == "🧰 Кто закупает материалы?":
        await update.message.reply_text(
            "🧰 **Кто закупает материалы?**\n\n"
            "Обычно материалы закупаем мы — так проще по логистике и срокам.\n\n"
            "Но если Вам спокойнее — Вы можете закупать сами или частично.",
            reply_markup=get_materials_faq_keyboard(),
            parse_mode='Markdown'
        )
        return 999

    elif text == "🧰 Можно выбрать материалы с вами?":
        await update.message.reply_text(
            "🧰 **Можно выбрать материалы с вами?**\n\n"
            "Да. Мы помогаем подобрать материалы под Ваш бюджет и задачи, чтобы не переплачивать и не ошибаться.",
            reply_markup=get_materials_faq_keyboard(),
            parse_mode='Markdown'
        )
        return 999

    # Вопросы по контролю
    elif text == "📸 Как увидеть что работы идут?":
        await update.message.reply_text(
            "📸 **Как увидеть что работы идут?**\n\n"
            "Вы будете видеть прогресс: фото/видео с объектов + отчётность по этапам.\n\n"
            "Никакой “мы работали, но показать нечего”.",
            reply_markup=get_control_faq_keyboard(),
            parse_mode='Markdown'
        )
        return 999

    elif text == "📸 Можно посмотреть ваши объекты?":
        await update.message.reply_text(
            "📸 **Можно посмотреть ваши объекты?**\n\n"
            "Да, по согласованию можем показать реальные объекты (в процессе или готовые).",
            reply_markup=get_control_faq_keyboard(),
            parse_mode='Markdown'
        )
        return 999

    # Вопросы по договору
    elif text == "📄 Вы работаете по договору?":
        await update.message.reply_text(
            "📄 **Вы работаете по договору?**\n\n"
            "Да, работаем по договору на юрлицо.\n\n"
            "Это фиксирует обязательства, условия и порядок работ.",
            reply_markup=get_contract_faq_keyboard(),
            parse_mode='Markdown'
        )
        return 999

    elif text == "📄 Какая гарантия?":
        await update.message.reply_text(
            "📄 **Какая гарантия?**\n\n"
            "Гарантия прописывается в договоре.\n\n"
            "На замере/созвоне менеджер пояснит сроки и что именно покрывает гарантия.",
            reply_markup=get_contract_faq_keyboard(),
            parse_mode='Markdown'
        )
        return 999

    elif text == "👷 Кто делает ремонт?":
        await update.message.reply_text(
            "👷 **Кто делает ремонт?**\n\n"
            "Работает наша бригада под руководством прораба.\n\n"
            "Ответственность не “размывается” между разными исполнителями.",
            reply_markup=get_contract_faq_keyboard(),
            parse_mode='Markdown'
        )
        return 999

    # Вопросы по началу
    elif text == "🚪 Замер платный?":
        await update.message.reply_text(
            "🚪 **Замер платный?**\n\n"
            "Нет, замер бесплатный.",
            reply_markup=get_start_faq_keyboard(),
            parse_mode='Markdown'
        )
        return 999

    elif text == "🚪 Что подготовить к замеру?":
        await update.message.reply_text(
            "🚪 **Что подготовить к замеру?**\n\n"
            "• планировку/план БТИ (фото или файл)\n"
            "• 2–3 примера “как нравится” (скриншоты)\n"
            "• ориентир по сроку заезда и бюджету",
            reply_markup=get_start_faq_keyboard(),
            parse_mode='Markdown'
        )
        return 999

    elif text == "🚪 Как быстро начать ремонт?":
        await update.message.reply_text(
            "🚪 **Как быстро начать ремонт?**\n\n"
            "Зависит от загрузки и готовности проекта/ТЗ.\n\n"
            "На созвоне/замере скажем ближайшие окна старта.",
            reply_markup=get_start_faq_keyboard(),
            parse_mode='Markdown'
        )
        return 999

    elif text == "🚫 Кому вы не подойдёте?":
        await update.message.reply_text(
            "🚫 **Кому мы не подойдём**\n\n"
            "Мы не подойдём, если:\n\n"
            "• метраж меньше 40 м²\n"
            "• нужен частичный ремонт\n"
            "• объект не в Ростове/Аксае/Батайске",
            reply_markup=get_faq_categories_keyboard(),
            parse_mode='Markdown'
        )
        return 999

    # ===== 3. НАВИГАЦИОННЫЕ КНОПКИ =====
    elif text == "❓ Задать свой вопрос":
        await update.message.reply_text(
            "❓ **Задайте свой вопрос** \n\n"
            "Напишите ваш вопрос в ответном сообщении, и мы обязательно ответим вам 👇",
            reply_markup=ReplyKeyboardRemove()
        )
        context.user_data['waiting_for_question'] = True
        return 999

    elif text == "🔙 Назад в категории":
        await update.message.reply_text(
            "❓ Часто задаваемые вопросы \n\n"
            "Выберите категорию вопросов:",
            reply_markup=get_faq_categories_keyboard(),
            parse_mode='Markdown'
        )
        return 999

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
        return RESULT

    # ===== 4. ОБРАБОТКА "НАЧАТЬ ЗАНОВО" =====
    elif text == "🔄 Начать заново":
        return await start(update, context)

    # ===== 5. ОБРАБОТКА ЗАПИСИ НА ЗАМЕР =====
    elif text == "✅ Записаться на бесплатный замер":
        return await final_choice_handler(update, context)

    # ===== 6. ОБРАБОТКА "❓У вас есть вопрос" =====
    elif text == "❓У вас есть вопрос":
        await update.message.reply_text(
            "❓ Часто задаваемые вопросы \n\n"
            "Выберите категорию вопросов:",
            reply_markup=get_faq_categories_keyboard(),
            parse_mode='Markdown'
        )
        return 999

    # ===== 7. ОБРАБОТКА "👀 Посмотреть примеры работ" =====
    elif text == "👀 Посмотреть примеры работ":
        await update.message.reply_text(
            "👀 Примеры наших работ:\n\n"
            "Наш Telegram-канал: https://t.me/remontkvartirRND61\n\n"
            "Там вы найдете:\n"
            "• Фото готовых объектов\n"
            "• Видео процессов\n"
            "• Отзывы клиентов\n"
            "• Идеи для ремонта",
            disable_web_page_preview=False
        )
        # Сразу возвращаемся к выбору
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
        return RESULT

    # ===== 8. ЕСЛИ НИЧЕГО НЕ ПОДОШЛО - ВОЗВРАЩАЕМСЯ В МЕНЮ =====
    else:
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
        return RESULT


# ================== УВЕДОМЛЕНИЯ МЕНЕДЖЕРА ==================

async def notify_manager(context, lead_data):
    """Уведомление менеджера о новой заявке"""
    # Добавляем информацию об опциях вторички, если есть
    secondary_info = ""
    if lead_data.get('secondary_options') and lead_data['secondary_options'] != "Не указано":
        secondary_info = f"🔨 **Опции вторички:** {lead_data['secondary_options']}\n"

    message = (
        f"🔔 **НОВАЯ ЗАЯВКА** 🔔\n\n"
        f"👤 **Имя:** {lead_data['name']}\n"
        f"📞 **Телефон:** {lead_data['phone']}\n"
        f"🏙 **Город:** {lead_data.get('geography', 'Не указан')}\n"
        f"🏠 **Тип объекта:** {lead_data.get('object_type', 'Не указан')}\n"
        f"{secondary_info}"
        f"🛁 **Состояние:** {lead_data.get('condition', 'Не указано')}\n"
        f"📐 **Метраж:** {lead_data.get('metrage', 0)} м²\n"
        f"🔨 **Формат ремонта:** {lead_data.get('repair_format', 'Не указан')}\n"
        f"🔑 **Ключи:** {lead_data.get('keys_ready', 'Не указано')}\n"
        f"📅 **Заезд:** {lead_data.get('deadline', 'Не указан')}\n"
        f"😟 **Страх:** {lead_data.get('main_fear', 'Не указан')}\n"
        f"💰 **Бюджет:** {lead_data.get('budget', 'Не указан')}\n"
        f"⏰ **Время:** {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    )

    for admin_id in MANAGER_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=message,
                parse_mode='Markdown'
            )
            logger.info(f"✅ Уведомление отправлено менеджеру {admin_id}")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось отправить менеджеру {admin_id}: {e}")


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

    for admin_id in MANAGER_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=message,
                parse_mode='Markdown'
            )
            logger.info(f"✅ Вопрос отправлен менеджеру {admin_id}")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось отправить вопрос менеджеру {admin_id}: {e}")


# ================== РАССЫЛКИ ==================

async def send_broadcast_first(app):
    """Отправка первой рассылки (фото с подписью)"""
    global broadcast_first_sent

    if broadcast_first_sent:
        return

    users = db.get_all_users_without_survey()

    if not users:
        broadcast_first_sent = True
        return

    FIRST_PHOTO_PATH = MEDIA_DIR / "broadcast_first.jpg"

    if not FIRST_PHOTO_PATH.exists():
        logger.error(f"❌ Фото для первой рассылки не найдено")
        broadcast_first_sent = True
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
            logger.error(f"Ошибка рассылки пользователю {user_id}: {e}")

    logger.info(f"✅ Первая рассылка. Отправлено: {success_count}")
    broadcast_first_sent = True


async def send_broadcast_second(app):
    """Отправка второй рассылки (файл с подписью)"""
    global broadcast_second_sent

    if broadcast_second_sent:
        return

    users = db.get_all_users_without_survey()

    if not users:
        broadcast_second_sent = True
        return

    SECOND_FILE_PATH = MEDIA_DIR / "broadcast_second.pdf"

    if not SECOND_FILE_PATH.exists():
        logger.error(f"❌ Файл для второй рассылки не найден")
        broadcast_second_sent = True
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
            logger.error(f"Ошибка рассылки пользователю {user_id}: {e}")

    logger.info(f"✅ Вторая рассылка. Отправлено: {success_count}")
    broadcast_second_sent = True


def broadcast_scheduler(app):
    """Планировщик рассылок"""
    logger.info("🚀 Планировщик рассылок запущен")

    start_time = datetime.now()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    while True:
        try:
            now = datetime.now()
            minutes_passed = (now - start_time).total_seconds() / 60

            if not broadcast_first_sent and minutes_passed >= config.AUTO_MESSAGE_DELAYS['first']:
                logger.info("📸 Запуск первой рассылки")
                loop.run_until_complete(send_broadcast_first(app))

            if not broadcast_second_sent and minutes_passed >= config.AUTO_MESSAGE_DELAYS['second']:
                logger.info("📎 Запуск второй рассылки")
                loop.run_until_complete(send_broadcast_second(app))

            if broadcast_first_sent and broadcast_second_sent:
                logger.info("✅ Все рассылки выполнены")

            time.sleep(60)

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
    # Возвращаемся в RESULT, а не завершаем диалог
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
    return RESULT


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
        await query.message.delete()

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

def main():
    """Главная функция"""
    application = Application.builder().token(config.BOT_TOKEN).build()

    # Создаем обработчик диалога
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start),
            MessageHandler(filters.Regex('^(✅ Начать тест)$'), handle_start_choice),
            MessageHandler(filters.Regex('^(📞 Сразу записаться на бесплатный замер)$'), handle_start_choice)
        ],
        states={
            GEOGRAPHY: [MessageHandler(filters.TEXT & ~filters.COMMAND, geography_handler)],
            OBJECT_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, object_type_handler)],
            SECONDARY_OPTIONS: [MessageHandler(filters.TEXT & ~filters.COMMAND, secondary_options_handler)],
            CONDITION: [MessageHandler(filters.TEXT & ~filters.COMMAND, condition_handler)],
            METRAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, metrage_handler)],
            REPAIR_FORMAT: [MessageHandler(filters.TEXT & ~filters.COMMAND, repair_format_handler)],
            KEYS_READY: [MessageHandler(filters.TEXT & ~filters.COMMAND, keys_ready_handler)],
            DEADLINE: [MessageHandler(filters.TEXT & ~filters.COMMAND, deadline_handler)],
            MAIN_FEAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, main_fear_handler)],
            BUDGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, budget_handler)],
            RESULT: [MessageHandler(filters.TEXT & ~filters.COMMAND, final_choice_handler)],
            999: [MessageHandler(filters.TEXT & ~filters.COMMAND, waiting_question_handler)],
            CONTACT: [MessageHandler(filters.CONTACT, contact_handler)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        per_message=False,
        per_chat=True,
        per_user=True,
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(CallbackQueryHandler(inline_callback_handler))

    # Планировщик рассылок
    thread = threading.Thread(target=broadcast_scheduler, args=(application,), daemon=True)
    thread.start()

    print("=" * 70)
    print("🚀 БОТ ДЛЯ ЗАПИСИ НА ЗАМЕР ЗАПУЩЕН!")
    print("=" * 70)
    print(f"📱 Менеджеры ID: {MANAGER_IDS}")
    print(f"📸 Первая рассылка через: {config.AUTO_MESSAGE_DELAYS['first']} мин")
    print(f"📎 Вторая рассылка через: {config.AUTO_MESSAGE_DELAYS['second']} мин")
    print("🛑 Нажмите Ctrl+C для остановки")
    print("=" * 70)

    application.run_polling()


if __name__ == '__main__':
    main()