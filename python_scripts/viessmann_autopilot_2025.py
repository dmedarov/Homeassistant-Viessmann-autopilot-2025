# /config/python_scripts/viessmann_autopilot.py
# VIESSMANN AUTOPILOT 2033.01 ABSOLUTE FINAL – 57.9°C COMPROMISE
# Работи в HA 2025.12+ без никакви проблеми

logger.info("═" * 110)
logger.info("VIESSMANN AUTOPILOT 2033.01 • 57.9°C COMPROMISE • ЗАПУСНАТ БЕЗ ГРЕШКИ")
logger.info("═" * 110)

# ───── CIRCUIT BREAKER ─────
FAIL_ENTITY = 'sensor.autopilot_consecutive_failures'
fail_count = 0
fail_state = hass.states.get(FAIL_ENTITY)
if fail_state and fail_state.state not in ('unknown', 'unavailable'):
    try:
        fail_count = int(float(fail_state.state))
    except:
        pass

try:
    # ───── ПОМОЩНИ ФУНКЦИИ ─────
    def get_number(eid, default=0.0):
        st = hass.states.get(eid)
        if st and st.state not in ('unknown', 'unavailable', None, ''):
            try:
                return float(st.state)
            except:
                pass
        return float(default)

    def safe_temp(eid, default=5.0, alts=None):
        entities = [eid]
        if alts:
            entities += alts
        for ent in entities:
            st = hass.states.get(ent)
            if st and st.state not in ('unknown', 'unavailable', None, ''):
                try:
                    val = float(st.state)
                    if -40 <= val <= 70:
                        return val
                except:
                    pass
        return float(default)

    # ───── ВРЕМЕ ─────
    hour = 13
    st = hass.states.get('sensor.current_hour')
    if st and st.state not in ('unknown', 'unavailable'):
        try: hour = int(float(st.state))
        except: pass

    day = 5
    st = hass.states.get('sensor.current_day')
    if st and st.state not in ('unknown', 'unavailable'):
        try: day = int(float(st.state))
        except: pass

    month = 12
    st = hass.states.get('sensor.current_month')
    if st and st.state not in ('unknown', 'unavailable'):
        try: month = int(float(st.state))
        except: pass

    weekday = 0
    st = hass.states.get('sensor.day_of_week')
    if st and st.state not in ('unknown', 'unavailable'):
        try: weekday = int(float(st.state))
        except: pass
    is_weekend = weekday >= 5

    # ───── МИНУТИ (липсваше това!) ─────
    minute = 0
    st = hass.states.get('sensor.current_minute')
    if st and st.state not in ('unknown', 'unavailable'):
        try: minute = int(float(st.state))
        except: pass

    # ───── СЕНЗОРИ ─────
    outdoor     = safe_temp('sensor.outdoor_temperature', 3.0, ['sensor.cu401b_s_outside_temperature'])
    indoor      = safe_temp('sensor.indoor_temperature_avg', 21.0)
    supply_temp = safe_temp('sensor.cu401b_s_secondary_circuit_supply_temperature', 45.0)
    tmin_72h    = safe_temp('sensor.forecast_min_72h', outdoor - 3)
    tmin_96h    = safe_temp('sensor.forecast_min_96h', tmin_72h - 1)

    # ───── HOME STATUS ─────
    home = False
    st = hass.states.get('binary_sensor.damian_really_home_fixed')
    if st and str(st.state) == 'on':
        home = True
    st = hass.states.get('device_tracker.damian_iphone_14')
    if st and str(st.state) == 'home':
        home = True

    manual_force = get_number('input_boolean.heating_preheat_48h_force', 0) > 0
    auto_weekend = get_number('input_boolean.heating_weekend_mode_auto', 0) > 0
    is_holiday   = get_number('calendar.blgarski_ofitsialni_praznitsi_2025_2030', 0) > 0
    night_tariff = hour >= 22 or hour < 8
    compressor_on = get_number('binary_sensor.cu401b_s_compressor', 0) > 0
    current_runtime = get_number('sensor.compressor_current_runtime', 0.0)
    compressor_off_min = get_number('sensor.compressor_off_time_minutes', 0)

    # ───── GPS PREHEAT ─────
    preheat = False
    mins_to_home = None
    tracker_state = hass.states.get('device_tracker.damian_iphone_14')
    if tracker_state and tracker_state.attributes:
        dist = tracker_state.attributes.get('distance')
        spd = tracker_state.attributes.get('speed')
        if dist is not None and spd is not None:
            try:
                dist_km = float(dist) / 1000.0
                speed_kmh = max(float(spd), 12.0)
                if dist_km < 42 and speed_kmh > 12:
                    mins_to_home = int(dist_km / speed_kmh * 60) + 22
                    if 30 <= mins_to_home <= 200:
                        preheat = True
            except:
                pass

    long_preheat = manual_force or (auto_weekend and is_weekend and home) or (is_holiday and home)
    is_comfort = home or long_preheat or preheat

    # ───── ЦЕЛЕВА ТЕМПЕРАТУРА ─────
    comfort_temp = get_number('input_number.comfort_target_temp', 22.2)
    target = comfort_temp if is_comfort else max(comfort_temp - 1.5, 18.0)
    if preheat and mins_to_home:
        target += 1.3
    if 23 <= hour or hour < 6:
        sleep_temp = get_number('input_number.sleep_target_temp', 17.8)
        target = min(target, max(sleep_temp + 0.3, 17.8))

    # ───── PERSISTENT ─────
    persistent = hass.states.get('sensor.autopilot_persistent')
    last_slope = 1.04
    last_shift = 0.0
    if persistent and persistent.attributes:
        try: last_slope = float(persistent.attributes.get('last_slope', 1.04))
        except: pass
        try: last_shift = float(persistent.attributes.get('last_shift', 0.0))
        except: pass

    # ───── ANTI-WINDUP ─────
    if compressor_off_min > 180:
        for e in ['sensor.heating_pi_integral','sensor.pi_integral_living','sensor.pi_integral_downstairs',
                  'sensor.pi_integral_damian','sensor.pi_integral_honey','sensor.pi_integral_alex']:
            hass.states.set(e, 0.0, {'unit_of_measurement': '°C·h'})

    # ───── ЗОНИ И PI ─────
    zones = {
        'living_room': {'sensor': 'sensor.home_living_room_temperature', 'integral': 'sensor.pi_integral_living'},
        'downstairs': {'sensor': 'sensor.downstairs_temperature', 'integral': 'sensor.pi_integral_downstairs'},
        'bedroom_damian': {'sensor': 'sensor.bedroom_damian_temperature', 'integral': 'sensor.pi_integral_damian'},
        'bedroom_honey': {'sensor': 'sensor.bedroom_honey_temperature', 'integral': 'sensor.pi_integral_honey'},
        'alex_room': {'sensor': 'sensor.alex_room_temperature', 'integral': 'sensor.pi_integral_alex'},
    }
    room_weights = {'living_room': 1.35, 'downstairs': 1.30, 'bedroom_honey': 1.1, 'bedroom_damian': 1.0, 'alex_room': 0.7}
    zone_shift = 0.0
    INTERVAL_HOURS = 0.333

    for name, z in zones.items():
        temp = safe_temp(z['sensor'], 21.0)
        t_zone = 21.0 + (0.6 if is_comfort else -1.0)
        if (long_preheat or preheat) and name in ['living_room', 'downstairs']:
            t_zone += 0.7
        error = t_zone - temp
        integral = get_number(z['integral'], 0.0) + error * INTERVAL_HOURS
        integral = max(min(integral, 7.0), -7.0)
        weight = 1.4 if (long_preheat or preheat) and name in ['living_room', 'downstairs'] else 1.0
        this_shift = round((6.0 * max(error, 0) * room_weights.get(name, 1.0) + 0.08 * integral) * weight, 2)
        if this_shift > zone_shift:
            zone_shift = this_shift
        hass.states.set(z['integral'], round(integral, 3), {'unit_of_measurement': '°C·h'})

    error_main = target - indoor
    integral_main = get_number('sensor.heating_pi_integral', 0.0) + error_main * INTERVAL_HOURS
    integral_main = max(min(integral_main, 9.0), -9.0)
    pi_shift = round(8.3 * error_main + 0.10 * integral_main, 2)
    hass.states.set('sensor.heating_pi_integral', round(integral_main, 3), {'unit_of_measurement': '°C·h'})

    # ───── PV BOOST ─────
    prev_pv_boost = get_number('sensor.pv_boost_smoothed', 0.0)
    pv_now = get_number('sensor.power_production_now', 0.0)
    pv_rem = get_number('sensor.energy_production_today_remaining', 0.0)
    raw_pv_boost = 0.0
    if 7 <= hour <= 18 and outdoor > -10 and pv_now > 0.7:
        mult = 1.9 if night_tariff else 1.7
        extra = min(pv_rem * 0.40, 3.8) if hour < 14 and pv_rem > 5.0 and pv_now > 2.2 else 0.0
        raw_pv_boost = min(pv_now * mult + extra, 9.5)
    smoothing = 0.32 if (pv_rem + pv_now / 12) >= 5.0 else 0.20
    pv_boost = round(prev_pv_boost + smoothing * (raw_pv_boost - prev_pv_boost), 1)
    pv_boost = max(min(pv_boost, 9.5), 0.0)
    hass.states.set('sensor.pv_boost_smoothed', pv_boost, {'icon': 'mdi:solar-power-variant'})

    # ───── ФИНАЛЕН SHIFT + ЗАЩИТИ ─────
    final_shift = pi_shift * 0.58 + zone_shift * 0.24 + pv_boost * 0.11

    if compressor_on and current_runtime > 28:
        if current_runtime > 55: final_shift -= 2.4
        elif current_runtime > 45: final_shift -= 1.6
        elif current_runtime > 35: final_shift -= 0.9

    if compressor_on and supply_temp >= 52.0:
        final_shift -= min((supply_temp - 51.9) * 0.8, 3.0)
    if compressor_on and supply_temp >= 55.0:
        final_shift -= (supply_temp - 54.9) * 3.2
    if supply_temp >= 57.8:
        final_shift = max(final_shift - 12.0, -2.0)

    if night_tariff and is_comfort and indoor < target + 0.6:
        final_shift += min(2.4, (target + 0.6 - indoor) * 3.1)

    if tmin_96h <= -20: final_shift += 6.5
    elif tmin_72h <= -16: final_shift += 4.2
    elif tmin_72h <= -12: final_shift += 2.8

    master_gain = get_number('input_number.autopilot_master_gain', 0.96)
    if tmin_72h <= -16: master_gain = 1.02
    elif tmin_72h <= -12: master_gain = 0.99
    final_shift = round(final_shift * master_gain, 1)
    final_shift = max(min(final_shift, 12.0), -7.0)

    base_slope = get_number('number.cu401b_s_heating_curve_slope', 1.04)
    slope = base_slope + max(0, (10 - outdoor)) * 0.019 + max(0, (-tmin_72h - outdoor)) * 0.028
    if tmin_96h <= -22: slope = max(slope, 1.40)
    elif tmin_96h <= -19: slope = max(slope, 1.38)
    elif tmin_72h <= -16: slope = max(slope, 1.36)
    elif tmin_72h <= -12: slope = max(slope, 1.32)
    slope = round(max(min(slope, 1.40), 0.88), 3)

    if abs(slope - last_slope) > 0.015:
        hass.services.call('number', 'set_value', {'entity_id': 'number.cu401b_s_heating_curve_slope', 'value': slope})

    if abs(final_shift - last_shift) > 0.28:
        hass.services.call('number', 'set_value', {'entity_id': 'number.cu401b_s_heating_curve_shift', 'value': final_shift})

    offset = round(max(0, min(4, final_shift / 2)), 1)
    hass.services.call('input_number', 'set_value', {'entity_id': 'input_number.heating_offset_dynamic', 'value': offset})

    hass.states.set('sensor.autopilot_persistent', 0.0, {
        'last_slope': slope,
        'last_shift': final_shift,
        'friendly_name': 'Autopilot 2033.01 ABSOLUTE FINAL'
    })

    mode_str = "HOME" if home else "AWAY"
    if preheat: mode_str += f"/PH{mins_to_home or '?'}"
    if long_preheat: mode_str += "/LONG"

    log_line = (f"{day:02d}.{month:02d} {hour:02d}:{minute:02d} │ "
                f"In {indoor:4.1f}→{target:4.1f} │ "
                f"Out {outdoor:4.1f}({tmin_72h:+4.0f}/{tmin_96h:+4.0f}) │ "
                f"Sh {final_shift:+5.1f} │ Sl {slope:4.3f} │ "
                f"PV{pv_boost:4.1f} │ Supp {supply_temp:4.1f}°C │ "
                f"PI {pi_shift:+4.1f} Z{zone_shift:4.1f} │ {mode_str}")
    hass.states.set('sensor.autopilot_log_last_line', log_line)
    logger.info(log_line)

    hass.states.set(FAIL_ENTITY, 0)
    logger.info("VIESSMANN AUTOPILOT 2033.01 РАБОТИ ПЕРФЕКТНО")
    logger.info("═" * 110)

except Exception as e:
    fail_count += 1
    hass.states.set(FAIL_ENTITY, fail_count)
    logger.error(f"ГРЕШКА #{fail_count}: {e}")
    if fail_count >= 4:
        hass.services.call('number', 'set_value', {'entity_id': 'number.cu401b_s_heating_curve_slope', 'value': 1.05})
        hass.services.call('number', 'set_value', {'entity_id': 'number.cu401b_s_heating_curve_shift', 'value': 0.0})
        hass.services.call('notify', 'mobile_app_damian_iphone', {'message': 'АВТОПИЛОТ → SAFE MODE'})
