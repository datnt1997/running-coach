-- Keep the average heart rate so the zone is computed from the current profile at read time.
ALTER TABLE activity_analyses ADD COLUMN avg_hr_bpm NUMERIC(5,1);
