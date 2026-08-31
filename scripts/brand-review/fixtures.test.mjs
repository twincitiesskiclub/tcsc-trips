import assert from "node:assert/strict";
import test from "node:test";
import { deriveRegistrationState } from "../../site/src/lib/registrationState.ts";
import { conditionsDisplayMode } from "../../site/src/lib/conditionsDisplayMode.ts";
import { seasonPayload, conditionsPayload } from "./fixture-api.mjs";

const now = Date.now();

test("season fixtures derive the state they are named for, in the browser and at build", () => {
  for (const [state, expected] of [["open", "open"], ["soon", "coming_soon"], ["closed", "closed"]]) {
    const body = seasonPayload(state);
    assert.equal(deriveRegistrationState(body.primary, now), expected, state);
    assert.equal(deriveRegistrationState(body.by_type["fall/winter"], now), expected, state);
    assert.equal(typeof body.generated_at, "string");
  }
});

test("conditions fixtures drive the display modes", () => {
  const august = new Date("2026-08-31T12:00:00-05:00");
  assert.equal(conditionsDisplayMode(conditionsPayload("live"), august), "live");
  assert.equal(conditionsDisplayMode(conditionsPayload("dryland"), august), "off-season");
  assert.equal(conditionsPayload("live").locations.length, 4);
});
