import requests
import os
import json
from datetime import datetime

# --- CONFIGURATION ---
TOKEN = os.getenv('DISCORD_TOKEN')
CHANNEL_ID = os.getenv('CHANNEL_ID')
MENTION = "<@&873137469770592267>"
BASE_URL = "https://nomads.ncep.noaa.gov/pub/data/nccf/com/gfs/prod/"

# --- VOS MESSAGES RECALÉS SUR L'HEURE FRANÇAISE ---
MESSAGES_DEBUT = {
    "00": "🌙 **GRIB 00Z en préparation** (Arrivée prévue au petit matin...)",
    "06": "🌤 **Chargement du GRIB 06Z en cours** (Prêt pour la pause déjeuner !)",
    "12": "🌆 **GRIB 12Z en route** (Le run du soir arrive...)",
    "18": "🌑 **GRIB 18Z lancé** (Calcul pour la nuit en cours...)"
}

MESSAGES_FIN = {
    "00": "☕ **GRIB 00Z DISPONIBLE !** Bonjour l'équipe, les données du réveil sont là.\n **Et Bonne Fête aux {saint} !** 🥳",
    "06": "🍴 **GRIB 06Z DISPONIBLE !** Juste à temps pour le point de la mi-journée. Bon app' les HPy !",
    "12": "🍹 **GRIB 12Z DISPONIBLE !** Les prévisions pour la soirée !",
    "18": "💤 **GRIB 18Z DISPONIBLE !** Le grib des noctambules... 🥱😴"
}

def get_saint_du_jour():
    """Récupère le prénom du jour via l'API Nominis"""
    try:
        r = requests.get("https://nominis.cef.fr/json/nominis.php", timeout=5)
        data = r.json()
        return data['saint']['main']['nom']
    except:
        return "tout le monde"

def log_activity(message):
    """Ajoute une ligne et garde seulement les 3000 dernières lignes"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    new_line = f"[{timestamp}] {message}\n"
    lines = []
    if os.path.exists('activity.log'):
        with open('activity.log', 'r') as f:
            lines = f.readlines()
    lines.append(new_line)
    if len(lines) > 3000:
        lines = lines[-3000:]
    with open('activity.log', 'w') as f:
        f.writelines(lines)

def send_discord_alert(is_success=False, cycle_h=""):
    url = f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages"
    headers = {"Authorization": f"Bot {TOKEN}", "Content-Type": "application/json"}
    color = 0x00ff00 if is_success else 0xcc00cc
    
    if is_success:
        raw_msg = MESSAGES_FIN.get(cycle_h, f"Cycle {cycle_h}z terminé.")
        if cycle_h == "00":
            saint = get_saint_du_jour()
            msg = raw_msg.format(saint=saint)
        else:
            msg = raw_msg
    else:
        msg = MESSAGES_DEBUT.get(cycle_h, f"Début du cycle {cycle_h}z.")

    payload = {
        "content": MENTION,
        "embeds": [{
            "title": f"🛰 GFS 0.25° | Actualisation {cycle_h}z",
            "description": msg,
            "color": color,
            "timestamp": datetime.utcnow().isoformat(),
            "footer": {"text": "NOMADS NOAA Server Monitoring"}
        }]
    }
    requests.post(url, headers=headers, json=payload)

def check_noaa():
    today = datetime.utcnow().strftime('%Y%m%d')
    try:
        with open('status.json', 'r') as f:
            status = json.load(f)
    except:
        status = {"last_cycle": "", "is_completed": False}

    try:
        response = requests.get(f"{BASE_URL}gfs.{today}/", timeout=15)
        if response.status_code != 200: return
    except: return

    found_cycles = [c for c in ["18", "12", "06", "00"] if f"{c}/" in response.text]
    if not found_cycles: return
    
    current_cycle = found_cycles[0]
    cycle_id = f"{today}_{current_cycle}"

    if cycle_id != status["last_cycle"]:
        send_discord_alert(is_success=False, cycle_h=current_cycle)
        log_activity(f"ALERTE: Nouveau cycle {current_cycle}z")
        status = {"last_cycle": cycle_id, "is_completed": False}

    elif not status["is_completed"]:
        file_check = f"gfs.{today}/{current_cycle}/atmos/gfs.t{current_cycle}z.pgrb2.0p25.f384.idx"
        check_res = requests.head(f"{BASE_URL}{file_check}")
        
        if check_res.status_code == 200:
            send_discord_alert(is_success=True, cycle_h=current_cycle)
            log_activity(f"ALERTE: Cycle {current_cycle}z COMPLET.")
            status["is_completed"] = True

    with open('status.json', 'w') as f:
        json.dump(status, f)

if __name__ == "__main__":
    check_noaa()
