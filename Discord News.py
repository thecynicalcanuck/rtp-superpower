#!/usr/bin/env python3
"""
Unraid Python script to poll a Discourse category for new replies (excluding the first post of each topic),
extract each post’s markdown heading, summarize via the Gemini API (rate-limited to 5 calls/min),
post only truly new replies via a Discord webhook, and persist state in Unraid's User Scripts folder.
Configure at the top. Schedule via Unraid User Scripts every 5 minutes.
"""
import os
import json
import logging
import re
import requests
import time
from html import unescape

# --- Configuration (edit these) ---
DISCOURSE_BASE_URL  = ""
DISCOURSE_API_KEY   = ""
DISCOURSE_API_USER  = "system"
GEMINI_API_KEY      = ""
GEMINI_ENDPOINT     = ""
DISCORD_WEBHOOK_URL = ""
CATEGORY_SLUG       = ""
CATEGORY_ID         = ""
# Rate limit (calls per minute)
GEMINI_MAX_PER_MIN  = 5
# Regex for markdown headings
HEADING_RE          = re.compile(r'^(?:#{1,2})\s+(.*)', re.MULTILINE)

# --- State file path ---
PERSISTENT_DIR      = "/boot/config/plugins/user.scripts/scripts/Discord News"
STATE_FILE          = os.path.join(PERSISTENT_DIR, "news_ticker_state.json")

# --- Logging ---
logging.basicConfig(format="%(asctime)s [%(levelname)s] %(message)s", level=logging.INFO)

gemini_times = []

# --- State handling ---
def load_state():
    os.makedirs(PERSISTENT_DIR, exist_ok=True)
    try:
        with open(STATE_FILE, 'r') as f:
            state = json.load(f)
    except FileNotFoundError:
        state = {'last_id': 0, 'mapped': {}}
    except Exception as e:
        logging.warning(f"Loading state failed ({e}); resetting.")
        state = {'last_id': 0, 'mapped': {}}
    # ensure keys
    state.setdefault('last_id', 0)
    state.setdefault('mapped', {})
    return state


def save_state(state):
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f, indent=2)
        logging.info("State saved.")
    except Exception as e:
        logging.error(f"Saving state failed: {e}")

# --- Discourse API ---
def fetch_topics():
    url = f"{DISCOURSE_BASE_URL}/c/{CATEGORY_SLUG}/{CATEGORY_ID}/l/latest.json"
    r = requests.get(url, headers={
        'Api-Key': DISCOURSE_API_KEY,
        'Api-Username': DISCOURSE_API_USER
    }, timeout=10)
    r.raise_for_status()
    return r.json().get('topic_list', {}).get('topics', [])


def fetch_posts(topic_id):
    url = f"{DISCOURSE_BASE_URL}/t/{topic_id}/posts.json?include_raw=true"
    r = requests.get(url, headers={
        'Api-Key': DISCOURSE_API_KEY,
        'Api-Username': DISCOURSE_API_USER
    }, timeout=10)
    r.raise_for_status()
    return r.json().get('post_stream', {}).get('posts', [])

# --- Summarize with rate limit ---
def summarize(text):
    global gemini_times
    now = time.time()
    gemini_times = [t for t in gemini_times if now - t < 60]
    if len(gemini_times) >= GEMINI_MAX_PER_MIN:
        wait = 60 - (now - gemini_times[0])
        logging.info(f"Rate limit hit; sleeping {wait:.1f}s")
        time.sleep(wait)
    payload = {
        'contents': [{ 'role': 'user', 'parts': [{ 'text': f"Summarize the following in two sentences:\n\n{text}" }] }],
        'generationConfig': { 'temperature': 0.3, 'candidateCount': 1, 'topP': 1.0, 'maxOutputTokens': 200 }
    }
    resp = requests.post(f"{GEMINI_ENDPOINT}:generateContent?key={GEMINI_API_KEY}", json=payload, timeout=20)
    resp.raise_for_status()
    parts = resp.json().get('candidates', [{}])[0].get('content', {}).get('parts', [])
    gemini_times.append(time.time())
    return parts[0].get('text', '').strip() if parts else ''

# --- Extract headline ---
def extract_headline(raw):
    m = HEADING_RE.search(raw)
    return unescape(m.group(1).strip()) if m else None

# --- Discord embed post ---
def post_to_discord(title, link, description):
    embed = { 'title': title, 'url': link, 'description': description }
    r = requests.post(DISCORD_WEBHOOK_URL, json={ 'embeds': [embed] }, timeout=10)
    r.raise_for_status()
    logging.info(f"Posted: {title}")
    try:
        return r.json().get('id')
    except:
        return None

# --- Main ---
def main():
    state = load_state()
    last_id = state['last_id']
    mapped = state['mapped']
    posts_to_process = []
    new_last = last_id

    # gather only truly new posts
    for topic in fetch_topics():
        tid = topic['id']
        slug = topic.get('slug', '')
        ttitle = topic.get('title', '')
        for p in fetch_posts(tid):
            pid = p.get('id')
            if p.get('post_number') == 1 or pid <= last_id or str(pid) in mapped:
                continue
            posts_to_process.append({
                'id': pid,
                'topic_id': tid,
                'slug': slug,
                'post_number': p.get('post_number'),
                'raw': p.get('raw', ''),
                'topic_title': ttitle
            })
            new_last = max(new_last, pid)

    # sort and post
    posts_to_process.sort(key=lambda x: x['id'])
    logging.info(f"Found {len(posts_to_process)} new posts to process.")
    for post in posts_to_process:
        title = extract_headline(post['raw']) or post['topic_title']
        link = f"{DISCOURSE_BASE_URL}/t/{post['slug']}/{post['topic_id']}/{post['post_number']}"
        summ = summarize(post['raw'])
        mid = post_to_discord(title, link, summ)
        if mid:
            mapped[str(post['id'])] = mid

    # persist new_last
    state['last_id'] = new_last
    state['mapped'] = mapped
    save_state(state)

if __name__ == '__main__':
    main()
