import logging

from aiogram.contrib.middlewares.i18n import I18nMiddleware
from aiogram import types, Dispatcher
from core.database.db_worker import get_user
from core.configs.locales import DEFAULT_USER_LOCALE, LANGUAGES
from typing import Tuple, Any


class ACLMiddleware(I18nMiddleware):
    def __init__(self, domain, path=None, default=DEFAULT_USER_LOCALE):

        super(ACLMiddleware, self).__init__(domain, path, default)
        self.cache = {}

    async def get_user_locale(
        self, action: str, args: Tuple[Any], user_id: int = None
    ) -> str:
        """
        Load user local from DB
        :param user_id:
        :param action:
        :param args:
        :return:
        """
        if user_id is not None:
            user = await get_user(user_id)
            return user.locale if user.locale else self.default

        tg_user = types.User.get_current()
        super_locale = await super().get_user_locale(action, args)
        user = await get_user(tg_user.id)

        if user.locale is not None:  # if user set his locale
            return user.locale
        else:
            if tg_user.locale in LANGUAGES:
                return tg_user.locale
            elif super_locale in LANGUAGES:
                return super_locale
            else:  # else, return default
                return DEFAULT_USER_LOCALE
