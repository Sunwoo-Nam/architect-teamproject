# DP — 장애 격리(Fault Isolation) 후보 비교

> **대상 QAS**: [QAS-008 세션 복구 성공률 ≥ 95%](../07-QAS.md) (Mapped NFR: [NFR-MAF-03](../05-NFR.md))
> **연관 DP**: [DP-A2 세션 상태 영속화 (Keystone)](../08-DP_풀어야할문제.md)
> **다이어그램**: [DP-fault-isolation-candidates.drawio](./DP-fault-isolation-candidates.drawio) (최하단에 B vs C 신규 다이어그램 추가)
>
> 본 문서는 IDS → MAF(Meta/Orchestrator/Sub-Agent) → 협상 → 외부 도구(Android 앱 제어)로 이어지는
> 긴 프로세스에서 **장애를 어떻게 격리할 것인가**에 대한 후보안을 정리하고, 프로젝트의 QAS를 기준으로 비교한다.
> 본 DP는 현재 [08-DP_풀어야할문제.md](../08-DP_풀어야할문제.md)에 등록되지 않은 **신규 결정 후보**이며, 합의 후 정식 DP로 승격 여부를 결정한다.
>
> **이전 버전과의 차이**: 이전 버전에서는 후보 A(단일 프로세스 + 논리적 격리만, 감독 없음)를 *최소 기본안*으로 포함했으나, 검토 결과 본 프로젝트에서 A는 모듈 단위 회수가 전혀 불가능해 가치가 작다고 판단되어 본 버전에서는 **B와 C 두 후보만 남긴다**. (A의 분석은 git 이력에서 확인 가능.)

---

## 0. 논의의 전제 (이 문서가 서 있는 4개의 기둥)

후보 비교에 들어가기 전에, 분석을 가능하게 한 전제들을 명시한다. (이것이 바뀌면 결론도 바뀐다.)

1. **장애 격리 ≠ 장애 복구.** 격리는 "장애를 가둬서 번지지 않게" 하는 것이고, QAS-008이 요구하는 "복구 성공률 95%"를 실제로 만드는 엔진은 **상태 영속화(DP-A2)**다. → 모든 후보는 복구를 DP-A2에 의존하며, 격리는 그 위에서 *장애 파급 범위(blast radius)*와 *영속화로 못 푸는 장애(멈춤·폭주)*만 담당한다.

2. **온디바이스 자원이 지배적 제약이다.** [QAS-014](../07-QAS.md)는 MAF에 **CPU 피크 40% / Memory 300MB**(Galaxy S26)를 못박는다. 동시 세션은 이 예산을 **공유**한다. → 프로세스를 늘리는 격리는 자원 예산과 정면 충돌한다.

3. **제어 대상은 "내 폰"이고, 제어 방식은 화면 이해(VLM)다.** Android 에이전트(ZeroClaw 계열 등)의 앱 제어는 **Accessibility Service + 스크린샷/VLM 화면 읽기 + 좌표 기반 탭/스크롤**로 이루어진다. Accessibility Service는 **앱 프로세스에 묶여 있어서**, "외부 장치라 격리한다"는 명분은 성립하지 않는다. (출처: 8절)

4. **"재시작하는 단위 크기(restart granularity)"는 "OS 프로세스 단위 크기"와 다르다.** "막힌 모듈만 죽이고 되살리기"는 OS 프로세스를 나누지 않고도 **감독자 트리(supervision tree, 같은 프로세스 안의 감독 구조)** 만으로 얻을 수 있다. OS 프로세스 분리가 *유일한* 회수 수단인 경우는 **취소 불가 네이티브 호출에서의 멈춤(native blocking)**뿐이다.

---

## 1. 평가 기준 (Evaluation Criteria)

프로젝트 QAS에 매핑한 평가축이다. 격리 후보가 **상충(trade-off)**시키는 품질속성을 중심으로 선정했다.

| # | 평가축 | 근거 QAS/NFR | 격리가 미치는 영향 |
|---|---|---|---|
| E1 | **온디바이스 자원** | [QAS-014](../07-QAS.md) | 프로세스·모델 중복 로딩·프로세스 간 통신(IPC) 버퍼가 메모리/CPU 잠식 |
| E2 | **통신 지연** | [QAS-002](../07-QAS.md) (≤180s) | 모듈 간 IPC 직렬화로 지연 누적 |
| E3 | **멈춤·폭주(hang/runaway) 회수** | (QAS-007 기술적 실패 방지) | 멈춤·폭주를 끊고 되살리는 능력 |
| E4 | **동시 세션 장애 파급 범위 (blast radius)** | (멀티세션 운영) | 한 세션 장애가 다른 세션에 번지는가 |
| E5 | **세션 복구 적합성** | [QAS-008](../07-QAS.md) (≥95%) | 중단 지점부터 재개가 쉬운 구조인가 (실엔진은 DP-A2) |
| E6 | **상태 일관성** | [QAS-011/012](../07-QAS.md) (불일치 0%) | 상태가 분산될수록 한 시점의 통합 스냅샷·동기화가 어려움 |
| E7 | **복잡도 / 유지보수** | (Maintainability) | 구현·디버깅·운영 난이도 |

> 표기: ★★★ 강함 · ★★ 보통 · ★ 약함/위배 위험

---

## 2. 후보안

두 후보는 **"막힌 단위를 어느 정도의 크기로 강제종료·재시작하는가(재시작 단위)"** 축 위에 놓인다.
공통적으로 복구는 **DP-A2 영속화**에 의존한다.

> **후보 구조에 대한 주의 — B와 C는 누적 관계다.** 기능적으로 **B ⊂ C**이다 (C는 B + 자격 있는 컴포넌트만 별도 프로세스 분리). 따라서 실질 결정은 다음 한 질문으로 환원된다:
> - **B ↔ C**: 취소 불가 네이티브 호출에서 멈추는(native blocking) 컴포넌트를 별도 OS 프로세스로 분리할 것인가? (같은 프로세스 안에서는 회수할 수 없는 영역의 격리 vs 분리 경계 K개의 프로세스 간 통신(IPC)·감시자(watchdog) 비용)
>
> 즉 **B = 감독자 트리에 투자한 단일 프로세스안**, **C = 감독자 트리 + 선택적 분리안**.

> **감시자(watchdog) 구현 부담 — 두 후보 공통.** Android는 systemd(`Restart=always`)·launchd(`KeepAlive`)·Kubernetes(`livenessProbe`) 같은 **표준 감시자 서비스를 제공하지 않는다**. 따라서 본 문서의 두 후보 모두 `ForegroundService`(전경 서비스) + `START_STICKY`(자동 재시작 플래그) + `AlarmManager`(OS 알람으로 자기 깨우기) + 살아있음을 알리는 파일/Binder 응답 확인(ping)을 **직접 조립**해야 한다. 이 비용은 후보별로 다르게 누적된다(아래 각 단점 참조). 자세한 패턴은 8절 Android 레퍼런스.

### 후보 B. 단일 프로세스 + 감독자 트리 (Supervision Tree)
- **구조**: 온디바이스 모듈(IDS·Meta·Sub·Orchestrator·Device I/O) 전체를 **한 OS 프로세스**에. 모듈을 **감독되는 task**로 두고 **감독자(Supervisor)** 가 관리. 막힌 모듈의 task만 **취소 + 같은 프로세스 안에서 재생성**. 회수 불가 시 **서비스를 통째로 자동 재시작**해 상위 단계로 격상(escalation).
- **재시작 단위 = 모듈 task (같은 프로세스 안, 저비용)**.
- **실증 근거**: Android 에이전트 런타임 ZeroClaw가 실제로 쓰는 방식 — **네이티브(C++/Rust) 코드를 호출하는 지점마다 *안전장치*를 둬서, 그 안에서 사고가 나도 앱 전체가 죽지 않고 그 호출만 실패하도록 막는다. 그래도 어쩌다 서비스가 통째 죽으면 Android OS가 자동으로 다시 띄운다.** Chrome처럼 모듈마다 별개 프로세스로 쪼개지는 *않는다*. (8절)
- **장점**
  - **모듈 단위 재시작을 프로세스 분리 없이** 확보 → **E3 ★★** (단, 협조적으로 취소 가능한 장애 한정).
  - 단일 프로세스라 자원·지연·일관성이 가장 가벼움 → **E1·E2·E6 ★★★**.
  - 구조가 비교적 단순 → **E7 ★★**.
- **단점**
  - 같은 프로세스 안의 취소는 **협조적(cooperative)** — 모듈이 비협조적 네이티브 코드에 박히면 강제 중단(abort) 불가. 이 경우 **프로세스 통째 재시작**으로 떨어짐 → **E3는 협조적 장애에 한해서만 우위, 취소 불가 네이티브 멈춤 영역에서는 ★로 추락**.
  - 동시 세션 장애 파급 범위(blast radius)는 통째 재시작으로 격상될 때 여전히 동시 세션 영향 → **E4 ★★는 협조적 장애에 한해서만 유효**.
  - **감독자 레이어 자체가 위험원**이 될 수 있음: 재시작 폭주(restart storm — 결정론적 실패 모듈의 무한 재시작), 에러 은폐, 오재시작 → 최대 재시작 횟수 제한(max-restart) 등 추가 기계장치 필요.
  - **감시자 구현 부담(중)**: 외부 감시자 + 같은 프로세스 안 감독자 레이어(Kotlin Coroutines `SupervisorJob` / `withTimeout` 활용 가능) + 최대 재시작 횟수 정책.

### 후보 C. 선택적 프로세스 분리 (Selective Process Isolation)　★ 권장

> **요지**: B만으로는 회수 불가능한 네이티브 멈춤(native blocking)이 본 프로젝트에서 *불가피*하다. 그래서 C를 **"B를 베이스로 두고, 분리 자격(취소 불가 네이티브 멈춤)이 있는 컴포넌트만 별도 프로세스로 빼는"** 형태로 정의한다. 이는 Chrome 사이트 격리·Android 시스템 서비스(mediaserver·audioserver)·Erlang OTP의 네이티브 함수(NIF) 분리 등 산업 표준 패턴(**격벽 패턴, bulkhead pattern**)과 동일한 사고다.

- **구조**: 메인 프로세스는 B(감독자 트리)로 운영하고, **취소 불가 네이티브 멈춤 컴포넌트만 별도 OS 프로세스**로 분리. 본 프로젝트의 분리 후보는 **(a) LLM 추론(Model-Server 프로세스)** 과 **(b) Accessibility Service**(Android 정책상 별도 프로세스 가능 여부는 5절 미결 변수). 분리 경계는 *2~3개*로 한정.
- **재시작 단위 = 일반 모듈은 task(같은 프로세스 안), 분리된 컴포넌트는 그 프로세스만 강제 종료(kill) 후 재기동**.
- **분리 자격 결정 트리** (모듈을 분리할지 판단할 때 적용):

  ```
  모듈 X를 별도 프로세스로 분리해야 하는가?

  ① X가 협조적 취소(cooperative cancellation)를 지원하는가?
     (취소 토큰/시간 초과에 반응해 정해진 시간 안에 깔끔하게 멈출 수 있는가)
     ├─ 예 → 감독자 트리(B)로 충분. 분리하지 말 것.
     └─ 아니오 → X는 취소 불가 네이티브 멈춤(native blocking). 분리 후보로 진행 ↓

  ② X의 장애가 잦은가, 또는 통째 재시작이 다른 진행 중인 작업에
     큰 충격을 주는가?
     ├─ 아니오 → 분리 비용 > 회수 이득. B 수준 통째 재시작 수용.
     └─ 예 → 분리 결정. AIDL/Binder(Android의 프로세스 간 통신) 인터페이스 정의 + 감시자 추가.
  ```
  → 본 프로젝트에서 ①·② 모두 통과하는 모듈: **LLM 추론**(거의 확정), **Accessibility Service**(분리 가능성 검증 후 결정 — 5절).

- **장점**
  - **취소 불가 네이티브 멈춤 회수 가능** → **E3 ★★★** (B의 ★★ 한계 돌파).
  - 분리된 컴포넌트의 멈춤이 메인을 끌고 가지 않음 → 메인은 계속 동작 → **E4 ★★** (분리 영역에 한해 격리).
  - 일반 모듈은 여전히 B와 동일한 단일 프로세스라 자원·일관성 부담은 *분리 경계 K개*에만 비례 (전면 분리 대비 압도적으로 작음).
  - 산업 표준 패턴(Chrome·Android 시스템 서비스·Erlang)으로 검증됨.
- **단점**
  - 분리 경계 K개당 비용: AIDL/Binder 인터페이스, 감시자 응답 확인(ping), 재시작 폭주 방지, Model-Server 프로세스의 모델 로딩 수명 관리 → **E1·E2 ★★** (B보다 약간 부담↑).
  - 분리 경계에서의 시점 동기화 비용은 *경계 수에 비례* — K=2~3이라 누적 부담 제한적이지만 0은 아님 → **E6 ★★**.
  - **감시자 구현 부담(중)**: B의 외부 감시자 + 같은 프로세스 안 감독자 + 분리 컴포넌트별 AIDL 응답 확인 감시자. B 대비 분리 경계 K개의 감시자 인프라가 추가.
  - Android Accessibility Service의 별도 프로세스 분리 가능성은 *프레임워크 제약*에 종속 → 5절 미결 변수.

---

## 3. 비교표

| 평가축 | B. 단일+감독자 트리 | C. 선택적 분리 ★ |
|---|:---:|:---:|
| E1 온디바이스 자원 (QAS-014) | ★★★ | ★★ |
| E2 지연 (QAS-002) | ★★★ | ★★ |
| E3 멈춤/폭주 회수 ※2 | ★★ (협조적 장애 한정) | ★★★ (취소 불가 네이티브 멈춤 포함) |
| E4 동시세션 장애 파급 범위 ※2 | ★★ | ★★ |
| E5 세션 복구 적합성 (QAS-008) ※1 | ★★ | ★★ |
| E6 상태 일관성 (QAS-011/012) | ★★★ | ★★ |
| E7 복잡도 / 자체 위험 | ★★ | ★★ |

> **※1 — E5는 두 후보가 동급.** QAS-008(복구율 95%)은 "세션이 *이미 중단된 후* 재개 성공률"이며, 그 수치는 두 후보 모두 **전적으로 DP-A2(영속화)가 결정**한다. C의 분리 경계 K=2~3에서의 시점 동기화 비용은 *복구 정합성에는* 부담이 되지만 K가 작아 ★★ 유지 가능.
>
> **※2 — E3에서 두 후보 차이는 "어떤 종류의 장애를 회수할 수 있는가"에 있다.** B는 *협조적으로 취소 가능한* 장애를 모듈 단위로 회수 가능 (그러나 취소 불가 네이티브 멈춤은 통째 재시작으로 떨어짐). C는 *취소 불가 네이티브 멈춤*까지 분리된 프로세스 강제 종료로 회수 가능. 본 프로젝트는 LLM 추론·Accessibility라는 *불가피한 네이티브 멈춤 컴포넌트*가 있어 B의 ★★는 *그 영역에 한해 ★*로 떨어진다 — 이게 C가 권장되는 결정적 근거.

---

## 4. 권고 (Recommendation)

본 프로젝트에서는 **C(선택적 분리)를 권장**한다. 그 근거를 정리하면:

### 4.1 본 프로젝트가 취소 불가 네이티브 멈춤을 *불가피하게* 가진다

B는 *협조적 취소(cooperative cancellation)* 가정 위에 서 있다. 즉 모든 모듈이 시간 초과/취소 토큰에 *반응해서* 정해진 시간 내에 멈출 수 있어야 같은 프로세스 안의 회수가 성립한다. 그러나 본 프로젝트는 다음 두 컴포넌트를 *반드시* 포함한다:

| 컴포넌트 | 왜 취소 불가 네이티브 멈춤인가 |
|---|---|
| **LLM 추론** | 모델의 네이티브(C++/CUDA/NNAPI) 추론 루프는 한 번 시작하면 *협조적 취소를 지원하지 않음*. 추론이 멈추면 프로세스 통째 강제 종료 외에 회수 수단이 없다 |
| **Accessibility Service** | Android 시스템과 직접 결합. 무한 루프·교착(deadlock) 시 *앱이 응답성을 잃지 않은 채* 모듈만 끊는 같은 프로세스 안 메커니즘이 없음 |

이 두 컴포넌트에 한해서는 **B의 감독자 트리가 ★를 받는다** — 같은 프로세스 안에서의 회수가 원리적으로 불가능하기 때문. 그래서 본 프로젝트에서 *순수* B는 취소 불가 네이티브 멈춤 영역에서 회수 능력이 사라진다.

### 4.2 C(선택적 분리)가 정합한 처방

- 일반 모듈(IDS·Meta·Sub·Orchestrator 등)은 협조적 취소를 지원하므로 **B와 동일하게 같은 프로세스 안 감독**으로 처리
- LLM 추론·Accessibility만 **별도 OS 프로세스로 분리**해 강제 종료로 회수 가능하게 함 (K=2)
- 분리 경계 비용(E1·E2·E6 각 ★★)이 누적되지만, K=2라 한정적
- 전면 분리(이전 검토 안)의 자기모순(Android 메모리 부족 시 자동 종료(LMK) 충돌, 자원 폭증, 일관성 붕괴)은 발생하지 않음

### 4.3 산업 표준과의 일관성

C가 채택하는 *선택적 분리(격벽 패턴, bulkhead pattern)* 는 Chrome 사이트 격리, Android 시스템 서비스(mediaserver·audioserver·surfaceflinger), Erlang OTP의 네이티브 함수(NIF) 분리에서 동일하게 쓰이는 패턴이다. "취소 불가 네이티브 멈춤만 분리"라는 원칙은 *원리적*으로 정당화된다 (전제 4: "OS 프로세스 분리가 *유일한* 회수 수단인 경우는 취소 불가능한 네이티브 멈춤뿐").

### 4.4 B는 언제 선택되는가

C를 권장한다고 B가 무가치한 것은 아니다. **취소 불가 네이티브 멈춤 컴포넌트가 *없는* 프로젝트** — 예: 순수 비즈니스 로직 + 외부 API 호출만으로 구성된 시스템 — 에서는 B가 더 정합하다. 분리 경계 K=0이 되니 자원·복잡도 부담이 가장 작다.

본 프로젝트는 LLM·Accessibility 때문에 그 경우에 해당하지 않으므로 C로 간다.

### 4.5 중요 — QAS-008과의 관계

어느 후보를 택하든 **QAS-008(복구율 95%) 달성 여부는 동일하게 DP-A2(영속화)에 달려 있다.** B·C 사이의 차이는 *복구율*이 아니라 *어떤 장애를 회수할 수 있는가*와 *재시작 빈도가 가용성에 주는 충격*이다. C가 추가로 회수하는 것은 **취소 불가 네이티브 멈춤**으로, 본 프로젝트의 LLM·Accessibility라는 *불가피한* 특성에 직접 대응한다.

---

## 4-1. 감시 계층(외부 감시자 / 같은 프로세스 안 감독자)의 위치와 동작

후보 비교의 ★ 점수는 **"감시 계층이 제대로 동작한다"** 는 전제 위에 서 있다. 이 절은 그 전제를 명시한다. Android는 systemd·launchd·Kubernetes 같은 표준 감시자를 제공하지 않으므로, **두 후보 모두 감시 계층을 직접 조립해야** 한다.

### 4-1.1 외부 감시자(Watchdog) vs 같은 프로세스 안 감독자(Supervisor) — 무엇이 다른가

| 축 | **외부 감시자 (Watchdog)** | **같은 프로세스 안 감독자 (Supervisor)** |
|---|---|---|
| 실행 위치 | **별도 프로세스 / OS / 외부** | **같은 프로세스 안** |
| 감시 대상 | 프로세스 1개의 생사 (살아있나) | 프로세스 안의 N개 모듈/액터/태스크 |
| 감시 방법 | 살아있음 파일의 마지막 수정 시각(mtime) · 응답 확인(ping) · AlarmManager 자기-깨우기 | 모듈의 예외·시간 초과·심각 에러(panic)를 직접 catch |
| 재시작 단위 | **프로세스 전체** (콜드 스타트) | **모듈 task 하나** (같은 프로세스 안 재생성, 저비용) |
| 회수 가능한 장애 | 충돌(crash), 동결(freeze), 무응답 (강제 종료 가능) | **협조적**으로 취소 가능한 장애만 (예외·비동기 시간 초과) |
| 한계 | 재시작 단위가 큼 — 무고한 모듈까지 같이 죽음 | **취소 불가 네이티브 멈춤은 회수 불가** (자기 자신도 동결됨) |

**핵심 원리**: 같은 프로세스 안 감독자는 자기 프로세스가 동결되면 같이 동결되므로 외부 감시자를 대체할 수 없다. 외부 감시자는 반드시 **다른 실행 컨텍스트(별도 프로세스 또는 OS 알람)** 에 있어야 한다.

### 4-1.2 후보별 감시 계층 배치

#### 후보 B — 같은 프로세스 안 감독자 + 외부 감시자 2층

```
┌─ [Watchdog]  (외부: FG-Service + AlarmManager + heartbeat 파일)
│       ↑ escalation (Supervisor도 회수 못 한 경우)
│       │
│  ┌─ [App proc]
│  │    ┌─ [Supervisor]  (in-process, Kotlin Coroutines SupervisorJob 등)
│  │    │      │ abort + restart (모듈 task 단위)
│  │    │      ↓
│  │    │  ┌─ IDS task ─┐
│  │    │  ├─ Meta task ─┤  ← 예외/timeout → Supervisor가 그 task만 재생성
│  │    │  ├─ Sub task  ─┤
│  │    │  ├─ Orchestrator task ─┤
│  │    │  └─ Device task ─┘
│  │    └─ (선택) max-restart 정책, restart storm 방지
```

- **감시 계층**: 2개 (같은 프로세스 안 감독자 1층 + 외부 감시자 2층)
- **재시작 단위**: 1층은 모듈 task, 2층은 프로세스
- **상위 단계 격상(escalation) 규칙**: 감독자가 N회 재시도 실패 또는 비협조적 장애 감지 → 외부 감시자로 격상 → 프로세스 통째 재시작
- **구현 부품**: `ForegroundService`(전경 서비스) + `START_STICKY`(자동 재시작 플래그) + `AlarmManager.setExactAndAllowWhileIdle` + 살아있음 파일 + `SupervisorJob` + `withTimeout` + 최대 재시작 횟수(max-restart) 정책

#### 후보 C — B의 2층 + 분리 컴포넌트별 AIDL 감시자

```
┌─ [Watchdog]  (외부, B와 동일 구조)
│       ↑ escalation (Supervisor도 회수 못 한 경우)
│       │
│  ┌─ [Main proc]
│  │    ┌─ [Supervisor]  (in-process, B와 동일)
│  │    │      │ abort + restart (모듈 task 단위)
│  │    │      ├─ IDS · Meta · Sub · Orchestrator task ─┘
│  │    │
│  │    └─ [Per-isolate Watchdog]  (분리 컴포넌트별 AIDL ping)
│  │         │ AIDL ping() 매 N초
│  │         ├─→ [Model-Server proc]  (LLM 추론 전담)
│  │         │       └─ 무응답 시 Main이 killProcess + bind 재시작
│  │         └─→ [Accessibility Service proc]  (분리 가능 시)
│  │                 └─ 무응답 시 Main이 unbind + 재시작
```

- **감시 계층**: 2개 (같은 프로세스 안 감독자 + 외부 감시자) **+** 분리 컴포넌트별 같은 프로세스 안 AIDL 감시자
- **재시작 단위**: 일반 모듈은 task (B와 동일), 분리 컴포넌트는 그 프로세스만 강제 종료 후 재기동
- **단일 장애점(SPOF) 구조**: Main이 죽으면 외부 감시자가 처리(B와 동일). 분리 컴포넌트는 Main의 자식으로 관리.
- **추가 부품 (B 대비)**: 분리 컴포넌트당 **AIDL/Binder** 인터페이스(`ping()`·요청·응답) + `onServiceDisconnected` 콜백(서비스 끊김 알림) + `bindService` 재연결 + Model-Server 프로세스의 모델 로딩 수명 관리 (콜드 스타트 vs 미리 로드) + 재시작 폭주 방지 정책. *분리 경계 K개에만 비례*.

### 4-1.3 공통 동작 시퀀스 (장애 발생 → 복구)

```
1. 모듈/프로세스에서 멈춤·충돌·예외 발생
2. 감시 계층이 감지
   - 같은 프로세스 안 감독자(B/C): 모듈의 예외·시간 초과를 직접 catch
   - 외부 감시자: 살아있음 신호 미수신 N초 또는 AIDL 응답 확인(ping) 무응답
3. 회수 시도 (재시작 단위가 작은 것부터)
   - 1층: 모듈 task 중단 + 재생성 (B/C 공통)
   - 2층(C만): 분리 컴포넌트는 그 프로세스만 강제 종료
   - 3층: 메인 프로세스 강제 종료 (Process.killProcess / SIGKILL)
4. OS 재기동
   - START_STICKY 플래그로 서비스 자동 재시작
   - 또는 AlarmManager가 PendingIntent로 부활 트리거
5. 재기동된 프로세스가 DP-A2(영속화)에서 세션 상태 로드 → 중단 지점부터 재개
   ↑ QAS-008 복구율 95%를 실제로 결정하는 단계 (감시 계층은 여기까지 도달하는 길을 만들 뿐)
```

### 4-1.4 왜 이 절이 ★ 점수에 영향을 주는가

- **B·C 모두 ★ 점수는 "감시 계층이 동작한다"는 전제 위에 있다.** 감시 계층 구현이 부실하면 두 후보 모두의 E3·E4·E5가 동시에 추락한다.
- **C의 ★ 점수는 위 토폴로지(B의 2층 + 분리 컴포넌트별 AIDL 감시자)를 모두 포함한 값**이다. 분리 경계 K=2~3에 한정되므로 *전면 분리* 시나리오의 비용 폭증(Manager 단일 장애점, 모든 모듈 프로세스 간 통신, 재시작 폭주 다발)은 발생하지 않는다.
- 다이어그램([DP-fault-isolation-candidates.drawio](./DP-fault-isolation-candidates.drawio)) 최하단 "B vs C" 영역에 본 절의 토폴로지가 시각화되어 있다.

---

## 5. 결정을 가르는 미결 변수 (Open Questions)

본 권고(C 선택적 분리)의 구체 형태는 아래 값에 따라 결정된다. **확정 필요.**

1. **Accessibility Service의 별도 프로세스 분리 가능성**: Android 프레임워크 제약 하에서 Accessibility Service를 메인 앱과 다른 OS 프로세스에 띄우는 것이 기술적으로 가능한지 검증 필요. 불가하면 C의 분리 경계는 K=1(LLM 추론만)로 축소되고, Accessibility 영역은 B 수준의 통째 재시작으로 떨어진다.
2. **Model-Server 프로세스의 모델 로딩 정책**: 콜드 스타트(요청 시 로드, 메모리 절약·지연↑) vs 항상 로드(메모리 소비·지연↓). 본 프로젝트의 QAS-002(≤180s)·QAS-014(Memory 300MB) 부등식에 맞춰 결정 필요.
3. **분리 자격 추가 후보 검증**: LLM·Accessibility 외에 *취소 불가 네이티브 멈춤* 자격이 있는 모듈이 더 있는가? (예: 외부 SDK·센서 통합 중 협조적 취소를 지원하지 않는 사례 발견 시 분리 후보 추가)
4. **동시 세션 수**: 본 프로젝트가 실제로 동시 N세션을 운영하는가, 보통 1~2세션인가? → 1~2개면 C로 충분. 많고 *세션 간* 격리가 추가로 필요하면 *세션별 분리*를 C 위에 얹는 추가 결정 필요(현재는 범위 밖).
5. **멈춤의 성격 분포**: 취소 불가 네이티브 멈춤의 발생 빈도가 *드물면* B로 후퇴해도 무방. C의 분리 비용을 정당화하려면 네이티브 멈춤이 *실제로 발생*한다는 운영 데이터(또는 합리적 가정)가 필요.

---

## 6. 다이어그램

[DP-fault-isolation-candidates.drawio](./DP-fault-isolation-candidates.drawio) — 두 가지 다이어그램이 한 페이지에 위·아래로 배치되어 있다 (draw.io로 열어 편집 가능):

- **상단 (이전 버전)**: A/B/C 3안 비교. 보존용 — *전면 분리* C를 포함한 초기 검토 형태.
- **하단 (본 버전 — 신규)**: B vs C 두 안 비교. 현재 권고 구조 — 메인 프로세스(감독자 트리) + 분리 컴포넌트 K개(LLM·Accessibility).

본문은 하단 다이어그램을 기준으로 한다.

---

## 7. 다음 단계

- 5절 미결 변수(특히 **Accessibility Service 분리 가능성**과 **Model-Server 모델 로딩 정책**)를 확정 → C의 구체 분리 경계 K 확정.
- 확정 시 본 문서를 [08-DP_풀어야할문제.md](../08-DP_풀어야할문제.md)에 **정식 DP("장애 격리 전략")로 등록**할지 결정.
- 격리(본 문서)와 짝을 이루는 **복구 설계(DP-A2: 영속화 — Event Sourcing / Snapshot / Hybrid)**를 후속 논의로 진행. 분리된 Model-Server 프로세스의 *세션 상태 영속화 책임 분배*를 함께 다뤄야 함.

---

## 8. 근거 / 출처

- 프로젝트 문서: [05-NFR.md](../05-NFR.md), [07-QAS.md](../07-QAS.md), [08-DP_풀어야할문제.md](../08-DP_풀어야할문제.md)
- Android 감시자 / 서비스 생존 패턴 (표준 감시자 부재로 직접 조립 필요):
  - `Service.START_STICKY` (서비스 강제 종료 시 OS 자동 재기동): https://developer.android.com/reference/android/app/Service#START_STICKY
  - ForegroundService 수명/제약: https://developer.android.com/develop/background-work/services/foreground-services
  - `AlarmManager.setExactAndAllowWhileIdle` (Doze 상태에서도 정시 발동): https://developer.android.com/reference/android/app/AlarmManager#setExactAndAllowWhileIdle(int,%20long,%20android.app.PendingIntent)
  - `Process.killProcess(myPid())` (자기 자신 강제 종료): https://developer.android.com/reference/android/os/Process#killProcess(int)
  - AIDL / Binder (proc 간 ping·수명 콜백 `onServiceDisconnected`): https://developer.android.com/develop/background-work/services/aidl
  - Kotlin Coroutines `SupervisorJob` (in-process Supervisor 부품): https://kotlinlang.org/api/kotlinx.coroutines/kotlinx-coroutines-core/kotlinx.coroutines/-supervisor-job.html
  - WorkManager `BackoffPolicy` (재시작 백오프): https://developer.android.com/reference/androidx/work/BackoffPolicy
- Android 에이전트 제어 방식 (Accessibility + VLM, ZeroClaw식 격리/복구) — 외부 조사:
  - ZeroClaw-Android: https://github.com/Natfii/ZeroClaw-Android
  - ZeroClaw 공식: https://zeroclaw.net/
  - MobClaw (Accessibility 기반 폰 제어): https://github.com/wamynobe/mobclaw
  - mobileClaw (VLM 화면 읽기 + 좌표 탭): https://github.com/eggbrid2/mobileClaw
  - AppAgent (LLM 멀티모달 스마트폰 에이전트): https://github.com/TencentQQGYLab/AppAgent

---

_본 문서는 2026-06-11 작성·2026-06-15 B/C 2-안 구조로 재정리되었으며, [07-QAS.md](../07-QAS.md)·[05-NFR.md](../05-NFR.md)의 변경에 종속된다._
