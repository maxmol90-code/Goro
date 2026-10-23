"""Астрология без напряга (v3). Звёзды светят, но зарплату не приносят.
requirements.txt:  python-telegram-bot[job-queue]
Переменные: BOT_TOKEN (обязательно), TZ_NAME (по умолчанию Europe/Moscow).
Картинки: jpg-файлы рядом со скриптом или в папке img/ (aries.jpg ... pisces.jpg, cat.jpg, welcome.jpg)."""
import os
import re
import json
import calendar
import random
import datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo

from telegram import (Update, InlineKeyboardButton as B, InlineKeyboardMarkup as M,
                      InlineQueryResultArticle, InputTextMessageContent)
from telegram.ext import (Application, CommandHandler, CallbackQueryHandler, InlineQueryHandler,
                          MessageHandler, ContextTypes, filters)

BASE = Path(__file__).parent
DB_FILE = BASE / "users.json"
MOTTO = "Звёзды светят, но зарплату не приносят."

# ---------------------------------------------------------------- знаки
# ключ: (эмодзи, название, даты, стихия, характер, девиз)
SIGNS = {
    "aries": ("♈", "Овен", "21.03–19.04", "fire",
              "Стартует быстрее всех, финиширует по настроению. Смелый, прямой, заряжает энергией. Серьёзно: считайте до трёх перед ответом в рабочем чате, это экономит нервы и отношения.",
              "Сначала сделал, потом подумал. Иногда наоборот, и это прогресс."),
    "taurus": ("♉", "Телец", "20.04–20.05", "earth",
               "Надёжный, терпеливый, любит комфорт и вкусную еду. Сдвинуть с места можно только пряником. Серьёзно: стабильность это ваша сила, но иногда пробуйте новое, хотя бы новый маршрут до работы.",
               "Не трогайте мой диван, мой обед и мои планы на выходные."),
    "gemini": ("♊", "Близнецы", "21.05–20.06", "air",
               "Болтливые, любознательные, находят общий язык с кем угодно. Начинают пять дел, заканчивают три. Серьёзно: выберите одно главное дело на день, и результат вас удивит.",
               "Нас двое, и оба не помнят, зачем зашли в комнату."),
    "cancer": ("♋", "Рак", "21.06–22.07", "water",
               "Заботливый, чуткий, с отличной памятью, особенно на обиды. Дом для него крепость. Серьёзно: говорите вслух, что вас задело, обида не должна жить в шкафу.",
               "Дома хорошо. На работе тоже, если оттуда можно уйти домой."),
    "leo": ("♌", "Лев", "23.07–22.08", "fire",
            "Яркий, щедрый, любит быть в центре внимания и заслуженно. Серьёзно: похвала вам нужна как воздух, так что просите обратную связь, а не ждите, когда догадаются.",
            "Хлопать не обязательно. Достаточно просто восхищаться."),
    "virgo": ("♍", "Дева", "23.08–22.09", "earth",
              "Внимательная, аккуратная, видит ошибки раньше, чем они случились. Серьёзно: «достаточно хорошо» тоже результат, не ругайте себя за то, что не идеально.",
              "Я не придираюсь. Я просто вижу ошибки. Везде."),
    "libra": ("♎", "Весы", "23.09–22.10", "air",
              "Обаятельные дипломаты, ценят красоту и справедливость. Выбор ужина занимает до часа. Серьёзно: не решать это тоже решение, и обычно не лучшее.",
              "Пицца или суши? Давайте обсудим на следующей неделе."),
    "scorpio": ("♏", "Скорпион", "23.10–21.11", "water",
                "Страстный, проницательный, видит людей насквозь. Не злопамятный, просто всё помнит. Серьёзно: доверять людям можно и без проверки, иногда это окупается.",
                "Я не злопамятный. У меня просто отличная память."),
    "sagittarius": ("♐", "Стрелец", "22.11–21.12", "fire",
                    "Оптимист, любит свободу и путешествия. Говорит то, что думает, и иногда зря. Серьёзно: правда лучше, когда её подают с добротой, а не как копьё.",
                    "Правда — лучший подарок. Даже если вас не просили."),
    "capricorn": ("♑", "Козерог", "22.12–19.01", "earth",
                  "Ответственный, упорный, идёт к цели, пока остальные пьют кофе. Серьёзно: отдых это часть работы, а не награда за её окончание.",
                  "Отдыхать буду на пенсии. Возможно."),
    "aquarius": ("♒", "Водолей", "20.01–18.02", "air",
                 "Оригинальный, независимый, с идеями, которые поймут через пять лет. Серьёзно: объясняйте свои идеи простыми словами, и вас услышат раньше.",
                 "Я не странный. Я опережаю своё время."),
    "pisces": ("♓", "Рыбы", "19.02–20.03", "water",
               "Мечтательные, добрые, тонко чувствуют людей и настроение. Серьёзно: мечты хороши, когда есть хотя бы один маленький шаг к ним на этой неделе.",
               "Мысленно я уже на море. Физически на созвоне."),
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

# ---------------------------------------------------------------- тексты
# (астрологическая фраза, перевод на человеческий)
TRANSLATE = [
    ("Сатурн в квадрате к Луне", "сегодня лучше не выходить из дома и не принимать решений."),
    ("Меркурий ретроградный", "не подписывайте ничего важного, не пишите бывшим и проверьте, прикрепили ли вы файл."),
    ("Венера в трине к Юпитеру", "можно наконец ответить на то сообщение. Да, на то самое."),
    ("Марс в оппозиции к Солнцу", "коллеги будут бесить. Это не вы, это Марс."),
    ("Луна в Скорпионе", "эмоции на максимум, терпение на минимум. Чай и плед спасут день."),
    ("Нептун в секстиле к Луне", "реальность размыта, дедлайны тоже. Живите, но не слишком."),
    ("Юпитер в доме финансов", "шанс найти пятьсот рублей в старой куртке заметно вырос."),
    ("Плутон в оппозиции к Солнцу", "пора разобрать антресоли и отношения. Начните с антресолей."),
    ("Луна без курса", "любые покупки и важные разговоры лучше отложить до завтра."),
    ("Солнце в гармонии с Луной", "день, когда всё получится само, пока вы не начали переживать."),
    ("Уран в квадрате к Марсу", "случится что-то неожиданное. Скорее всего это будет внеплановый созвон."),
]
MORNING = ["Утро будет бодрым, но только после кофе.", "С утра возможна хорошая идея. Запишите, пока не убежала.",
           "Не открывайте почту до завтрака: это ваш самый стабильный совет.", "Утро начнётся суетливо, к обеду наладится.",
           "Тёплое сообщение от близкого задаст тон дню."]
AFTERNOON = ["В середине дня придёт полезная новость или звонок.", "Хорошее время для переговоров, особенно по телефону с чаем.",
             "После обеда накроет сонливость. Прогулка поможет лучше второго кофе.", "Вас попросят о помощи. Выбирайте, что реально по силам.",
             "Мелкие дела быстро освободят голову, начните с самого нудного."]
EVENING = ["Вечером лучше отдыхать, а не решать срочное.", "Ужин и спокойный разговор принесут больше, чем скроллинг ленты.",
           "Возможно приглашение, от которого захочется отказаться, и зря.", "Ложитесь пораньше: завтра силы пригодятся.",
           "Подведите итоги дня и отметьте то, что удалось, даже если это «встал»."]
LOVE = ["Тёплый разговор сблизит с близким человеком.", "Одинокие могут встретить интересного человека. Для начала выйдите из дома.",
        "Не копите обиды: скажите прямо и мягко.", "Сюрприз для любимого принесёт больше, чем гороскоп.",
        "Возможно сообщение из прошлого. Отвечать необязательно."]
WORK = ["Завершите отложенное, и вас заметят.", "Идея, пришедшая внезапно, может выстрелить.",
        "Коллеги готовы помочь, если попросите.", "Проверьте детали: мелкая ошибка отнимет час.",
        "Начальство заметит вашу инициативу, или хотя бы вашу бледность."]
MONEY = ["Импульсивные покупки сегодня особенно соблазнительны. Подержите корзину до завтра.", "Возможен небольшой неожиданный доход.",
         "Хорошее время заглянуть в бюджет и не расстроиться.", "Вложения в знания окупаются, в чипсы нет.",
         "Не одалживайте крупные суммы, даже очень убедительным людям."]
HEALTH = ["Воды побольше, прогулок побольше.", "Берегите сон: он ваш главный ресурс, а не роскошь.",
          "Лёгкая зарядка вернёт бодрость, диван вернёт всё обратно.", "Делайте паузы, спина скажет спасибо.",
          "Овощи сегодня будут не лишними, а шоколад в меру."]
PROCRAST = ["сегодня разрешена в разумных пределах. Звёзды не осуждают.", "это не лень, это стратегическое планирование. Ну, почти.",
            "никто не узнает. Кроме дедлайна, но он вас пока ждёт.", "допустима до обеда. После обеда сами разберётесь.",
            "сегодня простительна. Завтра тоже, но об этом позже."]
ONE_THING = ["ответьте на одно письмо, которое висит дольше недели.", "выпейте стакан воды и вынесите мусор.",
             "сделайте самый неприятный пункт из списка за 10 минут.", "позвоните человеку, которому давно собирались.",
             "уберите со стола всё лишнее, голове станет легче."]
PET_SHORT = ["погладьте кота (или кошку) минимум три раза.", "потрите кота за ухом, удача придёт к вам и ему.",
             "если кота нет, погладьте любой пушистый предмет.", "поздоровайтесь с котом, он оценит и запомнит."]
PS = ["Если звёзды говорят «всё будет хорошо», не верьте. Они врут, чтобы вы не плакали.",
      "Звёзды светят, но зарплату не приносят.",
      "Если не сбылось, значит, Меркурий был ретроградным. Он всегда виноват.",
      "Прогноз носит развлекательный характер. Решения принимайте сами."]
SERIOUS = ["Серьёзно: стакан воды и сон до полуночи работают лучше любого транзита.",
           "Серьёзно: запишите три задачи на день, остальное необязательно.",
           "Серьёзно: если тревожно, выйдите на 10 минут на улицу без телефона.",
           "Серьёзно: скажите «спасибо» хотя бы двум людям, настроение улучшится.",
           "Серьёзно: не обещайте лишнего, держите слово там, где дали."]
WEEK_GENERAL = ["Неделя раскачается к среде, а к пятнице вы уже будете считать часы.", "Хороший период для завершения старых дел, начало новых можно отложить.",
                "Ждут приятные встречи, но придётся выйти из дома.", "Возможны неожиданные новости. Сохраняйте спокойствие, оно дешевле валерьянки."]
MONTH_GENERAL = ["Месяц принесёт перемены. Не пугайтесь, большинство из них бытовые.", "Время роста и новых возможностей, если перестать откладывать.",
                 "Месяц подходит для планов, учёбы и укрепления связей.", "Насыщенный период с приятными сюрпризами и парой неприятных."]
DECADES = [["Начало месяца: набирайте темп и не бойтесь пробовать новое.", "Первые дни пройдут спокойно, расставьте приоритеты."],
           ["Середина месяца: возможны важные разговоры и решения.", "Вторая декада принесёт движение в делах и встречи."],
           ["Конец месяца: подводите итоги и закрывайте хвосты.", "Финал месяца порадует результатом и новыми планами."]]
DATE_NOTES = ["удачный день для переговоров", "хорош для встреч и свиданий", "день для важных решений",
              "лучше отдохнуть и не торопиться", "благоприятен для покупок", "день приятных новостей"]
COLORS = ["красный ❤️", "синий 💙", "зелёный 💚", "жёлтый 💛", "фиолетовый 💜", "белый 🤍", "оранжевый 🧡", "золотой ✨"]
BALL = ["✅ Да, определённо!", "✅ Скорее всего да.", "✅ Звёзды говорят «да». Но зарплату всё равно не принесут.",
        "🤔 Пока неясно. Спросите позже или у кота.", "🤔 Лучше подождать и посмотреть.", "🤔 Всё зависит от ваших действий. Увы.",
        "❌ Вряд ли.", "❌ Нет. Звёзды против, Меркурий тоже.", "❌ Не рассчитывайте на это.",
        "✨ Да, но потребуется терпение.", "✨ Шансы хорошие, действуйте!", "🌙 Ответ скрыт. Сформулируйте иначе."]
TAROT = [("0 · Шут", "Прыгайте в новое. Парашют по желанию."), ("I · Маг", "Всё нужное у вас уже есть. Остаётся начать."),
         ("II · Верховная Жрица", "Доверьтесь интуиции и не всё рассказывайте."), ("III · Императрица", "Время творить, заботиться и вкусно есть."),
         ("IV · Император", "Порядок и границы. Скажите «нет» без объяснений."), ("V · Иерофант", "Спросите совета у опытного человека."),
         ("VI · Влюблённые", "Выбор сердцем, но с головой на месте."), ("VII · Колесница", "Двигайтесь вперёд, победа любит упорных."),
         ("VIII · Сила", "Мягкость сильнее напора. Особенно в чате."), ("IX · Отшельник", "Нужна пауза и время наедине с мыслями."),
         ("X · Колесо Фортуны", "Перемены к лучшему. Ловите момент."), ("XI · Справедливость", "За всё придётся отвечать. Но и награда будет."),
         ("XII · Повешенный", "Посмотрите на ситуацию иначе и не спешите."), ("XIII · Смерть", "Конец старого, начало нового. Не буквально."),
         ("XIV · Умеренность", "Баланс во всём, включая кофе."), ("XV · Дьявол", "Не поддавайтесь соблазнам и привычкам."),
         ("XVI · Башня", "Неожиданность, которая расчистит путь."), ("XVII · Звезда", "Надежда и вдохновение. Всё наладится."),
         ("XVIII · Луна", "Не всё так, как кажется. Проверьте детали."), ("XIX · Солнце", "Радость, успех, тёплые новости."),
         ("XX · Суд", "Время подвести итоги и принять решение."), ("XXI · Мир", "Завершение этапа и награда за труд.")]
COMPAT_TEXT = {"high": "💞 Вам повезло: ругаться из-за посуды будете, но недолго.",
               "mid": "🙂 Жить можно. Главное, заранее договориться, кто выносит мусор.",
               "low": "⚡ Будет весело. Возможно, слишком. Запаситесь терпением и чаем."}
PET_RITUALS = ["Подойдите к коту и погладьте его три раза от макушки к хвосту. Если он мурчит, удача засчитана.",
               "Почешите кота за ухом и скажите ему «спасибо» вслух. Да, это важно.",
               "Погладьте кошку по спине и подумайте о чём-то хорошем. Хотя бы про ужин.",
               "Сядьте рядом с котом на минуту. Просто сядьте. Больше ничего не нужно.",
               "Поздоровайтесь с котом первым. Хорошие дни начинаются с уважения."]
PET_NOCAT = ["Нет кота? Сойдёт кошка, соседский кот, плюшевый или фото в телефоне (эффективность 40%).",
             "Нет кота? Погладьте что-нибудь пушистое. Плед тоже считается."]

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


def find_photo(name: str):
    for folder in (BASE / "img", BASE):
        p = folder / f"{name}.jpg"
        if p.exists():
            return p
    return None

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


def translate_block(r) -> str:
    a, human = r.choice(TRANSLATE)
    return f"🪐 *Звёзды говорят:* «{a}»\n🗣 *По-человечески:* {human}"


def h_day(r) -> str:
    h = r.randint(8, 18)
    return (f"{translate_block(r)}\n\n"
            f"🌅 *Утро.* {r.choice(MORNING)}\n☀️ *День.* {r.choice(AFTERNOON)}\n🌙 *Вечер.* {r.choice(EVENING)}\n\n"
            f"💼 *Работа.* {r.choice(WORK)}\n💰 *Деньги.* {r.choice(MONEY)}\n"
            f"❤️ *Любовь.* {r.choice(LOVE)}\n🍀 *Здоровье.* {r.choice(HEALTH)}\n\n"
            f"🛋 *Прокрастинация* {r.choice(PROCRAST)}\n✅ *Но одно дело сделайте:* {r.choice(ONE_THING)}\n"
            f"🐈 *Ритуал:* {r.choice(PET_SHORT)}\n\n"
            f"{r.choice(SERIOUS)}\n\n"
            f"⏰ Удачное время: {h}:00–{h + 2}:00 · ⚡ Энергия {pct(r)}% (кофе не считается)\n"
            f"🎨 {r.choice(COLORS)} · 🔢 {r.randint(1, 99)}\n\n_P.S. {r.choice(PS)}_")


def h_week(r) -> str:
    d = r.sample(range(7), 3)
    return (f"{translate_block(r)}\n\n🔮 *Настрой недели.* {r.choice(WEEK_GENERAL)}\n\n"
            f"💼 *Работа.* {r.choice(WORK)}\n💰 *Деньги.* {r.choice(MONEY)}\n"
            f"❤️ *Любовь.* {r.choice(LOVE)}\n🍀 *Здоровье.* {r.choice(HEALTH)}\n\n"
            f"✅ Удачные дни: {WEEKDAYS[d[0]]}, {WEEKDAYS[d[1]]}\n⚠️ Осторожнее {WEEKDAYS_IN[d[2]]}\n"
            f"🛋 *Прокрастинация* {r.choice(PROCRAST)}\n🐈 *Ритуал:* {r.choice(PET_SHORT)}\n\n"
            f"{r.choice(SERIOUS)}\n\n⚡ Энергия {pct(r)}% · 🍀 Удача {pct(r)}%\n🎨 {r.choice(COLORS)} · 🔢 {r.randint(1, 99)}\n\n"
            f"_P.S. {r.choice(PS)}_")


def h_month(r) -> str:
    t = dt.date.today()
    days = sorted(r.sample(range(1, calendar.monthrange(t.year, t.month)[1] + 1), 3))
    dates = "\n".join(f"• {x:02d}.{t.month:02d}: {r.choice(DATE_NOTES)}" for x in days)
    return (f"{translate_block(r)}\n\n🔮 *Главная тема.* {r.choice(MONTH_GENERAL)}\n\n📆 *По декадам*\n"
            f"1–10: {r.choice(DECADES[0])}\n11–20: {r.choice(DECADES[1])}\n21–конец: {r.choice(DECADES[2])}\n\n"
            f"💼 Работа {stars(r.randint(2, 5))}\n❤️ Любовь {stars(r.randint(2, 5))}\n"
            f"💰 Финансы {stars(r.randint(2, 5))}\n🍀 Здоровье {stars(r.randint(2, 5))}\n\n"
            f"📌 *Ключевые даты*\n{dates}\n\n{r.choice(SERIOUS)}\n\n_P.S. {r.choice(PS)}_")


def local_horoscope(sign: str, period: str) -> str:
    e, name = SIGNS[sign][0], SIGNS[sign][1]
    head = f"{e} *{name}* · {period_title(period)}\n🌙 {moon_line()}\n\n"
    r = random.Random(f"{sign}-{period}-{period_key(period)}")  # одинаково в течение периода
    return head + {"day": h_day, "week": h_week, "month": h_month}[period](r)


async def get_horoscope(sign: str, period: str) -> str:
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


def boss_text(me: str, boss: str) -> str:
    r = random.Random("boss" + me + boss)
    ea, eb = SIGNS[me][3], SIGNS[boss][3]
    base = 70 if ea == eb else 62 if {ea, eb} in ({"fire", "air"}, {"earth", "water"}) else 40
    score = max(8, min(90, base + r.randint(-15, 15)))
    head = f"👔 *Вы* {SIGNS[me][0]} {SIGNS[me][1]} + *начальник* {SIGNS[boss][0]} {SIGNS[boss][1]}\n\n"
    if boss == "capricorn":
        return (head + "Совместимость: *7%*\n\n😶 Спойлер: он Козерог, так что бесполезно.\n"
                "Он видит график работы, а не ваши эмоции. Отгулы только по согласованию с вселенной.\n\n"
                "Серьёзно: Козерогов убеждают цифрами и сроками, а не обаянием. Приходите с фактами.")
    raise_chance, day_off = r.randint(5, 45), r.randint(20, 90)
    tip = r.choice(["приносите решения, а не проблемы, и всё станет проще.", "договаривайтесь заранее, а не в пятницу в 17:55.",
                    "пишите коротко и по делу, начальство ценит время.", "хвалите себя сами: начальник может не догадаться."])
    return (head + f"Совместимость: *{score}%*\n💸 Шанс на повышение: {raise_chance}%\n🏖 Шанс на отгул: {day_off}%\n\n"
            f"Серьёзно: {tip}\n\n_P.S. Звёзды зарплату не приносят, переговоры приносят._")


def tarot_text(uid) -> str:
    r = random.Random(f"{uid}-{dt.date.today().isoformat()}")
    name, meaning = r.choice(TAROT)
    return f"🃏 *Ваша карта дня*\n\n*{name}*\n{meaning}\n\n_Развлечение, а не руководство к действию._"


def pet_done(uid):
    today = dt.date.today()
    last, streak = db_get(uid, "pet_last"), db_get(uid, "pet_streak", 0)
    if last == today.isoformat():
        return streak, False
    streak = streak + 1 if last == (today - dt.timedelta(days=1)).isoformat() else 1
    db_set(uid, pet_last=today.isoformat(), pet_streak=streak)
    return streak, True


def pet_result(streak: int, new: bool) -> str:
    if not new:
        return "✅ Сегодня вы уже гладили. Больше уже не ритуал, а навязчивость (но кот не против)."
    if streak == 1:
        extra = "Удача +1. Кот доволен."
    elif streak < 7:
        extra = f"Серия: {streak} дн. подряд. Кот вас уважает."
    else:
        extra = f"Серия: {streak} дн.! Звёзды в шоке, кот тоже."
    return f"✅ Засчитано! {extra}"


def pet_caption(uid) -> str:
    r = random.Random(f"pet-{uid}-{dt.date.today().isoformat()}")
    streak = db_get(uid, "pet_streak", 0)
    line = f"\nСерия: {streak} дн." if streak else ""
    return (f"🐈 *Ритуал дня: погладь кота*\n\n{r.choice(PET_RITUALS)}\n\n{r.choice(PET_NOCAT)}{line}\n\n"
            f"_После ритуала нажмите кнопку, чтобы удача засчиталась._")

# ---------------------------------------------------------------- клавиатуры
def signs_grid(prefix: str, extra_rows=()) -> M:
    items = list(SIGNS.items())
    rows = [[B(f"{v[0]} {v[1]}", callback_data=f"{prefix}:{k}") for k, v in items[i:i + 3]]
            for i in range(0, 12, 3)]
    rows.extend(extra_rows)
    return M(rows)


def home_kb(uid) -> M:
    extra = [[B("📆 Знак по дате", callback_data="date"), B("🃏 Карта дня", callback_data="tarot:")],
             [B("🐈 Погладь кота", callback_data="cat:"), B("🎱 Шар", callback_data="ball")]]
    me = db_get(uid, "sign")
    if me:
        extra.insert(0, [B(f"👤 Мой знак: {SIGNS[me][0]} {SIGNS[me][1]}", callback_data=f"s2:{me}")])
    return signs_grid("s", extra)


def sign_menu(sign: str, uid) -> M:
    sub = db_get(uid, "sub", False)
    return M([
        [B(v, callback_data=f"p:{sign}:{k}") for k, v in PERIODS.items()],
        [B("🧬 Характер", callback_data=f"c:{sign}"), B("💞 Совместимость", callback_data=f"k:{sign}")],
        [B("🐈 Погладь кота", callback_data=f"cat:{sign}"), B("🃏 Карта дня", callback_data=f"tarot:{sign}")],
        [B("🎱 Шар", callback_data="ball"), B("🔕 Рассылка: выкл" if sub else "🔔 Рассылка 8:00", callback_data=f"sub:{sign}")],
        [B("⬅️ Другой знак", callback_data="home")],
    ])


def after_kb(sign: str, cur: str) -> M:
    others = [B(PERIODS[p], callback_data=f"p:{sign}:{p}") for p in PERIODS if p != cur]
    return M([others,
              [B("💞 Совместимость", callback_data=f"k:{sign}"), B("🐈 Погладь кота", callback_data=f"cat:{sign}")],
              [B("📤 Отправить в чат", switch_inline_query=SIGNS[sign][1])],
              [B("⬅️ В меню", callback_data=f"s2:{sign}")]])


def back_kb(sign: str) -> M:
    return M([[B("⬅️ Назад", callback_data=f"s2:{sign}" if sign else "home")]])


HOME_TEXT = ("✨ *Астрология без напряга* ✨\nДля тех, у кого нет сил даже на медитацию.\n\n"
             f"_{MOTTO}_\n\nВыберите знак зодиака:")


def menu_text(sign: str) -> str:
    e, name, dates, el, _, tag = SIGNS[sign]
    return f"{e} *{name}* · {dates}\nСтихия: {ELEMENTS[el]}\n_«{tag}»_\n\nЧто показать?"


async def put(q, ctx, text, kb, parse="Markdown"):
    """Правит сообщение; если это фото, то заменяет его текстовым."""
    if q.message.photo:
        chat = q.message.chat_id
        await q.message.delete()
        await ctx.bot.send_message(chat, text, reply_markup=kb, parse_mode=parse)
    else:
        await q.edit_message_text(text, reply_markup=kb, parse_mode=parse)


async def show_sign(bot, chat_id, uid, sign):
    e, name, dates, el, _, tag = SIGNS[sign]
    photo = find_photo(sign)
    if photo:
        with open(photo, "rb") as f:
            await bot.send_photo(chat_id, f)
    await bot.send_message(chat_id, menu_text(sign), reply_markup=sign_menu(sign, uid), parse_mode="Markdown")

# ---------------------------------------------------------------- обработчики
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.pop("mode", None)
    uid, chat = update.effective_user.id, update.effective_chat.id
    photo = find_photo("welcome")
    if photo:
        with open(photo, "rb") as f:
            await ctx.bot.send_photo(chat, f)
    await ctx.bot.send_message(chat, HOME_TEXT, reply_markup=home_kb(uid), parse_mode="Markdown")


async def on_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid = q.from_user.id
    parts = q.data.split(":")
    act = parts[0]
    if act != "sub":
        await q.answer()

    if act == "home":
        ctx.user_data.pop("mode", None)
        await put(q, ctx, HOME_TEXT, home_kb(uid))

    elif act == "s":
        sign = parts[1]
        db_set(uid, sign=sign, chat=q.message.chat_id)
        await q.message.delete()
        await show_sign(ctx.bot, q.message.chat_id, uid, sign)

    elif act == "s2":
        await put(q, ctx, menu_text(parts[1]), sign_menu(parts[1], uid))

    elif act == "p":
        await put(q, ctx, await get_horoscope(parts[1], parts[2]), after_kb(parts[1], parts[2]))

    elif act == "c":
        e, name, dates, el, text, tag = SIGNS[parts[1]]
        await put(q, ctx, f"{e} *{name}* · характер\n\n{text}\n\nСтихия: {ELEMENTS[el]}", back_kb(parts[1]))

    elif act == "k":
        sign = parts[1]
        extra = [[B("👔 Совместимость с начальником", callback_data=f"boss:{sign}")],
                 [B("⬅️ Назад", callback_data=f"s2:{sign}")]]
        await put(q, ctx, f"💞 Совместимость для {SIGNS[sign][0]} {SIGNS[sign][1]}.\nВыберите партнёра:",
                  signs_grid(f"k2:{sign}", extra), parse=None)

    elif act == "k2":
        a, b = parts[1], parts[2]
        kb = M([[B("💞 Другой знак", callback_data=f"k:{a}")], [B("⬅️ В меню", callback_data=f"s2:{a}")]])
        await put(q, ctx, compatibility(a, b), kb)

    elif act == "boss":
        sign = parts[1]
        await put(q, ctx, "👔 Какой знак у вашего начальника?\n(Спойлер: вы уже догадываетесь.)",
                  signs_grid(f"b2:{sign}", [[B("⬅️ Назад", callback_data=f"k:{sign}")]]), parse=None)

    elif act == "b2":
        me, boss = parts[1], parts[2]
        kb = M([[B("👔 Другой начальник", callback_data=f"boss:{me}")], [B("⬅️ В меню", callback_data=f"s2:{me}")]])
        await put(q, ctx, boss_text(me, boss), kb)

    elif act == "tarot":
        sign = parts[1] if len(parts) > 1 else ""
        await put(q, ctx, tarot_text(uid), back_kb(sign))

    elif act == "cat":
        sign = parts[1] if len(parts) > 1 else ""
        kb = M([[B("✅ Погладил(а), засчитай", callback_data=f"pet:{sign}")],
                [B("⬅️ Назад", callback_data=f"s2:{sign}" if sign else "home")]])
        photo = find_photo("cat")
        chat = q.message.chat_id
        await q.message.delete()
        if photo:
            with open(photo, "rb") as f:
                await ctx.bot.send_photo(chat, f, caption=pet_caption(uid), reply_markup=kb, parse_mode="Markdown")
        else:
            await ctx.bot.send_message(chat, pet_caption(uid), reply_markup=kb, parse_mode="Markdown")

    elif act == "pet":
        sign = parts[1] if len(parts) > 1 else ""
        streak, new = pet_done(uid)
        kb = back_kb(sign)
        text = f"🐈 *Ритуал дня*\n\n{pet_result(streak, new)}\n\n_P.S. {random.choice(PS)}_"
        if q.message.photo:
            await q.edit_message_caption(caption=text, reply_markup=kb, parse_mode="Markdown")
        else:
            await q.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")

    elif act == "ball":
        ctx.user_data["mode"] = "ball"
        await put(q, ctx, "🎱 Задумайте вопрос, на который можно ответить «да» или «нет», и напишите его сообщением.",
                  M([[B("⬅️ Отмена", callback_data="home")]]), parse=None)

    elif act == "date":
        ctx.user_data["mode"] = "date"
        await put(q, ctx, "📆 Напишите дату рождения числом и месяцем, например: 14.08",
                  M([[B("⬅️ Отмена", callback_data="home")]]), parse=None)

    elif act == "sub":
        if ctx.application.job_queue is None:
            await q.answer("Рассылка недоступна: в requirements.txt нужна строка python-telegram-bot[job-queue]",
                           show_alert=True)
            return
        new = not db_get(uid, "sub", False)
        db_set(uid, sub=new, sign=parts[1], chat=q.message.chat_id)
        await q.answer("🔔 Гороскоп будет приходить каждое утро в 8:00. Звёзды проснулись раньше вас." if new
                       else "🔕 Рассылка выключена. Спите спокойно.", show_alert=True)
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


def short_day(sign: str) -> str:
    """Краткий прогноз: один на весь день, одинаковый при каждом вызове сегодня."""
    e, name = SIGNS[sign][0], SIGNS[sign][1]
    r = random.Random(f"{sign}-short-{dt.date.today().isoformat()}")
    a, human = r.choice(TRANSLATE)
    return (f"{e} *{name}* · сегодня, {dt.date.today():%d.%m}\n\n"
            f"🪐 «{a}»\n🗣 {human}\n\n"
            f"💼 {r.choice(WORK)}\n🛋 Прокрастинация {r.choice(PROCRAST)}\n"
            f"🐈 {r.choice(PET_SHORT).capitalize()}\n\n"
            f"⚡ Энергия {pct(r)}% · 🎨 {r.choice(COLORS)} · 🔢 {r.randint(1, 99)}\n"
            f"_P.S. {r.choice(PS)}_")


def build_inline(query: str, uid) -> list:
    """Результаты для @имя_бота в любом чате: (id, заголовок, описание, текст)."""
    words = [w for w in query.lower().split() if len(w) >= 2]
    found = []
    for w in words:
        for k, v in SIGNS.items():
            if v[1].lower().startswith(w) and k not in found:
                found.append(k)
    out = []

    def add(rid, title, text, desc=None):
        if desc is None:
            desc = re.sub(r"[*_`]", "", text.split("\n\n")[1] if "\n\n" in text else text)[:90].replace("\n", " ")
        out.append((rid, title, desc, text))

    if len(found) >= 2:
        a, b = found[0], found[1]
        add(f"k-{a}-{b}", f"💞 {SIGNS[a][1]} + {SIGNS[b][1]}: совместимость", compatibility(a, b))
        add(f"b-{a}-{b}", f"👔 {SIGNS[a][1]} и начальник {SIGNS[b][1]}", boss_text(a, b))
    if found:
        for sign in found[:2]:
            e, name = SIGNS[sign][0], SIGNS[sign][1]
            add(f"s-{sign}", f"{e} {name} · коротко на сегодня", short_day(sign))
            if len(found) == 1:
                add(f"h-{sign}-day", f"{e} {name} · подробно на сегодня", local_horoscope(sign, "day"))
                add(f"h-{sign}-week", f"{e} {name} · на неделю", local_horoscope(sign, "week"))
                add(f"h-{sign}-month", f"{e} {name} · на месяц", local_horoscope(sign, "month"))
                add(f"c-{sign}", f"🧬 {name}: характер", f"{e} *{name}* · характер\n\n{SIGNS[sign][4]}")
    else:
        me = db_get(uid, "sign")
        order = ([me] if me else []) + [k for k in SIGNS if k != me]
        for sign in order:
            e, name = SIGNS[sign][0], SIGNS[sign][1]
            title = f"{e} Мой знак · {name}, коротко на сегодня" if sign == me else f"{e} {name} · коротко на сегодня"
            add(f"s-{sign}", title, short_day(sign))
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
                photo = find_photo(u["sign"])
                if photo:
                    with open(photo, "rb") as f:
                        await ctx.bot.send_photo(u["chat"], f)
                text = await get_horoscope(u["sign"], "day")
                await ctx.bot.send_message(u["chat"], "☀️ Доброе утро! Звёзды проснулись раньше вас.\n\n" + text,
                                           parse_mode="Markdown")
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
