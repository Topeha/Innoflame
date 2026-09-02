CREATE TABLE companies (
    company_key BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    business_id VARCHAR(20) NOT NULL UNIQUE,
    profinder_id VARCHAR(50),
    company_name VARCHAR(255) NOT NULL,
    marketing_name VARCHAR(255),
    legal_name VARCHAR(255),
    parent_business_id VARCHAR(20),
    parent_profinder_id VARCHAR(50),
    operating_site_type VARCHAR(100),
    country VARCHAR(100),
    address_line1 VARCHAR(255),
    address_line2 VARCHAR(255),
    postal_code VARCHAR(20),
    city VARCHAR(100),
    municipality VARCHAR(100),
    region VARCHAR(100),
    full_address VARCHAR(500),
    industry_primary VARCHAR(255),
    industry_secondary VARCHAR(500),
    industry_code VARCHAR(50),
    service_category VARCHAR(255),
    business_description TEXT,
    founded_year INTEGER,
    employee_count INTEGER,
    employee_class VARCHAR(100),
    revenue_eur NUMERIC(18,2),
    revenue_class VARCHAR(100),
    growth_class VARCHAR(100),
    risk_class VARCHAR(100),
    mobility_class VARCHAR(100),
    source_file VARCHAR(255),
    source_version VARCHAR(100),
    source_updated_at TIMESTAMP NULL,
    source_notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_companies_industry_primary ON companies (industry_primary);
CREATE INDEX idx_companies_city ON companies (city);
CREATE INDEX idx_companies_region ON companies (region);

CREATE TABLE company_contacts (
    contact_key BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    business_id VARCHAR(20) NOT NULL,
    profinder_id VARCHAR(50),
    contact_name VARCHAR(255),
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    title VARCHAR(255),
    job_title VARCHAR(255),
    responsibility_area VARCHAR(255),
    phone VARCHAR(100),
    decision_maker_phone VARCHAR(100),
    email VARCHAR(255),
    decision_maker_email VARCHAR(255),
    contact_person_id VARCHAR(100),
    source_file VARCHAR(255),
    source_updated_at TIMESTAMP NULL,
    is_decision_maker BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_company_contacts_company
        FOREIGN KEY (business_id) REFERENCES companies (business_id)
);

CREATE INDEX idx_company_contacts_business_id ON company_contacts (business_id);
CREATE INDEX idx_company_contacts_email ON company_contacts (email);

CREATE TABLE company_financials (
    financial_key BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    business_id VARCHAR(20) NOT NULL,
    reporting_period VARCHAR(20),
    revenue_eur NUMERIC(18,2),
    revenue_change_pct NUMERIC(10,4),
    operating_profit_pct NUMERIC(10,4),
    ebitda_pct NUMERIC(10,4),
    employee_count INTEGER,
    employee_change_pct NUMERIC(10,4),
    quick_ratio NUMERIC(10,4),
    current_ratio NUMERIC(10,4),
    equity_ratio NUMERIC(10,4),
    return_on_capital_pct NUMERIC(10,4),
    equity_eur NUMERIC(18,2),
    balance_sheet_total_eur NUMERIC(18,2),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_company_financials_company
        FOREIGN KEY (business_id) REFERENCES companies (business_id)
);

CREATE INDEX idx_company_financials_business_id ON company_financials (business_id);

CREATE TABLE prospect_scores (
    score_key BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id VARCHAR(100) NOT NULL,
    business_id VARCHAR(20) NOT NULL,
    score NUMERIC(12,8) NOT NULL,
    potential_band VARCHAR(50),
    priority_rank INTEGER,
    estimated_potential_eur NUMERIC(18,2),
    segment VARCHAR(50),
    revenue_class VARCHAR(100),
    headcount_class VARCHAR(100),
    industry VARCHAR(255),
    location VARCHAR(255),
    company_name VARCHAR(255),
    contact_name VARCHAR(255),
    title VARCHAR(255),
    phone VARCHAR(100),
    email VARCHAR(255),
    positive_signals TEXT,
    presentation_status VARCHAR(50),
    presentation_notes TEXT,
    model_name VARCHAR(255),
    model_version VARCHAR(100),
    scored_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_prospect_scores_company
        FOREIGN KEY (business_id) REFERENCES companies (business_id)
);

CREATE INDEX idx_prospect_scores_run_id ON prospect_scores (run_id);
CREATE INDEX idx_prospect_scores_business_id ON prospect_scores (business_id);
CREATE INDEX idx_prospect_scores_score ON prospect_scores (score);
