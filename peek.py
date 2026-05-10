{\rtf1\ansi\ansicpg1252\cocoartf2761
\cocoatextscaling0\cocoaplatform0{\fonttbl\f0\fswiss\fcharset0 Helvetica;}
{\colortbl;\red255\green255\blue255;}
{\*\expandedcolortbl;;}
\paperw8400\paperh11900\margl1440\margr1440\vieww11520\viewh8400\viewkind0
\pard\tx720\tx1440\tx2160\tx2880\tx3600\tx4320\tx5040\tx5760\tx6480\tx7200\tx7920\tx8640\pardirnatural\partightenfactor0

\f0\fs24 \cf0 import os, requests\
from dotenv import load_dotenv\
load_dotenv()\
\
r = requests.get(\
    "https://api.football-data.org/v4/competitions/WC/matches",\
    headers=\{"X-Auth-Token": os.environ["FD_TOKEN"]\},\
)\
matches = r.json()["matches"]\
\
# First 5 matches\
for m in matches[:5]:\
    print(f"\{m['utcDate']\}  \{m['homeTeam']['name']\} vs \{m['awayTeam']['name']\}  [\{m['status']\}]")}