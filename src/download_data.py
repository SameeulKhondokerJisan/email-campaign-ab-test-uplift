"""Download Kevin Hillstrom's MineThatData E-Mail Analytics Challenge data into data/raw/.

Source: http://www.minethatdata.com (dataset page:
https://blog.minethatdata.com/2008/03/minethatdata-e-mail-analytics-and-data.html).
64,000 customers randomly assigned to a Mens e-mail, a Womens e-mail, or no e-mail.

Usage:
    python -m src.download_data
"""
from __future__ import annotations

from pathlib import Path

from src._fetch import fetch, sha256, write_manifest

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
URL = "http://www.minethatdata.com/Kevin_Hillstrom_MineThatData_E-MailAnalytics_DataMiningChallenge_2008.03.20.csv"
DEST = RAW / "hillstrom_email_campaign.csv"


def main() -> None:
    path = fetch(URL, DEST)
    write_manifest(RAW, [{"file": path.name, "bytes": path.stat().st_size, "sha256": sha256(path), "url": URL}])
    print(f"ok  {path.name}  {path.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
