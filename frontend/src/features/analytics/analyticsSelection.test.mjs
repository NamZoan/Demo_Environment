import assert from "node:assert/strict";

import { resolveSelectedStationIds } from "./analyticsSelection.js";

const stations = [{ id: 8005 }, { id: 8006 }, { id: 8007 }];

assert.deepEqual(resolveSelectedStationIds(stations, [1, 2]), [8005, 8006]);
assert.deepEqual(resolveSelectedStationIds(stations, [8006]), [8006]);
assert.deepEqual(resolveSelectedStationIds([], [1, 2]), []);
