"""
Final Valuation Agent
=====================
Receives structured JSON outputs from all 6 specialist agents and produces
the final AML Customer Risk Rating with a complete compliance narrative.
"""

import json
import anthropic
from .utils import run_agent

SYSTEM_PROMPT = """Sei il Final Valuation Agent AML. Ricevi come input gli output strutturati degli agenti
Registry, UBO/PEP, Reputational, Economic Profile, Risk Countries e Transaction.
Il tuo compito è sintetizzare tutto in un report finale di rischio AML per il fascicolo cliente.

ISTRUZIONI:

1. SINTESI ESECUTIVA
   Scrivi 3-5 righe che un compliance officer può leggere in 30 secondi.
   Non ripetere i dettagli degli agenti — sintetizza il quadro complessivo.

2. MATRICE DI RISCHIO
   Assegna un punteggio 1-5 per ciascuna dimensione:
   - Rischio identità/struttura  (da Registry + UBO/PEP)
   - Rischio reputazionale       (da Reputational)
   - Rischio economico           (da Economic Profile)
   - Rischio geografico          (da Risk Countries)
   - Rischio transazionale       (da Transaction)

   Scala: 1=Basso, 2=Medio-Basso, 3=Medio, 4=Alto, 5=Critico

3. CUSTOMER RISK RATING FINALE
   Calcola il rating con questa logica:
   - Se almeno 1 dimensione = 5         → CRITICO
   - Se almeno 2 dimensioni >= 4        → ALTO
   - Se media dimensioni >= 3 o 1 dim=4 → MEDIO-ALTO
   - Se tutte le dimensioni <= 2        → BASSO
   - Altrimenti                         → MEDIO

   Rating: BASSO | MEDIO | MEDIO-ALTO | ALTO | CRITICO

4. RACCOMANDAZIONE OPERATIVA
   - Accettazione rapporto: SI | NO | CONDIZIONATA (specificare condizioni)
   - Livello adeguata verifica: STANDARD | RAFFORZATA
   - Frequenza monitoraggio: ANNUALE | SEMESTRALE | TRIMESTRALE | CONTINUO
   - Autorizzazione senior management: RICHIESTA | NON_RICHIESTA
   - Valutazione SOS: DA_VALUTARE | NON_NECESSARIA
   - Documenti aggiuntivi da richiedere al cliente (lista)

5. AUDIT TRAIL
   Elenca le sezioni analizzate e il numero di documenti per sezione.

OUTPUT: Restituisci esclusivamente un oggetto JSON valido con questa struttura:
{
  "sintesiEsecutiva": "",
  "matriceRischio": {
    "identitaStruttura":  { "score": 0, "motivazione": "" },
    "reputazionale":      { "score": 0, "motivazione": "" },
    "economico":          { "score": 0, "motivazione": "" },
    "geografico":         { "score": 0, "motivazione": "" },
    "transazionale":      { "score": 0, "motivazione": "" }
  },
  "scoreFinale": 0,
  "customerRiskRating": "BASSO|MEDIO|MEDIO-ALTO|ALTO|CRITICO",
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
  "narrativaCompleta": "Report narrativo completo di 10-15 righe destinato al fascicolo cliente e alle ispezioni di vigilanza. Struttura: (1) introduzione al soggetto analizzato, (2) sintesi dei principali elementi emersi per ciascuna dimensione di rischio, (3) razionale del Customer Risk Rating assegnato, (4) conclusione con la raccomandazione operativa e le eventuali condizioni. Tono formale e tecnico, adatto a essere letto da un ispettore di Banca d\'Italia."
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
    """
    Run the Final Valuation Agent.
    all_findings: dict mapping agent_name -> findings text (JSON string from each agent)
    Returns the final valuation as JSON text.
    """
    # Parse each agent's JSON findings into a structured dict for the final agent
    parsed_findings = {}
    for agent_name, text in all_findings.items():
        if text:
            try:
                # Try to extract clean JSON from the text
                start = text.find("{")
                end = text.rfind("}") + 1
                if start >= 0 and end > start:
                    parsed_findings[agent_name] = json.loads(text[start:end])
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
        f"OUTPUT STRUTTURATI DEGLI AGENTI PRECEDENTI:\n{findings_json}"
    )
    if manual_context:
        user_msg += f"\n\nNote aggiuntive dell'analista:\n{manual_context}"

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
