# ShopLite — Playwright Practice E-commerce App

A deliberately small e-commerce application built for UI/API automation practice. It uses **Flask + SQLite + server-rendered Jinja templates + vanilla CSS/HTML**. No React, Node, Redis, PostgreSQL, or external payment service is required.

## Features

- New user sign-up
- Login/logout
- Product search
- Clear "No matches found" state
- Product detail page
- Add to cart
- Modify quantity
- Remove from cart
- Cart persistence across refresh/back and logout/login for the same account
- Guest cart that merges into the account after login
- Checkout page with itemized cart and total
- Mock payment page and successful payment flow
- Order history per logged-in user
- Stable `data-testid` attributes for Playwright selectors
- SQLite database created automatically

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5001

The database is created and seeded automatically on first run.

### Optional: use Flask CLI

```bash
flask --app app init-db
flask --app app run --debug
```

### Run smoke tests

```bash
pytest -q
```

## Docker

```bash
docker build -t shoplite .
docker run --rm -p 5000:5000 shoplite
```

The included `Dockerfile` uses a small Python base image and stores SQLite inside the container. For persistent production data, mount a volume and set `ECOMMERCE_DB`.


## Reset test data

Stop the app and delete `ecommerce.db`, then start it again. The database will be recreated with the seeded products.