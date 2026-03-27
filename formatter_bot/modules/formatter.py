import json
import logging
import os
import tempfile
from collections import deque
from io import BytesIO

# دعم HEIC
from pillow_heif import register_heif_opener
register_heif_opener()

from telegram.ext import MessageHandler, CallbackQueryHandler, filters
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, InputMediaDocument
from PIL import Image, ImageEnhance, ImageFilter

from settings import HEADER
from core.keyboard import main_keyboard
from modules.designer import apply_custom_logo, apply_custom_logo_video, apply_brightness_video

# =========================
# Queue إعدادات
# =========================
MAX_FAST_SIZE = 2.3 * 1024 * 1024
heavy_queue = deque()
processing_queue = False

sessions = {}

LOGO_SETTINGS_FILE = os.path.join("data", "logo_settings.json")
SAVED_LOGOS_DIR = os.path.join("data", "saved_logos")

def save_logo_file_for_user(uid, logo_path):
    try:
        os.makedirs(SAVED_LOGOS_DIR, exist_ok=True)
        dst = os.path.join(SAVED_LOGOS_DIR, f"{uid}.png")
        Image.open(logo_path).convert("RGBA").save(dst, "PNG")
        return dst
    except Exception:
        return logo_path


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
logger = logging.getLogger(__name__)

async def _download_media_to_temp(file_obj, suffix=""):
    p = tempfile.mktemp(suffix=suffix)
    await file_obj.download_to_drive(p)
    return p

async def _update_receive_counter(msg, s, text):
    if s.get("counter_msg_id"):
        try:
            await msg.get_bot().edit_message_text(
                chat_id=msg.chat_id,
                message_id=s["counter_msg_id"],
                text=text
            )
            return
        except Exception:
            pass
    m = await msg.reply_text(text)
    s["counter_msg_id"] = m.message_id


def _safe_input_name(kind, original_name, fallback_ext):
    name = (original_name or "").strip()
    if name:
        return os.path.basename(name)

    ext = fallback_ext or ".bin"
    if not ext.startswith('.'):
        ext = f'.{ext}'

    if kind == "photo_doc":
        return f"image{ext}"
    if kind == "video_doc":
        return f"video{ext}"
    if kind.startswith("photo"):
        return f"photo{ext}"
    return f"media{ext}"


async def _set_progress_text(message, current_step, total_steps, label):
    total_steps = max(1, total_steps)
    current_step = max(0, min(current_step, total_steps))
    percent = int((current_step * 100) / total_steps)
    await message.edit_text(
        f"⏳ {label}\n{progress_bar(current_step, total_steps)} {percent}%"
    )


def _chunked(seq, size):
    for i in range(0, len(seq), size):
        yield seq[i:i + size]

# =========================
# فوتر الإعلان
# =========================
CUSTOM_FOOTER = """
---------------------------
بالامكان الاستفسار عن التفاصيل اكثر
من خلال الارقام الاتية :-
07754404477
07764404477
07735544404
او زيارة مقر العمل الكائن في 
البصرة - الجزائر - خلف مرطبات سنبلة
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

def progress_bar(current, total, width=10):
    total = max(total, 1)
    filled = int(width * current / total)
    return "█" * filled + "░" * (width - filled)

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
        "inputs": [],
        "counter_msg_id": None
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

    try:
        if s["step"] == "logo":
            f = await (msg.photo[-1].get_file() if msg.photo else msg.document.get_file())
            p = await _download_media_to_temp(f)
            s["logo"] = enhance_logo_colors(p)
            s["step"] = "width"
            await msg.reply_text("📏 أرسل عرض الشعار (0.10 – 1.00)")
            return

        if s["step"] != "media":
            await msg.reply_text("⚠️ البوت ليس في مرحلة استقبال الصور/الفيديو الآن")
            return

        if msg.photo:
            f = await msg.photo[-1].get_file()
            p = await _download_media_to_temp(f, suffix=".jpg")
            s["inputs"].append(("photo", p, "photo.jpg"))
            await _update_receive_counter(
                msg,
                s,
                f"✅ تم استلام صورة\n"
                f"📦 العدد الحالي: {len(s['inputs'])}"
            )

        elif msg.document:
            f = await msg.document.get_file()
            ext = os.path.splitext(msg.document.file_name or "")[-1].lower()
            p = await _download_media_to_temp(f, suffix=ext)

            video_exts = {
                ".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v",
                ".wmv", ".flv", ".mpeg", ".mpg", ".3gp", ".ts",
                ".ogv", ".mts", ".m2ts", ".vob"
            }

            image_exts = {
                ".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff",
                ".heic", ".heif", ".gif"
            }

            mime = (msg.document.mime_type or "").lower()
            if mime.startswith("video") or ext in video_exts:
                kind = "video_doc"
            elif mime.startswith("image") or ext in image_exts:
                kind = "photo_doc"
            else:
                os.remove(p)
                await msg.reply_text(
                    "⚠️ هذا الملف ليس صورة أو فيديو مدعوم.\n"
                    "أرسل صورة أو فيديو بصيغة معروفة مثل mp4 / mov / jpg / png"
                )
                return

            s["inputs"].append((kind, p, _safe_input_name(kind, msg.document.file_name, ext or ".bin")))
            if kind == "video_doc":
                await _update_receive_counter(
                    msg,
                    s,
                    f"✅ تم استلام فيديو كملف\n"
                    f"📦 العدد الحالي: {len(s['inputs'])}"
                )
            else:
                await _update_receive_counter(
                    msg,
                    s,
                    f"✅ تم استلام صورة كملف\n"
                    f"📦 العدد الحالي: {len(s['inputs'])}"
                )

        elif msg.video_note:
            f = await msg.video_note.get_file()
            p = await _download_media_to_temp(f, suffix=".mp4")
            s["inputs"].append(("video", p, "video.mp4"))
            await _update_receive_counter(
                msg,
                s,
                f"✅ تم استلام فيديو\n"
                f"📦 العدد الحالي: {len(s['inputs'])}"
            )

        elif msg.video:
            f = await msg.video.get_file()
            p = await _download_media_to_temp(f, suffix=".mp4")
            s["inputs"].append(("video", p, "video.mp4"))
            await _update_receive_counter(
                msg,
                s,
                f"✅ تم استلام فيديو\n"
                f"📦 العدد الحالي: {len(s['inputs'])}"
            )

    except Exception as e:
        logger.exception("Media receive failed for user %s: %s", uid, e)
        await msg.reply_text(
            "⚠️ تعذر استلام الملف أو تنزيله.\n"
            "جرّب إرسال الفيديو كملف أو تأكد من تفعيل Local Bot API بشكل صحيح."
        )

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
        if saved and saved.get("logo") and os.path.exists(saved.get("logo")):
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
        persistent_logo = save_logo_file_for_user(uid, s.get("logo")) if s.get("logo") else s.get("logo")
        saved_logo_settings[str(uid)] = {
            "logo": persistent_logo,
            "width": s.get("width"),
            "opacity": s.get("opacity"),
            "logo_color_percent": s.get("logo_color_percent", 0)
        }
        s["logo"] = persistent_logo
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
        s["counter_msg_id"] = None
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

    progress_msg = await q.message.reply_text("⏳ جاري تجهيز المعالجة...")

    if s["with_format"] and s["ad_text"]:
        await q.message.reply_text(
            f"{HEADER}\n{s['ad_text']}\n{CUSTOM_FOOTER}"
        )

    normalized_inputs = []
    for item in s["inputs"]:
        if len(item) >= 3:
            normalized_inputs.append(item)
        else:
            kind, path = item
            fallback_ext = os.path.splitext(path)[1].lower() or ".bin"
            normalized_inputs.append((kind, path, _safe_input_name(kind, None, fallback_ext)))

    total_items = len(normalized_inputs)
    total_steps = max(1, total_items * 2)
    step = 0

    outputs = []
    temp_files_to_delete = []
    logo_temp_files = []
    errors = []

    async def process_item(kind, path, original_name):
        if kind.startswith("photo"):
            img = Image.open(path).convert("RGB")

            if s["brightness"]:
                img = ImageEnhance.Brightness(img).enhance(1 + s["brightness_value"] / 100)

            if s["ai"]:
                img = enhance_strong(img) if s["ai_mode"] == "strong" else enhance_fast(img)

            tmp = tempfile.mktemp(suffix=".jpg")
            img.save(tmp, format="JPEG", quality=92)
            temp_files_to_delete.append(tmp)

            if s.get("use_logo", True):
                logo_path = s["logo"]
                if s["logo_color_percent"] != 0:
                    logo_path = adjust_logo_color(s["logo"], s["logo_color_percent"])
                    logo_temp_files.append(logo_path)
                out = apply_custom_logo(tmp, logo_path, s["width"], s["opacity"])
                temp_files_to_delete.append(out)
            else:
                out = tmp

            if kind == "photo_doc" or os.path.getsize(out) > 9_500_000:
                return {
                    "send_type": "document",
                    "path": out,
                    "file_name": _safe_input_name("photo_doc", original_name, ".jpg")
                }

            return {
                "send_type": "photo",
                "path": out,
                "file_name": _safe_input_name("photo", original_name, ".jpg")
            }

        if s.get("use_logo", True):
            logo_path = s["logo"]
            if s["logo_color_percent"] != 0:
                logo_path = adjust_logo_color(s["logo"], s["logo_color_percent"])
                logo_temp_files.append(logo_path)
            outv = apply_custom_logo_video(
                path,
                logo_path,
                s["width"],
                s["opacity"],
                s["brightness_value"] if s["brightness"] else 0
            )
        else:
            if s["brightness"]:
                outv = apply_brightness_video(path, s["brightness_value"])
            else:
                outv = path

        if outv != path:
            temp_files_to_delete.append(outv)

        if kind == "video_doc":
            return {
                "send_type": "document",
                "path": outv,
                "file_name": _safe_input_name("video_doc", original_name, os.path.splitext(original_name)[1].lower() or os.path.splitext(outv)[1].lower() or ".mp4")
            }

        return {
            "send_type": "video",
            "path": outv,
            "file_name": _safe_input_name("video", original_name, os.path.splitext(outv)[1].lower() or ".mp4")
        }

    async def send_output(item):
        send_type = item["send_type"]
        path = item["path"]
        file_name = item["file_name"]

        if send_type == "photo":
            with open(path, "rb") as f:
                await q.message.reply_photo(f, filename=file_name)
            return

        if send_type == "video":
            with open(path, "rb") as f:
                size = os.path.getsize(path) if os.path.exists(path) else 0
                if size > 45_000_000:
                    await q.message.reply_document(f, filename=file_name)
                else:
                    try:
                        await q.message.reply_video(f, supports_streaming=True, filename=file_name)
                    except Exception:
                        f.seek(0)
                        await q.message.reply_document(f, filename=file_name)
            return

        with open(path, "rb") as f:
            await q.message.reply_document(f, filename=file_name)

    try:
        for index, (kind, path, original_name) in enumerate(normalized_inputs, start=1):
            label = "جاري معالجة الفيديو..." if kind.startswith("video") else "جاري معالجة الصور..."
            await _set_progress_text(progress_msg, step, total_steps, label)

            try:
                outputs.append(await process_item(kind, path, original_name))
            except Exception as e:
                logger.exception("Processing failed for user %s: %s", uid, e)
                errors.append(f"فشل في معالجة: {original_name or os.path.basename(path)}")

            step += 1
            await _set_progress_text(progress_msg, step, total_steps, label)

        photo_batch = []

        async def flush_photo_batch():
            nonlocal step, photo_batch
            if not photo_batch:
                return
            for chunk in _chunked(photo_batch, 10):
                media = []
                handles = []
                try:
                    for photo_item in chunk:
                        fh = open(photo_item["path"], "rb")
                        handles.append(fh)
                        media.append(InputMediaPhoto(fh))
                    await q.message.reply_media_group(media)
                finally:
                    for fh in handles:
                        try:
                            fh.close()
                        except Exception:
                            pass
                step += len(chunk)
                await _set_progress_text(progress_msg, step, total_steps, "جاري الإرسال...")
            photo_batch = []

        for item in outputs:
            if item["send_type"] == "photo":
                photo_batch.append(item)
                continue

            await flush_photo_batch()
            try:
                await send_output(item)
            except Exception as e:
                logger.exception("Send failed for user %s: %s", uid, e)
                errors.append(f"فشل في الإرسال: {item.get('file_name')}")
            step += 1
            await _set_progress_text(progress_msg, step, total_steps, "جاري الإرسال...")

        await flush_photo_batch()

        if errors:
            await progress_msg.edit_text("⚠️ اكتملت العملية مع بعض الملاحظات")
            await q.message.reply_text(
                "⚠️ تمت المعالجة، لكن حدثت بعض المشاكل:\n" + "\n".join(errors[:10]),
                reply_markup=after_done()
            )
            return

        await progress_msg.edit_text("✅ تمت المعالجة بنجاح")
        await q.message.reply_text(
            "✅ تمت المعالجة بنجاح",
            reply_markup=after_done()
        )
    finally:
        for tmp_path in logo_temp_files + temp_files_to_delete:
            try:
                if tmp_path and os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
# =========================
# REGISTER
# =========================
def register(app):
    app.add_handler(CallbackQueryHandler(start_custom, pattern="^custom:start$"))
    app.add_handler(CallbackQueryHandler(finish_custom, pattern="^custom:finish$"))
    app.add_handler(CallbackQueryHandler(handle_callbacks))
    app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO | filters.VIDEO_NOTE | filters.Document.ALL, handle_media))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
