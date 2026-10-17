NIMIP — Nepal Infrastructure Monitoring & Incident Platform.
Monitor services, detect failures, record incidents, understand what happened, and demonstrate recovery.

Failure>Detection>Incident>Recovery>Resolution

Core concept:
Service → waiter
Incident → waiter has a problem
Events → individual things that happened during the problem

Distinguished logical services from runtime processes:
payment-worker        ← logical service
       │
       ├── Pod A       ← temporary runtime instance
       │    PID 421
       │
       └── Pod B       ← replacement
            PID 817

Designed the database relationship:
services
    │
    │ 1 → many
    ↓
incidents
    │
    │ 1 → many
    ↓
events

Created the first Flask API:
HTTP request
     ↓
Flask route
     ↓
JSON response

Flask → PostgreSQL relationship
Flask
  ↓
psycopg2  (is the Python driver that allows our application to communicate with PostgreSQL.)
  ↓
PostgreSQL

Downloaded the PostgreSQL image > docker pull postgres

Created and started the PostgreSQL container:
docker run \
  --name nimip-postgres \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=secret \
  -e POSTGRES_DB=nimip \
  -p 5432:5432 \
  -d \
  postgres

                         Docker Desktop
                              │
              ┌───────────────┴───────────────┐
              │                               │
              ↓                               ↓
     kind-control-plane                 nimip-postgres
          Kubernetes                     PostgreSQL


docker exec -it nimip-postgres psql -U postgres -d nimip > psql terminal inside the container nimip

create schema:
CREATE TABLE services (
    service_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE incidents (
    incident_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    service_id INT NOT NULL REFERENCES services(service_id),
    is_resolved BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE events (
    event_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    incident_id INT NOT NULL REFERENCES incidents(incident_id)
);


connect this db with Flask > psycopg2.connect("postgresql://postgres:secret@localhost:5432/nimip")

add post method





NIMIP - Incident Management
do get and post for incident
we use join to connect service and incident on the basis of foreign key
update the incident, if solved using PATCH and update
added created_at and resolved_at
make incident detection automatic
make new flask for health

NIMIP API — manages services and incidents on port 5000.
Monitored service — exposes /health on port 5002.

Next:
NIMIP checks a service.
If the check fails, NIMIP creates an incident.
If an incident is already open for that service, NIMIP does not create another one.
When the service recovers, NIMIP resolves the open incident.

MAke the service check automatic

https://chatgpt.com/c/6ac4e62a-1bc8-83ec-9722-b064dc08405e