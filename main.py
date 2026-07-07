import telebot
import time
import os
import random
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# ============ TOKEN ============
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise Exception("BOT_TOKEN not set!")

bot = telebot.TeleBot(BOT_TOKEN)
user_sessions = {}

# ============ BROWSER ============
def create_browser():
    options = ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--remote-debugging-port=9222")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    return driver

def human_typing(element, text):
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(0.05, 0.12))

# ============ LOGIN ============
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

# ============ CHANGE PASSWORD ============
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
        return "✅ Password changed successfully!"
    except Exception as e:
        return f"❌ Failed to change password: {str(e)[:100]}"

# ============ UPDATE EMAIL ============
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

        return "✅ New email added and set as primary!"
    except Exception as e:
        return f"⚠️ Error updating email: {str(e)[:100]}"

# ============ CHECK MINECRAFT LICENSE ============
def check_minecraft_license(driver):
    try:
        driver.get("https://www.minecraft.net/en-us/profile")
        time.sleep(3)
        if "profile" in driver.current_url:
            try:
                username = driver.find_element(By.CLASS_NAME, "profile-name").text
                return f"✅ Account has Minecraft license. Username: `{username}`"
            except:
                pass
        return "⚠️ No Minecraft license found on this account."
    except:
        return "⚠️ Could not verify license."

# ============ TELEGRAM COMMANDS ============
@bot.message_handler(commands=['start'])
def start(msg):
    bot.reply_to(msg,
        "🔐 *Minecraft Account Security Bot*\n\n"
        "📌 *Available Commands:*\n"
        "`/secure <email> <pass> <new_email> <new_pass>`\n"
        "`/code <code>`\n"
        "`/cancel`\n\n"
        "📝 *Example:*\n"
        "`/secure old@outlook.com OldPass123 new@email.com NewPass456`",
        parse_mode="Markdown")

@bot.message_handler(commands=['secure'])
def secure(msg):
    args = msg.text.split()
    if len(args) < 5:
        bot.reply_to(msg,
            "❌ *Usage:*\n"
            "`/secure <email> <pass> <new_email> <new_pass>`",
            parse_mode="Markdown")
        return

    old_email, old_pass, new_email, new_pass = args[1], args[2], args[3], args[4]
    chat_id = msg.chat.id

    bot.reply_to(msg, f"⏳ *Logging in to:* `{old_email}`...", parse_mode="Markdown")

    try:
        driver = create_browser()
    except Exception as e:
        bot.reply_to(msg, f"❌ *Browser error:* `{str(e)[:200]}`", parse_mode="Markdown")
        return

    user_sessions[chat_id] = {
        "driver": driver,
        "old_pass": old_pass,
        "new_email": new_email,
        "new_pass": new_pass
    }

    result = login_microsoft(driver, old_email, old_pass)

    if result == "2fa":
        bot.reply_to(msg,
            "🔐 *2FA Required!*\n"
            "Send `/code <code>`",
            parse_mode="Markdown")
        user_sessions[chat_id]["step"] = "2fa"
        return

    if result != "success":
        bot.reply_to(msg, f"❌ *Login failed:* `{result}`", parse_mode="Markdown")
        driver.quit()
        del user_sessions[chat_id]
        return

    bot.reply_to(msg, "✅ *Logged in successfully!*", parse_mode="Markdown")
    bot.reply_to(msg, check_minecraft_license(driver), parse_mode="Markdown")
    bot.reply_to(msg, update_email(driver, new_email), parse_mode="Markdown")
    bot.reply_to(msg, change_password(driver, old_pass, new_pass), parse_mode="Markdown")

    bot.reply_to(msg,
        f"✅ *Account Secured!*\n"
        f"📧 *New Email:* `{new_email}`\n"
        f"🔑 *New Password:* `{new_pass}`",
        parse_mode="Markdown")

    driver.quit()
    del user_sessions[chat_id]

@bot.message_handler(commands=['code'])
def code(msg):
    args = msg.text.split()
    if len(args) < 2:
        bot.reply_to(msg, "❌ *Usage:* `/code <code>`", parse_mode="Markdown")
        return

    code = args[1]
    chat_id = msg.chat.id

    if chat_id not in user_sessions or user_sessions[chat_id].get("step") != "2fa":
        bot.reply_to(msg, "❌ *No active session waiting for 2FA.*", parse_mode="Markdown")
        return

    driver = user_sessions[chat_id]["driver"]
    bot.reply_to(msg, "⏳ *Verifying code...*", parse_mode="Markdown")

    try:
        wait = WebDriverWait(driver, 30)
        code_input = wait.until(EC.presence_of_element_located((By.NAME, "otc")))
        human_typing(code_input, code)
        driver.find_element(By.ID, "iVerify").click()
        time.sleep(3)

        bot.reply_to(msg, "✅ *2FA Verified!*", parse_mode="Markdown")

        old_pass = user_sessions[chat_id]["old_pass"]
        new_email = user_sessions[chat_id]["new_email"]
        new_pass = user_sessions[chat_id]["new_pass"]

        bot.reply_to(msg, check_minecraft_license(driver), parse_mode="Markdown")
        bot.reply_to(msg, update_email(driver, new_email), parse_mode="Markdown")
        bot.reply_to(msg, change_password(driver, old_pass, new_pass), parse_mode="Markdown")

        bot.reply_to(msg,
            f"✅ *Account Secured!*\n"
            f"📧 *New Email:* `{new_email}`\n"
            f"🔑 *New Password:* `{new_pass}`",
            parse_mode="Markdown")

        driver.quit()
        del user_sessions[chat_id]

    except Exception as e:
        bot.reply_to(msg, f"❌ *Verification failed:* `{str(e)[:100]}`", parse_mode="Markdown")

@bot.message_handler(commands=['cancel'])
def cancel(msg):
    chat_id = msg.chat.id
    if chat_id in user_sessions:
        user_sessions[chat_id]["driver"].quit()
        del user_sessions[chat_id]
        bot.reply_to(msg, "✅ *Session cancelled.*", parse_mode="Markdown")
    else:
        bot.reply_to(msg, "❌ *No active session.*", parse_mode="Markdown")

@bot.message_handler(func=lambda m: True)
def fallback(msg):
    bot.reply_to(msg,
        "📌 *Available Commands:*\n"
        "`/secure <email> <pass> <new_email> <new_pass>`\n"
        "`/code <code>`\n"
        "`/cancel`",
        parse_mode="Markdown")

# ============ RUN BOT ============
if __name__ == "__main__":
    print("✅ Bot is running!")
    while True:
        try:
            bot.polling(none_stop=True, interval=1)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)
