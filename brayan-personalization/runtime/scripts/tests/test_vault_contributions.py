#!/usr/bin/env python3
"""TDD invariants for isolated vault contributions and snapshots."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest import TestCase, mock

SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))
import vault_contributions as vc  # noqa: E402


class VaultContributionsTests(TestCase):
    def _git(self, cwd: Path, *args: str) -> str:
        completed = subprocess.run(
            ["git", *args], cwd=cwd, text=True, capture_output=True, check=True
        )
        return completed.stdout.strip()

    def _repo(self, root: Path) -> tuple[Path, str]:
        repo = root / "repo"
        repo.mkdir()
        self._git(repo, "init", "--initial-branch=main")
        self._git(repo, "config", "user.email", "test@example.invalid")
        self._git(repo, "config", "user.name", "Test User")
        (repo / "canonical.md").write_text("first\n", encoding="utf-8")
        self._git(repo, "add", "canonical.md")
        self._git(repo, "commit", "-m", "initial")
        return repo, self._git(repo, "rev-parse", "HEAD")

    def _contract(self, root: Path, repo: Path) -> dict[str, str]:
        return {
            "version": 1,
            "hostname": "DarkArmy",
            "role": "contributor",
            "owner_hostname": "Calcifer",
            "hermes_home": str(root / ".hermes"),
            "vault_path": str(root / "personal-vault"),
            "repo_path": str(repo),
            "state_dir": str(root / ".hermes" / "vault-ownership"),
            "snapshot_root": str(root / ".hermes" / "vault-ownership" / "snapshots"),
            "contribution_root": str(root / ".hermes" / "vault-ownership" / "contributions"),
            "repository": "example/personal-vault",
            "remote": "file:///tmp/personal-vault.git",
            "branch": "main",
            "maintenance_branch": "brayan/darkarmy-vault-ownership",
        }

    def test_publish_snapshot_is_read_only_and_keeps_each_sha(self) -> None:
        with self.subTest("immutable snapshots and atomic current link"):
            with __import__("tempfile").TemporaryDirectory() as temporary:
                root = Path(temporary)
                repo, first_sha = self._repo(root)
                contract = self._contract(root, repo)
                first = vc.publish_snapshot(contract, repo, first_sha)
                current = Path(contract["vault_path"])
                self.assertTrue(current.is_symlink())
                self.assertEqual(current.resolve(), first.resolve())
                self.assertEqual((first / "canonical.md").read_text(), "first\n")
                self.assertFalse((first / "canonical.md").stat().st_mode & 0o222)

                (repo / "canonical.md").write_text("second\n", encoding="utf-8")
                self._git(repo, "add", "canonical.md")
                self._git(repo, "commit", "-m", "second")
                second_sha = self._git(repo, "rev-parse", "HEAD")
                second = vc.publish_snapshot(contract, repo, second_sha)
                self.assertEqual(current.resolve(), second.resolve())
                self.assertTrue(first.exists(), "old snapshots are retained")
                self.assertEqual((first / "canonical.md").read_text(), "first\n")

    def test_refresh_network_failure_keeps_current_snapshot_and_legacy_directory(self) -> None:
        with __import__("tempfile").TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo, first_sha = self._repo(root)
            contract = self._contract(root, repo)
            vc.publish_snapshot(contract, repo, first_sha)
            current = Path(contract["vault_path"])
            before = current.readlink()

            def fail_fetch(*args, **kwargs):
                raise vc.CommandError("git fetch failed")

            with self.assertRaises(vc.CommandError):
                vc.refresh_snapshot(contract, runner=fail_fetch)
            self.assertEqual(current.readlink(), before)

            legacy = root / "legacy-vault"
            legacy.mkdir()
            sentinel = legacy / "do-not-move.txt"
            sentinel.write_text("preserve", encoding="utf-8")
            contract["vault_path"] = str(legacy)
            with self.assertRaises(vc.ContributionError):
                vc.publish_snapshot(contract, repo, first_sha)
            self.assertEqual(sentinel.read_text(), "preserve")
            self.assertTrue(legacy.is_dir())

    def test_start_worktree_records_exact_scope_and_does_not_move_old_vault(self) -> None:
        with __import__("tempfile").TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo, _ = self._repo(root)
            legacy = root / "personal-vault"
            legacy.mkdir()
            sentinel = legacy / "old-edit.md"
            sentinel.write_text("keep", encoding="utf-8")
            contract = self._contract(root, repo)
            work = vc.start_contribution(
                contract,
                session="chat-42",
                intent="Update the canonical note",
                canonical_record="canonical.md",
                evidence_path="canonical.md",
                scope=["canonical.md"],
            )
            metadata = json.loads((work / vc.METADATA_NAME).read_text(encoding="utf-8"))
            self.assertEqual(metadata["host"], contract["hostname"])
            self.assertEqual(metadata["session"], "chat-42")
            self.assertEqual(metadata["base"], self._git(repo, "rev-parse", "HEAD"))
            self.assertEqual(metadata["intent"], "Update the canonical note")
            self.assertEqual(metadata["canonical_record"], "canonical.md")
            self.assertEqual(metadata["evidence_path"], "canonical.md")
            self.assertEqual(metadata["scope"], ["canonical.md"])
            self.assertEqual(sentinel.read_text(), "keep")
            self.assertTrue(work.joinpath(".git").exists())
            self.assertIn("chat-42", metadata["branch"])

    def test_parse_review_requires_strict_json_and_exact_commit_fields(self) -> None:
        approved = {
            "decision": "approve",
            "rationale": "The scoped canonical update is supported by the evidence.",
            "head_sha": "a" * 40,
            "base_sha": "b" * 40,
            "evidence": [{"path": "canonical.md", "sha256": "c" * 64}],
        }
        parsed = vc.parse_review_response(json.dumps(approved))
        self.assertEqual(parsed, approved)
        with self.assertRaises(vc.ReviewError):
            vc.parse_review_response("```json\n" + json.dumps(approved) + "\n```")
        malformed = dict(approved)
        malformed["extra"] = True
        with self.assertRaises(vc.ReviewError):
            vc.parse_review_response(json.dumps(malformed))
        changed_head = dict(approved, head_sha="d" * 40)
        with self.assertRaises(vc.ReviewError):
            vc.validate_review(changed_head, head_sha="a" * 40, base_sha="b" * 40, files=[])

    def test_review_scope_rejects_raw_deletion_sensitive_paths_and_conflicts(self) -> None:
        review = {
            "decision": "approve",
            "rationale": "supported",
            "head_sha": "a" * 40,
            "base_sha": "b" * 40,
            "evidence": [],
        }
        cases = [
            ([{"path": "raw/source.md", "status": "deleted"}], "raw deletion"),
            ([{"path": "profile/private.md", "status": "modified"}], "profile"),
            ([{"path": "canonical.md", "status": "modified"}], "conflict"),
        ]
        for files, label in cases:
            with self.subTest(label=label):
                with self.assertRaises(vc.ReviewError):
                    vc.validate_review(
                        review,
                        head_sha="a" * 40,
                        base_sha="b" * 40,
                        files=files,
                        allowed_paths=["canonical.md"],
                        merge_state="CONFLICTING" if label == "conflict" else "CLEAN",
                    )

    def test_owner_snapshot_does_not_replace_canonical_and_pin_is_stable(self):
        import tempfile
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo, sha = self._repo(root)
            contract = self._contract(root, repo)
            contract.update(role="owner", vault_path=str(repo))
            self.assertTrue(hasattr(vc, "ensure_snapshot"), "owner snapshot API missing")
            snapshot = vc.ensure_snapshot(contract, sha)
            self.assertTrue((repo / ".git").is_dir())
            self.assertFalse(repo.is_symlink())
            first = vc.pin_snapshot(contract, "reader", sha)
            (repo / "canonical.md").write_text("second", encoding="utf-8")
            self._git(repo, "commit", "-am", "second")
            next_sha = self._git(repo, "rev-parse", "HEAD")
            vc.ensure_snapshot(contract, next_sha)
            self.assertEqual(vc.pin_snapshot(contract, "reader")["sha"], first["sha"])
            self.assertEqual((snapshot / "canonical.md").read_text(encoding="utf-8"), "first\n")
            with self.assertRaises(vc.ContributionError):
                vc.pin_snapshot(contract, "reader", next_sha)

    def test_review_object_ids_must_be_complete_and_literal(self):
        for invalid in ["abcdef0", "A" * 40, "a" * 39, "a" * 41]:
            with self.subTest(invalid=invalid), self.assertRaises(vc.ContributionError):
                vc._sha(invalid)

    def test_complete_review_integration_uses_pinned_git_and_atomic_base(self):
        import tempfile, socket, base64
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo, base_sha = self._repo(root)
            remote = root / "remote.git"
            self._git(root, "clone", "--bare", str(repo), str(remote))
            self._git(repo, "remote", "add", "origin", str(remote))
            self._git(repo, "fetch", "origin")
            self._git(repo, "checkout", "-b", "vault/author/task")
            (repo / "canonical.md").write_text("second\n", encoding="utf-8")
            self._git(repo, "commit", "-am", "scoped change")
            head = self._git(repo, "rev-parse", "HEAD")
            self._git(repo, "push", "origin", "HEAD:refs/pull/1/head")
            self._git(repo, "checkout", "main")
            contract = self._contract(root, repo)
            contract.update(role="owner", hostname=socket.gethostname(), owner_hostname=socket.gethostname(), vault_path=str(repo), remote=str(remote))
            metadata = dict(host="author", session="task", intent="Update note with evidence", base=base_sha,
                canonical_record="canonical.md", evidence_path="canonical.md", scope=["canonical.md"])
            body = "<!-- vault-contribution-metadata\n" + json.dumps(metadata) + "\n-->"
            info = dict(number=1, url="https://github.com/example/personal-vault/pull/1", body=body,
                headRefOid=head, baseRefOid=base_sha, baseRefName="main", headRefName="vault/author/task", mergeStateStatus="CLEAN", state="OPEN", files=[])
            calls = []
            def external(argv, **kwargs):
                calls.append(argv)
                if argv[0] == "git":
                    return vc._run(argv, **kwargs)
                if argv[:3] == ["gh", "pr", "view"]:
                    if "comments" in argv:
                        return subprocess.CompletedProcess(argv, 0, json.dumps({"comments": [{"body": comment_bodies[-1]}]}), "")
                    return subprocess.CompletedProcess(argv, 0, json.dumps(info), "")
                if argv[0] == "claude":
                    evidence_hash = __import__('hashlib').sha256(b"first\n").hexdigest()
                    answer = dict(decision="approve", rationale="Supported scoped note update", head_sha=head, base_sha=base_sha,
                                  evidence=[dict(path="canonical.md", sha256=evidence_hash)])
                    output = json.dumps({"type":"result", "subtype":"success", "is_error":False, "result":json.dumps(answer)}) + "\n"
                    if sum(c[0] == "claude" for c in calls) == 1:
                        output = "malformed reviewer response\n"
                    if kwargs.get("stdout"):
                        kwargs["stdout"].write(output)
                        output = None
                    return subprocess.CompletedProcess(argv, 0, output, "")
                if argv[:3] == ["gh", "pr", "comment"]:
                    comment_bodies.append(argv[-1])
                    return subprocess.CompletedProcess(argv, 0, "https://example.invalid/comment", "")
                if argv[:3] == ["gh", "pr", "close"]:
                    info["state"] = "CLOSED"
                    return subprocess.CompletedProcess(argv, 0, "closed", "")
                self.fail(f"unexpected external operation: {argv[:3]}")
            comment_bodies = []
            with mock.patch.object(vc,"read_pinned_evidence",side_effect=vc.ReviewError("unsupported evidence")):
                with self.assertRaises(vc.ReviewError):
                    vc.review_contribution(contract,1,pin_session="failed-review",runner=external)
            self.assertFalse(vc._pin_path(contract,"failed-review").exists(),"failed review leaked pin")
            result = vc.review_contribution(contract, 1, pin_session="review-1", runner=external)
            self.assertEqual(result["review"]["decision"], "approve")
            self.assertTrue(any(c[:3]==["gh","pr","view"] and "comments" in c for c in calls),"PR comment must be read back")
            receipt_path = Path(result["receipt"])
            approved_receipt = receipt_path.read_bytes()
            for field in ["head_sha", "base_sha"]:
                bad = json.loads(approved_receipt)
                bad["review"][field] = "f" * 40
                receipt_path.write_text(json.dumps(bad), encoding="utf-8")
                with self.subTest(stale=field), self.assertRaises(vc.ReviewError):
                    vc.integrate_contribution(contract, 1, runner=external)
                self.assertEqual(self._git(repo, "rev-parse", "HEAD"), base_sha)
            receipt_path.write_bytes(approved_receipt)
            marker = Path(contract["state_dir"]) / "pending-owner.json"
            marker.write_text('{"intent":"other interrupted writer"}', encoding="utf-8")
            with self.assertRaises(vc.ReviewError):
                vc.integrate_contribution(contract, 1, runner=external)
            marker.unlink()
            comment_bodies.clear()
            integrated = vc.integrate_contribution(contract, 1, runner=external)
            self.assertEqual((repo / "canonical.md").read_text(encoding="utf-8"), "second\n")
            self.assertEqual(self._git(repo, "rev-parse", "HEAD"), integrated["sha"])
            self.assertFalse(repo.is_symlink())
            self.assertFalse(any(c[:3] == ["gh", "pr", "diff"] for c in calls), "diff must be SHA-pinned Git data")
            self.assertFalse(any(arg in {"--force", "--force-with-lease"} for c in calls for arg in c))
            self.assertTrue(comment_bodies)
            pushes = [c for c in calls if c[:2] == ["git", "push"]]
            self.assertEqual(pushes, [["git", "push", f"--force-with-lease=refs/heads/main:{base_sha}", "origin", f"{head}:refs/heads/main"]])

    def test_routine_policy_rejects_raw_modification_and_governance(self):
        review = dict(decision="approve", rationale="supported", head_sha="a"*40, base_sha="b"*40, evidence=[])
        for name in ["raw/notes/source.md", "_meta/schema.md", "_meta/workflows/owner.md", ".github/workflows/exfiltrate.yml"]:
            with self.subTest(path=name), self.assertRaises(vc.ReviewError):
                vc.validate_review(review, head_sha="a"*40, base_sha="b"*40,
                    files=[{"path":name,"status":"modified"}], allowed_paths=[name])

    def test_reused_snapshot_detects_changed_bytes(self):
        import tempfile
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo, sha = self._repo(root)
            contract = self._contract(root, repo)
            snapshot = vc.publish_snapshot(contract, repo, sha)
            note = snapshot / "canonical.md"
            note.chmod(0o644)
            note.write_text("unexpected mutation", encoding="utf-8")
            with self.assertRaises(vc.ContributionError):
                vc.ensure_snapshot(contract, sha)

    def test_snapshot_gc_retains_current_and_explicit_pins(self):
        import tempfile
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo, first = self._repo(root)
            contract = self._contract(root, repo)
            vc.publish_snapshot(contract, repo, first)
            vc.pin_snapshot(contract, "active-reader", first)
            for number in range(4):
                (repo / "canonical.md").write_text(str(number), encoding="utf-8")
                self._git(repo, "commit", "-am", f"revision {number}")
                vc.publish_snapshot(contract, repo, self._git(repo, "rev-parse", "HEAD"))
            self.assertTrue(hasattr(vc, "prune_snapshots"), "bounded snapshot retention missing")
            result = vc.prune_snapshots(contract, keep=2)
            self.assertTrue((Path(contract["snapshot_root"]) / first).is_dir())
            self.assertTrue(Path(contract["vault_path"]).resolve().is_dir())
            self.assertEqual(len(result["removed"]), 2)

    def test_pending_processor_integrates_and_does_not_repeat_rejections(self):
        import tempfile, socket
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo, sha = self._repo(root)
            contract = self._contract(root, repo)
            contract.update(role="owner", hostname=socket.gethostname(), owner_hostname=socket.gethostname())
            info = dict(number=4, headRefOid=sha, headRefName="vault/author/task", body="source metadata")
            self.assertTrue(hasattr(vc, "process_pending_reviews"), "automatic integration poller missing")
            with mock.patch.object(vc, "list_pending_reviews", return_value=[info]), mock.patch.object(vc, "review_contribution", side_effect=vc.ReviewError("sensitive update")) as review:
                first = vc.process_pending_reviews(contract)
                second = vc.process_pending_reviews(contract)
                self.assertEqual(review.call_count, 1)
                self.assertEqual(first["processed"][0]["status"], "needs-review")
                self.assertEqual(second["processed"], [])
            vc._review_receipt_path(contract, 4).unlink()
            with mock.patch.object(vc, "list_pending_reviews", return_value=[info]), mock.patch.object(vc, "review_contribution", return_value={"review":{"decision":"approve"}}), mock.patch.object(vc, "integrate_contribution", return_value={"sha":sha}) as integrate:
                result = vc.process_pending_reviews(contract)
                self.assertEqual(integrate.call_count, 1)
                self.assertEqual(result["processed"][0]["status"], "integrated")

    def test_transient_review_failure_is_retried_without_rejection_receipt(self):
        import tempfile, socket
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            repo,sha=self._repo(root)
            contract=self._contract(root,repo)
            contract.update(role="owner",hostname=socket.gethostname(),owner_hostname=socket.gethostname())
            info=dict(number=4,headRefOid=sha,headRefName="vault/author/task",body="source metadata")
            with mock.patch.object(vc,"list_pending_reviews",return_value=[info]), mock.patch.object(vc,"review_contribution",side_effect=vc.CommandError("temporary network failure")) as review:
                for _ in range(2):
                    result=vc.process_pending_reviews(contract)
                    self.assertEqual(result["processed"][0]["status"],"transient-error")
                    self.assertFalse(vc._review_receipt_path(contract,4).exists())
                self.assertEqual(review.call_count,2)

    def test_busy_owner_returns_json_and_poller_retries(self):
        import io, tempfile, socket
        from contextlib import redirect_stdout
        from vault_ownership_common import OwnershipBusy
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);repo,sha=self._repo(root);contract=self._contract(root,repo)
            contract.update(role="owner",hostname=socket.gethostname(),owner_hostname=socket.gethostname())
            info=dict(number=4,headRefOid=sha,headRefName="vault/author/task",body="source metadata")
            with mock.patch.object(vc,"list_pending_reviews",return_value=[info]), mock.patch.object(vc,"review_contribution",side_effect=OwnershipBusy("busy")):
                self.assertEqual(vc.process_pending_reviews(contract)["processed"][0]["status"],"transient-error")
            output=io.StringIO()
            with mock.patch.object(vc,"load_contract",return_value=contract),mock.patch.object(vc,"process_pending_reviews",side_effect=OwnershipBusy("busy")),redirect_stdout(output):
                self.assertEqual(vc.main(["tick"]),1)
            self.assertEqual(json.loads(output.getvalue())["error"],"busy")

    def test_unknown_merge_state_is_transient_not_artifact_rejection(self):
        review=dict(decision="approve",rationale="supported",head_sha="a"*40,base_sha="b"*40,evidence=[])
        try:
            vc.validate_review(review,head_sha="a"*40,base_sha="b"*40,files=[],merge_state="UNKNOWN")
        except vc.ContributionError as error:
            self.assertNotIsInstance(error,vc.ReviewError)
        else:
            self.fail("UNKNOWN must defer")

    def test_remote_identity_must_match_private_repository(self):
        import tempfile
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);repo,_=self._repo(root);contract=self._contract(root,repo)
            contract["remote"]="git@github.com:unrelated/public.git"
            work=vc.start_contribution(contract,session="identity",intent="scoped",canonical_record="canonical.md",evidence_path="canonical.md")
            self._git(repo,"remote","add","origin",contract["remote"])
            (work/"canonical.md").write_text("update",encoding="utf-8")
            def external(argv,**kwargs):
                if argv[:3]==["git","remote","get-url"] or argv[:3]==["git","branch","--show-current"]:
                    return vc._run(argv,**kwargs)
                self.fail("repository mismatch must refuse before mutation or external request")
            with self.assertRaisesRegex(vc.ContributionError,"repository"):
                vc.submit_contribution(contract,work,title="update",runner=external)

    def test_submit_commit_records_attribution(self):
        import tempfile
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);repo,sha=self._repo(root);contract=self._contract(root,repo)
            work=vc.start_contribution(contract,session="attribution",intent="correct spelling",canonical_record="canonical.md",evidence_path="canonical.md")
            contract["remote"]="git@github.com:example/personal-vault.git"
            self._git(repo,"remote","add","origin",contract["remote"])
            (work/"canonical.md").write_text("updated",encoding="utf-8")
            def external(argv,**kwargs):
                if argv[:2]==["git","push"]:
                    return subprocess.CompletedProcess(argv,0,stdout="",stderr="")
                if argv[:3]==["gh","repo","view"]:
                    return subprocess.CompletedProcess(argv,0,stdout=json.dumps(dict(isPrivate=True,nameWithOwner=contract["repository"])),stderr="")
                if argv[:3]==["gh","pr","create"]:
                    return subprocess.CompletedProcess(argv,0,stdout="https://github.com/example/personal-vault/pull/1",stderr="")
                if argv[:3]==["gh","pr","view"]:
                    return subprocess.CompletedProcess(argv,0,stdout=json.dumps(dict(number=1)),stderr="")
                return vc._run(argv,**kwargs)
            vc.submit_contribution(contract,work,title="Correct spelling",runner=external)
            message=self._git(work,"log","-1","--format=%B")
            for trailer in ["Source-Host: DarkArmy","Session: attribution",f"Base-SHA: {sha}","Intent: correct spelling"]:
                self.assertIn(trailer,message)

    def test_snapshot_manifest_exists_before_visible_directory(self):
        import tempfile
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);repo,sha=self._repo(root);contract=self._contract(root,repo)
            target=Path(contract["snapshot_root"])/sha
            manifest=Path(contract["state_dir"])/"snapshot-manifests"/(sha+".json")
            replace=os.replace
            def observe(source,destination):
                if Path(destination)==target:
                    self.assertTrue(manifest.is_file(),"visible snapshot lacks recovery manifest")
                return replace(source,destination)
            with mock.patch.object(vc.os,"replace",side_effect=observe):
                vc.publish_snapshot(contract,repo,sha)

    def test_lifecycle_changes_require_explicit_review(self):
        import tempfile
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo, _ = self._repo(root)
            note = repo / "projects/demo/README.md"
            note.parent.mkdir(parents=True)
            note.write_text("---\nstatus: seed\n---\nProject\n", encoding="utf-8")
            self._git(repo, "add", ".")
            self._git(repo, "commit", "-m", "seed")
            base = self._git(repo, "rev-parse", "HEAD")
            note.write_text("---\nstatus: active\n---\nProject\n", encoding="utf-8")
            self._git(repo, "commit", "-am", "activate")
            head = self._git(repo, "rev-parse", "HEAD")
            self.assertTrue(hasattr(vc, "_validate_content_changes"), "lifecycle check missing")
            with self.assertRaises(vc.ReviewError):
                vc._validate_content_changes(repo, base, head, [{"path":"projects/demo/README.md", "status":"modified"}])

    def test_git_rename_status_preserves_both_literal_paths(self):
        import tempfile
        with tempfile.TemporaryDirectory() as temporary:
            repo, _ = self._repo(Path(temporary))
            self._git(repo, "mv", "canonical.md", "renamed.md")
            self.assertEqual(set(vc._status_paths(repo)), {"canonical.md", "renamed.md"})

    def test_submit_refuses_mismatched_remote_before_any_publication(self):
        import tempfile
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo, _ = self._repo(root)
            contract = self._contract(root, repo)
            work = vc.start_contribution(contract, session="submit", intent="scoped", canonical_record="canonical.md", evidence_path="canonical.md")
            (work / "canonical.md").write_text("update", encoding="utf-8")
            self._git(repo, "remote", "add", "origin", "https://github.com/unrelated/public.git")
            def reject_external(argv, **kwargs):
                if argv[0] != "git" or argv[:2] in (["git", "push"], ["git", "commit"]):
                    self.fail("must reject mismatched remote before committing or calling GitHub")
                return vc._run(argv, **kwargs)
            with self.assertRaisesRegex(vc.ContributionError, "remote"):
                vc.submit_contribution(contract, work, title="Update", runner=reject_external)

    def test_claude_command_is_subscription_review_without_budget_or_tools(self) -> None:
        command = vc.build_reviewer_command("full exact diff", "pinned evidence")
        self.assertEqual(command[:2], ["claude", "--model"])
        self.assertIn("claude-fable-5-1", command)
        self.assertIn("--tools", command)
        self.assertEqual(command[command.index("--tools") + 1], "")
        self.assertIn("--output-format", command)
        self.assertIn("stream-json", command)
        self.assertIn("--verbose", command)
        self.assertNotIn("--max-budget-usd", command)
        self.assertNotIn("--max-turns", command)
        self.assertIn("full exact diff", command[-1])
        self.assertIn("pinned evidence", command[-1])

    def test_reviewer_command_pins_effort_medium_exactly(self) -> None:
        command = vc.build_reviewer_command("full exact diff", "pinned evidence")
        self.assertEqual(
            command[:-1],
            [
                "claude",
                "--model",
                "claude-fable-5-1",
                "--effort",
                "medium",
                "--tools",
                "",
                "--output-format",
                "stream-json",
                "--verbose",
                "--strict-mcp-config",
                "--mcp-config",
                '{"mcpServers":{}}',
                "--disable-slash-commands",
                "-p",
            ],
        )
        self.assertNotIn("xhigh", command)
        self.assertEqual(command[command.index("--effort") + 1], "medium")


if __name__ == "__main__":
    TestCase.maxDiff = None
    import unittest

    unittest.main()
