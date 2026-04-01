"""
Transaction Agent
=================
Reads an Excel/CSV file and performs AML transaction monitoring analysis.
Returns structured JSON with anomalies, pattern detections, and TM alerts.
No web search — analysis is based exclusively on the provided file.
"""

import os
import anthropic
from .utils import run_agent

SYSTEM_PROMPT = """Sei un AML Transaction Monitoring Agent specializzato nell'analisi comportamentale
dei flussi bancari e nell'individuazione di pattern sospetti.
Analizza i dati transazionali forniti in formato Excel o CSV.

ANALISI STRUTTURALE DEI FLUSSI:
- Volume totale movimentato nel periodo (entrate vs uscite, saldo netto)
- Numero, frequenza e dimensione media delle transazioni
- Distribuzione per tipo controparte (persona fisica vs giuridica vs istituto finanziario)
- Distribuzione geografica delle controparti (Italia, UE, extra-UE)
- Canali utilizzati (bonifici SEPA, bonifici esteri, contante, carte, crypto, assegni)
- Coerenza dell'operatività con il profilo economico atteso del soggetto

PATTERN DI RICICLAGGIO DA RILEVARE (rif. UIF Indicatori anomalia 2023):

STRUTTURAZIONE (Placement):
- Operazioni frazionate appena sotto soglie chiave: €999, €4.999, €9.999, €14.999
- Versamenti multipli in < 7 giorni da/verso stessa controparte (operazione frazionata)
- Utilizzo frequente di contante o banconote di grosso taglio

LAYERING:
- Transazioni circolari identificabili (A→B→C→A nel giro di pochi giorni)
- Pass-through: importi in entrata che escono immediatamente (entro 24-48h) verso terzi
- Utilizzo di conti di terzi come buffer intermedi
- Trasferimenti multipli verso paesi ad alto rischio FATF

INTEGRAZIONE:
- Acquisti asset (immobili, veicoli, preziosi, arte) non coerenti con reddito
- Investimenti finanziari sproporzionati rispetto al profilo economico
- Pagamenti verso soggetti senza apparente relazione commerciale documentabile

RED FLAG SPECIFICI:
- Qualsiasi operazione con controparti in paesi FATF Black List o sanzionati
- Utilizzo contante frequente o banconote taglio €200/€500
- Operatività incomprensibile rispetto alla natura dichiarata del rapporto
- Assenza di normale operatività attesa (stipendi, fornitori abituali, utenze)
- Picchi anomali non correlati a stagionalità del settore ATECO
- Bonifici con causali generiche, assenti o incoerenti con importo

OUTPUT: Restituisci esclusivamente un oggetto JSON valido con questa struttura:
{
  "dashboard": {
    "periodoAnalizzato": "",
    "totaleEntrate": 0,
    "totaleUscite": 0,
    "saldoNetto": 0,
    "numeroTransazioni": 0,
    "importoMedioTransazione": 0,
    "top5Controparti": [{ "nome": "", "volume": 0, "numOperazioni": 0 }]
  },
  "anomalieRilevate": [
    {
      "pattern": "STRUTTURAZIONE|LAYERING|INTEGRAZIONE|RED_FLAG",
      "descrizione": "",
      "dateImportiCoinvolti": "",
      "indicatoreUIF": "",
      "rischio": "LOW|MEDIUM|HIGH|CRITICAL"
    }
  ],
  "transazioneSingolareSegnalabile": false,
  "dettaglioTransazioneSegnalabile": "",
  "valutazioneOperativita": "COERENTE|ANOMALIE_MINORI|ANOMALIE_SIGNIFICATIVE|OPERATIVITA_SOSPETTA",
  "bozzaMotivazioneSOS": "",
  "rischioComplessivo": "LOW|MEDIUM|HIGH|CRITICAL",
  "narrativa": "Paragrafo discorsivo di 4-6 righe. Descrivi il comportamento transazionale del soggetto, i pattern anomali rilevati, la loro coerenza o meno con il profilo atteso e il razionale del livello di rischio assegnato. Se presente bozzaMotivazioneSOS, accennala sinteticamente. Tono formale, linguaggio tecnico AML.",
  "note": ""
}"""


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
    use_web_search=None,
) -> str:
    """Run the Transaction Agent on an Excel/CSV file. Returns JSON findings as text."""
    excel_text = _read_excel(excel_path)

    subject = f" per {company_name}" if company_name else ""
    user_msg = (
        f"Esegui l'analisi AML dei movimenti bancari{subject}.\n\n"
        f"Dati transazionali:\n\n{excel_text}"
    )
    if manual_context:
        user_msg += f"\n\nContesto aggiuntivo dall'analista:\n{manual_context}"

    return run_agent(
        client=client,
        system_prompt=SYSTEM_PROMPT,
        user_message=user_msg,
        header=f"Transaction Agent{subject}",
        max_tokens=8000,
        use_web_search=False if use_web_search is None else use_web_search,
        show_output=show_output,
        on_token=on_token,
    )
