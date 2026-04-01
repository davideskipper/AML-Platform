"""
Transaction Agent
=================
Reads an Excel file containing transaction data and performs AML analysis:
structuring detection, round-tripping, layering patterns, high-risk
counterparty identification, and TM alert generation.

No web search — analysis is based exclusively on the provided file.
"""

import os
import anthropic
from .utils import run_agent

SYSTEM_PROMPT = """You are the Transaction Agent of an AML/KYC compliance platform.

You have received transaction data in tabular form. Perform a comprehensive AML analysis.

Analyze for:

1. **Structuring** (smurfing)
   - Multiple transactions just below reporting thresholds (e.g., < €10,000 / < $10,000)
   - Suspicious frequency patterns

2. **Round-tripping**
   - Outflows to a counterparty followed by equivalent inflows (same or different entity)
   - Short time windows (suggest coordinated movement)

3. **Layering**
   - Complex chains of transactions through multiple intermediaries or jurisdictions
   - Rapid movements that obscure origin of funds

4. **High-risk counterparties**
   - Counterparties in FATF grey/black-listed jurisdictions
   - Counterparties with opaque ownership
   - Shell companies or offshore structures

5. **Volume anomalies**
   - YoY or MoM volume spikes with no clear business rationale
   - Concentration risk: single counterparty representing >30% of flows

6. **Unidentified counterparties**
   - Transactions where the ultimate beneficial counterparty is not identifiable

7. **Key statistics**
   - Total inbound / outbound volume
   - Number and value of flagged transactions
   - Top 5 counterparties by volume
   - Geographic distribution of flows

8. **TM Alerts** (Transaction Monitoring)
   - List each alert with: type, severity (HIGH/MEDIUM/LOW), description,
     affected transactions, recommended action

Produce a structured report with an overall transaction risk rating:
LOW / MEDIUM / HIGH / VERY HIGH

Respond in the same language as the request.
"""


def _read_excel(filepath: str) -> str:
    """Read Excel file with pandas and return a text representation."""
    try:
        import pandas as pd
    except ImportError:
        raise RuntimeError(
            "pandas is not installed. Run: pip install pandas openpyxl"
        )

    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".csv":
        dfs = {"Sheet1": pd.read_csv(filepath)}
    else:
        dfs = pd.read_excel(filepath, sheet_name=None)

    lines = []
    for sheet_name, df in dfs.items():
        lines.append(f"## Sheet: {sheet_name}")
        lines.append(f"Rows: {len(df)}  |  Columns: {', '.join(str(c) for c in df.columns)}")
        lines.append("")

        # Show up to 500 rows to stay within token limits
        sample = df.head(500)
        lines.append(sample.to_string(index=False))

        if len(df) > 500:
            lines.append(f"\n[... {len(df) - 500} more rows omitted ...]")

        lines.append("")

    return "\n".join(lines)


def run(
    client: anthropic.Anthropic,
    excel_path: str,
    company_name: str = "",
    manual_context: str = "",
    show_output: bool = True,
    on_token=None,
) -> str:
    """
    Run the Transaction Agent on an Excel/CSV file.
    Returns AML findings as text.
    """
    excel_text = _read_excel(excel_path)

    subject = f" for {company_name}" if company_name else ""
    user_msg = (
        f"Perform AML transaction analysis{subject}.\n\n"
        f"Transaction data:\n\n{excel_text}"
    )
    if manual_context:
        user_msg += f"\n\nAdditional context from analyst:\n{manual_context}"

    return run_agent(
        client=client,
        system_prompt=SYSTEM_PROMPT,
        user_message=user_msg,
        header=f"Transaction Agent{subject}",
        max_tokens=8000,
        use_web_search=False,   # analysis is purely data-driven
        show_output=show_output,
        on_token=on_token,
    )
