\# Price assumptions (simulation)



These prices are assumptions used for the FinOps simulation. They are not real

provider invoices. All components (gateway, ledger, dashboard, benchmark) must

use these same values.



| Model          | Role                          | USD per 1,000 tokens | USD per token |

|----------------|-------------------------------|----------------------|---------------|

| cheap-model    | Local Ollama model            | 0.0001               | 0.0000001     |

| strong-model   | Frontier cloud model (mock)   | 0.01                 | 0.00001       |



\## Savings formula



\- Cost without routing = every request sent to strong-model

\- Cost with routing = simple requests to cheap-model, complex to strong-model

\- Savings % = (cost without routing - cost with routing) / cost without routing

\- Target: more than 50%



\## Worked example (100 requests, 70 simple / 30 complex, 150 tokens each)



\- Without routing: 100 x 0.15 x 0.01 = 0.150 USD

\- With routing: 70 x 0.15 x 0.0001 + 30 x 0.15 x 0.01 = 0.04605 USD

\- Savings: about 69%

