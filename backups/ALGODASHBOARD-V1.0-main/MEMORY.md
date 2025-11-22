# Memória do Projeto e Roadmap Evolutivo

Este arquivo serve como "cérebro" do projeto, registrando o contexto, decisões tomadas, lições aprendidas e próximos passos. Novos desenvolvedores devem ler isso antes de começar.

---

## 📅 Histórico de Desenvolvimento

### [2025-11-21] - Ciclo 7: Otimização Realista e Benchmarking
**Objetivo:** Maximizar a eficiência do bot na Testnet e estabelecer um processo rigoroso de evolução de estratégia (Campeão x Desafiante).

**Ações Críticas:**
1.  **Clean Architecture:** Refatoração do `run_live.py` usando `BinanceDemoAdapter` para encapsular a complexidade da conexão Testnet.
2.  **Correção de PnL:** Implementação de fetch via endpoint V2 (`fapiPrivateGetV2Account`) para visualizar lucros reais.
3.  **Desafio de Estratégias (WFO Championship):**
    *   **Baseline:** `Hybrid` (Trend + RSI + Breakout). Retorno: **+303.38%**.
    *   **Challenger 1:** `SmartHybrid` (ATR Filter). Retorno: **+10.80%**.
    *   **Challenger 2:** `BollingerHybrid` (BB Squeeze). Retorno: **+36.64%**.
    *   **Veredito:** O Baseline massacrou os desafiantes. Complexidade extra reduziu a rentabilidade. O sistema permanece com o `Hybrid`.

**Status Atual:**
*   **Estratégia Ativa:** Hybrid Futures 2x (Short ETH/USDT).
*   **Infraestrutura:** Estável, com PnL em tempo real e Trailing Stop no lado do cliente.
*   **Risco:** Conservador (10% Equity).

---

## 📍 Estado Atual
*   **Estratégia Ativa:** Hybrid Long/Short (15m/4h).
    *   Alavancagem: 2x.
    *   Ambiente Padrão: **Testnet (Demo FAPI)**.
*   **Status:** Execução contínua. Posição Short aberta em ETH.

---

## 🗺️ Roadmap Evolutivo (Prioridades)

### 1. Validação e Monitoramento (Imediato)
*   [x] Executar `run_live.py` na Testnet por 24h.
*   [x] Verificar se todas as ordens no `trades_log.csv` correspondem à lógica esperada.
*   [x] Implementar Trailing Stop.

### 2. Melhoria de Execução (Curto Prazo)
*   [ ] Implementar "Smart Execution" (Maker/Limit orders) para reduzir taxas (Taker 0.05% -> Maker 0.02%).
*   [ ] Criar Dashboard Web simples (Flask/Streamlit) para não depender do console.

### 3. Expansão de Estratégia (Médio Prazo)
*   [ ] Testar **Portfolio Multi-Moeda** (ETH + BTC + SOL) para diversificar risco.
*   [ ] Desenvolver estratégia de "Mean Reversion Puro" para mercados laterais.

---

## ⚠️ Protocolo de Desenvolvimento Contínuo
1.  **Testnet First:** Nunca suba código novo direto para Mainnet.
2.  **Log Everything:** Se não está no log, não aconteceu. Use `report_performance.py`.
3.  **WFO Always:** Backtest sem Walk-Forward é ilusão. Só troque a estratégia se o WFO confirmar superioridade.
