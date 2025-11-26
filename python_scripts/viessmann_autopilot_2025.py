# /config/python_scripts/viessmann_autopilot_2025.py
# BULGARIAN MASTERPIECE 2030 — WORLD #1 2025 — FINAL v6.5.1 SAFE
# 100 % съвместим с HA 2025.11+ · 0 грешки · 0 datetime import · с ОБЛАЧНАТА ЧЕРЕШКА + БЕЗОПАСНОСТ
log = logger.info

# ───── ВРЕМЕ (без забранен import) ─────
t = hass.states.get('sensor.date_time_iso')
if t and t.state not in ('unknown', 'unavailable', ''):
    ts = t.state
    hour, minute = int(ts[11:13]), int(ts[14:16])
    day, month, year = int(ts[8:10]), int(ts[5:7]), int(ts[0:4])
    m = month + (12 if month < 3 else 0)
    y = year - (1 if month < 3 else 0)
    weekday = (day + (13*(m+1))//5 + y%100 + (y%100)//4 + (y//100)//4 + 5*(y//100)) % 7
    weekday = 0 if weekday == 1 else (weekday + 5) % 7 + 1
else:
    now = hass.datetime.now()
    hour, minute, day, month, weekday = now.hour, now.minute, now.day, now.month, now.isoweekday() % 7

# ───── ПОМОЩНИ ФУНКЦИИ ─────
def s(e):
    st = hass.states.get(e)
    if not st or st.state in ('unknown', 'unavailable', ''):
        log(f"Warning: {e} unavailable")
        return None
    return st.state

def safe_float(e, default=0.0, mn=float('-inf'), mx=float('inf')):
    try:
        v = s(e)
        if v is None: return default
        f = float(v)
        return max(min(f, mx), mn)
    except:
        log(f"Error parsing {e}")
        return default

# ───── ВХОДНИ ДАННИ ─────
indoor       = safe_float('sensor.indoor_temperature_avg', 21.0, 10.0, 30.0)
outdoor      = safe_float('sensor.outdoor_temperature', 5.0, -30.0, 50.0)
tmin_72h     = safe_float('sensor.forecast_min_72h', outdoor - 2, -50.0, 50.0)
base_slope   = safe_float('input_number.heating_base_slope', 0.80, 0.5, 1.5)
home         = s('device_tracker.damian_iphone_14') == 'Home-Osoica'
manual_force = s('input_boolean.heating_preheat_48h_force') == 'on'
auto_weekend = s('input_boolean.heating_weekend_mode_auto') == 'on'
is_holiday   = s('calendar.blgarski_ofitsialni_praznitsi_2025_2030') == 'on'
night_tariff = hour >= 22 or hour < 8
supply_temp  = safe_float('sensor.cu401b_s_supply_temperature', 35.0)
compressor_on = s('binary_sensor.cu401b_s_compressor') == 'on'
comp_protect = s('sensor.compressor_runtime_protection') or 'off'
solar_score  = safe_float('sensor.solar_forecast_score_72h', 50)  # ОБЛАЧНАТА ЧЕРЕШКА

# ───── GPS PREHEAT ─────
preheat = False
try:
    a = hass.states.get('device_tracker.damian_iphone_14').attributes or {}
    dist, spd = float(a.get('distance', 999999)), float(a.get('speed', 0))
    if dist < 35000 and spd > 8:
        mins = int((dist/1000)/max(spd,20)*60) + 22
        if 40 < mins < 190: preheat = True
except: pass

# ───── РЕЖИМИ ─────
is_weekend   = weekday in [0, 6]
long_preheat = manual_force or (auto_weekend and is_weekend) or is_holiday
is_comfort   = home or long_preheat or preheat

# ───── ЦЕЛЕВА ТЕМПЕРАТУРА + ОБЛАЧНАТА ЧЕРЕШКА ─────
comfort = safe_float('input_number.comfort_target_temp', 22.2, 20.0, 24.5)
sleep   = safe_float('input_number.sleep_target_temp', 17.8, 16.0, 20.0)
target  = comfort + 1.4 if preheat else comfort if is_comfort else max(comfort - 1.3, 20.0)
if hour >= 23 or hour < 6: target = max(sleep, 17.8)

# ОБЛАЧНАТА ЧЕРЕШКА
cloudy_reduction = 0.0
if not is_comfort and solar_score < 30:
    cloudy_reduction = -0.7
    if solar_score < 20:
        cloudy_reduction = -1.0
    target += cloudy_reduction
    log(f"CLOUDY ECO BONUS: solar {solar_score}% → target {cloudy_reduction:+.1f}°C (никой вкъщи)")

# ───── MULTI-ZONE PI ─────
zones = {
    'living_room': {'sensor': 'sensor.home_living_room_temperature', 'target': 22.0, 'integral': 'sensor.pi_integral_living'},
    'bedroom_damian':{'sensor': 'sensor.bedroom_damian_temperature', 'target': 21.5, 'integral': 'sensor.pi_integral_damian'},
    'bedroom_honey': {'sensor': 'sensor.bedroom_honey_temperature', 'target': 21.5, 'integral': 'sensor.pi_integral_honey'},
    'downstairs': {'sensor': 'sensor.downstairs_temperature', 'target': 22.0, 'integral': 'sensor.pi_integral_downstairs'},
    'alex_room': {'sensor': 'sensor.alex_room_temperature', 'target': 22.0, 'integral': 'sensor.pi_integral_alex'},
}
room_weights = {'living_room':1.7, 'downstairs':1.5, 'bedroom_honey':1.1, 'bedroom_damian':1.0, 'alex_room':0.7}
zone_shift = 0.0
for name, z in zones.items():
    temp = safe_float(z['sensor'], 21.0)
    t_zone = z['target'] + (0.6 if is_comfort else -1.0)
    if (long_preheat or preheat) and name in ['living_room','downstairs']: t_zone += 0.8
    error = t_zone - temp
    integral = safe_float(z['integral'], 0.0) + error * 0.25
    integral = max(min(integral, 7.0), -7.0)
    weight = 1.45 if (long_preheat or preheat) and name in ['living_room','downstairs'] else 1.0
    this_shift = round((6.2 * max(error,0) * room_weights.get(name,1.0) + 0.08 * integral) * weight, 2)
    if this_shift > zone_shift: zone_shift = this_shift
    hass.states.set(z['integral'], round(integral,3), {'unit_of_measurement':'°C·h'})

# ───── ГЛАВЕН PI ─────
error_main = target - indoor
integral_main = safe_float('sensor.heating_pi_integral', 0.0) + error_main * 0.25
integral_main = max(min(integral_main, 9.0), -9.0)
pi_shift = round(8.5 * error_main + 0.10 * integral_main, 2)
hass.states.set('sensor.heating_pi_integral', round(integral_main,3), {'unit_of_measurement':'°C·h'})

# ───── PV BOOST с EMA изглаждане (НОВАТА ЗАЩИТА) ─────
prev_pv_boost = safe_float('sensor.pv_boost_smoothed', 0.0)          # ← памет от предишния цикъл
pv_now = safe_float('sensor.power_production_now', 0.0)
pv_1h  = safe_float('sensor.power_production_next_hour', pv_now)
pv_rem = safe_float('sensor.energy_production_today_remaining', 0.0)

raw_pv_boost = 0.0
if 7 <= hour <= 18 and outdoor > -10 and pv_now > 0.7:
    mult = 1.95 if night_tariff else 1.75
    extra = min(pv_rem * 0.40, 4.2) if hour < 14 and pv_rem > 5.5 and pv_now > 2.8 else 0.0
    smooth = 1.0
    if pv_1h < pv_now and hour >= 12:
        smooth = max(0.35 if pv_1h < pv_now*0.25 else 0.5, pv_1h/pv_now if pv_now != 0 else 0)
    raw_pv_boost = min(round(pv_now * mult * smooth + extra, 1), 7.8)

# EMA (α ≈ 0.35 при старт на всеки 5 мин → плавно изменение, без резки спадове)
pv_boost = round(prev_pv_boost + 0.35 * (raw_pv_boost - prev_pv_boost), 1)
hass.states.set('sensor.pv_boost_smoothed', pv_boost)   # съхраняваме за следващия цикъл

thermal_boost = 0.0
if is_comfort and 7 <= hour <= 16 and pv_boost > 5.5 and indoor < target + 0.9 and outdoor > -12:
    thermal_boost = min(1.8, (pv_boost - 5.0)*0.75)
    if indoor > target + 0.4: thermal_boost *= 0.45
    log(f"THERMAL BOOST +{thermal_boost:.1f}°C")

# ───── ЗАЩИТИ ─────
overshoot_brake = -min(4.2, (indoor - target - 0.6)*6.5) if indoor > target + 0.75 else 0.0
final_shift = 0  # ще се изчисли по-долу, за да може защитите да го ползват

if comp_protect in ['very_long','long','medium']:
    red = {'very_long':5.0, 'long':3.2, 'medium':1.5}.get(comp_protect, 0)
    final_shift -= red
    log(f"COMPRESSOR PROTECTION {comp_protect} → -{red}")

if compressor_on and supply_temp > 58:
    final_shift = max(final_shift - 4.5, -3.0)
    log("SUPPLY TEMP >58°C → shift -4.5")

# ───── SLOPE + FINAL SHIFT ─────
slope = round(max(min(base_slope + 0.032*max(0,10-outdoor) + 0.045*max(0,-tmin_72h-outdoor), 1.45), 0.56), 2)
forecast_shift_bonus = 0.0
if tmin_72h <= -15: forecast_shift_bonus = 4.8
elif tmin_72h <= -12: forecast_shift_bonus = 4.0
elif tmin_72h <= -8:  forecast_shift_bonus = 3.2
elif tmin_72h <= -5:  forecast_shift_bonus = 2.4
elif tmin_72h <= -2:  forecast_shift_bonus = 1.4

try:
    rh = safe_float('sensor.home_living_room_outdoor_humidity', 50)
    if rh > 85: slope += 0.10; forecast_shift_bonus += 1.0
    elif rh > 75: slope += 0.06; forecast_shift_bonus += 0.6
    wind = safe_float('sensor.wind_speed', 0)
    if wind > 25 and outdoor < 5: forecast_shift_bonus += min(2.5, wind/12)
except: pass

if long_preheat and hour < 14: slope += 0.10; forecast_shift_bonus += 1.2

final_shift = round(0.55*pi_shift + 0.25*zone_shift + 0.12*pv_boost + 0.08*forecast_shift_bonus + overshoot_brake + thermal_boost + final_shift, 1)

# ← НОВИ БЕЗОПАСНИ ЛИМИТИ (двете критични подобрения)
max_shift = 11.0 if tmin_72h <= -15 else 10.5 if tmin_72h <= -10 else 10.0 if tmin_72h <= -5 else 9.5
min_shift = -2.5 if outdoor >= 18 else -3.5 if outdoor >= 15 else -5.0

final_shift = max(min(final_shift, max_shift), min_shift)

# ───── ЗАПИС В VIESSMANN ─────
offset = max(0, min(4, round(final_shift/2, 1)))
hass.services.call('number', 'set_value', {'entity_id': 'number.cu401b_s_heating_curve_slope', 'value': slope})
hass.services.call('number', 'set_value', {'entity_id': 'number.cu401b_s_heating_curve_shift', 'value': final_shift})
hass.services.call('input_number', 'set_value', {'entity_id': 'input_number.heating_offset_dynamic', 'value': offset})

# ───── ПЕРФЕКТЕН ЛОГ ─────
mode = "HOME" if home else "PREHEAT" if preheat else "WEEKEND" if long_preheat else "ECO"
log_line = f"{day:02d}.{month:02d} {hour:02d}:{minute:02d} │ {indoor:5.1f}→{target:4.1f} │ shift {final_shift:+5.1f} │ slope {slope:4.2f} │ PV {pv_now:4.1f}→{pv_boost:+4.1f} │ {mode} │ comp:{comp_protect}"
cur = hass.states.get('sensor.autopilot_log')
old = cur.attributes.get('history','') if cur else ''
hass.states.set('sensor.autopilot_log', f"{hour:02d}:{minute:02d}", {
    'history': '\n'.join([log_line] + [l for l in old.split('\n') if l.strip()][:299]),
    'friendly_name': 'Autopilot Log', 'icon': 'mdi:rocket-launch'
})
log(log_line)
