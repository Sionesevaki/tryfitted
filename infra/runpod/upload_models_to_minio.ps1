# Upload avatar-worker model assets into a private MinIO bucket (Windows-friendly).
# Uses the MinIO Client (`mc`) installed on your machine.
#
# Required env vars:
#   MINIO_URL          e.g. https://s3.trifitted.com  (S3 API URL, not console)
#   MINIO_ACCESS_KEY
#   MINIO_SECRET_KEY
#
# Optional:
#   MINIO_ALIAS        default: models
#   MODELS_BUCKET      default: trifitted-models
#   MODELS_PREFIX      default: (empty)
#   MINIO_INSECURE     true/false (use if your MinIO HTTPS cert isn't trusted)
#   DRY_RUN            true/false
#
# Optional upload sources (set what you have):
#   SMPLX_DIR
#   PIXIE_DATA_DIR
#   SAM3D_CHECKPOINT
#   SAM3D_MHR_MODEL
#   SAM2_CHECKPOINTS_DIR
#   GLTFPACK_FILE      (Linux gltfpack binary)

$ErrorActionPreference = "Stop"

function Note([string]$Message) {
  Write-Host "[upload-models] $Message"
}

function Die([string]$Message) {
  throw "ERROR: $Message"
}

function NeedEnv([string]$Name) {
  $value = [Environment]::GetEnvironmentVariable($Name)
  if ([string]::IsNullOrWhiteSpace($value)) { Die "Missing required env var: $Name" }
  return $value
}

function IsTruthy([string]$Value) {
  if ($null -eq $Value) { return $false }
  $v = $Value.Trim().ToLowerInvariant()
  return ($v -eq "1" -or $v -eq "true" -or $v -eq "yes" -or $v -eq "y")
}

function ToPosixPath([string]$Path) {
  return $Path.Replace("\", "/")
}

function ResolveMaybeRelativeToRepo([string]$Path) {
  if ([string]::IsNullOrWhiteSpace($Path)) { return $Path }
  if ([IO.Path]::IsPathRooted($Path)) { return (Resolve-Path $Path).Path }

  $repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
  $full = Join-Path $repoRoot $Path
  return (Resolve-Path $full).Path
}

function Run([switch]$DryRun, [string]$Command, [string[]]$Args) {
  if ($DryRun) {
    Note ("DRY_RUN: {0} {1}" -f $Command, ($Args -join " "))
    return
  }

  & $Command @Args | Out-Host
  if ($LASTEXITCODE -ne 0) { Die ("Command failed with exit code {0}: {1} {2}" -f $LASTEXITCODE, $Command, ($Args -join " ")) }
}

if (-not (Get-Command mc -ErrorAction SilentlyContinue)) {
  Die "'mc' (MinIO Client) is not installed or not on PATH. Install from https://min.io/docs/minio/linux/reference/minio-mc.html and ensure `mc --version` works."
}

$minioUrl = NeedEnv "MINIO_URL"
$minioAccessKey = NeedEnv "MINIO_ACCESS_KEY"
$minioSecretKey = NeedEnv "MINIO_SECRET_KEY"

$minioAlias = $env:MINIO_ALIAS
if ([string]::IsNullOrWhiteSpace($minioAlias)) { $minioAlias = "models" }

$modelsBucket = $env:MODELS_BUCKET
if ([string]::IsNullOrWhiteSpace($modelsBucket)) { $modelsBucket = "trifitted-models" }

$modelsPrefix = $env:MODELS_PREFIX
if ($null -eq $modelsPrefix) { $modelsPrefix = "" }
$remoteRoot = $modelsPrefix.TrimStart("/").TrimEnd("/")
if (-not [string]::IsNullOrWhiteSpace($remoteRoot)) { $remoteRoot = "$remoteRoot/" }

$dryRun = IsTruthy $env:DRY_RUN
$minioInsecure = IsTruthy $env:MINIO_INSECURE
$mcPrefixArgs = @()
if ($minioInsecure) { $mcPrefixArgs = @("--insecure") }

function RunMc([switch]$DryRun, [string[]]$Args) {
  Run -DryRun:$DryRun "mc" ($mcPrefixArgs + $Args)
}

Note "Config:"
Note "  MINIO_URL=$minioUrl"
Note "  MINIO_ALIAS=$minioAlias"
Note "  MODELS_BUCKET=$modelsBucket"
Note ("  MODELS_PREFIX={0}" -f ($(if ([string]::IsNullOrWhiteSpace($modelsPrefix)) { "<empty>" } else { $modelsPrefix })))
Note ("  DRY_RUN={0}" -f ($dryRun))
Note ("  MINIO_INSECURE={0}" -f ($minioInsecure))

Note "Setting MinIO alias..."
RunMc -DryRun:$dryRun @("alias", "set", $minioAlias, $minioUrl, $minioAccessKey, $minioSecretKey)

Note "Ensuring bucket exists: $modelsBucket"
try {
  RunMc -DryRun:$dryRun @("mb", "-p", "$minioAlias/$modelsBucket") | Out-Null
} catch {
  # Ignore "bucket exists" type errors
  Note "Bucket create returned non-zero (likely already exists); continuing."
}

function UploadDirContents([switch]$DryRun, [string]$SrcDir, [string]$Dest) {
  $resolved = ResolveMaybeRelativeToRepo $SrcDir
  if (-not (Test-Path $resolved -PathType Container)) { Die "Directory not found: $SrcDir (resolved: $resolved)" }
  $src = ToPosixPath $resolved
  if (-not $src.EndsWith("/")) { $src = "$src/" }
  Note "Uploading dir contents: $resolved -> $Dest"
  RunMc -DryRun:$DryRun @("cp", "--recursive", $src, $Dest)
}

function UploadFileAs([switch]$DryRun, [string]$SrcFile, [string]$Dest) {
  $resolved = ResolveMaybeRelativeToRepo $SrcFile
  if (-not (Test-Path $resolved -PathType Leaf)) { Die "File not found: $SrcFile (resolved: $resolved)" }
  $src = ToPosixPath $resolved
  Note "Uploading file: $resolved -> $Dest"
  RunMc -DryRun:$DryRun @("cp", $src, $Dest)
}

if (-not [string]::IsNullOrWhiteSpace($env:SMPLX_DIR)) {
  UploadDirContents -DryRun:$dryRun $env:SMPLX_DIR "$minioAlias/$modelsBucket/${remoteRoot}smplx/"
} else {
  Note "Skipping SMPL-X (SMPLX_DIR not set)"
}

if (-not [string]::IsNullOrWhiteSpace($env:PIXIE_DATA_DIR)) {
  UploadDirContents -DryRun:$dryRun $env:PIXIE_DATA_DIR "$minioAlias/$modelsBucket/${remoteRoot}pixie/"
} else {
  Note "Skipping PIXIE assets (PIXIE_DATA_DIR not set)"
}

if (-not [string]::IsNullOrWhiteSpace($env:SAM3D_CHECKPOINT)) {
  UploadFileAs -DryRun:$dryRun $env:SAM3D_CHECKPOINT "$minioAlias/$modelsBucket/${remoteRoot}sam3d/model.ckpt"
} else {
  Note "Skipping SAM3D checkpoint (SAM3D_CHECKPOINT not set)"
}

if (-not [string]::IsNullOrWhiteSpace($env:SAM3D_MHR_MODEL)) {
  UploadFileAs -DryRun:$dryRun $env:SAM3D_MHR_MODEL "$minioAlias/$modelsBucket/${remoteRoot}sam3d/assets/mhr_model.pt"
} else {
  Note "Skipping SAM3D MHR model (SAM3D_MHR_MODEL not set)"
}

if (-not [string]::IsNullOrWhiteSpace($env:SAM2_CHECKPOINTS_DIR)) {
  UploadDirContents -DryRun:$dryRun $env:SAM2_CHECKPOINTS_DIR "$minioAlias/$modelsBucket/${remoteRoot}sam2/checkpoints/"
} else {
  Note "Skipping SAM2 checkpoints (SAM2_CHECKPOINTS_DIR not set)"
}

if (-not [string]::IsNullOrWhiteSpace($env:GLTFPACK_FILE)) {
  UploadFileAs -DryRun:$dryRun $env:GLTFPACK_FILE "$minioAlias/$modelsBucket/${remoteRoot}tools/gltfpack"
} else {
  Note "Skipping gltfpack (GLTFPACK_FILE not set)"
}

Note "Done."
Note "Verify bucket contents:"
Note "  mc ls --recursive $minioAlias/$modelsBucket/$remoteRoot"
