-- -------------------------------------------------------------
-- TablePlus 6.1.8(574)
--
-- https://tableplus.com/
--
-- Database: postgres
-- Generation Time: 2024-12-11 01:08:34.3430
-- -------------------------------------------------------------


INSERT INTO "storage"."buckets" ("id", "name", "owner", "created_at", "updated_at", "public", "avif_autodetection", "file_size_limit", "allowed_mime_types", "owner_id") VALUES
('avatars', 'avatars', NULL, '2024-10-07 09:24:29.167737+00', '2024-10-07 09:24:29.167737+00', 't', 'f', NULL, NULL, NULL),
('logos', 'logos', NULL, '2023-04-10 14:33:38.868824+00', '2023-04-10 14:33:38.868824+00', 't', 'f', NULL, NULL, NULL),
('project-templates', 'project-templates', NULL, '2024-09-24 07:34:02.79065+00', '2024-09-24 07:34:02.79065+00', 'f', 'f', NULL, NULL, NULL),
('projects', 'projects', NULL, '2024-08-30 05:48:19.645052+00', '2024-08-30 05:48:19.645052+00', 'f', 'f', 52428800, NULL, NULL),
('smart-market-ops-cache', 'smart-market-ops-cache', NULL, '2024-08-27 09:38:17.895106+00', '2024-08-27 09:38:17.895106+00', 't', 'f', NULL, NULL, NULL),
('smart-market-upload-file', 'smart-market-upload-file', NULL, '2024-08-02 11:19:22.23905+00', '2024-08-02 11:19:22.23905+00', 't', 'f', NULL, NULL, NULL);

