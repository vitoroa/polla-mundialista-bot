"""
World Cup 2026 -> WhatsApp Group Notifier
Pulls live match data from football-data.org and posts updates to a WhatsApp
group via GREEN-API.

Run it on a schedule (cron, Railway, Render, or just on your laptop during
match days). It remembers what it has already announced via a tiny JSON file
so it never double-posts.
"""

import json
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

# --- Config from .env ---
GA_INSTANCE = os.environ["GA_INSTANCE"]
GA_TOKEN = os.environ["GA_TOKEN"]
GA_GROUP = os.environ["GA_GROUP"]               # e.g. 12036302...@g.us
FD_TOKEN = os.environ["FD_TOKEN"]               # football-data.org token
POLLAYA_LINK = os.environ.get("POLLAYA_LINK", "")

STATE_FILE = Path("wc_state.json")
FD_URL = "https://api.football-data.org/v4/competitions/WC/matches"


# ---------- State (so we don't double-announce) ----------
def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"announced_kickoffs": [], "announced_results": []}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2))


# ---------- WhatsApp send ----------
def send_whatsapp(text):
    url = f"https://api.green-api.com/waInstance{GA_INSTANCE}/sendMessage/{GA_TOKEN}"
    payload = {"chatId": GA_GROUP, "message": text}
    r = requests.post(url, json=payload, timeout=15)
    r.raise_for_status()
    print(f"  Sent: {text[:60]}...")
    # GREEN-API rate limit safety
    time.sleep(2)


# ---------- Football data ----------
def fetch_matches():
    headers = {"X-Auth-Token": FD_TOKEN}
    r = requests.get(FD_URL, headers=headers, timeout=15)
    r.raise_for_status()
    return r.json()["matches"]


# ---------- Message builders ----------
def kickoff_msg(m):
    home = m["homeTeam"]["name"]
    away = m["awayTeam"]["name"]
    stage = m.get("stage", "").replace("_", " ").title()
    msg = f"⚽ KICKOFF! {home} vs {away}\n📍 {stage}"
    if POLLAYA_LINK:
        msg += f"\n\nLast chance to lock in your prediction:\n{POLLAYA_LINK}"
    return msg


def result_msg(m):
    home = m["homeTeam"]["name"]
    away = m["awayTeam"]["name"]
    hs = m["score"]["fullTime"]["home"]
    as_ = m["score"]["fullTime"]["away"]
    winner = m["score"].get("winner")

    if winner == "HOME_TEAM":
        result_line = f"🏆 {home} wins!"
    elif winner == "AWAY_TEAM":
        result_line = f"🏆 {away} wins!"
    else:
        result_line = "🤝 Draw"

    msg = f"🔔 FULL TIME\n{home} {hs} - {as_} {away}\n{result_line}"
    if POLLAYA_LINK:
        msg += f"\n\nCheck the leaderboard:\n{POLLAYA_LINK}"
    return msg


# ---------- Main loop (one tick) ----------
def tick():
    state = load_state()
    matches = fetch_matches()
    print(f"Fetched {len(matches)} matches")

    for m in matches:
        mid = str(m["id"])
        status = m["status"]

        # Match just started
        if status == "IN_PLAY" and mid not in state["announced_kickoffs"]:
            send_whatsapp(kickoff_msg(m))
            state["announced_kickoffs"].append(mid)
            save_state(state)

        # Match finished
        if status == "FINISHED" and mid not in state["announced_results"]:
            send_whatsapp(result_msg(m))
            state["announced_results"].append(mid)
            save_state(state)


if __name__ == "__main__":
    tick()


#test line
send_whatsapp("🤖 Bot online and ready for the World Cup")
