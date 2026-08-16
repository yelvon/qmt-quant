-- Instrument table is the canonical code/name registry (cached from QMT).
-- Index rows that still need a name fetch after bar sync.

CREATE INDEX IF NOT EXISTS idx_instrument_name_missing
    ON instrument (code)
    WHERE name IS NULL
       OR btrim(name) = ''
       OR name = code
       OR name = split_part(code, '.', 1);

ANALYZE instrument;
