# Ops shift: shift-haiku

Baseline `exp-mvs5soni-3f12` vs governed `exp-mvs5sp6t-51b8`. 32 / 32 agents; each works a queue of ~10 tau2 customers in one context on a live database shared with its floor.

| | Governor off | Governor on |
|---|---|---|
| **Customers resolved** | 272/328 (83%) | 272/328 (83%) |
| Airline | 82/100 (82%) | 81/100 (81%) |
| Retail | 190/228 (83%) | 191/228 (84%) |
| Customers 1–3 | 78/96 (81%) | 80/96 (83%) |
| Customers 4–7 | 104/128 (81%) | 105/128 (82%) |
| Customers 8+ | 90/104 (87%) | 87/104 (84%) |
| Policy violations that took effect | 0 | 0 |
| Violations blocked | – | 4 |
| Customers handed to a human by the governor | – | 0 |
| Customers not reached (infra) | 0 | 0 |
| Model calls | 2846 | 2889 |
| Cost (OpenRouter, incl. customer simulator) | $2.09 | $2.09 |
| Infra errors | 0 | 0 |
