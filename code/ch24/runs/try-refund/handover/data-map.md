# Data map

## What the agent reads

| Column | Kind | Zone | Status |
|---|---|---|---|
| orders.customer | name | vendor | sent |
| orders.email | email | vendor | masked |
| orders.ship_to | address | vendor | sent |
| orders.note | email+phone | vendor | masked |
| payments.card | card | store | stays |
| tickets.body | phone | vendor | masked |

The full review is in [review.json](../review.json).
