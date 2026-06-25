# MAF LLM 배치 — 자원 PoC 하네스

[DP03-MAF-LLM-배치-PoC계획.md](../../docs/07-DP후보안/DP03-MAF-LLM-배치-PoC계획.md)의 **R1(메모리)·R2(전환 지연)·R3(추론 시간)** 을 단말에서 측정하는 벤치마크.

> ⚠️ **백엔드 = llama-cpp-python (CPU/GPU)** → **ballpark·상대 비교용**. NPU 절대 수치는 벤더 SDK(QAIRT/Genie, MediaTek)로 확인할 것 (DP03 §3).

## 1. 준비

```bash
pip install llama-cpp-python psutil
# GGUF 모델 준비 (예: ~1B 와 ~3B, Q4 양자화) → ./models/
#   작은 모델 = 툴/판정 후보, 큰 모델 = 협상 후보 (크기 브래킷으로 비교 — DP03 §2)
```

## 2. 실행

```bash
# R1(메모리) + R3(추론 속도) — 모델별
python bench.py --models models/m1b-q4.gguf:small models/m3b-q4.gguf:large \
                --prompt-tokens 512 --gen-tokens 128 --repeats 3 --out results.json

# R2(전환 지연) 루프 추가
python bench.py --models models/m1b-q4.gguf:small models/m3b-q4.gguf:large --swap

# R1 동시 상주 (IDS+MAF 가정: 두 모델 동시 적재 총 RAM)
python bench.py --models models/ids.gguf:IDS models/maf.gguf:MAF --coresident
```

주요 옵션: `--n-ctx`(컨텍스트), `--prompt-tokens`/`--gen-tokens`(부하 길이), `--repeats`, `--n-gpu-layers`(0=CPU), `--swap-rounds`.

## 3. 측정 정의 → DP03 매핑

| 출력 | 의미 | DP03 |
|---|---|---|
| `load_rss_mb` / `peak_rss_mb` | 모델 적재·추론 중 메모리 | R1 |
| `coresident.total_rss_mb` | 동시 상주 총 RAM (P2 fit) | R1 |
| `swap[].load_s + warmup_s` (cold/warm) | swap 1회 전환 비용 | R2 |
| `ttft_ms_med` | 프리필+첫 토큰 지연 | R3 |
| `decode_tok_s_med` | 토큰 생성 속도 (작을수록 큰 모델) | R3 (M4b) |

## 4. 해석 시 주의 (정직한 한계)

- **메모리는 CPU 백엔드(`--n-gpu-layers 0`)로 측정**해야 RSS가 정확. GPU/NPU 오프로드 시 가중치가 VRAM/NPU 메모리로 가서 RSS가 과소보고됨.
- **cold/warm**: 본 하네스는 "모델 첫 등장=cold, 이후=warm"으로 근사. *진짜 cold*(플래시에서 최초 로드)는 OS 페이지캐시를 비워야 함 — Linux: `echo 3 | sudo tee /proc/sys/vm/drop_caches` (root). cold 가 최악값.
- **크기→속도/메모리 곡선**으로 보기: 특정 모델 1개가 아니라 1B/3B/7B 식 브래킷으로 돌려, 최종 모델 미정이어도 결과가 전이되게 (DP03 §2).
- **에너지(R4)** 미포함: 같은 실행 중 외부 전력계 또는 단말 배터리 통계로 별도 측정 권장.
- llama.cpp 대신 **벤더 NPU 런타임**으로 확정치를 다시 떠야 함 — 이 하네스는 1차 ballpark 용.

## 5. 산출물 활용

`results.json` 의 메모리 수치로 **QAS-011("MAF Memory 300MB") 불일치를 확정**하고 NFR-MAF-06 재매핑 (DP03 §5, CLAUDE.md 7항). swap 총비용(= swap 1회 × P6 가정 1~3회)이 백그라운드 허용 범위를 넘으면 → 품질 검증 없이 B 수렴 (DP03 §4).
