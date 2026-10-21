# Checkout

> **TL;DR:** Pay.

:::tabs
::tab Maven
```sh
./mvnw test
```
::tab Gradle
```sh
./gradlew test
```
:::

:::cards
- [Orders](orders.md): how orders flow
- [Billing](billing.md): invoices
:::

:::steps
1. Pick the items.
2. Pay.
:::

:::details Why two retries
The gateway times out under load.
:::

:::business
Customers pay once; a failed payment can be retried.
:::

:::tech
`PaymentRetryJob` runs every minute.
:::

```md
:::tabs
inside a fence stays as is
:::
```

:::warning
not a directive: stays
:::
