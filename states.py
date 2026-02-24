from telegram.ext import ConversationHandler

# Состояния для опроса
(
    GEOGRAPHY,
    OBJECT_TYPE,
    SECONDARY_OPTIONS,
    CONDITION,
    METRAGE,
    REPAIR_FORMAT,
    KEYS_READY,
    DEADLINE,
    MAIN_FEAR,
    BUDGET,
    RESULT,
    CONTACT
) = range(12)