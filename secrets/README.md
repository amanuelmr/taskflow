# Secrets

This directory holds the RS256 keypair used to sign and verify JWTs.
The `.pem` files are **gitignored** — generate them locally:

```bash
openssl genrsa -out secrets/jwt_private.pem 2048
openssl rsa -in secrets/jwt_private.pem -pubout -out secrets/jwt_public.pem
```

- `jwt_private.pem` — mounted **only** into `user_service` (the token issuer).
- `jwt_public.pem` — mounted into every service that verifies tokens
  (`task_service`, `notification_service`, and `user_service` itself).

Never commit private keys. If a key is ever committed, treat it as
compromised: rotate it and force all users to re-authenticate.
