from modules import formatter
from modules import designer

from telegram.ext import Application, CommandHandler
from telegram import ReplyKeyboardMarkup, KeyboardButton

from settings import BOT_TOKEN, PROJECT_TAG
from core.keyboard import main_keyboard


# =========================
# زر Start ثابت للبوت كله
# =========================
def global_start_keyboard():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("🔄 Start")]],
        resize_keyboard=True
    )


# =========================
# أمر /start
# =========================
async def start(update, context):
    user_id = update.effective_user.id

    await update.message.reply_text(
        f"فيض ابو الحسن 🏢
        مرحبًا بك في بوت تنسيق الإعلانات\n\n"
        "اختر العملية من القائمة بالأسفل:",
        reply_markup=global_start_keyboard()
    )

    await update.message.reply_text(
        "القائمة الرئيسية:",
        reply_markup=main_keyboard(user_id)
    )


# =========================
# تشغيل البوت
# =========================
def main():
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN غير موجود في settings.py")
        return

    print("🚀 Formatter Bot Starting...")

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    # 🔴 الترتيب هنا هو الحل
    designer.register(app)    # 📸 تصميم الصور (أولاً)
    formatter.register(app)   # 🎨 صمم صورتك (أخيرًا لأنه عام)

    print("✅ Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
