"""
Amir X-UI V2 — entry point.

Sections:
  👤 Accounts  — multi Railway tokens
  🚀 Deploy    — staged wizard:
       stage1: deploy panels + create 4 ws+tls inbounds each
       stage2: pause → user sets regions → presses continue
       stage3: set domains (port 3000)
       stage4: link nodes to main panel
  🔌 Protocols — ws+tls inbound creator (amir_xu spec)
"""
import asyncio, logging, os, uuid

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (ApplicationBuilder, CommandHandler, CallbackQueryHandler,
                          ContextTypes, MessageHandler, filters)

import config, ui
from railway_api import RailwayAPI, RailwayError
from xui_api import PanelClient, XUIError, build_vless_link
from account_store import Accounts

ACC = Accounts()
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("amir-v2")


# ── helpers ──
def active_token(ctx): return ctx.user_data.get("_tok") or ""

def refresh_active(ctx, uid):
    acc = ACC.get(uid)
    if acc: ctx.user_data["_tok"] = acc["token"]
    else: ctx.user_data.pop("_tok", None)

def get_api(ctx):
    return RailwayAPI(active_token(ctx)) if active_token(ctx) else None

async def run_blocking(fn, *a): return await asyncio.to_thread(fn, *a)


def _require_token_wrap(fn):
    async def wrapper(update, ctx):
        refresh_active(ctx, update.effective_user.id)
        if not active_token(ctx):
            t = origin(update)
            if t: await t.reply_text(ui.NOT_CONNECTED, parse_mode="HTML")
            return
        return await fn(update, ctx)
    return wrapper


async def say(msg, text, keyboard=None):
    try: await msg.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    except Exception: pass

def origin(update):
    return update.message or (update.callback_query.message if update.callback_query else None)


# ── commands ──
async def cmd_start(update, ctx):
    uid = update.effective_user.id
    refresh_active(ctx, uid)
    await update.message.reply_text(
        ui.welcome(update.effective_user.first_name or "", ACC.active_label(uid)),
        reply_markup=ui.MENU, parse_mode="HTML")


async def cancel_cmd(update, ctx):
    uid = update.effective_user.id
    u = ctx.user_data.get(uid) or {}
    cleared = (u.pop("await_acc_label", None) or u.pop("pending_acc_label", None))
    await update.message.reply_text(
        ui.header("لغو شد ❌") if cleared else "چیزی برای لغو نبود.", parse_mode="HTML")


async def on_text(update, ctx):
    uid = update.effective_user.id
    u = ctx.user_data.get(uid) or {}

    if u.pop("await_acc_label", None):
        u["pending_acc_label"] = update.message.text.strip()[:32]
        await update.message.reply_text(
            ui.ADD_ACCOUNT.replace("{h}", ui.header(f"اکانت «{u['pending_acc_label']}» ➕"))
            + "\n\n🔑 حالا <b>توکن</b> رو بفرست:", parse_mode="HTML")
        return

    if "pending_acc_label" in u:
        label = u.pop("pending_acc_label")
        token = update.message.text.strip()
        st = await update.message.reply_text(ui.header("در حال بررسی... 🔍"), parse_mode="HTML")
        try:
            ws_id, email = await run_blocking(RailwayAPI(token).whoami)
            if not ACC.add(uid, label, token, email):
                await say(st, ui.header("تکراری ⚠️") + f"\n\nاسم {label} قبلاً هست.")
                return
            ACC.set_active(uid, label); refresh_active(ctx, uid)
            kb = ui.accounts_keyboard(ACC.list(uid))
            await say(st, f"{ui.header('اکانت اضافه شد ✅')}\n\n👤 {label} · <code>{email}</code>",
                      keyboard=kb)
        except RailwayError as e:
            await say(st, ui.header("توکن نامعتبر ⛔️") + f"\n\n<code>{e}</code>")


# ════════════════════════════════════════════
#  SECTION: ACCOUNTS
# ════════════════════════════════════════════
async def show_accounts(q, ctx, uid):
    await q.edit_message_text(ui.accounts_text(ACC.list(uid), ACC.active_label(uid)),
                              reply_markup=ui.accounts_keyboard(ACC.list(uid)),
                              parse_mode="HTML")


async def handle_accounts(update, ctx, q, data):
    uid = update.effective_user.id
    if data == "accadd":
        ctx.user_data.setdefault(uid, {})["await_acc_label"] = True
        await q.edit_message_text(ui.ADD_ACCOUNT.replace("{h}", ui.header("افزودن اکانت ➕")),
                                  parse_mode="HTML")
        return
    if data.startswith("accsw:"):
        lbl = data.split(":",1)[1]
        ok = ACC.set_active(uid, lbl); refresh_active(ctx, uid)
        accounts = ACC.list(uid)
        msg = f"{ui.header('سوییچ شد ✅' if ok else 'پیدا نشد ⛔️')}\n\n"
        await q.edit_message_text(msg, reply_markup=ui.accounts_keyboard(accounts), parse_mode="HTML")
        return
    if data.startswith("accdel:"):
        lbl = data.split(":",1)[1]
        ACC.remove(uid, lbl); refresh_active(ctx, uid)
        accounts = ACC.list(uid); act = ACC.active_label(uid)
        await q.edit_message_text(ui.accounts_text(accounts, act) + "\n\n🗑 حذف شد.",
                                  reply_markup=ui.accounts_keyboard(accounts), parse_mode="HTML")
        return


# ════════════════════════════════════════════
#  SECTION: DEPLOY — 4-stage wizard
# ════════════════════════════════════════════
def deploy_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 دپلوی کامل (۴ اینباند + دامنه + نود)", callback_data="go_deploy")],
        [InlineKeyboardButton("🔙 منوی اصلی", callback_data="refresh_menu")],
    ])

DEPLOY_WELCOME = (
    f"{ui.header('دپلوی 🚀')}\n\n"
    "فلو خودکار:\n\n"
    "1️⃣ 📦 دپلوی پنل‌ها + ساخت ۴ اینباند ws+tls\n"
    "2️⃣ ⏸ مکث → شما ریجن‌ها رو توی پنل‌ها ست می‌کنید\n"
    "3️⃣ 🌐 با زدن «ادامه»، دامنه‌ها ست میشن\n"
    "4️⃣ 🔗 نودها به پنل اصلی وصل میشن\n\n"
    f"{ui.MID}\n👇 آماده‌ای?"
)

async def show_deploy(update, ctx, q):
    await q.edit_message_text(DEPLOY_WELCOME, reply_markup=deploy_menu(), parse_mode="HTML")


@_require_token_wrap
async def cmd_deploy(update, ctx):
    """Stage 1: deploy panels + create inbounds. Then pause for region setting."""
    api = get_api(ctx)
    total = len(config.PANELS) + 2
    origin_msg = origin(update)
    status = await origin_msg.reply_text(
        ui.progress(0, total, "🚀 شروع..."), parse_mode="HTML")

    # project + env
    try:
        ws_id, email = await run_blocking(api.whoami)
        proj = await run_blocking(api.create_project, config.PROJECT_NAME, ws_id)
        pid = proj["id"]
        envs = await run_blocking(api.get_environments, pid)
        env_id = envs[0]["id"] if envs else ""
        ctx.user_data["_proj_id"] = pid
        ctx.user_data["_env_id"] = env_id
        await say(status, ui.progress(1, total, f"📦 پروژه: <code>{config.PROJECT_NAME}</code>"))
    except RailwayError as e:
        await say(status, f"{ui.header('خطا ⛔️')}\n\n❌ {e}")
        return

    # provision panels in parallel
    panels = []
    sem = asyncio.Semaphore(4)

    async def provision(p):
        async with sem:
            name = p["name"]
            try:
                svc = await run_blocking(api.create_service, name, pid, config.DOCKER_IMAGE)
                await run_blocking(api.deploy, svc["id"], env_id)
                domain = await run_blocking(api.create_domain, svc["id"], env_id,
                                            config.DOMAIN_TARGET_PORT)
                url = f"https://{domain}" if domain else ""
                panels.append({"name":name,"region":p["region"],"service_id":svc["id"],
                               "url":url,"status":"WAITING"})
                await say(status, ui.progress(1+len(panels), total,
                           f"🔨 {name} ارسال شد",
                           ui.panel_rows(panels)))
            except RailwayError as e:
                log.warning("provision %s: %s", name, e)

    await asyncio.gather(*(provision(p) for p in config.PANELS))
    if not panels:
        await say(status, ui.header("هیچ سرویسی ساخته نشد ⛔️")); return
    ctx.user_data["deployed_panels"] = list(panels)
    provisioned = list(panels)

    # poll until SUCCESS / FAILED
    loop = asyncio.get_event_loop()
    deadline = loop.time() + config.DEPLOY_POLL_TIMEOUT
    while panels and loop.time() < deadline:
        await asyncio.sleep(config.DEPOLL_INT if hasattr(config,'DEPOLL_INT') else config.DEPLOY_POLL_INTERVAL)
        pending = []
        for p in panels:
            d = await run_blocking(api.latest_deployment, p["service_id"])
            st = (d or {}).get("status",""); p["status"] = st or "WAITING"
            if st == "SUCCESS":
                p["ready"] = True
                if not p["url"] and d.get("staticUrl"): p["url"] = f"https://{d['staticUrl']}"
            elif st in ("FAILED","CRASHED","REMOVED"): p["failed"] = True
            else: pending.append(p)
        done = sum(1 for p in provisioned if p.get("ready") or p.get("failed"))
        await say(status, ui.progress(2, total, f"📡 SUCCESS ({done}/{len(provisioned)})",
                                      ui.panel_rows(provisioned)))
        panels = pending

    # report
    lines, ok = [], 0
    for p in provisioned:
        d = await run_blocking(api.latest_deployment, p["service_id"])
        st = (d or {}).get("status") or "WAITING"; p["status"] = st
        if st == "SUCCESS":
            ok += 1
            if not p["url"] and d.get("staticUrl"): p["url"] = f"https://{d['staticUrl']}"
        lines.append(f"{ui.ICONS.get(st,'⏳')} <b>{p['name']}</b>"
                     + (f"\n     🌐 {p['url'].replace('https://','')}/managepanel/"
                        if p.get("url") else f" · {st}"))

    await say(status,
              f"{ui.header(f'گزارش دپلوی ✅ ({ok}/{len(provisioned)})')}\n{ui.MID}\n"
              + "\n".join(lines))

    # ── STAGE 1b: create 4 ws+tls inbounds per panel ──
    await say(status, ui.header("مرحله ۱b — ساخت ۴ اینباند برای هر پنل..."))
    inbound_lines = []
    for p in provisioned:
        if not p.get("url"): continue

        def _mk(p=p):
            c = PanelClient(p["url"], config.XUI_USERNAME, config.XUI_PASSWORD)
            if not c.login(): raise XUIError(f"login fail {p['name']}")
            made = 0
            for k in range(config.INBOUNDS_PER_PANEL):
                u = str(uuid.uuid4())
                r = c.create_ws_tls_inbound(uuid=u, email=f"{p['name'].lower()}-in{k+1}",
                                            domain=p['url'].replace("https://",""),
                                            port=config.INBOUND_PORT,
                                            path=config.INBOUND_PATH)
                if r.get("success"): made += 1
            return made

        try:
            n = await run_blocking(_mk)
            inbound_lines.append(f"✅ <b>{p['name']}</b> ← {n}/{config.INBOUNDS_PER_PANEL} اینباند")
        except Exception as e:
            inbound_lines.append(f"⚠️ <b>{p['name']}</b> → {str(e)[:50]}")

    await say(status,
              ui.header("اینباندها ساخته شدن ✅")
              + f"\n{ui.MID}\n" + "\n".join(inbound_lines))

    # ── STAGE 2: PAUSE — user sets regions ──
    panel_list = "\n".join(f"  🌐 <code>{p['url'].replace('https://','')}/managepanel/</code>"
                          for p in provisioned if p.get("url"))
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ ریجن‌ها ست شد — ادامه (دامنه‌ها)", callback_data="flow_stage3")],
        [InlineKeyboardButton("⏭ رد شو — مستقیم دامنه‌ها", callback_data="flow_stage3")]])
    await say(status,
              ui.header("مرحله ۲/۴ — تنظیم ریجن‌ها ⏸")
              + f"\n{ui.MID}\n"
              + "✅ پنل‌ها و اینباندها آماده!\\n\\n"
              "⏸ حالا وارد هر پنل شو و **ریجن** رو تنظیم کن:\\n"
              + panel_list
              + f"\n\n{ui.BOT_}\\n👇 بعد از تموم شدن بزن:",
              keyboard=kb)



# ── stage 3: set domains ──
async def flow_stage3(update, ctx):
    refresh_active(ctx, update.effective_user.id)
    api = get_api(ctx)
    if not api:
        await q_edit_safe(update, ui.NOT_CONNECTED); return
    deployed = ctx.user_data.get("deployed_panels") or []
    if not deployed:
        await q_edit_safe(update, ui.header("پنلی توی جلسه نیست 📭")); return

    pid = ctx.user_data.get("_proj_id") or ""
    env_id = ctx.user_data.get("_env_id") or ""
    if not env_id and pid:
        envs = await run_blocking(api.get_environments, pid)
        env_id = envs[0]["id"] if envs else ""
        ctx.user_data["_env_id"] = env_id

    status = await _qmsg(update).reply_text(
        ui.header("مرحله ۳/۴ — ست کردن دامنه‌ها 🌐"), parse_mode="HTML")

    lines, okc = [], 0
    sem = asyncio.Semaphore(4)
    async def make(p):
        nonlocal okc
        async with sem:
            try:
                dom = await run_blocking(api.create_domain, p["service_id"], env_id,
                                          config.DOMAIN_TARGET_PORT)
                if dom:
                    okc += 1; p["url"] = f"https://{dom}"
                    lines.append(f"✅ <b>{p['name']}</b> → <code>{dom}</code>")
                else: lines.append(f"⚠️ <b>{p['name']}</b>")
            except Exception as e:
                lines.append(f"❌ <b>{p['name']}</b> → {str(e)[:50]}")
            await say(status, ui.header(f"دامنه‌ها ({okc}/{len(deployed)}) 🌐")
                      + f"\n{ui.MID}\n" + "\n".join(lines))
    await asyncio.gather(*(make(p) for p in deployed))

    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔗 مرحله ۴ — اتصال نودها",
                                                     callback_data="flow_stage4")],
                              [InlineKeyboardButton("🔙 منوی اصلی", callback_data="refresh_menu")]])
    await say(status, ui.header(f"دامنه‌ها ست شدن ✅ ({okc}/{len(deployed)})")
              + f"\n{ui.MID}\n" + "\n".join(lines)
              + f"\n\n{ui.BOT_}\n👇 مرحله آخر:",
              keyboard=kb)


# ── stage 4: link nodes ──
async def flow_stage4(update, ctx):
    refresh_active(ctx, update.effective_user.id)
    api = get_api(ctx)
    deployed = [p for p in (ctx.user_data.get("deployed_panels") or []) if p.get("url")]
    main = next((p for p in deployed if p["name"] == config.MAIN_PANEL), None)
    others = [p for p in deployed if p["name"] != config.MAIN_PANEL]

    if not main or not others:
        await q_edit_safe(update,
            f"{ui.header('نود برای اتصال نیست 📭')}\n\n"
            f"پنل اصلی <b>{config.MAIN_PANEL}</b> یا بقیه پنل‌ها پیدا نشدن.")
        return

    status = await _qmsg(update).reply_text(
        ui.header(f"مرحله ۴/۴ — اتصال به {config.MAIN_PANEL} 🔗"), parse_mode="HTML")

    lines = []
    async def link(p):
        def _w():
            mp = PanelClient(main["url"], config.XUI_USERNAME, config.XUI_PASSWORD)
            if not mp.login(): raise XUIError("ورود به پنل اصلی ناموفق")
            np = PanelClient(p["url"], config.XUI_USERNAME, config.XUI_PASSWORD)
            if not np.login(): raise XUIError(f"ورود به {p['name']} ناموفق")
            nuuid, ntok = np.get_uuid(), np.create_api_token()
            res = mp.add_node(p["name"], p["url"], nuuid, ntok)
            if not res.get("success"): raise XUIError(res.get("msg","ناموفق"))
        try:
            await run_blocking(_w)
            lines.append(f"✅ <b>{p['name']}</b> → متصل شد")
        except Exception as e:
            lines.append(f"⚠️ <b>{p['name']}</b> → {str(e)[:50]}")
        await say(status, ui.header(f"اتصال نودها ({len(lines)}/{len(others)}) 🔗")
                  + f"\n{ui.MID}\n" + "\n".join(lines))
    for p in others: await link(p)

    await say(status, ui.header("همه نودها متصل شدن 🎉")
              + f"\n{ui.MID}\n" + "\n".join(lines)
              + f"\n\n🏠 نود اصلی: <b>{config.MAIN_PANEL}</b>")


def _qmsg(update):
    return update.message or (update.callback_query.message if update.callback_query else None)

async def q_edit_safe(update, text, keyboard=None):
    q = update.callback_query
    if q and q.message:
        try: await q.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)
        except Exception: pass
    elif update.message:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)


# ════════════════════════════════════════════
#  SECTION: PROTOCOLS
# ════════════════════════════════════════════
def proto_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🌐 WS + TLS", callback_data="proto_wstls_pick")],
        [InlineKeyboardButton("🔙 منوی اصلی", callback_data="refresh_menu")],
    ])

PROTO_WELCOME = (
    f"{ui.header('پروتکل‌ها 🔌')}\n\n"
    "🌐 <b>WS + TLS</b>\n"
    "     └ VLESS + WebSocket + TLS\n"
    "     └ همون مشخصات amir_xu:\n"
    "         • پورت: 8080\n"
    "         • مسیر: /cdn\n"
    "         • TLS روی لبه Railway\n\n"
    f"{ui.MID}\n👇 انتخاب کن:")

async def show_proto(update, ctx, q):
    await q.edit_message_text(PROTO_WELCOME, reply_markup=proto_menu(), parse_mode="HTML")


async def handle_proto(update, ctx, q, data):
    uid = update.effective_user.id
    if data == "proto_wstls_pick":
        deployed = [p for p in (ctx.user_data.get("deployed_panels") or []) if p.get("url")]
        if not deployed:
            await q.edit_message_text(
                f"{ui.header('پنلی نیست 📭')}\n\nاول یه دپلوی انجام بده: 🚀 بخش دپلوی",
                parse_mode="HTML")
            return
        rows = [[InlineKeyboardButton(p["name"],
                 callback_data=f"wstls:{p['service_id']}:{p['name']}:{p['url']}")]
                for p in deployed]
        rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="sec_proto")])
        await q.edit_message_text(
            f"{ui.header('WS + TLS روی کدوم پنل؟ 🌐')}",
            reply_markup=InlineKeyboardMarkup(rows), parse_mode="HTML")
        return

    if data.startswith("wstls:"):
        _, sid, name, url = data.split(":", 3)
        status = await _qmsg(update).reply_text(
            ui.header(f"ساخت ws+tls روی {name}... 🔌"), parse_mode="HTML")

        def _work():
            c = PanelClient(url, config.XUI_USERNAME, config.XUI_PASSWORD)
            if not c.login(): raise XUIError("ورود ناموفق")
            u = str(uuid.uuid4())
            r = c.create_ws_tls_inbound(uuid=u, email=f"{name.lower()}-user",
                                        domain=url.replace("https://",""),
                                        port=config.INBOUND_PORT, path=config.INBOUND_PATH)
            if not r.get("success"): raise XUIError(r.get("msg","unknown"))
            return build_vless_link(url, u, config.INBOUND_PATH, f"Amir-{name}")

        try:
            link = await run_blocking(_work)
            await say(status,
                      ui.header(f"اینباند ws+tls ساخته شد ✅ — {name}")
                      + f"\n\n🔌 {config.INBOUND_PORT} · 🛣 {config.INBOUND_PATH}"
                      + f" · 🔐 TLS\n\n<code>{link}</code>\n\n"
                      "📲 کپی کن → v2rayNG → Import from clipboard")
        except Exception as e:
            await say(status, f"{ui.header('خطا ⛔️')}\n\n❌ {e}")
        return



async def cmd_status(update, ctx):
    refresh_active(ctx, update.effective_user.id)
    api = get_api(ctx)
    if not api:
        t = origin(update) or update.message
        await t.reply_text(ui.NOT_CONNECTED, parse_mode="HTML")
        return
    origin_msg = origin(update)
    status = await origin_msg.reply_text(ui.header("در حال دریافت... 📊"), parse_mode="HTML")
    try:
        projects = await run_blocking(api.list_projects)
        if not projects:
            await say(status, ui.header("پروژه‌ای نیست 📭")); return
        txt = f"{ui.header('پروژه‌های Railway 📦')}\n{ui.MID}\n"
        for p in sorted(projects, key=lambda x: x.get("createdAt",""), reverse=True)[:10]:
            txt += f"\n📦 <b>{p['name']}</b> · <code>{p['id'][:8]}</code>"
        await say(status, txt + f"\n\n{ui.BOT_}\n📊 مجموعه: <b>{len(projects)}</b>")
    except RailwayError as e:
        await say(status, f"{ui.header('خطا ⛔️')}\n\n❌ {e}")


# ════════════════════════════════════════════
#  ROUTER
# ════════════════════════════════════════════
async def on_callback(update, ctx):
    q = update.callback_query
    await q.answer()
    data = q.data
    uid = update.effective_user.id

    if data == "refresh_menu":
        refresh_active(ctx, uid)
        name = update.effective_user.first_name or ""
        await q.edit_message_text(
            ui.welcome(name, ACC.active_label(uid)), reply_markup=ui.MENU, parse_mode="HTML")
        return
    if data == "noop":
        await q.answer("این همون اکانت فعاله ✅", show_alert=True); return

    if data == "sec_account": await show_accounts(q, ctx, uid); return
    if data == "accadd" or data.startswith(("accsw:","accdel:")):
        await handle_accounts(update, ctx, q, data); return

    if data == "sec_deploy":
        await show_deploy(update, ctx, q); return
    if data == "go_deploy":
        refresh_active(ctx, uid)
        if not active_token(ctx):
            await q.edit_message_text(
                ui.NOT_CONNECTED,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("👤 رفتن به اکانت‌ها", callback_data="sec_account")]]),
                parse_mode="HTML")
            return
        await cmd_deploy(update, ctx); return
    if data == "flow_stage3": await flow_stage3(update, ctx); return
    if data == "flow_stage4": await flow_stage4(update, ctx); return

    if data == "sec_proto": await show_proto(update, ctx, q); return
    if data.startswith(("proto_", "wstls:")):
        await handle_proto(update, ctx, q, data); return

    await q.answer()


async def on_error(update, ctx):
    log.exception("Unhandled error", exc_info=ctx.error)
    try:
        q = getattr(update, "callback_query", None)
        msg = getattr(update, "effective_message", None) or (q.message if q else None)
        if msg:
            await msg.reply_text(
                f"{ui.header('خطای غیرمنتظره ⛔️')}\n\n<code>{str(ctx.error)[:200]}</code>",
                parse_mode="HTML")
    except Exception: pass


def main():
    if not config.BOT_TOKEN: raise SystemExit("BOT_TOKEN required!")
    app = ApplicationBuilder().token(config.BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_start))
    app.add_handler(CommandHandler("cancel", cancel_cmd))
    app.add_handler(CommandHandler("deploy", cmd_deploy))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_error_handler(on_error)
    log.info("Amir X-UI V2 started")
    app.run_polling()


if __name__ == "__main__":
    main()
