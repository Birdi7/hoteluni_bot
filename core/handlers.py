import asyncio
import datetime
import logging
import sys
from typing import Dict, Set

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
from core.configs import consts, database, telegram
from core.database import db_worker as db
from core.database.models import user_model
from core.reply_markups.callbacks.language_choice import language_callback
from core.reply_markups.inline import available_languages as available_languages_markup
from core.strings.scripts import _
from core.utils import decorators
from core.utils.middlewares import logger_middleware, update_middleware
from core.utils.states import (
    ChooseLanguageDialog,
    MailingEveryoneDialog,
    OffCleaningReminderStates,
    SetCleaningReminderStates,
)

logging.basicConfig(
    format="[%(asctime)s] %(levelname)s : %(name)s : %(message)s",
    level=logging.DEBUG,
    datefmt="%Y-%m-%d at %H:%M:%S",
)

logger.remove()
logger.add(
    consts.LOGS_FOLDER / "debug_logs.log",
    format="[{time:YYYY-MM-DD at HH:mm:ss}] {level}: {name} : {message}",
    level=logging.DEBUG,
    colorize=False,
)
logger.add(
    consts.LOGS_FOLDER / "info_logs.log",
    format="[{time:YYYY-MM-DD at HH:mm:ss}] {level}: {name} : {message}",
    level=logging.INFO,
    colorize=False,
)
logger.add(
    consts.LOGS_FOLDER / "warn_logs.log",
    format="[{time:YYYY-MM-DD at HH:mm:ss}] {level}: {name} : {message}",
    level=logging.WARNING,
    colorize=False,
)
logger.add(
    consts.LOGS_FOLDER / "error_logs.log",
    format="[{time:YYYY-MM-DD at HH:mm:ss}] {level}: {name} : {message}",
    level=logging.ERROR,
    colorize=False,
)
logger.add(
    sys.stdout,
    format="[{time:YYYY-MM-DD at HH:mm:ss}] {level}: {name} : {message}",
    level=logging.WARNING,
    colorize=False,
)

logging.getLogger("aiogram").setLevel(logging.INFO)

loop = asyncio.get_event_loop()
bot = Bot(telegram.BOT_TOKEN, loop=loop, parse_mode=types.ParseMode.HTML)

dp = Dispatcher(bot, storage=MemoryStorage())

# additional helpers
scheduler = AsyncIOScheduler(
    timezone=consts.default_timezone, coalesce=True, misfire_grace_time=10000
)
scheduler.add_jobstore(
    RedisJobStore(db=1, host=database.REDIS_HOST, port=database.REDIS_PORT)
)
scheduler.start()

inline_timepicker = InlineTimepicker()


@dp.message_handler(state="*", commands=["cancel"])
@dp.message_handler(lambda msg: msg.text.lower() == "cancel", state="*")
async def cancel_handler(msg: types.Message, state: FSMContext):
    await state.finish()
    await bot.send_message(msg.from_user.id, _("cancel"))


@dp.message_handler(commands=["start"], state="*")
async def start_command_handler(msg: types.Message):
    await bot.send_message(msg.chat.id, _("start_cmd_text"))


@dp.message_handler(commands=["help"], state="*")
async def help_command_handler(msg: types.Message):
    user = await db.get_user(chat_id=msg.from_user.id)
    await bot.send_message(
        msg.chat.id, _("help_cmd_text, formats: {name}").format(name=user.first_name)
    )

@dp.message_handler(commands=["peek"], state="*")
async def peek_command_handler(msg: types.Message):
    for job in scheduler.get_jobs():
        extra = 1 if job.id.endswith("day_before") else 0
        job_chat_id = job.args[0]
        if job_chat_id == msg.from_user.id:
            text = f'{_("remainder_is_scheduled")} {(job.next_run_time + datetime.timedelta(days=extra)).strftime("%d.%m.%Y (%A)")}'
            break
    else:
        text = _("remainder_is_not_scheduled")
    await bot.send_message(msg.chat.id, text)

@dp.message_handler(commands="language", state="*")
async def language_cmd_handler(msg: types.Message):
    await bot.send_message(
        msg.from_user.id,
        text=_("choose language"),
        reply_markup=available_languages_markup,
    )
    await ChooseLanguageDialog.enter_language_callback.set()


@dp.callback_query_handler(
    language_callback.filter(), state=ChooseLanguageDialog.enter_language_callback
)
async def language_choice_handler(
    query: types.CallbackQuery, state: FSMContext, callback_data: dict
):
    await query.answer()
    await db.update_user(query.from_user.id, locale=callback_data["user_locale"])
    from core.strings.scripts import i18n

    i18n.ctx_locale.set(callback_data["user_locale"])

    await bot.send_message(query.from_user.id, _("language is set"))
    await state.finish()


@dp.message_handler(commands="on", state="*")
async def on_cleaning_reminder(msg: types.Message):
    await msg.answer(
        _("set_is_day_before"), reply_markup=markups.inline.get_set_is_day_before_kb()
    )
    await SetCleaningReminderStates.set_is_day_before.set()


@dp.callback_query_handler(
    markups.callbacks.set_is_day_before.filter(),
    state=SetCleaningReminderStates.set_is_day_before,
)
async def set_is_day_before_cb_handler(
    query: types.CallbackQuery, state: FSMContext, callback_data: Dict[str, str]
):
    await query.answer()
    await query.message.delete()

    async with state.proxy() as proxy:
        proxy["is_day_before"] = callback_data.get("value") == "1"

    await bot.send_message(
        query.from_user.id,
        _("choose_campus"),
        reply_markup=markups.inline.campus_numbers,
    )

    await SetCleaningReminderStates.enter_campus_number.set()


@dp.callback_query_handler(
    markups.callbacks.choose_campus_number.filter(),
    state=SetCleaningReminderStates.enter_campus_number,
)
async def set_campus_number_cb_handler(
    query: types.CallbackQuery, state: FSMContext, callback_data: Dict[str, str]
):
    await query.answer()
    await query.message.delete()
    async with state.proxy() as proxy:
        proxy["campus_number_set_reminder"] = callback_data["number"]

    inline_timepicker.init(
        base_time=datetime.time(12, 0),
        min_time=datetime.time(0, 15),
        max_time=datetime.time(23, 45),
    )

    await bot.send_message(
        query.from_user.id,
        _("choose_cleaning_reminder_time"),
        reply_markup=inline_timepicker.get_keyboard(),
    )
    await SetCleaningReminderStates.enter_time.set()


async def personal_reminder_about_cleaning(
    chat_id, campus_number, is_day_before: bool = False
):
    from core.strings.scripts import i18n

    if is_day_before:
        text = _(
            "personal_reminder_cleaning_day_before",
            locale=await i18n.get_user_locale(None, None, user_id=chat_id),
        )
    else:
        text = _(
            "personal_reminder_cleaning, formats: number",
            locale=await i18n.get_user_locale(None, None, user_id=chat_id),
        )

    try:
        await bot.send_message(chat_id, text.format(number=campus_number))
    except TelegramAPIError as e:
        logger.exception(
            f"TelegramAPIError while sending reminder({chat_id}, {campus_number})"
            f"message={text}, locale={await i18n.get_user_locale(None, None, user_id=chat_id)}"
            f": {e}"
        )

        if is_day_before:
            await bot.send_message(
                chat_id, f"Завтра уборка в кампусе <b>{campus_number}</b>"
            )
        else:
            await bot.send_message(
                chat_id, f"Сегодня уборка в кампусе <b>{campus_number}</b>"
            )


def set_cleaning_reminder(
    chat_id: int, campus_number: int, time: datetime.time, is_day_before: bool
):
    if not isinstance(campus_number, int):
        campus_number = int(campus_number)
    for i in range(0, 4):
        base_data = consts.base_dates_campus_cleaning[campus_number][i]
        if base_data:
            run_time = datetime.datetime(
                year=base_data.year,
                month=base_data.month,
                day=base_data.day,
                hour=time.hour,
                minute=time.minute,
            )

            job_id = consts.job_id_format.format(
                chat_id=chat_id, campus_number=campus_number, index=i
            )

            if is_day_before:
                run_time -= datetime.timedelta(days=1)
                job_id += ":day_before"

            scheduler.add_job(
                personal_reminder_about_cleaning,
                "interval",
                weeks=4,
                args=[chat_id, campus_number, is_day_before],
                next_run_time=run_time,
                id=job_id,
                replace_existing=True,
            )


@dp.callback_query_handler(
    inline_timepicker.filter(), state=SetCleaningReminderStates.enter_time
)
async def set_cleaning_reminder_time_cb_handler(
    query: types.CallbackQuery, state: FSMContext, callback_data: Dict[str, str]
):
    await query.answer()
    reminder_time = inline_timepicker.handle(query.from_user.id, callback_data)
    if reminder_time:
        await bot.edit_message_text(
            _("cleaning_reminder_set"),
            chat_id=query.from_user.id,
            message_id=query.message.message_id,
        )

        async with state.proxy() as proxy:
            loop.run_in_executor(
                None,
                set_cleaning_reminder,
                query.from_user.id,
                proxy["campus_number_set_reminder"],
                reminder_time,
                proxy["is_day_before"],
            )
        await state.finish()
    else:
        await bot.edit_message_reply_markup(
            query.from_user.id,
            message_id=query.message.message_id,
            reply_markup=inline_timepicker.get_keyboard(),
        )


def _get_existing_reminder_at_the_day_of_cleaning(user_id) -> Set[str]:
    result = set()
    for campus in range(1, 5):
        for ind in range(0, 4):
            if scheduler.get_job(
                consts.job_id_format.format(
                    chat_id=user_id, campus_number=campus, index=ind
                )
            ):
                result.add(str(campus))
    return result


def _get_existing_reminder_day_before_the_cleaning(user_id) -> Set[str]:
    result = set()
    for campus in range(1, 5):
        for ind in range(0, 4):
            if scheduler.get_job(
                consts.job_id_format.format(
                    chat_id=user_id, campus_number=campus, index=ind
                )
                + ":day_before"
            ):
                result.add(str(campus))
    return result


@dp.message_handler(commands="off", state="*")
async def off_cleaning_reminder_command_handler(msg: types.Message, state: FSMContext):
    reminders_day_before = _get_existing_reminder_day_before_the_cleaning(
        msg.from_user.id
    )
    reminders_at_the_day = _get_existing_reminder_at_the_day_of_cleaning(
        msg.from_user.id
    )

    if not reminders_day_before and not reminders_at_the_day:
        await msg.answer(_("no_reminders_set"))
        return
    else:
        if reminders_at_the_day and reminders_day_before:
            await msg.answer(
                _("remove_set_is_day_before"),
                reply_markup=markups.inline.get_set_is_day_before_kb(),
            )
            await OffCleaningReminderStates.enter_is_day_before.set()
        else:
            async with state.proxy() as proxy:
                proxy["is_day_before"] = bool(reminders_day_before)
                await send_inline_kb_campus_numbers_to_remove_reminders(
                    msg.from_user.id, proxy["is_day_before"]
                )
            await OffCleaningReminderStates.enter_campus_number.set()


@dp.callback_query_handler(
    markups.callbacks.set_is_day_before.filter(),
    state=OffCleaningReminderStates.enter_is_day_before,
)
async def set_is_day_before_for_off_reminder_cb_handler(
    query: types.CallbackQuery, state, callback_data
):
    await query.answer()
    async with state.proxy() as proxy:
        proxy["is_day_before"] = callback_data.get("value") == "1"
        await send_inline_kb_campus_numbers_to_remove_reminders(
            query.from_user.id, proxy["is_day_before"]
        )
    await query.message.delete()
    await OffCleaningReminderStates.enter_campus_number.set()


async def send_inline_kb_campus_numbers_to_remove_reminders(user_id, is_day_before):
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    existing_reminder_campuses = (
        _get_existing_reminder_day_before_the_cleaning(user_id)
        if is_day_before
        else _get_existing_reminder_at_the_day_of_cleaning(user_id)
    )

    existing_reminder_campuses = sorted(existing_reminder_campuses)
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        *[
            InlineKeyboardButton(
                str(campus),
                callback_data=markups.callbacks.choose_campus_number.new(number=campus),
            )
            for campus in existing_reminder_campuses
        ]
    )
    await bot.send_message(user_id, _("choose_campus"), reply_markup=kb)


@dp.callback_query_handler(
    markups.callbacks.choose_campus_number.filter(),
    state=OffCleaningReminderStates.enter_campus_number,
)
async def off_cleaning_reminder_cb_handler(
    query: types.CallbackQuery, state: FSMContext, callback_data: Dict[str, str]
):
    async with state.proxy() as proxy:
        is_day_before = bool(proxy.get("is_day_before"))

    campus = int(callback_data["number"])
    for i in range(0, 4):
        if consts.base_dates_campus_cleaning[campus][i]:
            scheduler.remove_job(
                job_id=consts.job_id_format.format(
                    chat_id=query.from_user.id, campus_number=campus, index=i
                )
                + (":day_before" if is_day_before else "")
            )

    await bot.edit_message_text(
        _("reminder_is_off"),
        chat_id=query.from_user.id,
        message_id=query.message.message_id,
    )
    await state.finish()


@decorators.admin
@dp.message_handler(commands=["send_to_everyone"], state="*")
async def send_to_everyone_command_handler(msg: types.Message):
    await bot.send_message(msg.chat.id, _("mailing_everyone"))
    await MailingEveryoneDialog.first()


@dp.message_handler(state=MailingEveryoneDialog.enter_message)
async def mailing_everyone_handler(msg: types.Message, state: FSMContext):
    await bot.send_message(msg.chat.id, _("sent_to_everyone"))
    scheduler.add_job(send_to_everyone, args=[msg.text])
    await state.finish()


async def send_to_everyone(txt):
    for u in user_model.User.objects():
        try:
            await bot.send_message(u.chat_id, txt)
        except TelegramAPIError:
            pass
        await asyncio.sleep(0.5)


def main():
    logger.info(
        "Compile .po and .mo before running! Hint: pybabel compile -d locales -D bot"
    )

    update_middleware.on_startup(dp)
    logger_middleware.on_startup(dp)
    strings.on_startup(dp)  # enable i18n
    executor.start_polling(dp)


if __name__ == "__main__":
    main()
