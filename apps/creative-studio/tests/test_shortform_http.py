"""Bounded HTTP preflight: read-only response, no run creation or external effects."""
import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import app  # noqa: E402


class ShortformHttpTests(unittest.TestCase):
    def test_shortform_preflight_endpoint_does_not_write_run(self):
        with tempfile.TemporaryDirectory() as temp:
            old_runs = app.RUNS_ROOT
            app.RUNS_ROOT = Path(temp) / 'runs'
            server = app.ThreadingHTTPServer(('127.0.0.1', 0), app.StudioHandler)
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            base = f'http://127.0.0.1:{server.server_address[1]}'
            fixture = {
                'creative_id': 'EL-P01-PARENT-A', 'lane': 'Efficient Labs parent brand',
                'variation': 'A', 'hook_style': 'contradiction', 'first_frame_hook': 'WHAT PASSED?',
                'common_script': 'Proof needs an exact source.', 'cta': 'Follow for verified examples.',
                'objective': 'Educate', 'format': 'Motion graphics', 'state': 'SCRIPT_DRAFT',
                'render_status': 'SCRIPT_DRAFT', 'publish_status': 'BLOCKED_PENDING_REVIEW',
                'media_generation_jobs': [], 'published_urls': [], 'production_expenses_usd': 0,
                'approved_utm_destination': 'NOT_SET', 'source_references': ['source:A'],
                'original_art_assets_needed': ['Original text graphics'], 'hard_blockers': ['Owner review'],
            }
            try:
                def post(payload):
                    req = urllib.request.Request(
                        base + '/api/shortform/preflight', data=json.dumps(payload).encode('utf-8'),
                        headers={'Content-Type': 'application/json'}, method='POST',
                    )
                    return urllib.request.urlopen(req, timeout=4)

                with post({'creative': fixture}) as response:
                    self.assertEqual(response.status, 200)
                    body = json.loads(response.read())
                self.assertEqual(body['status'], 'DRAFT_NEEDS_REVIEW')
                self.assertEqual(body['external_effects'], 'NOT_ATTEMPTED')
                self.assertEqual(body['publishing'], 'DISABLED')
                self.assertFalse(app.RUNS_ROOT.exists())
                fixture['lane'] = 'Fake future client'
                with self.assertRaises(urllib.error.HTTPError) as bad:
                    post({'creative': fixture})
                self.assertEqual(bad.exception.code, 400)
                self.assertFalse(app.RUNS_ROOT.exists())
            finally:
                server.shutdown()
                server.server_close()
                worker.join(timeout=5)
                app.RUNS_ROOT = old_runs


if __name__ == '__main__':
    unittest.main()
