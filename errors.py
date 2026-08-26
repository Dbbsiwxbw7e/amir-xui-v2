"""Typed errors — every failure has a clear class."""


class AppError(Exception):
    """Base. `user_msg` is safe to show in Telegram."""
    user_msg = "خطای غیرمنتظره."

    def __init__(self, user_msg: str | None = None):
        if user_msg:
            self.user_msg = user_msg
        super().__init__(self.user_msg)


class AuthError(AppError):
    user_msg = "🔑 توکن Railway نامعتبره."


class NetworkError(AppError):
    user_msg = "🌐 خطای شبکه — دوباره تلاش کن."


class LimitError(AppError):
    user_msg = ("🚫 Railway اجازه ساخت منبع جدید نمیده.\n"
                "• سقف Free plan پر شده؟ پروژه‌های قدیمی رو حذف کن\n"
                "• اکانت جدید بدون کارت تأییدشده محدوده\n"
                "• هر ۳۰ ثانیه یک پروژه — کمی صبر کن")


class PanelError(AppError):
    user_msg = "🎛 خطا در ارتباط با پنل 3x-ui."
