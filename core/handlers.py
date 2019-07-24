import asyncio
import datetime
import logging
import sys
from typing import Optional, Dict

from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.utils.exceptions import TelegramAPIError
from apscheduler.jobstores.redis import RedisJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from inline_timepicker.inline_timepicker import InlineTimepicker
from loguru import logger

import core.reply_markups as markups
from core import strings
from core.configs import telegram, database, consts
from core.database import db_worker as db
from core.database.models import user_model
from core.reply_markups.callbacks.language_choice import language_callback
from core.reply_markups.inline import available_languages as available_languages_markup
from core.strings.scripts import _
from core.utils import decorators
from core.utils.middlewares import (
    update_middleware,
    logger_middleware
)
from core.utils.states import (
    MailingEveryoneDialog,
    SetCleaningReminderStates,
    OffCleaningReminderStates,
)

logging.basicConfig(format="[%(asctime)s] %(levelname)s : %(name)s : %(message)s",
                    level=logging.INFO, datefmt="%Y-%m-%d at %H:%M:%S")

logger.remove()
logger.add(consts.LOGS_FOLDER / "debug_logs.log", format="[{time:YYYY-MM-DD at HH:mm:ss}] {level}: {name} : {message}",
           level=logging.DEBUG,
           colorize=False)

logger.add(consts.LOGS_FOLDER / "info_logs.log", format="[{time:YYYY-MM-DD at HH:mm:ss}] {level}: {name} : {message}",
           level=logging.INFO,
           colorize=False)

logger.add(consts.LOGS_FOLDER / "warn_logs.log", format="[{time:YYYY-MM-DD at HH:mm:ss}] {level}: {name} : {message}",
           level=logging.WARNING,
           colorize=False)
logger.add(sys.stderr, format="[{time:YYYY-MM-DD at HH:mm:ss}] {level}: {name} : {message}", level=logging.INFO,
           colorize=False)

logging.getLogger('aiogram').setLevel(logging.INFO)

loop = asyncio.get_event_loop()
bot = Bot(telegram.BOT_TOKEN, loop=loop, parse_mode=types.ParseMode.HTML)
dp = Dispatcher(bot, storage=MemoryStorage())

# additional helpers
scheduler = AsyncIOScheduler(timezone=consts.default_timezone, coalesce=True, misfire_grace_time=10000)
scheduler.add_jobstore(RedisJobStore(db=1,
                                     host=database.REDIS_HOST,
                                     port=database.REDIS_PORT))
scheduler.start()

inline_timepicker = InlineTimepicker()


@dp.message_handler(state='*', commands=['cancel'])
@dp.message_handler(lambda msg: msg.text.lower() == 'cancel', state='*')
async def cancel_handler(msg: types.Message, state: FSMContext, raw_state: Optional[str] = None):
    await state.finish()
    await bot.send_message(msg.from_user.id, _("cancel"))


@dp.message_handler(commands=['start'], state='*')
async def start_command_handler(msg: types.Message):
    await bot.send_message(msg.chat.id, _("start_cmd_text"))


@dp.message_handler(commands=['help'], state='*')
async def help_command_handler(msg: types.Message):
    user = await db.get_user(chat_id=msg.from_user.id)
    await bot.send_message(msg.chat.id, _("help_cmd_text, formats: {name}").format(name=user.first_name))


@dp.message_handler(commands='language', state='*')
async def language_cmd_handler(msg: types.Message):
    await bot.send_message(msg.from_user.id,
                           text=_("choose language"),
                           reply_markup=available_languages_markup)


@dp.callback_query_handler(language_callback.filter())
async def language_choice_handler(query: types.CallbackQuery, callback_data: dict):
    await query.answer()
    await db.update_user(query.from_user.id,
                         locale=callback_data['user_locale'])
    from core.strings.scripts import i18n
    i18n.ctx_locale.set(callback_data['user_locale'])

    await bot.send_message(query.from_user.id,
                           _("language is set"))


@dp.message_handler(commands='on', state='*')
async def on_cleaning_reminder(msg: types.Message):
    await msg.answer(_("choose_campus"),
                     reply_markup=markups.inline.campus_numbers)
    await SetCleaningReminderStates.enter_campus_number.set()


@dp.callback_query_handler(markups.callbacks.choose_campus_number.filter(),
                           state=SetCleaningReminderStates.enter_campus_number)
async def set_campus_number_cb_handler(query: types.CallbackQuery,
                                       state: FSMContext,
                                       callback_data: Dict[str, str]):
    await query.answer()
    await query.message.delete()
    async with state.proxy() as proxy:
        proxy['campus_number_set_reminder'] = callback_data['number']

    inline_timepicker.init(
        base_time=datetime.time(12, 0),
        min_time=datetime.time(0, 15),
        max_time=datetime.time(23, 45)
    )

    await bot.send_message(query.from_user.id,
                           _("choose_cleaning_reminder_time"),
                           reply_markup=inline_timepicker.get_keyboard())
    await SetCleaningReminderStates.enter_time.set()


async def personal_reminder_about_cleaning(chat_id, campus_number):
    from core.strings.scripts import i18n
    try:
        await bot.send_message(chat_id, _("personal_reminder_cleaning, formats: number",
                                          locale=await i18n.get_user_locale(None, None, user_id=chat_id))
                               .format(number=campus_number))
    except TelegramAPIError:
        pass


def set_cleaning_reminder(chat_id: int, campus_number: int, time: datetime.time):
    if not isinstance(campus_number, int):
        campus_number = int(campus_number)
    for i in range(0, 4):
        base_data = consts.base_dates_campus_cleaning[campus_number][i]
        if base_data:
            run_time = datetime.datetime(year=base_data.year,
                                         month=base_data.month,
                                         day=base_data.day,
                                         hour=time.hour,
                                         minute=time.minute)

            scheduler.add_job(
                personal_reminder_about_cleaning, "interval",
                weeks=4, args=[chat_id, campus_number], next_run_time=run_time,
                id=consts.job_id_format.format(
                    chat_id=chat_id, campus_number=campus_number, index=i
                ), replace_existing=True
            )


@dp.callback_query_handler(inline_timepicker.filter(),
                           state=SetCleaningReminderStates.enter_time)
async def set_cleaning_reminder_time(query: types.CallbackQuery,
                                     state: FSMContext,
                                     callback_data: Dict[str, str]):
    await query.answer()
    reminder_time = inline_timepicker.handle(query.from_user.id, callback_data)
    if reminder_time:
        async with state.proxy() as proxy:
            loop.run_in_executor(None,
                                 set_cleaning_reminder,
                                 query.from_user.id,
                                 proxy['campus_number_set_reminder'],
                                 reminder_time
                                 )

        await bot.send_message(query.from_user.id,
                               _("cleaning_reminder_set"))

    else:
        await bot.edit_message_reply_markup(
            query.from_user.id,
            message_id=query.message.message_id,
            reply_markup=inline_timepicker.get_keyboard()
        )


@dp.message_handler(commands='off', state='*')
async def off_cleaning_reminder_command_handler(msg: types.Message):
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    campus_set = set()
    for campus in range(1, 5):
        for ind in range(0, 4):
            if scheduler.get_job(consts.job_id_format.format(
                chat_id=msg.from_user.id, campus_number=campus, index=ind
            )):
                campus_set.add(str(campus))

    if campus_set:
        campus_set = sorted(campus_set)

        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            *list(
                InlineKeyboardButton(str(campus),
                                     callback_data=
                                     markups.callbacks.choose_campus_number.new(number=campus))
                for campus in campus_set
            )
        )
        await msg.answer(_("choose_campus"), reply_markup=kb)
        await OffCleaningReminderStates.enter_campus_number.set()
    else:
        await msg.answer(_("no_reminders_set"))


@dp.callback_query_handler(markups.callbacks.choose_campus_number.filter(),
                            state=OffCleaningReminderStates.enter_campus_number)
async def off_cleaning_reminder_cb_handler(query: types.CallbackQuery,
                                           state: FSMContext,
                                           callback_data: Dict[str, str]):
    campus = int(callback_data['number'])
    for i in range(0, 4):
        if consts.base_dates_campus_cleaning[campus][i]:
            scheduler.remove_job(job_id=consts.job_id_format.format(
                chat_id=query.from_user.id, campus_number=campus, index=i
            ))

    await bot.edit_message_text(_("reminder_is_off"),
                                chat_id=query.from_user.id,
                                message_id=query.message.message_id)


@decorators.admin
@dp.message_handler(commands=['send_to_everyone'], state='*')
async def send_to_everyone_command_handler(msg: types.Message):
    await bot.send_message(msg.chat.id, _("mailing_everyone"))
    await MailingEveryoneDialog.first()


@dp.message_handler(state=MailingEveryoneDialog.enter_message)
async def mailing_everyone_handler(msg: types.Message):
    await bot.send_message(msg.chat.id, _("sent_to_everyone"))
    scheduler.add_job(send_to_everyone, args=[msg.text])


async def send_to_everyone(txt):
    for u in user_model.User.objects():
        try:
            await bot.send_message(u.chat_id, txt)
        except TelegramAPIError:
            pass
        await asyncio.sleep(.5)


def main():
    logger.info("Compile .po and .mo before running!")

    update_middleware.on_startup(dp)
    logger_middleware.on_startup(dp)
    strings.on_startup(dp)  # enable i18n
    executor.start_polling(dp)


if __name__ == '__main__':
    main()
