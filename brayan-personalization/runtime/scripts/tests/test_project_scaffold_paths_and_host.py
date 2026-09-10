#!/usr/bin/env python3
"""End-to-end invariants for project_scaffold path and host safety."""
from __future__ import annotations

import json
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "project_scaffold.py"
TEMPLATE_NAMES = (
    "project-workspace-status-template.md",
    "project-workspace-changelog-template.md",
    "project-workspace-closeout-template.md",
    "project-workspace-reopen-template.md",
)


class ProjectScaffoldPathsAndHostTests(unittest.TestCase):
    def _copy_templates(self, vault: Path) -> None:
        target = vault / "_meta" / "templates"
        target.mkdir(parents=True)
        for name in TEMPLATE_NAMES:
            (target / name).write_text(
                '---\nproject: "[[projects/{{slug}}/README]]"\n'
                'vault_project_path: "{{vault_project_path}}"\n'
                'workspace: "{{workspace}}"\nexecution_host: "{{execution_host}}"\n'
                'project_closeout_path: "{{project_closeout_path}}"\n---\n'
                '# {{Project Title}}\nNext review: {{next_review}}\n',
                encoding="utf-8",
            )

    def _write_project(
        self,
        project: Path,
        workspace: Path,
        *,
        execution_host: str | None,
        status: str = "seed",
    ) -> None:
        host_line = "" if execution_host is None else f"execution_host: {execution_host}\n"
        project.parent.mkdir(parents=True, exist_ok=True)
        project.write_text(
            """---
            title: Temporary CLI Project
            created: 2026-09-09
            updated: 2026-09-09
            type: project
            status: STATUS
            area: other
            priority: P1
            tags: [project]
            sources: []
            objective: Do the thing
            next_action: Review the thing
            success_criteria: [done]
            stop_condition: Stop when done
            review_cadence: 5d
            last_meaningful_update: 2026-09-09
            external_workspace: WORKSPACE
            HOST_LINE---
            # Temporary CLI Project
            """.replace("            ", "")
            .replace("STATUS", status)
            .replace("WORKSPACE", str(workspace))
            .replace("HOST_LINE", host_line),
            encoding="utf-8",
        )

    def _run_cli(self, *args: str) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertTrue(completed.stdout, completed.stderr)
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            self.fail(f"CLI did not emit JSON: {exc}\nstdout={completed.stdout}\nstderr={completed.stderr}")
        return completed, payload

    def _workspace_snapshot(self, root: Path) -> list[tuple[str, bool, bytes]]:
        snapshot: list[tuple[str, bool, bytes]] = []
        if not root.exists():
            return snapshot
        for path in sorted(root.rglob("*")):
            relative = path.relative_to(root).as_posix()
            if path.is_dir():
                snapshot.append((relative, True, b""))
            else:
                snapshot.append((relative, False, path.read_bytes()))
        return snapshot

    def test_cli_generates_all_workspace_files_with_resolved_values(self) -> None:
        host = socket.gethostname()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            vault = root / "vault"
            workspace_root = root / "workspace-root"
            project = vault / "projects" / "temporary-cli-project" / "README.md"
            workspace = workspace_root / "temporary-cli-project"
            self._copy_templates(vault)
            self._write_project(project, workspace, execution_host=host)

            commands = (
                ("--activate", "PROJECT_STATUS.md", "PROJECT_CHANGELOG.md"),
                ("--closeout", "PROJECT_CLOSEOUT.md"),
                ("--reopen", "PROJECT_REOPEN.md"),
            )
            for mode, *expected_files in commands:
                with self.subTest(mode=mode):
                    completed, payload = self._run_cli(
                        "--project",
                        str(project),
                        mode,
                        "--vault",
                        str(vault),
                        "--workspace-root",
                        str(workspace_root),
                        "--force",
                    )
                    self.assertEqual(completed.returncode, 0, completed.stderr)
                    self.assertEqual(payload["errors"], [])
                    for filename in expected_files:
                        generated = workspace / filename
                        self.assertTrue(generated.exists(), generated)
                        content = generated.read_text(encoding="utf-8")
                        self.assertNotRegex(content, r"\{\{[^{}]+\}\}")
                        self.assertIn(f'vault_project_path: "{project.resolve()}"', content)
                        self.assertIn(f'workspace: "{workspace.resolve()}"', content)
                        self.assertIn(f'execution_host: "{host}"', content)
                        if filename == "PROJECT_CLOSEOUT.md":
                            self.assertIn(
                                f'project_closeout_path: "{project.with_name("closeout.md").resolve()}"',
                                content,
                            )

    def test_template_failure_leaves_project_and_workspace_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            vault = root / "vault"
            workspace_root = root / "workspaces"
            project = vault / "projects" / "fixture" / "README.md"
            workspace = workspace_root / "fixture"
            self._copy_templates(vault)
            self._write_project(project, workspace, execution_host=socket.gethostname())
            bad_template = vault / "_meta/templates/project-workspace-changelog-template.md"
            bad_template.write_text(bad_template.read_text() + "\n{{unmapped_field}}\n")
            before = project.read_bytes()
            completed, payload = self._run_cli(
                "--project", str(project), "--activate", "--vault", str(vault),
                "--workspace-root", str(workspace_root),
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertTrue(payload["errors"])
            self.assertEqual(project.read_bytes(), before)
            self.assertFalse(workspace_root.exists())

    def test_refused_host_modes_leave_project_and_workspace_unchanged(self) -> None:
        actual_host = socket.gethostname()
        for host_kind, recorded_host in (
            ("foreign", actual_host + "-foreign"),
            ("unknown", "unknown"),
            ("missing", None),
        ):
            for mode in ("--activate", "--closeout", "--reopen", "--all-active"):
                with self.subTest(host_kind=host_kind, mode=mode):
                    with tempfile.TemporaryDirectory() as temporary:
                        root = Path(temporary)
                        vault = root / "vault"
                        workspace_root = root / "workspace-root"
                        project = vault / "projects" / "temporary-cli-project" / "README.md"
                        workspace = workspace_root / "temporary-cli-project"
                        self._copy_templates(vault)
                        self._write_project(
                            project,
                            workspace,
                            execution_host=recorded_host,
                            status="active",
                        )
                        workspace.mkdir(parents=True)
                        (workspace / "sentinel.txt").write_bytes(b"do not touch")
                        project_before = project.read_bytes()
                        workspace_before = self._workspace_snapshot(workspace_root)

                        arguments = [
                            mode,
                            "--vault",
                            str(vault),
                            "--workspace-root",
                            str(workspace_root),
                        ]
                        if mode != "--all-active":
                            arguments[1:1] = ["--project", str(project)]
                        completed, payload = self._run_cli(*arguments)

                        self.assertNotEqual(completed.returncode, 0, payload)
                        self.assertTrue(payload["errors"], payload)
                        self.assertEqual(payload["would_create"], [])
                        self.assertEqual(project.read_bytes(), project_before)
                        self.assertEqual(self._workspace_snapshot(workspace_root), workspace_before)

                        if host_kind == "foreign" and mode == "--activate":
                            dry_completed, dry_payload = self._run_cli(*arguments, "--dry-run")
                            self.assertNotEqual(dry_completed.returncode, 0, dry_payload)
                            self.assertTrue(dry_payload["errors"], dry_payload)
                            self.assertEqual(dry_payload["would_create"], [])
                            self.assertEqual(project.read_bytes(), project_before)
                            self.assertEqual(self._workspace_snapshot(workspace_root), workspace_before)

        self.assertNotEqual(actual_host, "")


if __name__ == "__main__":
    unittest.main()
