import os
import tempfile
from collections import deque
from io import BytesIO

# دعم HEIC
from pillow_heif import register_heif_opener
register_heif_opener()

from telegram.ext import MessageHandler, CallbackQueryHandler, filters
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from PIL import Image, ImageEnhance, ImageFilter

from settings import HEADER
from core.keyboard import main_keyboard
from modules.designer import apply_custom_logo, apply_custom_logo_video

# =========================
# Queue إعدادات
# =========================
MAX_FAST_SIZE = 2.3 * 1024 * 1024
heavy_queue = deque()
processing_queue = False

sessions = {}

# =========================
# فوتر الإعلان
# =========================
CUSTOM_FOOTER = """
---------------------------
بالامكان الاستفسار عن تفاصيل أكثر
من خلال الارقام الاتية :-
07754404477
07735544404
07764404477
"""

# =========================
# تحسين الشعار
# =========================
def enhance_logo_colors(path):
    img = Image.open(path).convert("RGBA")
    img = ImageEnhance.Color(img).enhance(1.6)
    img = ImageEnhance.Contrast(img).enhance(1.15)
    out = tempfile.mktemp(suffix=".png")
    img.save(out, "PNG")
    return out

# =========================
# تحسين الصور
# =========================
def enhance_fast(img):
    img = img.filter(ImageFilter.SHARPEN)
    img = ImageEnhance.Contrast(img).enhance(1.1)
    return img

def enhance_strong(img):
    img = img.filter(ImageFilter.MedianFilter(size=3))
    img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=140))
    img = ImageEnhance.Contrast(img).enhance(1.18)
    return img

# =========================
# Queue Worker
# =========================
async def process_queue():
    global processing_queue
    if processing_queue:
        return
    processing_queue = True
    while heavy_queue:
        job = heavy_queue.popleft()
        await job()
    processing_queue = False

# =========================
# Keyboards
# =========================
def yes_no(y, n):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ نعم", callback_data=y),
        InlineKeyboardButton("❌ لا", callback_data=n)
    ]])

def speed_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⚡ سريع", callback_data="ai:fast")],
        [InlineKeyboardButton("💎 قوي", callback_data="ai:strong")]
    ])

def send_done():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 تم إرسال الصور / الفيديو", callback_data="custom:finish")]
    ])

def after_done():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔁 المزيد", callback_data="custom:more")],
        [InlineKeyboardButton("⛔ إنهاء العملية", callback_data="custom:end")]
    ])

# =========================
# Start
# =========================
async def start_custom(update, context):
    uid = update.effective_user.id
    sessions[uid] = {
        "step": "logo",
        "logo": None,
        "width": None,
        "opacity": None,
        "brightness": False,
        "brightness_value": 0,
        "ai": False,
        "ai_mode": "fast",
        "with_format": False,
        "ad_text": None,
        "inputs": []
    }
    await update.callback_query.answer()
    await update.callback_query.message.reply_text("📎 أرسل شعارك الآن")

# =========================
# TEXT
# =========================
async def handle_text(update, context):
    uid = update.effective_user.id
    txt = update.message.text.strip()
    s = sessions.get(uid)

    if txt == "🔄 Start":
        sessions.pop(uid, None)
        await update.message.reply_text("⬅️ القائمة الرئيسية", reply_markup=main_keyboard(uid))
        return

    if not s:
        return

    if s["step"] == "width":
        s["width"] = float(txt)
        s["step"] = "opacity"
        await update.message.reply_text("🌫 أرسل نسبة الشفافية (0–100)")
        return

    if s["step"] == "opacity":
        s["opacity"] = int(txt)
        s["step"] = "ask_brightness"
        await update.message.reply_text("💡 هل تريد تعديل الإنارة؟", reply_markup=yes_no("bright:yes", "bright:no"))
        return

    if s["step"] == "brightness_value":
        s["brightness_value"] = int(txt)
        s["step"] = "ask_ai"
        await update.message.reply_text("🤖 هل تريد تحسين الصور؟", reply_markup=yes_no("ai:yes", "ai:no"))
        return

    if s["step"] == "ad_text":
        s["ad_text"] = txt
        s["step"] = "media"
        await update.message.reply_text("🖼 أرسل الصور أو الفيديو", reply_markup=send_done())

# =========================
# MEDIA
# =========================
async def handle_media(update, context):
    uid = update.effective_user.id
    s = sessions.get(uid)
    if not s:
        return

    msg = update.message

    if s["step"] == "logo":
        f = await (msg.photo[-1].get_file() if msg.photo else msg.document.get_file())
        p = tempfile.mktemp()
        await f.download_to_drive(p)
        s["logo"] = enhance_logo_colors(p)
        s["step"] = "width"
        await msg.reply_text("📏 أرسل عرض الشعار (0.10 – 1.00)")
        return

    if s["step"] != "media":
        return

    if msg.photo:
        f = await msg.photo[-1].get_file()
        p = tempfile.mktemp(suffix=".jpg")
        await f.download_to_drive(p)
        s["inputs"].append(("photo", p))

    elif msg.document:
        f = await msg.document.get_file()
        ext = os.path.splitext(msg.document.file_name or "")[-1].lower()
        p = tempfile.mktemp(suffix=ext)
        await f.download_to_drive(p)
        kind = "video_doc" if (msg.document.mime_type or "").startswith("video") else "photo_doc"
        s["inputs"].append((kind, p))

    elif msg.video:
        f = await msg.video.get_file()
        p = tempfile.mktemp(suffix=".mp4")
        await f.download_to_drive(p)
        s["inputs"].append(("video", p))

# =========================
# CALLBACKS
# =========================
async def handle_callbacks(update, context):
    q = update.callback_query
    uid = q.from_user.id
    s = sessions.get(uid)
    await q.answer()
    if not s:
        return

    if q.data == "bright:yes":
        s["brightness"] = True
        s["step"] = "brightness_value"
        await q.message.reply_text("💡 كم نسبة الإنارة؟")
        return

    if q.data == "bright:no":
        s["brightness"] = False
        s["step"] = "ask_ai"
        await q.message.reply_text("🤖 هل تريد تحسين الصور؟", reply_markup=yes_no("ai:yes", "ai:no"))
        return

    if q.data == "ai:yes":
        s["ai"] = True
        s["step"] = "ask_ai_mode"
        await q.message.reply_text("⚙️ اختر نوع التحسين", reply_markup=speed_kb())
        return

    if q.data == "ai:no":
        s["ai"] = False
        s["step"] = "ask_format"
        await q.message.reply_text("🧾 هل تريد تنسيق إعلان؟", reply_markup=yes_no("fmt:yes", "fmt:no"))
        return

    if q.data == "ai:fast":
        s["ai_mode"] = "fast"
        s["step"] = "ask_format"
        await q.message.reply_text("🧾 هل تريد تنسيق إعلان؟", reply_markup=yes_no("fmt:yes", "fmt:no"))
        return

    if q.data == "ai:strong":
        s["ai_mode"] = "strong"
        s["step"] = "ask_format"
        await q.message.reply_text("🧾 هل تريد تنسيق إعلان؟", reply_markup=yes_no("fmt:yes", "fmt:no"))
        return

    if q.data == "fmt:yes":
        s["with_format"] = True
        s["step"] = "ad_text"
        await q.message.reply_text("✏️ أرسل نص الإعلان")
        return

    if q.data == "fmt:no":
        s["with_format"] = False
        s["step"] = "media"
        await q.message.reply_text("🖼 أرسل الصور أو الفيديو", reply_markup=send_done())
        return

    if q.data == "custom:more":
        s["inputs"] = []
        s["ad_text"] = None
        s["step"] = "ask_brightness"
        await q.message.reply_text("💡 هل تريد تعديل الإنارة؟", reply_markup=yes_no("bright:yes", "bright:no"))
        return

    if q.data == "custom:end":
        sessions.pop(uid, None)
        await q.message.reply_text("⬅️ تم الإنهاء", reply_markup=main_keyboard(uid))

# =========================
# FINISH (الترتيب النهائي)
# =========================
async def finish_custom(update, context):
    q = update.callback_query
    uid = q.from_user.id
    s = sessions.get(uid)
    await q.answer()

    if not s or not s["inputs"]:
        await q.message.reply_text("⚠️ لم يتم إرسال ملفات")
        return

    # 1️⃣ رسالة الانتظار
    await q.message.reply_text("⏳ انتظر، جاري المعالجة...")

    # 2️⃣ الإعلان (إن وجد)
    if s["with_format"] and s["ad_text"]:
        await q.message.reply_text(
            f"{HEADER}\n{s['ad_text']}\n{CUSTOM_FOOTER}"
        )

    async def process_item(kind, path):
        if kind.startswith("photo"):
            img = Image.open(path).convert("RGB")
            if s["brightness"]:
                img = ImageEnhance.Brightness(img).enhance(1 + s["brightness_value"] / 100)
            if s["ai"]:
                img = enhance_strong(img) if s["ai_mode"] == "strong" else enhance_fast(img)

            buf = BytesIO()
            img.save(buf, format="JPEG", quality=92)
            buf.seek(0)

            tmp = tempfile.mktemp(suffix=".jpg")
            with open(tmp, "wb") as f:
                f.write(buf.read())

            out = apply_custom_logo(tmp, s["logo"], s["width"], s["opacity"])

            if kind == "photo":
                await q.message.reply_photo(open(out, "rb"))
            else:
                await q.message.reply_document(open(out, "rb"))
        else:
            outv = apply_custom_logo_video(path, s["logo"], s["width"], s["opacity"])
            await q.message.reply_video(open(outv, "rb"))

    for kind, path in s["inputs"]:
        if os.path.getsize(path) > MAX_FAST_SIZE:
            heavy_queue.append(lambda k=kind, p=path: process_item(k, p))
            await process_queue()
        else:
            await process_item(kind, path)

    # 3️⃣ آخر رسالة دائمًا
    await q.message.reply_text(
        "✅ تمت المعالجة بنجاح",
        reply_markup=after_done()
    )

# =========================
# REGISTER
# =========================
def register(app):
    app.add_handler(CallbackQueryHandler(start_custom, pattern="^custom:start$"))
    app.add_handler(CallbackQueryHandler(finish_custom, pattern="^custom:finish$"))
    app.add_handler(CallbackQueryHandler(handle_callbacks))
    app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO | filters.Document.ALL, handle_media))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
