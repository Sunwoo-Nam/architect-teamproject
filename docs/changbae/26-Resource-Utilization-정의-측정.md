# 26. Resource Utilization-메모리 — 정의 · 측정 방법 · 측정 목표

> 배경: 핵심 QA 2위인 Resource Utilization-메모리를 대상 Galaxy 단말의 프로세스 메모리 한도와 온디바이스 LLM 메모리를 기준으로 정의한다. 입력 검토: [`비LLM 기능의 이론적 최대 메모리`](../jongin-aug/non-llm-theoretical-memory.md).
> 지위: **측정 정의안**이다. 기존 문서의 `앱 가용 예산의 50% 이하`는 근거가 확정되지 않아 사용하지 않는다.
> 측정 수행 시 단일 참조: [`29-1 QA 측정 핸드북`](29-1-QA-측정-핸드북.md) — 본 문서는 지표·척도의 정의와 도출 근거를 담는다.

---

## 26.1 정의

> **Resource Utilization-메모리 = 온디바이스 LLM과 협상을 함께 실행할 때 앱 프로세스가 사용하는 Peak RSS와 Average RSS.**

LLM과 협상 기능은 동일한 앱 프로세스에서 실행한다고 가정한다. Peak RSS는 프로세스 메모리 한도 준수 여부를 판단하고, Average RSS는 설계 대안의 지속적인 메모리 효율을 비교하는 데 사용한다.

## 26.2 용어 정의

| 용어 | 정의 |
|---|---|
| **RSS (Resident Set Size)** | 측정 시점에 POC 프로세스가 물리 메모리에서 점유하는 메모리 크기 |
| **Peak RSS** | 측정 구간에서 관찰된 RSS의 최댓값 |
| **Average RSS** | 측정 구간에서 주기적으로 수집한 RSS의 산술평균 |

## 26.3 대상 단말과 프로세스 한도

Android 17 Memory Limiter는 앱 프로세스 상태에 따라 Visible과 Not-visible 한도를 적용한다. Android 권장 범위는 다음과 같다.

| 대상 단말 구성 | 물리 RAM | Visible 권장 범위 | Not-visible 권장 범위 |
|---|---:|---:|---:|
| Galaxy S25 FE | 8GiB | 4-5.33GiB | 2-2.67GiB |
| Galaxy S26 12GB 구성 | 12GiB | 6-8GiB | 3-4GiB |
| Galaxy S26 16GB 구성 | 16GiB | 8-10.67GiB | 4-5.33GiB |

표의 값은 명목 RAM을 기준으로 계산한 권장 범위다. 실제 측정에는 단말에서 확인한 프로세스 한도 `L_state`를 사용한다.

```bash
adb shell am memory-limiter status
```

Not-visible 상태는 화면을 표시하지 않고 협상하는 경우의 주 측정 조건이며, Visible 상태는 보조 조건이다.

## 26.4 LLM 메모리

구현 구조에 따라 LLM 사용 메모리는 앱 본 프로세스와 분리된 별도 프로세스의 메모리로 간주할 수 있다.

모델의 순수 가중치 크기는 `파라미터 수 × 양자화 bit ÷ 8`로 계산한다.

| 모델 | 4-bit 순수 가중치 | 8-bit 순수 가중치 |
|---|---:|---:|
| 1.5B | 약 715MiB | 약 1,431MiB |
| 2B | 약 954MiB | 약 1,907MiB |

순수 가중치에는 KV cache, activation, 추론 런타임과 CPU·GPU·NPU 버퍼가 포함되지 않는다. 따라서 최종 계산에는 LLM-only 실행에서 측정한 Peak RSS와 Average RSS를 사용한다.

## 26.5 비LLM 기능의 이론적 최대 메모리

LLM 실행 중 비LLM 기능이 사용할 수 있는 이론적 최대 메모리는 `B_nonLLM = L_state − M_LLM_peak`로 계산한다. `L_state`는 현재 프로세스 상태의 실제 한도, `M_LLM_peak`는 협상 없이 LLM만 실행했을 때의 Peak RSS다.

S25 FE의 Not-visible 한도를 2-2.67GiB로 가정하고 순수 가중치만 차감하면 다음과 같다.

| 모델 | 비LLM 기능의 낙관적 이론 상한 |
|---|---:|
| 1.5B 4-bit | 약 1,333-2,016MiB |
| 1.5B 8-bit | 약 617-1,300MiB |
| 2B 4-bit | 약 1,094-1,777MiB |
| 2B 8-bit | 약 141-824MiB |

이 값은 순수 가중치만 차감한 사전 검토값이다. 제품 판단에는 실측한 `M_LLM_peak`를 대입한다.

## 26.6 측정 지표

| 지표 | 계산 | 목적 |
|---|---|---|
| **Peak RSS** | 협상 실행 구간의 최대 Process RSS | 프로세스 한도와 비교 |
| **Average RSS** | 협상 실행 구간 Process RSS의 시간 평균 | 설계 대안 비교 |

LLM을 제외한 비LLM 기능의 메모리는 다음과 같이 계산한다.

- `비LLM Peak RSS = LLM+협상 Peak RSS − LLM-only Peak RSS`
- `비LLM Average RSS = LLM+협상 Average RSS − LLM-only Average RSS`

두 측정은 동일한 모델, prompt, context length, batch와 delegate 조건에서 수행한다.

## 26.7 측정 방법

측정은 ENV-B의 실제 Galaxy 단말에서 수행한다.

1. 단말에서 Visible 및 Not-visible 프로세스 한도를 확인한다.
2. 앱을 초기화하고 제품 최대 조건의 LLM-only workload를 실행한다.
3. 실행 구간의 Peak RSS와 Average RSS를 기록한다.
4. 앱을 같은 상태로 다시 초기화한다.
5. 같은 LLM workload와 최대 정상 협상을 함께 실행한다.
6. 실행 구간의 Peak RSS와 Average RSS를 기록한다.
7. LLM-only와 LLM+협상을 각각 5회 반복한다.
8. Peak RSS는 5회 중 최댓값, Average RSS는 5회 실행 평균으로 보고한다.

주 판정 단말은 Galaxy S25 FE 8GB이며, 주 프로세스 상태는 Not-visible이다. Galaxy S26 12GB와 16GB 및 Visible 상태는 동일 시나리오의 비교 결과로 기록한다.

최대 정상 협상은 제품이 지원하는 최대 참여자 수, 최대 의제 수, 최대 후보 수와 LLM 추론이 함께 실행되는 조건으로 고정한다.

## 26.8 측정 목표

Peak RSS의 목표는 `LLM+협상 Peak RSS < L_state`이다. 비LLM 관점에서는 `비LLM Peak RSS < B_nonLLM`과 같다.

Average RSS에는 근거 없는 고정 비율을 적용하지 않는다. 동일 단말·모델·협상 입력에서 Average RSS가 낮은 설계 대안을 더 우수한 대안으로 판단한다.

측정 결과에는 LLM-only와 LLM+협상의 Peak RSS 및 Average RSS 네 값을 MiB 단위로 제시한다.

## 26.9 경계와 기존 문서의 관계

- 본 QA는 최대 정상 협상에서의 절대 Peak RSS와 Average RSS를 측정한다.
- 참여자 수나 의제 조합 증가에 따른 메모리 증가 추세는 Scalability에서 측정한다.
- 협상 결과의 효용과 정확성은 Functional Correctness에서 측정한다.
- [`21`](21-핵심-QA-측정-정의.md)과 [`23`](23-핵심-QA-최종-확정.md)의 50% 기준은 본 문서에서 사용하지 않는다.

## 26.10 근거 자료

- Android Open Source Project, [Memory Limiter](https://source.android.com/docs/core/perf/memory-limiter)
- Android Developers, [Memory allocation among processes](https://developer.android.com/topic/performance/memory-management)
- Android Developers, [Process Memory (RSS)](https://developer.android.com/studio/profile/chart-glossary/process-memory)
