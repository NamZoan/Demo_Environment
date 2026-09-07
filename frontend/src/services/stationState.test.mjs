import assert from "node:assert/strict";
import { removeStationById, resolveBackendStations } from "./stationState.js";

assert.deepEqual(
  removeStationById([{ id: 7 }, { id: 8 }], "7"),
  [{ id: 8 }],
  "deleting a station must remove it when the UI and API use different ID types",
);

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
