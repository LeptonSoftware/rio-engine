
create extension if not exists "postgres_fdw" with schema "extensions";



create sequence "public"."user_sessions_id_seq";

drop policy "Enable insert for authenticated users only" on "public"."organization_invites";

drop policy "Enable read access for all users" on "public"."organization_invites";

drop policy "Enable delete for users based on user_id" on "public"."organization_join_requests";

drop policy "Enable insert for authenticated users only" on "public"."organization_join_requests";

drop policy "Enable read access for all users" on "public"."organization_join_requests";

revoke delete on table "public"."organization_invites" from "anon";

revoke insert on table "public"."organization_invites" from "anon";

revoke references on table "public"."organization_invites" from "anon";

revoke select on table "public"."organization_invites" from "anon";

revoke trigger on table "public"."organization_invites" from "anon";

revoke truncate on table "public"."organization_invites" from "anon";

revoke update on table "public"."organization_invites" from "anon";

revoke delete on table "public"."organization_invites" from "authenticated";

revoke insert on table "public"."organization_invites" from "authenticated";

revoke references on table "public"."organization_invites" from "authenticated";

revoke select on table "public"."organization_invites" from "authenticated";

revoke trigger on table "public"."organization_invites" from "authenticated";

revoke truncate on table "public"."organization_invites" from "authenticated";

revoke update on table "public"."organization_invites" from "authenticated";

revoke delete on table "public"."organization_invites" from "service_role";

revoke insert on table "public"."organization_invites" from "service_role";

revoke references on table "public"."organization_invites" from "service_role";

revoke select on table "public"."organization_invites" from "service_role";

revoke trigger on table "public"."organization_invites" from "service_role";

revoke truncate on table "public"."organization_invites" from "service_role";

revoke update on table "public"."organization_invites" from "service_role";

revoke delete on table "public"."organization_invites" from "supabase_auth_admin";

revoke insert on table "public"."organization_invites" from "supabase_auth_admin";

revoke references on table "public"."organization_invites" from "supabase_auth_admin";

revoke select on table "public"."organization_invites" from "supabase_auth_admin";

revoke trigger on table "public"."organization_invites" from "supabase_auth_admin";

revoke truncate on table "public"."organization_invites" from "supabase_auth_admin";

revoke update on table "public"."organization_invites" from "supabase_auth_admin";

revoke delete on table "public"."organization_join_requests" from "anon";

revoke insert on table "public"."organization_join_requests" from "anon";

revoke references on table "public"."organization_join_requests" from "anon";

revoke select on table "public"."organization_join_requests" from "anon";

revoke trigger on table "public"."organization_join_requests" from "anon";

revoke truncate on table "public"."organization_join_requests" from "anon";

revoke update on table "public"."organization_join_requests" from "anon";

revoke delete on table "public"."organization_join_requests" from "authenticated";

revoke insert on table "public"."organization_join_requests" from "authenticated";

revoke references on table "public"."organization_join_requests" from "authenticated";

revoke select on table "public"."organization_join_requests" from "authenticated";

revoke trigger on table "public"."organization_join_requests" from "authenticated";

revoke truncate on table "public"."organization_join_requests" from "authenticated";

revoke update on table "public"."organization_join_requests" from "authenticated";

revoke delete on table "public"."organization_join_requests" from "service_role";

revoke insert on table "public"."organization_join_requests" from "service_role";

revoke references on table "public"."organization_join_requests" from "service_role";

revoke select on table "public"."organization_join_requests" from "service_role";

revoke trigger on table "public"."organization_join_requests" from "service_role";

revoke truncate on table "public"."organization_join_requests" from "service_role";

revoke update on table "public"."organization_join_requests" from "service_role";

revoke delete on table "public"."organization_join_requests" from "supabase_auth_admin";

revoke insert on table "public"."organization_join_requests" from "supabase_auth_admin";

revoke references on table "public"."organization_join_requests" from "supabase_auth_admin";

revoke select on table "public"."organization_join_requests" from "supabase_auth_admin";

revoke trigger on table "public"."organization_join_requests" from "supabase_auth_admin";

revoke truncate on table "public"."organization_join_requests" from "supabase_auth_admin";

revoke update on table "public"."organization_join_requests" from "supabase_auth_admin";

alter table "public"."organization_invites" drop constraint "organization_invites_invitee_token_key";

alter table "public"."organization_invites" drop constraint "organization_invites_organization_id_fkey";

alter table "public"."organization_join_requests" drop constraint "organization_join_requests_organization_id_fkey";

alter table "public"."organization_join_requests" drop constraint "organization_requests_user_id_fkey";

alter table "public"."organization_invites" drop constraint "organization_invites_pkey";

alter table "public"."organization_join_requests" drop constraint "organization_requests_pkey";

drop index if exists "public"."organization_invites_invitee_token_key";

drop index if exists "public"."organization_invites_pkey";

drop index if exists "public"."organization_requests_pkey";

drop table "public"."organization_invites";

drop table "public"."organization_join_requests";

create table "public"."action_definitions" (
    "id" bigint generated by default as identity not null,
    "created_at" timestamp with time zone not null default now(),
    "action" text,
    "unit_cost" double precision
);


alter table "public"."action_definitions" enable row level security;

create table "public"."actions" (
    "id" bigint generated by default as identity not null,
    "created_at" timestamp with time zone not null default now(),
    "user_id" uuid default gen_random_uuid(),
    "organization_id" uuid default gen_random_uuid(),
    "credits_consumed" double precision,
    "action" text
);


alter table "public"."actions" enable row level security;

create table "public"."credit_limits" (
    "id" bigint generated by default as identity not null,
    "created_at" timestamp with time zone not null default now(),
    "entity_id" uuid,
    "entity_type" text,
    "limit_type" text,
    "total" double precision,
    "consumed" double precision,
    "remaining" numeric generated always as ((total - consumed)) stored
);


alter table "public"."credit_limits" enable row level security;

create table "public"."history" (
    "id" bigint generated by default as identity not null,
    "created_at" timestamp without time zone not null,
    "object_id" text,
    "json_patches" jsonb,
    "organization_id" uuid default gen_random_uuid(),
    "user_id" uuid default gen_random_uuid(),
    "updated_at" timestamp without time zone default now(),
    "version" text default ''::text,
    "object_type" text
);


alter table "public"."history" enable row level security;

create table "public"."notifications" (
    "id" bigint generated by default as identity not null,
    "created_at" timestamp with time zone not null default now(),
    "organization_id" uuid,
    "role" text,
    "email" text,
    "token" text,
    "expires_at" timestamp without time zone default (now() + '7 days'::interval),
    "status" text,
    "message" text,
    "type" text,
    "is_deleted" boolean default false,
    "user_id" uuid
);


alter table "public"."notifications" enable row level security;

create table "public"."org_credits" (
    "id" bigint generated by default as identity not null,
    "created_at" timestamp with time zone not null default now(),
    "organization_id" uuid,
    "total" double precision,
    "consumed" double precision,
    "remaining" numeric generated always as ((total - consumed)) stored,
    "expires_at" timestamp without time zone
);


alter table "public"."org_credits" enable row level security;

create table "public"."user_credits" (
    "id" bigint generated by default as identity not null,
    "created_at" timestamp with time zone not null default now(),
    "user_id" uuid,
    "organization_id" uuid,
    "total" double precision,
    "consumed" double precision,
    "remaining" numeric generated always as ((total - consumed)) stored,
    "expires_at" timestamp without time zone
);


alter table "public"."user_credits" enable row level security;

create table "public"."user_sessions" (
    "id" integer not null default nextval('user_sessions_id_seq'::regclass),
    "user_id" uuid not null,
    "session_token" text not null,
    "created_at" timestamp without time zone default now()
);


alter table "public"."profile" add column "default_organization_id" text;

alter table "public"."profile" add column "show_org_join_request_dialog" boolean default true;

alter table "public"."times" drop column "kolkata";

alter table "public"."times" drop column "mumbai";

alter table "public"."times" add column "city" text;

alter table "public"."times" add column "count" numeric;

alter table "public"."times" add column "routes" jsonb;

alter table "public"."times" add column "updated_at" timestamp without time zone;

alter sequence "public"."user_sessions_id_seq" owned by "public"."user_sessions"."id";

CREATE UNIQUE INDEX "History_id_key" ON public.history USING btree (id);

CREATE UNIQUE INDEX "History_pkey" ON public.history USING btree (id);

CREATE UNIQUE INDEX action_definitions_pkey ON public.action_definitions USING btree (id);

CREATE UNIQUE INDEX actions_pkey ON public.actions USING btree (id);

CREATE UNIQUE INDEX credit_limits_pkey ON public.credit_limits USING btree (id);

CREATE UNIQUE INDEX notifications_pkey ON public.notifications USING btree (id);

CREATE UNIQUE INDEX org_credits_pkey ON public.org_credits USING btree (id);

CREATE UNIQUE INDEX user_credits_pkey ON public.user_credits USING btree (id);

CREATE UNIQUE INDEX user_sessions_pkey ON public.user_sessions USING btree (id);

alter table "public"."action_definitions" add constraint "action_definitions_pkey" PRIMARY KEY using index "action_definitions_pkey";

alter table "public"."actions" add constraint "actions_pkey" PRIMARY KEY using index "actions_pkey";

alter table "public"."credit_limits" add constraint "credit_limits_pkey" PRIMARY KEY using index "credit_limits_pkey";

alter table "public"."history" add constraint "History_pkey" PRIMARY KEY using index "History_pkey";

alter table "public"."notifications" add constraint "notifications_pkey" PRIMARY KEY using index "notifications_pkey";

alter table "public"."org_credits" add constraint "org_credits_pkey" PRIMARY KEY using index "org_credits_pkey";

alter table "public"."user_credits" add constraint "user_credits_pkey" PRIMARY KEY using index "user_credits_pkey";

alter table "public"."user_sessions" add constraint "user_sessions_pkey" PRIMARY KEY using index "user_sessions_pkey";

alter table "public"."actions" add constraint "actions_organization_id_fkey" FOREIGN KEY (organization_id) REFERENCES organizations(id) ON UPDATE CASCADE ON DELETE CASCADE not valid;

alter table "public"."actions" validate constraint "actions_organization_id_fkey";

alter table "public"."actions" add constraint "actions_user_id_fkey" FOREIGN KEY (user_id) REFERENCES auth.users(id) ON UPDATE CASCADE ON DELETE CASCADE not valid;

alter table "public"."actions" validate constraint "actions_user_id_fkey";

alter table "public"."history" add constraint "History_id_key" UNIQUE using index "History_id_key";

alter table "public"."history" add constraint "history_organization_id_fkey" FOREIGN KEY (organization_id) REFERENCES organizations(id) ON UPDATE CASCADE ON DELETE RESTRICT not valid;

alter table "public"."history" validate constraint "history_organization_id_fkey";

alter table "public"."history" add constraint "history_user_id_fkey" FOREIGN KEY (user_id) REFERENCES profile(user_id) ON UPDATE CASCADE ON DELETE RESTRICT not valid;

alter table "public"."history" validate constraint "history_user_id_fkey";

alter table "public"."notifications" add constraint "notifications_organization_id_fkey" FOREIGN KEY (organization_id) REFERENCES organizations(id) ON UPDATE CASCADE ON DELETE CASCADE not valid;

alter table "public"."notifications" validate constraint "notifications_organization_id_fkey";

alter table "public"."org_credits" add constraint "org_credits_organization_id_fkey" FOREIGN KEY (organization_id) REFERENCES organizations(id) ON UPDATE CASCADE ON DELETE CASCADE not valid;

alter table "public"."org_credits" validate constraint "org_credits_organization_id_fkey";

alter table "public"."user_credits" add constraint "user_credits_organization_id_fkey" FOREIGN KEY (organization_id) REFERENCES organizations(id) ON UPDATE CASCADE ON DELETE CASCADE not valid;

alter table "public"."user_credits" validate constraint "user_credits_organization_id_fkey";

alter table "public"."user_credits" add constraint "user_credits_user_id_fkey" FOREIGN KEY (user_id) REFERENCES auth.users(id) ON UPDATE CASCADE ON DELETE CASCADE not valid;

alter table "public"."user_credits" validate constraint "user_credits_user_id_fkey";

alter table "public"."user_sessions" add constraint "user_sessions_user_id_fkey" FOREIGN KEY (user_id) REFERENCES auth.users(id) ON UPDATE CASCADE ON DELETE CASCADE not valid;

alter table "public"."user_sessions" validate constraint "user_sessions_user_id_fkey";

set check_function_bodies = off;

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

CREATE OR REPLACE FUNCTION public.get_server_time()
 RETURNS timestamp without time zone
 LANGUAGE plpgsql
AS $function$
BEGIN
    RETURN CURRENT_TIMESTAMP;
END;
$function$
;

CREATE OR REPLACE FUNCTION public.handle_user_signup_with_invite()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$DECLARE
  new_token TEXT;
  new_organization_id UUID;
  new_role TEXT;
BEGIN
  -- Extract signupToken from user_metadata (raw_user_meta_data)
  new_token := NEW.raw_user_meta_data ->> 'signupToken';

  -- If token is NULL, exit the function
  IF new_token IS NULL THEN
    RETURN NEW;
  END IF;

  -- Fetch organization_id and role from notifications table using the signup token
  SELECT organization_id, role
  INTO new_organization_id, new_role
  FROM public.notifications
  WHERE token = new_token AND type = 'invite'
  LIMIT 1;

  -- If no matching notification is found, exit the function
  IF new_organization_id IS NULL THEN
    RETURN NEW;
  END IF;

  -- Insert into organization_roles table with the fetched details and the NEW user ID
  INSERT INTO public.organization_roles (organization_id, user_id, role)
  VALUES (new_organization_id, NEW.id, new_role);

  -- Update the notifications table to mark the token as 'joined' and delete it
  UPDATE public.notifications
  SET status = 'joined', is_deleted = TRUE
  WHERE token = new_token;

  RETURN NEW;
END;$function$
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

    -- Check if the domain is a public email provider
    IF NOT (domain_name = ANY(ARRAY['gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'live.com'])) THEN
        -- Check if a domain-based organization already exists
        SELECT organization_id INTO domain_org_id
        FROM public.organization_domains
        WHERE domain = domain_name;

        -- If no domain-based organization exists, create one
        IF domain_org_id IS NULL THEN
            INSERT INTO public.organizations (name, logo, created_at, updated_at)
            VALUES (domain_name || ' Org', NULL, NOW(), NOW())
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

CREATE OR REPLACE FUNCTION public.approve_org_join_request(p_organization_id uuid, p_user_id uuid, p_role text, p_request_id bigint)
 RETURNS bigint
 LANGUAGE plpgsql
AS $function$BEGIN
    -- Insert into the organization_roles table
    INSERT INTO organization_roles (organization_id, user_id, role)
    VALUES (p_organization_id, p_user_id, p_role);

    -- Delete from the organization_join_requests table
    UPDATE notifications SET is_deleted='true', status='approved'
    WHERE id = p_request_id;

    RETURN p_request_id; -- Return the request ID
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

grant delete on table "public"."action_definitions" to "anon";

grant insert on table "public"."action_definitions" to "anon";

grant references on table "public"."action_definitions" to "anon";

grant select on table "public"."action_definitions" to "anon";

grant trigger on table "public"."action_definitions" to "anon";

grant truncate on table "public"."action_definitions" to "anon";

grant update on table "public"."action_definitions" to "anon";

grant delete on table "public"."action_definitions" to "authenticated";

grant insert on table "public"."action_definitions" to "authenticated";

grant references on table "public"."action_definitions" to "authenticated";

grant select on table "public"."action_definitions" to "authenticated";

grant trigger on table "public"."action_definitions" to "authenticated";

grant truncate on table "public"."action_definitions" to "authenticated";

grant update on table "public"."action_definitions" to "authenticated";

grant delete on table "public"."action_definitions" to "service_role";

grant insert on table "public"."action_definitions" to "service_role";

grant references on table "public"."action_definitions" to "service_role";

grant select on table "public"."action_definitions" to "service_role";

grant trigger on table "public"."action_definitions" to "service_role";

grant truncate on table "public"."action_definitions" to "service_role";

grant update on table "public"."action_definitions" to "service_role";

grant delete on table "public"."actions" to "anon";

grant insert on table "public"."actions" to "anon";

grant references on table "public"."actions" to "anon";

grant select on table "public"."actions" to "anon";

grant trigger on table "public"."actions" to "anon";

grant truncate on table "public"."actions" to "anon";

grant update on table "public"."actions" to "anon";

grant delete on table "public"."actions" to "authenticated";

grant insert on table "public"."actions" to "authenticated";

grant references on table "public"."actions" to "authenticated";

grant select on table "public"."actions" to "authenticated";

grant trigger on table "public"."actions" to "authenticated";

grant truncate on table "public"."actions" to "authenticated";

grant update on table "public"."actions" to "authenticated";

grant delete on table "public"."actions" to "service_role";

grant insert on table "public"."actions" to "service_role";

grant references on table "public"."actions" to "service_role";

grant select on table "public"."actions" to "service_role";

grant trigger on table "public"."actions" to "service_role";

grant truncate on table "public"."actions" to "service_role";

grant update on table "public"."actions" to "service_role";

grant delete on table "public"."credit_limits" to "anon";

grant insert on table "public"."credit_limits" to "anon";

grant references on table "public"."credit_limits" to "anon";

grant select on table "public"."credit_limits" to "anon";

grant trigger on table "public"."credit_limits" to "anon";

grant truncate on table "public"."credit_limits" to "anon";

grant update on table "public"."credit_limits" to "anon";

grant delete on table "public"."credit_limits" to "authenticated";

grant insert on table "public"."credit_limits" to "authenticated";

grant references on table "public"."credit_limits" to "authenticated";

grant select on table "public"."credit_limits" to "authenticated";

grant trigger on table "public"."credit_limits" to "authenticated";

grant truncate on table "public"."credit_limits" to "authenticated";

grant update on table "public"."credit_limits" to "authenticated";

grant delete on table "public"."credit_limits" to "service_role";

grant insert on table "public"."credit_limits" to "service_role";

grant references on table "public"."credit_limits" to "service_role";

grant select on table "public"."credit_limits" to "service_role";

grant trigger on table "public"."credit_limits" to "service_role";

grant truncate on table "public"."credit_limits" to "service_role";

grant update on table "public"."credit_limits" to "service_role";

grant delete on table "public"."history" to "anon";

grant insert on table "public"."history" to "anon";

grant references on table "public"."history" to "anon";

grant select on table "public"."history" to "anon";

grant trigger on table "public"."history" to "anon";

grant truncate on table "public"."history" to "anon";

grant update on table "public"."history" to "anon";

grant delete on table "public"."history" to "authenticated";

grant insert on table "public"."history" to "authenticated";

grant references on table "public"."history" to "authenticated";

grant select on table "public"."history" to "authenticated";

grant trigger on table "public"."history" to "authenticated";

grant truncate on table "public"."history" to "authenticated";

grant update on table "public"."history" to "authenticated";

grant delete on table "public"."history" to "service_role";

grant insert on table "public"."history" to "service_role";

grant references on table "public"."history" to "service_role";

grant select on table "public"."history" to "service_role";

grant trigger on table "public"."history" to "service_role";

grant truncate on table "public"."history" to "service_role";

grant update on table "public"."history" to "service_role";

grant delete on table "public"."notifications" to "anon";

grant insert on table "public"."notifications" to "anon";

grant references on table "public"."notifications" to "anon";

grant select on table "public"."notifications" to "anon";

grant trigger on table "public"."notifications" to "anon";

grant truncate on table "public"."notifications" to "anon";

grant update on table "public"."notifications" to "anon";

grant delete on table "public"."notifications" to "authenticated";

grant insert on table "public"."notifications" to "authenticated";

grant references on table "public"."notifications" to "authenticated";

grant select on table "public"."notifications" to "authenticated";

grant trigger on table "public"."notifications" to "authenticated";

grant truncate on table "public"."notifications" to "authenticated";

grant update on table "public"."notifications" to "authenticated";

grant delete on table "public"."notifications" to "service_role";

grant insert on table "public"."notifications" to "service_role";

grant references on table "public"."notifications" to "service_role";

grant select on table "public"."notifications" to "service_role";

grant trigger on table "public"."notifications" to "service_role";

grant truncate on table "public"."notifications" to "service_role";

grant update on table "public"."notifications" to "service_role";

grant delete on table "public"."notifications" to "supabase_auth_admin";

grant insert on table "public"."notifications" to "supabase_auth_admin";

grant references on table "public"."notifications" to "supabase_auth_admin";

grant select on table "public"."notifications" to "supabase_auth_admin";

grant trigger on table "public"."notifications" to "supabase_auth_admin";

grant truncate on table "public"."notifications" to "supabase_auth_admin";

grant update on table "public"."notifications" to "supabase_auth_admin";

grant delete on table "public"."org_credits" to "anon";

grant insert on table "public"."org_credits" to "anon";

grant references on table "public"."org_credits" to "anon";

grant select on table "public"."org_credits" to "anon";

grant trigger on table "public"."org_credits" to "anon";

grant truncate on table "public"."org_credits" to "anon";

grant update on table "public"."org_credits" to "anon";

grant delete on table "public"."org_credits" to "authenticated";

grant insert on table "public"."org_credits" to "authenticated";

grant references on table "public"."org_credits" to "authenticated";

grant select on table "public"."org_credits" to "authenticated";

grant trigger on table "public"."org_credits" to "authenticated";

grant truncate on table "public"."org_credits" to "authenticated";

grant update on table "public"."org_credits" to "authenticated";

grant delete on table "public"."org_credits" to "service_role";

grant insert on table "public"."org_credits" to "service_role";

grant references on table "public"."org_credits" to "service_role";

grant select on table "public"."org_credits" to "service_role";

grant trigger on table "public"."org_credits" to "service_role";

grant truncate on table "public"."org_credits" to "service_role";

grant update on table "public"."org_credits" to "service_role";

grant delete on table "public"."user_credits" to "anon";

grant insert on table "public"."user_credits" to "anon";

grant references on table "public"."user_credits" to "anon";

grant select on table "public"."user_credits" to "anon";

grant trigger on table "public"."user_credits" to "anon";

grant truncate on table "public"."user_credits" to "anon";

grant update on table "public"."user_credits" to "anon";

grant delete on table "public"."user_credits" to "authenticated";

grant insert on table "public"."user_credits" to "authenticated";

grant references on table "public"."user_credits" to "authenticated";

grant select on table "public"."user_credits" to "authenticated";

grant trigger on table "public"."user_credits" to "authenticated";

grant truncate on table "public"."user_credits" to "authenticated";

grant update on table "public"."user_credits" to "authenticated";

grant delete on table "public"."user_credits" to "service_role";

grant insert on table "public"."user_credits" to "service_role";

grant references on table "public"."user_credits" to "service_role";

grant select on table "public"."user_credits" to "service_role";

grant trigger on table "public"."user_credits" to "service_role";

grant truncate on table "public"."user_credits" to "service_role";

grant update on table "public"."user_credits" to "service_role";

grant delete on table "public"."user_sessions" to "anon";

grant insert on table "public"."user_sessions" to "anon";

grant references on table "public"."user_sessions" to "anon";

grant select on table "public"."user_sessions" to "anon";

grant trigger on table "public"."user_sessions" to "anon";

grant truncate on table "public"."user_sessions" to "anon";

grant update on table "public"."user_sessions" to "anon";

grant delete on table "public"."user_sessions" to "authenticated";

grant insert on table "public"."user_sessions" to "authenticated";

grant references on table "public"."user_sessions" to "authenticated";

grant select on table "public"."user_sessions" to "authenticated";

grant trigger on table "public"."user_sessions" to "authenticated";

grant truncate on table "public"."user_sessions" to "authenticated";

grant update on table "public"."user_sessions" to "authenticated";

grant delete on table "public"."user_sessions" to "service_role";

grant insert on table "public"."user_sessions" to "service_role";

grant references on table "public"."user_sessions" to "service_role";

grant select on table "public"."user_sessions" to "service_role";

grant trigger on table "public"."user_sessions" to "service_role";

grant truncate on table "public"."user_sessions" to "service_role";

grant update on table "public"."user_sessions" to "service_role";

create policy "Allow select notifications by token and type"
on "public"."notifications"
as permissive
for select
to authenticated
using (((token = current_setting('request.jwt.claims.signupToken'::text)) AND (type = 'invite'::text)));


create policy "Allow update notifications by token"
on "public"."notifications"
as permissive
for update
to authenticated
using ((token = current_setting('request.jwt.claims.signupToken'::text)));


create policy "Enable all access for all users"
on "public"."notifications"
as permissive
for all
to public
using (true);


create policy "Enable insert for authenticated users only"
on "public"."notifications"
as permissive
for insert
to authenticated
with check (true);


create policy "Enable update for authenticated users"
on "public"."notifications"
as permissive
for update
to authenticated
using (true)
with check (true);


create policy "select_notifications_by_token"
on "public"."notifications"
as permissive
for select
to public
using (((token = current_setting('request.jwt.claims.signupToken'::text)) AND (type = 'invite'::text)));


create policy "update_notifications_by_token"
on "public"."notifications"
as permissive
for update
to public
using ((token = current_setting('request.jwt.claims.signupToken'::text)));


create policy "Enable insert for authenticated users only"
on "public"."organization_roles"
as permissive
for insert
to authenticated
with check (true);


create policy "insert_organization_roles"
on "public"."organization_roles"
as permissive
for insert
to public
with check (((organization_id IS NOT NULL) AND (user_id = (current_setting('request.jwt.claims.user_id'::text))::uuid)));



