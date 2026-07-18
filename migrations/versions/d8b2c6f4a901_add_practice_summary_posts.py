"""add practice summary posts

Revision ID: d8b2c6f4a901
Revises: c4f1a8e2d9b7
Create Date: 2026-07-16
"""

from alembic import op
import sqlalchemy as sa

revision = "d8b2c6f4a901"
down_revision = "c4f1a8e2d9b7"
branch_labels = None
depends_on = None

SUMMARY_TABLE = "practice_summary_posts"
_EXPECTED_ID_DEFAULT = (
    "nextval('practice_summary_posts_id_seq'::regclass)"
)

_EXPECTED_COLUMN_SHAPE = (
    (1, "id", "integer", True, "", ""),
    (2, "week_start", "date", True, "", ""),
    (3, "surface", "character varying(32)", True, "", ""),
    (4, "channel_id", "character varying(50)", False, "", ""),
    (5, "message_ts", "character varying(50)", True, "", ""),
    (6, "created_at", "timestamp without time zone", True, "", ""),
    (7, "updated_at", "timestamp without time zone", True, "", ""),
)

_EXPECTED_CONSTRAINTS = (
    (
        "ck_practice_summary_post_surface",
        "c",
        ("surface",),
        "CHECK (surface::text = ANY (ARRAY['coach_summary'::character "
        "varying, 'weekly_summary'::character varying]::text[]))",
    ),
    (
        "practice_summary_posts_pkey",
        "p",
        ("id",),
        "PRIMARY KEY (id)",
    ),
    (
        "uq_practice_summary_post_week_surface",
        "u",
        ("week_start", "surface"),
        "UNIQUE (week_start, surface)",
    ),
)

_EXPECTED_INDEXES = (
    (
        "practice_summary_posts_pkey", True, True, True, True,
        "btree", 1, 1,
        ("id",), None, None,
    ),
    (
        "uq_practice_summary_post_week_surface", False, True, True, True,
        "btree", 2, 2,
        ("week_start", "surface"), None, None,
    ),
)


def _refuse_orphan_recovery(invariant):
    raise RuntimeError(
        "practice_summary_posts orphan recovery refused: " + invariant
    )


def _visible_summary_relation(bind):
    row = bind.execute(sa.text("""
        SELECT c.oid, n.nspname AS schema_name, c.relkind,
               c.relpersistence, c.relispartition,
               c.relrowsecurity, c.relforcerowsecurity,
               EXISTS (
                 SELECT 1 FROM pg_inherits AS inheritance
                 WHERE inheritance.inhrelid = c.oid
               ) AS has_parent
        FROM pg_class AS c
        JOIN pg_namespace AS n ON n.oid = c.relnamespace
        WHERE n.nspname = current_schema()
          AND c.relname = :table_name
    """), {"table_name": SUMMARY_TABLE}).mappings().one_or_none()
    return dict(row) if row is not None else None


def _visible_summary_table_oid(bind):
    relation = _visible_summary_relation(bind)
    return None if relation is None else relation["oid"]


def _qualified_summary_table(bind, schema_name):
    quote = bind.dialect.identifier_preparer.quote
    return f"{quote(schema_name)}.{quote(SUMMARY_TABLE)}"


def _lock_existing_summary_table(bind, relation_oid):
    relation = _visible_summary_relation(bind)
    if relation is None or relation["oid"] != relation_oid:
        _refuse_orphan_recovery("relation changed before lock")
    qualified = _qualified_summary_table(
        bind,
        relation["schema_name"],
    )
    try:
        bind.exec_driver_sql(
            f"LOCK TABLE {qualified} IN ACCESS EXCLUSIVE MODE"
        )
    except sa.exc.DBAPIError as error:
        raise RuntimeError(
            "practice_summary_posts orphan recovery refused: "
            "relation could not be locked"
        ) from error
    locked = _visible_summary_relation(bind)
    if locked is None or locked["oid"] != relation_oid:
        _refuse_orphan_recovery("relation changed while acquiring lock")
    return relation_oid


def _summary_table_fingerprint(bind, relation_oid):
    relation = _visible_summary_relation(bind)
    if relation is None or relation["oid"] != relation_oid:
        _refuse_orphan_recovery("locked relation is no longer visible")
    columns = bind.execute(sa.text("""
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
    """), {"oid": relation_oid}).all()
    # PostgreSQL 18 also exposes generated NOT NULL constraints as contype
    # "n". attnotnull above is the cross-version semantic fingerprint, so
    # version-generated NOT NULL constraint names are deliberately excluded.
    constraints = bind.execute(sa.text("""
        SELECT con.conname, con.contype,
               coalesce(
                 array_agg(a.attname ORDER BY key.ord)
                   FILTER (WHERE a.attname IS NOT NULL),
                 ARRAY[]::name[]
               ) AS columns,
               pg_get_constraintdef(con.oid, true) AS definition
        FROM pg_constraint AS con
        LEFT JOIN LATERAL
          unnest(con.conkey) WITH ORDINALITY AS key(attnum, ord) ON true
        LEFT JOIN pg_attribute AS a
          ON a.attrelid = con.conrelid AND a.attnum = key.attnum
        WHERE con.conrelid = :oid
          AND con.contype IN ('c', 'p', 'u', 'f', 'x')
        GROUP BY con.oid, con.conname, con.contype
        ORDER BY con.conname
    """), {"oid": relation_oid}).all()
    indexes = bind.execute(sa.text("""
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
    """), {"oid": relation_oid}).all()
    sequence = bind.execute(sa.text("""
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
          ON ownership.classid = 'pg_class'::regclass
         AND ownership.objsubid = 0
         AND ownership.refclassid = 'pg_class'::regclass
         AND ownership.refobjid = table_rel.oid
         AND ownership.refobjsubid = id_column.attnum
         AND ownership.deptype = 'a'
        JOIN pg_class AS seq
          ON seq.oid = ownership.objid AND seq.relkind = 'S'
        JOIN pg_namespace AS seq_ns ON seq_ns.oid = seq.relnamespace
        JOIN pg_depend AS default_dep
          ON default_dep.classid = 'pg_attrdef'::regclass
         AND default_dep.objid = id_default.oid
         AND default_dep.objsubid = 0
         AND default_dep.refclassid = 'pg_class'::regclass
         AND default_dep.refobjid = seq.oid
         AND default_dep.refobjsubid = 0
         AND default_dep.deptype = 'n'
        WHERE table_rel.oid = :oid
        ORDER BY seq_ns.nspname, seq.relname,
                 ownership.classid, ownership.objsubid,
                 ownership.refclassid, ownership.refobjsubid,
                 ownership.deptype,
                 default_dep.classid, default_dep.objsubid,
                 default_dep.refclassid, default_dep.refobjsubid,
                 default_dep.deptype
    """), {"oid": relation_oid}).all()
    has_external_dependencies = bind.execute(sa.text("""
        SELECT EXISTS (
            SELECT 1
            FROM pg_depend AS dependency
            LEFT JOIN pg_constraint AS dependent_constraint
              ON dependency.classid = 'pg_constraint'::regclass
             AND dependent_constraint.oid = dependency.objid
            WHERE dependency.refclassid = 'pg_class'::regclass
              AND dependency.refobjid = :oid
              AND dependency.deptype = 'n'
              AND NOT (
                dependency.classid = 'pg_constraint'::regclass
                AND dependent_constraint.conrelid = :oid
              )
        )
    """), {"oid": relation_oid}).scalar_one()
    attached_behavior = bind.execute(sa.text("""
        SELECT
          (SELECT count(*)
           FROM pg_trigger AS trigger
           WHERE trigger.tgrelid = :oid
             AND NOT trigger.tgisinternal) AS user_trigger_count,
          (SELECT count(*)
           FROM pg_policy AS policy
           WHERE policy.polrelid = :oid) AS policy_count
    """), {"oid": relation_oid}).one()
    publication_membership_count = bind.execute(sa.text("""
        SELECT count(*)
        FROM pg_publication_rel AS publication_relation
        WHERE publication_relation.prrelid = :oid
    """), {"oid": relation_oid}).scalar_one()
    qualified = _qualified_summary_table(bind, relation["schema_name"])
    has_rows = bind.exec_driver_sql(
        f"SELECT EXISTS (SELECT 1 FROM {qualified} LIMIT 1)"
    ).scalar_one()
    return {
        "relation": (
            relation["relkind"], relation["relpersistence"],
            relation["relispartition"], relation["has_parent"],
            relation["relrowsecurity"], relation["relforcerowsecurity"],
        ),
        "schema": relation["schema_name"],
        "columns": [tuple(row) for row in columns],
        "constraints": tuple(
            (row[0], row[1], tuple(row[2]), " ".join(row[3].split()))
            for row in constraints
        ),
        "indexes": tuple(
            (*tuple(row[:8]), tuple(row[8]), row[9], row[10])
            for row in indexes
        ),
        "sequence": [tuple(row) for row in sequence],
        "has_external_dependencies": has_external_dependencies,
        "attached_behavior": tuple(attached_behavior),
        "publication_membership_count": publication_membership_count,
        "has_rows": has_rows,
    }


def _assert_exact_empty_create_all_orphan(bind, relation_oid):
    fingerprint = _summary_table_fingerprint(bind, relation_oid)
    if fingerprint["relation"] != (
        "r", "p", False, False, False, False,
    ):
        _refuse_orphan_recovery("relation metadata mismatch")
    columns = fingerprint["columns"]
    shape = tuple(row[:6] for row in columns)
    if shape != _EXPECTED_COLUMN_SHAPE:
        _refuse_orphan_recovery("column shape mismatch")
    id_default = columns[0][6]
    if id_default != _EXPECTED_ID_DEFAULT:
        _refuse_orphan_recovery("id serial default mismatch")
    if any(row[6] is not None for row in columns[1:]):
        _refuse_orphan_recovery("non-id column default mismatch")
    expected_sequence = [(
        fingerprint["schema"],
        "practice_summary_posts_id_seq",
        "pg_class",
        0,
        "pg_class",
        1,
        "a",
        "pg_attrdef",
        0,
        "pg_class",
        0,
        "n",
    )]
    if fingerprint["sequence"] != expected_sequence:
        _refuse_orphan_recovery("owned serial sequence mismatch")
    if fingerprint["constraints"] != _EXPECTED_CONSTRAINTS:
        _refuse_orphan_recovery("constraint mismatch")
    if fingerprint["indexes"] != _EXPECTED_INDEXES:
        _refuse_orphan_recovery("index mismatch")
    if fingerprint["has_external_dependencies"] is not False:
        _refuse_orphan_recovery("external dependency mismatch")
    if fingerprint["attached_behavior"] != (0, 0):
        _refuse_orphan_recovery("attached behavior mismatch")
    if fingerprint["publication_membership_count"] != 0:
        _refuse_orphan_recovery("publication membership mismatch")
    if fingerprint["has_rows"]:
        _refuse_orphan_recovery("table contains rows")


def _drop_exact_empty_create_all_orphan_if_present(bind):
    relation_oid = _visible_summary_table_oid(bind)
    if relation_oid is None:
        return False
    _lock_existing_summary_table(bind, relation_oid)
    _assert_exact_empty_create_all_orphan(bind, relation_oid)
    locked = _visible_summary_relation(bind)
    if locked is None or locked["oid"] != relation_oid:
        _refuse_orphan_recovery("locked relation is no longer visible")
    op.drop_table(SUMMARY_TABLE, schema=locked["schema_name"])
    return True


def upgrade():
    _drop_exact_empty_create_all_orphan_if_present(op.get_bind())
    op.create_table(
        "practice_summary_posts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("surface", sa.String(32), nullable=False),
        sa.Column("channel_id", sa.String(50)),
        sa.Column("message_ts", sa.String(50), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "week_start", "surface",
            name="uq_practice_summary_post_week_surface",
        ),
        sa.CheckConstraint(
            "surface IN ('coach_summary', 'weekly_summary')",
            name="ck_practice_summary_post_surface",
        ),
    )
    op.execute(sa.text("""
        DO $$
        BEGIN
          IF EXISTS (
            WITH legacy AS (
              SELECT date_trunc('week', date)::date AS week_start,
                     'coach_summary'::text AS surface,
                     slack_coach_summary_ts AS message_ts
              FROM practices WHERE slack_coach_summary_ts IS NOT NULL
              UNION ALL
              SELECT date_trunc('week', date)::date,
                     'weekly_summary'::text,
                     slack_weekly_summary_ts
              FROM practices WHERE slack_weekly_summary_ts IS NOT NULL
            )
            SELECT 1
            FROM (
              SELECT 1
              FROM legacy
              GROUP BY week_start, surface
              HAVING count(DISTINCT message_ts) > 1
              UNION ALL
              SELECT 1
              FROM legacy
              GROUP BY surface, message_ts
              HAVING count(DISTINCT week_start) > 1
            ) AS conflicts
          ) THEN
            RAISE EXCEPTION
              'conflicting legacy practice summary timestamps';
          END IF;
        END $$;
    """))
    op.execute(sa.text("""
        INSERT INTO practice_summary_posts
            (week_start, surface, channel_id, message_ts)
        SELECT date_trunc('week', date)::date,
               'coach_summary', NULL, min(slack_coach_summary_ts)
        FROM practices
        WHERE slack_coach_summary_ts IS NOT NULL
        GROUP BY date_trunc('week', date)::date
        UNION ALL
        SELECT date_trunc('week', date)::date,
               'weekly_summary', NULL, min(slack_weekly_summary_ts)
        FROM practices
        WHERE slack_weekly_summary_ts IS NOT NULL
        GROUP BY date_trunc('week', date)::date
    """))


def downgrade():
    op.drop_table("practice_summary_posts")
