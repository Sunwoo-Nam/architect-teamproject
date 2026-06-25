#!/usr/bin/env python3
"""
DP03 — MAF On-Device LLM Placement: Resource PoC harness.

후보 GGUF 모델별로 다음을 측정한다 (DP03 §1 R1~R3):
  R1 메모리     : 모델 적재 +RSS, 추론 중 peak RSS, (--coresident) IDS+MAF 동시 상주 총량
  R2 전환 지연  : 모델 load 시간(cold/warm) + 워밍업(첫 토큰)   [--swap]
  R3 추론 시간  : TTFT(프리필+첫 토큰), decode tokens/sec

백엔드: llama-cpp-python (GGUF, CPU/GPU).
  ⚠ 이건 NPU가 아니다. 수치는 ballpark/상대 비교용 (DP03 §3).
    절대 on-device 수치는 벤더 NPU SDK(QAIRT/Genie, MediaTek 등)로 확인할 것.
  ⚠ 메모리(R1)는 CPU 백엔드(--n-gpu-layers 0)에서 RSS로 측정해야 정확.
    GPU/NPU 오프로드 시 가중치가 VRAM/NPU 메모리로 가 RSS가 과소보고된다.

설치:
  pip install llama-cpp-python psutil
  # GGUF 모델 준비 (예: ~1B 와 ~3B, Q4) → ./models

예시:
  # R1/R3 (모델별 메모리·속도)
  python bench.py --models models/m1b-q4.gguf:small models/m3b-q4.gguf:large \
                  --prompt-tokens 512 --gen-tokens 128 --repeats 3
  # R2 (전환 지연 루프) 추가
  python bench.py --models ... --swap
  # R1 동시 상주 (IDS+MAF 가정: 두 모델 동시 적재 총 RAM)
  python bench.py --models ids.gguf:IDS maf.gguf:MAF --coresident
"""
from __future__ import annotations
import argparse, gc, json, os, statistics, sys, threading, time

try:
    import psutil
except ImportError:
    sys.exit("psutil 필요: pip install psutil")

try:  # 콘솔 인코딩(cp949 등)에서 기호/한글 출력이 깨지거나 죽지 않도록
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

PROC = psutil.Process(os.getpid())


def rss_mb() -> float:
    return PROC.memory_info().rss / (1024 * 1024)


class PeakSampler:
    """블록 실행 중 RSS peak 를 잡는 백그라운드 샘플러."""

    def __init__(self, interval: float = 0.05):
        self.interval = interval
        self._peak = 0.0
        self._stop = threading.Event()
        self._t = None

    def __enter__(self):
        self._peak = rss_mb()
        self._t = threading.Thread(target=self._run, daemon=True)
        self._t.start()
        return self

    def _run(self):
        while not self._stop.is_set():
            self._peak = max(self._peak, rss_mb())
            time.sleep(self.interval)

    def __exit__(self, *exc):
        self._stop.set()
        if self._t:
            self._t.join()
        self._peak = max(self._peak, rss_mb())

    @property
    def peak(self) -> float:
        return self._peak


def load_llama(path: str, n_ctx: int, n_gpu_layers: int):
    from llama_cpp import Llama
    return Llama(model_path=path, n_ctx=n_ctx, n_gpu_layers=n_gpu_layers, verbose=False)


def make_prompt(llm, target_tokens: int) -> str:
    """~target_tokens 길이의 합성 프롬프트 (내용은 무관, 길이만 대표값 — DP03 §2)."""
    base = "다음 회의 일정을 협상하라. 참가자 선호와 제약을 고려해 합의안을 제시한다. "
    text = base
    while len(llm.tokenize(text.encode("utf-8"))) < target_tokens:
        text += base
    toks = llm.tokenize(text.encode("utf-8"))[:target_tokens]
    return llm.detokenize(toks).decode("utf-8", errors="ignore")


def measure_inference(llm, prompt: str, gen_tokens: int):
    """(ttft_ms, decode_tok_s, peak_rss_mb) 반환."""
    with PeakSampler() as ps:
        t0 = time.perf_counter()
        first_t = None
        n = 0
        for _chunk in llm.create_completion(prompt, max_tokens=gen_tokens,
                                            stream=True, temperature=0.0):
            if first_t is None:
                first_t = time.perf_counter()
            n += 1
        t1 = time.perf_counter()
    if first_t is None:
        return float("nan"), float("nan"), ps.peak
    ttft_ms = (first_t - t0) * 1000.0
    decode_s = t1 - first_t
    tok_s = (n - 1) / decode_s if decode_s > 0 and n > 1 else float("nan")
    return ttft_ms, tok_s, ps.peak


def bench_model(spec, args) -> dict:
    path, label = spec
    model = os.path.basename(path)
    print(f"\n=== {label} ({model}) ===")
    base_rss = rss_mb()

    t0 = time.perf_counter()
    llm = load_llama(path, args.n_ctx, args.n_gpu_layers)
    load_s = time.perf_counter() - t0
    load_rss = rss_mb() - base_rss
    print(f"  load: {load_s:.2f}s  +RSS {load_rss:.0f}MB")

    prompt = make_prompt(llm, args.prompt_tokens)
    ttfts, toks, peaks = [], [], []
    for i in range(args.repeats):
        ttft, tok_s, peak = measure_inference(llm, prompt, args.gen_tokens)
        ttfts.append(ttft)
        toks.append(tok_s)
        peaks.append(peak)
        print(f"  run{i + 1}: TTFT {ttft:.0f}ms  decode {tok_s:.1f} tok/s  peakRSS {peak:.0f}MB")

    t0 = time.perf_counter()
    del llm
    gc.collect()
    unload_s = time.perf_counter() - t0

    return {
        "label": label, "model": model, "n_ctx": args.n_ctx,
        "load_s": round(load_s, 3), "load_rss_mb": round(load_rss, 1),
        "unload_s": round(unload_s, 3),
        "ttft_ms_med": round(statistics.median(ttfts), 1),
        "decode_tok_s_med": round(statistics.median(toks), 2),
        "peak_rss_mb": round(max(peaks), 1),
    }


def bench_swap(specs, args) -> list:
    """R2: load A → 워밍업 → unload → load B → ...  각 load 비용 측정.
    각 모델 첫 등장 = cold(가능하면 OS 페이지캐시 비운 상태), 이후 = warm."""
    print("\n=== SWAP LOOP (R2) ===")
    rows = []
    order = specs * args.swap_rounds
    for i, (path, label) in enumerate(order):
        t0 = time.perf_counter()
        llm = load_llama(path, args.n_ctx, args.n_gpu_layers)
        load_s = time.perf_counter() - t0
        t1 = time.perf_counter()
        list(llm.create_completion("안녕", max_tokens=1, stream=True))  # 그래프 init + 첫 토큰
        warm_s = time.perf_counter() - t1
        del llm
        gc.collect()
        kind = "cold" if i < len(specs) else "warm"
        print(f"  swap#{i + 1} -> {label}: load {load_s:.2f}s + warmup {warm_s:.2f}s ({kind})")
        rows.append({"step": i + 1, "label": label, "load_s": round(load_s, 3),
                     "warmup_s": round(warm_s, 3), "kind": kind})
    return rows


def bench_coresident(specs, args) -> dict:
    """R1 핵심: 여러 모델(예: IDS + MAF)을 동시 적재해 총 RSS 측정 (P2 fit 확인)."""
    print("\n=== CO-RESIDENT (R1: 동시 상주 — IDS+MAF 가정) ===")
    base = rss_mb()
    llms = []
    for path, label in specs:
        llms.append(load_llama(path, args.n_ctx, args.n_gpu_layers))
        print(f"  +{label}: 누적 RSS {rss_mb():.0f}MB")
    total = rss_mb() - base
    print(f"  동시 상주 총 +RSS: {total:.0f}MB  ({len(llms)}개 모델)")
    for llm in llms:
        del llm
    gc.collect()
    return {"models": [l for _, l in specs], "total_rss_mb": round(total, 1)}


def main():
    ap = argparse.ArgumentParser(description="DP03 resource PoC harness (R1/R2/R3)")
    ap.add_argument("--models", nargs="+", required=True,
                    help="path:label ...  (예: models/m1b.gguf:small models/m3b.gguf:large)")
    ap.add_argument("--n-ctx", type=int, default=2048)
    ap.add_argument("--prompt-tokens", type=int, default=512)
    ap.add_argument("--gen-tokens", type=int, default=128)
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--n-gpu-layers", type=int, default=0,
                    help="0=CPU(메모리 측정 권장). GPU/Metal 오프로드 시 양수")
    ap.add_argument("--swap", action="store_true", help="전환 지연 루프(R2) 실행")
    ap.add_argument("--swap-rounds", type=int, default=2)
    ap.add_argument("--coresident", action="store_true", help="모델 동시 상주 총 RSS(R1) 측정")
    ap.add_argument("--out", default="results.json")
    args = ap.parse_args()

    specs = []
    for m in args.models:
        path, label = (m.rsplit(":", 1) if ":" in m else (m, os.path.basename(m)))
        if not os.path.exists(path):
            sys.exit(f"모델 없음: {path}")
        specs.append((path, label))

    print(f"backend=llama-cpp-python  n_ctx={args.n_ctx}  "
          f"prompt~{args.prompt_tokens}tok  gen={args.gen_tokens}tok  n_gpu_layers={args.n_gpu_layers}")
    print("⚠ CPU/GPU 백엔드 — NPU 수치 아님 (DP03 §3). 절대치는 벤더 NPU SDK로 확인.")

    results = {"config": vars(args), "models": [], "swap": [], "coresident": None}
    for spec in specs:
        results["models"].append(bench_model(spec, args))
    if args.swap and len(specs) >= 2:
        results["swap"] = bench_swap(specs, args)
    if args.coresident and len(specs) >= 2:
        results["coresident"] = bench_coresident(specs, args)

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print("\n==== SUMMARY (R1/R3) ====")
    print(f"{'label':10} {'load_s':>7} {'+RSS MB':>8} {'peakRSS':>8} {'TTFT ms':>8} {'tok/s':>7}")
    for r in results["models"]:
        print(f"{r['label']:10} {r['load_s']:>7.2f} {r['load_rss_mb']:>8.0f} "
              f"{r['peak_rss_mb']:>8.0f} {r['ttft_ms_med']:>8.0f} {r['decode_tok_s_med']:>7.1f}")
    print(f"\n결과 저장: {args.out}")
    print("에너지(R4): 본 하네스 미포함 — 외부 전력계/배터리 통계로 같은 실행 중 측정 권장.")


if __name__ == "__main__":
    main()
