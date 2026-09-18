import unittest
from pathlib import Path


UI = Path(__file__).resolve().parents[1] / "web" / "index.html"


class CreativeStudioAutopilotUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = UI.read_text(encoding="utf-8")

    def test_primary_surface_is_brief_first(self):
        self.assertIn("Describe the outcome.", self.html)
        self.assertIn('id="prompt"', self.html)
        self.assertIn("Create finished options", self.html)
        self.assertNotIn('id="sourceJson" spellcheck="false">{', self.html.split("<details class=\"advanced\"", 1)[0])

    def test_autopilot_exposes_hyperframes_lifecycle(self):
        for label in ("PLAN", "BUILD", "RENDER", "DELIVER"):
            self.assertIn(label, self.html)
        self.assertIn("Composing HyperFrames", self.html)
        self.assertIn("postRun(run.run_id,'approve')", self.html)
        self.assertIn("postRun(run.run_id,'render'", self.html)
        self.assertIn("postRun(run.run_id,'export')", self.html)

    def test_operator_controls_remain_behind_explicit_boundaries(self):
        self.assertIn("OpenRouter (explicit approval required)", self.html)
        self.assertIn("External effects", self.html)
        self.assertIn("Publishing remains a separate approved action", self.html)


if __name__ == "__main__":
    unittest.main()
