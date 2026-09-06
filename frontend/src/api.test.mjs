import assert from "node:assert/strict";

import { normalizeQueryEnvelope, normalizeStation } from "./api.js";

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

assert.deepEqual(
  normalizeStation({
    id: 7,
    code: "ENV-0007",
    name: "Station 7",
    region_id: 2,
    status: "active",
    metadata: {},
    live_status: "warning",
    temperature: 25,
    humidity: 70,
    wind_speed: 2,
    pm25: 80,
    qcvn_thresholds: {
      pm25: { warning_max: 100, critical_max: 120 },
    },
  }).qcvnThresholds,
  {
    pm25: { warning_max: 100, critical_max: 120 },
  },
);
