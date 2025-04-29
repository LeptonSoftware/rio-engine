alter table "public"."process_locks" drop constraint "process_locks_workflow_id_key";

alter table "public"."workflows" drop constraint "workflows_status_check";

drop index if exists "public"."process_locks_workflow_id_key";

alter table "public"."process_locks" alter column "workflow_id" drop not null;

CREATE UNIQUE INDEX process_locks_project_id_key ON public.process_locks USING btree (project_id);

alter table "public"."process_locks" add constraint "process_locks_project_id_key" UNIQUE using index "process_locks_project_id_key";

alter table "public"."workflows" add constraint "workflows_status_check" CHECK (((status)::text = ANY ((ARRAY['active'::character varying, 'archived'::character varying, 'draft'::character varying])::text[]))) not valid;

alter table "public"."workflows" validate constraint "workflows_status_check";

set check_function_bodies = off;

CREATE OR REPLACE FUNCTION public.handle_storage_changes()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
AS $function$
begin
  perform pg_notify(
    'storage_changes',
    json_build_object(
      'event', TG_OP,
      'record', row_to_json(NEW)
    )::text
  );
  return NEW;
end;
$function$
;


