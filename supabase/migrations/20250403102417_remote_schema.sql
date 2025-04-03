
alter table "public"."workflows" drop constraint "workflows_project_id_fkey";

alter table "public"."workflows" drop constraint "workflows_status_check";

alter table "public"."workflows" add constraint "workflows_project_id_fkey" FOREIGN KEY (project_id) REFERENCES projects(id) ON UPDATE CASCADE ON DELETE CASCADE not valid;

alter table "public"."workflows" validate constraint "workflows_project_id_fkey";

alter table "public"."workflows" add constraint "workflows_status_check" CHECK (((status)::text = ANY ((ARRAY['active'::character varying, 'archived'::character varying, 'draft'::character varying])::text[]))) not valid;

alter table "public"."workflows" validate constraint "workflows_status_check";


