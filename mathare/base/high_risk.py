# terrasat/high_risk.py
#
# Flood high-risk flagging, safe-shelter selection, and water-source
# hazard flagging, operating at GRID level (not ward level).
#
# IMPORTANT — data source note: this derives its canonical grid list by
# deduping grid_id + UFN interim-weighted score across the four already-
# confirmed joined tables (PoisJoined, BuildingsJoined, RoadsJoined,
# WaterwaysJoined), rather than querying mathare_with_ufn directly —
# that table's schema was never confirmed via inspectdb. If you later
# confirm mathare_with_ufn's schema and it's a cleaner one-row-per-grid
# source, swap get_all_grids() below to query it directly instead —
# everything downstream (flagging, shelters, water hazards) will keep
# working unchanged since they just consume its output.

import random

from django.core.cache import cache

from .models import BuildingsJoined, PhoneUser, Pofw, PoisJoined, RoadsJoined, WaterwaysJoined

HIGH_RISK_THRESHOLD = 0.13

SAFE_SPACE_FCLASSES = ["school", "community_centre", "public_building", "town_hall", "kindergarten"]

# Confirmed present in pois_joined; used to flag water sources inside
# high-risk grids as a cholera-contamination concern.
WATER_SOURCE_FCLASSES = ["drinking_water", "water_tower"]

MAX_SHELTERS_PER_ALERT = 5
MIN_SHELTERS_PER_ALERT = 3  # if a ward's own safe grids can't supply this many, borrow from other wards' safe grids rather than send an alert with 0-1 shelters


GRID_CACHE_KEY = "terrasat_all_grids_v1"
GRID_CACHE_TTL_SECONDS = 60 * 60 * 24  # 24 hours — data is currently static, so no need to re-run these multi-second queries often. Lower this (or add a manual cache-clear action) once the underlying data starts updating regularly.


def clear_grid_cache():
    """Call this after re-importing/updating any of the joined tables, so the next request recomputes fresh data instead of serving the stale 24h cache."""
    cache.delete(GRID_CACHE_KEY)


def get_all_grids():
    """
    Builds a canonical {grid_id: {"village": ..., "interim_ufn": ...}}
    registry by deduping across the four joined tables that share a
    grid_id + UFN column shape.

    CACHED — this query was measured taking 1-16+ SECONDS PER TABLE
    (confirmed via Postgres logs: pois_joined alone took up to 16.6s),
    and was previously re-run on every single map page load with no
    caching at all. Reloading the page a few times in quick succession
    piled up multiple overlapping multi-second queries simultaneously,
    which is what caused "loads once, then fails" — later requests
    were timing out / queuing behind the earlier ones. Caching this for
    5 minutes fixes that; if you need fresher data sooner, lower
    GRID_CACHE_TTL_SECONDS, or better, add a database index on grid_id
    for pois_joined/buildings_joined/roads_joined/waterways_joined,
    which would speed up the underlying query itself.
    """
    cached = cache.get(GRID_CACHE_KEY)
    if cached is not None:
        return cached

    grids = {}

    sources = [PoisJoined, BuildingsJoined, RoadsJoined, WaterwaysJoined]
    for model in sources:
        rows = (
            model.objects
            .exclude(grid_id__isnull=True)
            .values("grid_id", "mathare_ufn_village", "mathare_ufn_ufn_interim_weighted")
            .distinct()
        )
        for row in rows:
            gid = row["grid_id"]
            if gid not in grids or grids[gid]["interim_ufn"] is None:
                grids[gid] = {
                    "village": row["mathare_ufn_village"],
                    "interim_ufn": row["mathare_ufn_ufn_interim_weighted"],
                }

    cache.set(GRID_CACHE_KEY, grids, GRID_CACHE_TTL_SECONDS)
    return grids


def get_high_risk_grids():
    """Returns {grid_id: {...}} for every grid with interim UFN > threshold. Nulls excluded — a grid with no data is not assumed high-risk."""
    all_grids = get_all_grids()
    return {
        gid: info for gid, info in all_grids.items()
        if info["interim_ufn"] is not None and info["interim_ufn"] > HIGH_RISK_THRESHOLD
    }


def get_safe_grids():
    """Returns {grid_id: {...}} for every grid with interim UFN < threshold. Nulls excluded — unknown risk is not assumed safe."""
    all_grids = get_all_grids()
    return {
        gid: info for gid, info in all_grids.items()
        if info["interim_ufn"] is not None and info["interim_ufn"] < HIGH_RISK_THRESHOLD
    }


def group_grids_by_village():
    """
    {village: {"high_risk": [grid_id, ...], "safe": [grid_id, ...]}}
    Grids with no village or no UFN score are dropped — they can't be
    attributed to a ward for alerting purposes, and null-risk grids are
    neither flagged high-risk nor assumed safe (see get_high_risk_grids
    / get_safe_grids docstrings for the same reasoning).
    """
    all_grids = get_all_grids()
    by_village = {}
    for gid, info in all_grids.items():
        village = info["village"]
        ufn = info["interim_ufn"]
        if not village or ufn is None:
            continue
        by_village.setdefault(village, {"high_risk": [], "safe": []})
        if ufn > HIGH_RISK_THRESHOLD:
            by_village[village]["high_risk"].append(gid)
        elif ufn < HIGH_RISK_THRESHOLD:
            by_village[village]["safe"].append(gid)
    return by_village


def select_safe_shelters(safe_grid_ids, max_count=MAX_SHELTERS_PER_ALERT):
    """
    Picks up to `max_count` safe public spaces at random from the given
    safe grids — schools/community centres/public buildings/town
    halls/kindergartens (pois_joined) plus churches (pofw). Random
    selection is intentional: spreads people across multiple shelters
    rather than funnelling everyone to the single nearest one.
    """
    candidates = []

    poi_shelters = PoisJoined.objects.filter(
        grid_id__in=safe_grid_ids, fclass__in=SAFE_SPACE_FCLASSES
    ).exclude(name__isnull=True).exclude(name__exact="")
    for p in poi_shelters:
        candidates.append({"name": p.name, "type": p.fclass, "grid_id": p.grid_id})

    church_shelters = Pofw.objects.filter(grid_id__in=safe_grid_ids)
    for c in church_shelters:
        # grids with no churches simply contribute nothing here — expected, not an error
        if c.name:
            candidates.append({"name": c.name, "type": c.fclass or "place_of_worship", "grid_id": c.grid_id})

    if len(candidates) <= max_count:
        return candidates
    return random.sample(candidates, max_count)


def get_water_hazards(high_risk_grid_ids):
    """
    Water points/taps sitting inside high-risk grids — flagged for
    inspection, since floodwater intrusion at these points is a
    cholera-contamination risk.
    """
    points = PoisJoined.objects.filter(
        grid_id__in=high_risk_grid_ids, fclass__in=WATER_SOURCE_FCLASSES
    )
    return [
        {"name": p.name or "(unnamed)", "type": p.fclass, "grid_id": p.grid_id}
        for p in points
    ]


def get_affected_users_for_village(village):
    """Registered PhoneUsers in a specific ward/village (name-tolerant match, same pattern used elsewhere in the app)."""
    stripped = village.replace("ward", "").replace("Ward", "").strip()
    return PhoneUser.objects.filter(ward_name__icontains=stripped).distinct()


def build_ward_alert_summaries():
    """
    One summary block PER WARD that actually has high-risk grids —
    each with its own shelters (preferring safe grids inside that same
    ward, falling back to other wards' safe grids only if this ward
    doesn't have enough on its own), its own affected-user list, and
    its own water-hazard COUNT (not a full list — see note below).

    Water hazards: a ward can easily have 100+ flagged water points,
    which is unusable inside an SMS. The count + a standard cholera-
    prevention line goes in the SMS; the full point-by-point list stays
    in this summary for the admin review screen / inspection team only.
    """
    by_village = group_grids_by_village()
    ward_summaries = []

    for village, grids in by_village.items():
        if not grids["high_risk"]:
            continue  # only wards with an actual flagged grid need an alert

        shelters = select_safe_shelters(grids["safe"], max_count=MAX_SHELTERS_PER_ALERT)

        # This ward doesn't have enough of its own safe grids to hit the
        # minimum — borrow candidates from other wards' safe grids so
        # people still get at least MIN_SHELTERS_PER_ALERT options,
        # rather than an alert with one or zero shelters listed.
        if len(shelters) < MIN_SHELTERS_PER_ALERT:
            other_safe_ids = [
                gid for v, g in by_village.items() if v != village for gid in g["safe"]
            ]
            needed = MIN_SHELTERS_PER_ALERT - len(shelters)
            borrowed = select_safe_shelters(other_safe_ids, max_count=needed)
            shelters += borrowed

        water_hazards = get_water_hazards(grids["high_risk"])
        affected_users = get_affected_users_for_village(village)

        ward_summaries.append({
            "village": village,
            "high_risk_grid_count": len(grids["high_risk"]),
            "safe_grid_count": len(grids["safe"]),
            "shelters": shelters,
            "water_hazard_count": len(water_hazards),
            "water_hazards_detail": water_hazards,  # full list — admin/inspection use only, never put in SMS
            "affected_users_count": affected_users.count(),
            "affected_users": [
                {"phone_number": u.phone_number, "ward_name": u.ward_name, "language": u.language}
                for u in affected_users
            ],
        })

    return ward_summaries


def build_high_risk_summary():
    """
    Top-level summary for the admin review screen: overall grid counts
    plus the per-ward breakdown (shelters/water hazards/affected users
    are all ward-specific — see build_ward_alert_summaries). Does NOT
    send anything — that's a separate, explicit approval step.
    """
    high_risk = get_high_risk_grids()
    safe = get_safe_grids()
    ward_summaries = build_ward_alert_summaries()

    return {
        "threshold": HIGH_RISK_THRESHOLD,
        "high_risk_grid_count": len(high_risk),
        "safe_grid_count": len(safe),
        "wards_needing_alert": len(ward_summaries),
        "total_affected_users": sum(w["affected_users_count"] for w in ward_summaries),
        "total_water_hazards": sum(w["water_hazard_count"] for w in ward_summaries),
        "ward_summaries": ward_summaries,
    }