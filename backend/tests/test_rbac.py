import pytest

from app.repository import can_manage_users, normalize_user_role, public_user
from app.schemas import UserCreate, UserUpdate


def test_only_super_admin_can_manage_users():
    assert can_manage_users({"roles": ["super_admin"]}) is True
    assert can_manage_users({"roles": ["manager"]}) is False
    assert can_manage_users({"roles": ["viewer"]}) is False


def test_normalize_user_role_accepts_only_supported_roles():
    assert normalize_user_role("manager") == "manager"
    with pytest.raises(ValueError, match="Unsupported role"):
        normalize_user_role("operator")


def test_public_user_never_exposes_password_fields():
    result = public_user(
        {
            "id": 7,
            "username": "operator1",
            "full_name": "Operator One",
            "role": "manager",
            "status": "active",
            "roles": ["manager"],
            "region_ids": [1],
            "password_hash": "secret-hash",
        }
    )

    assert result["username"] == "operator1"
    assert "password_hash" not in result
    assert "password" not in result


def test_user_create_requires_password_and_user_update_makes_it_optional():
    assert UserCreate(username="new-user", password="password123", role="viewer").password == "password123"
    assert UserUpdate(role="manager").password is None
