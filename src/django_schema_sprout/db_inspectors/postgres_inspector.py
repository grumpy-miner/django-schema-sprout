from collections import namedtuple


from django.db import models
from django.db.models import Index
from django.db.backends.base.introspection import TableInfo as BaseTableInfo
from django.db.backends.base.introspection import FieldInfo as BaseFieldInfo
from django.db.backends.postgresql.introspection import DatabaseIntrospection
from django.core.management.commands.inspectdb import Command


TableInfo = namedtuple(
    "TableInfo",
    BaseTableInfo._fields
    + (
        "comment",
        "nspname",
    ),
)
FieldInfo = namedtuple("FieldInfo", BaseFieldInfo._fields + ("is_autofield", "comment"))


class PostgresDBInspect(DatabaseIntrospection):
    """
    A class for inspecting the PostgreSQL database schema.

    This class provides methods to retrieve information about tables, relations,
    constraints, primary keys, and table descriptions in a PostgreSQL database.
    """

    def get_table_list(self, cursor):
        """
        Return a list of table and view names in
        the current database in order of dependency.
        """
        cursor.execute(
            """
                with recursive fk_tree as (
                -- All tables not referencing anything else except self references
                SELECT
                    c.oid as reloid,
                    c.relname as table_name,
                    n.nspname as schema_name,
                    CASE
                        WHEN c.relispartition THEN 'p'
                        WHEN c.relkind IN ('m', 'v') THEN 'v'
                        ELSE 't'
                    END AS relcase,
                    obj_description(c.oid, 'pg_class') AS obj_desc,
                    null::text COLLATE "C" as referenced_table_name,
                    null::text COLLATE "C" as referenced_schema_name,
                    1 AS level
                FROM pg_catalog.pg_class c
                LEFT JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
                WHERE c.relkind IN ('f', 'm', 'p', 'r', 'v')
                AND n.nspname NOT IN ('pg_catalog', 'pg_toast')
                AND n.nspname = ANY(current_schemas(false))
                AND NOT EXISTS (
                    SELECT *
                    FROM pg_constraint
                    WHERE contype = 'f'
                    -- self-referencing-check
                    AND conrelid = c.oid AND conrelid != confrelid
                )
                UNION ALL
                SELECT
                    ref.oid,
                    ref.relname,
                    rs.nspname,
                    CASE
                        WHEN ref.relispartition THEN 'p'
                        WHEN ref.relkind IN ('m', 'v') THEN 'v'
                        ELSE 't'
                    END,
                    obj_description(c.oid, 'pg_class'),
                    p.table_name,
                    p.schema_name,
                    p.level + 1
                FROM pg_class ref
                    JOIN pg_namespace rs ON rs.oid = ref.relnamespace
                    JOIN pg_constraint c ON c.contype = 'f' AND c.conrelid = ref.oid
                    JOIN fk_tree p ON p.reloid = c.confrelid
                WHERE ref.relkind IN ('f', 'm', 'p', 'r', 'v')
                -- do not enter to tables referencing themselves.
                AND ref.oid != p.reloid
                )
                SELECT
                    table_name,
                    relcase,
                    obj_desc,
                    schema_name
                FROM fk_tree
                ORDER BY "level" asc, schema_name, table_name;
            """
        )

        return [
            TableInfo(*row)
            for row in cursor.fetchall()
            if row[0] not in self.ignored_tables
        ]

    def get_relations(self, cursor, table_name, nspname):
        """
        Return a dictionary of {field_name: (field_name_other_table, other_table)}
        representing all foreign keys in the given table.
        """
        cursor.execute(
            """
            SELECT a1.attname, c2.relname, a2.attname, n2.nspname
            FROM pg_constraint con
            LEFT JOIN pg_class c1 ON con.conrelid = c1.oid
            LEFT JOIN pg_class c2 ON con.confrelid = c2.oid
            LEFT JOIN
                pg_attribute a1 ON c1.oid = a1.attrelid AND a1.attnum = con.conkey[1]
            LEFT JOIN
                pg_attribute a2 ON c2.oid = a2.attrelid AND a2.attnum = con.confkey[1]
            LEFT JOIN pg_catalog.pg_namespace n1 ON n1.oid = c1.relnamespace
            LEFT JOIN pg_catalog.pg_namespace n2 ON n2.oid = c2.relnamespace
            WHERE
                c1.relname = %s AND
                con.contype = 'f' AND
                c1.relnamespace = c2.relnamespace AND
                n1.nspname = ANY(current_schemas(false)) AND
                n1.nspname = %s
        """,
            [table_name, nspname],
        )
        return {row[0]: (row[2], row[1], row[3]) for row in cursor.fetchall()}

    def get_constraints(self, cursor, table_name, nspname):
        """
        Retrieve any constraints or keys (unique, pk, fk, check, index) across
        one or more column in given namespace.
        Also retrieve the definition of expression-based indexes.
        """
        constraints = {}
        # Loop over the key table, collecting things as constraints. The column
        # array must return column names in the same order in which they were
        # created.
        cursor.execute(
            """
            SELECT
                c.conname,
                array(
                    SELECT attname
                    FROM unnest(c.conkey) WITH ORDINALITY cols(colid, arridx)
                    JOIN pg_attribute AS ca ON cols.colid = ca.attnum
                    WHERE ca.attrelid = c.conrelid
                    ORDER BY cols.arridx
                ),
                c.contype,
                (SELECT fkc.relname || '.' || fka.attname
                FROM pg_attribute AS fka
                JOIN pg_class AS fkc ON fka.attrelid = fkc.oid
                WHERE fka.attrelid = c.confrelid AND fka.attnum = c.confkey[1]),
                cl.reloptions
            FROM pg_constraint AS c
            JOIN pg_class AS cl ON c.conrelid = cl.oid
            LEFT JOIN pg_catalog.pg_namespace n ON n.oid = cl.relnamespace
            WHERE cl.relname = %s
            AND n.nspname = ANY(current_schemas(false))
            AND n.nspname = %s
        """,
            [table_name, nspname],
        )
        for constraint, columns, kind, used_cols, options in cursor.fetchall():
            constraints[constraint] = {
                "columns": columns,
                "primary_key": kind == "p",
                "unique": kind in ["p", "u"],
                "foreign_key": tuple(used_cols.split(".", 1)) if kind == "f" else None,
                "check": kind == "c",
                "index": False,
                "definition": None,
                "options": options,
            }
        # Now get indexes
        cursor.execute(
            """
            SELECT
                indexname,
                array_agg(attname ORDER BY arridx),
                indisunique,
                indisprimary,
                array_agg(ordering ORDER BY arridx),
                amname,
                exprdef,
                s2.attoptions
            FROM (
                SELECT
                    c2.relname as indexname, idx.*, attr.attname, am.amname,
                    CASE
                        WHEN idx.indexprs IS NOT NULL THEN
                            pg_get_indexdef(idx.indexrelid)
                    END AS exprdef,
                    CASE am.amname
                        WHEN %s THEN
                            CASE (option & 1)
                                WHEN 1 THEN 'DESC' ELSE 'ASC'
                            END
                    END as ordering,
                    c2.reloptions as attoptions
                FROM (
                    SELECT *
                    FROM
                        pg_index i,
                        unnest(i.indkey, i.indoption)
                            WITH ORDINALITY koi(key, option, arridx)
                ) idx
                LEFT JOIN pg_class c ON idx.indrelid = c.oid
                LEFT JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
                LEFT JOIN pg_class c2 ON idx.indexrelid = c2.oid
                LEFT JOIN pg_am am ON c2.relam = am.oid
                LEFT JOIN
                    pg_attribute attr ON attr.attrelid = c.oid AND attr.attnum = idx.key
                WHERE c.relname = %s
                AND n.nspname = ANY(current_schemas(false))
                AND n.nspname = %s
            ) s2
            GROUP BY indexname, indisunique, indisprimary, amname, exprdef, attoptions;
        """,
            [self.index_default_access_method, table_name, nspname],
        )
        for (
            index,
            columns,
            unique,
            primary,
            orders,
            type_,
            definition,
            options,
        ) in cursor.fetchall():
            if index not in constraints:
                basic_index = (
                    type_ == self.index_default_access_method
                    and
                    # '_btree' references
                    # django.contrib.postgres.indexes.BTreeIndex.suffix.
                    not index.endswith("_btree")
                    and options is None
                )
                constraints[index] = {
                    "columns": columns if columns != [None] else [],
                    "orders": orders if orders != [None] else [],
                    "primary_key": primary,
                    "unique": unique,
                    "foreign_key": None,
                    "check": False,
                    "index": True,
                    "type": Index.suffix if basic_index else type_,
                    "definition": definition,
                    "options": options,
                }
        return constraints

    def get_primary_key_column(self, cursor, table_name, nspname):
        """
        Return the name of the primary key column for the given table.
        """
        columns = self.get_primary_key_columns(cursor, table_name, nspname)
        return columns[0] if columns else None

    def get_primary_key_columns(self, cursor, table_name, nspname):
        """Return a list of primary key columns for the given table."""
        for constraint in self.get_constraints(cursor, table_name, nspname).values():
            if constraint["primary_key"]:
                return constraint["columns"]
        return None

    def get_table_description(self, cursor, table_name, nspname):
        """
        Return a description of the table with the DB-API cursor.description
        interface.
        """
        # Query the pg_catalog tables as cursor.description does not reliably
        # return the nullable property and information_schema.columns does not
        # contain details of materialized views.
        cursor.execute(
            """
            SELECT
                a.attname AS column_name,
                NOT (a.attnotnull OR (t.typtype = 'd' AND t.typnotnull)) AS is_nullable,
                pg_get_expr(ad.adbin, ad.adrelid) AS column_default,
                CASE WHEN collname = 'default' THEN NULL ELSE collname END AS collation,
                a.attidentity != '' AS is_autofield,
                col_description(a.attrelid, a.attnum) AS column_comment
            FROM pg_attribute a
            LEFT JOIN pg_attrdef ad ON a.attrelid = ad.adrelid AND a.attnum = ad.adnum
            LEFT JOIN pg_collation co ON a.attcollation = co.oid
            JOIN pg_type t ON a.atttypid = t.oid
            JOIN pg_class c ON a.attrelid = c.oid
            JOIN pg_namespace n ON c.relnamespace = n.oid
            WHERE c.relkind IN ('f', 'm', 'p', 'r', 'v')
                AND c.relname = %s
                AND n.nspname NOT IN ('pg_catalog', 'pg_toast')
                AND n.nspname = ANY(current_schemas(false))
                AND n.nspname = %s
        """,
            [table_name, nspname],
        )
        field_map = {line[0]: line[1:] for line in cursor.fetchall()}

        _quote_name = self.connection.ops.quote_name
        cursor.execute(
            "SELECT * FROM %s LIMIT 1"
            % f"{_quote_name(nspname)}.{_quote_name(table_name)}"
        )
        return [
            FieldInfo(
                line.name,
                line.type_code,
                # display_size is always None on psycopg2.
                line.internal_size if line.display_size is None else line.display_size,
                line.internal_size,
                line.precision,
                line.scale,
                *field_map[line.name],
            )
            for line in cursor.description
        ]

    def get_attributes(self, cursor, table_name, nspname):
        attributes = dict()
        relations = self.get_relations(cursor, table_name, nspname)
        constraints = self.get_constraints(cursor, table_name, nspname)

        primary_key_column = self.get_primary_key_column(cursor, table_name, nspname)
        unique_columns = [
            c["columns"][0]
            for c in constraints.values()
            if c["unique"] and len(c["columns"]) == 1
        ]

        table_description = self.get_table_description(cursor, table_name, nspname)

        used_column_names = []
        column_to_field_name = {}

        for row in table_description:
            extra_params = {}
            column_name = row.name
            is_relation = column_name in relations

            att_name, params, notes = self.normalize_col_name(
                column_name, used_column_names, is_relation
            )
            extra_params.update(params)

            used_column_names.append(att_name)
            column_to_field_name[column_name] = column_name

            if primary_key_column is None and unique_columns:
                primary_key_column = unique_columns[0]

            if column_name == primary_key_column:
                extra_params["primary_key"] = True
            elif column_name in unique_columns:
                extra_params["unique"] = True

            if is_relation:
                ref_db_column, ref_db_table, ref_db_nspname = relations[column_name]
                if extra_params.pop("unique", False) or extra_params.get("primary_key"):
                    rel_type = "OneToOneField"

                else:
                    rel_type = "ForeignKey"
                    ref_pk_column = self.get_primary_key_column(
                        cursor, ref_db_table, ref_db_nspname
                    )
                    if ref_pk_column and ref_pk_column != ref_db_column:
                        extra_params["to_field"] = ref_db_column
                if (
                    relations[column_name][1] == table_name
                    and relations[column_name][2] == nspname
                ):
                    field_type, field_params, field_notes = self.get_field_type(row)
                    if (
                        field_type == "CharField"
                        and field_params.get("max_length", -1) < 0
                    ):
                        field_type = "TextField"
                    extra_params.update(field_params)
                    rel_type = field_type

                else:
                    rel_to = f"{relations[column_name][2]}_{relations[column_name][1]}"
                    extra_params["to"] = rel_to
                    extra_params["on_delete"] = models.DO_NOTHING
                field_type = rel_type
            else:
                field_type, field_params, field_notes = self.get_field_type(row)

                if field_type == "CharField" and field_params.get("max_length", -1) < 0:
                    field_type = "TextField"

                extra_params.update(field_params)

            if row.null_ok:
                extra_params["blank"] = True
                extra_params["null"] = True

            if extra_params.get("primary_key"):
                extra_params["blank"] = False
                extra_params["null"] = False
            extra_params["db_column"] = column_name

            field = models.__getattribute__(field_type)
            field = field(**extra_params)
            attributes[column_name] = field

        if "name" in attributes:
            attributes["__str__"] = lambda x: x.__getattribute__("name")

        return attributes

    def normalize_col_name(self, col_name, used_column_names, is_relation):
        return Command.normalize_col_name(
            Command, col_name, used_column_names, is_relation
        )

    def get_field_type(self, row):
        field_params = {}
        field_notes = []

        try:
            field_type = super().get_field_type(row.type_code, row)
        except KeyError:
            field_type = "TextField"
            field_notes.append("This field type is a guess.")

        # Add max_length for all CharFields.
        if field_type == "CharField" and row.display_size:
            if (size := int(row.display_size)) and size > 0:
                field_params["max_length"] = size

        if field_type in {"CharField", "TextField"} and row.collation:
            field_params["db_collation"] = row.collation

        if field_type == "DecimalField":
            if row.precision is None or row.scale is None:
                field_notes.append(
                    "max_digits and decimal_places have been guessed, as this "
                    "database handles decimal fields as float"
                )
                field_params["max_digits"] = (
                    row.precision if row.precision is not None else 10
                )
                field_params["decimal_places"] = (
                    row.scale if row.scale is not None else 5
                )
            else:
                field_params["max_digits"] = row.precision
                field_params["decimal_places"] = row.scale

        return field_type, field_params, field_notes
