# Polla Mundialista Bot ⚽🇲🇽🇺🇸🇨🇦

WhatsApp bot for the FIFA World Cup 2026 prediction pool. Posts daily previews, kickoff alerts, and full-time results to a WhatsApp group — bilingual (Spanish + English) with kickoff times in 4 timezones (LA / NY / LDN / MAD).

## What it does

- **🌅 Daily preview** — every morning at 9 AM NY time, lists the day's matches with kickoff times in 4 zones
- **⏰ Pre-match reminder** — ~1 hour before kickoff, "last chance to predict"
- **⚽ Live kickoff** — when a match starts
- **🔔 Full-time result** — final score and winner
- All messages bilingual (Spanish first, then English)
- Country flag emojis
- Pollaya pool link in every message

## Sample messages

**Daily preview:**
```
☀️ Partidos de hoy / Today's matches

🇲🇽 México vs Sudáfrica / South Africa 🇿🇦
   🕒 10:00 LA · 13:00 NY · 18:00 LDN · 19:00 MAD

🇫🇷 France / Francia vs Iran 🇮🇷
   🕒 13:00 LA · 16:00 NY · 21:00 LDN · 22:00 MAD

⚡ Cargá tus pronósticos / Lock your predictions:
https://pollaya.com/...
```

**Full time:**
```
🔔 FINAL / FULL TIME

🇲🇽 Mexico / México 2 - 1 South Africa / Sudáfrica 🇿🇦
🏆 ¡Gana México! 🇲🇽
🏆 Mexico wins! 🇲🇽

📊 Tabla / Leaderboard:
https://pollaya.com/...
```

## Audience

Designed for a group spanning:
- 🇲🇽 Mexico City / 🇨🇷 Costa Rica (UTC-6)
- 🇺🇸 LA / Pacific (UTC-7 in summer)
- 🇺🇸 NY / 🇨🇴 Bogotá / 🇵🇪 Lima (UTC-4 to -5)
- 🇬🇧 London (UTC+1 in summer)
- 🇪🇸 Madrid (UTC+2 in summer)

(Note: BOG is one hour behind NY in summer; close enough that NY time covers it for planning purposes.)

## How it works

1. GitHub Actions runs `wc_bot.py` every 10 minutes
2. Bot fetches match data from [football-data.org](https://www.football-data.org)
3. Detects events worth announcing (kickoffs, finals, daily preview window, 1-hour reminders)
4. Posts to WhatsApp via [GREEN-API](https://green-api.com)
5. Tracks what's been announced in `wc_state.json` (committed back to repo)

## Setup

### Local development

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then edit .env with real values
python wc_bot.py
```

### Cloud deployment

Already deployed to GitHub Actions. Workflow runs every 10 minutes.
See `.github/workflows/bot.yml`.

Required GitHub secrets:
- `GA_INSTANCE` — GREEN-API instance ID
- `GA_TOKEN` — GREEN-API token
- `GA_GROUP` — WhatsApp group chat ID (ends in `@g.us`)
- `FD_TOKEN` — football-data.org API token
- `POLLAYA_LINK` — Pollaya pool invite URL

## Tuning

Constants at the top of `wc_bot.py`:
- `REFERENCE_TZ` — used to decide what "today" means and when to send the preview (currently NY = UTC-4 in summer)
- `DISPLAY_ZONES` — list of (label, timezone) shown in messages
- `PREVIEW_HOUR` — when to send the daily preview (24h, in REFERENCE_TZ)
- `REMIND_MIN` / `REMIND_MAX` — reminder window in minutes before kickoff

## Resetting

To re-announce something (e.g. for testing), edit `wc_state.json` and remove the match ID from the relevant list, then push.

To wipe all announcements:
```json
{
  "announced_kickoffs": [],
  "announced_results": [],
  "announced_reminders": [],
  "last_preview_date": null
}
```

## Costs

- GitHub Actions: free (public repo) or 2,000 min/month free (private)
- football-data.org: free tier (10 req/min)
- GREEN-API: ~$8/month Business plan during the tournament
- Pollaya: free for up to 8 users
