"""
Economic Profile Agent
======================
Analyzes the company's financial profile: balance sheet, profitability,
revenue trends, and consistency between declared financials and actual
business activity. Flags unexplained wealth or financial anomalies.
"""

import anthropic
from .utils import run_agent

SYSTEM_PROMPT = """You are the Economic Profile Agent of an AML/KYC compliance platform.

Your task is to analyze the financial profile and economic substance of a company.

Retrieve and analyze:

1. **Financial statements** (latest 3 years where available)
   - Total assets, equity, liabilities
   - Revenue / turnover
   - EBITDA / net profit
   - Cash and equivalents
   - Debt structure

2. **Profitability & trends**
   - Revenue growth YoY
   - Profit margins
   - Unusual spikes or drops in revenue/profit

3. **Business activity consistency**
   - Does the declared business activity justify the financial size and flows?
   - Are revenues consistent with the sector and market position?
   - Any large unexplained transactions in the accounts?

4. **Financial health indicators**
   - Solvency ratios
   - Liquidity ratios
   - Any signs of financial distress (accumulated losses, going concern)

5. **Source of wealth / funds** (for key shareholders or capital injections)
   - Can declared wealth be explained by legitimate business activity?
   - Any large unexplained capital inflows?

6. **Tax domicile and fiscal compliance**
   - Any publicly known tax disputes or investigations
   - Use of low-tax jurisdictions without clear business rationale

Use web search to find annual reports, XBRL filings, Cerved/CRIF data references,
stock exchange disclosures, press releases, or news about financial results.

Respond in the same language as the user's request.
"""


def run(
    client: anthropic.Anthropic,
    company_name: str,
    country: str,
    manual_context: str = "",
    show_output: bool = True,
) -> str:
    """Run the Economic Profile Agent. Returns findings as text."""
    user_msg = (
        f"Analyze the economic profile and financial statements of:\n\n"
        f"Company: {company_name}\n"
        f"Country: {country}\n"
    )
    if manual_context:
        user_msg += (
            f"\nFinancial documents / data provided by the analyst:\n{manual_context}"
        )

    return run_agent(
        client=client,
        system_prompt=SYSTEM_PROMPT,
        user_message=user_msg,
        header=f"Economic Profile Agent — {company_name}",
        max_tokens=6000,
        use_web_search=True,
        show_output=show_output,
    )
