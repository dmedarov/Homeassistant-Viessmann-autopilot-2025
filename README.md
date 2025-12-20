# Home Assistant Viessmann Autopilot 2025

# dmedarov/Homeassistant-Viessmann-autopilot-2025

**Advanced Open-Source Autopilot for Viessmann Heat Pumps in Home Assistant (2025+ Models)**  
**Achieving 15–35% Energy Savings • GPS-Based Preheat • Adaptive PV Excess Utilization • Cloud-Optimized Performance**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)  
[![HACS Custom Repository](https://img.shields.io/badge/HACS-Custom-blue.svg)](https://hacs.xyz)  
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/downloads/)  
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2025%2B-orange.svg)](https://www.home-assistant.io/)
























## Project Overview

This repository contains a sophisticated Python script designed to serve as an intelligent autopilot for Viessmann air-to-water heat pumps (e.g., Vitocal series with CU401B controllers) integrated into Home Assistant.

The autopilot dynamically optimizes the heating curve (slope and parallel shift) using advanced control algorithms, including multi-zone PI controllers with professional anti-windup techniques. It incorporates presence detection, GPS-based arrival prediction, weather forecast anticipation, and highly adaptive photovoltaic (PV) excess energy utilization—even under cloudy conditions ("Cloudy Cherry" optimization).

**Real-World Performance** (140 m² home with radiators, December 2025 data):
- Seasonal COP exceeding 3.2 in winter conditions (superior to typical 2.8–3.3 for radiator systems).
- 96–98% PV self-consumption rate.
- Estimated annual energy savings of 15–35% compared to standard Viessmann/ViCare controls.
- Consistent supply temperatures below 52°C, with a strict 57.9°C maximum ("Radiator Religion" principle).












## Key Features

- **Multi-Zone PI Control**: Individual proportional-integral controllers per room/zone, with weighted contributions, back-calculation anti-windup, and reset on comfort mode transition for exceptional stability (±0.1–0.2°C deviation).
- **Presence and GPS Preheat**: Real-time arrival prediction using device tracker data (e.g., iPhone location and speed).
- **Adaptive PV Boost ("Cloud Perfection")**: Cloud-cover-aware algorithms with smoothing, remaining production extras, and sunset buffering for maximum self-consumption.
- **Forecast Integration**: Proactive adjustments based on 72–96 hour minimum temperature predictions.
- **Safety and Efficiency Safeguards**: Compressor runtime penalties, supply temperature sanctions, hard 57.9°C cap, failure detection with safe mode fallback.
- **Version 2042.01 Enhancements**: Industrial-grade back-calculation anti-windup, comfort transition integral reset, reduced maximum slope (1.25) for enhanced COP.
















## Installation and Setup

1. Copy `viessmann_autopilot.py` to your Home Assistant `/config/python_scripts/` directory.
2. Ensure Viessmann integration entities are available (e.g., via ViCare component) and create necessary custom sensors.
3. Reload Python scripts or restart Home Assistant.
4. Schedule execution every 20 minutes:

```yaml
automation:
  - alias: "Viessmann Autopilot Execution"
    trigger:
      - platform: time_pattern
        minutes: "/20"
    action:
      - service: python_script.viessmann_autopilot
```

## Required Helpers (Create via UI > Helpers)

- `input_number.comfort_target_temp` (default: 22.2°C)
- `input_number.away_target_temp` (default: 19.8°C)
- `input_number.sleep_target_temp` (default: 17.8°C)
- `input_boolean.heating_preheat_48h_force`
- `input_boolean.heating_weekend_mode_auto`
- `input_number.autopilot_master_gain` (default: 0.96)

## Comparison with Alternatives

| Feature                          | This Autopilot                          | Official ViCare App                  | Standard HA ViCare Integrations      | Other Open-Source Heat Pump Projects |
|----------------------------------|-----------------------------------------|--------------------------------------|--------------------------------------|--------------------------------------|
| Dynamic Curve Override (Slope/Shift) | Full (PI + PV + Forecast)              | Basic Manual Adjustment             | Limited/Monitoring Only             | Rare/Basic                          |
| Multi-Zone PI with Anti-Windup   | Advanced (Back-Calculation + Reset)    | None                                | None                                | Basic PID (Few)                     |
| GPS Preheat & Presence           | Precise (Distance/Speed Prediction)    | Basic Schedules                     | Manual Automations                  | Occasional                          |
| Cloud-Adaptive PV Boost          | Yes ("Cloudy Cherry" Optimization)     | Basic Excess Detection              | Custom Add-ons Required             | Simple Thresholds                   |
| Forecast Anticipation            | 72–96h Minimum Temps                   | None                                | None                                | Rare                                |
| Real Winter COP (Radiators)      | 3.2+ (Verified 2025 Data)              | 2.8–3.3                             | Dependent on User Tuning            | 3.0–3.5 (Underfloor Preferred)      |

This project uniquely blends industrial control theory with smart home automation, delivering superior efficiency and stability.

## License

Released under the MIT License. Free for use, modification, and distribution.

Contributions are welcome—issues, feature requests, and pull requests are encouraged.

**Author**: dmedarov  
**Development Period**: 2021–2025 (Continuous Real-World Optimization)  
**Support the Project**: Star and share to promote efficient, sustainable heating solutions. 🚀
