"""
World Cup 2026 -> WhatsApp Group Notifier (Bilingual ES/EN, multi-timezone)

Features:
- Daily morning preview of the day's matches
- Pre-match reminder ~1 hour before kickoff
- Live kickoff announcement
- Full-time results
- Country flag emojis
- Times shown in LA / NY / LDN / MAD (summer offsets - tournament is in summer)
- Every message in Spanish AND English

Designed to run on GitHub Actions every 10 minutes.
State (announced events) is persisted in wc_state.json.
"""

import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

# --- Config ---
GA_INSTANCE = os.environ["GA_INSTANCE"]
GA_TOKEN = os.environ["GA_TOKEN"]
GA_GROUP = os.environ["GA_GROUP"]
FD_TOKEN = os.environ["FD_TOKEN"]
POLLAYA_LINK = os.environ.get("POLLAYA_LINK", "")

# --- Timezones ---
# Tournament runs June 11 - July 19, 2026 — all DST in summer.
# Reference timezone for "is it preview time yet?" decisions.
# NY (EDT = UTC-4) — chosen because the bot owner is in NY.
REFERENCE_TZ = timezone(timedelta(hours=-4))

# Display zones for kickoff times in messages (summer offsets):
# LA = UTC-7 (PDT), NY = UTC-4 (EDT), LDN = UTC+1 (BST), MAD = UTC+2 (CEST)
# BOG = UTC-5 year-round (≈ NY in winter, NY-1 in summer)
DISPLAY_ZONES = [
    ("LA", timezone(timedelta(hours=-7))),
    ("NY", timezone(timedelta(hours=-4))),
    ("BOG", timezone(timedelta(hours=-5))),
    ("LDN", timezone(timedelta(hours=1))),
    ("MAD", timezone(timedelta(hours=2))),
]

# Reminder window: send a "match in ~1 hour" alert if the match is between
# REMIND_MIN and REMIND_MAX minutes away. Wider than cron interval (10 min).
REMIND_MIN = 50
REMIND_MAX = 70

# Send the daily preview at this hour in REFERENCE_TZ (24h format).
PREVIEW_HOUR = 9

STATE_FILE = Path("wc_state.json")
FD_URL = "https://api.football-data.org/v4/competitions/WC/matches"

# Country name -> flag emoji.
FLAGS = {
    "Argentina": "🇦🇷", "Australia": "🇦🇺", "Austria": "🇦🇹",
    "Belgium": "🇧🇪", "Brazil": "🇧🇷", "Canada": "🇨🇦",
    "Cape Verde": "🇨🇻", "Colombia": "🇨🇴", "Croatia": "🇭🇷",
    "Czech Republic": "🇨🇿", "Czechia": "🇨🇿", "Denmark": "🇩🇰",
    "Ecuador": "🇪🇨", "Egypt": "🇪🇬", "England": "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
    "France": "🇫🇷", "Germany": "🇩🇪", "Ghana": "🇬🇭",
    "Iran": "🇮🇷", "Italy": "🇮🇹", "Ivory Coast": "🇨🇮",
    "Côte d'Ivoire": "🇨🇮", "Japan": "🇯🇵", "Jordan": "🇯🇴",
    "Mexico": "🇲🇽", "Morocco": "🇲🇦", "Netherlands": "🇳🇱",
    "New Zealand": "🇳🇿", "Norway": "🇳🇴", "Panama": "🇵🇦",
    "Paraguay": "🇵🇾", "Poland": "🇵🇱", "Portugal": "🇵🇹",
    "Qatar": "🇶🇦", "Saudi Arabia": "🇸🇦", "Scotland": "🏴󠁧󠁢󠁳󠁣󠁴󠁿",
    "Senegal": "🇸🇳", "South Africa": "🇿🇦", "South Korea": "🇰🇷",
    "Korea Republic": "🇰🇷", "Spain": "🇪🇸", "Switzerland": "🇨🇭",
    "Tunisia": "🇹🇳", "Türkiye": "🇹🇷", "Turkey": "🇹🇷",
    "United States": "🇺🇸", "USA": "🇺🇸", "Uruguay": "🇺🇾",
    "Uzbekistan": "🇺🇿", "Wales": "🏴󠁧󠁢󠁷󠁬󠁳󠁿", "Algeria": "🇩🇿",
    "Nigeria": "🇳🇬", "Cameroon": "🇨🇲", "Mali": "🇲🇱",
    "DR Congo": "🇨🇩", "Chile": "🇨🇱", "Peru": "🇵🇪",
    "Bolivia": "🇧🇴", "Venezuela": "🇻🇪", "Iraq": "🇮🇶",
    "United Arab Emirates": "🇦🇪", "Oman": "🇴🇲",
    "Costa Rica": "🇨🇷", "Honduras": "🇭🇳", "Jamaica": "🇯🇲",
    "Curaçao": "🇨🇼", "Haiti": "🇭🇹", "Suriname": "🇸🇷",
    "New Caledonia": "🇳🇨",
}

# Spanish translations of team names (only for those that differ).
TEAM_ES = {
    "Brazil": "Brasil", "Belgium": "Bélgica", "Czech Republic": "Chequia",
    "Czechia": "Chequia", "Denmark": "Dinamarca", "England": "Inglaterra",
    "France": "Francia", "Germany": "Alemania", "Ivory Coast": "Costa de Marfil",
    "Côte d'Ivoire": "Costa de Marfil", "Japan": "Japón", "Jordan": "Jordania",
    "Morocco": "Marruecos", "Netherlands": "Países Bajos",
    "New Zealand": "Nueva Zelanda", "Norway": "Noruega", "Panama": "Panamá",
    "Poland": "Polonia", "Saudi Arabia": "Arabia Saudita", "Scotland": "Escocia",
    "South Africa": "Sudáfrica", "South Korea": "Corea del Sur",
    "Korea Republic": "Corea del Sur", "Spain": "España",
    "Switzerland": "Suiza", "Türkiye": "Turquía", "Turkey": "Turquía",
    "United States": "Estados Unidos", "USA": "Estados Unidos",
    "Wales": "Gales", "Algeria": "Argelia", "Nigeria": "Nigeria",
    "Cameroon": "Camerún", "DR Congo": "RD Congo", "Iraq": "Irak",
    "United Arab Emirates": "Emiratos Árabes Unidos",
    "Curaçao": "Curazao", "Haiti": "Haití", "New Caledonia": "Nueva Caledonia",
}

# Stage translations: API value -> (English, Spanish).
STAGE = {
    "GROUP_STAGE": ("Group Stage", "Fase de Grupos"),
    "LAST_32": ("Round of 32", "Dieciseisavos"),
    "LAST_16": ("Round of 16", "Octavos"),
    "QUARTER_FINALS": ("Quarter-finals", "Cuartos de Final"),
    "SEMI_FINALS": ("Semi-finals", "Semifinales"),
    "THIRD_PLACE": ("Third-place Match", "Tercer Puesto"),
    "FINAL": ("Final", "Final"),
}


def flag(team_name):
    return FLAGS.get(team_name, "🌍")


def team_es(name):
    return TEAM_ES.get(name, name)


def stage_pair(api_stage):
    return STAGE.get(api_stage or "", ("Group Stage", "Fase de Grupos"))


# ---------- State ----------
def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {
        "announced_kickoffs": [],
        "announced_results": [],
        "announced_reminders": [],
        "last_preview_date": None,
    }


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2))


# ---------- WhatsApp send ----------
def send_whatsapp(text):
    url = f"https://api.green-api.com/waInstance{GA_INSTANCE}/sendMessage/{GA_TOKEN}"
    payload = {"chatId": GA_GROUP, "message": text}
    r = requests.post(url, json=payload, timeout=15)
    r.raise_for_status()
    print(f"  Sent: {text[:80].replace(chr(10), ' | ')}...")
    time.sleep(2)


# ---------- Football data ----------
def fetch_matches():
    headers = {"X-Auth-Token": FD_TOKEN}
    r = requests.get(FD_URL, headers=headers, timeout=15)
    if r.status_code != 200:
        print(f"API error {r.status_code}: {r.text}")
        r.raise_for_status()
    return r.json()["matches"]


def parse_kickoff(m):
    return datetime.fromisoformat(m["utcDate"].replace("Z", "+00:00"))


def kickoff_times_str(dt):
    """Format kickoff in all display zones, e.g. '10:00 LA · 13:00 NY · 18:00 LDN · 19:00 MAD'."""
    parts = []
    for label, tz in DISPLAY_ZONES:
        parts.append(f"{dt.astimezone(tz).strftime('%H:%M')} {label}")
    return " · ".join(parts)


# ---------- Message builders (each returns a single bilingual message) ----------
def matchup_only(m):
    """e.g. '🇲🇽 Mexico / México vs South Africa / Sudáfrica 🇿🇦'"""
    h, a = m["homeTeam"]["name"], m["awayTeam"]["name"]
    h_es, a_es = team_es(h), team_es(a)
    h_disp = h if h == h_es else f"{h} / {h_es}"
    a_disp = a if a == a_es else f"{a} / {a_es}"
    return f"{flag(h)} {h_disp} vs {a_disp} {flag(a)}"


def preview_msg(today_matches):
    if not today_matches:
        return None
    lines = ["☀️ *Partidos de hoy / Today's matches*", ""]
    for m in sorted(today_matches, key=parse_kickoff):
        ko = parse_kickoff(m)
        lines.append(matchup_only(m))
        lines.append(f"   🕒 {kickoff_times_str(ko)}")
        lines.append("")
    if POLLAYA_LINK:
        lines.append(f"⚡ Cargá tus pronósticos / Lock your predictions:")
        lines.append(POLLAYA_LINK)
    return "\n".join(lines).rstrip()


def reminder_msg(m):
    parts = [
        "⏰ *En ~1 hora / In ~1 hour*",
        "",
        matchup_only(m),
        f"🕒 {kickoff_times_str(parse_kickoff(m))}",
    ]
    if POLLAYA_LINK:
        parts += [
            "",
            "Última chance para pronosticar / Last chance to predict:",
            POLLAYA_LINK,
        ]
    return "\n".join(parts)


def kickoff_msg(m):
    stage_en, stage_es = stage_pair(m.get("stage"))
    parts = [
        "⚽ *ARRANCÓ / KICKOFF*",
        "",
        matchup_only(m),
        f"📍 {stage_es} / {stage_en}",
    ]
    return "\n".join(parts)


def result_msg(m):
    h, a = m["homeTeam"]["name"], m["awayTeam"]["name"]
    h_es, a_es = team_es(h), team_es(a)
    hs = m["score"]["fullTime"]["home"]
    as_ = m["score"]["fullTime"]["away"]
    winner = m["score"].get("winner")

    if winner == "HOME_TEAM":
        verdict_es = f"🏆 ¡Gana {h_es}! {flag(h)}"
        verdict_en = f"🏆 {h} wins! {flag(h)}"
    elif winner == "AWAY_TEAM":
        verdict_es = f"🏆 ¡Gana {a_es}! {flag(a)}"
        verdict_en = f"🏆 {a} wins! {flag(a)}"
    else:
        verdict_es = "🤝 Empate"
        verdict_en = "🤝 Draw"

    h_disp = h if h == h_es else f"{h} / {h_es}"
    a_disp = a if a == a_es else f"{a} / {a_es}"

    parts = [
        "🔔 *FINAL / FULL TIME*",
        "",
        f"{flag(h)} {h_disp} {hs} - {as_} {a_disp} {flag(a)}",
        f"{verdict_es}",
        f"{verdict_en}",
    ]
    if POLLAYA_LINK:
        parts += ["", f"📊 Tabla / Leaderboard:", POLLAYA_LINK]
    return "\n".join(parts)


# ---------- Logic ----------
def maybe_send_preview(state, matches, now_ref):
    today_str = now_ref.date().isoformat()
    if state.get("last_preview_date") == today_str:
        return
    if now_ref.hour < PREVIEW_HOUR:
        return

    today_matches = [
        m for m in matches
        if parse_kickoff(m).astimezone(REFERENCE_TZ).date() == now_ref.date()
    ]
    msg = preview_msg(today_matches)
    if msg:
        send_whatsapp(msg)
    state["last_preview_date"] = today_str
    save_state(state)


def maybe_send_reminders(state, matches, now_utc):
    for m in matches:
        if m["status"] != "SCHEDULED":
            continue
        mid = str(m["id"])
        if mid in state["announced_reminders"]:
            continue
        ko = parse_kickoff(m)
        minutes_to_kickoff = (ko - now_utc).total_seconds() / 60
        if REMIND_MIN <= minutes_to_kickoff <= REMIND_MAX:
            send_whatsapp(reminder_msg(m))
            state["announced_reminders"].append(mid)
            save_state(state)


def maybe_send_kickoffs_and_results(state, matches):
    for m in matches:
        mid = str(m["id"])
        status = m["status"]
        if status == "IN_PLAY" and mid not in state["announced_kickoffs"]:
            send_whatsapp(kickoff_msg(m))
            state["announced_kickoffs"].append(mid)
            save_state(state)
        if status == "FINISHED" and mid not in state["announced_results"]:
            send_whatsapp(result_msg(m))
            state["announced_results"].append(mid)
            save_state(state)


def tick():
    state = load_state()
    matches = fetch_matches()

    # Allow forcing a fake "today" for testing.
    # Set DEBUG_DATE=2026-06-11 (or any tournament date) in your .env
    # to simulate that day's preview/reminders/kickoffs/results.
    debug_date = os.environ.get("DEBUG_DATE", "").strip()
    if debug_date:
        target = datetime.fromisoformat(debug_date).replace(tzinfo=REFERENCE_TZ)
        # Pick a "now" in the middle of that day so all matches are visible
        now_utc = target.replace(hour=12, minute=0).astimezone(timezone.utc)
        print(f"⚠️  DEBUG_DATE active: pretending it's {debug_date} 12:00 NY")
    else:
        now_utc = datetime.now(timezone.utc)

    now_ref = now_utc.astimezone(REFERENCE_TZ)
    print(f"Fetched {len(matches)} matches. Reference time (NY): {now_ref}")

    maybe_send_preview(state, matches, now_ref)
    maybe_send_reminders(state, matches, now_utc)
    maybe_send_kickoffs_and_results(state, matches)


if __name__ == "__main__":
    tick()
