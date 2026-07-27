"""No test may call ``db.create_all()`` / ``db.drop_all()``.

The suite runs against the real local development database (see
tests/practices/conftest.py), whose schema Alembic owns. Calling create_all()
there is not merely redundant — it can wedge a developer's migration chain:
run the suite on a fresh checkout before ``flask db upgrade`` and create_all()
materialises every model's table with NO alembic_version bump, after which the
upgrade dies on "relation ... already exists".

That is not hypothetical. Migration ``d8b2c6f4a901`` carries ~350 lines of
fingerprinted orphan recovery precisely because it happened once with
``practice_summary_posts``. The four ``lead_availability_*`` tables added on
this branch have no such recovery, so a repeat means dropping four tables by
hand before the release phase can run.

Seventeen fixtures called create_all() when this guard was written. Removing
every one of them left the suite green, which is the proof that none of them
needed it.

Scoped to the ``db`` object on purpose: creating a genuinely throwaway schema
is fine and the suite does it deliberately elsewhere — see
``tests/scripts/test_seed_practice_plan_reaction_defaults.py`` (a SQLite file
under ``tmp_path``) and ``test_practice_migration_release.py``'s
``release_schema`` fixture.
"""

import ast
import pathlib

_TESTS_DIR = pathlib.Path(__file__).resolve().parent
_FORBIDDEN_METHODS = {"create_all", "drop_all"}


def _test_sources():
    """Every .py under tests/, resolved from THIS file's location.

    Absolute rather than relative: a suite invoked from outside the repo root
    would otherwise raise FileNotFoundError (or silently scan nothing) instead
    of actually checking anything.
    """
    return [
        path for path in sorted(_TESTS_DIR.rglob("*.py"))
        if path.name != pathlib.Path(__file__).name
    ]


def _schema_calls(path):
    """(lineno, source-ish) for every ``db.create_all()``/``db.drop_all()``.

    Parsed, not grepped: the string appears in several docstrings that explain
    this very rule, and a text scan flags those as violations.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return []

    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute) or func.attr not in _FORBIDDEN_METHODS:
            continue
        # Only the app's own session/metadata object. `X.metadata.create_all(engine)`
        # against a throwaway engine is legitimate and stays allowed.
        if isinstance(func.value, ast.Name) and func.value.id == "db":
            found.append((node.lineno, f"db.{func.attr}()"))
    return found


def test_the_scanner_actually_finds_test_files():
    """Positive control.

    Without this, a broken glob or a moved directory would make the guard
    below scan nothing and pass forever while enforcing nothing.
    """
    sources = _test_sources()
    assert len(sources) > 50, (
        f"expected to scan the whole suite, found {len(sources)} files"
    )
    assert "conftest.py" in {path.name for path in sources}


def test_the_scanner_detects_a_planted_call(tmp_path):
    """Second positive control: prove the AST matcher actually matches.

    A guard that never fires is indistinguishable from a guard that cannot.
    """
    planted = tmp_path / "test_planted.py"
    planted.write_text(
        "from app.models import db\n"
        "def test_x():\n"
        "    db.create_all()\n",
        encoding="utf-8",
    )
    assert _schema_calls(planted) == [(3, "db.create_all()")]

    # ...and that the throwaway-engine form stays allowed.
    allowed = tmp_path / "test_allowed.py"
    allowed.write_text(
        "def test_y(engine):\n"
        "    seed.metadata.create_all(engine)\n",
        encoding="utf-8",
    )
    assert _schema_calls(allowed) == []


def test_no_test_file_manages_the_schema():
    offenders = [
        f"{path.relative_to(_TESTS_DIR)}:{lineno}: {call}"
        for path in _test_sources()
        for lineno, call in _schema_calls(path)
    ]
    assert not offenders, (
        "db.create_all()/db.drop_all() are forbidden in tests -- Alembic owns "
        "this schema, and creating tables without an alembic_version bump "
        "wedges the migration chain. Offending lines:\n" + "\n".join(offenders)
    )
