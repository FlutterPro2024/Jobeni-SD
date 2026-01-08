--
-- PostgreSQL database dump
--

-- Dumped from database version 17.0
-- Dumped by pg_dump version 17.0

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

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: application; Type: TABLE; Schema: public; Owner: u0_a248
--

CREATE TABLE public.application (
    id integer NOT NULL,
    user_id integer NOT NULL,
    job_id integer NOT NULL,
    cv_id integer,
    match_score integer,
    match_explanation text,
    status character varying(20),
    applied_at timestamp without time zone
);


ALTER TABLE public.application OWNER TO u0_a248;

--
-- Name: application_id_seq; Type: SEQUENCE; Schema: public; Owner: u0_a248
--

CREATE SEQUENCE public.application_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.application_id_seq OWNER TO u0_a248;

--
-- Name: application_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: u0_a248
--

ALTER SEQUENCE public.application_id_seq OWNED BY public.application.id;


--
-- Name: comment; Type: TABLE; Schema: public; Owner: u0_a248
--

CREATE TABLE public.comment (
    id integer NOT NULL,
    body character varying(500) NOT NULL,
    "timestamp" timestamp without time zone,
    user_id integer NOT NULL,
    post_id integer NOT NULL
);


ALTER TABLE public.comment OWNER TO u0_a248;

--
-- Name: comment_id_seq; Type: SEQUENCE; Schema: public; Owner: u0_a248
--

CREATE SEQUENCE public.comment_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.comment_id_seq OWNER TO u0_a248;

--
-- Name: comment_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: u0_a248
--

ALTER SEQUENCE public.comment_id_seq OWNED BY public.comment.id;


--
-- Name: cv; Type: TABLE; Schema: public; Owner: u0_a248
--

CREATE TABLE public.cv (
    id integer NOT NULL,
    file_path character varying(200) NOT NULL,
    extracted_text text,
    profession character varying(100),
    skills json,
    feedback text,
    score integer,
    optimized_text text,
    user_id integer NOT NULL,
    created_at timestamp without time zone
);


ALTER TABLE public.cv OWNER TO u0_a248;

--
-- Name: cv_id_seq; Type: SEQUENCE; Schema: public; Owner: u0_a248
--

CREATE SEQUENCE public.cv_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.cv_id_seq OWNER TO u0_a248;

--
-- Name: cv_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: u0_a248
--

ALTER SEQUENCE public.cv_id_seq OWNED BY public.cv.id;


--
-- Name: followers; Type: TABLE; Schema: public; Owner: u0_a248
--

CREATE TABLE public.followers (
    follower_id integer,
    followed_id integer
);


ALTER TABLE public.followers OWNER TO u0_a248;

--
-- Name: interview_report; Type: TABLE; Schema: public; Owner: u0_a248
--

CREATE TABLE public.interview_report (
    id integer NOT NULL,
    user_id integer NOT NULL,
    job_title character varying(200),
    full_report text,
    score character varying(20),
    created_at timestamp without time zone
);


ALTER TABLE public.interview_report OWNER TO u0_a248;

--
-- Name: interview_report_id_seq; Type: SEQUENCE; Schema: public; Owner: u0_a248
--

CREATE SEQUENCE public.interview_report_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.interview_report_id_seq OWNER TO u0_a248;

--
-- Name: interview_report_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: u0_a248
--

ALTER SEQUENCE public.interview_report_id_seq OWNED BY public.interview_report.id;


--
-- Name: interview_session; Type: TABLE; Schema: public; Owner: u0_a248
--

CREATE TABLE public.interview_session (
    id integer NOT NULL,
    user_id integer NOT NULL,
    skill_name character varying(100) NOT NULL,
    questions_content text NOT NULL,
    created_at timestamp without time zone
);


ALTER TABLE public.interview_session OWNER TO u0_a248;

--
-- Name: interview_session_id_seq; Type: SEQUENCE; Schema: public; Owner: u0_a248
--

CREATE SEQUENCE public.interview_session_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.interview_session_id_seq OWNER TO u0_a248;

--
-- Name: interview_session_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: u0_a248
--

ALTER SEQUENCE public.interview_session_id_seq OWNED BY public.interview_session.id;


--
-- Name: job; Type: TABLE; Schema: public; Owner: u0_a248
--

CREATE TABLE public.job (
    id integer NOT NULL,
    title character varying(100) NOT NULL,
    company_name character varying(100) NOT NULL,
    location character varying(100) NOT NULL,
    description text NOT NULL,
    category character varying(50),
    salary character varying(50),
    job_type character varying(50),
    latitude double precision,
    longitude double precision,
    is_active boolean,
    created_at timestamp without time zone,
    employer_id integer NOT NULL
);


ALTER TABLE public.job OWNER TO u0_a248;

--
-- Name: job_id_seq; Type: SEQUENCE; Schema: public; Owner: u0_a248
--

CREATE SEQUENCE public.job_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.job_id_seq OWNER TO u0_a248;

--
-- Name: job_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: u0_a248
--

ALTER SEQUENCE public.job_id_seq OWNED BY public.job.id;


--
-- Name: message; Type: TABLE; Schema: public; Owner: u0_a248
--

CREATE TABLE public.message (
    id integer NOT NULL,
    sender_id integer NOT NULL,
    recipient_id integer NOT NULL,
    job_id integer,
    body text NOT NULL,
    "timestamp" timestamp without time zone,
    is_read boolean
);


ALTER TABLE public.message OWNER TO u0_a248;

--
-- Name: message_id_seq; Type: SEQUENCE; Schema: public; Owner: u0_a248
--

CREATE SEQUENCE public.message_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.message_id_seq OWNER TO u0_a248;

--
-- Name: message_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: u0_a248
--

ALTER SEQUENCE public.message_id_seq OWNED BY public.message.id;


--
-- Name: notification; Type: TABLE; Schema: public; Owner: u0_a248
--

CREATE TABLE public.notification (
    id integer NOT NULL,
    user_id integer NOT NULL,
    title character varying(150) NOT NULL,
    message text NOT NULL,
    category character varying(50),
    is_read boolean,
    link character varying(200),
    created_at timestamp without time zone
);


ALTER TABLE public.notification OWNER TO u0_a248;

--
-- Name: notification_id_seq; Type: SEQUENCE; Schema: public; Owner: u0_a248
--

CREATE SEQUENCE public.notification_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.notification_id_seq OWNER TO u0_a248;

--
-- Name: notification_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: u0_a248
--

ALTER SEQUENCE public.notification_id_seq OWNED BY public.notification.id;


--
-- Name: post; Type: TABLE; Schema: public; Owner: u0_a248
--

CREATE TABLE public.post (
    id integer NOT NULL,
    body text NOT NULL,
    image_path character varying(200),
    "timestamp" timestamp without time zone,
    user_id integer NOT NULL
);


ALTER TABLE public.post OWNER TO u0_a248;

--
-- Name: post_id_seq; Type: SEQUENCE; Schema: public; Owner: u0_a248
--

CREATE SEQUENCE public.post_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.post_id_seq OWNER TO u0_a248;

--
-- Name: post_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: u0_a248
--

ALTER SEQUENCE public.post_id_seq OWNED BY public.post.id;


--
-- Name: post_like; Type: TABLE; Schema: public; Owner: u0_a248
--

CREATE TABLE public.post_like (
    id integer NOT NULL,
    user_id integer NOT NULL,
    post_id integer NOT NULL
);


ALTER TABLE public.post_like OWNER TO u0_a248;

--
-- Name: post_like_id_seq; Type: SEQUENCE; Schema: public; Owner: u0_a248
--

CREATE SEQUENCE public.post_like_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.post_like_id_seq OWNER TO u0_a248;

--
-- Name: post_like_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: u0_a248
--

ALTER SEQUENCE public.post_like_id_seq OWNED BY public.post_like.id;


--
-- Name: user; Type: TABLE; Schema: public; Owner: u0_a248
--

CREATE TABLE public."user" (
    id integer NOT NULL,
    username character varying(50) NOT NULL,
    email character varying(120) NOT NULL,
    password character varying(200) NOT NULL,
    role character varying(20),
    full_name character varying(100),
    telegram_id character varying(100),
    created_at timestamp without time zone,
    avatar character varying(200) DEFAULT 'default_avatar.png'::character varying,
    bio text,
    headline character varying(150),
    location_name character varying(100),
    phone character varying(30)
);


ALTER TABLE public."user" OWNER TO u0_a248;

--
-- Name: user_id_seq; Type: SEQUENCE; Schema: public; Owner: u0_a248
--

CREATE SEQUENCE public.user_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.user_id_seq OWNER TO u0_a248;

--
-- Name: user_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: u0_a248
--

ALTER SEQUENCE public.user_id_seq OWNED BY public."user".id;


--
-- Name: application id; Type: DEFAULT; Schema: public; Owner: u0_a248
--

ALTER TABLE ONLY public.application ALTER COLUMN id SET DEFAULT nextval('public.application_id_seq'::regclass);


--
-- Name: comment id; Type: DEFAULT; Schema: public; Owner: u0_a248
--

ALTER TABLE ONLY public.comment ALTER COLUMN id SET DEFAULT nextval('public.comment_id_seq'::regclass);


--
-- Name: cv id; Type: DEFAULT; Schema: public; Owner: u0_a248
--

ALTER TABLE ONLY public.cv ALTER COLUMN id SET DEFAULT nextval('public.cv_id_seq'::regclass);


--
-- Name: interview_report id; Type: DEFAULT; Schema: public; Owner: u0_a248
--

ALTER TABLE ONLY public.interview_report ALTER COLUMN id SET DEFAULT nextval('public.interview_report_id_seq'::regclass);


--
-- Name: interview_session id; Type: DEFAULT; Schema: public; Owner: u0_a248
--

ALTER TABLE ONLY public.interview_session ALTER COLUMN id SET DEFAULT nextval('public.interview_session_id_seq'::regclass);


--
-- Name: job id; Type: DEFAULT; Schema: public; Owner: u0_a248
--

ALTER TABLE ONLY public.job ALTER COLUMN id SET DEFAULT nextval('public.job_id_seq'::regclass);


--
-- Name: message id; Type: DEFAULT; Schema: public; Owner: u0_a248
--

ALTER TABLE ONLY public.message ALTER COLUMN id SET DEFAULT nextval('public.message_id_seq'::regclass);


--
-- Name: notification id; Type: DEFAULT; Schema: public; Owner: u0_a248
--

ALTER TABLE ONLY public.notification ALTER COLUMN id SET DEFAULT nextval('public.notification_id_seq'::regclass);


--
-- Name: post id; Type: DEFAULT; Schema: public; Owner: u0_a248
--

ALTER TABLE ONLY public.post ALTER COLUMN id SET DEFAULT nextval('public.post_id_seq'::regclass);


--
-- Name: post_like id; Type: DEFAULT; Schema: public; Owner: u0_a248
--

ALTER TABLE ONLY public.post_like ALTER COLUMN id SET DEFAULT nextval('public.post_like_id_seq'::regclass);


--
-- Name: user id; Type: DEFAULT; Schema: public; Owner: u0_a248
--

ALTER TABLE ONLY public."user" ALTER COLUMN id SET DEFAULT nextval('public.user_id_seq'::regclass);


--
-- Data for Name: application; Type: TABLE DATA; Schema: public; Owner: u0_a248
--

COPY public.application (id, user_id, job_id, cv_id, match_score, match_explanation, status, applied_at) FROM stdin;
\.


--
-- Data for Name: comment; Type: TABLE DATA; Schema: public; Owner: u0_a248
--

COPY public.comment (id, body, "timestamp", user_id, post_id) FROM stdin;
\.


--
-- Data for Name: cv; Type: TABLE DATA; Schema: public; Owner: u0_a248
--

COPY public.cv (id, file_path, extracted_text, profession, skills, feedback, score, optimized_text, user_id, created_at) FROM stdin;
\.


--
-- Data for Name: followers; Type: TABLE DATA; Schema: public; Owner: u0_a248
--

COPY public.followers (follower_id, followed_id) FROM stdin;
\.


--
-- Data for Name: interview_report; Type: TABLE DATA; Schema: public; Owner: u0_a248
--

COPY public.interview_report (id, user_id, job_title, full_report, score, created_at) FROM stdin;
\.


--
-- Data for Name: interview_session; Type: TABLE DATA; Schema: public; Owner: u0_a248
--

COPY public.interview_session (id, user_id, skill_name, questions_content, created_at) FROM stdin;
\.


--
-- Data for Name: job; Type: TABLE DATA; Schema: public; Owner: u0_a248
--

COPY public.job (id, title, company_name, location, description, category, salary, job_type, latitude, longitude, is_active, created_at, employer_id) FROM stdin;
\.


--
-- Data for Name: message; Type: TABLE DATA; Schema: public; Owner: u0_a248
--

COPY public.message (id, sender_id, recipient_id, job_id, body, "timestamp", is_read) FROM stdin;
\.


--
-- Data for Name: notification; Type: TABLE DATA; Schema: public; Owner: u0_a248
--

COPY public.notification (id, user_id, title, message, category, is_read, link, created_at) FROM stdin;
\.


--
-- Data for Name: post; Type: TABLE DATA; Schema: public; Owner: u0_a248
--

COPY public.post (id, body, image_path, "timestamp", user_id) FROM stdin;
\.


--
-- Data for Name: post_like; Type: TABLE DATA; Schema: public; Owner: u0_a248
--

COPY public.post_like (id, user_id, post_id) FROM stdin;
\.


--
-- Data for Name: user; Type: TABLE DATA; Schema: public; Owner: u0_a248
--

COPY public."user" (id, username, email, password, role, full_name, telegram_id, created_at, avatar, bio, headline, location_name, phone) FROM stdin;
1	admin_boss	admin@jobeni.sd	scrypt:32768:8:1$qh1yqTPGszoJPtEL$993806b7486af581048f5aed85bb5356140384cf2d7b1482cc63bf0e0ddd75c6cdd8679ce1ae7e75a3b4fab7b88fd63e236fa1e37e5f7f0838901c8d05b90a7b	admin	Jobeni Super Admin	\N	2026-01-03 23:25:32.650099	default_avatar.png	\N	\N	\N	\N
\.


--
-- Name: application_id_seq; Type: SEQUENCE SET; Schema: public; Owner: u0_a248
--

SELECT pg_catalog.setval('public.application_id_seq', 1, false);


--
-- Name: comment_id_seq; Type: SEQUENCE SET; Schema: public; Owner: u0_a248
--

SELECT pg_catalog.setval('public.comment_id_seq', 1, false);


--
-- Name: cv_id_seq; Type: SEQUENCE SET; Schema: public; Owner: u0_a248
--

SELECT pg_catalog.setval('public.cv_id_seq', 1, false);


--
-- Name: interview_report_id_seq; Type: SEQUENCE SET; Schema: public; Owner: u0_a248
--

SELECT pg_catalog.setval('public.interview_report_id_seq', 1, false);


--
-- Name: interview_session_id_seq; Type: SEQUENCE SET; Schema: public; Owner: u0_a248
--

SELECT pg_catalog.setval('public.interview_session_id_seq', 1, false);


--
-- Name: job_id_seq; Type: SEQUENCE SET; Schema: public; Owner: u0_a248
--

SELECT pg_catalog.setval('public.job_id_seq', 1, false);


--
-- Name: message_id_seq; Type: SEQUENCE SET; Schema: public; Owner: u0_a248
--

SELECT pg_catalog.setval('public.message_id_seq', 1, false);


--
-- Name: notification_id_seq; Type: SEQUENCE SET; Schema: public; Owner: u0_a248
--

SELECT pg_catalog.setval('public.notification_id_seq', 1, false);


--
-- Name: post_id_seq; Type: SEQUENCE SET; Schema: public; Owner: u0_a248
--

SELECT pg_catalog.setval('public.post_id_seq', 1, false);


--
-- Name: post_like_id_seq; Type: SEQUENCE SET; Schema: public; Owner: u0_a248
--

SELECT pg_catalog.setval('public.post_like_id_seq', 1, false);


--
-- Name: user_id_seq; Type: SEQUENCE SET; Schema: public; Owner: u0_a248
--

SELECT pg_catalog.setval('public.user_id_seq', 1, true);


--
-- Name: application application_pkey; Type: CONSTRAINT; Schema: public; Owner: u0_a248
--

ALTER TABLE ONLY public.application
    ADD CONSTRAINT application_pkey PRIMARY KEY (id);


--
-- Name: comment comment_pkey; Type: CONSTRAINT; Schema: public; Owner: u0_a248
--

ALTER TABLE ONLY public.comment
    ADD CONSTRAINT comment_pkey PRIMARY KEY (id);


--
-- Name: cv cv_pkey; Type: CONSTRAINT; Schema: public; Owner: u0_a248
--

ALTER TABLE ONLY public.cv
    ADD CONSTRAINT cv_pkey PRIMARY KEY (id);


--
-- Name: interview_report interview_report_pkey; Type: CONSTRAINT; Schema: public; Owner: u0_a248
--

ALTER TABLE ONLY public.interview_report
    ADD CONSTRAINT interview_report_pkey PRIMARY KEY (id);


--
-- Name: interview_session interview_session_pkey; Type: CONSTRAINT; Schema: public; Owner: u0_a248
--

ALTER TABLE ONLY public.interview_session
    ADD CONSTRAINT interview_session_pkey PRIMARY KEY (id);


--
-- Name: job job_pkey; Type: CONSTRAINT; Schema: public; Owner: u0_a248
--

ALTER TABLE ONLY public.job
    ADD CONSTRAINT job_pkey PRIMARY KEY (id);


--
-- Name: message message_pkey; Type: CONSTRAINT; Schema: public; Owner: u0_a248
--

ALTER TABLE ONLY public.message
    ADD CONSTRAINT message_pkey PRIMARY KEY (id);


--
-- Name: notification notification_pkey; Type: CONSTRAINT; Schema: public; Owner: u0_a248
--

ALTER TABLE ONLY public.notification
    ADD CONSTRAINT notification_pkey PRIMARY KEY (id);


--
-- Name: post_like post_like_pkey; Type: CONSTRAINT; Schema: public; Owner: u0_a248
--

ALTER TABLE ONLY public.post_like
    ADD CONSTRAINT post_like_pkey PRIMARY KEY (id);


--
-- Name: post post_pkey; Type: CONSTRAINT; Schema: public; Owner: u0_a248
--

ALTER TABLE ONLY public.post
    ADD CONSTRAINT post_pkey PRIMARY KEY (id);


--
-- Name: user user_email_key; Type: CONSTRAINT; Schema: public; Owner: u0_a248
--

ALTER TABLE ONLY public."user"
    ADD CONSTRAINT user_email_key UNIQUE (email);


--
-- Name: user user_pkey; Type: CONSTRAINT; Schema: public; Owner: u0_a248
--

ALTER TABLE ONLY public."user"
    ADD CONSTRAINT user_pkey PRIMARY KEY (id);


--
-- Name: user user_username_key; Type: CONSTRAINT; Schema: public; Owner: u0_a248
--

ALTER TABLE ONLY public."user"
    ADD CONSTRAINT user_username_key UNIQUE (username);


--
-- Name: ix_comment_timestamp; Type: INDEX; Schema: public; Owner: u0_a248
--

CREATE INDEX ix_comment_timestamp ON public.comment USING btree ("timestamp");


--
-- Name: ix_post_timestamp; Type: INDEX; Schema: public; Owner: u0_a248
--

CREATE INDEX ix_post_timestamp ON public.post USING btree ("timestamp");


--
-- Name: application application_cv_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: u0_a248
--

ALTER TABLE ONLY public.application
    ADD CONSTRAINT application_cv_id_fkey FOREIGN KEY (cv_id) REFERENCES public.cv(id);


--
-- Name: application application_job_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: u0_a248
--

ALTER TABLE ONLY public.application
    ADD CONSTRAINT application_job_id_fkey FOREIGN KEY (job_id) REFERENCES public.job(id);


--
-- Name: application application_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: u0_a248
--

ALTER TABLE ONLY public.application
    ADD CONSTRAINT application_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: comment comment_post_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: u0_a248
--

ALTER TABLE ONLY public.comment
    ADD CONSTRAINT comment_post_id_fkey FOREIGN KEY (post_id) REFERENCES public.post(id);


--
-- Name: comment comment_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: u0_a248
--

ALTER TABLE ONLY public.comment
    ADD CONSTRAINT comment_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: cv cv_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: u0_a248
--

ALTER TABLE ONLY public.cv
    ADD CONSTRAINT cv_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: followers followers_followed_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: u0_a248
--

ALTER TABLE ONLY public.followers
    ADD CONSTRAINT followers_followed_id_fkey FOREIGN KEY (followed_id) REFERENCES public."user"(id);


--
-- Name: followers followers_follower_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: u0_a248
--

ALTER TABLE ONLY public.followers
    ADD CONSTRAINT followers_follower_id_fkey FOREIGN KEY (follower_id) REFERENCES public."user"(id);


--
-- Name: interview_report interview_report_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: u0_a248
--

ALTER TABLE ONLY public.interview_report
    ADD CONSTRAINT interview_report_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: interview_session interview_session_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: u0_a248
--

ALTER TABLE ONLY public.interview_session
    ADD CONSTRAINT interview_session_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: job job_employer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: u0_a248
--

ALTER TABLE ONLY public.job
    ADD CONSTRAINT job_employer_id_fkey FOREIGN KEY (employer_id) REFERENCES public."user"(id);


--
-- Name: message message_job_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: u0_a248
--

ALTER TABLE ONLY public.message
    ADD CONSTRAINT message_job_id_fkey FOREIGN KEY (job_id) REFERENCES public.job(id);


--
-- Name: message message_recipient_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: u0_a248
--

ALTER TABLE ONLY public.message
    ADD CONSTRAINT message_recipient_id_fkey FOREIGN KEY (recipient_id) REFERENCES public."user"(id);


--
-- Name: message message_sender_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: u0_a248
--

ALTER TABLE ONLY public.message
    ADD CONSTRAINT message_sender_id_fkey FOREIGN KEY (sender_id) REFERENCES public."user"(id);


--
-- Name: notification notification_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: u0_a248
--

ALTER TABLE ONLY public.notification
    ADD CONSTRAINT notification_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: post_like post_like_post_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: u0_a248
--

ALTER TABLE ONLY public.post_like
    ADD CONSTRAINT post_like_post_id_fkey FOREIGN KEY (post_id) REFERENCES public.post(id);


--
-- Name: post_like post_like_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: u0_a248
--

ALTER TABLE ONLY public.post_like
    ADD CONSTRAINT post_like_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: post post_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: u0_a248
--

ALTER TABLE ONLY public.post
    ADD CONSTRAINT post_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- PostgreSQL database dump complete
--

