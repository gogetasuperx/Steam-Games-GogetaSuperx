import time
import requests

CURATOR_ID = "44917508"
CURATOR_URL = f"https://store.steampowered.com/curator/{CURATOR_ID}/"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh-TW;q=0.7,zh;q=0.6,ja;q=0.5,ko;q=0.4,ru;q=0.3,de;q=0.2,fr;q=0.1,*;q=0.1',
}

def make_session(extra_cookies=None):
    s = requests.Session()
    s.cookies.set('mature_content', '1', domain='store.steampowered.com', path='/')
    s.cookies.set('wants_mature_content', '1', domain='store.steampowered.com', path='/')
    s.cookies.set('birthtime', '283993200', domain='store.steampowered.com', path='/')
    s.cookies.set('lastagecheckage', '1-0-1979', domain='store.steampowered.com', path='/')
    if extra_cookies:
        for k, v in extra_cookies.items():
            s.cookies.set(k, v, domain='store.steampowered.com', path='/')
    return s

def get_total_count(session, extra_params=None):
    url = f"{CURATOR_URL}ajaxgetfilteredrecommendations/render/"
    params = {'query': '', 'start': 0, 'count': 10, 'sort': 'recent'}
    if extra_params:
        params.update(extra_params)
    try:
        res = session.get(url, params=params, headers=HEADERS, timeout=20)
        data = res.json()
        return data.get('total_count', 'N/A')
    except Exception as e:
        return f"ERROR {e}"

def diagnose():
    print("=== DIAGNOSING STEAM FILTERING (looking for total_count=2000) ===")
    baseline = 0

    # 1) Baseline with current cookies
    s = make_session()
    baseline = get_total_count(s)
    print(f"baseline                     -> total_count={baseline}")
    time.sleep(1)

    # 2) Storefront country code as a URL param (cc)
    for cc in ['US', 'DE', 'RU', 'JP', 'CN', 'AU', 'GB']:
        s = make_session()
        tc = get_total_count(s, {'cc': cc})
        print(f"cc={cc}                       -> total_count={tc}")
        time.sleep(1)

    # 3) Store language as a URL param (l)
    for l in ['english', 'schinese', 'japanese']:
        s = make_session()
        tc = get_total_count(s, {'l': l})
        print(f"l={l}                 -> total_count={tc}")
        time.sleep(1)

    # 4) steamCountry cookie
    for cc in ['US', 'JP', 'CN']:
        s = make_session({'steamCountry': cc})
        tc = get_total_count(s)
        print(f"steamCountry cookie={cc}      -> total_count={tc}")
        time.sleep(1)

    print("=== DIAGNOSIS COMPLETE ===")
    print(f"Baseline was {baseline}. Any line above showing a HIGHER number is a winner.")

if __name__ == "__main__":
    diagnose()
