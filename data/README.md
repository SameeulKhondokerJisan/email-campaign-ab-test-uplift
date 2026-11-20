# Data

| File | Source | Licence / terms |
|---|---|---|
| `raw/hillstrom_email_campaign.csv` | Kevin Hillstrom, MineThatData E-Mail Analytics and Data Mining Challenge (2008). Downloaded from http://www.minethatdata.com by `src/download_data.py`. | Published by the author for public analysis; not redistributed here. |

`make data` downloads the file (about 4 MB) and writes `raw/MANIFEST.json` with its size and SHA-256.
`make pipeline` builds `processed/campaign.duckdb`. Both folders are git-ignored.

64,000 customers who purchased in the last 12 months were randomly assigned (1/3 each) to a
Mens merchandise e-mail, a Womens merchandise e-mail, or no e-mail. Outcomes were tracked for two
weeks after the send. See `docs/data_dictionary.md` for every column.
