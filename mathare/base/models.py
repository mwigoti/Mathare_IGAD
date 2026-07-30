# terrasat/models.py

from django.contrib.gis.db import models as gis_models
from django.db import models


class AllWardsMathare(models.Model):
    """
    OSM/UFN-joined ward polygons for Mathare, imported from gpkg.
    Unmanaged: table already exists in Postgres via ogr2ogr/QGIS import.
    """
    fid = models.BigIntegerField(primary_key=True)
    geom = gis_models.MultiPolygonField(srid=4326, blank=True, null=True)

    osm_id = models.CharField(max_length=12, blank=True, null=True)
    code = models.BigIntegerField(blank=True, null=True)
    fclass = models.CharField(max_length=28, blank=True, null=True)
    name = models.CharField(max_length=100, blank=True, null=True)
    layer = models.CharField(max_length=254, blank=True, null=True)
    path = models.CharField(max_length=254, blank=True, null=True)

    mathare_ufn_village = models.CharField(max_length=255, blank=True, null=True)
    mathare_ufn_ufn_equal = models.FloatField(blank=True, null=True)
    mathare_ufn_ufn_interim_weighted = models.FloatField(blank=True, null=True)
    mathare_ufn_q_1d = models.FloatField(blank=True, null=True)
    mathare_ufn_upstream_area_km2_local = models.FloatField(blank=True, null=True)
    mathare_ufn_usi = models.FloatField(blank=True, null=True)
    mathare_ufn_dsi_proxy = models.FloatField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "all_wards_mathare"

    def __str__(self):
        return f"{self.mathare_ufn_village or self.name or 'Ward'} (fid={self.fid})"


class PoisJoined(models.Model):
    """
    Points of interest (schools, health facilities, shops, etc.) joined
    with UFN flood-risk fields per Mathare ward. Note: Postgres reports
    this column as a Polygon type, not Point, despite the name —
    verify with `\\d pois_joined` in psql if geometry looks off downstream.
    """
    id_0 = models.AutoField(primary_key=True)
    geom = gis_models.PolygonField(srid=4326, blank=True, null=True)

    fid = models.BigIntegerField(blank=True, null=True)
    id = models.CharField(max_length=100, blank=True, null=True)
    grid_id = models.IntegerField(blank=True, null=True)
    village = models.CharField(max_length=255, blank=True, null=True)
    village_match = models.TextField(blank=True, null=True)

    mathare_ufn_village = models.CharField(max_length=255, blank=True, null=True)
    mathare_ufn_ufn_equal = models.FloatField(db_column="mathare_ufn_UFN_equal", blank=True, null=True)
    mathare_ufn_ufn_interim_weighted = models.FloatField(db_column="mathare_ufn_UFN_interim_weighted", blank=True, null=True)
    mathare_ufn_q_1d = models.FloatField(db_column="mathare_ufn_Q_1d", blank=True, null=True)
    mathare_ufn_upstream_area_km2_local = models.FloatField(blank=True, null=True)
    mathare_ufn_usi = models.FloatField(db_column="mathare_ufn_USI", blank=True, null=True)
    mathare_ufn_dsi_proxy = models.FloatField(db_column="mathare_ufn_DSI_proxy", blank=True, null=True)

    fid_2 = models.BigIntegerField(blank=True, null=True)
    osm_id = models.CharField(max_length=12, blank=True, null=True)
    code = models.IntegerField(blank=True, null=True)
    fclass = models.CharField(max_length=28, blank=True, null=True)
    name = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        managed = False
        db_table = "pois_joined"

    def __str__(self):
        return f"{self.name or self.fclass or 'POI'}"


class RoadsJoined(models.Model):
    id_0 = models.AutoField(primary_key=True)
    geom = gis_models.PolygonField(srid=4326, blank=True, null=True)  # inspectdb-reported type; verify with \d roads_joined

    fid = models.BigIntegerField(blank=True, null=True)
    id = models.CharField(max_length=100, blank=True, null=True)
    grid_id = models.IntegerField(blank=True, null=True)
    village = models.CharField(max_length=255, blank=True, null=True)
    village_match = models.TextField(blank=True, null=True)

    mathare_ufn_village = models.CharField(max_length=255, blank=True, null=True)
    mathare_ufn_ufn_equal = models.FloatField(db_column="mathare_ufn_UFN_equal", blank=True, null=True)
    mathare_ufn_ufn_interim_weighted = models.FloatField(db_column="mathare_ufn_UFN_interim_weighted", blank=True, null=True)
    mathare_ufn_q_1d = models.FloatField(db_column="mathare_ufn_Q_1d", blank=True, null=True)
    mathare_ufn_upstream_area_km2_local = models.FloatField(blank=True, null=True)
    mathare_ufn_usi = models.FloatField(db_column="mathare_ufn_USI", blank=True, null=True)
    mathare_ufn_dsi_proxy = models.FloatField(db_column="mathare_ufn_DSI_proxy", blank=True, null=True)

    fid_2 = models.BigIntegerField(blank=True, null=True)
    osm_id = models.CharField(max_length=12, blank=True, null=True)
    code = models.IntegerField(blank=True, null=True)
    fclass = models.CharField(max_length=28, blank=True, null=True)
    name = models.CharField(max_length=100, blank=True, null=True)
    ref = models.CharField(max_length=20, blank=True, null=True)
    oneway = models.CharField(max_length=1, blank=True, null=True)
    maxspeed = models.IntegerField(blank=True, null=True)
    layer = models.IntegerField(blank=True, null=True)
    bridge = models.CharField(max_length=1, blank=True, null=True)
    tunnel = models.CharField(max_length=1, blank=True, null=True)

    class Meta:
        managed = False
        db_table = "roads_joined"

    def __str__(self):
        return f"{self.name or self.fclass or 'Road'}"


class WaterwaysJoined(models.Model):
    id_0 = models.AutoField(primary_key=True)
    geom = gis_models.PolygonField(srid=4326, blank=True, null=True)  # inspectdb-reported type; verify with \d waterways_joined

    fid = models.BigIntegerField(blank=True, null=True)
    id = models.CharField(max_length=100, blank=True, null=True)
    grid_id = models.IntegerField(blank=True, null=True)
    village = models.CharField(max_length=255, blank=True, null=True)
    village_match = models.TextField(blank=True, null=True)

    mathare_ufn_village = models.CharField(max_length=255, blank=True, null=True)
    mathare_ufn_ufn_equal = models.FloatField(db_column="mathare_ufn_UFN_equal", blank=True, null=True)
    mathare_ufn_ufn_interim_weighted = models.FloatField(db_column="mathare_ufn_UFN_interim_weighted", blank=True, null=True)
    mathare_ufn_q_1d = models.FloatField(db_column="mathare_ufn_Q_1d", blank=True, null=True)
    mathare_ufn_upstream_area_km2_local = models.FloatField(blank=True, null=True)
    mathare_ufn_usi = models.FloatField(db_column="mathare_ufn_USI", blank=True, null=True)
    mathare_ufn_dsi_proxy = models.FloatField(db_column="mathare_ufn_DSI_proxy", blank=True, null=True)

    fid_2 = models.BigIntegerField(blank=True, null=True)
    osm_id = models.CharField(max_length=12, blank=True, null=True)
    code = models.IntegerField(blank=True, null=True)
    fclass = models.CharField(max_length=28, blank=True, null=True)
    width = models.IntegerField(blank=True, null=True)
    name = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        managed = False
        db_table = "waterways_joined"

    def __str__(self):
        return f"{self.name or self.fclass or 'Waterway'}"


class BuildingsJoined(models.Model):
    id_0 = models.AutoField(primary_key=True)
    geom = gis_models.PolygonField(srid=4326, blank=True, null=True)  # verify with \d buildings_joined if it renders oddly

    fid = models.BigIntegerField(blank=True, null=True)
    id = models.CharField(max_length=100, blank=True, null=True)
    grid_id = models.IntegerField(blank=True, null=True)
    village = models.CharField(max_length=255, blank=True, null=True)
    village_match = models.TextField(blank=True, null=True)

    mathare_ufn_village = models.CharField(max_length=255, blank=True, null=True)
    mathare_ufn_ufn_equal = models.FloatField(db_column="mathare_ufn_UFN_equal", blank=True, null=True)
    mathare_ufn_ufn_interim_weighted = models.FloatField(db_column="mathare_ufn_UFN_interim_weighted", blank=True, null=True)
    mathare_ufn_q_1d = models.FloatField(db_column="mathare_ufn_Q_1d", blank=True, null=True)
    mathare_ufn_upstream_area_km2_local = models.FloatField(blank=True, null=True)
    mathare_ufn_usi = models.FloatField(db_column="mathare_ufn_USI", blank=True, null=True)
    mathare_ufn_dsi_proxy = models.FloatField(db_column="mathare_ufn_DSI_proxy", blank=True, null=True)

    fid_2 = models.BigIntegerField(blank=True, null=True)
    osm_id = models.CharField(max_length=12, blank=True, null=True)
    code = models.IntegerField(blank=True, null=True)
    fclass = models.CharField(max_length=28, blank=True, null=True)
    name = models.CharField(max_length=100, blank=True, null=True)
    type = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        managed = False
        db_table = "buildings_joined"

    def __str__(self):
        return f"{self.name or self.fclass or 'Building'}"


class Pofw(models.Model):
    """Places of worship — separate table since pois_joined has no church/worship category at all."""
    id_0 = models.AutoField(primary_key=True)
    geom = gis_models.PolygonField(srid=4326, blank=True, null=True)

    fid = models.BigIntegerField(blank=True, null=True)
    id = models.CharField(max_length=100, blank=True, null=True)
    grid_id = models.IntegerField(blank=True, null=True)
    village = models.CharField(max_length=255, blank=True, null=True)
    village_match = models.TextField(blank=True, null=True)

    mathare_ufn_village = models.CharField(max_length=255, blank=True, null=True)
    mathare_ufn_ufn_equal = models.FloatField(db_column="mathare_ufn_UFN_equal", blank=True, null=True)
    mathare_ufn_ufn_interim_weighted = models.FloatField(db_column="mathare_ufn_UFN_interim_weighted", blank=True, null=True)
    mathare_ufn_q_1d = models.FloatField(db_column="mathare_ufn_Q_1d", blank=True, null=True)
    mathare_ufn_upstream_area_km2_local = models.FloatField(blank=True, null=True)
    mathare_ufn_usi = models.FloatField(db_column="mathare_ufn_USI", blank=True, null=True)
    mathare_ufn_dsi_proxy = models.FloatField(db_column="mathare_ufn_DSI_proxy", blank=True, null=True)

    fid_2 = models.BigIntegerField(blank=True, null=True)
    osm_id = models.CharField(max_length=12, blank=True, null=True)
    code = models.IntegerField(blank=True, null=True)
    fclass = models.CharField(max_length=28, blank=True, null=True)  # 'christian', 'christian_evangelical', etc.
    name = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        managed = False
        db_table = "pofw"

    def __str__(self):
        return f"{self.name or self.fclass or 'Place of worship'}"


class Pofw(models.Model):
    """
    Places of worship (churches etc.) — created separately since these
    were entirely absent from pois_joined's fclass categories. Same
    schema pattern as PoisJoined/BuildingsJoined/etc.
    """
    id_0 = models.AutoField(primary_key=True)
    geom = gis_models.PolygonField(srid=4326, blank=True, null=True)

    fid = models.BigIntegerField(blank=True, null=True)
    id = models.CharField(max_length=100, blank=True, null=True)
    grid_id = models.IntegerField(blank=True, null=True)
    village = models.CharField(max_length=255, blank=True, null=True)
    village_match = models.TextField(blank=True, null=True)

    mathare_ufn_village = models.CharField(max_length=255, blank=True, null=True)
    mathare_ufn_ufn_equal = models.FloatField(db_column="mathare_ufn_UFN_equal", blank=True, null=True)
    mathare_ufn_ufn_interim_weighted = models.FloatField(db_column="mathare_ufn_UFN_interim_weighted", blank=True, null=True)
    mathare_ufn_q_1d = models.FloatField(db_column="mathare_ufn_Q_1d", blank=True, null=True)
    mathare_ufn_upstream_area_km2_local = models.FloatField(blank=True, null=True)
    mathare_ufn_usi = models.FloatField(db_column="mathare_ufn_USI", blank=True, null=True)
    mathare_ufn_dsi_proxy = models.FloatField(db_column="mathare_ufn_DSI_proxy", blank=True, null=True)

    fid_2 = models.BigIntegerField(blank=True, null=True)
    osm_id = models.CharField(max_length=12, blank=True, null=True)
    code = models.IntegerField(blank=True, null=True)
    fclass = models.CharField(max_length=28, blank=True, null=True)  # 'christian', 'christian_evangelical', etc.
    name = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        managed = False
        db_table = "pofw"

    def __str__(self):
        return f"{self.name or self.fclass or 'Place of worship'}"


class MaintenanceTask(models.Model):
    """
    Hybrid task tracking: residents report via USSD (auto-tagged to
    their registered ward), staff verify/triage/resolve via admin.
    Managed table — created fresh, not imported.
    """
    CATEGORY_CHOICES = [
        ("blocked_drainage", "Blocked drainage"),
        ("drainage_expansion", "Drainage expansion needed"),
        ("broken_water_point", "Broken/contaminated water point"),
        ("other", "Other"),
    ]

    STATUS_CHOICES = [
        ("reported", "Reported (unverified)"),
        ("verified", "Verified"),
        ("in_progress", "In progress"),
        ("resolved", "Resolved"),
        ("rejected", "Rejected (false report / not actionable)"),
    ]

    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default="other")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="reported")

    ward_name = models.CharField(max_length=255, blank=True, null=True)
    ward_fid = models.BigIntegerField(blank=True, null=True)

    reported_by_phone = models.CharField(max_length=20, blank=True, null=True)
    description = models.TextField(blank=True, null=True)

    admin_notes = models.TextField(blank=True, null=True)  # internal, never sent to the reporter

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "maintenance_tasks"
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.get_category_display()}] {self.ward_name or 'unknown ward'} — {self.get_status_display()}"


class PhoneUser(models.Model):
    """
    Phone-identified user registered via USSD (Africa's Talking).
    Managed: this is a new table Django creates via migrations.
    """
    phone_number = models.CharField(max_length=20, unique=True)

    ward_fid = models.BigIntegerField(blank=True, null=True)
    ward_name = models.CharField(max_length=255, blank=True, null=True)

    LANGUAGE_CHOICES = [
        ("en", "English"),
        ("sw", "Kiswahili"),
        ("sheng", "Sheng"),
    ]
    language = models.CharField(max_length=10, choices=LANGUAGE_CHOICES, default="en")

    registered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "phone_users"

    def __str__(self):
        return f"{self.phone_number} — {self.ward_name or 'no ward set'}"