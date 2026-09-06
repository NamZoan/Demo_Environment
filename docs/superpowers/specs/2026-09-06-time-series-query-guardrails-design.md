# Time-Series Query Guardrails Design

## Goal

Make large time-series ranges usable in the current monitoring UI without changing the ingestion model or deleting existing data. The first implementation slice protects chart and analytics APIs from returning excessive raw points, routes long ranges to coarser Timescale data, and tells the frontend which resolution was actually used.

## Current State

The system stores telemetry in TimescaleDB table `sensor_data` and defines continuous aggregates `sensor_data_hourly` and `sensor_data_daily`. Station detail, analytics series, analytics scatter, and export endpoints all read time-series data. Station detail currently accepts `resolution=1m|1h|1d`, but the hourly and daily station query paths still aggregate raw `sensor_data` at request time. The frontend lets a user choose a resolution and time range, then renders every returned point in Recharts and the detail table.

The existing export endpoints are intentionally allowed to return larger datasets. This design does not apply chart downsampling to export endpoints.

## Scope

This feature covers interactive query paths only:

- `GET /api/stations/{station_id}/data`
- `GET /api/analytics/series`
- `GET /api/analytics/scatter`

This feature does not cover MQTT ingestion, ML anomaly detection, retention policies, compression policies, or multi-tenant row-level security. Those remain separate architectural slices.

## Resolution Policy

Backend APIs accept the existing `resolution` query parameter and a new optional `max_points` parameter.

Default `max_points` is `1000`. Valid range is `100` to `5000`.

The backend computes the requested time span and selects an effective resolution:

- `1m` is allowed when the requested span is at most `48 hours`.
- `1h` is allowed when the requested span is at most `90 days`.
- `1d` is used for spans longer than `90 days`.
- If a request asks for `1m` over more than `48 hours`, the backend upgrades it to `1h`.
- If a request asks for `1h` over more than `90 days`, the backend upgrades it to `1d`.
- If a request asks for `1d`, it remains `1d`.

The response includes metadata so the UI can explain what happened:

```json
{
  "requested_resolution": "1m",
  "effective_resolution": "1h",
  "max_points": 1000,
  "returned_points": 168,
  "downsampled": false,
  "resolution_note": "Switched from 1m to 1h because the selected range is longer than 48 hours."
}
```

## API Response Shape

Station data changes from a bare array to an envelope:

```json
{
  "meta": {
    "requested_resolution": "1m",
    "effective_resolution": "1h",
    "max_points": 1000,
    "returned_points": 168,
    "downsampled": false,
    "resolution_note": "Switched from 1m to 1h because the selected range is longer than 48 hours."
  },
  "points": [
    {
      "time": "2026-09-06T07:00:00Z",
      "temperature": 30.4,
      "humidity": 72.0,
      "wind_speed": 2.1,
      "pm25": 41.2,
      "samples": 60,
      "valid_hours": null
    }
  ]
}
```

For backwards compatibility during the frontend migration, the backend repository function can return the envelope while the route owns the final response model. The frontend must read `points`; no frontend code should assume station data is a bare array after this change.

Analytics series and scatter use the same `meta` fields. Series returns its existing `series` rows under a `points` key. Scatter returns its existing point rows under a `points` key.

## Query Sources

Backend station and analytics query code must use the appropriate Timescale source for the effective resolution:

- `1m`: `sensor_data`
- `1h`: `sensor_data_hourly`
- `1d`: `sensor_data_daily`

Hourly and daily interactive queries should not compute `time_bucket(...)` from raw `sensor_data` at request time when the continuous aggregate already exists. This keeps long-range chart queries bounded.

## Downsampling Policy

After selecting the effective resolution, the backend estimates or counts the number of candidate points for the selected station set and time range. If the candidate count is above `max_points`, the backend applies deterministic bucket downsampling.

For station detail, downsampling groups by evenly sized time buckets over the requested interval and returns average metric values per bucket. The bucket size is derived from:

```text
ceil(total_candidate_points / max_points) * effective_resolution_duration
```

For analytics series with multiple stations, the `max_points` budget applies per returned chart series, not globally across all stations. This prevents one station from hiding another station's trend.

For scatter, downsampling keeps paired `x_metric` and `y_metric` values from the same bucket. It must not independently downsample each axis.

Every downsampled response sets `meta.downsampled = true` and includes a `resolution_note` such as:

```text
Returned 1000 representative points from 86342 available points.
```

## Frontend Behavior

Station detail and analytics views read `response.points` and `response.meta`.

The UI displays a small status line near the time range controls when the backend changes resolution or downsampling is applied. Example Vietnamese copy:

```text
Dữ liệu đã được tối ưu: hiển thị trung bình giờ thay vì giá trị phút vì khoảng thời gian quá dài.
```

The chart renders only `response.points`. The detail table also uses `response.points` for now. Full raw export remains available through the export endpoint, so the table should not try to fetch all raw rows for long ranges in this slice.

## Error Handling

APIs return `400` when:

- `start_time` is after `end_time`.
- `max_points` is outside `100..5000`.
- The requested time range is longer than `5 years`.

The `5 years` hard cap prevents accidental unbounded queries from the interactive UI. Export endpoints keep their existing export-specific validation.

Permission failures and missing station failures keep the current behavior.

## Testing

Backend tests cover:

- `1m` over `24 hours` remains `1m`.
- `1m` over `7 days` becomes `1h`.
- `1h` over `120 days` becomes `1d`.
- `max_points` below `100` or above `5000` returns validation error.
- Station data response includes `meta` and `points`.
- Hourly station data uses `sensor_data_hourly`.
- Daily station data uses `sensor_data_daily`.
- Downsampling returns no more than `max_points` for station detail.

Frontend tests cover:

- API client normalizes the station data envelope.
- Station time range helper can choose a preferred resolution for common ranges.
- Station detail renders the backend optimization note when provided.

Existing export tests continue to prove export behavior is not changed.

## Rollout

The implementation should land in this order:

1. Add backend policy helpers and tests.
2. Change station data route and repository to return the envelope.
3. Update frontend API client and station detail to consume the envelope.
4. Apply the same policy to analytics series and scatter.
5. Rebuild and redeploy Docker stack.

The first deploy is compatible with existing stored data. No migration that deletes or rewrites telemetry is required.
