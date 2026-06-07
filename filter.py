"""
Fetches the Canberra raw IPTV playlist and writes a filtered copy
containing only the five nominated channels.

raw-tv.m3u8 format (#EXTINF, then zero or more #EXTVLCOPT lines, then URL):
  #EXTINF:-1 channel-id="mjh-abc-act" ... , ABC TV
  #EXTVLCOPT:http-user-agent=...
  #EXTVLCOPT:http-referrer=
  https://c.mjh.nz/abc-act.m3u8
"""

import re
import sys
import urllib.request

SOURCE = "https://i.mjh.nz/au/Canberra/raw-tv.m3u8"
OUTPUT = "canberra.m3u8"

KEEP = {
    "mjh-seven-syd",      # Seven     ch 7
    "mjh-channel-9-nsw",  # Channel 9 ch 9
    "mjh-10-nsw",         # 10        ch 10
    "mjh-abc-act",        # ABC TV    ch 21
    "mjh-abc-news",       # ABC NEWS  ch 24
}

def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "IPTV-Filter/1.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read().decode()

def filter_m3u(text: str) -> str:
    lines = text.splitlines()
    out   = []

    header = next((l for l in lines if l.startswith("#EXTM3U")), "#EXTM3U")
    out.append(header)

    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.startswith("#EXTINF"):
            i += 1
            continue

        m          = re.search(r'channel-id="([^"]+)"', line)
        channel_id = m.group(1) if m else ""

        # Collect the #EXTINF line plus any following #EXTVLCOPT metadata,
        # up to and including the first non-comment line (the stream URL).
        block = [line]
        j     = i + 1
        while j < len(lines):
            cur = lines[j]
            if not cur.strip():           # skip blank lines
                j += 1
                continue
            block.append(cur)
            if not cur.startswith("#"):   # this was the URL — stop
                break
            j += 1

        if channel_id in KEEP:
            out.append("")               # blank separator
            out.extend(block)

        i = j + 1

    return "\n".join(out) + "\n"

def main():
    print(f"Fetching {SOURCE} …")
    raw      = fetch(SOURCE)
    filtered = filter_m3u(raw)

    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(filtered)

    kept = filtered.count("#EXTINF")
    print(f"Written {OUTPUT} — {kept}/{len(KEEP)} channels matched")

    if kept != len(KEEP):
        missing = KEEP - set(re.findall(r'channel-id="([^"]+)"', filtered))
        print(f"WARNING: missing channel IDs: {missing}", file=sys.stderr)
        sys.exit(1)   # fail the Action so you get an email

if __name__ == "__main__":
    main()
