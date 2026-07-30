# TerraSat Mathare

TerraSat Mathare is a Django-based geospatial decision-support platform for flood-risk awareness, ward-level infrastructure monitoring, and community issue reporting in Mathare. The project combines GIS data, a public-facing interactive map, USSD-based resident reporting, and staff dashboards for triaging maintenance tasks and reviewing flood-risk information.

This repository contains the application logic, templates, GIS models, and URL routes that power the platform.

---

## Executive summary

TerraSat Mathare is a Django and GIS-based platform for helping communities and local responders understand flood risk, report infrastructure issues, and manage maintenance work in Mathare. The project combines a public map, ward-level analytics, USSD-based reporting, and staff dashboards into one operational workflow.

This repository is the implementation foundation for a practical, community-centered flood-response system.

---

## 1. Project overview

The system was designed to help local stakeholders understand flood exposure in Mathare and act on it in a practical way.

It supports three major workflows:

1. Public and staff-facing flood-risk visualization
   - Interactive map rendering of ward polygons and flood-risk indicators.
   - Ward-level detail panels showing risk context, infrastructure exposure, and nearby features.

2. Community reporting through USSD
   - Residents can register their ward.
   - They can report issues such as blocked drainage, drainage expansion needs, broken water points, or other problems.
   - Reports are stored as maintenance tasks for review.

3. Operational dashboarding for staff
   - High-risk dashboard for reviewing flood-risk conditions.
   - Maintenance task dashboard for tracking report status and updating tasks.
   - Public summary endpoints to support lightweight dashboard views and monitoring widgets.

---

## 2. What has been implemented

### 2.1 Interactive flood-risk map

The application exposes a main map page that:

- displays ward polygons from a GIS-enabled database,
- styles wards by flood-risk indicators,
- overlays labels for ward names,
- allows users to click a ward to inspect detailed information,
- presents visual risk/task summaries and explanatory content.

The map is built with Django templates and Leaflet.js on the frontend.

### 2.2 GIS-backed ward intelligence

The backend uses Django with GeoDjango and PostGIS-style spatial tables to work with geographic data. The project reads from existing spatial tables such as:

- all_wards_mathare
- pois_joined
- roads_joined
- waterways_joined
- buildings_joined
- pofw

These are modeled as unmanaged Django models so the app can query them without recreating the underlying tables.

### 2.3 USSD registration and reporting

The application includes a USSD flow for residents.

Supported actions include:

- choosing a language,
- registering or updating a ward,
- unsubscribing from the service,
- reporting a problem associated with a ward,
- providing a location description for the reported issue.

The flow is wired through Django views and responds in the format expected by Africa’s Talking.

### 2.4 Maintenance task tracking

Residents’ reports are converted into maintenance tasks in the system. The task model supports:

- category selection,
- status management,
- ward association,
- phone-number tracking for the reporter,
- notes for staff review.

The task dashboard provides a staff-friendly view of outstanding work.

### 2.5 High-risk and public summaries

The project includes dedicated endpoints and dashboard views for:

- public-safe high-risk summaries,
- task summaries,
- review workflows,
- alert-oriented reporting views.

This allows the platform to present a simple overview without exposing internal details unnecessarily.

---

## 3. Technology stack

The project is built with the following core technologies:

- Python 3.12
- Django
- GeoDjango
- PostgreSQL/PostGIS-compatible database
- Leaflet.js for map rendering
- Africa’s Talking for USSD/SMS integration
- HTML/CSS/JavaScript for the dashboard and map interface
- Django templates for server-rendered pages

---

## 4. Project structure

```text
Mathare_IGAD/
├── mathare/
│   ├── manage.py
│   ├── base/
│   │   ├── admin.py
│   │   ├── apps.py
│   │   ├── high_risk.py
│   │   ├── models.py
│   │   ├── urls.py
│   │   ├── views.py
│   │   ├── migrations/
│   │   └── templates/
│   │       └── terrasat/
│   └── mathare/
│       ├── settings.py
│       ├── urls.py
│       └── wsgi.py
└── README.md
```

### Key application modules

- base/models.py
  - Defines the GIS-backed models and task/phone-user models.

- base/views.py
  - Contains the map page logic, ward detail API, USSD flow, task dashboard logic, and high-risk/public summary endpoints.

- base/urls.py
  - Routes the web pages and API endpoints.

- base/templates/terrasat/
  - Holds the HTML templates for the map, high-risk dashboard, task dashboard, and shared base layout.

---

## 5. How it works

```mermaid
flowchart TD
    A[Resident] --> B[USSD flow]
    B --> C[Maintenance task record]
    D[Staff operator] --> E[Task dashboard]
    E --> C
    F[GIS database] --> G[Interactive map]
    G --> H[Ward detail insights]
    I[Flood-risk data] --> G
    C --> E
    H --> D
```

This architecture connects four main layers:

- Community input through USSD and SMS
- A GIS and data layer for spatial analysis
- A web-based map and dashboard experience
- Staff workflows for triaging and resolving reported issues

---

## 6. Screenshots

Add screenshots here as the project evolves:

- Main map view
- Ward detail panel
- High-risk dashboard
- Task dashboard
- USSD flow example

Suggested naming convention:

```text
screenshots/map-view.png
screenshots/ward-detail.png
screenshots/high-risk-dashboard.png
screenshots/task-dashboard.png
```

---

## 7. Prerequisites

Before running the project locally, ensure you have:

- Python 3.10+ (the project is currently using Python 3.12)
- A PostgreSQL/PostGIS-compatible database
- A working virtual environment
- Access to the required environment variables for the database and SMS/USSD integration

---

## 8. Environment configuration

The project reads environment variables from a .env file in the project root.

Create a .env file in the Mathare project directory (the one containing manage.py) with values similar to the following:

```env
DATABASE_URL=postgres://USER:PASSWORD@HOST:5432/DB_NAME
DB_SSL_REQUIRE=True

AT_USERNAME=sandbox
AT_API_KEY=your-africastalking-api-key

SECRET_KEY=your-django-secret-key
```

### Notes

- DATABASE_URL should point to a PostgreSQL/PostGIS database.
- The app expects the GIS tables to already exist in the database.
- AT_API_KEY is required if SMS confirmation is enabled.
- The current settings file also loads environment variables from .env automatically.

---

## 9. Setup instructions

### 7.1 Create and activate a virtual environment

```bash
cd /path/to/Mathare_IGAD
python3 -m venv venv
source venv/bin/activate
```

### 7.2 Install dependencies

Install the Python packages required by the project. At minimum the app relies on:

```bash
pip install Django dj-database-url python-dotenv africastalking psycopg2-binary
```

If you later add a requirements.txt file, you can replace the above with:

```bash
pip install -r requirements.txt
```

### 7.3 Run database migrations

If the project uses managed tables for the task/phone-user models, run:

```bash
cd mathare
python manage.py migrate
```

> Note: The GIS-backed models for the imported spatial layers are marked as unmanaged, so they rely on existing database tables rather than Django-generated migrations.

---

## 10. Running the application locally

From the project directory:

```bash
cd mathare
python manage.py runserver 0.0.0.0:8001
```

Then open the app in your browser:

- Main map: http://127.0.0.1:8001/
- High-risk dashboard: http://127.0.0.1:8001/high-risk/
- Tasks dashboard: http://127.0.0.1:8001/tasks/

---

## 11. Main routes and features

### Web pages

- /
  - Public-facing interactive map.

- /high-risk/
  - High-risk dashboard view.

- /tasks/
  - Maintenance task dashboard.

### APIs and endpoints

- /api/layers/mathare-floods/
  - Returns GeoJSON for the flood-risk map layer.

- /api/wards/<fid>/detail/
  - Returns ward-level detail information such as POIs, road lengths, waterways, and registered users.

- /ussd/register/
  - Africa’s Talking USSD endpoint for registration and reporting.

- /tasks/public-summary/
  - Public-safe task summary endpoint.

- /high-risk/public/
  - Public-safe high-risk summary endpoint.

---

## 12. Data model and GIS assumptions

This project assumes that the GIS data is already present in a spatial database. The Django models are connected to existing tables rather than newly generated ones for most geographic layers.

That means:

- the database schema must already contain the required GIS tables,
- spatial imports must have been done beforehand,
- the models reflect the column structure used by the imported data.

If the underlying data structure changes, the unmanaged model definitions may need to be updated.

---

## 13. Development notes

### Current implementation highlights

- The app is focused on flood-risk communication and operational reporting rather than a generic GIS dashboard.
- The UI emphasizes clarity, actionability, and a strong public-facing narrative.
- The data layer is intentionally designed to support both map exploration and field response workflows.

### Design philosophy

The project aims to make complex flood-risk and infrastructure data easier to understand for both the public and operational staff:

- residents can report problems quickly,
- staff can review those problems in a structured way,
- decision-makers can see the broader risk context through the map and summary views.

---

## 14. Security and operational considerations

Because this project handles location data, user registration, and potentially sensitive operational information, keep the following in mind:

- never commit real API keys, passwords, or database credentials to version control,
- keep secrets in environment variables or a secure secrets manager,
- review access to the USSD/SMS endpoints carefully,
- ensure the production database and web server are properly secured.

---

## 15. Suggested next steps

Future enhancements could include:

- adding user authentication for staff workflows,
- improving the map styling and risk classification logic,
- adding export/reporting tools for tasks and incidents,
- integrating more advanced GIS analysis or early-warning indicators,
- adding automated tests for views, models, and USSD workflows.

---

## 16. Contributor section

Contributions are welcome.

If you would like to contribute:

1. Fork the repository.
2. Create a feature branch.
3. Make your changes and test them locally.
4. Open a pull request with a clear description of what changed.

Suggested areas for contribution:

- UI and map interaction improvements
- better risk classification logic
- USSD flow enhancements
- documentation and screenshots
- tests for views, forms, and workflow logic

---

## 17. Summary

TerraSat Mathare is a practical, GIS-driven platform for flood-risk awareness and maintenance response in Mathare. It combines public-facing geospatial information, resident reporting via USSD, and staff dashboards into a single coherent system aimed at turning local observations and spatial analysis into actionable response work.
