from telegram import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup

def get_start_keyboard():
    """Клавиатура для стартового сообщения"""
    keyboard = [
        ["✅ Начать тест"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_geography_keyboard():
    """Клавиатура для выбора города"""
    keyboard = [
        ["🏙 Ростов‑на‑Дону", "🏙 Аксай"],
        ["🏙 Батайск", "Другой город"],
        ["🔄 Начать заново"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_object_type_keyboard():
    """Клавиатура для типа объекта"""
    keyboard = [
        ["🌃 Новостройка", "🏚 Вторичка"],
        ["🏠 Дом/коттедж"],
        ["🔄 Начать заново"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_secondary_options_keyboard():
    """Клавиатура для дополнительных опций при выборе вторички"""
    keyboard = [
        ["🔨 Требуется демонтаж"],
        ["📐 Планируется перепланировка"],
        ["✅ Демонтаж проведен"],
        ["🔄 И демонтаж, и перепланировка"],
        ["🔙 Назад к типам объектов"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_condition_keyboard():
    """Клавиатура для состояния квартиры"""
    keyboard = [
        ["🧱 Бетон", "🧱 Предчистовая"],
        ["🏗 С отделкой от застройщика", "😕 Другое/не знаю"],
        ["🔄 Начать заново"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_repair_format_keyboard():
    """Клавиатура для формата ремонта"""
    keyboard = [
        ["💪 Ремонт под ключ (вся квартира)"],
        ["❗️ Частичный (комната/санузел/кухня)"],
        ["🫣 Переделка после \"мастеров\""],
        ["✔️ Пока выбираю/сравниваю"],
        ["🔄 Начать заново"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_keys_ready_keyboard():
    """Клавиатура для наличия ключей"""
    keyboard = [
        ["✔️ Да, ключи есть"],
        ["🌟 Будут в ближайший месяц"],
        ["😉 Будут через 2–3 месяца+"],
        ["💸 Пока просто прицениваюсь"],
        ["🔄 Начать заново"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_deadline_keyboard():
    """Клавиатура для дедлайна"""
    keyboard = [
        ["В ближайшие 2–3 месяца"],
        ["3–4 месяца"],
        ["5–6 месяцев"],
        ["Пока не знаю"],
        ["🔄 Начать заново"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_main_fear_keyboard():
    """Клавиатура для главной тревоги"""
    keyboard = [
        ["💸 Боюсь, что смета вырастет"],
        ["⏳ Боюсь, что сроки затянутся"],
        ["🧱 Боюсь, что сделают плохо/скрытые косяки"],
        ["😱 Всё сразу"],
        ["🔄 Начать заново"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_budget_keyboard():
    """Клавиатура для бюджета"""
    keyboard = [
        ["до 400 тыс"],
        ["400–600 тыс"],
        ["600–900 тыс"],
        ["900 тыс +"],
        ["Не знаю / как раз хочу разобраться"],
        ["🔄 Начать заново"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_final_choice_keyboard():
    """Клавиатура для финального выбора"""
    keyboard = [
        ["✅ Записаться на бесплатный замер"],
        ["❓У вас есть вопрос"],
        ["👀 Посмотреть примеры работ"],
        ["🔄 Начать заново"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_contact_keyboard():
    """Клавиатура для отправки контакта"""
    contact_button = KeyboardButton("📱 Отправить номер телефона", request_contact=True)
    keyboard = [
        [contact_button],
        ["🔄 Начать заново"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_final_keyboard():
    """Финальная клавиатура после отправки заявки"""
    keyboard = [
        ["❓У вас есть вопрос"],
        ["🔄 Начать заново"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_faq_categories_keyboard():
    """Клавиатура с категориями FAQ"""
    keyboard = [
        ["💰 Бюджет и смета"],
        ["⏳ Сроки ремонта"],
        ["🧱 Объем работ"],
        ["🎨 Дизайн-проект"],
        ["🧰 Материалы"],
        ["📸 Контроль и отчетность"],
        ["📄 Договор и гарантии"],
        ["🚪 Начало ремонта"],
        ["🚫 Кому вы не подойдёте?"],
        ["❓ Задать свой вопрос"],
        ["🔙 Назад в меню"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_budget_faq_keyboard():
    """Клавиатура для вопросов по бюджету"""
    keyboard = [
        ["💸 Смета может вырасти в процессе?"],
        ["💸 Почему нельзя назвать цену без замера?"],
        ["💸 У вас есть цена за м²?"],
        ["🔙 Назад в категории"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_timing_faq_keyboard():
    """Клавиатура для вопросов по срокам"""
    keyboard = [
        ["⏳ Сколько длится ремонт под ключ?"],
        ["⏳ Как вы контролируете сроки?"],
        ["🔙 Назад в категории"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_scope_faq_keyboard():
    """Клавиатура для вопросов по объему работ"""
    keyboard = [
        ["🧱 Что входит в ремонт под ключ?"],
        ["🧱 Вы делаете частичный ремонт?"],
        ["🔙 Назад в категории"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_design_faq_keyboard():
    """Клавиатура для вопросов по дизайну"""
    keyboard = [
        ["🎨 Дизайн-проект входит?"],
        ["🎨 Если у нас есть дизайн-проект?"],
        ["🔙 Назад в категории"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_materials_faq_keyboard():
    """Клавиатура для вопросов по материалам"""
    keyboard = [
        ["🧰 Кто закупает материалы?"],
        ["🧰 Можно выбрать материалы с вами?"],
        ["🔙 Назад в категории"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_control_faq_keyboard():
    """Клавиатура для вопросов по контролю"""
    keyboard = [
        ["📸 Как увидеть что работы идут?"],
        ["📸 Можно посмотреть ваши объекты?"],
        ["🔙 Назад в категории"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_contract_faq_keyboard():
    """Клавиатура для вопросов по договору"""
    keyboard = [
        ["📄 Вы работаете по договору?"],
        ["📄 Какая гарантия?"],
        ["👷 Кто делает ремонт?"],
        ["🔙 Назад в категории"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_start_faq_keyboard():
    """Клавиатура для вопросов по началу ремонта"""
    keyboard = [
        ["🚪 Замер платный?"],
        ["🚪 Что подготовить к замеру?"],
        ["🚪 Как быстро начать ремонт?"],
        ["🔙 Назад в категории"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_examples_inline_keyboard():
    """Inline клавиатура с кнопкой-ссылкой на канал"""
    keyboard = [
        [InlineKeyboardButton("📱 Перейти в Telegram-канал", url="https://t.me/remontkvartirRND61")],
        [InlineKeyboardButton("🔙 Вернуться в меню", callback_data="back_to_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)