import requests
import os
import json
from datetime import datetime

# --- CONFIGURATION ---
TOKEN = os.getenv('DISCORD_TOKEN')
CHANNEL_ID = os.getenv('CHANNEL_ID')
MENTION = "<@&873137469770592267>"
BASE_URL = "https://nomads.ncep.noaa.gov/pub/data/nccf/com/gfs/prod/"

# --- VOS MESSAGES PERSONNALISÉS ---
MESSAGES_DEBUT = {
    "00": "🌙 **GRIB 00Z en préparation** (Arrivée prévue au petit matin...🤤)",
    "06": "🌤 **GRIB 06Z en cours** (Il sera prêt pour la pause déjeuner !🚀)",
    "12": "🌆 **GRIB 12Z en route** (Le run du soir arrive...🌀)",
    "18": "🌑 **GRIB 18Z lancé** (Le chargement pour la nuit est en cours...🥱)"
}

MESSAGES_FIN = {
    "00": "☕ **GRIB 00Z DISPONIBLE !** Bonjour l'équipe, les données du réveil sont là.👋\n **Et Bonne Fête aux {saint} !** 🥳",
    "06": "🍴 **GRIB 06Z DISPONIBLE !** Juste à temps pour le point de la mi-journée. Bon app' les HPy !🍽️",
    "12": "🍹 **GRIB 12Z DISPONIBLE !** Les prévisions pour la soirée... A vos routeurs !🍹",
    "18": "💤 **GRIB 18Z DISPONIBLE !** Le grib des courageux noctambules... 🥱😴"
}

def get_saint_du_jour():
    """Récupère le prénom (premier mot) ou la fête complète depuis saints.json"""
    try:
        now = datetime.now()
        mois, jour = str(now.month), str(now.day)
        
        if os.path.exists('saints.json'):
            with open('saints.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                entree = data.get(mois, {}).get(jour)
                
                if entree and isinstance(entree, list):
                    nom_complet = entree[0].strip() #
                    genre = entree[1].strip() #
                    
                    # CAS 1 : Jour férié ou fête (on garde tout le nom de la fete)
                    if not genre:
                        return f"Aujourd'hui c'est {nom_complet} !" #
                    
                    # CAS 2 : Saint/Sainte (on ne prend que le premier mot en cas de prenoms allonges)
                    # exemple "Thomas d'Aquin" -> ["Thomas", "d'Aquin"] -> "Thomas"
                    prenom_seul = nom_complet.split(' ')[0] #
                    return f"Bonne Fête aux {prenom_seul} !" #
    except Exception as e:
        log_activity(f"ERREUR lecture saints.json: {e}")
    return None

def log_activity(message):
    """Journalisation de l'activité (limite à 3000 lignes)"""
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
    """Envoie l'alerte sur Discord avec intégration intelligente du Saint/Fête"""
    url = f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages"
    headers = {"Authorization": f"Bot {TOKEN}", "Content-Type": "application/json"}
    color = 0x00ff00 if is_success else 0xcc00cc
    
    if is_success:
        msg = MESSAGES_FIN.get(cycle_h, f"GRIB {cycle_h}Z terminé!")
        # Logique spécifique au run 00Z pour les Saints/Fêtes
        if cycle_h == "00" and "{saint}" in msg:
            phrase_fete = get_saint_du_jour()
            if phrase_fete:
                # Remplace toute la ligne personnalisée par la phrase complète générée
                msg = msg.replace("**Et Bonne Fête aux {saint} !** 🥳", f"**{phrase_fete}** 🥳") #
            else:
                msg = msg.replace("\n **Et Bonne Fête aux {saint} !** 🥳", "")
    else:
        msg = MESSAGES_DEBUT.get(cycle_h, f"Début de chargement du GRIB {cycle_h}Z.")

    payload = {
        "content": MENTION,
        "embeds": [{
            "title": f"🛰 **| RUN {cycle_h}Z |**",
            "description": msg,
            "color": color,
            "timestamp": datetime.utcnow().isoformat(),
            "footer": {"text": "NOAA Server Monitoring for HPy Team"}
        }]
    }
    
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=10)
        return r.status_code in [200, 204]
    except:
        return False

def check_noaa():
    """Vérifie la présence des fichiers sur les serveurs de la NOAA"""
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
        if send_discord_alert(is_success=False, cycle_h=current_cycle):
            log_activity(f"ALERTE: Nouveau cycle {current_cycle}z")
            status = {"last_cycle": cycle_id, "is_completed": False}
        else:
            log_activity(f"ERREUR: Échec Discord début {current_cycle}z")

    elif not status["is_completed"]:
        file_check = f"gfs.{today}/{current_cycle}/atmos/gfs.t{current_cycle}z.pgrb2.0p25.f384.idx"
        try:
            check_res = requests.head(f"{BASE_URL}{file_check}", timeout=10)
            if check_res.status_code == 200:
                if send_discord_alert(is_success=True, cycle_h=current_cycle):
                    log_activity(f"ALERTE: Cycle {current_cycle}z COMPLET.")
                    status["is_completed"] = True
                else:
                    log_activity(f"ERREUR: Échec Discord fin {current_cycle}z")
        except:
            return

    with open('status.json', 'w') as f:
        json.dump(status, f)

if __name__ == "__main__":
    check_noaa()
