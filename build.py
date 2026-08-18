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
            curator_desc = desc_div.get_text(strip=True) if desc_div else ""
            
            readmore = rec.find('div', class_='recommendation_readmore')
            yt_link = ""
            if readmore:
                yt_a = readmore.find('a')
                if yt_a and 'youtu' in yt_a.get('href', ''): yt_link = yt_a.get('href')
                    
            games.append({'appid': appid, 'curator_desc': curator_desc, 'yt_link': yt_link, 'review_type': review_type})
        time.sleep(1)
    return games

def fetch_steam_data(appid):
    session = requests.Session()
    session.cookies.set('mature_content', '1', domain='store.steampowered.com', path='/')
    session.cookies.set('wants_mature_content', '1', domain='store.steampowered.com', path='/')
    session.cookies.set('birthtime', '283993200', domain='store.steampowered.com', path='/')
    
    url = f"https://store.steampowered.com/app/{appid}/"
    try:
        res = session.get(url, headers=HEADERS, timeout=15)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # FIXED: Steam uses class 'apphub_AppName' for titles now
        name_el = soup.find('div', class_='apphub_AppName') or soup.find('div', id='appHubTitle') or soup.find('title')
        name = name_el.get_text(strip=True) if name_el else "Unknown Game"
        if "on Steam" in name:
            name = name.replace("on Steam", "").strip()
            
        short_desc_el = soup.find('div', class_='game_description_snippet')
        short_desc = short_desc_el.get_text(strip=True) if short_desc_el else ""
        
        desc_div = soup.find('div', id='game_area_description')
        desc_html = str(desc_div) if desc_div else f"<p>{short_desc}</p>"
        
        dev_div = soup.find('div', id='developers_list')
        developers = ', '.join([a.get_text(strip=True) for a in dev_div.find_all('a')]) if dev_div else "Unknown"
        
        date_div = soup.find('div', class_='date')
        release_date = date_div.get_text(strip=True) if date_div else "Unknown"
        
        return {
            'name': name, 
            'description': desc_html, 
            'short_desc': short_desc,
            'header_image': f"https://cdn.akamai.steamstatic.com/steam/apps/{appid}/header.jpg",
            'developers': developers, 
            'publishers': developers, 
            'release_date': release_date
        }
    except Exception as e:
        print(f"Error scraping {appid}: {e}")
        return None

def build_site(games):
    env = Environment(loader=FileSystemLoader('.'))
    index_tpl = env.get_template('index_tpl.html')
    game_tpl = env.get_template('game_tpl.html')
    site_games = []
    
    for g in games:
        appid = g['appid']
        json_path = os.path.join(DATA_DIR, f"{appid}.json")
        steam_data = None
        
        # Force re-fetch to fix "Unknown Game" for existing cached games
        if os.path.exists(json_path):
            os.remove(json_path)
            
        print(f"Fetching details for {appid}...")
        steam_data = fetch_steam_data(appid)
        if steam_data:
            with open(json_path, 'w') as f: json.dump(steam_data, f)
        time.sleep(1.5)
            
        if not steam_data: continue
            
        yt_id = get_yt_id(g['yt_link'])
        game_info = {
            'appid': appid, 'name': steam_data.get('name'), 'header_image': steam_data.get('header_image'),
            'description': steam_data.get('description'), 'developers': steam_data.get('developers'),
            'publishers': steam_data.get('publishers'), 'release_date': steam_data.get('release_date'),
            'review_type': g['review_type'], 'curator_desc': g['curator_desc'], 'yt_id': yt_id,
            'short_desc': steam_data.get('short_desc')
        }
        site_games.append(game_info)
        game_tpl.stream(game=game_info).dump(os.path.join(OUTPUT_DIR, f"game_{appid}.html"))

    site_games.sort(key=lambda x: int(x['appid']), reverse=True)
    index_tpl.stream(games=site_games).dump(os.path.join(OUTPUT_DIR, "index.html"))
    print("Site generation complete.")

if __name__ == "__main__":
    reviews = fetch_curator_reviews()
    build_site(reviews)
