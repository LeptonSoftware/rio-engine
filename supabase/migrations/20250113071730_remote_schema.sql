revoke delete on table "public"."action_definitions" from "supabase_auth_admin";

revoke insert on table "public"."action_definitions" from "supabase_auth_admin";

revoke references on table "public"."action_definitions" from "supabase_auth_admin";

revoke select on table "public"."action_definitions" from "supabase_auth_admin";

revoke trigger on table "public"."action_definitions" from "supabase_auth_admin";

revoke truncate on table "public"."action_definitions" from "supabase_auth_admin";

revoke update on table "public"."action_definitions" from "supabase_auth_admin";

revoke delete on table "public"."actions" from "supabase_auth_admin";

revoke insert on table "public"."actions" from "supabase_auth_admin";

revoke references on table "public"."actions" from "supabase_auth_admin";

revoke select on table "public"."actions" from "supabase_auth_admin";

revoke trigger on table "public"."actions" from "supabase_auth_admin";

revoke truncate on table "public"."actions" from "supabase_auth_admin";

revoke update on table "public"."actions" from "supabase_auth_admin";

revoke delete on table "public"."credit_limits" from "supabase_auth_admin";

revoke insert on table "public"."credit_limits" from "supabase_auth_admin";

revoke references on table "public"."credit_limits" from "supabase_auth_admin";

revoke select on table "public"."credit_limits" from "supabase_auth_admin";

revoke trigger on table "public"."credit_limits" from "supabase_auth_admin";

revoke truncate on table "public"."credit_limits" from "supabase_auth_admin";

revoke update on table "public"."credit_limits" from "supabase_auth_admin";

revoke delete on table "public"."history" from "supabase_auth_admin";

revoke insert on table "public"."history" from "supabase_auth_admin";

revoke references on table "public"."history" from "supabase_auth_admin";

revoke select on table "public"."history" from "supabase_auth_admin";

revoke trigger on table "public"."history" from "supabase_auth_admin";

revoke truncate on table "public"."history" from "supabase_auth_admin";

revoke update on table "public"."history" from "supabase_auth_admin";

revoke delete on table "public"."org_credits" from "supabase_auth_admin";

revoke insert on table "public"."org_credits" from "supabase_auth_admin";

revoke references on table "public"."org_credits" from "supabase_auth_admin";

revoke select on table "public"."org_credits" from "supabase_auth_admin";

revoke trigger on table "public"."org_credits" from "supabase_auth_admin";

revoke truncate on table "public"."org_credits" from "supabase_auth_admin";

revoke update on table "public"."org_credits" from "supabase_auth_admin";

revoke delete on table "public"."user_credits" from "supabase_auth_admin";

revoke insert on table "public"."user_credits" from "supabase_auth_admin";

revoke references on table "public"."user_credits" from "supabase_auth_admin";

revoke select on table "public"."user_credits" from "supabase_auth_admin";

revoke trigger on table "public"."user_credits" from "supabase_auth_admin";

revoke truncate on table "public"."user_credits" from "supabase_auth_admin";

revoke update on table "public"."user_credits" from "supabase_auth_admin";

revoke delete on table "public"."user_sessions" from "supabase_auth_admin";

revoke insert on table "public"."user_sessions" from "supabase_auth_admin";

revoke references on table "public"."user_sessions" from "supabase_auth_admin";

revoke select on table "public"."user_sessions" from "supabase_auth_admin";

revoke trigger on table "public"."user_sessions" from "supabase_auth_admin";

revoke truncate on table "public"."user_sessions" from "supabase_auth_admin";

revoke update on table "public"."user_sessions" from "supabase_auth_admin";

drop view if exists "public"."org_members";

drop view if exists "public"."organization_profiles";

create table "public"."connections" (
    "id" bigint generated always as identity not null,
    "name" text not null,
    "type" text not null,
    "metadata" jsonb,
    "created_at" timestamp with time zone default now(),
    "updated_at" timestamp with time zone default now(),
    "user_id" uuid not null,
    "organization_id" uuid not null
);


alter table "public"."connections" enable row level security;

create table "public"."datasets" (
    "id" uuid not null default gen_random_uuid(),
    "user_id" uuid not null,
    "organization_id" uuid not null,
    "slug" text not null,
    "name" text not null,
    "metadata" jsonb default '{}'::jsonb
);


alter table "public"."datasets" enable row level security;

alter table "public"."profile" drop column "default_organization_id";

alter table "public"."profile" drop column "show_org_join_request_dialog";

alter table "public"."profile" add column "metadata" jsonb not null default '{"showJoinRequestDialog": true}'::jsonb;

alter table "public"."times" drop column "test";

CREATE INDEX connections_organization_id_idx ON public.connections USING btree (organization_id);

CREATE UNIQUE INDEX connections_pkey ON public.connections USING btree (id);

CREATE INDEX connections_user_id_idx ON public.connections USING btree (user_id);

CREATE INDEX datasets_organization_id_idx ON public.datasets USING btree (organization_id);

CREATE UNIQUE INDEX datasets_pkey ON public.datasets USING btree (id);

CREATE INDEX datasets_user_id_idx ON public.datasets USING btree (user_id);

CREATE UNIQUE INDEX unique_connection_type_user_org ON public.connections USING btree (type, user_id, organization_id);

CREATE UNIQUE INDEX unique_slug_per_user ON public.datasets USING btree (user_id, slug);

alter table "public"."connections" add constraint "connections_pkey" PRIMARY KEY using index "connections_pkey";

alter table "public"."datasets" add constraint "datasets_pkey" PRIMARY KEY using index "datasets_pkey";

alter table "public"."connections" add constraint "connections_organization_id_fkey" FOREIGN KEY (organization_id) REFERENCES organizations(id) ON UPDATE CASCADE ON DELETE CASCADE not valid;

alter table "public"."connections" validate constraint "connections_organization_id_fkey";

alter table "public"."connections" add constraint "connections_user_id_fkey" FOREIGN KEY (user_id) REFERENCES profile(user_id) ON UPDATE CASCADE ON DELETE CASCADE not valid;

alter table "public"."connections" validate constraint "connections_user_id_fkey";

alter table "public"."connections" add constraint "unique_connection_type_user_org" UNIQUE using index "unique_connection_type_user_org";

alter table "public"."datasets" add constraint "datasets_organization_id_fkey" FOREIGN KEY (organization_id) REFERENCES organizations(id) ON UPDATE CASCADE ON DELETE CASCADE not valid;

alter table "public"."datasets" validate constraint "datasets_organization_id_fkey";

alter table "public"."datasets" add constraint "datasets_user_id_fkey" FOREIGN KEY (user_id) REFERENCES profile(user_id) ON UPDATE CASCADE ON DELETE CASCADE not valid;

alter table "public"."datasets" validate constraint "datasets_user_id_fkey";

alter table "public"."datasets" add constraint "unique_slug_per_user" UNIQUE using index "unique_slug_per_user";

set check_function_bodies = off;

CREATE OR REPLACE FUNCTION public.update_updated_at_column()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
    NEW.updated_at = NOW();  -- Set the updated_at column to the current timestamp
    RETURN NEW;  -- Return the new row with the updated timestamp
END;
$function$
;

CREATE OR REPLACE FUNCTION public.add_user_to_organization_based_on_domain()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$DECLARE
    user_org_id uuid;
    user_name text;
    user_org_name text;
    domain_org_id uuid;
    domain_name text;
    clean_domain text;
BEGIN
    -- Determine the user's name from raw_user_meta_data or email
    user_name := CASE 
        WHEN NEW.raw_user_meta_data ->> 'name' IS NULL OR NEW.raw_user_meta_data ->> 'name' = '' THEN
            INITCAP(REPLACE(REPLACE(SUBSTRING(NEW.email FROM '^(.*?)(?=@)')::text, '.', ' '), '_', ' '))
        ELSE
            NEW.raw_user_meta_data ->> 'name'
    END;

    -- Create user-based organization name as 'user_name's Org'
    user_org_name := user_name || '''s Org';

    -- Always create a new organization for the user
    INSERT INTO public.organizations (name, logo, created_at, updated_at)
    VALUES (user_org_name, NULL, NOW(), NOW())
    RETURNING id INTO user_org_id;

    -- Add the user as an admin of their personal organization
    INSERT INTO public.organization_roles (organization_id, user_id, role, created_at, updated_at)
    VALUES (user_org_id, NEW.id, 'admin', NOW(), NOW());

    -- Extract domain from the user's email
    domain_name := split_part(NEW.email, '@', 2);

    -- Remove common domain extensions to get the organization name
    clean_domain := split_part(domain_name, '.', 1);

    -- Check if the domain is a public email provider
    IF NOT (domain_name = ANY(ARRAY['gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'live.com'])) THEN
        -- Check if a domain-based organization already exists
        SELECT organization_id INTO domain_org_id
        FROM public.organization_domains
        WHERE domain = domain_name;

        -- If no domain-based organization exists, create one
        IF domain_org_id IS NULL THEN
            INSERT INTO public.organizations (name, logo, created_at, updated_at)
            VALUES (clean_domain, NULL, NOW(), NOW())
            RETURNING id INTO domain_org_id;

            -- Associate the domain with the new organization
            INSERT INTO public.organization_domains (organization_id, domain)
            VALUES (domain_org_id, domain_name);

            -- Add the user to the domain-based organization as an admin
            INSERT INTO public.organization_roles (organization_id, user_id, role, created_at, updated_at)
            VALUES (domain_org_id, NEW.id, 'admin', NOW(), NOW());
        END IF;
    END IF;

    RETURN NEW;
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

create or replace view "public"."org_members" as  SELECT organization_roles.user_id,
    organization_roles.organization_id,
    organization_roles.role,
    profile.full_name,
    profile.email
   FROM (organization_roles
     JOIN profile ON ((organization_roles.user_id = profile.user_id)));


create or replace view "public"."organization_profiles" as  SELECT organization_roles.organization_id,
    organization_roles.role,
    profile.user_id,
    profile.full_name,
    profile.avatar_url,
    profile.email
   FROM (organization_roles
     JOIN profile ON ((organization_roles.user_id = profile.user_id)));


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

grant delete on table "public"."connections" to "anon";

grant insert on table "public"."connections" to "anon";

grant references on table "public"."connections" to "anon";

grant select on table "public"."connections" to "anon";

grant trigger on table "public"."connections" to "anon";

grant truncate on table "public"."connections" to "anon";

grant update on table "public"."connections" to "anon";

grant delete on table "public"."connections" to "authenticated";

grant insert on table "public"."connections" to "authenticated";

grant references on table "public"."connections" to "authenticated";

grant select on table "public"."connections" to "authenticated";

grant trigger on table "public"."connections" to "authenticated";

grant truncate on table "public"."connections" to "authenticated";

grant update on table "public"."connections" to "authenticated";

grant delete on table "public"."connections" to "service_role";

grant insert on table "public"."connections" to "service_role";

grant references on table "public"."connections" to "service_role";

grant select on table "public"."connections" to "service_role";

grant trigger on table "public"."connections" to "service_role";

grant truncate on table "public"."connections" to "service_role";

grant update on table "public"."connections" to "service_role";

grant delete on table "public"."datasets" to "anon";

grant insert on table "public"."datasets" to "anon";

grant references on table "public"."datasets" to "anon";

grant select on table "public"."datasets" to "anon";

grant trigger on table "public"."datasets" to "anon";

grant truncate on table "public"."datasets" to "anon";

grant update on table "public"."datasets" to "anon";

grant delete on table "public"."datasets" to "authenticated";

grant insert on table "public"."datasets" to "authenticated";

grant references on table "public"."datasets" to "authenticated";

grant select on table "public"."datasets" to "authenticated";

grant trigger on table "public"."datasets" to "authenticated";

grant truncate on table "public"."datasets" to "authenticated";

grant update on table "public"."datasets" to "authenticated";

grant delete on table "public"."datasets" to "service_role";

grant insert on table "public"."datasets" to "service_role";

grant references on table "public"."datasets" to "service_role";

grant select on table "public"."datasets" to "service_role";

grant trigger on table "public"."datasets" to "service_role";

grant truncate on table "public"."datasets" to "service_role";

grant update on table "public"."datasets" to "service_role";

create policy "Delete connections for organization members"
on "public"."connections"
as permissive
for delete
to authenticated
using ((organization_id IN ( SELECT my_organizations.organization_id
   FROM my_organizations
  WHERE (connections.user_id = auth.uid()))));


create policy "Insert connections for organization members"
on "public"."connections"
as permissive
for insert
to authenticated
with check ((organization_id IN ( SELECT my_organizations.organization_id
   FROM my_organizations
  WHERE (connections.user_id = auth.uid()))));


create policy "Select connections for organization members"
on "public"."connections"
as permissive
for select
to authenticated
using ((organization_id IN ( SELECT my_organizations.organization_id
   FROM my_organizations
  WHERE (connections.user_id = auth.uid()))));


create policy "Update connections for organization members"
on "public"."connections"
as permissive
for update
to authenticated
using ((organization_id IN ( SELECT my_organizations.organization_id
   FROM my_organizations
  WHERE (connections.user_id = auth.uid()))));


CREATE TRIGGER update_connections_updated_at BEFORE UPDATE ON public.connections FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();


