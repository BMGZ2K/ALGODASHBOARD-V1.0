# High-Performance Algo Trading System (Gem3.0)

Este projeto é um sistema de trading algorítmico focado em resultados comprovados através de Walk-Forward Optimization (WFO). O objetivo é superar o desempenho de Buy & Hold com menor drawdown e risco controlado.

## 🚀 Estratégia Vencedora Atual

**Nome:** Trend Pullback Multi-TF (15m/4h)
**Ativo:** ETH/USDT (Spot)
**Performance (Backtest WFO):**
- **Retorno Total:** +30.67% (vs +28.49% Buy & Hold)
- **Drawdown Médio:** -3.51% (Risco extremamente baixo)
- **Custo Simulado:** 0.15% por trade

### Lógica
Combina a segurança de longo prazo com a precisão de curto prazo.
- **Filtro de Tendência (4h):** SuperTrend (10, 3.0) deve estar em ALTA.
- **Sinal de Entrada (15m):** RSI(14) cai abaixo de 40 (Pullback).
- **Saída:** Reversão da tendência 4h OU RSI(14) acima de 70.

## 📂 Estrutura do Projeto

```
.
├── best_strategies/       # Configurações JSON das melhores estratégias encontradas
├── data/                  # Dados históricos OHLCV (CSV)
├── results/               # Relatórios detalhados dos backtests (WFO)
├── strategies/            # Código fonte das estratégias (ML, Trend, Mean Rev)
├── tools/                 # Ferramentas utilitárias
│   ├── wfo.py             # Motor de Backtest e Otimização (Walk-Forward)
│   ├── data_downloader.py # Downloader de dados da Binance
│   └── paper_trader.py    # Monitor de Spread/Slippage em tempo real
├── run_live.py            # Script principal para execução do BOT (Live/Testnet)
├── run_wfo.py             # Script para rodar as otimizações e pesquisas
└── MEMORY.md              # Histórico de desenvolvimento e Roadmap
```

## 🛠️ Como Usar

### 1. Instalação
Requer Python 3.10+
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt  # (Instalar dependências listadas abaixo)
# Dependências principais: ccxt, pandas, pandas_ta, numpy, scikit-learn
```

### 2. Configuração
Crie um arquivo `.env` na raiz com suas chaves da Binance:
```env
Binanceapikey=SUA_API_KEY
BinanceSecretkey=SUA_SECRET_KEY
```

### 3. Executar Backtest (Pesquisa)
Para testar novas ideias ou revalidar estratégias:
```bash
python run_wfo.py
```

### 4. Executar Bot (Live Trading)
Para iniciar a operação com a estratégia campeã:
```bash
python run_live.py
```
*O bot opera por padrão no modo Testnet (Sandbox). Para ir para produção, edite `run_live.py` e remova `exchange.set_sandbox_mode(True)`.*

## 🧠 Metodologia de Desenvolvimento

O projeto segue o ciclo **WFO (Walk-Forward Optimization)**:
1.  **Desenvolvimento:** Criar a lógica em `strategies/`.
2.  **Otimização (In-Sample):** Treinar parâmetros em janelas passadas.
3.  **Validação (Out-of-Sample):** Testar em dados "futuros" desconhecidos.
4.  **Benchmarking:** Comparar com Buy & Hold e descontar taxas reais.
5.  **Deploy:** Apenas estratégias com Alpha positivo vão para `run_live.py`.
