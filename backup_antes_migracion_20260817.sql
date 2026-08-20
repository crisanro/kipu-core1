--
-- PostgreSQL database dump
--

\restrict Wavtl3b3y5hu0z4tmzxMjrG7gEjzCaqIVeKy7EjIgfbZADYDq4dYDNodx3pOZif

-- Dumped from database version 17.6
-- Dumped by pg_dump version 17.11 (Ubuntu 17.11-1.pgdg24.04+2)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: auth; Type: SCHEMA; Schema: -; Owner: supabase_admin
--

CREATE SCHEMA auth;


ALTER SCHEMA auth OWNER TO supabase_admin;

--
-- Name: extensions; Type: SCHEMA; Schema: -; Owner: postgres
--

CREATE SCHEMA extensions;


ALTER SCHEMA extensions OWNER TO postgres;

--
-- Name: graphql; Type: SCHEMA; Schema: -; Owner: supabase_admin
--

CREATE SCHEMA graphql;


ALTER SCHEMA graphql OWNER TO supabase_admin;

--
-- Name: graphql_public; Type: SCHEMA; Schema: -; Owner: supabase_admin
--

CREATE SCHEMA graphql_public;


ALTER SCHEMA graphql_public OWNER TO supabase_admin;

--
-- Name: pgbouncer; Type: SCHEMA; Schema: -; Owner: pgbouncer
--

CREATE SCHEMA pgbouncer;


ALTER SCHEMA pgbouncer OWNER TO pgbouncer;

--
-- Name: realtime; Type: SCHEMA; Schema: -; Owner: supabase_admin
--

CREATE SCHEMA realtime;


ALTER SCHEMA realtime OWNER TO supabase_admin;

--
-- Name: storage; Type: SCHEMA; Schema: -; Owner: supabase_admin
--

CREATE SCHEMA storage;


ALTER SCHEMA storage OWNER TO supabase_admin;

--
-- Name: vault; Type: SCHEMA; Schema: -; Owner: supabase_admin
--

CREATE SCHEMA vault;


ALTER SCHEMA vault OWNER TO supabase_admin;

--
-- Name: pg_stat_statements; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pg_stat_statements WITH SCHEMA extensions;


--
-- Name: EXTENSION pg_stat_statements; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION pg_stat_statements IS 'track planning and execution statistics of all SQL statements executed';


--
-- Name: pg_trgm; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public;


--
-- Name: EXTENSION pg_trgm; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION pg_trgm IS 'text similarity measurement and index searching based on trigrams';


--
-- Name: pgcrypto; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA extensions;


--
-- Name: EXTENSION pgcrypto; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION pgcrypto IS 'cryptographic functions';


--
-- Name: supabase_vault; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS supabase_vault WITH SCHEMA vault;


--
-- Name: EXTENSION supabase_vault; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION supabase_vault IS 'Supabase Vault Extension';


--
-- Name: uuid-ossp; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA extensions;


--
-- Name: EXTENSION "uuid-ossp"; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION "uuid-ossp" IS 'generate universally unique identifiers (UUIDs)';


--
-- Name: aal_level; Type: TYPE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TYPE auth.aal_level AS ENUM (
    'aal1',
    'aal2',
    'aal3'
);


ALTER TYPE auth.aal_level OWNER TO supabase_auth_admin;

--
-- Name: code_challenge_method; Type: TYPE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TYPE auth.code_challenge_method AS ENUM (
    's256',
    'plain'
);


ALTER TYPE auth.code_challenge_method OWNER TO supabase_auth_admin;

--
-- Name: factor_status; Type: TYPE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TYPE auth.factor_status AS ENUM (
    'unverified',
    'verified'
);


ALTER TYPE auth.factor_status OWNER TO supabase_auth_admin;

--
-- Name: factor_type; Type: TYPE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TYPE auth.factor_type AS ENUM (
    'totp',
    'webauthn',
    'phone'
);


ALTER TYPE auth.factor_type OWNER TO supabase_auth_admin;

--
-- Name: oauth_authorization_status; Type: TYPE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TYPE auth.oauth_authorization_status AS ENUM (
    'pending',
    'approved',
    'denied',
    'expired'
);


ALTER TYPE auth.oauth_authorization_status OWNER TO supabase_auth_admin;

--
-- Name: oauth_client_type; Type: TYPE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TYPE auth.oauth_client_type AS ENUM (
    'public',
    'confidential'
);


ALTER TYPE auth.oauth_client_type OWNER TO supabase_auth_admin;

--
-- Name: oauth_registration_type; Type: TYPE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TYPE auth.oauth_registration_type AS ENUM (
    'dynamic',
    'manual'
);


ALTER TYPE auth.oauth_registration_type OWNER TO supabase_auth_admin;

--
-- Name: oauth_response_type; Type: TYPE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TYPE auth.oauth_response_type AS ENUM (
    'code'
);


ALTER TYPE auth.oauth_response_type OWNER TO supabase_auth_admin;

--
-- Name: one_time_token_type; Type: TYPE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TYPE auth.one_time_token_type AS ENUM (
    'confirmation_token',
    'reauthentication_token',
    'recovery_token',
    'email_change_token_new',
    'email_change_token_current',
    'phone_change_token'
);


ALTER TYPE auth.one_time_token_type OWNER TO supabase_auth_admin;

--
-- Name: action; Type: TYPE; Schema: realtime; Owner: supabase_realtime_admin
--

CREATE TYPE realtime.action AS ENUM (
    'INSERT',
    'UPDATE',
    'DELETE',
    'TRUNCATE',
    'ERROR'
);


ALTER TYPE realtime.action OWNER TO supabase_realtime_admin;

--
-- Name: equality_op; Type: TYPE; Schema: realtime; Owner: supabase_realtime_admin
--

CREATE TYPE realtime.equality_op AS ENUM (
    'eq',
    'neq',
    'lt',
    'lte',
    'gt',
    'gte',
    'in',
    'like',
    'ilike',
    'is',
    'match',
    'imatch',
    'isdistinct'
);


ALTER TYPE realtime.equality_op OWNER TO supabase_realtime_admin;

--
-- Name: user_defined_filter; Type: TYPE; Schema: realtime; Owner: supabase_realtime_admin
--

CREATE TYPE realtime.user_defined_filter AS (
	column_name text,
	op realtime.equality_op,
	value text,
	negate boolean
);


ALTER TYPE realtime.user_defined_filter OWNER TO supabase_realtime_admin;

--
-- Name: wal_column; Type: TYPE; Schema: realtime; Owner: supabase_realtime_admin
--

CREATE TYPE realtime.wal_column AS (
	name text,
	type_name text,
	type_oid oid,
	value jsonb,
	is_pkey boolean,
	is_selectable boolean
);


ALTER TYPE realtime.wal_column OWNER TO supabase_realtime_admin;

--
-- Name: wal_rls; Type: TYPE; Schema: realtime; Owner: supabase_realtime_admin
--

CREATE TYPE realtime.wal_rls AS (
	wal jsonb,
	is_rls_enabled boolean,
	subscription_ids uuid[],
	errors text[]
);


ALTER TYPE realtime.wal_rls OWNER TO supabase_realtime_admin;

--
-- Name: buckettype; Type: TYPE; Schema: storage; Owner: supabase_storage_admin
--

CREATE TYPE storage.buckettype AS ENUM (
    'STANDARD',
    'ANALYTICS',
    'VECTOR'
);


ALTER TYPE storage.buckettype OWNER TO supabase_storage_admin;

--
-- Name: email(); Type: FUNCTION; Schema: auth; Owner: supabase_auth_admin
--

CREATE FUNCTION auth.email() RETURNS text
    LANGUAGE sql STABLE
    AS $$
  select 
  coalesce(
    nullif(current_setting('request.jwt.claim.email', true), ''),
    (nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'email')
  )::text
$$;


ALTER FUNCTION auth.email() OWNER TO supabase_auth_admin;

--
-- Name: FUNCTION email(); Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON FUNCTION auth.email() IS 'Deprecated. Use auth.jwt() -> ''email'' instead.';


--
-- Name: jwt(); Type: FUNCTION; Schema: auth; Owner: supabase_auth_admin
--

CREATE FUNCTION auth.jwt() RETURNS jsonb
    LANGUAGE sql STABLE
    AS $$
  select 
    coalesce(
        nullif(current_setting('request.jwt.claim', true), ''),
        nullif(current_setting('request.jwt.claims', true), '')
    )::jsonb
$$;


ALTER FUNCTION auth.jwt() OWNER TO supabase_auth_admin;

--
-- Name: role(); Type: FUNCTION; Schema: auth; Owner: supabase_auth_admin
--

CREATE FUNCTION auth.role() RETURNS text
    LANGUAGE sql STABLE
    AS $$
  select 
  coalesce(
    nullif(current_setting('request.jwt.claim.role', true), ''),
    (nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'role')
  )::text
$$;


ALTER FUNCTION auth.role() OWNER TO supabase_auth_admin;

--
-- Name: FUNCTION role(); Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON FUNCTION auth.role() IS 'Deprecated. Use auth.jwt() -> ''role'' instead.';


--
-- Name: uid(); Type: FUNCTION; Schema: auth; Owner: supabase_auth_admin
--

CREATE FUNCTION auth.uid() RETURNS uuid
    LANGUAGE sql STABLE
    AS $$
  select 
  coalesce(
    nullif(current_setting('request.jwt.claim.sub', true), ''),
    (nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'sub')
  )::uuid
$$;


ALTER FUNCTION auth.uid() OWNER TO supabase_auth_admin;

--
-- Name: FUNCTION uid(); Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON FUNCTION auth.uid() IS 'Deprecated. Use auth.jwt() -> ''sub'' instead.';


--
-- Name: grant_pg_cron_access(); Type: FUNCTION; Schema: extensions; Owner: supabase_admin
--

CREATE FUNCTION extensions.grant_pg_cron_access() RETURNS event_trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  IF EXISTS (
    SELECT
    FROM pg_event_trigger_ddl_commands() AS ev
    JOIN pg_extension AS ext
    ON ev.objid = ext.oid
    WHERE ext.extname = 'pg_cron'
  )
  THEN
    grant usage on schema cron to postgres with grant option;

    alter default privileges in schema cron grant all on tables to postgres with grant option;
    alter default privileges in schema cron grant all on functions to postgres with grant option;
    alter default privileges in schema cron grant all on sequences to postgres with grant option;

    alter default privileges for user supabase_admin in schema cron grant all
        on sequences to postgres with grant option;
    alter default privileges for user supabase_admin in schema cron grant all
        on tables to postgres with grant option;
    alter default privileges for user supabase_admin in schema cron grant all
        on functions to postgres with grant option;

    grant all privileges on all tables in schema cron to postgres with grant option;
    revoke all on table cron.job from postgres;
    grant select on table cron.job to postgres with grant option;
  END IF;
END;
$$;


ALTER FUNCTION extensions.grant_pg_cron_access() OWNER TO supabase_admin;

--
-- Name: FUNCTION grant_pg_cron_access(); Type: COMMENT; Schema: extensions; Owner: supabase_admin
--

COMMENT ON FUNCTION extensions.grant_pg_cron_access() IS 'Grants access to pg_cron';


--
-- Name: grant_pg_graphql_access(); Type: FUNCTION; Schema: extensions; Owner: supabase_admin
--

CREATE FUNCTION extensions.grant_pg_graphql_access() RETURNS event_trigger
    LANGUAGE plpgsql
    AS $_$
begin
    if not exists (
        select 1
        from pg_event_trigger_ddl_commands() ev
        join pg_catalog.pg_extension e on ev.objid = e.oid
        where e.extname = 'pg_graphql'
    ) then
        return;
    end if;

    drop function if exists graphql_public.graphql;
    create or replace function graphql_public.graphql(
        "operationName" text default null,
        query text default null,
        variables jsonb default null,
        extensions jsonb default null
    )
        returns jsonb
        language sql
    as $$
        select graphql.resolve(
            query := query,
            variables := coalesce(variables, '{}'),
            "operationName" := "operationName",
            extensions := extensions
        );
    $$;

    -- Attach the wrapper to the extension so DROP EXTENSION cascades to it,
    -- which in turn triggers set_graphql_placeholder to reinstall the "not enabled" stub.
    alter extension pg_graphql add function graphql_public.graphql(text, text, jsonb, jsonb);

    grant usage on schema graphql to postgres, anon, authenticated, service_role;
    grant execute on function graphql.resolve to postgres, anon, authenticated, service_role;
    grant usage on schema graphql to postgres with grant option;
    grant usage on schema graphql_public to postgres with grant option;
end;
$_$;


ALTER FUNCTION extensions.grant_pg_graphql_access() OWNER TO supabase_admin;

--
-- Name: FUNCTION grant_pg_graphql_access(); Type: COMMENT; Schema: extensions; Owner: supabase_admin
--

COMMENT ON FUNCTION extensions.grant_pg_graphql_access() IS 'Grants access to pg_graphql';


--
-- Name: grant_pg_net_access(); Type: FUNCTION; Schema: extensions; Owner: supabase_admin
--

CREATE FUNCTION extensions.grant_pg_net_access() RETURNS event_trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM pg_event_trigger_ddl_commands() AS ev
    JOIN pg_extension AS ext
    ON ev.objid = ext.oid
    WHERE ext.extname = 'pg_net'
  )
  THEN
    IF NOT EXISTS (
      SELECT 1
      FROM pg_roles
      WHERE rolname = 'supabase_functions_admin'
    )
    THEN
      CREATE USER supabase_functions_admin NOINHERIT CREATEROLE LOGIN NOREPLICATION;
    END IF;

    GRANT USAGE ON SCHEMA net TO supabase_functions_admin, postgres, anon, authenticated, service_role;

    IF EXISTS (
      SELECT FROM pg_extension
      WHERE extname = 'pg_net'
      -- all versions in use on existing projects as of 2025-02-20
      -- version 0.12.0 onwards don't need these applied
      AND extversion IN ('0.2', '0.6', '0.7', '0.7.1', '0.8', '0.10.0', '0.11.0')
    ) THEN
      ALTER function net.http_get(url text, params jsonb, headers jsonb, timeout_milliseconds integer) SECURITY DEFINER;
      ALTER function net.http_post(url text, body jsonb, params jsonb, headers jsonb, timeout_milliseconds integer) SECURITY DEFINER;

      ALTER function net.http_get(url text, params jsonb, headers jsonb, timeout_milliseconds integer) SET search_path = net;
      ALTER function net.http_post(url text, body jsonb, params jsonb, headers jsonb, timeout_milliseconds integer) SET search_path = net;

      REVOKE ALL ON FUNCTION net.http_get(url text, params jsonb, headers jsonb, timeout_milliseconds integer) FROM PUBLIC;
      REVOKE ALL ON FUNCTION net.http_post(url text, body jsonb, params jsonb, headers jsonb, timeout_milliseconds integer) FROM PUBLIC;

      GRANT EXECUTE ON FUNCTION net.http_get(url text, params jsonb, headers jsonb, timeout_milliseconds integer) TO supabase_functions_admin, postgres, anon, authenticated, service_role;
      GRANT EXECUTE ON FUNCTION net.http_post(url text, body jsonb, params jsonb, headers jsonb, timeout_milliseconds integer) TO supabase_functions_admin, postgres, anon, authenticated, service_role;
    END IF;
  END IF;
END;
$$;


ALTER FUNCTION extensions.grant_pg_net_access() OWNER TO supabase_admin;

--
-- Name: FUNCTION grant_pg_net_access(); Type: COMMENT; Schema: extensions; Owner: supabase_admin
--

COMMENT ON FUNCTION extensions.grant_pg_net_access() IS 'Grants access to pg_net';


--
-- Name: pgrst_ddl_watch(); Type: FUNCTION; Schema: extensions; Owner: supabase_admin
--

CREATE FUNCTION extensions.pgrst_ddl_watch() RETURNS event_trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  cmd record;
BEGIN
  FOR cmd IN SELECT * FROM pg_event_trigger_ddl_commands()
  LOOP
    IF cmd.command_tag IN (
      'CREATE SCHEMA', 'ALTER SCHEMA'
    , 'CREATE TABLE', 'CREATE TABLE AS', 'SELECT INTO', 'ALTER TABLE'
    , 'CREATE FOREIGN TABLE', 'ALTER FOREIGN TABLE'
    , 'CREATE VIEW', 'ALTER VIEW'
    , 'CREATE MATERIALIZED VIEW', 'ALTER MATERIALIZED VIEW'
    , 'CREATE FUNCTION', 'ALTER FUNCTION'
    , 'CREATE TRIGGER'
    , 'CREATE TYPE', 'ALTER TYPE'
    , 'CREATE RULE'
    , 'COMMENT'
    )
    -- don't notify in case of CREATE TEMP table or other objects created on pg_temp
    AND cmd.schema_name is distinct from 'pg_temp'
    THEN
      NOTIFY pgrst, 'reload schema';
    END IF;
  END LOOP;
END; $$;


ALTER FUNCTION extensions.pgrst_ddl_watch() OWNER TO supabase_admin;

--
-- Name: pgrst_drop_watch(); Type: FUNCTION; Schema: extensions; Owner: supabase_admin
--

CREATE FUNCTION extensions.pgrst_drop_watch() RETURNS event_trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  obj record;
BEGIN
  FOR obj IN SELECT * FROM pg_event_trigger_dropped_objects()
  LOOP
    IF obj.object_type IN (
      'schema'
    , 'table'
    , 'foreign table'
    , 'view'
    , 'materialized view'
    , 'function'
    , 'trigger'
    , 'type'
    , 'rule'
    )
    AND obj.is_temporary IS false -- no pg_temp objects
    THEN
      NOTIFY pgrst, 'reload schema';
    END IF;
  END LOOP;
END; $$;


ALTER FUNCTION extensions.pgrst_drop_watch() OWNER TO supabase_admin;

--
-- Name: set_graphql_placeholder(); Type: FUNCTION; Schema: extensions; Owner: supabase_admin
--

CREATE FUNCTION extensions.set_graphql_placeholder() RETURNS event_trigger
    LANGUAGE plpgsql
    AS $_$
    DECLARE
    graphql_is_dropped bool;
    BEGIN
    graphql_is_dropped = (
        SELECT ev.schema_name = 'graphql_public'
        FROM pg_event_trigger_dropped_objects() AS ev
        WHERE ev.schema_name = 'graphql_public'
    );

    IF graphql_is_dropped
    THEN
        create or replace function graphql_public.graphql(
            "operationName" text default null,
            query text default null,
            variables jsonb default null,
            extensions jsonb default null
        )
            returns jsonb
            language plpgsql
        as $$
            DECLARE
                server_version float;
            BEGIN
                server_version = (SELECT (SPLIT_PART((select version()), ' ', 2))::float);

                IF server_version >= 14 THEN
                    RETURN jsonb_build_object(
                        'errors', jsonb_build_array(
                            jsonb_build_object(
                                'message', 'pg_graphql extension is not enabled.'
                            )
                        )
                    );
                ELSE
                    RETURN jsonb_build_object(
                        'errors', jsonb_build_array(
                            jsonb_build_object(
                                'message', 'pg_graphql is only available on projects running Postgres 14 onwards.'
                            )
                        )
                    );
                END IF;
            END;
        $$;
    END IF;

    END;
$_$;


ALTER FUNCTION extensions.set_graphql_placeholder() OWNER TO supabase_admin;

--
-- Name: FUNCTION set_graphql_placeholder(); Type: COMMENT; Schema: extensions; Owner: supabase_admin
--

COMMENT ON FUNCTION extensions.set_graphql_placeholder() IS 'Reintroduces placeholder function for graphql_public.graphql';


--
-- Name: graphql(text, text, jsonb, jsonb); Type: FUNCTION; Schema: graphql_public; Owner: supabase_admin
--

CREATE FUNCTION graphql_public.graphql("operationName" text DEFAULT NULL::text, query text DEFAULT NULL::text, variables jsonb DEFAULT NULL::jsonb, extensions jsonb DEFAULT NULL::jsonb) RETURNS jsonb
    LANGUAGE plpgsql
    AS $$
            DECLARE
                server_version float;
            BEGIN
                server_version = (SELECT (SPLIT_PART((select version()), ' ', 2))::float);

                IF server_version >= 14 THEN
                    RETURN jsonb_build_object(
                        'errors', jsonb_build_array(
                            jsonb_build_object(
                                'message', 'pg_graphql extension is not enabled.'
                            )
                        )
                    );
                ELSE
                    RETURN jsonb_build_object(
                        'errors', jsonb_build_array(
                            jsonb_build_object(
                                'message', 'pg_graphql is only available on projects running Postgres 14 onwards.'
                            )
                        )
                    );
                END IF;
            END;
        $$;


ALTER FUNCTION graphql_public.graphql("operationName" text, query text, variables jsonb, extensions jsonb) OWNER TO supabase_admin;

--
-- Name: get_auth(text); Type: FUNCTION; Schema: pgbouncer; Owner: supabase_admin
--

CREATE FUNCTION pgbouncer.get_auth(p_usename text) RETURNS TABLE(username text, password text)
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO ''
    AS $_$
  BEGIN
      RAISE DEBUG 'PgBouncer auth request: %', p_usename;

      RETURN QUERY
      SELECT
          rolname::text,
          CASE WHEN rolvaliduntil < now()
              THEN null
              ELSE rolpassword::text
          END
      FROM pg_authid
      WHERE rolname=$1 and rolcanlogin;
  END;
  $_$;


ALTER FUNCTION pgbouncer.get_auth(p_usename text) OWNER TO supabase_admin;

--
-- Name: apply_rls(jsonb, integer); Type: FUNCTION; Schema: realtime; Owner: supabase_realtime_admin
--

CREATE FUNCTION realtime.apply_rls(wal jsonb, max_record_bytes integer DEFAULT (1024 * 1024)) RETURNS SETOF realtime.wal_rls
    LANGUAGE plpgsql
    AS $$
declare
    -- Regclass of the table e.g. public.notes
    entity_ regclass = (quote_ident(wal ->> 'schema') || '.' || quote_ident(wal ->> 'table'))::regclass;

    -- I, U, D, T: insert, update ...
    action realtime.action = (
        case wal ->> 'action'
            when 'I' then 'INSERT'
            when 'U' then 'UPDATE'
            when 'D' then 'DELETE'
            else 'ERROR'
        end
    );

    -- Is row level security enabled for the table
    is_rls_enabled bool = relrowsecurity from pg_class where oid = entity_;

    subscriptions realtime.subscription[] = array_agg(subs)
        from
            realtime.subscription subs
        where
            subs.entity = entity_
            -- Filter by action early - only get subscriptions interested in this action
            -- action_filter column can be: '*' (all), 'INSERT', 'UPDATE', or 'DELETE'
            and (subs.action_filter = '*' or subs.action_filter = action::text);

    -- Subscription vars
    working_role regrole;
    working_selected_columns text[];
    claimed_role regrole;
    claims jsonb;

    subscription_id uuid;
    subscription_has_access bool;
    visible_to_subscription_ids uuid[] = '{}';

    -- structured info for wal's columns
    columns realtime.wal_column[];
    -- previous identity values for update/delete
    old_columns realtime.wal_column[];

    error_record_exceeds_max_size boolean = octet_length(wal::text) > max_record_bytes;

    -- Primary jsonb output for record
    output jsonb;

    -- Loop record for iterating unique roles (outer loop)
    role_record record;
    -- Loop record for iterating unique selected_columns within a role (inner loop)
    cols_record record;
    -- Subscription ids visible at the role level (before fanning out by selected_columns)
    visible_role_sub_ids uuid[] = '{}';

begin
    perform set_config('role', null, true);

    columns =
        array_agg(
            (
                x->>'name',
                x->>'type',
                x->>'typeoid',
                realtime.cast(
                    (x->'value') #>> '{}',
                    coalesce(
                        (x->>'typeoid')::regtype, -- null when wal2json version <= 2.4
                        (x->>'type')::regtype
                    )
                ),
                (pks ->> 'name') is not null,
                true
            )::realtime.wal_column
        )
        from
            jsonb_array_elements(wal -> 'columns') x
            left join jsonb_array_elements(wal -> 'pk') pks
                on (x ->> 'name') = (pks ->> 'name');

    old_columns =
        array_agg(
            (
                x->>'name',
                x->>'type',
                x->>'typeoid',
                realtime.cast(
                    (x->'value') #>> '{}',
                    coalesce(
                        (x->>'typeoid')::regtype, -- null when wal2json version <= 2.4
                        (x->>'type')::regtype
                    )
                ),
                (pks ->> 'name') is not null,
                true
            )::realtime.wal_column
        )
        from
            jsonb_array_elements(wal -> 'identity') x
            left join jsonb_array_elements(wal -> 'pk') pks
                on (x ->> 'name') = (pks ->> 'name');

    for role_record in
        select claims_role
        from (select distinct claims_role from unnest(subscriptions)) t
        order by claims_role::text
    loop
        working_role := role_record.claims_role;

        -- Update `is_selectable` for columns and old_columns (once per role)
        columns =
            array_agg(
                (
                    c.name,
                    c.type_name,
                    c.type_oid,
                    c.value,
                    c.is_pkey,
                    pg_catalog.has_column_privilege(working_role, entity_, c.name, 'SELECT')
                )::realtime.wal_column
            )
            from
                unnest(columns) c;

        old_columns =
                array_agg(
                    (
                        c.name,
                        c.type_name,
                        c.type_oid,
                        c.value,
                        c.is_pkey,
                        pg_catalog.has_column_privilege(working_role, entity_, c.name, 'SELECT')
                    )::realtime.wal_column
                )
                from
                    unnest(old_columns) c;

        if action <> 'DELETE' and count(1) = 0 from unnest(columns) c where c.is_pkey then
            -- Fan out 400 error per distinct selected_columns for this role
            for cols_record in
                select selected_columns
                from (select distinct selected_columns from unnest(subscriptions) s where s.claims_role = working_role) t
                order by coalesce(array_to_string(selected_columns, ','), '')
            loop
                working_selected_columns := cols_record.selected_columns;
                return next (
                    jsonb_build_object(
                        'schema', wal ->> 'schema',
                        'table', wal ->> 'table',
                        'type', action
                    ),
                    is_rls_enabled,
                    (select array_agg(s.subscription_id) from unnest(subscriptions) as s where s.claims_role = working_role and (s.selected_columns is not distinct from working_selected_columns)),
                    array['Error 400: Bad Request, no primary key']
                )::realtime.wal_rls;
            end loop;

        -- The claims role does not have SELECT permission to the primary key of entity
        elsif action <> 'DELETE' and sum(c.is_selectable::int) <> count(1) from unnest(columns) c where c.is_pkey then
            -- Fan out 401 error per distinct selected_columns for this role
            for cols_record in
                select selected_columns
                from (select distinct selected_columns from unnest(subscriptions) s where s.claims_role = working_role) t
                order by coalesce(array_to_string(selected_columns, ','), '')
            loop
                working_selected_columns := cols_record.selected_columns;
                return next (
                    jsonb_build_object(
                        'schema', wal ->> 'schema',
                        'table', wal ->> 'table',
                        'type', action
                    ),
                    is_rls_enabled,
                    (select array_agg(s.subscription_id) from unnest(subscriptions) as s where s.claims_role = working_role and (s.selected_columns is not distinct from working_selected_columns)),
                    array['Error 401: Unauthorized']
                )::realtime.wal_rls;
            end loop;

        else
            -- Create the prepared statement (once per role)
            if is_rls_enabled and action <> 'DELETE' then
                if (select 1 from pg_prepared_statements where name = 'walrus_rls_stmt' limit 1) > 0 then
                    deallocate walrus_rls_stmt;
                end if;
                execute realtime.build_prepared_statement_sql('walrus_rls_stmt', entity_, columns);
            end if;

            -- Collect all visible subscription IDs for this role (filter check + RLS check)
            visible_role_sub_ids = '{}';

            for subscription_id, claims in (
                    select
                        subs.subscription_id,
                        subs.claims
                    from
                        unnest(subscriptions) subs
                    where
                        subs.entity = entity_
                        and subs.claims_role = working_role
                        and (
                            realtime.is_visible_through_filters(columns, subs.filters)
                            or (
                              action = 'DELETE'
                              and realtime.is_visible_through_filters(old_columns, subs.filters)
                            )
                        )
            ) loop

                if not is_rls_enabled or action = 'DELETE' then
                    visible_role_sub_ids = visible_role_sub_ids || subscription_id;
                else
                    -- Check if RLS allows the role to see the record
                    perform
                        -- Trim leading and trailing quotes from working_role because set_config
                        -- doesn't recognize the role as valid if they are included
                        set_config('role', trim(both '"' from working_role::text), true),
                        set_config('request.jwt.claims', claims::text, true);

                    execute 'execute walrus_rls_stmt' into subscription_has_access;

                    -- Reset the role on every FOR..LOOP batch execution.
                    -- The first batch of 10 rows is pre-fetched using the current connection role (PG internal behaviour)
                    -- then we have to reset it again otherwise it would use the role defined in the `set_config` above
                    -- to fetch the remaining rows when rows>10, which could be a user-defined role that lacks execution grants.
                    -- The flow is:
                    --   1. run batch with conn role
                    --   2. set_config working_role
                    --   3. execute walrus
                    --   4. reset role (revert)
                    --   5. repeat
                    perform set_config('role', null, true);

                    if subscription_has_access then
                        visible_role_sub_ids = visible_role_sub_ids || subscription_id;
                    end if;
                end if;
            end loop;

            perform set_config('role', null, true);

            -- Inner loop: per distinct selected_columns for this role
            for cols_record in
                select selected_columns
                from (select distinct selected_columns from unnest(subscriptions) s where s.claims_role = working_role) t
                order by coalesce(array_to_string(selected_columns, ','), '')
            loop
                working_selected_columns := cols_record.selected_columns;

                output = jsonb_build_object(
                    'schema', wal ->> 'schema',
                    'table', wal ->> 'table',
                    'type', action,
                    'commit_timestamp', to_char(
                        ((wal ->> 'timestamp')::timestamptz at time zone 'utc'),
                        'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'
                    ),
                    'columns', (
                        select
                            jsonb_agg(
                                jsonb_build_object(
                                    'name', pa.attname,
                                    'type', pt.typname
                                )
                                order by pa.attnum asc
                            )
                        from
                            pg_attribute pa
                            join pg_type pt
                                on pa.atttypid = pt.oid
                            left join (
                                select unnest(conkey) as pkey_attnum
                                from pg_constraint
                                where conrelid = entity_ and contype = 'p'
                            ) pk on pk.pkey_attnum = pa.attnum
                        where
                            attrelid = entity_
                            and attnum > 0
                            and pg_catalog.has_column_privilege(working_role, entity_, pa.attname, 'SELECT')
                            and (working_selected_columns is null or pa.attname = any(working_selected_columns) or pk.pkey_attnum is not null)
                    )
                )
                -- Add "record" key for insert and update
                || case
                    when action in ('INSERT', 'UPDATE') then
                        jsonb_build_object(
                            'record',
                            (
                                select
                                    jsonb_object_agg(
                                        -- if unchanged toast, get column name and value from old record
                                        coalesce((c).name, (oc).name),
                                        case
                                            when (c).name is null then (oc).value
                                            else (c).value
                                        end
                                    )
                                from
                                    unnest(columns) c
                                    full outer join unnest(old_columns) oc
                                        on (c).name = (oc).name
                                where
                                    coalesce((c).is_selectable, (oc).is_selectable)
                                    and (working_selected_columns is null or coalesce((c).name, (oc).name) = any(working_selected_columns) or coalesce((c).is_pkey, (oc).is_pkey))
                                    and ( not error_record_exceeds_max_size or (octet_length((c).value::text) <= 64))
                            )
                        )
                    else '{}'::jsonb
                end
                -- Add "old_record" key for update and delete
                || case
                    when action = 'UPDATE' then
                        jsonb_build_object(
                                'old_record',
                                (
                                    select jsonb_object_agg((c).name, (c).value)
                                    from unnest(old_columns) c
                                    where
                                        (c).is_selectable
                                        and (working_selected_columns is null or (c).name = any(working_selected_columns) or (c).is_pkey)
                                        and ( not error_record_exceeds_max_size or (octet_length((c).value::text) <= 64))
                                )
                            )
                    when action = 'DELETE' then
                        jsonb_build_object(
                            'old_record',
                            (
                                select jsonb_object_agg((c).name, (c).value)
                                from unnest(old_columns) c
                                where
                                    (c).is_selectable
                                    and (working_selected_columns is null or (c).name = any(working_selected_columns) or (c).is_pkey)
                                    and ( not error_record_exceeds_max_size or (octet_length((c).value::text) <= 64))
                                    and ( not is_rls_enabled or (c).is_pkey ) -- if RLS enabled, we can't secure deletes so filter to pkey
                            )
                        )
                    else '{}'::jsonb
                end;

                -- Filter visible_role_sub_ids to those matching the current selected_columns group
                visible_to_subscription_ids = coalesce(
                    (
                        select array_agg(s.subscription_id)
                        from unnest(subscriptions) s
                        where s.claims_role = working_role
                          and (s.selected_columns is not distinct from working_selected_columns)
                          and s.subscription_id = any(visible_role_sub_ids)
                    ),
                    '{}'::uuid[]
                );

                return next (
                    output,
                    is_rls_enabled,
                    visible_to_subscription_ids,
                    case
                        when error_record_exceeds_max_size then array['Error 413: Payload Too Large']
                        else '{}'
                    end
                )::realtime.wal_rls;
            end loop;

        end if;
    end loop;

    perform set_config('role', null, true);
end;
$$;


ALTER FUNCTION realtime.apply_rls(wal jsonb, max_record_bytes integer) OWNER TO supabase_realtime_admin;

--
-- Name: broadcast_changes(text, text, text, text, text, record, record, text); Type: FUNCTION; Schema: realtime; Owner: supabase_realtime_admin
--

CREATE FUNCTION realtime.broadcast_changes(topic_name text, event_name text, operation text, table_name text, table_schema text, new record, old record, level text DEFAULT 'ROW'::text) RETURNS void
    LANGUAGE plpgsql
    AS $$
DECLARE
    -- Declare a variable to hold the JSONB representation of the row
    row_data jsonb := '{}'::jsonb;
BEGIN
    IF level = 'STATEMENT' THEN
        RAISE EXCEPTION 'function can only be triggered for each row, not for each statement';
    END IF;
    -- Check the operation type and handle accordingly
    IF operation = 'INSERT' OR operation = 'UPDATE' OR operation = 'DELETE' THEN
        row_data := jsonb_build_object('old_record', OLD, 'record', NEW, 'operation', operation, 'table', table_name, 'schema', table_schema);
        PERFORM realtime.send (row_data, event_name, topic_name);
    ELSE
        RAISE EXCEPTION 'Unexpected operation type: %', operation;
    END IF;
EXCEPTION
    WHEN OTHERS THEN
        RAISE EXCEPTION 'Failed to process the row: %', SQLERRM;
END;

$$;


ALTER FUNCTION realtime.broadcast_changes(topic_name text, event_name text, operation text, table_name text, table_schema text, new record, old record, level text) OWNER TO supabase_realtime_admin;

--
-- Name: build_prepared_statement_sql(text, regclass, realtime.wal_column[]); Type: FUNCTION; Schema: realtime; Owner: supabase_realtime_admin
--

CREATE FUNCTION realtime.build_prepared_statement_sql(prepared_statement_name text, entity regclass, columns realtime.wal_column[]) RETURNS text
    LANGUAGE sql
    AS $$
      /*
      Builds a sql string that, if executed, creates a prepared statement to
      tests retrive a row from *entity* by its primary key columns.
      Example
          select realtime.build_prepared_statement_sql('public.notes', '{"id"}'::text[], '{"bigint"}'::text[])
      */
          select
      'prepare ' || prepared_statement_name || ' as
          select
              exists(
                  select
                      1
                  from
                      ' || entity || '
                  where
                      ' || string_agg(quote_ident(pkc.name) || '=' || quote_nullable(pkc.value #>> '{}') , ' and ') || '
              )'
          from
              unnest(columns) pkc
          where
              pkc.is_pkey
          group by
              entity
      $$;


ALTER FUNCTION realtime.build_prepared_statement_sql(prepared_statement_name text, entity regclass, columns realtime.wal_column[]) OWNER TO supabase_realtime_admin;

--
-- Name: cast(text, regtype); Type: FUNCTION; Schema: realtime; Owner: supabase_realtime_admin
--

CREATE FUNCTION realtime."cast"(val text, type_ regtype) RETURNS jsonb
    LANGUAGE plpgsql IMMUTABLE
    AS $$
declare
  res jsonb;
begin
  if type_::text = 'bytea' then
    return to_jsonb(val);
  end if;
  execute format('select to_jsonb(%L::'|| type_::text || ')', val) into res;
  return res;
end
$$;


ALTER FUNCTION realtime."cast"(val text, type_ regtype) OWNER TO supabase_realtime_admin;

--
-- Name: check_equality_op(realtime.equality_op, regtype, text, text); Type: FUNCTION; Schema: realtime; Owner: supabase_realtime_admin
--

CREATE FUNCTION realtime.check_equality_op(op realtime.equality_op, type_ regtype, val_1 text, val_2 text) RETURNS boolean
    LANGUAGE plpgsql IMMUTABLE
    AS $$
/*
Casts *val_1* and *val_2* as type *type_* and check the *op* condition for truthiness
*/
declare
    op_symbol text = (
        case
            when op = 'eq' then '='
            when op = 'neq' then '!='
            when op = 'lt' then '<'
            when op = 'lte' then '<='
            when op = 'gt' then '>'
            when op = 'gte' then '>='
            when op = 'in' then '= any'
            else 'UNKNOWN OP'
        end
    );
    res boolean;
begin
    execute format(
        'select %L::'|| type_::text || ' ' || op_symbol
        || ' ( %L::'
        || (
            case
                when op = 'in' then type_::text || '[]'
                else type_::text end
        )
        || ')', val_1, val_2) into res;
    return res;
end;
$$;


ALTER FUNCTION realtime.check_equality_op(op realtime.equality_op, type_ regtype, val_1 text, val_2 text) OWNER TO supabase_realtime_admin;

--
-- Name: check_equality_op(realtime.equality_op, regtype, text, text, boolean); Type: FUNCTION; Schema: realtime; Owner: supabase_realtime_admin
--

CREATE FUNCTION realtime.check_equality_op(op realtime.equality_op, type_ regtype, val_1 text, val_2 text, negate boolean) RETURNS boolean
    LANGUAGE plpgsql STABLE
    AS $$
declare
    op_symbol text;
    res boolean;
begin
    -- IS DISTINCT FROM / IS NOT DISTINCT FROM: infix, both sides typed literals
    if op = 'isdistinct' then
        execute format(
            'select %L::%s %s %L::%s',
            val_1,
            type_::text,
            case when negate then 'IS NOT DISTINCT FROM' else 'IS DISTINCT FROM' end,
            val_2,
            type_::text
        ) into res;
        return res;
    end if;

    -- IS requires a keyword RHS (NULL, TRUE, FALSE, UNKNOWN), not a typed literal
    if op = 'is' then
        if val_2 not in ('null', 'true', 'false', 'unknown') then
            raise exception 'invalid value for is filter: must be null, true, false, or unknown';
        end if;
        execute format(
            'select %L::%s %s %s',
            val_1,
            type_::text,
            case when negate then 'IS NOT' else 'IS' end,
            upper(val_2)
        ) into res;
        return res;
    end if;

    op_symbol = case
        when op = 'eq'    then '='
        when op = 'neq'   then '!='
        when op = 'lt'    then '<'
        when op = 'lte'   then '<='
        when op = 'gt'    then '>'
        when op = 'gte'   then '>='
        when op = 'in'    then '= any'
        when op = 'like'   then 'LIKE'
        when op = 'ilike'  then 'ILIKE'
        when op = 'match'  then '~'
        when op = 'imatch' then '~*'
        else null
    end;

    if op_symbol is null then
        raise exception 'unsupported equality operator: %', op::text;
    end if;

    execute format(
        'select %L::%s %s (%L::%s)',
        val_1,
        type_::text,
        op_symbol,
        val_2,
        case when op = 'in' then type_::text || '[]' else type_::text end
    ) into res;

    return case when negate then not res else res end;
end;
$$;


ALTER FUNCTION realtime.check_equality_op(op realtime.equality_op, type_ regtype, val_1 text, val_2 text, negate boolean) OWNER TO supabase_realtime_admin;

--
-- Name: is_visible_through_filters(realtime.wal_column[], realtime.user_defined_filter[]); Type: FUNCTION; Schema: realtime; Owner: supabase_realtime_admin
--

CREATE FUNCTION realtime.is_visible_through_filters(columns realtime.wal_column[], filters realtime.user_defined_filter[]) RETURNS boolean
    LANGUAGE sql STABLE
    AS $$
    select
        filters is null
        or array_length(filters, 1) is null
        or coalesce(
            count(col.name) = count(1)
            and sum(
                realtime.check_equality_op(
                    op:=f.op,
                    type_:=coalesce(col.type_oid::regtype, col.type_name::regtype),
                    val_1:=col.value #>> '{}',
                    val_2:=f.value,
                    negate:=coalesce(f.negate, false)
                )::int
            ) filter (where col.name is not null) = count(col.name),
            false
        )
    from
        unnest(filters) f
        left join unnest(columns) col
            on f.column_name = col.name;
$$;


ALTER FUNCTION realtime.is_visible_through_filters(columns realtime.wal_column[], filters realtime.user_defined_filter[]) OWNER TO supabase_realtime_admin;

--
-- Name: list_changes(name, name, integer, integer); Type: FUNCTION; Schema: realtime; Owner: supabase_realtime_admin
--

CREATE FUNCTION realtime.list_changes(publication name, slot_name name, max_changes integer, max_record_bytes integer) RETURNS TABLE(wal jsonb, is_rls_enabled boolean, subscription_ids uuid[], errors text[], slot_changes_count bigint)
    LANGUAGE sql
    SET log_min_messages TO 'fatal'
    AS $$
  WITH pub AS (
    SELECT
      concat_ws(
        ',',
        CASE WHEN bool_or(pubinsert) THEN 'insert' ELSE NULL END,
        CASE WHEN bool_or(pubupdate) THEN 'update' ELSE NULL END,
        CASE WHEN bool_or(pubdelete) THEN 'delete' ELSE NULL END
      ) AS w2j_actions,
      coalesce(
        string_agg(
          realtime.quote_wal2json(format('%I.%I', schemaname, tablename)::regclass),
          ','
        ) filter (WHERE ppt.tablename IS NOT NULL),
        ''
      ) AS w2j_add_tables
    FROM pg_publication pp
    LEFT JOIN pg_publication_tables ppt ON pp.pubname = ppt.pubname
    WHERE pp.pubname = publication
    GROUP BY pp.pubname
    LIMIT 1
  ),
  -- MATERIALIZED ensures pg_logical_slot_get_changes is called exactly once
  w2j AS MATERIALIZED (
    SELECT x.*, pub.w2j_add_tables
    FROM pub,
         pg_logical_slot_get_changes(
           slot_name, null, max_changes,
           'include-pk', 'true',
           'include-transaction', 'false',
           'include-timestamp', 'true',
           'include-type-oids', 'true',
           'format-version', '2',
           'actions', pub.w2j_actions,
           'add-tables', pub.w2j_add_tables
         ) x
  ),
  slot_count AS (
    SELECT count(*)::bigint AS cnt
    FROM w2j
    WHERE w2j.w2j_add_tables <> ''
  ),
  rls_filtered AS (
    SELECT xyz.wal, xyz.is_rls_enabled, xyz.subscription_ids, xyz.errors
    FROM w2j,
         realtime.apply_rls(
           wal := w2j.data::jsonb,
           max_record_bytes := max_record_bytes
         ) xyz(wal, is_rls_enabled, subscription_ids, errors)
    WHERE w2j.w2j_add_tables <> ''
      AND xyz.subscription_ids[1] IS NOT NULL
  )
  SELECT rf.wal, rf.is_rls_enabled, rf.subscription_ids, rf.errors, sc.cnt
  FROM rls_filtered rf, slot_count sc

  UNION ALL

  SELECT null, null, null, null, sc.cnt
  FROM slot_count sc
  WHERE NOT EXISTS (SELECT 1 FROM rls_filtered)
$$;


ALTER FUNCTION realtime.list_changes(publication name, slot_name name, max_changes integer, max_record_bytes integer) OWNER TO supabase_realtime_admin;

--
-- Name: quote_wal2json(regclass); Type: FUNCTION; Schema: realtime; Owner: supabase_realtime_admin
--

CREATE FUNCTION realtime.quote_wal2json(entity regclass) RETURNS text
    LANGUAGE sql IMMUTABLE STRICT
    AS $$
  SELECT
    realtime.wal2json_escape_identifier(nsp.nspname::text)
    || '.'
    || realtime.wal2json_escape_identifier(pc.relname::text)
  FROM pg_class pc
  JOIN pg_namespace nsp ON pc.relnamespace = nsp.oid
  WHERE pc.oid = entity
$$;


ALTER FUNCTION realtime.quote_wal2json(entity regclass) OWNER TO supabase_realtime_admin;

--
-- Name: send(jsonb, text, text, boolean); Type: FUNCTION; Schema: realtime; Owner: supabase_realtime_admin
--

CREATE FUNCTION realtime.send(payload jsonb, event text, topic text, private boolean DEFAULT true) RETURNS void
    LANGUAGE plpgsql
    AS $$
DECLARE
  generated_id uuid;
  final_payload jsonb;
BEGIN
  BEGIN
    generated_id := gen_random_uuid();

    -- Check if payload has an 'id' key, if not, add the generated UUID
    IF payload ? 'id' THEN
      final_payload := payload;
    ELSE
      final_payload := jsonb_set(payload, '{id}', to_jsonb(generated_id));
    END IF;

    -- Set the topic configuration
    EXECUTE format('SET LOCAL realtime.topic TO %L', topic);

    INSERT INTO realtime.messages (id, payload, event, topic, private, extension)
    VALUES (generated_id, final_payload, event, topic, private, 'broadcast');
  EXCEPTION
    WHEN OTHERS THEN
      RAISE WARNING 'WarnSendingBroadcastMessage: %', SQLERRM;
  END;
END;
$$;


ALTER FUNCTION realtime.send(payload jsonb, event text, topic text, private boolean) OWNER TO supabase_realtime_admin;

--
-- Name: send_binary(bytea, text, text, boolean); Type: FUNCTION; Schema: realtime; Owner: supabase_realtime_admin
--

CREATE FUNCTION realtime.send_binary(payload bytea, event text, topic text, private boolean DEFAULT true) RETURNS void
    LANGUAGE plpgsql
    AS $$
DECLARE
  generated_id uuid;
BEGIN
  BEGIN
    generated_id := gen_random_uuid();

    EXECUTE format('SET LOCAL realtime.topic TO %L', topic);

    INSERT INTO realtime.messages (id, binary_payload, event, topic, private, extension)
    VALUES (generated_id, payload, event, topic, private, 'broadcast');
  EXCEPTION
    WHEN OTHERS THEN
      RAISE WARNING 'WarnSendingBroadcastMessage: %', SQLERRM;
  END;
END;
$$;


ALTER FUNCTION realtime.send_binary(payload bytea, event text, topic text, private boolean) OWNER TO supabase_realtime_admin;

--
-- Name: subscription_check_filters(); Type: FUNCTION; Schema: realtime; Owner: supabase_realtime_admin
--

CREATE FUNCTION realtime.subscription_check_filters() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
declare
    col_names text[] = coalesce(
            array_agg(a.attname order by a.attnum),
            '{}'::text[]
        )
        from
            pg_catalog.pg_attribute a
        where
            a.attrelid = new.entity
            and a.attnum > 0
            and not a.attisdropped
            and pg_catalog.has_column_privilege(
                (new.claims ->> 'role'),
                a.attrelid,
                a.attnum,
                'SELECT'
            );
    filter realtime.user_defined_filter;
    col_type regtype;
    in_val jsonb;
    selected_col text;
begin
    for filter in select * from unnest(new.filters) loop
        if not filter.column_name = any(col_names) then
            raise exception 'invalid column for filter %', filter.column_name;
        end if;

        col_type = (
            select atttypid::regtype
            from pg_catalog.pg_attribute
            where attrelid = new.entity
                  and attname = filter.column_name
        );
        if col_type is null then
            raise exception 'failed to lookup type for column %', filter.column_name;
        end if;

        if filter.op = 'in'::realtime.equality_op then
            in_val = realtime.cast(filter.value, (col_type::text || '[]')::regtype);
            if coalesce(jsonb_array_length(in_val), 0) > 100 then
                raise exception 'too many values for `in` filter. Maximum 100';
            end if;
        elsif filter.op = 'is'::realtime.equality_op then
            -- `is` requires a keyword RHS rather than a typed literal
            if filter.value not in ('null', 'true', 'false', 'unknown') then
                raise exception 'invalid value for is filter: must be null, true, false, or unknown';
            end if;
            -- IS NULL works for any type, but IS TRUE/FALSE/UNKNOWN require a boolean
            -- operand. Reject the non-null keywords on non-boolean columns here so they
            -- don't abort apply_rls at WAL time.
            if filter.value <> 'null' and col_type <> 'boolean'::regtype then
                raise exception 'is % filter requires a boolean column, got %', filter.value, col_type::text;
            end if;
        elsif filter.op in ('like'::realtime.equality_op, 'ilike'::realtime.equality_op) then
            -- like/ilike apply the text pattern operator (~~); reject column types that
            -- have no such operator instead of failing at WAL time
            if not exists (
                select 1 from pg_catalog.pg_operator
                where oprname = '~~' and oprleft = col_type
            ) then
                raise exception 'operator % requires a text-compatible column type, got %', filter.op::text, col_type::text;
            end if;
        elsif filter.op in ('match'::realtime.equality_op, 'imatch'::realtime.equality_op) then
            -- match/imatch apply the regex operators ~ / ~*; reject column types that have
            -- no such operator (e.g. integer) instead of failing at WAL time, mirroring the
            -- like/ilike guard above.
            if not exists (
                select 1 from pg_catalog.pg_operator
                where oprname = case when filter.op = 'imatch'::realtime.equality_op then '~*' else '~' end
                  and oprleft = col_type
                  and oprright = col_type
                  and oprresult = 'boolean'::regtype
            ) then
                raise exception 'operator % requires a text-compatible column type, got %', filter.op::text, col_type::text;
            end if;
            -- validate the regex eagerly so a bad pattern is rejected here, not inside
            -- apply_rls where it would abort the WAL stream for the entity
            begin
                perform '' ~ filter.value;
            exception when others then
                raise exception 'invalid regular expression for % filter: %', filter.op::text, sqlerrm;
            end;
        else
            -- eq/neq/lt/lte/gt/gte: value must be coercable to the type
            perform realtime.cast(filter.value, col_type);
        end if;
    end loop;

    if new.selected_columns is not null then
        for selected_col in select * from unnest(new.selected_columns) loop
            if not selected_col = any(col_names) then
                raise exception 'invalid column for select %', selected_col;
            end if;
        end loop;
    end if;

    -- Apply consistent order to filters so the unique constraint can't be tricked by a
    -- different filter order. negate is part of the sort key.
    new.filters = coalesce(
        array_agg(f order by f.column_name, f.op, f.value, f.negate),
        '{}'
    ) from unnest(new.filters) f;

    new.selected_columns = (
        select array_agg(c order by c)
        from unnest(new.selected_columns) c
    );

    return new;
end;
$$;


ALTER FUNCTION realtime.subscription_check_filters() OWNER TO supabase_realtime_admin;

--
-- Name: to_regrole(text); Type: FUNCTION; Schema: realtime; Owner: supabase_realtime_admin
--

CREATE FUNCTION realtime.to_regrole(role_name text) RETURNS regrole
    LANGUAGE sql IMMUTABLE
    AS $$ select role_name::regrole $$;


ALTER FUNCTION realtime.to_regrole(role_name text) OWNER TO supabase_realtime_admin;

--
-- Name: topic(); Type: FUNCTION; Schema: realtime; Owner: supabase_realtime_admin
--

CREATE FUNCTION realtime.topic() RETURNS text
    LANGUAGE sql STABLE
    AS $$
select nullif(current_setting('realtime.topic', true), '')::text;
$$;


ALTER FUNCTION realtime.topic() OWNER TO supabase_realtime_admin;

--
-- Name: wal2json_escape_identifier(text); Type: FUNCTION; Schema: realtime; Owner: supabase_realtime_admin
--

CREATE FUNCTION realtime.wal2json_escape_identifier(name text) RETURNS text
    LANGUAGE sql IMMUTABLE STRICT
    AS $$
  -- Prefix `\`, `,`, `.`, and any whitespace with `\`
  SELECT regexp_replace(name, '([\\,.[:space:]])', '\\\1', 'g')
$$;


ALTER FUNCTION realtime.wal2json_escape_identifier(name text) OWNER TO supabase_realtime_admin;

--
-- Name: allow_any_operation(text[]); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.allow_any_operation(expected_operations text[]) RETURNS boolean
    LANGUAGE sql STABLE
    AS $$
  WITH current_operation AS (
    SELECT storage.operation() AS raw_operation
  ),
  normalized AS (
    SELECT CASE
      WHEN raw_operation LIKE 'storage.%' THEN substr(raw_operation, 9)
      ELSE raw_operation
    END AS current_operation
    FROM current_operation
  )
  SELECT EXISTS (
    SELECT 1
    FROM normalized n
    CROSS JOIN LATERAL unnest(expected_operations) AS expected_operation
    WHERE expected_operation IS NOT NULL
      AND expected_operation <> ''
      AND n.current_operation = CASE
        WHEN expected_operation LIKE 'storage.%' THEN substr(expected_operation, 9)
        ELSE expected_operation
      END
  );
$$;


ALTER FUNCTION storage.allow_any_operation(expected_operations text[]) OWNER TO supabase_storage_admin;

--
-- Name: allow_only_operation(text); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.allow_only_operation(expected_operation text) RETURNS boolean
    LANGUAGE sql STABLE
    AS $$
  WITH current_operation AS (
    SELECT storage.operation() AS raw_operation
  ),
  normalized AS (
    SELECT
      CASE
        WHEN raw_operation LIKE 'storage.%' THEN substr(raw_operation, 9)
        ELSE raw_operation
      END AS current_operation,
      CASE
        WHEN expected_operation LIKE 'storage.%' THEN substr(expected_operation, 9)
        ELSE expected_operation
      END AS requested_operation
    FROM current_operation
  )
  SELECT CASE
    WHEN requested_operation IS NULL OR requested_operation = '' THEN FALSE
    ELSE COALESCE(current_operation = requested_operation, FALSE)
  END
  FROM normalized;
$$;


ALTER FUNCTION storage.allow_only_operation(expected_operation text) OWNER TO supabase_storage_admin;

--
-- Name: can_insert_object(text, text, uuid, jsonb); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.can_insert_object(bucketid text, name text, owner uuid, metadata jsonb) RETURNS void
    LANGUAGE plpgsql
    AS $$
BEGIN
  INSERT INTO "storage"."objects" ("bucket_id", "name", "owner", "metadata") VALUES (bucketid, name, owner, metadata);
  -- hack to rollback the successful insert
  RAISE sqlstate 'PT200' using
  message = 'ROLLBACK',
  detail = 'rollback successful insert';
END
$$;


ALTER FUNCTION storage.can_insert_object(bucketid text, name text, owner uuid, metadata jsonb) OWNER TO supabase_storage_admin;

--
-- Name: enforce_bucket_name_length(); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.enforce_bucket_name_length() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
begin
    if length(new.name) > 100 then
        raise exception 'bucket name "%" is too long (% characters). Max is 100.', new.name, length(new.name);
    end if;
    return new;
end;
$$;


ALTER FUNCTION storage.enforce_bucket_name_length() OWNER TO supabase_storage_admin;

--
-- Name: extension(text); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.extension(name text) RETURNS text
    LANGUAGE plpgsql IMMUTABLE
    AS $$
DECLARE
    _parts text[];
    _filename text;
BEGIN
    -- Split on "/" to get path segments
    SELECT string_to_array(name, '/') INTO _parts;
    -- Get the last path segment (the actual filename)
    SELECT _parts[array_length(_parts, 1)] INTO _filename;
    -- Extract extension: reverse, split on '.', then reverse again
    RETURN reverse(split_part(reverse(_filename), '.', 1));
END
$$;


ALTER FUNCTION storage.extension(name text) OWNER TO supabase_storage_admin;

--
-- Name: filename(text); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.filename(name text) RETURNS text
    LANGUAGE plpgsql
    AS $$
DECLARE
_parts text[];
BEGIN
	select string_to_array(name, '/') into _parts;
	return _parts[array_length(_parts,1)];
END
$$;


ALTER FUNCTION storage.filename(name text) OWNER TO supabase_storage_admin;

--
-- Name: foldername(text); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.foldername(name text) RETURNS text[]
    LANGUAGE plpgsql IMMUTABLE
    AS $$
DECLARE
    _parts text[];
BEGIN
    -- Split on "/" to get path segments
    SELECT string_to_array(name, '/') INTO _parts;
    -- Return everything except the last segment
    RETURN _parts[1 : array_length(_parts,1) - 1];
END
$$;


ALTER FUNCTION storage.foldername(name text) OWNER TO supabase_storage_admin;

--
-- Name: get_common_prefix(text, text, text); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.get_common_prefix(p_key text, p_prefix text, p_delimiter text) RETURNS text
    LANGUAGE sql IMMUTABLE
    AS $$
SELECT CASE
    WHEN position(p_delimiter IN substring(p_key FROM length(p_prefix) + 1)) > 0
    THEN left(p_key, length(p_prefix) + position(p_delimiter IN substring(p_key FROM length(p_prefix) + 1)))
    ELSE NULL
END;
$$;


ALTER FUNCTION storage.get_common_prefix(p_key text, p_prefix text, p_delimiter text) OWNER TO supabase_storage_admin;

--
-- Name: get_size_by_bucket(); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.get_size_by_bucket() RETURNS TABLE(size bigint, bucket_id text)
    LANGUAGE plpgsql STABLE
    AS $$
BEGIN
    return query
        select sum((metadata->>'size')::bigint)::bigint as size, obj.bucket_id
        from "storage".objects as obj
        group by obj.bucket_id;
END
$$;


ALTER FUNCTION storage.get_size_by_bucket() OWNER TO supabase_storage_admin;

--
-- Name: list_multipart_uploads_with_delimiter(text, text, text, integer, text, text); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.list_multipart_uploads_with_delimiter(bucket_id text, prefix_param text, delimiter_param text, max_keys integer DEFAULT 100, next_key_token text DEFAULT ''::text, next_upload_token text DEFAULT ''::text) RETURNS TABLE(key text, id text, created_at timestamp with time zone)
    LANGUAGE plpgsql
    AS $_$
BEGIN
    RETURN QUERY EXECUTE
        'SELECT DISTINCT ON(key COLLATE "C") * from (
            SELECT
                CASE
                    WHEN position($2 IN substring(key from length($1) + 1)) > 0 THEN
                        substring(key from 1 for length($1) + position($2 IN substring(key from length($1) + 1)))
                    ELSE
                        key
                END AS key, id, created_at
            FROM
                storage.s3_multipart_uploads
            WHERE
                bucket_id = $5 AND
                key ILIKE $1 || ''%'' AND
                CASE
                    WHEN $4 != '''' AND $6 = '''' THEN
                        CASE
                            WHEN position($2 IN substring(key from length($1) + 1)) > 0 THEN
                                substring(key from 1 for length($1) + position($2 IN substring(key from length($1) + 1))) COLLATE "C" > $4
                            ELSE
                                key COLLATE "C" > $4
                            END
                    ELSE
                        true
                END AND
                CASE
                    WHEN $6 != '''' THEN
                        id COLLATE "C" > $6
                    ELSE
                        true
                    END
            ORDER BY
                key COLLATE "C" ASC, created_at ASC) as e order by key COLLATE "C" LIMIT $3'
        USING prefix_param, delimiter_param, max_keys, next_key_token, bucket_id, next_upload_token;
END;
$_$;


ALTER FUNCTION storage.list_multipart_uploads_with_delimiter(bucket_id text, prefix_param text, delimiter_param text, max_keys integer, next_key_token text, next_upload_token text) OWNER TO supabase_storage_admin;

--
-- Name: list_objects_with_delimiter(text, text, text, integer, text, text, text); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.list_objects_with_delimiter(_bucket_id text, prefix_param text, delimiter_param text, max_keys integer DEFAULT 100, start_after text DEFAULT ''::text, next_token text DEFAULT ''::text, sort_order text DEFAULT 'asc'::text) RETURNS TABLE(name text, id uuid, metadata jsonb, updated_at timestamp with time zone, created_at timestamp with time zone, last_accessed_at timestamp with time zone)
    LANGUAGE plpgsql STABLE
    AS $_$
DECLARE
    v_peek_name TEXT;
    v_current RECORD;
    v_common_prefix TEXT;

    -- Configuration
    v_is_asc BOOLEAN;
    v_prefix TEXT;
    v_start TEXT;
    v_upper_bound TEXT;
    v_file_batch_size INT;

    -- Seek state
    v_next_seek TEXT;
    v_count INT := 0;

    -- Dynamic SQL for batch query only
    v_batch_query TEXT;

BEGIN
    -- ========================================================================
    -- INITIALIZATION
    -- ========================================================================
    v_is_asc := lower(coalesce(sort_order, 'asc')) = 'asc';
    v_prefix := coalesce(prefix_param, '');
    v_start := CASE WHEN coalesce(next_token, '') <> '' THEN next_token ELSE coalesce(start_after, '') END;
    v_file_batch_size := LEAST(GREATEST(max_keys * 2, 100), 1000);

    -- Calculate upper bound for prefix filtering (bytewise, using COLLATE "C")
    IF v_prefix = '' THEN
        v_upper_bound := NULL;
    ELSIF right(v_prefix, 1) = delimiter_param THEN
        v_upper_bound := left(v_prefix, -1) || chr(ascii(delimiter_param) + 1);
    ELSE
        v_upper_bound := left(v_prefix, -1) || chr(ascii(right(v_prefix, 1)) + 1);
    END IF;

    -- Build batch query (dynamic SQL - called infrequently, amortized over many rows)
    IF v_is_asc THEN
        IF v_upper_bound IS NOT NULL THEN
            v_batch_query := 'SELECT o.name, o.id, o.updated_at, o.created_at, o.last_accessed_at, o.metadata ' ||
                'FROM storage.objects o WHERE o.bucket_id = $1 AND o.name COLLATE "C" >= $2 ' ||
                'AND o.name COLLATE "C" < $3 ORDER BY o.name COLLATE "C" ASC LIMIT $4';
        ELSE
            v_batch_query := 'SELECT o.name, o.id, o.updated_at, o.created_at, o.last_accessed_at, o.metadata ' ||
                'FROM storage.objects o WHERE o.bucket_id = $1 AND o.name COLLATE "C" >= $2 ' ||
                'ORDER BY o.name COLLATE "C" ASC LIMIT $4';
        END IF;
    ELSE
        IF v_upper_bound IS NOT NULL THEN
            v_batch_query := 'SELECT o.name, o.id, o.updated_at, o.created_at, o.last_accessed_at, o.metadata ' ||
                'FROM storage.objects o WHERE o.bucket_id = $1 AND o.name COLLATE "C" < $2 ' ||
                'AND o.name COLLATE "C" >= $3 ORDER BY o.name COLLATE "C" DESC LIMIT $4';
        ELSE
            v_batch_query := 'SELECT o.name, o.id, o.updated_at, o.created_at, o.last_accessed_at, o.metadata ' ||
                'FROM storage.objects o WHERE o.bucket_id = $1 AND o.name COLLATE "C" < $2 ' ||
                'ORDER BY o.name COLLATE "C" DESC LIMIT $4';
        END IF;
    END IF;

    -- ========================================================================
    -- SEEK INITIALIZATION: Determine starting position
    -- ========================================================================
    IF v_start = '' THEN
        IF v_is_asc THEN
            v_next_seek := v_prefix;
        ELSE
            -- DESC without cursor: find the last item in range
            IF v_upper_bound IS NOT NULL THEN
                SELECT o.name INTO v_next_seek FROM storage.objects o
                WHERE o.bucket_id = _bucket_id AND o.name COLLATE "C" >= v_prefix AND o.name COLLATE "C" < v_upper_bound
                ORDER BY o.name COLLATE "C" DESC LIMIT 1;
            ELSIF v_prefix <> '' THEN
                SELECT o.name INTO v_next_seek FROM storage.objects o
                WHERE o.bucket_id = _bucket_id AND o.name COLLATE "C" >= v_prefix
                ORDER BY o.name COLLATE "C" DESC LIMIT 1;
            ELSE
                SELECT o.name INTO v_next_seek FROM storage.objects o
                WHERE o.bucket_id = _bucket_id
                ORDER BY o.name COLLATE "C" DESC LIMIT 1;
            END IF;

            IF v_next_seek IS NOT NULL THEN
                v_next_seek := v_next_seek || delimiter_param;
            ELSE
                RETURN;
            END IF;
        END IF;
    ELSE
        -- Cursor provided: determine if it refers to a folder or leaf
        IF EXISTS (
            SELECT 1 FROM storage.objects o
            WHERE o.bucket_id = _bucket_id
              AND o.name COLLATE "C" LIKE v_start || delimiter_param || '%'
            LIMIT 1
        ) THEN
            -- Cursor refers to a folder
            IF v_is_asc THEN
                v_next_seek := v_start || chr(ascii(delimiter_param) + 1);
            ELSE
                v_next_seek := v_start || delimiter_param;
            END IF;
        ELSE
            -- Cursor refers to a leaf object
            IF v_is_asc THEN
                v_next_seek := v_start || delimiter_param;
            ELSE
                v_next_seek := v_start;
            END IF;
        END IF;
    END IF;

    -- ========================================================================
    -- MAIN LOOP: Hybrid peek-then-batch algorithm
    -- Uses STATIC SQL for peek (hot path) and DYNAMIC SQL for batch
    -- ========================================================================
    LOOP
        EXIT WHEN v_count >= max_keys;

        -- STEP 1: PEEK using STATIC SQL (plan cached, very fast)
        IF v_is_asc THEN
            IF v_upper_bound IS NOT NULL THEN
                SELECT o.name INTO v_peek_name FROM storage.objects o
                WHERE o.bucket_id = _bucket_id AND o.name COLLATE "C" >= v_next_seek AND o.name COLLATE "C" < v_upper_bound
                ORDER BY o.name COLLATE "C" ASC LIMIT 1;
            ELSE
                SELECT o.name INTO v_peek_name FROM storage.objects o
                WHERE o.bucket_id = _bucket_id AND o.name COLLATE "C" >= v_next_seek
                ORDER BY o.name COLLATE "C" ASC LIMIT 1;
            END IF;
        ELSE
            IF v_upper_bound IS NOT NULL THEN
                SELECT o.name INTO v_peek_name FROM storage.objects o
                WHERE o.bucket_id = _bucket_id AND o.name COLLATE "C" < v_next_seek AND o.name COLLATE "C" >= v_prefix
                ORDER BY o.name COLLATE "C" DESC LIMIT 1;
            ELSIF v_prefix <> '' THEN
                SELECT o.name INTO v_peek_name FROM storage.objects o
                WHERE o.bucket_id = _bucket_id AND o.name COLLATE "C" < v_next_seek AND o.name COLLATE "C" >= v_prefix
                ORDER BY o.name COLLATE "C" DESC LIMIT 1;
            ELSE
                SELECT o.name INTO v_peek_name FROM storage.objects o
                WHERE o.bucket_id = _bucket_id AND o.name COLLATE "C" < v_next_seek
                ORDER BY o.name COLLATE "C" DESC LIMIT 1;
            END IF;
        END IF;

        EXIT WHEN v_peek_name IS NULL;

        -- STEP 2: Check if this is a FOLDER or FILE
        v_common_prefix := storage.get_common_prefix(v_peek_name, v_prefix, delimiter_param);

        IF v_common_prefix IS NOT NULL THEN
            -- FOLDER: Emit and skip to next folder (no heap access needed)
            name := rtrim(v_common_prefix, delimiter_param);
            id := NULL;
            updated_at := NULL;
            created_at := NULL;
            last_accessed_at := NULL;
            metadata := NULL;
            RETURN NEXT;
            v_count := v_count + 1;

            -- Advance seek past the folder range
            IF v_is_asc THEN
                v_next_seek := left(v_common_prefix, -1) || chr(ascii(delimiter_param) + 1);
            ELSE
                v_next_seek := v_common_prefix;
            END IF;
        ELSE
            -- FILE: Batch fetch using DYNAMIC SQL (overhead amortized over many rows)
            -- For ASC: upper_bound is the exclusive upper limit (< condition)
            -- For DESC: prefix is the inclusive lower limit (>= condition)
            FOR v_current IN EXECUTE v_batch_query USING _bucket_id, v_next_seek,
                CASE WHEN v_is_asc THEN COALESCE(v_upper_bound, v_prefix) ELSE v_prefix END, v_file_batch_size
            LOOP
                v_common_prefix := storage.get_common_prefix(v_current.name, v_prefix, delimiter_param);

                IF v_common_prefix IS NOT NULL THEN
                    -- Hit a folder: exit batch, let peek handle it
                    v_next_seek := v_current.name;
                    EXIT;
                END IF;

                -- Emit file
                name := v_current.name;
                id := v_current.id;
                updated_at := v_current.updated_at;
                created_at := v_current.created_at;
                last_accessed_at := v_current.last_accessed_at;
                metadata := v_current.metadata;
                RETURN NEXT;
                v_count := v_count + 1;

                -- Advance seek past this file
                IF v_is_asc THEN
                    v_next_seek := v_current.name || delimiter_param;
                ELSE
                    v_next_seek := v_current.name;
                END IF;

                EXIT WHEN v_count >= max_keys;
            END LOOP;
        END IF;
    END LOOP;
END;
$_$;


ALTER FUNCTION storage.list_objects_with_delimiter(_bucket_id text, prefix_param text, delimiter_param text, max_keys integer, start_after text, next_token text, sort_order text) OWNER TO supabase_storage_admin;

--
-- Name: operation(); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.operation() RETURNS text
    LANGUAGE plpgsql STABLE
    AS $$
BEGIN
    RETURN current_setting('storage.operation', true);
END;
$$;


ALTER FUNCTION storage.operation() OWNER TO supabase_storage_admin;

--
-- Name: protect_delete(); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.protect_delete() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    -- Check if storage.allow_delete_query is set to 'true'
    IF COALESCE(current_setting('storage.allow_delete_query', true), 'false') != 'true' THEN
        RAISE EXCEPTION 'Direct deletion from storage tables is not allowed. Use the Storage API instead.'
            USING HINT = 'This prevents accidental data loss from orphaned objects.',
                  ERRCODE = '42501';
    END IF;
    RETURN NULL;
END;
$$;


ALTER FUNCTION storage.protect_delete() OWNER TO supabase_storage_admin;

--
-- Name: search(text, text, integer, integer, integer, text, text, text); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.search(prefix text, bucketname text, limits integer DEFAULT 100, levels integer DEFAULT 1, offsets integer DEFAULT 0, search text DEFAULT ''::text, sortcolumn text DEFAULT 'name'::text, sortorder text DEFAULT 'asc'::text) RETURNS TABLE(name text, id uuid, updated_at timestamp with time zone, created_at timestamp with time zone, last_accessed_at timestamp with time zone, metadata jsonb)
    LANGUAGE plpgsql STABLE
    AS $_$
DECLARE
    v_peek_name TEXT;
    v_current RECORD;
    v_common_prefix TEXT;
    v_delimiter CONSTANT TEXT := '/';

    -- Configuration
    v_limit INT;
    v_prefix TEXT;
    v_prefix_lower TEXT;
    v_is_asc BOOLEAN;
    v_order_by TEXT;
    v_sort_order TEXT;
    v_upper_bound TEXT;
    v_file_batch_size INT;

    -- Dynamic SQL for batch query only
    v_batch_query TEXT;

    -- Seek state
    v_next_seek TEXT;
    v_count INT := 0;
    v_skipped INT := 0;
BEGIN
    -- ========================================================================
    -- INITIALIZATION
    -- ========================================================================
    v_limit := LEAST(coalesce(limits, 100), 1500);
    v_prefix := coalesce(prefix, '') || coalesce(search, '');
    v_prefix_lower := lower(v_prefix);
    v_is_asc := lower(coalesce(sortorder, 'asc')) = 'asc';
    v_file_batch_size := LEAST(GREATEST(v_limit * 2, 100), 1000);

    -- Validate sort column
    CASE lower(coalesce(sortcolumn, 'name'))
        WHEN 'name' THEN v_order_by := 'name';
        WHEN 'updated_at' THEN v_order_by := 'updated_at';
        WHEN 'created_at' THEN v_order_by := 'created_at';
        WHEN 'last_accessed_at' THEN v_order_by := 'last_accessed_at';
        ELSE v_order_by := 'name';
    END CASE;

    v_sort_order := CASE WHEN v_is_asc THEN 'asc' ELSE 'desc' END;

    -- ========================================================================
    -- NON-NAME SORTING: Use path_tokens approach (unchanged)
    -- ========================================================================
    IF v_order_by != 'name' THEN
        RETURN QUERY EXECUTE format(
            $sql$
            WITH folders AS (
                SELECT path_tokens[$1] AS folder
                FROM storage.objects
                WHERE objects.name ILIKE $2 || '%%'
                  AND bucket_id = $3
                  AND array_length(objects.path_tokens, 1) <> $1
                GROUP BY folder
                ORDER BY folder %s
            )
            (SELECT folder AS "name",
                   NULL::uuid AS id,
                   NULL::timestamptz AS updated_at,
                   NULL::timestamptz AS created_at,
                   NULL::timestamptz AS last_accessed_at,
                   NULL::jsonb AS metadata FROM folders)
            UNION ALL
            (SELECT path_tokens[$1] AS "name",
                   id, updated_at, created_at, last_accessed_at, metadata
             FROM storage.objects
             WHERE objects.name ILIKE $2 || '%%'
               AND bucket_id = $3
               AND array_length(objects.path_tokens, 1) = $1
             ORDER BY %I %s)
            LIMIT $4 OFFSET $5
            $sql$, v_sort_order, v_order_by, v_sort_order
        ) USING levels, v_prefix, bucketname, v_limit, offsets;
        RETURN;
    END IF;

    -- ========================================================================
    -- NAME SORTING: Hybrid skip-scan with batch optimization
    -- ========================================================================

    -- Calculate upper bound for prefix filtering
    IF v_prefix_lower = '' THEN
        v_upper_bound := NULL;
    ELSIF right(v_prefix_lower, 1) = v_delimiter THEN
        v_upper_bound := left(v_prefix_lower, -1) || chr(ascii(v_delimiter) + 1);
    ELSE
        v_upper_bound := left(v_prefix_lower, -1) || chr(ascii(right(v_prefix_lower, 1)) + 1);
    END IF;

    -- Build batch query (dynamic SQL - called infrequently, amortized over many rows)
    IF v_is_asc THEN
        IF v_upper_bound IS NOT NULL THEN
            v_batch_query := 'SELECT o.name, o.id, o.updated_at, o.created_at, o.last_accessed_at, o.metadata ' ||
                'FROM storage.objects o WHERE o.bucket_id = $1 AND lower(o.name) COLLATE "C" >= $2 ' ||
                'AND lower(o.name) COLLATE "C" < $3 ORDER BY lower(o.name) COLLATE "C" ASC LIMIT $4';
        ELSE
            v_batch_query := 'SELECT o.name, o.id, o.updated_at, o.created_at, o.last_accessed_at, o.metadata ' ||
                'FROM storage.objects o WHERE o.bucket_id = $1 AND lower(o.name) COLLATE "C" >= $2 ' ||
                'ORDER BY lower(o.name) COLLATE "C" ASC LIMIT $4';
        END IF;
    ELSE
        IF v_upper_bound IS NOT NULL THEN
            v_batch_query := 'SELECT o.name, o.id, o.updated_at, o.created_at, o.last_accessed_at, o.metadata ' ||
                'FROM storage.objects o WHERE o.bucket_id = $1 AND lower(o.name) COLLATE "C" < $2 ' ||
                'AND lower(o.name) COLLATE "C" >= $3 ORDER BY lower(o.name) COLLATE "C" DESC LIMIT $4';
        ELSE
            v_batch_query := 'SELECT o.name, o.id, o.updated_at, o.created_at, o.last_accessed_at, o.metadata ' ||
                'FROM storage.objects o WHERE o.bucket_id = $1 AND lower(o.name) COLLATE "C" < $2 ' ||
                'ORDER BY lower(o.name) COLLATE "C" DESC LIMIT $4';
        END IF;
    END IF;

    -- Initialize seek position
    IF v_is_asc THEN
        v_next_seek := v_prefix_lower;
    ELSE
        -- DESC: find the last item in range first (static SQL)
        IF v_upper_bound IS NOT NULL THEN
            SELECT o.name INTO v_peek_name FROM storage.objects o
            WHERE o.bucket_id = bucketname AND lower(o.name) COLLATE "C" >= v_prefix_lower AND lower(o.name) COLLATE "C" < v_upper_bound
            ORDER BY lower(o.name) COLLATE "C" DESC LIMIT 1;
        ELSIF v_prefix_lower <> '' THEN
            SELECT o.name INTO v_peek_name FROM storage.objects o
            WHERE o.bucket_id = bucketname AND lower(o.name) COLLATE "C" >= v_prefix_lower
            ORDER BY lower(o.name) COLLATE "C" DESC LIMIT 1;
        ELSE
            SELECT o.name INTO v_peek_name FROM storage.objects o
            WHERE o.bucket_id = bucketname
            ORDER BY lower(o.name) COLLATE "C" DESC LIMIT 1;
        END IF;

        IF v_peek_name IS NOT NULL THEN
            v_next_seek := lower(v_peek_name) || v_delimiter;
        ELSE
            RETURN;
        END IF;
    END IF;

    -- ========================================================================
    -- MAIN LOOP: Hybrid peek-then-batch algorithm
    -- Uses STATIC SQL for peek (hot path) and DYNAMIC SQL for batch
    -- ========================================================================
    LOOP
        EXIT WHEN v_count >= v_limit;

        -- STEP 1: PEEK using STATIC SQL (plan cached, very fast)
        IF v_is_asc THEN
            IF v_upper_bound IS NOT NULL THEN
                SELECT o.name INTO v_peek_name FROM storage.objects o
                WHERE o.bucket_id = bucketname AND lower(o.name) COLLATE "C" >= v_next_seek AND lower(o.name) COLLATE "C" < v_upper_bound
                ORDER BY lower(o.name) COLLATE "C" ASC LIMIT 1;
            ELSE
                SELECT o.name INTO v_peek_name FROM storage.objects o
                WHERE o.bucket_id = bucketname AND lower(o.name) COLLATE "C" >= v_next_seek
                ORDER BY lower(o.name) COLLATE "C" ASC LIMIT 1;
            END IF;
        ELSE
            IF v_upper_bound IS NOT NULL THEN
                SELECT o.name INTO v_peek_name FROM storage.objects o
                WHERE o.bucket_id = bucketname AND lower(o.name) COLLATE "C" < v_next_seek AND lower(o.name) COLLATE "C" >= v_prefix_lower
                ORDER BY lower(o.name) COLLATE "C" DESC LIMIT 1;
            ELSIF v_prefix_lower <> '' THEN
                SELECT o.name INTO v_peek_name FROM storage.objects o
                WHERE o.bucket_id = bucketname AND lower(o.name) COLLATE "C" < v_next_seek AND lower(o.name) COLLATE "C" >= v_prefix_lower
                ORDER BY lower(o.name) COLLATE "C" DESC LIMIT 1;
            ELSE
                SELECT o.name INTO v_peek_name FROM storage.objects o
                WHERE o.bucket_id = bucketname AND lower(o.name) COLLATE "C" < v_next_seek
                ORDER BY lower(o.name) COLLATE "C" DESC LIMIT 1;
            END IF;
        END IF;

        EXIT WHEN v_peek_name IS NULL;

        -- STEP 2: Check if this is a FOLDER or FILE
        v_common_prefix := storage.get_common_prefix(lower(v_peek_name), v_prefix_lower, v_delimiter);

        IF v_common_prefix IS NOT NULL THEN
            -- FOLDER: Handle offset, emit if needed, skip to next folder
            IF v_skipped < offsets THEN
                v_skipped := v_skipped + 1;
            ELSE
                name := split_part(rtrim(storage.get_common_prefix(v_peek_name, v_prefix, v_delimiter), v_delimiter), v_delimiter, levels);
                id := NULL;
                updated_at := NULL;
                created_at := NULL;
                last_accessed_at := NULL;
                metadata := NULL;
                RETURN NEXT;
                v_count := v_count + 1;
            END IF;

            -- Advance seek past the folder range
            IF v_is_asc THEN
                v_next_seek := lower(left(v_common_prefix, -1)) || chr(ascii(v_delimiter) + 1);
            ELSE
                v_next_seek := lower(v_common_prefix);
            END IF;
        ELSE
            -- FILE: Batch fetch using DYNAMIC SQL (overhead amortized over many rows)
            -- For ASC: upper_bound is the exclusive upper limit (< condition)
            -- For DESC: prefix_lower is the inclusive lower limit (>= condition)
            FOR v_current IN EXECUTE v_batch_query
                USING bucketname, v_next_seek,
                    CASE WHEN v_is_asc THEN COALESCE(v_upper_bound, v_prefix_lower) ELSE v_prefix_lower END, v_file_batch_size
            LOOP
                v_common_prefix := storage.get_common_prefix(lower(v_current.name), v_prefix_lower, v_delimiter);

                IF v_common_prefix IS NOT NULL THEN
                    -- Hit a folder: exit batch, let peek handle it
                    v_next_seek := lower(v_current.name);
                    EXIT;
                END IF;

                -- Handle offset skipping
                IF v_skipped < offsets THEN
                    v_skipped := v_skipped + 1;
                ELSE
                    -- Emit file
                    name := split_part(v_current.name, v_delimiter, levels);
                    id := v_current.id;
                    updated_at := v_current.updated_at;
                    created_at := v_current.created_at;
                    last_accessed_at := v_current.last_accessed_at;
                    metadata := v_current.metadata;
                    RETURN NEXT;
                    v_count := v_count + 1;
                END IF;

                -- Advance seek past this file
                IF v_is_asc THEN
                    v_next_seek := lower(v_current.name) || v_delimiter;
                ELSE
                    v_next_seek := lower(v_current.name);
                END IF;

                EXIT WHEN v_count >= v_limit;
            END LOOP;
        END IF;
    END LOOP;
END;
$_$;


ALTER FUNCTION storage.search(prefix text, bucketname text, limits integer, levels integer, offsets integer, search text, sortcolumn text, sortorder text) OWNER TO supabase_storage_admin;

--
-- Name: search_by_timestamp(text, text, integer, integer, text, text, text, text); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.search_by_timestamp(p_prefix text, p_bucket_id text, p_limit integer, p_level integer, p_start_after text, p_sort_order text, p_sort_column text, p_sort_column_after text) RETURNS TABLE(key text, name text, id uuid, updated_at timestamp with time zone, created_at timestamp with time zone, last_accessed_at timestamp with time zone, metadata jsonb)
    LANGUAGE plpgsql STABLE
    AS $_$
DECLARE
    v_cursor_op text;
    v_query text;
    v_prefix text;
BEGIN
    v_prefix := coalesce(p_prefix, '');

    IF p_sort_order = 'asc' THEN
        v_cursor_op := '>';
    ELSE
        v_cursor_op := '<';
    END IF;

    v_query := format($sql$
        WITH raw_objects AS (
            SELECT
                o.name AS obj_name,
                o.id AS obj_id,
                o.updated_at AS obj_updated_at,
                o.created_at AS obj_created_at,
                o.last_accessed_at AS obj_last_accessed_at,
                o.metadata AS obj_metadata,
                storage.get_common_prefix(o.name, $1, '/') AS common_prefix
            FROM storage.objects o
            WHERE o.bucket_id = $2
              AND o.name COLLATE "C" LIKE $1 || '%%'
        ),
        -- Aggregate common prefixes (folders)
        -- Both created_at and updated_at use MIN(obj_created_at) to match the old prefixes table behavior
        aggregated_prefixes AS (
            SELECT
                rtrim(common_prefix, '/') AS name,
                NULL::uuid AS id,
                MIN(obj_created_at) AS updated_at,
                MIN(obj_created_at) AS created_at,
                NULL::timestamptz AS last_accessed_at,
                NULL::jsonb AS metadata,
                TRUE AS is_prefix
            FROM raw_objects
            WHERE common_prefix IS NOT NULL
            GROUP BY common_prefix
        ),
        leaf_objects AS (
            SELECT
                obj_name AS name,
                obj_id AS id,
                obj_updated_at AS updated_at,
                obj_created_at AS created_at,
                obj_last_accessed_at AS last_accessed_at,
                obj_metadata AS metadata,
                FALSE AS is_prefix
            FROM raw_objects
            WHERE common_prefix IS NULL
        ),
        combined AS (
            SELECT * FROM aggregated_prefixes
            UNION ALL
            SELECT * FROM leaf_objects
        ),
        filtered AS (
            SELECT *
            FROM combined
            WHERE (
                $5 = ''
                OR ROW(
                    date_trunc('milliseconds', %I),
                    name COLLATE "C"
                ) %s ROW(
                    COALESCE(NULLIF($6, '')::timestamptz, 'epoch'::timestamptz),
                    $5
                )
            )
        )
        SELECT
            split_part(name, '/', $3) AS key,
            name,
            id,
            updated_at,
            created_at,
            last_accessed_at,
            metadata
        FROM filtered
        ORDER BY
            COALESCE(date_trunc('milliseconds', %I), 'epoch'::timestamptz) %s,
            name COLLATE "C" %s
        LIMIT $4
    $sql$,
        p_sort_column,
        v_cursor_op,
        p_sort_column,
        p_sort_order,
        p_sort_order
    );

    RETURN QUERY EXECUTE v_query
    USING v_prefix, p_bucket_id, p_level, p_limit, p_start_after, p_sort_column_after;
END;
$_$;


ALTER FUNCTION storage.search_by_timestamp(p_prefix text, p_bucket_id text, p_limit integer, p_level integer, p_start_after text, p_sort_order text, p_sort_column text, p_sort_column_after text) OWNER TO supabase_storage_admin;

--
-- Name: search_v2(text, text, integer, integer, text, text, text, text); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.search_v2(prefix text, bucket_name text, limits integer DEFAULT 100, levels integer DEFAULT 1, start_after text DEFAULT ''::text, sort_order text DEFAULT 'asc'::text, sort_column text DEFAULT 'name'::text, sort_column_after text DEFAULT ''::text) RETURNS TABLE(key text, name text, id uuid, updated_at timestamp with time zone, created_at timestamp with time zone, last_accessed_at timestamp with time zone, metadata jsonb)
    LANGUAGE plpgsql STABLE
    AS $$
DECLARE
    v_sort_col text;
    v_sort_ord text;
    v_limit int;
BEGIN
    -- Cap limit to maximum of 1500 records
    v_limit := LEAST(coalesce(limits, 100), 1500);

    -- Validate and normalize sort_order
    v_sort_ord := lower(coalesce(sort_order, 'asc'));
    IF v_sort_ord NOT IN ('asc', 'desc') THEN
        v_sort_ord := 'asc';
    END IF;

    -- Validate and normalize sort_column
    v_sort_col := lower(coalesce(sort_column, 'name'));
    IF v_sort_col NOT IN ('name', 'updated_at', 'created_at') THEN
        v_sort_col := 'name';
    END IF;

    -- Route to appropriate implementation
    IF v_sort_col = 'name' THEN
        -- Use list_objects_with_delimiter for name sorting (most efficient: O(k * log n))
        RETURN QUERY
        SELECT
            split_part(l.name, '/', levels) AS key,
            l.name AS name,
            l.id,
            l.updated_at,
            l.created_at,
            l.last_accessed_at,
            l.metadata
        FROM storage.list_objects_with_delimiter(
            bucket_name,
            coalesce(prefix, ''),
            '/',
            v_limit,
            start_after,
            '',
            v_sort_ord
        ) l;
    ELSE
        -- Use aggregation approach for timestamp sorting
        -- Not efficient for large datasets but supports correct pagination
        RETURN QUERY SELECT * FROM storage.search_by_timestamp(
            prefix, bucket_name, v_limit, levels, start_after,
            v_sort_ord, v_sort_col, sort_column_after
        );
    END IF;
END;
$$;


ALTER FUNCTION storage.search_v2(prefix text, bucket_name text, limits integer, levels integer, start_after text, sort_order text, sort_column text, sort_column_after text) OWNER TO supabase_storage_admin;

--
-- Name: update_updated_at_column(); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.update_updated_at_column() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW; 
END;
$$;


ALTER FUNCTION storage.update_updated_at_column() OWNER TO supabase_storage_admin;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: audit_log_entries; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TABLE auth.audit_log_entries (
    instance_id uuid,
    id uuid NOT NULL,
    payload json,
    created_at timestamp with time zone,
    ip_address character varying(64) DEFAULT ''::character varying NOT NULL
);


ALTER TABLE auth.audit_log_entries OWNER TO supabase_auth_admin;

--
-- Name: TABLE audit_log_entries; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON TABLE auth.audit_log_entries IS 'Auth: Audit trail for user actions.';


--
-- Name: custom_oauth_providers; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TABLE auth.custom_oauth_providers (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    provider_type text NOT NULL,
    identifier text NOT NULL,
    name text NOT NULL,
    client_id text NOT NULL,
    client_secret text NOT NULL,
    acceptable_client_ids text[] DEFAULT '{}'::text[] NOT NULL,
    scopes text[] DEFAULT '{}'::text[] NOT NULL,
    pkce_enabled boolean DEFAULT true NOT NULL,
    attribute_mapping jsonb DEFAULT '{}'::jsonb NOT NULL,
    authorization_params jsonb DEFAULT '{}'::jsonb NOT NULL,
    enabled boolean DEFAULT true NOT NULL,
    email_optional boolean DEFAULT false NOT NULL,
    issuer text,
    discovery_url text,
    skip_nonce_check boolean DEFAULT false NOT NULL,
    cached_discovery jsonb,
    discovery_cached_at timestamp with time zone,
    authorization_url text,
    token_url text,
    userinfo_url text,
    jwks_uri text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    custom_claims_allowlist text[] DEFAULT '{}'::text[] NOT NULL,
    CONSTRAINT custom_oauth_providers_authorization_url_https CHECK (((authorization_url IS NULL) OR (authorization_url ~~ 'https://%'::text))),
    CONSTRAINT custom_oauth_providers_authorization_url_length CHECK (((authorization_url IS NULL) OR (char_length(authorization_url) <= 2048))),
    CONSTRAINT custom_oauth_providers_client_id_length CHECK (((char_length(client_id) >= 1) AND (char_length(client_id) <= 512))),
    CONSTRAINT custom_oauth_providers_discovery_url_length CHECK (((discovery_url IS NULL) OR (char_length(discovery_url) <= 2048))),
    CONSTRAINT custom_oauth_providers_identifier_format CHECK ((identifier ~ '^[a-z0-9][a-z0-9:-]{0,48}[a-z0-9]$'::text)),
    CONSTRAINT custom_oauth_providers_issuer_length CHECK (((issuer IS NULL) OR ((char_length(issuer) >= 1) AND (char_length(issuer) <= 2048)))),
    CONSTRAINT custom_oauth_providers_jwks_uri_https CHECK (((jwks_uri IS NULL) OR (jwks_uri ~~ 'https://%'::text))),
    CONSTRAINT custom_oauth_providers_jwks_uri_length CHECK (((jwks_uri IS NULL) OR (char_length(jwks_uri) <= 2048))),
    CONSTRAINT custom_oauth_providers_name_length CHECK (((char_length(name) >= 1) AND (char_length(name) <= 100))),
    CONSTRAINT custom_oauth_providers_oauth2_requires_endpoints CHECK (((provider_type <> 'oauth2'::text) OR ((authorization_url IS NOT NULL) AND (token_url IS NOT NULL) AND (userinfo_url IS NOT NULL)))),
    CONSTRAINT custom_oauth_providers_oidc_discovery_url_https CHECK (((provider_type <> 'oidc'::text) OR (discovery_url IS NULL) OR (discovery_url ~~ 'https://%'::text))),
    CONSTRAINT custom_oauth_providers_oidc_issuer_https CHECK (((provider_type <> 'oidc'::text) OR (issuer IS NULL) OR (issuer ~~ 'https://%'::text))),
    CONSTRAINT custom_oauth_providers_oidc_requires_issuer CHECK (((provider_type <> 'oidc'::text) OR (issuer IS NOT NULL))),
    CONSTRAINT custom_oauth_providers_provider_type_check CHECK ((provider_type = ANY (ARRAY['oauth2'::text, 'oidc'::text]))),
    CONSTRAINT custom_oauth_providers_token_url_https CHECK (((token_url IS NULL) OR (token_url ~~ 'https://%'::text))),
    CONSTRAINT custom_oauth_providers_token_url_length CHECK (((token_url IS NULL) OR (char_length(token_url) <= 2048))),
    CONSTRAINT custom_oauth_providers_userinfo_url_https CHECK (((userinfo_url IS NULL) OR (userinfo_url ~~ 'https://%'::text))),
    CONSTRAINT custom_oauth_providers_userinfo_url_length CHECK (((userinfo_url IS NULL) OR (char_length(userinfo_url) <= 2048)))
);


ALTER TABLE auth.custom_oauth_providers OWNER TO supabase_auth_admin;

--
-- Name: flow_state; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TABLE auth.flow_state (
    id uuid NOT NULL,
    user_id uuid,
    auth_code text,
    code_challenge_method auth.code_challenge_method,
    code_challenge text,
    provider_type text NOT NULL,
    provider_access_token text,
    provider_refresh_token text,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    authentication_method text NOT NULL,
    auth_code_issued_at timestamp with time zone,
    invite_token text,
    referrer text,
    oauth_client_state_id uuid,
    linking_target_id uuid,
    email_optional boolean DEFAULT false NOT NULL
);


ALTER TABLE auth.flow_state OWNER TO supabase_auth_admin;

--
-- Name: TABLE flow_state; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON TABLE auth.flow_state IS 'Stores metadata for all OAuth/SSO login flows';


--
-- Name: identities; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TABLE auth.identities (
    provider_id text NOT NULL,
    user_id uuid NOT NULL,
    identity_data jsonb NOT NULL,
    provider text NOT NULL,
    last_sign_in_at timestamp with time zone,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    email text GENERATED ALWAYS AS (lower((identity_data ->> 'email'::text))) STORED,
    id uuid DEFAULT gen_random_uuid() NOT NULL
);


ALTER TABLE auth.identities OWNER TO supabase_auth_admin;

--
-- Name: TABLE identities; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON TABLE auth.identities IS 'Auth: Stores identities associated to a user.';


--
-- Name: COLUMN identities.email; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON COLUMN auth.identities.email IS 'Auth: Email is a generated column that references the optional email property in the identity_data';


--
-- Name: instances; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TABLE auth.instances (
    id uuid NOT NULL,
    uuid uuid,
    raw_base_config text,
    created_at timestamp with time zone,
    updated_at timestamp with time zone
);


ALTER TABLE auth.instances OWNER TO supabase_auth_admin;

--
-- Name: TABLE instances; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON TABLE auth.instances IS 'Auth: Manages users across multiple sites.';


--
-- Name: mfa_amr_claims; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TABLE auth.mfa_amr_claims (
    session_id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    authentication_method text NOT NULL,
    id uuid NOT NULL
);


ALTER TABLE auth.mfa_amr_claims OWNER TO supabase_auth_admin;

--
-- Name: TABLE mfa_amr_claims; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON TABLE auth.mfa_amr_claims IS 'auth: stores authenticator method reference claims for multi factor authentication';


--
-- Name: mfa_challenges; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TABLE auth.mfa_challenges (
    id uuid NOT NULL,
    factor_id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL,
    verified_at timestamp with time zone,
    ip_address inet NOT NULL,
    otp_code text,
    web_authn_session_data jsonb
);


ALTER TABLE auth.mfa_challenges OWNER TO supabase_auth_admin;

--
-- Name: TABLE mfa_challenges; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON TABLE auth.mfa_challenges IS 'auth: stores metadata about challenge requests made';


--
-- Name: mfa_factors; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TABLE auth.mfa_factors (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    friendly_name text,
    factor_type auth.factor_type NOT NULL,
    status auth.factor_status NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    secret text,
    phone text,
    last_challenged_at timestamp with time zone,
    web_authn_credential jsonb,
    web_authn_aaguid uuid,
    last_webauthn_challenge_data jsonb
);


ALTER TABLE auth.mfa_factors OWNER TO supabase_auth_admin;

--
-- Name: TABLE mfa_factors; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON TABLE auth.mfa_factors IS 'auth: stores metadata about factors';


--
-- Name: COLUMN mfa_factors.last_webauthn_challenge_data; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON COLUMN auth.mfa_factors.last_webauthn_challenge_data IS 'Stores the latest WebAuthn challenge data including attestation/assertion for customer verification';


--
-- Name: oauth_authorizations; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TABLE auth.oauth_authorizations (
    id uuid NOT NULL,
    authorization_id text NOT NULL,
    client_id uuid NOT NULL,
    user_id uuid,
    redirect_uri text NOT NULL,
    scope text NOT NULL,
    state text,
    resource text,
    code_challenge text,
    code_challenge_method auth.code_challenge_method,
    response_type auth.oauth_response_type DEFAULT 'code'::auth.oauth_response_type NOT NULL,
    status auth.oauth_authorization_status DEFAULT 'pending'::auth.oauth_authorization_status NOT NULL,
    authorization_code text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    expires_at timestamp with time zone DEFAULT (now() + '00:03:00'::interval) NOT NULL,
    approved_at timestamp with time zone,
    nonce text,
    CONSTRAINT oauth_authorizations_authorization_code_length CHECK ((char_length(authorization_code) <= 255)),
    CONSTRAINT oauth_authorizations_code_challenge_length CHECK ((char_length(code_challenge) <= 128)),
    CONSTRAINT oauth_authorizations_expires_at_future CHECK ((expires_at > created_at)),
    CONSTRAINT oauth_authorizations_nonce_length CHECK ((char_length(nonce) <= 255)),
    CONSTRAINT oauth_authorizations_redirect_uri_length CHECK ((char_length(redirect_uri) <= 2048)),
    CONSTRAINT oauth_authorizations_resource_length CHECK ((char_length(resource) <= 2048)),
    CONSTRAINT oauth_authorizations_scope_length CHECK ((char_length(scope) <= 4096)),
    CONSTRAINT oauth_authorizations_state_length CHECK ((char_length(state) <= 4096))
);


ALTER TABLE auth.oauth_authorizations OWNER TO supabase_auth_admin;

--
-- Name: oauth_client_states; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TABLE auth.oauth_client_states (
    id uuid NOT NULL,
    provider_type text NOT NULL,
    code_verifier text,
    created_at timestamp with time zone NOT NULL
);


ALTER TABLE auth.oauth_client_states OWNER TO supabase_auth_admin;

--
-- Name: TABLE oauth_client_states; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON TABLE auth.oauth_client_states IS 'Stores OAuth states for third-party provider authentication flows where Supabase acts as the OAuth client.';


--
-- Name: oauth_clients; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TABLE auth.oauth_clients (
    id uuid NOT NULL,
    client_secret_hash text,
    registration_type auth.oauth_registration_type NOT NULL,
    redirect_uris text NOT NULL,
    grant_types text NOT NULL,
    client_name text,
    client_uri text,
    logo_uri text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    deleted_at timestamp with time zone,
    client_type auth.oauth_client_type DEFAULT 'confidential'::auth.oauth_client_type NOT NULL,
    token_endpoint_auth_method text NOT NULL,
    CONSTRAINT oauth_clients_client_name_length CHECK ((char_length(client_name) <= 1024)),
    CONSTRAINT oauth_clients_client_uri_length CHECK ((char_length(client_uri) <= 2048)),
    CONSTRAINT oauth_clients_logo_uri_length CHECK ((char_length(logo_uri) <= 2048)),
    CONSTRAINT oauth_clients_token_endpoint_auth_method_check CHECK ((token_endpoint_auth_method = ANY (ARRAY['client_secret_basic'::text, 'client_secret_post'::text, 'none'::text])))
);


ALTER TABLE auth.oauth_clients OWNER TO supabase_auth_admin;

--
-- Name: oauth_consents; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TABLE auth.oauth_consents (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    client_id uuid NOT NULL,
    scopes text NOT NULL,
    granted_at timestamp with time zone DEFAULT now() NOT NULL,
    revoked_at timestamp with time zone,
    CONSTRAINT oauth_consents_revoked_after_granted CHECK (((revoked_at IS NULL) OR (revoked_at >= granted_at))),
    CONSTRAINT oauth_consents_scopes_length CHECK ((char_length(scopes) <= 2048)),
    CONSTRAINT oauth_consents_scopes_not_empty CHECK ((char_length(TRIM(BOTH FROM scopes)) > 0))
);


ALTER TABLE auth.oauth_consents OWNER TO supabase_auth_admin;

--
-- Name: one_time_tokens; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TABLE auth.one_time_tokens (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    token_type auth.one_time_token_type NOT NULL,
    token_hash text NOT NULL,
    relates_to text NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    CONSTRAINT one_time_tokens_token_hash_check CHECK ((char_length(token_hash) > 0))
);


ALTER TABLE auth.one_time_tokens OWNER TO supabase_auth_admin;

--
-- Name: refresh_tokens; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TABLE auth.refresh_tokens (
    instance_id uuid,
    id bigint NOT NULL,
    token character varying(255),
    user_id character varying(255),
    revoked boolean,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    parent character varying(255),
    session_id uuid
);


ALTER TABLE auth.refresh_tokens OWNER TO supabase_auth_admin;

--
-- Name: TABLE refresh_tokens; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON TABLE auth.refresh_tokens IS 'Auth: Store of tokens used to refresh JWT tokens once they expire.';


--
-- Name: refresh_tokens_id_seq; Type: SEQUENCE; Schema: auth; Owner: supabase_auth_admin
--

CREATE SEQUENCE auth.refresh_tokens_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE auth.refresh_tokens_id_seq OWNER TO supabase_auth_admin;

--
-- Name: refresh_tokens_id_seq; Type: SEQUENCE OWNED BY; Schema: auth; Owner: supabase_auth_admin
--

ALTER SEQUENCE auth.refresh_tokens_id_seq OWNED BY auth.refresh_tokens.id;


--
-- Name: saml_providers; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TABLE auth.saml_providers (
    id uuid NOT NULL,
    sso_provider_id uuid NOT NULL,
    entity_id text NOT NULL,
    metadata_xml text NOT NULL,
    metadata_url text,
    attribute_mapping jsonb,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    name_id_format text,
    CONSTRAINT "entity_id not empty" CHECK ((char_length(entity_id) > 0)),
    CONSTRAINT "metadata_url not empty" CHECK (((metadata_url = NULL::text) OR (char_length(metadata_url) > 0))),
    CONSTRAINT "metadata_xml not empty" CHECK ((char_length(metadata_xml) > 0))
);


ALTER TABLE auth.saml_providers OWNER TO supabase_auth_admin;

--
-- Name: TABLE saml_providers; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON TABLE auth.saml_providers IS 'Auth: Manages SAML Identity Provider connections.';


--
-- Name: saml_relay_states; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TABLE auth.saml_relay_states (
    id uuid NOT NULL,
    sso_provider_id uuid NOT NULL,
    request_id text NOT NULL,
    for_email text,
    redirect_to text,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    flow_state_id uuid,
    CONSTRAINT "request_id not empty" CHECK ((char_length(request_id) > 0))
);


ALTER TABLE auth.saml_relay_states OWNER TO supabase_auth_admin;

--
-- Name: TABLE saml_relay_states; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON TABLE auth.saml_relay_states IS 'Auth: Contains SAML Relay State information for each Service Provider initiated login.';


--
-- Name: schema_migrations; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TABLE auth.schema_migrations (
    version character varying(255) NOT NULL
);


ALTER TABLE auth.schema_migrations OWNER TO supabase_auth_admin;

--
-- Name: TABLE schema_migrations; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON TABLE auth.schema_migrations IS 'Auth: Manages updates to the auth system.';


--
-- Name: sessions; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TABLE auth.sessions (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    factor_id uuid,
    aal auth.aal_level,
    not_after timestamp with time zone,
    refreshed_at timestamp without time zone,
    user_agent text,
    ip inet,
    tag text,
    oauth_client_id uuid,
    refresh_token_hmac_key text,
    refresh_token_counter bigint,
    scopes text,
    CONSTRAINT sessions_scopes_length CHECK ((char_length(scopes) <= 4096))
);


ALTER TABLE auth.sessions OWNER TO supabase_auth_admin;

--
-- Name: TABLE sessions; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON TABLE auth.sessions IS 'Auth: Stores session data associated to a user.';


--
-- Name: COLUMN sessions.not_after; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON COLUMN auth.sessions.not_after IS 'Auth: Not after is a nullable column that contains a timestamp after which the session should be regarded as expired.';


--
-- Name: COLUMN sessions.refresh_token_hmac_key; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON COLUMN auth.sessions.refresh_token_hmac_key IS 'Holds a HMAC-SHA256 key used to sign refresh tokens for this session.';


--
-- Name: COLUMN sessions.refresh_token_counter; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON COLUMN auth.sessions.refresh_token_counter IS 'Holds the ID (counter) of the last issued refresh token.';


--
-- Name: sso_domains; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TABLE auth.sso_domains (
    id uuid NOT NULL,
    sso_provider_id uuid NOT NULL,
    domain text NOT NULL,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    CONSTRAINT "domain not empty" CHECK ((char_length(domain) > 0))
);


ALTER TABLE auth.sso_domains OWNER TO supabase_auth_admin;

--
-- Name: TABLE sso_domains; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON TABLE auth.sso_domains IS 'Auth: Manages SSO email address domain mapping to an SSO Identity Provider.';


--
-- Name: sso_providers; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TABLE auth.sso_providers (
    id uuid NOT NULL,
    resource_id text,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    disabled boolean,
    CONSTRAINT "resource_id not empty" CHECK (((resource_id = NULL::text) OR (char_length(resource_id) > 0)))
);


ALTER TABLE auth.sso_providers OWNER TO supabase_auth_admin;

--
-- Name: TABLE sso_providers; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON TABLE auth.sso_providers IS 'Auth: Manages SSO identity provider information; see saml_providers for SAML.';


--
-- Name: COLUMN sso_providers.resource_id; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON COLUMN auth.sso_providers.resource_id IS 'Auth: Uniquely identifies a SSO provider according to a user-chosen resource ID (case insensitive), useful in infrastructure as code.';


--
-- Name: users; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TABLE auth.users (
    instance_id uuid,
    id uuid NOT NULL,
    aud character varying(255),
    role character varying(255),
    email character varying(255),
    encrypted_password character varying(255),
    email_confirmed_at timestamp with time zone,
    invited_at timestamp with time zone,
    confirmation_token character varying(255),
    confirmation_sent_at timestamp with time zone,
    recovery_token character varying(255),
    recovery_sent_at timestamp with time zone,
    email_change_token_new character varying(255),
    email_change character varying(255),
    email_change_sent_at timestamp with time zone,
    last_sign_in_at timestamp with time zone,
    raw_app_meta_data jsonb,
    raw_user_meta_data jsonb,
    is_super_admin boolean,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    phone text DEFAULT NULL::character varying,
    phone_confirmed_at timestamp with time zone,
    phone_change text DEFAULT ''::character varying,
    phone_change_token character varying(255) DEFAULT ''::character varying,
    phone_change_sent_at timestamp with time zone,
    confirmed_at timestamp with time zone GENERATED ALWAYS AS (LEAST(email_confirmed_at, phone_confirmed_at)) STORED,
    email_change_token_current character varying(255) DEFAULT ''::character varying,
    email_change_confirm_status smallint DEFAULT 0,
    banned_until timestamp with time zone,
    reauthentication_token character varying(255) DEFAULT ''::character varying,
    reauthentication_sent_at timestamp with time zone,
    is_sso_user boolean DEFAULT false NOT NULL,
    deleted_at timestamp with time zone,
    is_anonymous boolean DEFAULT false NOT NULL,
    CONSTRAINT users_email_change_confirm_status_check CHECK (((email_change_confirm_status >= 0) AND (email_change_confirm_status <= 2)))
);


ALTER TABLE auth.users OWNER TO supabase_auth_admin;

--
-- Name: TABLE users; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON TABLE auth.users IS 'Auth: Stores user login data within a secure schema.';


--
-- Name: COLUMN users.is_sso_user; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON COLUMN auth.users.is_sso_user IS 'Auth: Set this column to true when the account comes from SSO. These accounts can have duplicate emails.';


--
-- Name: webauthn_challenges; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TABLE auth.webauthn_challenges (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid,
    challenge_type text NOT NULL,
    session_data jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    CONSTRAINT webauthn_challenges_challenge_type_check CHECK ((challenge_type = ANY (ARRAY['signup'::text, 'registration'::text, 'authentication'::text])))
);


ALTER TABLE auth.webauthn_challenges OWNER TO supabase_auth_admin;

--
-- Name: webauthn_credentials; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TABLE auth.webauthn_credentials (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    credential_id bytea NOT NULL,
    public_key bytea NOT NULL,
    attestation_type text DEFAULT ''::text NOT NULL,
    aaguid uuid,
    sign_count bigint DEFAULT 0 NOT NULL,
    transports jsonb DEFAULT '[]'::jsonb NOT NULL,
    backup_eligible boolean DEFAULT false NOT NULL,
    backed_up boolean DEFAULT false NOT NULL,
    friendly_name text DEFAULT ''::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    last_used_at timestamp with time zone
);


ALTER TABLE auth.webauthn_credentials OWNER TO supabase_auth_admin;

--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


ALTER TABLE public.alembic_version OWNER TO postgres;

--
-- Name: api_keys; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.api_keys (
    id integer NOT NULL,
    emisor_id integer NOT NULL,
    nombre character varying(100) NOT NULL,
    key_prefix character varying(10) NOT NULL,
    key_hash character varying(64) NOT NULL,
    revoked boolean DEFAULT false NOT NULL,
    expires_at timestamp with time zone,
    last_used_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now(),
    tipo character varying(20) DEFAULT 'external'::character varying,
    unlimited boolean DEFAULT false
);


ALTER TABLE public.api_keys OWNER TO postgres;

--
-- Name: api_keys_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.api_keys_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.api_keys_id_seq OWNER TO postgres;

--
-- Name: api_keys_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.api_keys_id_seq OWNED BY public.api_keys.id;


--
-- Name: app_ads; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.app_ads (
    id integer NOT NULL,
    titulo text NOT NULL,
    descripcion text,
    imagen_url text,
    cta_url text NOT NULL,
    hex_color character varying(9) DEFAULT '#4F46E5'::character varying,
    activo boolean DEFAULT true,
    views_count integer DEFAULT 0,
    clicks_count integer DEFAULT 0,
    created_at timestamp with time zone DEFAULT now(),
    producto character varying(50) DEFAULT 'kipu'::character varying
);


ALTER TABLE public.app_ads OWNER TO postgres;

--
-- Name: app_ads_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.app_ads_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.app_ads_id_seq OWNER TO postgres;

--
-- Name: app_ads_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.app_ads_id_seq OWNED BY public.app_ads.id;


--
-- Name: auth_challenges; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.auth_challenges (
    id integer NOT NULL,
    emisor_id integer,
    email text NOT NULL,
    whatsapp_number character varying(20),
    pin character varying(10) NOT NULL,
    tipo_accion character varying(30) NOT NULL,
    extra_data jsonb,
    expires_at timestamp with time zone NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.auth_challenges OWNER TO postgres;

--
-- Name: auth_challenges_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.auth_challenges_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.auth_challenges_id_seq OWNER TO postgres;

--
-- Name: auth_challenges_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.auth_challenges_id_seq OWNED BY public.auth_challenges.id;


--
-- Name: catalogo_items; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.catalogo_items (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    emisor_id integer NOT NULL,
    codigo character varying(50),
    descripcion text NOT NULL,
    precio numeric(12,2) NOT NULL,
    tipo_iva character varying(10),
    unidad character varying(20),
    activo boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    stock integer DEFAULT '-1'::integer
);


ALTER TABLE public.catalogo_items OWNER TO postgres;

--
-- Name: clientes_emisor; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.clientes_emisor (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    emisor_id integer NOT NULL,
    sujeto_global_id uuid,
    email character varying(150),
    telefono character varying(20),
    tipo_identificacion_sri character varying(2),
    identificacion character varying(20),
    razon_social text,
    direccion text,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.clientes_emisor OWNER TO postgres;

--
-- Name: credit_transactions; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.credit_transactions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    emisor_id integer NOT NULL,
    tipo character varying(25) NOT NULL,
    cantidad integer NOT NULL,
    precio_total numeric(10,2),
    metodo_pago character varying(30),
    referencia_pago character varying(100),
    notas text,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.credit_transactions OWNER TO postgres;

--
-- Name: declaraciones_sri; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.declaraciones_sri (
    id integer NOT NULL,
    emisor_id integer NOT NULL,
    tipo character varying(10) DEFAULT '104'::character varying NOT NULL,
    periodo date NOT NULL,
    declarado boolean DEFAULT false,
    fecha_declarado timestamp with time zone,
    declarado_por uuid,
    notas text,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.declaraciones_sri OWNER TO postgres;

--
-- Name: declaraciones_sri_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.declaraciones_sri_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.declaraciones_sri_id_seq OWNER TO postgres;

--
-- Name: declaraciones_sri_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.declaraciones_sri_id_seq OWNED BY public.declaraciones_sri.id;


--
-- Name: email_rate_limits; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.email_rate_limits (
    id integer NOT NULL,
    email character varying(255) NOT NULL,
    last_sent timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.email_rate_limits OWNER TO postgres;

--
-- Name: email_rate_limits_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.email_rate_limits_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.email_rate_limits_id_seq OWNER TO postgres;

--
-- Name: email_rate_limits_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.email_rate_limits_id_seq OWNED BY public.email_rate_limits.id;


--
-- Name: emisor_usuarios; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.emisor_usuarios (
    id integer NOT NULL,
    emisor_id integer NOT NULL,
    profile_id uuid NOT NULL,
    rol character varying(20),
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.emisor_usuarios OWNER TO postgres;

--
-- Name: emisor_usuarios_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.emisor_usuarios_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.emisor_usuarios_id_seq OWNER TO postgres;

--
-- Name: emisor_usuarios_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.emisor_usuarios_id_seq OWNED BY public.emisor_usuarios.id;


--
-- Name: emisores; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.emisores (
    id integer NOT NULL,
    ruc character varying(13) NOT NULL,
    razon_social text NOT NULL,
    nombre_comercial text,
    direccion_matriz text NOT NULL,
    contribuyente_especial character varying(13),
    obligado_contabilidad character varying(2),
    ambiente smallint,
    p12_path text,
    p12_pass text,
    p12_expiration date,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    ws_establecimiento character varying(3),
    ws_punto_emision character varying(3),
    stripe_customer_id character varying(50)
);


ALTER TABLE public.emisores OWNER TO postgres;

--
-- Name: emisores_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.emisores_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.emisores_id_seq OWNER TO postgres;

--
-- Name: emisores_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.emisores_id_seq OWNED BY public.emisores.id;


--
-- Name: establecimientos; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.establecimientos (
    id integer NOT NULL,
    emisor_id integer NOT NULL,
    codigo character varying(3) NOT NULL,
    nombre_comercial text,
    direccion text NOT NULL,
    is_active boolean
);


ALTER TABLE public.establecimientos OWNER TO postgres;

--
-- Name: establecimientos_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.establecimientos_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.establecimientos_id_seq OWNER TO postgres;

--
-- Name: establecimientos_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.establecimientos_id_seq OWNED BY public.establecimientos.id;


--
-- Name: fcm_tokens; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.fcm_tokens (
    id integer NOT NULL,
    profile_id uuid NOT NULL,
    emisor_id integer,
    token text NOT NULL,
    updated_at timestamp with time zone DEFAULT now(),
    created_at timestamp with time zone DEFAULT now(),
    device_id text DEFAULT 'default'::text NOT NULL
);


ALTER TABLE public.fcm_tokens OWNER TO postgres;

--
-- Name: fcm_tokens_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.fcm_tokens_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.fcm_tokens_id_seq OWNER TO postgres;

--
-- Name: fcm_tokens_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.fcm_tokens_id_seq OWNED BY public.fcm_tokens.id;


--
-- Name: invoices_emitidas; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.invoices_emitidas (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    emisor_id integer NOT NULL,
    punto_emision_id integer NOT NULL,
    cliente_emisor_id uuid,
    clave_acceso character varying(49),
    secuencial character varying(9) NOT NULL,
    numero_factura character varying(17),
    fecha_emision date DEFAULT CURRENT_DATE,
    estado character varying(20),
    identificacion_comprador character varying(20) NOT NULL,
    razon_social_comprador text NOT NULL,
    email_comprador character varying(150),
    importe_total numeric(12,2) NOT NULL,
    subtotal_iva numeric(12,2),
    subtotal_0 numeric(12,2),
    valor_iva numeric(12,2),
    datos_factura jsonb NOT NULL,
    xml_path text,
    pdf_path text,
    mensajes_sri jsonb,
    fecha_envio_sri timestamp with time zone,
    fecha_autorizacion timestamp with time zone,
    retry_count integer,
    last_retry timestamp with time zone,
    created_at timestamp with time zone DEFAULT now(),
    api_key_id integer,
    origen character varying(20) DEFAULT 'web'::character varying,
    cod_doc character varying(2) DEFAULT '01'::character varying,
    doc_referencia_id uuid
);


ALTER TABLE public.invoices_emitidas OWNER TO postgres;

--
-- Name: invoices_recibidas; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.invoices_recibidas (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    emisor_id integer NOT NULL,
    ruc_proveedor character varying(13) NOT NULL,
    razon_social_proveedor text NOT NULL,
    clave_acceso character varying(49),
    numero_factura character varying(17),
    fecha_emision date NOT NULL,
    subtotal_0 numeric(12,2),
    subtotal_iva numeric(12,2),
    valor_iva numeric(12,2),
    importe_total numeric(12,2) NOT NULL,
    categoria_gasto character varying(50),
    deducible_renta boolean,
    notas_cliente text,
    xml_path text,
    datos_factura jsonb,
    fuente character varying(10),
    procesado boolean,
    created_at timestamp with time zone DEFAULT now(),
    total_sin_impuestos numeric(12,2) DEFAULT 0,
    total_descuento numeric(12,2) DEFAULT 0,
    fecha_autorizacion timestamp with time zone,
    contribuyente_especial character varying(13),
    credito_tributario_iva boolean DEFAULT false,
    impuestos_detalle jsonb
);


ALTER TABLE public.invoices_recibidas OWNER TO postgres;

--
-- Name: leads_ex_usuarios; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.leads_ex_usuarios (
    id integer NOT NULL,
    ruc character varying(13),
    razon_social text,
    email text,
    full_name text,
    motivo_salida text,
    ultimo_balance_emision integer,
    ultimo_balance_recepcion integer,
    total_facturas_emitidas integer,
    total_facturas_recibidas integer,
    fecha_registro_original timestamp without time zone,
    fecha_eliminacion timestamp without time zone DEFAULT now(),
    whatsapp_number character varying(20)
);


ALTER TABLE public.leads_ex_usuarios OWNER TO postgres;

--
-- Name: leads_ex_usuarios_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.leads_ex_usuarios_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.leads_ex_usuarios_id_seq OWNER TO postgres;

--
-- Name: leads_ex_usuarios_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.leads_ex_usuarios_id_seq OWNED BY public.leads_ex_usuarios.id;


--
-- Name: notificaciones; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.notificaciones (
    id integer NOT NULL,
    emisor_id integer NOT NULL,
    tipo character varying(30) NOT NULL,
    titulo text NOT NULL,
    mensaje text NOT NULL,
    leida boolean DEFAULT false,
    created_at timestamp with time zone DEFAULT now(),
    referencia character varying(100) DEFAULT NULL::character varying
);


ALTER TABLE public.notificaciones OWNER TO postgres;

--
-- Name: notificaciones_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.notificaciones_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.notificaciones_id_seq OWNER TO postgres;

--
-- Name: notificaciones_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.notificaciones_id_seq OWNED BY public.notificaciones.id;


--
-- Name: planes_creditos; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.planes_creditos (
    id integer NOT NULL,
    nombre text NOT NULL,
    descripcion text,
    tipo character varying(20) NOT NULL,
    cantidad integer NOT NULL,
    precio numeric(10,2) NOT NULL,
    popular boolean DEFAULT false,
    activo boolean DEFAULT true,
    orden integer DEFAULT 0,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.planes_creditos OWNER TO postgres;

--
-- Name: planes_creditos_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.planes_creditos_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.planes_creditos_id_seq OWNER TO postgres;

--
-- Name: planes_creditos_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.planes_creditos_id_seq OWNED BY public.planes_creditos.id;


--
-- Name: profiles; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.profiles (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    firebase_uid text NOT NULL,
    emisor_id integer,
    email text NOT NULL,
    full_name text,
    role character varying(20),
    whatsapp_number character varying(20),
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.profiles OWNER TO postgres;

--
-- Name: puntos_emision; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.puntos_emision (
    id integer NOT NULL,
    establecimiento_id integer NOT NULL,
    emisor_id integer NOT NULL,
    codigo character varying(3) NOT NULL,
    secuencial_actual integer,
    nombre text,
    is_active boolean
);


ALTER TABLE public.puntos_emision OWNER TO postgres;

--
-- Name: puntos_emision_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.puntos_emision_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.puntos_emision_id_seq OWNER TO postgres;

--
-- Name: puntos_emision_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.puntos_emision_id_seq OWNED BY public.puntos_emision.id;


--
-- Name: servicios; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.servicios (
    id integer NOT NULL,
    nombre text NOT NULL,
    descripcion text,
    precio numeric(10,2) NOT NULL,
    moneda character varying(3) DEFAULT 'USD'::character varying,
    activo boolean DEFAULT true,
    orden integer DEFAULT 0,
    created_at timestamp with time zone DEFAULT now(),
    hex_color character varying(9) DEFAULT '#4F46E5'::character varying,
    imagen_url text
);


ALTER TABLE public.servicios OWNER TO postgres;

--
-- Name: servicios_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.servicios_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.servicios_id_seq OWNER TO postgres;

--
-- Name: servicios_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.servicios_id_seq OWNED BY public.servicios.id;


--
-- Name: sujetos_global; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.sujetos_global (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tipo_identificacion_sri character varying(2) NOT NULL,
    identificacion character varying(20) NOT NULL,
    codigo_pais character varying(3) NOT NULL,
    razon_social text NOT NULL,
    ultima_sincronizacion timestamp with time zone DEFAULT now()
);


ALTER TABLE public.sujetos_global OWNER TO postgres;

--
-- Name: transaction_logs; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.transaction_logs (
    id integer NOT NULL,
    target_emisor_id integer,
    amount integer NOT NULL,
    action_type character varying(50) NOT NULL,
    description text,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.transaction_logs OWNER TO postgres;

--
-- Name: transaction_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.transaction_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.transaction_logs_id_seq OWNER TO postgres;

--
-- Name: transaction_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.transaction_logs_id_seq OWNED BY public.transaction_logs.id;


--
-- Name: user_credits; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.user_credits (
    emisor_id integer NOT NULL,
    balance_emision integer NOT NULL,
    balance_recepcion integer NOT NULL,
    last_updated timestamp with time zone DEFAULT now()
);


ALTER TABLE public.user_credits OWNER TO postgres;

--
-- Name: webhooks; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.webhooks (
    id integer NOT NULL,
    emisor_id integer NOT NULL,
    api_key_id integer,
    url text NOT NULL,
    secret text,
    eventos jsonb,
    activo boolean,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.webhooks OWNER TO postgres;

--
-- Name: webhooks_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.webhooks_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.webhooks_id_seq OWNER TO postgres;

--
-- Name: webhooks_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.webhooks_id_seq OWNED BY public.webhooks.id;


--
-- Name: messages; Type: TABLE; Schema: realtime; Owner: supabase_realtime_admin
--

CREATE TABLE realtime.messages (
    topic text NOT NULL,
    extension text NOT NULL,
    payload jsonb,
    event text,
    private boolean DEFAULT false,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    inserted_at timestamp without time zone DEFAULT now() NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    binary_payload bytea
)
PARTITION BY RANGE (inserted_at);


ALTER TABLE realtime.messages OWNER TO supabase_realtime_admin;

--
-- Name: schema_migrations; Type: TABLE; Schema: realtime; Owner: supabase_admin
--

CREATE TABLE realtime.schema_migrations (
    version bigint NOT NULL,
    inserted_at timestamp(0) without time zone
);


ALTER TABLE realtime.schema_migrations OWNER TO supabase_admin;

--
-- Name: subscription; Type: TABLE; Schema: realtime; Owner: supabase_realtime_admin
--

CREATE TABLE realtime.subscription (
    id bigint NOT NULL,
    subscription_id uuid NOT NULL,
    entity regclass NOT NULL,
    filters realtime.user_defined_filter[] DEFAULT '{}'::realtime.user_defined_filter[] NOT NULL,
    claims jsonb NOT NULL,
    claims_role regrole GENERATED ALWAYS AS (realtime.to_regrole((claims ->> 'role'::text))) STORED NOT NULL,
    created_at timestamp without time zone DEFAULT timezone('utc'::text, now()) NOT NULL,
    action_filter text DEFAULT '*'::text,
    selected_columns text[],
    CONSTRAINT subscription_action_filter_check CHECK ((action_filter = ANY (ARRAY['*'::text, 'INSERT'::text, 'UPDATE'::text, 'DELETE'::text])))
);


ALTER TABLE realtime.subscription OWNER TO supabase_realtime_admin;

--
-- Name: subscription_id_seq; Type: SEQUENCE; Schema: realtime; Owner: supabase_realtime_admin
--

ALTER TABLE realtime.subscription ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME realtime.subscription_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: buckets; Type: TABLE; Schema: storage; Owner: supabase_storage_admin
--

CREATE TABLE storage.buckets (
    id text NOT NULL,
    name text NOT NULL,
    owner uuid,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    public boolean DEFAULT false,
    avif_autodetection boolean DEFAULT false,
    file_size_limit bigint,
    allowed_mime_types text[],
    owner_id text,
    type storage.buckettype DEFAULT 'STANDARD'::storage.buckettype NOT NULL
);


ALTER TABLE storage.buckets OWNER TO supabase_storage_admin;

--
-- Name: COLUMN buckets.owner; Type: COMMENT; Schema: storage; Owner: supabase_storage_admin
--

COMMENT ON COLUMN storage.buckets.owner IS 'Field is deprecated, use owner_id instead';


--
-- Name: buckets_analytics; Type: TABLE; Schema: storage; Owner: supabase_storage_admin
--

CREATE TABLE storage.buckets_analytics (
    name text NOT NULL,
    type storage.buckettype DEFAULT 'ANALYTICS'::storage.buckettype NOT NULL,
    format text DEFAULT 'ICEBERG'::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    deleted_at timestamp with time zone
);


ALTER TABLE storage.buckets_analytics OWNER TO supabase_storage_admin;

--
-- Name: buckets_vectors; Type: TABLE; Schema: storage; Owner: supabase_storage_admin
--

CREATE TABLE storage.buckets_vectors (
    id text NOT NULL,
    type storage.buckettype DEFAULT 'VECTOR'::storage.buckettype NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE storage.buckets_vectors OWNER TO supabase_storage_admin;

--
-- Name: migrations; Type: TABLE; Schema: storage; Owner: supabase_storage_admin
--

CREATE TABLE storage.migrations (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    hash character varying(40) NOT NULL,
    executed_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE storage.migrations OWNER TO supabase_storage_admin;

--
-- Name: objects; Type: TABLE; Schema: storage; Owner: supabase_storage_admin
--

CREATE TABLE storage.objects (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    bucket_id text,
    name text,
    owner uuid,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    last_accessed_at timestamp with time zone DEFAULT now(),
    metadata jsonb,
    path_tokens text[] GENERATED ALWAYS AS (string_to_array(name, '/'::text)) STORED,
    version text,
    owner_id text,
    user_metadata jsonb
);


ALTER TABLE storage.objects OWNER TO supabase_storage_admin;

--
-- Name: COLUMN objects.owner; Type: COMMENT; Schema: storage; Owner: supabase_storage_admin
--

COMMENT ON COLUMN storage.objects.owner IS 'Field is deprecated, use owner_id instead';


--
-- Name: s3_multipart_uploads; Type: TABLE; Schema: storage; Owner: supabase_storage_admin
--

CREATE TABLE storage.s3_multipart_uploads (
    id text NOT NULL,
    in_progress_size bigint DEFAULT 0 NOT NULL,
    upload_signature text NOT NULL,
    bucket_id text NOT NULL,
    key text NOT NULL COLLATE pg_catalog."C",
    version text NOT NULL,
    owner_id text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    user_metadata jsonb,
    metadata jsonb
);


ALTER TABLE storage.s3_multipart_uploads OWNER TO supabase_storage_admin;

--
-- Name: s3_multipart_uploads_parts; Type: TABLE; Schema: storage; Owner: supabase_storage_admin
--

CREATE TABLE storage.s3_multipart_uploads_parts (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    upload_id text NOT NULL,
    size bigint DEFAULT 0 NOT NULL,
    part_number integer NOT NULL,
    bucket_id text NOT NULL,
    key text NOT NULL COLLATE pg_catalog."C",
    etag text NOT NULL,
    owner_id text,
    version text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE storage.s3_multipart_uploads_parts OWNER TO supabase_storage_admin;

--
-- Name: vector_indexes; Type: TABLE; Schema: storage; Owner: supabase_storage_admin
--

CREATE TABLE storage.vector_indexes (
    id text DEFAULT gen_random_uuid() NOT NULL,
    name text NOT NULL COLLATE pg_catalog."C",
    bucket_id text NOT NULL,
    data_type text NOT NULL,
    dimension integer NOT NULL,
    distance_metric text NOT NULL,
    metadata_configuration jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE storage.vector_indexes OWNER TO supabase_storage_admin;

--
-- Name: refresh_tokens id; Type: DEFAULT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.refresh_tokens ALTER COLUMN id SET DEFAULT nextval('auth.refresh_tokens_id_seq'::regclass);


--
-- Name: api_keys id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.api_keys ALTER COLUMN id SET DEFAULT nextval('public.api_keys_id_seq'::regclass);


--
-- Name: app_ads id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.app_ads ALTER COLUMN id SET DEFAULT nextval('public.app_ads_id_seq'::regclass);


--
-- Name: auth_challenges id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.auth_challenges ALTER COLUMN id SET DEFAULT nextval('public.auth_challenges_id_seq'::regclass);


--
-- Name: declaraciones_sri id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.declaraciones_sri ALTER COLUMN id SET DEFAULT nextval('public.declaraciones_sri_id_seq'::regclass);


--
-- Name: email_rate_limits id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.email_rate_limits ALTER COLUMN id SET DEFAULT nextval('public.email_rate_limits_id_seq'::regclass);


--
-- Name: emisor_usuarios id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.emisor_usuarios ALTER COLUMN id SET DEFAULT nextval('public.emisor_usuarios_id_seq'::regclass);


--
-- Name: emisores id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.emisores ALTER COLUMN id SET DEFAULT nextval('public.emisores_id_seq'::regclass);


--
-- Name: establecimientos id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.establecimientos ALTER COLUMN id SET DEFAULT nextval('public.establecimientos_id_seq'::regclass);


--
-- Name: fcm_tokens id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.fcm_tokens ALTER COLUMN id SET DEFAULT nextval('public.fcm_tokens_id_seq'::regclass);


--
-- Name: leads_ex_usuarios id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.leads_ex_usuarios ALTER COLUMN id SET DEFAULT nextval('public.leads_ex_usuarios_id_seq'::regclass);


--
-- Name: notificaciones id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.notificaciones ALTER COLUMN id SET DEFAULT nextval('public.notificaciones_id_seq'::regclass);


--
-- Name: planes_creditos id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.planes_creditos ALTER COLUMN id SET DEFAULT nextval('public.planes_creditos_id_seq'::regclass);


--
-- Name: puntos_emision id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.puntos_emision ALTER COLUMN id SET DEFAULT nextval('public.puntos_emision_id_seq'::regclass);


--
-- Name: servicios id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.servicios ALTER COLUMN id SET DEFAULT nextval('public.servicios_id_seq'::regclass);


--
-- Name: transaction_logs id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.transaction_logs ALTER COLUMN id SET DEFAULT nextval('public.transaction_logs_id_seq'::regclass);


--
-- Name: webhooks id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.webhooks ALTER COLUMN id SET DEFAULT nextval('public.webhooks_id_seq'::regclass);


--
-- Data for Name: audit_log_entries; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--

COPY auth.audit_log_entries (instance_id, id, payload, created_at, ip_address) FROM stdin;
\.


--
-- Data for Name: custom_oauth_providers; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--

COPY auth.custom_oauth_providers (id, provider_type, identifier, name, client_id, client_secret, acceptable_client_ids, scopes, pkce_enabled, attribute_mapping, authorization_params, enabled, email_optional, issuer, discovery_url, skip_nonce_check, cached_discovery, discovery_cached_at, authorization_url, token_url, userinfo_url, jwks_uri, created_at, updated_at, custom_claims_allowlist) FROM stdin;
\.


--
-- Data for Name: flow_state; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--

COPY auth.flow_state (id, user_id, auth_code, code_challenge_method, code_challenge, provider_type, provider_access_token, provider_refresh_token, created_at, updated_at, authentication_method, auth_code_issued_at, invite_token, referrer, oauth_client_state_id, linking_target_id, email_optional) FROM stdin;
\.


--
-- Data for Name: identities; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--

COPY auth.identities (provider_id, user_id, identity_data, provider, last_sign_in_at, created_at, updated_at, id) FROM stdin;
\.


--
-- Data for Name: instances; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--

COPY auth.instances (id, uuid, raw_base_config, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: mfa_amr_claims; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--

COPY auth.mfa_amr_claims (session_id, created_at, updated_at, authentication_method, id) FROM stdin;
\.


--
-- Data for Name: mfa_challenges; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--

COPY auth.mfa_challenges (id, factor_id, created_at, verified_at, ip_address, otp_code, web_authn_session_data) FROM stdin;
\.


--
-- Data for Name: mfa_factors; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--

COPY auth.mfa_factors (id, user_id, friendly_name, factor_type, status, created_at, updated_at, secret, phone, last_challenged_at, web_authn_credential, web_authn_aaguid, last_webauthn_challenge_data) FROM stdin;
\.


--
-- Data for Name: oauth_authorizations; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--

COPY auth.oauth_authorizations (id, authorization_id, client_id, user_id, redirect_uri, scope, state, resource, code_challenge, code_challenge_method, response_type, status, authorization_code, created_at, expires_at, approved_at, nonce) FROM stdin;
\.


--
-- Data for Name: oauth_client_states; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--

COPY auth.oauth_client_states (id, provider_type, code_verifier, created_at) FROM stdin;
\.


--
-- Data for Name: oauth_clients; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--

COPY auth.oauth_clients (id, client_secret_hash, registration_type, redirect_uris, grant_types, client_name, client_uri, logo_uri, created_at, updated_at, deleted_at, client_type, token_endpoint_auth_method) FROM stdin;
\.


--
-- Data for Name: oauth_consents; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--

COPY auth.oauth_consents (id, user_id, client_id, scopes, granted_at, revoked_at) FROM stdin;
\.


--
-- Data for Name: one_time_tokens; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--

COPY auth.one_time_tokens (id, user_id, token_type, token_hash, relates_to, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: refresh_tokens; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--

COPY auth.refresh_tokens (instance_id, id, token, user_id, revoked, created_at, updated_at, parent, session_id) FROM stdin;
\.


--
-- Data for Name: saml_providers; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--

COPY auth.saml_providers (id, sso_provider_id, entity_id, metadata_xml, metadata_url, attribute_mapping, created_at, updated_at, name_id_format) FROM stdin;
\.


--
-- Data for Name: saml_relay_states; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--

COPY auth.saml_relay_states (id, sso_provider_id, request_id, for_email, redirect_to, created_at, updated_at, flow_state_id) FROM stdin;
\.


--
-- Data for Name: schema_migrations; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--

COPY auth.schema_migrations (version) FROM stdin;
20171026211738
20171026211808
20171026211834
20180103212743
20180108183307
20180119214651
20180125194653
00
20210710035447
20210722035447
20210730183235
20210909172000
20210927181326
20211122151130
20211124214934
20211202183645
20220114185221
20220114185340
20220224000811
20220323170000
20220429102000
20220531120530
20220614074223
20220811173540
20221003041349
20221003041400
20221011041400
20221020193600
20221021073300
20221021082433
20221027105023
20221114143122
20221114143410
20221125140132
20221208132122
20221215195500
20221215195800
20221215195900
20230116124310
20230116124412
20230131181311
20230322519590
20230402418590
20230411005111
20230508135423
20230523124323
20230818113222
20230914180801
20231027141322
20231114161723
20231117164230
20240115144230
20240214120130
20240306115329
20240314092811
20240427152123
20240612123726
20240729123726
20240802193726
20240806073726
20241009103726
20250717082212
20250731150234
20250804100000
20250901200500
20250903112500
20250904133000
20250925093508
20251007112900
20251104100000
20251111201300
20251201000000
20260115000000
20260121000000
20260219120000
20260302000000
20260625000000
\.


--
-- Data for Name: sessions; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--

COPY auth.sessions (id, user_id, created_at, updated_at, factor_id, aal, not_after, refreshed_at, user_agent, ip, tag, oauth_client_id, refresh_token_hmac_key, refresh_token_counter, scopes) FROM stdin;
\.


--
-- Data for Name: sso_domains; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--

COPY auth.sso_domains (id, sso_provider_id, domain, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: sso_providers; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--

COPY auth.sso_providers (id, resource_id, created_at, updated_at, disabled) FROM stdin;
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--

COPY auth.users (instance_id, id, aud, role, email, encrypted_password, email_confirmed_at, invited_at, confirmation_token, confirmation_sent_at, recovery_token, recovery_sent_at, email_change_token_new, email_change, email_change_sent_at, last_sign_in_at, raw_app_meta_data, raw_user_meta_data, is_super_admin, created_at, updated_at, phone, phone_confirmed_at, phone_change, phone_change_token, phone_change_sent_at, email_change_token_current, email_change_confirm_status, banned_until, reauthentication_token, reauthentication_sent_at, is_sso_user, deleted_at, is_anonymous) FROM stdin;
\.


--
-- Data for Name: webauthn_challenges; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--

COPY auth.webauthn_challenges (id, user_id, challenge_type, session_data, created_at, expires_at) FROM stdin;
\.


--
-- Data for Name: webauthn_credentials; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--

COPY auth.webauthn_credentials (id, user_id, credential_id, public_key, attestation_type, aaguid, sign_count, transports, backup_eligible, backed_up, friendly_name, created_at, updated_at, last_used_at) FROM stdin;
\.


--
-- Data for Name: alembic_version; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.alembic_version (version_num) FROM stdin;
\.


--
-- Data for Name: api_keys; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.api_keys (id, emisor_id, nombre, key_prefix, key_hash, revoked, expires_at, last_used_at, created_at, tipo, unlimited) FROM stdin;
7	20	Wappti	kp_live_	b9d3ef0c982cf09e15ad47e4f013960ac2c868568d4b5f53045a4f33a9a3a8cb	t	\N	\N	2026-08-02 19:34:16.380928+00	external	f
8	20	N8N	kp_live_	9ed5816ebf0bc48ca61567cf6e9f48bed6031e0bebf132920729415746a80c43	f	\N	2026-08-10 18:19:56.943571+00	2026-08-10 13:21:55.628011+00	external	f
9	20	WAPPTI	kp_live_	8c42acf08123094e66c816261145a69ed3d009257f83db319c69bc2815f7b643	f	\N	2026-08-14 22:14:44.238072+00	2026-08-14 22:14:00.244829+00	external	f
\.


--
-- Data for Name: app_ads; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.app_ads (id, titulo, descripcion, imagen_url, cta_url, hex_color, activo, views_count, clicks_count, created_at, producto) FROM stdin;
1	Factura desde WhatsApp	Rápido, fácil y autorizado por el SRI.	https://concepto.de/wp-content/uploads/2020/06/Computadora-de-escritorio-scaled-e1724955496406.jpg	https://kipu.ec	#CC001356	t	15	2	2026-05-17 20:00:56.199824+00	kipu
12	Cero cancelaciones	Wappti recuerda tus citas por WhatsApp.	https://concepto.de/wp-content/uploads/2020/06/Computadora-de-escritorio-scaled-e1724955496406.jpg	https://wappti.com	#CC001356	t	4	0	2026-05-19 01:57:33.448029+00	wappti
16	Preséntate en internet	Crea tu sitio web hoy con Vínculo.	https://concepto.de/wp-content/uploads/2020/06/Computadora-de-escritorio-scaled-e1724955496406.jpg	https://vinculo.cc	#CC001356	t	4	0	2026-05-19 01:57:33.448029+00	vinculo
13	Agenda automática	Recordatorios por WhatsApp sin esfuerzo.	https://concepto.de/wp-content/uploads/2020/06/Computadora-de-escritorio-scaled-e1724955496406.jpg	https://wappti.com	#CC001356	t	4	0	2026-05-19 01:57:33.448029+00	wappti
14	Tus clientes nunca olvidan	Automatiza recordatorios con Wappti.	https://concepto.de/wp-content/uploads/2020/06/Computadora-de-escritorio-scaled-e1724955496406.jpg	https://wappti.com	#CC001356	t	4	0	2026-05-19 01:57:33.448029+00	wappti
15	Tu web en minutos	Sin código. Sin técnicos. Solo tú y Vínculo.	https://concepto.de/wp-content/uploads/2020/06/Computadora-de-escritorio-scaled-e1724955496406.jpg	https://vinculo.cc	#CC001356	t	4	1	2026-05-19 01:57:33.448029+00	vinculo
17	¿Sin página web aún?	Vínculo lo resuelve en minutos.	https://concepto.de/wp-content/uploads/2020/06/Computadora-de-escritorio-scaled-e1724955496406.jpg	https://vinculo.cc	#CC001356	t	4	0	2026-05-19 01:57:33.448029+00	vinculo
10	Sin SRI, sin estrés	Kipu factura por ti en segundos.	https://concepto.de/wp-content/uploads/2020/06/Computadora-de-escritorio-scaled-e1724955496406.jpg	https://kipu.ec	#CC001356	t	5	1	2026-05-19 01:57:33.448029+00	kipu
11	Tu facturero en el bolsillo	Emite desde el celular, cuando quieras.	https://concepto.de/wp-content/uploads/2020/06/Computadora-de-escritorio-scaled-e1724955496406.jpg	https://kipu.ec	#CC001356	t	5	0	2026-05-19 01:57:33.448029+00	kipu
\.


--
-- Data for Name: auth_challenges; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.auth_challenges (id, emisor_id, email, whatsapp_number, pin, tipo_accion, extra_data, expires_at, created_at) FROM stdin;
24	20	cristhianromero19@outlook.com	\N	688164	CREAR_TOKEN	{}	2026-08-02 18:19:22.795291+00	2026-08-02 18:09:22.795291+00
25	20	cristhianromero19@outlook.com	\N	472909	CREAR_TOKEN	{}	2026-08-02 18:32:16.347435+00	2026-08-02 18:22:16.347435+00
26	20	cristhianromero19@outlook.com	\N	577882	CREAR_TOKEN	{}	2026-08-02 18:45:24.751534+00	2026-08-02 18:35:24.751534+00
27	20	cristhianromero19@outlook.com	\N	402525	CREAR_TOKEN	{}	2026-08-02 18:58:20.204057+00	2026-08-02 18:48:20.204057+00
\.


--
-- Data for Name: catalogo_items; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.catalogo_items (id, emisor_id, codigo, descripcion, precio, tipo_iva, unidad, activo, created_at, updated_at, stock) FROM stdin;
0151a502-2d43-41d3-ba34-9f2b8b537c77	20	1	www	2.00	15	UNIDAD	t	2026-08-04 20:34:17.381753+00	2026-08-11 20:04:32.869808+00	12
\.


--
-- Data for Name: clientes_emisor; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.clientes_emisor (id, emisor_id, sujeto_global_id, email, telefono, tipo_identificacion_sri, identificacion, razon_social, direccion, created_at) FROM stdin;
ac248cd7-7339-4992-b691-9c31aca4d551	20	d30d46ad-e396-4767-99b1-77758bdfce17	cristhianromero19@outlook.com	0960167213	05	1312838392	CRISTHIAN ROMERO	PORTOVIEJO	2026-08-02 20:42:35.512058+00
c0630cff-8a2e-454c-ba23-a5684d2e273c	20	5dab43aa-9767-4995-b022-ffa97ca7ae67	cristhianromero19@outlook.com		04	1312838392001	ROMERO GARCIA CRISTHIAN ANDRES	S/N	2026-08-10 05:47:13.112695+00
\.


--
-- Data for Name: credit_transactions; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.credit_transactions (id, emisor_id, tipo, cantidad, precio_total, metodo_pago, referencia_pago, notas, created_at) FROM stdin;
d6be78c2-73e7-4c97-98b7-98d6a6fd0976	20	BONO	10	0.00	SISTEMA	\N	REGALO POR APERTURA DE CUENTA	2026-08-01 22:25:04.801712+00
d602874d-a11f-42b1-afd8-63eb367b8479	20	BONO	25	0.00	SISTEMA	\N	BONO DE BIENVENIDA A PRODUCCIÓN — CRÉDITOS DE EMISIÓN	2026-08-02 16:36:05.281443+00
c0a18dd9-0147-40a0-8ff9-a42c2ff98906	20	RECARGA	50	8.03	STRIPE	\N	Stripe payment_intent=pi_3U2lGgGn1ILBomfh0Cdry2Ym plan_id=1	2026-08-10 05:56:51.148159+00
\.


--
-- Data for Name: declaraciones_sri; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.declaraciones_sri (id, emisor_id, tipo, periodo, declarado, fecha_declarado, declarado_por, notas, created_at) FROM stdin;
\.


--
-- Data for Name: email_rate_limits; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.email_rate_limits (id, email, last_sent) FROM stdin;
19	cristhianromero19@outlook.com	2026-08-14 22:13:44.340812+00
\.


--
-- Data for Name: emisor_usuarios; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.emisor_usuarios (id, emisor_id, profile_id, rol, created_at) FROM stdin;
1	20	97fcd876-5998-453f-8e54-bd51dcc94a2a	admin	2026-08-01 22:25:04.801712+00
\.


--
-- Data for Name: emisores; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.emisores (id, ruc, razon_social, nombre_comercial, direccion_matriz, contribuyente_especial, obligado_contabilidad, ambiente, p12_path, p12_pass, p12_expiration, created_at, updated_at, ws_establecimiento, ws_punto_emision, stripe_customer_id) FROM stdin;
20	1312838392001	ROMERO GARCIA CRISTHIAN ANDRES	\N	PORTOVIEJO		NO	1	1312838392001/firmas/firma_1312838392001_1785629113.p12	4128c162a122fcc1926e6fb50afcdb8e:e9b03629436b156798eda4b3db72d19c	2028-01-05	2026-08-01 22:25:04.801712+00	2026-08-02 16:36:05.281443+00	\N	\N	cus_Uzn209ez5rzYgV
\.


--
-- Data for Name: establecimientos; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.establecimientos (id, emisor_id, codigo, nombre_comercial, direccion, is_active) FROM stdin;
8	20	001	\N	PORTOVIEJO	t
\.


--
-- Data for Name: fcm_tokens; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.fcm_tokens (id, profile_id, emisor_id, token, updated_at, created_at, device_id) FROM stdin;
13	97fcd876-5998-453f-8e54-bd51dcc94a2a	20	eFizG4vl9FK5zlhi_imbTi:APA91bHlx8ftZ7XmhwSiiZQtEfbKT4imLVTnM7T0C3KixECN9zuTDQyotl-ok2VRCSQxPBRufo1vXApnWKIeXNvglksQthLLYSY7s4GjHmeKDReSmaMJB6E	2026-08-10 05:56:22.708183+00	2026-08-10 05:56:22.708183+00	f8bf7a88-5a9b-4448-a923-93c60a3e63d6
16	97fcd876-5998-453f-8e54-bd51dcc94a2a	20	c3PxnsAKZ1QZ5GrTzZNqYr:APA91bEG9X-T3EkVA-iKrjm6rOvESDNdlBtDh7rKui0CpbLOAqsdeRORBMsO0wMHoCKeJ2Z8IX_FqecP0UKWE3m9ddC1Zv9CTMLR88A7yOo8J7zypr8zzAw	2026-08-10 15:20:15.800384+00	2026-08-10 15:20:15.800384+00	b197d428-9c77-4195-827c-e4a7f46680e2
17	97fcd876-5998-453f-8e54-bd51dcc94a2a	20	fw2pvD_JzDsFOx-_C53c43:APA91bFjVHzo-en7BPpGtdGwxElcXjbW9whZS5_AlwqcD6PkkpYXvdgx9kCmrL5s_ejKsKwFyDS2hvho4-yRpLm7DfUMWH3EX3HtLVnFMv4-V1FK2O7mdvc	2026-08-10 15:29:22.60694+00	2026-08-10 15:29:22.60694+00	36b384b0-95bc-4541-a60f-b1b1a1242590
9	97fcd876-5998-453f-8e54-bd51dcc94a2a	20	f8mLK1Ij_-M8AgopQ6GyVU:APA91bGY5OyK6E65IjW-0dQDoYP_5T-7YvW3DNQ3kUzRUKG13EA9aYfOYPfya46YktTRLBA00UQE90c2hszvwl7FDKXm9HeNal3HZEoH0O2h8gte-yIPQE8	2026-08-12 15:19:59.850224+00	2026-08-10 05:46:19.012975+00	abd9b296-4010-4e9e-ab6b-eb8f1f51ed29
8	97fcd876-5998-453f-8e54-bd51dcc94a2a	20	coGoClJphEnDLkDMm6COLv:APA91bHVtaBOWSMluKhzOHq44LZjy_JemwawVfh9J-oe3CKbfJaReSnwAFwbtYQ4a7WXkxIF5q85URi4YyqhLL3ZTeaIrb-xLyLB-yiwl-CgHYGmaz5IK_A	2026-08-14 22:12:06.849194+00	2026-08-10 05:45:31.786623+00	3f510be2-62c8-42ac-8e80-18ba327f1ab4
\.


--
-- Data for Name: invoices_emitidas; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.invoices_emitidas (id, emisor_id, punto_emision_id, cliente_emisor_id, clave_acceso, secuencial, numero_factura, fecha_emision, estado, identificacion_comprador, razon_social_comprador, email_comprador, importe_total, subtotal_iva, subtotal_0, valor_iva, datos_factura, xml_path, pdf_path, mensajes_sri, fecha_envio_sri, fecha_autorizacion, retry_count, last_retry, created_at, api_key_id, origen, cod_doc, doc_referencia_id) FROM stdin;
fe2d32c6-e13c-42a1-ae78-c3447b33023f	20	16	\N	0308202601131283839200110010010000000183104191817	000000018	001-001-000000018	2026-08-03	AUTORIZADO	9999999999999	CONSUMIDOR FINAL	\N	1.86	1.61	0.00	0.25	{"@id": "comprobante", "@version": "1.1.0", "detalles": {"detalle": [{"cantidad": "1.000000", "descuento": "0.00", "impuestos": {"impuesto": {"valor": "0.02", "codigo": "2", "tarifa": "15", "baseImponible": "0.10", "codigoPorcentaje": "4"}}, "descripcion": "AAA", "precioUnitario": "0.100000", "codigoPrincipal": "S/C", "precioTotalSinImpuesto": "0.10"}, {"cantidad": "1.000000", "descuento": "0.75", "impuestos": {"impuesto": {"valor": "0.04", "codigo": "2", "tarifa": "15", "baseImponible": "0.25", "codigoPorcentaje": "4"}}, "descripcion": "BBB", "precioUnitario": "1.000000", "codigoPrincipal": "S/C", "precioTotalSinImpuesto": "0.25"}, {"cantidad": "1.000000", "descuento": "0.24", "impuestos": {"impuesto": {"valor": "0.11", "codigo": "2", "tarifa": "15", "baseImponible": "0.76", "codigoPorcentaje": "4"}}, "descripcion": "CCC", "precioUnitario": "1.000000", "codigoPrincipal": "S/C", "precioTotalSinImpuesto": "0.76"}, {"cantidad": "1.000000", "descuento": "0.50", "impuestos": {"impuesto": {"valor": "0.08", "codigo": "2", "tarifa": "15", "baseImponible": "0.50", "codigoPorcentaje": "4"}}, "descripcion": "DDD", "precioUnitario": "1.000000", "codigoPrincipal": "S/C", "precioTotalSinImpuesto": "0.50"}]}, "infoFactura": {"pagos": {"pago": [{"plazo": "0", "total": "1.86", "formaPago": "01", "unidadTiempo": "dias"}]}, "moneda": "DOLAR", "propina": "0.00", "fechaEmision": "03/08/2026", "importeTotal": "1.86", "totalDescuento": "1.49", "totalConImpuestos": {"totalImpuesto": [{"valor": "0.25", "codigo": "2", "baseImponible": "1.61", "codigoPorcentaje": "4"}]}, "totalSinImpuestos": "1.61", "dirEstablecimiento": "PORTOVIEJO", "obligadoContabilidad": "NO", "razonSocialComprador": "CONSUMIDOR FINAL", "identificacionComprador": "9999999999999", "tipoIdentificacionComprador": "07"}, "infoAdicional": {"campoAdicional": [{"#text": "tu ya sabes rey", "@nombre": "canastros"}, {"#text": "1312838392001 (www.kipu.ec)", "@nombre": "Proveedor"}]}, "infoTributaria": {"ruc": "1312838392001", "estab": "001", "codDoc": "01", "ptoEmi": "001", "ambiente": 1, "dirMatriz": "PORTOVIEJO", "secuencial": "000000018", "claveAcceso": "0308202601131283839200110010010000000183104191817", "razonSocial": "ROMERO GARCIA CRISTHIAN ANDRES", "tipoEmision": "1", "nombreComercial": "ROMERO GARCIA CRISTHIAN ANDRES"}}	1312838392001/facturas/0308202601131283839200110010010000000183104191817.xml	\N	\N	2026-08-04 00:04:33.971692+00	2026-08-04 00:04:35+00	\N	\N	2026-08-04 00:04:32.959344+00	\N	web	01	\N
54ce2e22-b855-4614-a28b-af572c8ce28f	20	16	ac248cd7-7339-4992-b691-9c31aca4d551	0808202601131283839200110010010000000421822127011	000000042	001-001-000000042	2026-08-08	DEVUELTA	1312838392	CRISTHIAN ROMERO	cristhianromero19@outlook.com	6.90	6.00	0.00	0.90	{"@id": "comprobante", "@version": "1.1.0", "detalles": {"detalle": [{"cantidad": "1.000000", "descuento": "0.00", "impuestos": {"impuesto": {"valor": "0.60", "codigo": "2", "tarifa": "15", "baseImponible": "4.00", "codigoPorcentaje": "4"}}, "descripcion": "MOVIMIENTO", "precioUnitario": "4.000000", "codigoPrincipal": "S/C", "precioTotalSinImpuesto": "4.00"}, {"cantidad": "1.000000", "descuento": "0.00", "impuestos": {"impuesto": {"valor": "0.30", "codigo": "2", "tarifa": "15", "baseImponible": "2.00", "codigoPorcentaje": "4"}}, "descripcion": "WWW", "precioUnitario": "2.000000", "codigoPrincipal": "1", "precioTotalSinImpuesto": "2.00"}]}, "infoFactura": {"pagos": {"pago": [{"plazo": "0", "total": "6.90", "formaPago": "01", "unidadTiempo": "dias"}]}, "moneda": "DOLAR", "propina": "0.00", "fechaEmision": "08/08/2026", "importeTotal": "6.90", "totalDescuento": "0.00", "totalConImpuestos": {"totalImpuesto": [{"valor": "0.90", "codigo": "2", "baseImponible": "6.00", "codigoPorcentaje": "4"}]}, "totalSinImpuestos": "6.00", "dirEstablecimiento": "PORTOVIEJO", "obligadoContabilidad": "NO", "razonSocialComprador": "CRISTHIAN ROMERO", "identificacionComprador": "1312838392", "tipoIdentificacionComprador": "05"}, "infoAdicional": {"campoAdicional": [{"#text": "1312838392001 (kipu.ec)", "@nombre": "Proveedor"}]}, "infoTributaria": {"ruc": "1312838392001", "estab": "001", "codDoc": "01", "ptoEmi": "001", "ambiente": 1, "dirMatriz": "PORTOVIEJO", "secuencial": "000000042", "claveAcceso": "0808202601131283839200110010010000000421822127011", "razonSocial": "ROMERO GARCIA CRISTHIAN ANDRES", "tipoEmision": "1", "nombreComercial": "ROMERO GARCIA CRISTHIAN ANDRES"}, "resumenImpuestos": [{"valor": "0.90", "tarifa": "15", "baseImponible": "6.00"}]}	1312838392001/facturas/0808202601131283839200110010010000000421822127011.xml	\N	{"estado": "DEVUELTA", "comprobantes": {"comprobante": {"mensajes": {"mensaje": {"tipo": "ERROR", "mensaje": "ARCHIVO NO CUMPLE ESTRUCTURA XML", "identificador": "35", "informacionAdicional": "Se encontró el siguiente error en la estructura del comprobante: cvc-complex-type.2.4.a: Invalid content was found starting with element 'plazo'. One of '{total}' is expected.."}}, "claveAcceso": "0808202601131283839200110010010000000421822127011"}}}	\N	\N	\N	\N	2026-08-08 17:22:20.058933+00	\N	web	01	\N
fcd7f645-42b0-4f91-b398-0d20791bd947	20	16	ac248cd7-7339-4992-b691-9c31aca4d551	0808202604131283839200110010010000000444529125710	000000044	001-001-000000044	2026-08-08	DEVUELTA	1312838392	CRISTHIAN ROMERO	cristhianromero19@outlook.com	2.30	2.00	0.00	0.30	{"@id": "comprobante", "@version": "1.1.0", "detalles": {"detalle": [{"cantidad": "1.000000", "descuento": "0.00", "impuestos": {"impuesto": {"valor": "0.30", "codigo": "2", "tarifa": "15", "baseImponible": "2.00", "codigoPorcentaje": "4"}}, "descripcion": "WWW", "precioUnitario": "2.000000", "codigoPrincipal": "1", "precioTotalSinImpuesto": "2.00"}]}, "infoAdicional": {"campoAdicional": [{"#text": "1312838392001 (kipu.ec)", "@nombre": "Proveedor"}]}, "infoTributaria": {"ruc": "1312838392001", "estab": "001", "codDoc": "04", "ptoEmi": "001", "ambiente": 1, "dirMatriz": "PORTOVIEJO", "secuencial": "000000044", "claveAcceso": "0808202604131283839200110010010000000444529125710", "razonSocial": "ROMERO GARCIA CRISTHIAN ANDRES", "tipoEmision": "1", "nombreComercial": "ROMERO GARCIA CRISTHIAN ANDRES"}, "infoNotaCredito": {"motivo": "DEVOLUCION DE BIEN", "fechaEmision": "08/08/2026", "codDocModificado": "01", "numDocModificado": "001-001-000000043", "totalConImpuestos": {"totalImpuesto": [{"valor": "0.30", "codigo": "2", "baseImponible": "2.00", "codigoPorcentaje": "4"}]}, "totalSinImpuestos": "2.00", "valorModificacion": "2.30", "dirEstablecimiento": "PORTOVIEJO", "obligadoContabilidad": "NO", "razonSocialComprador": "CRISTHIAN ROMERO", "fechaEmisionDocSustento": "08/08/2026", "identificacionComprador": "1312838392", "tipoIdentificacionComprador": "05"}, "resumenImpuestos": [{"valor": "0.30", "tarifa": "15", "baseImponible": "2.00"}], "factura_referencia": "323611ef-75f3-4ea6-8045-ee0a48526a7a"}	1312838392001/notas_credito/0808202604131283839200110010010000000444529125710.xml	\N	{"estado": "DEVUELTA", "comprobantes": {"comprobante": {"mensajes": {"mensaje": {"tipo": "ERROR", "mensaje": "ARCHIVO NO CUMPLE ESTRUCTURA XML", "identificador": "35", "informacionAdicional": "Se encontró el siguiente error en la estructura del comprobante: cvc-complex-type.2.4.a: Invalid content was found starting with element 'motivo'. One of '{moneda, totalConImpuestos}' is expected.."}}, "claveAcceso": "0808202604131283839200110010010000000444529125710"}}}	\N	\N	\N	\N	2026-08-08 17:29:46.402432+00	\N	web	04	323611ef-75f3-4ea6-8045-ee0a48526a7a
0343cc3c-0f81-4f1f-b18e-d4bef86a9ab2	20	16	\N	1008202601131283839200110010010000000515428126018	000000051	001-001-000000051	2026-08-10	AUTORIZADO	1712345678	JUAN CARLOS PÉREZ	194cr@proton.me	166.75	145.00	0.00	21.75	{"@id": "comprobante", "@version": "1.1.0", "detalles": {"detalle": [{"cantidad": "1.000000", "descuento": "0.00", "impuestos": {"impuesto": {"valor": "15.00", "codigo": "2", "tarifa": "15", "baseImponible": "100.00", "codigoPorcentaje": "4"}}, "descripcion": "SERVICIO DE DESARROLLO WEB", "precioUnitario": "100.000000", "codigoPrincipal": "PROD-001", "precioTotalSinImpuesto": "100.00"}, {"cantidad": "3.000000", "descuento": "0.00", "impuestos": {"impuesto": {"valor": "6.75", "codigo": "2", "tarifa": "15", "baseImponible": "45.00", "codigoPorcentaje": "4"}}, "descripcion": "HOSTING MENSUAL", "precioUnitario": "15.000000", "codigoPrincipal": "PROD-002", "precioTotalSinImpuesto": "45.00"}]}, "infoFactura": {"pagos": {"pago": [{"plazo": "0", "total": "166.75", "formaPago": "01", "unidadTiempo": "dias"}]}, "moneda": "DOLAR", "propina": "0.00", "fechaEmision": "10/08/2026", "importeTotal": "166.75", "totalDescuento": "0.00", "totalConImpuestos": {"totalImpuesto": [{"valor": "21.75", "codigo": "2", "baseImponible": "145.00", "codigoPorcentaje": "4"}]}, "totalSinImpuestos": "145.00", "dirEstablecimiento": "PORTOVIEJO", "obligadoContabilidad": "NO", "razonSocialComprador": "JUAN CARLOS PÉREZ", "identificacionComprador": "1712345678", "tipoIdentificacionComprador": "05"}, "infoAdicional": {"campoAdicional": [{"#text": "ORD-2026-001", "@nombre": "Referencia"}, {"#text": "Juan Pérez", "@nombre": "Vendedor"}, {"#text": "1312838392001 (kipu.ec)", "@nombre": "PROVEEDOR_SISTEMA_INFORMATICO"}]}, "infoTributaria": {"ruc": "1312838392001", "estab": "001", "codDoc": "01", "ptoEmi": "001", "ambiente": 1, "dirMatriz": "PORTOVIEJO", "secuencial": "000000051", "claveAcceso": "1008202601131283839200110010010000000515428126018", "razonSocial": "ROMERO GARCIA CRISTHIAN ANDRES", "tipoEmision": "1", "nombreComercial": "ROMERO GARCIA CRISTHIAN ANDRES"}, "resumenImpuestos": [{"valor": "21.75", "tarifa": "15", "baseImponible": "145.00"}]}	1312838392001/facturas/1008202601131283839200110010010000000515428126018.xml	\N	\N	2026-08-10 17:28:56.167895+00	2026-08-10 17:28:57+00	\N	\N	2026-08-10 17:28:53.812993+00	8	api	01	\N
16222be8-ee84-4536-a8b6-d61c00aeded6	20	16	\N	0308202601131283839200110010010000000190146202416	000000019	001-001-000000019	2026-08-03	AUTORIZADO	9999999999999	CONSUMIDOR FINAL	\N	1.15	1.00	0.00	0.15	{"@id": "comprobante", "@version": "1.1.0", "detalles": {"detalle": [{"cantidad": "1.000000", "descuento": "0.00", "impuestos": {"impuesto": {"valor": "0.15", "codigo": "2", "tarifa": "15", "baseImponible": "1.00", "codigoPorcentaje": "4"}}, "descripcion": "CONSULTORIA", "precioUnitario": "1.000000", "codigoPrincipal": "S/C", "precioTotalSinImpuesto": "1.00"}]}, "infoFactura": {"pagos": {"pago": [{"plazo": "0", "total": "1.15", "formaPago": "01", "unidadTiempo": "dias"}]}, "moneda": "DOLAR", "propina": "0.00", "fechaEmision": "03/08/2026", "importeTotal": "1.15", "totalDescuento": "0.00", "totalConImpuestos": {"totalImpuesto": [{"valor": "0.15", "codigo": "2", "baseImponible": "1.00", "codigoPorcentaje": "4"}]}, "totalSinImpuestos": "1.00", "dirEstablecimiento": "PORTOVIEJO", "obligadoContabilidad": "NO", "razonSocialComprador": "CONSUMIDOR FINAL", "identificacionComprador": "9999999999999", "tipoIdentificacionComprador": "07"}, "infoAdicional": {"campoAdicional": [{"#text": "1312838392001 (www.kipu.ec)", "@nombre": "Proveedor"}]}, "infoTributaria": {"ruc": "1312838392001", "estab": "001", "codDoc": "01", "ptoEmi": "001", "ambiente": 1, "dirMatriz": "PORTOVIEJO", "secuencial": "000000019", "claveAcceso": "0308202601131283839200110010010000000190146202416", "razonSocial": "ROMERO GARCIA CRISTHIAN ANDRES", "tipoEmision": "1", "nombreComercial": "ROMERO GARCIA CRISTHIAN ANDRES"}}	1312838392001/facturas/0308202601131283839200110010010000000190146202416.xml	\N	\N	2026-08-04 01:46:04.060359+00	2026-08-04 01:46:05+00	\N	\N	2026-08-04 01:46:02.933433+00	\N	web	01	\N
4024c08c-4e00-4b77-ae34-fc77d7509886	20	16	\N	0308202601131283839200110010010000000203339231418	000000020	001-001-000000020	2026-08-03	AUTORIZADO	9999999999999	CONSUMIDOR FINAL	\N	4.60	4.00	0.00	0.60	{"@id": "comprobante", "@version": "1.1.0", "detalles": {"detalle": [{"cantidad": "1.000000", "descuento": "0.00", "impuestos": {"impuesto": {"valor": "0.15", "codigo": "2", "tarifa": "15", "baseImponible": "1.00", "codigoPorcentaje": "4"}}, "descripcion": "QQ", "precioUnitario": "1.000000", "codigoPrincipal": "S/C", "precioTotalSinImpuesto": "1.00"}, {"cantidad": "1.000000", "descuento": "0.00", "impuestos": {"impuesto": {"valor": "0.15", "codigo": "2", "tarifa": "15", "baseImponible": "1.00", "codigoPorcentaje": "4"}}, "descripcion": "WW", "precioUnitario": "1.000000", "codigoPrincipal": "S/C", "precioTotalSinImpuesto": "1.00"}, {"cantidad": "2.000000", "descuento": "0.00", "impuestos": {"impuesto": {"valor": "0.30", "codigo": "2", "tarifa": "15", "baseImponible": "2.00", "codigoPorcentaje": "4"}}, "descripcion": "EE", "precioUnitario": "1.000000", "codigoPrincipal": "S/C", "precioTotalSinImpuesto": "2.00"}]}, "infoFactura": {"pagos": {"pago": [{"plazo": "0", "total": "4.35", "formaPago": "01", "unidadTiempo": "dias"}]}, "moneda": "DOLAR", "propina": "0.00", "fechaEmision": "03/08/2026", "importeTotal": "4.60", "totalDescuento": "0.00", "totalConImpuestos": {"totalImpuesto": [{"valor": "0.60", "codigo": "2", "baseImponible": "4.00", "codigoPorcentaje": "4"}]}, "totalSinImpuestos": "4.00", "dirEstablecimiento": "PORTOVIEJO", "obligadoContabilidad": "NO", "razonSocialComprador": "CONSUMIDOR FINAL", "identificacionComprador": "9999999999999", "tipoIdentificacionComprador": "07"}, "infoAdicional": {"campoAdicional": [{"#text": "aqui", "@nombre": "email"}, {"#text": "1312838392001 (www.kipu.ec)", "@nombre": "Proveedor"}]}, "infoTributaria": {"ruc": "1312838392001", "estab": "001", "codDoc": "01", "ptoEmi": "001", "ambiente": 1, "dirMatriz": "PORTOVIEJO", "secuencial": "000000020", "claveAcceso": "0308202601131283839200110010010000000203339231418", "razonSocial": "ROMERO GARCIA CRISTHIAN ANDRES", "tipoEmision": "1", "nombreComercial": "ROMERO GARCIA CRISTHIAN ANDRES"}}	1312838392001/facturas/0308202601131283839200110010010000000203339231418.xml	\N	\N	2026-08-04 04:39:35.992642+00	2026-08-04 04:39:37+00	\N	\N	2026-08-04 04:39:34.952168+00	\N	web	01	\N
0afbc7f5-a205-4517-8cca-32e57f30af9e	20	16	\N	1008202601131283839200110010010000000525728126317	000000052	001-001-000000052	2026-08-10	AUTORIZADO	1712345678	JUAN CARLOS PÉREZ	194cr@proton.me	166.75	145.00	0.00	21.75	{"@id": "comprobante", "@version": "1.1.0", "detalles": {"detalle": [{"cantidad": "1.000000", "descuento": "0.00", "impuestos": {"impuesto": {"valor": "15.00", "codigo": "2", "tarifa": "15", "baseImponible": "100.00", "codigoPorcentaje": "4"}}, "descripcion": "SERVICIO DE DESARROLLO WEB", "precioUnitario": "100.000000", "codigoPrincipal": "PROD-001", "precioTotalSinImpuesto": "100.00"}, {"cantidad": "3.000000", "descuento": "0.00", "impuestos": {"impuesto": {"valor": "6.75", "codigo": "2", "tarifa": "15", "baseImponible": "45.00", "codigoPorcentaje": "4"}}, "descripcion": "HOSTING MENSUAL", "precioUnitario": "15.000000", "codigoPrincipal": "PROD-002", "precioTotalSinImpuesto": "45.00"}]}, "infoFactura": {"pagos": {"pago": [{"plazo": "0", "total": "166.75", "formaPago": "01", "unidadTiempo": "dias"}]}, "moneda": "DOLAR", "propina": "0.00", "fechaEmision": "10/08/2026", "importeTotal": "166.75", "totalDescuento": "0.00", "totalConImpuestos": {"totalImpuesto": [{"valor": "21.75", "codigo": "2", "baseImponible": "145.00", "codigoPorcentaje": "4"}]}, "totalSinImpuestos": "145.00", "dirEstablecimiento": "PORTOVIEJO", "obligadoContabilidad": "NO", "razonSocialComprador": "JUAN CARLOS PÉREZ", "identificacionComprador": "1712345678", "tipoIdentificacionComprador": "05"}, "infoAdicional": {"campoAdicional": [{"#text": "ORD-2026-001", "@nombre": "Referencia"}, {"#text": "Juan Pérez", "@nombre": "Vendedor"}, {"#text": "1312838392001 (kipu.ec)", "@nombre": "PROVEEDOR_SISTEMA_INFORMATICO"}]}, "infoTributaria": {"ruc": "1312838392001", "estab": "001", "codDoc": "01", "ptoEmi": "001", "ambiente": 1, "dirMatriz": "PORTOVIEJO", "secuencial": "000000052", "claveAcceso": "1008202601131283839200110010010000000525728126317", "razonSocial": "ROMERO GARCIA CRISTHIAN ANDRES", "tipoEmision": "1", "nombreComercial": "ROMERO GARCIA CRISTHIAN ANDRES"}, "resumenImpuestos": [{"valor": "21.75", "tarifa": "15", "baseImponible": "145.00"}]}	1312838392001/facturas/1008202601131283839200110010010000000525728126317.xml	\N	\N	2026-08-10 17:28:58.623407+00	2026-08-10 17:28:59+00	\N	\N	2026-08-10 17:28:56.234173+00	8	api	01	\N
323611ef-75f3-4ea6-8045-ee0a48526a7a	20	16	ac248cd7-7339-4992-b691-9c31aca4d551	0808202601131283839200110010010000000433327124916	000000043	001-001-000000043	2026-08-08	AUTORIZADO	1312838392	CRISTHIAN ROMERO	cristhianromero19@outlook.com	6.90	6.00	0.00	0.90	{"@id": "comprobante", "@version": "1.1.0", "detalles": {"detalle": [{"cantidad": "1.000000", "descuento": "0.00", "impuestos": {"impuesto": {"valor": "0.60", "codigo": "2", "tarifa": "15", "baseImponible": "4.00", "codigoPorcentaje": "4"}}, "descripcion": "ALTO", "precioUnitario": "4.000000", "codigoPrincipal": "S/C", "precioTotalSinImpuesto": "4.00"}, {"cantidad": "1.000000", "descuento": "0.00", "impuestos": {"impuesto": {"valor": "0.30", "codigo": "2", "tarifa": "15", "baseImponible": "2.00", "codigoPorcentaje": "4"}}, "descripcion": "WWW", "precioUnitario": "2.000000", "codigoPrincipal": "1", "precioTotalSinImpuesto": "2.00"}]}, "infoFactura": {"pagos": {"pago": [{"plazo": "0", "total": "6.90", "formaPago": "01", "unidadTiempo": "dias"}]}, "moneda": "DOLAR", "propina": "0.00", "fechaEmision": "08/08/2026", "importeTotal": "6.90", "totalDescuento": "0.00", "totalConImpuestos": {"totalImpuesto": [{"valor": "0.90", "codigo": "2", "baseImponible": "6.00", "codigoPorcentaje": "4"}]}, "totalSinImpuestos": "6.00", "dirEstablecimiento": "PORTOVIEJO", "obligadoContabilidad": "NO", "razonSocialComprador": "CRISTHIAN ROMERO", "identificacionComprador": "1312838392", "tipoIdentificacionComprador": "05"}, "infoAdicional": {"campoAdicional": [{"#text": "1312838392001 (kipu.ec)", "@nombre": "Proveedor"}]}, "infoTributaria": {"ruc": "1312838392001", "estab": "001", "codDoc": "01", "ptoEmi": "001", "ambiente": 1, "dirMatriz": "PORTOVIEJO", "secuencial": "000000043", "claveAcceso": "0808202601131283839200110010010000000433327124916", "razonSocial": "ROMERO GARCIA CRISTHIAN ANDRES", "tipoEmision": "1", "nombreComercial": "ROMERO GARCIA CRISTHIAN ANDRES"}, "resumenImpuestos": [{"valor": "0.90", "tarifa": "15", "baseImponible": "6.00"}]}	1312838392001/facturas/0808202601131283839200110010010000000433327124916.xml	\N	\N	2026-08-08 17:27:36.767918+00	2026-08-08 17:27:38+00	\N	\N	2026-08-08 17:27:34.921269+00	\N	web	01	\N
398baa5e-8ea3-4070-bb87-94bfcf2c8100	20	17	\N	0308202601131283839200110010050000000053342239511	000000005	001-005-000000005	2026-08-03	AUTORIZADO	9999999999999	CONSUMIDOR FINAL	\N	4.60	4.00	0.00	0.60	{"@id": "comprobante", "@version": "1.1.0", "detalles": {"detalle": [{"cantidad": "1.000000", "descuento": "0.00", "impuestos": {"impuesto": {"valor": "0.15", "codigo": "2", "tarifa": "15", "baseImponible": "1.00", "codigoPorcentaje": "4"}}, "descripcion": "WW", "precioUnitario": "1.000000", "codigoPrincipal": "S/C", "precioTotalSinImpuesto": "1.00"}, {"cantidad": "1.000000", "descuento": "0.00", "impuestos": {"impuesto": {"valor": "0.15", "codigo": "2", "tarifa": "15", "baseImponible": "1.00", "codigoPorcentaje": "4"}}, "descripcion": "EE", "precioUnitario": "1.000000", "codigoPrincipal": "S/C", "precioTotalSinImpuesto": "1.00"}, {"cantidad": "1.000000", "descuento": "0.00", "impuestos": {"impuesto": {"valor": "0.30", "codigo": "2", "tarifa": "15", "baseImponible": "2.00", "codigoPorcentaje": "4"}}, "descripcion": "RR", "precioUnitario": "2.000000", "codigoPrincipal": "S/C", "precioTotalSinImpuesto": "2.00"}]}, "infoFactura": {"pagos": {"pago": [{"plazo": "0", "total": "4.35", "formaPago": "01", "unidadTiempo": "dias"}]}, "moneda": "DOLAR", "propina": "0.00", "fechaEmision": "03/08/2026", "importeTotal": "4.60", "totalDescuento": "0.00", "totalConImpuestos": {"totalImpuesto": [{"valor": "0.60", "codigo": "2", "baseImponible": "4.00", "codigoPorcentaje": "4"}]}, "totalSinImpuestos": "4.00", "dirEstablecimiento": "PORTOVIEJO", "obligadoContabilidad": "NO", "razonSocialComprador": "CONSUMIDOR FINAL", "identificacionComprador": "9999999999999", "tipoIdentificacionComprador": "07"}, "infoAdicional": {"campoAdicional": [{"#text": "sapo", "@nombre": "email"}, {"#text": "1312838392001 (www.kipu.ec)", "@nombre": "Proveedor"}]}, "infoTributaria": {"ruc": "1312838392001", "estab": "001", "codDoc": "01", "ptoEmi": "005", "ambiente": 1, "dirMatriz": "PORTOVIEJO", "secuencial": "000000005", "claveAcceso": "0308202601131283839200110010050000000053342239511", "razonSocial": "ROMERO GARCIA CRISTHIAN ANDRES", "tipoEmision": "1", "nombreComercial": "ROMERO GARCIA CRISTHIAN ANDRES"}}	1312838392001/facturas/0308202601131283839200110010050000000053342239511.xml	\N	\N	2026-08-04 04:42:35.536948+00	2026-08-04 04:42:36+00	\N	\N	2026-08-04 04:42:34.54896+00	\N	web	01	\N
8b81652a-b925-4503-b0e0-58830fa13987	20	16	\N	1108202601131283839200110010010000000533104158610	000000053	001-001-000000053	2026-08-11	AUTORIZADO	9999999999999	CONSUMIDOR FINAL	\N	2.30	2.00	0.00	0.30	{"@id": "comprobante", "@version": "1.1.0", "detalles": {"detalle": [{"cantidad": "1.000000", "descuento": "0.00", "impuestos": {"impuesto": {"valor": "0.30", "codigo": "2", "tarifa": "15", "baseImponible": "2.00", "codigoPorcentaje": "4"}}, "descripcion": "WWW", "precioUnitario": "2.000000", "codigoPrincipal": "1", "precioTotalSinImpuesto": "2.00"}]}, "infoFactura": {"pagos": {"pago": [{"plazo": "0", "total": "2.30", "formaPago": "01", "unidadTiempo": "dias"}]}, "moneda": "DOLAR", "propina": "0.00", "fechaEmision": "11/08/2026", "importeTotal": "2.30", "totalDescuento": "0.00", "totalConImpuestos": {"totalImpuesto": [{"valor": "0.30", "codigo": "2", "baseImponible": "2.00", "codigoPorcentaje": "4"}]}, "totalSinImpuestos": "2.00", "dirEstablecimiento": "PORTOVIEJO", "obligadoContabilidad": "NO", "razonSocialComprador": "CONSUMIDOR FINAL", "identificacionComprador": "9999999999999", "tipoIdentificacionComprador": "07"}, "infoAdicional": {"campoAdicional": [{"#text": "1312838392001 (kipu.ec)", "@nombre": "PROVEEDOR_SISTEMA_INFORMATICO"}]}, "infoTributaria": {"ruc": "1312838392001", "estab": "001", "codDoc": "01", "ptoEmi": "001", "ambiente": 1, "dirMatriz": "PORTOVIEJO", "secuencial": "000000053", "claveAcceso": "1108202601131283839200110010010000000533104158610", "razonSocial": "ROMERO GARCIA CRISTHIAN ANDRES", "tipoEmision": "1", "nombreComercial": "ROMERO GARCIA CRISTHIAN ANDRES"}, "resumenImpuestos": [{"valor": "0.30", "tarifa": "15", "baseImponible": "2.00"}]}	1312838392001/facturas/1108202601131283839200110010010000000533104158610.xml	\N	\N	2026-08-11 20:04:33.195893+00	2026-08-11 20:04:34+00	\N	\N	2026-08-11 20:04:31.069577+00	\N	web	01	\N
c0bf0e1c-b9d5-4b22-8290-ededbb29e84d	20	17	\N	0308202601131283839200110010050000000061348239018	000000006	001-005-000000006	2026-08-03	AUTORIZADO	9999999999999	CONSUMIDOR FINAL	\N	3.45	3.00	0.00	0.45	{"@id": "comprobante", "@version": "1.1.0", "detalles": {"detalle": [{"cantidad": "1.000000", "descuento": "0.00", "impuestos": {"impuesto": {"valor": "0.15", "codigo": "2", "tarifa": "15", "baseImponible": "1.00", "codigoPorcentaje": "4"}}, "descripcion": "EEE", "precioUnitario": "1.000000", "codigoPrincipal": "S/C", "precioTotalSinImpuesto": "1.00"}, {"cantidad": "1.000000", "descuento": "0.00", "impuestos": {"impuesto": {"valor": "0.15", "codigo": "2", "tarifa": "15", "baseImponible": "1.00", "codigoPorcentaje": "4"}}, "descripcion": "TT", "precioUnitario": "1.000000", "codigoPrincipal": "S/C", "precioTotalSinImpuesto": "1.00"}, {"cantidad": "1.000000", "descuento": "0.00", "impuestos": {"impuesto": {"valor": "0.15", "codigo": "2", "tarifa": "15", "baseImponible": "1.00", "codigoPorcentaje": "4"}}, "descripcion": "FF", "precioUnitario": "1.000000", "codigoPrincipal": "S/C", "precioTotalSinImpuesto": "1.00"}]}, "infoFactura": {"pagos": {"pago": [{"plazo": "0", "total": "3.20", "formaPago": "01", "unidadTiempo": "dias"}]}, "moneda": "DOLAR", "propina": "0.00", "fechaEmision": "03/08/2026", "importeTotal": "3.45", "totalDescuento": "0.00", "totalConImpuestos": {"totalImpuesto": [{"valor": "0.45", "codigo": "2", "baseImponible": "3.00", "codigoPorcentaje": "4"}]}, "totalSinImpuestos": "3.00", "dirEstablecimiento": "PORTOVIEJO", "obligadoContabilidad": "NO", "razonSocialComprador": "CONSUMIDOR FINAL", "identificacionComprador": "9999999999999", "tipoIdentificacionComprador": "07"}, "infoAdicional": {"campoAdicional": [{"#text": "1312838392001 (www.kipu.ec)", "@nombre": "Proveedor"}]}, "infoTributaria": {"ruc": "1312838392001", "estab": "001", "codDoc": "01", "ptoEmi": "005", "ambiente": 1, "dirMatriz": "PORTOVIEJO", "secuencial": "000000006", "claveAcceso": "0308202601131283839200110010050000000061348239018", "razonSocial": "ROMERO GARCIA CRISTHIAN ANDRES", "tipoEmision": "1", "nombreComercial": "ROMERO GARCIA CRISTHIAN ANDRES"}}	1312838392001/facturas/0308202601131283839200110010050000000061348239018.xml	\N	\N	2026-08-04 04:48:16.615246+00	2026-08-04 04:48:17+00	\N	\N	2026-08-04 04:48:15.627918+00	\N	web	01	\N
f6766380-7f78-412f-854c-fe9228bfad01	20	17	\N	0308202601131283839200110010050000000075551234911	000000007	001-005-000000007	2026-08-03	AUTORIZADO	9999999999999	CONSUMIDOR FINAL	\N	3.20	2.00	1.00	0.20	{"@id": "comprobante", "@version": "1.1.0", "detalles": {"detalle": [{"cantidad": "1.000000", "descuento": "0.00", "impuestos": {"impuesto": {"valor": "0.15", "codigo": "2", "tarifa": "15", "baseImponible": "1.00", "codigoPorcentaje": "4"}}, "descripcion": "FFFF", "precioUnitario": "1.000000", "codigoPrincipal": "S/C", "precioTotalSinImpuesto": "1.00"}, {"cantidad": "1.000000", "descuento": "0.00", "impuestos": {"impuesto": {"valor": "0.05", "codigo": "2", "tarifa": "5", "baseImponible": "1.00", "codigoPorcentaje": "5"}}, "descripcion": "WWW", "precioUnitario": "1.000000", "codigoPrincipal": "S/C", "precioTotalSinImpuesto": "1.00"}, {"cantidad": "1.000000", "descuento": "0.00", "impuestos": {"impuesto": {"valor": "0.00", "codigo": "2", "tarifa": "0", "baseImponible": "1.00", "codigoPorcentaje": "0"}}, "descripcion": "4ED", "precioUnitario": "1.000000", "codigoPrincipal": "S/C", "precioTotalSinImpuesto": "1.00"}]}, "infoFactura": {"pagos": {"pago": [{"plazo": "0", "total": "3.20", "formaPago": "01", "unidadTiempo": "dias"}]}, "moneda": "DOLAR", "propina": "0.00", "fechaEmision": "03/08/2026", "importeTotal": "3.20", "totalDescuento": "0.00", "totalConImpuestos": {"totalImpuesto": [{"valor": "0.15", "codigo": "2", "baseImponible": "1.00", "codigoPorcentaje": "4"}, {"valor": "0.05", "codigo": "2", "baseImponible": "1.00", "codigoPorcentaje": "5"}, {"valor": "0.00", "codigo": "2", "baseImponible": "1.00", "codigoPorcentaje": "0"}]}, "totalSinImpuestos": "3.00", "dirEstablecimiento": "PORTOVIEJO", "obligadoContabilidad": "NO", "razonSocialComprador": "CONSUMIDOR FINAL", "identificacionComprador": "9999999999999", "tipoIdentificacionComprador": "07"}, "infoAdicional": {"campoAdicional": [{"#text": "1312838392001 (www.kipu.ec)", "@nombre": "Proveedor"}]}, "infoTributaria": {"ruc": "1312838392001", "estab": "001", "codDoc": "01", "ptoEmi": "005", "ambiente": 1, "dirMatriz": "PORTOVIEJO", "secuencial": "000000007", "claveAcceso": "0308202601131283839200110010050000000075551234911", "razonSocial": "ROMERO GARCIA CRISTHIAN ANDRES", "tipoEmision": "1", "nombreComercial": "ROMERO GARCIA CRISTHIAN ANDRES"}}	1312838392001/facturas/0308202601131283839200110010050000000075551234911.xml	\N	\N	2026-08-04 04:51:58.079536+00	2026-08-04 04:51:59+00	\N	\N	2026-08-04 04:51:57.139006+00	\N	web	01	\N
1f25593b-0c46-456e-b471-a4d4effb0384	20	16	ac248cd7-7339-4992-b691-9c31aca4d551	0808202604131283839200110010010000000455332125710	000000045	001-001-000000045	2026-08-08	DEVUELTA	1312838392	CRISTHIAN ROMERO	cristhianromero19@outlook.com	4.60	4.00	0.00	0.60	{"@id": "comprobante", "@version": "1.1.0", "detalles": {"detalle": [{"cantidad": "1.000000", "descuento": "0.00", "impuestos": {"impuesto": {"valor": "0.60", "codigo": "2", "tarifa": "15", "baseImponible": "4.00", "codigoPorcentaje": "4"}}, "descripcion": "ALTO", "precioUnitario": "4.000000", "codigoPrincipal": "None", "precioTotalSinImpuesto": "4.00"}]}, "infoAdicional": {"campoAdicional": [{"#text": "1312838392001 (kipu.ec)", "@nombre": "Proveedor"}]}, "infoTributaria": {"ruc": "1312838392001", "estab": "001", "codDoc": "04", "ptoEmi": "001", "ambiente": 1, "dirMatriz": "PORTOVIEJO", "secuencial": "000000045", "claveAcceso": "0808202604131283839200110010010000000455332125710", "razonSocial": "ROMERO GARCIA CRISTHIAN ANDRES", "tipoEmision": "1", "nombreComercial": "ROMERO GARCIA CRISTHIAN ANDRES"}, "infoNotaCredito": {"moneda": "DOLAR", "motivo": "DEVLOLU", "fechaEmision": "08/08/2026", "codDocModificado": "01", "numDocModificado": "001-001-000000043", "totalConImpuestos": {"totalImpuesto": [{"valor": "0.60", "codigo": "2", "baseImponible": "4.00", "codigoPorcentaje": "4"}]}, "totalSinImpuestos": "4.00", "valorModificacion": "4.60", "dirEstablecimiento": "PORTOVIEJO", "obligadoContabilidad": "NO", "razonSocialComprador": "CRISTHIAN ROMERO", "fechaEmisionDocSustento": "08/08/2026", "identificacionComprador": "1312838392", "tipoIdentificacionComprador": "05"}, "resumenImpuestos": [{"valor": "0.60", "tarifa": "15", "baseImponible": "4.00"}], "factura_referencia": "323611ef-75f3-4ea6-8045-ee0a48526a7a"}	1312838392001/notas_credito/0808202604131283839200110010010000000455332125710.xml	\N	{"estado": "DEVUELTA", "comprobantes": {"comprobante": {"mensajes": {"mensaje": {"tipo": "ERROR", "mensaje": "ARCHIVO NO CUMPLE ESTRUCTURA XML", "identificador": "35", "informacionAdicional": "Se encontró el siguiente error en la estructura del comprobante: cvc-complex-type.2.4.a: Invalid content was found starting with element 'codigoPrincipal'. One of '{codigoInterno, codigoAdicional, descripcion}' is expected.."}}, "claveAcceso": "0808202604131283839200110010010000000455332125710"}}}	\N	\N	\N	\N	2026-08-08 17:32:55.027683+00	\N	web	04	323611ef-75f3-4ea6-8045-ee0a48526a7a
c0df0ef0-5299-4428-8ab8-52d1bc4f9554	20	16	\N	0408202601131283839200110010010000000211424109912	000000021	001-001-000000021	2026-08-04	DEVUELTA	9999999999999	CONSUMIDOR FINAL	\N	6.80	6.00	0.00	0.80	{"@id": "comprobante", "@version": "1.1.0", "detalles": {"detalle": [{"cantidad": "1.000000", "descuento": "0.00", "impuestos": {"impuesto": {"valor": "0.05", "codigo": "2", "tarifa": "5", "baseImponible": "1.00", "codigoPorcentaje": "5"}}, "descripcion": "IVA 5", "precioUnitario": "1.000000", "codigoPrincipal": "S/C", "precioTotalSinImpuesto": "1.00"}, {"cantidad": "1.000000", "descuento": "0.00", "impuestos": {"impuesto": {"valor": "0.30", "codigo": "2", "tarifa": "15", "baseImponible": "2.00", "codigoPorcentaje": "4"}}, "descripcion": "IVA 15", "precioUnitario": "2.000000", "codigoPrincipal": "S/C", "precioTotalSinImpuesto": "2.00"}, {"cantidad": "1.000000", "descuento": "0.00", "impuestos": {"impuesto": {"valor": "0.45", "codigo": "2", "tarifa": "15", "baseImponible": "3.00", "codigoPorcentaje": "4"}}, "descripcion": "CERO", "precioUnitario": "3.000000", "codigoPrincipal": "S/C", "precioTotalSinImpuesto": "3.00"}, {"cantidad": "1.000000", "descuento": "0.00", "impuestos": {"impuesto": {"valor": "0.00", "codigo": "2", "tarifa": "15", "baseImponible": "0.00", "codigoPorcentaje": "4"}}, "descripcion": "CUANTO", "precioUnitario": "0.000000", "codigoPrincipal": "S/C", "precioTotalSinImpuesto": "0.00"}]}, "infoFactura": {"pagos": {"pago": [{"plazo": "0", "total": "6.80", "formaPago": "01", "unidadTiempo": "dias"}]}, "moneda": "DOLAR", "propina": "0.00", "fechaEmision": "04/08/2026", "importeTotal": "6.80", "totalDescuento": "0.00", "totalConImpuestos": {"totalImpuesto": [{"valor": "0.05", "codigo": "2", "tarifa": "5", "baseImponible": "1.00", "codigoPorcentaje": "5"}, {"valor": "0.75", "codigo": "2", "tarifa": "15", "baseImponible": "5.00", "codigoPorcentaje": "4"}]}, "totalSinImpuestos": "6.00", "dirEstablecimiento": "PORTOVIEJO", "obligadoContabilidad": "NO", "razonSocialComprador": "CONSUMIDOR FINAL", "identificacionComprador": "9999999999999", "tipoIdentificacionComprador": "07"}, "infoAdicional": {"campoAdicional": [{"#text": "1312838392001 (kipu.ec)", "@nombre": "Proveedor"}]}, "infoTributaria": {"ruc": "1312838392001", "estab": "001", "codDoc": "01", "ptoEmi": "001", "ambiente": 1, "dirMatriz": "PORTOVIEJO", "secuencial": "000000021", "claveAcceso": "0408202601131283839200110010010000000211424109912", "razonSocial": "ROMERO GARCIA CRISTHIAN ANDRES", "tipoEmision": "1", "nombreComercial": "ROMERO GARCIA CRISTHIAN ANDRES"}}	1312838392001/facturas/0408202601131283839200110010010000000211424109912.xml	\N	{"estado": "DEVUELTA", "comprobantes": {"comprobante": {"mensajes": {"mensaje": {"tipo": "ERROR", "mensaje": "ARCHIVO NO CUMPLE ESTRUCTURA XML", "identificador": "35", "informacionAdicional": "Se encontró el siguiente error en la estructura del comprobante: cvc-complex-type.2.4.a: Invalid content was found starting with element 'tarifa'. One of '{valorDevolucionIva}' is expected.."}}, "claveAcceso": "0408202601131283839200110010010000000211424109912"}}}	\N	\N	\N	\N	2026-08-04 15:24:16.852452+00	\N	web	01	\N
3206b81b-55ed-466f-bbcf-49c2b95ecea6	20	16	ac248cd7-7339-4992-b691-9c31aca4d551	0808202604131283839200110010010000000463234121718	000000046	001-001-000000046	2026-08-08	DEVUELTA	1312838392	CRISTHIAN ROMERO	cristhianromero19@outlook.com	4.60	4.00	0.00	0.60	{"@id": "comprobante", "@version": "1.1.0", "detalles": {"detalle": [{"cantidad": "1.000000", "descuento": "0.00", "impuestos": {"impuesto": {"valor": "0.60", "codigo": "2", "tarifa": "15", "baseImponible": "4.00", "codigoPorcentaje": "4"}}, "descripcion": "ALTO", "precioUnitario": "4.000000", "codigoPrincipal": "None", "precioTotalSinImpuesto": "4.00"}]}, "infoAdicional": {"campoAdicional": [{"#text": "1312838392001 (kipu.ec)", "@nombre": "Proveedor"}]}, "infoTributaria": {"ruc": "1312838392001", "estab": "001", "codDoc": "04", "ptoEmi": "001", "ambiente": 1, "dirMatriz": "PORTOVIEJO", "secuencial": "000000046", "claveAcceso": "0808202604131283839200110010010000000463234121718", "razonSocial": "ROMERO GARCIA CRISTHIAN ANDRES", "tipoEmision": "1", "nombreComercial": "ROMERO GARCIA CRISTHIAN ANDRES"}, "infoNotaCredito": {"moneda": "DOLAR", "motivo": "DEVOLUCION DE ESTO", "fechaEmision": "08/08/2026", "codDocModificado": "01", "numDocModificado": "001-001-000000043", "totalConImpuestos": {"totalImpuesto": [{"valor": "0.60", "codigo": "2", "baseImponible": "4.00", "codigoPorcentaje": "4"}]}, "totalSinImpuestos": "4.00", "valorModificacion": "4.60", "dirEstablecimiento": "PORTOVIEJO", "obligadoContabilidad": "NO", "razonSocialComprador": "CRISTHIAN ROMERO", "fechaEmisionDocSustento": "08/08/2026", "identificacionComprador": "1312838392", "tipoIdentificacionComprador": "05"}, "resumenImpuestos": [{"valor": "0.60", "tarifa": "15", "baseImponible": "4.00"}], "factura_referencia": "323611ef-75f3-4ea6-8045-ee0a48526a7a"}	1312838392001/notas_credito/0808202604131283839200110010010000000463234121718.xml	\N	{"estado": "DEVUELTA", "comprobantes": {"comprobante": {"mensajes": {"mensaje": {"tipo": "ERROR", "mensaje": "ARCHIVO NO CUMPLE ESTRUCTURA XML", "identificador": "35", "informacionAdicional": "Se encontró el siguiente error en la estructura del comprobante: cvc-complex-type.2.4.a: Invalid content was found starting with element 'codigoPrincipal'. One of '{codigoInterno, codigoAdicional, descripcion}' is expected.."}}, "claveAcceso": "0808202604131283839200110010010000000463234121718"}}}	\N	\N	\N	\N	2026-08-08 17:34:34.158061+00	\N	web	04	323611ef-75f3-4ea6-8045-ee0a48526a7a
1407c108-72f3-44ac-a3dc-28a7e253f7e7	20	16	ac248cd7-7339-4992-b691-9c31aca4d551	0808202604131283839200110010010000000481741124719	000000048	001-001-000000048	2026-08-08	DEVUELTA	1312838392	CRISTHIAN ROMERO	cristhianromero19@outlook.com	2.30	2.00	0.00	0.30	{"@id": "comprobante", "@version": "1.1.0", "detalles": {"detalle": [{"cantidad": "1.000000", "descuento": "0.00", "impuestos": {"impuesto": {"valor": "0.30", "codigo": "2", "tarifa": "15", "baseImponible": "2.00", "codigoPorcentaje": "4"}}, "descripcion": "WWW", "precioUnitario": "2.000000", "codigoPrincipal": "1", "precioTotalSinImpuesto": "2.00"}]}, "infoAdicional": {"campoAdicional": [{"#text": "1312838392001 (kipu.ec)", "@nombre": "Proveedor"}]}, "infoTributaria": {"ruc": "1312838392001", "estab": "001", "codDoc": "04", "ptoEmi": "001", "ambiente": 1, "dirMatriz": "PORTOVIEJO", "secuencial": "000000048", "claveAcceso": "0808202604131283839200110010010000000481741124719", "razonSocial": "ROMERO GARCIA CRISTHIAN ANDRES", "tipoEmision": "1", "nombreComercial": "ROMERO GARCIA CRISTHIAN ANDRES"}, "infoNotaCredito": {"motivo": "DEVOLUCION", "fechaEmision": "08/08/2026", "codDocModificado": "01", "numDocModificado": "001-001-000000043", "totalConImpuestos": {"totalImpuesto": [{"valor": "0.30", "codigo": "2", "baseImponible": "2.00", "codigoPorcentaje": "4"}]}, "totalSinImpuestos": "2.00", "valorModificacion": "2.30", "dirEstablecimiento": "PORTOVIEJO", "obligadoContabilidad": "NO", "razonSocialComprador": "CRISTHIAN ROMERO", "fechaEmisionDocSustento": "08/08/2026", "identificacionComprador": "1312838392", "tipoIdentificacionComprador": "05"}, "resumenImpuestos": [{"valor": "0.30", "tarifa": "15", "baseImponible": "2.00"}], "factura_referencia": "323611ef-75f3-4ea6-8045-ee0a48526a7a"}	1312838392001/notas_credito/0808202604131283839200110010010000000481741124719.xml	\N	{"estado": "DEVUELTA", "comprobantes": {"comprobante": {"mensajes": {"mensaje": {"tipo": "ERROR", "mensaje": "ARCHIVO NO CUMPLE ESTRUCTURA XML", "identificador": "35", "informacionAdicional": "Se encontró el siguiente error en la estructura del comprobante: cvc-complex-type.2.4.a: Invalid content was found starting with element 'codigoPrincipal'. One of '{codigoInterno, codigoAdicional, descripcion}' is expected.."}}, "claveAcceso": "0808202604131283839200110010010000000481741124719"}}}	\N	\N	\N	\N	2026-08-08 17:41:19.01793+00	\N	web	04	323611ef-75f3-4ea6-8045-ee0a48526a7a
e9d8c059-8d8e-4ffc-b76c-e255db9b899f	20	16	\N	0408202601131283839200110010010000000222838108618	000000022	001-001-000000022	2026-08-04	AUTORIZADO	9999999999999	CONSUMIDOR FINAL	\N	6.35	3.00	3.00	0.35	{"@id": "comprobante", "@version": "1.1.0", "detalles": {"detalle": [{"cantidad": "1.000000", "descuento": "0.00", "impuestos": {"impuesto": {"valor": "0.05", "codigo": "2", "tarifa": "5", "baseImponible": "1.00", "codigoPorcentaje": "5"}}, "descripcion": "IVA 5", "precioUnitario": "1.000000", "codigoPrincipal": "S/C", "precioTotalSinImpuesto": "1.00"}, {"cantidad": "1.000000", "descuento": "0.00", "impuestos": {"impuesto": {"valor": "0.30", "codigo": "2", "tarifa": "15", "baseImponible": "2.00", "codigoPorcentaje": "4"}}, "descripcion": "IVA 15", "precioUnitario": "2.000000", "codigoPrincipal": "S/C", "precioTotalSinImpuesto": "2.00"}, {"cantidad": "1.000000", "descuento": "0.00", "impuestos": {"impuesto": {"valor": "0.00", "codigo": "2", "tarifa": "0", "baseImponible": "3.00", "codigoPorcentaje": "0"}}, "descripcion": "CERO", "precioUnitario": "3.000000", "codigoPrincipal": "S/C", "precioTotalSinImpuesto": "3.00"}, {"cantidad": "1.000000", "descuento": "0.00", "impuestos": {"impuesto": {"valor": "0.00", "codigo": "2", "tarifa": "15", "baseImponible": "0.00", "codigoPorcentaje": "4"}}, "descripcion": "CUANTO", "precioUnitario": "0.000000", "codigoPrincipal": "S/C", "precioTotalSinImpuesto": "0.00"}]}, "infoFactura": {"pagos": {"pago": [{"plazo": "0", "total": "6.35", "formaPago": "01", "unidadTiempo": "dias"}]}, "moneda": "DOLAR", "propina": "0.00", "fechaEmision": "04/08/2026", "importeTotal": "6.35", "totalDescuento": "0.00", "totalConImpuestos": {"totalImpuesto": [{"valor": "0.05", "codigo": "2", "baseImponible": "1.00", "codigoPorcentaje": "5"}, {"valor": "0.30", "codigo": "2", "baseImponible": "2.00", "codigoPorcentaje": "4"}, {"valor": "0.00", "codigo": "2", "baseImponible": "3.00", "codigoPorcentaje": "0"}]}, "totalSinImpuestos": "6.00", "dirEstablecimiento": "PORTOVIEJO", "obligadoContabilidad": "NO", "razonSocialComprador": "CONSUMIDOR FINAL", "identificacionComprador": "9999999999999", "tipoIdentificacionComprador": "07"}, "infoAdicional": {"campoAdicional": [{"#text": "1312838392001 (kipu.ec)", "@nombre": "Proveedor"}, {"#text": "1312838392001 (kipu.ec)", "@nombre": "Proveedor"}]}, "infoTributaria": {"ruc": "1312838392001", "estab": "001", "codDoc": "01", "ptoEmi": "001", "ambiente": 1, "dirMatriz": "PORTOVIEJO", "secuencial": "000000022", "claveAcceso": "0408202601131283839200110010010000000222838108618", "razonSocial": "ROMERO GARCIA CRISTHIAN ANDRES", "tipoEmision": "1", "nombreComercial": "ROMERO GARCIA CRISTHIAN ANDRES"}, "resumenImpuestos": [{"valor": "0.05", "tarifa": "5", "baseImponible": "1.00"}, {"valor": "0.30", "tarifa": "15", "baseImponible": "2.00"}, {"valor": "0.00", "tarifa": "0", "baseImponible": "3.00"}]}	1312838392001/facturas/0408202601131283839200110010010000000222838108618.xml	\N	\N	2026-08-04 15:38:31.973913+00	2026-08-04 15:38:33+00	\N	\N	2026-08-04 15:38:30.850796+00	\N	web	01	\N
79308eab-9df0-4a1d-a798-903a384345d2	20	16	\N	0408202601131283839200110010010000000230151108815	000000023	001-001-000000023	2026-08-04	AUTORIZADO	9999999999999	CONSUMIDOR FINAL	\N	6.35	3.00	3.00	0.35	{"@id": "comprobante", "@version": "1.1.0", "detalles": {"detalle": [{"cantidad": "1.000000", "descuento": "0.00", "impuestos": {"impuesto": {"valor": "0.05", "codigo": "2", "tarifa": "5", "baseImponible": "1.00", "codigoPorcentaje": "5"}}, "descripcion": "IVA 5", "precioUnitario": "1.000000", "codigoPrincipal": "S/C", "precioTotalSinImpuesto": "1.00"}, {"cantidad": "1.000000", "descuento": "0.00", "impuestos": {"impuesto": {"valor": "0.30", "codigo": "2", "tarifa": "15", "baseImponible": "2.00", "codigoPorcentaje": "4"}}, "descripcion": "IVA 15", "precioUnitario": "2.000000", "codigoPrincipal": "S/C", "precioTotalSinImpuesto": "2.00"}, {"cantidad": "1.000000", "descuento": "0.00", "impuestos": {"impuesto": {"valor": "0.00", "codigo": "2", "tarifa": "0", "baseImponible": "3.00", "codigoPorcentaje": "0"}}, "descripcion": "CERO", "precioUnitario": "3.000000", "codigoPrincipal": "S/C", "precioTotalSinImpuesto": "3.00"}, {"cantidad": "1.000000", "descuento": "0.00", "impuestos": {"impuesto": {"valor": "0.00", "codigo": "2", "tarifa": "15", "baseImponible": "0.00", "codigoPorcentaje": "4"}}, "descripcion": "CUANTO", "precioUnitario": "0.000000", "codigoPrincipal": "S/C", "precioTotalSinImpuesto": "0.00"}]}, "infoFactura": {"pagos": {"pago": [{"plazo": "0", "total": "6.35", "formaPago": "01", "unidadTiempo": "dias"}]}, "moneda": "DOLAR", "propina": "0.00", "fechaEmision": "04/08/2026", "importeTotal": "6.35", "totalDescuento": "0.00", "totalConImpuestos": {"totalImpuesto": [{"valor": "0.05", "codigo": "2", "baseImponible": "1.00", "codigoPorcentaje": "5"}, {"valor": "0.30", "codigo": "2", "baseImponible": "2.00", "codigoPorcentaje": "4"}, {"valor": "0.00", "codigo": "2", "baseImponible": "3.00", "codigoPorcentaje": "0"}]}, "totalSinImpuestos": "6.00", "dirEstablecimiento": "PORTOVIEJO", "obligadoContabilidad": "NO", "razonSocialComprador": "CONSUMIDOR FINAL", "identificacionComprador": "9999999999999", "tipoIdentificacionComprador": "07"}, "infoAdicional": {"campoAdicional": [{"#text": "1312838392001 (kipu.ec)", "@nombre": "Proveedor"}, {"#text": "1312838392001 (kipu.ec)", "@nombre": "Proveedor"}, {"#text": "1312838392001 (kipu.ec)", "@nombre": "Proveedor"}]}, "infoTributaria": {"ruc": "1312838392001", "estab": "001", "codDoc": "01", "ptoEmi": "001", "ambiente": 1, "dirMatriz": "PORTOVIEJO", "secuencial": "000000023", "claveAcceso": "0408202601131283839200110010010000000230151108815", "razonSocial": "ROMERO GARCIA CRISTHIAN ANDRES", "tipoEmision": "1", "nombreComercial": "ROMERO GARCIA CRISTHIAN ANDRES"}, "resumenImpuestos": [{"valor": "0.05", "tarifa": "5", "baseImponible": "1.00"}, {"valor": "0.30", "tarifa": "15", "baseImponible": "2.00"}, {"valor": "0.00", "tarifa": "0", "baseImponible": "3.00"}]}	1312838392001/facturas/0408202601131283839200110010010000000230151108815.xml	\N	\N	2026-08-04 15:51:05.101043+00	2026-08-04 15:51:06+00	\N	\N	2026-08-04 15:51:04.104757+00	\N	web	01	\N
ee36f9f4-1158-41f0-8fca-4a7b47987fa8	20	16	ac248cd7-7339-4992-b691-9c31aca4d551	0408202601131283839200110010010000000240206159916	000000024	001-001-000000024	2026-08-04	AUTORIZADO	1312838392	CRISTHIAN ROMERO		1.15	1.00	0.00	0.15	{"@id": "comprobante", "@version": "1.1.0", "detalles": {"detalle": [{"cantidad": "1.000000", "descuento": "0.00", "impuestos": {"impuesto": {"valor": "0.15", "codigo": "2", "tarifa": "15", "baseImponible": "1.00", "codigoPorcentaje": "4"}}, "descripcion": "EEE", "precioUnitario": "1.000000", "codigoPrincipal": "S/C", "precioTotalSinImpuesto": "1.00"}]}, "infoFactura": {"pagos": {"pago": [{"plazo": "0", "total": "1.15", "formaPago": "01", "unidadTiempo": "dias"}]}, "moneda": "DOLAR", "propina": "0.00", "fechaEmision": "04/08/2026", "importeTotal": "1.15", "totalDescuento": "0.00", "totalConImpuestos": {"totalImpuesto": [{"valor": "0.15", "codigo": "2", "baseImponible": "1.00", "codigoPorcentaje": "4"}]}, "totalSinImpuestos": "1.00", "dirEstablecimiento": "PORTOVIEJO", "obligadoContabilidad": "NO", "razonSocialComprador": "CRISTHIAN ROMERO", "identificacionComprador": "1312838392", "tipoIdentificacionComprador": "05"}, "infoAdicional": {"campoAdicional": [{"#text": "1312838392001 (kipu.ec)", "@nombre": "Proveedor"}]}, "infoTributaria": {"ruc": "1312838392001", "estab": "001", "codDoc": "01", "ptoEmi": "001", "ambiente": 1, "dirMatriz": "PORTOVIEJO", "secuencial": "000000024", "claveAcceso": "0408202601131283839200110010010000000240206159916", "razonSocial": "ROMERO GARCIA CRISTHIAN ANDRES", "tipoEmision": "1", "nombreComercial": "ROMERO GARCIA CRISTHIAN ANDRES"}, "resumenImpuestos": [{"valor": "0.15", "tarifa": "15", "baseImponible": "1.00"}]}	1312838392001/facturas/0408202601131283839200110010010000000240206159916.xml	\N	\N	2026-08-04 20:06:05.766711+00	2026-08-04 20:06:08+00	\N	\N	2026-08-04 20:06:04.74311+00	\N	web	01	\N
59a723f9-8d0c-42b5-82aa-68800194fdff	20	16	ac248cd7-7339-4992-b691-9c31aca4d551	0808202604131283839200110010010000000491656129219	000000049	001-001-000000049	2026-08-08	AUTORIZADO	1312838392	CRISTHIAN ROMERO	cristhianromero19@outlook.com	2.30	2.00	0.00	0.30	{"@id": "comprobante", "@version": "1.1.0", "detalles": {"detalle": [{"cantidad": "1.000000", "descuento": "0.00", "impuestos": {"impuesto": {"valor": "0.30", "codigo": "2", "tarifa": "15", "baseImponible": "2.00", "codigoPorcentaje": "4"}}, "descripcion": "WWW", "codigoInterno": "1", "precioUnitario": "2.000000", "precioTotalSinImpuesto": "2.00"}]}, "infoAdicional": {"campoAdicional": [{"#text": "1312838392001 (kipu.ec)", "@nombre": "Proveedor"}]}, "infoTributaria": {"ruc": "1312838392001", "estab": "001", "codDoc": "04", "ptoEmi": "001", "ambiente": 1, "dirMatriz": "PORTOVIEJO", "secuencial": "000000049", "claveAcceso": "0808202604131283839200110010010000000491656129219", "razonSocial": "ROMERO GARCIA CRISTHIAN ANDRES", "tipoEmision": "1", "nombreComercial": "ROMERO GARCIA CRISTHIAN ANDRES"}, "infoNotaCredito": {"motivo": "DEVEDE", "fechaEmision": "08/08/2026", "codDocModificado": "01", "numDocModificado": "001-001-000000043", "totalConImpuestos": {"totalImpuesto": [{"valor": "0.30", "codigo": "2", "baseImponible": "2.00", "codigoPorcentaje": "4"}]}, "totalSinImpuestos": "2.00", "valorModificacion": "2.30", "dirEstablecimiento": "PORTOVIEJO", "obligadoContabilidad": "NO", "razonSocialComprador": "CRISTHIAN ROMERO", "fechaEmisionDocSustento": "08/08/2026", "identificacionComprador": "1312838392", "tipoIdentificacionComprador": "05"}, "resumenImpuestos": [{"valor": "0.30", "tarifa": "15", "baseImponible": "2.00"}], "factura_referencia": "323611ef-75f3-4ea6-8045-ee0a48526a7a"}	1312838392001/notas_credito/0808202604131283839200110010010000000491656129219.xml	\N	\N	2026-08-08 17:56:19.508988+00	2026-08-08 17:56:20+00	\N	\N	2026-08-08 17:56:18.435532+00	\N	web	04	323611ef-75f3-4ea6-8045-ee0a48526a7a
7eefa5e0-7206-436c-9288-e82b8bb550f6	20	16	ac248cd7-7339-4992-b691-9c31aca4d551	0408202601131283839200110010010000000261647189516	000000026	001-001-000000026	2026-08-04	AUTORIZADO	1312838392	CRISTHIAN ROMERO	cristhianromero19@outlook.com	3.15	1.00	2.00	0.15	{"@id": "comprobante", "@version": "1.1.0", "detalles": {"detalle": [{"cantidad": "1.000000", "descuento": "0.00", "impuestos": {"impuesto": {"valor": "0.15", "codigo": "2", "tarifa": "15", "baseImponible": "1.00", "codigoPorcentaje": "4"}}, "descripcion": "AAA", "precioUnitario": "1.000000", "codigoPrincipal": "S/C", "precioTotalSinImpuesto": "1.00"}, {"cantidad": "1.000000", "descuento": "0.00", "impuestos": {"impuesto": {"valor": "0.00", "codigo": "2", "tarifa": "0", "baseImponible": "2.00", "codigoPorcentaje": "0"}}, "descripcion": "BBB", "precioUnitario": "2.000000", "codigoPrincipal": "S/C", "precioTotalSinImpuesto": "2.00"}]}, "infoFactura": {"pagos": {"pago": [{"plazo": "0", "total": "3.15", "formaPago": "01", "unidadTiempo": "dias"}]}, "moneda": "DOLAR", "propina": "0.00", "fechaEmision": "04/08/2026", "importeTotal": "3.15", "totalDescuento": "0.00", "totalConImpuestos": {"totalImpuesto": [{"valor": "0.15", "codigo": "2", "baseImponible": "1.00", "codigoPorcentaje": "4"}, {"valor": "0.00", "codigo": "2", "baseImponible": "2.00", "codigoPorcentaje": "0"}]}, "totalSinImpuestos": "3.00", "dirEstablecimiento": "PORTOVIEJO", "obligadoContabilidad": "NO", "razonSocialComprador": "CRISTHIAN ROMERO", "identificacionComprador": "1312838392", "tipoIdentificacionComprador": "05"}, "infoAdicional": {"campoAdicional": [{"#text": "1312838392001 (kipu.ec)", "@nombre": "Proveedor"}]}, "infoTributaria": {"ruc": "1312838392001", "estab": "001", "codDoc": "01", "ptoEmi": "001", "ambiente": 1, "dirMatriz": "PORTOVIEJO", "secuencial": "000000026", "claveAcceso": "0408202601131283839200110010010000000261647189516", "razonSocial": "ROMERO GARCIA CRISTHIAN ANDRES", "tipoEmision": "1", "nombreComercial": "ROMERO GARCIA CRISTHIAN ANDRES"}, "resumenImpuestos": [{"valor": "0.15", "tarifa": "15", "baseImponible": "1.00"}, {"valor": "0.00", "tarifa": "0", "baseImponible": "2.00"}]}	1312838392001/facturas/0408202601131283839200110010010000000261647189516.xml	\N	\N	2026-08-04 23:47:18.206123+00	2026-08-04 23:47:19+00	\N	\N	2026-08-04 23:47:17.690437+00	\N	web	01	\N
f32f4b49-e217-418a-b2e3-981fbfe811f2	20	17	c0630cff-8a2e-454c-ba23-a5684d2e273c	1008202601131283839200110010050000000081447006417	000000008	001-005-000000008	2026-08-10	AUTORIZADO	1312838392001	ROMERO GARCIA CRISTHIAN ANDRES	cristhianromero19@outlook.com	8.03	6.98	0.00	1.05	{"@id": "comprobante", "@version": "1.1.0", "detalles": {"detalle": [{"cantidad": "1.000000", "descuento": "0.00", "impuestos": {"impuesto": {"valor": "1.05", "codigo": "2", "tarifa": "15", "baseImponible": "6.98", "codigoPorcentaje": "4"}}, "descripcion": "RECARGA DE 50 CRÉDITOS DE EMISIÓN — KIPU", "precioUnitario": "6.980000", "codigoPrincipal": "S/C", "precioTotalSinImpuesto": "6.98"}]}, "infoFactura": {"pagos": {"pago": [{"plazo": "0", "total": "8.03", "formaPago": "16", "unidadTiempo": "dias"}]}, "moneda": "DOLAR", "propina": "0.00", "fechaEmision": "10/08/2026", "importeTotal": "8.03", "totalDescuento": "0.00", "totalConImpuestos": {"totalImpuesto": [{"valor": "1.05", "codigo": "2", "baseImponible": "6.98", "codigoPorcentaje": "4"}]}, "totalSinImpuestos": "6.98", "dirEstablecimiento": "PORTOVIEJO", "obligadoContabilidad": "NO", "razonSocialComprador": "ROMERO GARCIA CRISTHIAN ANDRES", "identificacionComprador": "1312838392001", "tipoIdentificacionComprador": "04"}, "infoAdicional": {"campoAdicional": [{"#text": "50 créditos", "@nombre": "Plan"}, {"#text": "pi_3U2lGgGn1ILBomfh0", "@nombre": "Referencia"}, {"#text": "1312838392001 (kipu.ec)", "@nombre": "Proveedor"}]}, "infoTributaria": {"ruc": "1312838392001", "estab": "001", "codDoc": "01", "ptoEmi": "005", "ambiente": 1, "dirMatriz": "PORTOVIEJO", "secuencial": "000000008", "claveAcceso": "1008202601131283839200110010050000000081447006417", "razonSocial": "ROMERO GARCIA CRISTHIAN ANDRES", "tipoEmision": "1", "nombreComercial": "ROMERO GARCIA CRISTHIAN ANDRES"}, "resumenImpuestos": [{"valor": "1.05", "tarifa": "15", "baseImponible": "6.98"}]}	1312838392001/facturas/1008202601131283839200110010050000000081447006417.xml	\N	\N	2026-08-10 05:47:15.664533+00	2026-08-10 05:47:16+00	\N	\N	2026-08-10 05:47:14.134091+00	\N	web	01	\N
36bed128-97c6-4329-af9a-e028182f1e25	20	16	\N	1008202601131283839200110010010000000501325086017	000000050	001-001-000000050	2026-08-10	AUTORIZADO	1712345678	JUAN CARLOS PÉREZ	cristhianromero19@outlook.com	166.75	145.00	0.00	21.75	{"@id": "comprobante", "@version": "1.1.0", "detalles": {"detalle": [{"cantidad": "1.000000", "descuento": "0.00", "impuestos": {"impuesto": {"valor": "15.00", "codigo": "2", "tarifa": "15", "baseImponible": "100.00", "codigoPorcentaje": "4"}}, "descripcion": "SERVICIO DE DESARROLLO WEB", "precioUnitario": "100.000000", "codigoPrincipal": "PROD-001", "precioTotalSinImpuesto": "100.00"}, {"cantidad": "3.000000", "descuento": "0.00", "impuestos": {"impuesto": {"valor": "6.75", "codigo": "2", "tarifa": "15", "baseImponible": "45.00", "codigoPorcentaje": "4"}}, "descripcion": "HOSTING MENSUAL", "precioUnitario": "15.000000", "codigoPrincipal": "PROD-002", "precioTotalSinImpuesto": "45.00"}]}, "infoFactura": {"pagos": {"pago": [{"plazo": "0", "total": "166.75", "formaPago": "01", "unidadTiempo": "dias"}]}, "moneda": "DOLAR", "propina": "0.00", "fechaEmision": "10/08/2026", "importeTotal": "166.75", "totalDescuento": "0.00", "totalConImpuestos": {"totalImpuesto": [{"valor": "21.75", "codigo": "2", "baseImponible": "145.00", "codigoPorcentaje": "4"}]}, "totalSinImpuestos": "145.00", "dirEstablecimiento": "PORTOVIEJO", "obligadoContabilidad": "NO", "razonSocialComprador": "JUAN CARLOS PÉREZ", "identificacionComprador": "1712345678", "tipoIdentificacionComprador": "05"}, "infoAdicional": {"campoAdicional": [{"#text": "ORD-2026-001", "@nombre": "Referencia"}, {"#text": "Juan Pérez", "@nombre": "Vendedor"}, {"#text": "1312838392001 (kipu.ec)", "@nombre": "Proveedor"}]}, "infoTributaria": {"ruc": "1312838392001", "estab": "001", "codDoc": "01", "ptoEmi": "001", "ambiente": 1, "dirMatriz": "PORTOVIEJO", "secuencial": "000000050", "claveAcceso": "1008202601131283839200110010010000000501325086017", "razonSocial": "ROMERO GARCIA CRISTHIAN ANDRES", "tipoEmision": "1", "nombreComercial": "ROMERO GARCIA CRISTHIAN ANDRES"}, "resumenImpuestos": [{"valor": "21.75", "tarifa": "15", "baseImponible": "145.00"}]}	1312838392001/facturas/1008202601131283839200110010010000000501325086017.xml	\N	\N	2026-08-10 13:25:14.879964+00	2026-08-10 13:25:15+00	\N	\N	2026-08-10 13:25:12.861153+00	8	api	01	\N
6a8b973e-17fd-4eca-b854-a5c8438adea6	20	17	\N	0208202601131283839200110010050000000020332203215	000000002	001-005-000000002	2026-08-02	AUTORIZADO	9999999999999	CONSUMIDOR FINAL	\N	0.12	0.10	0.00	0.02	{"@id": "comprobante", "@version": "1.1.0", "detalles": {"detalle": [{"cantidad": "1.000000", "descuento": "0.00", "impuestos": {"impuesto": {"valor": "0.02", "codigo": "2", "tarifa": "15", "baseImponible": "0.10", "codigoPorcentaje": "4"}}, "descripcion": "AAA", "precioUnitario": "0.100000", "codigoPrincipal": "S/C", "precioTotalSinImpuesto": "0.10"}]}, "infoFactura": {"pagos": {"pago": [{"plazo": "0", "total": "0.12", "formaPago": "01", "unidadTiempo": "dias"}]}, "moneda": "DOLAR", "propina": "0.00", "fechaEmision": "02/08/2026", "importeTotal": "0.12", "totalDescuento": "0.00", "totalConImpuestos": {"totalImpuesto": [{"valor": "0.02", "codigo": "2", "baseImponible": "0.10", "codigoPorcentaje": "4"}]}, "totalSinImpuestos": "0.10", "dirEstablecimiento": "PORTOVIEJO", "obligadoContabilidad": "NO", "razonSocialComprador": "CONSUMIDOR FINAL", "identificacionComprador": "9999999999999", "tipoIdentificacionComprador": "07"}, "infoAdicional": {"campoAdicional": [{"#text": "1312838392001", "@nombre": "PROVEEDOR_SISTEMA_INFORMATICO"}]}, "infoTributaria": {"ruc": "1312838392001", "estab": "001", "codDoc": "01", "ptoEmi": "005", "ambiente": 1, "dirMatriz": "PORTOVIEJO", "secuencial": "000000002", "claveAcceso": "0208202601131283839200110010050000000020332203215", "razonSocial": "ROMERO GARCIA CRISTHIAN ANDRES", "tipoEmision": "1", "nombreComercial": "ROMERO GARCIA CRISTHIAN ANDRES"}}	1312838392001/facturas/0208202601131283839200110010050000000020332203215.xml	\N	\N	2026-08-03 18:53:07.48983+00	2026-08-03 18:53:08+00	1	2026-08-03 18:37:18.652635+00	2026-08-03 01:32:04.435754+00	\N	web	01	\N
28bd7572-44df-4f53-867c-deca18c5180b	20	16	\N	0608202601131283839200110010010000000270050107614	000000027	001-001-000000027	2026-08-06	AUTORIZADO	9999999999999	CONSUMIDOR FINAL	\N	2.30	2.00	0.00	0.30	{"@id": "comprobante", "@version": "1.1.0", "detalles": {"detalle": [{"cantidad": "1.000000", "descuento": "0.00", "impuestos": {"impuesto": {"valor": "0.30", "codigo": "2", "tarifa": "15", "baseImponible": "2.00", "codigoPorcentaje": "4"}}, "descripcion": "WWW", "precioUnitario": "2.000000", "codigoPrincipal": "S/C", "precioTotalSinImpuesto": "2.00"}]}, "infoFactura": {"pagos": {"pago": [{"plazo": "0", "total": "2.30", "formaPago": "01", "unidadTiempo": "dias"}]}, "moneda": "DOLAR", "propina": "0.00", "fechaEmision": "06/08/2026", "importeTotal": "2.30", "totalDescuento": "0.00", "totalConImpuestos": {"totalImpuesto": [{"valor": "0.30", "codigo": "2", "baseImponible": "2.00", "codigoPorcentaje": "4"}]}, "totalSinImpuestos": "2.00", "dirEstablecimiento": "PORTOVIEJO", "obligadoContabilidad": "NO", "razonSocialComprador": "CONSUMIDOR FINAL", "identificacionComprador": "9999999999999", "tipoIdentificacionComprador": "07"}, "infoAdicional": {"campoAdicional": [{"#text": "1312838392001 (kipu.ec)", "@nombre": "Proveedor"}]}, "infoTributaria": {"ruc": "1312838392001", "estab": "001", "codDoc": "01", "ptoEmi": "001", "ambiente": 1, "dirMatriz": "PORTOVIEJO", "secuencial": "000000027", "claveAcceso": "0608202601131283839200110010010000000270050107614", "razonSocial": "ROMERO GARCIA CRISTHIAN ANDRES", "tipoEmision": "1", "nombreComercial": "ROMERO GARCIA CRISTHIAN ANDRES"}, "resumenImpuestos": [{"valor": "0.30", "tarifa": "15", "baseImponible": "2.00"}]}	1312838392001/facturas/0608202601131283839200110010010000000270050107614.xml	\N	\N	2026-08-06 15:50:02.162195+00	2026-08-06 15:50:04+00	\N	\N	2026-08-06 15:50:01.637214+00	\N	web	01	\N
ba288bef-97eb-4601-850c-f8478516c474	20	16	\N	0608202601131283839200110010010000000281314117712	000000028	001-001-000000028	2026-08-06	AUTORIZADO	9999999999999	CONSUMIDOR FINAL	\N	2.30	2.00	0.00	0.30	{"@id": "comprobante", "@version": "1.1.0", "detalles": {"detalle": [{"cantidad": "1.000000", "descuento": "0.00", "impuestos": {"impuesto": {"valor": "0.30", "codigo": "2", "tarifa": "15", "baseImponible": "2.00", "codigoPorcentaje": "4"}}, "descripcion": "WWW", "precioUnitario": "2.000000", "codigoPrincipal": "S/C", "precioTotalSinImpuesto": "2.00"}]}, "infoFactura": {"pagos": {"pago": [{"plazo": "0", "total": "2.30", "formaPago": "01", "unidadTiempo": "dias"}]}, "moneda": "DOLAR", "propina": "0.00", "fechaEmision": "06/08/2026", "importeTotal": "2.30", "totalDescuento": "0.00", "totalConImpuestos": {"totalImpuesto": [{"valor": "0.30", "codigo": "2", "baseImponible": "2.00", "codigoPorcentaje": "4"}]}, "totalSinImpuestos": "2.00", "dirEstablecimiento": "PORTOVIEJO", "obligadoContabilidad": "NO", "razonSocialComprador": "CONSUMIDOR FINAL", "identificacionComprador": "9999999999999", "tipoIdentificacionComprador": "07"}, "infoAdicional": {"campoAdicional": [{"#text": "1312838392001 (kipu.ec)", "@nombre": "Proveedor"}]}, "infoTributaria": {"ruc": "1312838392001", "estab": "001", "codDoc": "01", "ptoEmi": "001", "ambiente": 1, "dirMatriz": "PORTOVIEJO", "secuencial": "000000028", "claveAcceso": "0608202601131283839200110010010000000281314117712", "razonSocial": "ROMERO GARCIA CRISTHIAN ANDRES", "tipoEmision": "1", "nombreComercial": "ROMERO GARCIA CRISTHIAN ANDRES"}, "resumenImpuestos": [{"valor": "0.30", "tarifa": "15", "baseImponible": "2.00"}]}	1312838392001/facturas/0608202601131283839200110010010000000281314117712.xml	\N	\N	2026-08-06 16:14:14.686094+00	2026-08-06 16:14:15+00	\N	\N	2026-08-06 16:14:14.305821+00	\N	web	01	\N
fe5e8ea6-14a7-46aa-9411-7c60431b9554	20	16	\N	0308202601131283839200110010010000000152455112015	000000015	001-001-000000015	2026-08-03	AUTORIZADO	9999999999999	CONSUMIDOR FINAL	\N	0.12	0.10	0.00	0.02	{"@id": "comprobante", "@version": "1.1.0", "detalles": {"detalle": [{"cantidad": "1.000000", "descuento": "0.00", "impuestos": {"impuesto": {"valor": "0.02", "codigo": "2", "tarifa": "15", "baseImponible": "0.10", "codigoPorcentaje": "4"}}, "descripcion": "WWW", "precioUnitario": "0.100000", "codigoPrincipal": "S/C", "precioTotalSinImpuesto": "0.10"}]}, "infoFactura": {"pagos": {"pago": [{"plazo": "0", "total": "0.12", "formaPago": "01", "unidadTiempo": "dias"}]}, "moneda": "DOLAR", "propina": "0.00", "fechaEmision": "03/08/2026", "importeTotal": "0.12", "totalDescuento": "0.00", "totalConImpuestos": {"totalImpuesto": [{"valor": "0.02", "codigo": "2", "baseImponible": "0.10", "codigoPorcentaje": "4"}]}, "totalSinImpuestos": "0.10", "dirEstablecimiento": "PORTOVIEJO", "obligadoContabilidad": "NO", "razonSocialComprador": "CONSUMIDOR FINAL", "identificacionComprador": "9999999999999", "tipoIdentificacionComprador": "07"}, "infoTributaria": {"ruc": "1312838392001", "estab": "001", "codDoc": "01", "ptoEmi": "001", "ambiente": 1, "dirMatriz": "PORTOVIEJO", "secuencial": "000000015", "claveAcceso": "0308202601131283839200110010010000000152455112015", "razonSocial": "ROMERO GARCIA CRISTHIAN ANDRES", "tipoEmision": "1", "nombreComercial": "ROMERO GARCIA CRISTHIAN ANDRES"}}	1312838392001/facturas/0308202601131283839200110010010000000152455112015.xml	\N	\N	2026-08-03 18:53:04.752882+00	2026-08-03 18:53:07+00	1	2026-08-03 18:37:14.775692+00	2026-08-03 16:55:25.851106+00	\N	web	01	\N
957d9e37-8378-4276-aec4-c5e326d2be26	20	16	\N	0308202601131283839200110010010000000163602122317	000000016	001-001-000000016	2026-08-03	AUTORIZADO	9999999999999	CONSUMIDOR FINAL	\N	0.12	0.10	0.00	0.02	{"@id": "comprobante", "@version": "1.1.0", "detalles": {"detalle": [{"cantidad": "1.000000", "descuento": "0.00", "impuestos": {"impuesto": {"valor": "0.02", "codigo": "2", "tarifa": "15", "baseImponible": "0.10", "codigoPorcentaje": "4"}}, "descripcion": "FDFDS", "precioUnitario": "0.100000", "codigoPrincipal": "S/C", "precioTotalSinImpuesto": "0.10"}]}, "infoFactura": {"pagos": {"pago": [{"plazo": "0", "total": "0.12", "formaPago": "01", "unidadTiempo": "dias"}]}, "moneda": "DOLAR", "propina": "0.00", "fechaEmision": "03/08/2026", "importeTotal": "0.12", "totalDescuento": "0.00", "totalConImpuestos": {"totalImpuesto": [{"valor": "0.02", "codigo": "2", "baseImponible": "0.10", "codigoPorcentaje": "4"}]}, "totalSinImpuestos": "0.10", "dirEstablecimiento": "PORTOVIEJO", "obligadoContabilidad": "NO", "razonSocialComprador": "CONSUMIDOR FINAL", "identificacionComprador": "9999999999999", "tipoIdentificacionComprador": "07"}, "infoTributaria": {"ruc": "1312838392001", "estab": "001", "codDoc": "01", "ptoEmi": "001", "ambiente": 1, "dirMatriz": "PORTOVIEJO", "secuencial": "000000016", "claveAcceso": "0308202601131283839200110010010000000163602122317", "razonSocial": "ROMERO GARCIA CRISTHIAN ANDRES", "tipoEmision": "1", "nombreComercial": "ROMERO GARCIA CRISTHIAN ANDRES"}}	1312838392001/facturas/0308202601131283839200110010010000000163602122317.xml	\N	\N	2026-08-03 18:09:11.102403+00	2026-08-03 18:09:12+00	5	2026-08-03 17:17:36.596534+00	2026-08-03 17:02:37.468102+00	\N	web	01	\N
b3e88ce9-001c-4e89-8d98-ffa1cf029194	20	17	c0630cff-8a2e-454c-ba23-a5684d2e273c	1008202601131283839200110010050000000095256004611	000000009	001-005-000000009	2026-08-10	AUTORIZADO	1312838392001	ROMERO GARCIA CRISTHIAN ANDRES	cristhianromero19@outlook.com	8.03	6.98	0.00	1.05	{"@id": "comprobante", "@version": "1.1.0", "detalles": {"detalle": [{"cantidad": "1.000000", "descuento": "0.00", "impuestos": {"impuesto": {"valor": "1.05", "codigo": "2", "tarifa": "15", "baseImponible": "6.98", "codigoPorcentaje": "4"}}, "descripcion": "RECARGA DE 50 CRÉDITOS DE EMISIÓN — KIPU", "precioUnitario": "6.980000", "codigoPrincipal": "S/C", "precioTotalSinImpuesto": "6.98"}]}, "infoFactura": {"pagos": {"pago": [{"plazo": "0", "total": "8.03", "formaPago": "16", "unidadTiempo": "dias"}]}, "moneda": "DOLAR", "propina": "0.00", "fechaEmision": "10/08/2026", "importeTotal": "8.03", "totalDescuento": "0.00", "totalConImpuestos": {"totalImpuesto": [{"valor": "1.05", "codigo": "2", "baseImponible": "6.98", "codigoPorcentaje": "4"}]}, "totalSinImpuestos": "6.98", "dirEstablecimiento": "PORTOVIEJO", "obligadoContabilidad": "NO", "razonSocialComprador": "ROMERO GARCIA CRISTHIAN ANDRES", "identificacionComprador": "1312838392001", "tipoIdentificacionComprador": "04"}, "infoAdicional": {"campoAdicional": [{"#text": "50 créditos", "@nombre": "Plan"}, {"#text": "pi_3U2lGgGn1ILBomfh0", "@nombre": "Referencia"}, {"#text": "1312838392001 (kipu.ec)", "@nombre": "Proveedor"}]}, "infoTributaria": {"ruc": "1312838392001", "estab": "001", "codDoc": "01", "ptoEmi": "005", "ambiente": 1, "dirMatriz": "PORTOVIEJO", "secuencial": "000000009", "claveAcceso": "1008202601131283839200110010050000000095256004611", "razonSocial": "ROMERO GARCIA CRISTHIAN ANDRES", "tipoEmision": "1", "nombreComercial": "ROMERO GARCIA CRISTHIAN ANDRES"}, "resumenImpuestos": [{"valor": "1.05", "tarifa": "15", "baseImponible": "6.98"}]}	1312838392001/facturas/1008202601131283839200110010050000000095256004611.xml	\N	\N	2026-08-10 05:56:53.251775+00	2026-08-10 05:56:54+00	\N	\N	2026-08-10 05:56:51.783603+00	\N	web	01	\N
b6a20ce4-0d90-4c45-a561-bc718aff4dbe	20	16	\N	0308202601131283839200110010010000000175011125811	000000017	001-001-000000017	2026-08-03	AUTORIZADO	9999999999999	CONSUMIDOR FINAL	\N	0.12	0.10	0.00	0.02	{"@id": "comprobante", "@version": "1.1.0", "detalles": {"detalle": [{"cantidad": "1.000000", "descuento": "0.00", "impuestos": {"impuesto": {"valor": "0.02", "codigo": "2", "tarifa": "15", "baseImponible": "0.10", "codigoPorcentaje": "4"}}, "descripcion": "DDDD", "precioUnitario": "0.100000", "codigoPrincipal": "S/C", "precioTotalSinImpuesto": "0.10"}]}, "infoFactura": {"pagos": {"pago": [{"plazo": "0", "total": "0.12", "formaPago": "01", "unidadTiempo": "dias"}]}, "moneda": "DOLAR", "propina": "0.00", "fechaEmision": "03/08/2026", "importeTotal": "0.12", "totalDescuento": "0.00", "totalConImpuestos": {"totalImpuesto": [{"valor": "0.02", "codigo": "2", "baseImponible": "0.10", "codigoPorcentaje": "4"}]}, "totalSinImpuestos": "0.10", "dirEstablecimiento": "PORTOVIEJO", "obligadoContabilidad": "NO", "razonSocialComprador": "CONSUMIDOR FINAL", "identificacionComprador": "9999999999999", "tipoIdentificacionComprador": "07"}, "infoAdicional": {"campoAdicional": [{"#text": "1312838392001", "@nombre": "PROVEEDOR_SISTEMA_INFORMATICO"}]}, "infoTributaria": {"ruc": "1312838392001", "estab": "001", "codDoc": "01", "ptoEmi": "001", "ambiente": 1, "dirMatriz": "PORTOVIEJO", "secuencial": "000000017", "claveAcceso": "0308202601131283839200110010010000000175011125811", "razonSocial": "ROMERO GARCIA CRISTHIAN ANDRES", "tipoEmision": "1", "nombreComercial": "ROMERO GARCIA CRISTHIAN ANDRES"}}	1312838392001/facturas/0308202601131283839200110010010000000175011125811.xml	\N	\N	2026-08-03 18:09:06.203024+00	2026-08-03 18:09:07+00	2	2026-08-03 17:17:44.769253+00	2026-08-03 17:11:52.017128+00	\N	web	01	\N
1c943cb4-840e-461c-9843-a52d634fdb56	20	16	\N	0608202601131283839200110010010000000291325159110	000000029	001-001-000000029	2026-08-06	AUTORIZADO	9999999999999	CONSUMIDOR FINAL	\N	2.30	2.00	0.00	0.30	{"@id": "comprobante", "@version": "1.1.0", "detalles": {"detalle": [{"cantidad": "1.000000", "descuento": "0.00", "impuestos": {"impuesto": {"valor": "0.30", "codigo": "2", "tarifa": "15", "baseImponible": "2.00", "codigoPorcentaje": "4"}}, "descripcion": "WWW", "precioUnitario": "2.000000", "codigoPrincipal": "S/C", "precioTotalSinImpuesto": "2.00"}]}, "infoFactura": {"pagos": {"pago": [{"plazo": "0", "total": "2.30", "formaPago": "01", "unidadTiempo": "dias"}]}, "moneda": "DOLAR", "propina": "0.00", "fechaEmision": "06/08/2026", "importeTotal": "2.30", "totalDescuento": "0.00", "totalConImpuestos": {"totalImpuesto": [{"valor": "0.30", "codigo": "2", "baseImponible": "2.00", "codigoPorcentaje": "4"}]}, "totalSinImpuestos": "2.00", "dirEstablecimiento": "PORTOVIEJO", "obligadoContabilidad": "NO", "razonSocialComprador": "CONSUMIDOR FINAL", "identificacionComprador": "9999999999999", "tipoIdentificacionComprador": "07"}, "infoAdicional": {"campoAdicional": [{"#text": "1312838392001 (kipu.ec)", "@nombre": "Proveedor"}]}, "infoTributaria": {"ruc": "1312838392001", "estab": "001", "codDoc": "01", "ptoEmi": "001", "ambiente": 1, "dirMatriz": "PORTOVIEJO", "secuencial": "000000029", "claveAcceso": "0608202601131283839200110010010000000291325159110", "razonSocial": "ROMERO GARCIA CRISTHIAN ANDRES", "tipoEmision": "1", "nombreComercial": "ROMERO GARCIA CRISTHIAN ANDRES"}, "resumenImpuestos": [{"valor": "0.30", "tarifa": "15", "baseImponible": "2.00"}]}	1312838392001/facturas/0608202601131283839200110010010000000291325159110.xml	\N	\N	2026-08-06 20:25:14.18561+00	2026-08-06 20:25:15+00	\N	\N	2026-08-06 20:25:13.636004+00	\N	web	01	\N
5d0c4cdd-082c-41fa-a117-25106da23921	20	17	\N	0308202601131283839200110010050000000033213129316	000000003	001-005-000000003	2026-08-03	AUTORIZADO	9999999999999	CONSUMIDOR FINAL	\N	0.12	0.10	0.00	0.02	{"@id": "comprobante", "@version": "1.1.0", "detalles": {"detalle": [{"cantidad": "1.000000", "descuento": "0.00", "impuestos": {"impuesto": {"valor": "0.02", "codigo": "2", "tarifa": "15", "baseImponible": "0.10", "codigoPorcentaje": "4"}}, "descripcion": "CCC", "precioUnitario": "0.100000", "codigoPrincipal": "S/C", "precioTotalSinImpuesto": "0.10"}]}, "infoFactura": {"pagos": {"pago": [{"plazo": "0", "total": "0.12", "formaPago": "01", "unidadTiempo": "dias"}]}, "moneda": "DOLAR", "propina": "0.00", "fechaEmision": "03/08/2026", "importeTotal": "0.12", "totalDescuento": "0.00", "totalConImpuestos": {"totalImpuesto": [{"valor": "0.02", "codigo": "2", "baseImponible": "0.10", "codigoPorcentaje": "4"}]}, "totalSinImpuestos": "0.10", "dirEstablecimiento": "PORTOVIEJO", "obligadoContabilidad": "NO", "razonSocialComprador": "CONSUMIDOR FINAL", "identificacionComprador": "9999999999999", "tipoIdentificacionComprador": "07"}, "infoAdicional": {"campoAdicional": [{"#text": "1312838392001", "@nombre": "PROVEEDOR_SISTEMA_INFORMATICO"}]}, "infoTributaria": {"ruc": "1312838392001", "estab": "001", "codDoc": "01", "ptoEmi": "005", "ambiente": 1, "dirMatriz": "PORTOVIEJO", "secuencial": "000000003", "claveAcceso": "0308202601131283839200110010050000000033213129316", "razonSocial": "ROMERO GARCIA CRISTHIAN ANDRES", "tipoEmision": "1", "nombreComercial": "ROMERO GARCIA CRISTHIAN ANDRES"}}	1312838392001/facturas/0308202601131283839200110010050000000033213129316.xml	\N	\N	2026-08-03 18:08:54.571402+00	2026-08-03 18:08:56+00	1	2026-08-03 17:16:32.301825+00	2026-08-03 17:13:34.540244+00	\N	web	01	\N
c112232a-2317-44d8-a60d-c7d13f16d867	20	16	\N	0608202601131283839200110010010000000303528154716	000000030	001-001-000000030	2026-08-06	AUTORIZADO	9999999999999	CONSUMIDOR FINAL	\N	2.30	2.00	0.00	0.30	{"@id": "comprobante", "@version": "1.1.0", "detalles": {"detalle": [{"cantidad": "1.000000", "descuento": "0.00", "impuestos": {"impuesto": {"valor": "0.30", "codigo": "2", "tarifa": "15", "baseImponible": "2.00", "codigoPorcentaje": "4"}}, "descripcion": "WWW", "precioUnitario": "2.000000", "codigoPrincipal": "S/C", "precioTotalSinImpuesto": "2.00"}]}, "infoFactura": {"pagos": {"pago": [{"plazo": "0", "total": "2.30", "formaPago": "01", "unidadTiempo": "dias"}]}, "moneda": "DOLAR", "propina": "0.00", "fechaEmision": "06/08/2026", "importeTotal": "2.30", "totalDescuento": "0.00", "totalConImpuestos": {"totalImpuesto": [{"valor": "0.30", "codigo": "2", "baseImponible": "2.00", "codigoPorcentaje": "4"}]}, "totalSinImpuestos": "2.00", "dirEstablecimiento": "PORTOVIEJO", "obligadoContabilidad": "NO", "razonSocialComprador": "CONSUMIDOR FINAL", "identificacionComprador": "9999999999999", "tipoIdentificacionComprador": "07"}, "infoAdicional": {"campoAdicional": [{"#text": "1312838392001 (kipu.ec)", "@nombre": "Proveedor"}]}, "infoTributaria": {"ruc": "1312838392001", "estab": "001", "codDoc": "01", "ptoEmi": "001", "ambiente": 1, "dirMatriz": "PORTOVIEJO", "secuencial": "000000030", "claveAcceso": "0608202601131283839200110010010000000303528154716", "razonSocial": "ROMERO GARCIA CRISTHIAN ANDRES", "tipoEmision": "1", "nombreComercial": "ROMERO GARCIA CRISTHIAN ANDRES"}, "resumenImpuestos": [{"valor": "0.30", "tarifa": "15", "baseImponible": "2.00"}]}	1312838392001/facturas/0608202601131283839200110010010000000303528154716.xml	\N	\N	2026-08-06 20:28:36.537067+00	2026-08-06 20:28:37+00	\N	\N	2026-08-06 20:28:36.043779+00	\N	web	01	\N
d3eed257-c7d2-44a3-b1e8-ad3d70ad25a5	20	17	\N	0308202601131283839200110010050000000045714127915	000000004	001-005-000000004	2026-08-03	AUTORIZADO	9999999999999	CONSUMIDOR FINAL	\N	0.12	0.10	0.00	0.02	{"@id": "comprobante", "@version": "1.1.0", "detalles": {"detalle": [{"cantidad": "1.000000", "descuento": "0.00", "impuestos": {"impuesto": {"valor": "0.02", "codigo": "2", "tarifa": "15", "baseImponible": "0.10", "codigoPorcentaje": "4"}}, "descripcion": "DE", "precioUnitario": "0.100000", "codigoPrincipal": "S/C", "precioTotalSinImpuesto": "0.10"}]}, "infoFactura": {"pagos": {"pago": [{"plazo": "0", "total": "0.12", "formaPago": "01", "unidadTiempo": "dias"}]}, "moneda": "DOLAR", "propina": "0.00", "fechaEmision": "03/08/2026", "importeTotal": "0.12", "totalDescuento": "0.00", "totalConImpuestos": {"totalImpuesto": [{"valor": "0.02", "codigo": "2", "baseImponible": "0.10", "codigoPorcentaje": "4"}]}, "totalSinImpuestos": "0.10", "dirEstablecimiento": "PORTOVIEJO", "obligadoContabilidad": "NO", "razonSocialComprador": "CONSUMIDOR FINAL", "identificacionComprador": "9999999999999", "tipoIdentificacionComprador": "07"}, "infoAdicional": {"campoAdicional": [{"#text": "1312838392001", "@nombre": "PROVEEDOR_SISTEMA_INFORMATICO"}]}, "infoTributaria": {"ruc": "1312838392001", "estab": "001", "codDoc": "01", "ptoEmi": "005", "ambiente": 1, "dirMatriz": "PORTOVIEJO", "secuencial": "000000004", "claveAcceso": "0308202601131283839200110010050000000045714127915", "razonSocial": "ROMERO GARCIA CRISTHIAN ANDRES", "tipoEmision": "1", "nombreComercial": "ROMERO GARCIA CRISTHIAN ANDRES"}}	1312838392001/facturas/0308202601131283839200110010050000000045714127915.xml	\N	\N	2026-08-03 18:08:59.947362+00	2026-08-03 18:09:00+00	1	2026-08-03 17:17:39.15101+00	2026-08-03 17:14:59.162539+00	\N	web	01	\N
7a6b5f35-ce75-4ece-abe7-a230a0ad6169	20	16	\N	0608202601131283839200110010010000000311534152116	000000031	001-001-000000031	2026-08-06	AUTORIZADO	9999999999999	CONSUMIDOR FINAL	\N	2.30	2.00	0.00	0.30	{"@id": "comprobante", "@version": "1.1.0", "detalles": {"detalle": [{"cantidad": "1.000000", "descuento": "0.00", "impuestos": {"impuesto": {"valor": "0.30", "codigo": "2", "tarifa": "15", "baseImponible": "2.00", "codigoPorcentaje": "4"}}, "descripcion": "WWW", "precioUnitario": "2.000000", "codigoPrincipal": "1", "precioTotalSinImpuesto": "2.00"}]}, "infoFactura": {"pagos": {"pago": [{"plazo": "0", "total": "2.30", "formaPago": "01", "unidadTiempo": "dias"}]}, "moneda": "DOLAR", "propina": "0.00", "fechaEmision": "06/08/2026", "importeTotal": "2.30", "totalDescuento": "0.00", "totalConImpuestos": {"totalImpuesto": [{"valor": "0.30", "codigo": "2", "baseImponible": "2.00", "codigoPorcentaje": "4"}]}, "totalSinImpuestos": "2.00", "dirEstablecimiento": "PORTOVIEJO", "obligadoContabilidad": "NO", "razonSocialComprador": "CONSUMIDOR FINAL", "identificacionComprador": "9999999999999", "tipoIdentificacionComprador": "07"}, "infoAdicional": {"campoAdicional": [{"#text": "1312838392001 (kipu.ec)", "@nombre": "Proveedor"}]}, "infoTributaria": {"ruc": "1312838392001", "estab": "001", "codDoc": "01", "ptoEmi": "001", "ambiente": 1, "dirMatriz": "PORTOVIEJO", "secuencial": "000000031", "claveAcceso": "0608202601131283839200110010010000000311534152116", "razonSocial": "ROMERO GARCIA CRISTHIAN ANDRES", "tipoEmision": "1", "nombreComercial": "ROMERO GARCIA CRISTHIAN ANDRES"}, "resumenImpuestos": [{"valor": "0.30", "tarifa": "15", "baseImponible": "2.00"}]}	1312838392001/facturas/0608202601131283839200110010010000000311534152116.xml	\N	\N	2026-08-06 20:34:16.564533+00	2026-08-06 20:34:17+00	\N	\N	2026-08-06 20:34:15.75539+00	\N	web	01	\N
\.


--
-- Data for Name: invoices_recibidas; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.invoices_recibidas (id, emisor_id, ruc_proveedor, razon_social_proveedor, clave_acceso, numero_factura, fecha_emision, subtotal_0, subtotal_iva, valor_iva, importe_total, categoria_gasto, deducible_renta, notas_cliente, xml_path, datos_factura, fuente, procesado, created_at, total_sin_impuestos, total_descuento, fecha_autorizacion, contribuyente_especial, credito_tributario_iva, impuestos_detalle) FROM stdin;
\.


--
-- Data for Name: leads_ex_usuarios; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.leads_ex_usuarios (id, ruc, razon_social, email, full_name, motivo_salida, ultimo_balance_emision, ultimo_balance_recepcion, total_facturas_emitidas, total_facturas_recibidas, fecha_registro_original, fecha_eliminacion, whatsapp_number) FROM stdin;
1	1312838392001	ROMERO GARCIA CRISTHIAN ANDRES	cristhianromero19@outlook.com	ROMERO GARCIA CRISTHIAN ANDRES	\N	25	0	0	0	2026-05-12 03:42:17.743845	2026-05-16 23:34:36.981795	\N
2	1312838392001	ROMERO GARCIA CRISTHIAN ANDRES	cristhianromero19@outlook.com	ROMERO GARCIA CRISTHIAN ANDRES	\N	25	0	0	0	2026-05-16 23:56:01.944851	2026-05-17 18:19:39.202946	593960167213
5	1350083422001	ROMERO GARCÍA GABRIELA ALEJANDRA	rgaby598@gmail.com	ROMERO GARCÍA GABRIELA ALEJANDRA	\N	9	0	1	0	2026-05-18 19:56:56.523115	2026-05-19 01:20:35.041715	593978925402
\.


--
-- Data for Name: notificaciones; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.notificaciones (id, emisor_id, tipo, titulo, mensaje, leida, created_at, referencia) FROM stdin;
4	20	CREDITOS	✅ 50 créditos acreditados	Tu pago de $8.03 fue procesado. Ya tienes 50 créditos nuevos disponibles.	t	2026-08-10 05:00:17.175909+00	/creditos
3	20	DECLARACION	xsxs	xdsxsd	t	2026-08-10 04:23:58.324611+00	\N
5	20	CREDITOS	✅ 50 créditos acreditados	Tu pago de $8.03 fue procesado. Ya tienes 50 créditos nuevos disponibles.	t	2026-08-10 05:47:15.66454+00	/creditos
6	20	CREDITOS	✅ 50 créditos acreditados	Tu pago de $8.03 fue procesado. Ya tienes 50 créditos nuevos disponibles.	t	2026-08-10 05:56:53.251771+00	/creditos
\.


--
-- Data for Name: planes_creditos; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.planes_creditos (id, nombre, descripcion, tipo, cantidad, precio, popular, activo, orden, created_at) FROM stdin;
1	Starter	50 créditos para emitir facturas electrónicas	emision	50	699.00	f	t	1	2026-05-17 19:43:02.594164+00
2	Popular	100 créditos para emitir facturas electrónicas	emision	100	1299.00	t	t	2	2026-05-17 19:43:02.594164+00
3	Crecimiento	200 créditos para emitir facturas electrónicas	emision	200	2299.00	f	t	3	2026-05-17 19:43:02.594164+00
4	Empresarial	500 créditos para emitir facturas electrónicas	emision	500	4999.00	f	t	4	2026-05-17 19:43:02.594164+00
5	Básico	100 créditos para registrar facturas recibidas	recepcion	100	649.00	f	t	1	2026-05-17 19:43:02.594164+00
6	Profesional	200 créditos para registrar facturas recibidas	recepcion	200	1149.00	t	t	2	2026-05-17 19:43:02.594164+00
7	Empresarial	500 créditos para registrar facturas recibidas	recepcion	500	2499.00	f	t	3	2026-05-17 19:43:02.594164+00
\.


--
-- Data for Name: profiles; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.profiles (id, firebase_uid, emisor_id, email, full_name, role, whatsapp_number, created_at) FROM stdin;
97fcd876-5998-453f-8e54-bd51dcc94a2a	Uekf8E66YpZAml7guCmbqhP3xPy2	\N	cristhianromero19@outlook.com	ROMERO GARCIA CRISTHIAN ANDRES	superadmin	\N	2026-08-01 22:25:04.801712+00
\.


--
-- Data for Name: puntos_emision; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.puntos_emision (id, establecimiento_id, emisor_id, codigo, secuencial_actual, nombre, is_active) FROM stdin;
17	8	20	005	9	Punto 005	t
16	8	20	001	53	Punto 001	t
\.


--
-- Data for Name: servicios; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.servicios (id, nombre, descripcion, precio, moneda, activo, orden, created_at, hex_color, imagen_url) FROM stdin;
6	Plan Contable Mensual	Gestión contable mensual completa para tu negocio	9999.00	USD	t	6	2026-05-17 20:24:58.380796+00	#CC001356	https://concepto.de/wp-content/uploads/2020/06/Computadora-de-escritorio-scaled-e1724955496406.jpg
1	Asesoría Contable	Asesoría personalizada para no obligados a llevar contabilidad	2999.00	USD	t	1	2026-05-17 20:24:58.380796+00	#CC001356	https://concepto.de/wp-content/uploads/2020/06/Computadora-de-escritorio-scaled-e1724955496406.jpg
2	Declaración de Renta	Elaboración y presentación de tu declaración anual de renta	3999.00	USD	t	2	2026-05-17 20:24:58.380796+00	#CC001356	https://concepto.de/wp-content/uploads/2020/06/Computadora-de-escritorio-scaled-e1724955496406.jpg
3	Declaración Mensual de IVA	Gestión y presentación de tu declaración mensual del IVA al SRI	1499.00	USD	t	3	2026-05-17 20:24:58.380796+00	#CC001356	https://concepto.de/wp-content/uploads/2020/06/Computadora-de-escritorio-scaled-e1724955496406.jpg
\.


--
-- Data for Name: sujetos_global; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.sujetos_global (id, tipo_identificacion_sri, identificacion, codigo_pais, razon_social, ultima_sincronizacion) FROM stdin;
dd00982e-8a70-45d2-ac10-7e2da9f8e83d	05	1307196640	EC	JULIA GARCIA	2026-05-17 23:35:29.647207+00
cc1f8638-7a95-4c92-9cf7-82d3cf73b5d8	05	1301202311	EC	NANCY JIJON	2026-05-18 21:11:33.185302+00
c3a4e799-598a-47e3-b190-24fcb3b582de	04	0916247349001	EC	ACOSTA ARELLANO ALEX ARNOLDO	2026-05-18 21:25:14.121466+00
9d9e7029-5273-4457-9d7e-df908ec1458a	04	1307196640001	EC	GARCIA JIJON JULIA ISABEL	2026-05-28 17:14:47.57309+00
b64332ff-96f8-4974-823a-60c573c08ff0	04	1350865711001	EC	QUIROZ RODRIGUEZ EVELYN XIOMARA	2026-05-29 21:39:37.87919+00
631b590a-ff5b-400e-8591-a35a8151012e	05	1723772099	EC	DARWIN CHACAN	2026-07-15 19:00:31.858372+00
d30d46ad-e396-4767-99b1-77758bdfce17	05	1312838392	EC	CRISTHIAN ROMERO	2026-08-02 20:42:35.512058+00
5dab43aa-9767-4995-b022-ffa97ca7ae67	04	1312838392001	EC	ROMERO GARCIA CRISTHIAN ANDRES	2026-08-10 05:47:13.112695+00
\.


--
-- Data for Name: transaction_logs; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.transaction_logs (id, target_emisor_id, amount, action_type, description, created_at) FROM stdin;
\.


--
-- Data for Name: user_credits; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.user_credits (emisor_id, balance_emision, balance_recepcion, last_updated) FROM stdin;
20	164	20	2026-08-10 05:56:51.148159+00
\.


--
-- Data for Name: webhooks; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.webhooks (id, emisor_id, api_key_id, url, secret, eventos, activo, created_at) FROM stdin;
\.


--
-- Data for Name: schema_migrations; Type: TABLE DATA; Schema: realtime; Owner: supabase_admin
--

COPY realtime.schema_migrations (version, inserted_at) FROM stdin;
20211116024918	2026-05-23 17:05:29
20211116045059	2026-05-23 17:05:29
20211116050929	2026-05-23 17:05:29
20211116051442	2026-05-23 17:05:29
20211116212300	2026-05-23 17:05:30
20211116213355	2026-05-23 17:05:30
20211116213934	2026-05-23 17:05:30
20211116214523	2026-05-23 17:05:30
20211122062447	2026-05-23 17:05:30
20211124070109	2026-05-23 17:05:31
20211202204204	2026-05-23 17:05:31
20211202204605	2026-05-23 17:05:31
20211210212804	2026-05-23 17:05:32
20211228014915	2026-05-23 17:05:32
20220107221237	2026-05-23 17:05:32
20220228202821	2026-05-23 17:05:32
20220312004840	2026-05-23 17:05:32
20220603231003	2026-05-23 17:05:33
20220603232444	2026-05-23 17:05:33
20220615214548	2026-05-23 17:05:33
20220712093339	2026-05-23 17:05:33
20220908172859	2026-05-23 17:05:34
20220916233421	2026-05-23 17:05:34
20230119133233	2026-05-23 17:05:34
20230128025114	2026-05-23 17:05:34
20230128025212	2026-05-23 17:05:34
20230227211149	2026-05-23 17:05:35
20230228184745	2026-05-23 17:05:35
20230308225145	2026-05-23 17:05:35
20230328144023	2026-05-23 17:05:35
20231018144023	2026-05-23 17:05:35
20231204144023	2026-05-23 17:05:36
20231204144024	2026-05-23 17:05:36
20231204144025	2026-05-23 17:05:36
20240108234812	2026-05-23 17:05:36
20240109165339	2026-05-23 17:05:36
20240227174441	2026-05-23 17:05:37
20240311171622	2026-05-23 17:05:37
20240321100241	2026-05-23 17:05:37
20240401105812	2026-05-23 17:05:38
20240418121054	2026-05-23 17:05:38
20240523004032	2026-05-23 17:05:39
20240618124746	2026-05-23 17:05:39
20240801235015	2026-05-23 17:05:39
20240805133720	2026-05-23 17:05:40
20240827160934	2026-05-23 17:05:40
20240919163303	2026-05-23 17:05:40
20240919163305	2026-05-23 17:05:40
20241019105805	2026-05-23 17:05:40
20241030150047	2026-05-23 17:05:41
20241108114728	2026-05-23 17:05:41
20241121104152	2026-05-23 17:05:42
20241130184212	2026-05-23 17:05:42
20241220035512	2026-05-23 17:05:42
20241220123912	2026-05-23 17:05:42
20241224161212	2026-05-23 17:05:42
20250107150512	2026-05-23 17:05:43
20250110162412	2026-05-23 17:05:43
20250123174212	2026-05-23 17:05:43
20250128220012	2026-05-23 17:05:43
20250506224012	2026-05-23 17:05:43
20250523164012	2026-05-23 17:05:43
20250714121412	2026-05-23 17:05:44
20250905041441	2026-05-23 17:05:44
20251103001201	2026-05-23 17:05:44
20251120212548	2026-05-23 17:05:44
20251120215549	2026-05-23 17:05:45
20260218120000	2026-05-23 17:05:45
20260326120000	2026-05-23 17:05:45
20260514120000	2026-07-28 05:07:55
20260527120000	2026-07-28 05:07:55
20260528120000	2026-07-28 05:07:55
20260603120000	2026-07-28 05:07:56
20260605120000	2026-07-28 05:07:56
20260606110000	2026-07-28 05:07:56
20260616120000	2026-07-28 05:07:57
20260624120000	2026-07-28 05:07:57
20260626120000	2026-07-28 05:07:58
20260706120000	2026-07-28 05:07:58
20260707120000	2026-07-28 05:07:59
20260709120000	2026-07-28 05:08:00
\.


--
-- Data for Name: subscription; Type: TABLE DATA; Schema: realtime; Owner: supabase_realtime_admin
--

COPY realtime.subscription (id, subscription_id, entity, filters, claims, created_at, action_filter, selected_columns) FROM stdin;
\.


--
-- Data for Name: buckets; Type: TABLE DATA; Schema: storage; Owner: supabase_storage_admin
--

COPY storage.buckets (id, name, owner, created_at, updated_at, public, avif_autodetection, file_size_limit, allowed_mime_types, owner_id, type) FROM stdin;
\.


--
-- Data for Name: buckets_analytics; Type: TABLE DATA; Schema: storage; Owner: supabase_storage_admin
--

COPY storage.buckets_analytics (name, type, format, created_at, updated_at, id, deleted_at) FROM stdin;
\.


--
-- Data for Name: buckets_vectors; Type: TABLE DATA; Schema: storage; Owner: supabase_storage_admin
--

COPY storage.buckets_vectors (id, type, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: migrations; Type: TABLE DATA; Schema: storage; Owner: supabase_storage_admin
--

COPY storage.migrations (id, name, hash, executed_at) FROM stdin;
0	create-migrations-table	e18db593bcde2aca2a408c4d1100f6abba2195df	2026-05-23 12:34:40.42562
1	initialmigration	6ab16121fbaa08bbd11b712d05f358f9b555d777	2026-05-23 12:34:40.451053
2	storage-schema	f6a1fa2c93cbcd16d4e487b362e45fca157a8dbd	2026-05-23 12:34:40.45646
3	pathtoken-column	2cb1b0004b817b29d5b0a971af16bafeede4b70d	2026-05-23 12:34:40.475993
4	add-migrations-rls	427c5b63fe1c5937495d9c635c263ee7a5905058	2026-05-23 12:34:40.485243
5	add-size-functions	79e081a1455b63666c1294a440f8ad4b1e6a7f84	2026-05-23 12:34:40.490063
6	change-column-name-in-get-size	ded78e2f1b5d7e616117897e6443a925965b30d2	2026-05-23 12:34:40.495661
7	add-rls-to-buckets	e7e7f86adbc51049f341dfe8d30256c1abca17aa	2026-05-23 12:34:40.500737
8	add-public-to-buckets	fd670db39ed65f9d08b01db09d6202503ca2bab3	2026-05-23 12:34:40.505205
9	fix-search-function	af597a1b590c70519b464a4ab3be54490712796b	2026-05-23 12:34:40.509782
10	search-files-search-function	b595f05e92f7e91211af1bbfe9c6a13bb3391e16	2026-05-23 12:34:40.514043
11	add-trigger-to-auto-update-updated_at-column	7425bdb14366d1739fa8a18c83100636d74dcaa2	2026-05-23 12:34:40.518517
12	add-automatic-avif-detection-flag	8e92e1266eb29518b6a4c5313ab8f29dd0d08df9	2026-05-23 12:34:40.524213
13	add-bucket-custom-limits	cce962054138135cd9a8c4bcd531598684b25e7d	2026-05-23 12:34:40.52871
14	use-bytes-for-max-size	941c41b346f9802b411f06f30e972ad4744dad27	2026-05-23 12:34:40.533863
15	add-can-insert-object-function	934146bc38ead475f4ef4b555c524ee5d66799e5	2026-05-23 12:34:40.553619
16	add-version	76debf38d3fd07dcfc747ca49096457d95b1221b	2026-05-23 12:34:40.558503
17	drop-owner-foreign-key	f1cbb288f1b7a4c1eb8c38504b80ae2a0153d101	2026-05-23 12:34:40.562969
18	add_owner_id_column_deprecate_owner	e7a511b379110b08e2f214be852c35414749fe66	2026-05-23 12:34:40.567969
19	alter-default-value-objects-id	02e5e22a78626187e00d173dc45f58fa66a4f043	2026-05-23 12:34:40.574085
20	list-objects-with-delimiter	cd694ae708e51ba82bf012bba00caf4f3b6393b7	2026-05-23 12:34:40.579709
21	s3-multipart-uploads	8c804d4a566c40cd1e4cc5b3725a664a9303657f	2026-05-23 12:34:40.585971
22	s3-multipart-uploads-big-ints	9737dc258d2397953c9953d9b86920b8be0cdb73	2026-05-23 12:34:40.598254
23	optimize-search-function	9d7e604cddc4b56a5422dc68c9313f4a1b6f132c	2026-05-23 12:34:40.621892
24	operation-function	8312e37c2bf9e76bbe841aa5fda889206d2bf8aa	2026-05-23 12:34:40.626651
25	custom-metadata	d974c6057c3db1c1f847afa0e291e6165693b990	2026-05-23 12:34:40.631986
26	objects-prefixes	215cabcb7f78121892a5a2037a09fedf9a1ae322	2026-05-23 12:34:40.636599
27	search-v2	859ba38092ac96eb3964d83bf53ccc0b141663a6	2026-05-23 12:34:40.641078
28	object-bucket-name-sorting	c73a2b5b5d4041e39705814fd3a1b95502d38ce4	2026-05-23 12:34:40.645186
29	create-prefixes	ad2c1207f76703d11a9f9007f821620017a66c21	2026-05-23 12:34:40.649364
30	update-object-levels	2be814ff05c8252fdfdc7cfb4b7f5c7e17f0bed6	2026-05-23 12:34:40.653571
31	objects-level-index	b40367c14c3440ec75f19bbce2d71e914ddd3da0	2026-05-23 12:34:40.657724
32	backward-compatible-index-on-objects	e0c37182b0f7aee3efd823298fb3c76f1042c0f7	2026-05-23 12:34:40.661894
33	backward-compatible-index-on-prefixes	b480e99ed951e0900f033ec4eb34b5bdcb4e3d49	2026-05-23 12:34:40.665968
34	optimize-search-function-v1	ca80a3dc7bfef894df17108785ce29a7fc8ee456	2026-05-23 12:34:40.669978
35	add-insert-trigger-prefixes	458fe0ffd07ec53f5e3ce9df51bfdf4861929ccc	2026-05-23 12:34:40.673959
36	optimise-existing-functions	6ae5fca6af5c55abe95369cd4f93985d1814ca8f	2026-05-23 12:34:40.677967
37	add-bucket-name-length-trigger	3944135b4e3e8b22d6d4cbb568fe3b0b51df15c1	2026-05-23 12:34:40.681968
38	iceberg-catalog-flag-on-buckets	02716b81ceec9705aed84aa1501657095b32e5c5	2026-05-23 12:34:40.686717
39	add-search-v2-sort-support	6706c5f2928846abee18461279799ad12b279b78	2026-05-23 12:34:40.69401
40	fix-prefix-race-conditions-optimized	7ad69982ae2d372b21f48fc4829ae9752c518f6b	2026-05-23 12:34:40.697834
41	add-object-level-update-trigger	07fcf1a22165849b7a029deed059ffcde08d1ae0	2026-05-23 12:34:40.701795
42	rollback-prefix-triggers	771479077764adc09e2ea2043eb627503c034cd4	2026-05-23 12:34:40.70569
43	fix-object-level	84b35d6caca9d937478ad8a797491f38b8c2979f	2026-05-23 12:34:40.709813
44	vector-bucket-type	99c20c0ffd52bb1ff1f32fb992f3b351e3ef8fb3	2026-05-23 12:34:40.713818
45	vector-buckets	049e27196d77a7cb76497a85afae669d8b230953	2026-05-23 12:34:40.719637
46	buckets-objects-grants	fedeb96d60fefd8e02ab3ded9fbde05632f84aed	2026-05-23 12:34:40.739369
47	iceberg-table-metadata	649df56855c24d8b36dd4cc1aeb8251aa9ad42c2	2026-05-23 12:34:40.747018
48	iceberg-catalog-ids	e0e8b460c609b9999ccd0df9ad14294613eed939	2026-05-23 12:34:40.831969
49	buckets-objects-grants-postgres	072b1195d0d5a2f888af6b2302a1938dd94b8b3d	2026-05-23 12:34:40.866406
50	search-v2-optimised	6323ac4f850aa14e7387eb32102869578b5bd478	2026-05-23 12:34:40.871856
51	index-backward-compatible-search	2ee395d433f76e38bcd3856debaf6e0e5b674011	2026-05-23 12:34:41.830588
52	drop-not-used-indexes-and-functions	5cc44c8696749ac11dd0dc37f2a3802075f3a171	2026-05-23 12:34:41.833209
53	drop-index-lower-name	d0cb18777d9e2a98ebe0bc5cc7a42e57ebe41854	2026-05-23 12:34:41.844792
54	drop-index-object-level	6289e048b1472da17c31a7eba1ded625a6457e67	2026-05-23 12:34:41.847461
55	prevent-direct-deletes	262a4798d5e0f2e7c8970232e03ce8be695d5819	2026-05-23 12:34:41.849195
56	fix-optimized-search-function	b823ed1e418101032fa01374edc9a436e54e3ed4	2026-05-23 12:34:41.854084
57	s3-multipart-uploads-metadata	f127886e00d1b374fadbc7c6b31e09336aad5287	2026-05-23 12:34:41.860205
58	operation-ergonomics	00ca5d483b3fe0d522133d9002ccc5df98365120	2026-05-23 12:34:41.865006
59	drop-unused-functions	38456f13e39691c2bbb4b5151d0d1cdbabd4a8c4	2026-05-23 12:34:41.870357
60	optimize-existing-functions-again	db35e1c91a9201e59f4fef8d972c2f277d68b157	2026-05-23 12:34:41.874508
\.


--
-- Data for Name: objects; Type: TABLE DATA; Schema: storage; Owner: supabase_storage_admin
--

COPY storage.objects (id, bucket_id, name, owner, created_at, updated_at, last_accessed_at, metadata, version, owner_id, user_metadata) FROM stdin;
\.


--
-- Data for Name: s3_multipart_uploads; Type: TABLE DATA; Schema: storage; Owner: supabase_storage_admin
--

COPY storage.s3_multipart_uploads (id, in_progress_size, upload_signature, bucket_id, key, version, owner_id, created_at, user_metadata, metadata) FROM stdin;
\.


--
-- Data for Name: s3_multipart_uploads_parts; Type: TABLE DATA; Schema: storage; Owner: supabase_storage_admin
--

COPY storage.s3_multipart_uploads_parts (id, upload_id, size, part_number, bucket_id, key, etag, owner_id, version, created_at) FROM stdin;
\.


--
-- Data for Name: vector_indexes; Type: TABLE DATA; Schema: storage; Owner: supabase_storage_admin
--

COPY storage.vector_indexes (id, name, bucket_id, data_type, dimension, distance_metric, metadata_configuration, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: secrets; Type: TABLE DATA; Schema: vault; Owner: supabase_admin
--

COPY vault.secrets (id, name, description, secret, key_id, nonce, created_at, updated_at) FROM stdin;
\.


--
-- Name: refresh_tokens_id_seq; Type: SEQUENCE SET; Schema: auth; Owner: supabase_auth_admin
--

SELECT pg_catalog.setval('auth.refresh_tokens_id_seq', 1, false);


--
-- Name: api_keys_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.api_keys_id_seq', 9, true);


--
-- Name: app_ads_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.app_ads_id_seq', 17, true);


--
-- Name: auth_challenges_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.auth_challenges_id_seq', 31, true);


--
-- Name: declaraciones_sri_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.declaraciones_sri_id_seq', 1, false);


--
-- Name: email_rate_limits_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.email_rate_limits_id_seq', 29, true);


--
-- Name: emisor_usuarios_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.emisor_usuarios_id_seq', 1, true);


--
-- Name: emisores_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.emisores_id_seq', 20, true);


--
-- Name: establecimientos_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.establecimientos_id_seq', 8, true);


--
-- Name: fcm_tokens_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.fcm_tokens_id_seq', 26, true);


--
-- Name: leads_ex_usuarios_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.leads_ex_usuarios_id_seq', 5, true);


--
-- Name: notificaciones_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.notificaciones_id_seq', 6, true);


--
-- Name: planes_creditos_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.planes_creditos_id_seq', 7, true);


--
-- Name: puntos_emision_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.puntos_emision_id_seq', 17, true);


--
-- Name: servicios_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.servicios_id_seq', 6, true);


--
-- Name: transaction_logs_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.transaction_logs_id_seq', 1, false);


--
-- Name: webhooks_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.webhooks_id_seq', 1, false);


--
-- Name: subscription_id_seq; Type: SEQUENCE SET; Schema: realtime; Owner: supabase_realtime_admin
--

SELECT pg_catalog.setval('realtime.subscription_id_seq', 1, false);


--
-- Name: mfa_amr_claims amr_id_pk; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.mfa_amr_claims
    ADD CONSTRAINT amr_id_pk PRIMARY KEY (id);


--
-- Name: audit_log_entries audit_log_entries_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.audit_log_entries
    ADD CONSTRAINT audit_log_entries_pkey PRIMARY KEY (id);


--
-- Name: custom_oauth_providers custom_oauth_providers_identifier_key; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.custom_oauth_providers
    ADD CONSTRAINT custom_oauth_providers_identifier_key UNIQUE (identifier);


--
-- Name: custom_oauth_providers custom_oauth_providers_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.custom_oauth_providers
    ADD CONSTRAINT custom_oauth_providers_pkey PRIMARY KEY (id);


--
-- Name: flow_state flow_state_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.flow_state
    ADD CONSTRAINT flow_state_pkey PRIMARY KEY (id);


--
-- Name: identities identities_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.identities
    ADD CONSTRAINT identities_pkey PRIMARY KEY (id);


--
-- Name: identities identities_provider_id_provider_unique; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.identities
    ADD CONSTRAINT identities_provider_id_provider_unique UNIQUE (provider_id, provider);


--
-- Name: instances instances_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.instances
    ADD CONSTRAINT instances_pkey PRIMARY KEY (id);


--
-- Name: mfa_amr_claims mfa_amr_claims_session_id_authentication_method_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.mfa_amr_claims
    ADD CONSTRAINT mfa_amr_claims_session_id_authentication_method_pkey UNIQUE (session_id, authentication_method);


--
-- Name: mfa_challenges mfa_challenges_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.mfa_challenges
    ADD CONSTRAINT mfa_challenges_pkey PRIMARY KEY (id);


--
-- Name: mfa_factors mfa_factors_last_challenged_at_key; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.mfa_factors
    ADD CONSTRAINT mfa_factors_last_challenged_at_key UNIQUE (last_challenged_at);


--
-- Name: mfa_factors mfa_factors_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.mfa_factors
    ADD CONSTRAINT mfa_factors_pkey PRIMARY KEY (id);


--
-- Name: oauth_authorizations oauth_authorizations_authorization_code_key; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.oauth_authorizations
    ADD CONSTRAINT oauth_authorizations_authorization_code_key UNIQUE (authorization_code);


--
-- Name: oauth_authorizations oauth_authorizations_authorization_id_key; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.oauth_authorizations
    ADD CONSTRAINT oauth_authorizations_authorization_id_key UNIQUE (authorization_id);


--
-- Name: oauth_authorizations oauth_authorizations_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.oauth_authorizations
    ADD CONSTRAINT oauth_authorizations_pkey PRIMARY KEY (id);


--
-- Name: oauth_client_states oauth_client_states_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.oauth_client_states
    ADD CONSTRAINT oauth_client_states_pkey PRIMARY KEY (id);


--
-- Name: oauth_clients oauth_clients_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.oauth_clients
    ADD CONSTRAINT oauth_clients_pkey PRIMARY KEY (id);


--
-- Name: oauth_consents oauth_consents_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.oauth_consents
    ADD CONSTRAINT oauth_consents_pkey PRIMARY KEY (id);


--
-- Name: oauth_consents oauth_consents_user_client_unique; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.oauth_consents
    ADD CONSTRAINT oauth_consents_user_client_unique UNIQUE (user_id, client_id);


--
-- Name: one_time_tokens one_time_tokens_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.one_time_tokens
    ADD CONSTRAINT one_time_tokens_pkey PRIMARY KEY (id);


--
-- Name: refresh_tokens refresh_tokens_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.refresh_tokens
    ADD CONSTRAINT refresh_tokens_pkey PRIMARY KEY (id);


--
-- Name: refresh_tokens refresh_tokens_token_unique; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.refresh_tokens
    ADD CONSTRAINT refresh_tokens_token_unique UNIQUE (token);


--
-- Name: saml_providers saml_providers_entity_id_key; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.saml_providers
    ADD CONSTRAINT saml_providers_entity_id_key UNIQUE (entity_id);


--
-- Name: saml_providers saml_providers_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.saml_providers
    ADD CONSTRAINT saml_providers_pkey PRIMARY KEY (id);


--
-- Name: saml_relay_states saml_relay_states_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.saml_relay_states
    ADD CONSTRAINT saml_relay_states_pkey PRIMARY KEY (id);


--
-- Name: schema_migrations schema_migrations_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.schema_migrations
    ADD CONSTRAINT schema_migrations_pkey PRIMARY KEY (version);


--
-- Name: sessions sessions_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.sessions
    ADD CONSTRAINT sessions_pkey PRIMARY KEY (id);


--
-- Name: sso_domains sso_domains_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.sso_domains
    ADD CONSTRAINT sso_domains_pkey PRIMARY KEY (id);


--
-- Name: sso_providers sso_providers_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.sso_providers
    ADD CONSTRAINT sso_providers_pkey PRIMARY KEY (id);


--
-- Name: users users_phone_key; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.users
    ADD CONSTRAINT users_phone_key UNIQUE (phone);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: webauthn_challenges webauthn_challenges_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.webauthn_challenges
    ADD CONSTRAINT webauthn_challenges_pkey PRIMARY KEY (id);


--
-- Name: webauthn_credentials webauthn_credentials_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.webauthn_credentials
    ADD CONSTRAINT webauthn_credentials_pkey PRIMARY KEY (id);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: api_keys api_keys_key_hash_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.api_keys
    ADD CONSTRAINT api_keys_key_hash_key UNIQUE (key_hash);


--
-- Name: api_keys api_keys_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.api_keys
    ADD CONSTRAINT api_keys_pkey PRIMARY KEY (id);


--
-- Name: app_ads app_ads_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.app_ads
    ADD CONSTRAINT app_ads_pkey PRIMARY KEY (id);


--
-- Name: auth_challenges auth_challenges_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.auth_challenges
    ADD CONSTRAINT auth_challenges_pkey PRIMARY KEY (id);


--
-- Name: catalogo_items catalogo_items_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.catalogo_items
    ADD CONSTRAINT catalogo_items_pkey PRIMARY KEY (id);


--
-- Name: clientes_emisor clientes_emisor_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.clientes_emisor
    ADD CONSTRAINT clientes_emisor_pkey PRIMARY KEY (id);


--
-- Name: credit_transactions credit_transactions_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.credit_transactions
    ADD CONSTRAINT credit_transactions_pkey PRIMARY KEY (id);


--
-- Name: declaraciones_sri declaraciones_sri_emisor_id_tipo_periodo_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.declaraciones_sri
    ADD CONSTRAINT declaraciones_sri_emisor_id_tipo_periodo_key UNIQUE (emisor_id, tipo, periodo);


--
-- Name: declaraciones_sri declaraciones_sri_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.declaraciones_sri
    ADD CONSTRAINT declaraciones_sri_pkey PRIMARY KEY (id);


--
-- Name: email_rate_limits email_rate_limits_email_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.email_rate_limits
    ADD CONSTRAINT email_rate_limits_email_key UNIQUE (email);


--
-- Name: email_rate_limits email_rate_limits_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.email_rate_limits
    ADD CONSTRAINT email_rate_limits_pkey PRIMARY KEY (id);


--
-- Name: emisor_usuarios emisor_usuarios_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.emisor_usuarios
    ADD CONSTRAINT emisor_usuarios_pkey PRIMARY KEY (id);


--
-- Name: emisores emisores_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.emisores
    ADD CONSTRAINT emisores_pkey PRIMARY KEY (id);


--
-- Name: emisores emisores_ruc_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.emisores
    ADD CONSTRAINT emisores_ruc_key UNIQUE (ruc);


--
-- Name: establecimientos establecimientos_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.establecimientos
    ADD CONSTRAINT establecimientos_pkey PRIMARY KEY (id);


--
-- Name: fcm_tokens fcm_tokens_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.fcm_tokens
    ADD CONSTRAINT fcm_tokens_pkey PRIMARY KEY (id);


--
-- Name: fcm_tokens fcm_tokens_unique; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.fcm_tokens
    ADD CONSTRAINT fcm_tokens_unique UNIQUE (profile_id, emisor_id, device_id);


--
-- Name: invoices_emitidas invoices_clave_acceso_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.invoices_emitidas
    ADD CONSTRAINT invoices_clave_acceso_key UNIQUE (clave_acceso);


--
-- Name: invoices_emitidas invoices_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.invoices_emitidas
    ADD CONSTRAINT invoices_pkey PRIMARY KEY (id);


--
-- Name: invoices_recibidas invoices_recibidas_clave_acceso_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.invoices_recibidas
    ADD CONSTRAINT invoices_recibidas_clave_acceso_key UNIQUE (clave_acceso);


--
-- Name: invoices_recibidas invoices_recibidas_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.invoices_recibidas
    ADD CONSTRAINT invoices_recibidas_pkey PRIMARY KEY (id);


--
-- Name: leads_ex_usuarios leads_ex_usuarios_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.leads_ex_usuarios
    ADD CONSTRAINT leads_ex_usuarios_pkey PRIMARY KEY (id);


--
-- Name: notificaciones notificaciones_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.notificaciones
    ADD CONSTRAINT notificaciones_pkey PRIMARY KEY (id);


--
-- Name: planes_creditos planes_creditos_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.planes_creditos
    ADD CONSTRAINT planes_creditos_pkey PRIMARY KEY (id);


--
-- Name: profiles profiles_email_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.profiles
    ADD CONSTRAINT profiles_email_key UNIQUE (email);


--
-- Name: profiles profiles_firebase_uid_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.profiles
    ADD CONSTRAINT profiles_firebase_uid_key UNIQUE (firebase_uid);


--
-- Name: profiles profiles_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.profiles
    ADD CONSTRAINT profiles_pkey PRIMARY KEY (id);


--
-- Name: puntos_emision puntos_emision_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.puntos_emision
    ADD CONSTRAINT puntos_emision_pkey PRIMARY KEY (id);


--
-- Name: servicios servicios_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.servicios
    ADD CONSTRAINT servicios_pkey PRIMARY KEY (id);


--
-- Name: sujetos_global sujetos_global_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sujetos_global
    ADD CONSTRAINT sujetos_global_pkey PRIMARY KEY (id);


--
-- Name: transaction_logs transaction_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.transaction_logs
    ADD CONSTRAINT transaction_logs_pkey PRIMARY KEY (id);


--
-- Name: clientes_emisor uq_cliente_emisor_id; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.clientes_emisor
    ADD CONSTRAINT uq_cliente_emisor_id UNIQUE (emisor_id, identificacion);


--
-- Name: emisor_usuarios uq_emisor_profile; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.emisor_usuarios
    ADD CONSTRAINT uq_emisor_profile UNIQUE (emisor_id, profile_id);


--
-- Name: establecimientos uq_estab_emisor_codigo; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.establecimientos
    ADD CONSTRAINT uq_estab_emisor_codigo UNIQUE (emisor_id, codigo);


--
-- Name: puntos_emision uq_pe_estab_codigo; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.puntos_emision
    ADD CONSTRAINT uq_pe_estab_codigo UNIQUE (establecimiento_id, codigo);


--
-- Name: sujetos_global uq_sujetos_identificacion; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sujetos_global
    ADD CONSTRAINT uq_sujetos_identificacion UNIQUE (identificacion, tipo_identificacion_sri);


--
-- Name: user_credits user_credits_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_credits
    ADD CONSTRAINT user_credits_pkey PRIMARY KEY (emisor_id);


--
-- Name: webhooks webhooks_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.webhooks
    ADD CONSTRAINT webhooks_pkey PRIMARY KEY (id);


--
-- Name: messages messages_payload_exclusive; Type: CHECK CONSTRAINT; Schema: realtime; Owner: supabase_realtime_admin
--

ALTER TABLE realtime.messages
    ADD CONSTRAINT messages_payload_exclusive CHECK (((payload IS NULL) OR (binary_payload IS NULL))) NOT VALID;


--
-- Name: messages messages_pkey; Type: CONSTRAINT; Schema: realtime; Owner: supabase_realtime_admin
--

ALTER TABLE ONLY realtime.messages
    ADD CONSTRAINT messages_pkey PRIMARY KEY (id, inserted_at);


--
-- Name: subscription pk_subscription; Type: CONSTRAINT; Schema: realtime; Owner: supabase_realtime_admin
--

ALTER TABLE ONLY realtime.subscription
    ADD CONSTRAINT pk_subscription PRIMARY KEY (id);


--
-- Name: schema_migrations schema_migrations_pkey; Type: CONSTRAINT; Schema: realtime; Owner: supabase_admin
--

ALTER TABLE ONLY realtime.schema_migrations
    ADD CONSTRAINT schema_migrations_pkey PRIMARY KEY (version);


--
-- Name: buckets_analytics buckets_analytics_pkey; Type: CONSTRAINT; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE ONLY storage.buckets_analytics
    ADD CONSTRAINT buckets_analytics_pkey PRIMARY KEY (id);


--
-- Name: buckets buckets_pkey; Type: CONSTRAINT; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE ONLY storage.buckets
    ADD CONSTRAINT buckets_pkey PRIMARY KEY (id);


--
-- Name: buckets_vectors buckets_vectors_pkey; Type: CONSTRAINT; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE ONLY storage.buckets_vectors
    ADD CONSTRAINT buckets_vectors_pkey PRIMARY KEY (id);


--
-- Name: migrations migrations_name_key; Type: CONSTRAINT; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE ONLY storage.migrations
    ADD CONSTRAINT migrations_name_key UNIQUE (name);


--
-- Name: migrations migrations_pkey; Type: CONSTRAINT; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE ONLY storage.migrations
    ADD CONSTRAINT migrations_pkey PRIMARY KEY (id);


--
-- Name: objects objects_pkey; Type: CONSTRAINT; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE ONLY storage.objects
    ADD CONSTRAINT objects_pkey PRIMARY KEY (id);


--
-- Name: s3_multipart_uploads_parts s3_multipart_uploads_parts_pkey; Type: CONSTRAINT; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE ONLY storage.s3_multipart_uploads_parts
    ADD CONSTRAINT s3_multipart_uploads_parts_pkey PRIMARY KEY (id);


--
-- Name: s3_multipart_uploads s3_multipart_uploads_pkey; Type: CONSTRAINT; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE ONLY storage.s3_multipart_uploads
    ADD CONSTRAINT s3_multipart_uploads_pkey PRIMARY KEY (id);


--
-- Name: vector_indexes vector_indexes_pkey; Type: CONSTRAINT; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE ONLY storage.vector_indexes
    ADD CONSTRAINT vector_indexes_pkey PRIMARY KEY (id);


--
-- Name: audit_logs_instance_id_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX audit_logs_instance_id_idx ON auth.audit_log_entries USING btree (instance_id);


--
-- Name: confirmation_token_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE UNIQUE INDEX confirmation_token_idx ON auth.users USING btree (confirmation_token) WHERE ((confirmation_token)::text !~ '^[0-9 ]*$'::text);


--
-- Name: custom_oauth_providers_created_at_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX custom_oauth_providers_created_at_idx ON auth.custom_oauth_providers USING btree (created_at);


--
-- Name: custom_oauth_providers_enabled_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX custom_oauth_providers_enabled_idx ON auth.custom_oauth_providers USING btree (enabled);


--
-- Name: custom_oauth_providers_identifier_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX custom_oauth_providers_identifier_idx ON auth.custom_oauth_providers USING btree (identifier);


--
-- Name: custom_oauth_providers_provider_type_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX custom_oauth_providers_provider_type_idx ON auth.custom_oauth_providers USING btree (provider_type);


--
-- Name: email_change_token_current_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE UNIQUE INDEX email_change_token_current_idx ON auth.users USING btree (email_change_token_current) WHERE ((email_change_token_current)::text !~ '^[0-9 ]*$'::text);


--
-- Name: email_change_token_new_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE UNIQUE INDEX email_change_token_new_idx ON auth.users USING btree (email_change_token_new) WHERE ((email_change_token_new)::text !~ '^[0-9 ]*$'::text);


--
-- Name: factor_id_created_at_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX factor_id_created_at_idx ON auth.mfa_factors USING btree (user_id, created_at);


--
-- Name: flow_state_created_at_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX flow_state_created_at_idx ON auth.flow_state USING btree (created_at DESC);


--
-- Name: identities_email_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX identities_email_idx ON auth.identities USING btree (email text_pattern_ops);


--
-- Name: INDEX identities_email_idx; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON INDEX auth.identities_email_idx IS 'Auth: Ensures indexed queries on the email column';


--
-- Name: identities_user_id_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX identities_user_id_idx ON auth.identities USING btree (user_id);


--
-- Name: idx_auth_code; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX idx_auth_code ON auth.flow_state USING btree (auth_code);


--
-- Name: idx_oauth_client_states_created_at; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX idx_oauth_client_states_created_at ON auth.oauth_client_states USING btree (created_at);


--
-- Name: idx_user_id_auth_method; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX idx_user_id_auth_method ON auth.flow_state USING btree (user_id, authentication_method);


--
-- Name: idx_users_created_at_desc; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX idx_users_created_at_desc ON auth.users USING btree (created_at DESC);


--
-- Name: idx_users_email; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX idx_users_email ON auth.users USING btree (email);


--
-- Name: idx_users_last_sign_in_at_desc; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX idx_users_last_sign_in_at_desc ON auth.users USING btree (last_sign_in_at DESC);


--
-- Name: idx_users_name; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX idx_users_name ON auth.users USING btree (((raw_user_meta_data ->> 'name'::text))) WHERE ((raw_user_meta_data ->> 'name'::text) IS NOT NULL);


--
-- Name: mfa_challenge_created_at_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX mfa_challenge_created_at_idx ON auth.mfa_challenges USING btree (created_at DESC);


--
-- Name: mfa_factors_user_friendly_name_unique; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE UNIQUE INDEX mfa_factors_user_friendly_name_unique ON auth.mfa_factors USING btree (friendly_name, user_id) WHERE (TRIM(BOTH FROM friendly_name) <> ''::text);


--
-- Name: mfa_factors_user_id_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX mfa_factors_user_id_idx ON auth.mfa_factors USING btree (user_id);


--
-- Name: oauth_auth_pending_exp_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX oauth_auth_pending_exp_idx ON auth.oauth_authorizations USING btree (expires_at) WHERE (status = 'pending'::auth.oauth_authorization_status);


--
-- Name: oauth_clients_deleted_at_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX oauth_clients_deleted_at_idx ON auth.oauth_clients USING btree (deleted_at);


--
-- Name: oauth_consents_active_client_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX oauth_consents_active_client_idx ON auth.oauth_consents USING btree (client_id) WHERE (revoked_at IS NULL);


--
-- Name: oauth_consents_active_user_client_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX oauth_consents_active_user_client_idx ON auth.oauth_consents USING btree (user_id, client_id) WHERE (revoked_at IS NULL);


--
-- Name: oauth_consents_user_order_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX oauth_consents_user_order_idx ON auth.oauth_consents USING btree (user_id, granted_at DESC);


--
-- Name: one_time_tokens_relates_to_hash_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX one_time_tokens_relates_to_hash_idx ON auth.one_time_tokens USING hash (relates_to);


--
-- Name: one_time_tokens_token_hash_hash_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX one_time_tokens_token_hash_hash_idx ON auth.one_time_tokens USING hash (token_hash);


--
-- Name: one_time_tokens_user_id_token_type_key; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE UNIQUE INDEX one_time_tokens_user_id_token_type_key ON auth.one_time_tokens USING btree (user_id, token_type);


--
-- Name: reauthentication_token_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE UNIQUE INDEX reauthentication_token_idx ON auth.users USING btree (reauthentication_token) WHERE ((reauthentication_token)::text !~ '^[0-9 ]*$'::text);


--
-- Name: recovery_token_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE UNIQUE INDEX recovery_token_idx ON auth.users USING btree (recovery_token) WHERE ((recovery_token)::text !~ '^[0-9 ]*$'::text);


--
-- Name: refresh_tokens_instance_id_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX refresh_tokens_instance_id_idx ON auth.refresh_tokens USING btree (instance_id);


--
-- Name: refresh_tokens_instance_id_user_id_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX refresh_tokens_instance_id_user_id_idx ON auth.refresh_tokens USING btree (instance_id, user_id);


--
-- Name: refresh_tokens_parent_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX refresh_tokens_parent_idx ON auth.refresh_tokens USING btree (parent);


--
-- Name: refresh_tokens_session_id_revoked_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX refresh_tokens_session_id_revoked_idx ON auth.refresh_tokens USING btree (session_id, revoked);


--
-- Name: refresh_tokens_updated_at_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX refresh_tokens_updated_at_idx ON auth.refresh_tokens USING btree (updated_at DESC);


--
-- Name: saml_providers_sso_provider_id_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX saml_providers_sso_provider_id_idx ON auth.saml_providers USING btree (sso_provider_id);


--
-- Name: saml_relay_states_created_at_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX saml_relay_states_created_at_idx ON auth.saml_relay_states USING btree (created_at DESC);


--
-- Name: saml_relay_states_for_email_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX saml_relay_states_for_email_idx ON auth.saml_relay_states USING btree (for_email);


--
-- Name: saml_relay_states_sso_provider_id_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX saml_relay_states_sso_provider_id_idx ON auth.saml_relay_states USING btree (sso_provider_id);


--
-- Name: sessions_not_after_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX sessions_not_after_idx ON auth.sessions USING btree (not_after DESC);


--
-- Name: sessions_oauth_client_id_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX sessions_oauth_client_id_idx ON auth.sessions USING btree (oauth_client_id);


--
-- Name: sessions_user_id_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX sessions_user_id_idx ON auth.sessions USING btree (user_id);


--
-- Name: sso_domains_domain_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE UNIQUE INDEX sso_domains_domain_idx ON auth.sso_domains USING btree (lower(domain));


--
-- Name: sso_domains_sso_provider_id_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX sso_domains_sso_provider_id_idx ON auth.sso_domains USING btree (sso_provider_id);


--
-- Name: sso_providers_resource_id_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE UNIQUE INDEX sso_providers_resource_id_idx ON auth.sso_providers USING btree (lower(resource_id));


--
-- Name: sso_providers_resource_id_pattern_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX sso_providers_resource_id_pattern_idx ON auth.sso_providers USING btree (resource_id text_pattern_ops);


--
-- Name: unique_phone_factor_per_user; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE UNIQUE INDEX unique_phone_factor_per_user ON auth.mfa_factors USING btree (user_id, phone);


--
-- Name: user_id_created_at_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX user_id_created_at_idx ON auth.sessions USING btree (user_id, created_at);


--
-- Name: users_email_partial_key; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE UNIQUE INDEX users_email_partial_key ON auth.users USING btree (email) WHERE (is_sso_user = false);


--
-- Name: INDEX users_email_partial_key; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON INDEX auth.users_email_partial_key IS 'Auth: A partial unique index that applies only when is_sso_user is false';


--
-- Name: users_instance_id_email_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX users_instance_id_email_idx ON auth.users USING btree (instance_id, lower((email)::text));


--
-- Name: users_instance_id_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX users_instance_id_idx ON auth.users USING btree (instance_id);


--
-- Name: users_is_anonymous_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX users_is_anonymous_idx ON auth.users USING btree (is_anonymous);


--
-- Name: webauthn_challenges_expires_at_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX webauthn_challenges_expires_at_idx ON auth.webauthn_challenges USING btree (expires_at);


--
-- Name: webauthn_challenges_user_id_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX webauthn_challenges_user_id_idx ON auth.webauthn_challenges USING btree (user_id);


--
-- Name: webauthn_credentials_credential_id_key; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE UNIQUE INDEX webauthn_credentials_credential_id_key ON auth.webauthn_credentials USING btree (credential_id);


--
-- Name: webauthn_credentials_user_id_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX webauthn_credentials_user_id_idx ON auth.webauthn_credentials USING btree (user_id);


--
-- Name: idx_api_keys_emisor; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_api_keys_emisor ON public.api_keys USING btree (emisor_id, created_at DESC);


--
-- Name: idx_api_keys_hash; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_api_keys_hash ON public.api_keys USING btree (key_hash) WHERE (revoked = false);


--
-- Name: idx_auth_challenges_lookup; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_auth_challenges_lookup ON public.auth_challenges USING btree (emisor_id, tipo_accion, expires_at);


--
-- Name: idx_auth_challenges_pin; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_auth_challenges_pin ON public.auth_challenges USING btree (emisor_id, pin, tipo_accion, expires_at);


--
-- Name: idx_catalogo_items_emisor_codigo; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX idx_catalogo_items_emisor_codigo ON public.catalogo_items USING btree (emisor_id, codigo) WHERE (codigo IS NOT NULL);


--
-- Name: idx_clientes_emisor_identificacion; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_clientes_emisor_identificacion ON public.clientes_emisor USING btree (emisor_id, identificacion);


--
-- Name: idx_clientes_razon_social_trgm; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_clientes_razon_social_trgm ON public.clientes_emisor USING gin (razon_social public.gin_trgm_ops);


--
-- Name: idx_credit_transactions_emisor; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_credit_transactions_emisor ON public.credit_transactions USING btree (emisor_id, created_at DESC);


--
-- Name: idx_email_rate_limits_email; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_email_rate_limits_email ON public.email_rate_limits USING btree (email, last_sent);


--
-- Name: idx_emisores_ruc; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_emisores_ruc ON public.emisores USING btree (ruc);


--
-- Name: idx_establecimientos_emisor; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_establecimientos_emisor ON public.establecimientos USING btree (emisor_id, codigo);


--
-- Name: idx_invoices_clave_acceso; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_invoices_clave_acceso ON public.invoices_emitidas USING btree (clave_acceso);


--
-- Name: idx_invoices_emitidas_cliente; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_invoices_emitidas_cliente ON public.invoices_emitidas USING btree (emisor_id, identificacion_comprador);


--
-- Name: idx_invoices_emitidas_emisor_fecha; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_invoices_emitidas_emisor_fecha ON public.invoices_emitidas USING btree (emisor_id, fecha_emision DESC);


--
-- Name: idx_invoices_emitidas_estado; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_invoices_emitidas_estado ON public.invoices_emitidas USING btree (estado) WHERE ((estado)::text = ANY (ARRAY[('RECIBIDO'::character varying)::text, ('EN PROCESO'::character varying)::text]));


--
-- Name: idx_invoices_emitidas_export; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_invoices_emitidas_export ON public.invoices_emitidas USING btree (emisor_id, estado, fecha_emision DESC) WHERE (((estado)::text = 'AUTORIZADO'::text) AND (xml_path IS NOT NULL));


--
-- Name: idx_notificaciones_emisor; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_notificaciones_emisor ON public.notificaciones USING btree (emisor_id);


--
-- Name: idx_notificaciones_leida; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_notificaciones_leida ON public.notificaciones USING btree (emisor_id, leida);


--
-- Name: idx_profiles_email_lower; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_profiles_email_lower ON public.profiles USING btree (lower(email));


--
-- Name: idx_profiles_firebase_uid; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_profiles_firebase_uid ON public.profiles USING btree (firebase_uid);


--
-- Name: idx_profiles_whatsapp_number; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_profiles_whatsapp_number ON public.profiles USING btree (whatsapp_number) WHERE (whatsapp_number IS NOT NULL);


--
-- Name: idx_puntos_emision_emisor; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_puntos_emision_emisor ON public.puntos_emision USING btree (emisor_id, codigo);


--
-- Name: idx_puntos_emision_establecimiento; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_puntos_emision_establecimiento ON public.puntos_emision USING btree (establecimiento_id);


--
-- Name: idx_user_credits_emisor; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_user_credits_emisor ON public.user_credits USING btree (emisor_id);


--
-- Name: ix_realtime_subscription_entity; Type: INDEX; Schema: realtime; Owner: supabase_realtime_admin
--

CREATE INDEX ix_realtime_subscription_entity ON realtime.subscription USING btree (entity);


--
-- Name: messages_inserted_at_topic_index; Type: INDEX; Schema: realtime; Owner: supabase_realtime_admin
--

CREATE INDEX messages_inserted_at_topic_index ON ONLY realtime.messages USING btree (inserted_at DESC, topic) WHERE ((extension = 'broadcast'::text) AND (private IS TRUE));


--
-- Name: subscription_subscription_id_entity_filters_action_filter_selec; Type: INDEX; Schema: realtime; Owner: supabase_realtime_admin
--

CREATE UNIQUE INDEX subscription_subscription_id_entity_filters_action_filter_selec ON realtime.subscription USING btree (subscription_id, entity, filters, action_filter, COALESCE(selected_columns, '{}'::text[]));


--
-- Name: bname; Type: INDEX; Schema: storage; Owner: supabase_storage_admin
--

CREATE UNIQUE INDEX bname ON storage.buckets USING btree (name);


--
-- Name: bucketid_objname; Type: INDEX; Schema: storage; Owner: supabase_storage_admin
--

CREATE UNIQUE INDEX bucketid_objname ON storage.objects USING btree (bucket_id, name);


--
-- Name: buckets_analytics_unique_name_idx; Type: INDEX; Schema: storage; Owner: supabase_storage_admin
--

CREATE UNIQUE INDEX buckets_analytics_unique_name_idx ON storage.buckets_analytics USING btree (name) WHERE (deleted_at IS NULL);


--
-- Name: idx_multipart_uploads_list; Type: INDEX; Schema: storage; Owner: supabase_storage_admin
--

CREATE INDEX idx_multipart_uploads_list ON storage.s3_multipart_uploads USING btree (bucket_id, key, created_at);


--
-- Name: idx_objects_bucket_id_name; Type: INDEX; Schema: storage; Owner: supabase_storage_admin
--

CREATE INDEX idx_objects_bucket_id_name ON storage.objects USING btree (bucket_id, name COLLATE "C");


--
-- Name: idx_objects_bucket_id_name_lower; Type: INDEX; Schema: storage; Owner: supabase_storage_admin
--

CREATE INDEX idx_objects_bucket_id_name_lower ON storage.objects USING btree (bucket_id, lower(name) COLLATE "C");


--
-- Name: name_prefix_search; Type: INDEX; Schema: storage; Owner: supabase_storage_admin
--

CREATE INDEX name_prefix_search ON storage.objects USING btree (name text_pattern_ops);


--
-- Name: vector_indexes_name_bucket_id_idx; Type: INDEX; Schema: storage; Owner: supabase_storage_admin
--

CREATE UNIQUE INDEX vector_indexes_name_bucket_id_idx ON storage.vector_indexes USING btree (name, bucket_id);


--
-- Name: subscription tr_check_filters; Type: TRIGGER; Schema: realtime; Owner: supabase_realtime_admin
--

CREATE TRIGGER tr_check_filters BEFORE INSERT OR UPDATE ON realtime.subscription FOR EACH ROW EXECUTE FUNCTION realtime.subscription_check_filters();


--
-- Name: buckets enforce_bucket_name_length_trigger; Type: TRIGGER; Schema: storage; Owner: supabase_storage_admin
--

CREATE TRIGGER enforce_bucket_name_length_trigger BEFORE INSERT OR UPDATE OF name ON storage.buckets FOR EACH ROW EXECUTE FUNCTION storage.enforce_bucket_name_length();


--
-- Name: buckets protect_buckets_delete; Type: TRIGGER; Schema: storage; Owner: supabase_storage_admin
--

CREATE TRIGGER protect_buckets_delete BEFORE DELETE ON storage.buckets FOR EACH STATEMENT EXECUTE FUNCTION storage.protect_delete();


--
-- Name: objects protect_objects_delete; Type: TRIGGER; Schema: storage; Owner: supabase_storage_admin
--

CREATE TRIGGER protect_objects_delete BEFORE DELETE ON storage.objects FOR EACH STATEMENT EXECUTE FUNCTION storage.protect_delete();


--
-- Name: objects update_objects_updated_at; Type: TRIGGER; Schema: storage; Owner: supabase_storage_admin
--

CREATE TRIGGER update_objects_updated_at BEFORE UPDATE ON storage.objects FOR EACH ROW EXECUTE FUNCTION storage.update_updated_at_column();


--
-- Name: identities identities_user_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.identities
    ADD CONSTRAINT identities_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;


--
-- Name: mfa_amr_claims mfa_amr_claims_session_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.mfa_amr_claims
    ADD CONSTRAINT mfa_amr_claims_session_id_fkey FOREIGN KEY (session_id) REFERENCES auth.sessions(id) ON DELETE CASCADE;


--
-- Name: mfa_challenges mfa_challenges_auth_factor_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.mfa_challenges
    ADD CONSTRAINT mfa_challenges_auth_factor_id_fkey FOREIGN KEY (factor_id) REFERENCES auth.mfa_factors(id) ON DELETE CASCADE;


--
-- Name: mfa_factors mfa_factors_user_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.mfa_factors
    ADD CONSTRAINT mfa_factors_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;


--
-- Name: oauth_authorizations oauth_authorizations_client_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.oauth_authorizations
    ADD CONSTRAINT oauth_authorizations_client_id_fkey FOREIGN KEY (client_id) REFERENCES auth.oauth_clients(id) ON DELETE CASCADE;


--
-- Name: oauth_authorizations oauth_authorizations_user_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.oauth_authorizations
    ADD CONSTRAINT oauth_authorizations_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;


--
-- Name: oauth_consents oauth_consents_client_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.oauth_consents
    ADD CONSTRAINT oauth_consents_client_id_fkey FOREIGN KEY (client_id) REFERENCES auth.oauth_clients(id) ON DELETE CASCADE;


--
-- Name: oauth_consents oauth_consents_user_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.oauth_consents
    ADD CONSTRAINT oauth_consents_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;


--
-- Name: one_time_tokens one_time_tokens_user_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.one_time_tokens
    ADD CONSTRAINT one_time_tokens_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;


--
-- Name: refresh_tokens refresh_tokens_session_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.refresh_tokens
    ADD CONSTRAINT refresh_tokens_session_id_fkey FOREIGN KEY (session_id) REFERENCES auth.sessions(id) ON DELETE CASCADE;


--
-- Name: saml_providers saml_providers_sso_provider_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.saml_providers
    ADD CONSTRAINT saml_providers_sso_provider_id_fkey FOREIGN KEY (sso_provider_id) REFERENCES auth.sso_providers(id) ON DELETE CASCADE;


--
-- Name: saml_relay_states saml_relay_states_flow_state_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.saml_relay_states
    ADD CONSTRAINT saml_relay_states_flow_state_id_fkey FOREIGN KEY (flow_state_id) REFERENCES auth.flow_state(id) ON DELETE CASCADE;


--
-- Name: saml_relay_states saml_relay_states_sso_provider_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.saml_relay_states
    ADD CONSTRAINT saml_relay_states_sso_provider_id_fkey FOREIGN KEY (sso_provider_id) REFERENCES auth.sso_providers(id) ON DELETE CASCADE;


--
-- Name: sessions sessions_oauth_client_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.sessions
    ADD CONSTRAINT sessions_oauth_client_id_fkey FOREIGN KEY (oauth_client_id) REFERENCES auth.oauth_clients(id) ON DELETE CASCADE;


--
-- Name: sessions sessions_user_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.sessions
    ADD CONSTRAINT sessions_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;


--
-- Name: sso_domains sso_domains_sso_provider_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.sso_domains
    ADD CONSTRAINT sso_domains_sso_provider_id_fkey FOREIGN KEY (sso_provider_id) REFERENCES auth.sso_providers(id) ON DELETE CASCADE;


--
-- Name: webauthn_challenges webauthn_challenges_user_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.webauthn_challenges
    ADD CONSTRAINT webauthn_challenges_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;


--
-- Name: webauthn_credentials webauthn_credentials_user_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.webauthn_credentials
    ADD CONSTRAINT webauthn_credentials_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;


--
-- Name: api_keys api_keys_emisor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.api_keys
    ADD CONSTRAINT api_keys_emisor_id_fkey FOREIGN KEY (emisor_id) REFERENCES public.emisores(id) ON DELETE CASCADE;


--
-- Name: auth_challenges auth_challenges_emisor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.auth_challenges
    ADD CONSTRAINT auth_challenges_emisor_id_fkey FOREIGN KEY (emisor_id) REFERENCES public.emisores(id) ON DELETE CASCADE;


--
-- Name: catalogo_items catalogo_items_emisor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.catalogo_items
    ADD CONSTRAINT catalogo_items_emisor_id_fkey FOREIGN KEY (emisor_id) REFERENCES public.emisores(id) ON DELETE CASCADE;


--
-- Name: clientes_emisor clientes_emisor_emisor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.clientes_emisor
    ADD CONSTRAINT clientes_emisor_emisor_id_fkey FOREIGN KEY (emisor_id) REFERENCES public.emisores(id) ON DELETE CASCADE;


--
-- Name: clientes_emisor clientes_emisor_sujeto_global_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.clientes_emisor
    ADD CONSTRAINT clientes_emisor_sujeto_global_id_fkey FOREIGN KEY (sujeto_global_id) REFERENCES public.sujetos_global(id) ON DELETE SET NULL;


--
-- Name: credit_transactions credit_transactions_emisor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.credit_transactions
    ADD CONSTRAINT credit_transactions_emisor_id_fkey FOREIGN KEY (emisor_id) REFERENCES public.emisores(id) ON DELETE CASCADE;


--
-- Name: declaraciones_sri declaraciones_sri_declarado_por_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.declaraciones_sri
    ADD CONSTRAINT declaraciones_sri_declarado_por_fkey FOREIGN KEY (declarado_por) REFERENCES public.profiles(id);


--
-- Name: declaraciones_sri declaraciones_sri_emisor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.declaraciones_sri
    ADD CONSTRAINT declaraciones_sri_emisor_id_fkey FOREIGN KEY (emisor_id) REFERENCES public.emisores(id) ON DELETE CASCADE;


--
-- Name: emisor_usuarios emisor_usuarios_emisor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.emisor_usuarios
    ADD CONSTRAINT emisor_usuarios_emisor_id_fkey FOREIGN KEY (emisor_id) REFERENCES public.emisores(id) ON DELETE CASCADE;


--
-- Name: emisor_usuarios emisor_usuarios_profile_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.emisor_usuarios
    ADD CONSTRAINT emisor_usuarios_profile_id_fkey FOREIGN KEY (profile_id) REFERENCES public.profiles(id) ON DELETE CASCADE;


--
-- Name: establecimientos establecimientos_emisor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.establecimientos
    ADD CONSTRAINT establecimientos_emisor_id_fkey FOREIGN KEY (emisor_id) REFERENCES public.emisores(id) ON DELETE CASCADE;


--
-- Name: fcm_tokens fcm_tokens_emisor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.fcm_tokens
    ADD CONSTRAINT fcm_tokens_emisor_id_fkey FOREIGN KEY (emisor_id) REFERENCES public.emisores(id) ON DELETE CASCADE;


--
-- Name: fcm_tokens fcm_tokens_profile_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.fcm_tokens
    ADD CONSTRAINT fcm_tokens_profile_id_fkey FOREIGN KEY (profile_id) REFERENCES public.profiles(id) ON DELETE CASCADE;


--
-- Name: invoices_recibidas fk_invoices_recibidas_emisor; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.invoices_recibidas
    ADD CONSTRAINT fk_invoices_recibidas_emisor FOREIGN KEY (emisor_id) REFERENCES public.emisores(id) ON DELETE CASCADE;


--
-- Name: invoices_emitidas invoices_cliente_emisor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.invoices_emitidas
    ADD CONSTRAINT invoices_cliente_emisor_id_fkey FOREIGN KEY (cliente_emisor_id) REFERENCES public.clientes_emisor(id) ON DELETE SET NULL;


--
-- Name: invoices_emitidas invoices_emisor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.invoices_emitidas
    ADD CONSTRAINT invoices_emisor_id_fkey FOREIGN KEY (emisor_id) REFERENCES public.emisores(id) ON DELETE CASCADE;


--
-- Name: invoices_emitidas invoices_emitidas_api_key_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.invoices_emitidas
    ADD CONSTRAINT invoices_emitidas_api_key_id_fkey FOREIGN KEY (api_key_id) REFERENCES public.api_keys(id) ON DELETE SET NULL;


--
-- Name: invoices_emitidas invoices_emitidas_doc_referencia_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.invoices_emitidas
    ADD CONSTRAINT invoices_emitidas_doc_referencia_id_fkey FOREIGN KEY (doc_referencia_id) REFERENCES public.invoices_emitidas(id);


--
-- Name: invoices_emitidas invoices_punto_emision_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.invoices_emitidas
    ADD CONSTRAINT invoices_punto_emision_id_fkey FOREIGN KEY (punto_emision_id) REFERENCES public.puntos_emision(id);


--
-- Name: invoices_recibidas invoices_recibidas_emisor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.invoices_recibidas
    ADD CONSTRAINT invoices_recibidas_emisor_id_fkey FOREIGN KEY (emisor_id) REFERENCES public.emisores(id);


--
-- Name: notificaciones notificaciones_emisor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.notificaciones
    ADD CONSTRAINT notificaciones_emisor_id_fkey FOREIGN KEY (emisor_id) REFERENCES public.emisores(id) ON DELETE CASCADE;


--
-- Name: profiles profiles_emisor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.profiles
    ADD CONSTRAINT profiles_emisor_id_fkey FOREIGN KEY (emisor_id) REFERENCES public.emisores(id) ON DELETE SET NULL;


--
-- Name: puntos_emision puntos_emision_emisor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.puntos_emision
    ADD CONSTRAINT puntos_emision_emisor_id_fkey FOREIGN KEY (emisor_id) REFERENCES public.emisores(id) ON DELETE CASCADE;


--
-- Name: puntos_emision puntos_emision_establecimiento_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.puntos_emision
    ADD CONSTRAINT puntos_emision_establecimiento_id_fkey FOREIGN KEY (establecimiento_id) REFERENCES public.establecimientos(id) ON DELETE CASCADE;


--
-- Name: transaction_logs transaction_logs_target_emisor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.transaction_logs
    ADD CONSTRAINT transaction_logs_target_emisor_id_fkey FOREIGN KEY (target_emisor_id) REFERENCES public.emisores(id) ON DELETE SET NULL;


--
-- Name: user_credits user_credits_emisor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_credits
    ADD CONSTRAINT user_credits_emisor_id_fkey FOREIGN KEY (emisor_id) REFERENCES public.emisores(id) ON DELETE CASCADE;


--
-- Name: webhooks webhooks_api_key_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.webhooks
    ADD CONSTRAINT webhooks_api_key_id_fkey FOREIGN KEY (api_key_id) REFERENCES public.api_keys(id) ON DELETE CASCADE;


--
-- Name: webhooks webhooks_emisor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.webhooks
    ADD CONSTRAINT webhooks_emisor_id_fkey FOREIGN KEY (emisor_id) REFERENCES public.emisores(id) ON DELETE CASCADE;


--
-- Name: objects objects_bucketId_fkey; Type: FK CONSTRAINT; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE ONLY storage.objects
    ADD CONSTRAINT "objects_bucketId_fkey" FOREIGN KEY (bucket_id) REFERENCES storage.buckets(id);


--
-- Name: s3_multipart_uploads s3_multipart_uploads_bucket_id_fkey; Type: FK CONSTRAINT; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE ONLY storage.s3_multipart_uploads
    ADD CONSTRAINT s3_multipart_uploads_bucket_id_fkey FOREIGN KEY (bucket_id) REFERENCES storage.buckets(id);


--
-- Name: s3_multipart_uploads_parts s3_multipart_uploads_parts_bucket_id_fkey; Type: FK CONSTRAINT; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE ONLY storage.s3_multipart_uploads_parts
    ADD CONSTRAINT s3_multipart_uploads_parts_bucket_id_fkey FOREIGN KEY (bucket_id) REFERENCES storage.buckets(id);


--
-- Name: s3_multipart_uploads_parts s3_multipart_uploads_parts_upload_id_fkey; Type: FK CONSTRAINT; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE ONLY storage.s3_multipart_uploads_parts
    ADD CONSTRAINT s3_multipart_uploads_parts_upload_id_fkey FOREIGN KEY (upload_id) REFERENCES storage.s3_multipart_uploads(id) ON DELETE CASCADE;


--
-- Name: vector_indexes vector_indexes_bucket_id_fkey; Type: FK CONSTRAINT; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE ONLY storage.vector_indexes
    ADD CONSTRAINT vector_indexes_bucket_id_fkey FOREIGN KEY (bucket_id) REFERENCES storage.buckets_vectors(id);


--
-- Name: audit_log_entries; Type: ROW SECURITY; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE auth.audit_log_entries ENABLE ROW LEVEL SECURITY;

--
-- Name: flow_state; Type: ROW SECURITY; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE auth.flow_state ENABLE ROW LEVEL SECURITY;

--
-- Name: identities; Type: ROW SECURITY; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE auth.identities ENABLE ROW LEVEL SECURITY;

--
-- Name: instances; Type: ROW SECURITY; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE auth.instances ENABLE ROW LEVEL SECURITY;

--
-- Name: mfa_amr_claims; Type: ROW SECURITY; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE auth.mfa_amr_claims ENABLE ROW LEVEL SECURITY;

--
-- Name: mfa_challenges; Type: ROW SECURITY; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE auth.mfa_challenges ENABLE ROW LEVEL SECURITY;

--
-- Name: mfa_factors; Type: ROW SECURITY; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE auth.mfa_factors ENABLE ROW LEVEL SECURITY;

--
-- Name: one_time_tokens; Type: ROW SECURITY; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE auth.one_time_tokens ENABLE ROW LEVEL SECURITY;

--
-- Name: refresh_tokens; Type: ROW SECURITY; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE auth.refresh_tokens ENABLE ROW LEVEL SECURITY;

--
-- Name: saml_providers; Type: ROW SECURITY; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE auth.saml_providers ENABLE ROW LEVEL SECURITY;

--
-- Name: saml_relay_states; Type: ROW SECURITY; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE auth.saml_relay_states ENABLE ROW LEVEL SECURITY;

--
-- Name: schema_migrations; Type: ROW SECURITY; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE auth.schema_migrations ENABLE ROW LEVEL SECURITY;

--
-- Name: sessions; Type: ROW SECURITY; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE auth.sessions ENABLE ROW LEVEL SECURITY;

--
-- Name: sso_domains; Type: ROW SECURITY; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE auth.sso_domains ENABLE ROW LEVEL SECURITY;

--
-- Name: sso_providers; Type: ROW SECURITY; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE auth.sso_providers ENABLE ROW LEVEL SECURITY;

--
-- Name: users; Type: ROW SECURITY; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE auth.users ENABLE ROW LEVEL SECURITY;

--
-- Name: messages; Type: ROW SECURITY; Schema: realtime; Owner: supabase_realtime_admin
--

ALTER TABLE realtime.messages ENABLE ROW LEVEL SECURITY;

--
-- Name: buckets; Type: ROW SECURITY; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE storage.buckets ENABLE ROW LEVEL SECURITY;

--
-- Name: buckets_analytics; Type: ROW SECURITY; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE storage.buckets_analytics ENABLE ROW LEVEL SECURITY;

--
-- Name: buckets_vectors; Type: ROW SECURITY; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE storage.buckets_vectors ENABLE ROW LEVEL SECURITY;

--
-- Name: migrations; Type: ROW SECURITY; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE storage.migrations ENABLE ROW LEVEL SECURITY;

--
-- Name: objects; Type: ROW SECURITY; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE storage.objects ENABLE ROW LEVEL SECURITY;

--
-- Name: s3_multipart_uploads; Type: ROW SECURITY; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE storage.s3_multipart_uploads ENABLE ROW LEVEL SECURITY;

--
-- Name: s3_multipart_uploads_parts; Type: ROW SECURITY; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE storage.s3_multipart_uploads_parts ENABLE ROW LEVEL SECURITY;

--
-- Name: vector_indexes; Type: ROW SECURITY; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE storage.vector_indexes ENABLE ROW LEVEL SECURITY;

--
-- Name: supabase_realtime; Type: PUBLICATION; Schema: -; Owner: postgres
--

CREATE PUBLICATION supabase_realtime WITH (publish = 'insert, update, delete, truncate');


ALTER PUBLICATION supabase_realtime OWNER TO postgres;

--
-- Name: SCHEMA auth; Type: ACL; Schema: -; Owner: supabase_admin
--

GRANT USAGE ON SCHEMA auth TO anon;
GRANT USAGE ON SCHEMA auth TO authenticated;
GRANT USAGE ON SCHEMA auth TO service_role;
GRANT ALL ON SCHEMA auth TO supabase_auth_admin;
GRANT ALL ON SCHEMA auth TO dashboard_user;
GRANT USAGE ON SCHEMA auth TO postgres;


--
-- Name: SCHEMA extensions; Type: ACL; Schema: -; Owner: postgres
--

GRANT USAGE ON SCHEMA extensions TO anon;
GRANT USAGE ON SCHEMA extensions TO authenticated;
GRANT USAGE ON SCHEMA extensions TO service_role;
GRANT ALL ON SCHEMA extensions TO dashboard_user;


--
-- Name: SCHEMA public; Type: ACL; Schema: -; Owner: pg_database_owner
--

GRANT USAGE ON SCHEMA public TO postgres;
GRANT USAGE ON SCHEMA public TO anon;
GRANT USAGE ON SCHEMA public TO authenticated;
GRANT USAGE ON SCHEMA public TO service_role;


--
-- Name: SCHEMA realtime; Type: ACL; Schema: -; Owner: supabase_admin
--

GRANT USAGE ON SCHEMA realtime TO postgres WITH GRANT OPTION;
GRANT USAGE ON SCHEMA realtime TO anon;
GRANT USAGE ON SCHEMA realtime TO authenticated;
GRANT USAGE ON SCHEMA realtime TO service_role;
GRANT ALL ON SCHEMA realtime TO supabase_realtime_admin;


--
-- Name: SCHEMA storage; Type: ACL; Schema: -; Owner: supabase_admin
--

GRANT USAGE ON SCHEMA storage TO postgres WITH GRANT OPTION;
GRANT USAGE ON SCHEMA storage TO anon;
GRANT USAGE ON SCHEMA storage TO authenticated;
GRANT USAGE ON SCHEMA storage TO service_role;
GRANT ALL ON SCHEMA storage TO supabase_storage_admin WITH GRANT OPTION;
GRANT ALL ON SCHEMA storage TO dashboard_user;


--
-- Name: SCHEMA vault; Type: ACL; Schema: -; Owner: supabase_admin
--

GRANT USAGE ON SCHEMA vault TO postgres WITH GRANT OPTION;
GRANT USAGE ON SCHEMA vault TO service_role;


--
-- Name: FUNCTION gtrgm_in(cstring); Type: ACL; Schema: public; Owner: supabase_admin
--

GRANT ALL ON FUNCTION public.gtrgm_in(cstring) TO postgres;
GRANT ALL ON FUNCTION public.gtrgm_in(cstring) TO anon;
GRANT ALL ON FUNCTION public.gtrgm_in(cstring) TO authenticated;
GRANT ALL ON FUNCTION public.gtrgm_in(cstring) TO service_role;


--
-- Name: FUNCTION gtrgm_out(public.gtrgm); Type: ACL; Schema: public; Owner: supabase_admin
--

GRANT ALL ON FUNCTION public.gtrgm_out(public.gtrgm) TO postgres;
GRANT ALL ON FUNCTION public.gtrgm_out(public.gtrgm) TO anon;
GRANT ALL ON FUNCTION public.gtrgm_out(public.gtrgm) TO authenticated;
GRANT ALL ON FUNCTION public.gtrgm_out(public.gtrgm) TO service_role;


--
-- Name: FUNCTION email(); Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT ALL ON FUNCTION auth.email() TO dashboard_user;


--
-- Name: FUNCTION jwt(); Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT ALL ON FUNCTION auth.jwt() TO postgres;
GRANT ALL ON FUNCTION auth.jwt() TO dashboard_user;


--
-- Name: FUNCTION role(); Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT ALL ON FUNCTION auth.role() TO dashboard_user;


--
-- Name: FUNCTION uid(); Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT ALL ON FUNCTION auth.uid() TO dashboard_user;


--
-- Name: FUNCTION armor(bytea); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.armor(bytea) FROM postgres;
GRANT ALL ON FUNCTION extensions.armor(bytea) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.armor(bytea) TO dashboard_user;


--
-- Name: FUNCTION armor(bytea, text[], text[]); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.armor(bytea, text[], text[]) FROM postgres;
GRANT ALL ON FUNCTION extensions.armor(bytea, text[], text[]) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.armor(bytea, text[], text[]) TO dashboard_user;


--
-- Name: FUNCTION crypt(text, text); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.crypt(text, text) FROM postgres;
GRANT ALL ON FUNCTION extensions.crypt(text, text) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.crypt(text, text) TO dashboard_user;


--
-- Name: FUNCTION dearmor(text); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.dearmor(text) FROM postgres;
GRANT ALL ON FUNCTION extensions.dearmor(text) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.dearmor(text) TO dashboard_user;


--
-- Name: FUNCTION decrypt(bytea, bytea, text); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.decrypt(bytea, bytea, text) FROM postgres;
GRANT ALL ON FUNCTION extensions.decrypt(bytea, bytea, text) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.decrypt(bytea, bytea, text) TO dashboard_user;


--
-- Name: FUNCTION decrypt_iv(bytea, bytea, bytea, text); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.decrypt_iv(bytea, bytea, bytea, text) FROM postgres;
GRANT ALL ON FUNCTION extensions.decrypt_iv(bytea, bytea, bytea, text) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.decrypt_iv(bytea, bytea, bytea, text) TO dashboard_user;


--
-- Name: FUNCTION digest(bytea, text); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.digest(bytea, text) FROM postgres;
GRANT ALL ON FUNCTION extensions.digest(bytea, text) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.digest(bytea, text) TO dashboard_user;


--
-- Name: FUNCTION digest(text, text); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.digest(text, text) FROM postgres;
GRANT ALL ON FUNCTION extensions.digest(text, text) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.digest(text, text) TO dashboard_user;


--
-- Name: FUNCTION encrypt(bytea, bytea, text); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.encrypt(bytea, bytea, text) FROM postgres;
GRANT ALL ON FUNCTION extensions.encrypt(bytea, bytea, text) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.encrypt(bytea, bytea, text) TO dashboard_user;


--
-- Name: FUNCTION encrypt_iv(bytea, bytea, bytea, text); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.encrypt_iv(bytea, bytea, bytea, text) FROM postgres;
GRANT ALL ON FUNCTION extensions.encrypt_iv(bytea, bytea, bytea, text) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.encrypt_iv(bytea, bytea, bytea, text) TO dashboard_user;


--
-- Name: FUNCTION gen_random_bytes(integer); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.gen_random_bytes(integer) FROM postgres;
GRANT ALL ON FUNCTION extensions.gen_random_bytes(integer) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.gen_random_bytes(integer) TO dashboard_user;


--
-- Name: FUNCTION gen_random_uuid(); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.gen_random_uuid() FROM postgres;
GRANT ALL ON FUNCTION extensions.gen_random_uuid() TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.gen_random_uuid() TO dashboard_user;


--
-- Name: FUNCTION gen_salt(text); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.gen_salt(text) FROM postgres;
GRANT ALL ON FUNCTION extensions.gen_salt(text) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.gen_salt(text) TO dashboard_user;


--
-- Name: FUNCTION gen_salt(text, integer); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.gen_salt(text, integer) FROM postgres;
GRANT ALL ON FUNCTION extensions.gen_salt(text, integer) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.gen_salt(text, integer) TO dashboard_user;


--
-- Name: FUNCTION grant_pg_cron_access(); Type: ACL; Schema: extensions; Owner: supabase_admin
--

REVOKE ALL ON FUNCTION extensions.grant_pg_cron_access() FROM supabase_admin;
GRANT ALL ON FUNCTION extensions.grant_pg_cron_access() TO supabase_admin WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.grant_pg_cron_access() TO dashboard_user;


--
-- Name: FUNCTION grant_pg_graphql_access(); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.grant_pg_graphql_access() TO postgres WITH GRANT OPTION;


--
-- Name: FUNCTION grant_pg_net_access(); Type: ACL; Schema: extensions; Owner: supabase_admin
--

REVOKE ALL ON FUNCTION extensions.grant_pg_net_access() FROM supabase_admin;
GRANT ALL ON FUNCTION extensions.grant_pg_net_access() TO supabase_admin WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.grant_pg_net_access() TO dashboard_user;


--
-- Name: FUNCTION hmac(bytea, bytea, text); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.hmac(bytea, bytea, text) FROM postgres;
GRANT ALL ON FUNCTION extensions.hmac(bytea, bytea, text) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.hmac(bytea, bytea, text) TO dashboard_user;


--
-- Name: FUNCTION hmac(text, text, text); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.hmac(text, text, text) FROM postgres;
GRANT ALL ON FUNCTION extensions.hmac(text, text, text) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.hmac(text, text, text) TO dashboard_user;


--
-- Name: FUNCTION pg_stat_statements(showtext boolean, OUT userid oid, OUT dbid oid, OUT toplevel boolean, OUT queryid bigint, OUT query text, OUT plans bigint, OUT total_plan_time double precision, OUT min_plan_time double precision, OUT max_plan_time double precision, OUT mean_plan_time double precision, OUT stddev_plan_time double precision, OUT calls bigint, OUT total_exec_time double precision, OUT min_exec_time double precision, OUT max_exec_time double precision, OUT mean_exec_time double precision, OUT stddev_exec_time double precision, OUT rows bigint, OUT shared_blks_hit bigint, OUT shared_blks_read bigint, OUT shared_blks_dirtied bigint, OUT shared_blks_written bigint, OUT local_blks_hit bigint, OUT local_blks_read bigint, OUT local_blks_dirtied bigint, OUT local_blks_written bigint, OUT temp_blks_read bigint, OUT temp_blks_written bigint, OUT shared_blk_read_time double precision, OUT shared_blk_write_time double precision, OUT local_blk_read_time double precision, OUT local_blk_write_time double precision, OUT temp_blk_read_time double precision, OUT temp_blk_write_time double precision, OUT wal_records bigint, OUT wal_fpi bigint, OUT wal_bytes numeric, OUT jit_functions bigint, OUT jit_generation_time double precision, OUT jit_inlining_count bigint, OUT jit_inlining_time double precision, OUT jit_optimization_count bigint, OUT jit_optimization_time double precision, OUT jit_emission_count bigint, OUT jit_emission_time double precision, OUT jit_deform_count bigint, OUT jit_deform_time double precision, OUT stats_since timestamp with time zone, OUT minmax_stats_since timestamp with time zone); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.pg_stat_statements(showtext boolean, OUT userid oid, OUT dbid oid, OUT toplevel boolean, OUT queryid bigint, OUT query text, OUT plans bigint, OUT total_plan_time double precision, OUT min_plan_time double precision, OUT max_plan_time double precision, OUT mean_plan_time double precision, OUT stddev_plan_time double precision, OUT calls bigint, OUT total_exec_time double precision, OUT min_exec_time double precision, OUT max_exec_time double precision, OUT mean_exec_time double precision, OUT stddev_exec_time double precision, OUT rows bigint, OUT shared_blks_hit bigint, OUT shared_blks_read bigint, OUT shared_blks_dirtied bigint, OUT shared_blks_written bigint, OUT local_blks_hit bigint, OUT local_blks_read bigint, OUT local_blks_dirtied bigint, OUT local_blks_written bigint, OUT temp_blks_read bigint, OUT temp_blks_written bigint, OUT shared_blk_read_time double precision, OUT shared_blk_write_time double precision, OUT local_blk_read_time double precision, OUT local_blk_write_time double precision, OUT temp_blk_read_time double precision, OUT temp_blk_write_time double precision, OUT wal_records bigint, OUT wal_fpi bigint, OUT wal_bytes numeric, OUT jit_functions bigint, OUT jit_generation_time double precision, OUT jit_inlining_count bigint, OUT jit_inlining_time double precision, OUT jit_optimization_count bigint, OUT jit_optimization_time double precision, OUT jit_emission_count bigint, OUT jit_emission_time double precision, OUT jit_deform_count bigint, OUT jit_deform_time double precision, OUT stats_since timestamp with time zone, OUT minmax_stats_since timestamp with time zone) FROM postgres;
GRANT ALL ON FUNCTION extensions.pg_stat_statements(showtext boolean, OUT userid oid, OUT dbid oid, OUT toplevel boolean, OUT queryid bigint, OUT query text, OUT plans bigint, OUT total_plan_time double precision, OUT min_plan_time double precision, OUT max_plan_time double precision, OUT mean_plan_time double precision, OUT stddev_plan_time double precision, OUT calls bigint, OUT total_exec_time double precision, OUT min_exec_time double precision, OUT max_exec_time double precision, OUT mean_exec_time double precision, OUT stddev_exec_time double precision, OUT rows bigint, OUT shared_blks_hit bigint, OUT shared_blks_read bigint, OUT shared_blks_dirtied bigint, OUT shared_blks_written bigint, OUT local_blks_hit bigint, OUT local_blks_read bigint, OUT local_blks_dirtied bigint, OUT local_blks_written bigint, OUT temp_blks_read bigint, OUT temp_blks_written bigint, OUT shared_blk_read_time double precision, OUT shared_blk_write_time double precision, OUT local_blk_read_time double precision, OUT local_blk_write_time double precision, OUT temp_blk_read_time double precision, OUT temp_blk_write_time double precision, OUT wal_records bigint, OUT wal_fpi bigint, OUT wal_bytes numeric, OUT jit_functions bigint, OUT jit_generation_time double precision, OUT jit_inlining_count bigint, OUT jit_inlining_time double precision, OUT jit_optimization_count bigint, OUT jit_optimization_time double precision, OUT jit_emission_count bigint, OUT jit_emission_time double precision, OUT jit_deform_count bigint, OUT jit_deform_time double precision, OUT stats_since timestamp with time zone, OUT minmax_stats_since timestamp with time zone) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.pg_stat_statements(showtext boolean, OUT userid oid, OUT dbid oid, OUT toplevel boolean, OUT queryid bigint, OUT query text, OUT plans bigint, OUT total_plan_time double precision, OUT min_plan_time double precision, OUT max_plan_time double precision, OUT mean_plan_time double precision, OUT stddev_plan_time double precision, OUT calls bigint, OUT total_exec_time double precision, OUT min_exec_time double precision, OUT max_exec_time double precision, OUT mean_exec_time double precision, OUT stddev_exec_time double precision, OUT rows bigint, OUT shared_blks_hit bigint, OUT shared_blks_read bigint, OUT shared_blks_dirtied bigint, OUT shared_blks_written bigint, OUT local_blks_hit bigint, OUT local_blks_read bigint, OUT local_blks_dirtied bigint, OUT local_blks_written bigint, OUT temp_blks_read bigint, OUT temp_blks_written bigint, OUT shared_blk_read_time double precision, OUT shared_blk_write_time double precision, OUT local_blk_read_time double precision, OUT local_blk_write_time double precision, OUT temp_blk_read_time double precision, OUT temp_blk_write_time double precision, OUT wal_records bigint, OUT wal_fpi bigint, OUT wal_bytes numeric, OUT jit_functions bigint, OUT jit_generation_time double precision, OUT jit_inlining_count bigint, OUT jit_inlining_time double precision, OUT jit_optimization_count bigint, OUT jit_optimization_time double precision, OUT jit_emission_count bigint, OUT jit_emission_time double precision, OUT jit_deform_count bigint, OUT jit_deform_time double precision, OUT stats_since timestamp with time zone, OUT minmax_stats_since timestamp with time zone) TO dashboard_user;


--
-- Name: FUNCTION pg_stat_statements_info(OUT dealloc bigint, OUT stats_reset timestamp with time zone); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.pg_stat_statements_info(OUT dealloc bigint, OUT stats_reset timestamp with time zone) FROM postgres;
GRANT ALL ON FUNCTION extensions.pg_stat_statements_info(OUT dealloc bigint, OUT stats_reset timestamp with time zone) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.pg_stat_statements_info(OUT dealloc bigint, OUT stats_reset timestamp with time zone) TO dashboard_user;


--
-- Name: FUNCTION pg_stat_statements_reset(userid oid, dbid oid, queryid bigint, minmax_only boolean); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.pg_stat_statements_reset(userid oid, dbid oid, queryid bigint, minmax_only boolean) FROM postgres;
GRANT ALL ON FUNCTION extensions.pg_stat_statements_reset(userid oid, dbid oid, queryid bigint, minmax_only boolean) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.pg_stat_statements_reset(userid oid, dbid oid, queryid bigint, minmax_only boolean) TO dashboard_user;


--
-- Name: FUNCTION pgp_armor_headers(text, OUT key text, OUT value text); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.pgp_armor_headers(text, OUT key text, OUT value text) FROM postgres;
GRANT ALL ON FUNCTION extensions.pgp_armor_headers(text, OUT key text, OUT value text) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.pgp_armor_headers(text, OUT key text, OUT value text) TO dashboard_user;


--
-- Name: FUNCTION pgp_key_id(bytea); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.pgp_key_id(bytea) FROM postgres;
GRANT ALL ON FUNCTION extensions.pgp_key_id(bytea) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.pgp_key_id(bytea) TO dashboard_user;


--
-- Name: FUNCTION pgp_pub_decrypt(bytea, bytea); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.pgp_pub_decrypt(bytea, bytea) FROM postgres;
GRANT ALL ON FUNCTION extensions.pgp_pub_decrypt(bytea, bytea) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.pgp_pub_decrypt(bytea, bytea) TO dashboard_user;


--
-- Name: FUNCTION pgp_pub_decrypt(bytea, bytea, text); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.pgp_pub_decrypt(bytea, bytea, text) FROM postgres;
GRANT ALL ON FUNCTION extensions.pgp_pub_decrypt(bytea, bytea, text) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.pgp_pub_decrypt(bytea, bytea, text) TO dashboard_user;


--
-- Name: FUNCTION pgp_pub_decrypt(bytea, bytea, text, text); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.pgp_pub_decrypt(bytea, bytea, text, text) FROM postgres;
GRANT ALL ON FUNCTION extensions.pgp_pub_decrypt(bytea, bytea, text, text) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.pgp_pub_decrypt(bytea, bytea, text, text) TO dashboard_user;


--
-- Name: FUNCTION pgp_pub_decrypt_bytea(bytea, bytea); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.pgp_pub_decrypt_bytea(bytea, bytea) FROM postgres;
GRANT ALL ON FUNCTION extensions.pgp_pub_decrypt_bytea(bytea, bytea) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.pgp_pub_decrypt_bytea(bytea, bytea) TO dashboard_user;


--
-- Name: FUNCTION pgp_pub_decrypt_bytea(bytea, bytea, text); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.pgp_pub_decrypt_bytea(bytea, bytea, text) FROM postgres;
GRANT ALL ON FUNCTION extensions.pgp_pub_decrypt_bytea(bytea, bytea, text) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.pgp_pub_decrypt_bytea(bytea, bytea, text) TO dashboard_user;


--
-- Name: FUNCTION pgp_pub_decrypt_bytea(bytea, bytea, text, text); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.pgp_pub_decrypt_bytea(bytea, bytea, text, text) FROM postgres;
GRANT ALL ON FUNCTION extensions.pgp_pub_decrypt_bytea(bytea, bytea, text, text) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.pgp_pub_decrypt_bytea(bytea, bytea, text, text) TO dashboard_user;


--
-- Name: FUNCTION pgp_pub_encrypt(text, bytea); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.pgp_pub_encrypt(text, bytea) FROM postgres;
GRANT ALL ON FUNCTION extensions.pgp_pub_encrypt(text, bytea) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.pgp_pub_encrypt(text, bytea) TO dashboard_user;


--
-- Name: FUNCTION pgp_pub_encrypt(text, bytea, text); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.pgp_pub_encrypt(text, bytea, text) FROM postgres;
GRANT ALL ON FUNCTION extensions.pgp_pub_encrypt(text, bytea, text) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.pgp_pub_encrypt(text, bytea, text) TO dashboard_user;


--
-- Name: FUNCTION pgp_pub_encrypt_bytea(bytea, bytea); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.pgp_pub_encrypt_bytea(bytea, bytea) FROM postgres;
GRANT ALL ON FUNCTION extensions.pgp_pub_encrypt_bytea(bytea, bytea) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.pgp_pub_encrypt_bytea(bytea, bytea) TO dashboard_user;


--
-- Name: FUNCTION pgp_pub_encrypt_bytea(bytea, bytea, text); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.pgp_pub_encrypt_bytea(bytea, bytea, text) FROM postgres;
GRANT ALL ON FUNCTION extensions.pgp_pub_encrypt_bytea(bytea, bytea, text) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.pgp_pub_encrypt_bytea(bytea, bytea, text) TO dashboard_user;


--
-- Name: FUNCTION pgp_sym_decrypt(bytea, text); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.pgp_sym_decrypt(bytea, text) FROM postgres;
GRANT ALL ON FUNCTION extensions.pgp_sym_decrypt(bytea, text) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.pgp_sym_decrypt(bytea, text) TO dashboard_user;


--
-- Name: FUNCTION pgp_sym_decrypt(bytea, text, text); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.pgp_sym_decrypt(bytea, text, text) FROM postgres;
GRANT ALL ON FUNCTION extensions.pgp_sym_decrypt(bytea, text, text) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.pgp_sym_decrypt(bytea, text, text) TO dashboard_user;


--
-- Name: FUNCTION pgp_sym_decrypt_bytea(bytea, text); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.pgp_sym_decrypt_bytea(bytea, text) FROM postgres;
GRANT ALL ON FUNCTION extensions.pgp_sym_decrypt_bytea(bytea, text) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.pgp_sym_decrypt_bytea(bytea, text) TO dashboard_user;


--
-- Name: FUNCTION pgp_sym_decrypt_bytea(bytea, text, text); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.pgp_sym_decrypt_bytea(bytea, text, text) FROM postgres;
GRANT ALL ON FUNCTION extensions.pgp_sym_decrypt_bytea(bytea, text, text) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.pgp_sym_decrypt_bytea(bytea, text, text) TO dashboard_user;


--
-- Name: FUNCTION pgp_sym_encrypt(text, text); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.pgp_sym_encrypt(text, text) FROM postgres;
GRANT ALL ON FUNCTION extensions.pgp_sym_encrypt(text, text) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.pgp_sym_encrypt(text, text) TO dashboard_user;


--
-- Name: FUNCTION pgp_sym_encrypt(text, text, text); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.pgp_sym_encrypt(text, text, text) FROM postgres;
GRANT ALL ON FUNCTION extensions.pgp_sym_encrypt(text, text, text) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.pgp_sym_encrypt(text, text, text) TO dashboard_user;


--
-- Name: FUNCTION pgp_sym_encrypt_bytea(bytea, text); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.pgp_sym_encrypt_bytea(bytea, text) FROM postgres;
GRANT ALL ON FUNCTION extensions.pgp_sym_encrypt_bytea(bytea, text) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.pgp_sym_encrypt_bytea(bytea, text) TO dashboard_user;


--
-- Name: FUNCTION pgp_sym_encrypt_bytea(bytea, text, text); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.pgp_sym_encrypt_bytea(bytea, text, text) FROM postgres;
GRANT ALL ON FUNCTION extensions.pgp_sym_encrypt_bytea(bytea, text, text) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.pgp_sym_encrypt_bytea(bytea, text, text) TO dashboard_user;


--
-- Name: FUNCTION pgrst_ddl_watch(); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.pgrst_ddl_watch() TO postgres WITH GRANT OPTION;


--
-- Name: FUNCTION pgrst_drop_watch(); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.pgrst_drop_watch() TO postgres WITH GRANT OPTION;


--
-- Name: FUNCTION set_graphql_placeholder(); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.set_graphql_placeholder() TO postgres WITH GRANT OPTION;


--
-- Name: FUNCTION uuid_generate_v1(); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.uuid_generate_v1() FROM postgres;
GRANT ALL ON FUNCTION extensions.uuid_generate_v1() TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.uuid_generate_v1() TO dashboard_user;


--
-- Name: FUNCTION uuid_generate_v1mc(); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.uuid_generate_v1mc() FROM postgres;
GRANT ALL ON FUNCTION extensions.uuid_generate_v1mc() TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.uuid_generate_v1mc() TO dashboard_user;


--
-- Name: FUNCTION uuid_generate_v3(namespace uuid, name text); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.uuid_generate_v3(namespace uuid, name text) FROM postgres;
GRANT ALL ON FUNCTION extensions.uuid_generate_v3(namespace uuid, name text) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.uuid_generate_v3(namespace uuid, name text) TO dashboard_user;


--
-- Name: FUNCTION uuid_generate_v4(); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.uuid_generate_v4() FROM postgres;
GRANT ALL ON FUNCTION extensions.uuid_generate_v4() TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.uuid_generate_v4() TO dashboard_user;


--
-- Name: FUNCTION uuid_generate_v5(namespace uuid, name text); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.uuid_generate_v5(namespace uuid, name text) FROM postgres;
GRANT ALL ON FUNCTION extensions.uuid_generate_v5(namespace uuid, name text) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.uuid_generate_v5(namespace uuid, name text) TO dashboard_user;


--
-- Name: FUNCTION uuid_nil(); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.uuid_nil() FROM postgres;
GRANT ALL ON FUNCTION extensions.uuid_nil() TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.uuid_nil() TO dashboard_user;


--
-- Name: FUNCTION uuid_ns_dns(); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.uuid_ns_dns() FROM postgres;
GRANT ALL ON FUNCTION extensions.uuid_ns_dns() TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.uuid_ns_dns() TO dashboard_user;


--
-- Name: FUNCTION uuid_ns_oid(); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.uuid_ns_oid() FROM postgres;
GRANT ALL ON FUNCTION extensions.uuid_ns_oid() TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.uuid_ns_oid() TO dashboard_user;


--
-- Name: FUNCTION uuid_ns_url(); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.uuid_ns_url() FROM postgres;
GRANT ALL ON FUNCTION extensions.uuid_ns_url() TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.uuid_ns_url() TO dashboard_user;


--
-- Name: FUNCTION uuid_ns_x500(); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.uuid_ns_x500() FROM postgres;
GRANT ALL ON FUNCTION extensions.uuid_ns_x500() TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.uuid_ns_x500() TO dashboard_user;


--
-- Name: FUNCTION graphql("operationName" text, query text, variables jsonb, extensions jsonb); Type: ACL; Schema: graphql_public; Owner: supabase_admin
--

GRANT ALL ON FUNCTION graphql_public.graphql("operationName" text, query text, variables jsonb, extensions jsonb) TO postgres;
GRANT ALL ON FUNCTION graphql_public.graphql("operationName" text, query text, variables jsonb, extensions jsonb) TO anon;
GRANT ALL ON FUNCTION graphql_public.graphql("operationName" text, query text, variables jsonb, extensions jsonb) TO authenticated;
GRANT ALL ON FUNCTION graphql_public.graphql("operationName" text, query text, variables jsonb, extensions jsonb) TO service_role;


--
-- Name: FUNCTION pg_reload_conf(); Type: ACL; Schema: pg_catalog; Owner: supabase_admin
--

GRANT ALL ON FUNCTION pg_catalog.pg_reload_conf() TO postgres WITH GRANT OPTION;


--
-- Name: FUNCTION get_auth(p_usename text); Type: ACL; Schema: pgbouncer; Owner: supabase_admin
--

REVOKE ALL ON FUNCTION pgbouncer.get_auth(p_usename text) FROM PUBLIC;
GRANT ALL ON FUNCTION pgbouncer.get_auth(p_usename text) TO pgbouncer;


--
-- Name: FUNCTION gin_extract_query_trgm(text, internal, smallint, internal, internal, internal, internal); Type: ACL; Schema: public; Owner: supabase_admin
--

GRANT ALL ON FUNCTION public.gin_extract_query_trgm(text, internal, smallint, internal, internal, internal, internal) TO postgres;
GRANT ALL ON FUNCTION public.gin_extract_query_trgm(text, internal, smallint, internal, internal, internal, internal) TO anon;
GRANT ALL ON FUNCTION public.gin_extract_query_trgm(text, internal, smallint, internal, internal, internal, internal) TO authenticated;
GRANT ALL ON FUNCTION public.gin_extract_query_trgm(text, internal, smallint, internal, internal, internal, internal) TO service_role;


--
-- Name: FUNCTION gin_extract_value_trgm(text, internal); Type: ACL; Schema: public; Owner: supabase_admin
--

GRANT ALL ON FUNCTION public.gin_extract_value_trgm(text, internal) TO postgres;
GRANT ALL ON FUNCTION public.gin_extract_value_trgm(text, internal) TO anon;
GRANT ALL ON FUNCTION public.gin_extract_value_trgm(text, internal) TO authenticated;
GRANT ALL ON FUNCTION public.gin_extract_value_trgm(text, internal) TO service_role;


--
-- Name: FUNCTION gin_trgm_consistent(internal, smallint, text, integer, internal, internal, internal, internal); Type: ACL; Schema: public; Owner: supabase_admin
--

GRANT ALL ON FUNCTION public.gin_trgm_consistent(internal, smallint, text, integer, internal, internal, internal, internal) TO postgres;
GRANT ALL ON FUNCTION public.gin_trgm_consistent(internal, smallint, text, integer, internal, internal, internal, internal) TO anon;
GRANT ALL ON FUNCTION public.gin_trgm_consistent(internal, smallint, text, integer, internal, internal, internal, internal) TO authenticated;
GRANT ALL ON FUNCTION public.gin_trgm_consistent(internal, smallint, text, integer, internal, internal, internal, internal) TO service_role;


--
-- Name: FUNCTION gin_trgm_triconsistent(internal, smallint, text, integer, internal, internal, internal); Type: ACL; Schema: public; Owner: supabase_admin
--

GRANT ALL ON FUNCTION public.gin_trgm_triconsistent(internal, smallint, text, integer, internal, internal, internal) TO postgres;
GRANT ALL ON FUNCTION public.gin_trgm_triconsistent(internal, smallint, text, integer, internal, internal, internal) TO anon;
GRANT ALL ON FUNCTION public.gin_trgm_triconsistent(internal, smallint, text, integer, internal, internal, internal) TO authenticated;
GRANT ALL ON FUNCTION public.gin_trgm_triconsistent(internal, smallint, text, integer, internal, internal, internal) TO service_role;


--
-- Name: FUNCTION gtrgm_compress(internal); Type: ACL; Schema: public; Owner: supabase_admin
--

GRANT ALL ON FUNCTION public.gtrgm_compress(internal) TO postgres;
GRANT ALL ON FUNCTION public.gtrgm_compress(internal) TO anon;
GRANT ALL ON FUNCTION public.gtrgm_compress(internal) TO authenticated;
GRANT ALL ON FUNCTION public.gtrgm_compress(internal) TO service_role;


--
-- Name: FUNCTION gtrgm_consistent(internal, text, smallint, oid, internal); Type: ACL; Schema: public; Owner: supabase_admin
--

GRANT ALL ON FUNCTION public.gtrgm_consistent(internal, text, smallint, oid, internal) TO postgres;
GRANT ALL ON FUNCTION public.gtrgm_consistent(internal, text, smallint, oid, internal) TO anon;
GRANT ALL ON FUNCTION public.gtrgm_consistent(internal, text, smallint, oid, internal) TO authenticated;
GRANT ALL ON FUNCTION public.gtrgm_consistent(internal, text, smallint, oid, internal) TO service_role;


--
-- Name: FUNCTION gtrgm_decompress(internal); Type: ACL; Schema: public; Owner: supabase_admin
--

GRANT ALL ON FUNCTION public.gtrgm_decompress(internal) TO postgres;
GRANT ALL ON FUNCTION public.gtrgm_decompress(internal) TO anon;
GRANT ALL ON FUNCTION public.gtrgm_decompress(internal) TO authenticated;
GRANT ALL ON FUNCTION public.gtrgm_decompress(internal) TO service_role;


--
-- Name: FUNCTION gtrgm_distance(internal, text, smallint, oid, internal); Type: ACL; Schema: public; Owner: supabase_admin
--

GRANT ALL ON FUNCTION public.gtrgm_distance(internal, text, smallint, oid, internal) TO postgres;
GRANT ALL ON FUNCTION public.gtrgm_distance(internal, text, smallint, oid, internal) TO anon;
GRANT ALL ON FUNCTION public.gtrgm_distance(internal, text, smallint, oid, internal) TO authenticated;
GRANT ALL ON FUNCTION public.gtrgm_distance(internal, text, smallint, oid, internal) TO service_role;


--
-- Name: FUNCTION gtrgm_options(internal); Type: ACL; Schema: public; Owner: supabase_admin
--

GRANT ALL ON FUNCTION public.gtrgm_options(internal) TO postgres;
GRANT ALL ON FUNCTION public.gtrgm_options(internal) TO anon;
GRANT ALL ON FUNCTION public.gtrgm_options(internal) TO authenticated;
GRANT ALL ON FUNCTION public.gtrgm_options(internal) TO service_role;


--
-- Name: FUNCTION gtrgm_penalty(internal, internal, internal); Type: ACL; Schema: public; Owner: supabase_admin
--

GRANT ALL ON FUNCTION public.gtrgm_penalty(internal, internal, internal) TO postgres;
GRANT ALL ON FUNCTION public.gtrgm_penalty(internal, internal, internal) TO anon;
GRANT ALL ON FUNCTION public.gtrgm_penalty(internal, internal, internal) TO authenticated;
GRANT ALL ON FUNCTION public.gtrgm_penalty(internal, internal, internal) TO service_role;


--
-- Name: FUNCTION gtrgm_picksplit(internal, internal); Type: ACL; Schema: public; Owner: supabase_admin
--

GRANT ALL ON FUNCTION public.gtrgm_picksplit(internal, internal) TO postgres;
GRANT ALL ON FUNCTION public.gtrgm_picksplit(internal, internal) TO anon;
GRANT ALL ON FUNCTION public.gtrgm_picksplit(internal, internal) TO authenticated;
GRANT ALL ON FUNCTION public.gtrgm_picksplit(internal, internal) TO service_role;


--
-- Name: FUNCTION gtrgm_same(public.gtrgm, public.gtrgm, internal); Type: ACL; Schema: public; Owner: supabase_admin
--

GRANT ALL ON FUNCTION public.gtrgm_same(public.gtrgm, public.gtrgm, internal) TO postgres;
GRANT ALL ON FUNCTION public.gtrgm_same(public.gtrgm, public.gtrgm, internal) TO anon;
GRANT ALL ON FUNCTION public.gtrgm_same(public.gtrgm, public.gtrgm, internal) TO authenticated;
GRANT ALL ON FUNCTION public.gtrgm_same(public.gtrgm, public.gtrgm, internal) TO service_role;


--
-- Name: FUNCTION gtrgm_union(internal, internal); Type: ACL; Schema: public; Owner: supabase_admin
--

GRANT ALL ON FUNCTION public.gtrgm_union(internal, internal) TO postgres;
GRANT ALL ON FUNCTION public.gtrgm_union(internal, internal) TO anon;
GRANT ALL ON FUNCTION public.gtrgm_union(internal, internal) TO authenticated;
GRANT ALL ON FUNCTION public.gtrgm_union(internal, internal) TO service_role;


--
-- Name: FUNCTION set_limit(real); Type: ACL; Schema: public; Owner: supabase_admin
--

GRANT ALL ON FUNCTION public.set_limit(real) TO postgres;
GRANT ALL ON FUNCTION public.set_limit(real) TO anon;
GRANT ALL ON FUNCTION public.set_limit(real) TO authenticated;
GRANT ALL ON FUNCTION public.set_limit(real) TO service_role;


--
-- Name: FUNCTION show_limit(); Type: ACL; Schema: public; Owner: supabase_admin
--

GRANT ALL ON FUNCTION public.show_limit() TO postgres;
GRANT ALL ON FUNCTION public.show_limit() TO anon;
GRANT ALL ON FUNCTION public.show_limit() TO authenticated;
GRANT ALL ON FUNCTION public.show_limit() TO service_role;


--
-- Name: FUNCTION show_trgm(text); Type: ACL; Schema: public; Owner: supabase_admin
--

GRANT ALL ON FUNCTION public.show_trgm(text) TO postgres;
GRANT ALL ON FUNCTION public.show_trgm(text) TO anon;
GRANT ALL ON FUNCTION public.show_trgm(text) TO authenticated;
GRANT ALL ON FUNCTION public.show_trgm(text) TO service_role;


--
-- Name: FUNCTION similarity(text, text); Type: ACL; Schema: public; Owner: supabase_admin
--

GRANT ALL ON FUNCTION public.similarity(text, text) TO postgres;
GRANT ALL ON FUNCTION public.similarity(text, text) TO anon;
GRANT ALL ON FUNCTION public.similarity(text, text) TO authenticated;
GRANT ALL ON FUNCTION public.similarity(text, text) TO service_role;


--
-- Name: FUNCTION similarity_dist(text, text); Type: ACL; Schema: public; Owner: supabase_admin
--

GRANT ALL ON FUNCTION public.similarity_dist(text, text) TO postgres;
GRANT ALL ON FUNCTION public.similarity_dist(text, text) TO anon;
GRANT ALL ON FUNCTION public.similarity_dist(text, text) TO authenticated;
GRANT ALL ON FUNCTION public.similarity_dist(text, text) TO service_role;


--
-- Name: FUNCTION similarity_op(text, text); Type: ACL; Schema: public; Owner: supabase_admin
--

GRANT ALL ON FUNCTION public.similarity_op(text, text) TO postgres;
GRANT ALL ON FUNCTION public.similarity_op(text, text) TO anon;
GRANT ALL ON FUNCTION public.similarity_op(text, text) TO authenticated;
GRANT ALL ON FUNCTION public.similarity_op(text, text) TO service_role;


--
-- Name: FUNCTION strict_word_similarity(text, text); Type: ACL; Schema: public; Owner: supabase_admin
--

GRANT ALL ON FUNCTION public.strict_word_similarity(text, text) TO postgres;
GRANT ALL ON FUNCTION public.strict_word_similarity(text, text) TO anon;
GRANT ALL ON FUNCTION public.strict_word_similarity(text, text) TO authenticated;
GRANT ALL ON FUNCTION public.strict_word_similarity(text, text) TO service_role;


--
-- Name: FUNCTION strict_word_similarity_commutator_op(text, text); Type: ACL; Schema: public; Owner: supabase_admin
--

GRANT ALL ON FUNCTION public.strict_word_similarity_commutator_op(text, text) TO postgres;
GRANT ALL ON FUNCTION public.strict_word_similarity_commutator_op(text, text) TO anon;
GRANT ALL ON FUNCTION public.strict_word_similarity_commutator_op(text, text) TO authenticated;
GRANT ALL ON FUNCTION public.strict_word_similarity_commutator_op(text, text) TO service_role;


--
-- Name: FUNCTION strict_word_similarity_dist_commutator_op(text, text); Type: ACL; Schema: public; Owner: supabase_admin
--

GRANT ALL ON FUNCTION public.strict_word_similarity_dist_commutator_op(text, text) TO postgres;
GRANT ALL ON FUNCTION public.strict_word_similarity_dist_commutator_op(text, text) TO anon;
GRANT ALL ON FUNCTION public.strict_word_similarity_dist_commutator_op(text, text) TO authenticated;
GRANT ALL ON FUNCTION public.strict_word_similarity_dist_commutator_op(text, text) TO service_role;


--
-- Name: FUNCTION strict_word_similarity_dist_op(text, text); Type: ACL; Schema: public; Owner: supabase_admin
--

GRANT ALL ON FUNCTION public.strict_word_similarity_dist_op(text, text) TO postgres;
GRANT ALL ON FUNCTION public.strict_word_similarity_dist_op(text, text) TO anon;
GRANT ALL ON FUNCTION public.strict_word_similarity_dist_op(text, text) TO authenticated;
GRANT ALL ON FUNCTION public.strict_word_similarity_dist_op(text, text) TO service_role;


--
-- Name: FUNCTION strict_word_similarity_op(text, text); Type: ACL; Schema: public; Owner: supabase_admin
--

GRANT ALL ON FUNCTION public.strict_word_similarity_op(text, text) TO postgres;
GRANT ALL ON FUNCTION public.strict_word_similarity_op(text, text) TO anon;
GRANT ALL ON FUNCTION public.strict_word_similarity_op(text, text) TO authenticated;
GRANT ALL ON FUNCTION public.strict_word_similarity_op(text, text) TO service_role;


--
-- Name: FUNCTION word_similarity(text, text); Type: ACL; Schema: public; Owner: supabase_admin
--

GRANT ALL ON FUNCTION public.word_similarity(text, text) TO postgres;
GRANT ALL ON FUNCTION public.word_similarity(text, text) TO anon;
GRANT ALL ON FUNCTION public.word_similarity(text, text) TO authenticated;
GRANT ALL ON FUNCTION public.word_similarity(text, text) TO service_role;


--
-- Name: FUNCTION word_similarity_commutator_op(text, text); Type: ACL; Schema: public; Owner: supabase_admin
--

GRANT ALL ON FUNCTION public.word_similarity_commutator_op(text, text) TO postgres;
GRANT ALL ON FUNCTION public.word_similarity_commutator_op(text, text) TO anon;
GRANT ALL ON FUNCTION public.word_similarity_commutator_op(text, text) TO authenticated;
GRANT ALL ON FUNCTION public.word_similarity_commutator_op(text, text) TO service_role;


--
-- Name: FUNCTION word_similarity_dist_commutator_op(text, text); Type: ACL; Schema: public; Owner: supabase_admin
--

GRANT ALL ON FUNCTION public.word_similarity_dist_commutator_op(text, text) TO postgres;
GRANT ALL ON FUNCTION public.word_similarity_dist_commutator_op(text, text) TO anon;
GRANT ALL ON FUNCTION public.word_similarity_dist_commutator_op(text, text) TO authenticated;
GRANT ALL ON FUNCTION public.word_similarity_dist_commutator_op(text, text) TO service_role;


--
-- Name: FUNCTION word_similarity_dist_op(text, text); Type: ACL; Schema: public; Owner: supabase_admin
--

GRANT ALL ON FUNCTION public.word_similarity_dist_op(text, text) TO postgres;
GRANT ALL ON FUNCTION public.word_similarity_dist_op(text, text) TO anon;
GRANT ALL ON FUNCTION public.word_similarity_dist_op(text, text) TO authenticated;
GRANT ALL ON FUNCTION public.word_similarity_dist_op(text, text) TO service_role;


--
-- Name: FUNCTION word_similarity_op(text, text); Type: ACL; Schema: public; Owner: supabase_admin
--

GRANT ALL ON FUNCTION public.word_similarity_op(text, text) TO postgres;
GRANT ALL ON FUNCTION public.word_similarity_op(text, text) TO anon;
GRANT ALL ON FUNCTION public.word_similarity_op(text, text) TO authenticated;
GRANT ALL ON FUNCTION public.word_similarity_op(text, text) TO service_role;


--
-- Name: FUNCTION apply_rls(wal jsonb, max_record_bytes integer); Type: ACL; Schema: realtime; Owner: supabase_realtime_admin
--

GRANT ALL ON FUNCTION realtime.apply_rls(wal jsonb, max_record_bytes integer) TO postgres;
GRANT ALL ON FUNCTION realtime.apply_rls(wal jsonb, max_record_bytes integer) TO dashboard_user;
GRANT ALL ON FUNCTION realtime.apply_rls(wal jsonb, max_record_bytes integer) TO anon;
GRANT ALL ON FUNCTION realtime.apply_rls(wal jsonb, max_record_bytes integer) TO authenticated;
GRANT ALL ON FUNCTION realtime.apply_rls(wal jsonb, max_record_bytes integer) TO service_role;


--
-- Name: FUNCTION broadcast_changes(topic_name text, event_name text, operation text, table_name text, table_schema text, new record, old record, level text); Type: ACL; Schema: realtime; Owner: supabase_realtime_admin
--

GRANT ALL ON FUNCTION realtime.broadcast_changes(topic_name text, event_name text, operation text, table_name text, table_schema text, new record, old record, level text) TO postgres;
GRANT ALL ON FUNCTION realtime.broadcast_changes(topic_name text, event_name text, operation text, table_name text, table_schema text, new record, old record, level text) TO dashboard_user;


--
-- Name: FUNCTION build_prepared_statement_sql(prepared_statement_name text, entity regclass, columns realtime.wal_column[]); Type: ACL; Schema: realtime; Owner: supabase_realtime_admin
--

GRANT ALL ON FUNCTION realtime.build_prepared_statement_sql(prepared_statement_name text, entity regclass, columns realtime.wal_column[]) TO postgres;
GRANT ALL ON FUNCTION realtime.build_prepared_statement_sql(prepared_statement_name text, entity regclass, columns realtime.wal_column[]) TO dashboard_user;
GRANT ALL ON FUNCTION realtime.build_prepared_statement_sql(prepared_statement_name text, entity regclass, columns realtime.wal_column[]) TO anon;
GRANT ALL ON FUNCTION realtime.build_prepared_statement_sql(prepared_statement_name text, entity regclass, columns realtime.wal_column[]) TO authenticated;
GRANT ALL ON FUNCTION realtime.build_prepared_statement_sql(prepared_statement_name text, entity regclass, columns realtime.wal_column[]) TO service_role;


--
-- Name: FUNCTION "cast"(val text, type_ regtype); Type: ACL; Schema: realtime; Owner: supabase_realtime_admin
--

GRANT ALL ON FUNCTION realtime."cast"(val text, type_ regtype) TO postgres;
GRANT ALL ON FUNCTION realtime."cast"(val text, type_ regtype) TO dashboard_user;
GRANT ALL ON FUNCTION realtime."cast"(val text, type_ regtype) TO anon;
GRANT ALL ON FUNCTION realtime."cast"(val text, type_ regtype) TO authenticated;
GRANT ALL ON FUNCTION realtime."cast"(val text, type_ regtype) TO service_role;


--
-- Name: FUNCTION check_equality_op(op realtime.equality_op, type_ regtype, val_1 text, val_2 text); Type: ACL; Schema: realtime; Owner: supabase_realtime_admin
--

GRANT ALL ON FUNCTION realtime.check_equality_op(op realtime.equality_op, type_ regtype, val_1 text, val_2 text) TO postgres;
GRANT ALL ON FUNCTION realtime.check_equality_op(op realtime.equality_op, type_ regtype, val_1 text, val_2 text) TO dashboard_user;
GRANT ALL ON FUNCTION realtime.check_equality_op(op realtime.equality_op, type_ regtype, val_1 text, val_2 text) TO anon;
GRANT ALL ON FUNCTION realtime.check_equality_op(op realtime.equality_op, type_ regtype, val_1 text, val_2 text) TO authenticated;
GRANT ALL ON FUNCTION realtime.check_equality_op(op realtime.equality_op, type_ regtype, val_1 text, val_2 text) TO service_role;


--
-- Name: FUNCTION check_equality_op(op realtime.equality_op, type_ regtype, val_1 text, val_2 text, negate boolean); Type: ACL; Schema: realtime; Owner: supabase_realtime_admin
--

GRANT ALL ON FUNCTION realtime.check_equality_op(op realtime.equality_op, type_ regtype, val_1 text, val_2 text, negate boolean) TO postgres;
GRANT ALL ON FUNCTION realtime.check_equality_op(op realtime.equality_op, type_ regtype, val_1 text, val_2 text, negate boolean) TO dashboard_user;
GRANT ALL ON FUNCTION realtime.check_equality_op(op realtime.equality_op, type_ regtype, val_1 text, val_2 text, negate boolean) TO anon;
GRANT ALL ON FUNCTION realtime.check_equality_op(op realtime.equality_op, type_ regtype, val_1 text, val_2 text, negate boolean) TO authenticated;
GRANT ALL ON FUNCTION realtime.check_equality_op(op realtime.equality_op, type_ regtype, val_1 text, val_2 text, negate boolean) TO service_role;


--
-- Name: FUNCTION is_visible_through_filters(columns realtime.wal_column[], filters realtime.user_defined_filter[]); Type: ACL; Schema: realtime; Owner: supabase_realtime_admin
--

GRANT ALL ON FUNCTION realtime.is_visible_through_filters(columns realtime.wal_column[], filters realtime.user_defined_filter[]) TO postgres;
GRANT ALL ON FUNCTION realtime.is_visible_through_filters(columns realtime.wal_column[], filters realtime.user_defined_filter[]) TO dashboard_user;
GRANT ALL ON FUNCTION realtime.is_visible_through_filters(columns realtime.wal_column[], filters realtime.user_defined_filter[]) TO anon;
GRANT ALL ON FUNCTION realtime.is_visible_through_filters(columns realtime.wal_column[], filters realtime.user_defined_filter[]) TO authenticated;
GRANT ALL ON FUNCTION realtime.is_visible_through_filters(columns realtime.wal_column[], filters realtime.user_defined_filter[]) TO service_role;


--
-- Name: FUNCTION list_changes(publication name, slot_name name, max_changes integer, max_record_bytes integer); Type: ACL; Schema: realtime; Owner: supabase_realtime_admin
--

GRANT ALL ON FUNCTION realtime.list_changes(publication name, slot_name name, max_changes integer, max_record_bytes integer) TO postgres;
GRANT ALL ON FUNCTION realtime.list_changes(publication name, slot_name name, max_changes integer, max_record_bytes integer) TO dashboard_user;


--
-- Name: FUNCTION quote_wal2json(entity regclass); Type: ACL; Schema: realtime; Owner: supabase_realtime_admin
--

GRANT ALL ON FUNCTION realtime.quote_wal2json(entity regclass) TO postgres;
GRANT ALL ON FUNCTION realtime.quote_wal2json(entity regclass) TO dashboard_user;
GRANT ALL ON FUNCTION realtime.quote_wal2json(entity regclass) TO anon;
GRANT ALL ON FUNCTION realtime.quote_wal2json(entity regclass) TO authenticated;
GRANT ALL ON FUNCTION realtime.quote_wal2json(entity regclass) TO service_role;


--
-- Name: FUNCTION send(payload jsonb, event text, topic text, private boolean); Type: ACL; Schema: realtime; Owner: supabase_realtime_admin
--

GRANT ALL ON FUNCTION realtime.send(payload jsonb, event text, topic text, private boolean) TO postgres;
GRANT ALL ON FUNCTION realtime.send(payload jsonb, event text, topic text, private boolean) TO dashboard_user;


--
-- Name: FUNCTION send_binary(payload bytea, event text, topic text, private boolean); Type: ACL; Schema: realtime; Owner: supabase_realtime_admin
--

GRANT ALL ON FUNCTION realtime.send_binary(payload bytea, event text, topic text, private boolean) TO postgres;
GRANT ALL ON FUNCTION realtime.send_binary(payload bytea, event text, topic text, private boolean) TO dashboard_user;


--
-- Name: FUNCTION subscription_check_filters(); Type: ACL; Schema: realtime; Owner: supabase_realtime_admin
--

GRANT ALL ON FUNCTION realtime.subscription_check_filters() TO postgres;
GRANT ALL ON FUNCTION realtime.subscription_check_filters() TO dashboard_user;
GRANT ALL ON FUNCTION realtime.subscription_check_filters() TO anon;
GRANT ALL ON FUNCTION realtime.subscription_check_filters() TO authenticated;
GRANT ALL ON FUNCTION realtime.subscription_check_filters() TO service_role;


--
-- Name: FUNCTION to_regrole(role_name text); Type: ACL; Schema: realtime; Owner: supabase_realtime_admin
--

GRANT ALL ON FUNCTION realtime.to_regrole(role_name text) TO postgres;
GRANT ALL ON FUNCTION realtime.to_regrole(role_name text) TO dashboard_user;
GRANT ALL ON FUNCTION realtime.to_regrole(role_name text) TO anon;
GRANT ALL ON FUNCTION realtime.to_regrole(role_name text) TO authenticated;
GRANT ALL ON FUNCTION realtime.to_regrole(role_name text) TO service_role;


--
-- Name: FUNCTION topic(); Type: ACL; Schema: realtime; Owner: supabase_realtime_admin
--

GRANT ALL ON FUNCTION realtime.topic() TO postgres;
GRANT ALL ON FUNCTION realtime.topic() TO dashboard_user;


--
-- Name: FUNCTION wal2json_escape_identifier(name text); Type: ACL; Schema: realtime; Owner: supabase_realtime_admin
--

GRANT ALL ON FUNCTION realtime.wal2json_escape_identifier(name text) TO postgres;
GRANT ALL ON FUNCTION realtime.wal2json_escape_identifier(name text) TO dashboard_user;


--
-- Name: FUNCTION _crypto_aead_det_decrypt(message bytea, additional bytea, key_id bigint, context bytea, nonce bytea); Type: ACL; Schema: vault; Owner: supabase_admin
--

GRANT ALL ON FUNCTION vault._crypto_aead_det_decrypt(message bytea, additional bytea, key_id bigint, context bytea, nonce bytea) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION vault._crypto_aead_det_decrypt(message bytea, additional bytea, key_id bigint, context bytea, nonce bytea) TO service_role;


--
-- Name: FUNCTION create_secret(new_secret text, new_name text, new_description text, new_key_id uuid); Type: ACL; Schema: vault; Owner: supabase_admin
--

GRANT ALL ON FUNCTION vault.create_secret(new_secret text, new_name text, new_description text, new_key_id uuid) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION vault.create_secret(new_secret text, new_name text, new_description text, new_key_id uuid) TO service_role;


--
-- Name: FUNCTION update_secret(secret_id uuid, new_secret text, new_name text, new_description text, new_key_id uuid); Type: ACL; Schema: vault; Owner: supabase_admin
--

GRANT ALL ON FUNCTION vault.update_secret(secret_id uuid, new_secret text, new_name text, new_description text, new_key_id uuid) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION vault.update_secret(secret_id uuid, new_secret text, new_name text, new_description text, new_key_id uuid) TO service_role;


--
-- Name: TABLE audit_log_entries; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT ALL ON TABLE auth.audit_log_entries TO dashboard_user;
GRANT INSERT,REFERENCES,DELETE,TRIGGER,TRUNCATE,MAINTAIN,UPDATE ON TABLE auth.audit_log_entries TO postgres;
GRANT SELECT ON TABLE auth.audit_log_entries TO postgres WITH GRANT OPTION;


--
-- Name: TABLE custom_oauth_providers; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT ALL ON TABLE auth.custom_oauth_providers TO postgres;
GRANT ALL ON TABLE auth.custom_oauth_providers TO dashboard_user;


--
-- Name: TABLE flow_state; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT INSERT,REFERENCES,DELETE,TRIGGER,TRUNCATE,MAINTAIN,UPDATE ON TABLE auth.flow_state TO postgres;
GRANT SELECT ON TABLE auth.flow_state TO postgres WITH GRANT OPTION;
GRANT ALL ON TABLE auth.flow_state TO dashboard_user;


--
-- Name: TABLE identities; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT INSERT,REFERENCES,DELETE,TRIGGER,TRUNCATE,MAINTAIN,UPDATE ON TABLE auth.identities TO postgres;
GRANT SELECT ON TABLE auth.identities TO postgres WITH GRANT OPTION;
GRANT ALL ON TABLE auth.identities TO dashboard_user;


--
-- Name: TABLE instances; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT ALL ON TABLE auth.instances TO dashboard_user;
GRANT INSERT,REFERENCES,DELETE,TRIGGER,TRUNCATE,MAINTAIN,UPDATE ON TABLE auth.instances TO postgres;
GRANT SELECT ON TABLE auth.instances TO postgres WITH GRANT OPTION;


--
-- Name: TABLE mfa_amr_claims; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT INSERT,REFERENCES,DELETE,TRIGGER,TRUNCATE,MAINTAIN,UPDATE ON TABLE auth.mfa_amr_claims TO postgres;
GRANT SELECT ON TABLE auth.mfa_amr_claims TO postgres WITH GRANT OPTION;
GRANT ALL ON TABLE auth.mfa_amr_claims TO dashboard_user;


--
-- Name: TABLE mfa_challenges; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT INSERT,REFERENCES,DELETE,TRIGGER,TRUNCATE,MAINTAIN,UPDATE ON TABLE auth.mfa_challenges TO postgres;
GRANT SELECT ON TABLE auth.mfa_challenges TO postgres WITH GRANT OPTION;
GRANT ALL ON TABLE auth.mfa_challenges TO dashboard_user;


--
-- Name: TABLE mfa_factors; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT INSERT,REFERENCES,DELETE,TRIGGER,TRUNCATE,MAINTAIN,UPDATE ON TABLE auth.mfa_factors TO postgres;
GRANT SELECT ON TABLE auth.mfa_factors TO postgres WITH GRANT OPTION;
GRANT ALL ON TABLE auth.mfa_factors TO dashboard_user;


--
-- Name: TABLE oauth_authorizations; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT ALL ON TABLE auth.oauth_authorizations TO postgres;
GRANT ALL ON TABLE auth.oauth_authorizations TO dashboard_user;


--
-- Name: TABLE oauth_client_states; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT ALL ON TABLE auth.oauth_client_states TO postgres;
GRANT ALL ON TABLE auth.oauth_client_states TO dashboard_user;


--
-- Name: TABLE oauth_clients; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT ALL ON TABLE auth.oauth_clients TO postgres;
GRANT ALL ON TABLE auth.oauth_clients TO dashboard_user;


--
-- Name: TABLE oauth_consents; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT ALL ON TABLE auth.oauth_consents TO postgres;
GRANT ALL ON TABLE auth.oauth_consents TO dashboard_user;


--
-- Name: TABLE one_time_tokens; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT INSERT,REFERENCES,DELETE,TRIGGER,TRUNCATE,MAINTAIN,UPDATE ON TABLE auth.one_time_tokens TO postgres;
GRANT SELECT ON TABLE auth.one_time_tokens TO postgres WITH GRANT OPTION;
GRANT ALL ON TABLE auth.one_time_tokens TO dashboard_user;


--
-- Name: TABLE refresh_tokens; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT ALL ON TABLE auth.refresh_tokens TO dashboard_user;
GRANT INSERT,REFERENCES,DELETE,TRIGGER,TRUNCATE,MAINTAIN,UPDATE ON TABLE auth.refresh_tokens TO postgres;
GRANT SELECT ON TABLE auth.refresh_tokens TO postgres WITH GRANT OPTION;


--
-- Name: SEQUENCE refresh_tokens_id_seq; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT ALL ON SEQUENCE auth.refresh_tokens_id_seq TO dashboard_user;
GRANT ALL ON SEQUENCE auth.refresh_tokens_id_seq TO postgres;


--
-- Name: TABLE saml_providers; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT INSERT,REFERENCES,DELETE,TRIGGER,TRUNCATE,MAINTAIN,UPDATE ON TABLE auth.saml_providers TO postgres;
GRANT SELECT ON TABLE auth.saml_providers TO postgres WITH GRANT OPTION;
GRANT ALL ON TABLE auth.saml_providers TO dashboard_user;


--
-- Name: TABLE saml_relay_states; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT INSERT,REFERENCES,DELETE,TRIGGER,TRUNCATE,MAINTAIN,UPDATE ON TABLE auth.saml_relay_states TO postgres;
GRANT SELECT ON TABLE auth.saml_relay_states TO postgres WITH GRANT OPTION;
GRANT ALL ON TABLE auth.saml_relay_states TO dashboard_user;


--
-- Name: TABLE schema_migrations; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT SELECT ON TABLE auth.schema_migrations TO postgres WITH GRANT OPTION;


--
-- Name: TABLE sessions; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT INSERT,REFERENCES,DELETE,TRIGGER,TRUNCATE,MAINTAIN,UPDATE ON TABLE auth.sessions TO postgres;
GRANT SELECT ON TABLE auth.sessions TO postgres WITH GRANT OPTION;
GRANT ALL ON TABLE auth.sessions TO dashboard_user;


--
-- Name: TABLE sso_domains; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT INSERT,REFERENCES,DELETE,TRIGGER,TRUNCATE,MAINTAIN,UPDATE ON TABLE auth.sso_domains TO postgres;
GRANT SELECT ON TABLE auth.sso_domains TO postgres WITH GRANT OPTION;
GRANT ALL ON TABLE auth.sso_domains TO dashboard_user;


--
-- Name: TABLE sso_providers; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT INSERT,REFERENCES,DELETE,TRIGGER,TRUNCATE,MAINTAIN,UPDATE ON TABLE auth.sso_providers TO postgres;
GRANT SELECT ON TABLE auth.sso_providers TO postgres WITH GRANT OPTION;
GRANT ALL ON TABLE auth.sso_providers TO dashboard_user;


--
-- Name: TABLE users; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT ALL ON TABLE auth.users TO dashboard_user;
GRANT INSERT,REFERENCES,DELETE,TRIGGER,TRUNCATE,MAINTAIN,UPDATE ON TABLE auth.users TO postgres;
GRANT SELECT ON TABLE auth.users TO postgres WITH GRANT OPTION;


--
-- Name: TABLE webauthn_challenges; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT ALL ON TABLE auth.webauthn_challenges TO postgres;
GRANT ALL ON TABLE auth.webauthn_challenges TO dashboard_user;


--
-- Name: TABLE webauthn_credentials; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT ALL ON TABLE auth.webauthn_credentials TO postgres;
GRANT ALL ON TABLE auth.webauthn_credentials TO dashboard_user;


--
-- Name: TABLE pg_stat_statements; Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON TABLE extensions.pg_stat_statements FROM postgres;
GRANT ALL ON TABLE extensions.pg_stat_statements TO postgres WITH GRANT OPTION;
GRANT ALL ON TABLE extensions.pg_stat_statements TO dashboard_user;


--
-- Name: TABLE pg_stat_statements_info; Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON TABLE extensions.pg_stat_statements_info FROM postgres;
GRANT ALL ON TABLE extensions.pg_stat_statements_info TO postgres WITH GRANT OPTION;
GRANT ALL ON TABLE extensions.pg_stat_statements_info TO dashboard_user;


--
-- Name: TABLE alembic_version; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.alembic_version TO anon;
GRANT ALL ON TABLE public.alembic_version TO authenticated;
GRANT ALL ON TABLE public.alembic_version TO service_role;


--
-- Name: TABLE api_keys; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.api_keys TO anon;
GRANT ALL ON TABLE public.api_keys TO authenticated;
GRANT ALL ON TABLE public.api_keys TO service_role;


--
-- Name: SEQUENCE api_keys_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON SEQUENCE public.api_keys_id_seq TO anon;
GRANT ALL ON SEQUENCE public.api_keys_id_seq TO authenticated;
GRANT ALL ON SEQUENCE public.api_keys_id_seq TO service_role;


--
-- Name: TABLE app_ads; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.app_ads TO anon;
GRANT ALL ON TABLE public.app_ads TO authenticated;
GRANT ALL ON TABLE public.app_ads TO service_role;


--
-- Name: SEQUENCE app_ads_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON SEQUENCE public.app_ads_id_seq TO anon;
GRANT ALL ON SEQUENCE public.app_ads_id_seq TO authenticated;
GRANT ALL ON SEQUENCE public.app_ads_id_seq TO service_role;


--
-- Name: TABLE auth_challenges; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.auth_challenges TO anon;
GRANT ALL ON TABLE public.auth_challenges TO authenticated;
GRANT ALL ON TABLE public.auth_challenges TO service_role;


--
-- Name: SEQUENCE auth_challenges_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON SEQUENCE public.auth_challenges_id_seq TO anon;
GRANT ALL ON SEQUENCE public.auth_challenges_id_seq TO authenticated;
GRANT ALL ON SEQUENCE public.auth_challenges_id_seq TO service_role;


--
-- Name: TABLE catalogo_items; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.catalogo_items TO anon;
GRANT ALL ON TABLE public.catalogo_items TO authenticated;
GRANT ALL ON TABLE public.catalogo_items TO service_role;


--
-- Name: TABLE clientes_emisor; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.clientes_emisor TO anon;
GRANT ALL ON TABLE public.clientes_emisor TO authenticated;
GRANT ALL ON TABLE public.clientes_emisor TO service_role;


--
-- Name: TABLE credit_transactions; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.credit_transactions TO anon;
GRANT ALL ON TABLE public.credit_transactions TO authenticated;
GRANT ALL ON TABLE public.credit_transactions TO service_role;


--
-- Name: TABLE declaraciones_sri; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.declaraciones_sri TO anon;
GRANT ALL ON TABLE public.declaraciones_sri TO authenticated;
GRANT ALL ON TABLE public.declaraciones_sri TO service_role;


--
-- Name: SEQUENCE declaraciones_sri_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON SEQUENCE public.declaraciones_sri_id_seq TO anon;
GRANT ALL ON SEQUENCE public.declaraciones_sri_id_seq TO authenticated;
GRANT ALL ON SEQUENCE public.declaraciones_sri_id_seq TO service_role;


--
-- Name: TABLE email_rate_limits; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.email_rate_limits TO anon;
GRANT ALL ON TABLE public.email_rate_limits TO authenticated;
GRANT ALL ON TABLE public.email_rate_limits TO service_role;


--
-- Name: SEQUENCE email_rate_limits_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON SEQUENCE public.email_rate_limits_id_seq TO anon;
GRANT ALL ON SEQUENCE public.email_rate_limits_id_seq TO authenticated;
GRANT ALL ON SEQUENCE public.email_rate_limits_id_seq TO service_role;


--
-- Name: TABLE emisor_usuarios; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.emisor_usuarios TO anon;
GRANT ALL ON TABLE public.emisor_usuarios TO authenticated;
GRANT ALL ON TABLE public.emisor_usuarios TO service_role;


--
-- Name: SEQUENCE emisor_usuarios_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON SEQUENCE public.emisor_usuarios_id_seq TO anon;
GRANT ALL ON SEQUENCE public.emisor_usuarios_id_seq TO authenticated;
GRANT ALL ON SEQUENCE public.emisor_usuarios_id_seq TO service_role;


--
-- Name: TABLE emisores; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.emisores TO anon;
GRANT ALL ON TABLE public.emisores TO authenticated;
GRANT ALL ON TABLE public.emisores TO service_role;


--
-- Name: SEQUENCE emisores_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON SEQUENCE public.emisores_id_seq TO anon;
GRANT ALL ON SEQUENCE public.emisores_id_seq TO authenticated;
GRANT ALL ON SEQUENCE public.emisores_id_seq TO service_role;


--
-- Name: TABLE establecimientos; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.establecimientos TO anon;
GRANT ALL ON TABLE public.establecimientos TO authenticated;
GRANT ALL ON TABLE public.establecimientos TO service_role;


--
-- Name: SEQUENCE establecimientos_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON SEQUENCE public.establecimientos_id_seq TO anon;
GRANT ALL ON SEQUENCE public.establecimientos_id_seq TO authenticated;
GRANT ALL ON SEQUENCE public.establecimientos_id_seq TO service_role;


--
-- Name: TABLE fcm_tokens; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.fcm_tokens TO anon;
GRANT ALL ON TABLE public.fcm_tokens TO authenticated;
GRANT ALL ON TABLE public.fcm_tokens TO service_role;


--
-- Name: SEQUENCE fcm_tokens_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON SEQUENCE public.fcm_tokens_id_seq TO anon;
GRANT ALL ON SEQUENCE public.fcm_tokens_id_seq TO authenticated;
GRANT ALL ON SEQUENCE public.fcm_tokens_id_seq TO service_role;


--
-- Name: TABLE invoices_emitidas; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.invoices_emitidas TO anon;
GRANT ALL ON TABLE public.invoices_emitidas TO authenticated;
GRANT ALL ON TABLE public.invoices_emitidas TO service_role;


--
-- Name: TABLE invoices_recibidas; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.invoices_recibidas TO anon;
GRANT ALL ON TABLE public.invoices_recibidas TO authenticated;
GRANT ALL ON TABLE public.invoices_recibidas TO service_role;


--
-- Name: TABLE leads_ex_usuarios; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.leads_ex_usuarios TO anon;
GRANT ALL ON TABLE public.leads_ex_usuarios TO authenticated;
GRANT ALL ON TABLE public.leads_ex_usuarios TO service_role;


--
-- Name: SEQUENCE leads_ex_usuarios_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON SEQUENCE public.leads_ex_usuarios_id_seq TO anon;
GRANT ALL ON SEQUENCE public.leads_ex_usuarios_id_seq TO authenticated;
GRANT ALL ON SEQUENCE public.leads_ex_usuarios_id_seq TO service_role;


--
-- Name: TABLE notificaciones; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.notificaciones TO anon;
GRANT ALL ON TABLE public.notificaciones TO authenticated;
GRANT ALL ON TABLE public.notificaciones TO service_role;


--
-- Name: SEQUENCE notificaciones_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON SEQUENCE public.notificaciones_id_seq TO anon;
GRANT ALL ON SEQUENCE public.notificaciones_id_seq TO authenticated;
GRANT ALL ON SEQUENCE public.notificaciones_id_seq TO service_role;


--
-- Name: TABLE planes_creditos; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.planes_creditos TO anon;
GRANT ALL ON TABLE public.planes_creditos TO authenticated;
GRANT ALL ON TABLE public.planes_creditos TO service_role;


--
-- Name: SEQUENCE planes_creditos_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON SEQUENCE public.planes_creditos_id_seq TO anon;
GRANT ALL ON SEQUENCE public.planes_creditos_id_seq TO authenticated;
GRANT ALL ON SEQUENCE public.planes_creditos_id_seq TO service_role;


--
-- Name: TABLE profiles; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.profiles TO anon;
GRANT ALL ON TABLE public.profiles TO authenticated;
GRANT ALL ON TABLE public.profiles TO service_role;


--
-- Name: TABLE puntos_emision; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.puntos_emision TO anon;
GRANT ALL ON TABLE public.puntos_emision TO authenticated;
GRANT ALL ON TABLE public.puntos_emision TO service_role;


--
-- Name: SEQUENCE puntos_emision_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON SEQUENCE public.puntos_emision_id_seq TO anon;
GRANT ALL ON SEQUENCE public.puntos_emision_id_seq TO authenticated;
GRANT ALL ON SEQUENCE public.puntos_emision_id_seq TO service_role;


--
-- Name: TABLE servicios; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.servicios TO anon;
GRANT ALL ON TABLE public.servicios TO authenticated;
GRANT ALL ON TABLE public.servicios TO service_role;


--
-- Name: SEQUENCE servicios_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON SEQUENCE public.servicios_id_seq TO anon;
GRANT ALL ON SEQUENCE public.servicios_id_seq TO authenticated;
GRANT ALL ON SEQUENCE public.servicios_id_seq TO service_role;


--
-- Name: TABLE sujetos_global; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.sujetos_global TO anon;
GRANT ALL ON TABLE public.sujetos_global TO authenticated;
GRANT ALL ON TABLE public.sujetos_global TO service_role;


--
-- Name: TABLE transaction_logs; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.transaction_logs TO anon;
GRANT ALL ON TABLE public.transaction_logs TO authenticated;
GRANT ALL ON TABLE public.transaction_logs TO service_role;


--
-- Name: SEQUENCE transaction_logs_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON SEQUENCE public.transaction_logs_id_seq TO anon;
GRANT ALL ON SEQUENCE public.transaction_logs_id_seq TO authenticated;
GRANT ALL ON SEQUENCE public.transaction_logs_id_seq TO service_role;


--
-- Name: TABLE user_credits; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.user_credits TO anon;
GRANT ALL ON TABLE public.user_credits TO authenticated;
GRANT ALL ON TABLE public.user_credits TO service_role;


--
-- Name: TABLE webhooks; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.webhooks TO anon;
GRANT ALL ON TABLE public.webhooks TO authenticated;
GRANT ALL ON TABLE public.webhooks TO service_role;


--
-- Name: SEQUENCE webhooks_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON SEQUENCE public.webhooks_id_seq TO anon;
GRANT ALL ON SEQUENCE public.webhooks_id_seq TO authenticated;
GRANT ALL ON SEQUENCE public.webhooks_id_seq TO service_role;


--
-- Name: TABLE messages; Type: ACL; Schema: realtime; Owner: supabase_realtime_admin
--

GRANT ALL ON TABLE realtime.messages TO postgres;
GRANT ALL ON TABLE realtime.messages TO dashboard_user;
GRANT SELECT,INSERT,UPDATE ON TABLE realtime.messages TO anon;
GRANT SELECT,INSERT,UPDATE ON TABLE realtime.messages TO authenticated;
GRANT SELECT,INSERT,UPDATE ON TABLE realtime.messages TO service_role;


--
-- Name: TABLE subscription; Type: ACL; Schema: realtime; Owner: supabase_realtime_admin
--

GRANT ALL ON TABLE realtime.subscription TO postgres;
GRANT ALL ON TABLE realtime.subscription TO dashboard_user;
GRANT SELECT ON TABLE realtime.subscription TO anon;
GRANT SELECT ON TABLE realtime.subscription TO authenticated;
GRANT SELECT ON TABLE realtime.subscription TO service_role;


--
-- Name: SEQUENCE subscription_id_seq; Type: ACL; Schema: realtime; Owner: supabase_realtime_admin
--

GRANT ALL ON SEQUENCE realtime.subscription_id_seq TO postgres;
GRANT ALL ON SEQUENCE realtime.subscription_id_seq TO dashboard_user;
GRANT USAGE ON SEQUENCE realtime.subscription_id_seq TO anon;
GRANT USAGE ON SEQUENCE realtime.subscription_id_seq TO authenticated;
GRANT USAGE ON SEQUENCE realtime.subscription_id_seq TO service_role;


--
-- Name: TABLE buckets; Type: ACL; Schema: storage; Owner: supabase_storage_admin
--

REVOKE ALL ON TABLE storage.buckets FROM supabase_storage_admin;
GRANT ALL ON TABLE storage.buckets TO supabase_storage_admin WITH GRANT OPTION;
GRANT ALL ON TABLE storage.buckets TO service_role;
GRANT ALL ON TABLE storage.buckets TO authenticated;
GRANT ALL ON TABLE storage.buckets TO anon;
GRANT ALL ON TABLE storage.buckets TO postgres WITH GRANT OPTION;


--
-- Name: TABLE buckets_analytics; Type: ACL; Schema: storage; Owner: supabase_storage_admin
--

GRANT ALL ON TABLE storage.buckets_analytics TO service_role;
GRANT ALL ON TABLE storage.buckets_analytics TO authenticated;
GRANT ALL ON TABLE storage.buckets_analytics TO anon;


--
-- Name: TABLE buckets_vectors; Type: ACL; Schema: storage; Owner: supabase_storage_admin
--

GRANT SELECT ON TABLE storage.buckets_vectors TO service_role;
GRANT SELECT ON TABLE storage.buckets_vectors TO authenticated;
GRANT SELECT ON TABLE storage.buckets_vectors TO anon;


--
-- Name: TABLE objects; Type: ACL; Schema: storage; Owner: supabase_storage_admin
--

REVOKE ALL ON TABLE storage.objects FROM supabase_storage_admin;
GRANT ALL ON TABLE storage.objects TO supabase_storage_admin WITH GRANT OPTION;
GRANT ALL ON TABLE storage.objects TO service_role;
GRANT ALL ON TABLE storage.objects TO authenticated;
GRANT ALL ON TABLE storage.objects TO anon;
GRANT ALL ON TABLE storage.objects TO postgres WITH GRANT OPTION;


--
-- Name: TABLE s3_multipart_uploads; Type: ACL; Schema: storage; Owner: supabase_storage_admin
--

GRANT ALL ON TABLE storage.s3_multipart_uploads TO service_role;
GRANT SELECT ON TABLE storage.s3_multipart_uploads TO authenticated;
GRANT SELECT ON TABLE storage.s3_multipart_uploads TO anon;


--
-- Name: TABLE s3_multipart_uploads_parts; Type: ACL; Schema: storage; Owner: supabase_storage_admin
--

GRANT ALL ON TABLE storage.s3_multipart_uploads_parts TO service_role;
GRANT SELECT ON TABLE storage.s3_multipart_uploads_parts TO authenticated;
GRANT SELECT ON TABLE storage.s3_multipart_uploads_parts TO anon;


--
-- Name: TABLE vector_indexes; Type: ACL; Schema: storage; Owner: supabase_storage_admin
--

GRANT SELECT ON TABLE storage.vector_indexes TO service_role;
GRANT SELECT ON TABLE storage.vector_indexes TO authenticated;
GRANT SELECT ON TABLE storage.vector_indexes TO anon;


--
-- Name: TABLE secrets; Type: ACL; Schema: vault; Owner: supabase_admin
--

GRANT SELECT,REFERENCES,DELETE,TRUNCATE ON TABLE vault.secrets TO postgres WITH GRANT OPTION;
GRANT SELECT,DELETE ON TABLE vault.secrets TO service_role;


--
-- Name: TABLE decrypted_secrets; Type: ACL; Schema: vault; Owner: supabase_admin
--

GRANT SELECT,REFERENCES,DELETE,TRUNCATE ON TABLE vault.decrypted_secrets TO postgres WITH GRANT OPTION;
GRANT SELECT,DELETE ON TABLE vault.decrypted_secrets TO service_role;


--
-- Name: DEFAULT PRIVILEGES FOR SEQUENCES; Type: DEFAULT ACL; Schema: auth; Owner: supabase_auth_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_auth_admin IN SCHEMA auth GRANT ALL ON SEQUENCES TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_auth_admin IN SCHEMA auth GRANT ALL ON SEQUENCES TO dashboard_user;


--
-- Name: DEFAULT PRIVILEGES FOR FUNCTIONS; Type: DEFAULT ACL; Schema: auth; Owner: supabase_auth_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_auth_admin IN SCHEMA auth GRANT ALL ON FUNCTIONS TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_auth_admin IN SCHEMA auth GRANT ALL ON FUNCTIONS TO dashboard_user;


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: auth; Owner: supabase_auth_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_auth_admin IN SCHEMA auth GRANT ALL ON TABLES TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_auth_admin IN SCHEMA auth GRANT ALL ON TABLES TO dashboard_user;


--
-- Name: DEFAULT PRIVILEGES FOR SEQUENCES; Type: DEFAULT ACL; Schema: extensions; Owner: supabase_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA extensions GRANT ALL ON SEQUENCES TO postgres WITH GRANT OPTION;


--
-- Name: DEFAULT PRIVILEGES FOR FUNCTIONS; Type: DEFAULT ACL; Schema: extensions; Owner: supabase_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA extensions GRANT ALL ON FUNCTIONS TO postgres WITH GRANT OPTION;


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: extensions; Owner: supabase_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA extensions GRANT ALL ON TABLES TO postgres WITH GRANT OPTION;


--
-- Name: DEFAULT PRIVILEGES FOR SEQUENCES; Type: DEFAULT ACL; Schema: graphql; Owner: supabase_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql GRANT ALL ON SEQUENCES TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql GRANT ALL ON SEQUENCES TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql GRANT ALL ON SEQUENCES TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql GRANT ALL ON SEQUENCES TO service_role;


--
-- Name: DEFAULT PRIVILEGES FOR FUNCTIONS; Type: DEFAULT ACL; Schema: graphql; Owner: supabase_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql GRANT ALL ON FUNCTIONS TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql GRANT ALL ON FUNCTIONS TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql GRANT ALL ON FUNCTIONS TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql GRANT ALL ON FUNCTIONS TO service_role;


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: graphql; Owner: supabase_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql GRANT ALL ON TABLES TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql GRANT ALL ON TABLES TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql GRANT ALL ON TABLES TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql GRANT ALL ON TABLES TO service_role;


--
-- Name: DEFAULT PRIVILEGES FOR SEQUENCES; Type: DEFAULT ACL; Schema: graphql_public; Owner: supabase_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql_public GRANT ALL ON SEQUENCES TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql_public GRANT ALL ON SEQUENCES TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql_public GRANT ALL ON SEQUENCES TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql_public GRANT ALL ON SEQUENCES TO service_role;


--
-- Name: DEFAULT PRIVILEGES FOR FUNCTIONS; Type: DEFAULT ACL; Schema: graphql_public; Owner: supabase_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql_public GRANT ALL ON FUNCTIONS TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql_public GRANT ALL ON FUNCTIONS TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql_public GRANT ALL ON FUNCTIONS TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql_public GRANT ALL ON FUNCTIONS TO service_role;


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: graphql_public; Owner: supabase_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql_public GRANT ALL ON TABLES TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql_public GRANT ALL ON TABLES TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql_public GRANT ALL ON TABLES TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql_public GRANT ALL ON TABLES TO service_role;


--
-- Name: DEFAULT PRIVILEGES FOR SEQUENCES; Type: DEFAULT ACL; Schema: public; Owner: postgres
--

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON SEQUENCES TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON SEQUENCES TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON SEQUENCES TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON SEQUENCES TO service_role;


--
-- Name: DEFAULT PRIVILEGES FOR SEQUENCES; Type: DEFAULT ACL; Schema: public; Owner: supabase_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public GRANT ALL ON SEQUENCES TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public GRANT ALL ON SEQUENCES TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public GRANT ALL ON SEQUENCES TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public GRANT ALL ON SEQUENCES TO service_role;


--
-- Name: DEFAULT PRIVILEGES FOR FUNCTIONS; Type: DEFAULT ACL; Schema: public; Owner: postgres
--

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON FUNCTIONS TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON FUNCTIONS TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON FUNCTIONS TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON FUNCTIONS TO service_role;


--
-- Name: DEFAULT PRIVILEGES FOR FUNCTIONS; Type: DEFAULT ACL; Schema: public; Owner: supabase_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public GRANT ALL ON FUNCTIONS TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public GRANT ALL ON FUNCTIONS TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public GRANT ALL ON FUNCTIONS TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public GRANT ALL ON FUNCTIONS TO service_role;


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: public; Owner: postgres
--

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON TABLES TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON TABLES TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON TABLES TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON TABLES TO service_role;


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: public; Owner: supabase_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public GRANT ALL ON TABLES TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public GRANT ALL ON TABLES TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public GRANT ALL ON TABLES TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public GRANT ALL ON TABLES TO service_role;


--
-- Name: DEFAULT PRIVILEGES FOR SEQUENCES; Type: DEFAULT ACL; Schema: realtime; Owner: supabase_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA realtime GRANT ALL ON SEQUENCES TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA realtime GRANT ALL ON SEQUENCES TO dashboard_user;


--
-- Name: DEFAULT PRIVILEGES FOR FUNCTIONS; Type: DEFAULT ACL; Schema: realtime; Owner: supabase_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA realtime GRANT ALL ON FUNCTIONS TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA realtime GRANT ALL ON FUNCTIONS TO dashboard_user;


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: realtime; Owner: supabase_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA realtime GRANT ALL ON TABLES TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA realtime GRANT ALL ON TABLES TO dashboard_user;


--
-- Name: DEFAULT PRIVILEGES FOR SEQUENCES; Type: DEFAULT ACL; Schema: storage; Owner: postgres
--

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA storage GRANT ALL ON SEQUENCES TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA storage GRANT ALL ON SEQUENCES TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA storage GRANT ALL ON SEQUENCES TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA storage GRANT ALL ON SEQUENCES TO service_role;


--
-- Name: DEFAULT PRIVILEGES FOR FUNCTIONS; Type: DEFAULT ACL; Schema: storage; Owner: postgres
--

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA storage GRANT ALL ON FUNCTIONS TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA storage GRANT ALL ON FUNCTIONS TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA storage GRANT ALL ON FUNCTIONS TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA storage GRANT ALL ON FUNCTIONS TO service_role;


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: storage; Owner: postgres
--

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA storage GRANT ALL ON TABLES TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA storage GRANT ALL ON TABLES TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA storage GRANT ALL ON TABLES TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA storage GRANT ALL ON TABLES TO service_role;


--
-- Name: issue_graphql_placeholder; Type: EVENT TRIGGER; Schema: -; Owner: supabase_admin
--

CREATE EVENT TRIGGER issue_graphql_placeholder ON sql_drop
         WHEN TAG IN ('DROP EXTENSION')
   EXECUTE FUNCTION extensions.set_graphql_placeholder();


ALTER EVENT TRIGGER issue_graphql_placeholder OWNER TO supabase_admin;

--
-- Name: issue_pg_cron_access; Type: EVENT TRIGGER; Schema: -; Owner: supabase_admin
--

CREATE EVENT TRIGGER issue_pg_cron_access ON ddl_command_end
         WHEN TAG IN ('CREATE EXTENSION')
   EXECUTE FUNCTION extensions.grant_pg_cron_access();


ALTER EVENT TRIGGER issue_pg_cron_access OWNER TO supabase_admin;

--
-- Name: issue_pg_graphql_access; Type: EVENT TRIGGER; Schema: -; Owner: supabase_admin
--

CREATE EVENT TRIGGER issue_pg_graphql_access ON ddl_command_end
         WHEN TAG IN ('CREATE EXTENSION')
   EXECUTE FUNCTION extensions.grant_pg_graphql_access();


ALTER EVENT TRIGGER issue_pg_graphql_access OWNER TO supabase_admin;

--
-- Name: issue_pg_net_access; Type: EVENT TRIGGER; Schema: -; Owner: supabase_admin
--

CREATE EVENT TRIGGER issue_pg_net_access ON ddl_command_end
         WHEN TAG IN ('CREATE EXTENSION')
   EXECUTE FUNCTION extensions.grant_pg_net_access();


ALTER EVENT TRIGGER issue_pg_net_access OWNER TO supabase_admin;

--
-- Name: pgrst_ddl_watch; Type: EVENT TRIGGER; Schema: -; Owner: supabase_admin
--

CREATE EVENT TRIGGER pgrst_ddl_watch ON ddl_command_end
   EXECUTE FUNCTION extensions.pgrst_ddl_watch();


ALTER EVENT TRIGGER pgrst_ddl_watch OWNER TO supabase_admin;

--
-- Name: pgrst_drop_watch; Type: EVENT TRIGGER; Schema: -; Owner: supabase_admin
--

CREATE EVENT TRIGGER pgrst_drop_watch ON sql_drop
   EXECUTE FUNCTION extensions.pgrst_drop_watch();


ALTER EVENT TRIGGER pgrst_drop_watch OWNER TO supabase_admin;

--
-- PostgreSQL database dump complete
--

\unrestrict Wavtl3b3y5hu0z4tmzxMjrG7gEjzCaqIVeKy7EjIgfbZADYDq4dYDNodx3pOZif

