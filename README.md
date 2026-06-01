# Leapmotor B10 Integration (HACS Fork)

Questa è una versione personalizzata dell'integrazione Leapmotor B10, trasformata in un componente custom compatibile con **HACS**.

## Installazione via HACS

1. Vai su **HACS** -> **Integrations**.
2. Clicca sui tre puntini in alto a destra e seleziona **Custom repositories**.
3. Inserisci l'URL del tuo fork e seleziona **Integration** come categoria.
4. Clicca su **Add** e poi installa l'integrazione.

## Configurazione

Dopo l'installazione e il riavvio di Home Assistant:
1. Vai in **Impostazioni** -> **Dispositivi e Servizi**.
2. Clicca su **Aggiungi integrazione** e cerca **Leapmotor B10**.
3. Inserisci i dati richiesti nella finestra di configurazione:
   - **Entry ID**: L'ID dell'integrazione Leapmotor base (kerniger).
   - **Capacità Batteria**: (es. 67.1).
   - **Entità Wallbox**: L'entità del sensore di potenza della tua Wallbox.

## Struttura del progetto
I file YAML in `packages/` devono essere ancora collegati nel tuo `configuration.yaml` se non usi l'integrazione nativa per tutto.
I file Python e gli asset web sono ora gestiti centralmente dall'integrazione.
