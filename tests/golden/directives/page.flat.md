# Checkout

> **TL;DR:** Pay.

**Maven**

```sh
./mvnw test
```

**Gradle**

```sh
./gradlew test
```

- [Orders](orders.md): how orders flow
- [Billing](billing.md): invoices

1. Pick the items.
2. Pay.

**Why two retries**

The gateway times out under load.

Customers pay once; a failed payment can be retried.

`PaymentRetryJob` runs every minute.

```md
:::tabs
inside a fence stays as is
:::
```

:::warning
not a directive: stays
:::
