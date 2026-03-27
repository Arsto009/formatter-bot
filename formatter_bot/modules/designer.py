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


def _get_video_dimensions(video_path):
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height",
                "-of", "csv=s=x:p=0",
                video_path,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if result.returncode == 0:
            out = (result.stdout or "").strip()
            if "x" in out:
                w, h = out.split("x", 1)
                return int(w), int(h)
    except Exception:
        pass
    return None, None


def _prepare_logo_for_video(logo_path, video_width, width_ratio, opacity):
    logo = Image.open(logo_path).convert("RGBA")

    if not video_width:
        video_width = logo.width

    new_width = max(1, int(video_width * float(width_ratio)))
    ratio = new_width / max(1, logo.width)
    new_height = max(1, int(logo.height * ratio))

    logo = logo.resize((new_width, new_height), Image.LANCZOS)

    alpha = logo.split()[3]
    alpha = alpha.point(lambda p: int(p * (float(opacity) / 100)))
    logo.putalpha(alpha)

    prepared = tempfile.mktemp(suffix=".png")
    logo.save(prepared, "PNG")
    return prepared


def _build_video_tone_filter(brightness_value=0):
    if not brightness_value:
        return None

    value = max(-100, min(100, int(brightness_value)))
    pos = max(0, value)
    neg = abs(min(0, value))

    # للفيديو فقط: سطوع + تشبع + تقوية ظل/عمق بشكل أوضح ومن دون غسل الألوان
    brightness = value / 125.0
    contrast = 1.0 + (abs(value) / 160.0)
    saturation = 1.0 + (pos / 38.0)

    # عند خفض الإنارة ننزل التشبع قليلًا فقط حتى لا تصبح الألوان باهتة أو متسخة
    if value < 0:
        saturation = 1.0 - (neg / 210.0)

    # Gamma و gamma_weight يفيدان في إبراز العمق وتقوية الظل بدل الإحساس بالضباب
    gamma = 1.0 + (pos / 260.0) - (neg / 320.0)
    gamma_weight = 1.0 - (pos / 170.0)

    contrast = max(0.9, min(1.9, contrast))
    saturation = max(0.75, min(3.1, saturation))
    gamma = max(0.82, min(1.35, gamma))
    gamma_weight = max(0.50, min(1.0, gamma_weight))

    return (
        "eq="
        f"brightness={brightness:.4f}:"
        f"contrast={contrast:.4f}:"
        f"saturation={saturation:.4f}:"
        f"gamma={gamma:.4f}:"
        f"gamma_weight={gamma_weight:.4f}"
    )


def _run_ffmpeg_logo_overlay(video_path, prepared_logo_path, output_path, brightness_value=0, audio_codec="copy"):
    tone_filter = _build_video_tone_filter(brightness_value)
    if tone_filter:
        filter_complex = (
            f"[0:v]{tone_filter}[base_t];"
            f"[1:v]format=rgba[logo_rgba];"
            f"[base_t][logo_rgba]overlay=(main_w-overlay_w)/2:(main_h-overlay_h)/2[v]"
        )
    else:
        filter_complex = (
            f"[1:v]format=rgba[logo_rgba];"
            f"[0:v][logo_rgba]overlay=(main_w-overlay_w)/2:(main_h-overlay_h)/2[v]"
        )

    cmd = [
        "ffmpeg",
        "-y",
        "-i", video_path,
        "-i", prepared_logo_path,
        "-filter_complex", filter_complex,
        "-map", "[v]",
        "-map", "0:a?",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        "-map_metadata", "0",
    ]

    if audio_codec == "copy":
        cmd += ["-c:a", "copy"]
    else:
        cmd += ["-c:a", "aac", "-b:a", "192k"]

    cmd.append(output_path)

    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def apply_custom_logo_video(video_path, logo_path, width_ratio, opacity, brightness_value=0):
    source_ext = os.path.splitext(video_path)[1].lower() or ".mp4"
    safe_ext = source_ext if source_ext in {".mp4", ".mov", ".m4v", ".mkv", ".avi", ".webm"} else ".mp4"
    output = tempfile.mktemp(suffix=safe_ext)

    video_width, _ = _get_video_dimensions(video_path)
    prepared_logo = _prepare_logo_for_video(logo_path, video_width, width_ratio, opacity)

    try:
        result = _run_ffmpeg_logo_overlay(
            video_path,
            prepared_logo,
            output,
            brightness_value=brightness_value,
            audio_codec="copy",
        )

        if result.returncode != 0 or not os.path.exists(output) or os.path.getsize(output) < 1000:
            try:
                if os.path.exists(output):
                    os.remove(output)
            except Exception:
                pass

            result = _run_ffmpeg_logo_overlay(
                video_path,
                prepared_logo,
                output,
                brightness_value=brightness_value,
                audio_codec="aac",
            )

        if result.returncode != 0 or not os.path.exists(output) or os.path.getsize(output) < 1000:
            try:
                if os.path.exists(output):
                    os.remove(output)
            except Exception:
                pass
            return video_path
        return output
    finally:
        try:
            if os.path.exists(prepared_logo):
                os.remove(prepared_logo)
        except Exception:
            pass


def apply_brightness_video(video_path, brightness_value=0):
    source_ext = os.path.splitext(video_path)[1].lower() or ".mp4"
    safe_ext = source_ext if source_ext in {".mp4", ".mov", ".m4v", ".mkv", ".avi", ".webm"} else ".mp4"
    output = tempfile.mktemp(suffix=safe_ext)
    tone_filter = _build_video_tone_filter(brightness_value) or "null"

    cmd = [
        "ffmpeg",
        "-y",
        "-i", video_path,
        "-vf", tone_filter,
        "-map", "0:v",
        "-map", "0:a?",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        "-movflags", "+faststart",
        "-map_metadata", "0",
        output
    ]

    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0 or not os.path.exists(output) or os.path.getsize(output) < 1000:
        try:
            if os.path.exists(output):
                os.remove(output)
        except Exception:
            pass
        return video_path
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
