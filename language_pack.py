# language_pack.py
# Navigation instructions in multiple languages

DIRECTIONS = {
    "English": {
        "start":    "Start from {start}. Head towards {next_stop}.",
        "turn":     "At {current}, turn towards {next_stop}. Distance: {dist}km.",
        "arrive":   "You have arrived at {destination}! Total distance: {total_dist}km. ETA was {eta} minutes.",
        "sos":      "EMERGENCY ALERT! Nearest hospital: {hospital}. Nearest police: {police}.",
        "poi":      "Nearby places at {location} — Hospitals: {hospitals} | Police: {police} | Medical: {medical} | Petrol: {petrol} | Restaurants: {restaurants}",
    },
    "Hindi": {
        "start":    "{start} से शुरू करें। {next_stop} की ओर बढ़ें।",
        "turn":     "{current} पर {next_stop} की तरफ मुड़ें। दूरी: {dist}km।",
        "arrive":   "आप {destination} पहुंच गए हैं! कुल दूरी: {total_dist}km। अनुमानित समय: {eta} मिनट।",
        "sos":      "आपातकाल! नजदीकी अस्पताल: {hospital}। नजदीकी पुलिस: {police}।",
        "poi":      "{location} के पास — अस्पताल: {hospitals} | पुलिस: {police} | मेडिकल: {medical} | पेट्रोल: {petrol} | रेस्तरां: {restaurants}",
    },
    "Telugu": {
        "start":    "{start} నుండి ప్రారంభించండి. {next_stop} వైపు వెళ్ళండి.",
        "turn":     "{current} వద్ద {next_stop} వైపు తిరగండి. దూరం: {dist}km.",
        "arrive":   "మీరు {destination} చేరుకున్నారు! మొత్తం దూరం: {total_dist}km. అంచనా సమయం: {eta} నిమిషాలు.",
        "sos":      "అత్యవసరం! దగ్గరలో ఉన్న ఆసుపత్రి: {hospital}. పోలీసు: {police}.",
        "poi":      "{location} సమీపంలో — ఆసుపత్రులు: {hospitals} | పోలీసు: {police} | మెడికల్: {medical} | పెట్రోల్: {petrol} | రెస్టారెంట్లు: {restaurants}",
    },
    "Tamil": {
        "start":    "{start} இலிருந்து தொடங்குங்கள். {next_stop} நோக்கி செல்லுங்கள்.",
        "turn":     "{current} இல் {next_stop} திசையில் திரும்புங்கள். தூரம்: {dist}km.",
        "arrive":   "நீங்கள் {destination} வந்துவிட்டீர்கள்! மொத்த தூரம்: {total_dist}km. மதிப்பிடப்பட்ட நேரம்: {eta} நிமிடங்கள்.",
        "sos":      "அவசரநிலை! அருகில் உள்ள மருத்துவமனை: {hospital}. காவல்துறை: {police}.",
        "poi":      "{location} அருகில் — மருத்துவமனைகள்: {hospitals} | காவல்: {police} | மருந்தகம்: {medical} | பெட்ரோல்: {petrol} | உணவகங்கள்: {restaurants}",
    },
}

def get_instruction(lang: str, key: str, **kwargs) -> str:
    lang_data = DIRECTIONS.get(lang, DIRECTIONS["English"])
    template = lang_data.get(key, "")
    try:
        return template.format(**kwargs)
    except KeyError:
        return template