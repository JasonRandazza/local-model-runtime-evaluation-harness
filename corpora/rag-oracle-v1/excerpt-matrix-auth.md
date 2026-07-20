# Matrix Keychain excerpt

Pinned excerpt from the matrix operator guide for Osaurus credentials.

Store the Osaurus access key in Keychain with account `benchmark-harness` and service `local.jrazz.lmre.osaurus`:

```bash
/usr/bin/security add-generic-password \
  -a benchmark-harness \
  -s local.jrazz.lmre.osaurus \
  -l "LMRE Osaurus Matrix" \
  -U -w
```

Confirm with a local inventory probe (must return HTTP 200).
