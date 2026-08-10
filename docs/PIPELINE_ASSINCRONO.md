# Diagrama do Pipeline Oficial (Operação Assíncrona 4M&C)

> [!NOTE]
> Este diagrama ilustra como o Base Antigravity processa as burocracias de forma invisível e paralela, enquanto a equipe física (técnicos/expedição) já adianta o trabalho braçal usando o Kanban.

```mermaid
graph TD
    %% Nós principais de entrada
    A([Venda Mercado Livre]) --> B[BaseLucas: Fila 'Novos pedidos']

    %% Separação dos Caminhos Paralelos
    B -->|Automático (Background)| C{Macro Fiscal}
    B -->|Manual (UI/Kanban)| D{Filas de Produção}

    %% Caminho Burocrático / Fiscal (API)
    subgraph Fluxo Sistêmico e Fiscal (Automático)
        C -->|Gera Pedido de Venda| E[(Bling ERP)]
        E -.->|Pode demorar minutos ou horas| F[NF-e Autorizada]
        F -->|Sistema detecta a Nota| G{Macro Logística}
        G -->|Destrava Etiqueta IMEDIATAMENTE| H[ZPL Mercado Envios Disponível]
    end

    %% Caminho Físico / Braçal (Oficina)
    subgraph Fluxo Físico e Kanban (Manual)
        D -->|Arrastado na UI| I[Fila Técnico / Montagem]
        I -->|Trabalha SEM ESPERAR a Nota| J[Fila Pacote / Embalagem]
        J -->|Caixa Pronta p/ Etiqueta| K[Caixa na Bancada de Expedição]
    end

    %% Ponto de Convergência Final
    H ==> L(Convergência: Caixa + Nota)
    K ==> L
    
    L -->|Bipagem Final| M[Etiqueta Impressa e Colada na Hora]
    M --> N(((Fila: Transporte / Despachado)))

    %% Estilização para facilitar a leitura
    style A fill:#FFE600,stroke:#333,color:#333,stroke-width:2px
    style B fill:#1e293b,stroke:#38bdf8,stroke-width:2px,color:#fff
    style E fill:#00C7B1,stroke:#000,color:#fff
    style N fill:#10B981,stroke:#000,color:#fff
    style L fill:#F59E0B,stroke:#000,color:#fff
    style H fill:#3b82f6,stroke:#000,color:#fff
```

## Como ler este diagrama (O Segredo da Velocidade):
1. **Trabalho 100% Desbloqueado:** O técnico **não precisa** da Nota Fiscal para saber qual peça pegar, montar e embalar. Assim que a venda cai, a equipe física já bota a mão na massa através do Kanban na tela.
2. **Impressão Imediata:** A caixa pode ficar ali pronta na bancada por 5 minutos ou por 2 horas. No **exato segundo** em que a Sefaz/Bling aprovar a NF-e nos bastidores, o sistema puxa o XML e destrava o botão. Quando o expedidor passar o leitor de código de barras (bipar) na caixa pronta, a etiqueta ZPL sai da impressora instantaneamente.
