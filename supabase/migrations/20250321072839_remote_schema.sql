revoke delete on table "public"."workflow_uploads" from "supabase_auth_admin";

revoke insert on table "public"."workflow_uploads" from "supabase_auth_admin";

revoke references on table "public"."workflow_uploads" from "supabase_auth_admin";

revoke select on table "public"."workflow_uploads" from "supabase_auth_admin";

revoke trigger on table "public"."workflow_uploads" from "supabase_auth_admin";

revoke truncate on table "public"."workflow_uploads" from "supabase_auth_admin";

revoke update on table "public"."workflow_uploads" from "supabase_auth_admin";

alter table "public"."data_source" drop constraint "data_source_organization_id_fkey";

alter table "public"."workflows" drop constraint "workflows_status_check";

drop function if exists "public"."manage_api_key_endpoints"(api_key uuid, action text, endpoints jsonb);

create table "public"."console_errors" (
    "id" uuid not null default gen_random_uuid(),
    "created_at" timestamp with time zone not null default now(),
    "message" text,
    "url" text,
    "user_id" uuid,
    "user_agent" text,
    "stack" text
);


create table "public"."lat_lng" (
    "_c0" bigint,
    "account_or_bp" text,
    "street_address" text,
    "suburb" text,
    "state" text,
    "pc" double precision,
    "country" text,
    "longitude" double precision,
    "latitude" double precision,
    "out_precisioncode" text,
    "out_sourcedictionary" double precision,
    "out_country" text,
    "out_from_world_fallback" double precision,
    "out_error" double precision,
    "geometry" geometry(Point,4326)
);


alter table "public"."api_keys" alter column "created_at" set default now();

alter table "public"."data_source" drop column "organization_id";

alter table "public"."data_source" add column "org_id" uuid default gen_random_uuid();

CREATE UNIQUE INDEX console_errors_pkey ON public.console_errors USING btree (id);

CREATE INDEX idx_lat_lng_geometry ON public.lat_lng USING gist (geometry);

alter table "public"."console_errors" add constraint "console_errors_pkey" PRIMARY KEY using index "console_errors_pkey";

alter table "public"."console_errors" add constraint "console_errors_user_id_fkey" FOREIGN KEY (user_id) REFERENCES auth.users(id) ON UPDATE CASCADE ON DELETE SET NULL not valid;

alter table "public"."console_errors" validate constraint "console_errors_user_id_fkey";

alter table "public"."data_source" add constraint "data_source_org_id_fkey" FOREIGN KEY (org_id) REFERENCES organizations(id) ON UPDATE CASCADE ON DELETE SET NULL not valid;

alter table "public"."data_source" validate constraint "data_source_org_id_fkey";

alter table "public"."notifications" add constraint "notifications_user_id_fkey" FOREIGN KEY (user_id) REFERENCES auth.users(id) ON UPDATE CASCADE ON DELETE CASCADE not valid;

alter table "public"."notifications" validate constraint "notifications_user_id_fkey";

alter table "public"."workflows" add constraint "workflows_status_check" CHECK (((status)::text = ANY ((ARRAY['active'::character varying, 'archived'::character varying, 'draft'::character varying])::text[]))) not valid;

alter table "public"."workflows" validate constraint "workflows_status_check";

set check_function_bodies = off;

CREATE OR REPLACE FUNCTION public.generate_slug(object_id text, object_type text, meta jsonb)
 RETURNS text
 LANGUAGE plpgsql
AS $function$
DECLARE
    built_slug text;
    base_slug text;
    unique_slug text;
    counter integer := 1;
    id_part text;
BEGIN
    -- Check if there is a valid slug in meta
    IF meta IS NOT NULL AND meta->>'slug' IS NOT NULL THEN
        built_slug := meta->>'slug';
        -- IF slug !~ '^[a-z0-9-_]+$' THEN
        --     RAISE EXCEPTION 'The provided slug ''%s'' is not URL safe.', slug;
        -- END IF;
        IF EXISTS (SELECT 1 FROM world.objects object WHERE object.slug = built_slug) THEN
            RAISE EXCEPTION 'The provided slug ''%s'' is not unique.', built_slug;
        END IF;
        RETURN built_slug;  -- Return the slug if it is valid and unique
    -- If no valid slug, check for name in meta
    ELSIF meta IS NOT NULL AND meta->>'name' IS NOT NULL THEN
        built_slug := lower(regexp_replace(meta->>'name', '[^a-zA-Z0-9]+', '-', 'g'));
        -- IF slug !~ '^[a-z0-9-_]+$' THEN
        --     RAISE EXCEPTION 'The provided slug ''%s'' is not URL safe.', slug;
        -- END IF;
        -- IF EXISTS (SELECT 1 FROM world.objects object WHERE object.slug = built_slug) THEN
        --     RAISE EXCEPTION 'The provided slug ''%s'' is not unique.', built_slug;
        -- END IF;
        RETURN built_slug;  -- Return the slug if it is valid and unique
    ELSE
        -- Fallback to object_type and part of object_id
        base_slug := lower(regexp_replace(object_type, '[^a-zA-Z0-9]+', '-', 'g'));
        id_part := lower(object_id);
        unique_slug := base_slug || '-' || id_part;
        -- WHILE EXISTS (SELECT 1 FROM world.objects object WHERE object.slug = unique_slug) LOOP
        --     id_part := substr(lower(object_id), 1, length(id_part) + 1);
        --     unique_slug := base_slug || '-' || id_part;
        -- END LOOP;
        RETURN unique_slug;  -- Return the unique slug
    END IF;
END;
$function$
;

CREATE OR REPLACE FUNCTION public.jsonb_copy(jsonb, text[], text[])
 RETURNS jsonb
 LANGUAGE plpgsql
AS $function$
DECLARE
  retval ALIAS FOR $1;
  src_path ALIAS FOR $2;
  dst_path ALIAS FOR $3;
  tmp_value JSONB;
BEGIN
  tmp_value = retval#>src_path;
  RETURN jsonb_set(retval, dst_path, tmp_value::JSONB, true);
END;
$function$
;

CREATE OR REPLACE FUNCTION public.jsonb_move(jsonb, text[], text[])
 RETURNS jsonb
 LANGUAGE plpgsql
AS $function$
DECLARE
  retval ALIAS FOR $1;
  src_path ALIAS FOR $2;
  dst_path ALIAS FOR $3;
  tmp_value JSONB;
BEGIN
  tmp_value = retval#>src_path;
  retval = retval #- src_path;
  RETURN jsonb_set(retval, dst_path, tmp_value::JSONB, true);
END;
$function$
;

CREATE OR REPLACE FUNCTION public.jsonb_patch(jsonb, jsonb)
 RETURNS jsonb
 LANGUAGE plpgsql
AS $function$
DECLARE
  retval ALIAS FOR $1;
  patchset ALIAS FOR $2;
  patch_path TEXT[];
  value JSONB;
  chg RECORD;
BEGIN
  FOR chg IN SELECT * FROM jsonb_array_elements(patchset)
  LOOP
    patch_path = regexp_split_to_array(substr(chg.value->>'path', 2), E'/')::TEXT[];
    CASE chg.value->>'op'
      WHEN 'add' THEN retval = jsonb_set(retval, patch_path, (chg.value->'value')::JSONB, true);
      WHEN 'replace' THEN retval = jsonb_set(retval, patch_path, (chg.value->'value')::JSONB, false);
      WHEN 'remove' THEN retval = retval #- patch_path;
      WHEN 'copy' THEN retval = jsonb_copy(retval, regexp_split_to_array(substr(chg.value->>'from', 2), E'/')::TEXT[], patch_path);
      WHEN 'move' THEN retval = jsonb_move(retval, regexp_split_to_array(substr(chg.value->>'from', 2), E'/')::TEXT[], patch_path);
      WHEN 'test' THEN PERFORM jsonb_test(retval, patch_path, (chg.value->'value')::JSONB);
    END CASE;
  END LOOP;
  RETURN retval;
END;
$function$
;

CREATE OR REPLACE FUNCTION public.jsonb_test(jsonb, text[], jsonb)
 RETURNS void
 LANGUAGE plpgsql
AS $function$
DECLARE
  doc ALIAS FOR $1;
  test_path ALIAS FOR $2;
  test_val ALIAS FOR $3;
BEGIN
  IF (doc#>test_path)::JSONB != test_val::JSONB THEN
    RAISE 'Testing % for value % failed', test_path, test_val;
  END IF;
  RETURN;
END;
$function$
;

CREATE OR REPLACE FUNCTION public.track_api_usage_by_key(start_date timestamp with time zone, end_date timestamp with time zone)
 RETURNS TABLE(api_key text, endpoint text, total_hits bigint, average_latency double precision, error_hits bigint)
 LANGUAGE plpgsql
AS $function$
BEGIN
    RETURN QUERY
    SELECT 
        hits.api_key AS api_key, 
        hits.path AS endpoint, 
        COUNT(hits.path) AS total_hits, 
        AVG(hits.time_taken) AS average_latency, 
        COUNT(*) FILTER (WHERE hits.status_code >= 400) AS error_hits
    FROM 
        hits
        JOIN api_keys ON hits.api_key = api_keys.api_key
    WHERE 
        api_keys.user_id = auth.uid() and
        hits.created_at >= start_date
        AND hits.created_at <= (end_date + INTERVAL '1 day')
    GROUP BY 
        hits.api_key, hits.path
    ORDER BY 
        total_hits DESC;
END;
$function$
;

CREATE OR REPLACE FUNCTION public.track_api_usage_by_key(start_date timestamp with time zone, end_date timestamp with time zone, filter_api_key text DEFAULT NULL::text)
 RETURNS TABLE(api_key text, endpoint text, total_hits bigint, average_latency double precision, error_hits bigint)
 LANGUAGE plpgsql
AS $function$
BEGIN
    RETURN QUERY
    SELECT 
        hits.api_key AS api_key, 
        hits.path AS endpoint, 
        COUNT(hits.path) AS total_hits, 
        AVG(hits.time_taken) AS average_latency, 
        COUNT(*) FILTER (WHERE hits.status_code >= 400) AS error_hits
    FROM 
        hits
        JOIN api_keys ON hits.api_key = api_keys.api_key
    WHERE 
        api_keys.user_id = auth.uid() -- Ensure only the authenticated user's API keys are used
        AND hits.created_at >= start_date
        AND hits.created_at <= (end_date + INTERVAL '1 day')
        AND (filter_api_key IS NULL OR hits.api_key = filter_api_key) -- Apply API key filter only if provided
    GROUP BY 
        hits.api_key, hits.path
    ORDER BY 
        total_hits DESC;
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

grant delete on table "public"."console_errors" to "anon";

grant insert on table "public"."console_errors" to "anon";

grant references on table "public"."console_errors" to "anon";

grant select on table "public"."console_errors" to "anon";

grant trigger on table "public"."console_errors" to "anon";

grant truncate on table "public"."console_errors" to "anon";

grant update on table "public"."console_errors" to "anon";

grant delete on table "public"."console_errors" to "authenticated";

grant insert on table "public"."console_errors" to "authenticated";

grant references on table "public"."console_errors" to "authenticated";

grant select on table "public"."console_errors" to "authenticated";

grant trigger on table "public"."console_errors" to "authenticated";

grant truncate on table "public"."console_errors" to "authenticated";

grant update on table "public"."console_errors" to "authenticated";

grant delete on table "public"."console_errors" to "service_role";

grant insert on table "public"."console_errors" to "service_role";

grant references on table "public"."console_errors" to "service_role";

grant select on table "public"."console_errors" to "service_role";

grant trigger on table "public"."console_errors" to "service_role";

grant truncate on table "public"."console_errors" to "service_role";

grant update on table "public"."console_errors" to "service_role";

grant delete on table "public"."lat_lng" to "anon";

grant insert on table "public"."lat_lng" to "anon";

grant references on table "public"."lat_lng" to "anon";

grant select on table "public"."lat_lng" to "anon";

grant trigger on table "public"."lat_lng" to "anon";

grant truncate on table "public"."lat_lng" to "anon";

grant update on table "public"."lat_lng" to "anon";

grant delete on table "public"."lat_lng" to "authenticated";

grant insert on table "public"."lat_lng" to "authenticated";

grant references on table "public"."lat_lng" to "authenticated";

grant select on table "public"."lat_lng" to "authenticated";

grant trigger on table "public"."lat_lng" to "authenticated";

grant truncate on table "public"."lat_lng" to "authenticated";

grant update on table "public"."lat_lng" to "authenticated";

grant delete on table "public"."lat_lng" to "service_role";

grant insert on table "public"."lat_lng" to "service_role";

grant references on table "public"."lat_lng" to "service_role";

grant select on table "public"."lat_lng" to "service_role";

grant trigger on table "public"."lat_lng" to "service_role";

grant truncate on table "public"."lat_lng" to "service_role";

grant update on table "public"."lat_lng" to "service_role";

create policy "Enable update for authenticated users"
on "public"."api_keys"
as permissive
for update
to authenticated
using ((auth.uid() = user_id));



create sequence "world"."slug_redirects_id_seq";

create table "world"."object_changes" (
    "id" bigint generated by default as identity not null,
    "object_id" text not null,
    "change" jsonb not null,
    "version" integer not null,
    "hash" text not null,
    "parent_hash" text,
    "created_at" timestamp with time zone not null default now(),
    "user_id" uuid,
    "organization_id" uuid
);


create table "world"."object_types" (
    "id" integer generated by default as identity not null,
    "type_id" character varying(64) not null,
    "name" text not null,
    "content_type" text not null,
    "definition" jsonb,
    "created_at" timestamp with time zone default CURRENT_TIMESTAMP(6),
    "updated_at" timestamp with time zone default CURRENT_TIMESTAMP(6),
    "deleted_at" timestamp with time zone,
    "created_by" uuid,
    "updated_by" uuid
);


create table "world"."objects" (
    "object_type" character varying(64) not null,
    "object_id" text not null default gen_random_uuid(),
    "version" bigint not null default 1,
    "slug" character varying(128) not null,
    "created_at" timestamp with time zone default CURRENT_TIMESTAMP(6),
    "updated_at" timestamp with time zone default CURRENT_TIMESTAMP(6),
    "deleted_at" timestamp with time zone,
    "created_by" uuid,
    "updated_by" uuid,
    "meta" jsonb,
    "hash" text not null default ''::text
);


create table "world"."slug_redirects" (
    "id" bigint not null default nextval('world.slug_redirects_id_seq'::regclass),
    "old_slug" character varying(128) not null,
    "new_slug" character varying(128) not null,
    "created_at" timestamp with time zone default CURRENT_TIMESTAMP(6)
);


alter sequence "world"."slug_redirects_id_seq" owned by "world"."slug_redirects"."id";

CREATE UNIQUE INDEX object_changes_pkey ON world.object_changes USING btree (id);

CREATE UNIQUE INDEX object_types_pkey ON world.object_types USING btree (id);

CREATE UNIQUE INDEX object_types_uk_type_id ON world.object_types USING btree (type_id);

CREATE UNIQUE INDEX objects_pkey ON world.objects USING btree (object_id);

CREATE UNIQUE INDEX objects_slug_key ON world.objects USING btree (slug);

CREATE UNIQUE INDEX slug_redirects_pkey ON world.slug_redirects USING btree (id);

CREATE UNIQUE INDEX unique_slug_redirect ON world.slug_redirects USING btree (old_slug, new_slug);

alter table "world"."object_changes" add constraint "object_changes_pkey" PRIMARY KEY using index "object_changes_pkey";

alter table "world"."object_types" add constraint "object_types_pkey" PRIMARY KEY using index "object_types_pkey";

alter table "world"."objects" add constraint "objects_pkey" PRIMARY KEY using index "objects_pkey";

alter table "world"."slug_redirects" add constraint "slug_redirects_pkey" PRIMARY KEY using index "slug_redirects_pkey";

alter table "world"."object_changes" add constraint "object_changes_object_id_fkey" FOREIGN KEY (object_id) REFERENCES world.objects(object_id) ON DELETE CASCADE not valid;

alter table "world"."object_changes" validate constraint "object_changes_object_id_fkey";

alter table "world"."object_types" add constraint "object_types_uk_type_id" UNIQUE using index "object_types_uk_type_id";

alter table "world"."objects" add constraint "objects_slug_key" UNIQUE using index "objects_slug_key";

alter table "world"."slug_redirects" add constraint "unique_slug_redirect" UNIQUE using index "unique_slug_redirect";

set check_function_bodies = off;

CREATE OR REPLACE FUNCTION world.add_object_change(p_object_id text, p_change jsonb, p_user_id uuid, p_organization_id uuid)
 RETURNS void
 LANGUAGE plpgsql
AS $function$
DECLARE
    current_version integer;
    current_hash text;
    new_version integer;
    new_hash text;
BEGIN
    -- Retrieve the current version and hash of the object
    SELECT version, hash INTO current_version, current_hash
    FROM world.objects
    WHERE object_id = p_object_id;

    -- Calculate the new version number
    new_version := current_version + 1;

    -- Generate a new hash for the change (you can replace this with your actual hash calculation logic)
    new_hash := md5(p_change::text || current_hash);  -- Example hash calculation

    -- Insert the new change record
    INSERT INTO world.object_changes (object_id, change, version, hash, parent_hash, created_at, user_id, organization_id)
    VALUES (p_object_id, p_change, new_version, new_hash, current_hash, now(), p_user_id, p_organization_id);

    -- Update the hash in the world.objects table
    UPDATE world.objects
    SET version = new_version,
        hash = new_hash,
        updated_at = now()
    WHERE object_id = p_object_id;
END;
$function$
;

CREATE OR REPLACE FUNCTION world.get_applicable_changes(p_object_id text, p_version integer, p_hash text)
 RETURNS TABLE(version integer, hash text, change jsonb, parent_hash text, created_at timestamp with time zone)
 LANGUAGE plpgsql
AS $function$DECLARE
    current_hash text := p_hash;  -- Start with the provided hash
    rec RECORD;                   -- Record variable to hold each row
BEGIN
    -- Retrieve all changes for the specified object before the given version
    FOR rec IN
        SELECT object_change.version, object_change.hash, object_change.change, object_change.parent_hash, object_change.created_at
        FROM world.object_changes object_change
        WHERE object_id = p_object_id 
          AND object_change.version <= p_version
        ORDER BY created_at DESC
    LOOP
        -- Check if the current record's hash matches the current hash or if its parent hash matches
        IF rec.hash = current_hash OR rec.parent_hash = current_hash THEN
            -- Return the applicable change
            version := rec.version;
            hash := rec.hash;
            change := rec.change;
            parent_hash := rec.parent_hash;
            created_at := rec.created_at;
            RETURN NEXT;  -- Yield the current record
            -- Update current_hash to the parent_hash for the next iteration
            current_hash := rec.parent_hash;
        END IF;
    END LOOP;
END;$function$
;

CREATE OR REPLACE FUNCTION world.get_object_snapshot(p_object_id text)
 RETURNS jsonb
 LANGUAGE plpgsql
AS $function$
DECLARE
  latest_version bigint;
  latest_hash text;
BEGIN
  SELECT version, hash INTO latest_version, latest_hash
  FROM world.objects object
  WHERE object_id = p_object_id
  ORDER BY version DESC
  LIMIT 1;

  RETURN world.get_object_snapshot(p_object_id, latest_version::int4, latest_hash);
END;
$function$
;

CREATE OR REPLACE FUNCTION world.get_object_snapshot(p_object_id text, p_version integer, p_hash text)
 RETURNS jsonb
 LANGUAGE plpgsql
AS $function$DECLARE
    base_object jsonb := '{}'::jsonb;  -- Initialize the base object as an empty JSON object
    change_record RECORD;  -- Record variable to hold each change
BEGIN
    -- Iterate over the applicable changes and apply the JSON patches
    FOR change_record IN
        SELECT * FROM world.get_applicable_changes(p_object_id, p_version, p_hash) order by version
    LOOP
        -- Apply the JSON patch to the base object
        base_object := jsonb_patch(base_object, change_record.change);
    END LOOP;

    RETURN base_object;  -- Return the final snapshot
END;$function$
;

CREATE OR REPLACE FUNCTION world.restore_object(p_object_id text, p_timestamp timestamp with time zone, p_user_id uuid, p_organization_id uuid)
 RETURNS void
 LANGUAGE plpgsql
AS $function$
DECLARE
    target_change RECORD;
    current_version integer;
    current_hash text;
    new_version integer;
BEGIN
    -- Retrieve the change record that is closest to the specified timestamp
    SELECT *
    INTO target_change
    FROM world.object_changes
    WHERE object_id = p_object_id AND created_at <= p_timestamp
    ORDER BY created_at DESC
    LIMIT 1;

    -- Check if a target change was found
    IF NOT FOUND THEN
        RAISE EXCEPTION 'No changes found for object % at the specified time', p_object_id;
    END IF;

    -- Retrieve the current version and hash of the object
    SELECT version, hash INTO current_version, current_hash
    FROM world.objects
    WHERE object_id = p_object_id;

    -- Calculate the new version number
    new_version := current_version + 1;

    -- Restore the object to the state of the target change
    UPDATE world.objects
    SET version = target_change.version,
        hash = target_change.hash,
        updated_at = now()
    WHERE object_id = p_object_id;

    -- Log this restoration as a new change
    INSERT INTO world.object_changes (object_id, change, version, hash, parent_hash, created_at, user_id, organization_id)
    VALUES (p_object_id, target_change.change, new_version, target_change.hash, target_change.parent_hash, now(), p_user_id, p_organization_id);
END;
$function$
;

CREATE OR REPLACE FUNCTION world.track_object_changes()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$BEGIN
    IF TG_OP = 'INSERT' THEN
        NEW.created_by = auth.uid();  -- Set created_by on insert
        NEW.updated_by = auth.uid();  -- Set updated_by on insert
        NEW.version = 1;  -- Initialize version on insert
        NEW.slug = generate_slug(NEW.object_type, NEW.object_id, NEW.meta);  -- Generate slug on insert
        NEW.updated_at = CURRENT_TIMESTAMP;  -- Set updated_at on insert
    ELSIF TG_OP = 'UPDATE' THEN
        NEW.updated_by = auth.uid();  -- Update updated_by on update
        -- NEW.version = NEW.version + 1;  -- Increment version on update
        NEW.slug = generate_slug(NEW.object_type, NEW.object_id, NEW.meta);  -- Generate slug on update
        NEW.updated_at = CURRENT_TIMESTAMP;  -- Update updated_at on update

        -- Track slug changes
        IF NEW.slug IS DISTINCT FROM OLD.slug THEN
            INSERT INTO world.slug_redirects (old_slug, new_slug, created_at)
            VALUES (OLD.slug, NEW.slug, CURRENT_TIMESTAMP);
        END IF;

        -- Log the changes to the object as patches
        -- INSERT INTO public.object_patches (object_id, patch_data, parent_patch_id, created_at)
        -- VALUES (NEW.id, to_jsonb(NEW), NEW.id, CURRENT_TIMESTAMP);
    END IF;
    RETURN NEW;
END;$function$
;

grant delete on table "world"."object_changes" to "anon";

grant insert on table "world"."object_changes" to "anon";

grant references on table "world"."object_changes" to "anon";

grant select on table "world"."object_changes" to "anon";

grant trigger on table "world"."object_changes" to "anon";

grant truncate on table "world"."object_changes" to "anon";

grant update on table "world"."object_changes" to "anon";

grant delete on table "world"."object_changes" to "authenticated";

grant insert on table "world"."object_changes" to "authenticated";

grant references on table "world"."object_changes" to "authenticated";

grant select on table "world"."object_changes" to "authenticated";

grant trigger on table "world"."object_changes" to "authenticated";

grant truncate on table "world"."object_changes" to "authenticated";

grant update on table "world"."object_changes" to "authenticated";

grant delete on table "world"."object_changes" to "service_role";

grant insert on table "world"."object_changes" to "service_role";

grant references on table "world"."object_changes" to "service_role";

grant select on table "world"."object_changes" to "service_role";

grant trigger on table "world"."object_changes" to "service_role";

grant truncate on table "world"."object_changes" to "service_role";

grant update on table "world"."object_changes" to "service_role";

grant delete on table "world"."object_types" to "anon";

grant insert on table "world"."object_types" to "anon";

grant references on table "world"."object_types" to "anon";

grant select on table "world"."object_types" to "anon";

grant trigger on table "world"."object_types" to "anon";

grant truncate on table "world"."object_types" to "anon";

grant update on table "world"."object_types" to "anon";

grant delete on table "world"."object_types" to "authenticated";

grant insert on table "world"."object_types" to "authenticated";

grant references on table "world"."object_types" to "authenticated";

grant select on table "world"."object_types" to "authenticated";

grant trigger on table "world"."object_types" to "authenticated";

grant truncate on table "world"."object_types" to "authenticated";

grant update on table "world"."object_types" to "authenticated";

grant delete on table "world"."object_types" to "service_role";

grant insert on table "world"."object_types" to "service_role";

grant references on table "world"."object_types" to "service_role";

grant select on table "world"."object_types" to "service_role";

grant trigger on table "world"."object_types" to "service_role";

grant truncate on table "world"."object_types" to "service_role";

grant update on table "world"."object_types" to "service_role";

grant delete on table "world"."objects" to "anon";

grant insert on table "world"."objects" to "anon";

grant references on table "world"."objects" to "anon";

grant select on table "world"."objects" to "anon";

grant trigger on table "world"."objects" to "anon";

grant truncate on table "world"."objects" to "anon";

grant update on table "world"."objects" to "anon";

grant delete on table "world"."objects" to "authenticated";

grant insert on table "world"."objects" to "authenticated";

grant references on table "world"."objects" to "authenticated";

grant select on table "world"."objects" to "authenticated";

grant trigger on table "world"."objects" to "authenticated";

grant truncate on table "world"."objects" to "authenticated";

grant update on table "world"."objects" to "authenticated";

grant delete on table "world"."objects" to "service_role";

grant insert on table "world"."objects" to "service_role";

grant references on table "world"."objects" to "service_role";

grant select on table "world"."objects" to "service_role";

grant trigger on table "world"."objects" to "service_role";

grant truncate on table "world"."objects" to "service_role";

grant update on table "world"."objects" to "service_role";

grant delete on table "world"."slug_redirects" to "anon";

grant insert on table "world"."slug_redirects" to "anon";

grant references on table "world"."slug_redirects" to "anon";

grant select on table "world"."slug_redirects" to "anon";

grant trigger on table "world"."slug_redirects" to "anon";

grant truncate on table "world"."slug_redirects" to "anon";

grant update on table "world"."slug_redirects" to "anon";

grant delete on table "world"."slug_redirects" to "authenticated";

grant insert on table "world"."slug_redirects" to "authenticated";

grant references on table "world"."slug_redirects" to "authenticated";

grant select on table "world"."slug_redirects" to "authenticated";

grant trigger on table "world"."slug_redirects" to "authenticated";

grant truncate on table "world"."slug_redirects" to "authenticated";

grant update on table "world"."slug_redirects" to "authenticated";

grant delete on table "world"."slug_redirects" to "service_role";

grant insert on table "world"."slug_redirects" to "service_role";

grant references on table "world"."slug_redirects" to "service_role";

grant select on table "world"."slug_redirects" to "service_role";

grant trigger on table "world"."slug_redirects" to "service_role";

grant truncate on table "world"."slug_redirects" to "service_role";

grant update on table "world"."slug_redirects" to "service_role";

CREATE TRIGGER track_object_changes BEFORE INSERT OR DELETE OR UPDATE ON world.objects FOR EACH ROW EXECUTE FUNCTION world.track_object_changes();


