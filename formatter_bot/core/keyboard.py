from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from settings import ADMINS


def is_admin(user_id):
    return user_id in ADMINS


def main_keyboard(user_id=None):
    buttons = []

    # أزرار الأدمن فقط
    if user_id and is_admin(user_id):
        buttons.append(
            [InlineKeyboardButton("📸 تصميم الصور", callback_data="design:menu")]
        )

    # زر للجميع
    buttons.append(
        [InlineKeyboardButton("🎨 صمم صورتك", callback_data="custom:start")]
    )

    return InlineKeyboardMarkup(buttons)


def result_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📋 نسخ الإعلان", callback_data="fmt:copy"),
            InlineKeyboardButton("💬 واتساب", callback_data="fmt:wa")
        ],
        [
            InlineKeyboardButton("➕ حفظ الإعلان", callback_data="fmt:save")
        ]
    ])


def design_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("▶ تطبيق الشعار على الصور", callback_data="design:apply")],
        [InlineKeyboardButton("🖼 معاينة أول صورة", callback_data="design:preview")],
        [InlineKeyboardButton("📦 إرسال كل الصور", callback_data="design:send_all")],
        [InlineKeyboardButton("⬅ رجوع", callback_data="design:back")]
    ])


# زر إنهاء الإرسال (خاص بزر صمم صورتك فقط)
def finish_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 إنهاء الإرسال", callback_data="custom:finish")]
    ])
    
