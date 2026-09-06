import assert from "node:assert/strict";

import { normalizeQueryEnvelope } from "./api.js";

const meta = {
  requested_resolution: "1m",
  effective_resolution: "1h",
  max_points: 1000,
  returned_points: 1,
  downsampled: false,
  resolution_note: "Switched from 1m to 1h because the selected range is longer than 48 hours.",
};

assert.deepEqual(normalizeQueryEnvelope({ meta, points: [{ time: "2026-09-06T00:00:00Z", pm25: 42 }] }), {
  meta,
  points: [{ time: "2026-09-06T00:00:00Z", pm25: 42 }],
});

assert.deepEqual(normalizeQueryEnvelope([{ time: "2026-09-06T00:00:00Z", pm25: 42 }]), {
  meta: null,
  points: [{ time: "2026-09-06T00:00:00Z", pm25: 42 }],
});
