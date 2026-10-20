import pytest
from app import app

@pytest.fixture
def client(tmp_path, monkeypatch):
    db = tmp_path / "test.db"
    monkeypatch.setitem(app.config, "DATABASE", str(db))
    with app.app_context():
        from app import init_db
        init_db()
    return app.test_client()

def test_home_and_search(client):
    r = client.get("/")
    assert r.status_code == 200
    assert b"Wireless Mouse" in r.data
    r = client.get("/?q=does-not-exist")
    assert b"No matches found" in r.data

def test_signup_login_cart_checkout(client):
    client.post("/signup", data={"name":"Test User","email":"test@example.com","password":"secret1"})
    client.post("/cart/add/1")
    r = client.get("/cart")
    assert b"Wireless Mouse" in r.data
    assert b"Proceed to checkout" in r.data
