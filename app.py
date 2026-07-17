from flask import Flask
import requests
import datetime

app = Flask(__name__)

# ==========================================
# 1. TUS CREDENCIALES DE TELEGRAM
# ==========================================
TELEGRAM_TOKEN = "8707084467:AAEaROMxqU3B4muGQ9tGi0G86Ez2Ja0JRqs"
TELEGRAM_CHAT_ID = "7486357581"

# ==========================================
# 2. CONFIGURACIÓN Y FACTORES DE LA MLB
# ==========================================
ERA_PROMEDIO_LIGA = 4.20
OPS_PROMEDIO_LIGA = 0.720

PARK_FACTORS = {
    'ARI': 101, 'ATL': 99,  'BAL': 98,  'BOS': 108, 'CHC': 102,
    'CWS': 99,  'CIN': 111, 'CLE': 96,  'COL': 112, 'DET': 96,
    'HOU': 98,  'KC':  100, 'LAA': 101, 'LAD': 98,  'MIA': 94,
    'MIL': 101, 'MIN': 98,  'NYM': 95,  'NYY': 100, 'OAK': 93,
    'PHI': 104, 'PIT': 97,  'SD':  95,  'SF':  92,  'SEA': 92,
    'STL': 96,  'TB':  94,  'TEX': 102, 'TOR': 101, 'WSH': 101
}

MLB_MAP = {
    'Arizona Diamondbacks': 'ARI', 'Atlanta Braves': 'ATL', 'Baltimore Orioles': 'BAL',
    'Boston Red Sox': 'BOS', 'Chicago Cubs': 'CHC', 'Chicago White Sox': 'CWS',
    'Cincinnati Reds': 'CIN', 'Cleveland Guardians': 'CLE', 'Colorado Rockies': 'COL',
    'Detroit Tigers': 'DET', 'Houston Astros': 'HOU', 'Kansas City Royals': 'KC',
    'Los Angeles Angels': 'LAA', 'Los Angeles Dodgers': 'LAD', 'Miami Marlins': 'MIA',
    'Milwaukee Brewers': 'MIL', 'Minnesota Twins': 'MIN', 'New York Mets': 'NYM',
    'New York Yankees': 'NYY', 'Oakland Athletics': 'OAK', 'Philadelphia Phillies': 'PHI',
    'Pittsburgh Pirates': 'PIT', 'San Diego Padres': 'SD', 'San Francisco Giants': 'SF',
    'Seattle Mariners': 'SEA', 'St. Louis Cardinals': 'STL', 'Tampa Bay Rays': 'TB',
    'Texas Rangers': 'TEX', 'Toronto Blue Jays': 'TOR', 'Washington Nationals': 'WSH'
}

def obtener_era_pitcher(pitcher_id):
    if not pitcher_id: return ERA_PROMEDIO_LIGA
    url = f"https://statsapi.mlb.com/api/v1/people/{pitcher_id}/stats?stats=statsSingleSeason&group=pitching"
    try:
        data = requests.get(url).json()
        return float(data['stats'][0]['splits'][0]['stat']['era'])
    except: return ERA_PROMEDIO_LIGA

def obtener_ops_equipo(team_id):
    if not team_id: return OPS_PROMEDIO_LIGA
    url = f"https://statsapi.mlb.com/api/v1/teams/{team_id}/stats?stats=statsSingleSeason&group=hitting"
    try:
        data = requests.get(url).json()
        return float(data['stats'][0]['splits'][0]['stat']['ops'])
    except: return OPS_PROMEDIO_LIGA

def enviar_alerta_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mensaje, "parse_mode": "HTML"}
    try: requests.post(url, json=payload)
    except Exception as e: print(f"Error Telegram: {e}")

def procesar_juego_mlb(juego):
    era_visita = obtener_era_pitcher(juego['pitcher_vis_id'])
    era_local = obtener_era_pitcher(juego['pitcher_loc_id'])
    ops_visita = obtener_ops_equipo(juego['team_vis_id'])
    ops_local = obtener_ops_equipo(juego['team_loc_id'])
    pf_estadio = PARK_FACTORS.get(juego['local_abbr'], 100)

    carreras_visita = 4.5 * (ops_visita / OPS_PROMEDIO_LIGA) * (era_local / ERA_PROMEDIO_LIGA) * (pf_estadio / 100)
    carreras_local = 4.5 * (ops_local / OPS_PROMEDIO_LIGA) * (era_visita / ERA_PROMEDIO_LIGA) * (pf_estadio / 100)

    f5_visita = carreras_visita * (5 / 9)
    f5_local = carreras_local * (5 / 9)
    total_carreras_f5 = f5_visita + f5_local

    denominador = (f5_visita ** 1.83) + (f5_local ** 1.83)
    prob_visita_limpio = (f5_visita ** 1.83) / denominador
    prob_local_limpio = (f5_local ** 1.83) / denominador

    prob_empate = max(0.15, min(0.35, 0.26 - (0.012 * (total_carreras_f5 - 4.5))))

    prob_visita_directo = prob_visita_limpio * (1 - prob_empate)
    prob_local_directo = prob_local_limpio * (1 - prob_empate)
    prob_visita_hnd = prob_visita_directo + prob_empate
    prob_local_hnd = prob_local_directo + prob_empate

    opciones_picks = []
    opciones_picks.append({'tipo': 'HANDICAP', 'equipo': juego['visita_abbr'], 'detalle': f"{juego['visita_abbr']} (+0.5 F5)", 'prob': prob_visita_hnd, 'mercado': 'Innings 1 a 5 - Hándicap'})
    opciones_picks.append({'tipo': 'HANDICAP', 'equipo': juego['local_abbr'], 'detalle': f"{juego['local_abbr']} (+0.5 F5)", 'prob': prob_local_hnd, 'mercado': 'Innings 1 a 5 - Hándicap'})
    opciones_picks.append({'tipo': 'DIRECTO', 'equipo': juego['visita_abbr'], 'detalle': f"{juego['visita_abbr']} Ganador Directo (F5)", 'prob': prob_visita_directo, 'mercado': 'Innings 1 a 5 - Ganador'})
    opciones_picks.append({'tipo': 'DIRECTO', 'equipo': juego['local_abbr'], 'detalle': f"{juego['local_abbr']} Ganador Directo (F5)", 'prob': prob_local_directo, 'mercado': 'Innings 1 a 5 - Ganador'})

    prob_under = 0.65 if total_carreras_f5 < 4.2 else (0.35 if total_carreras_f5 > 4.8 else 0.50)
    prob_over = 1 - prob_under
    opciones_picks.append({'tipo': 'TOTALES', 'equipo': 'Bajas', 'detalle': 'Menos de 4.5 Carreras (F5)', 'prob': prob_under, 'mercado': 'Innings 1 a 5 - Totales'})
    opciones_picks.append({'tipo': 'TOTALES', 'equipo': 'Altas', 'detalle': 'Más de 4.5 Carreras (F5)', 'prob': prob_over, 'mercado': 'Innings 1 a 5 - Totales'})

    opciones_picks.sort(key=lambda x: x['prob'], reverse=True)
    mejor_pick = opciones_picks[0]

    if mejor_pick['prob'] >= 0.72:
        confianza_label = "🟢 ALTA"
        stake_sugerido = "Stake 2 ($20 MXN)"
        emoji_conf = "🔥🔥"
    elif mejor_pick['prob'] >= 0.55:
        confianza_label = "🟡 MEDIA"
        stake_sugerido = "Stake 1 ($10 MXN)"
        emoji_conf = "⭐"
    else:
        return

    cuota_minima = 1 / mejor_pick['prob']

    mensaje = (
        f"🎯 <b>PICK ÚNICO DEL PARTIDO</b> 🎯\n"
        f"───────────────────\n"
        f"⚾ <b>Juego:</b> {juego['visita_abbr']} vs {juego['local_abbr']}\n"
        f"📋 <b>Apuesta:</b> <u>{mejor_pick['detalle']}</u>\n"
        f"🗂️ <b>Mercado en Playdoit/Caliente:</b>\n"
        f"👉 <i>'{mejor_pick['mercado']}'</i>\n"
        f"───────────────────\n"
        f"📊 <b>Confianza del Bot:</b> <b>{confianza_label} ({mejor_pick['prob']:.1%})</b> {emoji_conf}\n"
        f"💰 <b>Cuota Mínima exigida:</b> <b>{cuota_minima:.2f}</b>\n"
        f"🛡️ <b>Gestión de Banco:</b> Meter <b>{stake_sugerido}</b>\n"
        f"───────────────────\n"
        f"💡 <i>¡Recuerda! Si el casino te paga MENOS de {cuota_minima:.2f}, no metas la apuesta.</i>"
    )
    enviar_alerta_telegram(mensaje)

def ejecutar_bot():
    hoy = datetime.date.today().strftime('%Y-%m-%d')
    url_schedule = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={hoy}&hydrate=probablePitcher,team"
    try:
        response = requests.get(url_schedule).json()
        dates = response.get('dates', [])
        if not dates: return "No hay juegos hoy"
        juegos = dates[0].get('games', [])
        for g in juegos:
            visita_name = g['teams']['away']['team']['name']
            local_name = g['teams']['home']['team']['name']
            vis_abbr = MLB_MAP.get(visita_name)
            loc_abbr = MLB_MAP.get(local_name)
            if not vis_abbr or not loc_abbr: continue
            juego_dict = {
                'visita_abbr': vis_abbr, 'local_abbr': loc_abbr,
                'team_vis_id': g['teams']['away']['team'].get('id'),
                'team_loc_id': g['teams']['home']['team'].get('id'),
                'pitcher_vis_id': g['teams']['away'].get('probablePitcher', {}).get('id'),
                'pitcher_loc_id': g['teams']['home'].get('probablePitcher', {}).get('id')
            }
            procesar_juego_mlb(juego_dict)
        return "OK"
    except Exception as e:
        return f"Error: {e}"

# ==========================================
# RUTAS DE LA PÁGINA WEB SECRETA
# ==========================================
@app.route('/')
def home():
    return "Servidor del bot activo y seguro."

@app.route('/disparar-bot-mlb-777')
def trigger():
    resultado = ejecutar_bot()
    return f"Proceso ejecutado. Estado: {resultado}"
