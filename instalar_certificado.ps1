# Instala o certificado da CA local como confiável no Windows
# (remove o aviso "Sua conexão não é particular" no navegador deste PC)
# Uso: clique com o botão direito > "Executar com o PowerShell" (ou rode como Admin)
$ErrorActionPreference = 'Stop'
$base = Split-Path -Parent $MyInvocation.MyCommand.Path
$ca = Join-Path $base 'certs\ca.crt'

if (-not (Test-Path $ca)) {
    Write-Host 'ca.crt não encontrado. Rode primeiro: python servidor_local.py'
    exit 1
}

# Compara pelo Thumbprint (identifica a CA de forma confiável)
$thumb = (New-Object System.Security.Cryptography.X509Certificates.X509Certificate2($ca)).Thumbprint
$existing = Get-ChildItem Cert:\LocalMachine\Root | Where-Object { $_.Thumbprint -eq $thumb }

if (-not $existing) {
    Import-Certificate -FilePath $ca -CertStoreLocation Cert:\LocalMachine\Root | Out-Null
    Write-Host 'CA instalada como confiável. Feche e reabra o navegador.'
} else {
    Write-Host 'CA já está instalada.'
}