"""
Amir X-UI V2 — entry point. Thin handlers; logic in wizard.py.
"""
import asyncio
import logging
import os
import uuid

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (ApplicationBuilder, CommandHandler, CallbackQueryHandler,
                          ContextTypes, MessageHandler, filters)

import config, ui
from accounts import Accounts
from errors import AppError, PanelError
from railway import Railway
from wizard import Wizard

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("amir-v2")

ACC = Accounts(os.path.join(config.DATA_DIR, "accounts.json"))


# ── helpers ──
def token_of(ctx):
    return ctx.user_data.get("_tok") or ""


def refresh(ctx):
    acc, lbl = ACC.get(ctx.user_data_key())
    ctx.user_data["_tok"] = acc["token"] if acc else ""
    ctx.user_data["_lbl"] = lbl


def origin(update: Update):
    if update.message:
        return update.message
    if update.callback_query:
        return update.callback_query.message
    return None


async def safe_edit(qmsg, text, keyboard=None):
    try:
        await qmsg.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    except Exception:
        pass



# ── commands ──
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    acc, lbl = ACC.get(uid)
    ctx.user_data["_tok"] = acc["token"] if acc else ""
    await update.message.reply_text(
        ui.welcome(update.effective_user.first_name or "", lbl),
        reply_markup=ui.MENU, parse_mode="HTML")


async def cmd_cancel(update, ctx):
    uid = update.effective_user.id
    st = ctx.user_data.setdefault(uid, {})
    cleared = st.pop("await_acc_label", False)
    wiz = ctx.bot_data.pop(f"wiz_{uid}", None)
    if wiz and wiz.state != "idle":
        wiz.state = "idle"
        await update.message.reply_text("🛑 عملیات لغو شد.", parse_mode="HTML")
    elif cleared:
        await update.message.reply_text(ui.header("لغو شد ❌"), parse_mode="HTML")
    else:
        await update.message.reply_text("چیزی برای لغو نبود.")


async def on_text(update, ctx):
    uid = update.effective_user.id
    st = ctx.user_data.setdefault(uid, {})

    if st.pop("await_acc_label", False):
        st["pending_label"] = update.message.text.strip()[:32]
        await update.message.reply_text(
            ui.ADD_ACCOUNT.replace(
                "{h}", ui.hdr(f"اکانت «{st['pending_label']}» ➕"))
            + "\n\n🔑 حالا <b>توکن</b> رو بفرست:", parse_mode="HTML")
        return

    if "pending_label" in st:
        label = st.pop("pending_label")
        token = update.message.text.strip()
        msg = await update.message.reply_text(
            ui.hdr("در حال بررسی... 🔍"), parse_mode="HTML")
        try:
            api = Railway(token)
            ws, email = await asyncio.to_thread(api.whoami)
            if not ACC.add(uid, label, token, email):
                await safe_edit(msg, ui.hdr("تکراری ⚠️") + f"\n\nاسم {label} هست.")
                return
            ctx.user_data["_tok"] = token
            accs = ACC.list(uid)
            await safe_edit(msg,
                            f"{ui.hdr('اکانت اضافه شد ✅')}\n\n"
                            f"👤 {label} · <code>{email}</code>",
                            keyboard=ui.accounts_kb(accs))
        except AppError as e:
            await safe_edit(msg, f"{ui.hdr('⛔️')}\n\n{e.user_msg}")


# ════════════════════════ ACCOUNTS ════════════════════════
async def show_accounts(update, ctx, q):
    uid = update.effective_user.id
    await q.edit_message_text(ui.accounts_text(ACC.list(uid), ACC.active_label(uid)),
                              reply_markup=ui.accounts_kb(ACC.list(uid)),
                              parse_mode="HTML")


async def do_accounts(update, ctx, q, data):
    uid = update.effective_user.id
    if data == "accadd":
        ctx.user_data.setdefault(uid, {})["await_acc_label"] = True
        await q.edit_message_text(
            ui.ADD_ACCOUNT.replace("{h}", ui.hdr("افزودن اکانت ➕")),
            parse_mode="HTML")
    elif data.startswith("accsw:"):
        lbl = data.split(":", 1)[1]
        ACC.switch(uid, lbl)
        # refresh token in user_data
        acc, _ = ACC.get(uid)
        ctx.user_data["_tok"] = acc["token"] if acc else ""
        await show_accounts(update, ctx, q)
    elif data.startswith("accdel:"):
        lbl = data.split(":", 1)[1]
        ACC.remove(uid, lbl)
        acc, _ = ACC.get(uid)
        ctx.user_data["_tok"] = acc["token"] if acc else ""
        await show_accounts(update, ctx, q)


# ════════════════════════ DEPLOY WIZARD ════════════════════════
def get_wiz(ctx, uid) -> Wizard:
    return ctx.bot_data.setdefault(f"wiz_{uid}", None)


async def start_deploy(update, ctx, q):
    uid = update.effective_user.id
    acc, _ = ACC.get(uid)
    if not acc:
        await q.edit_message_text(ui.NOT_CONNECTED, parse_mode="HTML")
        return
    ctx.user_data["_tok"] = acc["token"]
    api = Railway(acc["token"])

    async def status_cb(text):
        try:
            await q.edit_message_text(text, parse_mode="HTML")
        except Exception:
            pass

    wiz = Wizard(api)
    ctx.bot_data[f"wiz_{uid}"] = wiz

    ok = await wiz.deploy(status_cb)
    if not ok:
        await safe_edit(q.message, f"{ui.hdr('دپلوی ناموفق ⛔️')}\n\n{wiz.error}")
        return

    panel_list = "\n".join(
        f"  🌐 <code>{p['url'].replace('https://', '')}/managepanel/</code>"
        for p in wiz.panels if p.get("url"))
    await q.edit_message_text(
        f"{ui.hdr('مرحله ۲/۴ — تنظیم ریجن‌ها ⏸')}\n{ui.MID}\n"
        + ui.STAGE2_PROMPT + panel_list
        + f"\n\n{ui.BOT}\n👇 بعد از تموم شدن بزن:",
        reply_markup=ui.stage2_kb(), parse_mode="HTML")


async def stage_domains(update, ctx, q):
    uid = update.effective_user.id
    wiz = ctx.bot_data.get(f"wiz_{uid}")
    if not wiz or wiz.state == "idle":
        await q.edit_message_text(ui.hdr("فلو فعالی نیست 📭"), parse_mode="HTML")
        return

    async def status_cb(text):
        try:
            await q.edit_message_text(text, parse_mode="HTML")
        except Exception:
            pass

    ok = await wiz.set_domains(status_cb)
    await q.edit_message_text(
        f"{ui.hdr(f'دامنه‌ها ست شدن ✅ ({ok}/{len(wiz.panels)})')}\n{ui.MID}\n"
        + "\n".join(f"{'✅' if p['status']=='SUCCESS' else '⚠️'} <b>{p['name']}</b>"
                    for p in wiz.panels)
        + f"\n\n{ui.BOT}\n👇 مرحله آخر:",
        reply_markup=ui.stage4_kb(), parse_mode="HTML")


async def stage_nodes(update, ctx, q):
    uid = update.effective_user.id
    wiz = ctx.bot_data.get(f"wiz_{uid}")
    if not wiz:
        await q.edit_message_text(ui.hdr("فلو فعالی نیست 📭"), parse_mode="HTML")
        return

    async def status_cb(text):
        try:
            await q.edit_message_text(text, parse_mode="HTML")
        except Exception:
            pass

    lines = await wiz.link_nodes(status_cb)
    await q.edit_message_text(
        f"{ui.hdr('همه نودها متصل شدن 🎉')}\n{ui.MID}\n" + "\n".join(lines),
        parse_mode="HTML")


# ════════════════════════ PROTOCOLS ════════════════════════
async def show_proto(update, ctx, q):
    await q.edit_message_text(ui.PROTO_WELCOME, reply_markup=ui.proto_menu(),
                              parse_mode="HTML")


async def do_proto(update, ctx, q, data):
    uid = update.effective_user.id
    deployed = [p for p in (ctx.bot_data.get(f"wiz_{uid}").panels
                            if ctx.bot_data.get(f"wiz_{uid}") else [])
                if p.get("url")]
    if data == "proto_pick":
        if not deployed:
            await q.edit_message_text(
                f"{ui.hdr('پنلی نیست 📭')}\n\nاول دپلوی کن: 🚀 بخش دپلوی",
                parse_mode="HTML")
            return
        rows = [[InlineKeyboardButton(p["name"],
                 callback_data=f"wstls:{p['name']}:{p['url']}")] for p in deployed]
        rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="sec_proto")])
        await q.edit_message_text(ui.hdr("WS+TLS روی کدوم پنل؟ 🌐"),
                                  reply_markup=InlineKeyboardMarkup(rows),
                                  parse_mode="HTML")
        return

    if data.startswith("wstls:"):
        _, name, url = data.split(":", 2)
        msg = await _qmsg(update).reply_text(
            ui.hdr(f"ساخت ws+tls روی {name}... 🔌"), parse_mode="HTML")

        def work():
            from xui import Panel, vless_link
            c = Panel(url)
            if not c.login():
                raise PanelError("ورود به پنل ناموفق")
            u = str(uuid.uuid4())
            r = c.create_ws_tls_inbound(uuid=u, email=f"{name.lower()}-user",
                                        domain=url.replace("https://", ""),
                                        port=config.IN_PORT, path=config.IN_PATH)
            if not r.get("success"):
                raise PanelError(r.get("msg", "خطا"))
            return vless_link(url, u, config.IN_PATH, f"Amir-{name}")

        try:
            link = await asyncio.to_thread(work)
            await safe_edit(msg,
                            f"{ui.hdr(f'sاخته شد ✅ — {name}')}\n\n"
                            f"🔌 {config.IN_PORT} · 🛣 {config.IN_PATH} · 🔐 TLS"
                            f"\n\n<code>{link}</code>\n\n"
                            "📲 کپی → v2rayNG → Import")
        except PanelError as e:
            await safe_edit(msg, f"{ui.hdr('خطا ⛔️')}\n\n{e.user_msg}")


def _qmsg(update):
    return update.callback_query.message if update.callback_query else update.message


# ════════════════════════ ROUTER ════════════════════════
async def on_callback(update, ctx):
    q = update.callback_query
    await q.answer()
    data = q.data
    uid = update.effective_user.id

    if data == "refresh_menu":
        acc, lbl = ACC.get(uid)
        await q.edit_message_text(
            ui.welcome(update.effective_user.first_name or "", lbl),
            reply_markup=ui.MENU, parse_mode="HTML")
        return
    if data == "noop":
        await q.answer("این اکانت فعال ✅", show_alert=True)
        return
    if data == "sec_account":
        await show_accounts(update, ctx, q)
        return
    if data == "accadd" or data.startswith(("accsw:", "accdel:")):
        await do_accounts(update, ctx, q, data)
        return
    if data == "sec_deploy":
        await q.edit_message_text(ui.DEPLOY_WELCOME, reply_markup=ui.deploy_menu(),
                                  parse_mode="HTML")
        return
    if data == "go_deploy":
        await start_deploy(update, ctx, q)
        return
    if data == "flow_domains":
        await stage_domains(update, ctx, q)
        return
    if data == "flow_nodes":
        await stage_nodes(update, ctx, q)
        return
    if data == "sec_proto":
        await show_proto(update, ctx, q)
        return
    if data.startswith(("proto_", "wstls:")):
        await do_proto(update, ctx, q, data)
        return


async def on_error(update, ctx):
    log.exception("Unhandled error", exc_info=ctx.error)
    e = ctx.error
    user_msg = getattr(e, "user_msg", None) or str(e)[:200]
    try:
        q = getattr(update, "callback_query", None)
        msg = getattr(update, "effective_message", None) or (q.message if q else None)
        if msg:
            await msg.reply_text(f"{ui.hdr('خطا ⛔️')}\n\n{user_msg}",
                                 parse_mode="HTML")
    except Exception:
        pass


def main():
    if not config.BOT_TOKEN:
        raise SystemExit("BOT_TOKEN required!")
    app = ApplicationBuilder().token(config.BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_start))
    app.add_handler(CommandHandler("cancel", cmd_cancel))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_error_handler(on_error)
    log.info("Amir X-UI V2 (rebuilt) started")
    app.run_polling()


if __name__ == "__main__":
    main()
