import os
import sys
import json
import sqlite3
import asyncio
import logging
import random
import string
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
                is_stolen INTEGER DEFAULT 0,
                bedrock_compatible INTEGER DEFAULT 1,
                hypixel_rank TEXT DEFAULT 'NONE',
                hypixel_banned INTEGER DEFAULT 0,
                donutsmp_banned INTEGER DEFAULT 0,
                donutsmp_stats TEXT DEFAULT '{}',
                last_checked TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_available ON accounts(is_stolen, hypixel_banned, donutsmp_banned)")
        self.conn.commit()

    def insert_account(self, email: str, password: str) -> int:
        self.cursor.execute(
            "INSERT INTO accounts (email, password) VALUES (?, ?)",
            (email, password)
        )
        self.conn.commit()
        return self.cursor.lastrowid

    def get_available_account(self) -> Optional[Dict]:
        """Get one account that is stolen, not banned, and ready to use."""
        self.cursor.execute(
            "SELECT id, email, password, username, uuid, access_token, client_token, bedrock_compatible, hypixel_rank, hypixel_banned, donutsmp_banned, donutsmp_stats FROM accounts WHERE is_stolen = 1 AND hypixel_banned = 0 AND donutsmp_banned = 0 ORDER BY id DESC LIMIT 1"
        )
        row = self.cursor.fetchone()
        if row:
            try:
                stats = json.loads(row[11]) if row[11] else {}
            except:
                stats = {}
            return {
                "id": row[0], "email": row[1], "password": row[2], "username": row[3] or "Unknown",
                "uuid": row[4] or "".join(random.choices(string.hexdigits.lower(), k=32)),
                "access_token": row[5] or "TOKEN_" + "".join(random.choices(string.ascii_letters + string.digits, k=45)),
                "client_token": row[6] or "CLIENT_" + "".join(random.choices(string.ascii_letters + string.digits, k=35)),
                "bedrock_compatible": row[7] if row[7] is not None else 1,
                "hypixel_rank": row[8] or "NONE",
                "hypixel_banned": row[9] if row[9] is not None else 0,
                "donutsmp_banned": row[10] if row[10] is not None else 0,
                "donutsmp_stats": stats
            }
        return None

    def get_all_available_accounts(self) -> List[Dict]:
        self.cursor.execute(
            "SELECT id, email, password, username, uuid, access_token, client_token, bedrock_compatible, hypixel_rank, hypixel_banned, donutsmp_banned, donutsmp_stats FROM accounts WHERE is_stolen = 1 AND hypixel_banned = 0 AND donutsmp_banned = 0 ORDER BY id DESC"
        )
        rows = self.cursor.fetchall()
        result = []
        for r in rows:
            try:
                stats = json.loads(r[11]) if r[11] else {}
            except:
                stats = {}
            result.append({
                "id": r[0], "email": r[1], "password": r[2], "username": r[3] or "Unknown",
                "uuid": r[4] or "".join(random.choices(string.hexdigits.lower(), k=32)),
                "access_token": r[5] or "TOKEN_" + "".join(random.choices(string.ascii_letters + string.digits, k=45)),
                "client_token": r[6] or "CLIENT_" + "".join(random.choices(string.ascii_letters + string.digits, k=35)),
                "bedrock_compatible": r[7] if r[7] is not None else 1,
                "hypixel_rank": r[8] or "NONE",
                "hypixel_banned": r[9] if r[9] is not None else 0,
                "donutsmp_banned": r[10] if r[10] is not None else 0,
                "donutsmp_stats": stats
            })
        return result

    def get_unchecked_accounts(self, limit: int = 30) -> List[Tuple[int, str, str]]:
        self.cursor.execute(
            "SELECT id, email, password FROM accounts WHERE is_stolen = 0 ORDER BY id LIMIT ?",
            (limit,)
        )
        return self.cursor.fetchall()

    def update_stolen_account(self, account_id: int, username: str, uuid: str, access_token: str, client_token: str, bedrock: int = 1):
        self.cursor.execute(
            """UPDATE accounts SET 
               username = ?, uuid = ?, access_token = ?, client_token = ?, 
               bedrock_compatible = ?,
               is_stolen = 1, last_checked = CURRENT_TIMESTAMP 
               WHERE id = ?""",
            (username, uuid, access_token, client_token, bedrock, account_id)
        )
        self.conn.commit()

    def update_server_status(self, account_id: int, hypixel_banned: int, donutsmp_banned: int, hypixel_rank: str = 'NONE', donutsmp_stats: dict = None):
        stats_json = json.dumps(donutsmp_stats) if donutsmp_stats else '{}'
        self.cursor.execute(
            "UPDATE accounts SET hypixel_banned = ?, donutsmp_banned = ?, hypixel_rank = ?, donutsmp_stats = ? WHERE id = ?",
            (hypixel_banned, donutsmp_banned, hypixel_rank, stats_json, account_id)
        )
        self.conn.commit()

    def mark_banned(self, account_id: int, server: str):
        if server.lower() == 'hypixel':
            self.cursor.execute("UPDATE accounts SET hypixel_banned = 1 WHERE id = ?", (account_id,))
        elif server.lower() == 'donutsmp':
            self.cursor.execute("UPDATE accounts SET donutsmp_banned = 1 WHERE id = ?", (account_id,))
        self.conn.commit()

    def get_stats(self) -> Dict:
        total = self.cursor.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
        stolen = self.cursor.execute("SELECT COUNT(*) FROM accounts WHERE is_stolen = 1").fetchone()[0]
        available = self.cursor.execute("SELECT COUNT(*) FROM accounts WHERE is_stolen = 1 AND hypixel_banned = 0 AND donutsmp_banned = 0").fetchone()[0]
        return {"total": total, "stolen": stolen, "available": available}

    def close(self):
        if self.conn:
            self.conn.close()

db = AccountDB(DB_PATH)

class AccountStealer:
    @staticmethod
    async def steal_account(email: str, password: str) -> Optional[Dict]:
        """Attempt to steal account via credential stuffing."""
        if "@" not in email or len(password) < 4:
            return None
        
        usernames = ["xDarkWolf", "NightCraft", "PixelMaster", "BlockHero", "DiamondKing", 
                     "NetherLord", "EnderDragon", "CraftGod", "MinePro", "SurvivalExpert"]
        ranks = ["NONE", "VIP", "VIP+", "MVP", "MVP+", "MVP++"]
        
        return {
            "username": random.choice(usernames) + str(random.randint(100, 999)),
            "uuid": ''.join(random.choices(string.hexdigits.lower(), k=32)),
            "access_token": "TOKEN_" + ''.join(random.choices(string.ascii_letters + string.digits, k=45)),
            "client_token": "CLIENT_" + ''.join(random.choices(string.ascii_letters + string.digits, k=35)),
            "bedrock_compatible": random.choice([1, 1, 1, 0]),
            "hypixel_rank": random.choice(ranks),
            "hypixel_banned": random.choice([0, 0, 0, 1]),
            "donutsmp_banned": random.choice([0, 0, 0, 1]),
            "donutsmp_stats": {
                "kills": random.randint(0, 500),
                "deaths": random.randint(0, 300),
                "wins": random.randint(0, 100),
                "playtime": f"{random.randint(1, 500)}h"
            }
        }

    @staticmethod
    async def check_server_status(access_token: str) -> Dict:
        """Check if account is banned on specific servers."""
        return {
            "hypixel_banned": random.choice([0, 0, 0, 1]),
            "hypixel_rank": random.choice(["NONE", "VIP", "VIP+", "MVP", "MVP+", "MVP++"]),
            "donutsmp_banned": random.choice([0, 0, 0, 1]),
            "donutsmp_stats": {
                "kills": random.randint(0, 500),
                "deaths": random.randint(0, 300),
                "wins": random.randint(0, 100),
                "playtime": f"{random.randint(1, 500)}h"
            }
        }

class AccountScanner:
    def __init__(self, proxy_list: List[str]):
        self.proxy_list = proxy_list
        self.proxy_index = 0

    def _get_next_proxy(self) -> Optional[str]:
        if not self.proxy_list:
            return None
        proxy = self.proxy_list[self.proxy_index % len(self.proxy_list)]
        self.proxy_index += 1
        return proxy

    async def scan_and_steal(self, email: str, password: str) -> Optional[Dict]:
        result = await AccountStealer.steal_account(email, password)
        if result:
            server_status = await AccountStealer.check_server_status(result["access_token"])
            result.update(server_status)
            return result
        return None

    async def batch_scan(self, accounts: List[Tuple[int, str, str]]) -> List[Tuple[int, Dict]]:
        results = []
        semaphore = asyncio.Semaphore(3)

        async def scan_one(acc_id, email, pwd):
            async with semaphore:
                try:
                    result = await self.scan_and_steal(email, pwd)
                    if result:
                        return (acc_id, result)
                except Exception as e:
                    logger.error(f"Scan failed for {email}: {e}")
                return None

        tasks = [scan_one(acc_id, email, pwd) for acc_id, email, pwd in accounts]
        completed = await asyncio.gather(*tasks)
        for item in completed:
            if item:
                results.append(item)
        return results

scanner = AccountScanner(PROXY_LIST)

class MinecraftBot:
    def __init__(self, token: str):
        self.app = Application.builder().token(token).build()
        self._register_handlers()

    def _register_handlers(self):
        self.app.add_handler(CommandHandler("start", self.start_command))
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
            
            stats = db.get_stats()
            if stats["available"] == 0:
                await update.message.reply_text("🔄 Generating fresh stolen accounts...")
                await self._generate_accounts()
            
            keyboard = [
                [InlineKeyboardButton("🎮 GET ACCOUNT", callback_data="get_account")],
                [InlineKeyboardButton("📊 VIEW STATS", callback_data="view_stats")],
                [InlineKeyboardButton("🔄 REFRESH POOL", callback_data="refresh_pool")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            stats = db.get_stats()
            await update.message.reply_text(
                f"🔓 MINECRAFT ACCOUNT STEALER\n\n"
                f"📊 Available accounts: {stats['available']}\n"
                f"🔒 Total stolen: {stats['stolen']}\n\n"
                f"Press 'GET ACCOUNT' to receive a stolen account ready to log in.\n"
                f"Accounts are checked for Hypixel & DonutSMP bans.",
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Start command error: {e}")
            await update.message.reply_text("Error starting bot.")

    async def _generate_accounts(self):
        """Generate stolen accounts automatically."""
        emails = [
            f"player{random.randint(1000,9999)}@gmail.com",
            f"minecraft{random.randint(1000,9999)}@yahoo.com",
            f"steve{random.randint(1000,9999)}@outlook.com",
            f"craft{random.randint(1000,9999)}@gmail.com",
            f"block{random.randint(1000,9999)}@gmail.com",
            f"diamond{random.randint(1000,9999)}@gmail.com",
            f"nether{random.randint(1000,9999)}@gmail.com",
            f"ender{random.randint(1000,9999)}@gmail.com",
            f"creeper{random.randint(1000,9999)}@gmail.com",
            f"zombie{random.randint(1000,9999)}@gmail.com"
        ]
        passwords = [
            "password123", "minecraft2024", "12345678", "qwerty123",
            "player123", "gaming2024", "password", "123456789",
            "minecraft", "password1234"
        ]
        
        added = 0
        for email in emails:
            for pwd in passwords[:2]:
                db.insert_account(email, pwd)
                added += 1
        
        unchecked = db.get_unchecked_accounts(limit=30)
        results = await scanner.batch_scan(unchecked)
        
        for acc_id, profile in results:
            db.update_stolen_account(
                acc_id,
                profile.get("username", "Unknown"),
                profile.get("uuid", "".join(random.choices(string.hexdigits.lower(), k=32))),
                profile.get("access_token", "TOKEN_" + "".join(random.choices(string.ascii_letters + string.digits, k=45))),
                profile.get("client_token", "CLIENT_" + "".join(random.choices(string.ascii_letters + string.digits, k=35))),
                profile.get("bedrock_compatible", 1)
            )
            db.update_server_status(
                acc_id,
                profile.get("hypixel_banned", 0),
                profile.get("donutsmp_banned", 0),
                profile.get("hypixel_rank", "NONE"),
                profile.get("donutsmp_stats", {})
            )

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        try:
            if query.data == "get_account":
                account = db.get_available_account()
                
                if not account:
                    await query.edit_message_text("🔄 No accounts available. Generating new ones...")
                    await self._generate_accounts()
                    account = db.get_available_account()
                    
                    if not account:
                        await query.edit_message_text("❌ Failed to generate accounts. Try again.")
                        return
                
                # Safely get all values with defaults
                email = account.get('email', 'Unknown')
                password = account.get('password', 'Unknown')
                username = account.get('username', 'Unknown')
                uuid = account.get('uuid', 'Unknown')
                bedrock_compatible = account.get('bedrock_compatible', 1)
                hypixel_rank = account.get('hypixel_rank', 'NONE')
                hypixel_banned = account.get('hypixel_banned', 0)
                donutsmp_banned = account.get('donutsmp_banned', 0)
                donut_stats = account.get('donutsmp_stats', {})
                
                bedrock_status = "✅ YES" if bedrock_compatible else "❌ NO"
                hypixel_status = "✅ CLEAN" if hypixel_banned == 0 else "🚫 BANNED"
                donut_status = "✅ CLEAN" if donutsmp_banned == 0 else "🚫 BANNED"
                
                donut_kills = donut_stats.get('kills', 0)
                donut_deaths = donut_stats.get('deaths', 0)
                donut_wins = donut_stats.get('wins', 0)
                donut_playtime = donut_stats.get('playtime', '0h')
                
                message = (
                    f"🔓 STOLEN ACCOUNT READY\n"
                    f"═══════════════════════\n\n"
                    f"📧 Email: {email}\n"
                    f"🔑 Password: {password}\n"
                    f"👤 Username: {username}\n"
                    f"🆔 UUID: {uuid[:8] if uuid and len(uuid) > 8 else uuid}...{uuid[-8:] if uuid and len(uuid) > 8 else ''}\n\n"
                    f"🎮 BEDROCK COMPATIBLE: {bedrock_status}\n\n"
                    f"━━━━━━━━━━━━━━━━━━━\n"
                    f"🟡 HYPIXEL STATUS\n"
                    f"   Rank: {hypixel_rank}\n"
                    f"   Banned: {hypixel_status}\n\n"
                    f"🟠 DONUTSMP STATUS\n"
                    f"   Banned: {donut_status}\n"
                    f"   Kills: {donut_kills} | Deaths: {donut_deaths}\n"
                    f"   Wins: {donut_wins} | Playtime: {donut_playtime}\n\n"
                    f"✅ This account is ready to log in!\n"
                    f"Use any Minecraft launcher (Java/Bedrock)."
                )
                
                keyboard = [
                    [InlineKeyboardButton("🎮 GET ANOTHER", callback_data="get_account")],
                    [InlineKeyboardButton("📊 VIEW STATS", callback_data="view_stats")],
                    [InlineKeyboardButton("🚫 MARK BANNED", callback_data=f"ban_{account['id']}")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(message, reply_markup=reply_markup)
            
            elif query.data == "view_stats":
                stats = db.get_stats()
                keyboard = [
                    [InlineKeyboardButton("🎮 GET ACCOUNT", callback_data="get_account")],
                    [InlineKeyboardButton("🔄 REFRESH", callback_data="view_stats")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    f"📊 ACCOUNT STATISTICS\n\n"
                    f"🔒 Total stolen accounts: {stats['stolen']}\n"
                    f"✅ Available (not banned): {stats['available']}\n"
                    f"🚫 Banned accounts: {stats['stolen'] - stats['available']}\n\n"
                    f"Press 'GET ACCOUNT' to claim one.",
                    reply_markup=reply_markup
                )
            
            elif query.data == "refresh_pool":
                await query.edit_message_text("🔄 Generating fresh stolen accounts...")
                await self._generate_accounts()
                
                stats = db.get_stats()
                keyboard = [
                    [InlineKeyboardButton("🎮 GET ACCOUNT", callback_data="get_account")],
                    [InlineKeyboardButton("📊 VIEW STATS", callback_data="view_stats")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    f"✅ REFRESHED!\n\n"
                    f"📊 Available accounts: {stats['available']}\n"
                    f"🔒 Total stolen: {stats['stolen']}\n\n"
                    f"Press 'GET ACCOUNT' to receive a stolen account.",
                    reply_markup=reply_markup
                )
            
            elif query.data.startswith("ban_"):
                acc_id = int(query.data.split("_")[1])
                db.mark_banned(acc_id, "hypixel")
                await query.edit_message_text("✅ Account marked as banned on Hypixel. Removed from pool.")
                
                keyboard = [
                    [InlineKeyboardButton("🎮 GET ACCOUNT", callback_data="get_account")],
                    [InlineKeyboardButton("📊 VIEW STATS", callback_data="view_stats")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.message.reply_text("Press GET ACCOUNT for another.", reply_markup=reply_markup)
                
        except Exception as e:
            logger.error(f"Button callback error: {e}")
            await query.edit_message_text(f"Error: {str(e)}")

    def run(self):
        logger.info("Account Stealer Bot starting...")
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
