"""
Registry Agent
==============
Analyzes corporate structure, ownership chain, shareholders,
subsidiaries, and recent corporate changes using public registries
and open-source data.
"""

import anthropic
from .utils import run_agent

SYSTEM_PROMPT = """You are the Registry Agent of an AML/KYC compliance platform.

Your task is to analyze the corporate structure of a company and produce a structured report covering:
1. Legal name, form, registration number, registered office
2. Incorporation date and jurisdiction
3. Share capital and paid-up status
4. Current shareholder structure (names, stakes, nationalities)
5. Ownership chain up to ultimate natural persons
6. Subsidiaries and related entities
7. Recent corporate changes (last 24 months): new shareholders, address changes,
   management changes, capital changes
8. Pending insolvency proceedings, judicial measures, or regulatory restrictions
9. Cross-border structures or offshore elements

Use web search to find data from:
- Official company registries (Registro Imprese, Companies House, EDGAR, etc.)
- Orbis / Bureau van Dijk references
- Official gazette filings
- Stock exchange disclosures (if listed)

Be factual and cite sources. Flag any opacity in the ownership structure.
Respond in the same language as the user's request (Italian or English).
"""


def run(
    client: anthropic.Anthropic,
    company_name: str,
    country: str,
    manual_context: str = "",
    show_output: bool = True,
) -> str:
    """Run the Registry Agent. Returns findings as text."""
    user_msg = (
        f"Analyze the corporate structure of the following company:\n\n"
        f"Company: {company_name}\n"
        f"Country: {country}\n"
    )
    if manual_context:
        user_msg += f"\nAdditional context provided by the analyst:\n{manual_context}"

    return run_agent(
        client=client,
        system_prompt=SYSTEM_PROMPT,
        user_message=user_msg,
        header=f"Registry Agent — {company_name}",
        max_tokens=6000,
        use_web_search=True,
        show_output=show_output,
    )
