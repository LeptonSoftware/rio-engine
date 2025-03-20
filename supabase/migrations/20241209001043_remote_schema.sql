CREATE TRIGGER add_profile_trigger AFTER INSERT ON auth.users FOR EACH ROW EXECUTE FUNCTION add_profile();

CREATE TRIGGER add_user_to_organization_trigger AFTER INSERT ON auth.users FOR EACH ROW EXECUTE FUNCTION add_user_to_organization_based_on_domain();

CREATE TRIGGER is_active_trigger_function AFTER INSERT ON auth.users FOR EACH ROW EXECUTE FUNCTION is_active_trigger_function();

CREATE TRIGGER source_insert_trigger_function AFTER INSERT ON auth.users FOR EACH ROW EXECUTE FUNCTION source_insert_trigger_function();


set check_function_bodies = off;

CREATE OR REPLACE FUNCTION storage.extension(name text)
 RETURNS text
 LANGUAGE plpgsql
AS $function$
DECLARE
_parts text[];
_filename text;
BEGIN
    select string_to_array(name, '/') into _parts;
    select _parts[array_length(_parts,1)] into _filename;
    -- @todo return the last part instead of 2
    return split_part(_filename, '.', 2);
END
$function$
;

CREATE OR REPLACE FUNCTION storage.filename(name text)
 RETURNS text
 LANGUAGE plpgsql
AS $function$
DECLARE
_parts text[];
BEGIN
    select string_to_array(name, '/') into _parts;
    return _parts[array_length(_parts,1)];
END
$function$
;

CREATE OR REPLACE FUNCTION storage.foldername(name text)
 RETURNS text[]
 LANGUAGE plpgsql
AS $function$
DECLARE
_parts text[];
BEGIN
    select string_to_array(name, '/') into _parts;
    return _parts[1:array_length(_parts,1)-1];
END
$function$
;

create policy "Allow fetching files from visits bucket"
on "storage"."objects"
as permissive
for select
to anon, authenticated
using ((bucket_id = 'visits'::text));


create policy "Allow to Select, Update and Insert c0gsqt_0"
on "storage"."objects"
as permissive
for select
to authenticated
using ((bucket_id = 'project-templates'::text));


create policy "Allow to Select, Update and Insert c0gsqt_1"
on "storage"."objects"
as permissive
for insert
to authenticated
with check ((bucket_id = 'project-templates'::text));


create policy "Allow to Select, Update and Insert c0gsqt_2"
on "storage"."objects"
as permissive
for update
to authenticated
using ((bucket_id = 'project-templates'::text));


create policy "Give anon users access to JPG images in folder 1peuqw_0"
on "storage"."objects"
as permissive
for select
to public
using (((bucket_id = 'logos'::text) AND (auth.role() = 'anon'::text)));


create policy "Give users authenticated access to folder 1iiiika_0"
on "storage"."objects"
as permissive
for select
to public
using (((bucket_id = 'projects'::text) AND (auth.role() = 'authenticated'::text)));


create policy "allow_user_insert_smartmarket"
on "storage"."objects"
as permissive
for insert
to public
with check (true);


create policy "projects_all_user_access_temp 1iiiika_0"
on "storage"."objects"
as permissive
for insert
to authenticated
with check ((bucket_id = 'projects'::text));


create policy "projects_all_user_access_temp 1iiiika_1"
on "storage"."objects"
as permissive
for update
to authenticated
using ((bucket_id = 'projects'::text));


create policy "projects_all_user_access_temp 1iiiika_2"
on "storage"."objects"
as permissive
for select
to authenticated
using ((bucket_id = 'projects'::text));



