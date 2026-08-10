# 비LLM 기능의 이론적 최대 메모리

## 1. 목적

온디바이스 LLM과 협상 기능이 하나의 앱 프로세스에서 실행된다는 전제에서, LLM 실행 중 UI, 협상 그래프, 세션 관리 등 비LLM 기능이 사용할 수 있는 이론적 최대 메모리를 계산한다.

이 문서의 계산값은 제품의 최종 메모리 요구사항이 아니라, 단말과 모델 구성별 실행 가능성을 검토하기 위한 상한값이다.

## 2. 전제

- 온디바이스 LLM과 비LLM 기능은 동일한 앱 프로세스에 포함된다.
- Android 17 Memory Limiter는 개별 앱 프로세스에 `memory.high` 형태의 soft limit를 적용한다.
- 프로세스 상태는 화면을 표시하는 Visible과 화면을 표시하지 않지만 작업 중인 Not-visible로 구분한다.
- Android 권장 범위는 Visible 프로세스가 물리 RAM의 1/2~2/3, Not-visible 프로세스가 1/4~1/3이다.
- 실제 Galaxy 단말의 한도는 Samsung의 vendor 설정과 Android 버전에 따라 달라질 수 있으므로 실기기에서 확인해야 한다.
- 대상 단말의 RAM 사양은 본 검토에서 제시된 조건을 사용하며, 판매 지역이나 제품 변형에 따라 달라질 수 있다.

## 3. 대상 단말과 프로세스 메모리 한도

| 대상 | 물리 RAM | Visible 프로세스 권장 범위 | Not-visible 프로세스 권장 범위 |
|---|---:|---:|---:|
| Galaxy S25 FE | 8GiB | 4~5.33GiB | 2~2.67GiB |
| Galaxy S26 12GB 구성 | 12GiB | 6~8GiB | 3~4GiB |
| Galaxy S26 16GB 구성 | 16GiB | 8~10.67GiB | 4~5.33GiB |

이 값은 앱에 미리 보장되거나 할당된 메모리가 아니다. 프로세스가 한도에 접근하거나 초과하면 커널이 file-backed page 회수, anonymous page의 swap, 실행 throttling 등을 수행할 수 있다. 메모리 할당을 계속하고 swap까지 부족해지면 할당 실패나 프로세스 비정상 종료가 발생할 수 있다.

또한 Android 17 Memory Limiter가 비활성화됐거나 OEM이 다른 한도를 설정했을 수 있으므로 다음 명령으로 실제 설정을 확인한다.

```bash
adb shell am memory-limiter status
```

## 4. 모델별 순수 가중치 크기

순수 가중치 크기는 다음 식으로 계산한다.

```text
가중치 크기(byte) = 파라미터 수 × 양자화 bit / 8
```

| 모델 | 4-bit | 8-bit |
|---|---:|---:|
| 1.5B | 약 750MB = 715MiB | 약 1,500MB = 1,431MiB |
| 2B | 약 1,000MB = 954MiB | 약 2,000MB = 1,907MiB |

위 값은 모델의 순수 가중치만 계산한 값이다. 실제 LLM 실행 Peak에는 다음 메모리가 추가된다.

- KV cache
- activation
- 추론 런타임
- quantization metadata 및 정렬 오버헤드
- CPU, GPU, NPU 관련 공유 버퍼

따라서 최종 잔여 메모리 계산에는 순수 가중치가 아니라 실기기에서 측정한 `LLM 실행 Peak`를 사용해야 한다.

## 5. 비LLM 기능의 이론적 최대 메모리

계산식은 다음과 같다.

```text
비LLM 기능의 이론적 최대 메모리
= 현재 프로세스 상태의 Memory Limiter 한도
- LLM 실행 Peak 메모리
```

초기 설계 단계에서 LLM 실행 Peak를 아직 측정하지 못했다면, 순수 가중치 크기를 대신 사용해 낙관적인 이론 상한을 계산할 수 있다.

```text
낙관적 비LLM 이론 상한
= 현재 프로세스 상태의 Memory Limiter 한도
- LLM 순수 가중치 크기
```

이 값은 KV cache와 런타임 버퍼 등을 제외했기 때문에 실제 사용 가능량보다 크다.

## 6. Galaxy S25 FE 8GiB 계산 예시

Not-visible 프로세스 한도를 Android 권장 범위인 2~2.67GiB, 즉 약 2,048~2,731MiB로 가정한다.

| 모델 | 순수 가중치 | 비LLM 기능의 낙관적 이론 상한 |
|---|---:|---:|
| 1.5B 4-bit | 약 715MiB | 약 1,333~2,016MiB |
| 1.5B 8-bit | 약 1,431MiB | 약 617~1,300MiB |
| 2B 4-bit | 약 954MiB | 약 1,094~1,777MiB |
| 2B 8-bit | 약 1,907MiB | 약 141~824MiB |

예를 들어 2B 8-bit 모델을 사용하고 Not-visible 한도가 2GiB인 경우, 순수 가중치만 제외해도 비LLM 기능에 남는 이론적 공간은 약 141MiB이다. KV cache와 추론 런타임 메모리를 추가하면 잔여량이 0 이하가 될 수 있으므로 동일 프로세스 구성의 실행 가능성이 낮다.

반대로 1.5B 4-bit 모델은 동일 조건에서 순수 가중치 기준 약 1,333MiB가 남는다. 그러나 이 값 전체를 비LLM 기능의 제품 메모리 예산으로 사용할 수 있다는 의미는 아니다. 실제 LLM Peak와 Memory Limiter 한도 접근 시의 reclaim 및 throttling 영향을 측정해야 한다.

## 7. 최종 적용 방법

최종 판단은 다음 순서로 수행한다.

1. 대상 Galaxy 단말에서 실제 Visible 및 Not-visible Memory Limiter 한도를 확인한다.
2. 모델 구성별로 가중치, KV cache, activation 및 가속기 버퍼를 포함한 LLM 실행 Peak를 측정한다.
3. 실제 프로세스 한도에서 LLM 실행 Peak를 차감해 비LLM 기능의 이론적 최대 메모리를 다시 계산한다.
4. 최대 규모 협상에서 비LLM 기능의 Peak RSS 또는 PSS를 측정한다.
5. LLM과 협상 기능을 동시에 실행했을 때 Memory Limiter 이벤트, LMK 및 심각한 응답시간 저하가 발생하지 않는지 확인한다.

이 문서의 계산 결과는 용량 검토를 위한 이론 상한이며, 최종 제품 상한은 실기기 측정과 공존 시나리오 검증으로 확정한다.

## 8. 근거 자료

- Android Open Source Project, [Memory Limiter](https://source.android.com/docs/core/perf/memory-limiter)
- Android Developers, [Memory allocation among processes](https://developer.android.com/topic/performance/memory-management)
- Android Developers, [dumpsys로 PSS, USS, RSS 측정](https://developer.android.com/tools/dumpsys)
