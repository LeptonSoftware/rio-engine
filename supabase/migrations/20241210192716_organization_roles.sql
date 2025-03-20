-- -------------------------------------------------------------
-- TablePlus 6.1.8(574)
--
-- https://tableplus.com/
--
-- Database: postgres
-- Generation Time: 2024-12-11 00:55:53.8450
-- -------------------------------------------------------------


INSERT INTO "public"."organization_role_permissions" ("id", "organization_role", "permission", "is_granted", "created_at", "updated_at") VALUES
(1, 'admin', 'org.projects.manage_access', 't', '2024-09-22 12:51:21.016526+00', '2024-09-22 12:51:21.016526+00'),
(2, 'admin', 'org.users.delete', 't', '2024-11-26 07:34:37+00', '2024-11-26 07:34:43+00'),
(3, 'admin', 'org.users.invite_access', 't', '2024-11-28 05:40:50.982504+00', '2024-11-28 05:40:50.982504+00'),
(4, 'analyst', 'org.users.invite_access', 'f', '2024-11-28 05:42:35.536015+00', '2024-11-28 05:42:35.536015+00'),
(5, 'admin', 'org.users.approve_members_on_signup', 't', '2024-11-28 06:00:07.25398+00', '2024-11-28 06:00:07.25398+00'),
(7, 'analyst', 'org.project.create', 't', '2024-11-28 06:25:50.990062+00', '2024-11-28 06:25:50.990062+00'),
(8, 'admin', 'org.project.create', 't', '2024-11-28 06:26:07.108182+00', '2024-11-28 06:26:07.108182+00'),
(9, 'admin', 'org.project.duplicate', 't', '2024-11-28 11:46:55.170893+00', '2024-11-28 11:46:55.170893+00'),
(10, 'analyst', 'org.project.duplicate', 't', '2024-11-28 11:50:47.084733+00', '2024-11-28 11:50:47.084733+00'),
(11, 'admin', 'org.project.edit', 't', '2024-11-28 11:51:11.214059+00', '2024-11-28 11:51:11.214059+00'),
(12, 'analyst', 'org.project.edit', 't', '2024-11-28 11:51:28.846833+00', '2024-11-28 11:51:28.846833+00'),
(13, 'admin', 'org.project.manage_access', 't', '2024-11-28 11:52:07.757324+00', '2024-11-28 11:52:07.757324+00'),
(14, 'analyst', 'org.project.manage_access', 't', '2024-11-28 11:52:28.878086+00', '2024-11-28 11:52:28.878086+00'),
(15, 'admin', 'org.project.create_template', 't', '2024-11-28 11:53:05.080671+00', '2024-11-28 11:53:05.080671+00'),
(16, 'analyst', 'org.project.create_template', 't', '2024-11-28 11:53:23.836427+00', '2024-11-28 11:53:23.836427+00'),
(17, 'admin', 'org.project.delete', 't', '2024-11-28 11:53:54.304123+00', '2024-11-28 11:53:54.304123+00'),
(18, 'analyst', 'org.project.delete', 't', '2024-11-28 11:54:11.803708+00', '2024-11-28 11:54:11.803708+00'),
(20, 'admin', 'org.project.get_editor_access', 't', '2024-11-29 05:49:35.471418+00', '2024-11-29 05:49:35.471418+00'),
(21, 'analyst', 'org.project.get_editor_access', 't', '2024-11-29 05:49:55.794696+00', '2024-11-29 05:49:55.794696+00'),
(22, 'admin', 'org.users.view_analyst_license_usage', 't', '2024-12-03 05:47:07.206679+00', '2024-12-03 05:47:07.206679+00'),
(24, 'viewer', 'org.project.create', 'f', '2024-12-03 06:54:32.314371+00', '2024-12-03 06:54:32.314371+00'),
(26, 'admin', 'org.users.revert_analyst_access', 'f', '2024-12-05 07:57:25.761422+00', '2024-12-05 07:57:25.761422+00');


