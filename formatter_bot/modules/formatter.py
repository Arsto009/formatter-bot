import os
import tempfile
import shutil
import requests
import base64
import time
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
from core.storage import load_data, save_data

# =========================
# إعدادات الذكاء الاصطناعي - Replicate (أفضل تحسين واقعي)
# =========================
REPLICATE_API_TOKEN = "r8_4YFcKZpfUQl7Y6Hj3Xw2BnT9mL5sRqV"  # توكنك
REPLICATE_API_URL = "https://api.replicate.com/v1/predictions"

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
# حفظ واسترجاع إعدادات الشعار
# =========================
def save_logo_settings(user_id, logo_path, width, opacity, logo_color_percent):
    data = load_data()
    
    if "logo_settings" not in data:
        data["logo_settings"] = {}
    
    # نسخ الشعار إلى مجلد البيانات
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
        # حذف ملف الشعار المحفوظ
        saved_path = data["logo_settings"][str(user_id)].get("logo_path")
        if saved_path and os.path.exists(saved_path):
            os.remove(saved_path)
        del data["logo_settings"][str(user_id)]
        save_data(data)

# =========================
# تعديل لون الشعار بنسبة
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
# رفع الصورة لموقع مؤقت
# =========================
def upload_to_tmp(image_path):
    """يرفع الصورة لموقع مؤقت ويعيد الرابط"""
    try:
        with open(image_path, 'rb') as f:
            files = {'file': f}
            response = requests.post(
                "https://tmpfiles.org/api/v1/upload",
                files=files
            )
        
        if response.status_code == 200:
            # تحويل الرابط لرابط مباشر
            url = response.json()['data']['url']
            # tmpfiles.org يعطي رابط مثل https://tmpfiles.org/123/abc.jpg
            # نحتاج نحوله لرابط مباشر https://tmpfiles.org/dl/123/abc.jpg
            if 'tmpfiles.org/' in url:
                file_id = url.split('/')[-2] + '/' + url.split('/')[-1]
                direct_url = f"https://tmpfiles.org/dl/{file_id}"
                return direct_url
            return url
        return None
    except Exception as e:
        print(f"خطأ في رفع الصورة: {e}")
        return None

# =========================
# تحسين الصور - احترافي 4K (ذكاء اصطناعي واقعي)
# =========================
def enhance_image_professional(image_path):
    """
    يحسن الصورة باحترافية عالية جداً:
    - دقة 4K
    - واقعية كأنها من كاميرا نيكون
    - ناعمة وسلسة بدون غواش
    - إزالة كل التشويش
    """
    try:
        print("🎨 جاري تحسين الصورة بجودة 4K احترافية...")
        
        # 1. رفع الصورة
        image_url = upload_to_tmp(image_path)
        if not image_url:
            print("⚠️ فشل رفع الصورة")
            return enhance_4k_local(image_path)
        
        # 2. استخدام أفضل نموذج للتحسين الواقعي
        headers = {
            "Authorization": f"Token {REPLICATE_API_TOKEN}",
            "Content-Type": "application/json"
        }
        
        # نموذج Real-ESRGAN (أفضل نموذج للصور الواقعية)
        data = {
            "version": "42fed1c4974146e4a3f3d1c2d7d1c2d7",  # Real-ESRGAN
            "input": {
                "image": image_url,
                "scale": 4,  # تكبير 4 مرات (4K)
                "face_enhance": True,  # تحسين الوجوه
                "background_enhance": True,  # تحسين الخلفية
                "suffix": "_enhanced",
                "model": "RealESRGAN_x4plus",  # نموذج 4x
                "tile_size": 400,  # حجم المعالجة
                "preprocess": True
            }
        }
        
        # بدء التحسين
        response = requests.post(REPLICATE_API_URL, headers=headers, json=data)
        
        if response.status_code == 201:
            prediction_id = response.json()['id']
            
            # انتظار النتيجة
            max_attempts = 60  # انتظار أطول للجودة العالية
            for attempt in range(max_attempts):
                status_response = requests.get(
                    f"{REPLICATE_API_URL}/{prediction_id}",
                    headers=headers
                )
                status = status_response.json()
                
                if status['status'] == 'succeeded':
                    # تم التحسين بنجاح
                    if 'output' in status:
                        enhanced_url = status['output']
                        if isinstance(enhanced_url, list):
                            enhanced_url = enhanced_url[0]
                        
                        # تحميل الصورة المحسنة
                        img_response = requests.get(enhanced_url)
                        
                        output_path = tempfile.mktemp(suffix="_4k.jpg")
                        with open(output_path, 'wb') as f:
                            f.write(img_response.content)
                        
                        # تطبيق تحسين إضافي للنعومة والواقعية
                        output_path = final_touch(output_path)
                        
                        print("✅ تم تحسين الصورة بجودة 4K احترافية!")
                        return output_path
                
                elif status['status'] == 'failed':
                    print("⚠️ فشل التحسين، نستخدم الطريقة المحلية")
                    break
                
                time.sleep(3)  # انتظار 3 ثواني بين كل محاولة
        
        # إذا فشل كل شيء، نستخدم التحسين المحلي
        return enhance_4k_local(image_path)
        
    except Exception as e:
        print(f"❌ خطأ في التحسين: {e}")
        return enhance_4k_local(image_path)

# =========================
# تحسين 4K محلي (احتياطي)
# =========================
def enhance_4k_local(image_path):
    """تحسين محلي بجودة عالية إذا فشل API"""
    try:
        img = Image.open(image_path).convert("RGB")
        
        # حساب أبعاد 4K (3840x2160)
        target_width = 3840
        target_height = 2160
        
        # تكبير الصورة مع الحفاظ على النسبة
        ratio = min(target_width / img.width, target_height / img.height)
        new_size = (int(img.width * ratio), int(img.height * ratio))
        img = img.resize(new_size, Image.LANCZOS)
        
        # قص الصورة لتناسب 4K إذا لزم الأمر
        if new_size[0] > target_width or new_size[1] > target_height:
            left = (new_size[0] - target_width) // 2
            top = (new_size[1] - target_height) // 2
            right = left + target_width
            bottom = top + target_height
            img = img.crop((left, top, right, bottom))
        elif new_size[0] < target_width or new_size[1] < target_height:
            # إنشاء خلفية سوداء وتوسيط الصورة
            new_img = Image.new('RGB', (target_width, target_height), (0, 0, 0))
            paste_x = (target_width - new_size[0]) // 2
            paste_y = (target_height - new_size[1]) // 2
            new_img.paste(img, (paste_x, paste_y))
            img = new_img
        
        # تطبيق تحسينات احترافية
        # 1. تقليل التشويش (ناعم)
        img = img.filter(ImageFilter.MedianFilter(size=3))
        
        # 2. تحسين الحدة (بدون غواش)
        img = img.filter(ImageFilter.UnsharpMask(radius=1.5, percent=80, threshold=2))
        
        # 3. تحسين التباين (واقعي)
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.15)
        
        # 4. تحسين الألوان (طبيعي)
        enhancer = ImageEnhance.Color(img)
        img = enhancer.enhance(1.1)
        
        # 5. تحسين الوضوح (سلس)
        enhancer = ImageEnhance.Sharpness(img)
        img = enhancer.enhance(1.2)
        
        output_path = tempfile.mktemp(suffix="_4k_local.jpg")
        img.save(output_path, "JPEG", quality=100, subsampling=0)
        
        return output_path
        
    except Exception as e:
        print(f"خطأ في التحسين المحلي: {e}")
        return image_path

# =========================
# اللمسة النهائية (ناعمة كالماء)
# =========================
def final_touch(image_path):
    """يجعل الصورة ناعمة وسلسة كالماء"""
    try:
        img = Image.open(image_path).convert("RGB")
        
        # تقليل خفيف جداً للتشويش (نعومة)
        img = img.filter(ImageFilter.SMOOTH_MORE)
        
        # تحسين الحدة بشكل طبيعي
        img = img.filter(ImageFilter.UnsharpMask(radius=1, percent=50, threshold=0))
        
        # تحسين الألوان لتكون واقعية
        enhancer = ImageEnhance.Color(img)
        img = enhancer.enhance(1.05)
        
        output_path = tempfile.mktemp(suffix="_final.jpg")
        img.save(output_path, "JPEG", quality=100, subsampling=0)
        
        return output_path
        
    except:
        return image_path

# =========================
# تحسين الصور - سريع (عادي)
# =========================
def enhance_fast(img):
    img = img.filter(ImageFilter.SHARPEN)
    img = ImageEnhance.Contrast(img).enhance(1.1)
    img = ImageEnhance.Color(img).enhance(1.1)
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
        [InlineKeyboardButton("📷 4K احترافي (واقعي)", callback_data="ai:strong")]
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
            "✅ تم تحميل إعدادات الشعار المحفوظة\n"
            "💡 هل تريد تعديل الإنارة؟",
            reply_markup=yes_no("bright:yes", "bright:no")
        )
    else:
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
        s["step"] = "ask_logo_color"
        await update.message.reply_text("🎨 هل تريد تعديل لون الشعار؟", reply_markup=yes_no("logo_color:yes", "logo_color:no"))
        return

    if s["step"] == "logo_color_value":
        s["logo_color_percent"] = int(txt)
        s["step"] = "ask_save_settings"
        await update.message.reply_text(
            "💾 هل تريد حفظ إعدادات الشعار الحالية؟\n"
            "(الشعار، العرض، الشفافية، نسبة اللون)",
            reply_markup=yes_no("save:yes", "save:no")
        )
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

    if q.data == "logo_color:yes":
        s["step"] = "logo_color_value"
        await q.message.reply_text("كم نسبة التعديل؟ (مثال: 20 أو -20)")
        return

    if q.data == "logo_color:no":
        s["logo_color_percent"] = 0
        s["step"] = "ask_save_settings"
        await q.message.reply_text(
            "💾 هل تريد حفظ إعدادات الشعار الحالية؟\n"
            "(الشعار، العرض، الشفافية، نسبة اللون)",
            reply_markup=yes_no("save:yes", "save:no")
        )
        return

    if q.data == "save:yes":
        uid = q.from_user.id
        save_logo_settings(
            uid,
            s["logo"],
            s["width"],
            s["opacity"],
            s.get("logo_color_percent", 0)
        )
        s["step"] = "ask_brightness"
        await q.message.reply_text(
            "✅ تم حفظ الإعدادات بنجاح\n"
            "💡 هل تريد تعديل الإنارة؟",
            reply_markup=yes_no("bright:yes", "bright:no")
        )
        return

    if q.data == "save:no":
        s["step"] = "ask_brightness"
        await q.message.reply_text(
            "💡 هل تريد تعديل الإنارة؟",
            reply_markup=yes_no("bright:yes", "bright:no")
        )
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
        await q.message.reply_text(
            "🔄 لنبدأ مرة أخرى\n"
            "💡 هل تريد تعديل الإنارة؟",
            reply_markup=yes_no("bright:yes", "bright:no")
        )
        return

    if q.data == "custom:end":
        sessions.pop(uid, None)
        await q.message.reply_text("⬅️ تم الإنهاء", reply_markup=main_keyboard(uid))
        return

    if q.data == "custom:clear_settings":
        clear_logo_settings(uid)
        sessions.pop(uid, None)
        await q.message.reply_text(
            "🗑 تم مسح الإعدادات المحفوظة",
            reply_markup=main_keyboard(uid)
        )
        return

# =========================
# FINISH - المعالجة النهائية
# =========================
async def finish_custom(update, context):
    q = update.callback_query
    uid = q.from_user.id
    s = sessions.get(uid)
    await q.answer()

    if not s or not s["inputs"]:
        await q.message.reply_text("⚠️ لم يتم إرسال ملفات")
        return

    await q.message.reply_text("⏳ انتظر، جاري المعالجة...")

    if s["with_format"] and s["ad_text"]:
        await q.message.reply_text(
            f"{HEADER}\n{s['ad_text']}\n{CUSTOM_FOOTER}"
        )

    media_group = []
    video_files = []

    async def process_item(kind, path):
        if kind.startswith("photo"):
            # إذا كان التحسين احترافي 4K
            if s["ai"] and s["ai_mode"] == "strong":
                # 🔥 تحسين احترافي 4K
                enhanced_path = enhance_image_professional(path)
                img = Image.open(enhanced_path).convert("RGB")
            else:
                img = Image.open(path).convert("RGB")
                
                if s["brightness"]:
                    img = ImageEnhance.Brightness(img).enhance(1 + s["brightness_value"] / 100)

                if s["ai"] and s["ai_mode"] == "fast":
                    img = enhance_fast(img)

            buf = BytesIO()
            img.save(buf, format="JPEG", quality=100, subsampling=0)
            buf.seek(0)

            tmp = tempfile.mktemp(suffix=".jpg")
            with open(tmp, "wb") as f:
                f.write(buf.read())

            # تطبيق تعديل لون الشعار
            logo_path = s["logo"]
            if s["logo_color_percent"] != 0:
                logo_path = adjust_logo_color(s["logo"], s["logo_color_percent"])

            out = apply_custom_logo(tmp, logo_path, s["width"], s["opacity"])
            media_group.append(InputMediaPhoto(open(out, "rb")))
        else:
            # معالجة الفيديو
            logo_path = s["logo"]
            if s["logo_color_percent"] != 0:
                logo_path = adjust_logo_color(s["logo"], s["logo_color_percent"])

            outv = apply_custom_logo_video(path, logo_path, s["width"], s["opacity"])
            video_files.append(open(outv, "rb"))

    for kind, path in s["inputs"]:
        await process_item(kind, path)

    if media_group:
        await q.message.reply_media_group(media_group)

    for vf in video_files:
        await q.message.reply_video(vf)

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
    app.add_handler(CallbackQueryHandler(clear_settings_handler, pattern="^custom:clear_settings$"))
    app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO | filters.Document.ALL, handle_media))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

async def clear_settings_handler(update, context):
    q = update.callback_query
    uid = q.from_user.id
    await q.answer()
    
    clear_logo_settings(uid)
    sessions.pop(uid, None)
    
    await q.message.reply_text(
        "🗑 تم مسح الإعدادات المحفوظة",
        reply_markup=main_keyboard(uid)
    )
