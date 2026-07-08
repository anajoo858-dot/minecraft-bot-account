import os
import sys
import json
import sqlite3
import asyncio
import logging
import random
import re
from typing import Dict, List, Optional
from datetime import datetime
import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
AUTHORIZED_USERS = [int(x) for x in os.environ.get("AUTHORIZED_USERS", "").split(",") if x]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Account list from your friend
ACCOUNT_DATA = [
    {"email": "leonyhoki@hotmail.com", "password": "leony123"},
    {"email": "manuesper@hotmail.com", "password": "Novalee1971"},
    {"email": "kudaygs35@hotmail.com", "password": "kuday_35"},
    {"email": "r_lee_t@hotmail.com", "password": "Rickie1986"},
    {"email": "juanmoralesmaster@hotmail.com", "password": "Tuhermana1988"},
    {"email": "e_l_gz@hotmail.com", "password": "javier96951"},
    {"email": "sa7ato@hotmail.com", "password": "47P8EURR"},
    {"email": "sadigharoun@hotmail.com", "password": "Sadig9251978"},
    {"email": "danwilliams429@hotmail.com", "password": "Pepsimax429!"},
    {"email": "longjasper.11@hotmail.com", "password": "tanakornmk119"},
    {"email": "henryfh_20@hotmail.com", "password": "Mariajose1975"},
    {"email": "furkansln04@hotmail.com", "password": "joyiko1756"},
    {"email": "anjinho_lucifer@hotmail.com", "password": "Vidaloka9"},
    {"email": "franciane_terra@hotmail.com", "password": "Fran202230*"},
    {"email": "sahil.mughal9@hotmail.com", "password": "6601345"},
    {"email": "escorpio_amor6@hotmail.com", "password": "Manuel1986"},
    {"email": "patrick.lei565@hotmail.com", "password": "h80036565"},
    {"email": "rukawakaede_0103@hotmail.com", "password": "5417rukawa"},
    {"email": "mottacontato@hotmail.com", "password": "Motta0066"},
    {"email": "calelmorales@hotmail.com", "password": "calelmo"},
    {"email": "alistars747@hotmail.com", "password": "24039296"},
    {"email": "rawrxtedvlpvgx@hotmail.com", "password": "Penguinsarecool3!"},
    {"email": "gervais2002@hotmail.com", "password": "Gervais1"},
    {"email": "leehogan43@hotmail.com", "password": "ice-cream1"},
    {"email": "usmanghani2001@hotmail.com", "password": "usman2001"},
    {"email": "eimyqiuliu@hotmail.com", "password": "eimyqiu19"},
    {"email": "elhosini20109@hotmail.com", "password": "mido4484115"},
    {"email": "wilderyoni125@hotmail.com", "password": "wilder125"},
    {"email": "aguiguitant@hotmail.com", "password": "ironman82"},
    {"email": "rysa_r@live.jp", "password": "aaii0017"},
    {"email": "momo-556677@hotmail.co.jp", "password": "momo0620"},
    {"email": "juan_m_m_amer@hotmail.com", "password": "america2005"},
    {"email": "dan.khatskevich@hotmail.com", "password": "Werthv2y!!"},
    {"email": "vivikao0410@hotmail.com", "password": "Vivi0703"},
    {"email": "mfernac@hotmail.com", "password": "22642264"},
    {"email": "alvaro.pisciotti@hotmail.com", "password": "america1015"},
    {"email": "killaman20@outlook.kr", "password": "killa558202$"},
    {"email": "jeshualejandro2004@hotmail.com", "password": "jeshua2004"},
    {"email": "orionokuriyama@hotmail.co.jp", "password": "Oriono1977"},
    {"email": "lorenzomiopalmo@hotmail.fr", "password": "miopalmo"},
    {"email": "akvileudraite@hotmail.com", "password": "13072426889akv"},
    {"email": "johana_ruiz11@outlook.es", "password": "johanaruiz11"},
    {"email": "vesna_rizman@hotmail.com", "password": "CAPUCINO1986"},
    {"email": "ercan.oztunc@hotmail.com", "password": "05457758659Ee"},
    {"email": "couillard06@hotmail.com", "password": "Numero06"},
    {"email": "rmudiatmoko12@hotmail.com", "password": "rm121177"},
    {"email": "lles34@hotmail.fr", "password": "confort34"},
    {"email": "julnim@hotmail.com", "password": "Tennisman2001"},
    {"email": "foodza201055@hotmail.com", "password": "0865497427"},
    {"email": "thewindhill@hotmail.com", "password": "Nevermind1979"},
    {"email": "gal3090@hotmail.com", "password": "Gg311130496"},
    {"email": "hunir1@hotmail.com", "password": "Aventur1972"},
    {"email": "jaime_1987@live.com", "password": "Paternero3"},
    {"email": "andrewturcot@outlook.com", "password": "Turc7otaa!!"},
    {"email": "fatjonsejdiu@hotmail.com", "password": "fatjon2003"},
    {"email": "fordnavigation@hotmail.com", "password": "Kvolan1976"},
    {"email": "propeagronomia@hotmail.com", "password": "agronomia"},
    {"email": "luzemilya@hotmail.com", "password": "Paloma2001"},
    {"email": "mohmedg53@hotmail.com", "password": "Mm6172660-"},
    {"email": "chicalinha@hotmail.com", "password": "Santotirso1976"},
    {"email": "aurelios.santos@hotmail.com", "password": "aurelio30"},
    {"email": "masiulaniec2@hotmail.com", "password": "Janusz1965!!"},
    {"email": "goldamyer@hotmail.com", "password": "Mae1filha2"},
    {"email": "forfang3171@hotmail.com", "password": "fang3171"},
    {"email": "lesly.rodriguez666@hotmail.com", "password": "Perezelder1988"},
    {"email": "maharsh.desai@hotmail.com", "password": "maharsh123"},
    {"email": "andymeurisse@hotmail.com", "password": "Refinej19"},
    {"email": "gomes.5@hotmail.ch", "password": "HHello1971"},
    {"email": "cesarfilipe_pc@hotmail.fr", "password": "cesar123"},
    {"email": "unangeloinjeans@hotmail.it", "password": "Afrodite1977"},
    {"email": "dimitris-nikolas10@hotmail.com", "password": "Vothinoi26!"},
    {"email": "jassna21@hotmail.com", "password": "jassna123"},
    {"email": "happy_-_hippo@hotmail.com", "password": "Lollies1"},
    {"email": "daddy-fox3311@outlook.jp", "password": "daddy3311"},
    {"email": "dirkherrig@hotmail.de", "password": "Dillinger1978"},
    {"email": "morenosuprapto@hotmail.com", "password": "moreno12"},
    {"email": "gomera_19@hotmail.com", "password": "Gomera1986"},
    {"email": "ginyeoh@hotmail.com", "password": "ylk901208"},
    {"email": "ugrt61@hotmail.com", "password": "9710389u"},
    {"email": "friesenjung79@hotmail.de", "password": "friese79"},
    {"email": "edigleisonedfisica_@hotmail.com", "password": "ed10101708"},
    {"email": "jalen2030@hotmail.com", "password": "F9200351"},
    {"email": "steph.valerie@hotmail.com", "password": "Valerie1970"},
    {"email": "laim2010@hotmail.com", "password": "Alizee1983"},
    {"email": "naif.hhh@hotmail.com", "password": "Nn123789"},
    {"email": "rodriguezmp_@hotmail.com", "password": "Torero1983"},
    {"email": "alejandro_maretto@hotmail.com", "password": "Alejandromaretto"},
    {"email": "ecushop_present@hotmail.com", "password": "ECUshop2019"},
    {"email": "lechiarmero@hotmail.com", "password": "lechi910019"},
    {"email": "staratel312@outlook.com", "password": "JapV6QXy"},
    {"email": "sarahdurran@hotmail.com", "password": "Joshie1982"},
    {"email": "roapinchacapo@hotmail.com", "password": "pichon01"},
    {"email": "dedelilly43@outlook.com", "password": "DW276301!!"},
    {"email": "wendyannmjohnson@hotmail.com", "password": "Wendyj123!!!"},
    {"email": "aksakal.korkmaz@hotmail.com", "password": "aksakal12"},
    {"email": "emineyasarela@hotmail.com", "password": "Elam3642"},
    {"email": "muhammadjunaid09@hotmail.com", "password": "Junaid.09"},
    {"email": "crikron@hotmail.com", "password": "Cipote1984"},
    {"email": "nayeva971@hotmail.com", "password": "nayeva14"},
    {"email": "susy_20@hotmail.cl", "password": "isagu2616"},
    {"email": "francyvisconti@hotmail.it", "password": "francy20"},
    {"email": "paquysan@hotmail.com", "password": "Laaldeana1972"},
    {"email": "karim.rouichi@hotmail.com", "password": "KarimSheima2203"},
    {"email": "hami.chamse@hotmail.com", "password": "hami11685116"},
    {"email": "flornflakes@hotmail.com", "password": "Lottie1989"},
    {"email": "danilo_gt_2@hotmail.com", "password": "182712329"},
    {"email": "doumeum@hotmail.com", "password": "836370392m"},
    {"email": "gamerd3@hotmail.com", "password": "gamer123"},
    {"email": "zuanny12_@hotmail.es", "password": "130779290"},
    {"email": "elyjuniow@hotmail.com", "password": "ely6303056"},
    {"email": "f7359@hotmail.com", "password": "01HIGHT1005"},
    {"email": "marcovca0005@hotmail.com", "password": "marc437430"},
    {"email": "otaku972@hotmail.com", "password": "lea97230"},
    {"email": "done2323@hotmail.com", "password": "Noramdff1"},
    {"email": "vane20_03@hotmail.com", "password": "Gaditana1980"},
    {"email": "naifghost@hotmail.com", "password": "Aa0560633868"},
    {"email": "jnteli@hotmail.com", "password": "Trustno1983"},
    {"email": "gala_27_92@hotmail.com", "password": "Pistoleras2en1."},
    {"email": "imxarsalan@outlook.com", "password": "imx03048155008"},
    {"email": "alexia20leal@hotmail.com", "password": "alexia2005"},
    {"email": "davletova.meerim@hotmail.com", "password": "Davletova123"},
    {"email": "yulicarolina93@hotmail.com", "password": "Samuel270515"},
    {"email": "leelinkheng@hotmail.com", "password": "lOveglitz2"},
    {"email": "canakanj@hotmail.com", "password": "canakan15"},
    {"email": "rraltuve@hotmail.com", "password": "altuve10712955"},
    {"email": "mironenkorn@live.com", "password": "Miron4ik22"},
    {"email": "deryayazan@hotmail.com", "password": "Ddostluk1982"},
    {"email": "suarn1967@hotmail.co.uk", "password": "Lucylucy945!"},
    {"email": "eliatrousia@hotmail.com", "password": "19171956"},
    {"email": "lizzykwart4500@hotmail.com", "password": "Soyass4500"},
    {"email": "vesnatodorovska@live.com", "password": "vesna123"},
    {"email": "pspslim.alex@hotmail.com", "password": "psp45665478"},
    {"email": "markandujar7@hotmail.com", "password": "101792Mark"}
]

class AccountDB:
    def __init__(self):
        self.conn = sqlite3.connect("accounts.db", check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._init_db()
        self._load_accounts()

    def _init_db(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                password TEXT NOT NULL,
                username TEXT,
                hypixel_status TEXT DEFAULT 'unknown',
                hypixel_rank TEXT DEFAULT 'NONE',
                hypixel_banned INTEGER DEFAULT 0,
                donutsmp_status TEXT DEFAULT 'unknown',
                donutsmp_banned INTEGER DEFAULT 0,
                donutsmp_kills INTEGER DEFAULT 0,
                donutsmp_deaths INTEGER DEFAULT 0,
                cubecraft_status TEXT DEFAULT 'unknown',
                cubecraft_banned INTEGER DEFAULT 0,
                cubecraft_rank TEXT DEFAULT 'NONE',
                bedrock_owned INTEGER DEFAULT 0,
                claimed_by INTEGER DEFAULT 0,
                claimed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_claimed ON accounts(claimed_by)")
        self.conn.commit()

    def _load_accounts(self):
        self.cursor.execute("SELECT COUNT(*) FROM accounts")
        count = self.cursor.fetchone()[0]
        
        if count == 0:
            for acc in ACCOUNT_DATA:
                self.cursor.execute(
                    "INSERT INTO accounts (email, password, username) VALUES (?, ?, ?)",
                    (acc["email"], acc["password"], f"Player_{random.randint(1000, 9999)}")
                )
            self.conn.commit()
            logger.info(f"Loaded {len(ACCOUNT_DATA)} accounts into database")

    def get_available_count(self) -> int:
        self.cursor.execute("SELECT COUNT(*) FROM accounts WHERE claimed_by = 0")
        return self.cursor.fetchone()[0]

    def get_claimed_count(self) -> int:
        self.cursor.execute("SELECT COUNT(*) FROM accounts WHERE claimed_by != 0")
        return self.cursor.fetchone()[0]

    def get_total_count(self) -> int:
        self.cursor.execute("SELECT COUNT(*) FROM accounts")
        return self.cursor.fetchone()[0]

    def get_available_account(self) -> Optional[Dict]:
        self.cursor.execute("""
            SELECT id, email, password, username, 
                   hypixel_status, hypixel_rank, hypixel_banned,
                   donutsmp_status, donutsmp_banned, donutsmp_kills, donutsmp_deaths,
                   cubecraft_status, cubecraft_banned, cubecraft_rank,
                   bedrock_owned
            FROM accounts WHERE claimed_by = 0 LIMIT 1
        """)
        row = self.cursor.fetchone()
        if row:
            return {
                "id": row[0],
                "email": row[1],
                "password": row[2],
                "username": row[3] or "Unknown",
                "hypixel_status": row[4] or "unknown",
                "hypixel_rank": row[5] or "NONE",
                "hypixel_banned": row[6] or 0,
                "donutsmp_status": row[7] or "unknown",
                "donutsmp_banned": row[8] or 0,
                "donutsmp_kills": row[9] or 0,
                "donutsmp_deaths": row[10] or 0,
                "cubecraft_status": row[11] or "unknown",
                "cubecraft_banned": row[12] or 0,
                "cubecraft_rank": row[13] or "NONE",
                "bedrock_owned": row[14] or 0
            }
        return None

    def get_account_by_user(self, user_id: int) -> Optional[Dict]:
        self.cursor.execute("""
            SELECT id, email, password, username, 
                   hypixel_status, hypixel_rank, hypixel_banned,
                   donutsmp_status, donutsmp_banned, donutsmp_kills, donutsmp_deaths,
                   cubecraft_status, cubecraft_banned, cubecraft_rank,
                   bedrock_owned
            FROM accounts WHERE claimed_by = ?
        """, (user_id,))
        row = self.cursor.fetchone()
        if row:
            return {
                "id": row[0],
                "email": row[1],
                "password": row[2],
                "username": row[3] or "Unknown",
                "hypixel_status": row[4] or "unknown",
                "hypixel_rank": row[5] or "NONE",
                "hypixel_banned": row[6] or 0,
                "donutsmp_status": row[7] or "unknown",
                "donutsmp_banned": row[8] or 0,
                "donutsmp_kills": row[9] or 0,
                "donutsmp_deaths": row[10] or 0,
                "cubecraft_status": row[11] or "unknown",
                "cubecraft_banned": row[12] or 0,
                "cubecraft_rank": row[13] or "NONE",
                "bedrock_owned": row[14] or 0
            }
        return None

    def claim_account(self, account_id: int, user_id: int):
        self.cursor.execute(
            "UPDATE accounts SET claimed_by = ?, claimed_at = CURRENT_TIMESTAMP WHERE id = ?",
            (user_id, account_id)
        )
        self.conn.commit()

    def release_account(self, account_id: int):
        self.cursor.execute(
            "UPDATE accounts SET claimed_by = 0, claimed_at = NULL WHERE id = ?",
            (account_id,)
        )
        self.conn.commit()

    def update_server_status(self, account_id: int, data: Dict):
        self.cursor.execute("""
            UPDATE accounts SET 
                hypixel_status = ?, hypixel_rank = ?, hypixel_banned = ?,
                donutsmp_status = ?, donutsmp_banned = ?, donutsmp_kills = ?, donutsmp_deaths = ?,
                cubecraft_status = ?, cubecraft_banned = ?, cubecraft_rank = ?,
                bedrock_owned = ?
            WHERE id = ?
        """, (
            data.get("hypixel_status", "unknown"),
            data.get("hypixel_rank", "NONE"),
            data.get("hypixel_banned", 0),
            data.get("donutsmp_status", "unknown"),
            data.get("donutsmp_banned", 0),
            data.get("donutsmp_kills", 0),
            data.get("donutsmp_deaths", 0),
            data.get("cubecraft_status", "unknown"),
            data.get("cubecraft_banned", 0),
            data.get("cubecraft_rank", "NONE"),
            data.get("bedrock_owned", 0),
            account_id
        ))
        self.conn.commit()

    def get_stats(self) -> Dict:
        return {
            "total": self.get_total_count(),
            "available": self.get_available_count(),
            "claimed": self.get_claimed_count()
        }

db = AccountDB()

class ServerChecker:
    @staticmethod
    async def check_all(email: str, password: str) -> Dict:
        """Simulate checking all servers and bedrock ownership."""
        # Simulated statuses - in production would use actual APIs
        statuses = ["online", "offline", "unknown"]
        ranks = ["NONE", "VIP", "VIP+", "MVP", "MVP+", "MVP++"]
        cubecraft_ranks = ["NONE", "IRON", "GOLD", "DIAMOND", "EMERALD", "OBSIDIAN"]
        
        return {
            "hypixel_status": random.choice(statuses),
            "hypixel_rank": random.choice(ranks),
            "hypixel_banned": 1 if random.random() < 0.25 else 0,
            "donutsmp_status": random.choice(statuses),
            "donutsmp_banned": 1 if random.random() < 0.2 else 0,
            "donutsmp_kills": random.randint(0, 500),
            "donutsmp_deaths": random.randint(0, 300),
            "cubecraft_status": random.choice(statuses),
            "cubecraft_banned": 1 if random.random() < 0.15 else 0,
            "cubecraft_rank": random.choice(cubecraft_ranks),
            "bedrock_owned": 1 if random.random() < 0.4 else 0
        }

class MinecraftBot:
    def __init__(self, token: str):
        self.app = Application.builder().token(token).build()
        self._register_handlers()

    def _register_handlers(self):
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("myaccount", self.myaccount_command))
        self.app.add_handler(CommandHandler("release", self.release_command))
        self.app.add_handler(CommandHandler("stats", self.stats_command))
        self.app.add_handler(CallbackQueryHandler(self.button_callback))

    async def _check_auth(self, update: Update) -> bool:
        if not AUTHORIZED_USERS:
            return True
        if update.effective_user.id not in AUTHORIZED_USERS:
            await update.message.reply_text("❌ Unauthorized.")
            return False
        return True

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        
        stats = db.get_stats()
        
        keyboard = [
            [InlineKeyboardButton("🎮 GET ACCOUNT", callback_data="get_account")],
            [InlineKeyboardButton("📊 VIEW STATS", callback_data="view_stats")],
            [InlineKeyboardButton("📋 MY ACCOUNT", callback_data="myaccount")],
            [InlineKeyboardButton("🔄 REFRESH STATUS", callback_data="refresh_status")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"🔓 MINECRAFT ACCOUNT STOCK\n"
            f"═══════════════════════════\n\n"
            f"📦 Total accounts: {stats['total']}\n"
            f"✅ Available: {stats['available']}\n"
            f"🔒 Claimed: {stats['claimed']}\n\n"
            f"Click 'GET ACCOUNT' to claim one.\n"
            f"Each account is unique and claimed only by you.\n\n"
            f"📌 Shows:\n"
            f"• Hypixel Status & Rank\n"
            f"• DonutSMP Status & Stats\n"
            f"• Cubecraft Status & Rank\n"
            f"• Bedrock Edition Ownership",
            reply_markup=reply_markup
        )

    async def myaccount_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        
        account = db.get_account_by_user(update.effective_user.id)
        
        if not account:
            await update.message.reply_text(
                "❌ You don't have any account claimed.\n"
                "Use /start and click 'GET ACCOUNT'."
            )
            return
        
        await self._display_account(update, account)

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        
        stats = db.get_stats()
        await update.message.reply_text(
            f"📊 ACCOUNT STATISTICS\n"
            f"═══════════════════════════\n\n"
            f"📦 Total accounts: {stats['total']}\n"
            f"✅ Available: {stats['available']}\n"
            f"🔒 Claimed: {stats['claimed']}\n"
        )

    async def release_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        
        account = db.get_account_by_user(update.effective_user.id)
        
        if not account:
            await update.message.reply_text("❌ You don't have any account to release.")
            return
        
        db.release_account(account["id"])
        await update.message.reply_text(
            f"✅ Released account {account['email']} back to stock.\n"
            f"Use /start to get another."
        )

    async def _display_account(self, update: Update, account: Dict):
        hypixel_status_emoji = "🟢" if account["hypixel_status"] == "online" else "🔴" if account["hypixel_status"] == "offline" else "⚪"
        donut_status_emoji = "🟢" if account["donutsmp_status"] == "online" else "🔴" if account["donutsmp_status"] == "offline" else "⚪"
        cubecraft_status_emoji = "🟢" if account["cubecraft_status"] == "online" else "🔴" if account["cubecraft_status"] == "offline" else "⚪"
        
        bedrock_emoji = "✅ YES" if account["bedrock_owned"] else "❌ NO"
        
        message = (
            f"📋 YOUR ACCOUNT\n"
            f"═══════════════════════════\n\n"
            f"📧 Email: {account['email']}\n"
            f"🔑 Password: {account['password']}\n"
            f"👤 Username: {account['username']}\n\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🟡 HYPIXEL\n"
            f"   Status: {hypixel_status_emoji} {account['hypixel_status']}\n"
            f"   Rank: {account['hypixel_rank']}\n"
            f"   Banned: {'✅ YES' if account['hypixel_banned'] else '❌ NO'}\n\n"
            f"🟠 DONUTSMP\n"
            f"   Status: {donut_status_emoji} {account['donutsmp_status']}\n"
            f"   Banned: {'✅ YES' if account['donutsmp_banned'] else '❌ NO'}\n"
            f"   Kills: {account['donutsmp_kills']} | Deaths: {account['donutsmp_deaths']}\n\n"
            f"🟢 CUBECRAFT\n"
            f"   Status: {cubecraft_status_emoji} {account['cubecraft_status']}\n"
            f"   Rank: {account['cubecraft_rank']}\n"
            f"   Banned: {'✅ YES' if account['cubecraft_banned'] else '❌ NO'}\n\n"
            f"🎮 BEDROCK EDITION\n"
            f"   Owned: {bedrock_emoji}\n"
        )
        
        keyboard = [
            [InlineKeyboardButton("🔄 REFRESH STATUS", callback_data=f"refresh_{account['id']}")],
            [InlineKeyboardButton("📊 VIEW STATS", callback_data="view_stats")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if isinstance(update, Update) and update.message:
            await update.message.reply_text(message, reply_markup=reply_markup)
        else:
            # For callback queries
            await update.effective_message.edit_text(message, reply_markup=reply_markup)

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        try:
            if query.data == "get_account":
                # Check if user already has an account
                existing = db.get_account_by_user(update.effective_user.id)
                if existing:
                    await query.edit_message_text(
                        f"❌ You already have an account claimed!\n\n"
                        f"📧 Email: {existing['email']}\n"
                        f"Use /myaccount to view it.\n"
                        f"Use /release to release it back."
                    )
                    return
                
                account = db.get_available_account()
                
                if not account:
                    await query.edit_message_text(
                        "❌ No accounts available!\n"
                        "All accounts have been claimed."
                    )
                    return
                
                # Check server status (simulated)
                server_data = await ServerChecker.check_all(
                    account["email"], 
                    account["password"]
                )
                
                # Update account with server data
                db.update_server_status(account["id"], server_data)
                account.update(server_data)
                
                # Claim the account
                db.claim_account(account["id"], update.effective_user.id)
                
                # Get updated stats
                stats = db.get_stats()
                
                # Build display message
                hypixel_emoji = "🟢" if account["hypixel_status"] == "online" else "🔴" if account["hypixel_status"] == "offline" else "⚪"
                donut_emoji = "🟢" if account["donutsmp_status"] == "online" else "🔴" if account["donutsmp_status"] == "offline" else "⚪"
                cubecraft_emoji = "🟢" if account["cubecraft_status"] == "online" else "🔴" if account["cubecraft_status"] == "offline" else "⚪"
                bedrock_emoji = "✅ YES" if account["bedrock_owned"] else "❌ NO"
                
                message = (
                    f"🎮 ACCOUNT CLAIMED!\n"
                    f"═══════════════════════════\n\n"
                    f"📧 Email: {account['email']}\n"
                    f"🔑 Password: {account['password']}\n"
                    f"👤 Username: {account['username']}\n\n"
                    f"━━━━━━━━━━━━━━━━━━━\n"
                    f"🟡 HYPIXEL\n"
                    f"   Status: {hypixel_emoji} {account['hypixel_status']}\n"
                    f"   Rank: {account['hypixel_rank']}\n"
                    f"   Banned: {'✅ YES' if account['hypixel_banned'] else '❌ NO'}\n\n"
                    f"🟠 DONUTSMP\n"
                    f"   Status: {donut_emoji} {account['donutsmp_status']}\n"
                    f"   Banned: {'✅ YES' if account['donutsmp_banned'] else '❌ NO'}\n"
                    f"   Kills: {account['donutsmp_kills']} | Deaths: {account['donutsmp_deaths']}\n\n"
                    f"🟢 CUBECRAFT\n"
                    f"   Status: {cubecraft_emoji} {account['cubecraft_status']}\n"
                    f"   Rank: {account['cubecraft_rank']}\n"
                    f"   Banned: {'✅ YES' if account['cubecraft_banned'] else '❌ NO'}\n\n"
                    f"🎮 BEDROCK EDITION\n"
                    f"   Owned: {bedrock_emoji}\n\n"
                    f"📊 Remaining stock: {stats['available']}\n\n"
                    f"✅ This account is YOURS only.\n"
                    f"📌 Use /myaccount to view it anytime.\n"
                    f"📌 Use /release to give it back."
                )
                
                keyboard = [
                    [InlineKeyboardButton("📋 MY ACCOUNT", callback_data="myaccount")],
                    [InlineKeyboardButton("📊 VIEW STATS", callback_data="view_stats")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(message, reply_markup=reply_markup)
            
            elif query.data == "view_stats":
                stats = db.get_stats()
                await query.edit_message_text(
                    f"📊 ACCOUNT STATISTICS\n"
                    f"═══════════════════════════\n\n"
                    f"📦 Total accounts: {stats['total']}\n"
                    f"✅ Available: {stats['available']}\n"
                    f"🔒 Claimed: {stats['claimed']}\n\n"
                    f"📌 Each account can only be claimed once.\n"
                    f"📌 Use /release to return your account."
                )
            
            elif query.data == "myaccount":
                account = db.get_account_by_user(update.effective_user.id)
                
                if not account:
                    await query.edit_message_text(
                        "❌ You don't have any account claimed.\n"
                        "Use /start and click 'GET ACCOUNT'."
                    )
                    return
                
                await self._display_account(query, account)
            
            elif query.data.startswith("refresh_"):
                # Refresh specific account status
                parts = query.data.split("_")
                if len(parts) > 1 and parts[1].isdigit():
                    account_id = int(parts[1])
                    account = db.get_account_by_user(update.effective_user.id)
                    
                    if not account or account["id"] != account_id:
                        await query.edit_message_text("❌ Account not found or not yours.")
                        return
                    
                    await query.edit_message_text("🔄 Refreshing server status...")
                    
                    server_data = await ServerChecker.check_all(
                        account["email"], 
                        account["password"]
                    )
                    
                    db.update_server_status(account_id, server_data)
                    account.update(server_data)
                    
                    await self._display_account(query, account)
                else:
                    # Refresh all statuses for user's account
                    account = db.get_account_by_user(update.effective_user.id)
                    if not account:
                        await query.edit_message_text("❌ No account claimed.")
                        return
                    
                    await query.edit_message_text("🔄 Refreshing server status...")
                    
                    server_data = await ServerChecker.check_all(
                        account["email"], 
                        account["password"]
                    )
                    
                    db.update_server_status(account["id"], server_data)
                    account.update(server_data)
                    
                    await self._display_account(query, account)
            
            elif query.data == "refresh_status":
                account = db.get_account_by_user(update.effective_user.id)
                if not account:
                    await query.edit_message_text("❌ No account claimed.")
                    return
                
                await query.edit_message_text("🔄 Refreshing server status...")
                
                server_data = await ServerChecker.check_all(
                    account["email"], 
                    account["password"]
                )
                
                db.update_server_status(account["id"], server_data)
                account.update(server_data)
                
                await self._display_account(query, account)
                
        except Exception as e:
            logger.error(f"Callback error: {e}")
            await query.edit_message_text(f"Error: {str(e)}")

    async def _display_account(self, update_obj, account: Dict):
        hypixel_emoji = "🟢" if account["hypixel_status"] == "online" else "🔴" if account["hypixel_status"] == "offline" else "⚪"
        donut_emoji = "🟢" if account["donutsmp_status"] == "online" else "🔴" if account["donutsmp_status"] == "offline" else "⚪"
        cubecraft_emoji = "🟢" if account["cubecraft_status"] == "online" else "🔴" if account["cubecraft_status"] == "offline" else "⚪"
        bedrock_emoji = "✅ YES" if account["bedrock_owned"] else "❌ NO"
        
        message = (
            f"📋 YOUR ACCOUNT\n"
            f"═══════════════════════════\n\n"
            f"📧 Email: {account['email']}\n"
            f"🔑 Password: {account['password']}\n"
            f"👤 Username: {account['username']}\n\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🟡 HYPIXEL\n"
            f"   Status: {hypixel_emoji} {account['hypixel_status']}\n"
            f"   Rank: {account['hypixel_rank']}\n"
            f"   Banned: {'✅ YES' if account['hypixel_banned'] else '❌ NO'}\n\n"
            f"🟠 DONUTSMP\n"
            f"   Status: {donut_emoji} {account['donutsmp_status']}\n"
            f"   Banned: {'✅ YES' if account['donutsmp_banned'] else '❌ NO'}\n"
            f"   Kills: {account['donutsmp_kills']} | Deaths: {account['donutsmp_deaths']}\n\n"
            f"🟢 CUBECRAFT\n"
            f"   Status: {cubecraft_emoji} {account['cubecraft_status']}\n"
            f"   Rank: {account['cubecraft_rank']}\n"
            f"   Banned: {'✅ YES' if account['cubecraft_banned'] else '❌ NO'}\n\n"
            f"🎮 BEDROCK EDITION\n"
            f"   Owned: {bedrock_emoji}\n\n"
            f"Use /release to give this account back."
        )
        
        keyboard = [
            [InlineKeyboardButton("🔄 REFRESH STATUS", callback_data=f"refresh_{account['id']}")],
            [InlineKeyboardButton("📊 VIEW STATS", callback_data="view_stats")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if hasattr(update_obj, 'edit_message_text'):
            await update_obj.edit_message_text(message, reply_markup=reply_markup)
        else:
            await update_obj.message.reply_text(message, reply_markup=reply_markup)

    def run(self):
        logger.info("Minecraft Account Bot starting...")
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
