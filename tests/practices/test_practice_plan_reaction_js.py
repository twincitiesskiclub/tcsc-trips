import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

from app.practices.plan_reactions import (
    PlanReactionValidationError,
    build_plan_reaction_catalog,
    resolve_plan_reaction_defaults,
)


ROOT = Path(__file__).resolve().parents[2]


def test_admin_practice_reaction_javascript_suite():
    result = subprocess.run(
        ["npm", "run", "test:practice-reactions"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_javascript_source_order_matches_python_casefold_order():
    scenarios = [
        ["Zebra", "alpha", "Alpha"],
        ["Ábc", "Zebra"],
        ["Zebra", "Straße", "STRASSE", "Kelvin"],
    ]
    payload = []
    for names in scenarios:
        sources = [
            SimpleNamespace(
                id=index,
                name=name,
                default_plan_reactions=[{
                    "emoji": f"option_{index}",
                    "label": f"Option {index}",
                }],
            )
            for index, name in enumerate(names, start=1)
        ]
        payload.append({
            "sources": [
                {
                    "id": source.id,
                    "name": source.name,
                    "plan_reaction_sort_key": source.name.casefold(),
                    "default_plan_reactions": source.default_plan_reactions,
                }
                for source in sources
            ],
            "expected_resolution": resolve_plan_reaction_defaults(
                sources, []
            ).snapshot,
            "expected_catalog": [
                {"emoji": option.emoji, "label": option.label}
                for option in build_plan_reaction_catalog(sources, [])
            ],
        })
    script = """
const Model = require('./app/static/practice_plan_reactions.js');
let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => { input += chunk; });
process.stdin.on('end', () => {
  const scenarios = JSON.parse(input);
  const actual = scenarios.map(({sources}) => ({
    resolution: Model.resolve(sources, []).rows.map(({emoji, label}) => ({
      emoji, label,
    })),
    catalog: Model.buildCatalog(sources, []).map(({emoji, label}) => ({
      emoji, label,
    })),
  }));
  process.stdout.write(JSON.stringify(actual));
});
"""

    result = subprocess.run(
        ["node", "-e", script],
        cwd=ROOT,
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        timeout=10,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    actual = json.loads(result.stdout)
    assert len(actual) == len(payload)
    for observed, expected in zip(actual, payload, strict=True):
        assert observed["resolution"] == expected["expected_resolution"]
        assert observed["catalog"] == expected["expected_catalog"]


def test_javascript_source_and_conflict_errors_match_python():
    scenarios = [
        {
            "types": [{
                "id": "10",
                "name": "String id",
                "plan_reaction_sort_key": "string id",
                "default_plan_reactions": [],
            }],
            "activities": [],
        },
        {
            "types": [],
            "activities": [{
                "id": 1,
                "name": None,
                "plan_reaction_sort_key": "",
                "default_plan_reactions": [],
            }],
        },
        {
            "types": [
                {
                    "id": 1,
                    "name": "Alpha",
                    "plan_reaction_sort_key": "alpha",
                    "default_plan_reactions": [{
                        "emoji": "snowflake",
                        "label": "Snow",
                    }],
                },
                {
                    "id": 2,
                    "name": "Beta",
                    "plan_reaction_sort_key": "beta",
                    "default_plan_reactions": [{
                        "emoji": "snowflake",
                        "label": "Different snow",
                    }],
                },
            ],
            "activities": [],
        },
    ]

    def python_error(callback):
        try:
            callback()
        except PlanReactionValidationError as error:
            return str(error)
        return None

    expected = []
    for scenario in scenarios:
        types = [SimpleNamespace(**item) for item in scenario["types"]]
        activities = [
            SimpleNamespace(**item) for item in scenario["activities"]
        ]
        expected.append({
            "resolve": python_error(
                lambda: resolve_plan_reaction_defaults(types, activities)
            ),
            "catalog": python_error(
                lambda: build_plan_reaction_catalog(types, activities)
            ),
        })

    script = """
const Model = require('./app/static/practice_plan_reactions.js');
let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => { input += chunk; });
process.stdin.on('end', () => {
  function errorFrom(callback) {
    try {
      const result = callback();
      return result && result.error ? result.error : null;
    } catch (error) {
      return error.message;
    }
  }
  const actual = JSON.parse(input).map(({types, activities}) => ({
    resolve: errorFrom(() => Model.resolve(types, activities)),
    catalog: errorFrom(() => Model.buildCatalog(types, activities)),
  }));
  process.stdout.write(JSON.stringify(actual));
});
"""
    result = subprocess.run(
        ["node", "-e", script],
        cwd=ROOT,
        input=json.dumps(scenarios),
        text=True,
        capture_output=True,
        timeout=10,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout) == expected
