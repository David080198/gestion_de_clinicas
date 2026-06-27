"""Tests de autenticacion (Fase 2)."""

from __future__ import annotations


def test_register_patient(client, app):
    resp = client.post(
        "/api/auth/register",
        json={
            "email": "juan@test.com",
            "password": "Secret123",
            "first_name": "Juan",
            "last_name": "Perez",
            "role": "paciente",
            "document_number": "DOC123",
            "birth_date": "1990-05-15",
            "gender": "masculino",
        },
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["user"]["email"] == "juan@test.com"
    assert data["user"]["role"] == "paciente"


def test_login_and_me(client, admin_user):
    resp = client.post(
        "/api/auth/login",
        json={"email": "admin@test.com", "password": "Admin123!"},
    )
    assert resp.status_code == 200

    resp = client.get("/api/auth/me")
    assert resp.status_code == 200
    assert resp.get_json()["user"]["email"] == "admin@test.com"


def test_logout(client, admin_user):
    client.post(
        "/api/auth/login",
        json={"email": "admin@test.com", "password": "Admin123!"},
    )
    client.post("/api/auth/logout")
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_unauthorized_me(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401
