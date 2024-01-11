from django_schema_sprout.db_inspectors import PostgresDBInspect


def get_inspector(connection):
    if connection.vendor == "postgresql":
        return PostgresDBInspect(connection)
    else:
        raise NotImplementedError(f"Database {connection.vendor} not supported")
