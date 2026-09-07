export function resolveBackendStations(result, fallbackStations) {
  return result?.source === "backend" ? result.stations : fallbackStations;
}
