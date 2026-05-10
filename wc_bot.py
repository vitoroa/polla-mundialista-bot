"""
World Cup 2026 -> WhatsApp Group Notifier (Bilingual ES/EN, multi-timezone)

Features:
- Daily morning preview of the day's matches
- Pre-match reminder ~1 hour before kickoff
- Live kickoff announcement
- Full-time results
- Daily leaderboard from Pollaya, posted after the day's last match ends
- Country flag emojis
- Times shown in LA / NY / BOG / LDN / MAD (summer offsets)
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

# --- Required config ---
GA_INSTANCE = os.environ["GA_INSTANCE"]
GA_TOKEN = os.environ["GA_TOKEN"]
GA_GROUP = os.environ["GA_GROUP"]
FD_TOKEN = os.environ["FD_TOKEN"]

# --- Optional config ---
POLLAYA_LINK = os.environ.get("POLLAYA_LINK", "")
POLLAYA_TOKEN = os.environ.get("POLLAYA_TOKEN", "")
POLLAYA_GROUP_ID = os.environ.get("POLLAYA_GROUP_ID", "")

# --- Timezones (tournament is summer 2026, hardcoded DST) ---
REFERENCE_TZ = timezone(timedelta(hours=-4))  # NY in summer (EDT)

DISPLAY_ZONES = [
    ("LA", timezone(timedelta(hours=-7))),
    ("NY", timezone(timedelta(hours=-4))),
    ("BOG", timezone(timedelta(hours=-5))),
    ("LDN", timezone(timedelta(hours=1))),
    ("MAD", timezone(timedelta(hours=2))),
]

# Reminder window
REMIND_MIN = 50
REMIND_MAX = 70

# Daily preview hour (in REFERENCE_TZ)
PREVIEW_HOUR = 9

# How many minutes after a match ends until we send the leaderboard.
# Pollaya needs time to score, plus we want to wait in case other late games
# end shortly after.
LEADERBOARD_DELAY_MIN = 30

STATE_FILE = Path("wc_state.json")
FD_URL = "https://api.football-data.org/v4/competitions/WC/matches"
POLLAYA_URL = (
    f"https://api.pollaya.com/api/v1/groups/{POLLAYA_GROUP_ID}"
    f"/leaderboard?page=0&pageSize=100"
)
POLLAYA_HEADERS = {
    "Authorization": f"Bearer {POLLAYA_TOKEN}",
    "Accept": "application/json",
    "Origin": "https://game.pollaya.com",
    "Referer": "https://game.pollaya.com/",
    "X-Site-Domain": "https://game.pollaya.com",
}

# --- Country data ---
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
        "last_leaderboard_date": None,
    }


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2))


# ---------- WhatsApp ----------
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
        print(f"FD API error {r.status_code}: {r.text}")
        r.raise_for_status()
    return r.json()["matches"]


def parse_kickoff(m):
    return datetime.fromisoformat(m["utcDate"].replace("Z", "+00:00"))


def kickoff_times_str(dt):
    return " · ".join(
        f"{dt.astimezone(tz).strftime('%H:%M')} {label}"
        for label, tz in DISPLAY_ZONES
    )


# ---------- Pollaya leaderboard ----------
def fetch_leaderboard():
    if not (POLLAYA_TOKEN and POLLAYA_GROUP_ID):
        return None
    try:
        r = requests.get(POLLAYA_URL, headers=POLLAYA_HEADERS, timeout=15)
        if r.status_code != 200:
            print(f"Pollaya API error {r.status_code}: {r.text[:200]}")
            return None
        return r.json().get("results", [])
    except Exception as e:
        print(f"Pollaya fetch failed: {e}")
        return None


def medal(idx):
    return {0: "🥇", 1: "🥈", 2: "🥉"}.get(idx, f"{idx + 1}.")


# ---------- Message builders ----------
def matchup_only(m):
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
        lines += [f"⚡ Cargá tus pronósticos / Lock your predictions:", POLLAYA_LINK]
    return "\n".join(lines).rstrip()


def reminder_msg(m):
    parts = [
        "⏰ *En ~1 hora / In ~1 hour*",
        "",
        matchup_only(m),
        f"🕒 {kickoff_times_str(parse_kickoff(m))}",
    ]
    if POLLAYA_LINK:
        parts += ["", "Última chance para pronosticar / Last chance to predict:", POLLAYA_LINK]
    return "\n".join(parts)


def kickoff_msg(m):
    stage_en, stage_es = stage_pair(m.get("stage"))
    return "\n".join([
        "⚽ *ARRANCÓ / KICKOFF*",
        "",
        matchup_only(m),
        f"📍 {stage_es} / {stage_en}",
    ])


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
        verdict_es,
        verdict_en,
    ]
    if POLLAYA_LINK:
        parts += ["", "📊 Tabla / Leaderboard:", POLLAYA_LINK]
    return "\n".join(parts)


def leaderboard_msg(results):
    """Format the standings. results is the list from Pollaya's API."""
    if not results:
        return None

    # Pollaya returns sorted by position. If everyone is 0pts/position 1,
    # show a tied message instead.
    all_zero = all(r.get("points", 0) == 0 for r in results)
    if all_zero:
        body = [
            "📊 *Tabla del día / Today's standings*",
            "",
            "Todos en cero — ¡a remontar!",
            "All tied at zero — game on!",
        ]
        if POLLAYA_LINK:
            body += ["", POLLAYA_LINK]
        return "\n".join(body)

    lines = ["📊 *Tabla del día / Today's standings*", ""]

    # Find longest name for alignment (cap at 18 chars)
    max_name = max(min(len(r["user"].get("name", "?")), 18) for r in results)

    for i, r in enumerate(results):
        name = r["user"].get("name", "?")
        if len(name) > 18:
            name = name[:17] + "…"
        pts = r.get("points", 0)
        pos = r.get("position", i + 1)

        # Use medal for top 3 by position (handles ties in 1st)
        if pos == 1:
            mark = "🥇"
        elif pos == 2:
            mark = "🥈"
        elif pos == 3:
            mark = "🥉"
        else:
            mark = f"{pos}."

        # Pad name to align points
        padded = name.ljust(max_name)
        lines.append(f"{mark} {padded}  {pts} pts")

    if POLLAYA_LINK:
        lines += ["", f"🔗 {POLLAYA_LINK}"]
    return "\n".join(lines)


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


def maybe_send_leaderboard(state, matches, now_utc, now_ref):
    """Send the leaderboard once per match-day, after the day's last match
    has been finished for at least LEADERBOARD_DELAY_MIN minutes."""
    today_str = now_ref.date().isoformat()
    if state.get("last_leaderboard_date") == today_str:
        return  # already sent today

    # Find today's matches (in NY local terms)
    today_matches = [
        m for m in matches
        if parse_kickoff(m).astimezone(REFERENCE_TZ).date() == now_ref.date()
    ]
    if not today_matches:
        return  # no matches today, skip

    # All of today's matches must be finished
    if not all(m["status"] == "FINISHED" for m in today_matches):
        return

    # And the latest kickoff must be at least ~3 hours behind us
    # (matches last ~2h, plus LEADERBOARD_DELAY_MIN buffer for Pollaya scoring)
    latest_kickoff = max(parse_kickoff(m) for m in today_matches)
    delay = timedelta(hours=2, minutes=LEADERBOARD_DELAY_MIN)
    if now_utc < latest_kickoff + delay:
        return

    # Pull leaderboard and send
    results = fetch_leaderboard()
    if results is None:
        print("Skipping leaderboard: fetch failed")
        return

    msg = leaderboard_msg(results)
    if msg:
        send_whatsapp(msg)
    state["last_leaderboard_date"] = today_str
    save_state(state)


def tick():
    state = load_state()
    matches = fetch_matches()

    debug_date = os.environ.get("DEBUG_DATE", "").strip()
    if debug_date:
        target = datetime.fromisoformat(debug_date).replace(tzinfo=REFERENCE_TZ)
        now_utc = target.replace(hour=23, minute=30).astimezone(timezone.utc)
        print(f"⚠️  DEBUG_DATE active: pretending it's {debug_date} 23:30 NY")
    else:
        now_utc = datetime.now(timezone.utc)

    now_ref = now_utc.astimezone(REFERENCE_TZ)
    print(f"Fetched {len(matches)} matches. Reference time (NY): {now_ref}")

    maybe_send_preview(state, matches, now_ref)
    maybe_send_reminders(state, matches, now_utc)
    maybe_send_kickoffs_and_results(state, matches)
    maybe_send_leaderboard(state, matches, now_utc, now_ref)

if __name__ == "__main__":
    tick()

    # TEMP: test leaderboard format
	    #results = fetch_leaderboard()
	    #if results:
	    #    send_whatsapp(leaderboard_msg(results))