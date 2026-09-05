FROM timescale/timescaledb:latest-pg16

COPY init/001_schema.sql /docker-entrypoint-initdb.d/001_schema.sql
RUN chmod 0644 /docker-entrypoint-initdb.d/001_schema.sql
