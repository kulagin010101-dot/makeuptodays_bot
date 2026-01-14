import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from zoneinfo import ZoneInfo

from .config import get_settings
from .db import DB
from .logic import Answers, build_final_text

# ====== FSM states ======
class Quiz(StatesGroup):
    skin = State()
    tone = State()
    undertone = State()
    eyes = State()
    occasion = State()

# ====== Keyboards ======
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
    kb.adjust(2,2,1)
    return kb.as_markup()

def kb_tone():
    kb = InlineKeyboardBuilder()
    kb.button(text="Светлый", callback_data="tone:light")
    kb.button(text="Средний", callback_data="tone:medium")
    kb.button(text="Смуглый", callback_data="tone:tan")
    kb.adjust(2,1)
    return kb.as_markup()

def kb_undertone():
    kb = InlineKeyboardBuilder()
    kb.button(text="Тёплый", callback_data="undertone:warm")
    kb.button(text="Холодный", callback_data="undertone:cool")
    kb.button(text="Не знаю", callback_data="undertone:unknown")
    kb.adjust(2,1)
    return kb.as_markup()

def kb_eyes():
    kb = InlineKeyboardBuilder()
    kb.button(text="Маленькие", callback_data="eyes:small")
    kb.button(text="Большие", callback_data="eyes:big")
    kb.button(text="Нависшее веко", callback_data="eyes:hooded")
    kb.button(text="Миндалевидные", callback_data="eyes:almond")
    kb.adjust(2,2)
    return kb.as_markup()

def kb_occasion():
    kb = InlineKeyboardBuilder()
    kb.button(text="Каждый день", callback_data="occ:daily")
    kb.button(text="Свидание", callback_data="occ:date")
    kb.button(text="Праздник", callback_data="occ:party")
    kb.button(text="Фото / видео", callback_data="occ:photo")
    kb.adjust(2,2)
    return kb.as_markup()

def kb_result():
    kb = InlineKeyboardBuilder()
    kb.button(text="💾 Сохранить", callback_data="save")
    kb.button(text="💌 Получать советы", callback_data="tips_on")
    kb.adjust(1)
    return kb.as_markup()

def kb_tips_confirm():
    kb = InlineKeyboardBuilder()
    kb.button(text="Да, хочу ✨", callback_data="tips_yes")
    kb.button(text="Не сейчас", callback_data="tips_no")
    kb.adjust(1,1)
    return kb.as_markup()

# ====== Daily tips job ======
async def send_daily_tips(bot: Bot, db: DB):
    from .content import DAILY_TIPS

    users = db.get_all_tips_enabled_users()
    for chat_id, idx in users:
        try:
            tip = DAILY_TIPS[idx % len(DAILY_TIPS)]
            await bot.send_message(chat_id, tip)
            db.advance_tip_index(chat_id, (idx + 1) % len(DAILY_TIPS))
        except Exception:
            # не падаем из-за одного пользователя (например, если заблокировал бота)
            continue

# ====== App ======
async def main():
    settings = get_settings()
    bot = Bot(token=settings.bot_token, parse_mode="Markdown")
    dp = Dispatcher()

    db = DB(settings.db_path)
    db.init()

    # Scheduler
    scheduler = AsyncIOScheduler(timezone=ZoneInfo(settings.tz))
    scheduler.add_job(
        send_daily_tips,
        trigger=CronTrigger(hour=settings.daily_hour, minute=settings.daily_minute),
        args=[bot, db],
        id="daily_tips",
        replace_existing=True,
    )
    scheduler.start()

    # -------- handlers --------
    @dp.message(CommandStart())
    async def cmd_start(message: Message):
        db.ensure_user(message.chat.id)
        await message.answer(
            "Привет 💄\n"
            "Я помогу подобрать макияж, который подойдёт **именно тебе**.\n"
            "Это займёт не больше **2 минут** ✨",
            reply_markup=kb_start()
        )

    @dp.message(Command("my"))
    async def cmd_my(message: Message):
        db.ensure_user(message.chat.id)
        last = db.get_last_result(message.chat.id)
        if not last:
            await message.answer("Пока нет сохранённого результата. Нажми /start и пройди подбор 💄")
            return
        await message.answer("💾 **Твой сохранённый план:**\n\n" + last)

    @dp.message(Command("stop"))
    async def cmd_stop(message: Message):
        db.ensure_user(message.chat.id)
        db.set_tips(message.chat.id, False)
        await message.answer("Окей! Ежедневные советы отключены. Если захочешь снова — нажми «Получать советы» 💄")

    @dp.callback_query(F.data == "start_quiz")
    async def start_quiz(c: CallbackQuery, state: FSMContext):
        db.ensure_user(c.message.chat.id)
        await state.clear()
        await state.set_state(Quiz.skin)
        await c.message.answer("Какая у тебя кожа?", reply_markup=kb_skin())
        await c.answer()

    @dp.callback_query(F.data.startswith("skin:"))
    async def on_skin(c: CallbackQuery, state: FSMContext):
        await state.update_data(skin=c.data.split(":")[1])
        await state.set_state(Quiz.tone)
        await c.message.answer("Какой у тебя тон кожи?", reply_markup=kb_tone())
        await c.answer()

    @dp.callback_query(F.data.startswith("tone:"))
    async def on_tone(c: CallbackQuery, state: FSMContext):
        await state.update_data(tone=c.data.split(":")[1])
        await state.set_state(Quiz.undertone)
        await c.message.answer("Подтон кожи:", reply_markup=kb_undertone())
        await c.answer()

    @dp.callback_query(F.data.startswith("undertone:"))
    async def on_undertone(c: CallbackQuery, state: FSMContext):
        await state.update_data(undertone=c.data.split(":")[1])
        await state.set_state(Quiz.eyes)
        await c.message.answer("Какие глаза ближе всего по форме?", reply_markup=kb_eyes())
        await c.answer()

    @dp.callback_query(F.data.startswith("eyes:"))
    async def on_eyes(c: CallbackQuery, state: FSMContext):
        await state.update_data(eyes=c.data.split(":")[1])
        await state.set_state(Quiz.occasion)
        await c.message.answer("Для какого случая макияж?", reply_markup=kb_occasion())
        await c.answer()

    @dp.callback_query(F.data.startswith("occ:"))
    async def on_occ(c: CallbackQuery, state: FSMContext):
        data = await state.get_data()
        occasion = c.data.split(":")[1]
        a = Answers(
            skin=data["skin"],
            tone=data["tone"],
            undertone=data["undertone"],
            eyes=data["eyes"],
            occasion=occasion,
        )
        text = build_final_text(a)

        # отправляем результат
        await c.message.answer(text, reply_markup=kb_result())
        # временно запоминаем в state, чтобы сохранить по кнопке
        await state.update_data(last_text=text)
        await state.clear()
        await c.answer()

    @dp.callback_query(F.data == "save")
    async def on_save(c: CallbackQuery, state: FSMContext):
        # мы не храним state после clear, поэтому берём из последнего сообщения
        # но надёжнее: сохранять last_text до clear. Упростим:
        # сохранение — сохранить текст последнего сообщения бота (кроме кнопок).
        # В Telegram API прямого "get last message text" нет, поэтому используем костыль:
        # предлагаем пользователю нажать /my после сохранения — а сохраняем текст из message.text.
        # Здесь message — то сообщение, к которому прикреплена кнопка.
        db.ensure_user(c.message.chat.id)
        if c.message.text:
            db.save_last_result(c.message.chat.id, c.message.text)
            await c.message.answer("Готово! Я сохранила твой план 💾\nНапиши /my чтобы посмотреть его в любой момент.")
        else:
            await c.message.answer("Не смогла сохранить (нет текста). Попробуй пройти подбор ещё раз через /start 💄")
        await c.answer()

    @dp.callback_query(F.data == "tips_on")
    async def on_tips_on(c: CallbackQuery):
        await c.message.answer(
            "Хочешь получать **1 короткий совет по макияжу в день**?\n"
            "Без воды, только полезное 💄",
            reply_markup=kb_tips_confirm()
        )
        await c.answer()

    @dp.callback_query(F.data == "tips_yes")
    async def on_tips_yes(c: CallbackQuery):
        db.ensure_user(c.message.chat.id)
        db.set_tips(c.message.chat.id, True)
        await c.message.answer("Супер! Буду присылать 1 совет в день ✨\nОтключить можно командой /stop.")
        await c.answer()

    @dp.callback_query(F.data == "tips_no")
    async def on_tips_no(c: CallbackQuery):
        await c.message.answer("Хорошо 🙂 Если захочешь позже — нажми «Получать советы» в результате.")
        await c.answer()

    # start polling
    try:
        await dp.start_polling(bot)
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
