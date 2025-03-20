

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES  TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES  TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES  TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES  TO "service_role";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES  TO "supabase_auth_admin";

ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS  TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS  TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS  TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS  TO "service_role";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS  TO "supabase_auth_admin";

ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES  TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES  TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES  TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES  TO "service_role";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES  TO "supabase_auth_admin";

COMMENT ON SCHEMA "public" IS 'standard public schema';

GRANT USAGE ON SCHEMA "public" TO "anon";
GRANT USAGE ON SCHEMA "public" TO "authenticated";
GRANT USAGE ON SCHEMA "public" TO "service_role";
GRANT USAGE ON SCHEMA "public" TO "postgres";

CREATE SCHEMA IF NOT EXISTS "pgmq";

ALTER SCHEMA "pgmq" OWNER TO "postgres";

ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "pgmq" GRANT SELECT ON SEQUENCES  TO "pg_monitor";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "pgmq" GRANT SELECT ON TABLES  TO "pg_monitor";

CREATE EXTENSION IF NOT EXISTS "pg_cron" WITH SCHEMA "pg_catalog";

CREATE EXTENSION IF NOT EXISTS "pg_tle";

CREATE EXTENSION IF NOT EXISTS "pg_net" WITH SCHEMA "extensions";

CREATE EXTENSION IF NOT EXISTS "pgsodium" WITH SCHEMA "pgsodium";

CREATE EXTENSION IF NOT EXISTS "autoinc" WITH SCHEMA "extensions";

CREATE EXTENSION IF NOT EXISTS "http" WITH SCHEMA "extensions";

CREATE EXTENSION IF NOT EXISTS "moddatetime" WITH SCHEMA "extensions";

CREATE EXTENSION IF NOT EXISTS "pg_graphql" WITH SCHEMA "graphql";

CREATE EXTENSION IF NOT EXISTS "pg_stat_monitor" WITH SCHEMA "public";

CREATE EXTENSION IF NOT EXISTS "pg_stat_statements" WITH SCHEMA "extensions";

CREATE EXTENSION IF NOT EXISTS "pgaudit" WITH SCHEMA "extensions";

CREATE EXTENSION IF NOT EXISTS "pgcrypto" WITH SCHEMA "extensions";

CREATE EXTENSION IF NOT EXISTS "pgjwt" WITH SCHEMA "extensions";

CREATE EXTENSION IF NOT EXISTS "pgmq" WITH SCHEMA "pgmq";

CREATE EXTENSION IF NOT EXISTS "postgis" WITH SCHEMA "public";

CREATE EXTENSION IF NOT EXISTS "supabase_vault" WITH SCHEMA "vault";

CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA "extensions";

CREATE EXTENSION IF NOT EXISTS "wrappers" WITH SCHEMA "extensions";



CREATE TYPE "public"."region_type" AS ENUM (
    'COUNTRY',
    'STATE',
    'COUNTY',
    'CITY',
    'TOWN',
    'VILLAGE',
    'LOCALITY',
    'SUBLOCALITY',
    'PINCODE',
    'DISTRICT',
    'CUSTOM'
);


ALTER TYPE "public"."region_type" OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."add_profile"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    AS $$
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
$$;


ALTER FUNCTION "public"."add_profile"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."add_user_as_admin_and_member_to_new_organization"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    AS $$DECLARE
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
END;$$;


ALTER FUNCTION "public"."add_user_as_admin_and_member_to_new_organization"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."add_user_to_organization_based_on_domain"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    AS $$DECLARE
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

    RETURN NEW;
END;$$;


ALTER FUNCTION "public"."add_user_to_organization_based_on_domain"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."approve_org_join_request"("p_organization_id" "uuid", "p_user_id" "uuid", "p_role" "text", "p_request_id" bigint) RETURNS bigint
    LANGUAGE "plpgsql"
    AS $$BEGIN
    -- Insert into the organization_roles table
    INSERT INTO organization_roles (organization_id, user_id, role)
    VALUES (p_organization_id, p_user_id, p_role);

    -- Delete from the organization_join_requests table
    DELETE FROM organization_join_requests
    WHERE id = p_request_id;

    RETURN p_request_id; -- Return the request ID
END;$$;


ALTER FUNCTION "public"."approve_org_join_request"("p_organization_id" "uuid", "p_user_id" "uuid", "p_role" "text", "p_request_id" bigint) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."assign_owner_role"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    AS $$
BEGIN
    -- Insert the owner role for the user who created the project
    INSERT INTO public.project_roles (project_id, user_id, project_role)
    VALUES (NEW.id, NEW.user_id, 'owner');
    
    RETURN NEW;
END;
$$;


ALTER FUNCTION "public"."assign_owner_role"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."generate_geojson_id"("geometry" "jsonb") RETURNS "text"
    LANGUAGE "plpgsql"
    AS $$
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
$$;


ALTER FUNCTION "public"."generate_geojson_id"("geometry" "jsonb") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."generate_geojson_id"("geojson" "text") RETURNS "text"
    LANGUAGE "plpgsql"
    AS $$
DECLARE
    json_string text;
    hash bytea;
BEGIN
    
    -- Compute the SHA-256 hash of the JSON string
    hash := digest(geojson, 'sha256');
    
    -- Convert the hash to a hexadecimal string
    RETURN encode(hash, 'hex');
END;
$$;


ALTER FUNCTION "public"."generate_geojson_id"("geojson" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."get_hit_statistics"("start_date" timestamp without time zone, "end_date" timestamp without time zone) RETURNS TABLE("path" character varying, "total_hits" integer, "average_latency" numeric, "error_hits" integer)
    LANGUAGE "plpgsql"
    AS $$
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
$$;


ALTER FUNCTION "public"."get_hit_statistics"("start_date" timestamp without time zone, "end_date" timestamp without time zone) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."get_hits_count_past_24_hours"() RETURNS TABLE("hour_truncated" timestamp with time zone, "hit_count" bigint)
    LANGUAGE "plpgsql"
    AS $$
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
$$;


ALTER FUNCTION "public"."get_hits_count_past_24_hours"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."get_organization_roles"() RETURNS "text"[]
    LANGUAGE "plpgsql"
    AS $$
BEGIN
    RETURN (SELECT ARRAY_AGG(DISTINCT organization_role) FROM organization_role_permissions);
END;
$$;


ALTER FUNCTION "public"."get_organization_roles"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."get_permissions_by_organization_role"("organization_role_value" "text") RETURNS TABLE("permission" "text", "is_granted" boolean)
    LANGUAGE "plpgsql"
    AS $$BEGIN
    RETURN QUERY
    SELECT 
        opr.permission,
        opr.is_granted
    FROM 
        public.organization_role_permissions opr
    WHERE 
        opr.organization_role = organization_role_value;
END;$$;


ALTER FUNCTION "public"."get_permissions_by_organization_role"("organization_role_value" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."get_permissions_by_project_role"("project_role_value" "text") RETURNS TABLE("permission" "text", "is_granted" boolean)
    LANGUAGE "plpgsql"
    AS $$
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
$$;


ALTER FUNCTION "public"."get_permissions_by_project_role"("project_role_value" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."get_project_permissions"("p_user_id" "uuid", "p_project_id" bigint) RETURNS TABLE("permission" "text", "is_granted" boolean)
    LANGUAGE "plpgsql"
    AS $$
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
$$;


ALTER FUNCTION "public"."get_project_permissions"("p_user_id" "uuid", "p_project_id" bigint) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."get_project_roles"() RETURNS "text"[]
    LANGUAGE "plpgsql"
    AS $$
BEGIN
    RETURN (SELECT ARRAY_AGG(DISTINCT project_role) FROM project_role_permissions);
END;
$$;


ALTER FUNCTION "public"."get_project_roles"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."get_project_users_with_roles"("p_project_id" bigint) RETURNS TABLE("id" bigint, "title" character varying, "user_id" "uuid", "project_role" "text", "role_assigned_at" timestamp with time zone, "role_updated_at" timestamp with time zone, "visibility" "text", "organization_id" "uuid", "owner_id" "uuid", "email" "text", "full_name" "text", "avatar_url" "text")
    LANGUAGE "plpgsql"
    AS $$
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
$$;


ALTER FUNCTION "public"."get_project_users_with_roles"("p_project_id" bigint) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."get_projects_by_user_id"("p_user_id" "text") RETURNS TABLE("id" bigint, "title" "text", "user_id" "uuid", "project_role" "text", "role_assigned_at" timestamp with time zone, "role_updated_at" timestamp with time zone, "visibility" "text", "organization_id" bigint, "owner_id" "uuid", "email" "text", "full_name" "text", "avatar_url" "text")
    LANGUAGE "plpgsql"
    AS $$
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
$$;


ALTER FUNCTION "public"."get_projects_by_user_id"("p_user_id" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."get_table"("_tbl_type" "anyelement") RETURNS SETOF "anyelement"
    LANGUAGE "plpgsql"
    AS $$
BEGIN
   RETURN QUERY EXECUTE format('TABLE %s', pg_typeof(_tbl_type));
END
$$;


ALTER FUNCTION "public"."get_table"("_tbl_type" "anyelement") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."get_user_claims"() RETURNS "jsonb"
    LANGUAGE "sql" STABLE
    SET "search_path" TO 'public'
    AS $$
SELECT coalesce(
    current_setting('request.organizations', true)::jsonb, 
    auth.jwt()->'app_metadata'->'organizations'
)::jsonb;
$$;


ALTER FUNCTION "public"."get_user_claims"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."get_user_projects_by_organization"("p_organization_id" "uuid", "p_user_id" "uuid") RETURNS TABLE("project_id" bigint, "project_title" "text", "project_created_at" timestamp with time zone, "project_updated_at" timestamp with time zone, "shared_with" "jsonb")
    LANGUAGE "plpgsql"
    AS $$BEGIN
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
END;$$;


ALTER FUNCTION "public"."get_user_projects_by_organization"("p_organization_id" "uuid", "p_user_id" "uuid") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."get_user_projects_with_roles"("p_user_id" "uuid") RETURNS TABLE("id" bigint, "title" character varying, "project_role" "text", "role_assigned_at" timestamp with time zone, "role_updated_at" timestamp with time zone, "visibility" "text", "organization_id" "uuid", "owner_id" "uuid")
    LANGUAGE "plpgsql"
    AS $$
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
$$;


ALTER FUNCTION "public"."get_user_projects_with_roles"("p_user_id" "uuid") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."has_org_permission"("p_user_id" "uuid", "p_organization_id" "uuid", "p_permission" "text") RETURNS boolean
    LANGUAGE "plpgsql"
    AS $$
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
$$;


ALTER FUNCTION "public"."has_org_permission"("p_user_id" "uuid", "p_organization_id" "uuid", "p_permission" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."has_project_permission"("p_user_id" "uuid", "p_project_id" bigint, "p_permission" "text") RETURNS boolean
    LANGUAGE "plpgsql"
    AS $$
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
$$;


ALTER FUNCTION "public"."has_project_permission"("p_user_id" "uuid", "p_project_id" bigint, "p_permission" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."is_active_trigger_function"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    AS $$
BEGIN
  -- Insert the same data into the 'target' table
  -- INSERT INTO public.is_active(user_id) VALUES (NEW.id);

  -- If you want to cancel the insert operation in the 'source' table, uncomment the line below
  -- RETURN NULL;

  -- Return the NEW row to allow the original insert operation on the 'source' table to proceed
  RETURN NEW;
END;
$$;


ALTER FUNCTION "public"."is_active_trigger_function"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."jwt_is_expired"() RETURNS boolean
    LANGUAGE "plpgsql" STABLE
    SET "search_path" TO 'public'
    AS $$
BEGIN
  RETURN extract(epoch FROM now()) > coalesce(auth.jwt()->>'exp', '0')::numeric;
END;
$$;


ALTER FUNCTION "public"."jwt_is_expired"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."leave_organization"("p_user_id" "uuid", "p_organization_id" "uuid") RETURNS "void"
    LANGUAGE "plpgsql"
    AS $$DECLARE
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
END;$$;


ALTER FUNCTION "public"."leave_organization"("p_user_id" "uuid", "p_organization_id" "uuid") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."source_insert_trigger_function"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    AS $$
BEGIN
  -- Insert the same data into the 'target' table
  INSERT INTO public.credits(user_id,total,consumed) VALUES (NEW.id,50,0);

  -- If you want to cancel the insert operation in the 'source' table, uncomment the line below
  -- RETURN NULL;

  -- Return the NEW row to allow the original insert operation on the 'source' table to proceed
  RETURN NEW;
END;
$$;


ALTER FUNCTION "public"."source_insert_trigger_function"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."summarize_hits"() RETURNS TABLE("endpoint" "text", "total_hits" bigint, "average_latency" double precision, "error_hits" bigint)
    LANGUAGE "plpgsql"
    AS $$
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
$$;


ALTER FUNCTION "public"."summarize_hits"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."transfer_projects_and_remove_user"("p_user_id_owner" "uuid", "p_user_id_user" "uuid", "p_organization_id" "uuid") RETURNS "void"
    LANGUAGE "plpgsql"
    AS $$BEGIN

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


END$$;


ALTER FUNCTION "public"."transfer_projects_and_remove_user"("p_user_id_owner" "uuid", "p_user_id_user" "uuid", "p_organization_id" "uuid") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."update_project_roles"("p_user_id" "uuid", "p_role_changes" "jsonb") RETURNS "void"
    LANGUAGE "plpgsql"
    AS $$
DECLARE
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
            SET project_role = role,
                updated_at = now()
            WHERE  user_id = p_user_id AND project_id = current_project_id;
        ELSE
            -- Insert new role
            INSERT INTO public.project_roles (user_id, project_id, project_role, created_at, updated_at)
            VALUES (p_user_id, current_project_id, new_role, now(), now());
        END IF;
    END LOOP;
END;
$$;


ALTER FUNCTION "public"."update_project_roles"("p_user_id" "uuid", "p_role_changes" "jsonb") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."update_user_roles"() RETURNS "trigger"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'public'
    AS $$DECLARE
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
END;$$;


ALTER FUNCTION "public"."update_user_roles"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."update_user_roles_for_project"("p_project_id" bigint, "p_role_changes" "jsonb") RETURNS "void"
    LANGUAGE "plpgsql"
    AS $$
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
$$;


ALTER FUNCTION "public"."update_user_roles_for_project"("p_project_id" bigint, "p_role_changes" "jsonb") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."user_has_organization_role"("organization_id" "uuid", "organization_role" "text") RETURNS boolean
    LANGUAGE "plpgsql" STABLE
    SET "search_path" TO 'public'
    AS $$
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
$$;


ALTER FUNCTION "public"."user_has_organization_role"("organization_id" "uuid", "organization_role" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."user_is_organization_member"("organization_id" "uuid") RETURNS boolean
    LANGUAGE "plpgsql" STABLE
    SET "search_path" TO 'public'
    AS $$
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
$$;


ALTER FUNCTION "public"."user_is_organization_member"("organization_id" "uuid") OWNER TO "postgres";

SET default_tablespace = '';

SET default_table_access_method = "heap";


CREATE TABLE IF NOT EXISTS "public"."activities" (
    "id" integer NOT NULL,
    "user_id" "uuid" NOT NULL,
    "project_id" integer NOT NULL,
    "organisation_id" integer NOT NULL,
    "message" "text" NOT NULL,
    "timestamp" timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    "session_id" integer
);


ALTER TABLE "public"."activities" OWNER TO "postgres";


COMMENT ON TABLE "public"."activities" IS 'Contains activities over all projects';



COMMENT ON COLUMN "public"."activities"."session_id" IS 'defines the user current session';



CREATE TABLE IF NOT EXISTS "public"."api_keys" (
    "created_at" timestamp with time zone,
    "user_id" "uuid",
    "api_key" "text",
    "name" "text",
    "last_used" timestamp without time zone,
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL
);


ALTER TABLE "public"."api_keys" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."credits" (
    "id" bigint NOT NULL,
    "user_id" "uuid",
    "total" double precision,
    "consumed" double precision,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "remaining" double precision GENERATED ALWAYS AS (("total" - "consumed")) STORED
);


ALTER TABLE "public"."credits" OWNER TO "postgres";


COMMENT ON TABLE "public"."credits" IS 'this table can be used in a system where users need to manage credits, and you can perform various operations like deducting consumed credits or updating the total credits as needed.';



ALTER TABLE "public"."credits" ALTER COLUMN "id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."credits_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE SEQUENCE IF NOT EXISTS "public"."id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE "public"."id_seq" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."data_attribute" (
    "id" bigint DEFAULT "nextval"('"public"."id_seq"'::"regclass") NOT NULL,
    "name" "text",
    "description" "text",
    "type" "text",
    "dataset_id" integer,
    "show_on_tooltip" boolean,
    "attribute" boolean,
    "priority" integer DEFAULT 0,
    "unit" "text"
);


ALTER TABLE "public"."data_attribute" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."data_schema" (
    "id" bigint NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "url" "text",
    "type" "text",
    "name" "text",
    "organization_id" bigint,
    "user_id" "uuid",
    "provider" "text",
    "settings" "jsonb"
);


ALTER TABLE "public"."data_schema" OWNER TO "postgres";


ALTER TABLE "public"."data_schema" ALTER COLUMN "id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."data_schema_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."data_source" (
    "id" bigint NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "organization_id" bigint,
    "source" "jsonb",
    "name" "text",
    "style" "jsonb"
);


ALTER TABLE "public"."data_source" OWNER TO "postgres";


ALTER TABLE "public"."data_source" ALTER COLUMN "id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."data_source_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."dataset" (
    "id" bigint NOT NULL,
    "title" "text",
    "path" "text",
    "format" "text",
    "description" "text",
    "source" "text",
    "last updated" "text",
    "rows" bigint,
    "category" "text",
    "region" "text",
    "type" "text",
    "update frequence" "text",
    "sample_region" integer,
    "grid_sample_url" "text",
    "pincode_sample_url" "text",
    "locality_sample_url" "text",
    "icon_url" "text",
    "dataset_icon" "text",
    "identifier_attribute" "text",
    "priority" integer DEFAULT 0,
    "show_table" boolean DEFAULT false,
    "tags" "text" DEFAULT ''::"text"
);


ALTER TABLE "public"."dataset" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."gcp_usage_reports" (
    "operation_id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "user_procurement_id" "uuid",
    "created_at" timestamp with time zone DEFAULT "now"(),
    "consumer_id" character varying,
    "metric_name" character varying,
    "start_time" timestamp with time zone,
    "end_time" timestamp with time zone,
    "metric_value" real
);


ALTER TABLE "public"."gcp_usage_reports" OWNER TO "postgres";


COMMENT ON TABLE "public"."gcp_usage_reports" IS 'hourly usage reports of users for gcp.';



CREATE TABLE IF NOT EXISTS "public"."hits" (
    "id" "uuid" DEFAULT "gen_random_uuid"(),
    "created_at" timestamp with time zone DEFAULT "now"(),
    "user_id" "uuid",
    "status_code" integer,
    "time_taken" double precision,
    "ip_address" "text",
    "path" "text",
    "method" "text",
    "protocol" "text",
    "host" "text",
    "port" "text",
    "query_string" "text",
    "api_key" "text",
    "error_message" "text"
);


ALTER TABLE "public"."hits" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."logs" (
    "log_id" integer NOT NULL,
    "user_id" "uuid" NOT NULL,
    "project_id" integer NOT NULL,
    "organisation_id" integer NOT NULL,
    "level" character varying(50) NOT NULL,
    "message" "text" NOT NULL,
    "timestamp" timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    "metadata" "jsonb",
    "session_id" integer
);


ALTER TABLE "public"."logs" OWNER TO "postgres";


COMMENT ON COLUMN "public"."logs"."session_id" IS 'defines the user current session';



CREATE SEQUENCE IF NOT EXISTS "public"."logs_log_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE "public"."logs_log_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "public"."logs_log_id_seq" OWNED BY "public"."logs"."log_id";



CREATE TABLE IF NOT EXISTS "public"."organization_roles" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "organization_id" "uuid",
    "user_id" "uuid",
    "role" "text",
    "created_at" timestamp with time zone DEFAULT "now"(),
    "updated_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."organization_roles" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."my_organization_roles" AS
 SELECT DISTINCT "organization_roles"."user_id",
    "organization_roles"."organization_id",
    "organization_roles"."role"
   FROM "public"."organization_roles";


ALTER TABLE "public"."my_organization_roles" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."my_organizations" AS
 SELECT DISTINCT "organization_roles"."organization_id"
   FROM "public"."organization_roles"
  WHERE ("organization_roles"."user_id" = "auth"."uid"());


ALTER TABLE "public"."my_organizations" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."profile" (
    "user_id" "uuid" NOT NULL,
    "full_name" "text",
    "avatar_url" "text",
    "email" "text"
);


ALTER TABLE "public"."profile" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."org_members" AS
 SELECT "organization_roles"."user_id",
    "organization_roles"."organization_id",
    "organization_roles"."role",
    "profile"."full_name",
    "profile"."email"
   FROM ("public"."organization_roles"
     JOIN "public"."profile" ON (("organization_roles"."user_id" = "profile"."user_id")));


ALTER TABLE "public"."org_members" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."organization" (
    "id" bigint NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"(),
    "updated_at" timestamp with time zone DEFAULT "now"(),
    "name" "text",
    "logo_square_url" "text"
);


ALTER TABLE "public"."organization" OWNER TO "postgres";


COMMENT ON TABLE "public"."organization" IS 'Organization';



CREATE TABLE IF NOT EXISTS "public"."organization_domains" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "organization_id" "uuid" NOT NULL,
    "domain" "text" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


ALTER TABLE "public"."organization_domains" OWNER TO "postgres";


ALTER TABLE "public"."organization" ALTER COLUMN "id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."organization_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."organization_invites" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "organization_id" "uuid" NOT NULL,
    "role" "text" DEFAULT '{}'::"text"[] NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "email" "text",
    "token" "text" DEFAULT ''::"text" NOT NULL,
    "expires_at" "text" DEFAULT ("now"() + '7 days'::interval)
);


ALTER TABLE "public"."organization_invites" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."organization_join_requests" (
    "id" bigint NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "status" "text",
    "user_id" "uuid",
    "message" "text",
    "organization_id" "uuid"
);


ALTER TABLE "public"."organization_join_requests" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."organization_members" WITH ("security_invoker"='true') AS
 SELECT DISTINCT "organization_roles"."user_id",
    "organization_roles"."organization_id"
   FROM "public"."organization_roles";


ALTER TABLE "public"."organization_members" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."organization_permissions" (
    "id" integer NOT NULL,
    "organization_id" "uuid" NOT NULL,
    "permission" "text" NOT NULL,
    "is_granted" boolean DEFAULT false NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "created_by" "uuid" NOT NULL,
    "updated_by" "uuid"
);


ALTER TABLE "public"."organization_permissions" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "public"."organization_permissions_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE "public"."organization_permissions_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "public"."organization_permissions_id_seq" OWNED BY "public"."organization_permissions"."id";



CREATE OR REPLACE VIEW "public"."organization_profiles" AS
 SELECT "organization_roles"."organization_id",
    "organization_roles"."role",
    "profile"."user_id",
    "profile"."full_name",
    "profile"."avatar_url",
    "profile"."email"
   FROM ("public"."organization_roles"
     JOIN "public"."profile" ON (("organization_roles"."user_id" = "profile"."user_id")));


ALTER TABLE "public"."organization_profiles" OWNER TO "postgres";


ALTER TABLE "public"."organization_join_requests" ALTER COLUMN "id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."organization_requests_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."organization_role_permissions" (
    "id" bigint NOT NULL,
    "organization_role" "text" NOT NULL,
    "permission" "text" NOT NULL,
    "is_granted" boolean DEFAULT false NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


ALTER TABLE "public"."organization_role_permissions" OWNER TO "postgres";


ALTER TABLE "public"."organization_role_permissions" ALTER COLUMN "id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."organization_role_permissions_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."organization_user_permissions" (
    "id" bigint NOT NULL,
    "user_id" "uuid" NOT NULL,
    "organization_id" "uuid" NOT NULL,
    "permission" "text" NOT NULL,
    "is_granted" boolean DEFAULT false NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


ALTER TABLE "public"."organization_user_permissions" OWNER TO "postgres";


ALTER TABLE "public"."organization_user_permissions" ALTER COLUMN "id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."organization_user_permissions_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."organizations" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "name" "text" NOT NULL,
    "logo" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "category" "text",
    "domain" "text",
    "limit_per_role" "json" DEFAULT '{   "admin": 1,   "analyst": 5,   "viewer": 20 }'::"json"
);


ALTER TABLE "public"."organizations" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."project" (
    "id" bigint NOT NULL,
    "title" character varying,
    "organization_id" bigint,
    "created_at" timestamp with time zone DEFAULT "now"(),
    "updated_at" timestamp with time zone DEFAULT "now"(),
    "metadata" "jsonb",
    "state" "jsonb",
    "last_logged_in" timestamp with time zone,
    "tinybase" "jsonb" DEFAULT '{}'::"jsonb",
    "user_id" "uuid"
);


ALTER TABLE "public"."project" OWNER TO "postgres";


ALTER TABLE "public"."project" ALTER COLUMN "id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."project_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."project_permissions" (
    "id" bigint NOT NULL,
    "project_id" bigint NOT NULL,
    "permission" "text" NOT NULL,
    "is_granted" boolean DEFAULT false NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "created_by" "uuid" NOT NULL,
    "updated_by" "uuid"
);


ALTER TABLE "public"."project_permissions" OWNER TO "postgres";


ALTER TABLE "public"."project_permissions" ALTER COLUMN "id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."project_permissions_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."project_role_permissions" (
    "id" bigint NOT NULL,
    "project_role" "text" NOT NULL,
    "permission" "text" NOT NULL,
    "is_granted" boolean DEFAULT false NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


ALTER TABLE "public"."project_role_permissions" OWNER TO "postgres";


ALTER TABLE "public"."project_role_permissions" ALTER COLUMN "id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."project_role_permissions_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."project_roles" (
    "id" bigint NOT NULL,
    "project_id" bigint NOT NULL,
    "user_id" "uuid" NOT NULL,
    "project_role" "text" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


ALTER TABLE "public"."project_roles" OWNER TO "postgres";


ALTER TABLE "public"."project_roles" ALTER COLUMN "id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."project_roles_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."project_templates" (
    "id" bigint NOT NULL,
    "title" character varying,
    "created_at" timestamp with time zone DEFAULT "now"(),
    "updated_at" timestamp with time zone DEFAULT "now"(),
    "metadata" "jsonb",
    "tinybase" "jsonb",
    "user_id" "uuid",
    "organization_id" "uuid",
    "visibility" "text" DEFAULT 'private'::"text" NOT NULL,
    "project_id" bigint
);


ALTER TABLE "public"."project_templates" OWNER TO "postgres";


COMMENT ON TABLE "public"."project_templates" IS 'This table contains project templates';



ALTER TABLE "public"."project_templates" ALTER COLUMN "id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."project_templates_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."project_user_permissions" (
    "id" bigint NOT NULL,
    "user_id" "uuid" NOT NULL,
    "project_id" bigint NOT NULL,
    "permission" "text" NOT NULL,
    "is_granted" boolean DEFAULT false NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


ALTER TABLE "public"."project_user_permissions" OWNER TO "postgres";


ALTER TABLE "public"."project_user_permissions" ALTER COLUMN "id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."project_user_permissions_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."projects" (
    "id" bigint NOT NULL,
    "title" character varying,
    "created_at" timestamp with time zone DEFAULT "now"(),
    "updated_at" timestamp with time zone DEFAULT "now"(),
    "metadata" "jsonb",
    "tinybase" "jsonb",
    "user_id" "uuid",
    "organization_id" "uuid",
    "visibility" "text" DEFAULT 'private'::"text" NOT NULL,
    "is_template" boolean DEFAULT false
);


ALTER TABLE "public"."projects" OWNER TO "postgres";


COMMENT ON COLUMN "public"."projects"."is_template" IS 'Boolean that specifies if this is a template';



ALTER TABLE "public"."projects" ALTER COLUMN "id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."projects_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."region" (
    "id" integer NOT NULL,
    "name" character varying(100),
    "boundary_geom" "public"."geometry"(Geometry,4326),
    "type" "public"."region_type",
    "centroid_geom" "public"."geometry"(Point),
    "bounds_geom" "public"."geometry"
);


ALTER TABLE "public"."region" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "public"."state_ogc_fid_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE "public"."state_ogc_fid_seq" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."state" (
    "ogc_fid" integer DEFAULT "nextval"('"public"."state_ogc_fid_seq"'::"regclass") NOT NULL,
    "state_code" character varying(2) NOT NULL,
    "state_name" character varying(100),
    "simplified_geom" "public"."geometry"(Geometry,4326)
);


ALTER TABLE "public"."state" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."times" (
    "id" bigint NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "kolkata" "jsonb",
    "mumbai" "jsonb",
    "test" "jsonb"
);


ALTER TABLE "public"."times" OWNER TO "postgres";


ALTER TABLE "public"."times" ALTER COLUMN "id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."times_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."visits" (
    "id" bigint NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "name" "text",
    "comment" "jsonb",
    "identifier" "text",
    "images" "jsonb"
);


ALTER TABLE "public"."visits" OWNER TO "postgres";


ALTER TABLE "public"."visits" ALTER COLUMN "id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."visits_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."workflow_instances" (
    "id" bigint NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"(),
    "workflow_id" "uuid" DEFAULT "gen_random_uuid"(),
    "status" "text",
    "state" "jsonb" DEFAULT '{"edges": [], "nodes": []}'::"jsonb"
);


ALTER TABLE "public"."workflow_instances" OWNER TO "postgres";


ALTER TABLE "public"."workflow_instances" ALTER COLUMN "id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."workflow_instances_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."workflows" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"(),
    "name" "text",
    "metadata" "jsonb" DEFAULT '{}'::"jsonb"
);


ALTER TABLE "public"."workflows" OWNER TO "postgres";


ALTER TABLE ONLY "public"."logs" ALTER COLUMN "log_id" SET DEFAULT "nextval"('"public"."logs_log_id_seq"'::"regclass");



ALTER TABLE ONLY "public"."organization_permissions" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."organization_permissions_id_seq"'::"regclass");



ALTER TABLE ONLY "public"."activities"
    ADD CONSTRAINT "activities_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."api_keys"
    ADD CONSTRAINT "api_keys_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."credits"
    ADD CONSTRAINT "credits_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."data_attribute"
    ADD CONSTRAINT "data_attribute_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."data_schema"
    ADD CONSTRAINT "data_schema_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."data_source"
    ADD CONSTRAINT "data_source_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."dataset"
    ADD CONSTRAINT "dataset_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."gcp_usage_reports"
    ADD CONSTRAINT "gcp_usage_reports_pkey" PRIMARY KEY ("operation_id");



ALTER TABLE ONLY "public"."logs"
    ADD CONSTRAINT "logs_pkey" PRIMARY KEY ("log_id");



ALTER TABLE ONLY "public"."organization_domains"
    ADD CONSTRAINT "organization_domains_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."organization_invites"
    ADD CONSTRAINT "organization_invites_invitee_token_key" UNIQUE ("token");



ALTER TABLE ONLY "public"."organization_invites"
    ADD CONSTRAINT "organization_invites_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."organization_permissions"
    ADD CONSTRAINT "organization_permissions_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."organization"
    ADD CONSTRAINT "organization_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."organization_join_requests"
    ADD CONSTRAINT "organization_requests_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."organization_role_permissions"
    ADD CONSTRAINT "organization_role_permissions_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."organization_roles"
    ADD CONSTRAINT "organization_roles_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."organization_user_permissions"
    ADD CONSTRAINT "organization_user_permissions_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."organizations"
    ADD CONSTRAINT "organizations_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."profile"
    ADD CONSTRAINT "profile_pkey" PRIMARY KEY ("user_id");



ALTER TABLE ONLY "public"."project_permissions"
    ADD CONSTRAINT "project_permissions_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."project"
    ADD CONSTRAINT "project_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."project_role_permissions"
    ADD CONSTRAINT "project_role_permissions_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."project_roles"
    ADD CONSTRAINT "project_roles_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."project_templates"
    ADD CONSTRAINT "project_templates_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."project_user_permissions"
    ADD CONSTRAINT "project_user_permissions_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."projects"
    ADD CONSTRAINT "projects_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."region"
    ADD CONSTRAINT "region_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."times"
    ADD CONSTRAINT "times_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."organization_permissions"
    ADD CONSTRAINT "unique_organization_permission" UNIQUE ("organization_id", "permission");



ALTER TABLE ONLY "public"."project_permissions"
    ADD CONSTRAINT "unique_project_permission" UNIQUE ("project_id", "permission");



ALTER TABLE ONLY "public"."organization_roles"
    ADD CONSTRAINT "unique_user_organization" UNIQUE ("user_id", "organization_id");



ALTER TABLE ONLY "public"."visits"
    ADD CONSTRAINT "visits_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."workflow_instances"
    ADD CONSTRAINT "workflow_instances_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."workflows"
    ADD CONSTRAINT "workflows_pkey" PRIMARY KEY ("id");



CREATE INDEX "dataset_id_index" ON "public"."data_attribute" USING "btree" ("dataset_id");



CREATE INDEX "hits_user_id_idx" ON "public"."hits" USING "btree" ("user_id");



CREATE OR REPLACE TRIGGER "add_admin_and_member_after_organization_creation" AFTER INSERT ON "public"."organizations" FOR EACH ROW EXECUTE FUNCTION "public"."add_user_as_admin_and_member_to_new_organization"();



CREATE OR REPLACE TRIGGER "after_project_insert" AFTER INSERT ON "public"."projects" FOR EACH ROW EXECUTE FUNCTION "public"."assign_owner_role"();



CREATE OR REPLACE TRIGGER "on_org_role_update" AFTER INSERT OR DELETE OR UPDATE ON "public"."organization_roles" FOR EACH ROW EXECUTE FUNCTION "public"."update_user_roles"();



ALTER TABLE ONLY "public"."activities"
    ADD CONSTRAINT "activities_organisation_id_fkey" FOREIGN KEY ("organisation_id") REFERENCES "public"."organization"("id");



ALTER TABLE ONLY "public"."activities"
    ADD CONSTRAINT "activities_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "public"."projects"("id");



ALTER TABLE ONLY "public"."activities"
    ADD CONSTRAINT "activities_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."profile"("user_id");



ALTER TABLE ONLY "public"."api_keys"
    ADD CONSTRAINT "api_keys_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "auth"."users"("id") ON UPDATE CASCADE ON DELETE SET NULL;



ALTER TABLE ONLY "public"."data_attribute"
    ADD CONSTRAINT "data_attribute_dataset_id_fkey" FOREIGN KEY ("dataset_id") REFERENCES "public"."dataset"("id") ON UPDATE RESTRICT ON DELETE CASCADE;



ALTER TABLE ONLY "public"."data_schema"
    ADD CONSTRAINT "data_schema_organization_id_fkey" FOREIGN KEY ("organization_id") REFERENCES "public"."organization"("id");



ALTER TABLE ONLY "public"."data_schema"
    ADD CONSTRAINT "data_schema_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "auth"."users"("id");



ALTER TABLE ONLY "public"."data_source"
    ADD CONSTRAINT "data_source_organization_id_fkey" FOREIGN KEY ("organization_id") REFERENCES "public"."organization"("id") ON UPDATE CASCADE ON DELETE CASCADE;



ALTER TABLE ONLY "public"."dataset"
    ADD CONSTRAINT "dataset_sample_region_fkey" FOREIGN KEY ("sample_region") REFERENCES "public"."region"("id") ON UPDATE CASCADE ON DELETE RESTRICT;



ALTER TABLE ONLY "public"."logs"
    ADD CONSTRAINT "logs_organisation_id_fkey" FOREIGN KEY ("organisation_id") REFERENCES "public"."organization"("id");



ALTER TABLE ONLY "public"."logs"
    ADD CONSTRAINT "logs_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "public"."projects"("id");



ALTER TABLE ONLY "public"."logs"
    ADD CONSTRAINT "logs_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."profile"("user_id");



ALTER TABLE ONLY "public"."organization_domains"
    ADD CONSTRAINT "organization_domains_organization_id_fkey" FOREIGN KEY ("organization_id") REFERENCES "public"."organizations"("id");



ALTER TABLE ONLY "public"."organization_invites"
    ADD CONSTRAINT "organization_invites_organization_id_fkey" FOREIGN KEY ("organization_id") REFERENCES "public"."organizations"("id");



ALTER TABLE ONLY "public"."organization_join_requests"
    ADD CONSTRAINT "organization_join_requests_organization_id_fkey" FOREIGN KEY ("organization_id") REFERENCES "public"."organizations"("id");



ALTER TABLE ONLY "public"."organization_permissions"
    ADD CONSTRAINT "organization_permissions_organization_id_fkey" FOREIGN KEY ("organization_id") REFERENCES "public"."organizations"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."organization_join_requests"
    ADD CONSTRAINT "organization_requests_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "auth"."users"("id");



ALTER TABLE ONLY "public"."organization_roles"
    ADD CONSTRAINT "organization_roles_organization_id_fkey" FOREIGN KEY ("organization_id") REFERENCES "public"."organizations"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."organization_roles"
    ADD CONSTRAINT "organization_roles_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."profile"("user_id") ON UPDATE CASCADE ON DELETE CASCADE;



ALTER TABLE ONLY "public"."organization_user_permissions"
    ADD CONSTRAINT "organization_user_permissions_organization_id_fkey" FOREIGN KEY ("organization_id") REFERENCES "public"."organizations"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."organization_user_permissions"
    ADD CONSTRAINT "organization_user_permissions_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "auth"."users"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."profile"
    ADD CONSTRAINT "profile_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "auth"."users"("id") ON UPDATE CASCADE ON DELETE CASCADE;



ALTER TABLE ONLY "public"."project"
    ADD CONSTRAINT "project_organization_id_fkey" FOREIGN KEY ("organization_id") REFERENCES "public"."organization"("id");



ALTER TABLE ONLY "public"."project_permissions"
    ADD CONSTRAINT "project_permissions_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "public"."projects"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."project_roles"
    ADD CONSTRAINT "project_roles_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "public"."projects"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."project_roles"
    ADD CONSTRAINT "project_roles_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "auth"."users"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."project_templates"
    ADD CONSTRAINT "project_templates_organization_id_fkey" FOREIGN KEY ("organization_id") REFERENCES "public"."organizations"("id") ON UPDATE CASCADE ON DELETE CASCADE;



ALTER TABLE ONLY "public"."project_templates"
    ADD CONSTRAINT "project_templates_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."profile"("user_id") ON UPDATE CASCADE ON DELETE CASCADE;



ALTER TABLE ONLY "public"."project_templates"
    ADD CONSTRAINT "project_templates_user_id_fkey1" FOREIGN KEY ("user_id") REFERENCES "auth"."users"("id") ON UPDATE CASCADE ON DELETE CASCADE;



ALTER TABLE ONLY "public"."project"
    ADD CONSTRAINT "project_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."profile"("user_id") ON UPDATE CASCADE ON DELETE CASCADE;



ALTER TABLE ONLY "public"."project_user_permissions"
    ADD CONSTRAINT "project_user_permissions_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "public"."projects"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."project_user_permissions"
    ADD CONSTRAINT "project_user_permissions_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "auth"."users"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."projects"
    ADD CONSTRAINT "projects_organization_id_fkey" FOREIGN KEY ("organization_id") REFERENCES "public"."organizations"("id") ON UPDATE CASCADE ON DELETE CASCADE;



ALTER TABLE ONLY "public"."projects"
    ADD CONSTRAINT "projects_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "auth"."users"("id") ON UPDATE CASCADE ON DELETE CASCADE;



ALTER TABLE ONLY "public"."projects"
    ADD CONSTRAINT "projects_user_id_fkey1" FOREIGN KEY ("user_id") REFERENCES "public"."profile"("user_id") ON UPDATE CASCADE ON DELETE CASCADE;



CREATE POLICY "Allow everything to authenticated for now" ON "public"."projects" TO "authenticated" USING (true) WITH CHECK (true);



CREATE POLICY "Allow insert for users" ON "public"."organizations" FOR INSERT TO "authenticated" WITH CHECK (true);



CREATE POLICY "Allow select for auth admin" ON "public"."organization_roles" FOR SELECT TO "supabase_auth_admin" USING (true);



CREATE POLICY "Allow select for auth admin" ON "public"."organizations" FOR SELECT TO "supabase_auth_admin" USING (true);



CREATE POLICY "Allow select for organization members" ON "public"."organizations" FOR SELECT TO "authenticated" USING ((EXISTS ( SELECT 1
   FROM "public"."organization_roles"
  WHERE (("organization_roles"."organization_id" = "organizations"."id") AND ("organization_roles"."user_id" = "auth"."uid"())))));



CREATE POLICY "Allow select to organization members" ON "public"."organization_roles" FOR SELECT TO "authenticated" USING ((EXISTS ( SELECT 1
   FROM "public"."my_organizations" "uo"
  WHERE ("uo"."organization_id" = "organization_roles"."organization_id"))));



CREATE POLICY "Allow update to organization admins" ON "public"."organizations" FOR UPDATE USING ((EXISTS ( SELECT 1
   FROM "public"."organization_roles"
  WHERE (("organization_roles"."organization_id" = "organizations"."id") AND ("organization_roles"."user_id" = "auth"."uid"()) AND ("organization_roles"."role" = ANY (ARRAY['admin'::"text", 'superadmin'::"text"]))))));



CREATE POLICY "Enable delete for users based on user_id" ON "public"."organization_join_requests" FOR DELETE USING (true);



CREATE POLICY "Enable delete for users based on user_id" ON "public"."organization_roles" FOR DELETE USING ((( SELECT "auth"."uid"() AS "uid") = "user_id"));



CREATE POLICY "Enable insert for auth admin" ON "public"."organizations" FOR INSERT TO "supabase_auth_admin" WITH CHECK (true);



CREATE POLICY "Enable insert for authenticated users only" ON "public"."activities" FOR INSERT TO "authenticated" WITH CHECK (true);



CREATE POLICY "Enable insert for authenticated users only" ON "public"."hits" TO "authenticated" WITH CHECK (true);



CREATE POLICY "Enable insert for authenticated users only" ON "public"."organization_invites" FOR INSERT TO "authenticated" WITH CHECK (true);



CREATE POLICY "Enable insert for authenticated users only" ON "public"."organization_join_requests" FOR INSERT TO "authenticated" WITH CHECK (true);



CREATE POLICY "Enable read access for all users" ON "public"."hits" FOR SELECT TO "authenticated" USING (("auth"."uid"() = "user_id"));



CREATE POLICY "Enable read access for all users" ON "public"."organization_invites" FOR SELECT USING (true);



CREATE POLICY "Enable read access for all users" ON "public"."organization_join_requests" FOR SELECT USING (true);



CREATE POLICY "Enable read access for all users" ON "public"."organizations" FOR SELECT USING (true);



CREATE POLICY "Org Admin can delete Roles" ON "public"."organization_roles" FOR DELETE USING ((EXISTS ( SELECT 1
   FROM "public"."my_organization_roles" "org_roles"
  WHERE (("org_roles"."organization_id" = "organization_roles"."organization_id") AND ("org_roles"."user_id" = "auth"."uid"()) AND ("org_roles"."role" = 'admin'::"text")))));



CREATE POLICY "Org admin can update project" ON "public"."organization_roles" FOR UPDATE USING ((EXISTS ( SELECT 1
   FROM "public"."my_organization_roles" "org_roles"
  WHERE (("org_roles"."organization_id" = "organization_roles"."organization_id") AND ("org_roles"."user_id" = "auth"."uid"()) AND ("org_roles"."role" = 'admin'::"text")))));



CREATE POLICY "Supabase auth admin can insert roles" ON "public"."organization_roles" FOR INSERT WITH CHECK (true);



CREATE POLICY "Supabase auth admin can update roles" ON "public"."organization_roles" FOR UPDATE TO "supabase_auth_admin" USING (true);



ALTER TABLE "public"."activities" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."api_keys" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "authenticated" ON "public"."profile" TO "authenticated" USING (("auth"."uid"() = "user_id")) WITH CHECK (("auth"."uid"() = "user_id"));



ALTER TABLE "public"."credits" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "delete selected api_key" ON "public"."api_keys" FOR DELETE TO "authenticated" USING (("auth"."uid"() = "user_id"));



ALTER TABLE "public"."gcp_usage_reports" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."hits" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "insert_auth_admin" ON "public"."credits" FOR INSERT WITH CHECK ((CURRENT_USER = 'supabase_auth_admin'::"name"));



CREATE POLICY "insert_for_admin" ON "public"."profile" FOR INSERT TO "supabase_auth_admin" WITH CHECK (true);



ALTER TABLE "public"."organization_join_requests" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."organization_roles" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."organizations" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."projects" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "select_user_api_key" ON "public"."api_keys" FOR SELECT TO "authenticated" USING (("auth"."uid"() = "user_id"));



CREATE POLICY "select_user_credits" ON "public"."credits" FOR SELECT TO "authenticated" USING (("auth"."uid"() = "user_id"));



CREATE POLICY "view_own_organization_profiles" ON "public"."profile" FOR SELECT USING ((EXISTS ( SELECT 1
   FROM ("public"."organization_members" "om"
     JOIN "public"."my_organizations" "mo" ON (("om"."organization_id" = "mo"."organization_id")))
  WHERE ("om"."user_id" = "profile"."user_id"))));


ALTER PUBLICATION "supabase_realtime" OWNER TO "postgres";




RESET ALL;
