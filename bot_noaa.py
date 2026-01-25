import requests
import os
import json
from datetime import datetime

# --- CONFIGURATION ---
TOKEN = os.getenv('DISCORD_TOKEN')
CHANNEL_ID = os.getenv('CHANNEL_ID')
BASE_URL = "https://nomads.ncep.noaa.gov/pub/data/nccf/com/gfs/prod/"

def log_activity(message):
    """Ajoute une ligne horodatée au fichier activity.log"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open('activity.log', 'a') as f:
        f.write(f"[{timestamp}] {message}\n")

def send_discord_alert(message, is_success=False):
    url = f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages"
    headers = {"Authorization": f"Bot {TOKEN}", "Content-Type": "application/json"}
    color = 0x00ff00 if is_success else 0x3498db
    payload = {"embeds": [{
        "title": "📡 Surveillance GFS 0.25°",
        "description": message,
        "color": color,
        "timestamp": datetime.utcnow().isoformat()
    }]}
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
        if response.status_code != 200:
            log_activity(f"ERREUR: Serveur NOAA injoignable (Code {response.status_code})")
            return
    except Exception as e:
        log_activity(f"ERREUR Connexion: {str(e)}")
        return

    found_cycles = [c for c in ["18", "12", "06", "00"] if f"{c}/" in response.text]
    if not found_cycles:
        log_activity("INFO: Aucun cycle trouvé pour aujourd'hui pour le moment.")
        return
    
    current_cycle = found_cycles[0]
    cycle_id = f"{today}_{current_cycle}"

    # CAS A : Nouveau cycle
    if cycle_id != status["last_cycle"]:
        msg = f"🚀 Début du transfert détecté pour le cycle **{current_cycle}z**."
        send_discord_alert(msg)
        log_activity(f"ALERTE: Nouveau cycle détecté ({current_cycle}z)")
        status = {"last_cycle": cycle_id, "is_completed": False}

    # CAS B : Vérification de la complétion
    elif not status["is_completed"]:
        file_check = f"gfs.{today}/{current_cycle}/atmos/gfs.t{current_cycle}z.pgrb2.0p25.f384.idx"
        check_res = requests.head(f"{BASE_URL}{file_check}")
        
        if check_res.status_code == 200:
            msg = f"✅ Cycle complet ! Le cycle **{current_cycle}z** est prêt."
            send_discord_alert(msg, is_success=True)
            log_activity(f"ALERTE: Cycle {current_cycle}z marqué comme COMPLET.")
            status["is_completed"] = True
        else:
            log_activity(f"CHECK: Cycle {current_cycle}z en cours (f384 non trouvé).")
    else:
        log_activity(f"CHECK: Cycle {current_cycle}z déjà terminé. En attente du prochain.")

    with open('status.json', 'w') as f:
        json.dump(status, f)

if __name__ == "__main__":
    check_noaa()
