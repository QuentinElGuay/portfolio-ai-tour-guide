FROM postgres:17-alpine

COPY fixtures/metabase/ /backups/
