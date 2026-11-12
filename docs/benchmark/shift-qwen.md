# Ops shift: shift-qwen

Baseline `exp-mvs5snlt-c137` vs governed `exp-mvs5so3t-01fc`. 32 / 32 agents; each works a queue of ~10 tau2 customers in one context on a live database shared with its floor.

| | Governor off | Governor on |
|---|---|---|
| **Customers resolved** | 172/328 (52%) | 202/328 (62%) |
| Airline | 45/100 (45%) | 59/100 (59%) |
| Retail | 127/228 (56%) | 143/228 (63%) |
| Customers 1–3 | 54/96 (56%) | 66/96 (69%) |
| Customers 4–7 | 63/128 (49%) | 75/128 (59%) |
| Customers 8+ | 55/104 (53%) | 61/104 (59%) |
| Policy violations that took effect | 63 | 0 |
| Violations blocked | – | 94 |
| Customers handed to a human by the governor | – | 1 |
| Customers not reached (infra) | 0 | 0 |
| Model calls | 3717 | 4028 |
| Cost (OpenRouter, incl. customer simulator) | $9.81 | $12.03 |
| Infra errors | 0 | 3 |
