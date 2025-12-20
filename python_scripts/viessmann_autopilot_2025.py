# /config/python_scripts/viessmann_autopilot.py
# VIESSMANN AUTOPILOT 2041.02 • RADIATOR 57.9°C RELIGION • CLOUD PERFECTION EDITION
# 140 m² • радиатори • никога над 57.9°C • перфектен лог завинаги • 96–98 % самоконсумация дори в облачно

logger.info("═" * 140)
logger.info("VIESSMANN AUTOPILOT 2041.02 • RADIATOR 57.9°C RELIGION • CLOUD PERFECTION • ЗАПУСНАТ")
logger.info("═" * 140)

FAIL_ENTITY = 'sensor.autopilot_consecutive_failures'
fail_count = 0
fail_state = hass.states.get(FAIL_ENTITY)
if fail_state and fail_state.state not in ('unknown', 'unavailable'):
    try: fail_count = int(float(fail_state.state))
    except: pass

try:
    # ──────────────────────────────────────── ПОМОЩНИ ФУНКЦИИ ────────────────────────────────────────
    def get_number(eid, default=0.0):
        st = hass.states.get(eid)
        if st and st.state not in ('unknown', 'unavailable', None, ''):
            try: return float(st.state)
            except: pass
        return float(default)

    def safe_temp(eid, default=5.0, alts=None):
        entities = [eid] + (alts or [])
        for ent in entities:
            st = hass.states.get(ent)
            if st and st.state not in ('unknown', 'unavailable', None, ''):
                try:
                    val = float(st.state)
                    if -40 <= val <= 80: return val
                except: pass
        return float(default)

    # ──────────────────────────────────────── ОСНОВНИ ДАННИ ────────────────────────────────────────
    hour        = int(get_number('sensor.current_hour', 13))
    minute      = int(get_number('sensor.current_minute', 0))
    day         = int(get_number('sensor.current_day', 5))
    month       = int(get_number('sensor.current_month', 12))
    weekday     = int(get_number('sensor.day_of_week', 0))

    outdoor     = safe_temp('sensor.outdoor_temperature', 3.0, ['sensor.cu401b_s_outside_temperature'])
    indoor      = safe_temp('sensor.indoor_temperature_avg', 21.0)
    supply_temp = safe_temp('sensor.cu401b_s_secondary_circuit_supply_temperature', 45.0)

    tmin_72h    = safe_temp('sensor.forecast_min_72h', outdoor - 3)
    tmin_96h    = safe_temp('sensor.forecast_min_96h', tmin_72h - 1)

    home        = (hass.states.get('binary_sensor.damian_really_home_fixed') == 'on' or
                   hass.states.get('device_tracker.damian_iphone_14') == 'home')

    manual_force = get_number('input_boolean.heating_preheat_48h_force', 0) > 0
    auto_weekend = get_number('input_boolean.heating_weekend_mode_auto', 0) > 0
    is_holiday  = get_number('calendar.blgarski_ofitsialni_praznitsi_2025_2030', 0) > 0

    night_tariff = hour >= 22 or hour < 8
    compressor_on = get_number('binary_sensor.cu401b_s_compressor', 0) > 0
    current_runtime = get_number('sensor.compressor_current_runtime', 0.0)

    # ──────────────────────────────────────── GPS PREHEAT ────────────────────────────────────────
    preheat = False
    mins_to_home = None
    tr = hass.states.get('device_tracker.damian_iphone_14')
    if tr and tr.attributes and tr.attributes.get('distance') is not None and tr.attributes.get('speed') is not None:
        try:
            dist_km = float(tr.attributes['distance']) / 1000
            speed = max(float(tr.attributes['speed']), 12)
            if dist_km < 42 and speed > 12:
                mins_to_home = int(dist_km / speed * 60) + 22
                if 30 <= mins_to_home <= 200: preheat = True
        except: pass

    long_preheat = manual_force or (auto_weekend and weekday >= 5 and home) or (is_holiday and home)
    is_comfort = home or long_preheat or preheat

    # ──────────────────────────────────────── ЦЕЛЕВА ТЕМПЕРАТУРА ────────────────────────────────────────
    comfort_temp = get_number('input_number.comfort_target_temp', 22.2)
    away_target = get_number('input_number.away_target_temp', 19.8)
    target = comfort_temp if is_comfort else away_target
    if preheat and mins_to_home: target += 1.1
    if 23 <= hour or hour < 6:
        sleep_temp = get_number('input_number.sleep_target_temp', 17.8)
        target = min(target, max(sleep_temp + 0.3, 17.8))

    # ──────────────────────────────────────── ПЕРСИСТЕНТНИ ДАННИ ────────────────────────────────────────
    persistent = hass.states.get('sensor.autopilot_persistent')
    last_slope = float(persistent.attributes.get('last_slope', 1.04)) if persistent else 1.04
    last_shift = float(persistent.attributes.get('last_shift', 0.0)) if persistent else 0.0

    # ──────────────────────────────────────── НУЛИРАНЕ НА ИНТЕГРАЛИ СЛЕД 3 ЧАСА ИЗКЛЮЧЕН КОМПРЕСОР ────────────────────────────────────────
    if get_number('sensor.compressor_off_time_minutes', 0) > 180:
        for e in ['sensor.heating_pi_integral','sensor.pi_integral_living','sensor.pi_integral_downstairs',
                  'sensor.pi_integral_damian','sensor.pi_integral_honey','sensor.pi_integral_alex']:
            hass.states.set(e, 0.0, {'unit_of_measurement': '°C·h'})

    # ──────────────────────────────────────── ЗОНИ И PI КОНТРОЛ ────────────────────────────────────────
    zones = {
        'living_room':   {'sensor': 'sensor.home_living_room_temperature',   'integral': 'sensor.pi_integral_living'},
        'downstairs':    {'sensor': 'sensor.downstairs_temperature',        'integral': 'sensor.pi_integral_downstairs'},
        'bedroom_damian':{'sensor': 'sensor.bedroom_damian_temperature',    'integral': 'sensor.pi_integral_damian'},
        'bedroom_honey': {'sensor': 'sensor.bedroom_honey_temperature',     'integral': 'sensor.pi_integral_honey'},
        'alex_room':     {'sensor': 'sensor.alex_room_temperature',         'integral': 'sensor.pi_integral_alex'},
    }
    room_weights = {'living_room': 1.35, 'downstairs': 1.30, 'bedroom_honey': 1.1, 'bedroom_damian': 1.0, 'alex_room': 0.7}
    zone_shift = 0.0
    INTERVAL_HOURS = 0.333

    for name, z in zones.items():
        temp = safe_temp(z['sensor'], 21.0)
        t_zone = 21.0 + (0.6 if is_comfort else -1.0)
        if (long_preheat or preheat) and name in ['living_room', 'downstairs']: t_zone += 0.6
        error = t_zone - temp
        integral = get_number(z['integral'], 0.0) + error * INTERVAL_HOURS
        integral = max(min(integral, 7.0), -7.0)
        weight = 1.35 if (long_preheat or preheat) and name in ['living_room', 'downstairs'] else 1.0
        this_shift = round((3.3 * max(error, 0) * room_weights.get(name, 1.0) + 0.022 * integral) * weight, 2)
        if this_shift > zone_shift: zone_shift = this_shift
        hass.states.set(z['integral'], round(integral, 3), {'unit_of_measurement': '°C·h'})

    error_main = target - indoor
    integral_main = get_number('sensor.heating_pi_integral', 0.0) + error_main * INTERVAL_HOURS
    integral_main = max(min(integral_main, 9.0), -9.0)
    pi_shift = round(4.1 * error_main + 0.028 * integral_main, 2)
    hass.states.set('sensor.heating_pi_integral', round(integral_main, 3), {'unit_of_measurement': '°C·h'})

    # ──────────────────────────────────────── PV BOOST 2041.02 CLOUD PERFECTION ────────────────────────────────────────
    prev_pv_boost = get_number('sensor.pv_boost_smoothed', 0.0)
    pv_now = get_number('sensor.power_production_now', 0.0)
    pv_rem = get_number('sensor.energy_production_today_remaining', 0.0)
    cloud_score = get_number('sensor.cloud_cover_score', 50)          # 0 = ясно, 100 = апокалипсис

    raw_pv_boost = 0.0

    if 7 <= hour <= 18 and outdoor > -10 and pv_now > 0.3:
        if cloud_score >= 65:                                      # CLOUD MODE
            mult = 2.15 if night_tariff else 2.05
            extra = min(pv_rem * 0.55, 5.2) if hour < 14 and pv_rem > 5.5 and pv_now > 2.5 else 0.0
            sunset_buffer = 0.0                                    # НЕ намаляваме преди залез
            smoothing = 0.42 if pv_rem > 3 else 0.28
        else:
            mult = 1.95 if night_tariff else 1.82
            extra = min(pv_rem * 0.44, 4.6) if hour < 14 and pv_rem > 5.5 and pv_now > 2.5 else 0.0
            sunset_buffer = -min(pv_now * 1.1, 3.8) if hour >= 14 and pv_rem < 4.2 else 0.0
            smoothing = 0.36 if (pv_rem + pv_now/12) >= 6 else 0.22

        raw_pv_boost = pv_now * mult + extra + sunset_buffer
        raw_pv_boost = max(0.0, min(raw_pv_boost, 11.8))

        pv_boost = prev_pv_boost + smoothing * (raw_pv_boost - prev_pv_boost)
        pv_boost = round(max(0.0, min(pv_boost, 11.8)), 1)
    else:
        pv_boost = 0.0

    # Свещеният твърд кап – 57.9 °C религията е над всичко
    headroom = max(0.0, 57.9 - supply_temp - 0.32)      # по-агресивен в облачно време
    pv_boost = min(pv_boost, headroom)

    hass.states.set('sensor.pv_boost_smoothed', pv_boost, {
        'icon': 'mdi:solar-power-variant',
        'friendly_name': 'PV Boost 2041.02 CLOUD PERFECTION'
    })

    # ──────────────────────────────────────── ФИНАЛЕН SHIFT И SLOPE ────────────────────────────────────────
    final_shift = pi_shift * 0.62 + zone_shift * 0.22 + pv_boost * 0.10

    # Защити и санкции
    if compressor_on and current_runtime > 35:
        if current_runtime > 65: final_shift -= 2.2
        elif current_runtime > 50: final_shift -= 1.4
        elif current_runtime > 40: final_shift -= 0.8
    if compressor_on:
        if supply_temp >= 54.0: final_shift -= min((supply_temp - 53.9)*0.9, 3.5)
        if supply_temp >= 56.5: final_shift -= (supply_temp - 56.4)*3.0
    if supply_temp >= 57.6: final_shift = min(final_shift, -9.0)
    if supply_temp >= 57.9:
        final_shift = -15.0
        hass.services.call('number', 'set_value', {'entity_id': 'number.cu401b_s_heating_curve_shift', 'value': -15.0})

    if tmin_96h <= -20: final_shift += 5.5
    elif tmin_72h <= -16: final_shift += 3.8
    elif tmin_72h <= -12: final_shift += 2.4

    master_gain = get_number('input_number.autopilot_master_gain', 0.96)
    final_shift = round(final_shift * master_gain, 1)
    final_shift = max(min(final_shift, 14.0), -7.0)

    base_slope = get_number('number.cu401b_s_heating_curve_slope', 1.04)
    slope = base_slope + max(0, (10 - outdoor))*0.018 + max(0, (-tmin_72h - outdoor))*0.026
    slope = round(max(min(slope, 1.30), 0.80), 3)

    if abs(slope - last_slope) > 0.012:
        hass.services.call('number', 'set_value', {'entity_id': 'number.cu401b_s_heating_curve_slope', 'value': slope})
    if abs(final_shift - last_shift) > 0.25:
        hass.services.call('number', 'set_value', {'entity_id': 'number.cu401b_s_heating_curve_shift', 'value': final_shift})

    hass.states.set('sensor.autopilot_persistent', 0.0, {
        'last_slope': slope,
        'last_shift': final_shift,
        'friendly_name': 'Autopilot 2041.02 CLOUD PERFECTION'
    })

    mode_str = "HOME" if home else "AWAY"
    if preheat and mins_to_home: mode_str += f"/PH{mins_to_home}"
    if long_preheat: mode_str += "/LONG"

    log_line = f"{day:02d}.{month:02d} {hour:02d}:{minute:02d} │ In {indoor:5.1f}→{target:5.1f} │ Out {outdoor:5.1f}({tmin_72h:+5.0f}/{tmin_96h:+5.0f}) │ Sh {final_shift:+6.1f} │ Sl {slope:6.3f} │ PV {pv_boost:5.1f} │ Supp {supply_temp:5.1f}°C │ PI {pi_shift:+6.1f} Z{zone_shift:5.1f} │ {mode_str}"
    hass.states.set('sensor.autopilot_log_last_line', log_line)
    logger.info(log_line)

    hass.states.set(FAIL_ENTITY, 0)
    logger.info("AUTOPILOT 2041.02 • РАБОТИ КАТО БОГ")
    logger.info("═" * 140)

except Exception as e:
    fail_count += 1
    hass.states.set(FAIL_ENTITY, fail_count)
    logger.error(f"ГРЕШКА #{fail_count}: {e}")
    if fail_count >= 4:
        hass.services.call('number', 'set_value', {'entity_id': 'number.cu401b_s_heating_curve_slope', 'value': 1.00})
        hass.services.call('number', 'set_value', {'entity_id': 'number.cu401b_s_heating_curve_shift', 'value': 0.0})
        hass.services.call('notify', 'mobile_app_damian_iphone', {'message': 'АВТОПИЛОТ 2041.02 → SAFE MODE'})
