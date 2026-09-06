import assert from "node:assert/strict";

import {
  defaultStationTimeRange,
  isStationTimeRangeValid,
  preferredStationResolution,
  queryOptimizationNote,
  stationDataQuery,
} from "./stationTimeRange.js";

const range = defaultStationTimeRange();

assert.equal(isStationTimeRangeValid(range), true);
assert.equal(typeof stationDataQuery({ stationId: 8005, ...range }), "object");

assert.equal(
  preferredStationResolution({
    startTime: "2026-09-01T00:00",
    endTime: "2026-09-01T23:59",
  }),
  "1m",
);

assert.equal(
  preferredStationResolution({
    startTime: "2026-09-01T00:00",
    endTime: "2026-09-07T00:00",
  }),
  "1h",
);

assert.equal(
  preferredStationResolution({
    startTime: "2026-01-01T00:00",
    endTime: "2026-06-01T00:00",
  }),
  "1d",
);

assert.equal(
  queryOptimizationNote({
    requested_resolution: "1m",
    effective_resolution: "1h",
    downsampled: false,
    resolution_note: "Switched from 1m to 1h because the selected range is longer than 48 hours.",
  }),
  "Dữ liệu đã được tối ưu: hiển thị 1h thay vì 1m vì khoảng thời gian quá dài.",
);

assert.equal(
  queryOptimizationNote({
    requested_resolution: "1h",
    effective_resolution: "1h",
    max_points: 1000,
    downsampled: true,
    resolution_note: "Returned 1000 representative points from 86342 available points.",
  }),
  "Dữ liệu đã được tối ưu: hiển thị tối đa 1000 điểm đại diện.",
);
