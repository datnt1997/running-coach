-- Zones use heart-rate reserve (max and resting HR); the lactate-threshold HR is no longer kept.
ALTER TABLE runner_profiles DROP COLUMN IF EXISTS lactate_threshold_hr;
