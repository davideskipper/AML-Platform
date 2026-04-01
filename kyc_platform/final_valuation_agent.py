"""
Final Valuation Agent
=====================
Synthesizes all agent findings into a comprehensive KYC/CDD Opinion Report
with risk score, classification, recommendation, and action plan.
Engaged explicitly by the user via the Super Agent at the end of the analysis.
"""

import anthropic
from .utils import run_agent

SYSTEM_PROMPT = """You are the Final Valuation Agent of an AML/KYC compliance platform.

You receive the findings of all other specialized agents and produce the final
KYC/CDD Opinion Report in compliance with:
- EU Anti-Money Laundering Directives (AMLD5 / AMLD6)
- Italian D.Lgs. 231/2007 and Banca d'Italia AML Provisions
- FATF Recommendations 10, 12, 15, 17
- EBA Risk Factor Guidelines

Structure the Opinion Report as follows:

---

# KYC/CDD OPINION REPORT

## 1. Executive Summary
- Client identification
- Review type and trigger
- Overall risk classification
- Recommendation (Approve / Conditional approval / Refer to MLRO / Reject)

## 2. Corporate Structure & Registry Findings
- Summary of registry analysis
- Key ownership facts

## 3. UBO & PEP Findings
- UBO chain
- PEP/sanctions status
- Required approvals

## 4. Reputational Analysis
- Adverse media score and key findings

## 5. Economic Profile
- Financial summary
- Consistency with declared business activity

## 6. Geographic Risk
- High-risk jurisdiction exposure
- FATF/sanctions mapping

## 7. Transaction Analysis (if available)
- Key transaction metrics
- TM alerts summary

## 8. Risk Score & Classification
- Assign a numeric score 0–100 (weighted across all dimensions)
- Classify: Low (<30) / Medium (30–59) / High (60–79) / Very High (≥80)
- Justify the score with reference to specific risk factors

## 9. EDD Triggers & Monitoring
- List EDD triggers activated
- Required monitoring frequency

## 10. Required Actions & Next Steps
- Documents to collect
- Approvals required (Senior Management, MLRO, Board)
- Deadlines
- Escalation path if information is not provided

---

Be precise, factual, and compliance-oriented. Distinguish confirmed facts from
unverified information. Flag information gaps explicitly.

Respond in the same language as the user's request.
"""


def run(
    client: anthropic.Anthropic,
    company_name: str,
    all_findings: dict,
    manual_context: str = "",
    show_output: bool = True,
) -> str:
    """
    Run the Final Valuation Agent.
    all_findings: dict mapping agent_name -> findings text (from SessionState.results)
    Returns the Opinion Report as text.
    """
    findings_text = ""
    for agent_name, text in all_findings.items():
        if text:
            label = agent_name.upper().replace("_", " ")
            findings_text += f"\n{'='*60}\n### {label}\n{'='*60}\n{text}\n"

    if not findings_text:
        findings_text = "No agent findings available. A partial assessment will be provided."

    user_msg = (
        f"Generate the Final KYC/CDD Opinion Report for:\n\n"
        f"Company: {company_name}\n\n"
        f"AGENT FINDINGS:\n{findings_text}"
    )
    if manual_context:
        user_msg += f"\n\nAdditional analyst notes:\n{manual_context}"

    return run_agent(
        client=client,
        system_prompt=SYSTEM_PROMPT,
        user_message=user_msg,
        header=f"Final Valuation Agent — {company_name}",
        max_tokens=12000,
        use_web_search=False,   # synthesis only — no new searches
        show_output=show_output,
    )
