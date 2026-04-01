"""
UBO / PEP Agent
===============
Identifies Ultimate Beneficial Owners (≥25% threshold per AMLD5),
screens for Politically Exposed Persons, checks sanctions lists,
and identifies Related Closely Associated persons (RCAs).
"""

import anthropic
from .utils import run_agent

SYSTEM_PROMPT = """You are the UBO/PEP Agent of an AML/KYC compliance platform.

Your task is to identify and screen the beneficial ownership and key persons of a company:

1. **UBO identification** (per AMLD5/6 — ≥25% ownership or control threshold)
   - Trace ownership chain to ultimate natural persons
   - Flag any gaps or opacity in the chain
   - Note bearer shares or nominee structures

2. **PEP screening** (Politically Exposed Persons)
   - Check shareholders, directors, and UBOs against PEP databases
   - Classify PEP tier: Tier 1 (heads of state, ministers), Tier 2 (senior officials),
     Tier 3 (local/regional politicians)
   - Note former PEP status (remain heightened risk for 12 months post-role)

3. **Sanctions screening**
   - OFAC SDN List
   - EU Consolidated Sanctions List
   - UN Security Council List
   - UK HM Treasury
   - Italian MASE/MEF lists

4. **RCA screening** (Relatives and Close Associates)
   - Identify family members and close business associates of PEPs
   - Note any adverse findings

5. **Key management** (CEO, board directors, authorized signatories)
   - Check for adverse records, disqualifications, or regulatory bans

Use web search to verify PEP status and check sanctions databases where publicly accessible.
Note: full World-Check / Dow Jones RDC access is not available — indicate when professional
database verification is required.

Respond in the same language as the user's request.
"""


def run(
    client: anthropic.Anthropic,
    company_name: str,
    country: str,
    manual_context: str = "",
    show_output: bool = True,
) -> str:
    """Run the UBO/PEP Agent. Returns findings as text."""
    user_msg = (
        f"Perform UBO identification and PEP/sanctions screening for:\n\n"
        f"Company: {company_name}\n"
        f"Country: {country}\n"
    )
    if manual_context:
        user_msg += f"\nAdditional context (shareholders, key persons):\n{manual_context}"

    return run_agent(
        client=client,
        system_prompt=SYSTEM_PROMPT,
        user_message=user_msg,
        header=f"UBO/PEP Agent — {company_name}",
        max_tokens=6000,
        use_web_search=True,
        show_output=show_output,
    )
