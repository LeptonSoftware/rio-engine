create extension if not exists "kiwicopple-pg_idkit" with schema "extensions";


set check_function_bodies = off;

CREATE OR REPLACE FUNCTION external_services.update_api_key_credit_cost()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$DECLARE
    pricing_data jsonb;
    tiers jsonb;
    calculated_cost numeric := 0;
    tier jsonb;
    tier_min numeric;
    tier_max numeric;
    tier_price numeric; -- Changed from tier_price_per_1000
    tier_units numeric;
    i integer;
BEGIN
    -- Get the pricing structure for this record by service name
    SELECT pricing INTO pricing_data
    FROM external_services.pricing_structure
    WHERE service = NEW.service;
    
    IF pricing_data IS NULL THEN
        RAISE EXCEPTION 'No pricing structure found for service %', NEW.service;
    END IF;
    
    -- Extract the tiers array from the pricing data
    tiers := pricing_data->'tiers';
    
    -- Calculate the cost based on consumed units and pricing tiers
    FOR i IN 0..jsonb_array_length(tiers) - 1 LOOP
        tier := tiers->i;
        tier_min := (tier->>'min')::numeric;
        tier_max := (tier->>'max')::numeric;
        tier_price := (tier->>'price')::numeric; -- Changed from price_per_1000
        
        -- Calculate units in this tier
        IF NEW.consumed <= tier_min THEN
            -- Consumed is below this tier, skip
            CONTINUE;
        END IF;
        
        -- Calculate the number of units that fall within this tier
        IF tier_max IS NULL THEN
            -- This is the highest tier with no upper limit
            tier_units := NEW.consumed - tier_min + 1;
        ELSE
            -- This tier has an upper limit
            IF NEW.consumed > tier_max THEN
                -- Only count units up to the max for this tier
                tier_units := tier_max - tier_min + 1;
            ELSE
                -- Count units up to the consumed amount
                tier_units := NEW.consumed - tier_min + 1;
            END IF;
        END IF;
        
        -- Add cost for this tier (price per unit) - removed division by 1000
        calculated_cost := calculated_cost + (tier_units * tier_price);
    END LOOP;
    
    -- Update the cost field
    NEW.cost := calculated_cost;
    
    RETURN NEW;
END;$function$
;


create extension if not exists "supabase-dbdev" with schema "public" version '0.0.5';

revoke delete on table "public"."spatial_ref_sys" from "anon";

revoke insert on table "public"."spatial_ref_sys" from "anon";

revoke references on table "public"."spatial_ref_sys" from "anon";

revoke select on table "public"."spatial_ref_sys" from "anon";

revoke trigger on table "public"."spatial_ref_sys" from "anon";

revoke truncate on table "public"."spatial_ref_sys" from "anon";

revoke update on table "public"."spatial_ref_sys" from "anon";

revoke delete on table "public"."spatial_ref_sys" from "authenticated";

revoke insert on table "public"."spatial_ref_sys" from "authenticated";

revoke references on table "public"."spatial_ref_sys" from "authenticated";

revoke select on table "public"."spatial_ref_sys" from "authenticated";

revoke trigger on table "public"."spatial_ref_sys" from "authenticated";

revoke truncate on table "public"."spatial_ref_sys" from "authenticated";

revoke update on table "public"."spatial_ref_sys" from "authenticated";

revoke delete on table "public"."spatial_ref_sys" from "postgres";

revoke insert on table "public"."spatial_ref_sys" from "postgres";

revoke references on table "public"."spatial_ref_sys" from "postgres";

revoke select on table "public"."spatial_ref_sys" from "postgres";

revoke trigger on table "public"."spatial_ref_sys" from "postgres";

revoke truncate on table "public"."spatial_ref_sys" from "postgres";

revoke update on table "public"."spatial_ref_sys" from "postgres";

revoke delete on table "public"."spatial_ref_sys" from "service_role";

revoke insert on table "public"."spatial_ref_sys" from "service_role";

revoke references on table "public"."spatial_ref_sys" from "service_role";

revoke select on table "public"."spatial_ref_sys" from "service_role";

revoke trigger on table "public"."spatial_ref_sys" from "service_role";

revoke truncate on table "public"."spatial_ref_sys" from "service_role";

revoke update on table "public"."spatial_ref_sys" from "service_role";

revoke delete on table "public"."user_last_sign_in" from "anon";

revoke insert on table "public"."user_last_sign_in" from "anon";

revoke references on table "public"."user_last_sign_in" from "anon";

revoke select on table "public"."user_last_sign_in" from "anon";

revoke trigger on table "public"."user_last_sign_in" from "anon";

revoke truncate on table "public"."user_last_sign_in" from "anon";

revoke update on table "public"."user_last_sign_in" from "anon";

revoke delete on table "public"."user_last_sign_in" from "authenticated";

revoke insert on table "public"."user_last_sign_in" from "authenticated";

revoke references on table "public"."user_last_sign_in" from "authenticated";

revoke select on table "public"."user_last_sign_in" from "authenticated";

revoke trigger on table "public"."user_last_sign_in" from "authenticated";

revoke truncate on table "public"."user_last_sign_in" from "authenticated";

revoke update on table "public"."user_last_sign_in" from "authenticated";

revoke delete on table "public"."user_last_sign_in" from "service_role";

revoke insert on table "public"."user_last_sign_in" from "service_role";

revoke references on table "public"."user_last_sign_in" from "service_role";

revoke select on table "public"."user_last_sign_in" from "service_role";

revoke trigger on table "public"."user_last_sign_in" from "service_role";

revoke truncate on table "public"."user_last_sign_in" from "service_role";

revoke update on table "public"."user_last_sign_in" from "service_role";

revoke delete on table "public"."user_last_sign_in" from "supabase_auth_admin";

revoke insert on table "public"."user_last_sign_in" from "supabase_auth_admin";

revoke references on table "public"."user_last_sign_in" from "supabase_auth_admin";

revoke select on table "public"."user_last_sign_in" from "supabase_auth_admin";

revoke trigger on table "public"."user_last_sign_in" from "supabase_auth_admin";

revoke truncate on table "public"."user_last_sign_in" from "supabase_auth_admin";

revoke update on table "public"."user_last_sign_in" from "supabase_auth_admin";

alter table "public"."project_roles" drop constraint "project_roles_user_id_fkey";

alter table "public"."workflows" drop constraint "workflows_status_check";

create table "public"."chatbot-prompts" (
    "id" bigint generated by default as identity not null,
    "created_at" timestamp with time zone not null default now(),
    "user_id" text,
    "organization_id" text,
    "prompt" text,
    "ai_response" text,
    "project_id" text
);


alter table "public"."chatbot-prompts" enable row level security;

CREATE UNIQUE INDEX "chatbot-prompts_pkey" ON public."chatbot-prompts" USING btree (id);

alter table "public"."chatbot-prompts" add constraint "chatbot-prompts_pkey" PRIMARY KEY using index "chatbot-prompts_pkey";

alter table "public"."project_roles" add constraint "project_roles_user_id_fkey" FOREIGN KEY (user_id) REFERENCES auth.users(id) ON UPDATE CASCADE ON DELETE CASCADE not valid;

alter table "public"."project_roles" validate constraint "project_roles_user_id_fkey";

alter table "public"."workflows" add constraint "workflows_status_check" CHECK (((status)::text = ANY ((ARRAY['active'::character varying, 'archived'::character varying, 'draft'::character varying])::text[]))) not valid;

alter table "public"."workflows" validate constraint "workflows_status_check";

set check_function_bodies = off;

CREATE OR REPLACE FUNCTION public.add_profile()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
  INSERT INTO public.profile (user_id, full_name, avatar_url, email)
  VALUES (
    NEW.id,
    CASE 
      WHEN NEW.raw_user_meta_data ->> 'name' IS NULL OR NEW.raw_user_meta_data ->> 'name' = '' THEN
        INITCAP(REPLACE(REPLACE(SUBSTRING(NEW.email FROM '^(.*?)(?=@)')::text, '.', ' '), '_', ' '))
      ELSE
        NEW.raw_user_meta_data ->> 'name'
    END,
    NEW.raw_user_meta_data ->> 'avatar_url',
    NEW.email
  );
  RETURN NEW;
END;
$function$
;

CREATE OR REPLACE FUNCTION public.add_user_as_admin_and_member_to_new_organization()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$DECLARE
  user_role TEXT;
BEGIN
  -- Fetch the current user role
  user_role := auth.role();

  -- Check if the user is authenticated
  IF user_role = 'authenticated' THEN
    -- Insert the authenticated user as an 'admin'
    INSERT INTO public.organization_roles (organization_id, user_id, role, created_at, updated_at)
    VALUES (NEW.id, auth.uid(), 'admin', NOW(), NOW());

    -- Insert the authenticated user as a 'member'
    INSERT INTO public.organization_roles (organization_id, user_id, role, created_at, updated_at)
    VALUES (NEW.id, auth.uid(), 'member', NOW(), NOW());
  END IF;

  -- If the user is not authenticated, do nothing
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

CREATE OR REPLACE FUNCTION public.analyze_project_layers(project_id bigint)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$ 
DECLARE
    project_data jsonb;
    layer_names text[];
    result jsonb;
    bucket_name text := 'projects';
    file_path text := project_id::text || '/project.json';
BEGIN
    -- Get the project data (content) from storage bucket using project_id
    SELECT data::jsonb INTO project_data  -- Assuming the content is in the 'data' field
    FROM storage.objects
    WHERE bucket_id = bucket_name AND name = file_path;

    -- If no project data found, return empty result
    IF project_data IS NULL THEN
        RETURN jsonb_build_object(
            'success', false,
            'message', 'Project data not found',
            'layer_count', 0,
            'layer_names', '[]'::jsonb,
            'project_json', '{}'::jsonb  -- Return empty JSON as fallback
        );
    END IF;

    -- Get all layer names (the 'name' field from each layer in 'layers')
    SELECT array_agg((project_data->'layers'->key->>'name')) INTO layer_names
    FROM jsonb_object_keys(project_data->'layers') AS key;

    -- If no layers found or no 'name' field in layers, return empty result
    IF layer_names IS NULL OR array_length(layer_names, 1) = 0 THEN
        RETURN jsonb_build_object(
            'success', true,
            'message', 'No layers with names found',
            'layer_count', 0,
            'layer_names', '[]'::jsonb,
            'project_json', project_data  -- Return the project JSON
        );
    END IF;

    -- Build and return the result
    result := jsonb_build_object(
        'success', true,
        'layer_count', array_length(layer_names, 1),
        'layer_names', to_jsonb(layer_names),
        'project_json', project_data  -- Return the original project JSON
    );

    RETURN result;
END;
$function$
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

CREATE OR REPLACE FUNCTION public.assign_owner_role()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
    -- Insert the owner role for the user who created the project
    INSERT INTO public.project_roles (project_id, user_id, project_role)
    VALUES (NEW.id, NEW.user_id, 'owner');
    
    RETURN NEW;
END;
$function$
;

CREATE OR REPLACE FUNCTION public.create_new_org_super_admin(org_id uuid, org_name text, limit_per_role jsonb, org_roles jsonb[], credits_rows jsonb[])
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
AS $function$DECLARE
  now timestamp with time zone := now();
  result jsonb;
  credit_data jsonb;
BEGIN
  -- Insert into organizations table
  INSERT INTO organizations (
    id,
    name,
    created_at,
    updated_at,
    limit_per_role
  ) VALUES (
    org_id,
    org_name,
    now,
    now,
    limit_per_role
  );
  
  -- Insert organization roles
  INSERT INTO organization_roles (
    id,
    organization_id,
    user_id,
    role,
    created_at,
    updated_at
  )
  SELECT 
    (role_data->>'id')::uuid,
    (role_data->>'organization_id')::uuid,
    (role_data->>'user_id')::uuid,
    role_data->>'role',
    (role_data->>'created_at')::timestamp with time zone,
    (role_data->>'updated_at')::timestamp with time zone
  FROM unnest(org_roles) AS role_data;
  
  -- Handle credits - update existing records by adding new values
  -- For each user in credits_rows
  FOREACH credit_data IN ARRAY credits_rows
  LOOP
    -- Try to update existing record first
    UPDATE credits 
    SET 
      total = credits.total + (credit_data->>'total')::double precision,
      consumed = credits.consumed + (credit_data->>'consumed')::double precision
    WHERE user_id = (credit_data->>'user_id')::uuid;
    
    -- If no record was updated (no existing record), insert a new one
    IF NOT FOUND THEN
      INSERT INTO credits (
        id,
        user_id,
        total,
        consumed,
        created_at
      ) VALUES (
        (credit_data->>'id')::bigint,
        (credit_data->>'user_id')::uuid,
        (credit_data->>'total')::double precision,
        (credit_data->>'consumed')::double precision,
        (credit_data->>'created_at')::timestamp with time zone
      );
    END IF;
  END LOOP;
  
  -- Return success result
  result := jsonb_build_object(
    'success', true,
    'organization_id', org_id
  );
  
  RETURN result;
  
EXCEPTION WHEN OTHERS THEN
  -- Return error information
  result := jsonb_build_object(
    'success', false,
    'error', SQLERRM,
    'error_detail', SQLSTATE
  );
  
  RETURN result;
END;$function$
;

CREATE OR REPLACE FUNCTION public.generate_geojson_id(geojson text)
 RETURNS text
 LANGUAGE plpgsql
AS $function$
DECLARE
    json_string text;
    hash bytea;
BEGIN
    
    -- Compute the SHA-256 hash of the JSON string
    hash := digest(geojson, 'sha256');
    
    -- Convert the hash to a hexadecimal string
    RETURN encode(hash, 'hex');
END;
$function$
;

CREATE OR REPLACE FUNCTION public.generate_geojson_id(geometry jsonb)
 RETURNS text
 LANGUAGE plpgsql
AS $function$
DECLARE
    json_string text;
    hash bytea;
BEGIN
    -- Convert the geometry to a JSON string with consistent formatting
    json_string := to_jsonb(geometry)::text;
    
    -- Compute the SHA-256 hash of the JSON string
    hash := digest(json_string, 'sha256');
    
    -- Convert the hash to a hexadecimal string
    RETURN encode(hash, 'hex');
END;
$function$
;

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

CREATE OR REPLACE FUNCTION public.get_api_key_hits(org_id uuid DEFAULT NULL::uuid, limit_val integer DEFAULT 10, page_val integer DEFAULT 1)
 RETURNS TABLE(full_name text, user_id uuid, api_key text, path text, hit_count integer)
 LANGUAGE plpgsql
AS $function$
BEGIN
    IF org_id IS NULL THEN
        -- When no organization is specified, get all API keys and their usage
        RETURN QUERY
        SELECT
            p.full_name,
            p.user_id,
            ak.api_key,
            h.path,
            COALESCE(count(*), 0)::integer as hit_count
        FROM api_keys ak
        LEFT JOIN profile p ON p.user_id = ak.user_id
        LEFT JOIN hits h ON h.api_key = ak.api_key
        WHERE h.path IS NOT NULL
        GROUP BY p.full_name, p.user_id, ak.api_key, h.path
        ORDER BY hit_count DESC
        LIMIT limit_val
        OFFSET limit_val * GREATEST(page_val - 1, 0);
    ELSE
        -- When organization is specified, get API keys for that organization
        RETURN QUERY
        SELECT
            p.full_name,
            p.user_id,
            ak.api_key,
            h.path,
            COALESCE(count(*), 0)::integer as hit_count
        FROM api_keys ak
        LEFT JOIN profile p ON p.user_id = ak.user_id
        LEFT JOIN hits h ON h.api_key = ak.api_key
        WHERE ak.organization_id = org_id
          AND h.path IS NOT NULL
        GROUP BY p.full_name, p.user_id, ak.api_key, h.path
        ORDER BY hit_count DESC
        LIMIT limit_val
        OFFSET limit_val * GREATEST(page_val - 1, 0);
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

CREATE OR REPLACE FUNCTION public.get_count_for_super_admin(org_id uuid DEFAULT NULL::uuid)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
AS $function$
DECLARE
  project_count integer;
  org_count integer;
  user_count integer;
  result jsonb;
BEGIN
  -- Get count of projects based on org_id
  IF org_id IS NULL THEN
    -- Count all projects if org_id is NULL
    SELECT COUNT(*)
    INTO project_count
    FROM projects;
  ELSE
    -- Count projects for the specified organization
    SELECT COUNT(*)
    INTO project_count
    FROM projects
    WHERE organization_id = org_id;
  END IF;
  
  -- Get total count of organizations
  SELECT COUNT(*)
  INTO org_count
  FROM organizations;
  
  -- Get user count based on org_id
  IF org_id IS NULL THEN
    -- Count distinct users across all organizations if org_id is NULL
    SELECT COUNT(DISTINCT user_id)
    INTO user_count
    FROM organization_roles;
  ELSE
    -- Count users for the specified organization
    SELECT COUNT(*)
    INTO user_count
    FROM organization_roles
    WHERE organization_id = org_id;
  END IF;
  
  -- Construct the JSON result
  result := jsonb_build_object(
    'projects', project_count,
    'orgs', org_count,
    'users', user_count
  );
  
  RETURN result;
END;
$function$
;

CREATE OR REPLACE FUNCTION public.get_daywise_api_usage()
 RETURNS TABLE(date date, endpoint text, total_hits integer, average_latency numeric, error_hits integer)
 LANGUAGE sql
AS $function$
    SELECT 
        hits.created_at::date AS date,
        hits.path AS endpoint,
        COUNT(*) AS total_hits,
        AVG(hits.time_taken) AS average_latency,
        COUNT(*) FILTER (WHERE hits.status_code >= 400) AS error_hits
    FROM 
        credits 
        JOIN hits ON credits.user_id = hits.user_id
    WHERE 
        credits.user_id = auth.uid()
    GROUP BY 
        hits.created_at::date, hits.path
    ORDER BY 
        hits.created_at::date DESC;
$function$
;

CREATE OR REPLACE FUNCTION public.get_distinct_column_values(in_schema_name text, in_table_name text, in_column_name text)
 RETURNS TABLE(distinct_value text)
 LANGUAGE plpgsql
AS $function$
BEGIN
    RETURN QUERY EXECUTE format(
        'SELECT DISTINCT %I::TEXT FROM %I.%I',
        in_column_name, in_schema_name, in_table_name
    );
END;
$function$
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

CREATE OR REPLACE FUNCTION public.get_org_credits(org_id uuid)
 RETURNS TABLE(organization_id uuid, total double precision, consumed double precision, remaining numeric, expires_at timestamp without time zone)
 LANGUAGE sql
AS $function$
  select organization_id, total, consumed, remaining, expires_at 
  from org_credits 
  where organization_id = org_id;
$function$
;

CREATE OR REPLACE FUNCTION public.get_org_user_endpoint_hits(org_id uuid, p_user_identifier uuid, start_date date DEFAULT NULL::date, end_date date DEFAULT NULL::date)
 RETURNS TABLE(path text, hit_date date, hit_count integer)
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
begin
    return query
    select h.path, created_at::date, count(1)::integer from hits h where h.api_key in (select api_key from api_keys where organization_id = org_id and user_id = p_user_identifier)
    and ((start_date is null and end_date is null)
        or (start_date is not null and end_date is null and h.created_at::date = start_date)
        or (start_date is not null and end_date is not null and h.created_at::date between start_date and end_date))
    group by h.created_at::date, h.path order by count desc, h.created_at::date;
end;
$function$
;

CREATE OR REPLACE FUNCTION public.get_organization_members_with_credits_pagination_filters(org_id uuid, filter_name text DEFAULT NULL::text, filter_email text DEFAULT NULL::text, filter_role text DEFAULT NULL::text, page integer DEFAULT 1, page_size integer DEFAULT 10)
 RETURNS TABLE(user_id uuid, role text, full_name text, email text, avatar_url text, credits double precision, consumed double precision, remaining double precision, project_count bigint, total_count bigint, last_sign_in_at timestamp with time zone)
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
BEGIN
  RETURN QUERY
  WITH project_counts AS (
    -- Pre-calculate project counts in a separate CTE
    SELECT 
      projects.user_id,
      COUNT(*) AS count
    FROM public.projects
    WHERE projects.organization_id = org_id
    GROUP BY projects.user_id
  ),
  filtered_data AS (
    SELECT
      r.user_id,
      r.role,
      p.full_name,
      p.email,
      p.avatar_url,
      COALESCE(c.total, 0::double precision) AS credits,
      COALESCE(c.consumed, 0::double precision) AS consumed,
      COALESCE(c.remaining, 0::double precision) AS remaining,
      COALESCE(pc.count, 0::bigint) AS project_count,
      au.last_sign_in_at,
      COUNT(*) OVER() AS total_count
    FROM public.organization_roles r
    LEFT JOIN public.profile p ON r.user_id = p.user_id
    LEFT JOIN public.credits c ON r.user_id = c.user_id
    LEFT JOIN project_counts pc ON r.user_id = pc.user_id
    LEFT JOIN auth.users au ON r.user_id = au.id
    WHERE r.organization_id = org_id
      AND (filter_name IS NULL OR filter_name = '' OR p.full_name ILIKE '%' || filter_name || '%')
      AND (filter_email IS NULL OR filter_email = '' OR p.email ILIKE '%' || filter_email || '%')
      AND (filter_role IS NULL OR filter_role = '' OR LOWER(r.role) LIKE '%' || LOWER(filter_role) || '%')
  )
  SELECT 
    filtered_data.user_id, 
    filtered_data.role, 
    filtered_data.full_name, 
    filtered_data.email, 
    filtered_data.avatar_url, 
    filtered_data.credits, 
    filtered_data.consumed,
    filtered_data.remaining,
    filtered_data.project_count,
    filtered_data.total_count,
    filtered_data.last_sign_in_at
  FROM filtered_data
  ORDER BY filtered_data.full_name ASC
  LIMIT page_size
  OFFSET (page - 1) * page_size;
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

CREATE OR REPLACE FUNCTION public.get_organization_roles_count(org_id uuid)
 RETURNS integer
 LANGUAGE plpgsql
AS $function$DECLARE
  v_count BIGINT;
BEGIN
  SELECT COUNT(1) INTO v_count
  FROM organization_roles r
  WHERE r.organization_id = org_id;

  RETURN v_count;              -- send it back to the caller
END;$function$
;

CREATE OR REPLACE FUNCTION public.get_organization_roles_with_credits(org_id uuid)
 RETURNS TABLE(user_id uuid, role text, full_name text, email text, avatar_url text, credits double precision, consumed double precision)
 LANGUAGE plpgsql
 SECURITY DEFINER
AS $function$
BEGIN
  RETURN QUERY
  SELECT
    r.user_id,
    r.role,
    p.full_name,
    p.email,
    p.avatar_url,
    COALESCE(c.total, 0::double precision) AS credits,
    COALESCE(c.consumed, 0::double precision) AS consumed
  FROM organization_roles r
  LEFT JOIN profile p ON r.user_id = p.user_id
  LEFT JOIN credits c ON r.user_id = c.user_id
  WHERE r.organization_id = org_id;
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

CREATE OR REPLACE FUNCTION public.get_project_details(project_id bigint)
 RETURNS jsonb
 LANGUAGE plpgsql
AS $function$DECLARE
    role_details jsonb;
    saved_by jsonb;
    project_role_details jsonb;
BEGIN
    -- 1. Unique users with per-org roles in organizations
    SELECT jsonb_agg(jsonb_build_object(
        'user_id', user_id,
        'name', full_name,
        'organizations', organizations
    )) INTO role_details
    FROM (
        SELECT
            orl.user_id,
            p.full_name,
            (
                SELECT jsonb_agg(DISTINCT jsonb_build_object(
                    'organization_id', o.id,
                    'organization_name', o.name,
                    'role', orl2.role
                ))
                FROM public.organization_roles orl2
                JOIN public.organizations o ON o.id = orl2.organization_id
                WHERE orl2.user_id = orl.user_id
            ) AS organizations
        FROM public.project_roles pr
        JOIN public.organization_roles orl ON pr.user_id = orl.user_id
        LEFT JOIN public.profile p ON pr.user_id = p.user_id
        WHERE pr.project_id = $1
        GROUP BY orl.user_id, p.full_name
    ) grouped;

    -- 2. Group by project_role
    SELECT jsonb_object_agg(role, users) INTO project_role_details
    FROM (
        SELECT pr.project_role AS role,
               jsonb_agg(DISTINCT jsonb_build_object(
                   'name', p.full_name,
                   'user_id', pr.user_id
               )) AS users
        FROM public.project_roles pr
        LEFT JOIN public.profile p ON pr.user_id = p.user_id
        WHERE pr.project_id = $1
        GROUP BY pr.project_role
    ) grouped;

    -- 3. Get saved_by metadata
    SELECT jsonb_build_object('name', p2.full_name, 'user_id', pr.saved_by)
    INTO saved_by
    FROM public.projects pr
    LEFT JOIN public.profile p2 ON pr.saved_by::uuid = p2.user_id
    WHERE pr.id = $1;

    -- 4. Return final JSON object
    RETURN jsonb_build_object(
        'roles', COALESCE(role_details, '[]'::jsonb),
        'project_roles', COALESCE(project_role_details, '{}'::jsonb),
        'saved_by', saved_by
    );
END;$function$
;

CREATE OR REPLACE FUNCTION public.get_project_permissions(p_user_id uuid, p_project_id bigint)
 RETURNS TABLE(permission text, is_granted boolean)
 LANGUAGE plpgsql
AS $function$
BEGIN
    RETURN QUERY
    WITH custom_permissions AS (
        SELECT pup.permission, pup.is_granted
        FROM public.project_user_permissions pup
        WHERE pup.user_id = p_user_id
          AND pup.project_id = p_project_id
    ),
    role_permissions AS (
        SELECT prp.permission, prp.is_granted
        FROM public.project_roles pr
        JOIN public.project_role_permissions prp ON pr.project_role = prp.project_role
        WHERE pr.user_id = p_user_id
          AND pr.project_id = p_project_id
    ),
    project_permissions AS (
        SELECT pp.permission, pp.is_granted
        FROM public.project_permissions pp
        WHERE pp.project_id = p_project_id
    ),
    org_permissions AS (
        SELECT op.permission, op.is_granted
        FROM public.organization_permissions op
        JOIN public.projects proj ON proj.organization_id = op.organization_id
        WHERE proj.id = p_project_id
    )
    SELECT custom_permissions.permission, custom_permissions.is_granted
    FROM custom_permissions
    UNION ALL
    SELECT role_permissions.permission, role_permissions.is_granted
    FROM role_permissions
    WHERE role_permissions.permission NOT IN (SELECT custom_permissions.permission FROM custom_permissions)
    UNION ALL
    SELECT project_permissions.permission, project_permissions.is_granted
    FROM project_permissions
    WHERE project_permissions.permission NOT IN (SELECT custom_permissions.permission FROM custom_permissions)
      AND project_permissions.permission NOT IN (SELECT role_permissions.permission FROM role_permissions)
    UNION ALL
    SELECT org_permissions.permission, org_permissions.is_granted
    FROM org_permissions
    WHERE org_permissions.permission NOT IN (SELECT custom_permissions.permission FROM custom_permissions)
      AND org_permissions.permission NOT IN (SELECT role_permissions.permission FROM role_permissions)
      AND org_permissions.permission NOT IN (SELECT project_permissions.permission FROM project_permissions);
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

CREATE OR REPLACE FUNCTION public.get_project_users_with_roles(p_project_id bigint)
 RETURNS TABLE(id bigint, title character varying, user_id uuid, project_role text, role_assigned_at timestamp with time zone, role_updated_at timestamp with time zone, visibility text, organization_id uuid, owner_id uuid, email text, full_name text, avatar_url text)
 LANGUAGE plpgsql
AS $function$
BEGIN
    RETURN QUERY
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
        prof.email AS email,
        prof.full_name AS full_name,
        prof.avatar_url AS avatar_url
    FROM 
        public.projects p
    LEFT JOIN 
        public.project_roles pr ON p.id = pr.project_id
    LEFT JOIN 
        public.profile prof ON pr.user_id = prof.user_id
    WHERE 
        p.id = p_project_id
        AND (p.visibility <> 'private' OR pr.user_id IS NOT NULL);
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

CREATE OR REPLACE FUNCTION public.get_rjcorp_column_names(in_table_name text, in_table_schema text)
 RETURNS TABLE(column_name text)
 LANGUAGE plpgsql
AS $function$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_name = in_table_name
          AND table_schema = in_table_schema
    ) THEN
        RETURN QUERY
        SELECT c.column_name::TEXT
        FROM information_schema.columns c
        WHERE c.table_name = in_table_name
          AND c.table_schema = in_table_schema;
    ELSE
        RETURN QUERY
        SELECT 'Table not found in schema'::TEXT;
    END IF;
END;
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

CREATE OR REPLACE FUNCTION public.get_table_columns_with_types(in_table_schema text, in_table_name text)
 RETURNS TABLE(column_name text, data_type text)
 LANGUAGE plpgsql
AS $function$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = in_table_schema
          AND table_name   = in_table_name
    ) THEN

        RETURN QUERY
        SELECT c.column_name::text,
               c.data_type::text
        FROM   information_schema.columns AS c
        WHERE  c.table_schema = in_table_schema
          AND  c.table_name   = in_table_name
        ORDER  BY c.ordinal_position;

    ELSE
        RETURN QUERY
        SELECT 'Table not found in schema'::text,
               NULL::text;
    END IF;
END;
$function$
;

CREATE OR REPLACE FUNCTION public.get_user_claims()
 RETURNS jsonb
 LANGUAGE sql
 STABLE
 SET search_path TO 'public'
AS $function$
SELECT coalesce(
    current_setting('request.organizations', true)::jsonb, 
    auth.jwt()->'app_metadata'->'organizations'
)::jsonb;
$function$
;

CREATE OR REPLACE FUNCTION public.get_user_credits_for_super_admin(user_ids uuid[])
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
DECLARE
  result JSONB := '{}'::JSONB;
  user_record RECORD;
BEGIN
  -- Loop through each user ID and build the JSON object
  FOR user_record IN 
    SELECT 
      c.user_id,
      c.total,
      c.consumed,
      c.remaining
    FROM 
      public.credits c
    WHERE 
      c.user_id = ANY(user_ids)
  LOOP
    -- Add this user's data to our result object
    result := result || jsonb_build_object(
      user_record.user_id::TEXT, 
      jsonb_build_object(
        'total', user_record.total,
        'consumed', user_record.consumed,
        'remaining', user_record.remaining
      )
    );
  END LOOP;
  
  RETURN result;
END;
$function$
;

CREATE OR REPLACE FUNCTION public.get_user_endpoints_by_organization(org_id uuid)
 RETURNS TABLE(full_name text, email text, user_id uuid, path text, hit_count integer, avatar_url text)
 LANGUAGE plpgsql
AS $function$BEGIN
  RETURN QUERY
  WITH 
    selected_orgs AS (
      SELECT r.user_id, r.organization_id 
      FROM organization_roles r 
      WHERE r.organization_id = org_id
    ), 
    hit_counts AS (
      SELECT 
        h.path, 
        COUNT(h.path) AS total_hits, 
        h.user_id 
      FROM hits h
      WHERE h.user_id IN (SELECT so.user_id FROM selected_orgs so)
      GROUP BY h.user_id, h.path
    )
SELECT 
  hc.user_id::text AS user_id,  -- cast uuid to text
  p.full_name,
  p.avatar_url,
  hc.path AS endpoint,
  hc.total_hits 
FROM hit_counts hc 
JOIN profile p ON hc.user_id = p.user_id;
END;$function$
;

CREATE OR REPLACE FUNCTION public.get_user_endpoints_by_organization_2(org_id uuid)
 RETURNS TABLE(full_name text, user_uuid uuid, api_key text, path text, hit_count integer)
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
begin
    return query
    select p.full_name, p.user_id, ak.api_key, h.path, count(*)::integer as hit_count  from profile p
    join api_keys ak on ak.user_id = p.user_id and ak.organization_id = org_id
    left join hits h on h.api_key = ak.api_key
    where p.user_id in (select o.user_id from organization_roles o where o.organization_id = org_id)
    group by p.user_id, ak.api_key, h.path;
end;
$function$
;

CREATE OR REPLACE FUNCTION public.get_user_full_names_by_org(p_organization_id uuid)
 RETURNS TABLE(full_name text, email text, role text, quota integer, consumed integer, avatar_url text)
 LANGUAGE plpgsql
AS $function$
BEGIN
  RETURN QUERY
  SELECT 
         p.full_name AS profile_full_name,
         p.email,
         org_role.role,
         ouc.quota::integer,
         ouc.consumed::integer,
         p.avatar_url
  FROM organization_roles org_role
  JOIN profile p ON org_role.user_id = p.user_id
  LEFT JOIN org_user_credits ouc ON ouc.organization_id = org_role.organization_id 
                                AND ouc.user_id = org_role.user_id
  WHERE org_role.organization_id = p_organization_id;
END;
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

CREATE OR REPLACE FUNCTION public.get_user_projects_with_roles(p_user_id uuid)
 RETURNS TABLE(id bigint, title character varying, project_role text, role_assigned_at timestamp with time zone, role_updated_at timestamp with time zone, visibility text, organization_id uuid, owner_id uuid)
 LANGUAGE plpgsql
AS $function$
BEGIN
    RETURN QUERY
    SELECT 
        p.id AS id,
        p.title AS title,
        COALESCE(pr.project_role,
                  CASE
                      WHEN o.organization_id IS NOT NULL AND p.visibility = 'internal' THEN 'viewer'
                      ELSE NULL
                  END) AS project_role,
        pr.created_at AS role_assigned_at,
        pr.updated_at AS role_updated_at,
        p.visibility AS visibility,
        p.organization_id AS organization_id,
        p.user_id as owner_id
    FROM 
        public.projects p
    LEFT JOIN 
        public.project_roles pr ON p.id = pr.project_id AND pr.user_id = p_user_id
    LEFT JOIN 
        public.organization_roles o ON o.organization_id = p.organization_id AND o.user_id = p_user_id
    WHERE 
        (p.visibility <> 'private' OR pr.user_id IS NOT NULL) 
        AND (o.organization_id IS NOT NULL OR pr.user_id IS NOT NULL);  -- Ensure the user is either in the organization or has a role
END; 
$function$
;

CREATE OR REPLACE FUNCTION public.get_user_projects_with_search_and_saved_by(input_user_id uuid, input_org_id uuid DEFAULT NULL::uuid, search_term text DEFAULT NULL::text, page integer DEFAULT 1, page_size integer DEFAULT 10)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
DECLARE
  result JSONB;
BEGIN
  WITH filtered_projects AS (
    SELECT 
      p.id,
      p.title,
      p.created_at,
      p.updated_at,
      p.visibility,
      p.is_template,
      p.saved_by,
      creator.full_name AS creator_name
    FROM 
      public.projects p
      INNER JOIN public.profile creator ON p.user_id = creator.user_id
    WHERE 
      p.user_id = input_user_id
      AND (input_org_id IS NULL OR p.organization_id = input_org_id)
      AND (search_term IS NULL OR search_term = '' OR p.title ILIKE '%' || search_term || '%')
    ORDER BY 
      p.created_at DESC
    LIMIT page_size
    OFFSET (page - 1) * page_size
  )
  SELECT jsonb_agg(
    jsonb_build_object(
      'id', fp.id,
      'title', fp.title,
      'created_at', fp.created_at,
      'updated_at', fp.updated_at,
      'visibility', fp.visibility,
      'is_template', fp.is_template,
      'user', jsonb_build_object(
        'full_name', fp.creator_name
      ),
      'saved_by', CASE 
        WHEN fp.saved_by IS NULL OR fp.saved_by = '' THEN NULL
        ELSE (
          SELECT saved_prof.full_name
          FROM public.profile saved_prof
          WHERE saved_prof.user_id::text = fp.saved_by
          LIMIT 1
        )
      END
    )
  ) INTO result
  FROM filtered_projects fp;

  RETURN COALESCE(result, '[]'::jsonb);
END;
$function$
;

CREATE OR REPLACE FUNCTION public.get_user_total_credits(input_user_id uuid)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
DECLARE
  result JSONB;
BEGIN
  -- Get the user's total credits from the credits table
  SELECT jsonb_build_object(
    'total', COALESCE(SUM(total), 0),
    'consumed', COALESCE(SUM(consumed), 0),
    'remaining', COALESCE(SUM(remaining), 0)
  ) INTO result
  FROM public.credits
  WHERE user_id = input_user_id;

  -- Return default values if no credits found
  RETURN COALESCE(result, jsonb_build_object(
    'total', 0,
    'consumed', 0,
    'remaining', 0
  ));
END;
$function$
;

CREATE OR REPLACE FUNCTION public.get_users_with_filters(filter text DEFAULT NULL::text, page integer DEFAULT 0, page_size integer DEFAULT 10, sort_column text DEFAULT 'full_name'::text, sort_ascending boolean DEFAULT true, organization_id uuid DEFAULT NULL::uuid)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
DECLARE
  result JSONB;
  from_offset INTEGER;
  to_offset INTEGER;
BEGIN
  -- Calculate pagination offsets
  from_offset := page * page_size;
  to_offset := from_offset + page_size - 1;
  
  -- Build the query with filtering, sorting, and pagination
  WITH filtered_users AS (
    SELECT 
      p.user_id,
      p.full_name,
      p.email,
      p.avatar_url,
      au.last_sign_in_at,
      -- Get credit information using subqueries
      COALESCE((SELECT SUM(c.total) FROM public.credits c WHERE c.user_id = p.user_id), 0) AS total_credits,
      COALESCE((SELECT SUM(c.consumed) FROM public.credits c WHERE c.user_id = p.user_id), 0) AS consumed_credits,
      COALESCE((SELECT SUM(c.remaining) FROM public.credits c WHERE c.user_id = p.user_id), 0) AS remaining_credits
    FROM 
      public.profile p
      LEFT JOIN auth.users au ON p.user_id = au.id
    WHERE 
      (filter IS NULL OR 
       p.full_name ILIKE '%' || filter || '%' OR 
       p.email ILIKE '%' || filter || '%')
      -- Filter by organization if organization_id is provided
      AND (
        get_users_with_filters.organization_id IS NULL 
        OR 
        p.user_id IN (
          SELECT om.user_id 
          FROM public.organization_roles om 
          WHERE om.organization_id = get_users_with_filters.organization_id
        )
      )
    ORDER BY
      CASE 
        WHEN sort_column = 'full_name' AND sort_ascending THEN p.full_name 
      END ASC,
      CASE 
        WHEN sort_column = 'full_name' AND NOT sort_ascending THEN p.full_name 
      END DESC,
      CASE 
        WHEN sort_column = 'email' AND sort_ascending THEN p.email 
      END ASC,
      CASE 
        WHEN sort_column = 'email' AND NOT sort_ascending THEN p.email 
      END DESC,
      CASE 
        WHEN sort_column = 'last_sign_in_at' AND sort_ascending THEN au.last_sign_in_at 
      END ASC,
      CASE 
        WHEN sort_column = 'last_sign_in_at' AND NOT sort_ascending THEN au.last_sign_in_at 
      END DESC,
      -- Default sorting if sort_column is not recognized
      CASE 
        WHEN sort_column NOT IN ('full_name', 'email', 'last_sign_in_at') AND sort_ascending THEN p.full_name 
      END ASC,
      CASE 
        WHEN sort_column NOT IN ('full_name', 'email', 'last_sign_in_at') AND NOT sort_ascending THEN p.full_name 
      END DESC
    LIMIT page_size
    OFFSET from_offset
  )
  SELECT 
    jsonb_agg(
      jsonb_build_object(
        'user_id', fu.user_id,
        'full_name', fu.full_name,
        'email', fu.email,
        'avatar_url', fu.avatar_url,
        'last_sign_in_at', fu.last_sign_in_at,
        'credits', jsonb_build_object(
          'total', fu.total_credits,
          'consumed', fu.consumed_credits,
          'remaining', fu.remaining_credits
        )
      )
    ) INTO result
  FROM 
    filtered_users fu;

  RETURN COALESCE(result, '[]'::jsonb);
END;
$function$
;

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

CREATE OR REPLACE FUNCTION public.has_org_permission(p_user_id uuid, p_organization_id uuid, p_permission text)
 RETURNS boolean
 LANGUAGE plpgsql
AS $function$
DECLARE
    custom_permission_granted boolean;
    role_permission_granted boolean;
    org_permission_granted boolean;
BEGIN
    -- Check for custom permissions
    SELECT is_granted INTO custom_permission_granted
    FROM public.organization_user_permissions oup
    WHERE oup.user_id = p_user_id
      AND oup.organization_id = p_organization_id
      AND oup.permission = p_permission
    LIMIT 1;  -- Limit to one result

    -- If custom permission is found and is granted, return true
    IF custom_permission_granted IS TRUE THEN
        RETURN true;
    END IF;

    -- If custom permission is found and is denied, return false
    IF custom_permission_granted IS FALSE THEN
        RETURN false;
    END IF;

    -- Check for role-based permissions
    SELECT orp.is_granted INTO role_permission_granted
    FROM public.organization_roles org_roles
    JOIN public.organization_role_permissions orp ON org_roles.role = orp.organization_role
    WHERE org_roles.user_id = p_user_id
      AND org_roles.organization_id = p_organization_id
      AND orp.permission = p_permission
    LIMIT 1;  -- Limit to one result

    -- If role-based permission is found and is granted, return true
    IF role_permission_granted IS TRUE THEN
        RETURN true;
    END IF;

    -- Check for organization-level permissions
    SELECT op.is_granted INTO org_permission_granted
    FROM public.organization_permissions op
    WHERE op.organization_id = p_organization_id
      AND op.permission = p_permission
    LIMIT 1;  -- Limit to one result

    -- Return the result of the organization-level permission check
    RETURN org_permission_granted IS TRUE;
END;
$function$
;

CREATE OR REPLACE FUNCTION public.has_project_permission(p_user_id uuid, p_project_id bigint, p_permission text)
 RETURNS boolean
 LANGUAGE plpgsql
AS $function$
DECLARE
    custom_permission_granted boolean;
    role_permission_granted boolean;
    project_permission_granted boolean;
    org_permission_granted boolean;
BEGIN
    -- Check for custom permissions
    SELECT is_granted INTO custom_permission_granted
    FROM public.project_user_permissions pup
    WHERE pup.user_id = p_user_id
      AND pup.project_id = p_project_id
      AND pup.permission = p_permission
    LIMIT 1;  -- Limit to one result

    -- If custom permission is found and is granted, return true
    IF custom_permission_granted IS TRUE THEN
        RETURN true;
    END IF;

    -- If custom permission is found and is denied, return false
    IF custom_permission_granted IS FALSE THEN
        RETURN false;
    END IF;

    -- Check for role-based permissions
    SELECT prp.is_granted INTO role_permission_granted
    FROM public.project_roles pr
    JOIN public.project_role_permissions prp ON pr.project_role = prp.project_role
    WHERE pr.user_id = p_user_id
      AND pr.project_id = p_project_id
      AND prp.permission = p_permission
    LIMIT 1;  -- Limit to one result

    -- If role-based permission is found and is granted, return true
    IF role_permission_granted IS TRUE THEN
        RETURN true;
    END IF;

    -- Check for project-level permissions
    SELECT pp.is_granted INTO project_permission_granted
    FROM public.project_permissions pp
    WHERE pp.project_id = p_project_id
      AND pp.permission = p_permission
    LIMIT 1;  -- Limit to one result

    -- If project-level permission is found, return the result
    IF project_permission_granted IS TRUE THEN
        RETURN true;
    END IF;

    -- Check for organization-level permissions that apply to the project
    SELECT op.is_granted INTO org_permission_granted
    FROM public.organization_permissions op
    JOIN public.projects proj ON proj.organization_id = op.organization_id
    WHERE proj.id = p_project_id
      AND op.permission = p_permission
    LIMIT 1;  -- Limit to one result

    -- Return the result of the organization-level permission check
    RETURN org_permission_granted IS TRUE;
END;
$function$
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

CREATE OR REPLACE FUNCTION public.jwt_is_expired()
 RETURNS boolean
 LANGUAGE plpgsql
 STABLE
 SET search_path TO 'public'
AS $function$
BEGIN
  RETURN extract(epoch FROM now()) > coalesce(auth.jwt()->>'exp', '0')::numeric;
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

CREATE OR REPLACE FUNCTION public.pgrst_watch()
 RETURNS event_trigger
 LANGUAGE plpgsql
AS $function$
   BEGIN
     NOTIFY pgrst, 'reload schema';
   END;
   $function$
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

CREATE OR REPLACE FUNCTION public.summarize_hits()
 RETURNS TABLE(endpoint text, total_hits bigint, average_latency double precision, error_hits bigint)
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
    WHERE user_id = auth.uid()
    GROUP BY path;
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

CREATE OR REPLACE FUNCTION public.update_project_roles(p_user_id uuid, p_role_changes jsonb)
 RETURNS void
 LANGUAGE plpgsql
AS $function$DECLARE
    current_project_id bigint;
    new_role text;
    existing_role text;
BEGIN
    -- Loop through each project_id and role in the changes
    FOR current_project_id, new_role IN SELECT * FROM jsonb_each_text(p_role_changes) LOOP
        -- Check if the role already exists for the given user and project
        SELECT project_role INTO existing_role
        FROM public.project_roles
        WHERE user_id = p_user_id AND project_id = current_project_id;

        IF existing_role IS NOT NULL THEN
            -- Update existing role
            UPDATE public.project_roles
            SET project_role = new_role,
                updated_at = now()
            WHERE  user_id = p_user_id AND project_id = current_project_id;
        ELSE
            -- Insert new role
            INSERT INTO public.project_roles (user_id, project_id, project_role, created_at, updated_at)
            VALUES (p_user_id, current_project_id, new_role, now(), now());
        END IF;
    END LOOP;
END;$function$
;

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

CREATE OR REPLACE FUNCTION public.update_user_credits_super_admin(input_user_id uuid, new_total integer)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
DECLARE
  updated_record JSONB;
BEGIN
  -- Check if record exists
  IF EXISTS (SELECT 1 FROM public.credits WHERE user_id = input_user_id) THEN
    -- Update only the total column
    UPDATE public.credits
    SET total = new_total
    WHERE user_id = input_user_id
    RETURNING jsonb_build_object(
      'user_id', user_id,
      'total', total
    ) INTO updated_record;
  ELSE
    -- If no record exists, create a new one with just the required fields
    INSERT INTO public.credits (user_id, total)
    VALUES (input_user_id, new_total)
    RETURNING jsonb_build_object(
      'user_id', user_id,
      'total', total
    ) INTO updated_record;
  END IF;

  -- Return the updated record
  RETURN COALESCE(updated_record, jsonb_build_object(
    'error', 'Failed to update credits',
    'user_id', input_user_id
  ));
END;
$function$
;

CREATE OR REPLACE FUNCTION public.update_user_roles()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$DECLARE
  _organization_id TEXT = COALESCE(new.organization_id, old.organization_id)::TEXT;
  _organization_id_old TEXT = COALESCE(old.organization_id, new.organization_id)::TEXT;
  _user_id UUID = COALESCE(new.user_id, old.user_id);
  _user_id_old UUID = COALESCE(old.user_id, new.user_id);
  _role TEXT = COALESCE(new.role, old.role);
  _role_old TEXT = COALESCE(old.role, new.role);
  _raw_app_meta_data JSONB;
BEGIN
  -- Check if user_id or organization_id is changed
  IF _organization_id IS DISTINCT FROM _organization_id_old OR _user_id IS DISTINCT FROM _user_id_old THEN
      RAISE EXCEPTION 'Changing user_id or organization_id is not allowed';
  END IF;

  -- Fetch current raw_app_meta_data
  SELECT raw_app_meta_data INTO _raw_app_meta_data FROM auth.users WHERE id = _user_id;
  _raw_app_meta_data = coalesce(_raw_app_meta_data, '{}'::jsonb);

  -- Check if the record has been deleted or the role has been changed
  IF (TG_OP = 'DELETE') OR (TG_OP = 'UPDATE' AND _role IS DISTINCT FROM _role_old) THEN
    -- Remove role from raw_app_meta_data
    _raw_app_meta_data = jsonb_set(
        _raw_app_meta_data,
        '{organizations}',
        jsonb_strip_nulls(
            COALESCE(_raw_app_meta_data->'organizations', '{}'::jsonb) ||
            jsonb_build_object(
                _organization_id::text,
                (
                    SELECT jsonb_agg(val)
                    FROM jsonb_array_elements_text(COALESCE(_raw_app_meta_data->'organizations'->(_organization_id::text), '[]'::jsonb)) AS vals(val)
                    WHERE val <> _role_old
                )
            )
        )
    );
  END IF;

  -- Check if the record has been inserted or the role has been changed
  IF (TG_OP = 'INSERT') OR (TG_OP = 'UPDATE' AND _role IS DISTINCT FROM _role_old) THEN
    -- Add role to raw_app_meta_data
    _raw_app_meta_data = jsonb_set(
        _raw_app_meta_data,
        '{organizations}',
        COALESCE(_raw_app_meta_data->'organizations', '{}'::jsonb) ||
        jsonb_build_object(
            _organization_id::text,
            (
                SELECT jsonb_agg(DISTINCT val)
                FROM (
                    SELECT val
                    FROM jsonb_array_elements_text(COALESCE(_raw_app_meta_data->'organizations'->(_organization_id::text), '[]'::jsonb)) AS vals(val)
                    UNION
                    SELECT _role
                ) AS combined_roles(val)
            )
        )
    );
  END IF;

  -- Update raw_app_meta_data in auth.users
  UPDATE auth.users
  SET raw_app_meta_data = _raw_app_meta_data
  WHERE id = _user_id;

  -- Passthrough new record (the trigger function requires a return value)
  RETURN NEW;
END;$function$
;

CREATE OR REPLACE FUNCTION public.update_user_roles_for_project(p_project_id bigint, p_role_changes jsonb)
 RETURNS void
 LANGUAGE plpgsql
AS $function$
DECLARE
    current_user_id uuid;
    new_role text;
BEGIN
    -- Loop through each user_id and role in the changes
    FOR current_user_id, new_role IN SELECT * FROM jsonb_each_text(p_role_changes) LOOP
        IF new_role = 'remove' THEN
            -- Delete the user's project role
            DELETE FROM public.project_roles
            WHERE user_id = current_user_id AND project_id = p_project_id;
        ELSE
            -- Check if the role already exists for the given user and project
            IF EXISTS (
                SELECT 1
                FROM public.project_roles
                WHERE user_id = current_user_id AND project_id = p_project_id
            ) THEN
                -- Update existing role
                UPDATE public.project_roles
                SET project_role = new_role,
                    updated_at = now()
                WHERE user_id = current_user_id AND project_id = p_project_id;
            ELSE
                -- Insert new role
                INSERT INTO public.project_roles (user_id, project_id, project_role, created_at, updated_at)
                VALUES (current_user_id, p_project_id, new_role, now(), now());
            END IF;
        END IF;
    END LOOP;
END;
$function$
;

CREATE OR REPLACE FUNCTION public.user_has_organization_role(organization_id uuid, organization_role text)
 RETURNS boolean
 LANGUAGE plpgsql
 STABLE
 SET search_path TO 'public'
AS $function$
DECLARE 
  auth_role TEXT = auth.role();
  retval BOOLEAN;
BEGIN
    IF auth_role = 'authenticated' THEN
        IF jwt_is_expired() THEN
            RAISE EXCEPTION 'invalid_jwt' USING hint = 'jwt is expired or missing';
        END IF;
        -- Check if the user has the specified role in the organization
        SELECT coalesce(
            get_user_claims()->organization_id::TEXT ? organization_role,
            FALSE
        ) INTO retval;
        RETURN retval;
    ELSIF auth_role = 'anon' THEN
        RETURN FALSE;
    ELSE -- not a user session, probably being called from a trigger or something
        IF session_user = 'postgres' THEN
            RETURN TRUE;
        ELSE -- such as 'authenticator'
            RETURN FALSE;
        END IF;
    END IF;
END;
$function$
;

CREATE OR REPLACE FUNCTION public.user_is_organization_member(organization_id uuid)
 RETURNS boolean
 LANGUAGE plpgsql
 STABLE
 SET search_path TO 'public'
AS $function$
DECLARE
  auth_role TEXT = auth.role();
  retval BOOLEAN;
BEGIN
    IF auth_role = 'authenticated' THEN
        IF jwt_is_expired() THEN
            RAISE EXCEPTION 'invalid_jwt' USING hint = 'jwt is expired or missing';
        END IF;
        SELECT coalesce(get_user_claims() ? organization_id::TEXT, FALSE) INTO retval;
        RETURN retval;
    ELSIF auth_role = 'anon' THEN
        RETURN FALSE;
    ELSE -- not a user session, probably being called from a trigger or something
        IF session_user = 'postgres' THEN
            RETURN TRUE;
        ELSE -- such as 'authenticator'
            RETURN FALSE;
        END IF;
    END IF;
END;
$function$
;

create policy "AI Chat-Policy"
on "public"."chatbot-prompts"
as permissive
for all
to public
using (true)
with check (true);



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


