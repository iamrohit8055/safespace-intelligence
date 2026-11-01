# Infrastructure: Docker & Database Services

This directory contains container configurations and documentation for the SafeSpace Intelligence infrastructure.

## PostgreSQL 17 with PostGIS

The database service uses the official `postgis/postgis:17-3.5` Docker image, which bundles PostgreSQL 17 with PostGIS geospatial extensions.

### Service Details

- **Image:** `postgis/postgis:17-3.5`
- **Container Name:** `safespace-postgres`
- **Default Port:** `5432` (mapped to `127.0.0.1:5432` on the host)
- **Persistent Volume:** `safespace_postgres_data`
- **Network:** `safespace_network` (isolated bridge network)

### Common Commands

Start the database in the background:
```bash
docker compose up -d postgres
```

Check service status and health:
```bash
docker compose ps
```

View database logs:
```bash
docker compose logs -f postgres
```

Stop the database:
```bash
docker compose down
```

Stop and remove persistent data (warning: destroys all stored data):
```bash
docker compose down -v
```

Execute SQL directly in the container:
```bash
docker compose exec postgres psql -U safespace_user -d safespace_db -c "SELECT PostGIS_Version();"
```
