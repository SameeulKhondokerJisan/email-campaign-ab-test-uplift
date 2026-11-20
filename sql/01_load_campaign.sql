-- 01_load_campaign.sql
-- Load the raw Hillstrom CSV into a typed DuckDB table.
-- {raw_csv} is replaced with the absolute path by src/data.py.
CREATE OR REPLACE TABLE campaign AS
SELECT
    CAST(recency AS INTEGER)    AS recency,          -- months since last purchase (1-12)
    history_segment,                                 -- past-year spend band, e.g. '2) $100 - $200'
    CAST(history AS DOUBLE)     AS history,          -- dollars spent in the past year
    CAST(mens AS INTEGER)       AS mens,             -- 1 = bought mens merchandise in the past year
    CAST(womens AS INTEGER)     AS womens,           -- 1 = bought womens merchandise in the past year
    CASE WHEN zip_code = 'Surburban' THEN 'Suburban' ELSE zip_code END
                                AS zip_code,         -- Urban / Suburban / Rural (fixes the source typo 'Surburban')
    CAST(newbie AS INTEGER)     AS newbie,           -- 1 = new customer in the past 12 months
    channel,                                         -- Phone / Web / Multichannel
    segment,                                         -- randomized arm as published
    CASE segment
        WHEN 'Mens E-Mail'   THEN 'Mens'
        WHEN 'Womens E-Mail' THEN 'Womens'
        WHEN 'No E-Mail'     THEN 'Control'
    END                         AS arm,
    CAST(visit AS INTEGER)      AS visit,            -- visited the website within 2 weeks
    CAST(conversion AS INTEGER) AS conversion,       -- purchased within 2 weeks
    CAST(spend AS DOUBLE)       AS spend             -- dollars spent within 2 weeks
FROM read_csv_auto('{raw_csv}', header = true);
