import os
import tempfile
import shutil
import requests
import time
from collections import deque
from io import BytesIO

from pillow_heif import register_heif_opener
register_heif_opener()

from telegram.ext import MessageHandler, CallbackQueryHandler, filters
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from PIL import Image, ImageEnhance, ImageFilter, ImageResampling

from settings import HEADER
from core.keyboard import main_keyboard, yes_no, speed_kb, after_done, send_done
from modules.designer import apply_custom_logo, apply_custom_logo_video
from core.storage import load_data, save_data

# =========================
# إعدادات Replicate
# =========================
REPLICATE_API_TOKEN = "r8_4YFcKZpfUQl7Y6Hj3Xw2BnT9mL5sRqV"
REPLICATE_API_URL = "https://api.replicate.com/v1/predictions"

# =========================
# المتغيرات العامة
# =========================
sessions = {}
CUSTOM_FOOTER = """
---------------------------
بالامكان الاستفسار عن تفاصيل أكثر
07754404477 - 07735544404
"""

# =========================
# دوال حفظ الإعدادات
# =========================
def save_logo_settings(user_id, logo_path, width, opacity, logo_color_percent):
    data = load_data()
    if "logo_settings" not in data:
        data["logo_settings"] = {}
    
    saved_logo_dir = os.path.join("data", "saved_logos")
    os.makedirs(saved_logo_dir, exist_ok=True)
    saved_logo_path = os.path.join(saved_logo_dir, f"user_{user_id}.png")
    shutil.copy2(logo_path, saved_logo_path)
    
    data["logo_settings"][str(user_id)] = {
        "logo_path": saved_logo_path,
        "width": width,
        "opacity": opacity,
        "logo_color_percent": logo_color_percent
    }
    save_data(data)

def load_logo_settings(user_id):
    data = load_data()
    return data.get("logo_settings", {}).get(str(user_id))

def clear_logo_settings(user_id):
    data = load_data()
    if "logo_settings" in data and str(user_id) in data["logo_settings"]:
        saved_path = data["logo_settings"][str(user_id)].get("logo_path")
        if saved_path and os.path.exists(saved_path):
            os.remove(saved_path)
        del data["logo_settings"][str(user_id)]
        save_data(data)

# =========================
# دوال تحسين الصور
# =========================
def upload_to_tmp(image_path):
    try:
        with open(image_path, 'rb') as f:
            response = requests.post("https://tmpfiles.org/api/v1/upload", files={'file': f})
        if response.status_code == 200:
            url = response.json()['data']['url']
            if 'tmpfiles.org/' in url:
                file_id = url.split('/')[-2] + '/' + url.split('/')[-1]
                return f"https://tmpfiles.org/dl/{file_id}"
            return url
    except:
        return None

def enhance_4k_professional(image_path):
    """تحسين احترافي 4K"""
    try:
        # محاولة Replicate
        image_url = upload_to_tmp(image_path)
        if image_url:
            headers = {"Authorization": f"Token {REPLICATE_API_TOKEN}", "Content-Type": "application/json"}
            data = {
                "version": "42fed1c4974146e4a3f3d1c2d7d1c2d7",
                "input": {"image": image_url, "scale": 4, "face_enhance": True}
            }
            response = requests.post(REPLICATE_API_URL, headers=headers, json=data, timeout=30)
            
            if response.status_code == 201:
                prediction_id = response.json()['id']
                for _ in range(30):
                    status = requests.get(f"{REPLICATE_API_URL}/{prediction_id}", headers=headers).json()
                    if status['status'] == 'succeeded':
                        enhanced_url = status['output'][0] if isinstance(status['output'], list) else status['output']
                        img_response = requests.get(enhanced_url, timeout=60)
                        output_path = tempfile.mktemp(suffix="_4k.jpg")
                        with open(output_path, 'wb') as f:
                            f.write(img_response.content)
                        return output_path
                    elif status['status'] == 'failed':
                        break
                    time.sleep(2)
        
        # تحسين محلي احتياطي
        img = Image.open(image_path).convert("RGB")
        img = img.resize((3840, 2160), ImageResampling.LANCZOS)
        img = img.filter(ImageFilter.MedianFilter(size=3))
        img = img.filter(ImageFilter.UnsharpMask(radius=1.2, percent=60))
        
        output_path = tempfile.mktemp(suffix="_4k_local.jpg")
        img.save(output_path, "JPEG", quality=100)
        return output_path
    except:
        return image_path

def enhance_fast(img):
    img = img.filter(ImageFilter.SHARPEN)
    img = ImageEnhance.Contrast(img).enhance(1.1)
    img = ImageEnhance.Color(img).enhance(1.1)
    return img

def adjust_logo_color(path, percent):
    img = Image.open(path).convert("RGBA")
    factor = 1 + percent / 100
    img = ImageEnhance.Color(img).enhance(factor)
    out = tempfile.mktemp(suffix=".png")
    img.save(out, "PNG")
    return out

def enhance_logo_colors(path):
    img = Image.open(path).convert("RGBA")
    img = ImageEnhance.Color(img).enhance(1.6)
    out = tempfile.mktemp(suffix=".png")
    img.save(out, "PNG")
    return out

# =========================
# Start Custom
# =========================
async def start_custom(update, context):
    uid = update.effective_user.id
    saved = load_logo_settings(uid)
    
    sessions[uid] = {
        "step": "ask_brightness" if saved else "logo",
        "logo": saved.get("logo_path") if saved else None,
        "width": saved.get("width") if saved else None,
        "opacity": saved.get("opacity") if saved else None,
        "logo_color_percent": saved.get("logo_color_percent", 0) if saved else 0,
        "brightness": False,
        "brightness_value": 0,
        "ai": False,
        "ai_mode": "fast",
        "with_format": False,
        "ad_text": None,
        "inputs": []
    }
    
    await update.callback_query.answer()
    
    if saved:
        await update.callback_query.message.reply_text(
            "✅ تم تحميل الإعدادات\n💡 تعديل الإنارة؟",
            reply_markup=yes_no("bright:yes", "bright:no")
        )
    else:
        await update.callback_query.message.reply_text("📎 أرسل شعارك")

# =========================
# Handle Text
# =========================
async def handle_text(update, context):
    uid = update.effective_user.id
    txt = update.message.text.strip()
    s = sessions.get(uid)

    if txt == "🔄 Start":
        sessions.pop(uid, None)
        await update.message.reply_text("⬅️ القائمة", reply_markup=main_keyboard(uid))
        return

    if not s:
        return

    if s["step"] == "width":
        try:
            s["width"] = float(txt)
            s["step"] = "opacity"
            await update.message.reply_text("🌫 نسبة الشفافية (0–100)")
        except ValueError:
            await update.message.reply_text("❌ رقم غير صحيح")
        return

    if s["step"] == "opacity":
        try:
            s["opacity"] = int(txt)
            s["step"] = "ask_logo_color"
            await update.message.reply_text("🎨 تعديل لون الشعار؟", reply_markup=yes_no("logo_color:yes", "logo_color:no"))
        except ValueError:
            await update.message.reply_text("❌ رقم غير صحيح")
        return

    if s["step"] == "logo_color_value":
        try:
            s["logo_color_percent"] = int(txt)
            s["step"] = "ask_save_settings"
            await update.message.reply_text("💾 حفظ الإعدادات؟", reply_markup=yes_no("save:yes", "save:no"))
        except ValueError:
            await update.message.reply_text("❌ رقم غير صحيح")
        return

    if s["step"] == "brightness_value":
        try:
            s["brightness_value"] = int(txt)
            s["step"] = "ask_ai"
            await update.message.reply_text("🤖 تحسين الصور؟", reply_markup=yes_no("ai:yes", "ai:no"))
        except ValueError:
            await update.message.reply_text("❌ رقم غير صحيح")
        return

    if s["step"] == "ad_text":
        s["ad_text"] = txt
        s["step"] = "media"
        await update.message.reply_text("🖼 أرسل الصور")

# =========================
# Handle Media
# =========================
async def handle_media(update, context):
    uid = update.effective_user.id
    s = sessions.get(uid)
    if not s:
        return

    msg = update.message

    if s["step"] == "logo":
        if msg.photo:
            f = await msg.photo[-1].get_file()
        elif msg.document:
            f = await msg.document.get_file()
        else:
            await msg.reply_text("❌ الرجاء إرسال صورة")
            return
        
        p = tempfile.mktemp()
        await f.download_to_drive(p)
        s["logo"] = enhance_logo_colors(p)
        s["step"] = "width"
        await msg.reply_text("📏 عرض الشعار (0.10–1.00)")
        return

    if s["step"] != "media":
        return

    if msg.photo:
        f = await msg.photo[-1].get_file()
        p = tempfile.mktemp(suffix=".jpg")
        await f.download_to_drive(p)
        s["inputs"].append(("photo", p))
        await msg.reply_text(f"✅ تم استلام {len(s['inputs'])}", reply_markup=send_done())

# =========================
# Handle Callbacks
# =========================
async def handle_callbacks(update, context):
    q = update.callback_query
    uid = q.from_user.id
    s = sessions.get(uid)
    await q.answer()
    if not s:
        return

    if q.data == "logo_color:yes":
        s["step"] = "logo_color_value"
        await q.message.reply_text("كم نسبة التعديل؟")

    elif q.data == "logo_color:no":
        s["logo_color_percent"] = 0
        s["step"] = "ask_save_settings"
        await q.message.reply_text("💾 حفظ الإعدادات؟", reply_markup=yes_no("save:yes", "save:no"))

    elif q.data == "save:yes":
        save_logo_settings(uid, s["logo"], s["width"], s["opacity"], s.get("logo_color_percent", 0))
        s["step"] = "ask_brightness"
        await q.message.reply_text("✅ تم الحفظ\n💡 تعديل الإنارة؟", reply_markup=yes_no("bright:yes", "bright:no"))

    elif q.data == "save:no":
        s["step"] = "ask_brightness"
        await q.message.reply_text("💡 تعديل الإنارة؟", reply_markup=yes_no("bright:yes", "bright:no"))

    elif q.data == "bright:yes":
        s["brightness"] = True
        s["step"] = "brightness_value"
        await q.message.reply_text("💡 نسبة الإنارة؟")

    elif q.data == "bright:no":
        s["brightness"] = False
        s["step"] = "ask_ai"
        await q.message.reply_text("🤖 تحسين الصور؟", reply_markup=yes_no("ai:yes", "ai:no"))

    elif q.data == "ai:yes":
        s["ai"] = True
        s["step"] = "ask_ai_mode"
        await q.message.reply_text("⚙️ نوع التحسين", reply_markup=speed_kb())

    elif q.data == "ai:no":
        s["ai"] = False
        s["step"] = "ask_format"
        await q.message.reply_text("🧾 تنسيق إعلان؟", reply_markup=yes_no("fmt:yes", "fmt:no"))

    elif q.data == "ai:fast":
        s["ai_mode"] = "fast"
        s["step"] = "ask_format"
        await q.message.reply_text("🧾 تنسيق إعلان؟", reply_markup=yes_no("fmt:yes", "fmt:no"))

    elif q.data == "ai:strong":
        s["ai_mode"] = "strong"
        s["step"] = "ask_format"
        await q.message.reply_text("🧾 تنسيق إعلان؟", reply_markup=yes_no("fmt:yes", "fmt:no"))

    elif q.data == "fmt:yes":
        s["with_format"] = True
        s["step"] = "ad_text"
        await q.message.reply_text("✏️ نص الإعلان")

    elif q.data == "fmt:no":
        s["with_format"] = False
        s["step"] = "media"
        await q.message.reply_text("🖼 أرسل الصور")

    elif q.data == "custom:more":
        s["inputs"] = []
        s["ad_text"] = None
        s["step"] = "ask_brightness"
        await q.message.reply_text("🔄 مرة أخرى\n💡 تعديل الإنارة؟", reply_markup=yes_no("bright:yes", "bright:no"))

    elif q.data == "custom:end":
        sessions.pop(uid, None)
        await q.message.reply_text("⬅️ تم الإنهاء", reply_markup=main_keyboard(uid))

    elif q.data == "custom:clear_settings":
        clear_logo_settings(uid)
        sessions.pop(uid, None)
        await q.message.reply_text("🗑 تم المسح", reply_markup=main_keyboard(uid))

# =========================
# Finish Custom
# =========================
async def finish_custom(update, context):
    q = update.callback_query
    uid = q.from_user.id
    s = sessions.get(uid)
    await q.answer()

    if not s or not s["inputs"]:
        await q.message.reply_text("⚠️ لا توجد صور")
        return

    await q.message.reply_text("⏳ جاري المعالجة...")

    if s["with_format"] and s["ad_text"]:
        await q.message.reply_text(f"{HEADER}\n{s['ad_text']}\n{CUSTOM_FOOTER}")

    media_group = []
    video_files = []

    for kind, path in s["inputs"]:
        if kind == "photo":
            if s["ai"] and s["ai_mode"] == "strong":
                enhanced = enhance_4k_professional(path)
                img = Image.open(enhanced)
            else:
                img = Image.open(path)
                if s["brightness"]:
                    img = ImageEnhance.Brightness(img).enhance(1 + s["brightness_value"] / 100)
                if s["ai"] and s["ai_mode"] == "fast":
                    img = enhance_fast(img)

            buf = BytesIO()
            img.save(buf, format="JPEG", quality=100)
            buf.seek(0)

            tmp = tempfile.mktemp(suffix=".jpg")
            with open(tmp, "wb") as f:
                f.write(buf.read())

            logo_path = s["logo"]
            if s["logo_color_percent"] != 0:
                logo_path = adjust_logo_color(s["logo"], s["logo_color_percent"])

            out = apply_custom_logo(tmp, logo_path, s["width"], s["opacity"])
            media_group.append(InputMediaPhoto(open(out, "rb")))
        else:
            logo_path = s["logo"]
            if s["logo_color_percent"] != 0:
                logo_path = adjust_logo_color(s["logo"], s["logo_color_percent"])
            outv = apply_custom_logo_video(path, logo_path, s["width"], s["opacity"])
            video_files.append(open(outv, "rb"))

    if media_group:
        await q.message.reply_media_group(media_group)
    for vf in video_files:
        await q.message.reply_video(vf)
    
    await q.message.reply_text("✅ تمت المعالجة", reply_markup=after_done())

# =========================
# Register
# =========================
def register(app):
    app.add_handler(CallbackQueryHandler(start_custom, pattern="^custom:start$"))
    app.add_handler(CallbackQueryHandler(finish_custom, pattern="^custom:finish$"))
    app.add_handler(CallbackQueryHandler(handle_callbacks))
    app.add_handler(MessageHandler(filters.PHOTO, handle_media))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
