# map_data.py
# Simulated offline map using graph (node = location, edge = road)

import heapq

# Locations (nodes)
LOCATIONS = {
    "A": {"name": "City Center",       "lat": 17.3850, "lng": 78.4867},
    "B": {"name": "Railway Station",   "lat": 17.3900, "lng": 78.4800},
    "C": {"name": "Airport",           "lat": 17.2403, "lng": 78.4294},
    "D": {"name": "Old City",          "lat": 17.3616, "lng": 78.4747},
    "E": {"name": "Tech Park",         "lat": 17.4435, "lng": 78.3772},
    "F": {"name": "University",        "lat": 17.4156, "lng": 78.4536},
    "G": {"name": "Hospital Zone",     "lat": 17.3700, "lng": 78.5000},
    "H": {"name": "Market Area",       "lat": 17.3800, "lng": 78.4700},
}

# Roads (edges) — (distance in km, time in minutes)
ROADS = {
    "A": [("B", 2.5, 6),  ("H", 1.2, 3),  ("F", 5.0, 12)],
    "B": [("A", 2.5, 6),  ("C", 8.0, 20), ("G", 3.0, 8)],
    "C": [("B", 8.0, 20), ("D", 6.0, 15)],
    "D": [("C", 6.0, 15), ("H", 2.0, 5),  ("G", 4.0, 10)],
    "E": [("F", 3.0, 8),  ("A", 7.0, 18)],
    "F": [("E", 3.0, 8),  ("A", 5.0, 12), ("B", 4.0, 10)],
    "G": [("B", 3.0, 8),  ("D", 4.0, 10), ("H", 2.5, 6)],
    "H": [("A", 1.2, 3),  ("D", 2.0, 5),  ("G", 2.5, 6)],
}

def dijkstra(start: str, end: str):
    """Find shortest path and ETA between two locations."""
    distances = {node: float('inf') for node in LOCATIONS}
    times = {node: float('inf') for node in LOCATIONS}
    distances[start] = 0
    times[start] = 0
    prev = {node: None for node in LOCATIONS}
    pq = [(0, 0, start)]  # (distance, time, node)

    while pq:
        dist, time, node = heapq.heappop(pq)
        if node == end:
            break
        for neighbor, road_dist, road_time in ROADS.get(node, []):
            new_dist = dist + road_dist
            new_time = time + road_time
            if new_dist < distances[neighbor]:
                distances[neighbor] = new_dist
                times[neighbor] = new_time
                prev[neighbor] = node
                heapq.heappush(pq, (new_dist, new_time, neighbor))

    # Reconstruct path
    path = []
    node = end
    while node is not None:
        path.append(node)
        node = prev[node]
    path.reverse()

    if path[0] != start:
        return None, None, None  # No path found

    return path, round(distances[end], 2), round(times[end], 1)