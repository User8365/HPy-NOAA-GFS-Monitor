import requests
import os
import json
from datetime import datetime

# --- CONFIGURATION ---
TOKEN = os.getenv('DISCORD_TOKEN')
CHANNEL_ID = os.getenv('CHANNEL_ID')
BASE_URL = "https://nomads.ncep.noaa.gov/pub/data/nccf/com/gfs/prod/"

def send_discord_alert(message):
    """Envoie un message via l'API Discord."""
    url = f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages"
    headers = {"Authorization": f"Bot {TOKEN}", "Content-Type": "application/json"}
    payload = {"embeds": [{
        "title": "📡 Surveillance NOAA GFS 0.25°",
        "description": message,
        "color": 0x00ff00 if "complet" in message else 0x3498db,
        "timestamp": datetime.utcnow().isoformat()
    }]}
    requests.post(url, headers=headers, json=payload)

def check_noaa():
    today = datetime.utcnow().strftime('%Y%m%d')
    # Chargement de l'état précédent
    try:
        with open('status.json', 'r') as f:
            status = json.load(f)
    except:
        status = {"last_cycle": "", "is_completed": False}

    # 1. Vérifier quel est le cycle le plus récent sur le serveur
    try:
        response = requests.get(f"{BASE_URL}gfs.{today}/", timeout=15)
        if response.status_code != 200: return
    except: return

    # Trouver les cycles (00, 06, 12, 18) présents dans la page
    found_cycles = [c for c in ["18", "12", "06", "00"] if f"{c}/" in response.text]
    if not found_cycles: return
    
    current_cycle = found_cycles[0] # Le plus récent
    cycle_id = f"{today}_{current_cycle}"

    # 2. Logique de détection
    # CAS A : Nouveau cycle détecté (Début)
    if cycle_id != status["last_cycle"]:
        send_discord_alert(f"🚀 **Début du transfert** détecté pour le cycle **{current_cycle}z**.\nLes fichiers commencent à arriver sur NOMADS.")
        status = {"last_cycle": cycle_id, "is_completed": False}

    # CAS B : Cycle en cours, on cherche si le dernier fichier (f384) est arrivé
    elif not status["is_completed"]:
        # On vérifie l'existence du fichier d'index .idx du f384
        file_check = f"gfs.{today}/{current_cycle}/atmos/gfs.t{current_cycle}z.pgrb2.0p25.f384.idx"
        check_res = requests.head(f"{BASE_URL}{file_check}")
        
        if check_res.status_code == 200:
            send_discord_alert(f"✅ **Cycle complet !**\nLe fichier final (f384) du cycle **{current_cycle}z** est disponible.")
            status["is_completed"] = True

    # Sauvegarde de l'état
    with open('status.json', 'w') as f:
        json.dump(status, f)

if __name__ == "__main__":
    check_noaa()
