import os
import re
import json
import time
import requests
from bs4 import BeautifulSoup
from jinja2 import Environment, FileSystemLoader

CURATOR_ID = "44917508"
CURATOR_URL = f"https://store.steampowered.com/curator/{CURATOR_ID}/"
PLAYLIST_ID = "PL100msBiYaGgV-6-EesElWkuH-AbIx8nx"
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
    for page in range(1, 6): 
        url = f"{CURATOR_URL}?p={page}"
        print(f"Fetching curator reviews page {page}...")
        try:
            res = requests.get(url, headers=HEADERS, timeout=15)
            if res.status_code != 200:
                print(f"Failed to load page {page}, status: {res.status_code}")
                continue
                
            soup = BeautifulSoup(res.text, 'html.parser')
            recommendations = soup.find_all('div', class_='recommendation')
            
            if not recommendations:
                print(f"No more recommendations found on page {page}, stopping.")
                break
                
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
            
            time.sleep(3)
        except Exception as e:
            print(f"Error fetching curator page {page}: {e}")
            continue
            
    print(f"Found {len(games)} total games from curator.")
    return games

def fetch_playlist_videos():
    videos = []
    try:
        url = f"https://www.youtube.com/playlist?list={PLAYLIST_ID}"
        print("Fetching YouTube playlist...")
        res = requests.get(url, headers=HEADERS, timeout=20)
        match = re.search(r'(?:var ytInitialData|window\["ytInitialData"\])\s*=\s*(\{.*?\});\s*</script>', res.text, re.DOTALL)
        if not match:
            print("Could not find playlist data on the page.")
            return videos
        data = json.loads(match.group(1))
        items = None
        tabs = data.get('contents', {}).get('twoColumnBrowseResultsRenderer', {}).get('tabs', [])
        for tab in tabs:
            content = tab.get('tabRenderer', {}).get('content', {})
            for c in content.get('sectionListRenderer', {}).get('contents', []):
                ilr = c.get('itemListRenderer')
                if ilr:
                    items = ilr.get('contents', [])
                    break
            if items: break
        if not items:
            print("No playlist items found.")
            return videos
        for item in items[:48]:
            pvr = item.get('playlistVideoRenderer')
            if not pvr: continue
            vid = pvr.get('videoId')
            title_obj = pvr.get('title', {})
            title = title_obj.get('runs', [{}])[0].get('text', '') if 'runs' in title_obj else title_obj.get('simpleText', '')
            length = pvr.get('lengthText', {}).get('simpleText', '')
            if vid:
                videos.append({'video_id': vid, 'title': title, 'length': length})
        print(f"Found {len(videos)} playlist videos.")
    except Exception as e:
        print(f"Error fetching playlist: {e}")
    return videos

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
        if not screenshots:
            for s in soup.find_all('a', class_='highlight_screenshot_link')[:4]:
                if s.get('href'): screenshots.append(s.get('href'))

        tags = []
        tags_div = soup.find('div', class_='popular_tags')
        if tags_div:
            tags = [a.get_text(strip=True) for a in tags_div.find_all('a') if a.get_text(strip=True)][:6]
        if not tags:
            genres = soup.find('div', id='genresAndManufacturer')
            if genres:
                tags = [a.get_text(strip=True) for a in genres.find_all('a') if a.get_text(strip=True)][:6]

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
                if 'coming soon' in text or 'not yet available' in text or 'planned release' in text:
                    price = "Coming Soon"
                elif 'free to play' in text or 'play game' in text:
                    price = "Free"
                elif 'download demo' in text:
                    price = "Demo Available"
                else:
                    price = "See Steam"

        return {
            'name': name, 'description': desc_html, 'short_desc': short_desc,
            'header_image': header_img, 'screenshots': screenshots, 'tags': tags,
            'developers': developers, 'publishers': developers,
            'release_date': release_date, 'price': price
        }
    except Exception as e:
        print(f"Error scraping {appid}: {e}")
        return None

def build_site(games, playlist_videos):
    env = Environment(loader=FileSystemLoader('.'))
    index_tpl = env.get_template('index_tpl.html')
    game_tpl = env.get_template('game_tpl.html')
    playlist_tpl = env.get_template('playlist_tpl.html')
    site_games = []

    for g in games:
        appid = g['appid']
        json_path = os.path.join(DATA_DIR, f"{appid}.json")
        steam_data = None

        if os.path.exists(json_path):
            with open(json_path, 'r') as f: cached = json.load(f)
            if 'tags' in cached: steam_data = cached

        if not steam_data:
            print(f"Fetching details for {appid}...")
            steam_data = fetch_steam_data(appid)
            if steam_data:
                with open(json_path, 'w') as f: json.dump(steam_data, f)
            time.sleep(1.5)

        if not steam_data: continue

        yt_id = get_yt_id(g['yt_link'])
        game_info = {
            'appid': appid, 'name': steam_data.get('name'),
            'header_image': steam_data.get('header_image'),
            'screenshots': steam_data.get('screenshots', []),
            'tags': steam_data.get('tags', []),
            'price': steam_data.get('price', ''),
            'description': steam_data.get('description'),
            'developers': steam_data.get('developers'),
            'publishers': steam_data.get('publishers'),
            'release_date': steam_data.get('release_date'),
            'review_type': g['review_type'], 'curator_desc': g['curator_desc'], 'yt_id': yt_id
        }
        site_games.append(game_info)
        game_tpl.stream(game=game_info).dump(os.path.join(OUTPUT_DIR, f"game_{appid}.html"))

    index_tpl.stream(games=site_games).dump(os.path.join(OUTPUT_DIR, "index.html"))
    playlist_tpl.stream(videos=playlist_videos).dump(os.path.join(OUTPUT_DIR, "playlist.html"))
    print("Site generation complete.")

if __name__ == "__main__":
    reviews = fetch_curator_reviews()
    playlist_videos = fetch_playlist_videos()
    build_site(reviews, playlist_videos)
