"""Import every doctor and dentist in Northern Virginia from the NPPES bulk file.

The NPI Registry search API misses providers (for example most pediatricians whose
specialty is plain "Pediatrics"), so a complete import reads CMS's monthly full file:
https://download.cms.gov/nppes/NPI_Files.html ("Full Replacement Monthly NPI File",
about 1 GB zipped, 12 GB unzipped). It is read straight from the zip, without unpacking.

    python -m app.import_nppes /app/data_imports/nppes.zip [--zips 20147,20148] [--dry-run]

Entries are created and updated exactly like the admin page's NPI import (same keys,
grouping, categories, removed entries stay removed), as the first admin's profile.
"""

import argparse
import csv
import io
import re
import sys
import time
import zipfile
from collections import Counter, defaultdict
from typing import Any

from sqlalchemy import select

from app.api.routes.imports import doctor_categories, save_practices
from app.db.session import get_sessionmaker
from app.models import Profile
from app.models.enums import UserRole
from app.services.npi import DEFAULT_ZIPS, PRESETS, practices_from_results
from app.services.nucc_taxonomy import TAXONOMY_DESCRIPTIONS

MAIN_FILE = re.compile(r"^npidata_pfile_[\d-]+\.csv$")
DBA = "3"  # "Provider Other Organization Name Type Code": doing business as
TAXONOMY_SLOTS = 15


def _main_member(zf: zipfile.ZipFile) -> str:
    names = [n for n in zf.namelist() if MAIN_FILE.match(n.rsplit("/", 1)[-1])]
    if len(names) != 1:
        sys.exit(f"Expected one npidata_pfile_*.csv in the zip, found {names}")
    return names[0]


def to_record(row: dict[str, str]) -> dict[str, Any]:
    """A bulk-file row in the shape the NPI Registry API returns (what npi.py reads)."""
    taxonomies = []
    for i in range(1, TAXONOMY_SLOTS + 1):
        code = row.get(f"Healthcare Provider Taxonomy Code_{i}", "")
        if code:
            taxonomies.append(
                {
                    "code": code,
                    "desc": TAXONOMY_DESCRIPTIONS.get(code, ""),
                    "primary": row.get(f"Healthcare Provider Primary Taxonomy Switch_{i}") == "Y",
                }
            )
    dba = row.get("Provider Other Organization Name", "")
    deactivated = row.get("NPI Deactivation Date") and not row.get("NPI Reactivation Date")
    loc = "Provider Business Practice Location Address"
    return {
        "number": row["NPI"],
        "enumeration_type": "NPI-1" if row.get("Entity Type Code") == "1" else "NPI-2",
        "basic": {
            "first_name": row.get("Provider First Name", ""),
            "last_name": row.get("Provider Last Name (Legal Name)", ""),
            "credential": row.get("Provider Credential Text", ""),
            "organization_name": row.get("Provider Organization Name (Legal Business Name)", ""),
            "status": "D" if deactivated else "A",
        },
        "other_names": (
            [{"type": "Doing Business As", "organization_name": dba}]
            if dba and row.get("Provider Other Organization Name Type Code") == DBA
            else []
        ),
        "addresses": [
            {
                "address_purpose": "LOCATION",
                "address_1": row.get("Provider First Line Business Practice Location Address", ""),
                "address_2": row.get("Provider Second Line Business Practice Location Address", ""),
                "city": row.get(f"{loc} City Name", ""),
                "state": row.get(f"{loc} State Name", ""),
                "postal_code": row.get(f"{loc} Postal Code", ""),
                "telephone_number": row.get(f"{loc} Telephone Number", ""),
            }
        ],
        "taxonomies": taxonomies,
    }


def read_records(path: str, zips: set[str]) -> dict[str, list[dict[str, Any]]]:
    """Records whose practice location is in `zips` (VA), grouped by ZIP."""
    # Cheap text test before full CSV parsing: 12 GB is mostly other states.
    hint = re.compile(r'"VA","(' + "|".join(sorted(zips)) + r")")
    by_zip: dict[str, list[dict[str, Any]]] = defaultdict(list)
    started, seen = time.time(), 0
    with zipfile.ZipFile(path) as zf, zf.open(_main_member(zf)) as raw:
        lines = io.TextIOWrapper(raw, encoding="utf-8", errors="replace", newline="")
        header = next(csv.reader([next(lines)]))
        for line in lines:
            seen += 1
            if seen % 1_000_000 == 0:
                print(f"  read {seen:,} rows ({int(time.time() - started)}s)", flush=True)
            if not hint.search(line):
                continue
            values = next(csv.reader([line]))
            if len(values) != len(header):
                continue
            row = dict(zip(header, values, strict=True))
            loc = "Provider Business Practice Location Address"
            zip5 = row[f"{loc} Postal Code"][:5]
            if row[f"{loc} State Name"] == "VA" and zip5 in zips:
                by_zip[zip5].append(to_record(row))
    return by_zip


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("path", help="NPPES_Data_Dissemination_<Month>_<Year>_V2.zip")
    parser.add_argument("--zips", help="comma-separated ZIPs (default: all Northern Virginia)")
    parser.add_argument("--dry-run", action="store_true", help="count only, save nothing")
    args = parser.parse_args()
    zips = set(args.zips.split(",")) if args.zips else set(DEFAULT_ZIPS)

    print(f"Reading {args.path} for {len(zips)} ZIPs…", flush=True)
    by_zip = read_records(args.path, zips)
    print(f"{sum(len(v) for v in by_zip.values()):,} provider records in those ZIPs", flush=True)

    totals: Counter[str] = Counter()
    with get_sessionmaker()() as db:
        admin = db.scalars(select(Profile).where(Profile.role == UserRole.ADMIN)).first()
        if admin is None:
            sys.exit("No admin profile: sign in once and make yourself admin first")
        categories = doctor_categories(db)
        for zip5 in sorted(by_zip):
            for preset in PRESETS.values():
                practices = practices_from_results(by_zip[zip5], zip5, preset)
                totals[preset.key] += len(practices)
                if args.dry_run or not practices:
                    continue
                totals.update(save_practices(db, practices, admin, categories))
            if not args.dry_run:
                db.commit()
            print(f"  {zip5}: done", flush=True)
    print("Practices per type:", {k: totals[k] for k in PRESETS})
    print(
        "Saved:",
        {k: totals[k] for k in ("created", "updated", "already_listed", "skipped_removed")},
    )


if __name__ == "__main__":
    main()
