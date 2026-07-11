"""
Telegram + Discord Server Automation Bot
==========================================

A production-ready control panel: a Telegram bot (aiogram) lets the owner
pick a connected Discord server, then a Discord bot (discord.py) builds a
complete, professional server structure (roles, categories, channels,
permissions, and an in-Discord game-selection UI) automatically.

Run with:
    python main.py

Required environment variables:
    TELEGRAM_BOT_TOKEN
    DISCORD_BOT_TOKEN
    OWNER_ID            — numeric Telegram user ID of the bot owner

Optional environment variables:
    DISCORD_USER_ID     — numeric Discord user ID to auto-assign the Owner
                          role after the first build
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
import discord.ui
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
DISCORD_BOT_TOKEN  = os.getenv("DISCORD_BOT_TOKEN")
OWNER_ID_RAW       = os.getenv("OWNER_ID")
DISCORD_USER_ID_RAW = os.getenv("DISCORD_USER_ID")  # optional

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
    logger.critical("OWNER_ID must be an integer Telegram user id, got: %r", OWNER_ID_RAW)
    sys.exit(1)

DISCORD_USER_ID: Optional[int] = None
if DISCORD_USER_ID_RAW:
    try:
        DISCORD_USER_ID = int(DISCORD_USER_ID_RAW)
    except ValueError:
        logger.warning("DISCORD_USER_ID is not a valid integer; owner role assignment will be skipped.")

# ---------------------------------------------------------------------------
# Game database
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Game:
    key:           str
    name:          str
    channels:      tuple[str, ...]
    voice_channels: tuple[str, ...] = ("voice-chat",)


GAME_DATABASE: dict[str, Game] = {}


def _reg(game: Game) -> None:
    GAME_DATABASE[game.key] = game


_reg(Game("minecraft",        "Minecraft",               ("general","survival","creative","mods","resource-packs","screenshots","clips"),             ("survival-vc","creative-vc")))
_reg(Game("among-us",         "Among Us",                ("general","find-lobby","memes","screenshots"),                                              ("voice-chat",)))
_reg(Game("roblox",           "Roblox",                  ("general","game-links","trading","screenshots"),                                            ("voice-chat",)))
_reg(Game("valorant",         "Valorant",                ("general","ranked","looking-for-team","lineups","clips"),                                   ("ranked-vc","casual-vc")))
_reg(Game("fortnite",         "Fortnite",                ("general","squads","builds","clips"),                                                       ("squad-vc",)))
_reg(Game("cs2",              "Counter-Strike 2",        ("general","competitive","looking-for-team","clips"),                                        ("competitive-vc","casual-vc")))
_reg(Game("rocket-league",    "Rocket League",           ("general","ranked","looking-for-team","clips"),                                             ("ranked-vc",)))
_reg(Game("league-of-legends","League of Legends",       ("general","ranked","looking-for-team","builds","clips"),                                   ("ranked-vc","casual-vc")))
_reg(Game("rust",             "Rust",                    ("general","server-info","raids","screenshots"),                                             ("voice-chat",)))
_reg(Game("ark",              "ARK",                     ("general","server-info","tribes","screenshots"),                                            ("tribe-vc",)))
_reg(Game("terraria",         "Terraria",                ("general","worlds","builds","screenshots"),                                                 ("voice-chat",)))
_reg(Game("fall-guys",        "Fall Guys",               ("general","lobbies","clips","memes"),                                                       ("voice-chat",)))
_reg(Game("dead-by-daylight", "Dead by Daylight",        ("general","looking-for-team","builds","clips"),                                             ("voice-chat",)))
_reg(Game("rainbow-six-siege","Rainbow Six Siege",       ("general","ranked","looking-for-team","strats","clips"),                                   ("ranked-vc","casual-vc")))
_reg(Game("destiny-2",        "Destiny 2",               ("general","raids","looking-for-team","builds","clips"),                                    ("raid-vc","fireteam-vc")))
_reg(Game("apex-legends",     "Apex Legends",            ("general","ranked","looking-for-team","clips"),                                             ("ranked-vc","casual-vc")))
_reg(Game("overwatch-2",      "Overwatch 2",             ("general","ranked","looking-for-team","comps","clips"),                                    ("ranked-vc","casual-vc")))
_reg(Game("project-zomboid",  "Project Zomboid",         ("general","server-info","survival-tips","screenshots"),                                    ("voice-chat",)))
_reg(Game("palworld",         "Palworld",                ("general","server-info","pal-trading","screenshots"),                                       ("voice-chat",)))
_reg(Game("gta-v",            "GTA V",                   ("general","roleplay","heists","clips"),                                                     ("session-vc",)))
_reg(Game("pubg",             "PUBG: Battlegrounds",     ("general","squads","looking-for-team","clips"),                                             ("squad-vc",)))
_reg(Game("warzone",          "Call of Duty: Warzone",   ("general","squads","looking-for-team","clips"),                                             ("squad-vc",)))
_reg(Game("stardew-valley",   "Stardew Valley",          ("general","farms","screenshots"),                                                           ("voice-chat",)))
_reg(Game("genshin-impact",   "Genshin Impact",          ("general","builds","gacha","screenshots"),                                                  ("voice-chat",)))
_reg(Game("ff14",             "Final Fantasy XIV",       ("general","raids","looking-for-team","screenshots"),                                        ("raid-vc","casual-vc")))
_reg(Game("world-of-warcraft","World of Warcraft",       ("general","raids","pvp","looking-for-team","screenshots"),                                  ("raid-vc","pvp-vc")))
_reg(Game("phasmophobia",     "Phasmophobia",            ("general","looking-for-team","clips"),                                                      ("investigation-vc",)))
_reg(Game("lethal-company",   "Lethal Company",          ("general","looking-for-team","clips"),                                                      ("crew-vc",)))
_reg(Game("sea-of-thieves",   "Sea of Thieves",          ("general","crews","looking-for-team","clips"),                                              ("crew-vc",)))
_reg(Game("hell-let-loose",   "Hell Let Loose",          ("general","squads","clips"),                                                                ("squad-vc",)))
_reg(Game("escape-from-tarkov","Escape from Tarkov",     ("general","raids","trading","clips"),                                                       ("raid-vc",)))
_reg(Game("cyberpunk-2077",   "Cyberpunk 2077",          ("general","builds","screenshots"),                                                          ("voice-chat",)))
_reg(Game("baldurs-gate-3",   "Baldur's Gate 3",         ("general","co-op","builds","screenshots"),                                                  ("co-op-vc",)))
_reg(Game("helldivers-2",     "Helldivers 2",            ("general","squads","clips"),                                                                 ("squad-vc",)))

# Games featured in the ⭐ Popular Games quick-access panel
POPULAR_GAME_KEYS = [
    "minecraft", "roblox", "among-us", "valorant",
    "fortnite", "gta-v", "rocket-league",
]


def search_games(query: str) -> list[Game]:
    """Case-insensitive substring search across game names."""
    q = query.strip().lower()
    if not q:
        return []
    return sorted(
        (g for g in GAME_DATABASE.values() if q in g.name.lower()),
        key=lambda g: g.name,
    )


# ---------------------------------------------------------------------------
# Metadata tag
# Placed in every text-channel topic created by this bot so Update Server
# can detect bot-managed channels without ambiguity.
# ---------------------------------------------------------------------------

BOT_MANAGED_TOPIC = "[bot-managed]"


# ---------------------------------------------------------------------------
# Discord bot setup
# ---------------------------------------------------------------------------

intents = discord.Intents.default()
intents.guilds = True
intents.members = True   # required to fetch/assign member roles at build time

discord_bot = discord_commands.Bot(command_prefix="!", intents=intents)

DEFAULT_MAX_RETRIES = 5


async def _with_retries(coro_factory, *, what: str):
    """Run a Discord API call, retrying on rate limits / transient 5xx errors."""
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


# ---------------------------------------------------------------------------
# Role specifications (staff hierarchy)
# Game roles are created dynamically from GAME_DATABASE.
# ---------------------------------------------------------------------------

# (name, permissions, colour, hoist)
ROLE_SPECS: list[tuple[str, discord.Permissions, discord.Colour, bool]] = [
    ("👑 Owner",         discord.Permissions.all(),              discord.Colour.gold(),       True),
    ("🛡 Administrator", discord.Permissions(administrator=True), discord.Colour.red(),        True),
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
    ("🎮 Gamer",  discord.Permissions(), discord.Colour.green(),      False),
    ("🤖 Bots",   discord.Permissions(), discord.Colour.dark_grey(),  True),
    ("👤 Member", discord.Permissions(), discord.Colour.light_grey(), False),
]

# ---------------------------------------------------------------------------
# Server structure constants
# ---------------------------------------------------------------------------

INFO_TEXT_CHANNELS  = ("rules", "announcements", "updates", "welcome")
COMMUNITY_CHANNELS  = ("general", "media", "memes")
CUSTOMIZE_CHANNELS  = ("✨・customize-your-experience",)
VOICE_CHANNELS      = ("General VC", "Gaming VC")
STAFF_TEXT_CHANNELS = ("staff-chat",)
STAFF_VOICE_CHANNELS= ("staff-voice",)
BOT_CHANNELS        = ("bot-commands",)
LOG_CHANNELS        = ("logs",)

# Category display names (must match exactly for Update/Reset detection)
CAT_INFORMATION = "📢 INFORMATION"
CAT_COMMUNITY   = "💬 COMMUNITY"
CAT_CUSTOMIZE   = "✨ CUSTOMIZE YOUR EXPERIENCE"
CAT_VOICE       = "👥 VOICE"
CAT_STAFF       = "🛡 STAFF"
CAT_BOTS        = "🤖 BOTS"
CAT_LOGS        = "📜 LOGS"

STATIC_CATEGORY_NAMES = {
    CAT_INFORMATION, CAT_COMMUNITY, CAT_CUSTOMIZE,
    CAT_VOICE, CAT_STAFF, CAT_BOTS, CAT_LOGS,
}


def _game_category_name(game: Game) -> str:
    return f"🎮 {game.name.upper()}"


# ---------------------------------------------------------------------------
# Build progress tracking
# ---------------------------------------------------------------------------

@dataclass
class BuildProgress:
    steps_done:  int        = 0
    steps_total: int        = 0
    log:         list[str]  = field(default_factory=list)


# ---------------------------------------------------------------------------
# Discord channel / category / role helpers
# ---------------------------------------------------------------------------

def _bot_overwrite_entry(guild: discord.Guild) -> dict:
    """Grant the bot itself view + send access. Guards against guild.me being None."""
    target = guild.me
    if target is None:
        return {}
    return {target: discord.PermissionOverwrite(send_messages=True, view_channel=True)}


def _overwrites_read_only(
    guild: discord.Guild,
    roles: dict[str, discord.Role],
    writers: list[str],
) -> dict:
    """Everyone can read; only the listed role names can send."""
    ow = {
        guild.default_role: discord.PermissionOverwrite(
            view_channel=True, send_messages=False, read_message_history=True,
        ),
        **_bot_overwrite_entry(guild),
    }
    for rn in writers:
        role = roles.get(rn)
        if role:
            ow[role] = discord.PermissionOverwrite(send_messages=True, view_channel=True)
    return ow


def _overwrites_bot_only(guild: discord.Guild, roles: dict[str, discord.Role]) -> dict:
    """Visible to everyone, but only the bot can send (welcome channel)."""
    return {
        guild.default_role: discord.PermissionOverwrite(
            view_channel=True, send_messages=False, read_message_history=True,
        ),
        **_bot_overwrite_entry(guild),
    }


def _overwrites_hidden_except(
    guild: discord.Guild,
    roles: dict[str, discord.Role],
    visible_to: list[str],
) -> dict:
    """Hidden from @everyone; only the listed roles can see and write."""
    ow = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        **_bot_overwrite_entry(guild),
    }
    for rn in visible_to:
        role = roles.get(rn)
        if role:
            ow[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
    return ow


def _overwrites_open(guild: discord.Guild) -> dict:
    """Open to everyone."""
    return {
        guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        **_bot_overwrite_entry(guild),
    }


def _overwrites_game(
    guild: discord.Guild,
    game_role: discord.Role,
    staff_roles: list[discord.Role],
) -> dict:
    """
    Game categories are hidden from @everyone.
    Only the matching game role and staff roles can see them.
    """
    ow: dict = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        game_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        **_bot_overwrite_entry(guild),
    }
    for r in staff_roles:
        ow[r] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
    return ow


async def _create_category(
    guild: discord.Guild,
    name: str,
    progress: BuildProgress,
    overwrites: Optional[dict] = None,
) -> discord.CategoryChannel:
    cat = await _with_retries(
        lambda: guild.create_category(
            name=name, overwrites=overwrites or {}, reason="Automated server build",
        ),
        what=f"creating category {name}",
    )
    progress.steps_done += 1
    progress.log.append(f"Created category {name}")
    return cat


async def _create_text_channel(
    guild: discord.Guild,
    name: str,
    category: discord.CategoryChannel,
    progress: BuildProgress,
    overwrites: Optional[dict] = None,
    topic: str = BOT_MANAGED_TOPIC,
) -> discord.TextChannel:
    ch = await _with_retries(
        lambda: guild.create_text_channel(
            name=name,
            category=category,
            overwrites=overwrites,
            topic=topic,
            reason="Automated server build",
        ),
        what=f"creating text channel #{name}",
    )
    progress.steps_done += 1
    progress.log.append(f"Created #{name}")
    return ch


async def _create_voice_channel(
    guild: discord.Guild,
    name: str,
    category: discord.CategoryChannel,
    progress: BuildProgress,
    overwrites: Optional[dict] = None,
) -> discord.VoiceChannel:
    ch = await _with_retries(
        lambda: guild.create_voice_channel(
            name=name,
            category=category,
            overwrites=overwrites,
            reason="Automated server build",
        ),
        what=f"creating voice channel {name}",
    )
    progress.steps_done += 1
    progress.log.append(f"Created voice channel {name}")
    return ch


# ---------------------------------------------------------------------------
# Role creation
# ---------------------------------------------------------------------------

async def create_staff_roles(
    guild: discord.Guild,
    progress: BuildProgress,
) -> tuple[dict[str, discord.Role], list[discord.Role]]:
    """
    Create the standard staff-hierarchy roles.
    Returns (roles_by_name, newly_created_list) — the latter is used for
    rollback so only roles THIS build created are removed on failure.
    """
    roles: dict[str, discord.Role] = {}
    newly_created: list[discord.Role] = []
    existing = {r.name: r for r in guild.roles}

    for name, perms, colour, hoist in ROLE_SPECS:
        if name in existing:
            roles[name] = existing[name]
            continue
        role = await _with_retries(
            lambda n=name, p=perms, c=colour, h=hoist: guild.create_role(
                name=n, permissions=p, colour=c, hoist=h,
                reason="Automated server build",
            ),
            what=f"creating role {name}",
        )
        roles[name] = role
        newly_created.append(role)
        progress.steps_done += 1
        progress.log.append(f"Created role {name}")

    return roles, newly_created


async def create_game_roles(
    guild: discord.Guild,
    progress: BuildProgress,
) -> tuple[dict[str, discord.Role], list[discord.Role]]:
    """
    Create one role per game in GAME_DATABASE.
    Role name = game.name (e.g. "Minecraft", "Valorant").
    Returns (game_roles_by_key, newly_created_list).
    """
    game_roles: dict[str, discord.Role] = {}  # key → Role
    newly_created: list[discord.Role] = []
    existing = {r.name: r for r in guild.roles}

    for game in sorted(GAME_DATABASE.values(), key=lambda g: g.name):
        if game.name in existing:
            game_roles[game.key] = existing[game.name]
            continue
        role = await _with_retries(
            lambda gn=game.name: guild.create_role(
                name=gn,
                permissions=discord.Permissions(),
                colour=discord.Colour.blurple(),
                hoist=False,
                reason="Automated server build — game role",
            ),
            what=f"creating game role {game.name}",
        )
        game_roles[game.key] = role
        newly_created.append(role)
        progress.steps_done += 1
        progress.log.append(f"Created game role {game.name}")

    return game_roles, newly_created


# ---------------------------------------------------------------------------
# Discord UI — in-server game-selection components
# ---------------------------------------------------------------------------

def _game_role_toggle(
    guild: discord.Guild,
    game: Game,
    member: discord.Member,
) -> Optional[discord.Role]:
    """Look up the game's role in the guild by name."""
    return discord.utils.get(guild.roles, name=game.name)


class SearchGameModal(discord.ui.Modal, title="Search for a Game"):
    """Modal that accepts a search query and returns matching games."""

    query = discord.ui.TextInput(
        label="Game name",
        placeholder="e.g.  mine  •  valo  •  among  •  fort",
        min_length=1,
        max_length=50,
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        results = search_games(self.query.value)
        if not results:
            await interaction.response.send_message(
                f"❌ No games found matching **{self.query.value}**. Try a shorter search term.",
                ephemeral=True,
            )
            return

        member = interaction.user
        embed = discord.Embed(
            title=f"🔍 Results for \"{self.query.value}\"",
            description="Click a game to add or remove its role.",
            colour=discord.Colour.blurple(),
        )
        view = SearchResultsView(results=results[:10], member=member)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class _GameToggleButton(discord.ui.Button):
    """A single button that toggles a game role for the clicking member."""

    def __init__(self, game: Game, has_role: bool, row: int = 0) -> None:
        label = f"✅ {game.name}" if has_role else game.name
        super().__init__(
            label=label[:80],
            style=discord.ButtonStyle.success if has_role else discord.ButtonStyle.secondary,
            row=row,
        )
        self.game = game
        self.has_role = has_role

    async def callback(self, interaction: discord.Interaction) -> None:
        guild  = interaction.guild
        member = interaction.user
        role   = _game_role_toggle(guild, self.game, member)

        if role is None:
            await interaction.response.send_message(
                f"⚠️ The **{self.game.name}** role does not exist on this server yet. "
                "Ask the server owner to run a server build or update.",
                ephemeral=True,
            )
            return

        if self.has_role:
            await member.remove_roles(role, reason="Game deselected by user")
            await interaction.response.send_message(
                f"❌ Removed **{self.game.name}**. Those channels are now hidden.",
                ephemeral=True,
            )
        else:
            await member.add_roles(role, reason="Game selected by user")
            await interaction.response.send_message(
                f"✅ Added **{self.game.name}**! You can now see the {self.game.name} channels.",
                ephemeral=True,
            )


class SearchResultsView(discord.ui.View):
    """Ephemeral view showing search results as toggle buttons."""

    def __init__(self, results: list[Game], member: discord.Member) -> None:
        super().__init__(timeout=120)
        member_role_names = {r.name for r in member.roles}
        for i, game in enumerate(results[:10]):
            self.add_item(
                _GameToggleButton(game=game, has_role=game.name in member_role_names, row=i // 4)
            )


class _BrowseGamesSelect(discord.ui.Select):
    """
    A multi-select dropdown for a slice of the game list.
    Pre-fills options the user already has as selected.
    On submit, assigns / removes roles to match the new selection.
    """

    def __init__(self, games: list[Game], member: discord.Member, label_prefix: str = "") -> None:
        member_role_names = {r.name for r in member.roles}
        options = [
            discord.SelectOption(
                label=game.name,
                value=game.key,
                default=game.name in member_role_names,
                emoji="✅" if game.name in member_role_names else "🎮",
            )
            for game in games
        ]
        super().__init__(
            placeholder=f"Pick games{f' ({label_prefix})' if label_prefix else ''}…",
            min_values=0,
            max_values=len(options),
            options=options,
        )
        self._games = games

    async def callback(self, interaction: discord.Interaction) -> None:
        guild  = interaction.guild
        member = interaction.user
        want   = set(self.values)

        added, removed = [], []
        for game in self._games:
            role = discord.utils.get(guild.roles, name=game.name)
            if role is None:
                continue
            has  = role in member.roles
            need = game.key in want
            if need and not has:
                await member.add_roles(role, reason="Game selected by user")
                added.append(game.name)
            elif not need and has:
                await member.remove_roles(role, reason="Game deselected by user")
                removed.append(game.name)

        parts = []
        if added:
            parts.append(f"✅ Added: {', '.join(added)}")
        if removed:
            parts.append(f"❌ Removed: {', '.join(removed)}")
        await interaction.response.send_message(
            "\n".join(parts) if parts else "No changes made.",
            ephemeral=True,
        )


class BrowseGamesView(discord.ui.View):
    """
    Ephemeral view with one or two multi-select dropdowns covering all games.
    Discord limits a Select menu to 25 options, so games are split across
    up to two menus (alphabetically: A–M and N–Z) when the list exceeds 25.
    """

    def __init__(self, member: discord.Member) -> None:
        super().__init__(timeout=120)
        games = sorted(GAME_DATABASE.values(), key=lambda g: g.name)
        first_chunk  = games[:25]
        second_chunk = games[25:]
        self.add_item(_BrowseGamesSelect(first_chunk, member, "A–M" if second_chunk else ""))
        if second_chunk:
            self.add_item(_BrowseGamesSelect(second_chunk, member, "N–Z"))


class PopularGamesView(discord.ui.View):
    """
    Ephemeral view with quick-toggle buttons for the most popular games.
    """

    def __init__(self, member: discord.Member) -> None:
        super().__init__(timeout=120)
        member_role_names = {r.name for r in member.roles}
        popular = [GAME_DATABASE[k] for k in POPULAR_GAME_KEYS if k in GAME_DATABASE]
        for i, game in enumerate(popular):
            self.add_item(
                _GameToggleButton(game=game, has_role=game.name in member_role_names, row=i // 4)
            )


class _RemoveGameButton(discord.ui.Button):
    """Button that removes a specific game role from the user."""

    def __init__(self, game: Game, row: int = 0) -> None:
        super().__init__(
            label=f"❌ Remove {game.name}",
            style=discord.ButtonStyle.danger,
            row=row,
        )
        self.game = game

    async def callback(self, interaction: discord.Interaction) -> None:
        role = discord.utils.get(interaction.guild.roles, name=self.game.name)
        if role and role in interaction.user.roles:
            await interaction.user.remove_roles(role, reason="Game deselected from My Games")
            await interaction.response.send_message(
                f"❌ Removed **{self.game.name}**. Those channels are now hidden.",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                f"You don't currently have the **{self.game.name}** role.",
                ephemeral=True,
            )


class MyGamesView(discord.ui.View):
    """
    Ephemeral view listing the user's current game roles with individual
    Remove buttons.
    """

    def __init__(self, member: discord.Member) -> None:
        super().__init__(timeout=120)
        member_role_names = {r.name for r in member.roles}
        my_games = [g for g in GAME_DATABASE.values() if g.name in member_role_names]
        my_games.sort(key=lambda g: g.name)
        for i, game in enumerate(my_games[:20]):   # cap at 20 to stay within row limits
            self.add_item(_RemoveGameButton(game=game, row=i // 4))
        self._empty = len(my_games) == 0

    @property
    def is_empty(self) -> bool:
        return self._empty


class GameSelectionView(discord.ui.View):
    """
    Persistent view posted in the ✨・customize-your-experience channel.
    Survives bot restarts — registered with discord_bot.add_view() on startup.
    """

    def __init__(self) -> None:
        super().__init__(timeout=None)   # persistent

    @discord.ui.button(
        label="🎮 Browse Games",
        custom_id="gsv:browse",
        style=discord.ButtonStyle.primary,
        row=0,
    )
    async def browse_games(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        view = BrowseGamesView(member=interaction.user)
        embed = discord.Embed(
            title="🎮 Browse Games",
            description=(
                "Use the dropdown(s) below to select or deselect games.\n"
                "Your changes take effect immediately — selected games will appear in your channel list."
            ),
            colour=discord.Colour.blurple(),
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(
        label="🔍 Search Game",
        custom_id="gsv:search",
        style=discord.ButtonStyle.secondary,
        row=0,
    )
    async def search_game(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await interaction.response.send_modal(SearchGameModal())

    @discord.ui.button(
        label="⭐ Popular Games",
        custom_id="gsv:popular",
        style=discord.ButtonStyle.secondary,
        row=0,
    )
    async def popular_games(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        view = PopularGamesView(member=interaction.user)
        embed = discord.Embed(
            title="⭐ Popular Games",
            description="Quickly add or remove the most popular games.",
            colour=discord.Colour.gold(),
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(
        label="❤️ My Games",
        custom_id="gsv:mygames",
        style=discord.ButtonStyle.success,
        row=0,
    )
    async def my_games(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        view = MyGamesView(member=interaction.user)
        if view.is_empty:
            await interaction.response.send_message(
                "You haven't selected any games yet.\n"
                "Use **Browse Games**, **Search**, or **Popular Games** to get started!",
                ephemeral=True,
            )
            return
        embed = discord.Embed(
            title="❤️ My Games",
            description="Your currently selected games. Click to remove any.",
            colour=discord.Colour.green(),
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


def _customize_embed() -> discord.Embed:
    """Build the professional embed posted in ✨・customize-your-experience."""
    embed = discord.Embed(
        title="✨ Customize Your Experience",
        description=(
            "**Select the games you play** to unlock dedicated channels just for you.\n\n"
            "Only channels for your selected games will be visible — keeping your server "
            "clean and focused on what you actually play.\n\n"
            "You can change your selection at any time using the buttons below."
        ),
        colour=discord.Colour.purple(),
    )
    embed.add_field(
        name="🎮 Browse Games",
        value="Browse the full list and pick multiple games at once.",
        inline=True,
    )
    embed.add_field(
        name="🔍 Search Game",
        value="Type a game name to find it instantly.",
        inline=True,
    )
    embed.add_field(
        name="⭐ Popular Games",
        value="Quick access to the most popular titles.",
        inline=True,
    )
    embed.add_field(
        name="❤️ My Games",
        value="View and manage the games you've already selected.",
        inline=True,
    )
    embed.set_footer(text="Your role assignments update instantly when you click.")
    return embed


# ---------------------------------------------------------------------------
# build_server()
# ---------------------------------------------------------------------------

async def build_server(
    guild: discord.Guild,
    on_progress=None,
) -> BuildProgress:
    """
    Build the full server structure:
      - Staff hierarchy roles + one role per game
      - INFORMATION, COMMUNITY, CUSTOMIZE, VOICE, STAFF, BOTS, LOGS categories
      - One hidden category per game (visible only to the matching game role)
      - Persistent game-selection embed + view in ✨・customize-your-experience

    All created text-channel topics are tagged with BOT_MANAGED_TOPIC.
    On failure, rolls back every category/role that was newly created.
    """
    progress        = BuildProgress()
    created_cats: list[discord.CategoryChannel] = []
    newly_roles:  list[discord.Role]            = []

    async def notify() -> None:
        if on_progress:
            await on_progress(progress)

    try:
        # ── Roles ──────────────────────────────────────────────────────────
        staff_roles, new_staff  = await create_staff_roles(guild, progress)
        newly_roles.extend(new_staff)
        game_roles,  new_games  = await create_game_roles(guild, progress)
        newly_roles.extend(new_games)
        await notify()

        staff_visible = ["👑 Owner", "🛡 Administrator", "⚔ Moderator"]
        staff_role_objs = [staff_roles[n] for n in staff_visible if n in staff_roles]

        # ── INFORMATION ────────────────────────────────────────────────────
        info_ro = _overwrites_read_only(guild, staff_roles, ["👑 Owner", "🛡 Administrator"])
        info_cat = await _create_category(guild, CAT_INFORMATION, progress, {
            guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=False),
        })
        created_cats.append(info_cat)
        for ch in INFO_TEXT_CHANNELS:
            ow = _overwrites_bot_only(guild, staff_roles) if ch == "welcome" else info_ro
            await _create_text_channel(guild, ch, info_cat, progress, ow)
        await notify()

        # ── COMMUNITY ──────────────────────────────────────────────────────
        comm_cat = await _create_category(guild, CAT_COMMUNITY, progress, _overwrites_open(guild))
        created_cats.append(comm_cat)
        for ch in COMMUNITY_CHANNELS:
            await _create_text_channel(guild, ch, comm_cat, progress, _overwrites_open(guild))
        await notify()

        # ── CUSTOMIZE YOUR EXPERIENCE ──────────────────────────────────────
        cust_cat = await _create_category(guild, CAT_CUSTOMIZE, progress, _overwrites_open(guild))
        created_cats.append(cust_cat)
        customize_channel = await _create_text_channel(
            guild,
            CUSTOMIZE_CHANNELS[0],
            cust_cat,
            progress,
            _overwrites_bot_only(guild, staff_roles),
            topic=f"Select your games here! {BOT_MANAGED_TOPIC}",
        )
        await notify()

        # ── VOICE ──────────────────────────────────────────────────────────
        voice_cat = await _create_category(guild, CAT_VOICE, progress, _overwrites_open(guild))
        created_cats.append(voice_cat)
        for vc in VOICE_CHANNELS:
            await _create_voice_channel(guild, vc, voice_cat, progress, _overwrites_open(guild))
        await notify()

        # ── STAFF ──────────────────────────────────────────────────────────
        staff_ow = _overwrites_hidden_except(guild, staff_roles, staff_visible)
        staff_cat = await _create_category(guild, CAT_STAFF, progress, staff_ow)
        created_cats.append(staff_cat)
        for ch in STAFF_TEXT_CHANNELS:
            await _create_text_channel(guild, ch, staff_cat, progress, staff_ow)
        for vc in STAFF_VOICE_CHANNELS:
            await _create_voice_channel(guild, vc, staff_cat, progress, staff_ow)
        await notify()

        # ── BOTS ───────────────────────────────────────────────────────────
        bots_ow = _overwrites_read_only(
            guild, staff_roles, ["👑 Owner", "🛡 Administrator", "⚔ Moderator", "🤖 Bots"]
        )
        bots_cat = await _create_category(guild, CAT_BOTS, progress, _overwrites_open(guild))
        created_cats.append(bots_cat)
        for ch in BOT_CHANNELS:
            await _create_text_channel(guild, ch, bots_cat, progress, bots_ow)
        await notify()

        # ── LOGS ───────────────────────────────────────────────────────────
        logs_ow = _overwrites_hidden_except(guild, staff_roles, staff_visible)
        logs_cat = await _create_category(guild, CAT_LOGS, progress, logs_ow)
        created_cats.append(logs_cat)
        for ch in LOG_CHANNELS:
            await _create_text_channel(guild, ch, logs_cat, progress, logs_ow)
        await notify()

        # ── GAME CATEGORIES (one per game, hidden until role assigned) ─────
        for game in sorted(GAME_DATABASE.values(), key=lambda g: g.name):
            g_role = game_roles.get(game.key)
            if g_role is None:
                continue
            game_ow = _overwrites_game(guild, g_role, staff_role_objs)
            game_cat = await _create_category(guild, _game_category_name(game), progress, game_ow)
            created_cats.append(game_cat)
            for ch in game.channels:
                await _create_text_channel(guild, ch, game_cat, progress, game_ow)
            for vc in game.voice_channels:
                await _create_voice_channel(guild, vc, game_cat, progress, game_ow)
            await notify()

        # ── Post customize embed + persistent view ─────────────────────────
        try:
            await customize_channel.send(
                embed=_customize_embed(),
                view=GameSelectionView(),
            )
            progress.log.append("Posted game-selection embed in customize channel")
        except discord.HTTPException as exc:
            logger.warning("Could not post customize embed: %s", exc)

        # ── Assign Owner role to the configured Discord user ───────────────
        if DISCORD_USER_ID:
            owner_role = staff_roles.get("👑 Owner")
            if owner_role:
                try:
                    member = guild.get_member(DISCORD_USER_ID) or await guild.fetch_member(DISCORD_USER_ID)
                    await member.add_roles(owner_role, reason="Automated owner role assignment")
                    progress.log.append(f"Assigned 👑 Owner role to {member}")
                except (discord.NotFound, discord.HTTPException) as exc:
                    logger.warning("Could not assign Owner role to DISCORD_USER_ID=%s: %s", DISCORD_USER_ID, exc)

        return progress

    except Exception:
        logger.exception("Server build failed — rolling back created items")
        for cat in reversed(created_cats):
            try:
                for ch in list(cat.channels):
                    await ch.delete(reason="Rollback after failed build")
                await cat.delete(reason="Rollback after failed build")
            except discord.HTTPException:
                logger.warning("Could not delete category %s during rollback", cat.name)
        for role in reversed(newly_roles):
            try:
                await role.delete(reason="Rollback after failed build")
            except discord.HTTPException:
                logger.warning("Could not delete role %s during rollback", role.name)
        raise


# ---------------------------------------------------------------------------
# update_server()
# ---------------------------------------------------------------------------

async def update_server(
    guild: discord.Guild,
    on_progress=None,
) -> BuildProgress:
    """
    Synchronise the server structure without duplicating anything.

    Strategy:
      - Create any missing staff / game roles.
      - For each expected category: create if absent (by name).
      - For each expected channel in each category: create if absent.
      - If the customize channel exists but has no bot embed, re-post it.
      - User-created channels (topic ≠ BOT_MANAGED_TOPIC, not in a bot
        category) are never touched.
    """
    progress = BuildProgress()

    async def notify() -> None:
        if on_progress:
            await on_progress(progress)

    # ── Ensure roles exist ─────────────────────────────────────────────────
    staff_roles, _ = await create_staff_roles(guild, progress)
    game_roles,  _ = await create_game_roles(guild, progress)
    await notify()

    staff_visible   = ["👑 Owner", "🛡 Administrator", "⚔ Moderator"]
    staff_role_objs = [staff_roles[n] for n in staff_visible if n in staff_roles]

    # Helper: get or create a category by name
    async def _get_or_create_category(name: str, overwrites: dict) -> discord.CategoryChannel:
        existing = discord.utils.get(guild.categories, name=name)
        if existing:
            return existing
        return await _create_category(guild, name, progress, overwrites)

    # Helper: get or create a text channel by name within a category
    async def _ensure_text(name: str, cat: discord.CategoryChannel, ow: dict, topic: str = BOT_MANAGED_TOPIC) -> discord.TextChannel:
        existing = discord.utils.get(cat.text_channels, name=name)
        if existing:
            return existing
        return await _create_text_channel(guild, name, cat, progress, ow, topic)

    # Helper: get or create a voice channel within a category
    async def _ensure_voice(name: str, cat: discord.CategoryChannel, ow: dict) -> discord.VoiceChannel:
        existing = discord.utils.get(cat.voice_channels, name=name)
        if existing:
            return existing
        return await _create_voice_channel(guild, name, cat, progress, ow)

    # ── INFORMATION ────────────────────────────────────────────────────────
    info_ro  = _overwrites_read_only(guild, staff_roles, ["👑 Owner", "🛡 Administrator"])
    info_cat = await _get_or_create_category(CAT_INFORMATION, {
        guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=False),
    })
    for ch in INFO_TEXT_CHANNELS:
        ow = _overwrites_bot_only(guild, staff_roles) if ch == "welcome" else info_ro
        await _ensure_text(ch, info_cat, ow)
    await notify()

    # ── COMMUNITY ──────────────────────────────────────────────────────────
    comm_cat = await _get_or_create_category(CAT_COMMUNITY, _overwrites_open(guild))
    for ch in COMMUNITY_CHANNELS:
        await _ensure_text(ch, comm_cat, _overwrites_open(guild))
    await notify()

    # ── CUSTOMIZE ──────────────────────────────────────────────────────────
    cust_cat  = await _get_or_create_category(CAT_CUSTOMIZE, _overwrites_open(guild))
    cust_ch   = await _ensure_text(
        CUSTOMIZE_CHANNELS[0], cust_cat,
        _overwrites_bot_only(guild, staff_roles),
        topic=f"Select your games here! {BOT_MANAGED_TOPIC}",
    )
    # Re-post the embed only if the bot has no messages in this channel
    try:
        has_embed = False
        async for msg in cust_ch.history(limit=20):
            if msg.author == guild.me and msg.embeds:
                has_embed = True
                break
        if not has_embed:
            await cust_ch.send(embed=_customize_embed(), view=GameSelectionView())
            progress.log.append("Re-posted game-selection embed in customize channel")
    except discord.HTTPException as exc:
        logger.warning("Could not check/post customize embed during update: %s", exc)
    await notify()

    # ── VOICE ──────────────────────────────────────────────────────────────
    voice_cat = await _get_or_create_category(CAT_VOICE, _overwrites_open(guild))
    for vc in VOICE_CHANNELS:
        await _ensure_voice(vc, voice_cat, _overwrites_open(guild))
    await notify()

    # ── STAFF ──────────────────────────────────────────────────────────────
    staff_ow  = _overwrites_hidden_except(guild, staff_roles, staff_visible)
    staff_cat = await _get_or_create_category(CAT_STAFF, staff_ow)
    for ch in STAFF_TEXT_CHANNELS:
        await _ensure_text(ch, staff_cat, staff_ow)
    for vc in STAFF_VOICE_CHANNELS:
        await _ensure_voice(vc, staff_cat, staff_ow)
    await notify()

    # ── BOTS ───────────────────────────────────────────────────────────────
    bots_ow  = _overwrites_read_only(
        guild, staff_roles, ["👑 Owner", "🛡 Administrator", "⚔ Moderator", "🤖 Bots"]
    )
    bots_cat = await _get_or_create_category(CAT_BOTS, _overwrites_open(guild))
    for ch in BOT_CHANNELS:
        await _ensure_text(ch, bots_cat, bots_ow)
    await notify()

    # ── LOGS ───────────────────────────────────────────────────────────────
    logs_ow  = _overwrites_hidden_except(guild, staff_roles, staff_visible)
    logs_cat = await _get_or_create_category(CAT_LOGS, logs_ow)
    for ch in LOG_CHANNELS:
        await _ensure_text(ch, logs_cat, logs_ow)
    await notify()

    # ── GAME CATEGORIES ────────────────────────────────────────────────────
    for game in sorted(GAME_DATABASE.values(), key=lambda g: g.name):
        g_role = game_roles.get(game.key)
        if g_role is None:
            continue
        game_ow  = _overwrites_game(guild, g_role, staff_role_objs)
        game_cat = await _get_or_create_category(_game_category_name(game), game_ow)
        for ch in game.channels:
            await _ensure_text(ch, game_cat, game_ow)
        for vc in game.voice_channels:
            await _ensure_voice(vc, game_cat, game_ow)
        await notify()

    return progress


# ---------------------------------------------------------------------------
# reset_server()
# ---------------------------------------------------------------------------

async def reset_server(
    guild: discord.Guild,
    on_progress=None,
) -> BuildProgress:
    """
    Remove all bot-managed structure: game categories, static categories,
    staff hierarchy roles, and game roles.

    User-created categories/channels (names not matching the bot's known
    structure) are left untouched.
    """
    progress = BuildProgress()

    async def notify() -> None:
        if on_progress:
            await on_progress(progress)

    known_game_cat_names = {_game_category_name(g) for g in GAME_DATABASE.values()}
    all_known_cats = STATIC_CATEGORY_NAMES | known_game_cat_names

    # Delete known bot categories + their children
    for cat in list(guild.categories):
        if cat.name not in all_known_cats:
            continue
        for ch in list(cat.channels):
            try:
                await _with_retries(lambda c=ch: c.delete(reason="Server reset"), what=f"deleting {ch.name}")
                progress.steps_done += 1
                progress.log.append(f"Deleted {ch.name}")
            except discord.HTTPException:
                logger.warning("Could not delete channel %s during reset", ch.name)
        try:
            await _with_retries(lambda c=cat: c.delete(reason="Server reset"), what=f"deleting category {cat.name}")
            progress.steps_done += 1
            progress.log.append(f"Deleted category {cat.name}")
        except discord.HTTPException:
            logger.warning("Could not delete category %s during reset", cat.name)
        await notify()

    # Delete game roles
    game_names = {g.name for g in GAME_DATABASE.values()}
    for role in list(guild.roles):
        if role.name in game_names:
            try:
                await _with_retries(lambda r=role: r.delete(reason="Server reset"), what=f"deleting role {role.name}")
                progress.steps_done += 1
                progress.log.append(f"Deleted role {role.name}")
            except discord.HTTPException:
                logger.warning("Could not delete game role %s during reset", role.name)

    # Delete staff roles
    staff_names = {name for name, *_ in ROLE_SPECS}
    for role in list(guild.roles):
        if role.name in staff_names:
            try:
                await _with_retries(lambda r=role: r.delete(reason="Server reset"), what=f"deleting role {role.name}")
                progress.steps_done += 1
                progress.log.append(f"Deleted role {role.name}")
            except discord.HTTPException:
                logger.warning("Could not delete staff role %s during reset", role.name)

    await notify()
    return progress


# ---------------------------------------------------------------------------
# Discord event handlers
# ---------------------------------------------------------------------------

@discord_bot.event
async def on_ready() -> None:
    logger.info("Discord bot logged in as %s (id=%s)", discord_bot.user, discord_bot.user.id)
    # Register the persistent GameSelectionView so existing messages' buttons
    # still work after a bot restart.
    discord_bot.add_view(GameSelectionView())


def get_guild_by_id(guild_id: int) -> Optional[discord.Guild]:
    return discord_bot.get_guild(guild_id)


# ---------------------------------------------------------------------------
# Telegram bot
# ---------------------------------------------------------------------------

router = Router()


class BuildStates(StatesGroup):
    choosing_server        = State()
    choosing_update_server = State()
    confirming_reset       = State()
    choosing_reset_server  = State()


def owner_only(handler):
    """Restrict a handler to the configured OWNER_ID Telegram user."""
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


# ── Keyboard builders ───────────────────────────────────────────────────────

def home_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏗 Build Server",   callback_data="menu:build")],
        [InlineKeyboardButton(text="🔄 Update Server",  callback_data="menu:update")],
        [InlineKeyboardButton(text="🗑 Reset Server",   callback_data="menu:reset")],
        [InlineKeyboardButton(text="⚙ Settings",        callback_data="menu:settings")],
        [InlineKeyboardButton(text="📊 Status",         callback_data="menu:status")],
    ])


def home_text() -> str:
    return (
        "🏠 <b>Home — Server Builder Control Panel</b>\n\n"
        "Use the menu below to manage your Discord server structure."
    )


def guild_list_keyboard(action: str) -> InlineKeyboardMarkup:
    """Show every server the Discord bot is in, tagged with the intended action."""
    guilds = list(discord_bot.guilds)
    rows = [
        [InlineKeyboardButton(text=f"🌐 {g.name}", callback_data=f"{action}:{g.id}")]
        for g in guilds
    ]
    rows.append([InlineKeyboardButton(text="🏠 Home", callback_data="menu:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_confirm_keyboard(guild_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Start Build",  callback_data=f"build:start:{guild_id}")],
        [InlineKeyboardButton(text="🏠 Cancel",        callback_data="menu:home")],
    ])


def reset_confirm_keyboard(guild_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Confirm Reset", callback_data=f"reset:confirm:{guild_id}")],
        [InlineKeyboardButton(text="🏠 Cancel",         callback_data="menu:home")],
    ])


# ── Handlers ────────────────────────────────────────────────────────────────

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


@router.callback_query(F.data == "menu:status")
@owner_only
async def cb_status(callback: CallbackQuery, state: FSMContext) -> None:
    latency_ms = round(discord_bot.latency * 1000) if discord_bot.latency else 0
    text = (
        "📊 <b>Status</b>\n\n"
        f"Discord bot: {'🟢 Online' if discord_bot.is_ready() else '🔴 Offline'}\n"
        f"Connected servers: <b>{len(discord_bot.guilds)}</b>\n"
        f"Gateway latency: <b>{latency_ms} ms</b>\n"
        f"Games in database: <b>{len(GAME_DATABASE)}</b>"
    )
    await callback.message.edit_text(text, reply_markup=home_keyboard())
    await callback.answer()


@router.callback_query(F.data == "menu:settings")
@owner_only
async def cb_settings(callback: CallbackQuery, state: FSMContext) -> None:
    discord_uid_line = (
        f"Discord owner user ID: <code>{DISCORD_USER_ID}</code>"
        if DISCORD_USER_ID else
        "Discord owner user ID: <i>not set (DISCORD_USER_ID env var)</i>"
    )
    text = (
        "⚙ <b>Settings</b>\n\n"
        f"Telegram owner ID: <code>{OWNER_ID}</code>\n"
        f"{discord_uid_line}\n\n"
        "Environment variables are managed in the Railway dashboard."
    )
    await callback.message.edit_text(text, reply_markup=home_keyboard())
    await callback.answer()


# ── Build flow ───────────────────────────────────────────────────────────────

@router.callback_query(F.data == "menu:build")
@owner_only
async def cb_build(callback: CallbackQuery, state: FSMContext) -> None:
    if not discord_bot.guilds:
        await callback.message.edit_text(
            "⚠ The Discord bot is not in any server.\n"
            "Invite it with Administrator permission first, then try again.",
            reply_markup=home_keyboard(),
        )
        await callback.answer()
        return
    await state.set_state(BuildStates.choosing_server)
    await callback.message.edit_text(
        "🏗 <b>Build Server</b>\n\nSelect a Discord server to build:",
        reply_markup=guild_list_keyboard("do_build"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("do_build:"))
@owner_only
async def cb_do_build_select(callback: CallbackQuery, state: FSMContext) -> None:
    guild_id = int(callback.data.split(":", 1)[1])
    guild    = get_guild_by_id(guild_id)
    if guild is None:
        await callback.answer("Server not found — it may have removed the bot.", show_alert=True)
        return
    await state.clear()
    await callback.message.edit_text(
        f"🏗 <b>Ready to Build: {guild.name}</b>\n\n"
        f"This will create:\n"
        f"• Staff roles (Owner, Administrator, Moderator, Gamer, Bots, Member)\n"
        f"• One role per game ({len(GAME_DATABASE)} games)\n"
        f"• INFORMATION, COMMUNITY, CUSTOMIZE, VOICE, STAFF, BOTS, LOGS\n"
        f"• {len(GAME_DATABASE)} hidden game categories (visible per role)\n"
        f"• Game-selection embed in ✨・customize-your-experience\n\n"
        "Continue?",
        reply_markup=build_confirm_keyboard(guild_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("build:start:"))
@owner_only
async def cb_build_start(callback: CallbackQuery, state: FSMContext) -> None:
    guild_id = int(callback.data.split(":", 2)[2])
    guild    = get_guild_by_id(guild_id)
    if guild is None:
        await callback.message.edit_text("⚠ Server no longer available.", reply_markup=home_keyboard())
        await callback.answer()
        return

        prog_msg = await callback.message.edit_text(
        f'🏗 <b>Building "{guild.name}"…</b>\n\nStarting, please wait…'
    )

        await callback.answer()

        last_step = -1

async def on_progress(p: BuildProgress) -> None:
    nonlocal last_step

    if p.steps_done == last_step:
        return

    last_step = p.steps_done
    recent = "\n".join(f"• {ln}" for ln in p.log[-6:])

    try:
        await prog_msg.edit_text(
            f'🏗 <b>Building "{guild.name}"…</b>\n\n'
            f'Steps completed: <b>{p.steps_done}</b>\n\n{recent}'
        )
    except Exception:
        pass
    try:
        p = await build_server(guild, on_progress=on_progress)
        await prog_msg.edit_text(
            "✅ <b>Build Complete</b>\n\n"
            f"Server: <b>{guild.name}</b>\n"
            f"Steps completed: <b>{p.steps_done}</b>\n\n"
            "Roles, categories, channels, permissions, and the game-selection "
            "embed have all been created successfully.",
            reply_markup=home_keyboard(),
        )
        logger.info("Build complete — guild_id=%s (%s)", guild.id, guild.name)
    except Exception as exc:
        logger.exception("Build failed — guild_id=%s", guild.id)
        await prog_msg.edit_text(
            "❌ <b>Build Failed</b>\n\n"
            f"Error: <code>{exc}</code>\n\n"
            "Partially created items have been rolled back.\n"
            "Ensure the bot has Administrator permission and try again.",
            reply_markup=home_keyboard(),
        )


# ── Update flow ──────────────────────────────────────────────────────────────

@router.callback_query(F.data == "menu:update")
@owner_only
async def cb_update(callback: CallbackQuery, state: FSMContext) -> None:
    if not discord_bot.guilds:
        await callback.message.edit_text(
            "⚠ The Discord bot is not in any server.",
            reply_markup=home_keyboard(),
        )
        await callback.answer()
        return
    await state.set_state(BuildStates.choosing_update_server)
    await callback.message.edit_text(
        "🔄 <b>Update Server</b>\n\nSelect a Discord server to sync:",
        reply_markup=guild_list_keyboard("do_update"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("do_update:"))
@owner_only
async def cb_do_update(callback: CallbackQuery, state: FSMContext) -> None:
    guild_id = int(callback.data.split(":", 1)[1])
    guild    = get_guild_by_id(guild_id)
    if guild is None:
        await callback.answer("Server not found.", show_alert=True)
        return
    await state.clear()

    prog_msg = await callback.message.edit_text(
        f"🔄 <b>Updating "{guild.name}"…</b>\n\nChecking structure, please wait…"
    )
    await callback.answer()

    last_step = -1

    async def on_progress(p: BuildProgress) -> None:
        nonlocal last_step
        if p.steps_done == last_step:
            return
        last_step = p.steps_done
        recent = "\n".join(f"• {ln}" for ln in p.log[-6:])
        try:
            await prog_msg.edit_text(
                f"🔄 <b>Updating "{guild.name}"…</b>\n\n"
                f"Items updated: <b>{p.steps_done}</b>\n\n{recent or 'Checking…'}"
            )
        except Exception:
            pass

    try:
        p = await update_server(guild, on_progress=on_progress)
        summary = f"Added <b>{p.steps_done}</b> missing item(s)." if p.steps_done else "Everything was already up to date."
        await prog_msg.edit_text(
            f"✅ <b>Update Complete — {guild.name}</b>\n\n{summary}",
            reply_markup=home_keyboard(),
        )
        logger.info("Update complete — guild_id=%s (%s), steps=%d", guild.id, guild.name, p.steps_done)
    except Exception as exc:
        logger.exception("Update failed — guild_id=%s", guild.id)
        await prog_msg.edit_text(
            f"❌ <b>Update Failed</b>\n\nError: <code>{exc}</code>",
            reply_markup=home_keyboard(),
        )


# ── Reset flow ───────────────────────────────────────────────────────────────

@router.callback_query(F.data == "menu:reset")
@owner_only
async def cb_reset(callback: CallbackQuery, state: FSMContext) -> None:
    if not discord_bot.guilds:
        await callback.message.edit_text(
            "⚠ The Discord bot is not in any server.",
            reply_markup=home_keyboard(),
        )
        await callback.answer()
        return
    await state.set_state(BuildStates.choosing_reset_server)
    await callback.message.edit_text(
        "🗑 <b>Reset Server</b>\n\nSelect a Discord server to reset:",
        reply_markup=guild_list_keyboard("do_reset"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("do_reset:"))
@owner_only
async def cb_do_reset_select(callback: CallbackQuery, state: FSMContext) -> None:
    guild_id = int(callback.data.split(":", 1)[1])
    guild    = get_guild_by_id(guild_id)
    if guild is None:
        await callback.answer("Server not found.", show_alert=True)
        return
    await state.set_state(BuildStates.confirming_reset)
    await callback.message.edit_text(
        f"⚠️ <b>Confirm Reset — {guild.name}</b>\n\n"
        "This will permanently delete <b>all</b> bot-created roles, categories, "
        "and channels from this server.\n\n"
        "<b>This cannot be undone.</b> User-created channels will not be touched.",
        reply_markup=reset_confirm_keyboard(guild_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("reset:confirm:"))
@owner_only
async def cb_reset_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    guild_id = int(callback.data.split(":", 2)[2])
    guild    = get_guild_by_id(guild_id)
    if guild is None:
        await callback.message.edit_text("⚠ Server no longer available.", reply_markup=home_keyboard())
        await callback.answer()
        return
    await state.clear()

    prog_msg = await callback.message.edit_text(
        f"🗑 <b>Resetting "{guild.name}"…</b>\n\nRemoving bot-managed items…"
    )
    await callback.answer()

    last_step = -1

    async def on_progress(p: BuildProgress) -> None:
        nonlocal last_step
        if p.steps_done == last_step:
            return
        last_step = p.steps_done
        try:
            await prog_msg.edit_text(
                f"🗑 <b>Resetting "{guild.name}"…</b>\n\n"
                f"Items removed: <b>{p.steps_done}</b>"
            )
        except Exception:
            pass

    try:
        p = await reset_server(guild, on_progress=on_progress)
        await prog_msg.edit_text(
            f"✅ <b>Reset Complete — {guild.name}</b>\n\n"
            f"Removed <b>{p.steps_done}</b> bot-managed item(s).",
            reply_markup=home_keyboard(),
        )
        logger.info("Reset complete — guild_id=%s (%s), removed=%d", guild.id, guild.name, p.steps_done)
    except Exception as exc:
        logger.exception("Reset failed — guild_id=%s", guild.id)
        await prog_msg.edit_text(
            f"❌ <b>Reset Failed</b>\n\nError: <code>{exc}</code>",
            reply_markup=home_keyboard(),
        )


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

async def main() -> None:
    bot        = Bot(token=TELEGRAM_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
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
