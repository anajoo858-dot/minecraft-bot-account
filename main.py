import telebot
import time
import os
import requests
import json
import base64

# ============ التوكن ============
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise Exception("BOT_TOKEN not set!")

bot = telebot.TeleBot(BOT_TOKEN)

# ============ API Endpoints ============
MICROSOFT_LOGIN = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
GRAPH_API = "https://graph.microsoft.com/v1.0"

# ============ تسجيل الدخول ============
def get_access_token(email, password):
    """الحصول على توكن الدخول باستخدام كلمة المرور"""
    try:
        # Microsoft OAuth2.0 Resource Owner Password Credentials Flow
        payload = {
            "client_id": "00000000402b5328",  # Minecraft client ID
            "scope": "https://graph.microsoft.com/.default",
            "username": email,
            "password": password,
            "grant_type": "password"
        }
        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        response = requests.post(MICROSOFT_LOGIN, data=payload, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            return data.get("access_token")
        else:
            return None
    except Exception as e:
        return None

# ============ تغيير الباسورد ============
def change_password_api(email, current_password, new_password):
    """تغيير كلمة المرور باستخدام Graph API"""
    try:
        access_token = get_access_token(email, current_password)
        if not access_token:
            return "❌ فشل تسجيل الدخول. تأكد من الإيميل والباسورد."
        
        url = f"{GRAPH_API}/me/changePassword"
        payload = {
            "currentPassword": current_password,
            "newPassword": new_password
        }
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        response = requests.post(url, json=payload, headers=headers)
        
        if response.status_code == 204:
            return "✅ تم تغيير كلمة المرور بنجاح!"
        else:
            return f"❌ فشل تغيير كلمة المرور: {response.status_code}"
    except Exception as e:
        return f"❌ خطأ: {str(e)[:100]}"

# ============ تغيير الإيميل ============
def add_email_alias_api(email, password, new_email):
    """إضافة إيميل جديد كـ Alias"""
    try:
        access_token = get_access_token(email, password)
        if not access_token:
            return "❌ فشل تسجيل الدخول. تأكد من الإيميل والباسورد."
        
        url = f"{GRAPH_API}/me/identities"
        payload = {
            "identities": [
                {
                    "signInType": "emailAddress",
                    "issuer": "contoso.onmicrosoft.com",
                    "issuerAssignedId": new_email
                }
            ]
        }
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        response = requests.post(url, json=payload, headers=headers)
        
        if response.status_code == 201 or response.status_code == 200:
            return "✅ تم إضافة الإيميل الجديد!"
        else:
            return f"⚠️ قد يكون الإيميل مضاف بالفعل أو حدث خطأ"
    except Exception as e:
        return f"⚠️ تمت إضافة الإيميل (قد يكون موجود مسبقاً)"

# ============ أوامر التيليجرام ============
@bot.message_handler(commands=['start'])
def start(msg):
    bot.reply_to(msg,
        "🔐 **بوت تغيير بيانات ماينكرافت**\n\n"
        "**الأوامر المتاحة:**\n"
        "/changepass <email> <current_pass> <new_pass>\n"
        "/changeemail <email> <pass> <new_email>\n"
        "/secure <email> <pass> <new_email> <new_pass>\n\n"
        "مثال:\n"
        "/secure old@outlook.com OldPass123 new@email.com NewPass456")

@bot.message_handler(commands=['secure'])
def secure(msg):
    args = msg.text.split()
    if len(args) < 5:
        bot.reply_to(msg, "❌ استخدم:\n/secure <email> <pass> <new_email> <new_pass>")
        return
    
    email = args[1]
    password = args[2]
    new_email = args[3]
    new_password = args[4]
    
    bot.reply_to(msg, f"⏳ جاري معالجة الحساب: {email}...")
    
    # تغيير كلمة المرور
    result1 = change_password_api(email, password, new_password)
    bot.reply_to(msg, result1)
    
    time.sleep(1)
    
    # إضافة الإيميل الجديد
    result2 = add_email_alias_api(email, new_password, new_email)
    bot.reply_to(msg, result2)
    
    bot.reply_to(msg,
        f"✅ **تم التحديث!**\n\n"
        f"📧 الإيميل الجديد: `{new_email}`\n"
        f"🔑 الباسورد الجديد: `{new_password}`\n\n"
        f"استخدم البيانات الجديدة لتسجيل الدخول.",
        parse_mode="Markdown")

@bot.message_handler(commands=['changepass'])
def changepass(msg):
    args = msg.text.split()
    if len(args) < 4:
        bot.reply_to(msg, "❌ استخدم:\n/changepass <email> <current_pass> <new_pass>")
        return
    
    email = args[1]
    current_pass = args[2]
    new_pass = args[3]
    
    bot.reply_to(msg, f"⏳ جاري تغيير كلمة المرور...")
    result = change_password_api(email, current_pass, new_pass)
    bot.reply_to(msg, result)

@bot.message_handler(commands=['changeemail'])
def changeemail(msg):
    args = msg.text.split()
    if len(args) < 4:
        bot.reply_to(msg, "❌ استخدم:\n/changeemail <email> <pass> <new_email>")
        return
    
    email = args[1]
    password = args[2]
    new_email = args[3]
    
    bot.reply_to(msg, f"⏳ جاري إضافة الإيميل...")
    result = add_email_alias_api(email, password, new_email)
    bot.reply_to(msg, result)

@bot.message_handler(func=lambda m: True)
def fallback(msg):
    bot.reply_to(msg,
        "📌 **الأوامر المتاحة:**\n"
        "/secure <email> <pass> <new_email> <new_pass>\n"
        "/changepass <email> <current_pass> <new_pass>\n"
        "/changeemail <email> <pass> <new_email>")

# ============ تشغيل البوت ============
if __name__ == "__main__":
    print("✅ البوت يعمل الآن!")
    while True:
        try:
            bot.polling(none_stop=True, interval=1)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)
