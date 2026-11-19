"""Reading the NPPES bulk file: rows become API-shaped records the importer understands."""

import csv
import io
import zipfile
from pathlib import Path

from app.import_nppes import read_records, to_record
from app.services.npi import PRESETS, practices_from_results

LOC = "Provider Business Practice Location Address"
HEADER = [
    "NPI", "Entity Type Code", "Provider Organization Name (Legal Business Name)",
    "Provider Last Name (Legal Name)", "Provider First Name", "Provider Credential Text",
    "Provider Other Organization Name", "Provider Other Organization Name Type Code",
    "Provider First Line Business Practice Location Address",
    "Provider Second Line Business Practice Location Address",
    f"{LOC} City Name", f"{LOC} State Name", f"{LOC} Postal Code", f"{LOC} Telephone Number",
    "NPI Deactivation Date", "NPI Reactivation Date",
    "Healthcare Provider Taxonomy Code_1", "Healthcare Provider Primary Taxonomy Switch_1",
]  # fmt: skip


def _row(npi: str, last: str, cred: str, zip9: str, phone: str, code: str, **extra: str) -> dict:
    row = dict.fromkeys(HEADER, "")
    row.update({
        "NPI": npi, "Entity Type Code": "1", "Provider Last Name (Legal Name)": last,
        "Provider First Name": "ANA", "Provider Credential Text": cred,
        "Provider First Line Business Practice Location Address": "44045 RIVERSIDE PKWY",
        f"{LOC} City Name": "ASHBURN", f"{LOC} State Name": "VA", f"{LOC} Postal Code": zip9,
        f"{LOC} Telephone Number": phone, "Healthcare Provider Taxonomy Code_1": code,
        "Healthcare Provider Primary Taxonomy Switch_1": "Y",
    })  # fmt: skip
    row.update(extra)
    return row


ROWS = [
    _row("1", "RAO", "M.D.", "201473416", "7037261234", "208000000X"),  # pediatrician
    _row("2", "KIM", "CPNP", "201473416", "7035550000", "363LP0200X"),  # NP, pediatrics
    _row(
        "3",
        "OLD",
        "MD",
        "201473416",
        "7035551111",
        "208000000X",
        **{"NPI Deactivation Date": "01/01/2020"},
    ),  # fmt: skip
    _row("4", "FAR", "MD", "232201234", "8045550000", "208000000X"),  # Richmond
    _row(
        "5", "MD", "MD", "201470000", "7035552222", "208000000X", **{f"{LOC} State Name": "MD"}
    ),  # fmt: skip
]


def test_plain_pediatrics_is_found() -> None:
    record = to_record(ROWS[0])
    assert record["taxonomies"] == [{"code": "208000000X", "desc": "Pediatrics", "primary": True}]
    records = [to_record(r) for r in ROWS]
    names = [p.name for p in practices_from_results(records, "20147", PRESETS["pediatricians"])]
    assert names == ["Dr. Ana Rao, MD"]


def test_read_records_from_zip(tmp_path: Path) -> None:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=HEADER, quoting=csv.QUOTE_ALL)
    writer.writeheader()
    writer.writerows(ROWS)
    path = tmp_path / "nppes.zip"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("npidata_pfile_20050523-20261102.csv", buffer.getvalue())
        zf.writestr("npidata_pfile_20050523-20261102_fileheader.csv", "x")
    by_zip = read_records(str(path), {"20147"})
    assert list(by_zip) == ["20147"]
    assert [r["number"] for r in by_zip["20147"]] == ["1", "2", "3"]
