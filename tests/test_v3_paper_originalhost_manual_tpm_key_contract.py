"""Offline fail-closed contract for original-host manual TPM key enrolment.

The enrollment function is never invoked by CI; no private key is generated
and no Windows certificate store, service or Paper task is touched here.
"""
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
P=ROOT/"tools/v3-paper-originalhost-manual-tpm-enroll-INACTIVE.ps1"

class ManualTPMKeySourceContract(unittest.TestCase):
 def setUp(self):
  self.s=P.read_text(encoding="utf-8")

 def test_explicit_interactive_admin_only_separated_from_system_and_runner(self):
  for x in ("[switch]$Enroll","$Approval -cne $confirmation",
            "ENROLL_MANUAL_TPM_SIGNING_KEY_NO_V3_RELEASE",
            "WindowsIdentity]::GetCurrent()","COMPUTERNAME+'\\ADMIN'",
            "S-1-5-18","UserInteractive","New-SelfSignedCertificate"):
   self.assertIn(x,self.s)
  self.assertNotIn("Register-ScheduledTask",self.s)

 def test_private_key_only_tpm_nonexportable_user_not_system(self):
  for x in ("'Cert:\\CurrentUser\\My'",
           "'Microsoft Platform Crypto Provider'",
           "KeyExportPolicy='NonExportable'","KeyProtection='Protect'",
           "KeyUsage='DigitalSignature'","HashAlgorithm='SHA256'",
           "KeyLength=2048","TpmPresent","TpmReady",
           "V3_SIGNER_TPM_NOT_READY_NO_SOFTWARE_FALLBACK",
           "V3_SIGNER_ALREADY_EXISTS_NO_REENROLL"):
   self.assertIn(x,self.s)
  for bad in ("Cert:\\LocalMachine","TrustedRoot","TrustedPeople",
              "Export-PfxCertificate","Export-Certificate",
              "Microsoft Software Key Storage Provider",
              "Invoke-RestMethod","Invoke-WebRequest","Start-ScheduledTask",
              "Enable-ScheduledTask","Disable-ScheduledTask",
              "Set-Acl","icacls.exe","Set-ExecutionPolicy",
              "Add-LocalGroupMember","New-LocalUser",
              ".rpc(","Start-Process"):
   self.assertNotIn(bad,self.s)

 def test_public_pin_not_release_authority(self):
  for x in ("certificate_der_sha256_public_pin_unapproved",
            "originalhost_signed_receipt_generated=$false",
            "pin_externally_reviewed_and_approved=$false",
            "originalhost_runtime_identity_verified=$false",
            "private_key_acl_independently_verified=$false",
            "tpm_hardware_attestation_independently_verified=$false",
            "six_e2e_release_proofs_credited=0",
            "cloud_cas_authorized=$false","v3_task_modified=$false",
            "v2r4_modified=$false","v3_paper_activated=$false"):
   self.assertIn(x,self.s)

if __name__=="__main__":
 unittest.main()
