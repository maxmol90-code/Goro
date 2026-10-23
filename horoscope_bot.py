"""Гороскоп-бот для Telegram (v2): день/неделя/месяц, характер, совместимость,
карта Таро дня, шар предсказаний, определение знака по дате, утренняя рассылка.
requirements.txt:  python-telegram-bot[job-queue]
Переменные: BOT_TOKEN (обязательно), TZ_NAME (необязательно, по умолчанию Europe/Moscow),
HORO_URL / HORO_SOURCE (необязательно, внешний источник)."""
import os
import re
import json
import calendar
import random
import datetime as dt
import xml.etree.ElementTree as ET
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
from telegram import (Update, InlineKeyboardButton as B, InlineKeyboardMarkup as M,
                      InlineQueryResultArticle, InputTextMessageContent)
from telegram.ext import (Application, CommandHandler, CallbackQueryHandler, InlineQueryHandler,
                          MessageHandler, ContextTypes, filters)

BASE = Path(__file__).parent
IMG = BASE / "img"
DB_FILE = BASE / "users.json"

# ---------------------------------------------------------------- данные
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
SIGN_STARTS = [(1, 20, "aquarius"), (2, 19, "pisces"), (3, 21, "aries"), (4, 20, "taurus"),
               (5, 21, "gemini"), (6, 21, "cancer"), (7, 23, "leo"), (8, 23, "virgo"),
               (9, 23, "libra"), (10, 23, "scorpio"), (11, 22, "sagittarius"), (12, 22, "capricorn")]
ELEMENTS = {"fire": "🔥 Огонь", "earth": "🌍 Земля", "air": "💨 Воздух", "water": "💧 Вода"}
PERIODS = {"day": "📅 День", "week": "🗓 Неделя", "month": "🌙 Месяц"}
MONTHS = ["январь", "февраль", "март", "апрель", "май", "июнь", "июль", "август",
          "сентябрь", "октябрь", "ноябрь", "декабрь"]
WEEKDAYS = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
WEEKDAYS_IN = ["в понедельник", "во вторник", "в среду", "в четверг", "в пятницу", "в субботу", "в воскресенье"]

MORNING = ["Начните день без спешки: утро подарит ясность мыслей.", "С утра возможна важная идея, запишите её.",
           "Зарядка и стакан воды настроят на удачный лад.", "Утром лучше решать сложные вопросы, пока голова свежая.",
           "Тёплое сообщение от близкого человека задаст хороший тон.", "Не хватайтесь за всё сразу: выберите одну главную задачу.",
           "Утро может начаться суетливо, но к обеду всё наладится."]
AFTERNOON = ["В середине дня вас ждёт полезный разговор или новость.", "Хороший момент для встреч, звонков и переговоров.",
             "Энергии будет много, направьте её на самое важное дело.", "Не откладывайте мелкие дела, они быстро освободят голову.",
             "Возможна неожиданная просьба о помощи, ваша поддержка будет оценена.",
             "После обеда легко отвлечься, держите фокус на главном.", "Сделайте паузу и выйдите на свежий воздух, это вернёт силы."]
EVENING = ["Вечером лучше отдохнуть, чем решать срочные дела.", "Тёплый ужин и спокойный разговор принесут больше, чем гаджеты.",
           "Вечер подойдёт для планов на завтра и приятных мелочей.", "Возможна встреча или приглашение, которое поднимет настроение.",
           "Пораньше ложитесь спать, завтра понадобятся силы.", "Любимая музыка или фильм помогут расслабиться.",
           "Подведите итоги дня и отметьте то, что удалось."]
LOVE = ["Тёплый разговор сблизит вас с близким человеком.", "Одинокие могут встретить интересного собеседника.",
        "Не копите обиды, скажите всё прямо и мягко.", "Сюрприз для любимого человека будет очень кстати.",
        "Флирт и лёгкость сделают вас притягательнее.", "Подарите близкому человеку внимание, это дороже подарков.",
        "Возможна старая встреча или сообщение из прошлого."]
WORK = ["Завершите отложенное и получите признание.", "Хороший период для переговоров и презентаций.",
        "Не берите лишнего, расставьте приоритеты.", "Идея, пришедшая внезапно, может выстрелить.",
        "Коллеги готовы помочь, если вы попросите.", "Проверьте детали, мелкая ошибка может стоить времени.",
        "Начальство заметит вашу инициативу."]
MONEY = ["Избегайте импульсивных покупок.", "Возможен небольшой неожиданный доход.",
         "Хорошее время, чтобы пересмотреть бюджет.", "Вложения в себя и знания окупятся.",
         "Не одалживайте крупные суммы.", "Выгодно покупать то, что давно планировали.",
         "Сравните цены, найдётся хорошая скидка."]
HEALTH = ["Больше воды и прогулок на свежем воздухе.", "Берегите сон, он ваш главный ресурс.",
          "Лёгкая зарядка вернёт бодрость.", "Не перегружайте себя, делайте паузы.",
          "Подойдут спорт и йога.", "Следите за осанкой и дайте отдых глазам.",
          "Добавьте в рацион больше овощей и фруктов."]
ADVICE = ["Прислушайтесь к интуиции, она не подведёт.", "Скажите «спасибо» трём людям, это повысит удачу.",
          "Начните с самого неприятного дела, остальное пойдёт легче.", "Улыбка откроет больше дверей, чем кажется.",
          "Не обещайте лишнего и держите слово.", "Сделайте доброе дело без повода.",
          "Откажитесь от сомнений, сегодня смелость в плюсе.", "Запишите три цели на день и вычеркните хотя бы две."]
WEEK_GENERAL = ["Неделя наберёт обороты постепенно, к середине вы почувствуете подъём.",
                "Звёзды советуют не спешить с решениями и взвесить все за и против.",
                "На этой неделе вас ждут приятные встречи и новые знакомства.",
                "Хороший период для завершения старых дел и начала нового.",
                "Возможны неожиданные новости, сохраняйте спокойствие и гибкость.",
                "Неделя обещает быть насыщенной, распределяйте силы заранее."]
WEEK_LOVE = ["Отношения потребуют внимания: найдите время для двоих.", "Одинокие рискуют встретить интересного человека через друзей.",
             "Не обсуждайте старые обиды, лучше строить планы вместе.", "Неделя подходит для свидания и совместных поездок."]
WEEK_WORK = ["Важные задачи лучше закрыть до середины недели.", "Возможно интересное предложение, обдумайте его спокойно.",
             "Работа в команде даст больше, чем в одиночку.", "Проверяйте сроки и документы дважды."]
WEEK_MONEY = ["Финансы стабильны, но от крупных трат лучше воздержаться.", "Возможна прибавка или бонус, будьте внимательны к предложениям.",
              "Хорошая неделя, чтобы навести порядок в бюджете.", "Не ввязывайтесь в сомнительные сделки."]
WEEK_HEALTH = ["Силы будут расти, но не забывайте про отдых.", "Больше движения и свежего воздуха.",
               "Выберите спокойный режим сна, он повысит энергию.", "Не пропускайте приёмы пищи и пейте воду."]
MONTH_GENERAL = ["Месяц принесёт перемены, к которым стоит подготовиться заранее.",
                 "Время роста и новых возможностей, действуйте уверенно.",
                 "Месяц подходит для планов, обучения и укрепления связей.",
                 "Вас ждёт насыщенный период с приятными сюрпризами."]
DECADES = [["Начало месяца: набирайте темп и не бойтесь пробовать новое.", "Первые дни пройдут спокойно, самое время расставить приоритеты."],
           ["Середина месяца: возможны важные разговоры и решения.", "Вторая декада принесёт движение в делах и встречи."],
           ["Конец месяца: подводите итоги и закрывайте хвосты.", "Финал месяца порадует результатом и новыми планами."]]
DATE_NOTES = ["удачный день для переговоров", "хорошо подходит для встреч и свиданий", "день для важных решений",
              "лучше отдохнуть и не торопиться", "благоприятен для покупок", "день приятных новостей"]
COLORS = ["красный ❤️", "синий 💙", "зелёный 💚", "жёлтый 💛", "фиолетовый 💜", "белый 🤍", "оранжевый 🧡", "золотой ✨"]
STONES = ["аметист", "бирюза", "янтарь", "лунный камень", "нефрит", "гранат", "агат", "топаз", "кварц"]
BALL = ["✅ Да, определённо!", "✅ Скорее всего да.", "✅ Звёзды говорят «да».", "🤔 Пока неясно, спросите позже.",
        "🤔 Лучше подождать и посмотреть.", "🤔 Всё зависит от ваших действий.", "❌ Вряд ли.",
        "❌ Нет, звёзды против.", "❌ Не стоит на это рассчитывать.", "✨ Да, но потребуется терпение.",
        "✨ Шансы хорошие, действуйте!", "🌙 Ответ скрыт, сформулируйте иначе."]
TAROT = [("0 · Шут", "Новое начало, лёгкость, шаг в неизвестность."), ("I · Маг", "Всё нужное у вас уже есть, действуйте."),
         ("II · Верховная Жрица", "Доверьтесь интуиции, не всё нужно говорить."), ("III · Императрица", "Время творчества, заботы и роста."),
         ("IV · Император", "Порядок, воля и чёткие границы."), ("V · Иерофант", "Совет наставника и опора на традиции."),
         ("VI · Влюблённые", "Выбор сердцем, важные отношения."), ("VII · Колесница", "Победа через упорство, двигайтесь вперёд."),
         ("VIII · Сила", "Мягкая сила и терпение сильнее напора."), ("IX · Отшельник", "Нужна пауза и время наедине с мыслями."),
         ("X · Колесо Фортуны", "Перемены к лучшему, ловите момент."), ("XI · Справедливость", "Честность и ответственность за решения."),
         ("XII · Повешенный", "Взгляните на ситуацию иначе, не спешите."), ("XIII · Смерть", "Конец старого открывает дорогу новому."),
         ("XIV · Умеренность", "Баланс и спокойный ритм."), ("XV · Дьявол", "Не поддавайтесь соблазнам и дурным привычкам."),
         ("XVI · Башня", "Неожиданность, которая расчищает путь."), ("XVII · Звезда", "Надежда, вдохновение, всё наладится."),
         ("XVIII · Луна", "Не всё так, как кажется, проверьте детали."), ("XIX · Солнце", "Радость, успех и тёплые новости."),
         ("XX · Суд", "Время подвести итоги и принять решение."), ("XXI · Мир", "Завершение этапа и награда за труд.")]
COMPAT_TEXT = {"high": "💞 Отличная пара! Много общего, легко понимаете друг друга.",
               "mid": "🙂 Хорошие шансы. Нужно немного терпения и уступок.",
               "low": "⚡ Непросто, но интересно: вы очень разные и можете многому научиться."}

# ---------------------------------------------------------------- хранилище
def db_load() -> dict:
    try:
        return json.loads(DB_FILE.read_text("utf-8"))
    except Exception:
        return {}


DB = db_load()


def db_set(uid, **kw):
    DB.setdefault(str(uid), {}).update(kw)
    try:
        DB_FILE.write_text(json.dumps(DB, ensure_ascii=False), "utf-8")
    except Exception:
        pass


def db_get(uid, key, default=None):
    return DB.get(str(uid), {}).get(key, default)

# ---------------------------------------------------------------- логика
def stars(n: int) -> str:
    return "⭐" * n + "☆" * (5 - n)


def pct(r) -> int:
    return r.randint(55, 98)


def sign_by_date(d: int, m: int) -> str:
    cur = "capricorn"
    for sm, sd, key in SIGN_STARTS:
        if (m, d) >= (sm, sd):
            cur = key
    return cur


def period_key(period: str) -> str:
    t = dt.date.today()
    if period == "day":
        return t.isoformat()
    if period == "week":
        y, w, _ = t.isocalendar()
        return f"{y}-W{w}"
    return f"{t.year}-{t.month}"


def period_title(period: str) -> str:
    t = dt.date.today()
    if period == "day":
        return f"гороскоп на сегодня, {t:%d.%m}"
    if period == "week":
        mon = t - dt.timedelta(days=t.weekday())
        return f"гороскоп на неделю {mon:%d.%m}–{mon + dt.timedelta(days=6):%d.%m}"
    return f"гороскоп на {MONTHS[t.month - 1]} {t.year}"


def moon_line() -> str:
    ref = dt.datetime(2000, 1, 6, 18, 14, tzinfo=dt.timezone.utc)
    age = ((dt.datetime.now(dt.timezone.utc) - ref).total_seconds() / 86400) % 29.530588853
    phases = [(1.85, "🌑 Новолуние"), (5.54, "🌒 Растущий серп"), (9.23, "🌓 Первая четверть"),
              (12.91, "🌔 Растущая Луна"), (16.61, "🌕 Полнолуние"), (20.30, "🌖 Убывающая Луна"),
              (23.99, "🌗 Последняя четверть"), (27.68, "🌘 Убывающий серп"), (99, "🌑 Новолуние")]
    return f"{next(n for lim, n in phases if age < lim)} · лунный день ≈ {int(age) + 1}"


def h_day(r) -> str:
    h = r.randint(8, 18)
    return (f"🌅 *Утро*\n{r.choice(MORNING)}\n\n☀️ *День*\n{r.choice(AFTERNOON)}\n\n🌙 *Вечер*\n{r.choice(EVENING)}\n\n"
            f"❤️ *Любовь*\n{r.choice(LOVE)}\n\n💼 *Работа*\n{r.choice(WORK)}\n\n"
            f"💰 *Деньги*\n{r.choice(MONEY)}\n\n🍀 *Здоровье*\n{r.choice(HEALTH)}\n\n"
            f"💡 *Совет дня:* {r.choice(ADVICE)}\n\n⏰ Удачное время: {h}:00–{h + 2}:00\n"
            f"⚡ Энергия {pct(r)}% · 🍀 Удача {pct(r)}% · 😊 Настроение {pct(r)}%\n"
            f"🎨 Цвет: {r.choice(COLORS)}\n🔢 Число: {r.randint(1, 99)} · 💎 Камень: {r.choice(STONES)}")


def h_week(r) -> str:
    d = r.sample(range(7), 3)
    return (f"🔮 *Настрой недели*\n{r.choice(WEEK_GENERAL)}\n\n❤️ *Любовь*\n{r.choice(WEEK_LOVE)}\n\n"
            f"💼 *Работа*\n{r.choice(WEEK_WORK)}\n\n💰 *Деньги*\n{r.choice(WEEK_MONEY)}\n\n"
            f"🍀 *Здоровье*\n{r.choice(WEEK_HEALTH)}\n\n"
            f"✅ Удачные дни: {WEEKDAYS[d[0]]}, {WEEKDAYS[d[1]]}\n⚠️ Осторожнее {WEEKDAYS_IN[d[2]]}\n\n"
            f"💡 *Совет недели:* {r.choice(ADVICE)}\n\n"
            f"⚡ Энергия {pct(r)}% · 🍀 Удача {pct(r)}%\n🎨 Цвет: {r.choice(COLORS)} · 🔢 Число: {r.randint(1, 99)}")


def h_month(r) -> str:
    t = dt.date.today()
    days = sorted(r.sample(range(1, calendar.monthrange(t.year, t.month)[1] + 1), 3))
    dates = "\n".join(f"• {x:02d}.{t.month:02d} — {r.choice(DATE_NOTES)}" for x in days)
    return (f"🔮 *Главная тема*\n{r.choice(MONTH_GENERAL)}\n\n📆 *По декадам*\n"
            f"1–10: {r.choice(DECADES[0])}\n11–20: {r.choice(DECADES[1])}\n21–конец: {r.choice(DECADES[2])}\n\n"
            f"❤️ Любовь {stars(r.randint(2, 5))}\n{r.choice(LOVE)}\n"
            f"💼 Работа {stars(r.randint(2, 5))}\n{r.choice(WORK)}\n"
            f"💰 Финансы {stars(r.randint(2, 5))}\n{r.choice(MONEY)}\n"
            f"🍀 Здоровье {stars(r.randint(2, 5))}\n{r.choice(HEALTH)}\n\n"
            f"📌 *Ключевые даты*\n{dates}\n\n💡 *Совет месяца:* {r.choice(ADVICE)}\n"
            f"🎨 Цвет: {r.choice(COLORS)} · 🔢 Число: {r.randint(1, 99)}")


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


def local_horoscope(sign: str, period: str) -> str:
    e, name = SIGNS[sign][0], SIGNS[sign][1]
    head = f"{e} *{name}* · {period_title(period)}\n🌙 {moon_line()}\n\n"
    r = random.Random(f"{sign}-{period}-{period_key(period)}")  # одинаково в течение периода
    return head + {"day": h_day, "week": h_week, "month": h_month}[period](r)


async def get_horoscope(sign: str, period: str) -> str:
    e, name = SIGNS[sign][0], SIGNS[sign][1]
    ext = await fetch_external(sign, period)
    if ext:
        head = f"{e} *{name}* · {period_title(period)}\n🌙 {moon_line()}\n\n"
        return f"{head}{ext}\n\n_Источник: {EXT_NAME}_"
    return local_horoscope(sign, period)


def compatibility(a: str, b: str) -> str:
    ea, eb = SIGNS[a][3], SIGNS[b][3]
    pair = {ea, eb}
    base = 85 if ea == eb else 80 if pair in ({"fire", "air"}, {"earth", "water"}) else 55
    r = random.Random("".join(sorted([a, b])))
    score = max(30, min(99, base + r.randint(-10, 10)))
    level = "high" if score >= 75 else "mid" if score >= 60 else "low"
    love, friend, work = (max(20, min(99, score + r.randint(-12, 12))) for _ in range(3))
    return (f"{SIGNS[a][0]} *{SIGNS[a][1]}* + {SIGNS[b][0]} *{SIGNS[b][1]}*\n\n"
            f"Общая совместимость: *{score}%*\n❤️ Любовь: {love}%\n🤝 Дружба: {friend}%\n💼 Работа: {work}%\n\n"
            f"{COMPAT_TEXT[level]}")


def tarot_text(uid) -> str:
    r = random.Random(f"{uid}-{dt.date.today().isoformat()}")
    name, meaning = r.choice(TAROT)
    return f"🃏 *Ваша карта дня*\n\n*{name}*\n{meaning}\n\n_Развлекательное предсказание, не руководство к действию._"

# ---------------------------------------------------------------- клавиатуры
def signs_grid(prefix: str, extra_rows=()) -> M:
    items = list(SIGNS.items())
    rows = [[B(f"{v[0]} {v[1]}", callback_data=f"{prefix}:{k}") for k, v in items[i:i + 3]]
            for i in range(0, 12, 3)]
    rows.extend(extra_rows)
    return M(rows)


def home_kb(uid) -> M:
    extra = [[B("📆 Знак по дате", callback_data="date"), B("🃏 Карта дня", callback_data="tarot:")],
             [B("🎱 Шар предсказаний", callback_data="ball")]]
    me = db_get(uid, "sign")
    if me:
        extra.insert(0, [B(f"👤 Мой знак: {SIGNS[me][0]} {SIGNS[me][1]}", callback_data=f"s2:{me}")])
    return signs_grid("s", extra)


def sign_menu(sign: str, uid) -> M:
    sub = db_get(uid, "sub", False)
    return M([
        [B(v, callback_data=f"p:{sign}:{k}") for k, v in PERIODS.items()],
        [B("🧬 Характер", callback_data=f"c:{sign}"), B("💞 Совместимость", callback_data=f"k:{sign}")],
        [B("🃏 Карта дня", callback_data=f"tarot:{sign}"), B("🎱 Шар", callback_data="ball")],
        [B("🔕 Выключить рассылку" if sub else "🔔 Утренняя рассылка", callback_data=f"sub:{sign}")],
        [B("⬅️ Другой знак", callback_data="home")],
    ])


def after_kb(sign: str, cur: str) -> M:
    others = [B(PERIODS[p], callback_data=f"p:{sign}:{p}") for p in PERIODS if p != cur]
    return M([others,
              [B("💞 Совместимость", callback_data=f"k:{sign}"), B("🃏 Карта дня", callback_data=f"tarot:{sign}")],
              [B("📤 Отправить в чат", switch_inline_query=SIGNS[sign][1])],
              [B("⬅️ В меню", callback_data=f"s2:{sign}")]])


def back_kb(sign: str) -> M:
    return M([[B("⬅️ Назад", callback_data=f"s2:{sign}" if sign else "home")]])


HOME_TEXT = "✨ *Гороскоп-бот* ✨\nВыберите знак зодиака или попробуйте что-то новое:"


def menu_text(sign: str) -> str:
    e, name, dates, el, _ = SIGNS[sign]
    return f"{e} *{name}* · {dates}\nСтихия: {ELEMENTS[el]}\n\nЧто показать?"


async def show_sign(bot, chat_id, uid, sign):
    e, name, dates, el, _ = SIGNS[sign]
    photo = IMG / f"{sign}.jpg"
    if photo.exists():
        with open(photo, "rb") as f:
            await bot.send_photo(chat_id, f, caption=f"{e} {name} · {dates}")
    await bot.send_message(chat_id, menu_text(sign), reply_markup=sign_menu(sign, uid), parse_mode="Markdown")

# ---------------------------------------------------------------- обработчики
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.pop("mode", None)
    await update.message.reply_text(HOME_TEXT, reply_markup=home_kb(update.effective_user.id), parse_mode="Markdown")


async def on_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid = q.from_user.id
    parts = q.data.split(":")
    act = parts[0]
    if act != "sub":
        await q.answer()

    if act == "home":
        ctx.user_data.pop("mode", None)
        await q.edit_message_text(HOME_TEXT, reply_markup=home_kb(uid), parse_mode="Markdown")

    elif act == "s":
        sign = parts[1]
        db_set(uid, sign=sign, chat=q.message.chat_id)
        await q.message.delete()
        await show_sign(ctx.bot, q.message.chat_id, uid, sign)

    elif act == "s2":
        await q.edit_message_text(menu_text(parts[1]), reply_markup=sign_menu(parts[1], uid), parse_mode="Markdown")

    elif act == "p":
        await q.edit_message_text(await get_horoscope(parts[1], parts[2]),
                                  reply_markup=after_kb(parts[1], parts[2]), parse_mode="Markdown")

    elif act == "c":
        e, name, dates, el, text = SIGNS[parts[1]]
        await q.edit_message_text(f"{e} *{name}* · характер\n\n{text}\n\nСтихия: {ELEMENTS[el]}",
                                  reply_markup=back_kb(parts[1]), parse_mode="Markdown")

    elif act == "k":
        sign = parts[1]
        await q.edit_message_text(f"💞 Совместимость для {SIGNS[sign][0]} {SIGNS[sign][1]}.\nВыберите партнёра:",
                                  reply_markup=signs_grid(f"k2:{sign}", [[B("⬅️ Назад", callback_data=f"s2:{sign}")]]))

    elif act == "k2":
        a, b = parts[1], parts[2]
        kb = M([[B("💞 Другой знак", callback_data=f"k:{a}")], [B("⬅️ В меню", callback_data=f"s2:{a}")]])
        await q.edit_message_text(compatibility(a, b), reply_markup=kb, parse_mode="Markdown")

    elif act == "tarot":
        sign = parts[1] if len(parts) > 1 else ""
        await q.edit_message_text(tarot_text(uid), reply_markup=back_kb(sign), parse_mode="Markdown")

    elif act == "ball":
        ctx.user_data["mode"] = "ball"
        await q.edit_message_text("🎱 Задумайте вопрос, на который можно ответить «да» или «нет», и напишите его сообщением.",
                                  reply_markup=M([[B("⬅️ Отмена", callback_data="home")]]))

    elif act == "date":
        ctx.user_data["mode"] = "date"
        await q.edit_message_text("📆 Напишите дату рождения числом и месяцем, например: 14.08",
                                  reply_markup=M([[B("⬅️ Отмена", callback_data="home")]]))

    elif act == "sub":
        if ctx.application.job_queue is None:
            await q.answer("Рассылка недоступна: в requirements.txt нужна строка python-telegram-bot[job-queue]",
                           show_alert=True)
            return
        new = not db_get(uid, "sub", False)
        db_set(uid, sub=new, sign=parts[1], chat=q.message.chat_id)
        await q.answer("🔔 Гороскоп будет приходить каждое утро в 8:00" if new else "🔕 Рассылка выключена",
                       show_alert=True)
        await q.edit_message_reply_markup(reply_markup=sign_menu(parts[1], uid))


async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    mode = ctx.user_data.pop("mode", None)
    txt = (update.message.text or "").strip()
    if mode == "ball":
        await update.message.reply_text(f"🎱 {random.choice(BALL)}",
                                        reply_markup=M([[B("🎱 Ещё вопрос", callback_data="ball")],
                                                        [B("⬅️ В меню", callback_data="home")]]))
    elif mode == "date":
        m = re.search(r"(\d{1,2})\D+(\d{1,2})", txt)
        try:
            d, mo = int(m.group(1)), int(m.group(2))
            dt.date(2000, mo, d)
        except Exception:
            ctx.user_data["mode"] = "date"
            await update.message.reply_text("Не получилось разобрать дату. Напишите, например: 14.08")
            return
        sign = sign_by_date(d, mo)
        db_set(uid, sign=sign, chat=update.effective_chat.id)
        await show_sign(ctx.bot, update.effective_chat.id, uid, sign)
    elif update.effective_chat.type != "private":
        return  # в группах без запроса молчим
    else:
        await update.message.reply_text("Нажмите /start, чтобы открыть меню 👇",
                                        reply_markup=M([[B("✨ Открыть меню", callback_data="home")]]))


def build_inline(query: str, uid) -> list:
    """Результаты для вызова бота через @имя_бота в любом чате: (id, заголовок, описание, текст)."""
    words = [w for w in query.lower().split() if len(w) >= 2]
    found = []
    for w in words:
        for k, v in SIGNS.items():
            if v[1].lower().startswith(w) and k not in found:
                found.append(k)
    out = []

    def add(rid, title, text):
        desc = re.sub(r"[*_`]", "", text.split("\n\n")[1] if "\n\n" in text else text)[:90].replace("\n", " ")
        out.append((rid, title, desc, text))

    if len(found) >= 2:
        a, b = found[0], found[1]
        add(f"k-{a}-{b}", f"💞 {SIGNS[a][1]} + {SIGNS[b][1]}: совместимость", compatibility(a, b))
    if found:
        for sign in found[:2]:
            e, name = SIGNS[sign][0], SIGNS[sign][1]
            for p, label in (("day", "на сегодня"), ("week", "на неделю"), ("month", "на месяц")):
                add(f"h-{sign}-{p}", f"{e} {name} · {label}", local_horoscope(sign, p))
            add(f"c-{sign}", f"🧬 {name}: характер", f"{e} *{name}* · характер\n\n{SIGNS[sign][4]}")
    else:
        me = db_get(uid, "sign")
        order = ([me] if me else []) + [k for k in SIGNS if k != me]
        for sign in order:
            e, name = SIGNS[sign][0], SIGNS[sign][1]
            add(f"h-{sign}-day", f"{e} {name} · гороскоп на сегодня", local_horoscope(sign, "day"))
        add("tarot", "🃏 Карта дня", tarot_text(uid))
        add("ball", "🎱 Шар предсказаний", f"🎱 {random.choice(BALL)}")
    return out[:50]


async def on_inline(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.inline_query
    items = build_inline(q.query, q.from_user.id)
    results = [InlineQueryResultArticle(id=rid[:64], title=title, description=desc,
                                        input_message_content=InputTextMessageContent(text, parse_mode="Markdown"))
               for rid, title, desc, text in items]
    await q.answer(results, cache_time=1, is_personal=True)


async def daily_job(ctx: ContextTypes.DEFAULT_TYPE):
    for u in list(DB.values()):
        if u.get("sub") and u.get("sign") and u.get("chat"):
            try:
                text = await get_horoscope(u["sign"], "day")
                await ctx.bot.send_message(u["chat"], "☀️ Доброе утро!\n\n" + text, parse_mode="Markdown")
            except Exception:
                pass


def main():
    app = Application.builder().token(os.environ["BOT_TOKEN"]).build()
    app.add_handler(CommandHandler(["start", "menu"], start))
    app.add_handler(CallbackQueryHandler(on_button))
    app.add_handler(InlineQueryHandler(on_inline))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    if app.job_queue:
        try:
            tz = ZoneInfo(os.environ.get("TZ_NAME", "Europe/Moscow"))
        except Exception:
            tz = dt.timezone(dt.timedelta(hours=3))
        app.job_queue.run_daily(daily_job, dt.time(8, 0, tzinfo=tz))
    app.run_polling()


if __name__ == "__main__":
    main()
