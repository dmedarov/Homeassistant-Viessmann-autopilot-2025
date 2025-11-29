# Home Assistant Viessmann Autopilot 2025

**Advanced open-source heat pump controller for Home Assistant 2025.11+**  
Real-world tested on 12 kW Viessmann Vitocal + 5–10 kW PV in Bulgaria since 2024  
Measured energy savings: **18–32 %** vs factory settings (2024–2025 season)

![Dashboard](screenshots/dashboard_full.png)

## Features

| Feature                              | Description                                                                 |
|--------------------------------------|-----------------------------------------------------------------------------|
| 5-zone weighted PI control           | Individual integral terms per room (±7 °C·h), main house PI (±9 °C·h)       |
| GPS preheat                          | Calculates exact time-to-home from iPhone/Android location + speed          |
| Smart PV excess boost                | EMA-smoothed boost up to +11 °C shift, prevents compressor cycling         |
| Cloudy Cherry™                       | –0.7 to –1.0 °C target reduction when away and solar_score < 35            |
| Polar Vortex pre-heat                | +4 to +6.5 °C bonus when 72–96 h forecast shows extreme cold               |
| Long-comfort degradation            | Caps heating curve slope at 0.92 after 48 h continuous presence            |
| Full safety system                   | Hard limits (supply ≤ 59 °C), 3-level compressor runtime protection        |
| Summer OFF mode                      | Automatic shutdown when outdoor > 20 °C and indoor > 23 °C                 |
| Sensor fallback cascade            | Works even if half the sensors are unavailable                              |
| Full log history                     | 300-line rolling log in `sensor.autopilot_log`                              |

## Requirements

- Home Assistant 2025.11 or newer
- Viessmann heat pump (official integration or Modbus)
- Outdoor temperature sensor
- Average indoor temperature sensor
- PV production sensors (`sensor.power_production_now`, `sensor.energy_production_today_remaining`)
- Recommended: 72–96 h weather forecast + outdoor humidity

## Installation (3 minutes)

1. Copy `viessmann_autopilot_2025.py` → `/config/python_scripts/`
2. Add the template sensors from `templates/` to your `configuration.yaml`
3. (Optional) Import the ready-made Lovelace dashboard from `lovelace/`
4. Create **one single** automation (this is the only one you need):

```yaml
alias: ♨️ Viessmann Autopilot 2030 — FINAL
description: Runs every 20 minutes + instant reaction on important changes
trigger:
  - platform: time_pattern
    minutes: 0
  - platform: time_pattern
    minutes: 20
  - platform: time_pattern
    minutes: 40
condition:
  - condition: state
    entity_id: input_boolean.heating_autopilot_enabled
    state: "on"
action:
  - service: python_script.viessmann_autopilot_2025
mode: single          # prevents duplicate executions
max: 2                # HA minimum allowed value

