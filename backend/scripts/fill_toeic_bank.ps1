# Dựng ngân hàng TOEIC cho đến khi đủ mục tiêu (đề thi thử 200 câu). Chạy tách khỏi phiên làm việc:
#   Start-Process powershell -ArgumentList '-NoProfile','-File','backend\scripts\fill_toeic_bank.ps1' -WindowStyle Hidden
# Mỗi lượt thử Gemini trước (nhanh, chất lượng cao, nhưng hạn mức ngày nhỏ) rồi Ollama; chạy lại bao nhiêu lần cũng an toàn
# vì build_toeic_bank bỏ qua đề trùng. Log: fill_toeic_bank.log cạnh file này.
$targets = @{ 7 = 18; 2 = 34; 5 = 40; 3 = 13; 6 = 5; 4 = 10 }   # tổng số đơn vị mong muốn trong toeic_bank mỗi Part
$log = Join-Path $PSScriptRoot "fill_toeic_bank.log"

function Count-Bank([int]$part) {
    $n = docker exec lumina_db psql -U lumina_user -d lumina_db -At -c "select count(*) from toeic_bank where part=$part and disabled is false" 2>$null
    if ($n -match '^\d+$') { [int]$n } else { -1 }
}

for ($round = 1; $round -le 6; $round++) {
    $allDone = $true
    foreach ($part in $targets.Keys) {
        $have = Count-Bank $part
        if ($have -lt 0) { Start-Sleep 60; $allDone = $false; continue }   # DB/Docker chưa sẵn sàng
        $todo = $targets[$part] - $have
        if ($todo -le 0) { continue }
        $allDone = $false
        Add-Content $log "$(Get-Date -Format s) round $round part $part have $have todo $todo"
        foreach ($author in @("gemini", "ollama")) {
            $out = docker exec -e PYTHONPATH=/app lumina_api python -u -m app.scripts.build_toeic_bank --part $part --target $todo --author $author --verifier $author 2>&1 | Select-String -NotMatch "sqlalchemy" | Select-Object -Last 2
            Add-Content $log "  $author -> $out"
            $todo = $targets[$part] - (Count-Bank $part)
            if ($todo -le 0) { break }
        }
    }
    if ($allDone) { break }
}
Add-Content $log "$(Get-Date -Format s) ALLDONE"
