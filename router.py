"""
router.py — Offline A* routing engine
Reads road graph from data/roads.db (built by setup.py).
Downloads tiles on-demand when online.
Falls back to straight-line when no graph data available.
"""

import sqlite3, math, heapq, os, threading
from datetime import datetime

DB_PATH = "data/roads.db"
_lock   = threading.Lock()
_conn   = None

ROAD_SPEEDS = {
    "motorway":80,"motorway_link":60,"trunk":70,"trunk_link":55,
    "primary":60,"primary_link":50,"secondary":50,"secondary_link":40,
    "tertiary":40,"tertiary_link":35,"unclassified":30,"residential":25,
    "service":20,"track":15,"path":10,"footway":5,"cycleway":15,
    "living_street":20,"road":30,
}

def get_conn():
    global _conn
    if _conn is None:
        if not os.path.exists(DB_PATH):
            _init_empty_db()
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA cache_size=10000")
    return _conn

def _init_empty_db():
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS nodes (
        id INTEGER PRIMARY KEY, lat REAL, lon REAL, tile_lat REAL, tile_lon REAL)""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_nl ON nodes(lat,lon)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_nt ON nodes(tile_lat,tile_lon)")
    conn.execute("""CREATE TABLE IF NOT EXISTS edges (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_node INTEGER, to_node INTEGER,
        length_m REAL, speed_kmh REAL,
        road_type TEXT, name TEXT, oneway INTEGER,
        tile_lat REAL, tile_lon REAL)""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ef ON edges(from_node)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_et ON edges(to_node)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_etile ON edges(tile_lat,tile_lon)")
    conn.execute("""CREATE TABLE IF NOT EXISTS downloaded_tiles (
        tile_lat REAL, tile_lon REAL,
        downloaded_at TEXT, node_count INTEGER, edge_count INTEGER,
        PRIMARY KEY(tile_lat,tile_lon))""")
    conn.commit()
    conn.close()

def hav_m(a, b):
    R = 6371000.0
    p1,p2 = math.radians(a[0]),math.radians(b[0])
    dp = math.radians(b[0]-a[0]); dl = math.radians(b[1]-a[1])
    h = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return R * 2 * math.asin(math.sqrt(max(0,min(1,h))))

def hav_km(a, b):
    return hav_m(a,b) / 1000.0

def bearing(a, b):
    la1,lo1 = math.radians(a[0]),math.radians(a[1])
    la2,lo2 = math.radians(b[0]),math.radians(b[1])
    dlo = lo2-lo1
    x = math.sin(dlo)*math.cos(la2)
    y = math.cos(la1)*math.sin(la2)-math.sin(la1)*math.cos(la2)*math.cos(dlo)
    return (math.degrees(math.atan2(x,y))+360)%360

def dir_name(deg):
    return ["North","NE","East","SE","South","SW","West","NW"][round(deg/45)%8]

def tile_key(lat, lon, step=0.5):
    return round(lat/step)*step, round(lon/step)*step

# ── Tile availability ────────────────────────────────────────────────────────
def has_tile(lat, lon):
    tl, tlo = tile_key(lat, lon)
    conn = get_conn()
    row = conn.execute(
        "SELECT 1 FROM downloaded_tiles WHERE tile_lat=? AND tile_lon=?",
        (tl, tlo)
    ).fetchone()
    return row is not None

def list_downloaded_tiles():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM downloaded_tiles").fetchall()
    return [dict(r) for r in rows]

def get_tile_count():
    conn = get_conn()
    return conn.execute("SELECT COUNT(*) FROM downloaded_tiles").fetchone()[0]

def get_node_count():
    conn = get_conn()
    return conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]

def get_edge_count():
    conn = get_conn()
    return conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]

# ── Download tile on-demand ──────────────────────────────────────────────────
def download_tile(lat, lon, radius_m=25000):
    """Download road tile for (lat,lon) using osmnx. Requires internet."""
    tl, tlo = tile_key(lat, lon)
    conn = get_conn()

    # Check if already downloaded
    if conn.execute("SELECT 1 FROM downloaded_tiles WHERE tile_lat=? AND tile_lon=?",
                    (tl,tlo)).fetchone():
        return True, "already_exists"

    try:
        import osmnx as ox
        print(f"[router] Downloading tile ({tl:.1f},{tlo:.1f}) r={radius_m}m…")

        G = ox.graph_from_point((lat, lon), dist=radius_m,
                                network_type='drive', simplify=True)
        nc, ec = 0, 0
        with _lock:
            for node_id, d in G.nodes(data=True):
                nlat, nlon = d['y'], d['x']
                ntl, ntlo = tile_key(nlat, nlon)
                conn.execute(
                    "INSERT OR IGNORE INTO nodes(id,lat,lon,tile_lat,tile_lon) VALUES(?,?,?,?,?)",
                    (node_id, nlat, nlon, ntl, ntlo))
                nc += 1

            for u, v, d in G.edges(data=True):
                length = d.get('length', 0)
                hw = d.get('highway','road')
                if isinstance(hw, list): hw = hw[0]
                speed = ROAD_SPEEDS.get(hw, 30)
                name  = d.get('name','') or ''
                if isinstance(name, list): name = name[0]
                ow = 1 if d.get('oneway', False) else 0
                ud = G.nodes[u]
                etl, etlo = tile_key(ud['y'], ud['x'])
                conn.execute("""INSERT INTO edges
                    (from_node,to_node,length_m,speed_kmh,road_type,name,oneway,tile_lat,tile_lon)
                    VALUES(?,?,?,?,?,?,?,?,?)""",
                    (u,v,length,speed,hw,name,ow,etl,etlo))
                if not ow:
                    conn.execute("""INSERT INTO edges
                        (from_node,to_node,length_m,speed_kmh,road_type,name,oneway,tile_lat,tile_lon)
                        VALUES(?,?,?,?,?,?,?,?,?)""",
                        (v,u,length,speed,hw,name,ow,etl,etlo))
                ec += 1

            conn.execute("""INSERT OR REPLACE INTO downloaded_tiles
                (tile_lat,tile_lon,downloaded_at,node_count,edge_count)
                VALUES(?,?,datetime('now'),?,?)""", (tl,tlo,nc,ec))
            conn.commit()
        print(f"[router] ✓ Tile ({tl:.1f},{tlo:.1f}): {nc} nodes, {ec} edges")
        return True, f"downloaded {nc} nodes {ec} edges"

    except Exception as e:
        print(f"[router] Tile download failed: {e}")
        return False, str(e)

# ── Nearest node search ──────────────────────────────────────────────────────
def nearest_node(lat, lon, search_radius_deg=0.5):
    """Find nearest road node to (lat,lon)."""
    conn = get_conn()
    # Search expanding radius
    for rad in [0.1, 0.3, 0.5, 1.0, 2.0]:
        rows = conn.execute("""
            SELECT id, lat, lon FROM nodes
            WHERE lat BETWEEN ? AND ? AND lon BETWEEN ? AND ?
            LIMIT 500
        """, (lat-rad, lat+rad, lon-rad, lon+rad)).fetchall()
        if rows:
            best = min(rows, key=lambda r: hav_m([lat,lon],[r['lat'],r['lon']]))
            return best['id'], best['lat'], best['lon']
    return None, None, None

# ── A* routing ────────────────────────────────────────────────────────────────
def astar_route(origin, dest):
    """
    A* shortest path between origin and dest using local road graph.
    origin/dest: [lat, lon]
    Returns route dict or None.
    """
    conn = get_conn()

    on_id, on_lat, on_lon = nearest_node(origin[0], origin[1])
    dn_id, dn_lat, dn_lon = nearest_node(dest[0],   dest[1])

    if on_id is None or dn_id is None:
        return None, "no_nodes_found"

    if on_id == dn_id:
        return None, "same_node"

    # Preload adjacency from DB for relevant area
    # Get bounding box covering origin→dest + buffer
    min_lat = min(origin[0], dest[0]) - 0.3
    max_lat = max(origin[0], dest[0]) + 0.3
    min_lon = min(origin[1], dest[1]) - 0.3
    max_lon = max(origin[1], dest[1]) + 0.3

    print(f"[astar] Loading graph {min_lat:.2f}..{max_lat:.2f}, {min_lon:.2f}..{max_lon:.2f}")

    # Load nodes in bounding box
    node_coords = {}
    rows = conn.execute("""
        SELECT id, lat, lon FROM nodes
        WHERE lat BETWEEN ? AND ? AND lon BETWEEN ? AND ?
    """, (min_lat, max_lat, min_lon, max_lon)).fetchall()
    for r in rows:
        node_coords[r['id']] = (r['lat'], r['lon'])

    if not node_coords:
        return None, "no_graph_data_in_area"

    # Load edges in bounding box
    adj = {}  # node_id -> [(neighbor_id, cost_s, length_m, road_type, name)]
    rows = conn.execute("""
        SELECT from_node, to_node, length_m, speed_kmh, road_type, name
        FROM edges
        WHERE tile_lat BETWEEN ? AND ? AND tile_lon BETWEEN ? AND ?
    """, (min_lat-0.5, max_lat+0.5, min_lon-0.5, max_lon+0.5)).fetchall()

    for r in rows:
        fn, tn = r['from_node'], r['to_node']
        cost = r['length_m'] / (r['speed_kmh'] * 1000/3600)  # seconds
        if fn not in adj: adj[fn] = []
        adj[fn].append((tn, cost, r['length_m'], r['road_type'], r['name']))

    print(f"[astar] Graph: {len(node_coords)} nodes, {sum(len(v) for v in adj.values())} edges")

    if on_id not in adj and on_id not in node_coords:
        return None, "origin_node_not_in_graph"

    # A* algorithm
    def h(node_id):
        if node_id not in node_coords: return float('inf')
        nc = node_coords[node_id]
        dc = node_coords.get(dn_id, (dest[0], dest[1]))
        return hav_m(nc, dc) / 30  # heuristic: max 30m/s

    g_score = {on_id: 0}
    f_score = {on_id: h(on_id)}
    came_from = {}
    open_set = [(f_score[on_id], on_id)]
    closed = set()
    max_iter = 200000

    for iteration in range(max_iter):
        if not open_set:
            break
        _, current = heapq.heappop(open_set)
        if current == dn_id:
            # Reconstruct path
            path = []
            node = dn_id
            while node in came_from:
                path.append(node)
                node = came_from[node]
            path.append(on_id)
            path.reverse()

            # Build coordinate list and compute stats
            coords = []
            total_dist = 0.0
            total_time = 0.0
            for i, nid in enumerate(path):
                nc = node_coords.get(nid)
                if nc:
                    coords.append(list(nc))
                    if i > 0:
                        prev_nc = node_coords.get(path[i-1])
                        if prev_nc:
                            seg = hav_m(prev_nc, nc)
                            total_dist += seg
                            total_time += seg / (40*1000/3600)  # 40km/h avg

            steps = build_steps(coords, list(origin), list(dest))
            return {
                "source":     "offline_graph",
                "label":      "Offline route (local road network)",
                "coords":     [[c[1],c[0]] for c in coords],
                "distance":   round(total_dist/1000, 2),
                "duration":   round(total_time/60, 1),
                "steps":      steps,
                "has_toll":   False,
                "road_types": ["Local roads"],
                "node_count": len(path),
            }, None

        if current in closed:
            continue
        closed.add(current)

        for neighbor, cost, length, road_type, name in adj.get(current, []):
            if neighbor in closed:
                continue
            tentative_g = g_score.get(current, float('inf')) + cost
            if tentative_g < g_score.get(neighbor, float('inf')):
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                f = tentative_g + h(neighbor)
                f_score[neighbor] = f
                heapq.heappush(open_set, (f, neighbor))

    return None, f"no_path_found (explored {len(closed)} nodes)"

# ── Step generation ──────────────────────────────────────────────────────────
def build_steps(coords, origin, dest):
    if len(coords) < 2:
        d = hav_km(origin, dest)
        brg = bearing(origin, dest)
        return [
            {"instruction": f"Head {dir_name(brg)} towards destination",
             "maneuver":"depart","modifier":"","distance":round(d*1000),
             "duration":round(d/30*3600),"location":origin},
            {"instruction":"Arrive at destination","maneuver":"arrive",
             "modifier":"","distance":0,"duration":0,"location":dest},
        ]

    steps = [{"instruction":"Depart — follow the highlighted route",
               "maneuver":"depart","modifier":"","distance":0,"duration":0,
               "location":list(coords[0])}]
    THRESH = 25
    chunk = 0.0

    for i in range(1, len(coords)-1):
        seg = hav_m(coords[i-1], coords[i])
        chunk += seg
        b1 = bearing(coords[i-1], coords[i])
        b2 = bearing(coords[i],   coords[i+1])
        diff = (b2-b1+360)%360
        if diff > 180: diff -= 360
        if abs(diff) >= THRESH:
            if   diff >=  90: mod = "right"
            elif diff <= -90: mod = "left"
            elif diff >   0:  mod = "slight right"
            else:             mod = "slight left"
            steps.append({
                "instruction": f"Turn {mod}",
                "maneuver":"turn","modifier":mod,
                "distance":round(chunk),
                "duration":round(chunk/(40*1000/3600)),
                "location":list(coords[i])
            })
            chunk = 0.0

    steps.append({"instruction":"Arrive at your destination",
                  "maneuver":"arrive","modifier":"","distance":0,"duration":0,
                  "location":list(dest)})
    return steps

# ── Straight-line fallback ────────────────────────────────────────────────────
def straight_line(origin, dest):
    d = hav_km(origin, dest)
    brg = bearing(origin, dest)
    dirn = dir_name(brg)
    pts = [[origin[0]+(dest[0]-origin[0])*t, origin[1]+(dest[1]-origin[1])*t]
           for t in [0,.25,.5,.75,1]]
    return {
        "source":   "offline_estimate",
        "label":    "Straight-line estimate — download map for real roads",
        "coords":   [[p[1],p[0]] for p in pts],
        "distance": round(d, 2),
        "duration": round(d/30*60, 1),
        "steps": [
            {"instruction": f"Head {dirn} ({round(brg)}°) — {round(d,1)} km",
             "maneuver":"depart","modifier":"","distance":round(d*1000),
             "duration":round(d/30*3600),"location":list(origin)},
            {"instruction":"Arrive at destination","maneuver":"arrive",
             "modifier":"","distance":0,"duration":0,"location":list(dest)},
        ],
        "has_toll":False,"road_types":["Direct line estimate"],
        "bearing":round(brg),"direction":dirn,"needs_download":True,
    }

# ── Route entry point ─────────────────────────────────────────────────────────
def route(origin, dest):
    """
    Main routing function. Tries A* on local graph.
    If no graph data, auto-triggers download if online.
    Falls back to straight-line.
    """
    result, err = astar_route(origin, dest)
    if result:
        return result

    print(f"[router] A* failed: {err}")

    # If no nodes, try downloading tile first
    if err in ("no_nodes_found", "no_graph_data_in_area"):
        print("[router] No local data — trying download…")
        ok, msg = download_tile(origin[0], origin[1], radius_m=20000)
        if ok:
            result, err2 = astar_route(origin, dest)
            if result:
                return result
        # Also try dest tile
        ok2, msg2 = download_tile(dest[0], dest[1], radius_m=20000)
        if ok2:
            result, err3 = astar_route(origin, dest)
            if result:
                return result

    return straight_line(origin, dest)