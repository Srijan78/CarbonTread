# Single source of truth for all carbon emission factors in CarbonTread.
# Constants are in kg CO2 per unit, sourced and cited from PRD Section 5.

# Transport Emission Factors (kg CO2/km or kg CO2/passenger-km)
# Indian Railways passenger-km data (conservative estimate)
TRAIN_INTERCITY = 0.010
# Mid-size petrol car (ARAI/NITI Aayog real-world studies)
PETROL_CAR = 0.160
# Mid-size diesel car (diesel efficiency mileage scale-down)
DIESEL_CAR = 0.140
CNG_CAR = 0.110               # Mid-size passenger CNG car (rickshaw scale-up)
# Grid-charged mid-size EV (0.15 kWh/km * 0.736 grid factor)
ELECTRIC_CAR = 0.110
# Petrol two-wheeler (NITI Aayog real-world trip data)
TWO_WHEELER = 0.040
# CNG Auto-rickshaw (Clean Development Mechanism reports)
CNG_AUTO = 0.080
METRO = 0.012                 # DMRC / IEA & UIC railway reporting
BUS_SHARED = 0.040            # Shared bus passenger-km (WRI India averages)
# Domestic airline flight allocation (ICAO guidelines)
FLIGHT_DOMESTIC = 0.200
WALK_CYCLE = 0.000            # Zero-emission transport modes

# Energy/Electricity & Home Appliance Factors
# India grid kg CO2/kWh (CEA CO2 Database v21.0 Nov 2025)
GRID_FACTOR = 0.736
# AC daily usage footprint (assumes ~2 kWh/day * grid factor)
AC_DAILY_YES = 1.50
AC_DAILY_NO = 0.00            # Zero AC footprint
AC_DAILY_SEASONAL = 0.75      # Seasonal average AC usage across the year

# Cooking Fuel Factors
# Induction cooking daily (assumes ~1 kWh/day * grid factor)
INDUCTION_DAILY = 0.74
# Piped Natural Gas daily (assumes ~0.4 m3/day * IPCC defaults)
PNG_DAILY = 0.85
# LPG combustion factor (resolves to 42.4 kg per 14.2kg cylinder)
LPG_PER_KG = 2.984
# Derived daily baseline: 14.2kg cylinder lasting average of 60 days
# (14.2 kg * 2.984 kg CO2/kg) / 60 days = ~0.706 kg CO2/day
LPG_DAILY = 0.706

# Diet Factors (kg CO2/day)
# India-specific vegetarian dietary footprint (Pathak et al.)
DIET_VEG = 0.724
# India-specific non-vegetarian dietary footprint (Pathak et al.)
DIET_NON_VEG = 0.950
DIET_VEGAN = 0.600            # General plant-based diet offset baseline

# Daily Carbon Budget Target
# Level needed by 2030 to stay aligned with the 1.5°C climate goal (kg CO2/day)
DAILY_BUDGET = 6.0

# Onboarding Distance Midpoints (km)
DISTANCE_MIDPOINTS = {
    "0-5km": 3.0,
    "5-15km": 10.0,
    "15-30": 22.0,
    "15-30km": 22.0,  # Handle potential query/PRD casing variances
    "30km+": 35.0
}


def get_distance_midpoint(bucket: str) -> float:
    """Return the midpoint distance in km for a given onboarding distance bucket."""
    normalized = bucket.strip().lower().replace(" ", "")
    # Standardize formats
    if "0-5" in normalized:
        return DISTANCE_MIDPOINTS["0-5km"]
    elif "5-15" in normalized:
        return DISTANCE_MIDPOINTS["5-15km"]
    elif "15-30" in normalized:
        return DISTANCE_MIDPOINTS["15-30km"]
    elif "30" in normalized:
        return DISTANCE_MIDPOINTS["30km+"]
    return 10.0  # Default fallback midpoint


def calculate_transport_co2(
        mode: str,
        distance_km: float,
        fuel_type: str = None) -> float:
    """Calculate kg CO2 emitted for a given transport mode and distance."""
    normalized_mode = mode.strip().lower()
    normalized_fuel = fuel_type.strip().lower() if fuel_type else None

    if normalized_mode == "car":
        if normalized_fuel == "petrol":
            factor = PETROL_CAR
        elif normalized_fuel == "diesel":
            factor = DIESEL_CAR
        elif normalized_fuel == "cng":
            factor = CNG_CAR
        elif normalized_fuel == "electric":
            factor = ELECTRIC_CAR
        else:
            factor = PETROL_CAR  # Default fallback
    elif normalized_mode in ("uber_ola", "uber", "ola"):
        # Uber/Ola default to Petrol car factor unless overridden by a specific
        # fuel type
        if normalized_fuel == "petrol":
            factor = PETROL_CAR
        elif normalized_fuel == "diesel":
            factor = DIESEL_CAR
        elif normalized_fuel == "cng":
            factor = CNG_CAR
        elif normalized_fuel == "electric":
            factor = ELECTRIC_CAR
        else:
            factor = PETROL_CAR  # Default fallback
    elif normalized_mode in ("auto_rickshaw", "auto"):
        factor = CNG_AUTO
    elif normalized_mode == "two_wheeler":
        factor = TWO_WHEELER
    elif normalized_mode == "bus":
        factor = BUS_SHARED
    elif normalized_mode == "metro":
        factor = METRO
    elif normalized_mode == "train":
        factor = TRAIN_INTERCITY
    elif normalized_mode == "flight":
        factor = FLIGHT_DOMESTIC
    elif normalized_mode in ("walk_cycle", "walk", "cycle"):
        factor = WALK_CYCLE
    else:
        # PRD Section 3.1 Mode Defaults
        if normalized_mode == "bike":
            factor = TWO_WHEELER
        else:
            factor = WALK_CYCLE

    return max(0.0, distance_km * factor)


def calculate_diet_co2(diet_type: str) -> float:
    """Calculate daily kg CO2 footprint for a diet type."""
    normalized = diet_type.strip().lower()
    if "non" in normalized:
        return DIET_NON_VEG
    elif "vegan" in normalized:
        return DIET_VEGAN
    return DIET_VEG  # Default to Vegetarian


def calculate_ac_co2(ac_usage: str) -> float:
    """Calculate daily kg CO2 footprint for AC usage configuration."""
    normalized = ac_usage.strip().lower()
    if normalized == "yes":
        return AC_DAILY_YES
    elif normalized == "seasonal":
        return AC_DAILY_SEASONAL
    return AC_DAILY_NO


def calculate_cooking_co2(fuel: str) -> float:
    """Calculate daily kg CO2 footprint for cooking fuel configuration."""
    normalized = fuel.strip().lower()
    if normalized == "lpg":
        return LPG_DAILY
    elif "png" in normalized or "piped" in normalized:
        return PNG_DAILY
    elif "induction" in normalized:
        return INDUCTION_DAILY
    elif "mix" in normalized or "both" in normalized:
        # mixed defaults to LPG + Induction average if unspecified
        return (LPG_DAILY + INDUCTION_DAILY) / 2.0
    return LPG_DAILY  # Fallback baseline


def calculate_counterfactuals(
        distance_km: float,
        user_car_fuel: str = None) -> dict:
    """Compare a car journey's CO2 emissions against metro and bus alternatives."""
    # Determine reference car factor
    fuel = user_car_fuel.strip().lower() if user_car_fuel else "petrol"
    if fuel == "petrol":
        car_factor = PETROL_CAR
    elif fuel == "diesel":
        car_factor = DIESEL_CAR
    elif fuel == "cng":
        car_factor = CNG_CAR
    elif fuel == "electric":
        car_factor = ELECTRIC_CAR
    else:
        car_factor = PETROL_CAR

    car_co2 = distance_km * car_factor
    metro_co2 = distance_km * METRO
    bus_co2 = distance_km * BUS_SHARED

    return {
        "car_co2": round(car_co2, 3),
        "metro_co2": round(metro_co2, 3),
        "bus_co2": round(bus_co2, 3),
        "metro_saved": round(max(0.0, car_co2 - metro_co2), 3),
        "bus_saved": round(max(0.0, car_co2 - bus_co2), 3)
    }
