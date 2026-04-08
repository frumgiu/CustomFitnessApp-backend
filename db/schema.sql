-- Tabelle dati salute (iOS HealthKit bridge)

CREATE TABLE IF NOT EXISTS health_steps (
    date    TEXT PRIMARY KEY,   -- "yyyy-MM-dd"
    steps   INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS health_sleep (
    date                    TEXT PRIMARY KEY,   -- "yyyy-MM-dd" del risveglio
    sleep_start             TEXT NOT NULL,      -- ISO 8601 UTC
    sleep_end               TEXT NOT NULL,      -- ISO 8601 UTC
    total_sleep_minutes     INTEGER NOT NULL,
    deep_sleep_minutes      INTEGER,
    rem_sleep_minutes       INTEGER,
    core_sleep_minutes      INTEGER
);

CREATE TABLE IF NOT EXISTS health_heart_rate_samples (
    timestamp   TEXT PRIMARY KEY,   -- ISO 8601 UTC
    bpm         REAL NOT NULL,
    source      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS health_daily_heart_rate (
    date        TEXT PRIMARY KEY,   -- "yyyy-MM-dd"
    avg_bpm     REAL NOT NULL,
    min_bpm     REAL NOT NULL,
    max_bpm     REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS health_resting_heart_rate (
    date    TEXT PRIMARY KEY,   -- "yyyy-MM-dd"
    bpm     REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS health_hrv (
    timestamp   TEXT PRIMARY KEY,   -- ISO 8601 UTC
    sdnn_ms     REAL NOT NULL       -- millisecondi
);

CREATE TABLE IF NOT EXISTS health_active_energy (
    date    TEXT PRIMARY KEY,   -- "yyyy-MM-dd"
    kcal    REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS health_workouts (
    id                      TEXT PRIMARY KEY,   -- UUID stringa
    activity_type           TEXT NOT NULL,
    start_date              TEXT NOT NULL,      -- ISO 8601 UTC
    end_date                TEXT NOT NULL,      -- ISO 8601 UTC
    duration_seconds        REAL NOT NULL,
    total_energy_kcal       REAL,
    total_distance_meters   REAL,
    source_name             TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS health_menstrual_flow (
    date        TEXT PRIMARY KEY,   -- "yyyy-MM-dd"
    flow_level  TEXT NOT NULL       -- 'not_present' | 'unspecified' | 'light' | 'medium' | 'heavy'
);

-- Log delle sync ricevute dall'app iOS
CREATE TABLE IF NOT EXISTS health_sync_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    synced_at   TEXT NOT NULL   -- ISO 8601 UTC: campo synced_at del payload iOS
);

-- Metriche aggregate giornaliere: fitness (CTL/ATL/TSB), recupero, sonno, baselines
CREATE TABLE IF NOT EXISTS analytics_daily (
    date             TEXT PRIMARY KEY,   -- "yyyy-MM-dd"
    daily_load       REAL NOT NULL DEFAULT 0,
    ctl              REAL,              -- Chronic Training Load (fitness, tau=42gg)
    atl              REAL,              -- Acute Training Load (fatica, tau=7gg)
    tsb              REAL,              -- Training Stress Balance = CTL - ATL
    acwr             REAL,             -- Acute:Chronic Workload Ratio
    recovery_score   REAL,             -- 0-100, composto da HRV/RHR/sonno/TSB
    sleep_score      REAL,             -- 0-100, basato su durata/deep/REM
    -- Baselines e delta HRV (finestra 7 giorni)
    hrv_baseline     REAL,
    hrv_delta        REAL,
    hrv_zscore       REAL,
    -- Baselines e delta resting HR (finestra 14 giorni)
    rhr_baseline     REAL,
    rhr_delta        REAL,
    -- Baselines e delta sonno (finestra 28 giorni)
    sleep_baseline   REAL,
    sleep_delta      REAL,
    computed_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_analytics_daily_date ON analytics_daily (date);

-- Profilo atleta — singleton modificabile dall'utente (settings)
CREATE TABLE IF NOT EXISTS athlete_profile (
    id          INTEGER PRIMARY KEY CHECK (id = 1),
    name        TEXT,
    sex         TEXT NOT NULL DEFAULT 'F',   -- 'M' | 'F'
    birthday    TEXT,                         -- "yyyy-MM-dd"
    weight_kg   REAL,
    height_cm   REAL,
    max_hr      INTEGER,
    updated_at  TEXT NOT NULL
);

-- Metriche derivate per singolo workout HealthKit (sostituisce analytics_activity)
CREATE TABLE IF NOT EXISTS analytics_workout (
    workout_id          TEXT PRIMARY KEY,   -- riferimento a health_workouts.id
    training_load       REAL,              -- TRIMP o stima energetica
    load_method         TEXT,              -- 'bannister' | 'energy' | NULL
    efficiency_factor   REAL,              -- speed / avg_hr (NULL: no HR da HealthKit)
    equivalent_dist_km  REAL,             -- distanza equivalente Naismith (hiking)
    trail_effort        REAL,             -- indice effort (hiking)
    computed_at         TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_health_menstrual_flow_date   ON health_menstrual_flow (date);
CREATE INDEX IF NOT EXISTS idx_health_steps_date            ON health_steps (date);
CREATE INDEX IF NOT EXISTS idx_health_sleep_date            ON health_sleep (date);
CREATE INDEX IF NOT EXISTS idx_health_hr_samples_ts         ON health_heart_rate_samples (timestamp);
CREATE INDEX IF NOT EXISTS idx_health_resting_hr_date       ON health_resting_heart_rate (date);
CREATE INDEX IF NOT EXISTS idx_health_hrv_ts                ON health_hrv (timestamp);
CREATE INDEX IF NOT EXISTS idx_health_workouts_start        ON health_workouts (start_date);
CREATE INDEX IF NOT EXISTS idx_health_workouts_type         ON health_workouts (activity_type);
