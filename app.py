"""
app.py — OffNav Flask Backend
==============================
All features work offline:
  - Routing: local OSRM Docker container (port 5001)
  - Nearby places: local SQLite from extract_amenities.py
  - Place search: local SQLite FTS from build_places.py
  - Voice directions: browser Web Speech API (no internet needed)
  - Map tiles: Service Worker cache
"""
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS
import requests, sqlite3, os, math, unicodedata, re
from datetime import datetime

app = Flask(__name__, template_folder="templates", static_folder="static")
CORS(app)
os.makedirs("data", exist_ok=True)

OSRM_URL      = "http://localhost:5001"
PLACES_DB     = "data/places.db"
AMENITIES_DB  = "data/amenities.db"

# ── Math helpers ──────────────────────────────────────────────────────────────
def hav(a, b):
    R = 6371.0
    la1,lo1 = math.radians(float(a[0])),math.radians(float(a[1]))
    la2,lo2 = math.radians(float(b[0])),math.radians(float(b[1]))
    h = math.sin((la2-la1)/2)**2 + math.cos(la1)*math.cos(la2)*math.sin((lo2-lo1)/2)**2
    return R * 2 * math.asin(math.sqrt(max(0,min(1,h))))

def bearing(a, b):
    la1,lo1 = math.radians(float(a[0])),math.radians(float(a[1]))
    la2,lo2 = math.radians(float(b[0])),math.radians(float(b[1]))
    dlo = lo2-lo1
    x = math.sin(dlo)*math.cos(la2)
    y = math.cos(la1)*math.sin(la2)-math.sin(la1)*math.cos(la2)*math.cos(dlo)
    return (math.degrees(math.atan2(x,y))+360)%360

def dir_name(d):
    return ["North","NE","East","SE","South","SW","West","NW"][round(d/45)%8]

AMENITY_ICONS = {
    "hospital":"🏥","clinic":"🏥","doctors":"🏥","dentist":"🦷",
    "police":"🚔","fire_station":"🚒",
    "pharmacy":"💊",
    "fuel":"⛽","charging_station":"🔌",
    "restaurant":"🍽️","fast_food":"🍔","cafe":"☕","food_court":"🍱","bar":"🍺",
    "atm":"🏧","bank":"🏦",
    "supermarket":"🛒","convenience":"🏪","marketplace":"🏪",
    "school":"🏫","college":"🎓","university":"🎓",
    "hotel":"🏨","guest_house":"🏨","hostel":"🏨",
    "bus_station":"🚌","taxi":"🚕",
    "post_office":"📮","veterinary":"🐾","place_of_worship":"🛕",
}

def amenity_icon(a):
    return AMENITY_ICONS.get(a, "📍")

# ── Connectivity checks ───────────────────────────────────────────────────────
def is_internet():
    try: requests.get("https://tile.openstreetmap.org", timeout=3); return True
    except: return False

def is_osrm():
    try:
        r = requests.get(
            f"{OSRM_URL}/route/v1/driving/78.4867,17.385;79.5941,17.9784?overview=false",
            timeout=3)
        return r.status_code == 200
    except:
        return False

# ── Places DB (name search) ───────────────────────────────────────────────────
def get_places_db():
    conn = sqlite3.connect(PLACES_DB, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def get_amenities_db():
    conn = sqlite3.connect(AMENITIES_DB, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def amenities_db_ready():
    if not os.path.exists(AMENITIES_DB): return False
    try:
        conn = sqlite3.connect(AMENITIES_DB)
        n = conn.execute("SELECT COUNT(*) FROM amenities").fetchone()[0]
        conn.close()
        return n > 1000
    except: return False

def ensure_places_db():
    conn = get_places_db()
    conn.execute("""CREATE TABLE IF NOT EXISTS places (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL, name_te TEXT DEFAULT '', name_hi TEXT DEFAULT '',
        type TEXT DEFAULT 'place', state TEXT DEFAULT '',
        lat REAL NOT NULL, lon REAL NOT NULL,
        osm_id TEXT DEFAULT '', source TEXT DEFAULT 'osm',
        used INTEGER DEFAULT 0, used_at TEXT DEFAULT '',
        UNIQUE(name, lat, lon)
    )""")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_n  ON places(name)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_ll ON places(lat,lon)")
    conn.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS places_fts USING fts5(
        name, name_te, name_hi, state,
        content=places, content_rowid=id,
        tokenize='unicode61 remove_diacritics 2'
    )""")
    conn.execute("""CREATE TRIGGER IF NOT EXISTS pla_ai AFTER INSERT ON places BEGIN
        INSERT INTO places_fts(rowid,name,name_te,name_hi,state)
        VALUES(new.id,new.name,new.name_te,new.name_hi,new.state);
    END""")
    count = conn.execute("SELECT COUNT(*) FROM places WHERE source='builtin'").fetchone()[0]
    if count == 0:
        try:
            from build_places import load_builtin_places
            places = load_builtin_places()
            conn.executemany(
                "INSERT OR IGNORE INTO places(name,type,state,lat,lon,source) VALUES(?,?,?,?,?,'builtin')",
                places)
            print(f"[app] Loaded {len(places)} built-in places")
        except Exception as e:
            print(f"[app] Could not load builtin places: {e}")
    conn.commit()
    conn.close()

def norm(s):
    s = s.lower().strip()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s)

def search_local(query, ulat=None, ulon=None, limit=10):
    conn = get_places_db()
    q = query.strip()
    results = []

    try:
        fts_q = " OR ".join(w+"*" for w in q.split() if w)
        rows = conn.execute("""
            SELECT p.*, rank FROM places p
            JOIN places_fts fts ON p.id = fts.rowid
            WHERE places_fts MATCH ? ORDER BY rank LIMIT ?
        """, (fts_q, limit*3)).fetchall()
        seen = set()
        for r in rows:
            if r["name"] in seen: continue
            seen.add(r["name"])
            dist = hav([ulat,ulon],[r["lat"],r["lon"]]) if ulat else 9999
            results.append({"name":r["name"],"short":r["name"].split(",")[0],
                             "type":r["type"],"state":r["state"],
                             "lat":r["lat"],"lon":r["lon"],"source":"offline_db",
                             "dist_km":round(dist,1) if dist<9999 else None})
    except Exception as e:
        print(f"[search] FTS error: {e}")

    if len(results) < 3:
        try:
            rows = conn.execute(
                "SELECT * FROM places WHERE name LIKE ? ORDER BY used DESC LIMIT ?",
                (f"%{q}%", limit*2)).fetchall()
            seen2 = {r["name"] for r in results}
            for r in rows:
                if r["name"] in seen2: continue
                dist = hav([ulat,ulon],[r["lat"],r["lon"]]) if ulat else 9999
                results.append({"name":r["name"],"short":r["name"].split(",")[0],
                                 "type":r["type"],"state":r["state"],
                                 "lat":r["lat"],"lon":r["lon"],"source":"offline_db",
                                 "dist_km":round(dist,1) if dist<9999 else None})
                seen2.add(r["name"])
        except: pass

    conn.close()
    if ulat: results.sort(key=lambda x: x["dist_km"] or 9999)
    return results[:limit]

def save_place(name, lat, lon):
    try:
        conn = get_places_db()
        conn.execute("""INSERT INTO places(name,type,lat,lon,source,used,used_at)
            VALUES(?,?,?,?,'user',1,?)
            ON CONFLICT(name,lat,lon) DO UPDATE SET used=used+1,used_at=excluded.used_at""",
            (name,"searched",lat,lon,datetime.now().isoformat()))
        conn.commit(); conn.close()
    except: pass

# ── NEARBY — queries local amenities DB ───────────────────────────────────────
CATEGORY_TYPES = {
    "hospital":    ["hospital","clinic","doctors","dentist"],
    "police":      ["police","fire_station"],
    "pharmacy":    ["pharmacy"],
    "fuel":        ["fuel","charging_station"],
    "restaurant":  ["restaurant","fast_food","cafe","food_court"],
    "atm":         ["atm","bank"],
    "supermarket": ["supermarket","convenience","marketplace"],
    "all": list(AMENITY_ICONS.keys()),
}

def nearby_from_local_db(lat, lon, radius_m, category):
    """Query local SQLite amenities DB. Works 100% offline."""
    if not amenities_db_ready():
        return [], "db_empty"

    types = CATEGORY_TYPES.get(category, CATEGORY_TYPES["all"])
    deg   = (radius_m * 1.5) / 111000.0   # generous bounding box

    conn = get_amenities_db()
    placeholders = ",".join("?"*len(types))
    rows = conn.execute(f"""
        SELECT * FROM amenities
        WHERE lat BETWEEN ? AND ?
          AND lon BETWEEN ? AND ?
          AND type IN ({placeholders})
        LIMIT 500
    """, (lat-deg, lat+deg, lon-deg, lon+deg, *types)).fetchall()
    conn.close()

    results = []
    for r in rows:
        d = hav([lat,lon],[r["lat"],r["lon"]]) * 1000
        if d > radius_m * 1.2: continue
        results.append({
            "id":       r["id"],
            "name":     r["name"],
            "amenity":  r["type"],
            "icon":     r["icon"],
            "lat":      r["lat"],
            "lon":      r["lon"],
            "phone":    r["phone"],
            "address":  r["address"],
            "distance": round(d),
        })

    results.sort(key=lambda x: x["distance"])
    return results[:50], "offline_db"

# ── ROUTES ────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/sw.js")
def sw():
    return send_from_directory("static", "sw.js", mimetype="application/javascript")

# ── SEARCH ────────────────────────────────────────────────────────────────────
@app.route("/api/search", methods=["POST"])
def search():
    data  = request.json or {}
    query = data.get("query","").strip()
    ulat  = data.get("lat"); ulon = data.get("lon")
    if not query: return jsonify([])

    # Online: Nominatim (and save result offline)
    try:
        r = requests.get("https://nominatim.openstreetmap.org/search",
                         params={"q":query,"format":"json","limit":7,
                                 "accept-language":"en"},
                         headers={"User-Agent":"OffNavApp/5.0"}, timeout=5)
        results = r.json()
        out = []
        for p in results:
            name  = p.get("display_name","")
            short = name.split(",")[0]
            lat,lon = float(p["lat"]),float(p["lon"])
            save_place(name, lat, lon)
            out.append({"name":name,"short":short,"lat":lat,"lon":lon,"source":"online"})
        return jsonify(out)
    except: pass

    # Offline: local FTS DB
    return jsonify(search_local(query, ulat, ulon, limit=10))

@app.route("/api/history")
def history():
    conn = get_places_db()
    rows = conn.execute(
        "SELECT * FROM places WHERE source='user' ORDER BY used_at DESC LIMIT 20"
    ).fetchall()
    conn.close()
    return jsonify([{"name":r["name"],"short":r["name"],"lat":r["lat"],
                     "lon":r["lon"],"type":r["type"],"source":"history"} for r in rows])

@app.route("/api/save_dest", methods=["POST"])
def save_dest():
    d = request.json or {}
    if d.get("name") and d.get("lat") and d.get("lon"):
        save_place(d["name"], float(d["lat"]), float(d["lon"]))
    return jsonify({"ok": True})

# ── ROUTE ─────────────────────────────────────────────────────────────────────
@app.route("/api/route", methods=["POST"])
def get_route():
    data      = request.json
    origin    = [float(data["origin"][0]), float(data["origin"][1])]
    dest      = [float(data["dest"][0]),   float(data["dest"][1])]
    dest_name = data.get("dest_name","")
    want_alt  = data.get("alternative", True)
    if dest_name: save_place(dest_name, dest[0], dest[1])

    def parse_osrm(osrm_json, source_label):
        routes_out = []
        for ri, route in enumerate(osrm_json.get("routes",[])[:2]):
            legs  = route["legs"][0]
            steps = []
            for s in legs.get("steps",[]):
                man = s.get("maneuver",{})
                loc = man.get("location",[origin[1],origin[0]])
                steps.append({
                    "instruction": s.get("name","") or s.get("ref","") or "Continue",
                    "maneuver":    man.get("type",""),
                    "modifier":    man.get("modifier",""),
                    "distance":    round(s.get("distance",0)),
                    "duration":    round(s.get("duration",0)),
                    "location":    [loc[1], loc[0]],
                })
            refs  = " ".join(s.get("ref","")  for s in legs.get("steps",[]))
            names = " ".join(s.get("name","") for s in legs.get("steps",[]))
            has_toll = "toll" in names.lower()
            has_hw   = any(x in refs+names for x in ["NH","SH","Expressway","Highway","National"])
            rt = []
            if has_hw:   rt.append("Highway")
            if has_toll: rt.append("Toll road")
            if not rt:   rt.append("City roads")
            routes_out.append({
                "source":    source_label,
                "label":     ["Fastest","Alternative"][min(ri,1)],
                "index":     ri,
                "coords":    route["geometry"]["coordinates"],
                "distance":  round(route["distance"]/1000, 2),
                "duration":  round(route["duration"]/60, 1),
                "steps":     steps,
                "has_toll":  has_toll,
                "has_highway": has_hw,
                "road_types": rt,
            })
        return routes_out

    # 1. Local OSRM (offline routing — always tried first)
    if is_osrm():
        try:
            alts = "true" if want_alt else "false"
            url  = (f"{OSRM_URL}/route/v1/driving/"
                    f"{origin[1]},{origin[0]};{dest[1]},{dest[0]}"
                    f"?overview=full&geometries=geojson&steps=true&alternatives={alts}")
            r = requests.get(url, timeout=15)
            if r.status_code == 200:
                routes = parse_osrm(r.json(), "offline_osrm")
                if routes:
                    return jsonify({"routes": routes, "source": "offline_osrm"})
        except Exception as e:
            print(f"[route] local OSRM error: {e}")

    # 2. Online OSRM fallback (when local OSRM not running but internet available)
    try:
        url = (f"http://router.project-osrm.org/route/v1/driving/"
               f"{origin[1]},{origin[0]};{dest[1]},{dest[0]}"
               f"?overview=full&geometries=geojson&steps=true&alternatives=true")
        r = requests.get(url, timeout=8)
        if r.status_code == 200:
            routes = parse_osrm(r.json(), "online_osrm")
            if routes:
                return jsonify({"routes": routes, "source": "online_osrm"})
    except: pass

    # 3. No routing available
    d   = hav(origin, dest)
    brg = bearing(origin, dest)
    dirn = dir_name(brg)
    result = {
        "source":   "no_osrm",
        "label":    "⚠️ OSRM not running",
        "coords":   [[origin[1],origin[0]],[dest[1],dest[0]]],
        "distance": round(d,2),
        "duration": round(d/30*60,1),
        "steps": [
            {"instruction":f"⚠️ OSRM not running. Head {dirn} ({round(brg)}°), {round(d,1)} km to destination. Run start.bat to enable real routing.",
             "maneuver":"depart","modifier":"","distance":round(d*1000),
             "duration":round(d/30*3600),"location":list(origin)},
            {"instruction":"Arrive at destination","maneuver":"arrive",
             "modifier":"","distance":0,"duration":0,"location":list(dest)},
        ],
        "has_toll":False,"road_types":["⚠️ Run start.bat for real routing"],
        "bearing":round(brg),"direction":dirn,"needs_osrm":True,
    }
    return jsonify({"routes":[result],"source":"no_osrm"})

# ── NEARBY ────────────────────────────────────────────────────────────────────
@app.route("/api/nearby", methods=["POST"])
def nearby():
    data     = request.json
    lat,lon  = float(data["lat"]),  float(data["lon"])
    radius   = int(data.get("radius", 3000))
    category = data.get("category","all")

    amenities = CATEGORY_TYPES.get(category, CATEGORY_TYPES["all"])

    # 1. Online Overpass (best results)
    try:
        union = "\n".join(f'  node["amenity"="{a}"](around:{radius},{lat},{lon});'
                          for a in amenities)
        q = f'[out:json][timeout:14];\n(\n{union}\n);\nout body;'
        r = requests.post("https://overpass-api.de/api/interpreter",
                          data={"data":q}, timeout=16)
        if r.status_code == 200:
            places = []
            for el in r.json().get("elements",[])[:100]:
                tags    = el.get("tags",{})
                amenity = tags.get("amenity","")
                name    = tags.get("name") or amenity.replace("_"," ").title()
                elat,elon = el.get("lat"),el.get("lon")
                if not elat or not elon: continue
                places.append({
                    "id":el["id"],"name":name,"amenity":amenity,
                    "icon":amenity_icon(amenity),"lat":elat,"lon":elon,
                    "phone":tags.get("phone",""),"address":"",
                    "distance":round(hav([lat,lon],[elat,elon])*1000),
                })
            places.sort(key=lambda x:x["distance"])
            # Also save to local amenities DB for future offline use
            _cache_amenities_to_local(places)
            return jsonify({"source":"online","places":places})
    except Exception as e:
        print(f"[nearby] Overpass error: {e}")

    # 2. Offline: local amenities SQLite DB (from extract_amenities.py)
    places, source = nearby_from_local_db(lat, lon, radius, category)
    if places:
        return jsonify({"source":"offline_db","places":places})

    # 3. Nothing available
    return jsonify({"source":"offline_empty","places":[]})

def _cache_amenities_to_local(places):
    """Cache online results into local DB for future offline use."""
    if not os.path.exists(AMENITIES_DB):
        return
    try:
        conn = sqlite3.connect(AMENITIES_DB)
        for p in places:
            if not p.get("name"): continue
            conn.execute("""
                INSERT OR IGNORE INTO amenities(osm_id,name,type,icon,lat,lon,phone)
                VALUES(?,?,?,?,?,?,?)
            """, (str(p.get("id","")), p["name"], p["amenity"],
                  amenity_icon(p["amenity"]), p["lat"], p["lon"], p.get("phone","")))
        conn.commit(); conn.close()
    except: pass

# ── STATUS ────────────────────────────────────────────────────────────────────
@app.route("/api/status")
def status():
    internet   = is_internet()
    osrm_ok    = is_osrm()
    am_ready   = amenities_db_ready()

    # Count places
    try:
        pc = get_places_db()
        places_n = pc.execute("SELECT COUNT(*) FROM places").fetchone()[0]
        pc.close()
    except: places_n = 0

    # Count amenities
    amenities_n = 0
    if am_ready:
        try:
            ac = get_amenities_db()
            amenities_n = ac.execute("SELECT COUNT(*) FROM amenities").fetchone()[0]
            ac.close()
        except: pass

    return jsonify({
        "internet":        internet,
        "osrm_running":    osrm_ok,
        "amenities_ready": am_ready,
        "amenities_count": amenities_n,
        "places_count":    places_n,
        "fully_offline":   osrm_ok and am_ready,
    })

# ── STARTUP ───────────────────────────────────────────────────────────────────
ensure_places_db()

if __name__ == "__main__":
    osrm_ok  = is_osrm()
    am_ready = amenities_db_ready()
    print("\n" + "="*60)
    print("  OffNav — Offline Navigation System")
    print("="*60)
    print(f"  Website:    http://localhost:5000")
    print(f"  OSRM:       {'✅ Running (offline routing active)' if osrm_ok else '❌ Not running — run start.bat'}")
    print(f"  Amenities:  {'✅ Ready (offline nearby places active)' if am_ready else '❌ Run setup.bat to extract amenities'}")
    print("="*60 + "\n")
    app.run(debug=False, port=5000, host="0.0.0.0")