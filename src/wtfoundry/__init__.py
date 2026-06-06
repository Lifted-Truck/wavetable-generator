"""wtfoundry — a diversity-seeking, oracle-validated wavetable generator.

The public entry point is the control surface (the "lever set") defined in
``wtfoundry.api``. The CLI, the MCP server (run 2), and any future GUI are thin
skins over it, so their behavior cannot diverge.

    from wtfoundry import foundry
    foundry.generate(...)

Everything below the lever set — the generators, the oracle, and the single
validated write path — is reachable only through it, so no client can bypass
quality control.
"""

from wtfoundry.api import foundry

__all__ = ["foundry"]
__version__ = "0.0.1"
