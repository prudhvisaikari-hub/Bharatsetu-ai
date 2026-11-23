from unittest.mock import patch, MagicMock
from backend import orchestrator
from backend.store import get_msme_audit

def test_claude_tool_loop_and_fallback():
    # 1. Test fallback when Anthropic API fails
    with patch("backend.config.ANTHROPIC_API_KEY", "sk-ant-test-key"):
        with patch("anthropic.Anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_anthropic.return_value = mock_client
            mock_client.messages.create.side_effect = Exception("Anthropic 401 Unauthorized")

            res = orchestrator.chat("session_fallback", "carbon report for export")
            assert "Carbon draft" in res["reply"]
            assert "Energy Agent" in res["trace"]
            # Check fallback audit logged
            audits = get_msme_audit("demo", limit=5)
            assert any("Claude unavailable" in a["action"] for a in audits)

    # 2. Test successful tool loop iteration
    with patch("backend.config.ANTHROPIC_API_KEY", "sk-ant-test-key"):
        with patch("anthropic.Anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_anthropic.return_value = mock_client

            # Step 1: Claude decides to call carbon_report tool
            block_tool = MagicMock()
            block_tool.type = "tool_use"
            block_tool.name = "carbon_report"
            block_tool.id = "toolu_01"
            block_tool.input = {}

            res_step1 = MagicMock()
            res_step1.stop_reason = "tool_use"
            res_step1.content = [block_tool]

            # Step 2: Claude answers using tool results
            block_text = MagicMock()
            block_text.type = "text"
            block_text.text = "Based on your smart meter, your monthly Scope 2 emissions are 13.06 tCO2e."

            res_step2 = MagicMock()
            res_step2.stop_reason = "end_turn"
            res_step2.content = [block_text]

            mock_client.messages.create.side_effect = [res_step1, res_step2]

            res = orchestrator.chat("session_tool_test", "I need a carbon report")
            assert "13.06 tCO2e" in res["reply"]
            assert "Energy Agent" in res["trace"]
