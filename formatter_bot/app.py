from modules import poster, formatter, designer
from telegram.ext import Application, CommandHandler
from telegram import ReplyKeyboardMarkup, KeyboardButton
from settings import BOT_TOKEN, PROJECT_TAG
from core.keyboard import main_keyboard

import logging

# تفعيل التسجيل (لرؤية الأخطاء)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

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
    logger.info(f"User {user_id} started the bot")
    
    try:
        await update.message.reply_text(
            f"{PROJECT_TAG} 🏢 مرحبًا بك في بوت تنسيق الإعلانات\n\n"
            "اختر العملية من القائمة بالأسفل:",
            reply_markup=global_start_keyboard()
        )

        await update.message.reply_text(
            "القائمة الرئيسية:",
            reply_markup=main_keyboard(user_id)
        )
    except Exception as e:
        logger.error(f"Error in start handler: {e}")
        await update.message.reply_text("❌ حدث خطأ. يرجى المحاولة لاحقاً")

# =========================
# معالج الأخطاء العام
# =========================
async def error_handler(update, context):
    logger.error(f"Update {update} caused error {context.error}")

# =========================
# تشغيل البوت
# =========================
def main():
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN غير موجود في settings.py")
        print("❌ BOT_TOKEN غير موجود في settings.py")
        return

    if BOT_TOKEN == "PUT_YOUR_TOKEN_HERE":
        logger.error("❌ يرجى وضع التوكن الحقيقي في settings.py")
        print("❌ يرجى وضع التوكن الحقيقي في settings.py")
        return

    print("🚀 Formatter Bot Starting...")
    logger.info("Starting Formatter Bot...")

    try:
        # بناء التطبيق
        app = Application.builder().token(BOT_TOKEN).build()

        # إضافة المعالجات
        app.add_handler(CommandHandler("start", start))
        
        # تسجيل الوحدات
        designer.register(app)    # 📸 تصميم الصور
        poster.register(app)      # 📢 نشر منشور
        formatter.register(app)   # 🎨 صمم صورتك

        # إضافة معالج الأخطاء
        app.add_error_handler(error_handler)

        # تشغيل البوت
        print("✅ Bot is running... Press Ctrl+C to stop")
        logger.info("Bot started successfully")
        app.run_polling()
        
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        print(f"❌ فشل تشغيل البوت: {e}")

if __name__ == "__main__":
    main()
