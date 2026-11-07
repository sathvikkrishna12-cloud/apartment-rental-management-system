# Apartment Rental Management System

A small web application for managing apartment listings, tenants and rental
agreements. Owners add apartments with rent and bedrooms, tenants register,
and a rental agreement marks the apartment as rented. Anyone can search for
available apartments by city and maximum rent.

## Features

- Add, view and update apartment listings
- Register tenants with name, phone and email
- Create rental agreements (an apartment can only be rented once at a time)
- Search available apartments by city and maximum rent
- Validation for rent, bedrooms, phone numbers and dates

## Tech stack

- Python 3 (standard library only: `http.server`, `sqlite3`)
- SQL (SQLite) for storage
- HTML and CSS for the interface

No third-party packages are needed.

## Getting started

```bash
git clone https://github.com/<your-username>/apartment-rental-management-system.git
cd apartment-rental-management-system
python app.py
```

Then open http://127.0.0.1:8001 in your browser.

The database file `rentals.db` is created automatically on the first run from
`schema.sql`. To use a different location, set the `RENTAL_DB` environment
variable. To use a different port, set `PORT`.

## Project structure

```
apartment-rental-management-system/
├── app.py            # Server, routes, validation and HTML pages
├── schema.sql        # Database tables
├── static/
│   └── style.css     # Page styling
├── .gitignore
└── README.md
```

## How it works

1. **Apartments** are stored in `listings` with a status of Available or Rented.
2. **Tenants** are stored in `tenants`.
3. **Agreements** link one apartment to one tenant with start and end dates.
   Creating an agreement marks the apartment as Rented.
4. **Search** shows apartments that are Available, filtered by city and rent.
