from pathlib import Path

from app.repository import authentication_query


def test_authentication_query_uses_pgcrypto_password_check():
    query = authentication_query()

    assert "FROM users" in query
    assert "password_hash = crypt($2, password_hash)" in query
    assert "status = 'active'" in query


def test_schema_creates_internal_admin_user():
    schema = Path("db/init/001_schema.sql").read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS users" in schema
    assert "'admin'" in schema
    assert "crypt('admin@123', gen_salt('bf'))" in schema

