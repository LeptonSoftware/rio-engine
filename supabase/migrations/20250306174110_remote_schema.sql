
revoke delete on table "public"."process_locks" from "supabase_auth_admin";

revoke insert on table "public"."process_locks" from "supabase_auth_admin";

revoke references on table "public"."process_locks" from "supabase_auth_admin";

revoke select on table "public"."process_locks" from "supabase_auth_admin";

revoke trigger on table "public"."process_locks" from "supabase_auth_admin";

revoke truncate on table "public"."process_locks" from "supabase_auth_admin";

revoke update on table "public"."process_locks" from "supabase_auth_admin";

revoke delete on table "public"."workflow_runs" from "supabase_auth_admin";

revoke insert on table "public"."workflow_runs" from "supabase_auth_admin";

revoke references on table "public"."workflow_runs" from "supabase_auth_admin";

revoke select on table "public"."workflow_runs" from "supabase_auth_admin";

revoke trigger on table "public"."workflow_runs" from "supabase_auth_admin";

revoke truncate on table "public"."workflow_runs" from "supabase_auth_admin";

revoke update on table "public"."workflow_runs" from "supabase_auth_admin";

revoke delete on table "public"."workflow_templates" from "supabase_auth_admin";

revoke insert on table "public"."workflow_templates" from "supabase_auth_admin";

revoke references on table "public"."workflow_templates" from "supabase_auth_admin";

revoke select on table "public"."workflow_templates" from "supabase_auth_admin";

revoke trigger on table "public"."workflow_templates" from "supabase_auth_admin";

revoke truncate on table "public"."workflow_templates" from "supabase_auth_admin";

revoke update on table "public"."workflow_templates" from "supabase_auth_admin";

alter table "public"."workflows" drop constraint "workflows_status_check";

create table "public"."workflow_uploads" (
    "id" uuid not null,
    "file_name" text not null,
    "file_type" text not null,
    "uploaded_at" timestamp with time zone not null,
    "file_size" bigint not null,
    "workflow_id" text not null,
    "file_path" text not null,
    "created_at" timestamp with time zone default now(),
    "description" text,
    "tags" text[]
);


alter table "public"."api_keys" add column "allowed_endpoints" jsonb;

alter table "public"."datasets" add column "source" jsonb;

alter table "public"."datasets" add column "visibility" text;

alter table "public"."datasets" alter column "slug" drop not null;

alter table "public"."datasets" disable row level security;

CREATE UNIQUE INDEX workflow_uploads_pkey ON public.workflow_uploads USING btree (id);

CREATE INDEX workflow_uploads_workflow_id_idx ON public.workflow_uploads USING btree (workflow_id);

alter table "public"."workflow_uploads" add constraint "workflow_uploads_pkey" PRIMARY KEY using index "workflow_uploads_pkey";

alter table "public"."workflows" add constraint "workflows_status_check" CHECK (((status)::text = ANY ((ARRAY['active'::character varying, 'archived'::character varying, 'draft'::character varying])::text[]))) not valid;

alter table "public"."workflows" validate constraint "workflows_status_check";

set check_function_bodies = off;

CREATE OR REPLACE FUNCTION public.manage_api_key_endpoints(api_key uuid, action text, endpoints jsonb DEFAULT 'null'::jsonb)
 RETURNS jsonb
 LANGUAGE plpgsql
AS $function$
DECLARE
  current_endpoints jsonb;
BEGIN
  IF action = 'list' THEN
    -- Return the current allowed_endpoints for the specified api_key.
    SELECT allowed_endpoints INTO current_endpoints
    FROM api_keys
    WHERE id = api_key;
    RETURN current_endpoints;

  ELSIF action = 'add' THEN
    IF endpoints IS NULL THEN
      RAISE EXCEPTION 'endpoints cannot be null for add action';
    END IF;
    -- If endpoints isn't an array, wrap it in an array.
    IF jsonb_typeof(endpoints) <> 'array' THEN
      endpoints := jsonb_build_array(endpoints);
    END IF;
    -- Append the new endpoint(s) to the allowed_endpoints.
    UPDATE api_keys
    SET allowed_endpoints = COALESCE(allowed_endpoints, '[]'::jsonb) || endpoints
    WHERE id = api_key;
    
    SELECT allowed_endpoints INTO current_endpoints
    FROM api_keys
    WHERE id = api_key;
    RETURN current_endpoints;

  ELSIF action = 'remove' THEN
    IF endpoints IS NULL THEN
      RAISE EXCEPTION 'endpoints cannot be null for remove action';
    END IF;
    -- If endpoints isn't an array, wrap it in an array.
    IF jsonb_typeof(endpoints) <> 'array' THEN
      endpoints := jsonb_build_array(endpoints);
    END IF;
    -- Remove any endpoint(s) in the provided list from allowed_endpoints.
    UPDATE api_keys
    SET allowed_endpoints = (
      SELECT COALESCE(jsonb_agg(e), '[]'::jsonb)
      FROM (
        SELECT e
        FROM jsonb_array_elements_text(allowed_endpoints) AS e
        WHERE e NOT IN (
          SELECT value FROM jsonb_array_elements_text(endpoints) AS t(value)
        )
      ) sub
    )
    WHERE id = api_key;
    
    SELECT allowed_endpoints INTO current_endpoints
    FROM api_keys
    WHERE id = api_key;
    RETURN current_endpoints;

  ELSE
    RAISE EXCEPTION 'Invalid action. Valid actions are list, add, remove';
  END IF;
END;
$function$
;

CREATE OR REPLACE FUNCTION public.manage_api_key_endpoints(api_key_value text, action text, endpoints jsonb DEFAULT 'null'::jsonb)
 RETURNS jsonb
 LANGUAGE plpgsql
AS $function$
DECLARE
  current_endpoints jsonb;
BEGIN
  IF action = 'list' THEN
    -- Return the current allowed_endpoints for the specified api_key.
    SELECT allowed_endpoints INTO current_endpoints
    FROM api_keys
    WHERE api_key = api_key_value;
    RETURN current_endpoints;

  ELSIF action = 'add' THEN
    IF endpoints IS NULL THEN
      RAISE EXCEPTION 'endpoints cannot be null for add action';
    END IF;
    -- If endpoints isn't an array, wrap it in an array.
    IF jsonb_typeof(endpoints) <> 'array' THEN
      endpoints := jsonb_build_array(endpoints);
    END IF;
    -- Append the new endpoint(s) while avoiding duplicates.
    UPDATE api_keys
    SET allowed_endpoints = (
      SELECT COALESCE(jsonb_agg(e), '[]'::jsonb)
      FROM (
        SELECT DISTINCT e
        FROM jsonb_array_elements_text(
          COALESCE(allowed_endpoints, '[]'::jsonb) || endpoints
        ) AS e
      ) sub
    )
    WHERE api_key = api_key_value;
    
    SELECT allowed_endpoints INTO current_endpoints
    FROM api_keys
    WHERE api_key = api_key_value;
    RETURN current_endpoints;

  ELSIF action = 'remove' THEN
    IF endpoints IS NULL THEN
      RAISE EXCEPTION 'endpoints cannot be null for remove action';
    END IF;
    -- If endpoints isn't an array, wrap it in an array.
    IF jsonb_typeof(endpoints) <> 'array' THEN
      endpoints := jsonb_build_array(endpoints);
    END IF;
    -- Remove any endpoint(s) in the provided list from allowed_endpoints.
    UPDATE api_keys
    SET allowed_endpoints = (
      SELECT COALESCE(jsonb_agg(e), '[]'::jsonb)
      FROM (
        SELECT e
        FROM jsonb_array_elements_text(allowed_endpoints) AS e
        WHERE e NOT IN (
          SELECT value FROM jsonb_array_elements_text(endpoints) AS t(value)
        )
      ) sub
    )
    WHERE api_key = api_key_value;
    
    SELECT allowed_endpoints INTO current_endpoints
    FROM api_keys
    WHERE api_key = api_key_value;
    RETURN current_endpoints;

  ELSE
    RAISE EXCEPTION 'Invalid action. Valid actions are list, add, remove';
  END IF;
END;
$function$
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

grant delete on table "public"."workflow_uploads" to "anon";

grant insert on table "public"."workflow_uploads" to "anon";

grant references on table "public"."workflow_uploads" to "anon";

grant select on table "public"."workflow_uploads" to "anon";

grant trigger on table "public"."workflow_uploads" to "anon";

grant truncate on table "public"."workflow_uploads" to "anon";

grant update on table "public"."workflow_uploads" to "anon";

grant delete on table "public"."workflow_uploads" to "authenticated";

grant insert on table "public"."workflow_uploads" to "authenticated";

grant references on table "public"."workflow_uploads" to "authenticated";

grant select on table "public"."workflow_uploads" to "authenticated";

grant trigger on table "public"."workflow_uploads" to "authenticated";

grant truncate on table "public"."workflow_uploads" to "authenticated";

grant update on table "public"."workflow_uploads" to "authenticated";

grant delete on table "public"."workflow_uploads" to "service_role";

grant insert on table "public"."workflow_uploads" to "service_role";

grant references on table "public"."workflow_uploads" to "service_role";

grant select on table "public"."workflow_uploads" to "service_role";

grant trigger on table "public"."workflow_uploads" to "service_role";

grant truncate on table "public"."workflow_uploads" to "service_role";

grant update on table "public"."workflow_uploads" to "service_role";


create table "workflows"."cache_entries" (
    "created_at" timestamp with time zone not null default now(),
    "invalidated_at" timestamp with time zone,
    "table_name" text not null,
    "is_valid" boolean
);


alter table "workflows"."cache_entries" enable row level security;

CREATE UNIQUE INDEX cache_entries_pkey ON workflows.cache_entries USING btree (table_name);

alter table "workflows"."cache_entries" add constraint "cache_entries_pkey" PRIMARY KEY using index "cache_entries_pkey";


