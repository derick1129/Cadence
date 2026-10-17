# Local Development Infrastructure

This directory contains the Docker Compose configuration and service settings for running Cadence's local infrastructure stack.

## Services

| Service | Image | Local Port(s) | Description | Default Credentials |
|---|---|---|---|---|
| `postgres` | `postgres:16-alpine` | `5432` | Relational database (`cadence_dev`) | User: `cadence`, Password: `cadence_password` |
| `redis` | `redis:7-alpine` | `6379` | Cache, pub/sub, concurrency counters | None |
| `minio` | `minio/minio` | `9000` (API), `9001` (Console) | S3-compatible object storage | User: `minioadmin`, Password: `minioadmin_secret` |
| `minio-create-buckets` | `minio/mc` | N/A | One-shot setup job to initialize buckets | Auto-creates `cadence-recordings`, `cadence-knowledge` |
| `livekit` | `livekit/livekit-server:v1.6.0` | `7880` (HTTP/WS), `7881` (TCP RTC), `50000-50020` (UDP RTC) | Real-time WebRTC media server | API Key: `devkey`, Secret: `secret` |

## Usage

### Prerequisites

- [Docker Engine](https://docs.docker.com/engine/) (v24.0+)
- [Docker Compose](https://docs.docker.com/compose/) (v2.20+)

### Start Infrastructure

To start all services in the background:

```bash
docker compose -f deploy/docker-compose.yml up -d
```

### Check Service Health & Status

Verify running containers and their health check status:

```bash
docker compose -f deploy/docker-compose.yml ps
```

To tail logs for all services or a specific service:

```bash
# All services
docker compose -f deploy/docker-compose.yml logs -f

# Specific service (e.g., livekit or postgres)
docker compose -f deploy/docker-compose.yml logs -f livekit
```

### Stop Infrastructure

To stop all services without deleting persistent data:

```bash
docker compose -f deploy/docker-compose.yml down
```

To stop all services and wipe all database/storage volumes:

```bash
docker compose -f deploy/docker-compose.yml down -v
```

## Configuration Files

- `docker-compose.yml`: Compose definition with healthchecks and persistent volumes (`pgdata`, `miniodata`).
- `livekit.yaml`: Development configuration for the LiveKit WebRTC server mounted into the container at `/etc/livekit.yaml`.
