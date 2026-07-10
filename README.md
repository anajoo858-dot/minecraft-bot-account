# Discord Server Builder

A Telegram control panel that automatically builds a complete, professional
Discord server structure — roles, categories, text/voice channels, and
permissions — tailored to the games you select.

## How it works

1. You DM your Telegram bot (only the configured `OWNER_ID` can use it).
2. `🏗 Build Server` lists every Discord server the Discord bot has joined.
3. Pick a server, then pick one or more games from the built-in database
   (or search by typing part of a name, e.g. `mine` → Minecraft).
4. Confirm, and the bot builds:
   - Roles: 👑 Owner, 🛡 Administrator, ⚔ Moderator, 🎮 Gamer, 🤖 Bots, 👤 Member
   - Categories: 📢 INFORMATION, 💬 COMMUNITY, 🎮 one per selected game, 👥 VOICE,
     🛡 STAFF, 🤖 BOTS, 📜 LOGS
   - Channel permissions matching each channel's purpose (read-only
     announcements, hidden staff/logs, open community chat, etc.)
5. Progress is reported live in Telegram; a success (or failure + rollback)
   message follows.

## Requirements

- Python 3.12+
- A Telegram bot token ([@BotFather](https://t.me/BotFather))
- A Discord bot token, invited to your server(s) with **Administrator**
  permission ([Discord Developer Portal](https://discord.com/developers/applications))
- Your numeric Telegram user ID (the only account allowed to use the bot)

## Environment variables

| Variable | Description |
| --- | --- |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token from BotFather |
| `DISCORD_BOT_TOKEN` | Discord bot token from the Developer Portal |
| `OWNER_ID` | Your numeric Telegram user ID (only this ID can use the bot) |

Never commit these values. Set them as environment variables on your
hosting platform (e.g. Railway → Project → Variables).

## Running locally

```bash
pip install -r requirements.txt
export TELEGRAM_BOT_TOKEN=your_token
export DISCORD_BOT_TOKEN=your_token
export OWNER_ID=123456789
python main.py
```

## Deploying on Railway

1. Push this project to a GitHub repository.
2. Create a new Railway project from that repository.
3. Add the three environment variables above under **Variables**.
4. Railway detects `railway.json` / `Procfile` and runs `python main.py`
   automatically. No further configuration needed.

## Project structure

- `main.py` — the entire bot (Telegram control panel + Discord automation)
- `requirements.txt` — Python dependencies
- `Procfile` / `railway.json` — process + deploy config for Railway
- `runtime.txt` — pinned Python version
