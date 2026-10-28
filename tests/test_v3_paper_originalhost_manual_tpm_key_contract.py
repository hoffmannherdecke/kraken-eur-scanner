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
            "WindowsIdentity]::GetCurrent()","$expected='MINI-PC\\Thomas'",
            "$expectedSid='S-1-5-21-3814592484-1822576909-3594267478-1000'",
            "S-1-5-18","UserInteractive","New-SelfSignedCertificate",
            "WindowsPrincipal]::new($identity)", "IsInRole($adminRole)",
            "Get-Process -Id $PID", "sessionId -le 0",
            "COMPUTERNAME -ine 'MINI-PC'"):
   self.assertIn(x,self.s)
  self.assertNotIn("Register-ScheduledTask",self.s)


 def test_rejects_username_only_or_generic_admin_or_wrong_host(self):
  self.assertNotIn("COMPUTERNAME+'\\\\ADMIN'",self.s)
  self.assertIn("[string]$identity.User.Value -cne $expectedSid",self.s)
  self.assertIn("V3_SIGNER_REQUIRES_PINNED_INTERACTIVE_MINIPC_THOMAS_ADMIN_SID_NOT_SYSTEM_OR_RUNNER",self.s)
  self.assertIn("$env:COMPUTERNAME -ine 'MINI-PC'",self.s)
  self.assertIn("-not $who.IsInRole($adminRole)",self.s)
  self.assertIn("$sessionId -le 0",self.s)
  self.assertNotIn("Add-LocalGroupMember",self.s)

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

 def test_optional_existing_cng_provider_inspection_is_readonly_and_failclosed(self):
  # Distinct new proof: actual existing user key provider/export metadata,
  # not a new enrollment or remote CAS/TPM-attestation authority.
  for x in (
    "[switch]$InspectProvider",
    "if($InspectProvider -and $Enroll)",
    "V3_SIGNER_PROVIDER_READONLY_CANNOT_ENROLL",
    "if($InspectProvider){",
    "if($null -eq $cert){throw 'V3_SIGNER_PROVIDER_READONLY_CERT_MISSING'}",
    "RSACertificateExtensions]::GetRSAPrivateKey($cert)",
    "Security.Cryptography.RSACng",
    "$cng.Provider.Provider -ceq $provider",
    "-not [bool]$cng.IsMachineKey",
    "CngExportPolicies]::None",
    "$rsa.Dispose()",
    "V3_SIGNER_PROVIDER_READONLY_METADATA_HOLD",
    "provider_metadata_readonly_checked=$providerReadOnly",
    "existing_key_platform_provider_matches=$providerExactPlatform",
    "existing_key_current_user_scope_matches=$userScopedKey",
    "existing_key_nonexportable_policy_matches=$exportPolicyNonExportable",
    "provider_metadata_not_external_attestation=$true",
    "tpm_hardware_attestation_independently_verified=$false",
    "cloud_cas_authorized=$false",
  ):
   with self.subTest(field=x): self.assertIn(x,self.s)
  self.assertLess(self.s.index("if($InspectProvider -and $Enroll)"),
                  self.s.index("if($Enroll){"))
  self.assertLess(self.s.index("if($InspectProvider){"),
                  self.s.index("[pscustomobject][ordered]@{"))
  self.assertEqual(self.s.count("New-SelfSignedCertificate @options"),1)
  self.assertNotIn("Export-CngKey",self.s)
  self.assertNotIn("Set-Acl",self.s)
  self.assertNotIn("SignData(",self.s)

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
