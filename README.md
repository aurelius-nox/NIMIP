# NIMIP — Nepal Infrastructure Monitoring & Incident Platform

## Project Overview

NIMIP is a self-hosted monitoring and incident-management platform designed to detect service failures, create incidents, track repeated failures, and record recovery events.

The goal is to build a practical DevOps/SRE project that does more than simply deploy an application. It should identify service problems, maintain an incident history, and provide useful information for understanding failures and recovery.

## Technology Stack

- **Python** — application logic
- **Flask** — REST API
- **PostgreSQL** — persistent storage
- **psycopg2** — Python-to-PostgreSQL connection
- **Requests** — HTTP health checks
- **Docker** — local PostgreSQL container

## 1. Database Design

We established three related database tables.

### `services`

Stores the services that NIMIP monitors.

| Column       | Purpose                                   |
| ------------ | ----------------------------------------- |
| `service_id` | Unique service identifier and primary key |
| `name`       | Service name; must be unique              |
| `health_url` | URL used to check service health          |

### `incidents`

Stores service incidents.

| Column        | Purpose                                          |
| ------------- | ------------------------------------------------ |
| `incident_id` | Unique incident identifier and primary key       |
| `service_id`  | References the affected service                  |
| `is_resolved` | Indicates whether the incident has been resolved |
| `created_at`  | Time the incident was created                    |
| `resolved_at` | Time the incident was resolved; nullable         |

### `events`

Stores individual events associated with an incident.

| Column        | Purpose                                 |
| ------------- | --------------------------------------- |
| `event_id`    | Unique event identifier and primary key |
| `incident_id` | References the associated incident      |
| `event_type`  | Describes what happened                 |
| `created_at`  | Time the event was recorded             |

### Relationships

- One service can have multiple incidents.
- One incident can have multiple events.
- Foreign keys maintain the relationships between these tables.

We added timestamp columns to incidents so the system can track when an incident begins and ends. We also added event types and timestamps so individual incident events can be recorded chronologically.

## 2. REST API Implementation

The Flask application contains endpoints for managing services and incidents.

### Service endpoints

| Method | Endpoint                            | Purpose                                          |
| ------ | ----------------------------------- | ------------------------------------------------ |
| `GET`  | `/api/services`                     | Retrieve the list of services                    |
| `POST` | `/api/services`                     | Register a new service                           |
| `GET`  | `/api/services/<service_id>/health` | Check a service's health                         |
| `POST` | `/api/services/<service_id>/check`  | Perform a health check and update incident state |

Service registration accepts a name and an optional health URL. Basic input validation rejects missing or empty service names.

### Incident endpoints

| Method  | Endpoint                               | Purpose                                               |
| ------- | -------------------------------------- | ----------------------------------------------------- |
| `GET`   | `/api/incidents`                       | Retrieve incidents and their associated service names |
| `POST`  | `/api/incidents`                       | Create an incident manually                           |
| `PATCH` | `/api/incidents/<incident_id>/resolve` | Resolve an incident                                   |

The incident listing endpoint joins the `incidents` and `services` tables. It also calculates resolution duration in seconds using PostgreSQL timestamp arithmetic.

Input validation was added to the manual incident creation endpoint to ensure that `service_id` is a positive integer.

## 3. Service Health Checks

A separate Flask application acts as a monitored service.

- NIMIP API: port `5000`
- Monitored service: port `5002`
- Health endpoint: `/health`

The monitored service returns HTTP 200 when healthy.

NIMIP uses Python's `requests` library to send HTTP requests to the configured health URL. The request has a three-second timeout.

The health-check logic treats:

- HTTP 200 as healthy.
- Other HTTP status codes as unhealthy.
- Request errors and timeouts as unhealthy.

This gives NIMIP a way to detect service failures through actual HTTP checks rather than relying only on manually created incidents.

## 4. Automatic Incident Management

We implemented functions to manage the incident lifecycle:

- `check_service_health()` — checks the health URL.
- `get_open_incident()` — finds an unresolved incident for a service.
- `create_incident()` — creates an incident and records its initial failure event.
- `resolve_open_incident()` — resolves an open incident and records recovery.
- `record_event()` — inserts an event into the database.
- `process_service_check()` — connects health-check results to incident management.

The system follows this logic:

1. Check the service's health.
2. If the service is unhealthy and has no open incident, create an incident.
3. If the service is still unhealthy and already has an open incident, record another failure-check event.
4. If the service recovers while an incident is open, resolve the incident and record a recovery event.
5. If the service is healthy and no incident is open, do not create an incident.

This avoids creating a separate incident for every failed health check during one continuous outage.

## 5. Event Tracking

We introduced the following event types:

| Event type             | Meaning                                                     |
| ---------------------- | ----------------------------------------------------------- |
| `failure_detected`     | An outage was detected and an incident was created          |
| `failure_check_failed` | A subsequent health check found the service still unhealthy |
| `recovery_detected`    | The service recovered and the incident was resolved         |

Each event has its own identifier and timestamp. Multiple events can belong to the same incident, allowing the system to retain a history of what happened during an outage.

## 6. Background Monitoring

We implemented a background monitoring loop using Python's `threading` module.

The `monitor_services()` function:

1. Retrieves registered service IDs from PostgreSQL.
2. Checks each service through `process_service_check()`.
3. Prints the resulting action or error.
4. Waits approximately ten seconds before the next monitoring cycle.

The `start_monitor()` function launches this loop in a daemon thread when the application starts.

Services without a configured health URL are reported as unable to be checked. The `reporting-worker` test service was configured with a health URL and used to test the monitoring workflow.

## 7. Testing and Verification

We tested the incident lifecycle using the monitored service.

### Failure detection

When the monitored service became unavailable, NIMIP created an incident and recorded `failure_detected`.

### Repeated failure checks

While the service remained unavailable, subsequent checks recorded `failure_check_failed` events against the same incident.

For example, incident **9** accumulated multiple failure-check events. This verified that repeated checks did not create a new incident for every failed request.

### Recovery detection

When the monitored service became healthy again, NIMIP recorded `recovery_detected` and resolved the open incident.

The latest events for incident 9 showed:

- `recovery_detected`
- `failure_check_failed`
- `failure_check_failed`

The events were ordered newest first for this verification query. Their timestamps confirmed that repeated checks occurred approximately ten seconds apart and that recovery was recorded.

## 8. Concepts Practised

During this stage, we worked with:

- Relational database design and foreign keys
- PostgreSQL identity columns and default values
- Timestamp storage using `TIMESTAMPTZ`
- SQL joins and timestamp calculations
- Flask route definitions and HTTP methods
- JSON request validation and JSON responses
- Parameterized SQL queries
- HTTP health checks and request timeouts
- Python exception handling
- Background threads and periodic monitoring
- Incident lifecycle management
- Event history and timestamps
- Testing failures and recovery using a real local service

## 9. Current Project Status

Completed in this stage:

- Created the `services`, `incidents`, and `events` tables.
- Added service health URLs.
- Added incident creation and resolution timestamps.
- Added event types and timestamps.
- Implemented service and incident REST endpoints.
- Implemented HTTP health checks.
- Implemented automatic incident creation and resolution.
- Implemented repeated-failure and recovery event recording.
- Implemented a background monitoring loop.
- Tested the failure-to-recovery lifecycle.

## 10. Next Step

The next planned feature is an incident event timeline endpoint:

`GET /api/incidents/<incident_id>/events`

It will retrieve the events belonging to a particular incident in chronological order. This will make it possible to inspect the sequence of failure and recovery events through the API rather than querying PostgreSQL manually.

After that, the project can progress toward stronger error handling, automated tests, configuration through environment variables, Docker Compose, Kubernetes deployment, metrics, dashboards, and CI/CD.

The project is being developed incrementally, with an emphasis on understanding the underlying concepts rather than simply assembling code.

# NIMIP — Nepal Infrastructure Monitoring & Incident Platform

A containerized infrastructure monitoring and incident management platform built with Python, Flask, PostgreSQL, Docker, and Kubernetes.

NIMIP is designed to monitor application services, detect service failures, record incidents, and track service health. The project is being developed as a practical demonstration of DevOps engineering, container orchestration, application reliability, database persistence, and infrastructure management.

> **Project status:** Local development and Kubernetes deployment are operational. Resource requests and limits have been configured for the API, monitored service, and PostgreSQL workloads. Further reliability, security, and CI/CD improvements are planned.

---

## Table of Contents

- [Overview](#overview)
- [Project Goals](#project-goals)
- [Architecture](#architecture)
- [Technology Stack](#technology-stack)
- [Project Structure](#project-structure)
- [Application Components](#application-components)
- [Database Design](#database-design)
- [API Endpoints](#api-endpoints)
- [Local Development](#local-development)
- [Kubernetes Deployment](#kubernetes-deployment)
- [Resource Management](#resource-management)
- [Health Checks and Reliability](#health-checks-and-reliability)
- [Testing](#testing)
- [Security Considerations](#security-considerations)
- [Troubleshooting](#troubleshooting)
- [Current Limitations](#current-limitations)
- [Planned Improvements](#planned-improvements)
- [Learning Objectives](#learning-objectives)

---

## Overview

Modern applications depend on multiple services working together. When a service becomes unavailable, engineers need to identify the failure, understand its impact, record what happened, and determine when the service recovered.

NIMIP explores this problem through a locally deployable monitoring and incident management system.

The platform contains three main components:

1. **NIMIP API:** Provides HTTP endpoints for querying services, checking service health, and accessing incident information.
2. **Monitored service:** Exposes a health endpoint that the monitoring logic can check to determine service availability.
3. **PostgreSQL:** Stores registered services, incidents, and their associated events.

The application components run in containers and are deployed to a local Kubernetes cluster. Kubernetes manages the workloads, provides service discovery, and supports controlled application updates.

The project is designed to run locally, making it possible to practise containerization and orchestration without depending on paid cloud infrastructure.

## Project Goals

NIMIP aims to demonstrate practical DevOps skills through a working application rather than a collection of unrelated deployments.

The primary goals are to:

- Build a Python-based API for infrastructure monitoring and incident management.
- Run application components in separate containers.
- Persist application data in PostgreSQL.
- Deploy workloads to Kubernetes using declarative YAML manifests.
- Use Kubernetes Services for communication between components.
- Store database credentials in a Kubernetes Secret.
- Preserve database files using persistent storage.
- Configure CPU and memory requests and limits.
- Use readiness probes to check whether workloads are ready.
- Validate configuration changes before applying them.
- Verify application behavior after Kubernetes rollouts.
- Test service health and database persistence.
- Prepare the project for version control and future CI/CD automation.

---

## Architecture

### High-level architecture

```text
                   Developer / Client
                          |
                          | HTTP
                          v
                   NIMIP API :5000
                          |
                +---------+----------+
                |                    |
                v                    v
           PostgreSQL          Monitored Service
             :5432                  :5002
                |                    |
                v                    v
          Persistent Data       /health endpoint
                                     ^
                                     |
                              Health Monitoring
                              and Incident Logic
```

The API, database, and monitored service run as separate workloads in Kubernetes.

Kubernetes Services provide stable internal endpoints for communication between pods. The API connects to PostgreSQL through the `postgres` Service and can reach the monitored service through the `monitored-service` Service.

### Kubernetes namespace

The application workloads are deployed in the `nimip` namespace.

The namespace keeps NIMIP's Kubernetes resources logically grouped and makes it easier to inspect and manage the application's Deployments, Services, Secrets, and persistent storage.

### Internal service communication

| Component         | Kubernetes Service  | Internal port |
| ----------------- | ------------------- | ------------: |
| NIMIP API         | `api`               |          5000 |
| Monitored service | `monitored-service` |          5002 |
| PostgreSQL        | `postgres`          |          5432 |

The Kubernetes DNS names allow components to communicate without depending on pod IP addresses.

For example, the monitored service is reachable internally at:

`http://monitored-service:5002/health`

The PostgreSQL Service is reachable at:

`postgres:5432`

### Accessing the API locally

During local Kubernetes development, the API can be exposed to the host using `kubectl port-forward`:

```bash
kubectl port-forward -n nimip service/api 5050:5000
```

The API is then accessible at:

`http://localhost:5050`

The port-forward process must remain running in its terminal while the connection is in use.

---

## Technology Stack

| Technology             | Purpose                                    |
| ---------------------- | ------------------------------------------ |
| Python                 | Application and monitoring logic           |
| Flask                  | HTTP API and health endpoint               |
| PostgreSQL             | Persistent relational database             |
| Docker                 | Application containerization               |
| Docker Compose         | Local multi-container development          |
| Kubernetes             | Workload orchestration and recovery        |
| kind                   | Local Kubernetes cluster                   |
| Kubernetes Services    | Internal service discovery and networking  |
| Kubernetes Deployments | Application rollout and replica management |
| Kubernetes Secrets     | Database credential injection              |
| PersistentVolumeClaim  | Persistent database storage                |
| Readiness probes       | Determine whether a workload is ready      |
| pytest                 | Automated application tests                |
| Git and GitHub         | Version control and project hosting        |

---

## Project Structure

The main project files are organized as follows:

```text
NIMIP/
├── app/
│   ├── __init__.py
│   └── app.py
├── monitored_service/
│   ├── Dockerfile
│   └── app.py
├── k8s/
│   ├── api.yaml
│   ├── monitored-service.yaml
│   ├── postgres-pvc.yaml
│   └── postgres.yaml
├── tests/
│   ├── __init__.py
│   └── test_api.py
├── Dockerfile
├── compose.yaml
├── requirements.txt
├── README.md
└── .gitignore
```

### Important files

- `app/app.py` — the main Flask API and its application logic.
- `monitored_service/app.py` — the monitored application's HTTP health endpoint.
- `Dockerfile` — builds the API container image.
- `monitored_service/Dockerfile` — builds the monitored service image.
- `compose.yaml` — defines the local multi-container environment.
- `k8s/api.yaml` — defines the API Deployment and Service.
- `k8s/monitored-service.yaml` — defines the monitored service Deployment and Service.
- `k8s/postgres.yaml` — defines the PostgreSQL Deployment and Service.
- `k8s/postgres-pvc.yaml` — defines the database's PersistentVolumeClaim.
- `tests/test_api.py` — contains automated API tests.
- `requirements.txt` — lists Python dependencies.
- `.gitignore` — excludes local and generated files from Git.

The project may evolve as more features are added.

---

## Application Components

### 1. NIMIP API

The API provides HTTP endpoints for interacting with registered services and incident records.

Its responsibilities include:

- Returning registered services.
- Checking the health of a monitored service.
- Exposing incident information.
- Providing access to events associated with an incident.
- Supporting an endpoint for manually resolving an incident.

The API runs on port `5000` inside its container.

### 2. Monitored service

The monitored service exposes a health endpoint:

`GET /health`

When healthy, it returns:

```json
{
  "status": "ok"
}
```

The endpoint gives the monitoring logic a way to check whether the service is responding.

The service runs on port `5002` inside its container.

### 3. PostgreSQL

PostgreSQL stores the data used by the platform.

The database runs as a separate container and Kubernetes workload. Application components access it over the network rather than relying on an embedded database.

Database files are stored using a PersistentVolumeClaim so that replacing a PostgreSQL pod does not automatically mean losing the database's persistent files.

---

## Database Design

NIMIP uses three main database entities.

### Services

The `services` table represents the applications or workers being monitored.

Each service has a unique identifier and name. A service record also contains the health-check URL used by the monitoring logic.

Example registered services:

| Service ID | Name               |
| ---------: | ------------------ |
|          1 | `payment-worker`   |
|          2 | `inventory-worker` |
|          3 | `reporting-worker` |

These records have been verified in the running PostgreSQL database.

### Incidents

The `incidents` table records service failures.

Each incident references the service associated with the failure. This relationship allows a service to have multiple incidents over time.

Incident records can represent the period between a detected failure and its recovery or resolution.

### Events

The `events` table records events associated with incidents.

Event types used by the monitoring logic include:

- `failure_detected`
- `failure_check_failed`
- `recovery_detected`

This event history provides a record of how an incident developed and how the system detected recovery.

### Relationships

```text
Services
   |
   | One service can have multiple incidents
   v
Incidents
   |
   | One incident can have multiple events
   v
Events
```

The database uses relational keys to connect services, incidents, and events.

---

## API Endpoints

The following endpoints are implemented in the application.

| Method  | Endpoint                               | Purpose                                   |
| ------- | -------------------------------------- | ----------------------------------------- |
| `GET`   | `/api/services`                        | Return registered services                |
| `GET`   | `/api/incidents`                       | Return incident information               |
| `GET`   | `/api/incidents/<incident_id>/events`  | Return events associated with an incident |
| `GET`   | `/api/services/<service_id>/health`    | Check a service's health                  |
| `GET`   | `/api/services/<service_id>/check`     | Run a service check                       |
| `PATCH` | `/api/incidents/<incident_id>/resolve` | Request incident resolution               |

### Example: list services

Request:

```http
GET /api/services
```

Example response:

```json
[
  {
    "name": "payment-worker",
    "service_id": 1
  },
  {
    "name": "inventory-worker",
    "service_id": 2
  },
  {
    "name": "reporting-worker",
    "service_id": 3
  }
]
```

### Example: check service health

Request:

```http
GET /api/services/1/health
```

Example response when healthy:

```json
{
  "name": "payment-worker",
  "service_id": 1,
  "status": "healthy",
  "status_code": 200
}
```

### Example: retrieve incident events

Request:

```http
GET /api/incidents/1/events
```

This endpoint retrieves the event history for the specified incident. The returned information depends on the records currently stored in the database.

### Example: resolve an incident

Request:

```http
PATCH /api/incidents/1/resolve
```

This endpoint requests resolution of the specified incident. A valid incident identifier must be supplied.

---

## Local Development

### Prerequisites

Install the following tools:

- Python
- Git
- Docker with Docker Compose support
- `kubectl` for Kubernetes operations
- kind for a local Kubernetes cluster

The project is intended for local development. A paid cloud account is not required for the local workflow.

### 1. Clone the repository

After the project has been published to GitHub:

```bash
git clone https://github.com/aurelius-nox/NIMIP.git
cd NIMIP
```

To work on the development branch:

```bash
git switch develop
```

### 2. Create a Python virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

Upgrade pip if needed:

```bash
python -m pip install --upgrade pip
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run automated tests

```bash
pytest -v
```

### 5. Run the local environment

The repository includes a `compose.yaml` file for local multi-container development.

Start the Compose environment with:

```bash
docker compose up --build
```

Inspect running services:

```bash
docker compose ps
```

Follow the logs:

```bash
docker compose logs -f
```

Stop the environment:

```bash
docker compose down
```

**Important:** this command does not normally delete named volumes. Avoid `docker compose down -v` unless you intentionally want to remove the associated Compose-managed volumes.

The local environment requires the database credentials and service configuration expected by the Compose manifest. Review `compose.yaml` before running it and provide credentials securely rather than publishing real secrets.

---

## Kubernetes Deployment

NIMIP has been deployed to a local kind cluster.

The Kubernetes manifests are stored in the `k8s/` directory.

### 1. Verify the cluster

```bash
kubectl cluster-info
kubectl config current-context
```

For the development cluster used by this project, the context is:

```text
kind-kind
```

### 2. Create the namespace

If it does not already exist:

```bash
kubectl create namespace nimip
```

If Kubernetes reports that the namespace already exists, continue without recreating it.

### 3. Configure database credentials

The PostgreSQL Deployment uses a Kubernetes Secret named `postgres-secret`.

The Secret provides the database username, password, and database name to the PostgreSQL container.

A Secret can be created or updated using a secure deployment process. Do not commit real credential values to the repository.

Before applying the manifests, ensure that the expected Secret exists:

```bash
kubectl get secret postgres-secret -n nimip
```

This command displays Secret metadata, not the secret values.

### 4. Create persistent database storage

Apply the PersistentVolumeClaim manifest:

```bash
kubectl apply -f k8s/postgres-pvc.yaml
```

Check its status:

```bash
kubectl get pvc -n nimip
```

The PostgreSQL pod needs its PVC to be bound and its volume to be mounted successfully.

**Warning:** do not delete the PVC casually. Depending on the storage provisioner and persistent volume reclaim policy, deleting storage resources can cause data loss.

### 5. Deploy PostgreSQL

```bash
kubectl apply -f k8s/postgres.yaml
```

Wait for the rollout:

```bash
kubectl rollout status deployment/postgres -n nimip
```

### 6. Deploy the monitored service

```bash
kubectl apply -f k8s/monitored-service.yaml
```

Wait for the rollout:

```bash
kubectl rollout status deployment/monitored-service -n nimip
```

### 7. Deploy the API

```bash
kubectl apply -f k8s/api.yaml
```

Wait for the rollout:

```bash
kubectl rollout status deployment/api -n nimip
```

### 8. Inspect the workloads

```bash
kubectl get deployments -n nimip
kubectl get pods -n nimip
kubectl get services -n nimip
kubectl get pvc -n nimip
```

All expected application pods should eventually become ready.

### 9. Access the API

Open a dedicated terminal and run:

```bash
kubectl port-forward -n nimip service/api 5050:5000
```

In another terminal:

```bash
curl http://localhost:5050/api/services
```

Check the health of a registered service:

```bash
curl http://localhost:5050/api/services/1/health
```

Expected healthy response:

```json
{
  "name": "payment-worker",
  "service_id": 1,
  "status": "healthy",
  "status_code": 200
}
```

---

## Resource Management

Kubernetes resource requests and limits have been configured for all three main workloads.

These settings help Kubernetes schedule containers and constrain their CPU and memory consumption.

### Current resource configuration

| Workload          | CPU request | CPU limit | Memory request | Memory limit |
| ----------------- | ----------: | --------: | -------------: | -----------: |
| API               |      `100m` |    `500m` |        `128Mi` |      `256Mi` |
| Monitored service |       `50m` |    `250m` |         `64Mi` |      `128Mi` |
| PostgreSQL        |      `100m` |    `500m` |        `256Mi` |      `512Mi` |

These are initial development values. They have not been established through formal capacity testing and may need adjustment based on measured consumption.

### CPU requests and limits

A CPU quantity ending in `m` represents millicores.

For example:

- `100m` represents one-tenth of a CPU core.
- `500m` represents half of a CPU core.

A CPU request informs Kubernetes scheduling. A CPU limit caps CPU execution and can cause throttling when the container attempts to exceed its allocation.

### Memory requests and limits

Memory quantities use binary units such as `Mi`.

For example:

- `128Mi` represents 128 mebibytes.
- `512Mi` represents 512 mebibytes.

Memory requests influence scheduling. Exceeding a container's memory limit can result in termination with an out-of-memory condition.

### Inspect configured resources

For the API:

```bash
kubectl get deployment api -n nimip -o yaml
```

For the monitored service:

```bash
kubectl get deployment monitored-service -n nimip -o yaml
```

For PostgreSQL:

```bash
kubectl get deployment postgres -n nimip -o yaml
```

Configured limits are not the same as actual consumption. Future improvements should measure real usage and adjust resource settings accordingly.

---

## Health Checks and Reliability

### Application health endpoint

The monitored service exposes `/health`, which returns a successful response when the application is healthy.

The monitoring logic uses health-check responses to determine whether the service is available.

### Kubernetes readiness probes

The current manifests include readiness checks for the application workloads.

A readiness probe tells Kubernetes whether a pod is ready to receive traffic. An unsuccessful readiness check can cause Kubernetes to stop routing Service traffic to that pod until it becomes ready again.

PostgreSQL uses `pg_isready` in its readiness probe to check database availability.

### Deployment rollouts

Kubernetes Deployments manage the desired number of pod replicas and replace pods when their pod templates change.

For example, updating the API resource configuration triggers a rollout of the API Deployment.

Monitor a rollout using:

```bash
kubectl rollout status deployment/api -n nimip
```

Inspect pod status:

```bash
kubectl get pods -n nimip
```

An old pod may remain in `Terminating` temporarily while Kubernetes completes the replacement process.

### Verifying application behavior

A successful rollout alone does not prove that the application works end to end.

NIMIP has been verified using:

- Kubernetes pod and Deployment status.
- SQL queries against the PostgreSQL database.
- Requests to `/api/services`.
- Requests to `/api/services/1/health`.
- Internal network checks against the monitored service.

The database was verified to retain the registered service records after PostgreSQL's pod was replaced during a resource configuration update.

---

## Testing

The project includes automated tests in `tests/test_api.py`.

The test suite includes checks for:

- Retrieving registered services successfully.
- Handling requests for events associated with a nonexistent incident.
- Rejecting invalid service identifiers.

Run the test suite:

```bash
pytest -v
```

The previously executed test suite contained three tests, all of which passed.

Testing should be expanded as additional application features are implemented.

---

## Security Considerations

Security is an ongoing part of the project.

### Credentials

Database credentials should be provided through environment configuration or Kubernetes Secrets rather than hardcoded into committed files.

Do not commit:

- `.env` files containing real credentials.
- Database passwords or connection strings containing passwords.
- API tokens or private keys.
- Database backups containing potentially sensitive data.

### Git exclusions

The `.gitignore` file excludes common local development artifacts, including:

```gitignore
__pycache__/
*.py[cod]
.pytest_cache/
venv/
.venv/
.env
.env.*
!.env.example
*.sql
*.dump
.vscode/
```

Ignoring a file does not remove it from Git if it was already tracked. Review staged files before committing.

### Database backups

Database backups should be stored and managed separately from the public source repository.

Keep backups available until the restored database and persistent storage have been verified. Avoid publishing backups unless they have been reviewed and are intentionally safe to distribute.

### Kubernetes Secrets

Kubernetes Secrets provide a mechanism for supplying credentials to workloads. They should not be treated as automatically encrypted or fully protected in every cluster configuration.

Production deployments should consider appropriate access controls, encryption at rest, least-privilege permissions, and secure secret-management practices.

### Local development limitations

This project is a local development deployment. It should not be treated as production-hardened without further work on authentication, authorization, network restrictions, secret management, resource monitoring, and operational procedures.

---

## Troubleshooting

### API does not respond on port 5050

Check whether the port-forward process is still running.

Start it again if necessary:

```bash
kubectl port-forward -n nimip service/api 5050:5000
```

Then test:

```bash
curl http://localhost:5050/api/services
```

### A pod is not ready

Inspect the pods:

```bash
kubectl get pods -n nimip
```

Inspect a particular pod:

```bash
kubectl describe pod <pod-name> -n nimip
```

Read its logs:

```bash
kubectl logs <pod-name> -n nimip
```

Replace `<pod-name>` with the actual pod name.

### PostgreSQL is unavailable

Check the PostgreSQL workload:

```bash
kubectl get pods -n nimip
kubectl logs deployment/postgres -n nimip
kubectl get pvc -n nimip
```

Check database readiness from inside the PostgreSQL container:

```bash
kubectl exec -n nimip deployment/postgres -- \
  pg_isready -U postgres -d nimip
```

Avoid deleting the PVC as a troubleshooting shortcut.

### The API cannot reach the monitored service

Check the Service and Deployment:

```bash
kubectl get service monitored-service -n nimip
kubectl get deployment monitored-service -n nimip
kubectl get endpoints monitored-service -n nimip
```

The API must use the Kubernetes Service address rather than a `localhost` URL to reach a separate pod.

### A rollout fails

Check its status:

```bash
kubectl rollout status deployment/<deployment-name> -n nimip
```

Inspect the Deployment and related pods before attempting recovery:

```bash
kubectl describe deployment <deployment-name> -n nimip
kubectl get pods -n nimip
```

Do not force-delete resources or modify persistent storage before identifying the cause.

---

## Current Limitations

NIMIP is under active development. The following are known areas that need further work:

- Resource settings are initial estimates rather than the result of load testing.
- Readiness checks are configured, but liveness and startup probes require further evaluation.
- The local Kubernetes environment is not a production cluster.
- Automated CI/CD has not yet been established as part of the verified workflow documented here.
- Production-grade authentication and authorization require further implementation and review.
- Resource consumption has not yet been tuned using a complete set of performance measurements.

These limitations provide concrete opportunities for future development.

---

## Planned Improvements

Potential next steps include:

1. **CI/CD automation** — validate code and run automated tests on every proposed change.
2. **Container image automation** — build and publish versioned images through an automated pipeline.
3. **Kubernetes reliability** — evaluate liveness and startup probes, rollout behavior, and recovery strategies.
4. **Security hardening** — use least-privilege configuration, strengthen secret handling, and review container security settings.
5. **Resource tuning** — measure CPU and memory consumption under realistic workloads.
6. **Testing** — expand unit, integration, and failure-recovery coverage.
7. **Documentation** — document deployment procedures, architecture decisions, and operational recovery steps.
8. **Incident lifecycle improvements** — expand incident handling and event history as the application evolves.

These are planned improvements, not claims that the features are already implemented.

---

## Learning Objectives

NIMIP is being developed as a hands-on DevOps portfolio project.

It provides practical experience with:

- Containerizing Python applications.
- Connecting application containers to PostgreSQL.
- Defining multi-container environments with Docker Compose.
- Deploying applications with Kubernetes.
- Managing Kubernetes Deployments and Services.
- Understanding pod replacement and rolling updates.
- Using Kubernetes DNS for service discovery.
- Persisting database data using a PVC.
- Injecting credentials through Kubernetes Secrets.
- Configuring CPU and memory requests and limits.
- Using readiness probes.
- Testing HTTP endpoints and database persistence.
- Validating configuration changes before applying them.
- Preparing code for Git-based collaboration and automated delivery.

---

## Repository

GitHub: https://github.com/aurelius-nox/NIMIP

The repository is intended to contain the application source, Docker configuration, Kubernetes manifests, tests, and documentation required to understand and develop the project.

## License

A license has not yet been specified. Add an appropriate `LICENSE` file before presenting the project as open source or granting reuse rights.
