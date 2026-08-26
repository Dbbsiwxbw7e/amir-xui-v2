"""All user-facing text + keyboards."""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import config

APP = "⚡️ AMIR X-UI V2 ⚡️"
TOP = "╔══════════════════════╗"
MID = "╠══════════════════════╣"
BOT = "╚══════════════════════╝"
S = "║"

def hdr(sub=""):
    h = f"{TOP}\n{S}  <b>{APP}</b>  {S}\n"
    if sub:
        h += f"{S}  <i>{sub}</i>  {S}\n"
    return h + BOT

MENU = InlineKeyboardMarkup([
    [InlineKeyboardButton("👤 اکانت‌ها", callback_data="sec_account"),
     InlineKeyboardButton("🚀 دپلوی", callback_data="sec_deploy")],
    [InlineKeyboardButton("🔌 پروتکل‌ها", callback_data="sec_proto")],
])

def welcome(name="", account=""):
    who = f"، {name}" if name else ""
    badge = (f"👤 اکانت فعال: <b>{account}</b>\n" if account
             else "⚪️ اکانتی ثبت نشده — بخش 👤 اکانت‌ها\n")
    return (f"{hdr(f'سلام{who} 👋')}\n\n{badge}"
            "🎛 مدیریت کامل 3x-ui روی Railway\n\n"
            f"{MID}\n👇 انتخاب کن:")

NOT_CONNECTED = (f"{hdr('قفل 🔒')}\n\n"
                 "اول از بخش 👤 <b>اکانت‌ها</b> یه اکانت Railway اضافه کن.\n\n"
                 f"{BOT}")

HELP = (f"{hdr('راهنما 📖')}\n\n"
        "👤 <b>اکانت‌ها</b> — چند توکن Railway، سوییچ آنی\n\n"
        "🚀 <b>دپلوی</b> — فلو ۴ مرحله‌ای:\n"
        "     1️⃣ دپلوی پنل‌ها + ۴ اینباند ws+tls هرکدوم\n"
        "     2️⃣ ⏸ مکث → ست ریجن توسط شما\n"
        "     3️⃣ 🌐 ست دامنه‌ها\n"
        "     4️⃣ 🔗 اتصال نودها\n\n"
        "🔌 <b>پروتکل‌ها</b> — ساخت اینباند ws+tls روی هر پنل\n\n"
        f"{MID}\n⚠️ بعد از افزودن اکانت، پیام حاوی توکن رو پاک کن 🗑")

# ── accounts ──
def accounts_text(accs, active):
    if not accs:
        body = "  (خالی)"
    else:
        body = "\n".join(
            f'{"🟢" if a["active"] else "⚪️"} <b>{a["label"]}</b>'
            + (f' · <code>{a["email"]}</code>' if a.get("email") else "")
            for a in accs)
    return f"{hdr('اکانت‌ها 👤')}\n\n{body}\n\n{MID}\n🟢 فعال: <b>{active or '—'}</b>"

def accounts_kb(accs):
    rows = []
    for a in accs:
        lbl = a["label"]
        if a["active"]:
            rows.append([InlineKeyboardButton(f"🟢 {lbl} (فعال)", callback_data="noop")])
        else:
            rows.append([InlineKeyboardButton(f"⚪️ سوییچ به {lbl}", callback_data=f"accsw:{lbl}"),
                         InlineKeyboardButton("🗑", callback_data=f"accdel:{lbl}")])
    rows.append([InlineKeyboardButton("➕ افزودن اکانت", callback_data="accadd")])
    rows.append([InlineKeyboardButton("🔙 منوی اصلی", callback_data="refresh_menu")])
    return InlineKeyboardMarkup(rows)

ADD_ACCOUNT = ("{h}\n\n1️⃣ یه <b>اسم</b> بفرست (مثلاً <code>اصلی</code>)\n"
               "2️⃣ بعد <b>توکن Railway</b> رو بفرست\n\nلغو: /cancel")

# ── deploy ──
def deploy_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 شروع فلو کامل", callback_data="go_deploy")],
        [InlineKeyboardButton("🔙 منوی اصلی", callback_data="refresh_menu")],
    ])

DEPLOY_WELCOME = (
    f"{hdr('دپلوی 🚀')}\n\n"
    "1️⃣ 📦 دپلوی پنل‌ها + ۴ اینباند ws+tls هر پنل\n"
    "2️⃣ ⏸ مکث → ریجن‌ها رو خودت ست می‌کنی\n"
    "3️⃣ 🌐 ادامه → دامنه‌ها ست میشن\n"
    "4️⃣ 🔗 ادامه → نودها وصل میشن\n\n"
    f"{MID}\n👇 آماده‌ای?")

STAGE2_PROMPT = ("✅ پنل‌ها و اینباندها آماده!\n\n"
                 "⏸ حالا وارد هر پنل شو و ریجن رو تنظیم کن:\n")

def stage2_kb():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ ست کردم — ادامه (دامنه‌ها)", callback_data="flow_domains")]])

def stage4_kb():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🔗 مرحله آخر — اتصال نودها", callback_data="flow_nodes")],
        [InlineKeyboardButton("🔙 منوی اصلی", callback_data="refresh_menu")]])

# ── protocols ──
def proto_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🌐 WS + TLS", callback_data="proto_pick")],
        [InlineKeyboardButton("🔙 منوی اصلی", callback_data="refresh_menu")],
    ])

PROTO_WELCOME = (
    f"{hdr('پروتکل‌ها 🔌')}\n\n"
    "🌐 <b>WS + TLS</b>\n"
    "     └ VLESS + WebSocket + TLS\n"
    f"     └ پورت {config.IN_PORT} · مسیر {config.IN_PATH}\n\n"
    f"{MID}\n👇 انتخاب کن:")
