import json
import os
import tempfile
from collections import deque
from io import BytesIO

# دعم HEIC
from pillow_heif import register_heif_opener
register_heif_opener()

from telegram.ext import MessageHandler, CallbackQueryHandler, filters
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
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

LOGO_SETTINGS_FILE = os.path.join("data", "logo_settings.json")

def load_logo_settings():
    try:
        if os.path.exists(LOGO_SETTINGS_FILE):
            with open(LOGO_SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
    except Exception:
        pass
    return {}

def save_logo_settings():
    try:
        os.makedirs("data", exist_ok=True)
        with open(LOGO_SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(saved_logo_settings, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

saved_logo_settings = load_logo_settings()

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
# 🔥 جديد: تعديل لون الشعار بنسبة
# =========================
def adjust_logo_color(path, percent):
    img = Image.open(path).convert("RGBA")
    factor = 1 + percent / 100
    img = ImageEnhance.Color(img).enhance(factor)
    img = ImageEnhance.Contrast(img).enhance(factor)
    img = ImageEnhance.Sharpness(img).enhance(factor)
    out = tempfile.mktemp(suffix=".png")
    img.save(out, "PNG")
    return out

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
        "step": "ask_use_logo",
        "use_logo": None,
        "logo": None,
        "width": None,
        "opacity": None,
        "logo_color_percent": 0,
        "brightness": False,
        "brightness_value": 0,
        "ai": False,
        "ai_mode": "fast",
        "with_format": False,
        "ad_text": None,
        "inputs": []
    }
    await update.callback_query.answer()
    await update.callback_query.message.reply_text(
        "هل تريد استخدام الشعار؟",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ نعم استخدم الشعار", callback_data="use_logo:yes"),
                InlineKeyboardButton("❌ بدون شعار", callback_data="use_logo:no")
            ]
        ])
    )

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
        s["step"] = "ask_logo_color"
        await update.message.reply_text("🎨 هل تريد تعديل لون الشعار؟", reply_markup=yes_no("logo_color:yes", "logo_color:no"))
        return

    if s["step"] == "logo_color_value":
        s["logo_color_percent"] = int(txt)
        s["step"] = "ask_save_logo"
        await update.message.reply_text("💾 هل تريد حفظ إعدادات الشعار؟", reply_markup=yes_no("logo_save:yes", "logo_save:no"))
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

    if q.data == "use_logo:yes":
        s["use_logo"] = True
        if str(uid) in saved_logo_settings:
            s["step"] = "resume_saved"
            await q.message.reply_text(
                "💾 عندك إعدادات شعار محفوظة.\nهل تريد تكمل بيها؟",
                reply_markup=yes_no("resume_saved:yes", "resume_saved:no")
            )
        else:
            s["step"] = "logo"
            await q.message.reply_text("📎 أرسل شعارك الآن")
        return

    if q.data == "use_logo:no":
        s["use_logo"] = False
        s["step"] = "ask_brightness"
        await q.message.reply_text("💡 هل تريد تعديل الإنارة؟", reply_markup=yes_no("bright:yes", "bright:no"))
        return

    if q.data == "resume_saved:yes":
        saved = saved_logo_settings.get(str(uid))
        if saved:
            s["logo"] = saved.get("logo")
            s["width"] = saved.get("width")
            s["opacity"] = saved.get("opacity")
            s["logo_color_percent"] = saved.get("logo_color_percent", 0)
            s["step"] = "ask_brightness"
            await q.message.reply_text("💡 هل تريد تعديل الإنارة؟", reply_markup=yes_no("bright:yes", "bright:no"))
        else:
            s["step"] = "logo"
            await q.message.reply_text("📎 أرسل شعارك الآن")
        return

    if q.data == "resume_saved:no":
        s["step"] = "logo"
        await q.message.reply_text("📎 أرسل شعارك الآن")
        return

    if q.data == "logo_color:yes":
        s["step"] = "logo_color_value"
        await q.message.reply_text("كم نسبة التعديل؟ (مثال: 20 أو -20)")
        return

    if q.data == "logo_color:no":
        s["step"] = "ask_save_logo"
        await q.message.reply_text("💾 هل تريد حفظ إعدادات الشعار؟", reply_markup=yes_no("logo_save:yes", "logo_save:no"))
        return

    if q.data == "logo_save:yes":
        saved_logo_settings[str(uid)] = {
            "logo": s.get("logo"),
            "width": s.get("width"),
            "opacity": s.get("opacity"),
            "logo_color_percent": s.get("logo_color_percent", 0)
        }
        save_logo_settings()
        s["step"] = "ask_brightness"
        await q.message.reply_text("💡 هل تريد تعديل الإنارة؟", reply_markup=yes_no("bright:yes", "bright:no"))
        return

    if q.data == "logo_save:no":
        s["step"] = "ask_brightness"
        await q.message.reply_text("💡 هل تريد تعديل الإنارة؟", reply_markup=yes_no("bright:yes", "bright:no"))
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
# FINISH (كما هو بدون تغيير)
# =========================

async def finish_custom(update, context):
    q = update.callback_query
    uid = q.from_user.id
    s = sessions.get(uid)
    await q.answer()

    if not s or not s["inputs"]:
        await q.message.reply_text("⚠️ لم يتم إرسال ملفات")
        return

    progress_msg = await q.message.reply_text("⏳ بدء المعالجة...")

    if s["with_format"] and s["ad_text"]:
        await q.message.reply_text(f"{HEADER}
{s['ad_text']}
{CUSTOM_FOOTER}")

    out_photos = []
    out_documents = []
    out_videos = []
    out_video_documents = []

    total_steps = 0
    for kind, _ in s["inputs"]:
        if kind.startswith("photo"):
            total_steps += 5
        else:
            total_steps += 3
    done_steps = 0

    async def tick(label: str):
        nonlocal done_steps
        done_steps += 1
        await set_progress(progress_msg, done_steps, total_steps, label)

    async def process_item(kind, path):
        if kind.startswith("photo"):
            await tick("قراءة الصورة")
            img = await asyncio.to_thread(lambda: Image.open(path).convert("RGB"))

            if s["brightness"]:
                await tick("تعديل الإنارة")
                img = await asyncio.to_thread(
                    lambda: ImageEnhance.Brightness(img).enhance(1 + s["brightness_value"] / 100)
                )
            else:
                await tick("تجاوز الإنارة")

            if s["ai"]:
                await tick("تحسين الصورة")
                if s["ai_mode"] == "strong":
                    img = await asyncio.to_thread(enhance_strong, img)
                elif s["ai_mode"] == "fast":
                    img = await asyncio.to_thread(enhance_fast, img)
                elif s["ai_mode"] == "pro":
                    def _do_openai():
                        tmp_for_ai = tempfile.mktemp(suffix=".jpg")
                        img.save(tmp_for_ai, "JPEG", quality=95)
                        enhanced_path = ai_enhance_openai(tmp_for_ai)
                        try:
                            return Image.open(enhanced_path).convert("RGB")
                        except Exception:
                            return enhance_fast(img)
                    img = await asyncio.to_thread(_do_openai)
            else:
                await tick("بدون تحسين AI")

            await tick("تجهيز الحفظ")
            def _save_and_logo():
                buf = BytesIO()
                img.save(buf, format="JPEG", quality=92)
                buf.seek(0)

                tmp = tempfile.mktemp(suffix=".jpg")
                with open(tmp, "wb") as f:
                    f.write(buf.read())

                logo_path = s["logo"]
                if s["logo_color_percent"] != 0:
                    logo_path = adjust_logo_color(s["logo"], s["logo_color_percent"])

                out = apply_custom_logo(tmp, logo_path, s["width"], s["opacity"])
                return out
            out = await asyncio.to_thread(_save_and_logo)

            await tick("إنهاء الصورة")
            if kind == "photo_doc":
                out_documents.append(out)
            else:
                out_photos.append(out)

        else:
            await tick("معالجة الفيديو")
            def _process_video():
                logo_path = s["logo"]
                if s["logo_color_percent"] != 0:
                    logo_path = adjust_logo_color(s["logo"], s["logo_color_percent"])
                return apply_custom_logo_video(path, logo_path, s["width"], s["opacity"])
            outv = await asyncio.to_thread(_process_video)

            await tick("تجهيز الإرسال")
            if kind == "video_doc":
                out_video_documents.append(outv)
            else:
                out_videos.append(outv)

            await tick("إنهاء الفيديو")

    for kind, path in s["inputs"]:
        await process_item(kind, path)

    try:
        await progress_msg.edit_text(
            "✅ تمت المعالجة بنجاح

"
            f"{progress_bar(100)} 100%
"
            f"{total_steps}/{total_steps}"
        )
    except Exception:
        pass

    # صور عادية -> حزمة صور
    if out_photos:
        batch = []
        open_files = []
        for i, path in enumerate(out_photos, start=1):
            try:
                f = open(path, "rb")
                open_files.append(f)
                batch.append(InputMediaPhoto(media=f))
                if len(batch) == 10 or i == len(out_photos):
                    try:
                        await q.message.reply_media_group(media=batch)
                    except RetryAfter as e:
                        await asyncio.sleep(int(getattr(e, "retry_after", 2)) + 1)
                        await q.message.reply_media_group(media=batch)
                    for ff in open_files:
                        try:
                            ff.close()
                        except:
                            pass
                    batch, open_files = [], []
                    await asyncio.sleep(0.25)
            except Exception:
                continue

    # صور كملفات -> حزمة ملفات
    if out_documents:
        batch = []
        open_files = []
        for i, path in enumerate(out_documents, start=1):
            try:
                f = open(path, "rb")
                open_files.append(f)
                batch.append(InputMediaDocument(media=f))
                if len(batch) == 10 or i == len(out_documents):
                    try:
                        await q.message.reply_media_group(media=batch)
                    except RetryAfter as e:
                        await asyncio.sleep(int(getattr(e, "retry_after", 2)) + 1)
                        await q.message.reply_media_group(media=batch)
                    for ff in open_files:
                        try:
                            ff.close()
                        except:
                            pass
                    batch, open_files = [], []
                    await asyncio.sleep(0.25)
            except Exception:
                continue

    # فيديو عادي -> فيديو
    for outv in out_videos:
        try:
            with open(outv, "rb") as f:
                await q.message.reply_video(video=f)
            await asyncio.sleep(0.2)
        except RetryAfter as e:
            await asyncio.sleep(int(getattr(e, "retry_after", 2)) + 1)
        except Exception:
            continue

    # فيديو كملف -> ملف
    for outv in out_video_documents:
        try:
            with open(outv, "rb") as f:
                await q.message.reply_document(document=f, filename=os.path.basename(outv))
            await asyncio.sleep(0.2)
        except RetryAfter as e:
            await asyncio.sleep(int(getattr(e, "retry_after", 2)) + 1)
        except Exception:
            continue

    await q.message.reply_text("✅ تمت المعالجة بنجاح", reply_markup=after_done())

# =========================
# REGISTER
# =========================
def register(app):
    app.add_handler(CallbackQueryHandler(start_custom, pattern="^custom:start$"))
    app.add_handler(CallbackQueryHandler(finish_custom, pattern="^custom:finish$"))
    app.add_handler(CallbackQueryHandler(handle_callbacks))
    app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO | filters.Document.ALL, handle_media))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
