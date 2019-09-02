from aiogram.dispatcher.filters.state import State, StatesGroup


class ChooseLanguageDialog(StatesGroup):
    enter_language_callback = State()
