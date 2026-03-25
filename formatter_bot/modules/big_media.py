import os

TELEGRAM_REMOTE_DOWNLOAD_LIMIT = 20 * 1024 * 1024


def is_local_bot_api_enabled(context=None):
    env_enabled = os.getenv("TELEGRAM_LOCAL_MODE", "").strip().lower() in {"1", "true", "yes", "on"}
    if env_enabled:
        return True

    if context is None:
        return False

    bot = getattr(context, "bot", None)
    base_file_url = str(getattr(bot, "base_file_url", "") or "")
    base_url = str(getattr(bot, "base_url", "") or "")

    return (
        "api.telegram.org" not in base_file_url and bool(base_file_url)
    ) or (
        "api.telegram.org" not in base_url and bool(base_url)
    )


def get_message_media_meta(msg):
    if getattr(msg, "video", None):
        return {"file_size": int(getattr(msg.video, "file_size", 0) or 0), "label": "الفيديو"}

    if getattr(msg, "video_note", None):
        return {"file_size": int(getattr(msg.video_note, "file_size", 0) or 0), "label": "الفيديو"}

    if getattr(msg, "document", None):
        mime = str(getattr(msg.document, "mime_type", "") or "").lower()
        file_name = str(getattr(msg.document, "file_name", "") or "")
        label = "الملف"
        if mime.startswith("video") or file_name.lower().endswith((".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v", ".wmv", ".flv", ".mpeg", ".mpg", ".3gp", ".ts", ".ogv", ".mts", ".m2ts", ".vob")):
            label = "الفيديو"
        elif mime.startswith("image") or file_name.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff", ".heic", ".heif", ".gif")):
            label = "الصورة"
        return {"file_size": int(getattr(msg.document, "file_size", 0) or 0), "label": label}

    return None


def get_media_download_warning(label, file_size):
    size_mb = round(file_size / (1024 * 1024), 2)
    return (
        f"⚠️ حجم {label} هو {size_mb} MB\n"
        f"هذا أكبر من 20 MB والبوت الآن يعمل على Bot API العادي.\n"
        f"لكي يستقبل ويعالج الملفات الأكبر فعليًا، شغّل البوت على Telegram Local Bot API ثم فعّل TELEGRAM_LOCAL_MODE=1."
    )
