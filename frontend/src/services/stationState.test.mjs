import assert from "node:assert/strict";
import { resolveBackendStations } from "./stationState.js";

assert.deepEqual(
  resolveBackendStations({ source: "backend", stations: [] }, [{ id: "demo" }]),
  [],
  "an empty backend response must replace mock stations",
);

assert.deepEqual(
  resolveBackendStations({ source: "mock", stations: [] }, [{ id: "demo" }]),
  [{ id: "demo" }],
  "a failed backend response may keep mock stations",
);

console.log("station state tests passed");
