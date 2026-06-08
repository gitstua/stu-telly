"""
Fetches the Canberra raw IPTV playlist and EPG, writes filtered copies
containing only the five nominated channels.

raw-tv.m3u8 format (#EXTINF, then zero or more #EXTVLCOPT lines, then URL):
  #EXTINF:-1 channel-id="mjh-abc-act" ... , ABC TV
  #EXTVLCOPT:http-user-agent=...
  #EXTVLCOPT:http-referrer=
  https://c.mjh.nz/abc-act.m3u8
"""

import gzip
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET

SOURCE_M3U = "https://i.mjh.nz/au/Canberra/raw-tv.m3u8"
SOURCE_EPG = "https://i.mjh.nz/au/Canberra/epg.xml.gz"

# Raw URL for the EPG we publish to the release branch.
# Jellyfin/Moonfin reads this instead of the full upstream EPG.
EPG_RAW_URL = "https://raw.githubusercontent.com/gitstua/stu-telly/release/epg.xml.gz"

OUTPUT_M3U = "canberra.m3u8"
OUTPUT_EPG = "epg.xml.gz"

KEEP = {
    "mjh-seven-syd",      # Seven     ch 7
    "mjh-channel-9-nsw",  # Channel 9 ch 9
    "mjh-10-nsw",         # 10        ch 10
    "mjh-abc-act",        # ABC TV    ch 21
    "mjh-abc-news",       # ABC NEWS  ch 24
}

def fetch_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "IPTV-Filter/1.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read()

def fetch(url: str) -> str:
    return fetch_bytes(url).decode()

def filter_m3u(text: str) -> str:
    lines  = text.splitlines()
    out    = []

    header = next((l for l in lines if l.startswith("#EXTM3U")), "#EXTM3U")
    # Point x-tvg-url at our filtered EPG on the release branch.
    header = re.sub(r'x-tvg-url="[^"]*"', f'x-tvg-url="{EPG_RAW_URL}"', header)
    if 'x-tvg-url=' not in header:
        header += f' x-tvg-url="{EPG_RAW_URL}"'
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
            if not cur.strip():
                j += 1
                continue
            block.append(cur)
            if not cur.startswith("#"):   # stream URL — stop
                break
            j += 1

        if channel_id in KEEP:
            out.append("")
            out.extend(block)

        i = j + 1

    return "\n".join(out) + "\n"

def filter_epg(data: bytes) -> bytes:
    raw  = gzip.decompress(data)
    root = ET.fromstring(raw)

    for elem in root.findall("channel"):
        if elem.get("id") not in KEEP:
            root.remove(elem)

    for elem in root.findall("programme"):
        if elem.get("channel") not in KEEP:
            root.remove(elem)

    header = '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE tv SYSTEM "xmltv.dtd">\n'
    return gzip.compress((header + ET.tostring(root, encoding="unicode")).encode())

def main():
    print(f"Fetching {SOURCE_M3U} …")
    raw_m3u  = fetch(SOURCE_M3U)
    filtered = filter_m3u(raw_m3u)

    with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
        f.write(filtered)

    kept = filtered.count("#EXTINF")
    print(f"Written {OUTPUT_M3U} — {kept}/{len(KEEP)} channels matched")

    if kept != len(KEEP):
        missing = KEEP - set(re.findall(r'channel-id="([^"]+)"', filtered))
        print(f"WARNING: missing channel IDs: {missing}", file=sys.stderr)
        sys.exit(1)

    print(f"Fetching {SOURCE_EPG} …")
    raw_epg      = fetch_bytes(SOURCE_EPG)
    filtered_epg = filter_epg(raw_epg)

    with open(OUTPUT_EPG, "wb") as f:
        f.write(filtered_epg)

    print(f"Written {OUTPUT_EPG}")

if __name__ == "__main__":
    main()
