from services.carbon_calculator import (
    get_distance_midpoint,
    calculate_transport_co2,
    calculate_diet_co2,
    calculate_ac_co2,
    calculate_cooking_co2,
    calculate_counterfactuals,
    PETROL_CAR,
    DIESEL_CAR,
    CNG_CAR,
    ELECTRIC_CAR,
    TWO_WHEELER,
    CNG_AUTO,
    METRO,
    BUS_SHARED,
    FLIGHT_DOMESTIC,
    DIET_VEG,
    DIET_NON_VEG,
    DIET_VEGAN,
    AC_DAILY_YES,
    AC_DAILY_NO,
    AC_DAILY_SEASONAL,
    LPG_DAILY,
    PNG_DAILY,
    INDUCTION_DAILY
)


def test_get_distance_midpoint() -> None:
    """Verify that distance buckets resolve to the correct midpoints and fallbacks."""
    assert get_distance_midpoint("0-5km") == 3.0
    assert get_distance_midpoint(" 5-15 km ") == 10.0
    assert get_distance_midpoint("15-30km") == 22.0
    assert get_distance_midpoint("30km+") == 35.0
    assert get_distance_midpoint("unknown") == 10.0


def test_calculate_transport_co2_modes() -> None:
    """Verify CO2 calculations across all supported transport modes."""
    # Base cases
    assert calculate_transport_co2("metro", 10.0) == 10.0 * METRO
    assert calculate_transport_co2("bus", 10.0) == 10.0 * BUS_SHARED
    assert calculate_transport_co2("train", 100.0) == 100.0 * 0.010
    assert calculate_transport_co2("flight", 500.0) == 500.0 * FLIGHT_DOMESTIC
    assert calculate_transport_co2("auto_rickshaw", 5.0) == 5.0 * CNG_AUTO
    assert calculate_transport_co2("two_wheeler", 15.0) == 15.0 * TWO_WHEELER
    assert calculate_transport_co2("walk_cycle", 5.0) == 0.0
    
    # Fallback/casing cases
    assert calculate_transport_co2("walk", 5.0) == 0.0
    assert calculate_transport_co2("bike", 10.0) == 10.0 * TWO_WHEELER
    assert calculate_transport_co2("unknown_mode", 10.0) == 0.0
    
    # Zero/negative bounds
    assert calculate_transport_co2("metro", 0.0) == 0.0
    assert calculate_transport_co2("metro", -10.0) == 0.0


def test_calculate_transport_co2_car_fuel() -> None:
    """Verify CO2 calculations for cars and ride-hailing services by fuel types."""
    # Personal Car
    assert calculate_transport_co2("car", 10.0, "petrol") == 10.0 * PETROL_CAR
    assert calculate_transport_co2("car", 10.0, "diesel") == 10.0 * DIESEL_CAR
    assert calculate_transport_co2("car", 10.0, "cng") == 10.0 * CNG_CAR
    assert calculate_transport_co2("car", 10.0, "electric") == 10.0 * ELECTRIC_CAR
    assert calculate_transport_co2("car", 10.0) == 10.0 * PETROL_CAR  # default fallback
    
    # Uber/Ola
    assert calculate_transport_co2("uber_ola", 10.0, "diesel") == 10.0 * DIESEL_CAR
    assert calculate_transport_co2("uber", 10.0, "electric") == 10.0 * ELECTRIC_CAR
    assert calculate_transport_co2("ola", 10.0) == 10.0 * PETROL_CAR  # default fallback


def test_calculate_diet_co2() -> None:
    """Verify dietary daily CO2 footprint aggregation and defaults."""
    assert calculate_diet_co2("veg") == DIET_VEG
    assert calculate_diet_co2("vegetarian") == DIET_VEG
    assert calculate_diet_co2("non-veg") == DIET_NON_VEG
    assert calculate_diet_co2("mostly non-veg") == DIET_NON_VEG
    assert calculate_diet_co2("vegan") == DIET_VEGAN
    assert calculate_diet_co2("other") == DIET_VEG  # default fallback


def test_calculate_ac_co2() -> None:
    """Verify daily AC configurations CO2 footprint mapping."""
    assert calculate_ac_co2("yes") == AC_DAILY_YES
    assert calculate_ac_co2("seasonal") == AC_DAILY_SEASONAL
    assert calculate_ac_co2("no") == AC_DAILY_NO
    assert calculate_ac_co2("unknown") == AC_DAILY_NO  # fallback


def test_calculate_cooking_co2() -> None:
    """Verify daily cooking configuration CO2 footprint values and fallbacks."""
    assert calculate_cooking_co2("lpg") == LPG_DAILY
    assert calculate_cooking_co2("png") == PNG_DAILY
    assert calculate_cooking_co2("piped gas") == PNG_DAILY
    assert calculate_cooking_co2("induction") == INDUCTION_DAILY
    assert calculate_cooking_co2("mixed") == (LPG_DAILY + INDUCTION_DAILY) / 2.0
    assert calculate_cooking_co2("unknown") == LPG_DAILY  # default fallback


def test_calculate_counterfactuals() -> None:
    """Verify comparative counterfactual calculations between car and transit modes."""
    distance = 15.0
    cf_petrol = calculate_counterfactuals(distance, "petrol")
    
    expected_car = distance * PETROL_CAR
    expected_metro = distance * METRO
    expected_bus = distance * BUS_SHARED
    
    assert cf_petrol["car_co2"] == round(expected_car, 3)
    assert cf_petrol["metro_co2"] == round(expected_metro, 3)
    assert cf_petrol["bus_co2"] == round(expected_bus, 3)
    assert cf_petrol["metro_saved"] == round(max(0.0, expected_car - expected_metro), 3)
    assert cf_petrol["bus_saved"] == round(max(0.0, expected_car - expected_bus), 3)

    # Test diesel EV difference
    cf_ev = calculate_counterfactuals(distance, "electric")
    assert cf_ev["car_co2"] == round(distance * ELECTRIC_CAR, 3)
