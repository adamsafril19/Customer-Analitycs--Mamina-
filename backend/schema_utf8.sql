--
-- PostgreSQL database dump
--

\restrict MMI9WebUUtJgtpJRdOuUsy2HSEH3rtnW1bK7tCHJKotj5hNJcEPI4O7F61QeiYC

-- Dumped from database version 17.9 (Debian 17.9-1.pgdg12+1)
-- Dumped by pg_dump version 17.9 (Debian 17.9-1.pgdg12+1)

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
-- Name: vector; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;


--
-- Name: EXTENSION vector; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION vector IS 'vector data type and ivfflat and hnsw access methods';


--
-- Name: validate_feature_customer_id(); Type: FUNCTION; Schema: public; Owner: mamina
--

CREATE FUNCTION public.validate_feature_customer_id() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
            IF NEW.link_id IS NOT NULL THEN
                IF NEW.customer_id != (
                    SELECT customer_id FROM feedback_linked WHERE link_id = NEW.link_id
                ) THEN
                    RAISE EXCEPTION 'customer_id mismatch: feedback_features.customer_id must match feedback_linked.customer_id';
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$;


ALTER FUNCTION public.validate_feature_customer_id() OWNER TO mamina;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: actions; Type: TABLE; Schema: public; Owner: mamina
--

CREATE TABLE public.actions (
    action_id uuid NOT NULL,
    pred_id uuid,
    customer_id uuid NOT NULL,
    action_type character varying(50) NOT NULL,
    priority character varying(20) NOT NULL,
    assigned_to character varying(120),
    status character varying(20) NOT NULL,
    notes text,
    due_date date,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.actions OWNER TO mamina;

--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: mamina
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


ALTER TABLE public.alembic_version OWNER TO mamina;

--
-- Name: churn_labels; Type: TABLE; Schema: public; Owner: mamina
--

CREATE TABLE public.churn_labels (
    label_id uuid NOT NULL,
    customer_id uuid NOT NULL,
    observation_date date NOT NULL,
    outcome_date date NOT NULL,
    is_churned boolean NOT NULL,
    days_to_next_tx integer,
    last_tx_before_obs date,
    labeled_at timestamp without time zone,
    label_method character varying(50)
);


ALTER TABLE public.churn_labels OWNER TO mamina;

--
-- Name: churn_predictions; Type: TABLE; Schema: public; Owner: mamina
--

CREATE TABLE public.churn_predictions (
    pred_id uuid NOT NULL,
    customer_id uuid NOT NULL,
    churn_score double precision NOT NULL,
    churn_label character varying(20) NOT NULL,
    model_version character varying(50) NOT NULL,
    as_of_date date NOT NULL,
    created_at timestamp without time zone DEFAULT now(),
    features_used json,
    feature_as_of timestamp without time zone,
    feature_schema_hash character varying(64),
    model_hash character varying(32)
);


ALTER TABLE public.churn_predictions OWNER TO mamina;

--
-- Name: COLUMN churn_predictions.features_used; Type: COMMENT; Schema: public; Owner: mamina
--

COMMENT ON COLUMN public.churn_predictions.features_used IS 'Immutable snapshot of features at prediction time';


--
-- Name: COLUMN churn_predictions.feature_as_of; Type: COMMENT; Schema: public; Owner: mamina
--

COMMENT ON COLUMN public.churn_predictions.feature_as_of IS 'Exact timestamp features were computed (for Explainer)';


--
-- Name: COLUMN churn_predictions.feature_schema_hash; Type: COMMENT; Schema: public; Owner: mamina
--

COMMENT ON COLUMN public.churn_predictions.feature_schema_hash IS 'Hash of feature schema at prediction time';


--
-- Name: COLUMN churn_predictions.model_hash; Type: COMMENT; Schema: public; Owner: mamina
--

COMMENT ON COLUMN public.churn_predictions.model_hash IS 'Hash of model used for prediction';


--
-- Name: customer_numeric_features; Type: TABLE; Schema: public; Owner: mamina
--

CREATE TABLE public.customer_numeric_features (
    feature_id uuid NOT NULL,
    customer_id uuid NOT NULL,
    as_of_date date NOT NULL,
    r_score double precision,
    f_score double precision,
    m_score double precision,
    tenure_days integer,
    created_at timestamp without time zone,
    recency_days integer,
    tx_count_30d integer,
    tx_count_90d integer,
    spend_30d double precision,
    spend_90d double precision,
    avg_tx_value double precision,
    homecare_tx_ratio_90d double precision,
    last_tx_is_homecare double precision,
    zero_amount_tx_count_90d integer,
    lifetime_tx_count integer
);


ALTER TABLE public.customer_numeric_features OWNER TO mamina;

--
-- Name: customer_text_semantics; Type: TABLE; Schema: public; Owner: mamina
--

CREATE TABLE public.customer_text_semantics (
    id uuid NOT NULL,
    customer_id uuid NOT NULL,
    as_of_date date NOT NULL,
    top_topic_counts jsonb,
    sentiment_dist jsonb,
    top_keywords jsonb,
    top_complaint_types jsonb,
    last_n_msg_ids jsonb,
    created_at timestamp without time zone,
    avg_sentiment_score double precision,
    avg_topic_similarity double precision,
    topic_model_version character varying(50),
    sentiment_model_version character varying(100)
);


ALTER TABLE public.customer_text_semantics OWNER TO mamina;

--
-- Name: customer_text_signals; Type: TABLE; Schema: public; Owner: mamina
--

CREATE TABLE public.customer_text_signals (
    id uuid NOT NULL,
    customer_id uuid NOT NULL,
    as_of_date date NOT NULL,
    msg_count_7d integer,
    msg_count_30d integer,
    msg_volatility double precision,
    avg_msg_length_30d double precision,
    complaint_rate_30d double precision,
    response_delay_mean double precision,
    avg_embedding public.vector(384),
    embedding_count_30d integer,
    created_at timestamp without time zone
);


ALTER TABLE public.customer_text_signals OWNER TO mamina;

--
-- Name: customers; Type: TABLE; Schema: public; Owner: mamina
--

CREATE TABLE public.customers (
    customer_id uuid NOT NULL,
    external_id character varying(256),
    name character varying(200) NOT NULL,
    phone_hash character varying(256),
    city character varying(100),
    consent_given boolean,
    is_active boolean,
    created_at timestamp without time zone DEFAULT now(),
    last_seen_at timestamp without time zone,
    is_provisional boolean DEFAULT false
);


ALTER TABLE public.customers OWNER TO mamina;

--
-- Name: feedback_features; Type: TABLE; Schema: public; Owner: mamina
--

CREATE TABLE public.feedback_features (
    feature_id uuid NOT NULL,
    msg_id uuid NOT NULL,
    customer_id uuid NOT NULL,
    msg_length integer,
    num_exclamations integer,
    num_questions integer,
    has_complaint boolean,
    has_refund_request boolean,
    language_confidence double precision,
    response_time_secs integer,
    processed_at timestamp without time zone,
    embedding public.vector(384),
    link_id uuid NOT NULL,
    embedding_model_version character varying(100),
    sentiment_label character varying(20),
    sentiment_score double precision,
    sentiment_model_version character varying(100),
    sentiment_processed_at timestamp without time zone
);


ALTER TABLE public.feedback_features OWNER TO mamina;

--
-- Name: feedback_linked; Type: TABLE; Schema: public; Owner: mamina
--

CREATE TABLE public.feedback_linked (
    link_id uuid NOT NULL,
    msg_id uuid NOT NULL,
    customer_id uuid NOT NULL,
    match_confidence double precision,
    match_method character varying(50),
    linked_at timestamp without time zone,
    link_status character varying(20) DEFAULT 'provisional'::character varying NOT NULL,
    CONSTRAINT chk_link_status CHECK (((link_status)::text = ANY ((ARRAY['verified'::character varying, 'probable'::character varying, 'provisional'::character varying, 'rejected'::character varying])::text[]))),
    CONSTRAINT chk_match_confidence_range CHECK (((match_confidence >= (0)::double precision) AND (match_confidence <= (1)::double precision)))
);


ALTER TABLE public.feedback_linked OWNER TO mamina;

--
-- Name: dashboard_semantic_embeddings; Type: VIEW; Schema: public; Owner: mamina
--

CREATE VIEW public.dashboard_semantic_embeddings AS
 SELECT fl.customer_id,
    fl.link_id,
    fl.link_status,
    ff.embedding,
    ff.embedding_model_version,
    ff.processed_at
   FROM (public.feedback_linked fl
     JOIN public.feedback_features ff ON ((fl.link_id = ff.link_id)))
  WHERE (((fl.link_status)::text = ANY ((ARRAY['verified'::character varying, 'probable'::character varying])::text[])) AND (ff.embedding IS NOT NULL));


ALTER VIEW public.dashboard_semantic_embeddings OWNER TO mamina;

--
-- Name: embedding_model_registry; Type: TABLE; Schema: public; Owner: mamina
--

CREATE TABLE public.embedding_model_registry (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    model_name character varying(200) NOT NULL,
    model_version character varying(100) NOT NULL,
    model_hash character varying(50) NOT NULL,
    embedding_dim integer NOT NULL,
    is_active boolean DEFAULT false,
    registered_at timestamp without time zone DEFAULT now(),
    notes text
);


ALTER TABLE public.embedding_model_registry OWNER TO mamina;

--
-- Name: feedback_raw; Type: TABLE; Schema: public; Owner: mamina
--

CREATE TABLE public.feedback_raw (
    msg_id uuid NOT NULL,
    direction character varying(20) NOT NULL,
    text text,
    "timestamp" timestamp without time zone NOT NULL,
    raw_meta jsonb,
    created_at timestamp without time zone DEFAULT now(),
    phone_number character varying(256) NOT NULL
);


ALTER TABLE public.feedback_raw OWNER TO mamina;

--
-- Name: ml_model_registry; Type: TABLE; Schema: public; Owner: mamina
--

CREATE TABLE public.ml_model_registry (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    model_name character varying(100) DEFAULT 'churn_model'::character varying NOT NULL,
    model_version character varying(50) NOT NULL,
    model_hash character varying(64) NOT NULL,
    feature_schema_hash character varying(64) NOT NULL,
    feature_names jsonb,
    expected_feature_count integer NOT NULL,
    trained_on_embedding_model_hash character varying(50),
    trained_on_link_status character varying(50) DEFAULT 'verified'::character varying,
    training_data_count integer,
    training_date timestamp without time zone,
    shap_explainer_hash character varying(64),
    is_active boolean DEFAULT false,
    registered_at timestamp without time zone DEFAULT now(),
    notes text
);


ALTER TABLE public.ml_model_registry OWNER TO mamina;

--
-- Name: model_versions; Type: TABLE; Schema: public; Owner: mamina
--

CREATE TABLE public.model_versions (
    model_version character varying(50) NOT NULL,
    model_path text,
    trained_at timestamp without time zone,
    metrics json,
    deployed boolean,
    notes text,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.model_versions OWNER TO mamina;

--
-- Name: real_customers; Type: VIEW; Schema: public; Owner: mamina
--

CREATE VIEW public.real_customers AS
 SELECT customer_id,
    external_id,
    name,
    phone_hash,
    city,
    consent_given,
    is_active,
    created_at,
    last_seen_at,
    is_provisional
   FROM public.customers
  WHERE ((is_provisional = false) OR (is_provisional IS NULL));


ALTER VIEW public.real_customers OWNER TO mamina;

--
-- Name: recommendation_contexts; Type: TABLE; Schema: public; Owner: mamina
--

CREATE TABLE public.recommendation_contexts (
    context_id uuid NOT NULL,
    pred_id uuid NOT NULL,
    customer_id uuid NOT NULL,
    as_of_date date NOT NULL,
    context_status character varying(30) NOT NULL,
    sentiment_label character varying(20),
    sentiment_score double precision,
    sentiment_trend double precision,
    dominant_topic_id character varying(50),
    dominant_topic_name text,
    topic_similarity double precision,
    complaint_ratio double precision,
    message_count integer NOT NULL,
    last_message_at timestamp without time zone,
    evidence_messages jsonb,
    recommended_action_type character varying(50) NOT NULL,
    priority character varying(20) NOT NULL,
    title character varying(200) NOT NULL,
    rationale text NOT NULL,
    reason_codes jsonb NOT NULL,
    policy_version character varying(50) NOT NULL,
    risk_model_version character varying(50) NOT NULL,
    sentiment_model_version character varying(100),
    topic_model_version character varying(100),
    embedding_model_version character varying(100),
    review_status character varying(20) NOT NULL,
    reviewed_by character varying(120),
    reviewed_at timestamp without time zone,
    created_at timestamp without time zone NOT NULL,
    recommendation_details jsonb
);


ALTER TABLE public.recommendation_contexts OWNER TO mamina;

--
-- Name: shap_cache; Type: TABLE; Schema: public; Owner: mamina
--

CREATE TABLE public.shap_cache (
    pred_id uuid NOT NULL,
    shap_values json,
    computed_at timestamp without time zone DEFAULT now(),
    explainer_version character varying(50),
    shap_top json,
    nearest_messages json,
    feature_schema_hash character varying(64),
    model_version character varying(50),
    explanation_type character varying(20),
    as_of timestamp without time zone
);


ALTER TABLE public.shap_cache OWNER TO mamina;

--
-- Name: topics; Type: TABLE; Schema: public; Owner: mamina
--

CREATE TABLE public.topics (
    topic_id uuid DEFAULT gen_random_uuid() NOT NULL,
    name text,
    top_keywords text[],
    model_version character varying(50) NOT NULL,
    created_at timestamp without time zone DEFAULT now(),
    topic_idx integer
);


ALTER TABLE public.topics OWNER TO mamina;

--
-- Name: transactions; Type: TABLE; Schema: public; Owner: mamina
--

CREATE TABLE public.transactions (
    tx_id uuid NOT NULL,
    customer_id uuid NOT NULL,
    tx_date timestamp without time zone NOT NULL,
    service_type character varying(100) NOT NULL,
    amount numeric(12,2) NOT NULL,
    status character varying(20) NOT NULL,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.transactions OWNER TO mamina;

--
-- Name: trusted_feedback_dashboard; Type: VIEW; Schema: public; Owner: mamina
--

CREATE VIEW public.trusted_feedback_dashboard AS
 SELECT fr.msg_id,
    fr.phone_number,
    fr.text,
    fr."timestamp",
    fr.direction,
    fl.link_id,
    fl.customer_id,
    fl.match_confidence,
    fl.link_status,
    ff.feature_id,
    ff.msg_length,
    ff.num_exclamations,
    ff.num_questions,
    ff.embedding,
    ff.processed_at
   FROM ((public.feedback_raw fr
     JOIN public.feedback_linked fl ON ((fr.msg_id = fl.msg_id)))
     LEFT JOIN public.feedback_features ff ON ((fl.link_id = ff.link_id)))
  WHERE ((fl.link_status)::text = ANY ((ARRAY['verified'::character varying, 'probable'::character varying])::text[]));


ALTER VIEW public.trusted_feedback_dashboard OWNER TO mamina;

--
-- Name: trusted_feedback_ml; Type: VIEW; Schema: public; Owner: mamina
--

CREATE VIEW public.trusted_feedback_ml AS
 SELECT fr.msg_id,
    fr.phone_number,
    fr.text,
    fr."timestamp",
    fr.direction,
    fl.link_id,
    fl.customer_id,
    fl.match_confidence,
    fl.link_status,
    ff.feature_id,
    ff.msg_length,
    ff.num_exclamations,
    ff.num_questions,
    ff.embedding,
    ff.processed_at
   FROM ((public.feedback_raw fr
     JOIN public.feedback_linked fl ON ((fr.msg_id = fl.msg_id)))
     LEFT JOIN public.feedback_features ff ON ((fl.link_id = ff.link_id)))
  WHERE ((fl.link_status)::text = 'verified'::text);


ALTER VIEW public.trusted_feedback_ml OWNER TO mamina;

--
-- Name: trusted_semantic_embeddings; Type: VIEW; Schema: public; Owner: mamina
--

CREATE VIEW public.trusted_semantic_embeddings AS
 SELECT fl.customer_id,
    fl.link_id,
    fl.link_status,
    ff.embedding,
    ff.embedding_model_version,
    ff.processed_at
   FROM (public.feedback_linked fl
     JOIN public.feedback_features ff ON ((fl.link_id = ff.link_id)))
  WHERE (((fl.link_status)::text = 'verified'::text) AND (ff.embedding IS NOT NULL) AND ((ff.embedding_model_version IS NULL) OR ((ff.embedding_model_version)::text = (( SELECT embedding_model_registry.model_version
           FROM public.embedding_model_registry
          WHERE (embedding_model_registry.is_active = true)
         LIMIT 1))::text)));


ALTER VIEW public.trusted_semantic_embeddings OWNER TO mamina;

--
-- Name: users; Type: TABLE; Schema: public; Owner: mamina
--

CREATE TABLE public.users (
    user_id uuid NOT NULL,
    username character varying(80) NOT NULL,
    email character varying(120) NOT NULL,
    password_hash character varying(256) NOT NULL,
    role character varying(20) NOT NULL,
    is_active boolean,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    last_login timestamp without time zone
);


ALTER TABLE public.users OWNER TO mamina;

--
-- Name: actions actions_pkey; Type: CONSTRAINT; Schema: public; Owner: mamina
--

ALTER TABLE ONLY public.actions
    ADD CONSTRAINT actions_pkey PRIMARY KEY (action_id);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: mamina
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: churn_labels churn_labels_pkey; Type: CONSTRAINT; Schema: public; Owner: mamina
--

ALTER TABLE ONLY public.churn_labels
    ADD CONSTRAINT churn_labels_pkey PRIMARY KEY (label_id);


--
-- Name: churn_predictions churn_predictions_pkey; Type: CONSTRAINT; Schema: public; Owner: mamina
--

ALTER TABLE ONLY public.churn_predictions
    ADD CONSTRAINT churn_predictions_pkey PRIMARY KEY (pred_id);


--
-- Name: customer_numeric_features customer_numeric_features_pkey; Type: CONSTRAINT; Schema: public; Owner: mamina
--

ALTER TABLE ONLY public.customer_numeric_features
    ADD CONSTRAINT customer_numeric_features_pkey PRIMARY KEY (feature_id);


--
-- Name: customer_text_semantics customer_text_semantics_pkey; Type: CONSTRAINT; Schema: public; Owner: mamina
--

ALTER TABLE ONLY public.customer_text_semantics
    ADD CONSTRAINT customer_text_semantics_pkey PRIMARY KEY (id);


--
-- Name: customer_text_signals customer_text_signals_pkey; Type: CONSTRAINT; Schema: public; Owner: mamina
--

ALTER TABLE ONLY public.customer_text_signals
    ADD CONSTRAINT customer_text_signals_pkey PRIMARY KEY (id);


--
-- Name: customers customers_pkey; Type: CONSTRAINT; Schema: public; Owner: mamina
--

ALTER TABLE ONLY public.customers
    ADD CONSTRAINT customers_pkey PRIMARY KEY (customer_id);


--
-- Name: embedding_model_registry embedding_model_registry_pkey; Type: CONSTRAINT; Schema: public; Owner: mamina
--

ALTER TABLE ONLY public.embedding_model_registry
    ADD CONSTRAINT embedding_model_registry_pkey PRIMARY KEY (id);


--
-- Name: feedback_features feedback_features_pkey; Type: CONSTRAINT; Schema: public; Owner: mamina
--

ALTER TABLE ONLY public.feedback_features
    ADD CONSTRAINT feedback_features_pkey PRIMARY KEY (feature_id);


--
-- Name: feedback_linked feedback_linked_pkey; Type: CONSTRAINT; Schema: public; Owner: mamina
--

ALTER TABLE ONLY public.feedback_linked
    ADD CONSTRAINT feedback_linked_pkey PRIMARY KEY (link_id);


--
-- Name: feedback_raw feedback_raw_pkey; Type: CONSTRAINT; Schema: public; Owner: mamina
--

ALTER TABLE ONLY public.feedback_raw
    ADD CONSTRAINT feedback_raw_pkey PRIMARY KEY (msg_id);


--
-- Name: ml_model_registry ml_model_registry_pkey; Type: CONSTRAINT; Schema: public; Owner: mamina
--

ALTER TABLE ONLY public.ml_model_registry
    ADD CONSTRAINT ml_model_registry_pkey PRIMARY KEY (id);


--
-- Name: model_versions model_versions_pkey; Type: CONSTRAINT; Schema: public; Owner: mamina
--

ALTER TABLE ONLY public.model_versions
    ADD CONSTRAINT model_versions_pkey PRIMARY KEY (model_version);


--
-- Name: recommendation_contexts recommendation_contexts_pkey; Type: CONSTRAINT; Schema: public; Owner: mamina
--

ALTER TABLE ONLY public.recommendation_contexts
    ADD CONSTRAINT recommendation_contexts_pkey PRIMARY KEY (context_id);


--
-- Name: recommendation_contexts recommendation_contexts_pred_id_key; Type: CONSTRAINT; Schema: public; Owner: mamina
--

ALTER TABLE ONLY public.recommendation_contexts
    ADD CONSTRAINT recommendation_contexts_pred_id_key UNIQUE (pred_id);


--
-- Name: shap_cache shap_cache_pkey; Type: CONSTRAINT; Schema: public; Owner: mamina
--

ALTER TABLE ONLY public.shap_cache
    ADD CONSTRAINT shap_cache_pkey PRIMARY KEY (pred_id);


--
-- Name: topics topics_pkey; Type: CONSTRAINT; Schema: public; Owner: mamina
--

ALTER TABLE ONLY public.topics
    ADD CONSTRAINT topics_pkey PRIMARY KEY (topic_id);


--
-- Name: transactions transactions_pkey; Type: CONSTRAINT; Schema: public; Owner: mamina
--

ALTER TABLE ONLY public.transactions
    ADD CONSTRAINT transactions_pkey PRIMARY KEY (tx_id);


--
-- Name: churn_labels uq_churn_label_customer_date; Type: CONSTRAINT; Schema: public; Owner: mamina
--

ALTER TABLE ONLY public.churn_labels
    ADD CONSTRAINT uq_churn_label_customer_date UNIQUE (customer_id, observation_date);


--
-- Name: customer_numeric_features uq_numeric_features_date; Type: CONSTRAINT; Schema: public; Owner: mamina
--

ALTER TABLE ONLY public.customer_numeric_features
    ADD CONSTRAINT uq_numeric_features_date UNIQUE (customer_id, as_of_date);


--
-- Name: customer_text_semantics uq_text_semantics_date; Type: CONSTRAINT; Schema: public; Owner: mamina
--

ALTER TABLE ONLY public.customer_text_semantics
    ADD CONSTRAINT uq_text_semantics_date UNIQUE (customer_id, as_of_date);


--
-- Name: customer_text_signals uq_text_signals_date; Type: CONSTRAINT; Schema: public; Owner: mamina
--

ALTER TABLE ONLY public.customer_text_signals
    ADD CONSTRAINT uq_text_signals_date UNIQUE (customer_id, as_of_date);


--
-- Name: topics uq_topic_idx_version; Type: CONSTRAINT; Schema: public; Owner: mamina
--

ALTER TABLE ONLY public.topics
    ADD CONSTRAINT uq_topic_idx_version UNIQUE (topic_idx, model_version);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: mamina
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (user_id);


--
-- Name: idx_action_assigned; Type: INDEX; Schema: public; Owner: mamina
--

CREATE INDEX idx_action_assigned ON public.actions USING btree (assigned_to);


--
-- Name: idx_action_due_date; Type: INDEX; Schema: public; Owner: mamina
--

CREATE INDEX idx_action_due_date ON public.actions USING btree (due_date);


--
-- Name: idx_action_priority; Type: INDEX; Schema: public; Owner: mamina
--

CREATE INDEX idx_action_priority ON public.actions USING btree (priority);


--
-- Name: idx_action_status; Type: INDEX; Schema: public; Owner: mamina
--

CREATE INDEX idx_action_status ON public.actions USING btree (status);


--
-- Name: idx_active_model; Type: INDEX; Schema: public; Owner: mamina
--

CREATE INDEX idx_active_model ON public.embedding_model_registry USING btree (is_active) WHERE (is_active = true);


--
-- Name: idx_churn_label_customer_obs; Type: INDEX; Schema: public; Owner: mamina
--

CREATE INDEX idx_churn_label_customer_obs ON public.churn_labels USING btree (customer_id, observation_date);


--
-- Name: idx_ml_active_model; Type: INDEX; Schema: public; Owner: mamina
--

CREATE INDEX idx_ml_active_model ON public.ml_model_registry USING btree (is_active) WHERE (is_active = true);


--
-- Name: idx_numeric_features_customer_date; Type: INDEX; Schema: public; Owner: mamina
--

CREATE INDEX idx_numeric_features_customer_date ON public.customer_numeric_features USING btree (customer_id, as_of_date);


--
-- Name: idx_pred_customer_date; Type: INDEX; Schema: public; Owner: mamina
--

CREATE INDEX idx_pred_customer_date ON public.churn_predictions USING btree (customer_id, as_of_date);


--
-- Name: idx_pred_feature_as_of; Type: INDEX; Schema: public; Owner: mamina
--

CREATE INDEX idx_pred_feature_as_of ON public.churn_predictions USING btree (feature_as_of);


--
-- Name: idx_pred_label; Type: INDEX; Schema: public; Owner: mamina
--

CREATE INDEX idx_pred_label ON public.churn_predictions USING btree (churn_label);


--
-- Name: idx_pred_score; Type: INDEX; Schema: public; Owner: mamina
--

CREATE INDEX idx_pred_score ON public.churn_predictions USING btree (churn_score);


--
-- Name: idx_recommendation_customer_date; Type: INDEX; Schema: public; Owner: mamina
--

CREATE INDEX idx_recommendation_customer_date ON public.recommendation_contexts USING btree (customer_id, as_of_date);


--
-- Name: idx_recommendation_review_status; Type: INDEX; Schema: public; Owner: mamina
--

CREATE INDEX idx_recommendation_review_status ON public.recommendation_contexts USING btree (review_status);


--
-- Name: idx_text_semantics_customer_date; Type: INDEX; Schema: public; Owner: mamina
--

CREATE INDEX idx_text_semantics_customer_date ON public.customer_text_semantics USING btree (customer_id, as_of_date);


--
-- Name: idx_text_signals_customer_date; Type: INDEX; Schema: public; Owner: mamina
--

CREATE INDEX idx_text_signals_customer_date ON public.customer_text_signals USING btree (customer_id, as_of_date);


--
-- Name: idx_tx_customer_date; Type: INDEX; Schema: public; Owner: mamina
--

CREATE INDEX idx_tx_customer_date ON public.transactions USING btree (customer_id, tx_date);


--
-- Name: ix_actions_customer_id; Type: INDEX; Schema: public; Owner: mamina
--

CREATE INDEX ix_actions_customer_id ON public.actions USING btree (customer_id);


--
-- Name: ix_actions_pred_id; Type: INDEX; Schema: public; Owner: mamina
--

CREATE INDEX ix_actions_pred_id ON public.actions USING btree (pred_id);


--
-- Name: ix_churn_labels_customer_id; Type: INDEX; Schema: public; Owner: mamina
--

CREATE INDEX ix_churn_labels_customer_id ON public.churn_labels USING btree (customer_id);


--
-- Name: ix_churn_labels_observation_date; Type: INDEX; Schema: public; Owner: mamina
--

CREATE INDEX ix_churn_labels_observation_date ON public.churn_labels USING btree (observation_date);


--
-- Name: ix_churn_predictions_as_of_date; Type: INDEX; Schema: public; Owner: mamina
--

CREATE INDEX ix_churn_predictions_as_of_date ON public.churn_predictions USING btree (as_of_date);


--
-- Name: ix_churn_predictions_customer_id; Type: INDEX; Schema: public; Owner: mamina
--

CREATE INDEX ix_churn_predictions_customer_id ON public.churn_predictions USING btree (customer_id);


--
-- Name: ix_customer_numeric_features_as_of_date; Type: INDEX; Schema: public; Owner: mamina
--

CREATE INDEX ix_customer_numeric_features_as_of_date ON public.customer_numeric_features USING btree (as_of_date);


--
-- Name: ix_customer_numeric_features_customer_id; Type: INDEX; Schema: public; Owner: mamina
--

CREATE INDEX ix_customer_numeric_features_customer_id ON public.customer_numeric_features USING btree (customer_id);


--
-- Name: ix_customer_text_semantics_as_of_date; Type: INDEX; Schema: public; Owner: mamina
--

CREATE INDEX ix_customer_text_semantics_as_of_date ON public.customer_text_semantics USING btree (as_of_date);


--
-- Name: ix_customer_text_semantics_customer_id; Type: INDEX; Schema: public; Owner: mamina
--

CREATE INDEX ix_customer_text_semantics_customer_id ON public.customer_text_semantics USING btree (customer_id);


--
-- Name: ix_customer_text_semantics_sentiment_model_version; Type: INDEX; Schema: public; Owner: mamina
--

CREATE INDEX ix_customer_text_semantics_sentiment_model_version ON public.customer_text_semantics USING btree (sentiment_model_version);


--
-- Name: ix_customer_text_semantics_topic_model_version; Type: INDEX; Schema: public; Owner: mamina
--

CREATE INDEX ix_customer_text_semantics_topic_model_version ON public.customer_text_semantics USING btree (topic_model_version);


--
-- Name: ix_customer_text_signals_as_of_date; Type: INDEX; Schema: public; Owner: mamina
--

CREATE INDEX ix_customer_text_signals_as_of_date ON public.customer_text_signals USING btree (as_of_date);


--
-- Name: ix_customer_text_signals_customer_id; Type: INDEX; Schema: public; Owner: mamina
--

CREATE INDEX ix_customer_text_signals_customer_id ON public.customer_text_signals USING btree (customer_id);


--
-- Name: ix_customers_external_id; Type: INDEX; Schema: public; Owner: mamina
--

CREATE UNIQUE INDEX ix_customers_external_id ON public.customers USING btree (external_id);


--
-- Name: ix_customers_is_provisional; Type: INDEX; Schema: public; Owner: mamina
--

CREATE INDEX ix_customers_is_provisional ON public.customers USING btree (is_provisional);


--
-- Name: ix_customers_phone_hash; Type: INDEX; Schema: public; Owner: mamina
--

CREATE UNIQUE INDEX ix_customers_phone_hash ON public.customers USING btree (phone_hash);


--
-- Name: ix_embedding_model_registry_is_active; Type: INDEX; Schema: public; Owner: mamina
--

CREATE INDEX ix_embedding_model_registry_is_active ON public.embedding_model_registry USING btree (is_active);


--
-- Name: ix_embedding_model_registry_model_hash; Type: INDEX; Schema: public; Owner: mamina
--

CREATE UNIQUE INDEX ix_embedding_model_registry_model_hash ON public.embedding_model_registry USING btree (model_hash);


--
-- Name: ix_feedback_features_customer_id; Type: INDEX; Schema: public; Owner: mamina
--

CREATE INDEX ix_feedback_features_customer_id ON public.feedback_features USING btree (customer_id);


--
-- Name: ix_feedback_features_embedding_model_version; Type: INDEX; Schema: public; Owner: mamina
--

CREATE INDEX ix_feedback_features_embedding_model_version ON public.feedback_features USING btree (embedding_model_version);


--
-- Name: ix_feedback_features_link_id; Type: INDEX; Schema: public; Owner: mamina
--

CREATE UNIQUE INDEX ix_feedback_features_link_id ON public.feedback_features USING btree (link_id);


--
-- Name: ix_feedback_features_msg_id; Type: INDEX; Schema: public; Owner: mamina
--

CREATE UNIQUE INDEX ix_feedback_features_msg_id ON public.feedback_features USING btree (msg_id);


--
-- Name: ix_feedback_features_sentiment_label; Type: INDEX; Schema: public; Owner: mamina
--

CREATE INDEX ix_feedback_features_sentiment_label ON public.feedback_features USING btree (sentiment_label);


--
-- Name: ix_feedback_features_sentiment_model_version; Type: INDEX; Schema: public; Owner: mamina
--

CREATE INDEX ix_feedback_features_sentiment_model_version ON public.feedback_features USING btree (sentiment_model_version);


--
-- Name: ix_feedback_linked_customer_id; Type: INDEX; Schema: public; Owner: mamina
--

CREATE INDEX ix_feedback_linked_customer_id ON public.feedback_linked USING btree (customer_id);


--
-- Name: ix_feedback_linked_link_status; Type: INDEX; Schema: public; Owner: mamina
--

CREATE INDEX ix_feedback_linked_link_status ON public.feedback_linked USING btree (link_status);


--
-- Name: ix_feedback_linked_msg_id; Type: INDEX; Schema: public; Owner: mamina
--

CREATE UNIQUE INDEX ix_feedback_linked_msg_id ON public.feedback_linked USING btree (msg_id);


--
-- Name: ix_feedback_raw_phone_number; Type: INDEX; Schema: public; Owner: mamina
--

CREATE INDEX ix_feedback_raw_phone_number ON public.feedback_raw USING btree (phone_number);


--
-- Name: ix_feedback_raw_timestamp; Type: INDEX; Schema: public; Owner: mamina
--

CREATE INDEX ix_feedback_raw_timestamp ON public.feedback_raw USING btree ("timestamp");


--
-- Name: ix_ml_model_registry_is_active; Type: INDEX; Schema: public; Owner: mamina
--

CREATE INDEX ix_ml_model_registry_is_active ON public.ml_model_registry USING btree (is_active);


--
-- Name: ix_ml_model_registry_model_hash; Type: INDEX; Schema: public; Owner: mamina
--

CREATE UNIQUE INDEX ix_ml_model_registry_model_hash ON public.ml_model_registry USING btree (model_hash);


--
-- Name: ix_recommendation_contexts_as_of_date; Type: INDEX; Schema: public; Owner: mamina
--

CREATE INDEX ix_recommendation_contexts_as_of_date ON public.recommendation_contexts USING btree (as_of_date);


--
-- Name: ix_recommendation_contexts_customer_id; Type: INDEX; Schema: public; Owner: mamina
--

CREATE INDEX ix_recommendation_contexts_customer_id ON public.recommendation_contexts USING btree (customer_id);


--
-- Name: ix_recommendation_contexts_pred_id; Type: INDEX; Schema: public; Owner: mamina
--

CREATE INDEX ix_recommendation_contexts_pred_id ON public.recommendation_contexts USING btree (pred_id);


--
-- Name: ix_topics_model_version; Type: INDEX; Schema: public; Owner: mamina
--

CREATE INDEX ix_topics_model_version ON public.topics USING btree (model_version);


--
-- Name: ix_topics_topic_idx; Type: INDEX; Schema: public; Owner: mamina
--

CREATE INDEX ix_topics_topic_idx ON public.topics USING btree (topic_idx);


--
-- Name: ix_transactions_customer_id; Type: INDEX; Schema: public; Owner: mamina
--

CREATE INDEX ix_transactions_customer_id ON public.transactions USING btree (customer_id);


--
-- Name: ix_transactions_tx_date; Type: INDEX; Schema: public; Owner: mamina
--

CREATE INDEX ix_transactions_tx_date ON public.transactions USING btree (tx_date);


--
-- Name: ix_users_email; Type: INDEX; Schema: public; Owner: mamina
--

CREATE UNIQUE INDEX ix_users_email ON public.users USING btree (email);


--
-- Name: ix_users_username; Type: INDEX; Schema: public; Owner: mamina
--

CREATE UNIQUE INDEX ix_users_username ON public.users USING btree (username);


--
-- Name: feedback_features trg_validate_feature_customer_id; Type: TRIGGER; Schema: public; Owner: mamina
--

CREATE TRIGGER trg_validate_feature_customer_id BEFORE INSERT OR UPDATE ON public.feedback_features FOR EACH ROW EXECUTE FUNCTION public.validate_feature_customer_id();


--
-- Name: actions actions_customer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: mamina
--

ALTER TABLE ONLY public.actions
    ADD CONSTRAINT actions_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES public.customers(customer_id) ON DELETE CASCADE;


--
-- Name: actions actions_pred_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: mamina
--

ALTER TABLE ONLY public.actions
    ADD CONSTRAINT actions_pred_id_fkey FOREIGN KEY (pred_id) REFERENCES public.churn_predictions(pred_id) ON DELETE SET NULL;


--
-- Name: churn_labels churn_labels_customer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: mamina
--

ALTER TABLE ONLY public.churn_labels
    ADD CONSTRAINT churn_labels_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES public.customers(customer_id) ON DELETE CASCADE;


--
-- Name: churn_predictions churn_predictions_customer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: mamina
--

ALTER TABLE ONLY public.churn_predictions
    ADD CONSTRAINT churn_predictions_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES public.customers(customer_id) ON DELETE CASCADE;


--
-- Name: customer_numeric_features customer_numeric_features_customer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: mamina
--

ALTER TABLE ONLY public.customer_numeric_features
    ADD CONSTRAINT customer_numeric_features_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES public.customers(customer_id) ON DELETE CASCADE;


--
-- Name: customer_text_semantics customer_text_semantics_customer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: mamina
--

ALTER TABLE ONLY public.customer_text_semantics
    ADD CONSTRAINT customer_text_semantics_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES public.customers(customer_id) ON DELETE CASCADE;


--
-- Name: customer_text_signals customer_text_signals_customer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: mamina
--

ALTER TABLE ONLY public.customer_text_signals
    ADD CONSTRAINT customer_text_signals_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES public.customers(customer_id) ON DELETE CASCADE;


--
-- Name: feedback_features feedback_features_customer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: mamina
--

ALTER TABLE ONLY public.feedback_features
    ADD CONSTRAINT feedback_features_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES public.customers(customer_id) ON DELETE CASCADE;


--
-- Name: feedback_features feedback_features_link_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: mamina
--

ALTER TABLE ONLY public.feedback_features
    ADD CONSTRAINT feedback_features_link_id_fkey FOREIGN KEY (link_id) REFERENCES public.feedback_linked(link_id) ON DELETE CASCADE;


--
-- Name: feedback_features feedback_features_msg_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: mamina
--

ALTER TABLE ONLY public.feedback_features
    ADD CONSTRAINT feedback_features_msg_id_fkey FOREIGN KEY (msg_id) REFERENCES public.feedback_raw(msg_id) ON DELETE CASCADE;


--
-- Name: feedback_linked feedback_linked_customer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: mamina
--

ALTER TABLE ONLY public.feedback_linked
    ADD CONSTRAINT feedback_linked_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES public.customers(customer_id) ON DELETE CASCADE;


--
-- Name: feedback_linked feedback_linked_msg_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: mamina
--

ALTER TABLE ONLY public.feedback_linked
    ADD CONSTRAINT feedback_linked_msg_id_fkey FOREIGN KEY (msg_id) REFERENCES public.feedback_raw(msg_id) ON DELETE CASCADE;


--
-- Name: recommendation_contexts recommendation_contexts_customer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: mamina
--

ALTER TABLE ONLY public.recommendation_contexts
    ADD CONSTRAINT recommendation_contexts_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES public.customers(customer_id) ON DELETE CASCADE;


--
-- Name: recommendation_contexts recommendation_contexts_pred_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: mamina
--

ALTER TABLE ONLY public.recommendation_contexts
    ADD CONSTRAINT recommendation_contexts_pred_id_fkey FOREIGN KEY (pred_id) REFERENCES public.churn_predictions(pred_id) ON DELETE CASCADE;


--
-- Name: shap_cache shap_cache_pred_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: mamina
--

ALTER TABLE ONLY public.shap_cache
    ADD CONSTRAINT shap_cache_pred_id_fkey FOREIGN KEY (pred_id) REFERENCES public.churn_predictions(pred_id) ON DELETE CASCADE;


--
-- Name: transactions transactions_customer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: mamina
--

ALTER TABLE ONLY public.transactions
    ADD CONSTRAINT transactions_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES public.customers(customer_id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict MMI9WebUUtJgtpJRdOuUsy2HSEH3rtnW1bK7tCHJKotj5hNJcEPI4O7F61QeiYC

