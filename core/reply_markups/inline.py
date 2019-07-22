from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup
)

from core.strings import LANGUAGE_MAPPING
from core.reply_markups.callbacks import *

available_languages = InlineKeyboardMarkup()
available_languages.add(
    *list(
        InlineKeyboardButton(
            lang_name, callback_data=language_callback.new(user_locale=lang)
        ) for lang, lang_name in LANGUAGE_MAPPING.items()
    )
)


campus_numbers = InlineKeyboardMarkup(row_width=2)
campus_numbers.add(
    *list(
        InlineKeyboardButton(
            str(i), callback_data=choose_campus_number.new(number=i)
        ) for i in range(1, 5)
    )
)

__all__ = [
    'available_languages',
    'campus_numbers'
]
