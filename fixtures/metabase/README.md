# Metabase application backup

Run `make dashboard-export` to create `metabase.sql` in this directory.

The `metabase-database` image bundles that file and restores it when the Metabase
application database is created for the first time. Existing application databases are
left unchanged.

The dump contains Metabase application data, including users, settings, questions, and
dashboards. Review it for credentials or other sensitive values before committing it.
