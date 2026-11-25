import os
from pathlib import Path

def test_repo_secret_leak_scanner():
    """Scans the repository to ensure no default credentials, passwords, or known secrets leak into the codebase.
    Checks for:
    - 'setu123' (legacy demo owner password)
    - 'bharatsetu-msme-pithampur-secure-jwt-key-2026' (known public JWT key)
    - 'bharatsetu-dev-secret-key-change-in-production-2026' (known dev JWT key)
    - 'bharatsetu_verify_token' (legacy verify token default)
    - 'bharatsetu-phone-salt-2026' (legacy phone hash salt)

    Allowlist:
    - tests/test_secret_leak_scanner.py (this scanner definition)
    - backend/config.py (startup validation rejecting known forbidden secrets)
    """
    repo_root = Path(__file__).resolve().parent.parent

    # Split strings so scanner file itself does not inadvertently trigger match
    forbidden_strings = [
        "setu" + "123",
        "bharatsetu-msme-pithampur-secure-jwt-key-" + "2026",
        "bharatsetu-dev-secret-key-change-in-production-" + "2026",
        "bharatsetu_" + "verify_token",
        "bharatsetu-phone-" + "salt-2026",
    ]

    excluded_dirs = {
        ".git", "models", ".venv", "venv", "env", "node_modules",
        ".pytest_cache", ".playwright", "test-results", "__pycache__", ".yolo"
    }

    allowed_rel_paths = {
        "tests/test_secret_leak_scanner.py",
        "backend/config.py",
    }

    violations = []

    for root, dirs, files in os.walk(repo_root):
        # Exclude directories
        dirs[:] = [d for d in dirs if d not in excluded_dirs]

        for file_name in files:
            file_path = Path(root) / file_name
            rel_path = file_path.relative_to(repo_root).as_posix()

            if rel_path in allowed_rel_paths:
                continue

            # Skip binary files like images, models, sqlite databases
            if file_path.suffix.lower() in {".pt", ".onnx", ".png", ".jpg", ".jpeg", ".ico", ".db", ".sqlite", ".sqlite3", ".pyc"}:
                continue

            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            for forbidden in forbidden_strings:
                if forbidden in content:
                    lines = content.splitlines()
                    for idx, line in enumerate(lines, 1):
                        if forbidden in line:
                            violations.append(f"{rel_path}:{idx} -> found forbidden string '{forbidden}'")

    assert not violations, f"Secret leak violations found in repository:\n" + "\n".join(violations)
