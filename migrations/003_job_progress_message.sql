-- Job progress message for polling UI
ALTER TABLE job ADD COLUMN progress_message TEXT DEFAULT '';
