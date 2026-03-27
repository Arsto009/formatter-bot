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


def _clamp(value, min_value, max_value):
    return max(min_value, min(max_value, value))


def _build_video_tone_filter(brightness_value=0):
    v = float(brightness_value or 0)

    positive = max(0.0, v)
    negative = abs(min(0.0, v))

    # لا نخلي brightness قوي حتى لا يفتح الأسود ويصير ضباب
    if v >= 0:
        brightness = _clamp(v / 220.0, 0.0, 0.18)
    else:
        brightness = _clamp(v / 140.0, -0.25, 0.0)

    # كلما زادت الإنارة نقوي التباين أكثر حتى يبقى الظل واضح
    contrast = _clamp(1.0 + (positive * 0.0055) + (negative * 0.0025), 1.0, 1.28)

    # تشبع خفيف فقط للفيديو
    saturation = _clamp(1.0 + (positive * 0.0045) - (negative * 0.0020), 0.92, 1.22)

    return (
        f"eq=brightness={brightness:.4f}:"
        f"contrast={contrast:.4f}:"
        f"saturation={saturation:.4f}"
    )


def _run_ffmpeg_logo_overlay(video_path, prepared_logo_path, output_path, brightness_value=0, audio_codec="copy"):
    video_tone = _build_video_tone_filter(brightness_value)
    if brightness_value:
        filter_complex = (
            f"[0:v]{video_tone}[base_b];"
            f"[1:v]format=rgba[logo_rgba];"
            f"[base_b][logo_rgba]overlay=(main_w-overlay_w)/2:(main_h-overlay_h)/2[v]"
        )
    else:
        filter_complex = (
            f"[0:v]{video_tone}[base_b];"
            f"[1:v]format=rgba[logo_rgba];"
            f"[base_b][logo_rgba]overlay=(main_w-overlay_w)/2:(main_h-overlay_h)/2[v]"
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
    ]

    if audio_codec == "copy":
        cmd += ["-c:a", "copy"]
    else:
        cmd += ["-c:a", "aac", "-b:a", "192k"]

    cmd.append(output_path)

    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def apply_custom_logo_video(video_path, logo_path, width_ratio, opacity, brightness_value=0):
    ext = os.path.splitext(video_path)[1] or ".mp4"
    output = tempfile.mktemp(suffix=ext)

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
    ext = os.path.splitext(video_path)[1] or ".mp4"
    output = tempfile.mktemp(suffix=ext)

    cmd = [
        "ffmpeg",
        "-y",
        "-i", video_path,
        "-vf", _build_video_tone_filter(brightness_value),
        "-map", "0:v",
        "-map", "0:a?",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        "-movflags", "+faststart",
        output
    ]

    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0 or not os.path.exists(output) or os.path.getsize(output) < 1000:
        try:
            if os.path.exists(output):
                os.remove(output)
        except Exception:
            pass

        fallback_cmd = cmd[:]
        for i in range(len(fallback_cmd)):
            if fallback_cmd[i] == "copy" and i > 0 and fallback_cmd[i-1] == "-c:a":
                fallback_cmd[i:i+1] = ["aac"]
                fallback_cmd.insert(i+1, "-b:a")
                fallback_cmd.insert(i+2, "192k")
                break
        result = subprocess.run(fallback_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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
