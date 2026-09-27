#!/usr/bin/env python3
# Rebuild data/players.json + data/photos from the user-provided dataset in
# "ipl data/": "ipl players.xlsx" (Name, Role, Team, Base Price, Marquee) and
# photos/<Player Name>.jpg. Photos are matched to players by name (fuzzy) and
# copied to data/photos/<sr>.jpg (the naming the server expects).
import openpyxl, json, re, os, shutil, sys, difflib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IPL  = os.path.join(ROOT, 'ipl data')
XLSX = os.path.join(IPL, 'ipl players.xlsx')
SRC_PHOTOS = os.path.join(IPL, 'photos')
DATA = os.path.join(ROOT, 'data')
OUT_PHOTOS = os.path.join(DATA, 'photos')

def norm(n): return re.sub(r'[^a-z]', '', str(n).lower())

BASE = {'₹2cr':200, '₹1.5cr':150, '₹1cr':100, '₹75l':75, '₹50l':50, '₹30l':30}
def base_of(s):
    key = re.sub(r'\s+','', str(s).lower())
    return BASE.get(key, 30)

def role_of(r):
    r = str(r or '')
    if re.search(r'wicket', r, re.I): return 'WICKETKEEPER'
    if re.search(r'all', r, re.I):    return 'ALL-ROUNDER'
    if re.search(r'bowl', r, re.I):   return 'BOWLER'
    return 'BATTER'

# --- country: carry from previous master, override the ones it didn't know ---
old = json.load(open(os.path.join(DATA, 'players.json'), encoding='utf-8')) if os.path.exists(os.path.join(DATA,'players.json')) else {'PLAYERS':[],'CATS':{}}
old_country = {norm(p['name']): p.get('country','India') for p in old.get('PLAYERS',[])}
OVERSEAS = {norm(n) for n in [
    'Matthew Short','Kagiso Rabada','Adam Milne','Akeal Hosein','Blessing Muzarabani',
    'Dilshan Madushanka','Dushmantha Chameera','Kwena Maphaka','Spencer Johnson',
    'Mitchell Marsh','Mitchell Santner','Dasun Shanaka','Mitchell Owen','Heinrich Klaasen',
    'Nicholas Pooran','Jordan Cox','Philip Salt','Matthew Breetzke',
]}
def country_of(name):
    k = norm(name)
    if k in old_country: return old_country[k]
    return 'Overseas' if k in OVERSEAS else 'India'

# --- read the sheet ---
wb = openpyxl.load_workbook(XLSX, data_only=True)
ws = wb['IPL Players']
rows = [r for r in ws.iter_rows(values_only=True)]
hi = next(i for i,r in enumerate(rows) if r and r[0]=='Name')
data = [r for r in rows[hi+1:] if r and r[0] not in (None,'')]

# --- photo index (basename -> file), for fuzzy matching by normalized name ---
photo_files = [f for f in os.listdir(SRC_PHOTOS) if re.search(r'\.(jpe?g|png|webp)$', f, re.I)]
photo_by_norm = {norm(os.path.splitext(f)[0]): f for f in photo_files}
photo_norms = list(photo_by_norm.keys())
# explicit fixes for photo files whose names are too misspelled to fuzzy-match
PHOTO_OVERRIDES = {
    norm('Digvesh Singh Rathi'): 'Digvesh rathi.jpg',
    norm('Philip Salt'):         'philip star.jpg',
    norm('Kartik Sharma'):       'karthik sharma,jpg.webp',
    norm('Spencer Johnson'):     'Spencer jonhsin.jpg',
}

players, stars, photo_ops, no_photo, overridden = [], {}, [], [], []
for i, r in enumerate(data, start=1):
    name = str(r[0]).strip()
    role = role_of(r[1])
    base = base_of(r[3])
    marquee = '★' in str(r[4] or '')
    country = country_of(name)
    if norm(name) not in old_country: overridden.append((name, country))
    p = {
        'sr': i, 'code': 'P'+str(i).zfill(3), 'name': name,
        'country': country, 'role': role, 'cu': '', 'base': base,
        'set': 'Marquee' if marquee else 'Set '+str(1 + (i % 5)),
    }
    if marquee:
        p['cat'] = 'M'
        stars[name] = True
    players.append(p)
    # match a photo: exact-normalized first, then a close fuzzy match
    key = norm(name)
    match = None
    if key in PHOTO_OVERRIDES:
        match = PHOTO_OVERRIDES[key]
    elif key in photo_by_norm:
        match = photo_by_norm[key]
    else:
        cand = difflib.get_close_matches(key, photo_norms, n=1, cutoff=0.86)
        if cand: match = photo_by_norm[cand[0]]
    if match: photo_ops.append((i, match))
    else: no_photo.append(name)

# --- write out: wipe old data, then write fresh ---
if os.path.isdir(OUT_PHOTOS): shutil.rmtree(OUT_PHOTOS)
os.makedirs(OUT_PHOTOS, exist_ok=True)
used = set()
for sr, fname in photo_ops:
    ext = os.path.splitext(fname)[1].lower()
    ext = '.jpg' if ext in ('.jpeg',) else ext
    shutil.copyfile(os.path.join(SRC_PHOTOS, fname), os.path.join(OUT_PHOTOS, str(sr)+ext))
    used.add(fname)

out = {
    'PLAYERS': players,
    'STARS': stars,
    'CATS': old.get('CATS') or {
        'M':{'c':'F4C430','label':'MARQUEE'},'BA':{'c':'E63946','label':'BATSMEN'},
        'WK':{'c':'2EC4B6','label':'WICKETKEEPER'},'AL':{'c':'9B5DE5','label':'ALL-ROUNDER'},
        'FA':{'c':'FF7A00','label':'FAST BOWLER'},'SP':{'c':'35C46A','label':'SPIN BOWLER'},
        'UBA':{'c':'00BBF9','label':'EMERGING BAT'},'UAL':{'c':'00BBF9','label':'EMERGING AR'},
        'UWK':{'c':'00BBF9','label':'EMERGING WK'},'UFA':{'c':'00BBF9','label':'EMERGING PACE'},
        'USP':{'c':'00BBF9','label':'EMERGING SPIN'},'-':{'c':'8C99B8','label':'OTHER'},
    },
    'STATS': {},
    'meta': {'source': 'ipl players.xlsx', 'built': __import__('datetime').date.today().isoformat(), 'count': len(players)},
}
json.dump(out, open(os.path.join(DATA,'players.json'),'w',encoding='utf-8'), ensure_ascii=False, indent=1)

overseas = sum(1 for p in players if p['country']=='Overseas')
unused = [f for f in photo_files if f not in used]
print(f'players written : {len(players)}  (India {len(players)-overseas} / Overseas {overseas})')
print(f'marquee         : {len(stars)}')
print(f'photos copied   : {len(photo_ops)}   players without a photo: {len(no_photo)}')
print(f'country inferred : {len(overridden)} (not in old master)')
print(f'photo files unused: {len(unused)}')
if no_photo:
    print('\nNO PHOTO for:'); [print('  -',n) for n in no_photo]
if unused:
    print('\nUNUSED photo files:'); [print('  x',f) for f in unused]
