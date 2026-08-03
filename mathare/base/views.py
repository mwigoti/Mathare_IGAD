# terrasat/views.py

import json

import africastalking
from django.conf import settings
from django.contrib.gis.db.models.functions import Length
from django.core.serializers import serialize
from django.db.models import Avg, Count, Sum
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .models import AllWardsMathare, BuildingsJoined, MaintenanceTask, PhoneUser, PoisJoined, RoadsJoined, WaterwaysJoined


# ---------------------------------------------------------------------
# Mathare flood-risk map
# ---------------------------------------------------------------------

def mathare_map(request):
    return render(request, "terrasat/mathare_map.html")


def mathare_flood_geojson(request):
    qs = AllWardsMathare.objects.all()

    village = request.GET.get("village")
    if village:
        qs = qs.filter(mathare_ufn_village__iexact=village)

    min_ufn = request.GET.get("min_ufn")
    if min_ufn:
        qs = qs.filter(mathare_ufn_ufn_equal__gte=float(min_ufn))

    geojson = serialize(
        "geojson",
        qs,
        geometry_field="geom",
        fields=(
            "name",
            "fclass",
            "mathare_ufn_village",
            "mathare_ufn_ufn_equal",
            "mathare_ufn_ufn_interim_weighted",
            "mathare_ufn_q_1d",
            "mathare_ufn_upstream_area_km2_local",
            "mathare_ufn_usi",
            "mathare_ufn_dsi_proxy",
        ),
    )
    return JsonResponse(json.loads(geojson))


def ward_detail(request, fid):
    """
    Given a ward's fid, returns POI/school breakdown, road length, and
    waterway presence within that ward's polygon — powers the click-to-
    zoom detail panel on the map.

    NOTE: buildings_joined does not currently exist in the database
    (confirmed via inspectdb — table not found), so building counts are
    omitted here. Add BuildingsJoined + a count once that table exists.
    """
    try:
        ward = AllWardsMathare.objects.get(fid=fid)
    except AllWardsMathare.DoesNotExist:
        raise Http404("Ward not found")

    if not ward.geom:
        return JsonResponse({"error": "Ward has no geometry"}, status=400)

    # A "ward" is made up of multiple polygon rows sharing the same
    # village name (that's why the USSD menu uses distinct village
    # names, not distinct fids). The single row looked up by fid above
    # is just one fragment — average the UFN interim-weighted score
    # across every row belonging to this ward for a representative
    # figure, rather than reporting one polygon's value.
    #
    # Null handling: rows with no UFN value (unmodeled fragments, e.g.
    # slivers outside the flood catchment) are explicitly excluded
    # before averaging, rather than relying on Avg() to silently skip
    # them — this keeps the null count visible/auditable and makes the
    # exclusion intentional rather than incidental.
    # ward.mathare_ufn_village is null across the ENTIRE all_wards_mathare
    # table — that join never populated. The real ward name lives in
    # `name` instead (e.g. "Mabatini ward"), confirmed against the table.
    ward_name = (ward.name or "").strip() or None

    if not ward_name:
        # Genuinely no name available for this polygon at all —
        # return early with a clear signal rather than a misleading 0/0.
        return JsonResponse({
            "fid": ward.fid,
            "ward_name": None,
            "ufn_interim_weighted_avg": None,
            "ufn_rows_used": 0,
            "ufn_rows_null_excluded": 0,
            "ufn_rows_total": 0,
            "note": "No ward name available for this polygon.",
        })

    # UFN data does NOT live on all_wards_mathare (confirmed null there).
    # It lives on pois_joined, where mathare_ufn_village and the UFN
    # fields ARE actually populated. Match on ward name (case/whitespace
    # tolerant, since names can carry inconsistent casing across tables)
    # and average the interim-weighted score, explicitly excluding nulls
    # first so they can't silently skew the result.
    ufn_source_rows = PoisJoined.objects.filter(mathare_ufn_village__iexact=ward_name)

    # Fallback: if no exact match, the two tables may name wards
    # slightly differently (e.g. "Kiamaiko" vs "Kiamaiko ward"). Try a
    # looser match on the ward name with "ward" stripped before giving up.
    if not ufn_source_rows.exists():
        stripped_name = ward_name.replace("ward", "").replace("Ward", "").strip()
        if stripped_name:
            ufn_source_rows = PoisJoined.objects.filter(
                mathare_ufn_village__icontains=stripped_name
            )

    total_ward_rows = ufn_source_rows.count()
    ufn_rows = ufn_source_rows.exclude(mathare_ufn_ufn_interim_weighted__isnull=True)
    null_ufn_rows = total_ward_rows - ufn_rows.count()

    avg_ufn_interim = ufn_rows.aggregate(avg=Avg("mathare_ufn_ufn_interim_weighted"))["avg"]

    # Building count for this ward, same name-match-with-fallback
    # approach used for the UFN source rows above.
    buildings_in_ward = BuildingsJoined.objects.filter(mathare_ufn_village__iexact=ward_name)
    if not buildings_in_ward.exists():
        stripped_name = ward_name.replace("ward", "").replace("Ward", "").strip()
        if stripped_name:
            buildings_in_ward = BuildingsJoined.objects.filter(
                mathare_ufn_village__icontains=stripped_name
            )
    building_count = buildings_in_ward.count()

    # Registered users in this ward — PhoneUser.ward_name is saved from
    # the same `name` field on all_wards_mathare during USSD
    # registration, so this should match directly.
    registered_users_count = PhoneUser.objects.filter(ward_name__iexact=ward_name).count()

    # POIs within this ward, broken down by type
    pois_in_ward = PoisJoined.objects.filter(geom__intersects=ward.geom)
    poi_breakdown = list(
        pois_in_ward.exclude(fclass__isnull=True)
        .values("fclass")
        .annotate(count=Count("fclass"))
        .order_by("-count")
    )
    school_count = pois_in_ward.filter(fclass__iexact="school").count()
    total_poi_count = pois_in_ward.count()

    # Roads within this ward — count + total length in meters
    roads_in_ward = RoadsJoined.objects.filter(geom__intersects=ward.geom)
    road_count = roads_in_ward.count()
    road_length_agg = roads_in_ward.annotate(seg_length=Length("geom")).aggregate(
        total=Sum("seg_length")
    )
    road_length_m = road_length_agg["total"].m if road_length_agg["total"] else 0

    # Waterways within this ward — count + total length in meters
    waterways_in_ward = WaterwaysJoined.objects.filter(geom__intersects=ward.geom)
    waterway_count = waterways_in_ward.count()
    waterway_length_agg = waterways_in_ward.annotate(seg_length=Length("geom")).aggregate(
        total=Sum("seg_length")
    )
    waterway_length_m = waterway_length_agg["total"].m if waterway_length_agg["total"] else 0

    return JsonResponse({
        "fid": ward.fid,
        "ward_name": ward_name,
        "ufn_interim_weighted_avg": round(avg_ufn_interim, 4) if avg_ufn_interim is not None else None,
        "ufn_rows_used": ufn_rows.count(),
        "ufn_rows_null_excluded": null_ufn_rows,
        "ufn_rows_total": total_ward_rows,
        # Below fields are from the single clicked polygon fragment only,
        # not averaged across the ward — kept for reference/debugging.
        "clicked_fragment": {
            "ufn_equal": ward.mathare_ufn_ufn_equal,
            "ufn_interim_weighted": ward.mathare_ufn_ufn_interim_weighted,
            "q_1d": ward.mathare_ufn_q_1d,
            "usi": ward.mathare_ufn_usi,
            "dsi_proxy": ward.mathare_ufn_dsi_proxy,
        },
        "pois": {
            "total": total_poi_count,
            "schools": school_count,
            "by_type": poi_breakdown,
        },
        "roads": {
            "count": road_count,
            "total_length_m": round(road_length_m, 1),
        },
        "waterways": {
            "count": waterway_count,
            "total_length_m": round(waterway_length_m, 1),
        },
        "buildings": building_count,
        "registered_users": registered_users_count,
    })


# ---------------------------------------------------------------------
# SMS confirmation (Africa's Talking) — outbound, needs API key unlike
# the USSD webhook flow above.
# ---------------------------------------------------------------------

_at_initialized = False


def _send_confirmation_sms(phone_number, message):
    """
    Sends a one-off SMS. Wrapped in try/except and never raises — if
    the SMS fails (bad key, network issue, insufficient sandbox credit),
    the USSD registration itself must still succeed and respond to the
    user normally. SMS failure is logged, not surfaced to the caller.
    """
    global _at_initialized
    try:
        if not settings.AT_API_KEY:
            print("SMS skipped: AT_API_KEY not configured.")
            return
        if not _at_initialized:
            africastalking.initialize(settings.AT_USERNAME, settings.AT_API_KEY)
            _at_initialized = True
        sms = africastalking.SMS
        sms.send(message, [phone_number])
    except Exception as e:
        # Deliberately swallow — registration must not fail because SMS did.
        print(f"SMS confirmation failed for {phone_number}: {e}")


SMS_CONFIRMATION = {
    "en": "TerraSat: You're registered/updated under {ward} ward. Reply to this SMS if you ever need to update your details.",
    "sw": "TerraSat: Umesajiliwa/kubadilishwa chini ya wodi ya {ward}. Jibu SMS hii ukihitaji kubadilisha taarifa zako.",
    "sheng": "TerraSat: Umewekwa kwa ward ya {ward}. Reply hii SMS ukitaka change details zako.",
}


# ---------------------------------------------------------------------
# USSD ward registration + problem reporting (Africa's Talking)
#
# Menu structure (tracked via the '*'-joined `text` steps AT sends):
#   Level 0 (text==""):      language select
#   Level 1 (1 step):        main menu — register/update ward, unsubscribe, or report a problem
#   Level 2 (2 steps):       ward list (branch 1) OR unsubscribe confirm (branch 2) OR category list (branch 3)
#   Level 3 (3 steps):       ward chosen -> save, END  OR  confirm yes/no -> delete/cancel, END  OR  category chosen -> save task, END
# ---------------------------------------------------------------------

LANG_CODES = {"1": "en", "2": "sw", "3": "sheng"}

LANG_PROMPT = "CON Choose language / Chagua lugha:\n1. English\n2. Kiswahili\n3. Sheng"

MAIN_MENU = {
    "en": "CON Welcome to TerraSat.\n1. Register/update my ward\n2. Unsubscribe\n3. Report a problem",
    "sw": "CON Karibu TerraSat.\n1. Sajili/badilisha wodi yangu\n2. Jiondoe\n3. Ripoti tatizo",
    "sheng": "CON Poa, ni TerraSat.\n1. Weka/change ward yako\n2. Toka kwa list\n3. Ripoti shida",
}

WARD_HEADER = {
    "en": "CON Select your ward (this updates your saved location if you're already registered):\n",
    "sw": "CON Chagua wodi yako (hii itabadilisha eneo lako lililohifadhiwa):\n",
    "sheng": "CON Chagua ward yako (hii ita-update location yako ya zamani):\n",
}

UNSUB_CONFIRM = {
    "en": "CON Are you sure you want to unsubscribe? All your data will be deleted.\n1. Yes\n2. No",
    "sw": "CON Una uhakika unataka kujiondoa? Taarifa zako zote zitafutwa.\n1. Ndiyo\n2. Hapana",
    "sheng": "CON Uko sure unataka toka kabisa? Data yako yote itafutwa.\n1. Ndio\n2. Hapana",
}

REGISTERED_MSG = {
    "en": "END You're registered/updated under {ward} ward. Thank you.",
    "sw": "END Umesajiliwa/kubadilishwa chini ya wodi ya {ward}. Asante.",
    "sheng": "END Umewekwa kwa ward ya {ward}. Asante.",
}

UNSUB_DONE = {
    "en": "END You've been unsubscribed and your data deleted.",
    "sw": "END Umeondolewa na taarifa zako zimefutwa.",
    "sheng": "END Umetoka na data yako imefutwa kabisa.",
}

UNSUB_CANCELLED = {
    "en": "END Unsubscribe cancelled.",
    "sw": "END Kughairi kujiondoa.",
    "sheng": "END Sawa, hujatoka.",
}

NO_WARDS_AVAILABLE = {
    "en": "END No wards are available right now. Please try again later.",
    "sw": "END Hakuna wodi zinazopatikana sasa. Tafadhali jaribu tena baadaye.",
    "sheng": "END Hakuna ward zozote sasa hivi. Try tena baadaye.",
}

INVALID = {
    "en": "END Invalid selection. Please dial in again.",
    "sw": "END Chaguo si sahihi. Tafadhali piga tena.",
    "sheng": "END Umechagua vibaya. Piga tena.",
}

NOT_REGISTERED_YET = {
    "en": "END You need to register your ward first (option 1 from the main menu) before reporting a problem.",
    "sw": "END Lazima usajili wodi yako kwanza (chagua 1 kwenye menyu kuu) kabla ya kuripoti tatizo.",
    "sheng": "END Lazima u-register ward yako kwanza (chagua 1 kwenye menu) kabla ya kuripoti shida.",
}

REPORT_CATEGORY_MENU = {
    "en": "CON What's the problem? (Reporting for {ward})\n1. Blocked drainage\n2. Drainage expansion needed\n3. Broken/contaminated water point\n4. Other",
    "sw": "CON Tatizo ni gani? (Unaripoti kwa {ward})\n1. Mfereji umeziba\n2. Mfereji unahitaji kupanuliwa\n3. Chanzo cha maji kimeharibika/kimechafuliwa\n4. Nyingine",
    "sheng": "CON Shida ni gani? (Unaripoti kwa {ward})\n1. Drainage imeblock\n2. Drainage inahitaji expand\n3. Water point imeharibika/imechafuka\n4. Ingine",
}

LOCATION_PROMPT = {
    "en": "CON Where exactly? Describe using a nearby landmark so it can be found, e.g. 'near Blue Star shop', 'behind Mabatini primary school', 'next to the water tank on River road'. Type it now:",
    "sw": "CON Iko wapi hasa? Eleza ukitumia alama karibu ili ipatikane, mfano 'karibu na duka la Blue Star', 'nyuma ya shule ya Mabatini', 'karibu na tanki la maji Mtaa wa Mto'. Andika sasa:",
    "sheng": "CON Iko wapi exactly? Describe ukitumia landmark iko karibu, mfano 'karibu na shop ya Blue Star', 'nyuma ya shule ya Mabatini', 'karibu na tank ya maji River road'. Type sasa:",
}

REPORT_CONFIRMED = {
    "en": "END Thank you. Your report ({category}) for {ward} has been received and will be reviewed.",
    "sw": "END Asante. Ripoti yako ({category}) kwa {ward} imepokelewa na itapitiwa.",
    "sheng": "END Asante. Report yako ({category}) ya {ward} imepokewa na itaangaliwa.",
}


def _get_ward_choices():
    """
    NOTE: mathare_ufn_village is null across the ENTIRE all_wards_mathare
    table — the UFN join never actually populated it. The real ward
    names live in `name` instead (e.g. "Mabatini ward", "Huruma ward"),
    which comes from the admin_level8 boundary layer. Using that here
    until the UFN join is fixed at the source.
    """
    names = (
        AllWardsMathare.objects
        .exclude(name__isnull=True)
        .exclude(name__exact="")
        .values_list("name", flat=True)
        .distinct()
        .order_by("name")
    )
    return list(names)


@csrf_exempt
def ussd_register(request):
    phone_number = request.POST.get("phoneNumber", "")
    text = request.POST.get("text", "")
    steps = text.split("*") if text else []

    # --- Level 0: language select ---
    if text == "":
        return HttpResponse(LANG_PROMPT, content_type="text/plain")

    lang = LANG_CODES.get(steps[0])
    if lang is None:
        # Bad language choice at step 0 — bail out in English since we
        # don't know their preferred language yet.
        return HttpResponse(INVALID["en"], content_type="text/plain")

    # --- Level 1: main menu ---
    if len(steps) == 1:
        return HttpResponse(MAIN_MENU[lang], content_type="text/plain")

    main_choice = steps[1]

    # --- Level 2 ---
    if len(steps) == 2:
        if main_choice == "1":
            wards = _get_ward_choices()
            if not wards:
                return HttpResponse(NO_WARDS_AVAILABLE[lang], content_type="text/plain")
            menu = WARD_HEADER[lang]
            for i, ward in enumerate(wards, start=1):
                menu += f"{i}. {ward}\n"
            return HttpResponse(menu, content_type="text/plain")

        elif main_choice == "2":
            return HttpResponse(UNSUB_CONFIRM[lang], content_type="text/plain")

        elif main_choice == "3":
            # Reporting requires an existing registration — that's how
            # we know which ward the report belongs to without asking
            # again or needing GPS.
            phone_user = PhoneUser.objects.filter(phone_number=phone_number).first()
            if not phone_user or not phone_user.ward_name:
                return HttpResponse(NOT_REGISTERED_YET[lang], content_type="text/plain")
            return HttpResponse(
                REPORT_CATEGORY_MENU[lang].format(ward=phone_user.ward_name),
                content_type="text/plain",
            )

        else:
            return HttpResponse(INVALID[lang], content_type="text/plain")

    # --- Level 3 ---
    if len(steps) == 3:
        third = steps[2]

        if main_choice == "1":
            wards = _get_ward_choices()
            if third.isdigit() and 1 <= int(third) <= len(wards):
                selected_ward = wards[int(third) - 1]
                matching_row = AllWardsMathare.objects.filter(
                    name__iexact=selected_ward
                ).first()

                PhoneUser.objects.update_or_create(
                    phone_number=phone_number,
                    defaults={
                        "ward_name": selected_ward,
                        "ward_fid": matching_row.fid if matching_row else None,
                        "language": lang,
                    },
                )
                _send_confirmation_sms(
                    phone_number,
                    SMS_CONFIRMATION[lang].format(ward=selected_ward),
                )
                return HttpResponse(
                    REGISTERED_MSG[lang].format(ward=selected_ward),
                    content_type="text/plain",
                )
            else:
                return HttpResponse(INVALID[lang], content_type="text/plain")

        elif main_choice == "2":
            if third == "1":
                PhoneUser.objects.filter(phone_number=phone_number).delete()
                return HttpResponse(UNSUB_DONE[lang], content_type="text/plain")
            elif third == "2":
                return HttpResponse(UNSUB_CANCELLED[lang], content_type="text/plain")
            else:
                return HttpResponse(INVALID[lang], content_type="text/plain")

        elif main_choice == "3":
            phone_user = PhoneUser.objects.filter(phone_number=phone_number).first()
            if not phone_user or not phone_user.ward_name:
                return HttpResponse(NOT_REGISTERED_YET[lang], content_type="text/plain")

            category_map = {"1": "blocked_drainage", "2": "drainage_expansion", "3": "broken_water_point", "4": "other"}
            if third not in category_map:
                return HttpResponse(INVALID[lang], content_type="text/plain")

            # Don't save yet — ask for a landmark-based location
            # description first so the report is actually findable.
            return HttpResponse(LOCATION_PROMPT[lang], content_type="text/plain")

        else:
            return HttpResponse(INVALID[lang], content_type="text/plain")

    # --- Level 4: only reached for the report-a-problem flow, capturing
    # the free-text landmark description ---
    if len(steps) >= 4 and main_choice == "3":
        phone_user = PhoneUser.objects.filter(phone_number=phone_number).first()
        if not phone_user or not phone_user.ward_name:
            return HttpResponse(NOT_REGISTERED_YET[lang], content_type="text/plain")

        category_map = {"1": "blocked_drainage", "2": "drainage_expansion", "3": "broken_water_point", "4": "other"}
        category = category_map.get(steps[2])
        if not category:
            return HttpResponse(INVALID[lang], content_type="text/plain")

        # Rejoin everything after step 3 with '*' — protects against a
        # landmark description that itself happens to contain a '*',
        # which would otherwise get incorrectly split into extra steps.
        description = "*".join(steps[3:]).strip()
        if not description:
            description = None  # empty/whitespace-only entry — still save the report, just without location detail

        MaintenanceTask.objects.create(
            category=category,
            status="reported",
            ward_name=phone_user.ward_name,
            ward_fid=phone_user.ward_fid,
            reported_by_phone=phone_number,
            description=description,
        )

        category_label = dict(MaintenanceTask.CATEGORY_CHOICES)[category]
        return HttpResponse(
            REPORT_CONFIRMED[lang].format(category=category_label, ward=phone_user.ward_name),
            content_type="text/plain",
        )

    # Anything deeper than expected — bail out safely.
    return HttpResponse(INVALID[lang], content_type="text/plain")


# ---------------------------------------------------------------------
# High-risk flood alert review (staff-only, approve-before-send)
# ---------------------------------------------------------------------

HIGH_RISK_ALERT_MSG = {
    "en": "TerraSat FLOOD ALERT: Your area is at HIGH RISK of flooding. Move to a safer location. Nearby safe spaces: {shelters}. Warning: {water_count} water points in your area may be contaminated — avoid untreated tap/well water, boil before drinking.",
    "sw": "TerraSat TAHADHARI: Eneo lako liko HATARINI KUBWA ya mafuriko. Hamia mahali salama. Maeneo salama karibu: {shelters}. Tahadhari: vyanzo {water_count} vya maji karibu yako vinaweza kuchafuliwa — epuka maji ya bomba yasiyotibiwa, chemsha kabla ya kunywa.",
    "sheng": "TerraSat ALERT: Area yako iko HATARINI KUBWA ya mafuriko. Hama uende mahali safe. Places za karibu: {shelters}. Warning: {water_count} water points karibu yako inaweza kuwa contaminated — usikunywe maji ya bomba bila kuchemsha.",
}


def high_risk_clear_cache(request):
    """Manual cache-bust — call this after re-importing/updating the underlying gpkg data, since the grid registry is cached for 24h."""
    from .high_risk import clear_grid_cache
    clear_grid_cache()
    return JsonResponse({"status": "cache cleared"})


def high_risk_public_summary(request):
    """
    Public-safe version — just which wards are flagged and grid counts,
    no phone numbers or user lists. Used to draw the risk overlay on
    the main public map without exposing registrant data to anyone
    who loads that page.
    """
    from .high_risk import build_ward_alert_summaries
    ward_summaries = build_ward_alert_summaries()
    return JsonResponse({
        "flagged_wards": [
            {"village": w["village"], "high_risk_grid_count": w["high_risk_grid_count"]}
            for w in ward_summaries
        ]
    })


def task_public_summary(request):
    """Public-safe maintenance task summary shown on the map view."""
    tasks = MaintenanceTask.objects.all()
    return JsonResponse({
        "total_tasks": tasks.count(),
        "reported": tasks.filter(status="reported").count(),
        "verified": tasks.filter(status="verified").count(),
        "in_progress": tasks.filter(status="in_progress").count(),
        "resolved": tasks.filter(status="resolved").count(),
    })


def high_risk_dashboard(request):
    """Renders the visual dashboard page; it fetches /high-risk/review/ itself via JS."""
    return render(request, "terrasat/high_risk_dashboard.html")


def high_risk_review(request):
    """
    GET-only summary screen: shows flagged high-risk grids, who would
    be notified, proposed safe shelters, and water-source hazards.
    Does NOT send anything. Staff-only since this surfaces registered
    users' phone numbers.
    """
    from .high_risk import build_high_risk_summary
    summary = build_high_risk_summary()
    return JsonResponse(summary)


def high_risk_send_alerts(request):
    """
    POST-only: sends the flood alert SMS. If a `village` param is
    provided, sends ONLY to that ward. If omitted, sends to every
    currently-flagged ward — used deliberately, not by accident, since
    that's a much bigger action. Requires explicit confirm=yes either way.
    """
    if request.method != "POST" or request.POST.get("confirm") != "yes":
        return JsonResponse(
            {"error": "Must POST with confirm=yes to send alerts."}, status=400
        )

    from .high_risk import build_ward_alert_summaries
    ward_summaries = build_ward_alert_summaries()

    target_village = request.POST.get("village")
    if target_village:
        ward_summaries = [w for w in ward_summaries if w["village"] == target_village]
        if not ward_summaries:
            return JsonResponse({"error": f"No flagged ward matching '{target_village}'."}, status=404)

    results = []
    total_sent = 0
    total_failed = 0

    for ward in ward_summaries:
        shelter_names = ", ".join(s["name"] for s in ward["shelters"]) or "check with local authorities"

        sent_count = 0
        failed_count = 0
        for user in ward["affected_users"]:
            lang = user["language"] if user["language"] in HIGH_RISK_ALERT_MSG else "en"
            message = HIGH_RISK_ALERT_MSG[lang].format(
                shelters=shelter_names,
                water_count=ward["water_hazard_count"],
            )
            try:
                _send_confirmation_sms(user["phone_number"], message)
                sent_count += 1
            except Exception:
                failed_count += 1

        total_sent += sent_count
        total_failed += failed_count
        results.append({
            "village": ward["village"],
            "sent": sent_count,
            "failed": failed_count,
            "shelters_referenced": ward["shelters"],
            "water_hazard_count": ward["water_hazard_count"],
        })

    return JsonResponse({
        "total_sent": total_sent,
        "total_failed": total_failed,
        "wards": results,
    })


# ---------------------------------------------------------------------
# Maintenance task dashboard (blocked drainage, water hazards, etc.)
# ---------------------------------------------------------------------

TASK_RESOLVED_SMS = {
    "en": "TerraSat: Your report ({category}) for {ward} has been marked RESOLVED. Thank you for reporting it.",
    "sw": "TerraSat: Ripoti yako ({category}) kwa {ward} imetatuliwa. Asante kwa kuripoti.",
    "sheng": "TerraSat: Report yako ({category}) ya {ward} imefix. Asante kwa kuripoti.",
}


def set_task_status(task, new_status):
    """
    Shared status-transition logic — used by BOTH the admin panel and
    the staff dashboard, so they can never drift out of sync (e.g. one
    path sending the SMS and the other not). Only 'resolved' notifies
    the original reporter; every other transition is silent.
    """
    task.status = new_status
    if new_status == "resolved":
        task.resolved_at = timezone.now()
    task.save()

    if new_status == "resolved" and task.reported_by_phone:
        phone_user = PhoneUser.objects.filter(phone_number=task.reported_by_phone).first()
        lang = phone_user.language if phone_user and phone_user.language in TASK_RESOLVED_SMS else "en"
        category_label = dict(MaintenanceTask.CATEGORY_CHOICES).get(task.category, task.category)
        _send_confirmation_sms(
            task.reported_by_phone,
            TASK_RESOLVED_SMS[lang].format(category=category_label, ward=task.ward_name or "your area"),
        )
    return task


def task_dashboard(request):
    """Renders the staff task-triage dashboard; fetches data itself via JS."""
    return render(request, "terrasat/task_dashboard.html")


def task_list(request):
    """JSON list of all maintenance tasks, most recent first. Optional ?status=reported filter."""
    qs = MaintenanceTask.objects.all()
    status_filter = request.GET.get("status")
    if status_filter:
        qs = qs.filter(status=status_filter)

    tasks = [
        {
            "id": t.id,
            "category": t.category,
            "category_label": t.get_category_display(),
            "status": t.status,
            "status_label": t.get_status_display(),
            "ward_name": t.ward_name,
            "description": t.description,
            "reported_by_phone": t.reported_by_phone,
            "created_at": t.created_at.strftime("%Y-%m-%d %H:%M"),
            "resolved_at": t.resolved_at.strftime("%Y-%m-%d %H:%M") if t.resolved_at else None,
        }
        for t in qs
    ]
    return JsonResponse({"tasks": tasks})


def task_update_status(request, task_id):
    """
    POST-only status change for a single task. 'resolved' triggers the
    closing-the-loop SMS via set_task_status — the exact same path the
    admin bulk action uses, so behavior is identical either way.
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST required."}, status=400)

    new_status = request.POST.get("new_status")
    valid_statuses = dict(MaintenanceTask.STATUS_CHOICES)
    if new_status not in valid_statuses:
        return JsonResponse({"error": f"Invalid status '{new_status}'."}, status=400)

    try:
        task = MaintenanceTask.objects.get(id=task_id)
    except MaintenanceTask.DoesNotExist:
        return JsonResponse({"error": "Task not found."}, status=404)

    set_task_status(task, new_status)
    return JsonResponse({"id": task.id, "status": task.status, "status_label": task.get_status_display()})