from types import SimpleNamespace

import pytest
from fastapi import HTTPException, status

from app.dependencies import require_event_owner, require_ticket_validator


def user(user_id, role="user"):
    return SimpleNamespace(id=user_id, role=role)


def event(created_by):
    return SimpleNamespace(created_by=created_by)


@pytest.mark.parametrize(
    "current_user",
    [user(10), user(10, role="admin"), user(99, role="admin")],
)
def test_event_owner_permission_allows_owner_and_admin(current_user):
    require_event_owner(event(created_by=10), current_user)


@pytest.mark.parametrize("current_user", [user(99), user(0), user(-1)])
def test_event_owner_permission_rejects_non_owner_user(current_user):
    with pytest.raises(HTTPException) as error:
        require_event_owner(event(created_by=10), current_user)

    assert error.value.status_code == status.HTTP_403_FORBIDDEN
    assert error.value.detail == "No tienes permisos sobre este evento"


@pytest.mark.parametrize(
    "current_user",
    [user(10), user(10, role="admin"), user(99, role="admin")],
)
def test_ticket_validator_permission_allows_owner_and_admin(current_user):
    require_ticket_validator(event(created_by=10), current_user)


@pytest.mark.parametrize("current_user", [user(99), user(0), user(-1)])
def test_ticket_validator_permission_rejects_non_owner_user(current_user):
    with pytest.raises(HTTPException) as error:
        require_ticket_validator(event(created_by=10), current_user)

    assert error.value.status_code == status.HTTP_403_FORBIDDEN
    assert (
        error.value.detail == "No tienes permisos para validar tickets de este evento"
    )
