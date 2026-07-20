from __future__ import annotations

import json
import unittest

from local_model_runtime_evaluation.credentials import Credential, CredentialError, CredentialState, FakeCredentialProvider


class CredentialBoundaryTest(unittest.TestCase):
    def test_credential_never_reveals_value_in_repr_or_status(self) -> None:
        secret = "stage1-test-secret-value"
        credential = Credential(secret)
        provider = FakeCredentialProvider(credential)
        self.assertEqual(provider.status(), CredentialState.PRESENT)
        self.assertNotIn(secret, repr(credential))
        self.assertNotIn(secret, json.dumps({"status": provider.status().value}))

    def test_missing_and_auth_failed_expose_only_state(self) -> None:
        self.assertEqual(FakeCredentialProvider(None).status(), CredentialState.MISSING)
        provider = FakeCredentialProvider(None, auth_failed=True)
        self.assertEqual(provider.status(), CredentialState.AUTH_FAILED)
        with self.assertRaises(CredentialError) as raised:
            provider.get()
        self.assertNotIn("secret", str(raised.exception).lower())

    def test_osaurus_access_key_shape(self) -> None:
        self.assertTrue(
            Credential("osk-v1.eyJpc3MiOiIxIn0.signature").looks_like_osaurus_access_key()
        )
        self.assertFalse(Credential("osk-v1.eyJpc3MiOiIxIn0").looks_like_osaurus_access_key())
        self.assertFalse(Credential("not-an-access-key").looks_like_osaurus_access_key())


if __name__ == "__main__":
    unittest.main()
