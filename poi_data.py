# poi_data.py
# Preloaded Points of Interest (offline data)

POIS = {
    "A": {  # City Center
        "hospitals":       ["Apollo Hospital - 0.5km", "Care Hospital - 1.2km"],
        "police":          ["MG Road Police Station - 0.3km"],
        "medical_stores":  ["MedPlus Pharmacy - 0.2km", "Apollo Pharmacy - 0.6km"],
        "petrol_pumps":    ["HPCL Pump - 0.4km", "Indian Oil - 0.9km"],
        "restaurants":     ["Hotel Shadab - 0.3km", "Paradise Biryani - 0.5km"],
    },
    "B": {  # Railway Station
        "hospitals":       ["Railway Hospital - 0.4km", "Niloufer Hospital - 1.5km"],
        "police":          ["Railway Police Station - 0.1km"],
        "medical_stores":  ["Station Pharmacy - 0.2km"],
        "petrol_pumps":    ["BPCL Pump - 0.7km"],
        "restaurants":     ["Cafe Coffee Day - 0.1km", "Subway - 0.3km"],
    },
    "C": {  # Airport
        "hospitals":       ["Airport Medical Centre - 0.2km"],
        "police":          ["Airport Police - 0.1km"],
        "medical_stores":  ["Terminal Pharmacy - 0.3km"],
        "petrol_pumps":    ["Airport Fuel Station - 1.0km"],
        "restaurants":     ["Food Court Terminal 1 - 0.1km"],
    },
    "D": {  # Old City
        "hospitals":       ["Osmania Hospital - 0.8km", "Government Hospital - 1.0km"],
        "police":          ["Old City Police - 0.5km", "Charminar Police - 0.9km"],
        "medical_stores":  ["Charminar Medical - 0.3km"],
        "petrol_pumps":    ["Old City Petrol - 0.6km"],
        "restaurants":     ["Shadab Hotel - 0.4km", "Nimrah Cafe - 0.2km"],
    },
    "E": {  # Tech Park
        "hospitals":       ["Medicover Hospital - 1.2km"],
        "police":          ["Hitech City Police - 0.8km"],
        "medical_stores":  ["Wellness Forever - 0.5km"],
        "petrol_pumps":    ["Shell Pump - 0.6km"],
        "restaurants":     ["Cafe Niloufer - 0.3km", "Ohri's - 0.7km"],
    },
    "F": {  # University
        "hospitals":       ["University Health Center - 0.1km"],
        "police":          ["University Police Post - 0.2km"],
        "medical_stores":  ["Campus Pharmacy - 0.1km"],
        "petrol_pumps":    ["Campus Fuel - 0.9km"],
        "restaurants":     ["University Canteen - 0.1km", "Campus Cafe - 0.2km"],
    },
    "G": {  # Hospital Zone
        "hospitals":       ["NIMS Hospital - 0.1km", "Yashoda Hospital - 0.3km", "Rainbow Hospital - 0.5km"],
        "police":          ["Hospital Zone Police - 0.4km"],
        "medical_stores":  ["24hr MedPlus - 0.1km", "Yashoda Pharmacy - 0.2km"],
        "petrol_pumps":    ["HP Petrol - 0.5km"],
        "restaurants":     ["Hospital Canteen - 0.1km"],
    },
    "H": {  # Market Area
        "hospitals":       ["Market Clinic - 0.6km"],
        "police":          ["Market Police Station - 0.3km"],
        "medical_stores":  ["Market Pharmacy - 0.1km", "24hr Medicals - 0.4km"],
        "petrol_pumps":    ["Market Fuel - 0.2km", "IOCL Pump - 0.5km"],
        "restaurants":     ["Market Biryani - 0.2km", "Street Food Hub - 0.1km"],
    },
}

def get_nearest_poi(location: str) -> dict:
    return POIS.get(location, {})

def get_sos_info(location: str) -> dict:
    poi = POIS.get(location, {})
    return {
        "nearest_hospital": poi.get("hospitals", ["Unknown"])[0],
        "nearest_police":   poi.get("police",    ["Unknown"])[0],
        "sos_message": f"🚨 EMERGENCY! Nearest hospital: {poi.get('hospitals',['Unknown'])[0]} | Police: {poi.get('police',['Unknown'])[0]}"
    }
