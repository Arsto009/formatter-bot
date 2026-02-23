import requests
import time
from urllib.parse import urlparse

from telegram.ext import CallbackQueryHandler, MessageHandler, filters
from telegram import Update
from telegram.ext import ContextTypes

from settings import META_ACCESS_TOKEN, PROJECT_TAG, ADMINS

GRAPH = "https://graph.facebook.com/v18.0"

sessions = {}


def is_admin(user_id: int) -> bool:
    return user_id in ADMINS


def safe_json(resp):
    try:
        return resp.json()
    except Exception:
        return {}


def get_groups():
    try:
        r = requests.get(
            f"{GRAPH}/me/groups",
            params={"access_token": META_ACCESS_TOKEN, "limit": 500},
            timeout=30
        )

        data = safe_json(r)
        if data.get("error"):
            return None, data["error"]

        return data.get("data", []), None

    except Exception as e:
        return None, {"message": str(e)}


def post_to_group(group_id, link):
    try:
        r = requests.post(
            f"{GRAPH}/{group_id}/feed",
            data={"link": link, "access_token": META_ACCESS_TOKEN},
            timeout=20
        )
        return safe_json(r)
    except Exception as e:
        return {"error": {"message": str(e)}}


async def start_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    user_id = q.from_user.id

    if not is_admin(user_id):
        await q.answer("❌ هذا الخيار للأدمن فقط", show_alert=True)
        return

    sessions[user_id] = {"mode": "post"}
    await q.answer()
    await q.message.reply_text(
        f"{PROJECT_TAG} 🔗 أرسل رابط منشور فيسبوك الآن\n\n"
        "للإلغاء اكتب: إلغاء"
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    session = sessions.get(user_id)
    if not session or session.get("mode") != "post":
        return

    link = update.message.text.strip()

    if link.lower() in ["إلغاء", "الغاء", "cancel", "stop"]:
        sessions.pop(user_id, None)
        await update.message.reply_text(f"{PROJECT_TAG} ❌ تم إلغاء العملية")
        return

    parsed = urlparse(link)
    if "facebook.com" not in (parsed.netloc or ""):
        await update.message.reply_text("❌ هذا ليس رابط فيسبوك صحيح")
        return

    groups, error = get_groups()
    if error:
        await update.message.reply_text("❌ فشل الاتصال مع Meta API")
        sessions.pop(user_id, None)
        return

    ok = 0
    fail = 0

    for g in groups:
        gid = g.get("id")
        if not gid:
            fail += 1
            continue

        res = post_to_group(gid, link)
        if res.get("id"):
            ok += 1
        else:
            fail += 1

        time.sleep(4)

    await update.message.reply_text(
        f"{PROJECT_TAG} ✅ انتهى النشر\n\nنجاح: {ok}\nفشل: {fail}"
    )
    sessions.pop(user_id, None)


def register(app):
    app.add_handler(CallbackQueryHandler(start_post, pattern="^post:menu$"))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text),
        group=-1
    )
