import test from "node:test";
import assert from "node:assert/strict";

import { buildBackendHeaders } from "./backend-request.ts";

test("buildBackendHeaders adds the server-only internal token", () => {
    assert.deepEqual(buildBackendHeaders("unit-test-placeholder"), {
        "Content-Type": "application/json",
        "X-Internal-Token": "unit-test-placeholder",
    });
});

test("buildBackendHeaders rejects missing internal token", () => {
    assert.throws(() => buildBackendHeaders(""), /BACKEND_INTERNAL_TOKEN/);
});
