# Database design

The system uses two databases, each for what it does best.

- **PostgreSQL** – relational and transactional data (accounts, vehicles, alerts, audit trail).
- **MongoDB** – high-volume, flexible, time-series-like data (telemetry, ML output, logs).
- **Object storage (S3 / MinIO)** – audio files. Databases hold only the URL and metadata.

## PostgreSQL tables

All primary keys are UUIDs. Timestamps are timezone-aware (UTC). Enum-like columns are plain
strings validated by the API (no PostgreSQL ENUM types, so adding a value needs no migration).

### `users`
| Column | Notes |
| --- | --- |
| `id` | UUID PK |
| `name`, `email` | `email` unique + indexed (stored lower-case) |
| `password_hash` | bcrypt hash (SHA-256 pre-hashed to avoid the 72-byte limit). Never plain text |
| `role` | `admin` or `user` |
| `created_at`, `updated_at` | |

### `user_sessions` (refresh/revocation support)
One row per issued token; its `id` is the JWT `jti`. `expires_at`, `revoked_at`. `POST /auth/logout`
sets `revoked_at`, so a stolen token stops working immediately.

### `vehicles`
`id`, `vehicle_code` (unique, indexed, e.g. `CAR-1024`), `vehicle_type`, `status`
(`connected` / `disconnected` / `maintenance`), `owner_id` → `users`, `last_seen_at`,
`created_at`, `updated_at`.

### `vehicle_assignments`
`id`, `user_id` → `users`, `vehicle_id` → `vehicles`, `assigned_at`; unique on
`(user_id, vehicle_id)`. A user can access a vehicle they own or are assigned to; admins see all.

### `audio_records`
`id`, `vehicle_id` → `vehicles` (indexed), `storage_url`, `file_name`, `file_type`,
`duration_seconds`, `file_size`, `uploaded_at`, `processing_status`
(`pending` / `processing` / `completed` / `failed`).

### `alerts`
`id`, `vehicle_id` → `vehicles` (indexed), `audio_record_id` → `audio_records` (nullable),
`event_type`, `severity` (`low` / `medium` / `high` / `critical`), `confidence` (0–1),
`status` (`open` / `acknowledged` / `resolved`, indexed), `location`, `detected_at` (indexed),
`reviewed_at`, `resolved_at`.

### `alert_actions`
Audit trail. `id`, `alert_id` → `alerts` (indexed), `user_id` → `users` (null for system-created),
`action_type` (`created` / `acknowledged` / `resolved`), `notes`, `created_at`.

### `device_status`
Latest health snapshot, one row per vehicle (unique `vehicle_id`): `microphone_status`,
`gps_status`, `engine_status`, `battery_level`, `last_sync_at`, plus control state
(`monitoring_mode`, `audio_capture_enabled`, `recording`) and `online_since` (start of the current
connected period; drives the uptime display). Updated whenever telemetry arrives.

### `devices`
IoT inventory and current state. `id`, `vehicle_id` → `vehicles` (nullable so history survives
vehicle deletion), `owner_id` → `users`, `hardware_id` (globally unique), `name`,
`firmware_version`, JSON `configuration`, `state`, `last_heartbeat_at`, `retired_at`, `removed_at`,
`created_at`, `updated_at`. Device states are `PENDING`, `ONLINE`, `WARNING`, `DELAYED`, `OFFLINE`,
`DISABLED`, and terminal `RETIRED`.

## Entity relationships

```mermaid
erDiagram
    USERS ||--o{ USER_SESSIONS : "has"
    USERS ||--o{ VEHICLES : "owns"
    USERS ||--o{ VEHICLE_ASSIGNMENTS : "assigned"
    VEHICLES ||--o{ VEHICLE_ASSIGNMENTS : "assigned to"
    VEHICLES ||--o{ AUDIO_RECORDS : "records"
    VEHICLES ||--o{ ALERTS : "raises"
    VEHICLES ||--|| DEVICE_STATUS : "reports"
    VEHICLES ||--o{ DEVICES : "contains"
    USERS ||--o{ DEVICES : "owns"
    AUDIO_RECORDS |o--o{ ALERTS : "triggers"
    ALERTS ||--o{ ALERT_ACTIONS : "audited by"
    USERS |o--o{ ALERT_ACTIONS : "performs"

    USERS {
        uuid id PK
        string name
        string email UK
        string password_hash
        string role
        datetime created_at
        datetime updated_at
    }
    USER_SESSIONS {
        uuid id PK
        uuid user_id FK
        datetime expires_at
        datetime revoked_at
    }
    VEHICLES {
        uuid id PK
        string vehicle_code UK
        string vehicle_type
        string status
        uuid owner_id FK
        datetime last_seen_at
    }
    VEHICLE_ASSIGNMENTS {
        uuid id PK
        uuid user_id FK
        uuid vehicle_id FK
        datetime assigned_at
    }
    AUDIO_RECORDS {
        uuid id PK
        uuid vehicle_id FK
        string storage_url
        string file_name
        string file_type
        float duration_seconds
        int file_size
        datetime uploaded_at
        string processing_status
    }
    ALERTS {
        uuid id PK
        uuid vehicle_id FK
        uuid audio_record_id FK
        string event_type
        string severity
        float confidence
        string status
        string location
        datetime detected_at
        datetime reviewed_at
        datetime resolved_at
    }
    ALERT_ACTIONS {
        uuid id PK
        uuid alert_id FK
        uuid user_id FK
        string action_type
        string notes
        datetime created_at
    }
    DEVICE_STATUS {
        uuid id PK
        uuid vehicle_id FK
        string microphone_status
        string gps_status
        string engine_status
        string monitoring_mode
        bool audio_capture_enabled
        bool recording
        int battery_level
        datetime online_since
        datetime last_sync_at
    }
    DEVICES {
        uuid id PK
        uuid vehicle_id FK
        uuid owner_id FK
        string hardware_id UK
        string name
        string firmware_version
        json configuration
        string state
        datetime last_heartbeat_at
        datetime retired_at
        datetime removed_at
    }
```

Deleting a vehicle removes its assignments, audio records, alerts, alert actions and device
status (explicit deletes plus `ON DELETE CASCADE`). Its registered devices are first detached and
retired so inventory/audit history survives. MongoDB history is intentionally retained.

## MongoDB collections

Vehicles are referenced by `vehicle_code` (not the PostgreSQL UUID) so documents stay readable
and devices can write without a lookup. Timestamps are stored as UTC datetimes.

| Collection | Document |
| --- | --- |
| `telemetry_events` | `vehicle_id`, `timestamp`, `location{latitude, longitude}`, `speed`, `engine_temperature`, `battery_level`, `gps_status` |
| `audio_analysis_results` | `audio_record_id` (PostgreSQL UUID as string), `vehicle_id`, `model_name`, `model_version`, `predicted_class`, `confidence`, `processing_time_ms`, `created_at` |
| `sensor_events` | `vehicle_id`, `sensor_type`, `value`, `unit`, `timestamp` (derived from each telemetry post) |
| `device_logs` | `vehicle_id`, `event_type`, `message`, `timestamp` |
| `device_heartbeats` | `heartbeat_id`, `device_id` (PostgreSQL UUID as string), `vehicle_id` (vehicle code), `health`, `reported_at`, `received_at`, flexible `metrics` |

## Indexing strategy

| Store | Index | Serves |
| --- | --- | --- |
| PG | `users.email` (unique) | login / duplicate check |
| PG | `vehicles.vehicle_code` (unique) | lookup by code |
| PG | `alerts.vehicle_id`, `alerts.status`, `alerts.detected_at` | per-vehicle lists, active-alert counts, newest-first ordering |
| PG | `audio_records.vehicle_id`, `device_status.vehicle_id` (unique) | per-vehicle lookups |
| PG | `devices.hardware_id` (unique), `devices.vehicle_id`, `devices.owner_id` | registration and scoped inventory lookups |
| PG | FK columns on assignments, sessions, actions | access checks, joins |
| Mongo | `telemetry_events.vehicle_id`, `.timestamp` | single-field filters |
| Mongo | `telemetry_events (vehicle_id, timestamp)` | "latest reading" and history range queries |
| Mongo | `audio_analysis_results.vehicle_id`, `.predicted_class` | analytics grouping and filtering |
| Mongo | `sensor_events` / `device_logs (vehicle_id, timestamp)` | history queries |
| Mongo | `device_heartbeats (device_id, received_at)` | newest-first device connectivity history |

Mongo indexes are created idempotently at API startup. For long-running telemetry, consider a TTL
index or time-series collection to bound storage.

## CRUD design

| Resource | Create | Read | Update | Delete |
| --- | --- | --- | --- | --- |
| User | `POST /auth/register` | `GET /auth/me`, `/users/me` | `PATCH /users/me` | – |
| Vehicle | `POST /vehicles` (any user; admin may set owner/assignees) | list (scoped), get | `PATCH` (owner/admin) | `DELETE` (owner/admin) |
| Device | `POST /vehicles/{id}/devices` | per-vehicle list, get, heartbeat history | details, configuration, heartbeat | soft remove / retire |
| Audio | `POST /audio` (runs the workflow) | list, get (+ analysis) | `PATCH /audio/{id}/status` | – |
| Alert | `POST /alerts` (manual) or automatically | list (filter by vehicle/status), get (+ actions, analysis) | `acknowledge`, `resolve` (admin) | – |
| Telemetry | `POST /telemetry/{vehicle}` | history (range + limit), latest | – (append-only) | – |

Access rule everywhere: non-admin users only touch vehicles they own or are assigned to;
anything else returns `404`. Every write commits in one PostgreSQL transaction in the service layer.

Device records are relational because hardware identity, ownership, unique constraints and current
state need transactions. Heartbeats are MongoDB documents because they are append-only,
high-volume, and may carry changing metrics. `device_status` remains the existing vehicle-level
telemetry snapshot; it is not replaced by the per-hardware `devices` table.

## Audio-to-alert data flow

```mermaid
flowchart TD
    A[Client uploads audio file] --> S[(Object storage S3 / MinIO)]
    A -->|metadata + storage URL| B[POST /api/v1/audio]
    B --> C[(PostgreSQL audio_records<br/>status = processing)]
    C --> D[audio_classifier.classify_audio<br/>MOCK - not a trained model]
    D --> E[(MongoDB audio_analysis_results)]
    D --> F{confidence >= 0.80<br/>and class != normal?}
    F -- no --> G[audio_records.status = completed]
    F -- yes --> H[(PostgreSQL alerts<br/>status = open)]
    H --> I[(alert_actions: created)]
    H --> J[Dashboard / Alert Details]
    J --> K{Admin action}
    K -->|acknowledge| L[alerts.status = acknowledged<br/>+ alert_actions row]
    K -->|resolve| M[alerts.status = resolved<br/>+ alert_actions row]
    D -. error .-> X[audio_records.status = failed]
```

Telemetry flow: `POST /telemetry/{vehicle}` → MongoDB `telemetry_events` (+ `sensor_events`) →
PostgreSQL `device_status` and `vehicles.last_seen_at` are refreshed → the Live Map and Car
Monitoring pages read the latest document.

Analytics: `total_events`, `average_confidence`, events-over-time and events-by-type come from
MongoDB `audio_analysis_results`; `critical_events` (severity `high`/`critical`),
`resolution_rate` and `active_alert_count` come from PostgreSQL `alerts`.
