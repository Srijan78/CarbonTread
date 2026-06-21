import pytest
import os
import tempfile
from flask.testing import FlaskClient
import services.db
from app import create_app


@pytest.fixture
def client() -> FlaskClient:
    """Configure a Flask test client with an isolated temporary SQLite database."""
    db_fd, temp_db_path = tempfile.mkstemp()
    old_db_path = services.db.DB_PATH
    services.db.DB_PATH = temp_db_path
    
    app = create_app()
    app.config["TESTING"] = True
    
    with app.test_client() as client:
        yield client
        
    services.db.DB_PATH = old_db_path
    os.close(db_fd)
    try:
        os.unlink(temp_db_path)
    except OSError:
        pass


def test_session_init(client: FlaskClient) -> None:
    """Verify that session initialization generates a valid UUID and inserts it into database."""
    response = client.post("/api/session/init")
    assert response.status_code == 201
    data = response.get_json()
    assert "user_id" in data
    assert len(data["user_id"]) == 36  # UUID length


def test_onboarding_and_dashboard(client: FlaskClient) -> None:
    """Verify the calibration flow profile storage and subsequent dashboard retrieval."""
    # 1. Initialize session
    init_res = client.post("/api/session/init")
    user_id = init_res.get_json()["user_id"]
    headers = {"X-User-ID": user_id}

    # 2. Submit Part A base profile
    profile_payload = {
        "city": "Mumbai",
        "commute_mode": "metro",
        "distance_bucket": "5-15km",
        "diet": "veg",
        "ac_usage": "yes",
        "cooking_fuel": "lpg"
    }
    prof_res = client.post("/api/onboarding/profile", json=profile_payload, headers=headers)
    assert prof_res.status_code == 200
    
    # 3. Submit Part B recap
    recap_payload = {
        "transport_pattern": "mostly_metro_bus",
        "food_pattern": "mostly_veg"
    }
    recap_res = client.post("/api/onboarding/recap", json=recap_payload, headers=headers)
    assert recap_res.status_code == 200

    # 4. Fetch dashboard
    dash_res = client.get("/api/dashboard", headers=headers)
    assert dash_res.status_code == 200
    dash_data = dash_res.get_json()
    
    assert dash_data["overall_confidence"] == "LOW"  # Today is low confidence (no today events logged yet)
    assert dash_data["categories"]["transport"]["confidence"] == "LOW"
    assert dash_data["categories"]["food"]["confidence"] == "LOW"


def test_event_logging(client: FlaskClient) -> None:
    """Verify structured manual event logging elevates category confidence."""
    # 1. Setup user
    init_res = client.post("/api/session/init")
    user_id = init_res.get_json()["user_id"]
    headers = {"X-User-ID": user_id}
    
    client.post("/api/onboarding/profile", json={
        "city": "Delhi", "commute_mode": "car", "commute_fuel": "petrol",
        "distance_bucket": "15-30km", "diet": "non-veg", "ac_usage": "no", "cooking_fuel": "png"
    }, headers=headers)

    # 2. Log transport trip (20km car)
    log_payload = {
        "category": "transport",
        "subtype": "car",
        "value": 20.0,
        "unit": "km",
        "fuel_type": "petrol"
    }
    log_res = client.post("/api/event/log", json=log_payload, headers=headers)
    assert log_res.status_code == 201
    log_data = log_res.get_json()
    assert log_data["status"] == "logged"
    assert "counterfactual" in log_data

    # 3. Check dashboard reflects logged transport event (HIGH confidence)
    dash_res = client.get("/api/dashboard", headers=headers)
    dash_data = dash_res.get_json()
    assert dash_data["categories"]["transport"]["confidence"] == "HIGH"
    assert dash_data["categories"]["transport"]["co2_kg"] == round(20.0 * 0.160, 3)


def test_session_isolation(client: FlaskClient) -> None:
    """Verify data isolation/multi-tenancy: User A logs must not affect User B dashboard states."""
    # 1. Initialize User A
    res_a = client.post("/api/session/init")
    user_a = res_a.get_json()["user_id"]
    headers_a = {"X-User-ID": user_a}
    client.post("/api/onboarding/profile", json={
        "city": "Bengaluru", "commute_mode": "metro",
        "distance_bucket": "5-15km", "diet": "veg", "ac_usage": "no", "cooking_fuel": "induction"
    }, headers=headers_a)

    # 2. Initialize User B
    res_b = client.post("/api/session/init")
    user_b = res_b.get_json()["user_id"]
    headers_b = {"X-User-ID": user_b}
    client.post("/api/onboarding/profile", json={
        "city": "Bengaluru", "commute_mode": "metro",
        "distance_bucket": "5-15km", "diet": "veg", "ac_usage": "no", "cooking_fuel": "induction"
    }, headers=headers_b)

    # 3. Log a high-emissions car event for User A (50km petrol car -> 8.0 kg CO2)
    client.post("/api/event/log", json={
        "category": "transport",
        "subtype": "car",
        "value": 50.0,
        "unit": "km",
        "fuel_type": "petrol"
    }, headers=headers_a)

    # 4. Fetch User B's dashboard — should ONLY reflect User B's low confidence baseline
    dash_b = client.get("/api/dashboard", headers=headers_b)
    data_b = dash_b.get_json()
    
    # User B's transport should still be LOW confidence (unaffected by User A's HIGH log)
    assert data_b["categories"]["transport"]["confidence"] == "LOW"
    # Transport co2 is baseline midpoint (10km) * metro factor (0.012) = 0.12 kg
    assert data_b["categories"]["transport"]["co2_kg"] == 0.12

    # Fetch User A's dashboard — should reflect User A's logged high confidence event
    dash_a = client.get("/api/dashboard", headers=headers_a)
    data_a = dash_a.get_json()
    
    assert data_a["categories"]["transport"]["confidence"] == "HIGH"
    assert data_a["categories"]["transport"]["co2_kg"] == 8.0


def test_missing_header_rejection(client: FlaskClient) -> None:
    """Verify routes reject requests missing the required X-User-ID header with 400 Bad Request."""
    response = client.get("/api/dashboard")
    assert response.status_code == 400
    assert response.get_json() == {"error": "Missing X-User-ID header"}


def test_invalid_user_rejection(client: FlaskClient) -> None:
    """Verify routes reject non-existent user IDs with 404 Not Found."""
    headers = {"X-User-ID": "non-existent-uuid-key-here"}
    response = client.get("/api/dashboard", headers=headers)
    assert response.status_code == 404
    assert response.get_json() == {"error": "User not found"}
