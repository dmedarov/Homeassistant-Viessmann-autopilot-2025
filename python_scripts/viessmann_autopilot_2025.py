# /config/python_scripts/viessmann_autopilot_2025.py
# VIESSMANN AUTOPILOT v2030.12 — ETERNAL FINAL — 100% съвместим с HA 2025.11+
# Копирайте точно този код и всичко ще работи завинаги

logger.info("Viessmann Autopilot 2030.12 ETERNAL FINAL стартира")
log = logger.info

# ───── БЕЗОПАСНО ВРЕМЕ ─────
dt_entity = hass.states.get('sensor.datetime')
dt_str = "2025-11-30 13:00:00"
if dt_entity and dt_entity.state not in ('unknown', 'unavailable', None, ''):
    dt_str = str(dt_entity.state)

try:
    if ' ' in dt_str:
        date_part, time_part = dt_str.split(' ', 1)
    else:
        date_part, time_part = dt_str, "00:00:00"

    if '-' in date_part:
        year, month, day = map(int, date_part.split('-')[:3])
    elif '.' in date_part:
        day, month, year = map(int, date_part.split('.')[:3])
    else:
        year, month, day = 2025, 11, 30

    hour, minute, _ = map(int, (time_part + ":00").split(':')[:3])
except Exception:
    year, month, day, hour, minute = 2025, 11, 30, 13, 45

# ───── ПОМОЩНИ ФУНКЦИИ ─────
def s(entity_id):
    state = hass.states.get(entity_id)
    if state is None or state.state in ('unknown', 'unavailable', '', None):
        return None
    return state.state

def f(entity_id, default=0.0, alternatives=None):
    entities = [entity_id] + (alternatives or [])
    for e in entities:
        val = s(e)
        if val not in (None, '', 'unknown', 'unavailable'):
            try:
                return float(val)
            except (ValueError, TypeError):
                continue
    return default

# ───── PERSISTENT ДАННИ ─────
persistent = hass.states.get('sensor.autopilot_persistent')
last_slope = float(persistent.attributes.get('last_slope', 999)) if persistent else 999
last_shift = float(persistent.attributes.get('last_shift', 999)) if persistent else 999

# ───── ОСНОВНИ СЕНЗОРИ ─────
outdoor = f('sensor.outdoor_temperature', 5.0, ['sensor.cu401b_s_outside_temperature'])
indoor = f('sensor.indoor_temperature_avg', 21.0)
tmin_72h = f('sensor.forecast_min_72h', outdoor - 2)
tmin_96h = f('sensor.forecast_min_96h', tmin_72h)
base_slope = f('number.cu401b_s_heating_curve_slope', 0.96)
master_gain = f('input_number.autopilot_master_gain', 0.92)
home = s('binary_sensor.damian_really_home') == 'on'
manual_force = s('input_boolean.heating_preheat_48h_force') == 'on'
auto_weekend = s('input_boolean.heating_weekend_mode_auto') == 'on'
is_holiday = s('calendar.blgarski_ofitsialni_praznitsi_2025_2030') == 'on'
night_tariff = hour >= 22 or hour < 8
supply_temp = f('sensor.cu401b_s_secondary_circuit_supply_temperature', 35.0)
compressor_on = s('binary_sensor.cu401b_s_compressor') == 'on'
solar_score = f('sensor.solar_forecast_score_72h', 50)
rh = f('sensor.home_living_room_outdoor_humidity', 50)

# ───── КОМПРЕСОРНИ БРОЯЧИ ─────
today = f"{year}-{month:02d}-{day:02d}"
last_day = s('sensor.compressor_last_day') or '1970-01-01'

current_runtime = f('sensor.compressor_current_runtime', 0.0)
if compressor_on:
    current_runtime += 1
else:
    current_runtime = 0
hass.states.set('sensor.compressor_current_runtime', current_runtime,
                {'friendly_name': 'Компресор текущ цикъл', 'unit_of_measurement': 'min', 'icon': 'mdi:timer'})

daily_minutes = f('sensor.compressor_daily_minutes', 0.0)
season_minutes = f('sensor.compressor_season_minutes', 0.0)

if compressor_on:
    daily_minutes += 1
    season_minutes += 1

if last_day != today:
    daily_minutes = 1 if compressor_on else 0.0
    hass.states.set('sensor.compressor_last_day', today)

hass.states.set('sensor.compressor_daily_minutes', round(daily_minutes, 1),
                {'friendly_name': 'Компресор днес', 'unit_of_measurement': 'мин', 'icon': 'mdi:clock-outline'})
hass.states.set('sensor.compressor_season_minutes', round(season_minutes, 1),
                {'friendly_name': 'Компресор сезона 2025/26', 'unit_of_measurement': 'мин', 'icon': 'mdi:snowflake'})

if current_runtime > 45:
    comp_protect = 'very_long'
elif current_runtime > 35:
    comp_protect = 'long'
elif current_runtime > 25:
    comp_protect = 'medium'
else:
    comp_protect = 'normal' if compressor_on else 'off'

# ───── GPS PREHEAT ─────
preheat = False
mins_to_home = None
try:
    tr = hass.states.get('device_tracker.damian_iphone_14')
    if tr and tr.attributes:
        dist = float(tr.attributes.get('distance', 999999))
        spd = float(tr.attributes.get('speed') or 0)
        if dist < 35000 and spd > 8:
            mins_to_home = int((dist / 1000) / max(spd, 20) * 60) + 22
            if 40 < mins_to_home < 190:
                preheat = True
except Exception:
    pass

# ───── РЕЖИМИ ─────
is_weekend = (day + (13*(month-1))//5 + year%100 + (year%100)//4 + (year//100)//4 - year//100 + 5) % 7 >= 5
long_preheat = manual_force or (auto_weekend and is_weekend and home) or (is_holiday and home)
is_comfort = home or long_preheat or preheat

# ───── ЦЕЛЕВА ТЕМПЕРАТУРА ─────
comfort = f('input_number.comfort_target_temp', 22.2)
sleep = f('input_number.sleep_target_temp', 17.8)
cloudy_reduction = 0.0
if not is_comfort and solar_score < 35:
    cloudy_reduction = -0.8 - min(0.9, (35 - solar_score) / 10) - 0.004 * max(0, rh - 60)

target = comfort + 1.4 if preheat else comfort if is_comfort else max(comfort - 1.5 + cloudy_reduction, 18.0)

if 23 <= hour or hour < 6:
    night_target = max(sleep, 17.5)
    if night_target < target:
        log(f"NIGHT MODE: target ↓ {target:.1f} → {night_target:.1f}°C")
        target = night_target

# ───── ЗОНИ И PI КОНТРОЛ ─────
zones = {
    'living_room':    {'sensor': 'sensor.home_living_room_temperature',     'integral': 'sensor.pi_integral_living'},
    'downstairs':     {'sensor': 'sensor.downstairs_temperature',            'integral': 'sensor.pi_integral_downstairs'},
    'bedroom_damian': {'sensor': 'sensor.bedroom_damian_temperature',      'integral': 'sensor.pi_integral_damian'},
    'bedroom_honey':  {'sensor': 'sensor.bedroom_honey_temperature',       'integral': 'sensor.pi_integral_honey'},
    'alex_room':      {'sensor': 'sensor.alex_room_temperature',           'integral': 'sensor.pi_integral_alex'},
}

room_weights = {'living_room': 1.35, 'downstairs': 1.30, 'bedroom_honey': 1.1, 'bedroom_damian': 1.0, 'alex_room': 0.7}
zone_shift = 0.0

for name, z in zones.items():
    temp = f(z['sensor'], 21.0)
    t_zone = 21.0 + (0.6 if is_comfort else -1.0)
    if (long_preheat or preheat) and name in ['living_room', 'downstairs']:
        t_zone += 0.8
    error = t_zone - temp
    integral = f(z['integral'], 0.0) + error * 0.25
    integral = max(min(integral, 7.0), -7.0)
    weight = 1.45 if (long_preheat or preheat) and name in ['living_room', 'downstairs'] else 1.0
    this_shift = round((6.2 * max(error, 0) * room_weights.get(name, 1.0) + 0.08 * integral) * weight, 2)
    if this_shift > zone_shift:
        zone_shift = this_shift
    hass.states.set(z['integral'], round(integral, 3), {'unit_of_measurement': '°C·h'})

error_main = target - indoor
integral_main = f('sensor.heating_pi_integral', 0.0) + error_main * 0.25
integral_main = max(min(integral_main, 9.0), -9.0)
pi_shift = round(8.5 * error_main + 0.10 * integral_main, 2)
hass.states.set('sensor.heating_pi_integral', round(integral_main, 3), {'unit_of_measurement': '°C·h'})

# ───── PV BOOST ─────
prev_pv_boost = f('sensor.pv_boost_smoothed', 0.0)
pv_now_raw = f('sensor.power_production_now', 0.0)
pv_rem = f('sensor.energy_production_today_remaining', 0.0)
raw_pv_boost = 0.0

if 7 <= hour <= 18 and outdoor > -10 and pv_now_raw > 0.7:
    mult = 1.95 if night_tariff else 1.75
    extra = min(pv_rem * 0.45, 4.5) if hour < 14 and pv_rem > 5.0 and pv_now_raw > 2.2 else 0.0
    raw_pv_boost = round(pv_now_raw * mult + extra, 1)

max_allowed = min(10.5, [10.5, 9.0, 7.0, 5.0, 3.0][min(4, int((10 - (pv_rem + pv_now_raw / 12)) // 2))])
raw_pv_boost = min(raw_pv_boost, max_allowed)
smoothing = 0.35 if (pv_rem + pv_now_raw / 12) >= 5.0 else 0.22
pv_boost = round(prev_pv_boost + smoothing * (raw_pv_boost - prev_pv_boost), 1)
pv_boost = min(pv_boost, max_allowed, 13.0)
hass.states.set('sensor.pv_boost_smoothed', pv_boost, {'friendly_name': 'PV Boost 2030.12', 'icon': 'mdi:solar-power-variant'})

# ───── ТЕРМАЛНИ И ЗАЩИТНИ БОНУСИ ─────
thermal_boost = 0.0
if is_comfort and 7 <= hour <= 16 and pv_boost > 7.0 and indoor < target + 0.8 and outdoor > -12:
    thermal_boost = min(2.8, (pv_boost - 6.5) * 0.9)
    if indoor > target + 0.2:
        thermal_boost *= 0.4

overshoot_brake = -min(4.5, (indoor - target - 0.6) * 7.0) if indoor > target + 0.75 else 0.0
final_shift = overshoot_brake + thermal_boost

if comp_protect in ['very_long', 'long', 'medium']:
    final_shift -= {'very_long': 5.0, 'long': 3.2, 'medium': 1.5}.get(comp_protect, 0)

if compressor_on:
    if supply_temp >= 60.0:
        final_shift = max(final_shift - 10.0, -8.0)
    elif supply_temp >= 58.5:
        final_shift = max(final_shift - min((supply_temp - 57.5) * 3.5, 7.5), -6.5)

night_preheat_bonus = 0.0
if night_tariff and is_comfort and indoor < target + 0.8 and outdoor < 10:
    night_preheat_bonus = min(3.8, (target + 0.8 - indoor) * 4.2)
    if supply_temp < 48:
        night_preheat_bonus *= 1.6
    elif supply_temp < 52:
        night_preheat_bonus *= 1.35

# ───── SLOPE И ПРОГНОЗНИ КОРЕКЦИИ ─────
raw_slope = base_slope + 0.032 * max(0, 10 - outdoor) + 0.045 * max(0, -tmin_72h - outdoor)
slope = round(max(min(raw_slope, 1.50), 0.56), 2)
cold_slope = f('input_number.heating_cold_slope', 1.15)

if tmin_72h <= -12:
    slope = max(slope, cold_slope)
elif tmin_72h <= -8:
    slope = max(slope, cold_slope - 0.05)

forecast_shift_bonus = 0.0
if tmin_96h <= -25:    forecast_shift_bonus = 12.0
elif tmin_96h <= -20: forecast_shift_bonus = 9.5
elif tmin_96h <= -18: forecast_shift_bonus = 6.5
elif tmin_72h <= -15: forecast_shift_bonus = 4.8
elif tmin_72h <= -12: forecast_shift_bonus = 4.0
elif tmin_72h <= -8:  forecast_shift_bonus = 3.2
elif tmin_72h <= -5:  forecast_shift_bonus = 2.4
elif tmin_72h <= -2:  forecast_shift_bonus = 1.4

if rh > 85:
    slope += 0.10
    forecast_shift_bonus += 1.0
elif rh > 75:
    slope += 0.06
    forecast_shift_bonus += 0.6

if long_preheat and hour < 14:
    slope += 0.10
    forecast_shift_bonus += 1.2

# ───── ДЪЛГОСРОЧЕН КОМФОРТ ─────
long_comfort_h = f('sensor.long_comfort_counter', 0.0)
long_comfort_h += 0.25 if is_comfort else max(-1.0, -long_comfort_h/12)
hass.states.set('sensor.long_comfort_counter', round(long_comfort_h, 2))

if long_comfort_h > 48:
    reduction = min((long_comfort_h - 48) * 0.006, 0.22)
    slope = min(slope, 0.92 + reduction)

if not is_comfort and slope > 1.00:
    slope = 1.00

# ───── ФИНАЛНО ИЗЧИСЛЯВАНЕ ─────
final_shift_raw = (0.58 * pi_shift + 0.24 * zone_shift + 0.11 * pv_boost +
                   0.07 * forecast_shift_bonus + night_preheat_bonus + final_shift)
final_shift = round(final_shift_raw * master_gain, 1)

max_shift = 11.5 if tmin_72h <= -15 else 11.0 if tmin_72h <= -10 else 10.5 if tmin_72h <= -5 else 10.0
final_shift = max(min(final_shift, max_shift), -7.0)

# ───── ПРИЛАГАНЕ НА ПРОМЕНИ ─────
slope_changed = abs(slope - last_slope) > 0.02
shift_changed = abs(final_shift - last_shift) > 0.3

if slope_changed or shift_changed:
    if slope_changed:
        hass.services.call('number', 'set_value', {'entity_id': 'number.cu401b_s_heating_curve_slope', 'value': slope})
    if shift_changed:
        hass.services.call('number', 'set_value', {'entity_id': 'number.cu401b_s_heating_curve_shift', 'value': final_shift})

    offset = round(max(0, min(4, final_shift / 2)), 1)
    hass.services.call('input_number', 'set_value', {'entity_id': 'input_number.heating_offset_dynamic', 'value': offset})

    hass.states.set('sensor.autopilot_persistent', 0.0, {
        'last_slope': slope,
        'last_shift': final_shift,
        'last_run': f"{year}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}",
        'friendly_name': 'Autopilot persistent 2030.12'
    })

# ───── ЛОГ И КРАЙ ─────
mode_str = "HOME" if home else "AWAY"
if preheat and mins_to_home:
    mode_str += f"/PH{mins_to_home}m"
if long_preheat:
    mode_str += "/LONG"

comp_today = daily_minutes / 60
log_line = (f"{day:02d}.{month:02d} {comp_today:5.1f}h │ In {indoor:5.2f}→{target:5.2f} │ Out {outdoor:4.1f} │ "
            f"Sh {final_shift:+5.1f} │ Sl {slope:4.3f} │ PI{pi_shift:+4.1f}│Z{zone_shift:+4.1f}│PV{pv_boost:+4.1f}│"
            f"TB{thermal_boost:+3.1f} │ NB{night_preheat_bonus:+3.1f}│FB{forecast_shift_bonus:+3.1f} │ "
            f"{comp_protect.upper():>6}│S{supply_temp:3.0f}°│RH{rh:2.0f}%│{mode_str}")

hass.states.set('sensor.autopilot_log_last_line', log_line)
logger.info(log_line)
