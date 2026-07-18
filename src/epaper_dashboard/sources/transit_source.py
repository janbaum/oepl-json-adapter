from __future__ import annotations

from datetime import datetime
from typing import Any

import requests
from dateutil import parser

from epaper_dashboard.models import DashboardData, Departure, TransitGroup


def load_transit_data(config: dict[str, Any], dashboard: dict[str, Any]) -> DashboardData:
    provider = str(config.get("provider", "rmv_hapi"))
    limit = int(dashboard.get("sections", {}).get("transit", {}).get("max_items", 5))

    if provider == "rmv_hapi":
        return _load_rmv_hapi_data(config, limit)
    if provider == "db_transport_rest":
        return _load_db_transport_rest_data(config, limit)

    raise ValueError(f"Unsupported transit provider: {provider}")


def _load_rmv_hapi_data(config: dict[str, Any], limit: int) -> DashboardData:
    directions = config.get("directions") or []
    if directions:
        return _load_rmv_hapi_groups(config, limit, directions)

    mode = str(config.get("mode", "departure_board"))
    if mode == "departure_board":
        departures = _rmv_departure_board(config, limit)
    elif mode == "trip":
        departures = _rmv_trip_departures(config, limit)
    else:
        raise ValueError(f"Unsupported RMV transit mode: {mode}")

    departures = _filter_departures(departures, config)
    departures.sort(key=lambda item: item.time)
    return DashboardData(calendar=[], tasks=[], departures=departures[:limit], news=[])


def _load_rmv_hapi_groups(config: dict[str, Any], limit: int, directions: list[dict[str, Any]]) -> DashboardData:
    groups = []
    flat_departures = []
    for direction in directions:
        direction_config = {**config, **direction, "directions": []}
        direction_limit = int(direction.get("max_items", direction.get("max_journeys", limit)))
        if "mode" not in direction_config or not direction_config["mode"]:
            direction_config["mode"] = "trip" if direction_config.get("dst_station_id") else "departure_board"

        if direction_config["mode"] == "departure_board":
            departures = _rmv_departure_board(direction_config, direction_limit)
        elif direction_config["mode"] == "trip":
            departures = _rmv_trip_departures(direction_config, direction_limit)
        else:
            raise ValueError(f"Unsupported RMV transit mode: {direction_config['mode']}")

        departures = _filter_departures(departures, direction_config)
        departures.sort(key=lambda item: item.time)
        departures = departures[:direction_limit]
        flat_departures.extend(departures)
        groups.append(
            TransitGroup(
                title=_direction_title(direction_config),
                origin=str(direction_config.get("src_label") or direction_config.get("src_station_id") or ""),
                destination=str(direction_config.get("dst_label") or direction_config.get("dst_station_id") or ""),
                departures=departures,
            )
        )

    flat_departures.sort(key=lambda item: item.time)
    return DashboardData(calendar=[], tasks=[], departures=flat_departures[:limit], news=[], transit_groups=groups)


def _rmv_departure_board(config: dict[str, Any], limit: int) -> list[Departure]:
    src_station_id = str(config.get("src_station_id", "")).strip()
    if not src_station_id:
        raise ValueError("sources.transit.src_station_id must be set for RMV departure_board mode")

    if not bool(config.get("all_departures", True)) and not _has_departure_filter(config):
        raise ValueError(
            "sources.transit.all_departures is false, but no direction/destination/line/product filter is configured"
        )

    params = _rmv_common_params(config)
    params.update(
        {
            "id": src_station_id,
            "maxJourneys": max(limit, int(config.get("max_journeys", limit))),
            "duration": int(config.get("duration_minutes", 60)),
            "rtMode": "REALTIME" if bool(config.get("realtime", True)) else "OFF",
        }
    )

    direction = str(config.get("direction", "")).strip()
    if direction:
        params["direction"] = direction

    data = _rmv_get(config, "departureBoard", params)
    raw_departures = _as_list(data.get("DepartureBoard", {}).get("Departure") or data.get("Departure"))
    return [_parse_rmv_departure(item) for item in raw_departures if isinstance(item, dict)]


def _rmv_trip_departures(config: dict[str, Any], limit: int) -> list[Departure]:
    src_station_id = str(config.get("src_station_id", "")).strip()
    dst_station_id = str(config.get("dst_station_id", "")).strip()
    if not src_station_id or not dst_station_id:
        raise ValueError("sources.transit.src_station_id and dst_station_id must be set for RMV trip mode")

    params = _rmv_common_params(config)
    params.update(
        {
            "originId": src_station_id,
            "destId": dst_station_id,
            "numF": max(limit, int(config.get("max_journeys", limit))),
            "rtMode": "REALTIME" if bool(config.get("realtime", True)) else "OFF",
        }
    )

    data = _rmv_get(config, "trip", params)
    trips = _as_list(data.get("Trip"))
    departures = []
    for trip in trips:
        if isinstance(trip, dict):
            departure = _parse_rmv_trip(trip)
            if departure:
                departures.append(departure)
    return departures


def _rmv_common_params(config: dict[str, Any]) -> dict[str, str | int]:
    access_id = str(config.get("access_id", "")).strip()
    if not access_id:
        raise ValueError("sources.transit.access_id must be set for RMV HAPI")

    return {
        "accessId": access_id,
        "format": "json",
        "lang": str(config.get("language", "de")),
    }


def _rmv_get(config: dict[str, Any], endpoint: str, params: dict[str, str | int]) -> dict[str, Any]:
    base_url = str(config.get("base_url", "https://www.rmv.de/hapi")).rstrip("/")
    response = requests.get(
        f"{base_url}/{endpoint}",
        params=params,
        headers={"User-Agent": "epaper-dashboard/0.1"},
        timeout=int(config.get("timeout_seconds", 20)),
    )
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise ValueError(f"Unexpected RMV HAPI response for {endpoint}")
    return data


def _load_db_transport_rest_data(config: dict[str, Any], limit: int) -> DashboardData:
    station_id = str(config.get("station_id", "")).strip()
    if not station_id:
        raise ValueError("sources.transit.station_id must be set for db_transport_rest")

    base_url = str(config.get("base_url", "https://v6.db.transport.rest")).rstrip("/")
    timeout = int(config.get("timeout_seconds", 20))
    params = _db_transport_rest_params(config, limit)

    response = requests.get(
        f"{base_url}/stops/{station_id}/departures",
        params=params,
        headers={"User-Agent": "epaper-dashboard/0.1"},
        timeout=timeout,
    )
    response.raise_for_status()

    departures = [_parse_db_transport_rest_departure(item) for item in response.json()]
    departures = [item for item in departures if item is not None]
    departures.sort(key=lambda item: item.time)
    return DashboardData(calendar=[], tasks=[], departures=departures[:limit], news=[])


def _db_transport_rest_params(config: dict[str, Any], limit: int) -> dict[str, str | int]:
    params: dict[str, str | int] = {
        "results": limit,
        "duration": int(config.get("duration_minutes", 60)),
        "language": str(config.get("language", "de")),
        "profile": str(config.get("profile", "dbnav")),
    }

    direction = str(config.get("direction", "")).strip()
    if direction:
        params["direction"] = direction

    for key, value in dict(config.get("products", {})).items():
        params[str(key)] = "true" if bool(value) else "false"

    return params


def _parse_db_transport_rest_departure(item: dict[str, Any]) -> Departure | None:
    when = item.get("when") or item.get("plannedWhen")
    if not when:
        return None

    line = item.get("line") or {}
    delay_seconds = item.get("delay") or 0
    delay_minutes = int(round(delay_seconds / 60))

    return Departure(
        line=str(line.get("name") or "?"),
        destination=str(item.get("direction") or "?"),
        time=_parse_time(str(when)),
        delay_minutes=delay_minutes,
        platform=item.get("platform") or item.get("plannedPlatform"),
        cancelled=bool(item.get("cancelled", False)),
    )


def _parse_rmv_departure(item: dict[str, Any]) -> Departure:
    planned = _rmv_datetime(str(item.get("date", "")), str(item.get("time", "")))
    realtime = _rmv_datetime(str(item.get("rtDate", "")), str(item.get("rtTime", ""))) if item.get("rtTime") else None
    when = realtime or planned
    delay_minutes = int(round((when - planned).total_seconds() / 60)) if realtime else 0

    product_name = _rmv_product_name(item)
    line = str(item.get("name") or product_name or "?")

    return Departure(
        line=line,
        destination=str(item.get("direction") or "?"),
        time=when,
        delay_minutes=delay_minutes,
        platform=item.get("rtTrack") or item.get("track"),
        cancelled=_rmv_cancelled(item),
    )


def _parse_rmv_trip(trip: dict[str, Any]) -> Departure | None:
    legs = _as_list((trip.get("LegList") or {}).get("Leg"))
    public_legs = [leg for leg in legs if isinstance(leg, dict) and _rmv_leg_is_public(leg)]
    first_leg = public_legs[0] if public_legs else (legs[0] if legs and isinstance(legs[0], dict) else None)
    if not first_leg:
        return None

    origin = first_leg.get("Origin") or trip.get("Origin") or {}
    destination = trip.get("Destination") or first_leg.get("Destination") or {}
    planned = _rmv_datetime(str(origin.get("date", "")), str(origin.get("time", "")))
    realtime = (
        _rmv_datetime(str(origin.get("rtDate", "")), str(origin.get("rtTime", ""))) if origin.get("rtTime") else None
    )
    when = realtime or planned
    delay_minutes = int(round((when - planned).total_seconds() / 60)) if realtime else 0

    product_name = _rmv_product_name(first_leg)
    line = str(first_leg.get("name") or product_name or "?")

    return Departure(
        line=line,
        destination=str(destination.get("name") or first_leg.get("direction") or "?"),
        time=when,
        delay_minutes=delay_minutes,
        platform=origin.get("rtTrack") or origin.get("track"),
        cancelled=_rmv_cancelled(first_leg),
    )


def _filter_departures(departures: list[Departure], config: dict[str, Any]) -> list[Departure]:
    included_products = _normalized_product_set(config.get("included_products", []))
    excluded_products = _normalized_product_set(config.get("excluded_products", []))
    lines = _normalized_line_set(config.get("lines", []))
    destinations = _normalized_set(config.get("destination_names", []))

    filtered = []
    for departure in departures:
        product = _line_product(departure.line)
        line = _normalize_line(departure.line)
        destination = _normalize(departure.destination)
        if included_products and product not in included_products:
            continue
        if excluded_products and product in excluded_products:
            continue
        if lines and line not in lines:
            continue
        if destinations and destination not in destinations:
            continue
        filtered.append(departure)
    return filtered


def _has_departure_filter(config: dict[str, Any]) -> bool:
    return any(
        [
            str(config.get("direction", "")).strip(),
            config.get("included_products"),
            config.get("lines"),
            config.get("destination_names"),
        ]
    )


def _direction_title(config: dict[str, Any]) -> str:
    if config.get("name"):
        return str(config["name"])

    source = str(config.get("src_label") or config.get("src_station_id") or "?")
    destination = str(config.get("dst_label") or config.get("direction_label") or config.get("dst_station_id") or "")
    return f"{source} -> {destination}" if destination else source


def _rmv_product_name(item: dict[str, Any]) -> str:
    product = item.get("Product") or item.get("product") or {}
    if isinstance(product, dict):
        return str(
            product.get("catOutS")
            or product.get("catOutL")
            or product.get("catIn")
            or product.get("name")
            or item.get("type")
            or ""
        )
    return str(item.get("type") or "")


def _rmv_cancelled(item: dict[str, Any]) -> bool:
    return str(item.get("cancelled") or item.get("isCancelled") or "").lower() in {"true", "1", "yes"}


def _rmv_leg_is_public(leg: dict[str, Any]) -> bool:
    leg_type = str(leg.get("type") or "").upper()
    return leg_type not in {"WALK", "TRSF", "DEVI"}


def _rmv_datetime(date_value: str, time_value: str) -> datetime:
    if not date_value or not time_value:
        raise ValueError("RMV HAPI item is missing date/time")
    return parser.parse(f"{date_value}T{time_value}")


def _line_product(line: str) -> str:
    value = line.strip().upper()
    for prefix in ["ICE", "IC", "EC", "RE", "RB", "S", "U", "BUS", "TRAM", "STR"]:
        if value == prefix or value.startswith(prefix + " ") or value.startswith(prefix):
            return _normalize_product(prefix)
    return _normalize_product(value.split(" ", 1)[0] if value else "")


def _normalized_product_set(values: Any) -> set[str]:
    if values is None:
        return set()
    if isinstance(values, (str, int)):
        values = [values]
    return {_normalize_product(str(value)) for value in values if str(value).strip()}


def _normalized_set(values: Any) -> set[str]:
    if values is None:
        return set()
    if isinstance(values, (str, int)):
        values = [values]
    return {_normalize(str(value)) for value in values if str(value).strip()}


def _normalized_line_set(values: Any) -> set[str]:
    if values is None:
        return set()
    if isinstance(values, (str, int)):
        values = [values]
    return {_normalize_line(str(value)) for value in values if str(value).strip()}


def _normalize(value: str) -> str:
    return value.strip().casefold()


def _normalize_line(value: str) -> str:
    return "".join(char for char in _normalize(value) if char.isalnum())


def _normalize_product(value: str) -> str:
    normalized = _normalize(value).replace("_", "-")
    aliases = {
        "ice": "ice",
        "nationalexpress": "ice",
        "ic": "ic",
        "ec": "ec",
        "national": "ic",
        "re": "re",
        "regionalexpress": "re",
        "rb": "rb",
        "regional": "rb",
        "s": "s",
        "s-bahn": "s",
        "suburban": "s",
        "u": "u-bahn",
        "u-bahn": "u-bahn",
        "subway": "u-bahn",
        "tram": "tram",
        "str": "tram",
        "strassenbahn": "tram",
        "bus": "bus",
        "ferry": "ferry",
        "taxi": "taxi",
    }
    return aliases.get(normalized, normalized)


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _parse_time(value: str) -> datetime:
    parsed = parser.isoparse(value)
    return parsed if parsed.tzinfo else parsed.astimezone()
