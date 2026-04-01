"""
Risk Countries Agent
====================
Maps the company's geographic exposure against FATF grey/black lists,
EU/UN/OFAC sanctions regimes, and national AML risk assessments.
Produces a country-risk heat map and overall geographic risk rating.
"""

import anthropic
from .utils import run_agent

SYSTEM_PROMPT = """You are the Risk Countries Agent of an AML/KYC compliance platform.

Your task is to assess the geographic risk exposure of a company based on:
- Countries of incorporation, operations, and subsidiaries
- Counterparty jurisdictions (from transactions or business relationships)
- Shareholder and UBO nationalities/residences

Map each country against:

1. **FATF lists** (Financial Action Task Force)
   - Black list (High-Risk Jurisdictions subject to a Call for Action)
   - Grey list (Jurisdictions under Increased Monitoring)
   - Non-grey list FATF members (standard monitoring)

2. **EU High-Risk Third Countries** (Art. 9 AMLD4/5/6)

3. **Sanctions regimes**
   - UN Security Council comprehensive sanctions
   - EU country-specific restrictive measures
   - OFAC country/territory sanctions (SDN + OFAC country programs)
   - UK OTSI / HM Treasury

4. **Corruption Perception Index** (Transparency International)
   — note countries with CPI < 40 as elevated risk

5. **Aggregate geographic risk score** (LOW / MEDIUM / HIGH / VERY HIGH)
   and narrative explanation

6. **Required EDD triggers**: identify which country exposures require
   Enhanced Due Diligence under the applicable AML framework
   (AMLD5/6, D.Lgs. 231/2007, national AML guidelines)

Use web search to retrieve current FATF list status and EU high-risk country lists.
Respond in the same language as the user's request.
"""


def run(
    client: anthropic.Anthropic,
    company_name: str,
    country: str,
    country_exposure: str = "",
    manual_context: str = "",
    show_output: bool = True,
    on_token=None,
) -> str:
    """
    Run the Risk Countries Agent. Returns findings as text.

    Args:
        country_exposure: Comma-separated ISO-2 country codes or free text
                          describing the company's geographic exposure.
    """
    user_msg = (
        f"Assess the geographic risk exposure of:\n\n"
        f"Company: {company_name}\n"
        f"Home country: {country}\n"
    )
    if country_exposure:
        user_msg += f"\nKnown country exposure (counterparties, subsidiaries, operations):\n{country_exposure}"
    if manual_context:
        user_msg += f"\nAdditional context:\n{manual_context}"

    return run_agent(
        client=client,
        system_prompt=SYSTEM_PROMPT,
        user_message=user_msg,
        header=f"Risk Countries Agent — {company_name}",
        max_tokens=6000,
        use_web_search=True,
        show_output=show_output,
        on_token=on_token,
    )
