param(
  [string]$Root = "."
)

$ErrorActionPreference = "Stop"
$rootPath = (Resolve-Path -LiteralPath $Root).Path
$errors = New-Object System.Collections.Generic.List[string]
$warnings = New-Object System.Collections.Generic.List[string]

function Add-Error([string]$Message) {
  $script:errors.Add($Message) | Out-Null
}

function Add-Warning([string]$Message) {
  $script:warnings.Add($Message) | Out-Null
}

function Resolve-MarkdownTarget([string]$BaseFile, [string]$Link) {
  $clean = ($Link -split "#", 2)[0]
  if ([string]::IsNullOrWhiteSpace($clean)) {
    return $null
  }
  if ($clean -match "^[a-zA-Z][a-zA-Z0-9+.-]*:") {
    return $null
  }
  $baseDir = Split-Path -Parent $BaseFile
  return [System.IO.Path]::GetFullPath((Join-Path $baseDir $clean))
}

$required = @(
  "AGENTS.md",
  ".agents/index.md",
  ".agents/log.md",
  ".agents/memory/CURRENT.md",
  ".agents/rules/kb_maintenance_rules.md",
  ".agents/rules/role-activation.md",
  ".agents/references/Context_Navigation.md",
  ".agents/references/System_Map.md",
  "docs/STATE.md"
)

foreach ($path in $required) {
  $full = Join-Path $rootPath $path
  if (-not (Test-Path -LiteralPath $full)) {
    Add-Error "Missing required file: $path"
  }
}

$markdownFiles = Get-ChildItem -Recurse -File -LiteralPath $rootPath -Filter *.md

foreach ($file in $markdownFiles) {
  $text = Get-Content -Raw -LiteralPath $file.FullName
  $matches = [regex]::Matches($text, "\[[^\]]+\]\(([^)]+)\)")
  foreach ($match in $matches) {
    $link = $match.Groups[1].Value.Trim()
    $target = Resolve-MarkdownTarget $file.FullName $link
    if ($null -eq $target) {
      continue
    }
    if ($target -notlike "$rootPath*") {
      Add-Warning "Link points outside repo: $($file.FullName.Replace($rootPath + [IO.Path]::DirectorySeparatorChar, '')) -> $link"
      continue
    }
    if (-not (Test-Path -LiteralPath $target)) {
      Add-Error "Broken link: $($file.FullName.Replace($rootPath + [IO.Path]::DirectorySeparatorChar, '')) -> $link"
    }
  }
}

$referenceDirs = @(
  (Join-Path $rootPath ".agents/references"),
  (Join-Path $rootPath ".agents")
)

foreach ($dir in $referenceDirs) {
  if (-not (Test-Path -LiteralPath $dir)) {
    continue
  }
  Get-ChildItem -File -LiteralPath $dir -Filter *.md | ForEach-Object {
    if ($_.Name -eq "log.md") {
      return
    }
    $lines = Get-Content -LiteralPath $_.FullName -TotalCount 20
    $rel = $_.FullName.Replace($rootPath + [IO.Path]::DirectorySeparatorChar, "")
    if ($lines.Count -eq 0 -or $lines[0] -ne "---") {
      Add-Warning "Missing frontmatter: $rel"
      return
    }
    foreach ($field in @("title:", "type:", "sources:", "related:", "updated:", "confidence:")) {
      if (-not ($lines | Select-String -SimpleMatch $field -Quiet)) {
        Add-Warning "Frontmatter missing $field $rel"
      }
    }
  }
}

$placeholderCount = 0
foreach ($file in $markdownFiles) {
  $text = Get-Content -Raw -LiteralPath $file.FullName
  $placeholderCount += [regex]::Matches($text, "<[A-Z0-9_]+>").Count
}
if ($placeholderCount -gt 0) {
  Add-Warning "Placeholder tokens remaining: $placeholderCount"
}

$logPath = Join-Path $rootPath ".agents/log.md"
if (Test-Path -LiteralPath $logPath) {
  $dates = Select-String -Path $logPath -Pattern "^## \[(\d{4}-\d{2}-\d{2})\]" | ForEach-Object {
    [datetime]::ParseExact($_.Matches[0].Groups[1].Value, "yyyy-MM-dd", $null)
  }
  for ($i = 1; $i -lt $dates.Count; $i++) {
    if ($dates[$i] -gt $dates[$i - 1]) {
      Add-Error ".agents/log.md is not newest-first near entry $($i + 1)"
      break
    }
  }
}

if ($warnings.Count -gt 0) {
  Write-Host "Warnings:"
  $warnings | ForEach-Object { Write-Host "  - $_" }
}

if ($errors.Count -gt 0) {
  Write-Host "Errors:"
  $errors | ForEach-Object { Write-Host "  - $_" }
  exit 1
}

Write-Host "Agent KB lint passed. Markdown files: $($markdownFiles.Count). Warnings: $($warnings.Count)."
