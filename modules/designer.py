import os
import tempfile
import subprocess
from PIL import Image

from telegram.ext import CallbackQueryHandler
from telegram import InlineKeyboardMarkup, InlineKeyboardButton

from core.keyboard import design_menu, main_keyboard

# =========================
# إعدادات أساسية
# =========================
LOGO_PATH = "logo.PNG"

INPUT_DIR = "مابي حقوق"
OUTPUT_DIR = "بي حقوق"

os.makedirs(INPUT_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# =========================
# إيجاد مجلد رقم جديد
# =========================
def get_next_folder():
    nums = []
    for name in os.listdir(OUTPUT_DIR):
        if name.isdigit():
            nums.append(int(name))
    return str(max(nums) + 1) if nums else "1"

# =========================
# إزالة الخلفية السوداء
# =========================
def remove_black_background(img, threshold=30):
    img = img.convert("RGBA")
    pixels = img.load()

    for y in range(img.height):
        for x in range(img.width):
            r, g, b, a = pixels[x, y]
            if r < threshold and g < threshold and b < threshold:
                pixels[x, y] = (r, g, b, 0)

    return img

# =========================
# تطبيق الشعار (تصميم الصور – الأدمن)
# =========================
def apply_logo(image_path, target_folder):
    base = Image.open(image_path).convert("RGBA")
    logo = Image.open(LOGO_PATH).convert("RGBA")

    logo = remove_black_background(logo)

    bw, bh = base.size
    new_width = int(bw * 0.70)
    ratio = new_width / logo.width
    new_height = int(logo.height * ratio)

    logo = logo.resize((new_width, new_height), Image.LANCZOS)

    alpha = logo.split()[3]
    alpha = alpha.point(lambda p: int(p * 0.5))
    logo.putalpha(alpha)

    x = (bw - logo.width) // 2
    y = (bh - logo.height) // 2

    base.paste(logo, (x, y), logo)

    filename = os.path.basename(image_path)
    out_path = os.path.join(target_folder, filename)

    base.convert("RGB").save(out_path, "JPEG", quality=95)
    return out_path

# =========================
# معالجة كل الصور داخل (مابي حقوق)
# =========================
def process_all():
    if not os.path.exists(LOGO_PATH):
        return [], [], "❌ ملف الشعار غير موجود"

    files = [
        f for f in os.listdir(INPUT_DIR)
        if f.lower().endswith((".jpg", ".jpeg", ".png"))
    ]

    if not files:
        return [], [], None

    next_folder = get_next_folder()
    target_folder = os.path.join(OUTPUT_DIR, next_folder)
    os.makedirs(target_folder, exist_ok=True)

    images = []
    documents = []

    for file in files:
        full_path = os.path.join(INPUT_DIR, file)
        try:
            out = apply_logo(full_path, target_folder)

            ext = os.path.splitext(file)[1].lower()
            if ext in [".jpg", ".jpeg", ".png"]:
                images.append(out)
            else:
                documents.append(out)

            os.remove(full_path)

        except Exception as e:
            print("❌ فشل:", e)

    return images, documents, next_folder

# =====================================================
# دوال مطلوبة من formatter (لا تُحذف)
# =====================================================

def apply_custom_logo(image_path, logo_path, width_ratio, opacity):
    base = Image.open(image_path).convert("RGBA")
    logo = Image.open(logo_path).convert("RGBA")

    bw, bh = base.size
    new_width = int(bw * width_ratio)
    ratio = new_width / logo.width
    new_height = int(logo.height * ratio)

    logo = logo.resize((new_width, new_height), Image.LANCZOS)

    alpha = logo.split()[3]
    alpha = alpha.point(lambda p: int(p * (opacity / 100)))
    logo.putalpha(alpha)

    x = (bw - logo.width) // 2
    y = (bh - logo.height) // 2

    base.paste(logo, (x, y), logo)

    out = tempfile.mktemp(suffix=".png")
    base.save(out, "PNG")
    return out


def apply_custom_logo_video(video_path, logo_path, width_ratio, opacity):
    output = tempfile.mktemp(suffix=".mp4")

    cmd = [
        "ffmpeg",
        "-i", video_path,
        "-i", logo_path,
        "-filter_complex",
        f"[1]scale=iw*{width_ratio}:-1,format=rgba,colorchannelmixer=aa={opacity/100}[logo];"
        f"[0][logo]overlay=(main_w-overlay_w)/2:(main_h-overlay_h)/2",
        "-y",
        output
    ]

    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return output

# =========================
# Handlers تلگرام (تصميم الصور)
# =========================
async def start_design(update, context):
    q = update.callback_query
    await q.answer()
    await q.message.reply_text(
        "📸 تصميم الصور\nاختر العملية:",
        reply_markup=design_menu()
    )

async def apply_design(update, context):
    q = update.callback_query
    await q.answer()

    await q.message.reply_text("⏳ جاري معالجة الصور...")

    images, documents, folder = process_all()

    if not images and not documents:
        await q.message.reply_text("⚠️ لا توجد صور في مجلد (مابي حقوق)")
        return

    if images:
        with open(images[0], "rb") as f:
            await q.message.reply_photo(
                f,
                caption=f"✅ تم تطبيق الشعار\n📁 المجلد: {folder}"
            )

    for doc in documents:
        with open(doc, "rb") as f:
            await q.message.reply_document(f)

async def design_back(update, context):
    q = update.callback_query
    user_id = q.from_user.id
    await q.answer()
    await q.message.reply_text(
        "⬅️ رجوع للقائمة الرئيسية",
        reply_markup=main_keyboard(user_id)
    )

def register(app):
    app.add_handler(CallbackQueryHandler(start_design, pattern="^design:menu$"))
    app.add_handler(CallbackQueryHandler(apply_design, pattern="^design:apply$"))
    app.add_handler(CallbackQueryHandler(design_back, pattern="^design:back$"))
