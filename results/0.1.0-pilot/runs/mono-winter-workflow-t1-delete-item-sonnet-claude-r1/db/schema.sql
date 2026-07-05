--
-- PostgreSQL database dump
--

\restrict zsknqpLQzeTSmIrB5FbVzv2mwwgzF84W6qv2r8y6wx0QrX1JRIVlkjXX5iiGoGX

-- Dumped from database version 16.14 (Debian 16.14-1.pgdg13+1)
-- Dumped by pg_dump version 16.14 (Debian 16.14-1.pgdg13+1)

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

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: items; Type: TABLE; Schema: public; Owner: wts_alpha
--

CREATE TABLE public.items (
    id bigint NOT NULL,
    label character varying NOT NULL,
    source character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.items OWNER TO wts_alpha;

--
-- Name: items_id_seq; Type: SEQUENCE; Schema: public; Owner: wts_alpha
--

CREATE SEQUENCE public.items_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.items_id_seq OWNER TO wts_alpha;

--
-- Name: items_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: wts_alpha
--

ALTER SEQUENCE public.items_id_seq OWNED BY public.items.id;


--
-- Name: items id; Type: DEFAULT; Schema: public; Owner: wts_alpha
--

ALTER TABLE ONLY public.items ALTER COLUMN id SET DEFAULT nextval('public.items_id_seq'::regclass);


--
-- Name: items items_pkey; Type: CONSTRAINT; Schema: public; Owner: wts_alpha
--

ALTER TABLE ONLY public.items
    ADD CONSTRAINT items_pkey PRIMARY KEY (id);


--
-- PostgreSQL database dump complete
--

\unrestrict zsknqpLQzeTSmIrB5FbVzv2mwwgzF84W6qv2r8y6wx0QrX1JRIVlkjXX5iiGoGX

