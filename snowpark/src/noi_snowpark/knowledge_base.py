"""Synthetic knowledge base articles and firmware release notes.

Fixed content (no randomness) so search evaluations always have the same
"right answer" documents. All products and versions are fictional and match
the generator: APs AX-200/400/600 on 10.1.4/10.2.1/10.3.0, switches
SW-24P/48P/CORE on 8.4.2/8.5.1.
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

# (id, title, product_models, firmware_version, category, days_before_as_of, body)
KB_ARTICLES = [
    ("KB-1001", "Known issue: client roaming failures on AP firmware 10.2.1",
     "AX-200, AX-400, AX-600", "10.2.1", "Wi-Fi roaming", 75,
     "Symptom: wireless clients disconnect or stall when moving between access points. Voice calls "
     "and voice badges drop while walking between floors, and logs show repeated reassociation failures. "
     "Cause: a regression in 802.11r fast transition key caching introduced in AP firmware 10.2.1. "
     "Workaround: disable 802.11r fast transition on affected SSIDs until you can upgrade. "
     "Resolution: upgrade access points to firmware 10.3.0, which contains the fix."),
    ("KB-1002", "Troubleshooting 802.1X authentication timeouts",
     "AX-200, AX-400, AX-600", None, "Authentication / RADIUS", 400,
     "Symptom: users intermittently fail 802.1X login and the RADIUS server logs show timeouts. "
     "Check that the RADIUS shared secret matches on the access point profile and the server, confirm "
     "the server is reachable from the AP management network, and raise the RADIUS timeout to 5 seconds "
     "with 3 retries. Expired server certificates cause the same symptom for EAP-TLS clients."),
    ("KB-1003", "Guest captive portal redirect loop",
     "AX-200, AX-400, AX-600", None, "Authentication / RADIUS", 320,
     "Symptom: the guest portal login page reloads in a loop on some devices while the staff SSID works. "
     "Most loops come from HTTPS redirect handling. Enable HTTP redirect on the guest profile and add the "
     "portal domain to the walled garden so the browser can load it before authentication."),
    ("KB-1004", "Switch port flapping: diagnosis steps",
     "SW-24P, SW-48P, SW-CORE", "8.4.2", "Switch port flapping", 210,
     "Symptom: access ports or uplinks go down and up repeatedly, disconnecting downstream access points. "
     "Check cabling and SFP modules first, then the PoE power budget on the switch. Disable Energy "
     "Efficient Ethernet on ports serving access points. Switch firmware 8.4.2 has a known PoE "
     "renegotiation issue that causes port flaps with some access points; it is fixed in 8.5.1."),
    ("KB-1005", "AX-200 end of sale: upgrade path to the AX-400",
     "AX-200", None, "Hardware lifecycle", 120,
     "The AX-200 access point reaches end of sale on 2026-12-31. Support and firmware updates continue "
     "for five years after end of sale. The recommended replacement is the AX-400, which uses the same "
     "mounting bracket. Plan replacements site by site and keep the same SSID profiles to avoid client changes."),
    ("KB-1006", "Planning a firmware upgrade maintenance window",
     None, None, "Firmware upgrade", 500,
     "Upgrade in stages: start with a canary group of about 10 percent of devices at one site, monitor for "
     "24 hours, then roll out by site. Back up configuration before upgrading, schedule outside business "
     "hours, and confirm a rollback plan. Access points reboot once during the upgrade."),
    ("KB-1007", "Firmware upgrade stalls or rolls back to the previous image",
     None, None, "Firmware upgrade", 260,
     "Symptom: an upgrade stops partway and the device reboots to its previous firmware. Rolling back is a "
     "safety feature when the new image fails verification. Common causes are low flash space and an "
     "interrupted download. Remove old images, then retry the upgrade from the cloud dashboard."),
    ("KB-1008", "High channel utilization and slow Wi-Fi in dense areas",
     "AX-200, AX-400, AX-600", None, "Slow Wi-Fi performance", 350,
     "Symptom: users report slow Wi-Fi at peak hours and channel utilization stays above 80 percent. "
     "Enable band steering to move capable clients to 5 GHz, turn off some 2.4 GHz radios in dense areas, "
     "use 20 or 40 MHz channel widths, and add access points where more than 40 clients share one radio."),
    ("KB-1009", "Devices show as unlicensed after onboarding",
     None, None, "Licensing", 280,
     "Licenses are assigned from the customer subscription. If new devices show as unlicensed, sync the "
     "subscription in the cloud dashboard. If the subscription has fewer licenses than onboarded devices, "
     "contact your partner or the renewals team to add capacity."),
    ("KB-1010", "RMA: replacing a failed or dead device",
     None, None, "Hardware failure", 600,
     "For a device with no power or repeated failures, collect the serial number and recent logs and open "
     "a case requesting an RMA. Premier tier customers receive advance replacement shipped the next "
     "business day; Standard tier replacements ship after the failed unit is received."),
    ("KB-1011", "Access point reboots with thermal warnings",
     "AX-200, AX-400, AX-600", None, "Hardware failure", 190,
     "Symptom: an access point reboots randomly and logs show thermal warnings first. Check that the AP is "
     "not mounted in an enclosed space, that ambient temperature is within the rated range, and that "
     "plenum-rated mounting is used above ceilings. Firmware 10.3.0 improves thermal throttling."),
    ("KB-1012", "Best practices for Wi-Fi in hospitals",
     "AX-400, AX-600", "10.3.0", "Design guide", 150,
     "Clinical voice badges and mobile carts need fast, reliable roaming. Run access points on firmware "
     "10.3.0 or later with 802.11r enabled, place a separate SSID for medical IoT devices, and survey "
     "patient floors for coverage in elevators and stairwells."),
    ("KB-1013", "Best practices for high-density venues",
     "AX-600", None, "Design guide", 230,
     "Stadiums and arenas need many small cells: under-seat or handrail access points, directional "
     "antennas, and 5 GHz and 6 GHz for capacity. Plan for tens of thousands of simultaneous clients "
     "during events and disable low data rates."),
    ("KB-1014", "Wi-Fi design for K-12 classrooms",
     "AX-200, AX-400", None, "Design guide", 300,
     "Place one access point per classroom for device-heavy lessons, enable content filtering on the "
     "student SSID, and tune minimum RSSI so Chromebooks roam to the nearest access point."),
    ("KB-1015", "How uptime and degraded device-days are calculated",
     None, None, "Reporting", 90,
     "Uptime percent is the share of each day a device was reachable, from 0 to 100. A degraded "
     "device-day is any day a device's uptime falls below 99 percent. Wi-Fi metrics such as roaming and "
     "authentication failures apply only to access points."),
]

RELEASE_NOTES = [
    ("RN-AP-10.1.4", "Access point firmware 10.1.4 release notes",
     "AX-200, AX-400, AX-600", "10.1.4", "Release note", 420,
     "Improvements: general stability and faster boot time. Known issue: channel changes after radar "
     "detection on DFS channels can take longer than expected."),
    ("RN-AP-10.2.1", "Access point firmware 10.2.1 release notes",
     "AX-200, AX-400, AX-600", "10.2.1", "Release note", 160,
     "New: WPA3-Enterprise enhancements and improved client analytics. Known issue: clients may fail to "
     "roam between access points when 802.11r fast transition is enabled; see KB-1001."),
    ("RN-AP-10.3.0", "Access point firmware 10.3.0 release notes",
     "AX-200, AX-400, AX-600", "10.3.0", "Release note", 70,
     "Fixed: client roaming failures with 802.11r fast transition introduced in 10.2.1. Fixed: improved "
     "thermal throttling to prevent reboots in hot environments. Recommended upgrade for all devices on 10.2.x."),
    ("RN-SW-8.4.2", "Switch firmware 8.4.2 release notes",
     "SW-24P, SW-48P, SW-CORE", "8.4.2", "Release note", 380,
     "Improvements: LACP stability. Known issue: PoE renegotiation can cause access ports to flap with "
     "some access points."),
    ("RN-SW-8.5.1", "Switch firmware 8.5.1 release notes",
     "SW-24P, SW-48P, SW-CORE", "8.5.1", "Release note", 110,
     "Fixed: PoE renegotiation causing port flapping with access points. Improved: LLDP neighbor discovery "
     "and faster uplink failover."),
]

COLUMNS = ["DOC_ID", "TITLE", "PRODUCT_MODELS", "FIRMWARE_VERSION", "CATEGORY", "PUBLISHED_DATE", "BODY"]


def _to_frame(rows, as_of: date) -> pd.DataFrame:
    records = [
        (doc_id, title, models, fw, category, pd.Timestamp(as_of - timedelta(days=age)), body)
        for doc_id, title, models, fw, category, age, body in rows
    ]
    return pd.DataFrame(records, columns=COLUMNS)


def build_kb_articles(as_of: date) -> pd.DataFrame:
    return _to_frame(KB_ARTICLES, as_of)


def build_release_notes(as_of: date) -> pd.DataFrame:
    return _to_frame(RELEASE_NOTES, as_of)
