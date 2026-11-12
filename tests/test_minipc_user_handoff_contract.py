"""Offline guardrails for the existing Mini-PC file bridge's local user-facing SendTo adapter."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/"tools/minipc_runner_guard/local_file_handoff.ps1"

class LocalUserHandoffContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s=P.read_text(encoding="utf-8")

    def test_existing_bridge_no_new_runner_or_elevation(self):
        s=self.s
        for forbidden in ("Start-Service", "Stop-Service", "Set-Service", "Start-ScheduledTask",
                          "Register-ScheduledTask", "Set-Acl", "icacls",
                          "Invoke-Expression","Invoke-WebRequest","Invoke-RestMethod",
                          "New-Service", "RunAs", "Verb RunAs", "GITHUB_TOKEN"):
            self.assertNotIn(forbidden,s)
        self.assertIn("WindowsBuiltInRole]::Administrator",s)
        self.assertIn("HANDOFF_HOLD: Bitte als normal angemeldeter Windows-Benutzer",s)
        self.assertIn("Microsoft\Windows\SendTo",s)
        self.assertIn("ChatGPT - gepruefter Dateiexport.lnk",s)
        self.assertIn("WScript.Shell",s)
        self.assertIn("-SourcePath",s)

    def test_exactly_one_user_selected_file_no_implicit_upload(self):
        s=self.s
        for item in (
            "Mandatory=$true)][string]$SourcePath",
            "Test-Path -LiteralPath $SourcePath -PathType Leaf",
            "Assert-NoReparse $full",
            "Assert-SafeFileName $file.Name",
            "Assert-SafeContent $bytes",
            "[Text.UTF8Encoding]::new($false,$true)",
            "Get-FileHash -LiteralPath $full",
            "Get-FileHash -LiteralPath $dest",
            "MINIPC_USER_HANDOFF_EXPORT_PASS",
            "ChatGPT-Uebergabe",
            "origin-sha256.json",
            "user_review_required=$true",
            "original_modified=$false",
        ):
            self.assertIn(item,s,item)
        for forbidden in ("Start-BitsTransfer","UploadFile","upload-artifact","https://",
                          "git push", "Remove-Item -LiteralPath $SourcePath", "Copy-Item -LiteralPath $SourcePath"):
            self.assertNotIn(forbidden,s)

    def test_fail_closed_for_binary_secret_symlinks_and_unbounded_size(self):
        s=self.s
        for item in ("2097152","ReparsePoint","HANDOFF_HOLD: Dateiname gesperrt",
                     "HANDOFF_HOLD: Moegliche Zugangsdaten",
                     "HANDOFF_HOLD: Nur gueltiger UTF-8-Text",
                     "HANDOFF_HOLD: Dateityp nicht fuer Direktexport zugelassen",
                     "HANDOFF_HOLD: Datei waehrend der Pruefung veraendert"):
            self.assertIn(item,s)
        # ZIP is an output archive in EvidenceBundle mode, never a source input.
        self.assertIn("if($ext -cnotin @('.txt','.md','.csv','.json','.log','.xml','.yml','.yaml'))",s)
        self.assertNotIn("GrantAccess",s)

if __name__=="__main__": unittest.main()
