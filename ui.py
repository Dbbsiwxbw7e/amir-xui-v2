"""
All UI text and keyboards — boxed console style.
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

APP = "⚡️ AMIR X-UI V2 ⚡️"
TOP, MID, BOT_, S = "╔══════════════════════╗", "╠══════════════════════╣", "╚══════════════════════╝", "║"

def header(sub=""):
    h = f"{TOP}\n{S}  <b>{APP}</b>  {S}\n"
    if sub: h += f"{S}  <i>{sub}</i>  {S}\n"
    return h + BOT_

ICONS = {"SUCCESS":"🟢","FAILED":"🔴","CRASHED":"💥","DEPLOYING":"🟡",
         "BUILDING":"🟡","WAITING":"⚪️","REMOVED":"⚫️"}

MENU = InlineKeyboardMarkup([
    [InlineKeyboardButton("👤 اکانت‌ها", callback_data="sec_account"),
     InlineKeyboardButton("🚀 دپلوی", callback_data="sec_deploy")],
    [InlineKeyboardButton("🔌 پروتکل‌ها", callback_data="sec_proto")],
])

def welcome(name="", account=""):
    who = f"، {name}" if name else ""
    badge = f"👤 اکانت فعال: <b>{account}</b>\n" if account else "⚪️ هنوز اکانتی اضافه نکردی\n"
    return (f"{header(f'سلام{who} 👋')}\n\n"
            f"{badge}"
            "🎛 کنترل کامل 3x-ui روی Railway\n\n"
            f"{MID}\n👇 یک بخش رو انتخاب کن:")

NOT_CONNECTED = (f"{header('قفل 🔒')}\n\n"
                 "اول از بخش 👤 <b>اکانت‌ها</b> یه اکانت Railway اضافه کن.\n\n"
                 f"{BOT_}")

HELP = (f"{header('راهنما 📖')}\n\n"
        "👤 <b>اکانت‌ها</b> — افزودن/سوییچ/حذف توکن Railway\n\n"
        "🚀 <b>دپلوی</b> — فلو ۴ مرحله‌ای:\n"
        "     1️⃣ دپلوی پنل‌ها + ساخت ۴ اینباند\n"
        "     2️⃣ ⏸ مکث → ست ریجن توسط شما\n"
        "     3️⃣ 🌐 ست دامنه‌ها\n"
        "     4️⃣ 🔗 اتصال نودها\n\n"
        "🔌 <b>پروتکل‌ها</b> — ws+tls و بقیه\n\n"
        f"{MID}\n⚠️ بعد از افزودن اکانت، پیام حاوی توکن رو پاک کن 🗑")

# ── accounts ──
def accounts_text(accounts, active):
    if not accounts: body = "  (خالی)"
    else:
        body = "\n".join(
            f'{"🟢" if a["active"] else "⚪️"} <b>{a["label"]}</b>'
            + (f' · <code>{a["email"]}</code>' if a.get("email") else "")
            for a in accounts)
    return (f"{header('اکانت‌ها 👤')}\n\n{body}\n\n{MID}\n"
            f"🟢 فعال: <b>{active or '—'}</b>")

def accounts_keyboard(accounts):
    rows = []
    for a in accounts:
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

# ── deploy section ──
def deploy_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 دپلوی کامل (۴ اینباند + دامنه + نود)",
                              callback_data="go_deploy")],
        [InlineKeyboardButton("🔙 منوی اصلی", callback_data="refresh_menu")],
    ])

DEPLOY_WELCOME = (
    f"{header('دپلوی 🚀')}\n\n"
    "فلو خودکار:\n\n"
    "1️⃣ 📦 دپلوی پنل‌ها + ساخت ۴ اینباند ws+tls\n"
    "2️⃣ ⏸ مکث → شما ریجن‌ها رو توی پنل‌ها ست می‌کنید\n"
    "3️⃣ 🌐 با زدن «ادامه»، دامنه‌ها ست میشن\n"
    "4️⃣ 🔗 نودها به پنل اصلی وصل میشن\n\n"
    f"{MID}\n👇 آماده‌ای؟"
)

def progress(step, total, title, detail=""):
    filled = round(step*14/max(total,1))
    bar = "▓"*filled + "░"*(14-filled)
    txt = (f"{header('در حال اجرا...')}\n\n{bar} <b>"
           f"{round(step*100/max(total,1))}%</b>\n📍 {step}/{total}\n\n{MID}\n{title}")
    if detail: txt += f"\n{detail}"
    return txt

def panel_rows(panels):
    s = ""
    for p in panels:
        ic = ICONS.get(p.get("status",""), "⏳")
        s += f"\n{ic} <b>{p['name']}</b> · {p.get('region','')}"
        if p.get("url"):
            s += f"\n     🌐 {p['url'].replace('https://','')}/managepanel/"
    return s
