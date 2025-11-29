# Home Assistant Viessmann Autopilot 2025

Open-source advanced heat pump controller for Home Assistant (2025.11+)

Tested on 12 kW Viessmann Vitocal + 5–10 kW PV in real Bulgarian house since 2024.  
Real measured savings: 18–32 % compared to factory settings (2024–2025 season).

## Features
- 5-zone weighted PI control with per-zone integrals
- GPS-based preheat (time-to-home calculation)
- Smart PV excess boost with EMA smoothing (up to +11 °C shift)
- “Cloudy Cherry” target reduction when away and low solar score
- Polar Vortex pre-heat based on 72 h / 96 h forecast
- Long-comfort slope capping after 48 h presence
- Full safety limits (supply ≤ 59 °C, compressor protection)
- Summer OFF mode
- Complete sensor fallback cascade
- Full log history (300 lines) in sensor.autopilot_log

## Requirements
- Home Assistant 2025.11 or newer
- Viessmann heat pump (Modbus or official integration)
- Outdoor temperature sensor
- Indoor average temperature sensor
- PV production sensors
- (Recommended) 72 h forecast and humidity sensors

## Installation
1. Copy `viessmann_autopilot_2025.py` → `/config/python_scripts/`
2. Add the provided template sensors to `configuration.yaml`
3. (Optional) Import the Lovelace dashboard
4. Create one automation (recommended every 20 minutes):

```yaml
alias: Viessmann Autopilot 2030
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
mode: single
max: 2
