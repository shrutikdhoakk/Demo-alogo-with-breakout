# scripts/grid.ps1
param(
  [string]$Start="2023-01-01",
  [string]$End="2024-12-31",
  [string]$Uni=".\\data\\symbols_nifty500_clean.csv",
  [string]$Cfg=".\\backtest\\config.yaml"
)

$bufs   = 0.25, 0.30
$trails = 0.90, 1.30
$re = [regex]'CAGR:\s*([-0-9\.]+)%,\s*Max Drawdown:\s*([-0-9\.]+)%'

"buf,trail,CAGR,MaxDD" | Set-Content results.csv -Encoding utf8

foreach ($b in $bufs) {
  foreach ($t in $trails) {

    $tmp = New-TemporaryFile

    $content = Get-Content $Cfg
    # Update nested strategycfg (indented) AND top-level keys
    $content = $content -replace '^\s+breakout_atr_buf:\s*.*', "  breakout_atr_buf: $b"
    $content = $content -replace '^breakout_atr_buf:\s*.*',    "breakout_atr_buf: $b"
    $content = $content -replace '^\s+trail_atr_mult:\s*.*',   "  trail_atr_mult: $t"
    $content = $content -replace '^trail_atr_mult:\s*.*',      "trail_atr_mult: $t"
    $content | Set-Content $tmp -Encoding utf8

    $out = python -m backtest --start $Start --end $End --universe $Uni --max-pos 3 --config $tmp | Out-String
    $m = $re.Match($out)
    if ($m.Success) {
      "$b,$t,$($m.Groups[1].Value),$($m.Groups[2].Value)" | Add-Content results.csv
      Write-Host ("buf={0} trail={1} -> CAGR {2}% | DD {3}%" -f $b, $t, $m.Groups[1].Value, $m.Groups[2].Value)
    } else {
      Write-Warning "No metrics parsed for buf=$b trail=$t"
    }

    Remove-Item $tmp -Force
  }
}
