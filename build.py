import os
import json
import time
import requests
from bs4 import BeautifulSoup
from jinja2 import Environment, FileSystemLoader

CURATOR_ID = "44917508"
CURATOR_URL = f"https://store.steampowered.com/curator/{CURATOR_ID}/"
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
DATA_DIR = "data"
OUTPUT_DIR = "public"

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

def get_yt_id(url):
    if not url: return None
    if 'youtu.be/' in url: return url.split('youtu.be/')[1].split('?')[0]
    elif 'youtube.com/watch?v=' in url: return url.split('v=')[1].split('&')[0]
    return None

def fetch_curator_reviews():
    games = []
    for page in range(1, 4):
        url = f"{CURATOR_URL}?p={page}&numperpage=100"
        print(f"Fetching curator reviews page {page}...")
        res = requests.get(url, headers=HEADERS)
        soup = BeautifulSoup(res.text, 'html.parser')
        recommendations = soup.find_all('div', class_='recommendation')

        for rec in recommendations:
            a_tag = rec.find('a', attrs={'data-ds-appid': True})
            if not a_tag: continue
            appid = a_tag.get('data-ds-appid')
            if any(g['appid'] == appid for g in games): continue

            review_type = "Informational"
            if rec.find('span', class_='color_recommended'): review_type = "Recommended"
            elif rec.find('span', class_='color_not_recommended'): review_type = "Not Recommended"

            desc_div = rec.find('div', class_='recommendation_desc')
            curator_desc = desc_div.get_text(strip=True) if desc_div else
