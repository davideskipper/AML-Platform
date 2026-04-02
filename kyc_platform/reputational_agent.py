"""
Reputational Agent
==================
Searches for adverse media and reputational risk using web search
(limited to 3 searches) and any documents provided.
Returns structured JSON with events, flags, and a compliance narrative.
"""

import anthropic
from .utils import run_agent

SYSTEM_PROMPT = """Sei un AML Reputational Risk Analysis Agent specializzato in adverse media screening
e valutazione del casellario giudiziario e dei precedenti regolatori.
Analizza i documenti reputazionali forniti (sentenze, comunicati stampa, atti giudiziari)
e integra con ricerche web mirate.

ANALISI DOCUMENTI GIUDIZIARI:
- Identifica procedimenti penali: tipologia reato, stato (indagato/imputato/condannato/prosciolto)
- Verifica se il reato rientra tra i reati presupposto del riciclaggio (D.Lgs. 231/2007 Allegato)
- Misure cautelari personali o patrimoniali in corso (sequestri, arresti, interdizioni)
- Sentenze definitive di condanna (verifica ostatività alla continuazione del rapporto)
- Procedimenti per reati societari, fiscali, fallimentari
- Interdizioni, incapacità o misure di prevenzione antimafia

REATI AD ALTO RISCHIO AML — segnala con priorità CRITICAL:
- Riciclaggio, autoriciclaggio (art. 648-bis/ter c.p.)
- Corruzione, concussione, peculato
- Frode fiscale, false fatturazioni, evasione grave
- Appartenenza o concorso con organizzazioni criminali (art. 416-bis c.p.)
- Traffico di stupefacenti, armi, esseri umani
- Terrorismo e finanziamento del terrorismo
- Reati ambientali gravi (D.Lgs. 231/2001)

ANALISI STAMPA E COMUNICATI:
- Identifica articoli o comunicati che citino indagini, sequestri, ispezioni
- Valuta attendibilità della fonte (testata giornalistica nazionale vs locale vs blog)
- Distingui tra notizie verificate, indiscrezioni e mere speculazioni
- Considera il timeframe: recente (<2 anni) vs storico (>5 anni)
- Verifica se vi siano smentite ufficiali o esiti assolutori successivi

RICERCA WEB: Effettua ricerche mirate per trovare notizie recenti non coperte dai documenti.
Priorità: notizie degli ultimi 2 anni. Limita le ricerche alle più rilevanti.

FLAG AUTOMATICI:
- Reati presupposto AML anche se non definitivi
- Misure di prevenzione antimafia (anche solo proposte)
- Procedimenti in corso per reati fiscali o societari gravi
- Citazioni in atti giudiziari come soggetto terzo rilevante
- Notizie negative recenti non smentite da fonti attendibili

OUTPUT: Restituisci esclusivamente un oggetto JSON valido con questa struttura:
{
  "sintesiReputazionale": "max 3 righe",
  "eventiNegativi": [
    {
      "data": "",
      "fonte": "",
      "tipoEvento": "",
      "statoProcedurale": "",
      "reatoPredicate": true,
      "rilevanzeAML": "SI|NO|POSSIBILE",
      "rischio": "LOW|MEDIUM|HIGH|CRITICAL"
    }
  ],
  "flags": [
    { "tipo": "", "descrizione": "", "rischio": "LOW|MEDIUM|HIGH|CRITICAL", "riferimentoNormativo": "" }
  ],
  "raccomandazione": "PROCEED|ENHANCED_MONITORING|ESCALATE_TO_COMPLIANCE|RIFIUTO",
  "principaliEvidenze": [
    {
      "evidenza": "Descrizione sintetica dell'elemento di attenzione o anomalia rilevata",
      "normativa": "Riferimento normativo specifico (es. Art.20 D.Lgs.231/2007, UIF Indic.n.42/2023, FATF Rec.10)",
      "livello": "ATTENZIONE|ANOMALIA|CRITICO"
    }
  ],
  "rischioComplessivo": "LOW|MEDIUM|HIGH|CRITICAL",
  "narrativa": "Testo discorsivo di 10-14 righe. Descrivi il profilo reputazionale del soggetto, gli eventi negativi più rilevanti, la loro attualità e il loro peso ai fini AML. Spiega il razionale della raccomandazione. Tono formale, linguaggio tecnico AML.",
  "note": ""
}"""


def run(
    client: anthropic.Anthropic,
    company_name: str,
    country: str,
    key_persons: str = "",
    manual_context: str = "",
    show_output: bool = True,
    on_token=None,
    on_thinking=None,
    use_web_search=None,
) -> str:
    """Run the Reputational Agent. Returns JSON findings as text."""
    user_msg = (
        f"Esegui l'analisi reputazionale e adverse media screening per:\n\n"
        f"Azienda: {company_name}\n"
        f"Paese: {country}\n"
    )
    if key_persons:
        user_msg += f"\nPersone chiave da sottoporre a screening individuale:\n{key_persons}"
    if manual_context:
        user_msg += f"\nDocumenti e informazioni forniti dall'analista:\n{manual_context}"

    _use_web = True if use_web_search is None else use_web_search
    return run_agent(
        client=client,
        system_prompt=SYSTEM_PROMPT,
        user_message=user_msg,
        header=f"Reputational Agent — {company_name}",
        max_tokens=6000,
        use_web_search=_use_web,
        max_search_uses=3 if _use_web else None,
        show_output=show_output,
        on_token=on_token,
        on_thinking=on_thinking,
    )
