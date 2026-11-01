"""Synthetic data generator for the Network Ops Insights Agent.

Produces a realistic, fully fictional networking customer base:
partners, customers, sites, devices (access points and switches),
daily device health, support cases with free-text descriptions,
subscriptions, knowledge base articles and firmware release notes.

Planted signals the agent should be able to find later:
  * Access points on firmware 10.2.1 have ~4x more roaming failures and
    generate most "Wi-Fi roaming" support cases.
  * Model AX-200 reaches end of sale on 2026-12-31.
  * A handful of customers have subscriptions renewing in the next 90 days
    while also having open critical (P1/P2) cases.

Run locally:
    uv run python -m noi_snowpark.generate_data --dry-run        # CSVs to ./data, no Snowflake
    uv run python -m noi_snowpark.generate_data --env dev        # load NOI_DEV.RAW

In Stage 6 the same `generate_tables` function is wrapped in a Snowpark
stored procedure, so the logic lives in one place.
"""

from __future__ import annotations

import argparse
import os
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from faker import Faker

from noi_snowpark.knowledge_base import build_kb_articles, build_release_notes

# --------------------------------------------------------------------------
# Reference data (all names are invented)
# --------------------------------------------------------------------------
INDUSTRIES = {
    # industry: (site types, sites per customer range, APs per site range)
    "Healthcare": (["Hospital", "Clinic"], (3, 8), (25, 60)),
    "Higher Education": (["Campus", "Residence Hall"], (2, 6), (30, 70)),
    "K-12 Education": (["School"], (4, 10), (10, 25)),
    "Manufacturing": (["Plant", "Warehouse"], (2, 5), (10, 30)),
    "Retail": (["Store", "Distribution Center"], (5, 12), (4, 12)),
    "Hospitality": (["Hotel"], (2, 6), (20, 45)),
    "State and Local Government": (["Office", "Library"], (3, 7), (8, 20)),
    "Sports and Venues": (["Stadium", "Arena"], (1, 2), (80, 150)),
}
NAME_SUFFIX = {
    "Healthcare": ["Health System", "Medical Center", "Health Partners"],
    "Higher Education": ["University", "State College", "Institute of Technology"],
    "K-12 Education": ["Unified School District", "Public Schools", "County Schools"],
    "Manufacturing": ["Manufacturing", "Industries", "Fabrication Co"],
    "Retail": ["Outfitters", "Market Group", "Home Goods"],
    "Hospitality": ["Hotels & Resorts", "Hospitality Group", "Inns"],
    "State and Local Government": ["County", "City Government", "Public Services"],
    "Sports and Venues": ["Arena Group", "Stadium Authority", "Event Center"],
}
REGIONS = ["North America East", "North America West", "EMEA", "APAC"]

AP_MODELS = {"AX-200": "2026-12-31", "AX-400": "2029-06-30", "AX-600": "2031-03-31"}
SWITCH_MODELS = {"SW-24P": "2028-09-30", "SW-48P": "2030-01-31", "SW-CORE": "2031-12-31"}
AP_FIRMWARE = ["10.1.4", "10.2.1", "10.3.0"]
SWITCH_FIRMWARE = ["8.4.2", "8.5.1"]
BUGGY_AP_FIRMWARE = "10.2.1"

CASE_CATEGORIES = [
    "Wi-Fi roaming", "Authentication / RADIUS", "Switch port flapping",
    "Firmware upgrade", "Hardware failure", "Licensing", "Slow Wi-Fi performance",
]
SEVERITIES = ["P1", "P2", "P3", "P4"]
RESOLUTION_HOURS = {"P1": (2, 12), "P2": (6, 48), "P3": (24, 120), "P4": (48, 240)}

CASE_TEXT = {
    "Wi-Fi roaming": [
        "Clients drop connection when moving between access points in the {site_type}. "
        "Issue started after upgrading {model} access points to firmware {fw}.",
        "Voice calls on mobile devices cut out while walking between floors. "
        "Roaming logs show repeated reassociation failures on {model} running {fw}.",
    ],
    "Authentication / RADIUS": [
        "Users intermittently fail 802.1X authentication. RADIUS server shows timeouts "
        "from {model} access points at the {site_type}.",
        "Guest portal login loops back to the start page for some devices. Staff SSID unaffected.",
    ],
    "Switch port flapping": [
        "Access ports on {model} switch flap several times per hour, disconnecting downstream APs.",
        "Uplink on {model} goes down and up repeatedly. Suspect cabling or SFP at the {site_type}.",
    ],
    "Firmware upgrade": [
        "Requesting guidance on upgrading {model} from {fw}. Need a maintenance window plan.",
        "Firmware upgrade on {model} stalled at 80 percent and device rebooted to previous image.",
    ],
    "Hardware failure": [
        "{model} at the {site_type} is unresponsive and shows no power LED. Requesting RMA.",
        "Device {model} reboots randomly. Logs show thermal warnings before each reboot.",
    ],
    "Licensing": [
        "New devices added at the {site_type} show as unlicensed in the cloud dashboard.",
        "Subscription renewal shows fewer device licenses than devices onboarded.",
    ],
    "Slow Wi-Fi performance": [
        "Users report slow Wi-Fi during peak hours in the {site_type}. Channel utilization above 80 percent.",
        "Throughput on {model} drops sharply when more than 40 clients are connected.",
    ],
}


# --------------------------------------------------------------------------
# Table builders: pure pandas, no Snowflake dependency
# --------------------------------------------------------------------------
def build_partners(rng: np.random.Generator, fake: Faker) -> pd.DataFrame:
    rows = []
    for i in range(1, 9):
        rows.append({
            "PARTNER_ID": f"PTR-{i:03d}",
            "PARTNER_NAME": f"{fake.last_name()} {rng.choice(['Networks', 'IT Services', 'Solutions', 'Technologies'])}",
            "PARTNER_TYPE": "MSP" if i % 3 == 0 else "Reseller",
            "REGION": REGIONS[(i - 1) % len(REGIONS)],
        })
    return pd.DataFrame(rows)


def build_customers(rng, fake, partners: pd.DataFrame, as_of: date, n: int = 40) -> pd.DataFrame:
    industries = list(INDUSTRIES)
    rows = []
    for i in range(1, n + 1):
        industry = industries[(i - 1) % len(industries)]
        partner = partners.sample(1, random_state=int(rng.integers(1e9))).iloc[0]
        rows.append({
            "CUSTOMER_ID": f"CUST-{i:04d}",
            "CUSTOMER_NAME": f"{fake.city()} {rng.choice(NAME_SUFFIX[industry])}",
            "INDUSTRY": industry,
            "REGION": partner["REGION"],
            "PARTNER_ID": partner["PARTNER_ID"],
            "CONTRACT_TIER": "Premier" if rng.random() < 0.35 else "Standard",
            "CREATED_AT": pd.Timestamp(as_of - timedelta(days=int(rng.integers(200, 2500)))),
        })
    return pd.DataFrame(rows)


def build_sites(rng, fake, customers: pd.DataFrame) -> pd.DataFrame:
    rows, n = [], 0
    for c in customers.itertuples():
        site_types, (lo, hi), _ = INDUSTRIES[c.INDUSTRY]
        for _ in range(int(rng.integers(lo, hi + 1))):
            n += 1
            site_type = str(rng.choice(site_types))
            rows.append({
                "SITE_ID": f"SITE-{n:05d}",
                "CUSTOMER_ID": c.CUSTOMER_ID,
                "SITE_NAME": f"{fake.street_name()} {site_type}",
                "SITE_TYPE": site_type,
                "CITY": fake.city(),
                "COUNTRY": "United States" if c.REGION.startswith("North America") else fake.country(),
            })
    return pd.DataFrame(rows)


def build_devices(rng, sites: pd.DataFrame, customers: pd.DataFrame, as_of: date) -> pd.DataFrame:
    industry_by_customer = customers.set_index("CUSTOMER_ID")["INDUSTRY"]
    rows, n = [], 0
    for s in sites.itertuples():
        _, _, (ap_lo, ap_hi) = INDUSTRIES[industry_by_customer[s.CUSTOMER_ID]]
        # Firmware is mostly consistent within a site, like real rollouts
        site_ap_fw = str(rng.choice(AP_FIRMWARE, p=[0.35, 0.30, 0.35]))
        site_sw_fw = str(rng.choice(SWITCH_FIRMWARE))
        n_aps = int(rng.integers(ap_lo, ap_hi + 1))
        n_switches = max(1, n_aps // 12)
        for kind, count, models, fw in (
            ("access_point", n_aps, AP_MODELS, site_ap_fw),
            ("switch", n_switches, SWITCH_MODELS, site_sw_fw),
        ):
            for _ in range(count):
                n += 1
                model = str(rng.choice(list(models)))
                rows.append({
                    "DEVICE_ID": f"DEV-{n:06d}",
                    "SITE_ID": s.SITE_ID,
                    "DEVICE_TYPE": kind,
                    "MODEL": model,
                    "FIRMWARE_VERSION": fw if rng.random() < 0.9 else str(rng.choice(
                        AP_FIRMWARE if kind == "access_point" else SWITCH_FIRMWARE)),
                    "INSTALL_DATE": pd.Timestamp(as_of - timedelta(days=int(rng.integers(90, 1800)))),
                    "END_OF_SALE_DATE": pd.Timestamp(models[model]),
                })
    return pd.DataFrame(rows)


def build_device_health(rng, devices: pd.DataFrame, as_of: date, days: int) -> pd.DataFrame:
    """One row per device per day. Vectorized for speed (~hundreds of thousands of rows)."""
    dates = pd.date_range(end=pd.Timestamp(as_of) - pd.Timedelta(days=1), periods=days, freq="D")
    n_dev, n_day = len(devices), len(dates)
    total = n_dev * n_day

    is_ap = np.repeat((devices["DEVICE_TYPE"] == "access_point").to_numpy(), n_day)
    buggy = np.repeat((devices["FIRMWARE_VERSION"] == BUGGY_AP_FIRMWARE).to_numpy(), n_day) & is_ap
    weekday = np.tile(dates.dayofweek.to_numpy() < 5, n_dev)

    outage = rng.random(total) < 0.008
    uptime = np.where(outage, rng.uniform(55, 98.5, total), rng.uniform(99.5, 100.0, total))

    clients = np.where(is_ap, rng.poisson(np.where(weekday, 28, 14)), rng.integers(8, 48, total))
    disconnects = rng.poisson(np.where(outage, 25, np.where(buggy, 6, 2)))
    auth_fail = np.where(is_ap, rng.poisson(3, total), 0)
    roam_fail = np.where(is_ap, rng.poisson(np.where(buggy, 8, 2)), 0)

    df = pd.DataFrame({
        "DEVICE_ID": np.repeat(devices["DEVICE_ID"].to_numpy(), n_day),
        "METRIC_DATE": np.tile(dates.to_numpy(), n_dev),
        "UPTIME_PCT": uptime.round(3),
        "CPU_PCT": rng.normal(35, 12, total).clip(2, 99).round(1),
        "CLIENT_COUNT": clients,
        "DISCONNECT_COUNT": disconnects,
        "AUTH_FAILURE_COUNT": auth_fail,
        "ROAMING_FAILURE_COUNT": roam_fail,
    })
    # Wi-Fi metrics don't apply to switches: store as NULL, not zero
    for col in ("AUTH_FAILURE_COUNT", "ROAMING_FAILURE_COUNT"):
        df[col] = df[col].astype("Int64").mask(~is_ap)
    return df


def build_support_cases(rng, devices, sites, as_of: date, days: int, n: int = 650) -> pd.DataFrame:
    dev = devices.merge(sites[["SITE_ID", "CUSTOMER_ID", "SITE_TYPE"]], on="SITE_ID")
    # Buggy-firmware APs are 3x more likely to have a case; switches 2x (fewer of them, more critical)
    weights = np.select(
        [dev["FIRMWARE_VERSION"] == BUGGY_AP_FIRMWARE, dev["DEVICE_TYPE"] == "switch"], [3.0, 2.0], default=1.0)
    picked = dev.sample(n, replace=True, weights=weights, random_state=int(rng.integers(1e9)))

    rows = []
    for i, d in enumerate(picked.itertuples(), start=1):
        if d.FIRMWARE_VERSION == BUGGY_AP_FIRMWARE and rng.random() < 0.5:
            category = "Wi-Fi roaming"
        elif d.DEVICE_TYPE == "switch":
            category = str(rng.choice(["Switch port flapping", "Firmware upgrade", "Hardware failure", "Licensing"]))
        else:
            category = str(rng.choice([c for c in CASE_CATEGORIES if c != "Switch port flapping"]))
        severity = str(rng.choice(SEVERITIES, p=[0.06, 0.18, 0.46, 0.30]))
        opened = pd.Timestamp(as_of) - pd.Timedelta(minutes=int(rng.integers(30, days * 24 * 60)))
        lo, hi = RESOLUTION_HOURS[severity]
        closed = opened + pd.Timedelta(hours=float(rng.uniform(lo, hi)))
        is_open = closed > pd.Timestamp(as_of) or rng.random() < 0.08
        text = str(rng.choice(CASE_TEXT[category])).format(
            site_type=d.SITE_TYPE.lower(), model=d.MODEL, fw=d.FIRMWARE_VERSION)
        rows.append({
            "CASE_ID": f"CASE-{i:06d}",
            "CUSTOMER_ID": d.CUSTOMER_ID,
            "SITE_ID": d.SITE_ID,
            "DEVICE_ID": d.DEVICE_ID,
            "OPENED_AT": opened,
            "CLOSED_AT": pd.NaT if is_open else closed,
            "STATUS": "Open" if is_open else "Closed",
            "SEVERITY": severity,
            "CATEGORY": category,
            "PRODUCT_MODEL": d.MODEL,
            "FIRMWARE_VERSION": d.FIRMWARE_VERSION,
            "SUBJECT": f"{category}: {d.MODEL} at {d.SITE_TYPE}",
            "DESCRIPTION": text,
        })
    return pd.DataFrame(rows)


def build_subscriptions(rng, customers, devices, sites, as_of: date) -> pd.DataFrame:
    device_counts = devices.merge(sites[["SITE_ID", "CUSTOMER_ID"]], on="SITE_ID").groupby("CUSTOMER_ID").size()
    rows, n = [], 0
    for c in customers.itertuples():
        products = ["Cloud Management"] + (["Premier Support"] if c.CONTRACT_TIER == "Premier" else [])
        for product in products:
            n += 1
            term_years = int(rng.choice([1, 3], p=[0.6, 0.4]))
            # Spread end dates from 30 days ago to ~2 years out; ~20% renew within 90 days
            end = as_of + timedelta(days=int(rng.integers(-30, 730)) if rng.random() > 0.2 else int(rng.integers(5, 90)))
            per_device = 45 if product == "Cloud Management" else 30
            rows.append({
                "SUBSCRIPTION_ID": f"SUB-{n:05d}",
                "CUSTOMER_ID": c.CUSTOMER_ID,
                "PRODUCT": product,
                "TERM_YEARS": term_years,
                "START_DATE": pd.Timestamp(end - timedelta(days=365 * term_years)),
                "END_DATE": pd.Timestamp(end),
                "ANNUAL_VALUE_USD": round(float(device_counts.get(c.CUSTOMER_ID, 0) * per_device * rng.uniform(0.85, 1.15)), 2),
            })
    return pd.DataFrame(rows)


def generate_tables(as_of: date, days: int = 60, seed: int = 42) -> dict[str, pd.DataFrame]:
    """Build every RAW table. Same seed + as_of = identical data, which evals rely on."""
    rng = np.random.default_rng(seed)
    fake = Faker("en_US")
    Faker.seed(seed)

    partners = build_partners(rng, fake)
    customers = build_customers(rng, fake, partners, as_of)
    sites = build_sites(rng, fake, customers)
    devices = build_devices(rng, sites, customers, as_of)
    return {
        "PARTNERS": partners,
        "CUSTOMERS": customers,
        "SITES": sites,
        "DEVICES": devices,
        "DEVICE_HEALTH_DAILY": build_device_health(rng, devices, as_of, days),
        "SUPPORT_CASES": build_support_cases(rng, devices, sites, as_of, days),
        "SUBSCRIPTIONS": build_subscriptions(rng, customers, devices, sites, as_of),
        "KB_ARTICLES": build_kb_articles(as_of),
        "RELEASE_NOTES": build_release_notes(as_of),
    }


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------
ENVIRONMENTS = {
    "dev": {"database": "NOI_DEV", "role": "NOI_DBT_DEV", "warehouse": "NOI_WH_DEV"},
    "prod": {"database": "NOI_PROD", "role": "NOI_DBT_PROD", "warehouse": "NOI_WH_PROD"},
}


def write_to_snowflake(session, tables: dict[str, pd.DataFrame], database: str | None = None,
                       schema: str | None = None) -> dict[str, int]:
    """Replace each RAW table. Used locally and inside the GENERATE_DATA stored procedure.

    database/schema: set explicitly inside a procedure, where the session's current schema is the
    procedure's own schema (OPS), not RAW. Returns row counts per table.
    """
    counts = {}
    for name, df in tables.items():
        session.write_pandas(
            df, table_name=name, database=database, schema=schema,
            auto_create_table=True, overwrite=True, use_logical_type=True,
        )
        counts[name] = len(df)
        print(f"  loaded {name:<22} {len(df):>8,} rows")
    return counts


def create_session(env: str, role: str | None = None, secondary_roles: bool = True):
    """Key-pair session from environment variables (same ones dbt uses).

    role: override the environment's default role (persona tests run as partner roles).
    secondary_roles=False: run USE SECONDARY ROLES NONE, so the session has ONLY `role`'s
    privileges. Persona tests need this; otherwise your other roles leak into the session.
    """
    from snowflake.snowpark import Session  # imported here so --dry-run needs no Snowflake libs

    cfg = ENVIRONMENTS[env]
    session = Session.builder.configs({
        "account": os.environ["SNOWFLAKE_ACCOUNT"],
        "user": os.environ["SNOWFLAKE_USER"],
        "authenticator": "SNOWFLAKE_JWT",
        "private_key_file": os.environ["SNOWFLAKE_PRIVATE_KEY_PATH"],
        "role": role or cfg["role"],
        "warehouse": cfg["warehouse"],
        "database": cfg["database"],
        "schema": "RAW",
    }).create()
    if not secondary_roles:
        session.sql("use secondary roles none").collect()
    return session


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic network operations data.")
    parser.add_argument("--env", choices=list(ENVIRONMENTS), default="dev")
    parser.add_argument("--days", type=int, default=60, help="days of device health history")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today(), help="YYYY-MM-DD")
    parser.add_argument("--dry-run", action="store_true", help="write CSVs to ./data instead of Snowflake")
    args = parser.parse_args()

    print(f"Generating data as of {args.as_of} ({args.days} days, seed {args.seed})")
    tables = generate_tables(args.as_of, args.days, args.seed)

    if args.dry_run:
        out = Path("data")
        out.mkdir(exist_ok=True)
        for name, df in tables.items():
            df.to_csv(out / f"{name.lower()}.csv", index=False)
            print(f"  wrote data/{name.lower()}.csv {len(df):>8,} rows")
        return

    session = create_session(args.env)
    try:
        print(f"Loading into {ENVIRONMENTS[args.env]['database']}.RAW as {ENVIRONMENTS[args.env]['role']}")
        write_to_snowflake(session, tables)
    finally:
        session.close()


if __name__ == "__main__":
    main()
