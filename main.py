"""
Telegram + Discord Server Automation Bot
==========================================

A production-ready control panel: a Telegram bot (aiogram) lets the owner
pick a connected Discord server and a set of games, then a Discord bot
(discord.py) builds out a complete, professional server structure
(roles, categories, channels, permissions) automatically.

Run with:
    python main.py

Required environment variables:
    TELEGRAM_BOT_TOKEN
    DISCORD_BOT_TOKEN
    OWNER_ID
"""

from __future__ import annotations

import asyncio
import functools
import logging
import os
import sys
from dataclasses import dataclass, field
from typing import Optional

import discord
from discord.ext import commands as discord_commands

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("server-builder")
logging.getLogger("discord").setLevel(logging.WARNING)
logging.getLogger("aiogram").setLevel(logging.WARNING)

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
OWNER_ID_RAW = os.getenv("OWNER_ID")

if not TELEGRAM_BOT_TOKEN:
    logger.critical("Missing required environment variable: TELEGRAM_BOT_TOKEN")
    sys.exit(1)

if not DISCORD_BOT_TOKEN:
    logger.critical("Missing required environment variable: DISCORD_BOT_TOKEN")
    sys.exit(1)

if not OWNER_ID_RAW:
    logger.critical("Missing required environment variable: OWNER_ID")
    sys.exit(1)

try:
    OWNER_ID = int(OWNER_ID_RAW)
except ValueError:
    logger.critical("OWNER_ID must be an integer Telegram user id")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Game database
# ---------------------------------------------------------------------------

# Store keys correspond to badges shown to the user and to channel-permission
# templates. Every game lists ONLY the stores that officially support it.

STEAM = "steam"
EPIC = "epic-games"
MS_STORE = "microsoft-store"
XBOX = "xbox-store"

STORE_LABELS = {
    STEAM: "Steam",
    EPIC: "Epic Games Store",
    MS_STORE: "Microsoft Store",
    XBOX: "Xbox Store",
}


@dataclass(frozen=True)
class Game:
    key: str
    name: str
    stores: tuple[str, ...]
    channels: tuple[str, ...]
    voice_channels: tuple[str, ...] = ("voice-chat",)


GAME_DATABASE: dict[str, Game] = {}


def _register(game: Game) -> None:
    GAME_DATABASE[game.key] = game


_register(Game(
    key="minecraft",
    name="Minecraft",
    stores=(MS_STORE, XBOX),
    channels=("general", "survival", "creative", "mods", "resource-packs", "screenshots", "clips"),
    voice_channels=("survival-vc", "creative-vc"),
))
_register(Game(
    key="among-us",
    name="Among Us",
    stores=(STEAM, EPIC, MS_STORE, XBOX),
    channels=("general", "find-lobby", "memes", "screenshots"),
    voice_channels=("voice-chat",),
))
_register(Game(
    key="roblox",
    name="Roblox",
    stores=(MS_STORE, XBOX),
    channels=("general", "game-links", "trading", "screenshots"),
    voice_channels=("voice-chat",),
))
_register(Game(
    key="valorant",
    name="Valorant",
    stores=(EPIC,),
    channels=("general", "ranked", "looking-for-team", "lineups", "clips"),
    voice_channels=("ranked-vc", "casual-vc"),
))
_register(Game(
    key="fortnite",
    name="Fortnite",
    stores=(EPIC, MS_STORE, XBOX),
    channels=("general", "squads", "builds", "clips"),
    voice_channels=("squad-vc",),
))
_register(Game(
    key="cs2",
    name="Counter-Strike 2",
    stores=(STEAM,),
    channels=("general", "competitive", "looking-for-team", "clips"),
    voice_channels=("competitive-vc", "casual-vc"),
))
_register(Game(
    key="rocket-league",
    name="Rocket League",
    stores=(STEAM, EPIC, MS_STORE, XBOX),
    channels=("general", "ranked", "looking-for-team", "clips"),
    voice_channels=("ranked-vc",),
))
_register(Game(
    key="league-of-legends",
    name="League of Legends",
    stores=(),
    channels=("general", "ranked", "looking-for-team", "builds", "clips"),
    voice_channels=("ranked-vc", "casual-vc"),
))
_register(Game(
    key="rust",
    name="Rust",
    stores=(STEAM,),
    channels=("general", "server-info", "raids", "screenshots"),
    voice_channels=("voice-chat",),
))
_register(Game(
    key="ark",
    name="ARK",
    stores=(STEAM, EPIC, MS_STORE, XBOX),
    channels=("general", "server-info", "tribes", "screenshots"),
    voice_channels=("tribe-vc",),
))
_register(Game(
    key="terraria",
    name="Terraria",
    stores=(STEAM, MS_STORE, XBOX),
    channels=("general", "worlds", "builds", "screenshots"),
    voice_channels=("voice-chat",),
))
_register(Game(
    key="fall-guys",
    name="Fall Guys",
    stores=(EPIC, MS_STORE, XBOX),
    channels=("general", "lobbies", "clips", "memes"),
    voice_channels=("voice-chat",),
))
_register(Game(
    key="dead-by-daylight",
    name="Dead by Daylight",
    stores=(STEAM, EPIC, MS_STORE, XBOX),
    channels=("general", "looking-for-team", "builds", "clips"),
    voice_channels=("voice-chat",),
))
_register(Game(
    key="rainbow-six-siege",
    name="Rainbow Six Siege",
    stores=(STEAM, MS_STORE, XBOX),
    channels=("general", "ranked", "looking-for-team", "strats", "clips"),
    voice_channels=("ranked-vc", "casual-vc"),
))
_register(Game(
    key="destiny-2",
    name="Destiny 2",
    stores=(STEAM, EPIC, MS_STORE, XBOX),
    channels=("general", "raids", "looking-for-team", "builds", "clips"),
    voice_channels=("raid-vc", "fireteam-vc"),
))
_register(Game(
    key="apex-legends",
    name="Apex Legends",
    stores=(STEAM, EPIC, MS_STORE, XBOX),
    channels=("general", "ranked", "looking-for-team", "clips"),
    voice_channels=("ranked-vc", "casual-vc"),
))
_register(Game(
    key="overwatch-2",
    name="Overwatch 2",
    stores=(STEAM, MS_STORE, XBOX),
    channels=("general", "ranked", "looking-for-team", "comps", "clips"),
    voice_channels=("ranked-vc", "casual-vc"),
))
_register(Game(
    key="project-zomboid",
    name="Project Zomboid",
    stores=(STEAM,),
    channels=("general", "server-info", "survival-tips", "screenshots"),
    voice_channels=("voice-chat",),
))
_register(Game(
    key="palworld",
    name="Palworld",
    stores=(STEAM, MS_STORE, XBOX),
    channels=("general", "server-info", "pal-trading", "screenshots"),
    voice_channels=("voice-chat",),
))
_register(Game(
    key="gta-v",
    name="GTA V",
    stores=(STEAM, EPIC, MS_STORE),
    channels=("general", "roleplay", "heists", "clips"),
    voice_channels=("session-vc",),
))
_register(Game(
    key="pubg",
    name="PUBG: Battlegrounds",
    stores=(STEAM, MS_STORE, XBOX),
    channels=("general", "squads", "looking-for-team", "clips"),
    voice_channels=("squad-vc",),
))
_register(Game(
    key="warzone",
    name="Call of Duty: Warzone",
    stores=(MS_STORE, XBOX),
    channels=("general", "squads", "looking-for-team", "clips"),
    voice_channels=("squad-vc",),
))
_register(Game(
    key="stardew-valley",
    name="Stardew Valley",
    stores=(STEAM, MS_STORE, XBOX),
    channels=("general", "farms", "screenshots"),
    voice_channels=("voice-chat",),
))
_register(Game(
    key="genshin-impact",
    name="Genshin Impact",
    stores=(),
    channels=("general", "builds", "gacha", "screenshots"),
    voice_channels=("voice-chat",),
))
_register(Game(
    key="ff14",
    name="Final Fantasy XIV",
    stores=(STEAM,),
    channels=("general", "raids", "looking-for-team", "screenshots"),
    voice_channels=("raid-vc", "casual-vc"),
))
_register(Game(
    key="world-of-warcraft",
    name="World of Warcraft",
    stores=(),
    channels=("general", "raids", "pvp", "looking-for-team", "screenshots"),
    voice_channels=("raid-vc", "pvp-vc"),
))
_register(Game(
    key="phasmophobia",
    name="Phasmophobia",
    stores=(STEAM,),
    channels=("general", "looking-for-team", "clips"),
    voice_channels=("investigation-vc",),
))
_register(Game(
    key="lethal-company",
    name="Lethal Company",
    stores=(STEAM,),
    channels=("general", "looking-for-team", "clips"),
    voice_channels=("crew-vc",),
))
_register(Game(
    key="sea-of-thieves",
    name="Sea of Thieves",
    stores=(STEAM, MS_STORE, XBOX),
    channels=("general", "crews", "looking-for-team", "clips"),
    voice_channels=("crew-vc",),
))
_register(Game(
    key="hell-let-loose",
    name="Hell Let Loose",
    stores=(STEAM, XBOX),
    channels=("general", "squads", "clips"),
    voice_channels=("squad-vc",),
))
_register(Game(
    key="escape-from-tarkov",
    name="Escape from Tarkov",
    stores=(),
    channels=("general", "raids", "trading", "clips"),
    voice_channels=("raid-vc",),
))
_register(Game(
    key="cyberpunk-2077",
    name="Cyberpunk 2077",
    stores=(STEAM, EPIC, MS_STORE, XBOX),
    channels=("general", "builds", "screenshots"),
    voice_channels=("voice-chat",),
))
_register(Game(
    key="baldurs-gate-3",
    name="Baldur's Gate 3",
    stores=(STEAM, MS_STORE, XBOX),
    channels=("general", "co-op", "builds", "screenshots"),
    voice_channels=("co-op-vc",),
))
_register(Game(
    key="helldivers-2",
    name="Helldivers 2",
    stores=(STEAM, MS_STORE, XBOX),
    channels=("general", "squads", "clips"),
    voice_channels=("squad-vc",),
))


def search_games(query: str) -> list[Game]:
    """Case-insensitive substring search across game names."""
    query = query.strip().lower()
    if not query:
        return []
    return sorted(
        (g for g in GAME_DATABASE.values() if query in g.name.lower()),
        key=lambda g: g.name,
    )


# ---------------------------------------------------------------------------
# Discord bot
# ---------------------------------------------------------------------------

intents = discord.Intents.default()
intents.guilds = True

discord_bot = discord_commands.Bot(command_prefix="!", intents=intents)

DEFAULT_MAX_RETRIES = 5


async def _with_retries(coro_factory, *, what: str):
    """Run a Discord API call, retrying on rate limits / transient errors."""
    last_error: Optional[Exception] = None
    for attempt in range(1, DEFAULT_MAX_RETRIES + 1):
        try:
            return await coro_factory()
        except discord.HTTPException as exc:
            last_error = exc
            if exc.status == 429:
                retry_after = getattr(exc, "retry_after", None) or 2 * attempt
                logger.warning(
                    "Rate limited while %s (attempt %d/%d). Retrying in %.1fs",
                    what, attempt, DEFAULT_MAX_RETRIES, retry_after,
                )
                await asyncio.sleep(retry_after)
                continue
            if 500 <= exc.status < 600:
                wait = 1.5 * attempt
                logger.warning(
                    "Discord server error while %s (attempt %d/%d): %s. Retrying in %.1fs",
                    what, attempt, DEFAULT_MAX_RETRIES, exc, wait,
                )
                await asyncio.sleep(wait)
                continue
            logger.error("Non-retryable Discord error while %s: %s", what, exc)
            raise
        except discord.DiscordServerError as exc:
            last_error = exc
            wait = 1.5 * attempt
            logger.warning(
                "Discord server error while %s (attempt %d/%d). Retrying in %.1fs",
                what, attempt, DEFAULT_MAX_RETRIES, wait,
            )
            await asyncio.sleep(wait)
    logger.error("Giving up on %s after %d attempts", what, DEFAULT_MAX_RETRIES)
    if last_error:
        raise last_error
    raise RuntimeError(f"Failed to complete: {what}")


ROLE_SPECS: list[tuple[str, discord.Permissions, discord.Colour, bool]] = [
    ("👑 Owner", discord.Permissions.all(), discord.Colour.gold(), True),
    ("🛡 Administrator", discord.Permissions(administrator=True), discord.Colour.red(), True),
    (
        "⚔ Moderator",
        discord.Permissions(
            manage_messages=True,
            kick_members=True,
            moderate_members=True,
            manage_nicknames=True,
        ),
        discord.Colour.blue(),
        True,
    ),
    ("🎮 Gamer", discord.Permissions(), discord.Colour.green(), False),
    ("🤖 Bots", discord.Permissions(), discord.Colour.dark_grey(), True),
    ("👤 Member", discord.Permissions(), discord.Colour.light_grey(), False),
]

INFO_CHANNELS = ("rules", "announcements", "updates", "welcome")
COMMUNITY_CHANNELS = ("general", "media", "memes")
VOICE_CHANNELS = ("General VC", "Gaming VC")
STAFF_TEXT_CHANNELS = ("staff-chat",)
STAFF_VOICE_CHANNELS = ("staff-voice",)
BOT_CHANNELS = ("bot-commands",)
LOG_CHANNELS = ("logs",)


@dataclass
class BuildProgress:
    steps_done: int = 0
    steps_total: int = 0
    log: list[str] = field(default_factory=list)


async def create_roles(
    guild: discord.Guild, progress: BuildProgress,
) -> tuple[dict[str, discord.Role], list[discord.Role]]:
    """Create the standard role set, skipping roles that already exist by name.

    Returns (all_roles_by_name, newly_created_roles) so callers can roll back
    only the roles this build actually created, never pre-existing ones.
    """
    roles: dict[str, discord.Role] = {}
    newly_created: list[discord.Role] = []
    existing = {r.name: r for r in guild.roles}
    for name, perms, colour, hoist in ROLE_SPECS:
        if name in existing:
            roles[name] = existing[name]
            continue
        role = await _with_retries(
            lambda name=name, perms=perms, colour=colour, hoist=hoist: guild.create_role(
                name=name, permissions=perms, colour=colour, hoist=hoist,
                reason="Automated server build",
            ),
            what=f"creating role {name}",
        )
        roles[name] = role
        newly_created.append(role)
        progress.steps_done += 1
        progress.log.append(f"Created role {name}")
    return roles, newly_created


def _bot_overwrite_entry(guild: discord.Guild) -> dict:
    """Grant the bot's own member/role view+send access, if resolvable.

    `guild.me` can be `None` in edge cases (e.g. cache not yet populated),
    so this is guarded rather than assumed present.
    """
    target = guild.me
    if target is None:
        return {}
    return {target: discord.PermissionOverwrite(send_messages=True, view_channel=True)}


def _overwrites_read_only(guild: discord.Guild, roles: dict[str, discord.Role], writers: list[str]) -> dict:
    """Everyone can read, only the given role names can send messages."""
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(
            view_channel=True, send_messages=False, read_message_history=True,
        ),
        **_bot_overwrite_entry(guild),
    }
    for role_name in writers:
        role = roles.get(role_name)
        if role:
            overwrites[role] = discord.PermissionOverwrite(send_messages=True, view_channel=True)
    return overwrites


def _overwrites_bot_only(guild: discord.Guild, roles: dict[str, discord.Role]) -> dict:
    return {
        guild.default_role: discord.PermissionOverwrite(
            view_channel=True, send_messages=False, read_message_history=True,
        ),
        **_bot_overwrite_entry(guild),
    }


def _overwrites_hidden_except(guild: discord.Guild, roles: dict[str, discord.Role], visible_to: list[str]) -> dict:
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        **_bot_overwrite_entry(guild),
    }
    for role_name in visible_to:
        role = roles.get(role_name)
        if role:
            overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
    return overwrites


def _overwrites_open(guild: discord.Guild) -> dict:
    return {
        guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        **_bot_overwrite_entry(guild),
    }


async def create_category(
    guild: discord.Guild, name: str, progress: BuildProgress, overwrites: Optional[dict] = None,
) -> discord.CategoryChannel:
    category = await _with_retries(
        lambda: guild.create_category(name=name, overwrites=overwrites or {}, reason="Automated server build"),
        what=f"creating category {name}",
    )
    progress.steps_done += 1
    progress.log.append(f"Created category {name}")
    return category


async def create_text_channel(
    guild: discord.Guild, name: str, category: discord.CategoryChannel,
    progress: BuildProgress, overwrites: Optional[dict] = None,
) -> discord.TextChannel:
    channel = await _with_retries(
        lambda: guild.create_text_channel(
            name=name, category=category, overwrites=overwrites, reason="Automated server build",
        ),
        what=f"creating text channel {name}",
    )
    progress.steps_done += 1
    progress.log.append(f"Created #{name}")
    return channel


async def create_voice_channel(
    guild: discord.Guild, name: str, category: discord.CategoryChannel,
    progress: BuildProgress, overwrites: Optional[dict] = None,
) -> discord.VoiceChannel:
    channel = await _with_retries(
        lambda: guild.create_voice_channel(
            name=name, category=category, overwrites=overwrites, reason="Automated server build",
        ),
        what=f"creating voice channel {name}",
    )
    progress.steps_done += 1
    progress.log.append(f"Created voice channel {name}")
    return channel


async def build_server(
    guild: discord.Guild,
    game_keys: list[str],
    on_progress=None,
) -> BuildProgress:
    """
    Build the full server structure: roles, information/community/staff/bots/logs
    categories, one category per selected game, and voice channels.

    Cleans up any partially created categories/roles if a fatal error occurs.
    """
    progress = BuildProgress()
    created_categories: list[discord.CategoryChannel] = []
    created_roles: dict[str, discord.Role] = {}
    newly_created_roles: list[discord.Role] = []

    async def notify():
        if on_progress:
            await on_progress(progress)

    try:
        created_roles, newly_created_roles = await create_roles(guild, progress)
        await notify()

        # INFORMATION
        info_overwrites_default = _overwrites_read_only(
            guild, created_roles, ["👑 Owner", "🛡 Administrator"],
        )
        info_category = await create_category(guild, "📢 INFORMATION", progress, {
            guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=False),
        })
        created_categories.append(info_category)
        for ch in INFO_CHANNELS:
            if ch == "welcome":
                overwrites = _overwrites_bot_only(guild, created_roles)
            else:
                overwrites = info_overwrites_default
            await create_text_channel(guild, ch, info_category, progress, overwrites)
        await notify()

        # COMMUNITY
        community_category = await create_category(guild, "💬 COMMUNITY", progress, _overwrites_open(guild))
        created_categories.append(community_category)
        for ch in COMMUNITY_CHANNELS:
            await create_text_channel(guild, ch, community_category, progress, _overwrites_open(guild))
        await notify()

        # GAMING (dynamic, one category per selected game)
        for game_key in game_keys:
            game = GAME_DATABASE.get(game_key)
            if not game:
                logger.warning("Unknown game key skipped: %s", game_key)
                continue
            game_category = await create_category(
                guild, f"🎮 {game.name.upper()}", progress, _overwrites_open(guild),
            )
            created_categories.append(game_category)
            for ch in game.channels:
                await create_text_channel(guild, ch, game_category, progress, _overwrites_open(guild))
            for vc in game.voice_channels:
                await create_voice_channel(guild, vc, game_category, progress, _overwrites_open(guild))
            await notify()

        # VOICE
        voice_category = await create_category(guild, "👥 VOICE", progress, _overwrites_open(guild))
        created_categories.append(voice_category)
        for vc in VOICE_CHANNELS:
            await create_voice_channel(guild, vc, voice_category, progress, _overwrites_open(guild))
        await notify()

        # STAFF
        staff_overwrites = _overwrites_hidden_except(
            guild, created_roles, ["👑 Owner", "🛡 Administrator", "⚔ Moderator"],
        )
        staff_category = await create_category(guild, "🛡 STAFF", progress, staff_overwrites)
        created_categories.append(staff_category)
        for ch in STAFF_TEXT_CHANNELS:
            await create_text_channel(guild, ch, staff_category, progress, staff_overwrites)
        for vc in STAFF_VOICE_CHANNELS:
            await create_voice_channel(guild, vc, staff_category, progress, staff_overwrites)
        await notify()

        # BOTS
        bots_overwrites = _overwrites_read_only(
            guild, created_roles, ["👑 Owner", "🛡 Administrator", "⚔ Moderator", "🤖 Bots"],
        )
        bots_category = await create_category(guild, "🤖 BOTS", progress, _overwrites_open(guild))
        created_categories.append(bots_category)
        for ch in BOT_CHANNELS:
            await create_text_channel(guild, ch, bots_category, progress, bots_overwrites)
        await notify()

        # LOGS
        logs_overwrites = _overwrites_hidden_except(
            guild, created_roles, ["👑 Owner", "🛡 Administrator", "⚔ Moderator"],
        )
        logs_category = await create_category(guild, "📜 LOGS", progress, logs_overwrites)
        created_categories.append(logs_category)
        for ch in LOG_CHANNELS:
            await create_text_channel(guild, ch, logs_category, progress, logs_overwrites)
        await notify()

        return progress

    except Exception:
        logger.exception("Server build failed, cleaning up partially created roles/categories")
        for category in reversed(created_categories):
            try:
                for channel in list(category.channels):
                    await channel.delete(reason="Cleanup after failed build")
                await category.delete(reason="Cleanup after failed build")
            except discord.HTTPException:
                logger.warning("Failed to clean up category %s during rollback", category.name)
        for role in reversed(newly_created_roles):
            try:
                await role.delete(reason="Cleanup after failed build")
            except discord.HTTPException:
                logger.warning("Failed to clean up role %s during rollback", role.name)
        raise


@discord_bot.event
async def on_ready():
    logger.info("Discord bot logged in as %s (id=%s)", discord_bot.user, discord_bot.user.id)


def get_guild_by_id(guild_id: int) -> Optional[discord.Guild]:
    return discord_bot.get_guild(guild_id)


# ---------------------------------------------------------------------------
# Telegram bot
# ---------------------------------------------------------------------------

router = Router()


class BuildStates(StatesGroup):
    choosing_server = State()
    choosing_games = State()
    searching_games = State()


def owner_only(handler):
    @functools.wraps(handler)
    async def wrapper(event, *args, **kwargs):
        user = event.from_user
        if user is None or user.id != OWNER_ID:
            if isinstance(event, Message):
                await event.answer("⛔ You are not authorized to use this bot.")
            elif isinstance(event, CallbackQuery):
                await event.answer("⛔ Not authorized.", show_alert=True)
            logger.warning("Unauthorized access attempt from user_id=%s", user.id if user else "unknown")
            return
        return await handler(event, *args, **kwargs)
    return wrapper


def home_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏗 Build Server", callback_data="menu:build")],
        [InlineKeyboardButton(text="🎮 Select Games", callback_data="menu:games")],
        [InlineKeyboardButton(text="⚙ Settings", callback_data="menu:settings")],
        [InlineKeyboardButton(text="📊 Status", callback_data="menu:status")],
        [InlineKeyboardButton(text="❌ Cancel", callback_data="menu:cancel")],
    ])


def home_text() -> str:
    return (
        "🏠 <b>Home — Server Builder Control Panel</b>\n\n"
        "Use the menu below to build a complete, professional Discord server "
        "structure automatically."
    )


def guild_list_keyboard() -> InlineKeyboardMarkup:
    guilds = list(discord_bot.guilds)
    rows = [
        [InlineKeyboardButton(text=f"🌐 {g.name}", callback_data=f"server:{g.id}")]
        for g in guilds
    ]
    rows.append([InlineKeyboardButton(text="🏠 Home", callback_data="menu:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def game_selection_keyboard(selected: set[str], page: int = 0, page_size: int = 8) -> InlineKeyboardMarkup:
    games = sorted(GAME_DATABASE.values(), key=lambda g: g.name)
    start = page * page_size
    page_games = games[start:start + page_size]

    rows = []
    for game in page_games:
        mark = "✅ " if game.key in selected else "▫️ "
        rows.append([InlineKeyboardButton(text=f"{mark}{game.name}", callback_data=f"game:{game.key}")])

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅ Prev", callback_data=f"gamepage:{page - 1}"))
    if start + page_size < len(games):
        nav_row.append(InlineKeyboardButton(text="Next ➡", callback_data=f"gamepage:{page + 1}"))
    if nav_row:
        rows.append(nav_row)

    rows.append([InlineKeyboardButton(text="🔎 Search Games", callback_data="game:search")])
    if selected:
        rows.append([InlineKeyboardButton(text=f"✅ Confirm ({len(selected)} selected)", callback_data="game:confirm")])
    rows.append([InlineKeyboardButton(text="🏠 Home", callback_data="menu:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def search_results_keyboard(results: list[Game], selected: set[str]) -> InlineKeyboardMarkup:
    rows = []
    for game in results[:15]:
        mark = "✅ " if game.key in selected else "▫️ "
        rows.append([InlineKeyboardButton(text=f"{mark}{game.name}", callback_data=f"game:{game.key}")])
    if selected:
        rows.append([InlineKeyboardButton(text=f"✅ Confirm ({len(selected)} selected)", callback_data="game:confirm")])
    rows.append([InlineKeyboardButton(text="🎮 Back to List", callback_data="menu:games")])
    rows.append([InlineKeyboardButton(text="🏠 Home", callback_data="menu:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def game_stores_text(game: Game) -> str:
    if not game.stores:
        return "No PC storefront listed"
    return ", ".join(STORE_LABELS[s] for s in game.stores)


def build_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Start Build", callback_data="build:start")],
        [InlineKeyboardButton(text="🎮 Change Games", callback_data="menu:games")],
        [InlineKeyboardButton(text="🏠 Home", callback_data="menu:home")],
    ])


@router.message(Command("start"))
@owner_only
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(home_text(), reply_markup=home_keyboard())


@router.callback_query(F.data == "menu:home")
@owner_only
async def cb_home(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(home_text(), reply_markup=home_keyboard())
    await callback.answer()


@router.callback_query(F.data == "menu:cancel")
@owner_only
async def cb_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("❌ Operation cancelled.", reply_markup=home_keyboard())
    await callback.answer()


@router.callback_query(F.data == "menu:status")
@owner_only
async def cb_status(callback: CallbackQuery, state: FSMContext) -> None:
    guild_count = len(discord_bot.guilds)
    latency_ms = round(discord_bot.latency * 1000) if discord_bot.latency else 0
    text = (
        "📊 <b>Status</b>\n\n"
        f"Discord bot: {'🟢 Online' if discord_bot.is_ready() else '🔴 Offline'}\n"
        f"Connected servers: <b>{guild_count}</b>\n"
        f"Gateway latency: <b>{latency_ms} ms</b>\n"
        f"Games in database: <b>{len(GAME_DATABASE)}</b>"
    )
    await callback.message.edit_text(text, reply_markup=home_keyboard())
    await callback.answer()


@router.callback_query(F.data == "menu:settings")
@owner_only
async def cb_settings(callback: CallbackQuery, state: FSMContext) -> None:
    text = (
        "⚙ <b>Settings</b>\n\n"
        f"Owner ID: <code>{OWNER_ID}</code>\n"
        "This bot only responds to its configured owner.\n"
        "Environment variables are managed outside this bot (Railway dashboard)."
    )
    await callback.message.edit_text(text, reply_markup=home_keyboard())
    await callback.answer()


@router.callback_query(F.data == "menu:build")
@owner_only
async def cb_build(callback: CallbackQuery, state: FSMContext) -> None:
    if not discord_bot.guilds:
        await callback.message.edit_text(
            "⚠ The Discord bot is not currently in any server.\n\n"
            "Invite it with Administrator permission first, then try again.",
            reply_markup=home_keyboard(),
        )
        await callback.answer()
        return
    await state.set_state(BuildStates.choosing_server)
    await callback.message.edit_text(
        "🏗 <b>Build Server</b>\n\nSelect a Discord server to build:",
        reply_markup=guild_list_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("server:"))
@owner_only
async def cb_select_server(callback: CallbackQuery, state: FSMContext) -> None:
    guild_id = int(callback.data.split(":", 1)[1])
    guild = get_guild_by_id(guild_id)
    if guild is None:
        await callback.answer("Server not found. It may have removed the bot.", show_alert=True)
        return
    await state.update_data(guild_id=guild_id, selected_games=[])
    await state.set_state(BuildStates.choosing_games)
    await callback.message.edit_text(
        f"🎮 <b>Select Games</b>\nServer: <b>{guild.name}</b>\n\n"
        "Tap games to add them. Each selected game gets its own category "
        "with tailored channels.",
        reply_markup=game_selection_keyboard(set()),
    )
    await callback.answer()


@router.callback_query(F.data == "menu:games")
@owner_only
async def cb_games_menu(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    if "guild_id" not in data:
        await callback.message.edit_text(
            "🏗 <b>Build Server</b>\n\nSelect a Discord server first:",
            reply_markup=guild_list_keyboard(),
        )
        await state.set_state(BuildStates.choosing_server)
        await callback.answer()
        return
    selected = set(data.get("selected_games", []))
    await state.set_state(BuildStates.choosing_games)
    await callback.message.edit_text(
        "🎮 <b>Select Games</b>\n\nTap games to add or remove them.",
        reply_markup=game_selection_keyboard(selected),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("gamepage:"))
@owner_only
async def cb_game_page(callback: CallbackQuery, state: FSMContext) -> None:
    page = int(callback.data.split(":", 1)[1])
    data = await state.get_data()
    selected = set(data.get("selected_games", []))
    await callback.message.edit_reply_markup(reply_markup=game_selection_keyboard(selected, page=page))
    await callback.answer()


@router.callback_query(F.data.startswith("game:"))
@owner_only
async def cb_toggle_game(callback: CallbackQuery, state: FSMContext) -> None:
    action = callback.data.split(":", 1)[1]

    if action == "search":
        await state.set_state(BuildStates.searching_games)
        await callback.message.edit_text(
            "🔎 <b>Search Games</b>\n\nType part of a game name (e.g. <i>mine</i>, <i>fall</i>) "
            "and send it as a message.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🎮 Back to List", callback_data="menu:games")],
            ]),
        )
        await callback.answer()
        return

    if action == "confirm":
        data = await state.get_data()
        selected = data.get("selected_games", [])
        if not selected:
            await callback.answer("Select at least one game first.", show_alert=True)
            return
        game_names = ", ".join(GAME_DATABASE[k].name for k in selected if k in GAME_DATABASE)
        guild = get_guild_by_id(data["guild_id"])
        text = (
            "🚀 <b>Ready to Build</b>\n\n"
            f"Server: <b>{guild.name if guild else 'Unknown'}</b>\n"
            f"Games: <b>{game_names}</b>\n\n"
            "The following will be created:\n"
            "• Roles (Owner, Administrator, Moderator, Gamer, Bots, Member)\n"
            "• 📢 INFORMATION, 💬 COMMUNITY, 👥 VOICE, 🛡 STAFF, 🤖 BOTS, 📜 LOGS categories\n"
            "• One category per selected game with tailored channels\n\n"
            "Continue?"
        )
        await callback.message.edit_text(text, reply_markup=build_confirm_keyboard())
        await callback.answer()
        return

    game_key = action
    if game_key not in GAME_DATABASE:
        await callback.answer("Unknown game.", show_alert=True)
        return

    data = await state.get_data()
    selected = set(data.get("selected_games", []))
    if game_key in selected:
        selected.discard(game_key)
    else:
        selected.add(game_key)
    await state.update_data(selected_games=list(selected))

    game = GAME_DATABASE[game_key]
    await callback.answer(f"{game.name}: {game_stores_text(game)}")
    await callback.message.edit_reply_markup(reply_markup=game_selection_keyboard(selected))


@router.message(BuildStates.searching_games)
@owner_only
async def handle_game_search(message: Message, state: FSMContext) -> None:
    query = message.text or ""
    results = search_games(query)
    data = await state.get_data()
    selected = set(data.get("selected_games", []))

    if not results:
        await message.answer(
            f"No games found matching “{query}”. Try another search term.",
            reply_markup=search_results_keyboard([], selected),
        )
        return

    names = ", ".join(g.name for g in results[:15])
    await message.answer(
        f"🔎 Found {len(results)} match(es): {names}\n\nTap to select:",
        reply_markup=search_results_keyboard(results, selected),
    )


@router.callback_query(F.data == "build:start")
@owner_only
async def cb_build_start(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    guild_id = data.get("guild_id")
    selected_games = data.get("selected_games", [])
    guild = get_guild_by_id(guild_id) if guild_id else None

    if guild is None:
        await callback.message.edit_text(
            "⚠ Server no longer available.", reply_markup=home_keyboard(),
        )
        await callback.answer()
        return

    progress_message = await callback.message.edit_text(
        f"🏗 <b>Building “{guild.name}”…</b>\n\nStarting up, please wait…",
    )
    await callback.answer()

    last_rendered_step = -1

    async def on_progress(progress: BuildProgress) -> None:
        nonlocal last_rendered_step
        if progress.steps_done == last_rendered_step:
            return
        last_rendered_step = progress.steps_done
        recent = "\n".join(f"• {line}" for line in progress.log[-6:])
        try:
            await progress_message.edit_text(
                f"🏗 <b>Building “{guild.name}”…</b>\n\n"
                f"Progress: <b>{progress.steps_done}</b> steps completed\n\n{recent}",
            )
        except Exception:
            logger.debug("Progress edit skipped (rate limit or unchanged content)")

    try:
        progress = await build_server(guild, selected_games, on_progress=on_progress)
        game_names = ", ".join(GAME_DATABASE[k].name for k in selected_games if k in GAME_DATABASE)
        await progress_message.edit_text(
            "✅ <b>Server Build Complete</b>\n\n"
            f"Server: <b>{guild.name}</b>\n"
            f"Games: <b>{game_names}</b>\n"
            f"Total steps: <b>{progress.steps_done}</b>\n\n"
            "Roles, categories, channels, and permissions have been created successfully.",
            reply_markup=home_keyboard(),
        )
        logger.info("Server build completed for guild_id=%s (%s)", guild.id, guild.name)
    except Exception as exc:
        logger.exception("Server build failed for guild_id=%s", guild.id)
        await progress_message.edit_text(
            "❌ <b>Build Failed</b>\n\n"
            f"An error occurred while building the server: <code>{exc}</code>\n"
            "Any partially created channels/categories have been rolled back.\n\n"
            "Make sure the bot has Administrator permission and try again.",
            reply_markup=home_keyboard(),
        )
    finally:
        await state.clear()


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

async def main() -> None:
    bot = Bot(
        token=TELEGRAM_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher.include_router(router)

    logger.info("Starting Discord bot and Telegram bot concurrently…")

    async def run_discord() -> None:
        try:
            await discord_bot.start(DISCORD_BOT_TOKEN)
        except discord.LoginFailure:
            logger.critical("Invalid DISCORD_BOT_TOKEN — could not log in to Discord")
            raise
        except Exception:
            logger.exception("Discord bot crashed")
            raise

    async def run_telegram() -> None:
        try:
            await bot.delete_webhook(drop_pending_updates=True)
            await dispatcher.start_polling(bot)
        except Exception:
            logger.exception("Telegram bot crashed")
            raise

    try:
        await asyncio.gather(run_discord(), run_telegram())
    finally:
        await bot.session.close()
        if not discord_bot.is_closed():
            await discord_bot.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down (keyboard interrupt)")
