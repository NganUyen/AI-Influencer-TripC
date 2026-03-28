-- Latest disposable schema snapshot for psql-based bootstraps and reviews.
--
-- Production and staging must apply the ordered versioned migrations in this
-- directory instead of replaying this file on a long-lived database.
--
-- This delegates to the rebuilt steady-state bootstrap file so the snapshot
-- stays aligned with the latest migrated shape without carrying its own copy.

\ir ../schema.sql
