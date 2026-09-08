import io
import sys
import unittest

from glchat_backend import pretty_log


class PrettyLogEncodingTests(unittest.TestCase):
    def test_logging_does_not_fail_on_cp1252_console(self):
        raw = io.BytesIO()
        console = io.TextIOWrapper(raw, encoding="cp1252", errors="strict")
        original_stdout = sys.stdout
        sys.stdout = console
        try:
            pretty_log.banner("SSO token", subtitle="validate → mint")
            pretty_log.sdk("validate signature", "forged assertion", ok=False)
            pretty_log.app("nonce claimed")
            pretty_log.warn("rate limited")
            pretty_log.err("signature rejected")
            pretty_log.done("request handled")
            pretty_log.divider()
            console.flush()
        finally:
            sys.stdout = original_stdout

        self.assertTrue(raw.getvalue())


if __name__ == "__main__":
    unittest.main()
