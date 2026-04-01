"""
Reputational Agent
==================
Searches for negative news, adverse media, and regulatory actions
concerning the company and its key persons (shareholders, directors, UBOs).
"""

import anthropic
from .utils import run_agent

SYSTEM_PROMPT = """You are the Reputational Agent of an AML/KYC compliance platform.

Your task is to conduct adverse media and reputational research for a company and its key persons.

Search for and report on:

1. **Adverse media** — negative news involving:
   - Financial crimes: fraud, money laundering, tax evasion, embezzlement
   - Corruption, bribery, or political scandals
   - Regulatory sanctions or enforcement actions
   - Civil litigation or criminal proceedings
   - Bankruptcy, insolvency, or financial distress

2. **Regulatory actions** from supervisory authorities:
   - Italy: CONSOB, Banca d'Italia, IVASS, Guardia di Finanza, AGCM
   - EU: EBA, ESMA, ECB
   - US: SEC, FINRA, OCC, FinCEN
   - UK: FCA, PRA
   - Other relevant national regulators

3. **Watchlists and debarment lists**:
   - World Bank debarment
   - EBRD ineligibility
   - EU/UN procurement bans

4. **Key persons**: run the same adverse media check for shareholders,
   directors, and UBOs individually.

5. **Adverse media scoring**: assign a score 0–10
   (0 = no adverse media, 10 = severe confirmed adverse media)
   and justify the score.

Search recent news (last 5 years prioritized, flag older material separately).
Distinguish between confirmed facts, allegations, and reputational rumours.
Cite sources with dates.

Respond in the same language as the user's request.
"""


def run(
    client: anthropic.Anthropic,
    company_name: str,
    country: str,
    key_persons: str = "",
    manual_context: str = "",
    show_output: bool = True,
    on_token=None,
) -> str:
    """Run the Reputational Agent. Returns findings as text."""
    user_msg = (
        f"Conduct adverse media and reputational research for:\n\n"
        f"Company: {company_name}\n"
        f"Country: {country}\n"
    )
    if key_persons:
        user_msg += f"\nKey persons to screen individually:\n{key_persons}"
    if manual_context:
        user_msg += f"\nAdditional context:\n{manual_context}"

    return run_agent(
        client=client,
        system_prompt=SYSTEM_PROMPT,
        user_message=user_msg,
        header=f"Reputational Agent — {company_name}",
        max_tokens=6000,
        use_web_search=True,
        show_output=show_output,
        on_token=on_token,
    )
