revoke delete on table "public"."connections" from "supabase_auth_admin";

revoke insert on table "public"."connections" from "supabase_auth_admin";

revoke references on table "public"."connections" from "supabase_auth_admin";

revoke select on table "public"."connections" from "supabase_auth_admin";

revoke trigger on table "public"."connections" from "supabase_auth_admin";

revoke truncate on table "public"."connections" from "supabase_auth_admin";

revoke update on table "public"."connections" from "supabase_auth_admin";

revoke delete on table "public"."datasets" from "supabase_auth_admin";

revoke insert on table "public"."datasets" from "supabase_auth_admin";

revoke references on table "public"."datasets" from "supabase_auth_admin";

revoke select on table "public"."datasets" from "supabase_auth_admin";

revoke trigger on table "public"."datasets" from "supabase_auth_admin";

revoke truncate on table "public"."datasets" from "supabase_auth_admin";

revoke update on table "public"."datasets" from "supabase_auth_admin";

revoke delete on table "public"."workflows" from "supabase_auth_admin";

revoke insert on table "public"."workflows" from "supabase_auth_admin";

revoke references on table "public"."workflows" from "supabase_auth_admin";

revoke select on table "public"."workflows" from "supabase_auth_admin";

revoke trigger on table "public"."workflows" from "supabase_auth_admin";

revoke truncate on table "public"."workflows" from "supabase_auth_admin";

revoke update on table "public"."workflows" from "supabase_auth_admin";

create table "public"."process_locks" (
    "lock_id" text not null,
    "locked_by" text not null,
    "locked_at" timestamp with time zone default CURRENT_TIMESTAMP,
    "project_id" text not null,
    "workflow_id" text not null
);


create table "public"."workflow_runs" (
    "id" uuid not null default gen_random_uuid(),
    "dag_run_id" text not null,
    "output_hashkey" text,
    "created_at" timestamp with time zone,
    "config" jsonb not null,
    "workflow_id" text,
    "status" text
);


create table "public"."workflow_templates" (
    "created_at" timestamp with time zone not null default now(),
    "title" text not null,
    "description" text,
    "category" text,
    "visibility" text,
    "id" text not null,
    "user_id" uuid,
    "organization_id" uuid default gen_random_uuid()
);


alter table "public"."workflow_templates" enable row level security;

alter table "public"."dataset" drop column "last updated";

alter table "public"."dataset" drop column "update frequence";

alter table "public"."dataset" add column "last_updated" text;

alter table "public"."dataset" add column "update_frequency" text;

alter table "public"."workflows" drop column "metadata";

alter table "public"."workflows" add column "config" jsonb;

alter table "public"."workflows" add column "created_by" character varying(255);

alter table "public"."workflows" add column "dag_created" boolean not null default false;

alter table "public"."workflows" add column "description" text;

alter table "public"."workflows" add column "last_executed" timestamp with time zone;

alter table "public"."workflows" add column "org_id" uuid;

alter table "public"."workflows" add column "project_id" bigint;

alter table "public"."workflows" add column "status" character varying(50) default 'active'::character varying;

alter table "public"."workflows" add column "user_id" uuid not null;

alter table "public"."workflows" add column "version" integer not null default 1;

alter table "public"."workflows" add column "workflow_id" text;

alter table "public"."workflows" alter column "name" set not null;

alter table "public"."workflows" alter column "name" set data type character varying(255) using "name"::character varying(255);

alter table "public"."workflows" alter column "updated_at" set not null;

CREATE INDEX idx_process_locks_project ON public.process_locks USING btree (project_id);

CREATE UNIQUE INDEX process_locks_pkey ON public.process_locks USING btree (lock_id);

CREATE UNIQUE INDEX process_locks_workflow_id_key ON public.process_locks USING btree (workflow_id);

CREATE INDEX user_sessions_idx_user_id ON public.user_sessions USING btree (user_id);

CREATE UNIQUE INDEX workflow_runs_pkey ON public.workflow_runs USING btree (id);

CREATE UNIQUE INDEX workflow_templates_pkey ON public.workflow_templates USING btree (id);

CREATE UNIQUE INDEX workflows_workflow_id_key ON public.workflows USING btree (workflow_id);

alter table "public"."process_locks" add constraint "process_locks_pkey" PRIMARY KEY using index "process_locks_pkey";

alter table "public"."workflow_runs" add constraint "workflow_runs_pkey" PRIMARY KEY using index "workflow_runs_pkey";

alter table "public"."workflow_templates" add constraint "workflow_templates_pkey" PRIMARY KEY using index "workflow_templates_pkey";

alter table "public"."process_locks" add constraint "process_locks_workflow_id_key" UNIQUE using index "process_locks_workflow_id_key";

alter table "public"."workflow_runs" add constraint "workflow_runs_workflow_id_fkey" FOREIGN KEY (workflow_id) REFERENCES workflows(workflow_id) not valid;

alter table "public"."workflow_runs" validate constraint "workflow_runs_workflow_id_fkey";

alter table "public"."workflows" add constraint "workflows_org_id_fkey" FOREIGN KEY (org_id) REFERENCES organizations(id) not valid;

alter table "public"."workflows" validate constraint "workflows_org_id_fkey";

alter table "public"."workflows" add constraint "workflows_project_id_fkey" FOREIGN KEY (project_id) REFERENCES projects(id) not valid;

alter table "public"."workflows" validate constraint "workflows_project_id_fkey";

alter table "public"."workflows" add constraint "workflows_status_check" CHECK (((status)::text = ANY ((ARRAY['active'::character varying, 'archived'::character varying, 'draft'::character varying])::text[]))) not valid;

alter table "public"."workflows" validate constraint "workflows_status_check";

alter table "public"."workflows" add constraint "workflows_user_id_fkey" FOREIGN KEY (user_id) REFERENCES profile(user_id) not valid;

alter table "public"."workflows" validate constraint "workflows_user_id_fkey";

alter table "public"."workflows" add constraint "workflows_workflow_id_key" UNIQUE using index "workflows_workflow_id_key";

set check_function_bodies = off;

CREATE OR REPLACE FUNCTION public.get_lepton_console_usage(start_date text, end_date text)
 RETURNS TABLE(user_id uuid, endpoint text, total_hits bigint, average_latency double precision, error_hits bigint)
 LANGUAGE plpgsql
AS $function$BEGIN
    RETURN QUERY
    SELECT 
        credits.user_id, 
        hits.path as endpoint, 
        COUNT(hits.path) AS total_hits, 
        AVG(time_taken) AS average_latency, 
        COUNT(*) FILTER (WHERE status_code >= 400) AS error_hits
    FROM 
        credits 
        JOIN hits ON credits.user_id = hits.user_id
        JOIN public.profile ON credits.user_id = profile.user_id
    WHERE 
        credits.user_id = auth.uid() AND 
        hits.created_at >= (start_date::TIMESTAMP WITH TIME ZONE) AND 
        hits.created_at <= ((end_date::DATE + 1)::TIMESTAMP WITH TIME ZONE)
    GROUP BY 
        credits.user_id, hits.path
    ORDER BY 
        total_hits DESC;
END;$function$
;

CREATE OR REPLACE FUNCTION public.get_city_routes(city_name text)
 RETURNS TABLE(routes jsonb)
 LANGUAGE plpgsql
AS $function$BEGIN
    RETURN QUERY
    SELECT t.routes
    FROM times t
    WHERE t.city = city_name
    AND ABS(EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - t.updated_at)) / 60) <= 30;
END;$function$
;

CREATE OR REPLACE FUNCTION public.get_hit_statistics(start_date timestamp without time zone, end_date timestamp without time zone)
 RETURNS TABLE(path character varying, total_hits integer, average_latency numeric, error_hits integer)
 LANGUAGE plpgsql
AS $function$
BEGIN
    RETURN QUERY
    SELECT 
        path, 
        COUNT(*) AS total_hits, 
        AVG(time_taken) AS average_latency,
        COUNT(*) FILTER (WHERE status_code > 200) AS error_hits
    FROM hits
    WHERE hits.user_id = auth.uid()
        AND created_at BETWEEN get_hit_statistics.start_date AND get_hit_statistics.end_date
    GROUP BY path;
END;
$function$
;

CREATE OR REPLACE FUNCTION public.get_hits_count_past_24_hours()
 RETURNS TABLE(hour_truncated timestamp with time zone, hit_count bigint)
 LANGUAGE plpgsql
AS $function$
BEGIN
  RETURN QUERY
    WITH HourSequence AS (
      SELECT generate_series(
               current_timestamp - interval '23 hours',
               current_timestamp,
               '1 hour'::interval
           ) AS hour_truncated
    )
    SELECT
      hs.hour_truncated,
      COUNT(h.created_at) AS hit_count
    FROM
      HourSequence hs
    LEFT JOIN
      hits h ON hs.hour_truncated <= h.created_at AND h.created_at < hs.hour_truncated + interval '1 hour'
          AND h.user_id = auth.uid()
    GROUP BY
      hs.hour_truncated
    ORDER BY
      hs.hour_truncated;

END;
$function$
;

CREATE OR REPLACE FUNCTION public.get_organization_roles()
 RETURNS text[]
 LANGUAGE plpgsql
AS $function$
BEGIN
    RETURN (SELECT ARRAY_AGG(DISTINCT organization_role) FROM organization_role_permissions);
END;
$function$
;

CREATE OR REPLACE FUNCTION public.get_permissions_by_organization_role(organization_role_value text)
 RETURNS TABLE(permission text, is_granted boolean)
 LANGUAGE plpgsql
AS $function$BEGIN
    RETURN QUERY
    SELECT 
        opr.permission,
        opr.is_granted
    FROM 
        public.organization_role_permissions opr
    WHERE 
        opr.organization_role = organization_role_value;
END;$function$
;

CREATE OR REPLACE FUNCTION public.get_permissions_by_project_role(project_role_value text)
 RETURNS TABLE(permission text, is_granted boolean)
 LANGUAGE plpgsql
AS $function$
BEGIN
    RETURN QUERY
    SELECT 
        opr.permission,
        opr.is_granted
    FROM 
        public.project_role_permissions opr
    WHERE 
        opr.project_role = project_role_value;
END;
$function$
;

CREATE OR REPLACE FUNCTION public.get_project_roles()
 RETURNS text[]
 LANGUAGE plpgsql
AS $function$
BEGIN
    RETURN (SELECT ARRAY_AGG(DISTINCT project_role) FROM project_role_permissions);
END;
$function$
;

CREATE OR REPLACE FUNCTION public.get_projects_by_user_id(p_user_id text)
 RETURNS TABLE(id bigint, title text, user_id uuid, project_role text, role_assigned_at timestamp with time zone, role_updated_at timestamp with time zone, visibility text, organization_id bigint, owner_id uuid, email text, full_name text, avatar_url text)
 LANGUAGE plpgsql
AS $function$
BEGIN
  RETURN
    QUERY
    SELECT 
      p.id AS id, 
      p.title AS title, 
      pr.user_id AS user_id,
      pr.project_role AS project_role,
      pr.created_at AS role_assigned_at,
      pr.updated_at AS role_updated_at,
      p.visibility AS visibility,
      p.organization_id AS organization_id,
      p.user_id AS owner_id,
      prof.email::text AS email,  
      -- Explicitly cast to text
      prof.full_name::text AS full_name,  
      -- Explicitly cast to text
      prof.avatar_url::text AS avatar_url  -- Explicitly cast to text
    FROM
      public.projects p
    LEFT JOIN
      public.project_roles pr ON p.id = pr.project_id
    LEFT JOIN
      public.profile prof ON pr.user_id = prof.user_id
    WHERE
      pr.user_id = p_user_id
      AND (p.visibility <> 'private' OR pr.user_id IS NOT NULL);
END
;
$function$
;

CREATE OR REPLACE FUNCTION public.get_server_time()
 RETURNS timestamp without time zone
 LANGUAGE plpgsql
AS $function$
BEGIN
    RETURN CURRENT_TIMESTAMP;
END;
$function$
;

CREATE OR REPLACE FUNCTION public.get_table(_tbl_type anyelement)
 RETURNS SETOF anyelement
 LANGUAGE plpgsql
AS $function$
BEGIN
   RETURN QUERY EXECUTE format('TABLE %s', pg_typeof(_tbl_type));
END
$function$
;

CREATE OR REPLACE FUNCTION public.get_user_projects_by_organization(p_organization_id uuid, p_user_id uuid)
 RETURNS TABLE(project_id bigint, project_title text, project_created_at timestamp with time zone, project_updated_at timestamp with time zone, shared_with jsonb)
 LANGUAGE plpgsql
AS $function$BEGIN
  RETURN QUERY
  SELECT
    p.id::BIGINT AS project_id,  -- Ensure project_id matches the BIGINT type
    p.title::TEXT AS project_title,  -- Convert to TEXT if necessary
    p.created_at AS project_created_at,
    p.updated_at AS project_updated_at,
    JSON_AGG(
      JSON_BUILD_OBJECT(
        'user_id',
        pr.user_id::TEXT,  -- Convert to TEXT for compatibility
        'role',
        pr.project_role::TEXT  -- Convert to TEXT for compatibility
      )
    )::JSONB AS shared_with  -- Ensure JSONB format
  FROM
    public.projects p
    JOIN public.project_roles pr ON p.id = pr.project_id
  WHERE
    p.organization_id = p_organization_id
    AND p.user_id = p_user_id
    AND pr.project_role <> 'owner'  -- Exclude the owner role
  GROUP BY
    p.id;
END;$function$
;

CREATE OR REPLACE FUNCTION public.is_active_trigger_function()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
  -- Insert the same data into the 'target' table
  -- INSERT INTO public.is_active(user_id) VALUES (NEW.id);

  -- If you want to cancel the insert operation in the 'source' table, uncomment the line below
  -- RETURN NULL;

  -- Return the NEW row to allow the original insert operation on the 'source' table to proceed
  RETURN NEW;
END;
$function$
;

CREATE OR REPLACE FUNCTION public.leave_organization(p_user_id uuid, p_organization_id uuid)
 RETURNS void
 LANGUAGE plpgsql
AS $function$DECLARE
    v_admin_id UUID;
    project_record RECORD;  -- Declare a record variable for the loop
    v_new_owner_id UUID;
BEGIN
    -- Step 1: Get the admin of the organization
    SELECT user_id INTO v_admin_id
    FROM organization_roles
    WHERE organization_id = p_organization_id AND role = 'admin'
    LIMIT 1;

    -- Step 2: Transfer all projects owned by the user to the admin if visibility is internal or public
    UPDATE projects
    SET user_id = v_admin_id
    WHERE user_id = p_user_id 
      AND organization_id = p_organization_id
      AND (visibility = 'internal' OR visibility = 'public');

    -- Step 3: Update project roles for the transferred projects
    UPDATE project_roles
    SET user_id = v_admin_id  -- Assign to the admin
    WHERE user_id = p_user_id  -- Where the user is the current owner
      AND project_id IN (
        SELECT id 
        FROM projects
        WHERE organization_id = p_organization_id
          AND user_id = v_admin_id 
      );

    -- Step 4: Handle projects with private visibility
FOR project_record IN
    SELECT id
    FROM projects
    WHERE user_id = p_user_id 
      AND organization_id = p_organization_id
      AND visibility = 'private'
LOOP
    -- Check if an editor exists to assign as the new owner
    IF EXISTS (
        SELECT 1
        FROM project_roles
        WHERE project_id = project_record.id 
          AND project_role = 'editor'
          AND user_id != p_user_id
    ) THEN
        -- Get the editor's user_id
        SELECT user_id INTO v_new_owner_id
        FROM project_roles
        WHERE project_id = project_record.id 
          AND user_id != p_user_id 
          AND project_role = 'editor'
        LIMIT 1;

        -- Update the project's user_id to the editor's user_id
        UPDATE projects
        SET user_id = v_new_owner_id
        WHERE id = project_record.id
          AND user_id != v_new_owner_id;

        -- Delete all existing roles for new owner
        DELETE FROM project_roles WHERE project_id = project_record.id
          AND user_id = v_new_owner_id;

        -- Update the editor's role to owner in project_roles
        UPDATE project_roles
        SET project_role = 'owner'
        WHERE project_id = project_record.id
          AND user_id = v_new_owner_id
          AND project_role = 'editor';

    ELSE
        -- No editor exists, assign admin as the new owner
        v_new_owner_id := v_admin_id;
        
        -- Delete all existing roles for new owner
        DELETE FROM project_roles WHERE project_id = project_record.id
          AND user_id = v_new_owner_id;

        -- Update the project's user_id to the admin's user_id
        UPDATE projects
        SET user_id = v_new_owner_id
        WHERE id = project_record.id
          AND user_id != v_new_owner_id;

        -- Update the owner role for admin in project_roles
        UPDATE project_roles
        SET user_id = v_new_owner_id
        WHERE project_id = project_record.id
          AND project_role = 'owner'
          AND user_id = p_user_id;
    END IF;
END LOOP;

    DELETE FROM organization_roles
    WHERE user_id = p_user_id 
      AND organization_id = p_organization_id;

    DELETE FROM project_roles
    WHERE user_id = p_user_id;

    RAISE NOTICE 'User % has left organization % and all applicable projects have been transferred to admin %', p_user_id, p_organization_id, v_admin_id;
END;$function$
;

CREATE OR REPLACE FUNCTION public.source_insert_trigger_function()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
  -- Insert the same data into the 'target' table
  INSERT INTO public.credits(user_id,total,consumed) VALUES (NEW.id,50,0);

  -- If you want to cancel the insert operation in the 'source' table, uncomment the line below
  -- RETURN NULL;

  -- Return the NEW row to allow the original insert operation on the 'source' table to proceed
  RETURN NEW;
END;
$function$
;

CREATE OR REPLACE FUNCTION public.transfer_projects_and_remove_user(p_user_id_owner uuid, p_user_id_user uuid, p_organization_id uuid)
 RETURNS void
 LANGUAGE plpgsql
AS $function$BEGIN

    -- Step 1: Transfer all projects to the new owner
    UPDATE projects
    SET user_id = p_user_id_owner
    WHERE user_id = p_user_id_user
      AND organization_id = p_organization_id;



    UPDATE project_roles
    SET user_id = p_user_id_owner
    WHERE user_id = p_user_id_user
      AND project_id IN (
        SELECT id 
        FROM projects
        WHERE organization_id = p_organization_id
      );

    -- Step 2: Remove the user from the organization
    DELETE FROM organization_roles
    WHERE user_id = p_user_id_user
      AND organization_id = p_organization_id;


END$function$
;

grant delete on table "public"."process_locks" to "anon";

grant insert on table "public"."process_locks" to "anon";

grant references on table "public"."process_locks" to "anon";

grant select on table "public"."process_locks" to "anon";

grant trigger on table "public"."process_locks" to "anon";

grant truncate on table "public"."process_locks" to "anon";

grant update on table "public"."process_locks" to "anon";

grant delete on table "public"."process_locks" to "authenticated";

grant insert on table "public"."process_locks" to "authenticated";

grant references on table "public"."process_locks" to "authenticated";

grant select on table "public"."process_locks" to "authenticated";

grant trigger on table "public"."process_locks" to "authenticated";

grant truncate on table "public"."process_locks" to "authenticated";

grant update on table "public"."process_locks" to "authenticated";

grant delete on table "public"."process_locks" to "service_role";

grant insert on table "public"."process_locks" to "service_role";

grant references on table "public"."process_locks" to "service_role";

grant select on table "public"."process_locks" to "service_role";

grant trigger on table "public"."process_locks" to "service_role";

grant truncate on table "public"."process_locks" to "service_role";

grant update on table "public"."process_locks" to "service_role";

grant delete on table "public"."workflow_runs" to "anon";

grant insert on table "public"."workflow_runs" to "anon";

grant references on table "public"."workflow_runs" to "anon";

grant select on table "public"."workflow_runs" to "anon";

grant trigger on table "public"."workflow_runs" to "anon";

grant truncate on table "public"."workflow_runs" to "anon";

grant update on table "public"."workflow_runs" to "anon";

grant delete on table "public"."workflow_runs" to "authenticated";

grant insert on table "public"."workflow_runs" to "authenticated";

grant references on table "public"."workflow_runs" to "authenticated";

grant select on table "public"."workflow_runs" to "authenticated";

grant trigger on table "public"."workflow_runs" to "authenticated";

grant truncate on table "public"."workflow_runs" to "authenticated";

grant update on table "public"."workflow_runs" to "authenticated";

grant delete on table "public"."workflow_runs" to "service_role";

grant insert on table "public"."workflow_runs" to "service_role";

grant references on table "public"."workflow_runs" to "service_role";

grant select on table "public"."workflow_runs" to "service_role";

grant trigger on table "public"."workflow_runs" to "service_role";

grant truncate on table "public"."workflow_runs" to "service_role";

grant update on table "public"."workflow_runs" to "service_role";

grant delete on table "public"."workflow_templates" to "anon";

grant insert on table "public"."workflow_templates" to "anon";

grant references on table "public"."workflow_templates" to "anon";

grant select on table "public"."workflow_templates" to "anon";

grant trigger on table "public"."workflow_templates" to "anon";

grant truncate on table "public"."workflow_templates" to "anon";

grant update on table "public"."workflow_templates" to "anon";

grant delete on table "public"."workflow_templates" to "authenticated";

grant insert on table "public"."workflow_templates" to "authenticated";

grant references on table "public"."workflow_templates" to "authenticated";

grant select on table "public"."workflow_templates" to "authenticated";

grant trigger on table "public"."workflow_templates" to "authenticated";

grant truncate on table "public"."workflow_templates" to "authenticated";

grant update on table "public"."workflow_templates" to "authenticated";

grant delete on table "public"."workflow_templates" to "service_role";

grant insert on table "public"."workflow_templates" to "service_role";

grant references on table "public"."workflow_templates" to "service_role";

grant select on table "public"."workflow_templates" to "service_role";

grant trigger on table "public"."workflow_templates" to "service_role";

grant truncate on table "public"."workflow_templates" to "service_role";

grant update on table "public"."workflow_templates" to "service_role";

create policy "Allow CRUD to all users"
on "public"."workflow_templates"
as permissive
for all
to public
using (true)
with check (true);



create schema if not exists "workflows";


create schema if not exists "world";


create schema if not exists "zero";

create table "zero"."permissions" (
    "permissions" jsonb,
    "hash" text,
    "lock" boolean not null default true
);


create table "zero"."schemaVersions" (
    "minSupportedVersion" integer,
    "maxSupportedVersion" integer,
    "lock" boolean not null default true
);


CREATE UNIQUE INDEX permissions_pkey ON zero.permissions USING btree (lock);

CREATE UNIQUE INDEX "schemaVersions_pkey" ON zero."schemaVersions" USING btree (lock);

alter table "zero"."permissions" add constraint "permissions_pkey" PRIMARY KEY using index "permissions_pkey";

alter table "zero"."schemaVersions" add constraint "schemaVersions_pkey" PRIMARY KEY using index "schemaVersions_pkey";

alter table "zero"."permissions" add constraint "zero_permissions_single_row_constraint" CHECK (lock) not valid;

alter table "zero"."permissions" validate constraint "zero_permissions_single_row_constraint";

alter table "zero"."schemaVersions" add constraint "zero_schema_versions_single_row_constraint" CHECK (lock) not valid;

alter table "zero"."schemaVersions" validate constraint "zero_schema_versions_single_row_constraint";

set check_function_bodies = off;

CREATE OR REPLACE FUNCTION zero.set_permissions_hash()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
  BEGIN
      NEW.hash = md5(NEW.permissions::text);
      RETURN NEW;
  END;
  $function$
;

CREATE TRIGGER on_set_permissions BEFORE INSERT OR UPDATE ON zero.permissions FOR EACH ROW EXECUTE FUNCTION zero.set_permissions_hash();


create schema if not exists "zero_0";

create table "zero_0"."clients" (
    "clientGroupID" text not null,
    "clientID" text not null,
    "lastMutationID" bigint not null,
    "userID" text
);


create table "zero_0"."shardConfig" (
    "publications" text[] not null,
    "ddlDetection" boolean not null,
    "initialSchema" json,
    "lock" boolean not null default true
);


create table "zero_0"."versionHistory" (
    "dataVersion" integer not null,
    "schemaVersion" integer not null,
    "minSafeVersion" integer not null,
    "lock" character(1) not null default 'v'::bpchar
);


CREATE UNIQUE INDEX clients_pkey ON zero_0.clients USING btree ("clientGroupID", "clientID");

CREATE UNIQUE INDEX pk_schema_meta_lock ON zero_0."versionHistory" USING btree (lock);

CREATE UNIQUE INDEX "shardConfig_pkey" ON zero_0."shardConfig" USING btree (lock);

alter table "zero_0"."clients" add constraint "clients_pkey" PRIMARY KEY using index "clients_pkey";

alter table "zero_0"."shardConfig" add constraint "shardConfig_pkey" PRIMARY KEY using index "shardConfig_pkey";

alter table "zero_0"."versionHistory" add constraint "pk_schema_meta_lock" PRIMARY KEY using index "pk_schema_meta_lock";

alter table "zero_0"."shardConfig" add constraint "single_row_shard_config_0" CHECK (lock) not valid;

alter table "zero_0"."shardConfig" validate constraint "single_row_shard_config_0";

alter table "zero_0"."versionHistory" add constraint "ck_schema_meta_lock" CHECK ((lock = 'v'::bpchar)) not valid;

alter table "zero_0"."versionHistory" validate constraint "ck_schema_meta_lock";


