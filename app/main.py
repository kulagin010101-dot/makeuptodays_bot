import asyncio
import json
from zoneinfo import ZoneInfo

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.client.default import DefaultBotProperties

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import get_settings
from .db import DB
from .logic import Answers, build_text
from .content import DAILY_TIPS


# ================= STATES =================

class Quiz(StatesGroup):
    skin = State()
    tone = State()
    undertone = State()
    eyes = State()
    occasion = State()


# ================= KEYBOARDS =================

def kb_start():
    kb = InlineKeyboardBuilder()
    kb.button(text="👉 Начать", callback_data="start_quiz")
    kb.adjust(1)
    return kb.as_markup()


def kb_skin():
    kb = InlineKeyboardBuilder()
    kb.button(text="Сухая", callback_data="skin:dry")
    kb.button(text="Нормальная", callback_data="skin:normal")
    kb.button(text="Комбинированная", callback_data="skin:combo")
    kb.button(text="Жирная", callback_data="skin:oily")
    kb.button(text="Не знаю 🤍", callback_data="skin:unknown")
    kb.adjust(2, 2, 1)
    return kb.as_markup()


def kb_tone():
    kb = InlineKeyboardBuilder()
    kb.button(text="Светлый", callback_data="tone:light")
    kb.button(text="Средний", callback_data="tone:medium")
    kb.button(text="Смуглый", callback_data="tone:tan")
    kb.adjust(2, 1)
    return kb.as_markup()


def kb_undertone():
    kb = InlineKeyboardBuilder()
    kb.button(text="Тёплый", callback_data="undertone:warm")
    kb.button(text="Холодный", callback_data="undertone:cool")
    kb.button(text="Не знаю", callback_data="undertone:unknown")
    kb.adjust(2, 1)
    return kb.as_markup()


def kb_eyes():
    kb = InlineKeyboardBuilder()
    kb.button(text="Маленькие", callback_data="eyes:small")
    kb.button(text="Большие", callback_data="eyes:big")
    kb.button(text="Нависшее веко", callback_data="eyes:hooded")
    kb.button(text="Миндалевидные", callback_data="eyes:almond")
    kb.adjust(2, 2)
    return kb.as_markup()


def kb_occasion():
    kb = InlineKeyboardBuilder()
    kb.button(text="Каждый день", callback_data="occ:daily")
    kb.button(text="Свидание", callback_data="occ:date")
    kb.button(text="Праздник", callback_data="occ:party")
    kb.button(text="Фото / видео", callback_data="occ:photo")
    kb.adjust(2, 2)
    return kb.as_markup()


def kb_result():
    kb = InlineKeyboardBuilder()
    kb.button(text="📌 Подробнее", callback_data="detail")
    kb.button(text="💾 Сохранить", callback_data="save")
    kb.button(text="💌 Получать советы", callback_data="tips_on")
    kb.button(text="🔁 Начать сначала", callback_data="restart")
    kb.adjust(1, 1, 1, 1)
    return kb.as_markup()


def kb_tips_confirm():
    kb = InlineKeyboardBuilder()
    kb.button(text="Да, хочу ✨", callback_data="tips_yes")
    kb.button(text="Не сейчас", callback_data="tips_no")
    kb.adjust(1, 1)
    return kb.as_markup()


# ================= DAILY TIPS =================

async def send_daily_tips(bot: Bot, db: DB):
    users = db.get_all_tips_enabled_users()
    for chat_id, idx in users:
        try:
            tip = DAILY_TIPS[idx % len(DAILY_TIPS)]
            await bot.send_message(chat_id, tip)
            db.advance_tip_index(chat_id, (idx + 1) % len(DAILY_TIPS))
        except Exception:
            continue


# ================= MAIN =================

async def main():
    settings = get_settings()

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode="Markdown")
    )

    dp = Dispatcher()
    db = DB(settings.db_path)
    db.init()

    # ----- Scheduler -----
    scheduler = AsyncIOScheduler(timezone=ZoneInfo(settings.tz))
    scheduler.add_job(
        send_daily_tips,
        trigger=CronTrigger(hour=settings.daily_hour, minute=settings.daily_minute),
        args=[bot, db],
        id="daily_tips",
        replace_existing=True
    )
    scheduler.start()

    # ================= HANDLERS =================

    @dp.message(CommandStart())
    async def start_cmd(message: Message):
        db.ensure_user(message.chat.id)
        await message.answer(
            "Привет 💄\n"
            "Я помогу подобрать макияж, который подойдёт **именно тебе**.\n"
            "Это займёт не больше **2 минут** ✨",
            reply_markup=kb_start()
        )

    @dp.message(Command("my"))
    async def my_cmd(message: Message):
        db.ensure_user(message.chat.id)
        last = db.get_last_result(message.chat.id)
        if not last:
            await message.answer("Пока нет сохранённого результата. Нажми /start 💄")
            return
        await message.answer("💾 **Твой сохранённый план:**\n\n" + last)

    @dp.message(Command("stop"))
    async def stop_cmd(message: Message):
        db.ensure_user(message.chat.id)
        db.set_tips(message.chat.id, False)
        await message.answer("Готово 🙂 Ежедневные советы отключены. Включить снова можно через «Получать советы».")

    # ===== Start quiz =====

    @dp.callback_query(F.data == "start_quiz")
    async def start_quiz(cb: CallbackQuery, state: FSMContext):
        db.ensure_user(cb.message.chat.id)
        await state.clear()
        await state.set_state(Quiz.skin)
        await cb.message.answer("Какая у тебя кожа?", reply_markup=kb_skin())
        await cb.answer()

    # ===== Restart quiz =====

    @dp.callback_query(F.data == "restart")
    async def restart_quiz(cb: CallbackQuery, state: FSMContext):
        db.ensure_user(cb.message.chat.id)
        await state.clear()
        await state.set_state(Quiz.skin)
        await cb.message.answer("Начнём заново 💄\nКакая у тебя кожа?", reply_markup=kb_skin())
        await cb.answer()

    @dp.callback_query(F.data.startswith("skin:"))
    async def on_skin(cb: CallbackQuery, state: FSMContext):
        await state.update_data(skin=cb.data.split(":")[1])
        await state.set_state(Quiz.tone)
        await cb.message.answer("Какой у тебя тон кожи?", reply_markup=kb_tone())
        await cb.answer()

    @dp.callback_query(F.data.startswith("tone:"))
    async def on_tone(cb: CallbackQuery, state: FSMContext):
        await state.update_data(tone=cb.data.split(":")[1])
        await state.set_state(Quiz.undertone)
        await cb.message.answer("Подтон кожи:", reply_markup=kb_undertone())
        await cb.answer()

    @dp.callback_query(F.data.startswith("undertone:"))
    async def on_undertone(cb: CallbackQuery, state: FSMContext):
        await state.update_data(undertone=cb.data.split(":")[1])
        await state.set_state(Quiz.eyes)
        await cb.message.answer("Форма глаз:", reply_markup=kb_eyes())
        await cb.answer()

    @dp.callback_query(F.data.startswith("eyes:"))
    async def on_eyes(cb: CallbackQuery, state: FSMContext):
        await state.update_data(eyes=cb.data.split(":")[1])
        await state.set_state(Quiz.occasion)
        await cb.message.answer("Для какого случая макияж?", reply_markup=kb_occasion())
        await cb.answer()

    # ===== Final (short) + save answers for Detail =====

    @dp.callback_query(F.data.startswith("occ:"))
    async def on_occasion(cb: CallbackQuery, state: FSMContext):
        db.ensure_user(cb.message.chat.id)
        data = await state.get_data()

        answers = Answers(
            skin=data["skin"],
            tone=data["tone"],
            undertone=data["undertone"],
            eyes=data["eyes"],
            occasion=cb.data.split(":")[1],
        )

        # Short text first
        text_short = build_text(answers, level="short")
        await cb.message.answer(text_short, reply_markup=kb_result())

        # Save payload for "Подробнее"
        payload = {
            "skin": answers.skin,
            "tone": answers.tone,
            "undertone": answers.undertone,
            "eyes": answers.eyes,
            "occasion": answers.occasion,
        }
        db.save_last_answers(cb.message.chat.id, json.dumps(payload, ensure_ascii=False))

        await state.clear()
        await cb.answer()

    # ===== Detail button =====

    @dp.callback_query(F.data == "detail")
    async def on_detail(cb: CallbackQuery):
        db.ensure_user(cb.message.chat.id)
        raw = db.get_last_answers(cb.message.chat.id)
        if not raw:
            await cb.message.answer("Не вижу последнего результата. Нажми /start и пройди подбор 💄")
            await cb.answer()
            return

        data = json.loads(raw)
        answers = Answers(
            skin=data["skin"],
            tone=data["tone"],
            undertone=data["undertone"],
            eyes=data["eyes"],
            occasion=data["occasion"],
        )

        text_full = build_text(answers, level="full")
        await cb.message.answer(text_full)
        await cb.answer()

    # ===== Save =====

    @dp.callback_query(F.data == "save")
    async def on_save(cb: CallbackQuery):
        db.ensure_user(cb.message.chat.id)
        if cb.message.text:
            db.save_last_result(cb.message.chat.id, cb.message.text)
            await cb.message.answer("💾 Сохранила! Напиши /my, чтобы посмотреть позже.")
        await cb.answer()

    # ===== Tips subscription =====

    @dp.callback_query(F.data == "tips_on")
    async def tips_on(cb: CallbackQuery):
        await cb.message.answer(
            "Хочешь получать **1 короткий совет по макияжу в день**?\n"
            "Без воды, только полезное 💄",
            reply_markup=kb_tips_confirm()
        )
        await cb.answer()

    @dp.callback_query(F.data == "tips_yes")
    async def tips_yes(cb: CallbackQuery):
        db.ensure_user(cb.message.chat.id)
        db.set_tips(cb.message.chat.id, True)
        await cb.message.answer("✨ Отлично! Буду присылать советы каждый день.\nОтключить можно командой /stop.")
        await cb.answer()

    @dp.callback_query(F.data == "tips_no")
    async def tips_no(cb: CallbackQuery):
        await cb.message.answer("Хорошо 🙂 Если захочешь — включишь позже в любой момент.")
        await cb.answer()

    # ================= START =================
    try:
        await dp.start_polling(bot)
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
