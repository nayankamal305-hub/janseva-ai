from app.db import guard_test_database_url as _g; _g()
import subprocess, unittest, shutil, os
R = os.path.dirname(os.path.dirname(__file__))
@unittest.skipUnless(shutil.which("node"), "node missing")
class J(unittest.TestCase):
    def test_parse(self): self.assertEqual(subprocess.run(["node", "--check", R + "/app/static/app.js"]).returncode, 0)
    def test_smoke(self):
        r = subprocess.run(["node", R + "/tests/js/smoke.js", R + "/app/static/app.js"], capture_output=True, text=True); self.assertEqual(r.returncode, 0, r.stderr)
    def test_login_click(self):
        r = subprocess.run(["node", R + "/tests/js/login.js", R + "/app/static/app.js"], capture_output=True, text=True); self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
