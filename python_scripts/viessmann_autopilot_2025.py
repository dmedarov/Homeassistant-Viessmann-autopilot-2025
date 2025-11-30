# /config/python_scripts/viessmann_autopilot_2025.py
# VIESSMANN AUTOPILOT v8.0.9 — 2030 ETERNAL FINAL
# 30.11.2025 13:45 — последната версия завинаги

log = logger.info

# ───── 100% БЕЗОПАСНО ВРЕМЕ ЗА HA 2025.11+ (без import, без hass.data) ─────
dt_entity = hass.states.get('sensor.datetime')
if dt_entity and dt_entity.state not in ('unknown', 'unavailable'):
    dt_str = str(dt_entity.state)
else:
    dt_str = "2025-11-30 13:00:00"

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

    hour, minute = map(int, time_part.split(':')[:2])
    second = int(time_part.split(':')[2]) if len(time_part.split(':')) > 2 else 0
except:
    year, month, day, hour, minute, second = 2025, 11, 30, 13, 45, 0

# Ден от седмицата (0 = неделя, 1 = понеделник … 6 = събота)
weekday = (day + (13*(month-1))//5 + year%100 + (year%100)//4 + (year//100)//4 - year//100 + 5) % 7

# ───── ПОМОЩНИ ФУНКЦИИ ─────
def s(e):
    state = hass.states.get(e)
    return state.state if state and state.state not in ('unknown', 'unavailable', '') else None

def f(e, default=0.0, alt=None):
    for entity in [e] + (alt or []):
        val = s(entity)
        if val not in (None, '', 'unknown', 'unavailable'):
            try:
                return float(val)
            except:
                continue
    return default

# ───── PERSISTENT ДАННИ (КОРИГИРАН РЕД 55) ─────
persistent = hass.states.get('sensor.autopilot_persistent')
last_slope = float(persistent.attributes.get('last_slope', 999)) if persistent and 'last_slope' in persistent.attributes else 999
last_shift = float(persistent.attributes.get('last_shift', 999)) if persistent and 'last_shift' in persistent.attributes else 999

# ───── ДАННИ ─────
outdoor = f('sensor.outdoor_temperature', 5.0, ['sensor.cu401b_s_outside_temperature', 'sensor.netatmo_outdoor_temperature'])
indoor = f('sensor.indoor_temperature_avg', 21.0)
tmin_72h = f('sensor.forecast_min_72h', outdoor - 2)
tmin_96h = f('sensor.forecast_min_96h', tmin_72h)
base_slope = f('input_number.heating_base_slope', 0.80)
master_gain = f('input_number.autopilot_master_gain', 1.00)

home = s('device_tracker.damian_iphone_14') == 'Home-Osoica'
manual_force = s('input_boolean.heating_preheat_48h_force') == 'on'
auto_weekend = s('input_boolean.heating_weekend_mode_auto') == 'on'
is_holiday = s('calendar.blgarski_ofitsialni_praznitsi_2025_2030') == 'on'
night_tariff = hour >= 22 or hour < 8
supply_temp = f('sensor.cu401b_s_supply_temperature', 35.0)
compressor_on = s('binary_sensor.cu401b_s_compressor') == 'on'
comp_protect = s('sensor.compressor_runtime_protection') or 'off'
solar_score = f('sensor.solar_forecast_score_72h', 50)
rh = f('sensor.home_living_room_outdoor_humidity', 50)

# ───── GPS PREHEAT ─────
preheat = False
try:
    attrs = hass.states.get('device_tracker.damian_iphone_14').attributes or {}
    dist = float(attrs.get('distance', 999999))
    spd = float(attrs.get('speed', 0))
    if dist < 35000 and spd > 8:
        mins_to_home = int((dist / 1000) / max(spd, 20) * 60) + 22
        if 40 < mins_to_home < 190:
            preheat = True
except:
    pass

# ───── РЕЖИМИ ─────
is_weekend = weekday >= 5
long_preheat = manual_force or (auto_weekend and is_weekend and home) or (is_holiday and home)
is_comfort = home or long_preheat or preheat

# ───── ЗОНИ ─────
zones = {
    'living_room': {'sensor': 'sensor.home_living_room_temperature', 'target': 22.0, 'integral': 'sensor.pi_integral_living'},
    'downstairs': {'sensor': 'sensor.downstairs_temperature', 'target': 22.0, 'integral': 'sensor.pi_integral_downstairs'},
    'bedroom_damian': {'sensor': 'sensor.bedroom_damian_temperature', 'target': 21.5, 'integral': 'sensor.pi_integral_damian'},
    'bedroom_honey': {'sensor': 'sensor.bedroom_honey_temperature', 'target': 21.5, 'integral': 'sensor.pi_integral_honey'},
    'alex_room': {'sensor': 'sensor.alex_room_temperature', 'target': 22.0, 'integral': 'sensor.pi_integral_alex'},
}
room_weights = {'living_room': 1.7, 'downstairs': 1.5, 'bedroom_honey': 1.1, 'bedroom_damian': 1.0, 'alex_room': 0.7}

# ───── ЦЕЛЕВА ТЕМПЕРАТУРА ─────
comfort = f('input_number.comfort_target_temp', 22.2)
sleep = f('input_number.sleep_target_temp', 17.8)
cloudy_reduction = 0.0
if not is_comfort and solar_score < 35:
    cloudy_reduction = -0.8 - min(0.9, (35 - solar_score) / 10) - 0.004 * max(0, rh - 60)
target = comfort + 1.4 if preheat else comfort if is_comfort else max(comfort - 1.5 + cloudy_reduction, 18.0)

# ───── НОЩЕН / СУТРЕШЕН БОНУС ─────
morning_preheat_bonus = night_preheat_bonus = 0.0
if 23 <= hour or hour < 4:
    if not is_comfort:
        target = min(target, max(sleep, 17.5))
    else:
        target = max(target, sleep)
elif 4 <= hour < 8.5 and is_comfort and indoor < comfort - 0.3:
    morning_preheat_bonus = min(3.4, (comfort - max(indoor, sleep)) * 4.0)
    if hour < 5:
        morning_preheat_bonus *= 1.5

# ───── MULTI-ZONE PI ─────
zone_shift = 0.0
for name, z in zones.items():
    temp = f(z['sensor'], 21.0)
    t_zone = z['target'] + (0.6 if is_comfort else -1.0)
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

# ───── ГЛАВЕН PI ─────
error_main = target - indoor
integral_main = f('sensor.heating_pi_integral', 0.0) + error_main * 0.25
integral_main = max(min(integral_main, 9.0), -9.0)
pi_shift = round(8.5 * error_main + 0.10 * integral_main, 2)
hass.states.set('sensor.heating_pi_integral', round(integral_main, 3), {'unit_of_measurement': '°C·h'})

# ───── PV BOOST ─────
prev_pv_boost = f('sensor.pv_boost_smoothed', 0.0)
pv_now = f('sensor.power_production_now', 0.0)
pv_rem = f('sensor.energy_production_today_remaining', 0.0)
pv_forecast_today = pv_rem + pv_now / 12
raw_pv_boost = 0.0
if 7 <= hour <= 18 and outdoor > -10 and pv_now > 0.7:
    mult = 1.95 if night_tariff else 1.75
    extra = min(pv_rem * 0.45, 4.5) if hour < 14 and pv_rem > 5.0 and pv_now > 2.2 else 0.0
    raw_pv_boost = round(pv_now * mult + extra, 1)

max_allowed = 10.5
if pv_forecast_today < 10.0: max_allowed = 9.5
if pv_forecast_today < 7.0: max_allowed = 7.5
if pv_forecast_today < 5.5: max_allowed = 5.5
if pv_forecast_today < 4.0: max_allowed = 3.5
if pv_forecast_today < 3.0: max_allowed = 2.5
raw_pv_boost = min(raw_pv_boost, max_allowed)
smoothing = 0.35 if pv_forecast_today >= 5.0 else 0.25
pv_boost = round(prev_pv_boost + smoothing * (raw_pv_boost - prev_pv_boost), 1)
pv_boost = min(pv_boost, max_allowed)
hass.states.set('sensor.pv_boost_smoothed', pv_boost, {'friendly_name': 'PV Boost v8.0.9', 'icon': 'mdi:solar-power-variant'})

thermal_boost = 0.0
if is_comfort and 7 <= hour <= 16 and pv_boost > 7.0 and indoor < target + 0.8 and outdoor > -12:
    thermal_boost = min(2.8, (pv_boost - 6.5) * 0.9)
    if indoor > target + 0.2:
        thermal_boost *= 0.4

# ───── ЗАЩИТИ ─────
overshoot_brake = -min(4.2, (indoor - target - 0.6) * 6.5) if indoor > target + 0.75 else 0.0
final_shift = overshoot_brake + thermal_boost

if comp_protect in ['very_long', 'long', 'medium']:
    final_shift -= {'very_long': 5.0, 'long': 3.2, 'medium': 1.5}.get(comp_protect, 0)

if compressor_on:
    if supply_temp >= 60.0:
        final_shift = max(final_shift - 10.0, -8.0)
    elif supply_temp >= 58.5:
        final_shift = max(final_shift - min((supply_temp - 57.5) * 3.2, 7.0), -6.0)

if night_tariff and is_comfort and indoor < target + 0.8 and outdoor < 10:
    night_preheat_bonus = min(3.8, (target + 0.8 - indoor) * 4.2)
    if supply_temp < 52:
        night_preheat_bonus *= 1.4

# ───── SLOPE + ДЪЛБОК СТУД + ДЪЛЪГ КОМФОРТ ─────
raw_slope = base_slope + 0.032 * max(0, 10 - outdoor) + 0.045 * max(0, -tmin_72h - outdoor)
slope = round(max(min(raw_slope, 1.45), 0.56), 2)

forecast_shift_bonus = 0.0
if tmin_96h <= -20: forecast_shift_bonus = 9.5
elif tmin_96h <= -18: forecast_shift_bonus = 6.5
elif tmin_72h <= -15: forecast_shift_bonus = 4.8
elif tmin_72h <= -12: forecast_shift_bonus = 4.0
elif tmin_72h <= -8: forecast_shift_bonus = 3.2
elif tmin_72h <= -5: forecast_shift_bonus = 2.4
elif tmin_72h <= -2: forecast_shift_bonus = 1.4

if rh > 85: slope += 0.10; forecast_shift_bonus += 1.0
elif rh > 75: slope += 0.06; forecast_shift_bonus += 0.6
if long_preheat and hour < 14: slope += 0.10; forecast_shift_bonus += 1.2

long_comfort_h = f('sensor.long_comfort_counter', 0.0)
if is_comfort:
    long_comfort_h += 0.25
else:
    long_comfort_h = max(0, long_comfort_h - 1.0)
hass.states.set('sensor.long_comfort_counter', round(long_comfort_h, 2))

if long_comfort_h > 48: slope = min(slope, 0.92)
if not is_comfort and slope > 1.00: slope = 1.00

# ───── MIN_SHIFT ─────
min_shift = -8.0 if outdoor >= 20 else -6.5 if outdoor >= 18 else -5.0 if outdoor >= 15 else -3.5

# ───── КРАЙНО ИЗЧИСЛЯВАНЕ ─────
final_shift_raw = (
    0.55 * pi_shift +
    0.25 * zone_shift +
    0.12 * pv_boost +
    0.08 * forecast_shift_bonus +
    night_preheat_bonus +
    morning_preheat_bonus +
    final_shift
)
final_shift = round(final_shift_raw * master_gain, 1)

max_shift = 11.5 if tmin_72h <= -15 else 11.0 if tmin_72h <= -10 else 10.5 if tmin_72h <= -5 else 10.0
final_shift = max(min(final_shift, max_shift), min_shift)

# ───── ЗАПИС В VIESSMANN ─────
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
        'friendly_name': 'Autopilot persistent v8.0.9'
    })

# ───── АЛЕРТ ─────
if supply_temp >= 59.5 or comp_protect == 'very_long':
    hass.services.call('notify', 'mobile_app_damian_iphone_14', {
        'title': 'Viessmann Alert',
        'message': f"Топла вода {supply_temp:.1f}°C | Компресор {comp_protect.upper()}"
    })

# ───── ПЕРФЕКТЕН ЛОГ ─────
mode = "HOME" if home else "PREHEAT" if preheat else "WEEKEND/HOLIDAY" if long_preheat else "AWAY"
log_line = (
    f"{day:02d}.{month:02d} {hour:02d}:{minute:02d} │ "
    f"{indoor:5.1f}→{target:4.1f}°C │ "
    f"shift {final_shift:+5.1f} │ slope {slope:4.2f} │ "
    f"PV {pv_now:5.1f}→{pv_boost:+4.1f} │ {mode} │ {comp_protect.upper()}"
)

hass.states.set('sensor.autopilot_log_last_line', log_line)
logger.info(log_line)
