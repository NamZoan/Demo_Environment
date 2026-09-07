import assert from "node:assert/strict";

import { stationTableRows } from "./stationDataTable.js";

const rows = stationTableRows([
  {
    time: "2026-09-07T10:00:00Z",
    temperature: 31.2,
    humidity: 70.5,
    wind_speed: 2.4,
    pm25: 18.1,
  },
]);

assert.deepEqual(rows, [
  {
    time: "2026-09-07T10:00:00Z",
    temperature: 31.2,
    humidity: 70.5,
    windSpeed: 2.4,
    pm25: 18.1,
  },
]);

console.log("station data table tests passed");
