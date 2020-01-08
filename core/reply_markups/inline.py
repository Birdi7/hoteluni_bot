from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from core.reply_markups.callbacks import *
from core.strings import LANGUAGE_MAPPING

available_languages = InlineKeyboardMarkup()
available_languages.add(
    *list(
        InlineKeyboardButton(
            lang_name, callback_data=language_callback.new(user_locale=lang)
        )
        for lang, lang_name in LANGUAGE_MAPPING.items()
    )
)


campus_numbers = InlineKeyboardMarkup(row_width=2)
campus_numbers.add(
    *list(
        InlineKeyboardButton(str(i), callback_data=choose_campus_number.new(number=i))
        for i in range(1, 5)
    )
)


def get_set_is_day_before_kb():
    from core.strings.scripts import _

    set_is_day_before_kb = InlineKeyboardMarkup(row_width=1)
    set_is_day_before_kb.add(
        InlineKeyboardButton(
            _("is_day_before_inline_kb_false"),
            callback_data=set_is_day_before.new(value="1"),
        ),
        InlineKeyboardButton(
            _("is_day_before_inline_kb_true"),
            callback_data=set_is_day_before.new(value="0"),
        ),
    )
    return set_is_day_before_kb


__all__ = ["available_languages", "campus_numbers"]
