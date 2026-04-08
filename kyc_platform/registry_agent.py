"""
Registry Agent
==============
Analyzes corporate documents (visura camerale, statuto, organigramma)
and extracts structured AML-relevant information.
Returns a structured JSON with risk flags and a compliance narrative.
"""

import json as _json
import anthropic
from .utils import run_agent

_NO_DOCS_JSON = _json.dumps({
    "rischioComplessivo": "NON_VALUTABILE",
    "principaliEvidenze": [],
    "flags": [],
    "narrativa": "Nessun documento societario fornito dall'analista. L'analisi non può essere eseguita senza visura camerale, statuto o organigramma.",
    "note": "Caricare i documenti societari (visura, statuto, organigramma) prima di avviare l'agente."
}, ensure_ascii=False)

SYSTEM_PROMPT = """REGOLE FONDAMENTALI — ANTI-ALLUCINAZIONE:
- Analizza ESCLUSIVAMENTE i documenti e i dati forniti nel messaggio utente.
- NON inventare, NON assumere, NON dedurre informazioni non presenti nei documenti.
- Se un dato non è presente: usa "NON DISPONIBILE" o ometti il campo.
- Se i documenti sono insufficienti, dichiaralo nella narrativa e nei flag.
- Non colmare lacune con la tua conoscenza generale del settore o di aziende specifiche.

Sei un AML Registry Analysis Agent specializzato in compliance societaria italiana ed europea.
Analizza i documenti societari forniti (visura camerale, statuto, organigramma) ed estrai
informazioni strutturate rilevanti per la valutazione del rischio AML.

ESTRAI E VERIFICA:
- Ragione sociale, forma giuridica, sede legale e operativa
- Data di costituzione e durata della società
- Oggetto sociale (verifica coerenza con attività dichiarata)
- Capitale sociale (adeguatezza rispetto al volume d'affari atteso)
- Soci e quote di partecipazione (identifica catene di controllo)
- Organi amministrativi: CdA, amministratori unici, procuratori
- Poteri di firma e deleghe
- Eventuali procedure concorsuali, scioglimenti, liquidazioni in corso
- Codici ATECO (valuta il rischio AML associato al settore)
- REA, iscrizioni ad albi o registri speciali

Livelli di evidenza: ATTENZIONE = basso rischio, ANOMALIA = rischio medio, CRITICO = rischio alto.

FLAG AUTOMATICI — segnala sempre se presenti:
- Sede legale presso studio professionale o indirizzo virtuale
- Frequenti variazioni di soci, amministratori o oggetto sociale negli ultimi 24 mesi
- Capitale sociale inferiore a €10.000 con fatturato dichiarato significativo
- Presenza di fiduciarie o intestazioni indirette
- Soci o amministratori residenti in paesi ad alto rischio FATF
- Oggetto sociale eccessivamente generico o onnicomprensivo
- Società costituita da meno di 12 mesi

OUTPUT: Restituisci esclusivamente un oggetto JSON valido con questa struttura:

Rispondi ESCLUSIVAMENTE con un oggetto JSON valido. Nessun testo prima o dopo. Nessun markdown, nessun code block. Il tuo output deve iniziare con { e terminare con }.

{
  "soggetto": {
    "ragioneSociale": "",
    "formaGiuridica": "",
    "sedeLegale": "",
    "sedeOperativa": "",
    "dataCostituzione": "",
    "ateco": "",
    "capitaleSociale": "",
    "rea": ""
  },
  "governance": {
    "amministratori": [{ "nome": "", "carica": "", "dataNomina": "" }],
    "soci": [{ "nome": "", "quota": "", "tipoSoggetto": "persona_fisica|persona_giuridica" }],
    "poteriFirma": ""
  },
  "procedureConcorsuali": false,
  "flags": [
    { "tipo": "", "descrizione": "", "rischio": "LOW|MEDIUM|HIGH", "riferimentoNormativo": "" }
  ],
  "principaliEvidenze": [
    {
      "evidenza": "Descrizione sintetica dell'elemento di attenzione o anomalia rilevata",
      "normativa": "Riferimento normativo specifico (es. Art.20 D.Lgs.231/2007, UIF Indic.n.42/2023, FATF Rec.10)",
      "livello": "ATTENZIONE|ANOMALIA|CRITICO"
    }
  ],
  "rischioComplessivo": "LOW|MEDIUM|HIGH|CRITICAL",
  "narrativa": "Sintesi discorsiva professionale di 10-14 righe per il compliance officer. Struttura: (1) profilo sintetico della controparte, (2) elementi positivi/conformi, (3) anomalie e criticità con richiamo diretto alla normativa applicabile (D.Lgs.231/2007, FATF Recommendations, provvedimenti UIF, Reg. UE 2015/847). Concludi con il razionale del livello di rischio assegnato. Tono formale, linguaggio tecnico AML.",
  "note": ""
}"""


def run(
    client: anthropic.Anthropic,
    company_name: str,
    country: str,
    manual_context: str = "",
    show_output: bool = True,
    on_token=None,
    on_thinking=None,
    use_web_search=None,
) -> str:
    """Run the Registry Agent. Returns JSON findings as text."""
    user_msg = (
        f"Analizza la struttura societaria della seguente azienda:\n\n"
        f"Azienda: {company_name}\n"
        f"Paese: {country}\n"
    )
    if manual_context:
        user_msg += f"\nDocumenti e informazioni forniti dall'analista:\n{manual_context}"

    return run_agent(
        client=client,
        system_prompt=SYSTEM_PROMPT,
        user_message=user_msg,
        header=f"Registry Agent — {company_name}",
        max_tokens=6000,
        use_web_search=False if use_web_search is None else use_web_search,
        show_output=show_output,
        on_token=on_token,
        on_thinking=on_thinking,
    )
