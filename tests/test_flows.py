from datetime import datetime, timedelta, timezone


def register_and_login(client, name, email):
    password = "Password1"
    register_response = client.post(
        "/api/auth/register",
        json={
            "name": name,
            "email": email,
            "password": password,
            "confirm_password": password,
        },
    )
    assert register_response.status_code == 201

    login_response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def event_payload(name="Charla de Python", capacity=10, start_delta_days=2):
    start = datetime.now(timezone.utc) + timedelta(days=start_delta_days)
    end = start + timedelta(hours=2)
    return {
        "name": name,
        "description": "Evento de prueba",
        "event_type": "event",
        "modality": "presencial",
        "location": "Auditorio",
        "start_datetime": start.isoformat(),
        "end_datetime": end.isoformat(),
        "total_capacity": capacity,
    }


def create_event(client, headers, **overrides):
    payload = event_payload(**overrides)
    response = client.post("/api/events", json=payload, headers=headers)
    assert response.status_code == 201
    return response.json()


def create_reservation(client, headers, event_id, quantity=1):
    response = client.post(
        "/api/reservations",
        json={"event_id": event_id, "quantity": quantity},
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


def test_event_owner_permissions_and_date_rules(client):
    owner_headers = register_and_login(client, "Owner", "owner@example.com")
    other_headers = register_and_login(client, "Other", "other@example.com")
    event = create_event(client, owner_headers)

    update_response = client.put(
        f"/api/events/{event['id']}",
        json={**event_payload(name="Cambio no autorizado"), "status": "available"},
        headers=other_headers,
    )
    assert update_response.status_code == 403

    past_event_response = client.post(
        "/api/events",
        json=event_payload(name="Evento pasado", start_delta_days=-1),
        headers=owner_headers,
    )
    assert past_event_response.status_code == 422

    service_response = client.post(
        "/api/events",
        json={
            "name": "Asesoría abierta",
            "description": "Servicio sin fecha definida",
            "event_type": "service",
            "modality": "virtual",
            "location": "Meet",
            "start_datetime": None,
            "end_datetime": None,
            "total_capacity": 5,
        },
        headers=owner_headers,
    )
    assert service_response.status_code == 201
    assert service_response.json()["start_datetime"] is None


def test_rejected_payment_keeps_capacity_and_does_not_create_ticket(client):
    owner_headers = register_and_login(client, "Owner", "owner@example.com")
    buyer_headers = register_and_login(client, "Buyer", "buyer@example.com")
    event = create_event(client, owner_headers, capacity=1)
    reservation = create_reservation(client, buyer_headers, event["id"])

    held_event_response = client.get(f"/api/events/{event['id']}")
    assert held_event_response.json()["available_capacity"] == 0

    payment_response = client.post(
        f"/api/reservations/{reservation['id']}/pay",
        json={"holder_name": "Buyer", "result": "rejected"},
        headers=buyer_headers,
    )
    assert payment_response.status_code == 200
    payment_data = payment_response.json()
    assert payment_data["payment"]["result"] == "rejected"
    assert payment_data["reservation"]["status"] == "rejected"
    assert payment_data["ticket"] is None

    event_response = client.get(f"/api/events/{event['id']}")
    assert event_response.json()["available_capacity"] == 1

    tickets_response = client.get("/api/tickets/my", headers=buyer_headers)
    assert tickets_response.status_code == 200
    assert tickets_response.json() == []


def test_payment_confirmation_enforces_remaining_capacity(client):
    owner_headers = register_and_login(client, "Owner", "owner@example.com")
    first_buyer_headers = register_and_login(client, "First Buyer", "first@example.com")
    second_buyer_headers = register_and_login(client, "Second Buyer", "second@example.com")
    event = create_event(client, owner_headers, capacity=1)

    first_reservation = create_reservation(client, first_buyer_headers, event["id"])
    second_reservation = client.post(
        "/api/reservations",
        json={"event_id": event["id"], "quantity": 1},
        headers=second_buyer_headers,
    )
    assert second_reservation.status_code == 400
    assert second_reservation.json()["detail"] == "No hay cupos suficientes"

    first_payment = client.post(
        f"/api/reservations/{first_reservation['id']}/pay",
        json={"holder_name": "First Buyer", "result": "approved"},
        headers=first_buyer_headers,
    )
    assert first_payment.status_code == 200
    assert first_payment.json()["ticket"]["ticket_code"].startswith("RSV-")

    event_response = client.get(f"/api/events/{event['id']}")
    assert event_response.json()["available_capacity"] == 0
    assert event_response.json()["status"] == "sold_out"


def test_only_event_owner_can_validate_ticket(client):
    owner_headers = register_and_login(client, "Owner", "owner@example.com")
    buyer_headers = register_and_login(client, "Buyer", "buyer@example.com")
    event = create_event(client, owner_headers, capacity=2)
    reservation = create_reservation(client, buyer_headers, event["id"])
    payment = client.post(
        f"/api/reservations/{reservation['id']}/pay",
        json={"holder_name": "Buyer", "result": "approved"},
        headers=buyer_headers,
    )
    ticket_code = payment.json()["ticket"]["ticket_code"]

    buyer_validation = client.post(f"/api/tickets/{ticket_code}/validate", headers=buyer_headers)
    assert buyer_validation.status_code == 403

    owner_validation = client.post(f"/api/tickets/{ticket_code}/validate", headers=owner_headers)
    assert owner_validation.status_code == 200
    assert owner_validation.json()["valid"] is True
    assert owner_validation.json()["status"] == "valid"

    duplicate_validation = client.post(f"/api/tickets/{ticket_code}/validate", headers=owner_headers)
    assert duplicate_validation.status_code == 200
    assert duplicate_validation.json()["valid"] is False
    assert duplicate_validation.json()["status"] == "already_used"
