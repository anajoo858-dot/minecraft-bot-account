import telebot
import time
import os
import random
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service

# ============ التوكن ============
BOT_TOKEN = os.environ.get("BOT_TOKEN") or "YOUR_BOT_TOKEN_HERE"
bot = telebot.TeleBot(BOT_TOKEN)

# ============ SESSIONS ============
user_sessions = {}

# ============ المتصفح ============
def create_browser():
    options = ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--remote-debugging-port=9222")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    # استخدم Chrome المثبت على النظام
    chrome_path = os.environ.get("CHROME_PATH", "/usr/bin/google-chrome")
    options.binary_location = chrome_path
    
    # ChromeDriver في PATH
    service = Service("/usr/bin/chromedriver")
    driver = webdriver.Chrome(service=service, options=options)
    
    return driver

def human_typing(element, text):
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(0.05, 0.12))

# ============ تسجيل الدخول ============
def login_microsoft(driver, email, password):
    try:
        driver.get("https://login.live.com")
        wait = WebDriverWait(driver, 30)

        email_input = wait.until(EC.presence_of_element_located((By.NAME, "loginfmt")))
        human_typing(email_input, email)
        driver.find_element(By.ID, "idSIButton9").click()
        time.sleep(2)

        pass_input = wait.until(EC.presence_of_element_located((By.NAME, "passwd")))
        human_typing(pass_input, password)
        driver.find_element(By.ID, "idSIButton9").click()
        time.sleep(3)

        if "identity" in driver.current_url or "code" in driver.current_url:
            return "2fa"

        return "success" if "login" not in driver.current_url.lower() else "fail"
    except Exception as e:
        return str(e)

# ============ تحديث البريد الإلكتروني ============
def update_email(driver, new_email):
    try:
        driver.get("https://account.live.com/names/manage")
        time.sleep(3)

        add_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), 'Add')]"))
        )
        add_btn.click()
        time.sleep(2)

        alias_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, "newEmail"))
        )
        human_typing(alias_input, new_email)
        driver.find_element(By.ID, "iAdd").click()
        time.sleep(3)

        driver.get("https://account.live.com/names/manage")
        time.sleep(2)
        for btn in driver.find_elements(By.XPATH, "//button[contains(text(), 'Make primary')]"):
            btn.click()
            time.sleep(1)
            break

        return "✅ تم إضافة بريدك الإلكتروني الجديد وجعله الأساسي."
    except Exception as e:
        return f"⚠️ حدث خطأ أثناء تحديث البريد: {str(e)[:100]}"

# ============ تغيير كلمة المرور ============
def change_password(driver, current_password, new_password):
    try:
        driver.get("https://account.live.com/password/change")
        time.sleep(3)

        wait = WebDriverWait(driver, 10)
        old_pass = wait.until(EC.presence_of_element_located((By.NAME, "oldPassword")))
        human_typing(old_pass, current_password)

        new_pass1 = driver.find_element(By.NAME, "newPassword")
        human_typing(new_pass1, new_password)

        new_pass2 = driver.find_element(By.NAME, "verifyPassword")
        human_typing(new_pass2, new_password)

        driver.find_element(By.ID, "iSave").click()
        time.sleep(3)
        return "✅ تم تغيير كلمة المرور بنجاح."
    except Exception as e:
        return f"⚠️ حدث خطأ أثناء تغيير كلمة المرور: {str(e)[:100]}"

# ============ التحقق من رخصة ماينكرافت ============
def check_minecraft_license(driver):
    try:
        driver.get("https://www.minecraft.net/en-us/profile")
        time.sleep(3)
        if "profile" in driver.current_url:
            try:
                username = driver.find_element(By.CLASS_NAME, "profile-name").text
                return f"✅ الحساب يملك رخصة ماينكرافت. اسم المستخدم: {username}"
            except:
                pass
        return "⚠️ لم يتم العثور على رخصة ماينكرافت على هذا الحساب."
    except:
        return "⚠️ تعذر التحقق من رخصة ماينكرافت."

# ============ أوامر التيليجرام ============
@bot.message_handler(commands=['start'])
def start(msg):
    bot.reply_to(msg,
        "🔐 **مرحبًا بك في بوت تأمين الحساب**\n\n"
        "هذا البوت يساعدك على تغيير بيانات حساب ماينكرافت الخاص بك.\n\n"
        "**للاستخدام:**\n"
        "/secure <الإيميل_الحالي> <كلمة_المرور_الحالية> <الإيميل_الجديد> <كلمة_المرور_الجديدة>\n\n"
        "**مثال:**\n"
        "/secure old@outlook.com OldPass123 my@email.com MyNewPass456\n\n"
        "إذا كان التفعيل بخطوتين (2FA) مفعلًا، استخدم الأمر /code <الرمز>")

@bot.message_handler(commands=['secure'])
def secure(msg):
    args = msg.text.split()
    if len(args) < 5:
        bot.reply_to(msg, "❌ الصيغة الصحيحة:\n/secure <الإيميل_الحالي> <كلمة_المرور_الحالية> <الإيميل_الجديد> <كلمة_المرور_الجديدة>")
        return

    old_email, old_pass, new_email, new_pass = args[1], args[2], args[3], args[4]
    chat_id = msg.chat.id

    bot.reply_to(msg, f"⏳ جاري تسجيل الدخول إلى الحساب: {old_email}...")

    try:
        driver = create_browser()
    except Exception as e:
        bot.reply_to(msg, f"❌ فشل إنشاء المتصفح: {str(e)[:200]}")
        return

    user_sessions[chat_id] = {"driver": driver, "old_pass": old_pass, "new_email": new_email, "new_pass": new_pass}

    result = login_microsoft(driver, old_email, old_pass)

    if result == "2fa":
        bot.reply_to(msg, "🔐 التفعيل بخطوتين (2FA) مفعل! أرسل /code <الرمز>")
        user_sessions[chat_id]["step"] = "2fa"
        return

    if result != "success":
        bot.reply_to(msg, f"❌ فشل تسجيل الدخول: {result}")
        driver.quit()
        del user_sessions[chat_id]
        return

    bot.reply_to(msg, "✅ تم تسجيل الدخول بنجاح!")
    bot.reply_to(msg, "🔍 جاري التحقق من رخصة ماينكرافت...")
    bot.reply_to(msg, check_minecraft_license(driver))

    bot.reply_to(msg, "📧 جاري تحديث البريد الإلكتروني...")
    bot.reply_to(msg, update_email(driver, new_email))

    bot.reply_to(msg, "🔑 جاري تغيير كلمة المرور...")
    bot.reply_to(msg, change_password(driver, old_pass, new_pass))

    bot.reply_to(msg,
        f"✅ **تم تأمين الحساب بنجاح!**\n\n"
        f"📧 **الإيميل الجديد:** `{new_email}`\n"
        f"🔑 **كلمة المرور الجديدة:** `{new_pass}`\n\n"
        f"⚠️ احتفظ بهذه البيانات في مكان آمن.",
        parse_mode="Markdown")

    driver.quit()
    del user_sessions[chat_id]

@bot.message_handler(commands=['code'])
def code(msg):
    args = msg.text.split()
    if len(args) < 2:
        bot.reply_to(msg, "❌ استخدم: /code <الرمز>")
        return

    code = args[1]
    chat_id = msg.chat.id

    if chat_id not in user_sessions or user_sessions[chat_id].get("step") != "2fa":
        bot.reply_to(msg, "❌ لا توجد جلسة نشطة تنتظر رمز التحقق.")
        return

    driver = user_sessions[chat_id]["driver"]
    bot.reply_to(msg, "⏳ جاري التحقق من الرمز...")

    try:
        wait = WebDriverWait(driver, 30)
        code_input = wait.until(EC.presence_of_element_located((By.NAME, "otc")))
        human_typing(code_input, code)
        driver.find_element(By.ID, "iVerify").click()
        time.sleep(3)

        bot.reply_to(msg, "✅ تم التحقق بنجاح! جاري استكمال التحديثات...")

        old_pass = user_sessions[chat_id]["old_pass"]
        new_email = user_sessions[chat_id]["new_email"]
        new_pass = user_sessions[chat_id]["new_pass"]

        bot.reply_to(msg, check_minecraft_license(driver))
        bot.reply_to(msg, update_email(driver, new_email))
        bot.reply_to(msg, change_password(driver, old_pass, new_pass))

        bot.reply_to(msg,
            f"✅ **تم تأمين الحساب بنجاح!**\n\n"
            f"📧 **الإيميل الجديد:** `{new_email}`\n"
            f"🔑 **كلمة المرور الجديدة:** `{new_pass}`\n\n"
            f"⚠️ احتفظ بهذه البيانات في مكان آمن.",
            parse_mode="Markdown")

        driver.quit()
        del user_sessions[chat_id]

    except Exception as e:
        bot.reply_to(msg, f"❌ فشل التحقق: {str(e)[:100]}")

@bot.message_handler(commands=['cancel'])
def cancel(msg):
    chat_id = msg.chat.id
    if chat_id in user_sessions:
        user_sessions[chat_id]["driver"].quit()
        del user_sessions[chat_id]
        bot.reply_to(msg, "✅ تم إلغاء الجلسة.")
    else:
        bot.reply_to(msg, "❌ لا توجد جلسة نشطة.")

@bot.message_handler(func=lambda m: True)
def fallback(msg):
    bot.reply_to(msg,
        "📌 **الأوامر المتاحة:**\n"
        "/secure <الإيميل_الحالي> <كلمة_المرور_الحالية> <الإيميل_الجديد> <كلمة_المرور_الجديدة>\n"
        "/code <الرمز>\n"
        "/cancel")

# ============ تشغيل البوت ============
if __name__ == "__main__":
    print("✅ البوت يعمل الآن!")
    while True:
        try:
            bot.polling(none_stop=True, interval=1)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)
