"""
World Cup 2026 -> WhatsApp Group Notifier (Bilingual ES/EN, multi-timezone)

Features:
- Daily morning preview of the day's matches
- Pre-match reminder ~1 hour before kickoff
- Live kickoff announcement
- Full-time results
- Daily leaderboard from Pollaya, with backfill for missed days
- Country flag emojis
- Times shown in LA / NY / BOG / LDN / MAD (summer offsets)
- Every message in Spanish AND English
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
GA_GROUP_LEADERBOARD = os.environ.get("GA_GROUP_LEADERBOARD", GA_GROUP)
FD_TOKEN = os.environ["FD_TOKEN"]

# --- Optional config ---
POLLAYA_LINK = os.environ.get("POLLAYA_LINK", "")
POLLAYA_TOKEN = os.environ.get("POLLAYA_TOKEN", "")
POLLAYA_GROUP_ID = os.environ.get("POLLAYA_GROUP_ID", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# --- Timezones (tournament is summer 2026, hardcoded DST) ---
REFERENCE_TZ = timezone(timedelta(hours=-4))  # NY in summer (EDT)

DISPLAY_ZONES = [
    ("LA", timezone(timedelta(hours=-7))),
    ("NY", timezone(timedelta(hours=-4))),
    ("BOG", timezone(timedelta(hours=-5))),
    ("LDN", timezone(timedelta(hours=1))),
    ("MAD", timezone(timedelta(hours=2))),
]

REMIND_MIN = 50
REMIND_MAX = 70
PREVIEW_HOUR = 9
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
        state = json.loads(STATE_FILE.read_text())
        # Migrate old single-string format to list format
        if "sent_leaderboard_dates" not in state:
            old = state.get("last_leaderboard_date")
            state["sent_leaderboard_dates"] = [old] if old else []
            state.pop("last_leaderboard_date", None)
        # New field for delta tracking
        if "previous_leaderboard" not in state:
            state["previous_leaderboard"] = []
        return state
    return {
        "announced_kickoffs": [],
        "announced_results": [],
        "announced_reminders": [],
        "last_preview_date": None,
        "sent_leaderboard_dates": [],
        "previous_leaderboard": [],
    }


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2))


# ---------- WhatsApp ----------
def send_whatsapp(text, chat_id=None):
    target = chat_id or GA_GROUP
    url = f"https://api.green-api.com/waInstance{GA_INSTANCE}/sendMessage/{GA_TOKEN}"
    payload = {"chatId": target, "message": text}
    r = requests.post(url, json=payload, timeout=15)
    r.raise_for_status()
    print(f"  Sent to {target[:20]}...: {text[:60].replace(chr(10), ' | ')}...")
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
    ko = parse_kickoff(m)
    return "\n".join([
        "⚽ *EMPIEZA PRONTO / STARTING SOON*",
        "",
        matchup_only(m),
        f"🕒 {kickoff_times_str(ko)}",
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


def first_name(full):
    return full.split()[0] if full else "?"


def compute_deltas(current, previous):
    """For each current entry, return dict with name, points, position,
    points_delta, position_delta. position_delta positive = moved up.
    Joined on user.id for stability against duplicate names."""
    prev_by_id = {r["user"].get("id"): r for r in previous} if previous else {}
    out = []
    for r in current:
        uid = r["user"].get("id")
        name = r["user"].get("name", "?")
        pts = r.get("points", 0)
        pos = r.get("position", 0)
        prev = prev_by_id.get(uid)
        out.append({
            "name": name,
            "points": pts,
            "position": pos,
            "points_delta": pts - prev["points"] if prev else None,
            "position_delta": prev["position"] - pos if prev else None,
        })
    return out


def find_movers(deltas):
    """Return (mvp, faller) — each is a dict from compute_deltas, or None."""
    with_deltas = [d for d in deltas if d["points_delta"] is not None]
    if not with_deltas:
        return None, None
    mvp = max(with_deltas, key=lambda d: d["points_delta"])
    if mvp["points_delta"] <= 0:
        mvp = None
    faller = min(with_deltas, key=lambda d: d["position_delta"])
    if faller["position_delta"] >= 0:
        faller = None
    return mvp, faller


def ai_commentary(deltas, mvp, faller):
    """Call Claude API to generate witty bilingual commentary.
    Returns dict {es, en} on success, None on any failure."""
    if not ANTHROPIC_API_KEY:
        return None

    top_5 = sorted(deltas, key=lambda d: d["position"])[:5]
    standings_lines = []
    for d in top_5:
        delta_str = ""
        if d["points_delta"] is not None:
            delta_str = f" ({d['points_delta']:+d} pts"
            if d["position_delta"]:
                delta_str += f", {d['position_delta']:+d} pos)"
            else:
                delta_str += ")"
        standings_lines.append(f"{d['position']}. {d['name']} - {d['points']} pts{delta_str}")

    mvp_line = "none today"
    if mvp:
        mvp_line = f"{first_name(mvp['name'])} (+{mvp['points_delta']} pts)"
    faller_line = "none today"
    if faller:
        faller_line = f"{first_name(faller['name'])} ({faller['position_delta']:+d} positions)"

    prompt = f"""You're the dry, deadpan commentator of a friends-only World Cup prediction pool. Think understated British wit, but in two distinct flavors: Colombian Spanish and New York English. SHORT and CUTTING — never loud.

TOP 5 STANDINGS (after today's matches):
{chr(10).join(standings_lines)}

TODAY'S MOVES:
🔥 MVP (most points gained): {mvp_line}
📉 Biggest faller (lost most positions): {faller_line}

TONE — dry humor, not loud:
- Less exclamation, more sting
- One specific observation per line, not a list of jokes
- Like a friend who watches you mess up and just says "ah"
- Sounds like someone who barely cares but is paying very close attention
- Mock-casual delivery makes the dig land

SPANISH — COLOMBIAN flavor:
- "Parce", "ñero", "berraco", "tranqui", "vea pues", "mijo"
- "Esa sí no se la perdono", "qué nota", "qué pereza"
- Polite-on-the-surface, cutting underneath
- Example: "Parce, Evan se mandó 139 puntos hoy. Calladito. Como si nadie tuviera que notar."

ENGLISH — NEW YORK flavor:
- "Yo", "look at this guy", "buddy", "pal", "c'mon now"
- "Are you kidding me", "real subtle"
- Brooklyn-deadpan, jaded sports-bar energy
- Example: "Yo. Evan dropped 139 today. Real quiet about it too. We supposed to not notice?"

STRICT RULES:
- 1 sentence per language, MAX 15 words each
- ALWAYS name one specific person from the data
- ALWAYS reference one specific stat (points gained, positions moved)
- FIRST NAMES only (e.g., "Victor", not "Victor Roa")
- No emojis in the commentary text itself
- No mean-spirited attacks on personality, intelligence, or appearance

GOAL: provoke a reply. Make someone feel called out enough to fire back.

Return ONLY valid JSON, no markdown:
{{"es": "...", "en": "..."}}"""

    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-sonnet-4-6",
                "max_tokens": 300,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=20,
        )
        if r.status_code != 200:
            print(f"  Claude API error {r.status_code}: {r.text[:200]}")
            return None
        text = r.json()["content"][0]["text"].strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        result = json.loads(text)
        if "es" in result and "en" in result:
            return result
        return None
    except Exception as e:
        print(f"  Claude API failed: {e}")
        return None


def leaderboard_msg(results, previous=None):
    if not results:
        return None

    deltas = compute_deltas(results, previous)
    has_history = any(d["points_delta"] is not None for d in deltas)
    all_zero = all(r.get("points", 0) == 0 for r in results)

    header = "📊 *Tabla / Standings*"

    if all_zero:
        body = [
            header, "",
            "Todos en cero — ¡a remontar!",
            "All tied at zero — game on!",
        ]
        if POLLAYA_LINK:
            body += ["", POLLAYA_LINK]
        return "\n".join(body)

    lines = [header, ""]

    # MVP / Faller callout (only if we have history)
    mvp, faller = (None, None)
    if has_history:
        mvp, faller = find_movers(deltas)
        callouts = []
        if mvp:
            callouts.append(f"🔥 MVP: {first_name(mvp['name'])} (+{mvp['points_delta']} pts)")
        if faller:
            callouts.append(f"📉 Difícil: {first_name(faller['name'])} ({faller['position_delta']:+d} pos)")
        if callouts:
            lines += callouts + [""]

    # Standings table
    max_name = max(min(len(d["name"]), 16) for d in deltas)
    for d in deltas:
        name = d["name"]
        if len(name) > 16:
            name = name[:15] + "…"

        pos = d["position"]
        if pos == 1:
            mark = "🥇"
        elif pos == 2:
            mark = "🥈"
        elif pos == 3:
            mark = "🥉"
        else:
            mark = f"{pos}."

        line = f"{mark} {name.ljust(max_name)}  {d['points']} pts"
        if d["points_delta"] is not None and d["points_delta"] != 0:
            line += f" ({d['points_delta']:+d})"
        if d["position_delta"] is not None and d["position_delta"] != 0:
            arrow = "↑" if d["position_delta"] > 0 else "↓"
            line += f" {arrow}{abs(d['position_delta'])}"
        lines.append(line)

    # AI commentary (only if we have history)
    if has_history:
        commentary = ai_commentary(deltas, mvp, faller)
        if commentary:
            lines += [
                "",
                f"💬 {commentary['es']}",
                f"💬 {commentary['en']}",
            ]

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


def maybe_send_kickoffs_and_results(state, matches, now_utc):
    for m in matches:
        mid = str(m["id"])
        status = m["status"]

        # Kickoff announcement: fire when kickoff is within 30 min in the
        # future, or up to 60 min after (safety net if cron ran late).
        # Safety guards:
        # - Status not POSTPONED/CANCELLED/SUSPENDED (don't announce non-events)
        if mid not in state["announced_kickoffs"]:
            ko = parse_kickoff(m)
            minutes_until = (ko - now_utc).total_seconds() / 60
            if (-60 <= minutes_until <= 30
                    and status not in ("POSTPONED", "CANCELLED", "SUSPENDED")):
                send_whatsapp(kickoff_msg(m))
                state["announced_kickoffs"].append(mid)
                save_state(state)

        # Result: still triggered by API status (this is correct — we need
        # the final score, which only exists after the match ends).
        if status == "FINISHED" and mid not in state["announced_results"]:
            send_whatsapp(result_msg(m))
            state["announced_results"].append(mid)
            save_state(state)


def maybe_send_leaderboard(state, matches, now_utc):
    """Scan all match days that have already passed conditions and send
    leaderboards for any not yet sent. Handles missed days by backfilling.
    Multiple sends in a row are throttled to one per run."""

    # Group matches by NY local date
    by_date = {}
    for m in matches:
        local_date = parse_kickoff(m).astimezone(REFERENCE_TZ).date()
        by_date.setdefault(local_date, []).append(m)

    sent = set(state.get("sent_leaderboard_dates", []))
    delay = timedelta(hours=2, minutes=LEADERBOARD_DELAY_MIN)

    # Sort dates ascending so we backfill oldest first
    for d in sorted(by_date.keys()):
        date_str = d.isoformat()
        if date_str in sent:
            continue

        day_matches = by_date[d]

        # All matches that day must be FINISHED
        if not all(m["status"] == "FINISHED" for m in day_matches):
            continue

        # And enough time must have passed since the latest kickoff
        latest_kickoff = max(parse_kickoff(m) for m in day_matches)
        if now_utc < latest_kickoff + delay:
            continue

        # All conditions met — send the leaderboard
        results = fetch_leaderboard()
        if results is None:
            print(f"  Skipping leaderboard for {date_str}: fetch failed")
            return  # retry next run; don't mark as sent

        previous = state.get("previous_leaderboard", [])
        msg = leaderboard_msg(results, previous=previous)
        if msg:
            send_whatsapp(msg, chat_id=GA_GROUP_LEADERBOARD)

        # Snapshot current results for tomorrow's diff
        state["previous_leaderboard"] = [
            {
                "user": {
                    "id": r["user"].get("id"),
                    "name": r["user"].get("name", "?"),
                },
                "points": r.get("points", 0),
                "position": r.get("position", 0),
            }
            for r in results
        ]
        sent.add(date_str)
        state["sent_leaderboard_dates"] = sorted(sent)
        save_state(state)
        return  # send only one per run to avoid flooding


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
    maybe_send_kickoffs_and_results(state, matches, now_utc)
    maybe_send_leaderboard(state, matches, now_utc)


if __name__ == "__main__":
    tick()
