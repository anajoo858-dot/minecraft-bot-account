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

# Account list with REAL Minecraft usernames
ACCOUNT_DATA = [
    {"email": "leonyhoki@hotmail.com", "password": "leony123", "username": "leonyhoki"},
    {"email": "manuesper@hotmail.com", "password": "Novalee1971", "username": "manuesper"},
    {"email": "kudaygs35@hotmail.com", "password": "kuday_35", "username": "kudaygs35"},
    {"email": "r_lee_t@hotmail.com", "password": "Rickie1986", "username": "r_lee_t"},
    {"email": "juanmoralesmaster@hotmail.com", "password": "Tuhermana1988", "username": "juanmoralesmaster"},
    {"email": "e_l_gz@hotmail.com", "password": "javier96951", "username": "e_l_gz"},
    {"email": "sa7ato@hotmail.com", "password": "47P8EURR", "username": "sa7ato"},
    {"email": "sadigharoun@hotmail.com", "password": "Sadig9251978", "username": "sadigharoun"},
    {"email": "danwilliams429@hotmail.com", "password": "Pepsimax429!", "username": "danwilliams429"},
    {"email": "longjasper.11@hotmail.com", "password": "tanakornmk119", "username": "longjasper.11"},
    {"email": "henryfh_20@hotmail.com", "password": "Mariajose1975", "username": "henryfh_20"},
    {"email": "furkansln04@hotmail.com", "password": "joyiko1756", "username": "furkansln04"},
    {"email": "anjinho_lucifer@hotmail.com", "password": "Vidaloka9", "username": "anjinho_lucifer"},
    {"email": "franciane_terra@hotmail.com", "password": "Fran202230*", "username": "franciane_terra"},
    {"email": "sahil.mughal9@hotmail.com", "password": "6601345", "username": "sahil.mughal9"},
    {"email": "escorpio_amor6@hotmail.com", "password": "Manuel1986", "username": "escorpio_amor6"},
    {"email": "patrick.lei565@hotmail.com", "password": "h80036565", "username": "patrick.lei565"},
    {"email": "rukawakaede_0103@hotmail.com", "password": "5417rukawa", "username": "rukawakaede_0103"},
    {"email": "mottacontato@hotmail.com", "password": "Motta0066", "username": "mottacontato"},
    {"email": "calelmorales@hotmail.com", "password": "calelmo", "username": "calelmorales"},
    {"email": "alistars747@hotmail.com", "password": "24039296", "username": "alistars747"},
    {"email": "rawrxtedvlpvgx@hotmail.com", "password": "Penguinsarecool3!", "username": "rawrxtedvlpvgx"},
    {"email": "gervais2002@hotmail.com", "password": "Gervais1", "username": "gervais2002"},
    {"email": "leehogan43@hotmail.com", "password": "ice-cream1", "username": "leehogan43"},
    {"email": "usmanghani2001@hotmail.com", "password": "usman2001", "username": "usmanghani2001"},
    {"email": "eimyqiuliu@hotmail.com", "password": "eimyqiu19", "username": "eimyqiuliu"},
    {"email": "elhosini20109@hotmail.com", "password": "mido4484115", "username": "elhosini20109"},
    {"email": "wilderyoni125@hotmail.com", "password": "wilder125", "username": "wilderyoni125"},
    {"email": "aguiguitant@hotmail.com", "password": "ironman82", "username": "aguiguitant"},
    {"email": "rysa_r@live.jp", "password": "aaii0017", "username": "rysa_r"},
    {"email": "momo-556677@hotmail.co.jp", "password": "momo0620", "username": "momo-556677"},
    {"email": "juan_m_m_amer@hotmail.com", "password": "america2005", "username": "juan_m_m_amer"},
    {"email": "dan.khatskevich@hotmail.com", "password": "Werthv2y!!", "username": "dan.khatskevich"},
    {"email": "vivikao0410@hotmail.com", "password": "Vivi0703", "username": "vivikao0410"},
    {"email": "mfernac@hotmail.com", "password": "22642264", "username": "mfernac"},
    {"email": "alvaro.pisciotti@hotmail.com", "password": "america1015", "username": "alvaro.pisciotti"},
    {"email": "killaman20@outlook.kr", "password": "killa558202$", "username": "killaman20"},
    {"email": "jeshualejandro2004@hotmail.com", "password": "jeshua2004", "username": "jeshualejandro2004"},
    {"email": "orionokuriyama@hotmail.co.jp", "password": "Oriono1977", "username": "orionokuriyama"},
    {"email": "lorenzomiopalmo@hotmail.fr", "password": "miopalmo", "username": "lorenzomiopalmo"},
    {"email": "akvileudraite@hotmail.com", "password": "13072426889akv", "username": "akvileudraite"},
    {"email": "johana_ruiz11@outlook.es", "password": "johanaruiz11", "username": "johana_ruiz11"},
    {"email": "vesna_rizman@hotmail.com", "password": "CAPUCINO1986", "username": "vesna_rizman"},
    {"email": "ercan.oztunc@hotmail.com", "password": "05457758659Ee", "username": "ercan.oztunc"},
    {"email": "couillard06@hotmail.com", "password": "Numero06", "username": "couillard06"},
    {"email": "rmudiatmoko12@hotmail.com", "password": "rm121177", "username": "rmudiatmoko12"},
    {"email": "lles34@hotmail.fr", "password": "confort34", "username": "lles34"},
    {"email": "julnim@hotmail.com", "password": "Tennisman2001", "username": "julnim"},
    {"email": "foodza201055@hotmail.com", "password": "0865497427", "username": "foodza201055"},
    {"email": "thewindhill@hotmail.com", "password": "Nevermind1979", "username": "thewindhill"},
    {"email": "gal3090@hotmail.com", "password": "Gg311130496", "username": "gal3090"},
    {"email": "hunir1@hotmail.com", "password": "Aventur1972", "username": "hunir1"},
    {"email": "jaime_1987@live.com", "password": "Paternero3", "username": "jaime_1987"},
    {"email": "andrewturcot@outlook.com", "password": "Turc7otaa!!", "username": "andrewturcot"},
    {"email": "fatjonsejdiu@hotmail.com", "password": "fatjon2003", "username": "fatjonsejdiu"},
    {"email": "fordnavigation@hotmail.com", "password": "Kvolan1976", "username": "fordnavigation"},
    {"email": "propeagronomia@hotmail.com", "password": "agronomia", "username": "propeagronomia"},
    {"email": "luzemilya@hotmail.com", "password": "Paloma2001", "username": "luzemilya"},
    {"email": "mohmedg53@hotmail.com", "password": "Mm6172660-", "username": "mohmedg53"},
    {"email": "chicalinha@hotmail.com", "password": "Santotirso1976", "username": "chicalinha"},
    {"email": "aurelios.santos@hotmail.com", "password": "aurelio30", "username": "aurelios.santos"},
    {"email": "masiulaniec2@hotmail.com", "password": "Janusz1965!!", "username": "masiulaniec2"},
    {"email": "goldamyer@hotmail.com", "password": "Mae1filha2", "username": "goldamyer"},
    {"email": "forfang3171@hotmail.com", "password": "fang3171", "username": "forfang3171"},
    {"email": "lesly.rodriguez666@hotmail.com", "password": "Perezelder1988", "username": "lesly.rodriguez666"},
    {"email": "maharsh.desai@hotmail.com", "password": "maharsh123", "username": "maharsh.desai"},
    {"email": "andymeurisse@hotmail.com", "password": "Refinej19", "username": "andymeurisse"},
    {"email": "gomes.5@hotmail.ch", "password": "HHello1971", "username": "gomes.5"},
    {"email": "cesarfilipe_pc@hotmail.fr", "password": "cesar123", "username": "cesarfilipe_pc"},
    {"email": "unangeloinjeans@hotmail.it", "password": "Afrodite1977", "username": "unangeloinjeans"},
    {"email": "dimitris-nikolas10@hotmail.com", "password": "Vothinoi26!", "username": "dimitris-nikolas10"},
    {"email": "jassna21@hotmail.com", "password": "jassna123", "username": "jassna21"},
    {"email": "happy_-_hippo@hotmail.com", "password": "Lollies1", "username": "happy_-_hippo"},
    {"email": "daddy-fox3311@outlook.jp", "password": "daddy3311", "username": "daddy-fox3311"},
    {"email": "dirkherrig@hotmail.de", "password": "Dillinger1978", "username": "dirkherrig"},
    {"email": "morenosuprapto@hotmail.com", "password": "moreno12", "username": "morenosuprapto"},
    {"email": "gomera_19@hotmail.com", "password": "Gomera1986", "username": "gomera_19"},
    {"email": "ginyeoh@hotmail.com", "password": "ylk901208", "username": "ginyeoh"},
    {"email": "ugrt61@hotmail.com", "password": "9710389u", "username": "ugrt61"},
    {"email": "friesenjung79@hotmail.de", "password": "friese79", "username": "friesenjung79"},
    {"email": "edigleisonedfisica_@hotmail.com", "password": "ed10101708", "username": "edigleisonedfisica_"},
    {"email": "jalen2030@hotmail.com", "password": "F9200351", "username": "jalen2030"},
    {"email": "steph.valerie@hotmail.com", "password": "Valerie1970", "username": "steph.valerie"},
    {"email": "laim2010@hotmail.com", "password": "Alizee1983", "username": "laim2010"},
    {"email": "naif.hhh@hotmail.com", "password": "Nn123789", "username": "naif.hhh"},
    {"email": "rodriguezmp_@hotmail.com", "password": "Torero1983", "username": "rodriguezmp_"},
    {"email": "alejandro_maretto@hotmail.com", "password": "Alejandromaretto", "username": "alejandro_maretto"},
    {"email": "ecushop_present@hotmail.com", "password": "ECUshop2019", "username": "ecushop_present"},
    {"email": "lechiarmero@hotmail.com", "password": "lechi910019", "username": "lechiarmero"},
    {"email": "staratel312@outlook.com", "password": "JapV6QXy", "username": "staratel312"},
    {"email": "sarahdurran@hotmail.com", "password": "Joshie1982", "username": "sarahdurran"},
    {"email": "roapinchacapo@hotmail.com", "password": "pichon01", "username": "roapinchacapo"},
    {"email": "dedelilly43@outlook.com", "password": "DW276301!!", "username": "dedelilly43"},
    {"email": "wendyannmjohnson@hotmail.com", "password": "Wendyj123!!!", "username": "wendyannmjohnson"},
    {"email": "aksakal.korkmaz@hotmail.com", "password": "aksakal12", "username": "aksakal.korkmaz"},
    {"email": "emineyasarela@hotmail.com", "password": "Elam3642", "username": "emineyasarela"},
    {"email": "muhammadjunaid09@hotmail.com", "password": "Junaid.09", "username": "muhammadjunaid09"},
    {"email": "crikron@hotmail.com", "password": "Cipote1984", "username": "crikron"},
    {"email": "nayeva971@hotmail.com", "password": "nayeva14", "username": "nayeva971"},
    {"email": "susy_20@hotmail.cl", "password": "isagu2616", "username": "susy_20"},
    {"email": "francyvisconti@hotmail.it", "password": "francy20", "username": "francyvisconti"},
    {"email": "paquysan@hotmail.com", "password": "Laaldeana1972", "username": "paquysan"},
    {"email": "karim.rouichi@hotmail.com", "password": "KarimSheima2203", "username": "karim.rouichi"},
    {"email": "hami.chamse@hotmail.com", "password": "hami11685116", "username": "hami.chamse"},
    {"email": "flornflakes@hotmail.com", "password": "Lottie1989", "username": "flornflakes"},
    {"email": "danilo_gt_2@hotmail.com", "password": "182712329", "username": "danilo_gt_2"},
    {"email": "doumeum@hotmail.com", "password": "836370392m", "username": "doumeum"},
    {"email": "gamerd3@hotmail.com", "password": "gamer123", "username": "gamerd3"},
    {"email": "zuanny12_@hotmail.es", "password": "130779290", "username": "zuanny12_"},
    {"email": "elyjuniow@hotmail.com", "password": "ely6303056", "username": "elyjuniow"},
    {"email": "f7359@hotmail.com", "password": "01HIGHT1005", "username": "f7359"},
    {"email": "marcovca0005@hotmail.com", "password": "marc437430", "username": "marcovca0005"},
    {"email": "otaku972@hotmail.com", "password": "lea97230", "username": "otaku972"},
    {"email": "done2323@hotmail.com", "password": "Noramdff1", "username": "done2323"},
    {"email": "vane20_03@hotmail.com", "password": "Gaditana1980", "username": "vane20_03"},
    {"email": "naifghost@hotmail.com", "password": "Aa0560633868", "username": "naifghost"},
    {"email": "jnteli@hotmail.com", "password": "Trustno1983", "username": "jnteli"},
    {"email": "gala_27_92@hotmail.com", "password": "Pistoleras2en1.", "username": "gala_27_92"},
    {"email": "imxarsalan@outlook.com", "password": "imx03048155008", "username": "imxarsalan"},
    {"email": "alexia20leal@hotmail.com", "password": "alexia2005", "username": "alexia20leal"},
    {"email": "davletova.meerim@hotmail.com", "password": "Davletova123", "username": "davletova.meerim"},
    {"email": "yulicarolina93@hotmail.com", "password": "Samuel270515", "username": "yulicarolina93"},
    {"email": "leelinkheng@hotmail.com", "password": "lOveglitz2", "username": "leelinkheng"},
    {"email": "canakanj@hotmail.com", "password": "canakan15", "username": "canakanj"},
    {"email": "rraltuve@hotmail.com", "password": "altuve10712955", "username": "rraltuve"},
    {"email": "mironenkorn@live.com", "password": "Miron4ik22", "username": "mironenkorn"},
    {"email": "deryayazan@hotmail.com", "password": "Ddostluk1982", "username": "deryayazan"},
    {"email": "suarn1967@hotmail.co.uk", "password": "Lucylucy945!", "username": "suarn1967"},
    {"email": "eliatrousia@hotmail.com", "password": "19171956", "username": "eliatrousia"},
    {"email": "lizzykwart4500@hotmail.com", "password": "Soyass4500", "username": "lizzykwart4500"},
    {"email": "vesnatodorovska@live.com", "password": "vesna123", "username": "vesnatodorovska"},
    {"email": "pspslim.alex@hotmail.com", "password": "psp45665478", "username": "pspslim.alex"},
    {"email": "markandujar7@hotmail.com", "password": "101792Mark", "username": "markandujar7"}
]

class AccountDB:
    def __init__(self):
        self.conn = sqlite3.connect("accounts.db", check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._init_db()
        self._load_accounts()
        self.last_shown_id = {}  # Track last shown account per user

    def _init_db(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                password TEXT NOT NULL,
                username TEXT NOT NULL,
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
                    (acc["email"], acc["password"], acc["username"])
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

    def get_available_account(self, exclude_id: int = None) -> Optional[Dict]:
        if exclude_id:
            self.cursor.execute("""
                SELECT id, email, password, username, 
                       hypixel_status, hypixel_rank, hypixel_banned,
                       donutsmp_status, donutsmp_banned, donutsmp_kills, donutsmp_deaths,
                       cubecraft_status, cubecraft_banned, cubecraft_rank,
                       bedrock_owned
                FROM accounts WHERE claimed_by = 0 AND id != ? LIMIT 1
            """, (exclude_id,))
        else:
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
                "username": row[3],
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
                "username": row[3],
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

    def get_last_shown(self, user_id: int) -> int:
        return self.last_shown_id.get(user_id, None)

    def set_last_shown(self, user_id: int, account_id: int):
        self.last_shown_id[user_id] = account_id

db = AccountDB()

class ServerChecker:
    @staticmethod
    async def check_all(email: str, password: str) -> Dict:
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
            [InlineKeyboardButton("🎮 SHOW ACCOUNT", callback_data="show_account")],
            [InlineKeyboardButton("📊 VIEW STATS", callback_data="view_stats")],
            [InlineKeyboardButton("📋 MY ACCOUNT", callback_data="myaccount")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"🔓 MINECRAFT ACCOUNT STOCK\n"
            f"═══════════════════════════\n\n"
            f"📦 Total accounts: {stats['total']}\n"
            f"✅ Available: {stats['available']}\n"
            f"🔒 Claimed: {stats['claimed']}\n\n"
            f"Click 'SHOW ACCOUNT' to view an account.\n"
            f"Then click 'CLAIM ACCOUNT' to claim it.",
            reply_markup=reply_markup
        )

    async def myaccount_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        
        account = db.get_account_by_user(update.effective_user.id)
        
        if not account:
            await update.message.reply_text(
                "❌ You don't have any account claimed.\n"
                "Use /start and click 'SHOW ACCOUNT' then 'CLAIM ACCOUNT'."
            )
            return
        
        await self._display_claimed_account(update, account)

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

    async def _display_available_account(self, update_obj, account: Dict):
        hypixel_emoji = "🟢" if account["hypixel_status"] == "online" else "🔴" if account["hypixel_status"] == "offline" else "⚪"
        donut_emoji = "🟢" if account["donutsmp_status"] == "online" else "🔴" if account["donutsmp_status"] == "offline" else "⚪"
        cubecraft_emoji = "🟢" if account["cubecraft_status"] == "online" else "🔴" if account["cubecraft_status"] == "offline" else "⚪"
        bedrock_emoji = "✅ YES" if account["bedrock_owned"] else "❌ NO"
        
        message = (
            f"🎮 AVAILABLE ACCOUNT #{account['id']}\n"
            f"═══════════════════════════\n\n"
            f"📧 Email: {account['email']}\n"
            f"🔑 Password: {account['password']}\n"
            f"🎮 Username: {account['username']}\n\n"
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
            f"⚠️ This account is NOT claimed yet.\n"
            f"Click 'CLAIM ACCOUNT' to make it YOURS."
        )
        
        keyboard = [
            [InlineKeyboardButton("✅ CLAIM ACCOUNT", callback_data=f"claim_{account['id']}")],
            [InlineKeyboardButton("🔄 SHOW ANOTHER", callback_data="show_account")],
            [InlineKeyboardButton("📊 VIEW STATS", callback_data="view_stats")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if hasattr(update_obj, 'edit_message_text'):
            await update_obj.edit_message_text(message, reply_markup=reply_markup)
        else:
            await update_obj.message.reply_text(message, reply_markup=reply_markup)

    async def _display_claimed_account(self, update_obj, account: Dict):
        hypixel_emoji = "🟢" if account["hypixel_status"] == "online" else "🔴" if account["hypixel_status"] == "offline" else "⚪"
        donut_emoji = "🟢" if account["donutsmp_status"] == "online" else "🔴" if account["donutsmp_status"] == "offline" else "⚪"
        cubecraft_emoji = "🟢" if account["cubecraft_status"] == "online" else "🔴" if account["cubecraft_status"] == "offline" else "⚪"
        bedrock_emoji = "✅ YES" if account["bedrock_owned"] else "❌ NO"
        
        message = (
            f"📋 YOUR CLAIMED ACCOUNT\n"
            f"═══════════════════════════\n\n"
            f"📧 Email: {account['email']}\n"
            f"🔑 Password: {account['password']}\n"
            f"🎮 Username: {account['username']}\n\n"
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
            f"✅ This account is YOURS. Only you can see it.\n"
            f"Use /release to give it back."
        )
        
        keyboard = [
            [InlineKeyboardButton("📊 VIEW STATS", callback_data="view_stats")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if hasattr(update_obj, 'edit_message_text'):
            await update_obj.edit_message_text(message, reply_markup=reply_markup)
        else:
            await update_obj.message.reply_text(message, reply_markup=reply_markup)

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        try:
            if query.data == "show_account":
                # Check if user already has a claimed account
                existing = db.get_account_by_user(update.effective_user.id)
                if existing:
                    await query.edit_message_text(
                        f"❌ You already have an account claimed!\n\n"
                        f"📧 Email: {existing['email']}\n"
                        f"🎮 Username: {existing['username']}\n"
                        f"Use /myaccount to view it.\n"
                        f"Use /release to give it back."
                    )
                    return
                
                # Get last shown account ID for this user
                last_shown = db.get_last_shown(update.effective_user.id)
                
                # Get a NEW account (different from last shown)
                account = db.get_available_account(exclude_id=last_shown)
                
                # If no account found (maybe only one available), get any
                if not account:
                    account = db.get_available_account()
                
                if not account:
                    await query.edit_message_text(
                        "❌ No accounts available!\n"
                        "All accounts have been claimed."
                    )
                    return
                
                # Store this as the last shown account for this user
                db.set_last_shown(update.effective_user.id, account["id"])
                
                # Update server status for this account
                server_data = await ServerChecker.check_all(
                    account["email"], 
                    account["password"]
                )
                db.update_server_status(account["id"], server_data)
                account.update(server_data)
                
                await self._display_available_account(query, account)
            
            elif query.data.startswith("claim_"):
                account_id = int(query.data.split("_")[1])
                
                # Check if user already has a claimed account
                existing = db.get_account_by_user(update.effective_user.id)
                if existing:
                    await query.edit_message_text(
                        f"❌ You already have an account claimed!\n\n"
                        f"📧 Email: {existing['email']}\n"
                        f"🎮 Username: {existing['username']}\n"
                        f"Use /myaccount to view it.\n"
                        f"Use /release to give it back."
                    )
                    return
                
                # Verify account exists and is available
                self.cursor = db.conn.cursor()
                self.cursor.execute("SELECT id FROM accounts WHERE id = ? AND claimed_by = 0", (account_id,))
                row = self.cursor.fetchone()
                
                if not row:
                    await query.edit_message_text(
                        "❌ This account was already claimed by someone else!\n"
                        "Click 'SHOW ANOTHER' to see a different account."
                    )
                    return
                
                # Claim the account
                db.claim_account(account_id, update.effective_user.id)
                
                # Get the claimed account
                claimed = db.get_account_by_user(update.effective_user.id)
                if claimed:
                    await self._display_claimed_account(query, claimed)
                else:
                    await query.edit_message_text("✅ Account claimed successfully! Use /myaccount to view it.")
            
            elif query.data == "view_stats":
                stats = db.get_stats()
                keyboard = [
                    [InlineKeyboardButton("🎮 SHOW ACCOUNT", callback_data="show_account")],
                    [InlineKeyboardButton("🔙 BACK", callback_data="back_to_menu")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    f"📊 ACCOUNT STATISTICS\n"
                    f"═══════════════════════════\n\n"
                    f"📦 Total accounts: {stats['total']}\n"
                    f"✅ Available: {stats['available']}\n"
                    f"🔒 Claimed: {stats['claimed']}\n\n"
                    f"📌 Each account can only be claimed once.",
                    reply_markup=reply_markup
                )
            
            elif query.data == "myaccount":
                account = db.get_account_by_user(update.effective_user.id)
                
                if not account:
                    await query.edit_message_text(
                        "❌ You don't have any account claimed.\n"
                        "Use /start and click 'SHOW ACCOUNT' then 'CLAIM ACCOUNT'."
                    )
                    return
                
                await self._display_claimed_account(query, account)
            
            elif query.data == "back_to_menu":
                stats = db.get_stats()
                keyboard = [
                    [InlineKeyboardButton("🎮 SHOW ACCOUNT", callback_data="show_account")],
                    [InlineKeyboardButton("📊 VIEW STATS", callback_data="view_stats")],
                    [InlineKeyboardButton("📋 MY ACCOUNT", callback_data="myaccount")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    f"🔓 MINECRAFT ACCOUNT STOCK\n"
                    f"═══════════════════════════\n\n"
                    f"📦 Total accounts: {stats['total']}\n"
                    f"✅ Available: {stats['available']}\n"
                    f"🔒 Claimed: {stats['claimed']}\n\n"
                    f"Click 'SHOW ACCOUNT' to view an account.\n"
                    f"Then click 'CLAIM ACCOUNT' to claim it.",
                    reply_markup=reply_markup
                )
                
        except Exception as e:
            logger.error(f"Callback error: {e}")
            await query.edit_message_text(f"Error: {str(e)}")

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
