"""Bounded signed-evidence bundle through the EXISTING Mini-PC user SendTo adapter."""
from pathlib import Path
import unittest

SRC=(Path(__file__).resolve().parents[1]/"tools/minipc_runner_guard/local_file_handoff.ps1").read_text("utf-8")

class EvidenceBundleContract(unittest.TestCase):
    def test_existing_sendto_is_extended_not_replaced(self):
        for marker in ("[switch]$EvidenceBundle","ChatGPT - signierte Nachweise.lnk",
                       "MINIPC_USER_HANDOFF_INSTALLED","MINIPC_USER_HANDOFF_EXPORT_PASS",
                       "Export-EvidenceBundle $SourcePath","-EvidenceBundle -SourcePath"):
            self.assertIn(marker,SRC)
    def test_cms_hashes_and_original_byte_copy(self):
        for marker in ("'.p7s'","'.p7m'","'.cms'","'.sig'","'.der'","'.cer'","'.crt'",
                       "'.sha256'","'.json'","'.pdf'",
                       "MINIPC_SIGNED_EVIDENCE_HANDOFF_V1","evidence-manifest-sha256.json",
                       "Get-FileHash -LiteralPath $candidate.FullName",
                       "[IO.File]::WriteAllBytes($dest,$entry.bytes)",
                       "Get-FileHash -LiteralPath $dest",
                       "signatures_verified=$false",
                       "authenticity_requires_existing_independent_verifier=$true",
                       "user_review_required=$true"):
            self.assertIn(marker,SRC,marker)
    def test_strict_selection_and_limited_impact(self):
        for marker in ("$visited -gt 120","$node.depth -ge 2",
                       "$candidates.Count -gt 80","8388608","33554432",
                       "Assert-NoReparse $source","Assert-NoReparse $candidate.FullName",
                       "HANDOFF_HOLD: Nachweisdateiname gesperrt",
                       "HANDOFF_HOLD: Vertrauliche Nachweisdaten erkannt",
                       "original_files_modified=$false"):
            self.assertIn(marker,SRC,marker)
        for forbidden in ("Set-Acl","icacls","Start-Service","Start-ScheduledTask",
                          "Invoke-RestMethod","Invoke-WebRequest","Start-BitsTransfer",
                          "Import-PfxCertificate","Export-PfxCertificate","Get-PrivateKey",
                          "UploadFile","Set-AuthenticodeSignature","SignCms"):
            self.assertNotIn(forbidden,SRC,forbidden)

if __name__ == "__main__":
    unittest.main()
