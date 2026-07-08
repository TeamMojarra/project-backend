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

    login_response = client.post(
        "/api/auth/login", json={"email": email, "password": password}
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def event_payload(
    name="Charla de Python",
    capacity=10,
    start_delta_days=2,
    max_tickets_per_purchase=1,
    price=0.0,
):
    start = datetime.now(timezone.utc) + timedelta(days=start_delta_days)
    end = start + timedelta(hours=2)
    return {
        "name": name,
        "description": "Evento de prueba",
        "event_type": "event",
        "modality": "presencial",
        "location": "Auditorio",
        "price": price,
        "start_datetime": start.isoformat(),
        "end_datetime": end.isoformat(),
        "total_capacity": capacity,
        "max_tickets_per_purchase": max_tickets_per_purchase,
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
            "price": 0.0,
            "start_datetime": None,
            "end_datetime": None,
            "total_capacity": 5,
            "max_tickets_per_purchase": 1,
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

    reservations_response = client.get("/api/reservations/my", headers=buyer_headers)
    assert reservations_response.status_code == 200
    assert reservations_response.json() == []


def test_event_purchase_limit_blocks_larger_reservations(client):
    owner_headers = register_and_login(client, "Owner", "owner@example.com")
    buyer_headers = register_and_login(client, "Buyer", "buyer@example.com")
    event = create_event(
        client, owner_headers, capacity=5, max_tickets_per_purchase=2
    )

    rejected_reservation = client.post(
        "/api/reservations",
        json={"event_id": event["id"], "quantity": 3},
        headers=buyer_headers,
    )
    assert rejected_reservation.status_code == 400
    assert "hasta 2 tickets" in rejected_reservation.json()["detail"]

    reservation = create_reservation(client, buyer_headers, event["id"], quantity=2)
    assert reservation["quantity"] == 2

    payment_response = client.post(
        f"/api/reservations/{reservation['id']}/pay",
        json={"holder_name": "Buyer", "result": "approved"},
        headers=buyer_headers,
    )
    assert payment_response.status_code == 200
    assert len(payment_response.json()["tickets"]) == 2

    tickets_response = client.get("/api/tickets/my", headers=buyer_headers)
    assert len(tickets_response.json()) == 2


def test_payment_amount_uses_event_price_and_quantity(client):
    owner_headers = register_and_login(client, "Owner", "owner@example.com")
    buyer_headers = register_and_login(client, "Buyer", "buyer@example.com")
    event = create_event(
        client,
        owner_headers,
        capacity=5,
        max_tickets_per_purchase=3,
        price=25.5,
    )
    reservation = create_reservation(client, buyer_headers, event["id"], quantity=3)

    payment_response = client.post(
        f"/api/reservations/{reservation['id']}/pay",
        json={"holder_name": "Buyer", "result": "approved"},
        headers=buyer_headers,
    )
    assert payment_response.status_code == 200
    assert payment_response.json()["payment"]["amount"] == 76.5


def test_cancel_pending_reservation_releases_capacity(client):
    owner_headers = register_and_login(client, "Owner", "owner@example.com")
    buyer_headers = register_and_login(client, "Buyer", "buyer@example.com")
    event = create_event(client, owner_headers, capacity=1)
    reservation = create_reservation(client, buyer_headers, event["id"])

    cancel_response = client.delete(
        f"/api/reservations/{reservation['id']}", headers=buyer_headers
    )
    assert cancel_response.status_code == 200

    event_response = client.get(f"/api/events/{event['id']}")
    assert event_response.json()["available_capacity"] == 1
    assert event_response.json()["status"] == "available"


def test_service_slots_can_be_generated_and_reserved(client):
    owner_headers = register_and_login(client, "Barber", "barber@example.com")
    buyer_headers = register_and_login(client, "Client", "client@example.com")
    service_response = client.post(
        "/api/events",
        json={
            "name": "Barberia",
            "description": "Corte clasico",
            "event_type": "service",
            "modality": "presencial",
            "location": "Local 1",
            "price": 12.0,
            "start_datetime": None,
            "end_datetime": None,
            "total_capacity": 1,
            "max_tickets_per_purchase": 1,
        },
        headers=owner_headers,
    )
    assert service_response.status_code == 201
    service = service_response.json()
    start = (datetime.now(timezone.utc) + timedelta(days=1)).date()
    generate_response = client.post(
        f"/api/events/{service['id']}/slots/generate",
        json={
            "start_date": start.isoformat(),
            "end_date": start.isoformat(),
            "weekdays": [start.weekday()],
            "start_time": "09:00:00",
            "end_time": "10:00:00",
            "slot_minutes": 30,
        },
        headers=owner_headers,
    )
    assert generate_response.status_code == 200
    slots = generate_response.json()
    assert len(slots) == 2

    reservation_response = client.post(
        "/api/reservations",
        json={"event_id": service["id"], "quantity": 1, "service_slot_id": slots[0]["id"]},
        headers=buyer_headers,
    )
    assert reservation_response.status_code == 201
    assert reservation_response.json()["service_slot"]["id"] == slots[0]["id"]

    available_slots = client.get(f"/api/events/{service['id']}/slots")
    assert len(available_slots.json()) == 1

    payment_response = client.post(
        f"/api/reservations/{reservation_response.json()['id']}/pay",
        json={"holder_name": "Client", "result": "approved"},
        headers=buyer_headers,
    )
    assert payment_response.status_code == 200
    assert payment_response.json()["payment"]["amount"] == 12.0


def test_cancelled_service_does_not_expose_available_slots(client):
    owner_headers = register_and_login(client, "Barber", "barber@example.com")
    service_response = client.post(
        "/api/events",
        json={
            "name": "Barberia",
            "description": "Corte clasico",
            "event_type": "service",
            "modality": "presencial",
            "location": "Local 1",
            "price": 12.0,
            "start_datetime": None,
            "end_datetime": None,
            "total_capacity": 1,
            "max_tickets_per_purchase": 1,
        },
        headers=owner_headers,
    )
    service = service_response.json()
    start = (datetime.now(timezone.utc) + timedelta(days=1)).date()
    client.post(
        f"/api/events/{service['id']}/slots/generate",
        json={
            "start_date": start.isoformat(),
            "end_date": start.isoformat(),
            "weekdays": [start.weekday()],
            "start_time": "09:00:00",
            "end_time": "10:00:00",
            "slot_minutes": 30,
        },
        headers=owner_headers,
    )

    update_response = client.put(
        f"/api/events/{service['id']}",
        json={**service, "status": "cancelled"},
        headers=owner_headers,
    )
    assert update_response.status_code == 200
    assert update_response.json()["status"] == "cancelled"

    slots_response = client.get(f"/api/events/{service['id']}/slots")
    assert slots_response.status_code == 200
    assert slots_response.json() == []


def test_rejected_service_payment_releases_slot(client):
    owner_headers = register_and_login(client, "Barber", "barber@example.com")
    buyer_headers = register_and_login(client, "Client", "client@example.com")
    service_response = client.post(
        "/api/events",
        json={
            "name": "Barberia",
            "description": "Corte clasico",
            "event_type": "service",
            "modality": "presencial",
            "location": "Local 1",
            "price": 12.0,
            "start_datetime": None,
            "end_datetime": None,
            "total_capacity": 1,
            "max_tickets_per_purchase": 1,
        },
        headers=owner_headers,
    )
    service = service_response.json()
    start = (datetime.now(timezone.utc) + timedelta(days=1)).date()
    slots = client.post(
        f"/api/events/{service['id']}/slots/generate",
        json={
            "start_date": start.isoformat(),
            "end_date": start.isoformat(),
            "weekdays": [start.weekday()],
            "start_time": "09:00:00",
            "end_time": "09:30:00",
            "slot_minutes": 30,
        },
        headers=owner_headers,
    ).json()
    reservation = client.post(
        "/api/reservations",
        json={"event_id": service["id"], "quantity": 1, "service_slot_id": slots[0]["id"]},
        headers=buyer_headers,
    ).json()

    payment_response = client.post(
        f"/api/reservations/{reservation['id']}/pay",
        json={"holder_name": "Client", "result": "rejected"},
        headers=buyer_headers,
    )
    assert payment_response.status_code == 200

    available_slots = client.get(f"/api/events/{service['id']}/slots")
    assert len(available_slots.json()) == 1


def test_owner_can_list_and_cancel_confirmed_reservation(client):
    owner_headers = register_and_login(client, "Owner", "owner@example.com")
    buyer_headers = register_and_login(client, "Buyer", "buyer@example.com")
    event = create_event(client, owner_headers, capacity=1)
    reservation = create_reservation(client, buyer_headers, event["id"])
    payment = client.post(
        f"/api/reservations/{reservation['id']}/pay",
        json={"holder_name": "Buyer", "result": "approved"},
        headers=buyer_headers,
    )
    assert payment.status_code == 200
    ticket_code = payment.json()["ticket"]["ticket_code"]

    reservations_response = client.get(
        f"/api/events/{event['id']}/reservations", headers=owner_headers
    )
    assert reservations_response.status_code == 200
    assert reservations_response.json()[0]["user"]["name"] == "Buyer"

    cancel_response = client.post(
        f"/api/reservations/{reservation['id']}/owner-cancel", headers=owner_headers
    )
    assert cancel_response.status_code == 200

    event_response = client.get(f"/api/events/{event['id']}")
    assert event_response.json()["available_capacity"] == 1
    validation_response = client.post(
        f"/api/tickets/{ticket_code}/validate", headers=owner_headers
    )
    assert validation_response.status_code == 200
    assert validation_response.json()["valid"] is False
    assert validation_response.json()["status"] == "cancelled"


def test_payment_confirmation_enforces_remaining_capacity(client):
    owner_headers = register_and_login(client, "Owner", "owner@example.com")
    first_buyer_headers = register_and_login(client, "First Buyer", "first@example.com")
    second_buyer_headers = register_and_login(
        client, "Second Buyer", "second@example.com"
    )
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

    buyer_validation = client.post(
        f"/api/tickets/{ticket_code}/validate", headers=buyer_headers
    )
    assert buyer_validation.status_code == 403

    owner_validation = client.post(
        f"/api/tickets/{ticket_code}/validate", headers=owner_headers
    )
    assert owner_validation.status_code == 200
    assert owner_validation.json()["valid"] is True
    assert owner_validation.json()["status"] == "valid"
    assert owner_validation.json()["ticket"]["event"]["name"] == event["name"]
    assert owner_validation.json()["ticket"]["user"]["name"] == "Buyer"

    duplicate_validation = client.post(
        f"/api/tickets/{ticket_code}/validate", headers=owner_headers
    )
    assert duplicate_validation.status_code == 200
    assert duplicate_validation.json()["valid"] is False
    assert duplicate_validation.json()["status"] == "already_used"
