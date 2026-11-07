-- Database schema for the Apartment Rental Management System (SQLite).

CREATE TABLE IF NOT EXISTS listings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT    NOT NULL,
    city        TEXT    NOT NULL,
    rent        INTEGER NOT NULL CHECK (rent > 0),
    bedrooms    INTEGER NOT NULL CHECK (bedrooms BETWEEN 1 AND 10),
    status      TEXT    NOT NULL DEFAULT 'Available' CHECK (status IN ('Available', 'Rented'))
);

CREATE TABLE IF NOT EXISTS tenants (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name   TEXT    NOT NULL,
    phone       TEXT    NOT NULL CHECK (length(phone) = 10),
    email       TEXT
);

CREATE TABLE IF NOT EXISTS agreements (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    listing_id   INTEGER NOT NULL REFERENCES listings (id),
    tenant_id    INTEGER NOT NULL REFERENCES tenants (id),
    start_date   TEXT    NOT NULL,
    end_date     TEXT    NOT NULL,
    monthly_rent INTEGER NOT NULL CHECK (monthly_rent > 0)
);
