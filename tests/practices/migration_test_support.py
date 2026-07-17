from sqlalchemy import text

from app.practices.models import PracticeSummaryPost


def create_exact_summary_orphan(connection):
    """Create only the ORM table in the active test schema."""
    PracticeSummaryPost.__table__.create(connection)


def summary_catalog_snapshot(connection):
    relation = connection.execute(text("""
        SELECT c.oid, n.nspname AS schema_name,
               c.relkind, c.relpersistence, c.relispartition,
               c.relrowsecurity, c.relforcerowsecurity,
               EXISTS (
                 SELECT 1 FROM pg_inherits AS inheritance
                 WHERE inheritance.inhrelid = c.oid
               ) AS has_parent
        FROM pg_class AS c
        JOIN pg_namespace AS n ON n.oid = c.relnamespace
        WHERE n.nspname = current_schema()
          AND c.relname = 'practice_summary_posts'
    """)).mappings().one_or_none()
    if relation is None:
        return None
    oid = relation["oid"]
    columns = connection.execute(text("""
        SELECT a.attnum, a.attname,
               format_type(a.atttypid, a.atttypmod) AS sql_type,
               a.attnotnull, a.attidentity, a.attgenerated,
               pg_get_expr(d.adbin, d.adrelid) AS default_expr
        FROM pg_attribute AS a
        LEFT JOIN pg_attrdef AS d
          ON d.adrelid = a.attrelid AND d.adnum = a.attnum
        WHERE a.attrelid = :oid
          AND a.attnum > 0
          AND NOT a.attisdropped
        ORDER BY a.attnum
    """), {"oid": oid}).all()
    constraints = connection.execute(text("""
        SELECT con.conname, con.contype,
               coalesce(
                 array_agg(a.attname ORDER BY key.ord)
                   FILTER (WHERE a.attname IS NOT NULL),
                 ARRAY[]::name[]
               ) AS columns,
               pg_get_constraintdef(con.oid, true) AS definition,
               con.conislocal, con.coninhcount, con.connoinherit
        FROM pg_constraint AS con
        LEFT JOIN LATERAL
          unnest(con.conkey) WITH ORDINALITY AS key(attnum, ord) ON true
        LEFT JOIN pg_attribute AS a
          ON a.attrelid = con.conrelid AND a.attnum = key.attnum
        WHERE con.conrelid = :oid
          AND con.contype IN ('c', 'n', 'p', 'u', 'f', 'x')
        GROUP BY con.oid, con.conname, con.contype
        ORDER BY con.conname
    """), {"oid": oid}).all()
    indexes = connection.execute(text("""
        SELECT idx.relname, ind.indisprimary, ind.indisunique,
               ind.indisvalid, ind.indisready,
               am.amname, ind.indnkeyatts, ind.indnatts,
               array_agg(a.attname ORDER BY key.ord) AS columns,
               pg_get_expr(ind.indpred, ind.indrelid) AS predicate,
               pg_get_expr(ind.indexprs, ind.indrelid) AS expressions
        FROM pg_index AS ind
        JOIN pg_class AS idx ON idx.oid = ind.indexrelid
        JOIN pg_am AS am ON am.oid = idx.relam
        JOIN LATERAL
          unnest(ind.indkey::smallint[]) WITH ORDINALITY
          AS key(attnum, ord) ON true
        LEFT JOIN pg_attribute AS a
          ON a.attrelid = ind.indrelid AND a.attnum = key.attnum
        WHERE ind.indrelid = :oid
        GROUP BY idx.relname, ind.indisprimary, ind.indisunique,
                 ind.indisvalid, ind.indisready,
                 am.amname, ind.indnkeyatts, ind.indnatts,
                 ind.indpred, ind.indexprs, ind.indrelid
        ORDER BY idx.relname
    """), {"oid": oid}).all()
    sequence = connection.execute(text("""
        SELECT seq_ns.nspname, seq.relname,
               ownership.classid::regclass::text,
               ownership.objsubid,
               ownership.refclassid::regclass::text,
               ownership.refobjsubid,
               ownership.deptype,
               default_dep.classid::regclass::text,
               default_dep.objsubid,
               default_dep.refclassid::regclass::text,
               default_dep.refobjsubid,
               default_dep.deptype
        FROM pg_class AS table_rel
        JOIN pg_attribute AS id_column
          ON id_column.attrelid = table_rel.oid
         AND id_column.attname = 'id'
        JOIN pg_attrdef AS id_default
          ON id_default.adrelid = table_rel.oid
         AND id_default.adnum = id_column.attnum
        JOIN pg_depend AS ownership
          ON ownership.refobjid = table_rel.oid
         AND ownership.refobjsubid = id_column.attnum
        JOIN pg_class AS seq
          ON seq.oid = ownership.objid AND seq.relkind = 'S'
        JOIN pg_namespace AS seq_ns ON seq_ns.oid = seq.relnamespace
        JOIN pg_depend AS default_dep
          ON default_dep.objid = id_default.oid
         AND default_dep.refobjid = seq.oid
        WHERE table_rel.oid = :oid
        ORDER BY seq_ns.nspname, seq.relname,
                 ownership.classid, ownership.objsubid,
                 ownership.refclassid, ownership.refobjsubid,
                 ownership.deptype,
                 default_dep.classid, default_dep.objsubid,
                 default_dep.refclassid, default_dep.refobjsubid,
                 default_dep.deptype
    """), {"oid": oid}).all()
    quote = connection.dialect.identifier_preparer.quote
    qualified = (
        f"{quote(relation['schema_name'])}."
        f"{quote('practice_summary_posts')}"
    )
    row_count = connection.exec_driver_sql(
        f"SELECT count(*) FROM {qualified}"
    ).scalar_one()
    return {
        "relation": tuple(relation[key] for key in (
            "relkind", "relpersistence", "relispartition", "has_parent",
            "relrowsecurity", "relforcerowsecurity",
        )),
        "columns": [tuple(row) for row in columns],
        "constraints": [
            (
                row[0], row[1], tuple(row[2]), " ".join(row[3].split()),
                row[4], row[5], row[6],
            )
            for row in constraints
        ],
        "indexes": [
            (*tuple(row[:8]), tuple(row[8]), row[9], row[10])
            for row in indexes
        ],
        "sequence": [tuple(row) for row in sequence],
        "row_count": row_count,
    }
