from flask import Flask, jsonify, request
import psycopg2, requests
import threading
import os
import time
from psycopg2 import IntegrityError
from psycopg2.extras import RealDictCursor

app = Flask(__name__)

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:secret@localhost:5432/nimip"
)

@app.route("/api/services", methods=["GET"])
def get_services():
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT service_id, name, health_url FROM services ORDER BY service_id ASC;")
            rows = cur.fetchall()

    services = [{"service_id": row[0], "name": row[1]} for row in rows]
    return jsonify(services), 200


@app.route("/api/services", methods=["POST"])
def post_services():
    data = request.get_json()

    if not isinstance(data, dict) or not isinstance(data.get("name"), str) or not data["name"].strip():
        return jsonify({"error": "A non-empty service name is required"}), 400

    name = data["name"].strip()

    health_url = data.get("health_url")

    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "INSERT INTO services (name, health_url) VALUES (%s, %s) RETURNING service_id, name, health_url;",
                (name,health_url)
            )
            service = cur.fetchone()

    return jsonify(service), 201


@app.route("/api/incidents", methods=["GET"])
def get_incidents():
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    i.incident_id,
                    i.service_id,
                    s.name AS service_name,
                    i.is_resolved,
                    i.created_at,
                    i.resolved_at,
                    EXTRACT(EPOCH FROM (i.resolved_at - i.created_at))::float8 AS resolution_duration_seconds
                FROM incidents i
                JOIN services s ON i.service_id = s.service_id
                ORDER BY i.incident_id ASC;
            """)
            incidents = cur.fetchall()

    return jsonify(incidents), 200


@app.route("/api/incidents", methods=["POST"])
def post_incidents():
    data = request.get_json()

    if not isinstance(data, dict):
        return jsonify({"error": "A JSON object is required"}), 400

    service_id = data.get("service_id")

    if isinstance(service_id, bool) or not isinstance(service_id, int) or service_id <= 0:
        return jsonify({"error": "service_id must be a positive integer"}), 400

    try:
        with psycopg2.connect(DATABASE_URL) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    INSERT INTO incidents (service_id)
                    VALUES (%s)
                    RETURNING incident_id, service_id, is_resolved;
                    """,
                    (service_id,)
                )
                incident = cur.fetchone()

    except IntegrityError:
        return jsonify({"error": "Service already has an open incident"}), 409

    return jsonify(incident), 201

@app.route("/api/incidents/<int:incident_id>/resolve", methods = ["PATCH"])
def resolve_incident(incident_id):
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor(cursor_factory = RealDictCursor) as cur:
            cur.execute(
                """
                UPDATE incidents
                SET is_resolved = TRUE,
                resolved_at = NOW()
                WHERE incident_id = %s
                RETURNING incident_id, service_id, is_resolved, created_at, resolved_at;
                """, 
                (incident_id, )
            )
            updated_incident = cur.fetchone()
    if not updated_incident:
        return jsonify({"error": f"Incident with ID {incident_id} not found"}), 404
    return jsonify(updated_incident), 200

@app.route("/api/services/<int:service_id>/health", methods=["GET"])
def check_service(service_id):
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT service_id, name, health_url FROM services WHERE service_id = %s;",
                (service_id,)
            )
            service = cur.fetchone()

    if not service:
        return jsonify({"error": "Service not found"}), 404

    if not service["health_url"]:
        return jsonify({"error": "Service has no health URL"}), 400

    result = check_service_health(service["health_url"])

    return jsonify({
        "service_id": service["service_id"],
        "name": service["name"],
        **result
    }), 200


@app.route("/api/services/<int:service_id>/check", methods=["POST"])
def process_service_check_route(service_id):
    result, status_code = process_service_check(service_id)
    return jsonify(result), status_code



@app.route("/api/incidents/<int:incident_id>/events", methods=["GET"])
def get_incident_events(incident_id):
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                        "SELECT incident_id FROM incidents WHERE incident_id = %s",
                         (incident_id,)
                            )
            incident = cur.fetchone()
            
            if incident is None:
                return jsonify({"error": "Incident not found"}), 404

            cur.execute("""
                SELECT event_id, event_type, created_at
                FROM events
                WHERE incident_id = %s
                ORDER BY created_at ASC
            """, (incident_id,))

            events = cur.fetchall()

            

    return jsonify(events)



def get_open_incident(service_id):
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT incident_id, service_id, created_at
                FROM incidents
                WHERE service_id = %s
                  AND is_resolved = FALSE
                ORDER BY created_at ASC
                LIMIT 1;
                """,
                (service_id,)
            )
            return cur.fetchone()



def create_incident(service_id):
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO incidents (service_id)
                VALUES (%s)
                RETURNING incident_id, service_id, is_resolved, created_at;
                """,
                (service_id,)
            )
            incident = cur.fetchone()

            cur.execute(
                """
                INSERT INTO events (incident_id, event_type)
                VALUES (%s, %s);
                """,
                (incident["incident_id"], "failure_detected")
            )

    return incident




def resolve_open_incident(incident_id):
    """Resolve an incident and record its recovery event."""
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                UPDATE incidents
                SET is_resolved = TRUE,
                    resolved_at = NOW()
                WHERE incident_id = %s
                  AND is_resolved = FALSE
                RETURNING incident_id, service_id, is_resolved,
                          created_at, resolved_at;
                """,
                (incident_id,)
            )
            incident = cur.fetchone()

            if incident is not None:
                cur.execute(
                    """
                    INSERT INTO events (incident_id, event_type)
                    VALUES (%s, %s);
                    """,
                    (incident_id, "recovery_detected")
                )

    return incident



def check_service_health(health_url):
    try:
        response = requests.get(health_url, timeout=3)

        if response.status_code == 200:
            return {"status": "healthy", "status_code": response.status_code}

        return {"status": "unhealthy", "status_code": response.status_code}

    except requests.RequestException:
        return {"status": "unhealthy", "error": "Health check failed or timed out"}


def process_service_check(service_id):
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT service_id, name, health_url
                FROM services
                WHERE service_id = %s;
                """,
                (service_id,)
            )
            service = cur.fetchone()

    if not service:
        return {"error": "Service not found"}, 404

    if not service["health_url"]:
        return {"error": "Service has no health URL"}, 400

    health = check_service_health(service["health_url"])
    open_incident = get_open_incident(service_id)

    if health["status"] == "unhealthy":
        if open_incident is None:
            incident = create_incident(service_id)
            action = "incident_created"
        else:
            incident = open_incident
            record_event(
            incident["incident_id"],
            "failure_check_failed"
        )
        action = "incident_already_open"
    else:
        if open_incident is not None:
            incident = resolve_open_incident(
                open_incident["incident_id"]
            )
            action = "incident_resolved"
        else:
            incident = None
            action = "no_incident_needed"

    return {
        "service_id": service["service_id"],
        "name": service["name"],
        "health": health,
        "action": action,
        "incident": incident
    }, 200


def record_event(incident_id, event_type):
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO events (incident_id, event_type)
                VALUES (%s, %s);
                """,
                (incident_id, event_type)
            )

# for automatic checks
def monitor_services():
    while True:
        try:
            with psycopg2.connect(DATABASE_URL) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT service_id FROM services;"
                    )
                    service_ids = [row[0] for row in cur.fetchall()]

            for service_id in service_ids:
                try:
                    result, status_code = process_service_check(service_id)
                    print(
                        f"[monitor] service={service_id} "
                        f"action={result.get('action', result.get('error'))}"
                    )
                except Exception as exc:
                    print(
                        f"[monitor] service={service_id} "
                        f"check failed: {exc}"
                    )

        except Exception as exc:
            print(f"[monitor] monitoring cycle failed: {exc}")

        time.sleep(10)


def start_monitor():
    monitor_thread = threading.Thread(
        target=monitor_services,
        daemon=True
    )
    monitor_thread.start()


def record_event(incident_id, event_type):
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO events (incident_id, event_type)
                VALUES (%s, %s);
                """,
                (incident_id, event_type)
            )


if __name__ == "__main__":
    start_monitor()
    app.run(host="0.0.0.0", port=5000)