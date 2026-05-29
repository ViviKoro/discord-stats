import subprocess
import json
import os
import re
from collections import defaultdict, Counter
from datetime import datetime

CHANNEL_ID = "907961620251172874"   # ID du MP enmiruto
TOKEN = os.environ["DISCORD_TOKEN"] # token récupéré depuis les secrets GitHub
MY_NAME = "enmiruto"
OTHER_NAME = "vivikoro"

# 1. Export via DiscordChatExporter CLI
print("Export en cours...")
subprocess.run([
    "dotnet", "DiscordChatExporter.Cli.dll",
    "export",
    "-t", TOKEN,
    "-c", CHANNEL_ID,
    "-f", "Json",
    "-o", "messages.json"
], check=True)

# 2. Parse le JSON
with open("messages.json") as f:
    data = json.load(f)

messages = [m for m in data["messages"] if m.get("type") == "Default" and not m["author"].get("isBot")]

# Stats
monthly = defaultdict(lambda: defaultdict(int))
hourly = defaultdict(lambda: defaultdict(int))
dow = defaultdict(lambda: defaultdict(int))
lengths = defaultdict(list)
attachments = defaultdict(int)
words = defaultdict(Counter)
response_times = defaultdict(list)
daily = defaultdict(int)

STOPWORDS = {'le','la','les','de','du','des','un','une','je','tu','il','on','nous','vous','ils','elles','et','en','que','qui','quoi','ce','se','sa','son','ses','mon','ma','mes','ton','ta','tes','lui','pas','plus','pour','sur','dans','est','au','aux','par','mais','ou','y','a','si','ca','ça','nan','oui','ui','non'}

sorted_msgs = sorted(messages, key=lambda m: m["timestamp"])

for i, m in enumerate(sorted_msgs):
    author = m["author"]["name"]
    ts = m["timestamp"]
    dt = datetime.fromisoformat(ts)
    ym = ts[:7]

    monthly[ym][author] += 1
    hourly[dt.hour][author] += 1
    dow[dt.weekday()][author] += 1
    lengths[author].append(len(m.get("content", "") or ""))
    daily[ts[:10]] += 1
    if m.get("attachments"):
        attachments[author] += len(m["attachments"])

    content = m.get("content", "") or ""
    ws = re.findall(r"[a-záàâéèêëîïôùûüç']{3,}", content.lower())
    for w in ws:
        w = w.strip("'")
        if w not in STOPWORDS and len(w) >= 3:
            words[author][w] += 1

    if i > 0:
        prev = sorted_msgs[i-1]
        if prev["author"]["name"] != author:
            try:
                t1 = datetime.fromisoformat(prev["timestamp"])
                t2 = datetime.fromisoformat(ts)
                diff = (t2 - t1).total_seconds()
                if 0 < diff < 3600:
                    response_times[author].append(diff)
            except:
                pass

months_sorted = sorted(monthly.keys())
authors = [MY_NAME, OTHER_NAME]

enm_m = [monthly[m].get(MY_NAME, 0) for m in months_sorted]
viv_m = [monthly[m].get(OTHER_NAME, 0) for m in months_sorted]
hourly_enm = [hourly[h].get(MY_NAME, 0) for h in range(24)]
hourly_viv = [hourly[h].get(OTHER_NAME, 0) for h in range(24)]
dow_enm = [dow[d].get(MY_NAME, 0) for d in range(7)]
dow_viv = [dow[d].get(OTHER_NAME, 0) for d in range(7)]

total = len(messages)
by_author = {a: sum(monthly[m].get(a, 0) for m in months_sorted) for a in authors}
avg_len = {a: round(sum(lengths[a])/len(lengths[a]), 1) if lengths[a] else 0 for a in authors}
avg_resp = {a: round(sum(response_times[a])/len(response_times[a])) if response_times[a] else 0 for a in authors}
top_day = max(daily, key=daily.get)
top_words = {a: words[a].most_common(15) for a in authors}

def fmt_time(s):
    m, sec = divmod(int(s), 60)
    return f"{m} min {sec:02d}s"

# 3. Injecte les données dans le HTML template
with open("template.html") as f:
    html = f.read()

replacements = {
    "{{TOTAL}}": f"{total:,}".replace(",", " "),
    "{{ENM_COUNT}}": f"{by_author[MY_NAME]:,}".replace(",", " "),
    "{{VIV_COUNT}}": f"{by_author[OTHER_NAME]:,}".replace(",", " "),
    "{{ENM_PCT}}": f"{by_author[MY_NAME]/total*100:.1f}",
    "{{VIV_PCT}}": f"{by_author[OTHER_NAME]/total*100:.1f}",
    "{{NB_MONTHS}}": str(len(months_sorted)),
    "{{TOP_DAY}}": top_day,
    "{{TOP_DAY_COUNT}}": str(daily[top_day]),
    "{{ENM_ATTACH}}": str(attachments.get(MY_NAME, 0)),
    "{{VIV_ATTACH}}": str(attachments.get(OTHER_NAME, 0)),
    "{{TOTAL_ATTACH}}": str(sum(attachments.values())),
    "{{ENM_RESP}}": fmt_time(avg_resp.get(MY_NAME, 0)),
    "{{VIV_RESP}}": fmt_time(avg_resp.get(OTHER_NAME, 0)),
    "{{ENM_AVG_LEN}}": str(avg_len.get(MY_NAME, 0)),
    "{{VIV_AVG_LEN}}": str(avg_len.get(OTHER_NAME, 0)),
    "{{MONTHS_JSON}}": json.dumps(months_sorted),
    "{{ENM_M_JSON}}": json.dumps(enm_m),
    "{{VIV_M_JSON}}": json.dumps(viv_m),
    "{{HOURLY_ENM_JSON}}": json.dumps(hourly_enm),
    "{{HOURLY_VIV_JSON}}": json.dumps(hourly_viv),
    "{{DOW_ENM_JSON}}": json.dumps(dow_enm),
    "{{DOW_VIV_JSON}}": json.dumps(dow_viv),
    "{{WORDS_ENM_JSON}}": json.dumps(top_words[MY_NAME]),
    "{{WORDS_VIV_JSON}}": json.dumps(top_words[OTHER_NAME]),
    "{{UPDATED_AT}}": datetime.utcnow().strftime("%d/%m/%Y à %Hh%M UTC"),
    "{{FIRST_DATE}}": months_sorted[0] if months_sorted else "",
}

for k, v in replacements.items():
    html = html.replace(k, str(v))

with open("index.html", "w") as f:
    f.write(html)

print(f"Dashboard généré — {total} messages au total.")
