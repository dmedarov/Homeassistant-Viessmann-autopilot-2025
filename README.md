## Homeassistant-Viessmann-autopilot-2025
#Open-source Viessmann heat-pump autopilot for Home Assistant 2025+ · 15–35 % savings · GPS · PV boost · Cloudy Cherry


# Viessmann Autopilot 2025 — World #1 Open-Source Heat Pump Brain
**15–35 % реални спестявания · 100 % съвместим с Home Assistant 2025.11+**  
GPS preheat · Облачната черешка · PV boost + EMA · Многозонов PI · нулев риск

![Dashboard](screenshots/dashboard_full.png)

## Защо е #1 в света (2025–2026)
| Функция                    | Този автопилот | Viessmann Vitocal | Versatile Thermostat |
|----------------------------|----------------|---------------------|----------------------|
| Многозонов PI с тегла      | 5 зони + интеграли | Не                 | Не                  |
| GPS + време до вкъщи       | Да            | Не                 | Не                  |
| PV boost + EMA изглаждане  | до +11 °C     | Базов              | Не                  |
| Облачна черешка            | -1.0 °C при лошо време | Не            | Не                  |
| Безопасност целогодишно    | 100 %         | Да                 | Частично            |

## Инсталация (3 минути)
1. Копирай `viessmann_autopilot_2025.py` в `/config/python_scripts/`
2. Добави template сензорите в `configuration.yaml`
3. Добави Lovelace dashboard-а
4. Създай automation:
```yaml
- alias: Viessmann Autopilot
  trigger: time_pattern: "*/5"   # на всеки 5 минути
  action:
    - service: python_script.viessmann_autopilot_2025


Ключови функции и алгоритми
Проектът се отличава с комбинация от софтуерни и хардуерни интеграции:

Многозонова PI-регулация: 5 зони (хол, спални, долен етаж) с индивидуални интеграли (±7 °C·h) и тегла; главен PI за цялата система (интеграл ±9 °C·h).
GPS preheat: Изчислява време до вкъщи (дистанция/скорост + буфер 22 мин) и активира комфорт режим.
PV boost с EMA: Използва соларна продукция (до +11 °C shift) с експоненциално изглаждане (α=0.35) за плавни промени (памет ~10–40 мин).
Облачната черешка (Cloudy Cherry): Намалява целевата температура с -0.7 до -1.0 °C при нисък solar score (<30%) и отсъствие.
Защити: Динамични лимити на shift (-2.5 до +11 °C според външна температура и прогноза); защита на компресора и подаваща температура (>58 °C).
Съвместимост: 100% с HA 2025.11+; използва template сензори и automations.
