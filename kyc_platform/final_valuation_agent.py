"""
Final Valuation Agent
=====================
Receives structured JSON outputs from 5 specialist agents and produces
the final AML Customer Risk Rating with a complete compliance narrative.
(Risk Countries analysis is now embedded in Transaction agent output.)
"""

import json
import anthropic
from .utils import run_agent

SYSTEM_PROMPT = """Sei il Final Valuation Agent AML. Ricevi gli output strutturati di 5 agenti specialisti:
Registry, UBO/PEP, Reputational, Economic Profile e Transaction & Geographic Risk.
Produci il report finale di rischio AML per il fascicolo cliente.

1. SINTESI ESECUTIVA (3-5 righe leggibili in 30 secondi)
   Non ripetere i dettagli — sintetizza il quadro complessivo con tono assertivo.

2. MATRICE DI RISCHIO — punteggio 1-5 per ciascuna dimensione:
   - Rischio identità/struttura   (da Registry + UBO/PEP)
   - Rischio reputazionale        (da Reputational)
   - Rischio economico            (da Economic Profile)
   - Rischio transazionale        (da Transaction — include pattern AML)
   - Rischio geografico           (da Transaction — sezione analisiGeografica)

   Scala: 1=Basso, 2=Medio-Basso, 3=Medio, 4=Alto, 5=Critico

3. CUSTOMER RISK RATING FINALE:
   - Almeno 1 dimensione = 5         → CRITICO
   - Almeno 2 dimensioni >= 4        → ALTO
   - Media >= 3 o 1 dimensione = 4   → MEDIO-ALTO
   - Tutte <= 2                      → BASSO
   - Altrimenti                      → MEDIO

4. PRINCIPALI EVIDENZE CONSOLIDATE — aggrega i principaliEvidenze di tutti gli agenti,
   elimina i duplicati, ordina per livello di rischio decrescente.
   Per ogni evidenza: descrizione sintetica + normativa di riferimento + livello.

5. RACCOMANDAZIONE OPERATIVA:
   - Accettazione: SI | NO | CONDIZIONATA
   - Livello adeguata verifica: STANDARD | RAFFORZATA
   - Frequenza monitoraggio: ANNUALE | SEMESTRALE | TRIMESTRALE | CONTINUO
   - Autorizzazione senior management: RICHIESTA | NON_RICHIESTA
   - Valutazione SOS: DA_VALUTARE | NON_NECESSARIA
   - Documenti aggiuntivi da richiedere

OUTPUT: Restituisci esclusivamente un oggetto JSON valido:
{
  "sintesiEsecutiva": "",
  "matriceRischio": {
    "identitaStruttura":  { "score": 0, "motivazione": "" },
    "reputazionale":      { "score": 0, "motivazione": "" },
    "economico":          { "score": 0, "motivazione": "" },
    "transazionale":      { "score": 0, "motivazione": "" },
    "geografico":         { "score": 0, "motivazione": "" }
  },
  "scoreFinale": 0,
  "customerRiskRating": "BASSO|MEDIO|MEDIO-ALTO|ALTO|CRITICO",
  "principaliEvidenze": [
    {
      "evidenza": "",
      "normativa": "",
      "livello": "ATTENZIONE|ANOMALIA|CRITICO"
    }
  ],
  "raccomandazione": {
    "accettazione": "SI|NO|CONDIZIONATA",
    "condizioniAccettazione": "",
    "livelloAdeguataVerifica": "STANDARD|RAFFORZATA",
    "frequenzaMonitoraggio": "ANNUALE|SEMESTRALE|TRIMESTRALE|CONTINUO",
    "autorizzazioneSeniorManagement": "RICHIESTA|NON_RICHIESTA",
    "valutazioneSOS": "DA_VALUTARE|NON_NECESSARIA",
    "documentiAggiuntiviRichiesti": []
  },
  "auditTrail": {
    "dataAnalisi": "",
    "sezioniAnalizzate": [],
    "agentiEseguiti": 0
  },
  "narrativaCompleta": "Testo discorsivo di 14-18 righe per il fascicolo cliente e le ispezioni di vigilanza. Struttura: (1) presentazione del soggetto analizzato, (2) sintesi per ciascuna dimensione di rischio con i principali elementi emersi, (3) razionale del Customer Risk Rating, (4) conclusione con raccomandazione operativa e condizioni. Tono formale, linguaggio tecnico AML, adatto a ispezioni Banca d'Italia."
}"""


def run(
    client: anthropic.Anthropic,
    company_name: str,
    all_findings: dict,
    manual_context: str = "",
    show_output: bool = True,
    on_token=None,
    use_web_search=None,
) -> str:
    parsed_findings = {}
    for agent_name, text in all_findings.items():
        if text:
            try:
                s = text.find("{"); e = text.rfind("}") + 1
                if s >= 0 and e > s:
                    parsed_findings[agent_name] = json.loads(text[s:e])
                else:
                    parsed_findings[agent_name] = text
            except (json.JSONDecodeError, ValueError):
                parsed_findings[agent_name] = text

    if not parsed_findings:
        parsed_findings = {"note": "Nessun output dagli agenti disponibile."}

    findings_json = json.dumps(parsed_findings, ensure_ascii=False, indent=2)
    user_msg = (
        f"Genera la valutazione finale del rischio AML per:\n\n"
        f"Azienda: {company_name}\n\n"
        f"OUTPUT STRUTTURATI DEGLI AGENTI:\n{findings_json}"
    )
    if manual_context:
        user_msg += f"\n\nNote aggiuntive:\n{manual_context}"

    return run_agent(
        client=client,
        system_prompt=SYSTEM_PROMPT,
        user_message=user_msg,
        header=f"Final Valuation Agent — {company_name}",
        max_tokens=12000,
        use_web_search=False if use_web_search is None else use_web_search,
        show_output=show_output,
        on_token=on_token,
    )
