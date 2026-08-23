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

def parse_recommendations(soup):
    entries = []
    for rec in soup.find_all('div', class_='recommendation'):
        a_tag = rec.find('a', attrs={'data-ds-appid': True})
        if not a_tag: continue
        appid = a_tag.get('data-ds-appid')
        review_type = "Informational"
        if rec.find('span', class_='color_recommended'): review_type = "Recommended"
        elif rec.find('span', class_='color_not_recommended'): review_type = "Not Recommended"
        desc_div = rec.find('div', class_='recommendation_desc')
        curator_desc = desc_div.get_text(strip=True) if desc_div else ""
        yt_link = ""
        readmore = rec.find('div', class_='recommendation_readmore')
        if readmore:
            yt_a = readmore.find('a')
            if yt_a and 'youtu' in yt_a.get('href', ''): yt_link = yt_a.get('href')
        entries.append({'appid': appid, 'review_type': review_type,
                        'curator_desc': curator_desc, 'yt_link': yt_link})
    return entries

def fetch_curator_reviews():
    seen = {}
    ordered = []

    def add(entries):
        for e in entries:
            if e['appid'] not in seen:
                seen[e['appid']] = e
                ordered.append(e['appid'])

    for page in range(1, 21): 
        try:
            url = f"{CURATOR_URL}?p={page}"
            print(f"Fetching HTML page {page}...")
            res = requests.get(url, headers=HEADERS, timeout=15)
            if res.status_code != 200: continue
            
            entries = parse_recommendations(BeautifulSoup(res.text, 'html.parser'))
            if not entries: 
                print(f"End of reviews reached on page {page}.")
                break
                
            add(entries)
            time.sleep(2)
        except Exception as e:
            print(f"HTML page {page} error: {e}")

    print(f"Collected {len(ordered)} unique reviews this run")
    return [seen[a] for a in ordered]

def fetch_steam_data(appid):
    session = requests.Session()
    session.cookies.set('mature_content', '1', domain='store.steampowered.com', path='/')
    session.cookies.set('birthtime', '283993200', domain='store.steampowered.com', path='/')
    url = f"https://store.steampowered.com/app/{appid}/"
    try:
        res = session.get(url, headers=HEADERS, timeout=15)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, 'html.parser')

        name_el = soup.find('div', class_='apphub_AppName') or soup.find('div', id='appHubTitle') or soup.find('title')
        name = name_el.get_text(strip=True) if name_el else "Unknown Game"
        if "on Steam" in name: name = name.replace("on Steam", "").strip()

        header_img = None
        img_el = soup.find('img', class_='game_header_image_full')
        if img_el and img_el.get('src'): header_img = img_el.get('src')
        if not header_img:
            og = soup.find('meta', property='og:image')
            if og and og.get('content'): header_img = og.get('content')
        if not header_img:
            header_img = f"https://cdn.akamai.steamstatic.com/steam/apps/{appid}/header.jpg"

        screenshots = []
        for s in soup.find_all('img', class_='highlight_screenshot_image')[:4]:
            if s.get('src'): screenshots.append(s.get('src'))

        tags = []
        tags_div = soup.find('div', class_='popular_tags')
        if tags_div: tags = [a.get_text(strip=True) for a in tags_div.find_all('a') if a.get_text(strip=True)][:6]

        short_desc_el = soup.find('div', class_='game_description_snippet')
        short_desc = short_desc_el.get_text(strip=True) if short_desc_el else ""
        desc_div = soup.find('div', id='game_area_description')
        desc_html = str(desc_div) if desc_div else f"<p>{short_desc}</p>"

        dev_div = soup.find('div', id='developers_list')
        developers = ', '.join([a.get_text(strip=True) for a in dev_div.find_all('a')]) if dev_div else "Unknown"
        date_div = soup.find('div', class_='date')
        release_date = date_div.get_text(strip=True) if date_div else "Unknown"

        price = ""
        price_el = soup.find('div', class_='game_purchase_price')
        if not price_el: price_el = soup.find('div', class_='discount_final_price')
        if price_el:
            price = price_el.get_text(strip=True)
        else:
            purchase = soup.find('div', class_='game_area_purchase')
            if purchase:
                text = purchase.get_text(" ", strip=True).lower()
                if 'coming soon' in text or 'not yet available' in text: price = "Coming Soon"
                elif 'free to play' in text or 'play game' in text: price = "Free"
                elif 'download demo' in text: price = "Demo Available"
                else: price = "See Steam"

        return {
            'name': name, 'description': desc_html, 'short_desc': short_desc,
            'header_image': header_img, 'screenshots': screenshots, 'tags': tags,
            'developers': developers, 'publishers': developers,
            'release_date': release_date, 'price': price
        }
    except Exception as e:
        print(f"Error scraping {appid}: {e}")
        return None

def load_saved_games():
    saved = {}
    if os.path.exists(DATA_DIR):
        for fname in os.listdir(DATA_DIR):
            if fname.endswith('.json'):
                try:
                    with open(os.path.join(DATA_DIR, fname)) as f:
                        saved[fname[:-5]] = json.load(f)
                except: pass
    return saved

def build_site(reviews):
    now = time.time()
    new_count = 0
    for idx, r in enumerate(reviews):
        appid = r['appid']
        if appid in saved:
            saved[appid]['review_type'] = r['review_type']
            saved[appid]['curator_desc'] = r['curator_desc']
            saved[appid]['yt_link'] = r['yt_link']
            
            # NEW: If we failed to fetch this game previously, try again now!
            if saved[appid].get('name') == 'Unknown Game (Fetch Failed)':
                print(f"Retrying fetch for previously failed game {appid}...")
                steam = fetch_steam_data(appid)
                if steam:
                    steam['appid'] = appid
                    steam['review_type'] = r['review_type']
                    steam['curator_desc'] = r['curator_desc']
                    steam['yt_link'] = r['yt_link']
                    steam['first_seen'] = saved[appid].get('first_seen', now)
                    saved[appid] = steam
        else:
            print(f"Fetching NEW game {appid}...")
            steam = fetch_steam_data(appid)
            if not steam: 
                # NEW: Create a placeholder so the game NEVER disappears from the site
                print(f"WARNING: Could not fetch Steam data for {appid}. Saving basic info anyway!")
                steam = {
                    'appid': appid, 'name': 'Unknown Game (Fetch Failed)', 
                    'description': '<p>Could not load details from Steam.</p>', 
                    'short_desc': '', 'header_image': f"https://cdn.akamai.steamstatic.com/steam/apps/{appid}/header.jpg",
                    'screenshots': [], 'tags': [], 'developers': 'Unknown', 
                    'publishers': 'Unknown', 'release_date': 'Unknown', 'price': 'See Steam'
                }
            
            steam['appid'] = appid
            steam['review_type'] = r['review_type']
            steam['curator_desc'] = r['curator_desc']
            steam['yt_link'] = r['yt_link']
            steam['first_seen'] = now - idx
            saved[appid] = steam
            new_count += 1
            time.sleep(1.5)
            
        # Save every single game permanently, even if it failed to fetch details
        with open(os.path.join(DATA_DIR, f"{appid}.json"), 'w') as f:
            json.dump(saved[appid], f)

    print(f"Added {new_count} new games. Total saved: {len(saved)}")

    site_games = []
    for appid, d in saved.items():
        game_info = {
            'appid': appid, 'name': d.get('name'), 'header_image': d.get('header_image'),
            'screenshots': d.get('screenshots', []), 'tags': d.get('tags', []),
            'price': d.get('price', ''), 'description': d.get('description'),
            'developers': d.get('developers'), 'publishers': d.get('publishers'),
            'release_date': d.get('release_date'), 'review_type': d.get('review_type'),
            'curator_desc': d.get('curator_desc'), 'yt_id': get_yt_id(d.get('yt_link')),
            'first_seen': d.get('first_seen', 0),
        }
        site_games.append(game_info)
        game_tpl.stream(game=game_info).dump(os.path.join(OUTPUT_DIR, f"game_{appid}.html"))

    site_games.sort(key=lambda g: g['first_seen'], reverse=True)
    index_tpl.stream(games=site_games).dump(os.path.join(OUTPUT_DIR, "index.html"))
    print(f"Site generation complete. Total games on site: {len(site_games)}")

if __name__ == "__main__":
    reviews = fetch_curator_reviews()
    build_site(reviews)
