"""Гороскоп-бот для Telegram.
Установка:  pip install python-telegram-bot
Запуск:     BOT_TOKEN=ваш_токен python horoscope_bot.py
Картинки (необязательно): папка img/ рядом со скриптом, файлы aries.jpg, taurus.jpg ...
"""
import os
import re
import random
import datetime as dt
import xml.etree.ElementTree as ET
from pathlib import Path

import httpx

from telegram import Update, InlineKeyboardButton as B, InlineKeyboardMarkup as M
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

IMG = Path(__file__).parent / "img"

# key: (эмодзи, название, даты, стихия, характер)
SIGNS = {
    "aries": ("♈", "Овен", "21.03–19.04", "fire",
              "Лидер по натуре: смелый, энергичный, прямой. Любит начинать новое и не терпит ждать. Минус — вспыльчивость и нетерпение."),
    "taurus": ("♉", "Телец", "20.04–20.05", "earth",
               "Надёжный, терпеливый, ценит комфорт и стабильность. Упрямый, но верный. Любит вкусно поесть и красиво жить."),
    "gemini": ("♊", "Близнецы", "21.05–20.06", "air",
               "Общительный, любознательный, остроумный. Быстро схватывает новое и легко находит общий язык. Минус — непостоянство."),
    "cancer": ("♋", "Рак", "21.06–22.07", "water",
               "Чуткий, заботливый, привязан к дому и близким. Сильная интуиция и память. Может быть слишком обидчивым."),
    "leo": ("♌", "Лев", "23.07–22.08", "fire",
            "Яркий, щедрый, харизматичный. Любит внимание и умеет вдохновлять. Минус — гордость и жажда признания."),
    "virgo": ("♍", "Дева", "23.08–22.09", "earth",
              "Аккуратная, внимательная, практичная. Всё анализирует и доводит до идеала. Бывает слишком самокритична."),
    "libra": ("♎", "Весы", "23.09–22.10", "air",
              "Дипломатичные, обаятельные, ценят гармонию и красоту. Справедливы, но долго выбирают и сомневаются."),
    "scorpio": ("♏", "Скорпион", "23.10–21.11", "water",
                "Страстный, проницательный, сильный духом. Глубокие чувства и железная воля. Минус — ревность и скрытность."),
    "sagittarius": ("♐", "Стрелец", "22.11–21.12", "fire",
                    "Оптимист и искатель приключений. Любит свободу, путешествия и философию. Бывает слишком прямолинеен."),
    "capricorn": ("♑", "Козерог", "22.12–19.01", "earth",
                  "Целеустремлённый, дисциплинированный, ответственный. Идёт к цели шаг за шагом. Минус — излишняя строгость к себе."),
    "aquarius": ("♒", "Водолей", "20.01–18.02", "air",
                 "Оригинальный, независимый, с нестандартным мышлением. Ценит дружбу и свободу. Может казаться отстранённым."),
    "pisces": ("♓", "Рыбы", "19.02–20.03", "water",
               "Мечтательные, творческие, добрые. Тонко чувствуют людей. Минус — уход от реальности и нерешительность."),
}
ELEMENTS = {"fire": "🔥 Огонь", "earth": "🌍 Земля", "air": "💨 Воздух", "water": "💧 Вода"}
PERIODS = {"day": "📅 День", "week": "🗓 Неделя", "month": "🌙 Месяц"}

TEXTS = {
    "general": ["Звёзды благоволят смелым шагам.", "Хороший момент замедлиться и всё обдумать.",
                "Неожиданная новость поднимет настроение.", "Энергии много — направьте её в главное дело.",
                "Прислушайтесь к интуиции, она не подведёт.", "Возможна приятная встреча или звонок."],
    "love": ["Тёплый разговор сблизит вас с близким человеком.", "Одинокие могут встретить интересного собеседника.",
             "Не копите обиды — скажите всё прямо.", "Сюрприз для любимого человека будет очень кстати.",
             "Флирт и лёгкость сделают вас притягательнее."],
    "work": ["Завершите отложенное — получите признание.", "Хороший период для переговоров.",
             "Не берите лишнего, расставьте приоритеты.", "Идея, которая пришла внезапно, может выстрелить.",
             "Коллеги готовы помочь, если попросите."],
    "money": ["Избегайте импульсивных покупок.", "Возможен небольшой неожиданный доход.",
              "Хорошее время, чтобы пересмотреть бюджет.", "Вложения в себя окупятся.",
              "Не одалживайте крупные суммы."],
    "health": ["Больше воды и прогулок на свежем воздухе.", "Берегите сон — он ваш главный ресурс.",
               "Лёгкая зарядка вернёт бодрость.", "Не перегружайте себя, делайте паузы.",
               "Время для спорта или йоги."],
}
COLORS = ["красный ❤️", "синий 💙", "зелёный 💚", "жёлтый 💛", "фиолетовый 💜", "белый 🤍", "оранжевый 🧡", "золотой ✨"]
COMPAT_TEXT = {
    "high": "💞 Отличная пара! Много общего, легко понимаете друг друга.",
    "mid": "🙂 Хорошие шансы. Нужно немного терпения и уступок.",
    "low": "⚡ Непросто, но интересно: вы очень разные и можете многому научиться.",
}


def stars(n: int) -> str:
    return "⭐" * n + "☆" * (5 - n)


def period_key(period: str) -> str:
    t = dt.date.today()
    if period == "day":
        return t.isoformat()
    if period == "week":
        y, w, _ = t.isocalendar()
        return f"{y}-W{w}"
    return f"{t.year}-{t.month}"


def horoscope(sign: str, period: str) -> str:
    rnd = random.Random(f"{sign}-{period}-{period_key(period)}")  # один и тот же результат в течение периода
    e, name, dates, _, _ = SIGNS[sign]
    span = {"day": "на сегодня", "week": "на неделю", "month": "на месяц"}[period]
    return (
        f"{e} *{name}* — гороскоп {span}\n\n"
        f"🔮 {rnd.choice(TEXTS['general'])}\n"
        f"❤️ Любовь {stars(rnd.randint(2, 5))}\n{rnd.choice(TEXTS['love'])}\n"
        f"💼 Работа {stars(rnd.randint(2, 5))}\n{rnd.choice(TEXTS['work'])}\n"
        f"💰 Финансы {stars(rnd.randint(2, 5))}\n{rnd.choice(TEXTS['money'])}\n"
        f"🍀 Здоровье {stars(rnd.randint(2, 5))}\n{rnd.choice(TEXTS['health'])}\n\n"
        f"🎨 Цвет удачи: {rnd.choice(COLORS)}\n🔢 Счастливое число: {rnd.randint(1, 99)}"
    )


def moon_line() -> str:
    """Фаза Луны на сегодня: считается по астрономической формуле, без интернета."""
    ref = dt.datetime(2000, 1, 6, 18, 14, tzinfo=dt.timezone.utc)  # известное новолуние
    age = ((dt.datetime.now(dt.timezone.utc) - ref).total_seconds() / 86400) % 29.530588853
    phases = [(1.85, "🌑 Новолуние"), (5.54, "🌒 Растущий серп"), (9.23, "🌓 Первая четверть"),
              (12.91, "🌔 Растущая Луна"), (16.61, "🌕 Полнолуние"), (20.30, "🌖 Убывающая Луна"),
              (23.99, "🌗 Последняя четверть"), (27.68, "🌘 Убывающий серп"), (99, "🌑 Новолуние")]
    name = next(n for lim, n in phases if age < lim)
    return f"{name} · лунный день ≈ {int(age) + 1}"


# Внешний источник (необязательно). Шаблон ссылки с {sign} и {period}, задаётся в переменной HORO_URL.
EXT_URL = os.environ.get("HORO_URL", "")
EXT_NAME = os.environ.get("HORO_SOURCE", "внешний источник")


async def fetch_external(sign: str, period: str):
    if not EXT_URL:
        return None
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as c:
            r = await c.get(EXT_URL.format(sign=sign, period=period))
        r.raise_for_status()
        node = ET.fromstring(r.content).find(".//item/description")
        if node is None or not node.text:
            return None
        text = re.sub(r"<[^>]+>", "", node.text).strip()
        return re.sub(r"([_*`\[\\])", r"\\\1", text)[:3500]
    except Exception:
        return None


async def get_horoscope(sign: str, period: str) -> str:
    ext = await fetch_external(sign, period)
    e, name = SIGNS[sign][0], SIGNS[sign][1]
    if ext:
        span = {"day": "на сегодня", "week": "на неделю", "month": "на месяц"}[period]
        return f"{e} *{name}* — гороскоп {span}\n\n{ext}\n\n🌙 {moon_line()}\n_Источник: {EXT_NAME}_"
    return f"{horoscope(sign, period)}\n\n🌙 {moon_line()}"


def compatibility(a: str, b: str) -> str:
    ea, eb = SIGNS[a][3], SIGNS[b][3]
    pair = {ea, eb}
    if ea == eb:
        base = 85
    elif pair in ({"fire", "air"}, {"earth", "water"}):
        base = 80
    else:
        base = 55
    rnd = random.Random("".join(sorted([a, b])))  # симметрично: A+B = B+A
    score = max(30, min(99, base + rnd.randint(-10, 10)))
    level = "high" if score >= 75 else "mid" if score >= 60 else "low"
    love, friend, work = (max(20, min(99, score + rnd.randint(-12, 12))) for _ in range(3))
    return (
        f"{SIGNS[a][0]} *{SIGNS[a][1]}* + {SIGNS[b][0]} *{SIGNS[b][1]}*\n\n"
        f"Общая совместимость: *{score}%*\n"
        f"❤️ Любовь: {love}%\n🤝 Дружба: {friend}%\n💼 Работа: {work}%\n\n"
        f"{COMPAT_TEXT[level]}"
    )


def signs_grid(prefix: str, extra=None) -> M:
    items = list(SIGNS.items())
    rows = [[B(f"{v[0]} {v[1]}", callback_data=f"{prefix}:{k}") for k, v in items[i:i + 3]]
            for i in range(0, 12, 3)]
    if extra:
        rows.append(extra)
    return M(rows)


def sign_menu(sign: str) -> M:
    return M([
        [B(PERIODS["day"], callback_data=f"p:{sign}:day"),
         B(PERIODS["week"], callback_data=f"p:{sign}:week"),
         B(PERIODS["month"], callback_data=f"p:{sign}:month")],
        [B("🧬 Характер", callback_data=f"c:{sign}"),
         B("💞 Совместимость", callback_data=f"k:{sign}")],
        [B("⬅️ Другой знак", callback_data="home")],
    ])


def back(sign: str) -> M:
    return M([[B("⬅️ Назад", callback_data=f"s2:{sign}")]])


HOME_TEXT = "✨ *Гороскоп-бот* ✨\nВыберите ваш знак зодиака:"


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HOME_TEXT, reply_markup=signs_grid("s"), parse_mode="Markdown")


async def on_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    parts = q.data.split(":")
    act = parts[0]

    if act == "home":
        await q.edit_message_text(HOME_TEXT, reply_markup=signs_grid("s"), parse_mode="Markdown")

    elif act == "s":  # выбран знак: картинка + меню
        sign = parts[1]
        e, name, dates, el, _ = SIGNS[sign]
        caption = f"{e} {name} · {dates}\nСтихия: {ELEMENTS[el]}"
        await q.message.delete()
        photo = IMG / f"{sign}.jpg"
        if photo.exists():
            with open(photo, "rb") as f:
                await ctx.bot.send_photo(q.message.chat_id, f, caption=caption)
        else:
            caption = f"{e}{e}{e}\n{caption}"
        await ctx.bot.send_message(q.message.chat_id, f"{caption}\n\nЧто показать?",
                                   reply_markup=sign_menu(sign))

    elif act == "s2":  # назад в меню знака
        sign = parts[1]
        e, name, dates, el, _ = SIGNS[sign]
        await q.edit_message_text(f"{e} {name} · {dates}\nСтихия: {ELEMENTS[el]}\n\nЧто показать?",
                                  reply_markup=sign_menu(sign))

    elif act == "p":
        await q.edit_message_text(await get_horoscope(parts[1], parts[2]), reply_markup=back(parts[1]),
                                  parse_mode="Markdown")

    elif act == "c":
        e, name, dates, el, text = SIGNS[parts[1]]
        await q.edit_message_text(f"{e} *{name}* — характер\n\n{text}\n\nСтихия: {ELEMENTS[el]}",
                                  reply_markup=back(parts[1]), parse_mode="Markdown")

    elif act == "k":  # выбор второго знака
        sign = parts[1]
        await q.edit_message_text(f"💞 Совместимость для {SIGNS[sign][0]} {SIGNS[sign][1]}.\nВыберите партнёра:",
                                  reply_markup=signs_grid(f"k2:{sign}", [B("⬅️ Назад", callback_data=f"s2:{sign}")]))

    elif act == "k2":
        a, b = parts[1], parts[2]
        kb = M([[B("💞 Другой знак", callback_data=f"k:{a}")], [B("⬅️ В меню", callback_data=f"s2:{a}")]])
        await q.edit_message_text(compatibility(a, b), reply_markup=kb, parse_mode="Markdown")


def main():
    token = os.environ["BOT_TOKEN"]
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler(["start", "menu"], start))
    app.add_handler(CallbackQueryHandler(on_button))
    app.run_polling()


if __name__ == "__main__":
    main()
