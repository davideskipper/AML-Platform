"""
AML IntelliGent Platform — KYC/CDD Agent
=========================================
A real Claude-powered agent that processes KYC cases using tool use.
Each tool represents a specialised sub-agent (Registry, UBO/PEP, Transaction, etc.).
The Super Agent (claude-opus-4-6) orchestrates analysis and produces an Opinion Report.

Usage:
    pip install anthropic
    export ANTHROPIC_API_KEY="sk-..."
    python kyc_agent.py
"""

import anthropic
import json
import os
import sys
from datetime import datetime

# ──────────────────────────────────────────────
# SAMPLE CASE: Meridian Capital S.r.l.
# (matches the data already in the dashboard)
# ──────────────────────────────────────────────
SAMPLE_CASE = {
    "case_id": "AV-2026-0341",
    "company_name": "Meridian Capital S.r.l.",
    "entity_type": "Legal entity — S.r.l.",
    "tax_id": "IT 04821930215",
    "registered_office": "Milan, Lombardy (IT)",
    "sector": "Wealth Management / Investment Advisory",
    "relationship_start": "March 2018",
    "review_type": "Customer Due Diligence (CDD) — New risk trigger",
    "declared_turnover_eur": 14_200_000,
    "share_capital_eur": 500_000,
    "shareholders": [
        {"name": "Alessandro Greco", "stake_pct": 70, "nationality": "IT"},
        {"name": "Karim Al-Rashid", "stake_pct": 30, "nationality": "AE",
         "notes": "Entry Feb 2026 — former public official MENA"},
    ],
}

# ──────────────────────────────────────────────
# TOOL IMPLEMENTATIONS
# Each function simulates a specialized sub-agent
# calling external data sources.
# ──────────────────────────────────────────────

def registry_lookup(company_name: str, tax_id: str) -> dict:
    """Registry Agent — corporate registry & Orbis data."""
    return {
        "agent": "Registry Agent",
        "source": "Registro Imprese / Orbis",
        "legal_name": company_name,
        "legal_form": "S.r.l. — Società a responsabilità limitata",
        "tax_id": tax_id,
        "registration_number": "MI-2312847",
        "registration_date": "2007-03-14",
        "registered_office": "Via Montenapoleone 12, Milan (IT)",
        "share_capital_eur": 500_000,
        "status": "Active",
        "recent_corporate_changes": [
            "Feb 2026: new shareholder Karim Al-Rashid (30% stake)",
            "Feb 2026: registered office change within Milan",
        ],
        "subsidiaries": [
            {"name": "Meridian RE S.r.l.", "country": "IT", "ownership_pct": 75},
            {"name": "MC Asset Mgmt SA", "country": "LU", "ownership_pct": 100},
        ],
        "insolvency_proceedings": "None identified",
        "judicial_measures": "None identified",
    }


def ubo_pep_screening(shareholders: list) -> dict:
    """UBO/PEP Agent — World-Check, Dow Jones, Refinitiv, OFAC, EU Sanctions."""
    return {
        "agent": "UBO/PEP Agent",
        "sources": ["World-Check", "Dow Jones Risk & Compliance", "Refinitiv", "OFAC SDN", "EU Consolidated List"],
        "ubos": [
            {
                "name": "Alessandro Greco",
                "stake_pct": 70,
                "nationality": "IT",
                "pep_status": "Not PEP",
                "sanctions": "None",
                "adverse_findings": "None",
            },
            {
                "name": "Karim Al-Rashid",
                "stake_pct": 30,
                "nationality": "AE",
                "pep_status": "PEP Tier 1 — former Minister of Finance (MENA jurisdiction)",
                "sanctions": "None active — OFAC: clear, EU: clear, UN SC: clear",
                "rca_screening": "Spouse and 2 business associates identified — no adverse findings",
                "notes": "Entry Feb 2026. Senior Management approval required per AML policy.",
            },
        ],
        "bearer_shares": "None",
        "nominees": "None identified",
        "cdd_documents_status": "Outdated — last update 2021, refresh required",
    }


def transaction_analysis(company_name: str, period_months: int) -> dict:
    """Transaction Agent — AML pattern analysis across 47 transactions."""
    return {
        "agent": "Transaction Agent",
        "analysis_period": f"Jan 2025 – Feb 2026 ({period_months} months)",
        "total_transactions": 47,
        "total_inbound_eur": 8_400_000,
        "yoy_volume_change_pct": 340,
        "avg_transaction_eur": 178_723,
        "largest_transaction_eur": 1_200_000,
        "largest_transaction_counterparty": "Falcon Holdings FZE (UAE)",
        "high_risk_jurisdiction_pct": 68,
        "flagged_counterparties": ["Falcon Holdings FZE (UAE)", "Gulf Invest Partners (UAE)"],
        "tm_alerts": [
            {
                "type": "Structuring",
                "description": "8 transactions just below €10,000 threshold over 45 days",
                "severity": "HIGH",
            },
            {
                "type": "Round-tripping",
                "description": "€470,000 outflow to Malta + equivalent inflow after 12 days",
                "severity": "HIGH",
            },
            {
                "type": "Unidentified beneficial counterparty",
                "description": "6 transactions with counterparties whose UBO chain is not fully traceable",
                "severity": "MEDIUM",
            },
        ],
        "prior_sars": "None on this client",
        "cash_equivalent_flows": "None detected",
        "edd_required": True,
    }


def reputational_scan(company_name: str, shareholders: list) -> dict:
    """Reputational Agent — adverse media, CONSOB, Banca d'Italia."""
    return {
        "agent": "Reputational Agent",
        "sources": ["Factiva", "LexisNexis", "CONSOB", "Banca d'Italia"],
        "company_adverse_media": "None significant — 2024 positive press on AUM growth",
        "shareholder_findings": [
            {
                "name": "Alessandro Greco",
                "adverse_media": "None",
                "regulatory_actions": "None",
            },
            {
                "name": "Karim Al-Rashid",
                "adverse_media": "2019 ministerial inquiry — concluded without charges",
                "regulatory_actions": "None",
            },
        ],
        "consob_measures": "None",
        "banca_italia_actions": "None",
        "adverse_media_score": "2 / 10 — Low",
        "watchlists": "Not present on any watchlist",
    }


def economic_assessment(company_name: str, declared_turnover_eur: float,
                        transaction_volume_eur: float) -> dict:
    """Economic Assessment Agent — risk profile consistency vs. financials."""
    ratio = transaction_volume_eur / declared_turnover_eur
    consistent = ratio <= 0.70  # heuristic: flows should not exceed 70% of turnover
    return {
        "agent": "Economic Assessment Agent",
        "declared_turnover_eur": declared_turnover_eur,
        "observed_transaction_volume_eur": transaction_volume_eur,
        "turnover_flow_ratio": round(ratio, 2),
        "consistency": "Partially consistent" if not consistent else "Consistent",
        "notes": (
            "Transaction volume exceeds expected profile for a wealth management advisory firm "
            "of this size. Updated corporate documents (2026 articles of association, "
            "shareholder deed) not found in internal repository or open sources."
        ),
        "documents_missing": [
            "2026 Articles of Association",
            "Updated Shareholder Deed",
            "Source of wealth declaration — Karim Al-Rashid",
            "Source of funds for €2.1M acquisition (Falcon Holdings FZE wire)",
        ],
        "preliminary_risk_proposal": "Very High",
        "user_input_required": True,
    }


def document_validation(company_name: str) -> dict:
    """Document Agent — KYC documentation completeness & expiry."""
    return {
        "agent": "Document Agent",
        "kyc_pack_status": "Incomplete",
        "documents_present": [
            {"doc": "Certificate of Incorporation", "expiry": "N/A", "status": "Valid"},
            {"doc": "ID — Alessandro Greco", "expiry": "2027-06", "status": "Valid"},
            {"doc": "Previous CDD form", "expiry": "2021-03", "status": "EXPIRED"},
        ],
        "documents_missing": [
            "ID — Karim Al-Rashid (new shareholder — not yet provided)",
            "Source of Wealth declaration — Karim Al-Rashid",
            "Updated CDD form (current one expired Mar 2021)",
            "2026 Articles of Association",
            "Senior Management approval form (PEP Tier 1)",
        ],
        "edd_checklist_complete": False,
    }


def geographic_risk(counterparty_countries: list) -> dict:
    """Geographic Agent — jurisdiction risk vs. FATF lists."""
    risk_map = {
        "AE": {"country": "United Arab Emirates", "fatf_status": "Grey list — Enhanced monitoring", "risk": "HIGH"},
        "MT": {"country": "Malta", "fatf_status": "Removed from grey list 2022", "risk": "MEDIUM"},
        "LU": {"country": "Luxembourg", "fatf_status": "FATF member — standard monitoring", "risk": "LOW"},
        "IT": {"country": "Italy", "fatf_status": "FATF member — standard monitoring", "risk": "LOW"},
        "CY": {"country": "Cyprus", "fatf_status": "EU member — standard", "risk": "MEDIUM"},
    }
    assessed = {c: risk_map.get(c, {"country": c, "fatf_status": "Unknown", "risk": "MEDIUM"})
                for c in counterparty_countries}
    high_risk_countries = [c for c, v in assessed.items() if v["risk"] == "HIGH"]
    return {
        "agent": "Geographic Agent",
        "assessed_jurisdictions": assessed,
        "high_risk_country_codes": high_risk_countries,
        "recommendation": (
            "Enhanced Due Diligence required for flows to/from AE. "
            "Correspondent bank confirmations needed for Malta flows."
        ),
    }


# ──────────────────────────────────────────────
# TOOL DISPATCH
# ──────────────────────────────────────────────

TOOL_FUNCTIONS = {
    "registry_lookup": lambda inp: registry_lookup(
        inp["company_name"], inp["tax_id"]
    ),
    "ubo_pep_screening": lambda inp: ubo_pep_screening(
        inp["shareholders"]
    ),
    "transaction_analysis": lambda inp: transaction_analysis(
        inp["company_name"], inp.get("period_months", 14)
    ),
    "reputational_scan": lambda inp: reputational_scan(
        inp["company_name"], inp.get("shareholders", [])
    ),
    "economic_assessment": lambda inp: economic_assessment(
        inp["company_name"],
        inp["declared_turnover_eur"],
        inp["transaction_volume_eur"],
    ),
    "document_validation": lambda inp: document_validation(
        inp["company_name"]
    ),
    "geographic_risk": lambda inp: geographic_risk(
        inp["counterparty_countries"]
    ),
}

# ──────────────────────────────────────────────
# TOOL DEFINITIONS (Claude API schema)
# ──────────────────────────────────────────────

TOOLS = [
    {
        "name": "registry_lookup",
        "description": (
            "Registry Agent: retrieves corporate registry data, ownership structure, "
            "subsidiaries, and recent corporate changes from Registro Imprese and Orbis."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "company_name": {"type": "string", "description": "Legal name of the entity"},
                "tax_id": {"type": "string", "description": "Tax ID / VAT number"},
            },
            "required": ["company_name", "tax_id"],
        },
    },
    {
        "name": "ubo_pep_screening",
        "description": (
            "UBO/PEP Agent: screens beneficial owners and shareholders against PEP lists "
            "(World-Check, Dow Jones, Refinitiv) and sanctions lists (OFAC SDN, EU Consolidated, UN SC)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "shareholders": {
                    "type": "array",
                    "description": "List of shareholder objects with name, stake_pct, nationality",
                    "items": {"type": "object"},
                },
            },
            "required": ["shareholders"],
        },
    },
    {
        "name": "transaction_analysis",
        "description": (
            "Transaction Agent: analyses transaction flows for AML patterns including "
            "structuring, round-tripping, layering, and unidentified counterparties. "
            "Generates TM alerts and flags high-risk jurisdiction exposure."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "company_name": {"type": "string"},
                "period_months": {"type": "integer", "description": "Analysis window in months", "default": 14},
            },
            "required": ["company_name"],
        },
    },
    {
        "name": "reputational_scan",
        "description": (
            "Reputational Agent: searches adverse media (Factiva, LexisNexis), "
            "regulatory databases (CONSOB, Banca d'Italia) and watchlists."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "company_name": {"type": "string"},
                "shareholders": {"type": "array", "items": {"type": "object"}},
            },
            "required": ["company_name"],
        },
    },
    {
        "name": "economic_assessment",
        "description": (
            "Economic Assessment Agent: compares declared turnover with observed transaction "
            "volume to assess consistency, flags discrepancies, and identifies missing documents."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "company_name": {"type": "string"},
                "declared_turnover_eur": {"type": "number", "description": "Declared annual turnover in EUR"},
                "transaction_volume_eur": {"type": "number", "description": "Observed transaction volume in EUR"},
            },
            "required": ["company_name", "declared_turnover_eur", "transaction_volume_eur"],
        },
    },
    {
        "name": "document_validation",
        "description": (
            "Document Agent: checks KYC documentation completeness, expiry dates, "
            "and EDD checklist compliance."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "company_name": {"type": "string"},
            },
            "required": ["company_name"],
        },
    },
    {
        "name": "geographic_risk",
        "description": (
            "Geographic Agent: maps counterparty jurisdictions against FATF lists, "
            "EU/UN sanctions regimes, and national risk assessments."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "counterparty_countries": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "ISO-2 country codes of counterparty jurisdictions",
                },
            },
            "required": ["counterparty_countries"],
        },
    },
]

# ──────────────────────────────────────────────
# SYSTEM PROMPT — Super Agent / Orchestrator
# ──────────────────────────────────────────────

SYSTEM_PROMPT = """You are the **Super Agent** of the AML IntelliGent Platform, an AI orchestrator \
for KYC/CDD (Know Your Customer / Customer Due Diligence) analysis in compliance with \
EU AML Directives (AMLD5/AMLD6), Italian Legislative Decree 231/2007, and FATF Recommendations.

Your role is to:
1. Orchestrate the 7 specialised sub-agents (tools) to gather all relevant data
2. Analyse the collected evidence holistically
3. Produce a structured, actionable **KYC Opinion Report**

**Analysis sequence** (follow this order):
1. Registry Agent — corporate structure
2. UBO/PEP Agent — beneficial owners & PEP screening
3. Transaction Agent — transaction flow analysis
4. Reputational Agent — adverse media & watchlists
5. Economic Assessment Agent — economic profile consistency
6. Document Agent — document completeness
7. Geographic Agent — jurisdiction risk (use country codes from transaction data)

**Opinion Report structure** (output after all tools have run):
- Section 1: Registry & corporate structure
- Section 2: UBO/PEP findings
- Section 3: Transaction flow analysis
- Section 4: TM alerts & AML red flags
- Section 5: PEP/sanctions screening
- Section 6: Reputational findings
- Section 7: Risk assessment & scoring (0–100)
- Section 8: EDD triggers & enhanced monitoring
- Section 9: Economic assessment & document gaps
- Section 10: Final recommendation & next steps

Use precise regulatory language. Flag items requiring Senior Management approval. \
Assign a risk score 0–100 and classify as: Low (<30), Medium (30–59), High (60–79), Very High (≥80).
"""

# ──────────────────────────────────────────────
# AGENTIC LOOP
# ──────────────────────────────────────────────

def run_kyc_agent(case: dict) -> str:
    """
    Run the KYC Super Agent on the given case.
    Returns the final Opinion Report as a string.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY environment variable not set.", file=sys.stderr)
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    user_message = f"""Please perform a full KYC/CDD analysis for the following case:

**Case ID:** {case['case_id']}
**Company:** {case['company_name']}
**Entity type:** {case['entity_type']}
**Tax ID:** {case['tax_id']}
**Registered office:** {case['registered_office']}
**Sector:** {case['sector']}
**Review type:** {case['review_type']}
**Declared turnover:** €{case['declared_turnover_eur']:,.0f}
**Share capital:** €{case['share_capital_eur']:,.0f}
**Shareholders:** {json.dumps(case['shareholders'], indent=2)}

Run all specialised agents in sequence, then produce the complete Opinion Report."""

    messages = [{"role": "user", "content": user_message}]

    print(f"\n{'='*60}")
    print(f"  AML IntelliGent Platform — KYC Agent")
    print(f"  Case: {case['case_id']} — {case['company_name']}")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    iteration = 0
    while True:
        iteration += 1
        print(f"[Super Agent] API call #{iteration}...")

        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=16000,
            thinking={"type": "adaptive"},
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        # Collect all tool calls in this turn
        tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
        text_blocks = [b for b in response.content if b.type == "text"]

        # Print any thinking summaries (adaptive thinking may produce these)
        for block in response.content:
            if block.type == "thinking" and hasattr(block, "thinking"):
                print(f"  [thinking] {block.thinking[:120]}...")

        # Print text output (intermediate or final)
        for block in text_blocks:
            if block.text.strip():
                print(f"\n[Super Agent] {block.text[:200]}{'...' if len(block.text) > 200 else ''}")

        # If done, return the final report
        if response.stop_reason == "end_turn":
            final_text = "\n".join(b.text for b in text_blocks if b.text.strip())
            return final_text

        # Execute tool calls
        if not tool_use_blocks:
            # No tools and not end_turn — shouldn't happen, but break to avoid infinite loop
            break

        # Append assistant response
        messages.append({"role": "assistant", "content": response.content})

        # Execute each tool and collect results
        tool_results = []
        for tool_block in tool_use_blocks:
            tool_name = tool_block.name
            tool_input = tool_block.input

            print(f"\n  ▶ [{tool_name}] called with: {json.dumps(tool_input, ensure_ascii=False)[:120]}")

            fn = TOOL_FUNCTIONS.get(tool_name)
            if fn:
                try:
                    result = fn(tool_input)
                    result_str = json.dumps(result, ensure_ascii=False, indent=2)
                    print(f"  ✓ [{tool_name}] completed — {len(result_str)} chars")
                except Exception as e:
                    result_str = json.dumps({"error": str(e)})
                    print(f"  ✗ [{tool_name}] ERROR: {e}")
            else:
                result_str = json.dumps({"error": f"Unknown tool: {tool_name}"})

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_block.id,
                "content": result_str,
            })

        # Append tool results as user message
        messages.append({"role": "user", "content": tool_results})

    return "[Agent loop ended without final report]"


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────

if __name__ == "__main__":
    report = run_kyc_agent(SAMPLE_CASE)

    print(f"\n{'='*60}")
    print("  FINAL KYC OPINION REPORT")
    print(f"{'='*60}\n")
    print(report)

    # Save to file
    output_path = f"opinion_{SAMPLE_CASE['case_id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"KYC Opinion Report — {SAMPLE_CASE['case_id']}\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n")
        f.write("=" * 60 + "\n\n")
        f.write(report)
    print(f"\n[Saved to {output_path}]")
