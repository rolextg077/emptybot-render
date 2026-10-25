# eMpTy Strong Protection — Render Deployment

This package contains the Telegram bot only. The bot uses the Cloudflare Worker URL already configured in `bot/bot.py` (`WEB_DOMAIN`). The Cloudflare Worker source is intentionally not included because it is already hosted separately.

## Deploy on Render

1. Upload these project files to a GitHub repository.
2. In Render, create a Background Worker connected to that repository.
3. Select Docker as the runtime so Render uses the root `Dockerfile`.
4. Deploy and inspect the logs.

The Dockerfile installs dependencies from `bot/requirements.txt` and starts `python bot.py`.

## Important

Before deployment, replace any exposed Telegram bot token and API keys with fresh credentials, preferably configured through environment variables.
