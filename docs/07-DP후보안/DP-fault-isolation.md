# DP — 장애 격리(Fault Isolation) 후보 비교

> **대상 QAS**: [QAS-008 세션 복구 성공률 ≥ 95%](../07-QAS.md) (Mapped NFR: [NFR-MAF-03](../05-NFR.md))
> **연관 DP**: [DP-A2 세션 상태 영속화 (Keystone)](../08-DP_풀어야할문제.md)
> **다이어그램**: [DP-fault-isolation-candidates.drawio](./DP-fault-isolation-candidates.drawio) (최하단에 B vs C 신규 다이어그램 추가)
>
> 본 문서는 IDS → MAF(Meta/Orchestrator/Sub-Agent) → 협상 → 외부 도구(Android 앱 제어)로 이어지는
> 긴 프로세스에서 **장애를 어떻게 격리할 것인가**에 대한 후보안을 정리하고, 프로젝트의 QAS를 기준으로 비교한다.
> 본 DP는 현재 [08-DP_풀어야할문제.md](../08-DP_풀어야할문제.md)에 등록되지 않은 **신규 결정 후보**이며, 합의 후 정식 DP로 승격 여부를 결정한다.
>
> **이전 버전과의 차이 (2026-06-16)**: 이전 버전에서는 후보 A(단일 프로세스 + 논리적 격리만, 감독 없음)를 포함했고, B는 *전체 모듈을 한 프로세스로 묶는* 안이었다. 검토 과정에서 (1) A는 모듈 단위 회수 불가로 가치가 작고, (2) LLM·Accessibility는 자격 A(취소 불가 네이티브 멈춤)로 *원리적으로 분리 불가피*하다는 사실이 확립되어, 본 버전에서는 **B와 C의 의미를 재정의**한다 — **B = 최소 분리 (자격 A만, K=2)**, **C = 확장 분리 (B + MAF, K=3)**. 실질 결정 질문은 *MAF를 IDS에서 분리할 것인가*. (A와 이전 B 정의는 git 이력 참조.)

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

> **후보 구조에 대한 주의 — B와 C는 누적 관계다.** 두 안 모두 *자격 A* 컴포넌트(LLM 추론·Accessibility Service)는 분리한다 — 이건 *분리 여부*의 결정이 아니라 *프로젝트 제약상 분리되어야 함*이 자명하기 때문(4.1 참조). 따라서 실질 결정은 다음 한 질문으로 환원된다:
> - **B ↔ C**: 자격 B(생애주기 비대칭) 컴포넌트인 **MAF**를 IDS와 분리할 것인가? (메모리 결정론적 회수·IDS perception 보존 vs 추가 분리 경계 1개의 IPC·수명 관리 비용)
>
> 즉 **B = K=2 최소 분리 (자격 A만)**, **C = K=3 확장 분리 (B + MAF)**. C가 B를 *완전히 포함*하는 진부분집합 관계.

> **감시자(watchdog) 구현 부담 — 두 후보 공통.** Android는 systemd(`Restart=always`)·launchd(`KeepAlive`)·Kubernetes(`livenessProbe`) 같은 **표준 감시자 서비스를 제공하지 않는다**. 따라서 본 문서의 두 후보 모두 `ForegroundService`(전경 서비스) + `START_STICKY`(자동 재시작 플래그) + `AlarmManager`(OS 알람으로 자기 깨우기) + 살아있음을 알리는 파일/Binder 응답 확인(ping)을 **직접 조립**해야 한다. 이 비용은 후보별로 다르게 누적된다(아래 각 단점 참조). 자세한 패턴은 8절 Android 레퍼런스.

### 후보 B. 최소 분리 (K=2) — 자격 A만 분리

- **구조**: 메인 프로세스에 **IDS + MAF(Meta·Sub·Orchestrator)** 가 *함께* 거주하며 감독자 트리(supervision tree)로 관리. 자격 A 컴포넌트인 **LLM 추론**은 Model-Server 프로세스로 분리, **Accessibility Service**는 별도 프로세스로 분리(Android 프레임워크 허용 시 — 5절 미결 변수).
- **재시작 단위**: 메인 안의 모듈은 task(같은 프로세스 안), 분리된 컴포넌트는 그 프로세스만 강제 종료(kill) 후 재기동.
- **분리 경계 K=2** (LLM, Accessibility).
- **장점**
  - 자격 A 컴포넌트는 분리되어 있어 취소 불가 네이티브 멈춤도 회수 가능 → **E3 ★★★**.
  - IDS↔MAF가 같은 프로세스라 함수 호출로 통신 → **IPC 지연 없음, QAS-002에 유리** → **E2 ★★★**.
  - 분리 경계가 K=2로 가장 적어 자원·복잡도 부담이 C보다 작음 → **E7 ★★**.
- **단점**
  - **MAF idle 시 메모리가 같은 프로세스에 누적** — JVM GC가 확률적으로 회수하지만 보장 없음. QAS-014(Memory 300MB)에 압박 → **E1 ★★** (C와 비등하거나 살짝 불리).
  - **MAF crash가 IDS를 끌고 감** — 메인 프로세스 통째 재시작 시 IDS의 누적 perception 상태가 함께 손실됨 → **E4 ★★**.
  - **lifecycle mismatch가 같은 컨테이너에 묶임** — 데몬형(IDS)과 태스크형(MAF)이 한 프로세스에 공존하는 안티 패턴. Chrome·Android·Erlang 등 산업 표준이 일관되게 분리하는 사고를 따르지 않음.
  - 감독자 레이어 자체가 위험원이 될 수 있음(재시작 폭주, 에러 은폐, 오재시작) → 최대 재시작 횟수 제한 등 추가 정책 필요.

### 후보 C. 확장 분리 (K=3) — B + MAF 추가 분리　★ 권장

> **요지**: C는 **B(K=2)에 MAF 분리(자격 B — 생애주기 비대칭)를 추가**한 안이다. 자격 A 분리(LLM·Accessibility)는 두 후보 공통이고, C만의 차이는 *MAF를 별도 OS 프로세스로 분리*하는 것. 이는 Chrome(network process 상시 vs renderer 태스크형), Android(system_server 상시 vs 앱 프로세스 요청형), Erlang OTP(application supervisor 상시 vs job workers 태스크형) 등 산업 표준 패턴(**격벽 패턴, bulkhead pattern**)에서 *예외 없이* 적용되는 사고다.

- **구조**: 메인 프로세스에 **IDS만** 거주(상시 데몬, perception 누적). **MAF(Meta·Sub·Orchestrator)** 는 별도 OS 프로세스로 분리(태스크형, 협상 시점에만 활성). 자격 A 분리는 B와 동일 — **LLM 추론**·**Accessibility Service**.
- **분리 경계 K=3** (LLM, Accessibility, MAF).
- **재시작 단위 = 일반 모듈은 task(같은 프로세스 안), 분리된 컴포넌트는 그 프로세스만 강제 종료(kill) 후 재기동**.
- **분리 자격 결정 트리** (모듈을 분리할지 판단할 때 적용):

  ```
  모듈 X를 별도 프로세스로 분리해야 하는가?

  [1단계 — 분리 자격이 있는가?]

  자격 (A): 기술적 격리 자격
    X가 협조적 취소(cooperative cancellation)를 지원하지 않는가?
    (= 취소 토큰/시간 초과로 깔끔하게 멈출 수 없는 취소 불가 네이티브 멈춤)
    → 예 → 자격 있음
    → 본 프로젝트 해당: LLM 추론, Accessibility Service

  자격 (B): 자원/운영 격리 자격
    X가 시스템의 다른 부분과 생애주기가 비대칭인가?
    (= 상시 떠 있어야 하는 모듈과 특정 작업에서만 활성인 모듈이 섞여 있음)
    그리고 X의 idle 시 메모리 부하가 의미 있는가?
    → 둘 다 예 → 자격 있음
    → 본 프로젝트 해당: MAF (IDS는 상시, MAF는 협상 등 태스크형)

  → (A) 또는 (B) 중 하나라도 yes면 분리 후보로 진행.
  → 둘 다 no면 같은 프로세스 유지 (감독자 트리로 충분).

  [2단계 — 이득이 비용을 정당화하는가?]

  분리 경계 비용(AIDL/Binder 인터페이스, 감시자, 수명 관리)보다
  회수/메모리/격리 이득이 큰가?
    → 예 → 분리 결정
    → 아니오 → 같은 프로세스 유지
  ```
  → 본 프로젝트에서 분리 결정된 모듈: **LLM 추론**(자격 A, B·C 공통), **Accessibility Service**(자격 A, B·C 공통, 분리 가능성 검증 — 5절), **MAF**(자격 B, C에서만 분리 — 본 DP의 핵심 결정).

- **장점 (B 대비 추가 이득)**
  - **MAF idle 시 메모리 결정론적 회수** → **E1 부분 개선** (같은 프로세스 lazy load는 GC가 확률적이지만 별도 프로세스는 OS가 즉시 회수). QAS-014(Memory 300MB) tight 예산에 유리.
  - **IDS의 누적 perception 상태 보존** → MAF가 죽어도 IDS 프로세스는 계속 동작, 누적 정보 손실 없음 → **E4 ★★★** (B의 ★★ 한계 돌파).
  - 데몬형(IDS)과 태스크형(MAF) 분리 — 산업 표준 패턴과 일치, 운영 위생(operational hygiene) 측면 개선.
- **단점 (B 대비 추가 비용)**
  - **IDS↔MAF가 IPC 경계로 분리됨** → 협상 중 잦은 호출 시 IPC 직렬화 지연 누적, QAS-002(≤180s) 영향 가능 → **E2 ★★** (B의 ★★★보다 불리).
  - **MAF 수명 관리 정책** 추가 필요 (언제 깨우고/죽일지, 콜드 스타트 비용) → **E7 부담↑**, 5절 미결 변수.
  - 분리 경계 K=3, 시점 동기화·감시자 인프라가 B 대비 1개분 추가.

---

## 3. 비교표

| 평가축 | B. K=2 최소 분리 | C. K=3 확장 분리 ★ |
|---|:---:|:---:|
| E1 온디바이스 자원 (QAS-014) ※2 | ★★ | ★★ |
| E2 지연 (QAS-002) ※3 | ★★★ | ★★ |
| E3 멈춤/폭주 회수 | ★★★ | ★★★ |
| E4 동시세션 장애 파급 범위 ※4 | ★★ | ★★★ |
| E5 세션 복구 적합성 (QAS-008) ※1 | ★★ | ★★ |
| E6 상태 일관성 (QAS-011/012) | ★★ | ★★ |
| E7 복잡도 / 자체 위험 ※5 | ★★ | ★★ |

> **※1 — E5는 두 후보 동급.** QAS-008(복구율 95%)은 "세션이 *이미 중단된 후* 재개 성공률"이며, 두 후보 모두 **전적으로 DP-A2(영속화)가 결정**한다. K 차이가 시점 동기화 비용에 영향은 주지만 K=2~3이라 ★★ 유지.
>
> **※2 — E1은 두 측면이 상쇄.** B는 분리 경계가 적어 IPC·감시자 부담↓ 이지만 MAF idle 메모리가 같은 프로세스에 누적되어 확률적 GC에 의존. C는 분리 경계 1개 더 있지만 MAF idle 시 OS가 결정론적으로 회수. *어느 효과가 큰지는 MAF idle 메모리 측정에 달림* (5절 미결 변수). 측정 전 잠정 동급.
>
> **※3 — E2는 B 우위.** B는 IDS↔MAF가 함수 호출(IPC 없음). C는 IDS↔MAF가 IPC 경계라 협상 중 잦은 호출 시 직렬화 지연 누적 — QAS-002(≤180s) 압박 가능. *IDS↔MAF 호출 빈도·페이로드 측정 필요* (5절 미결 변수).
>
> **※4 — E4가 본 DP의 핵심 결정 축.** B에서 MAF crash는 *메인 프로세스 통째 재시작*을 트리거 → IDS의 누적 perception 상태가 함께 손실. C에서 MAF crash는 *MAF 프로세스만 재시작* → IDS는 살아남아 perception 보존. *본 프로젝트의 IDS perception 상태는 시간에 걸쳐 누적되어 복원 비용이 큼* → E4 우위가 C 권장의 결정적 근거.
>
> **※5 — E7은 동급.** B는 K=2로 분리 경계가 적지만 MAF 관련 같은 프로세스 메모리 관리가 새 부담. C는 K=3으로 경계가 1개 더 있지만 MAF 수명 관리 정책이 명시적 — *암묵적 부담을 명시적 부담으로 옮긴 것*이라 절대치는 비등.

---

## 4. 권고 (Recommendation)

본 프로젝트의 핵심 결정 질문은 **"MAF를 IDS와 분리할 것인가?"** 다 (자격 A 분리는 두 후보 공통). 본 권고는 **C(K=3 확장 분리) 채택**이다. 근거를 정리하면:

### 4.1 자격 A 분리는 *불가피* — 두 후보 모두 적용

LLM 추론·Accessibility Service는 *협조적 취소(cooperative cancellation)를 지원하지 않으므로* 같은 프로세스 안에서는 멈춤(hang)을 회수할 수 없다:

| 컴포넌트 | 왜 취소 불가 네이티브 멈춤(자격 A)인가 |
|---|---|
| **LLM 추론** | 모델의 네이티브(C++/CUDA/NNAPI) 추론 루프는 한 번 시작하면 *협조적 취소를 지원하지 않음*. 추론이 멈추면 프로세스 통째 강제 종료 외에 회수 수단이 없다 |
| **Accessibility Service** | Android 시스템과 직접 결합. 무한 루프·교착(deadlock) 시 *앱이 응답성을 잃지 않은 채* 모듈만 끊는 같은 프로세스 안 메커니즘이 없음 |

따라서 B와 C 모두 *이 두 컴포넌트는 분리*한다 (B의 K=2, C의 K=3 중 LLM·Accessibility 2개). 이 부분은 결정 사항이 아님.

### 4.2 본 DP의 진짜 결정 — MAF 분리 여부

B와 C의 *유일한* 차이는 **MAF를 IDS와 같은 프로세스에 둘 것인가(B), 별도 프로세스로 분리할 것인가(C)** 다. 양측의 트레이드오프:

| 축 | B (MAF 같이) | C (MAF 분리) |
|---|---|---|
| MAF idle 메모리 | 같은 프로세스에 누적, GC가 확률적 회수 | OS가 결정론적으로 회수 |
| IDS↔MAF 통신 | 함수 호출 (지연 없음) | IPC (직렬화 지연) |
| MAF crash 영향 | IDS perception까지 함께 손실 | MAF만 재시작, IDS 보존 |
| 수명 관리 복잡도 | 같은 프로세스 메모리 관리 (암묵적) | MAF 깨우기/죽이기 정책 (명시적) |

### 4.3 C 권장의 결정적 근거 — IDS perception 보존 (E4)

본 프로젝트에서 **IDS의 누적 perception 상태는 *시간에 걸쳐 모은 정보*라 복원 비용이 크다**. MAF가 협상 중 crash해서 메인 프로세스가 통째 재시작되면 *영속화 사이 윈도우 동안의 perception이 손실*된다 — 이건 단순 재시작으로 복구되지 않는 가치 손실. C는 MAF를 분리해 *MAF crash가 IDS를 끌고 가지 않게* 함으로써 이 위험을 구조적으로 제거한다.

추가로 다음 세 가지가 C 권장을 강화:
- **메모리 결정론적 회수**: QAS-014(Memory 300MB) tight 예산에서 MAF idle 메모리를 GC에 맡기지 않음
- **lifecycle hygiene**: Chrome·Android·Erlang OTP가 *예외 없이* 데몬형과 태스크형을 분리하는 패턴과 일치
- **명시적 수명 관리**: MAF의 시작/종료 정책이 코드로 드러나 운영 가시성이 좋음

### 4.4 C의 비용은 *측정과 정책*으로 흡수 가능

C의 주된 비용 — IDS↔MAF IPC 지연(E2) — 은 다음으로 완화 가능:
- IDS context를 MAF가 *반복 조회하지 않게* 캐싱 정책 (5절 미결 변수 #5)
- 호출 빈도·페이로드를 *측정해* QAS-002 예산 안에 들도록 조정 (5절 미결 변수 #5)
- MAF 수명 관리 정책을 *단순*하게 (예: 협상 시작 시 fork, 협상 종료 후 N분 idle 시 종료)

### 4.5 B로 후퇴할 조건

다음 *어느 하나라도* 측정·검증 결과 명백하면 C가 정당화되지 않으므로 B로 후퇴 검토:
- MAF idle 메모리 < 10MB (분리 이득 미미)
- IDS↔MAF 호출이 매우 잦고 페이로드 큼 → 캐싱으로도 QAS-002 위반 (분리가 *해로움*)
- MAF 수명 관리 정책이 너무 복잡해 새 위험원이 됨 (E7 폭증)

위 조건은 5절 미결 변수의 측정 항목이다. *측정 전까지는 C 권고이되, 측정 결과 반대로 나오면 B로 재검토.*

### 4.6 중요 — QAS-008과의 관계

어느 후보를 택하든 **QAS-008(복구율 95%) 달성 여부는 동일하게 DP-A2(영속화)에 달려 있다.** B·C의 차이는 *복구율*이 아니라 *재시작이 가용성·perception 보존에 주는 충격*이다. C가 주는 추가 가치는 **"MAF 장애 시 IDS가 살아남는다"** 는 격리 보장.

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

#### 후보 B (K=2) — 메인 + LLM·Accessibility 분리

```
┌─ [Watchdog]  (외부: FG-Service + AlarmManager + heartbeat 파일)
│       ↑ escalation
│       │
│  ┌─ [Main proc]
│  │    ┌─ [Supervisor]  (in-process)
│  │    │      │ abort + restart (모듈 task 단위)
│  │    │      ├─ IDS task ───────┐
│  │    │      ├─ Meta task ──────┤  ← 예외/timeout → Supervisor가 그 task만 재생성
│  │    │      ├─ Sub task ───────┤
│  │    │      └─ Orchestrator task ┘
│  │    │
│  │    └─ [Per-isolate Watchdog]  (자격 A 분리 컴포넌트별 AIDL ping)
│  │         ├─→ [Model-Server proc]  (LLM 추론)
│  │         └─→ [Accessibility Service proc]  (분리 가능 시)
```

- **감시 계층**: 2개 (같은 프로세스 안 감독자 + 외부 감시자) + 자격 A 분리 컴포넌트별 AIDL 감시자
- **재시작 단위**: 메인 모듈은 task, 자격 A 분리 컴포넌트는 그 프로세스만 강제 종료 후 재기동
- **상위 단계 격상(escalation) 규칙**: 감독자가 N회 재시도 실패 또는 비협조적 장애 감지 → 외부 감시자로 격상 → 프로세스 통째 재시작
- **구현 부품**: `ForegroundService` + `START_STICKY` + `AlarmManager.setExactAndAllowWhileIdle` + 살아있음 파일 + `SupervisorJob` + `withTimeout` + 최대 재시작 횟수 정책 + 자격 A 컴포넌트당 AIDL 인터페이스

#### 후보 C (K=3) — B의 토폴로지 + MAF 별도 프로세스

```
┌─ [Watchdog]  (외부, B와 동일)
│       ↑ escalation
│       │
│  ┌─ [Main proc]  ← IDS 전용 (상시 데몬)
│  │    ┌─ [Supervisor]  (in-process, IDS task만)
│  │    │
│  │    └─ [Per-isolate Watchdog]  (3개 컴포넌트 AIDL ping)
│  │         ├─→ [MAF proc]  (Meta · Sub · Orchestrator, 태스크형 — 자격 B)
│  │         │       └─ 무응답 시 Main이 killProcess + bind 재시작
│  │         ├─→ [Model-Server proc]  (LLM 추론 — 자격 A)
│  │         │       └─ 무응답 시 Main이 killProcess + bind 재시작
│  │         └─→ [Accessibility Service proc]  (분리 가능 시 — 자격 A)
│  │                 └─ 무응답 시 Main이 unbind + 재시작
```

- **감시 계층**: B와 동일 + MAF 컴포넌트가 Per-isolate Watchdog 감시 대상에 추가
- **재시작 단위**: IDS는 task (Main 안), 3개 분리 컴포넌트는 그 프로세스만 강제 종료 후 재기동
- **단일 장애점(SPOF) 구조**: Main(IDS)가 죽으면 외부 감시자가 처리. 분리 컴포넌트는 Main의 자식으로 관리.
- **추가 부품 (B 대비)**: MAF AIDL 인터페이스 + MAF 수명 관리 정책(언제 깨우고 죽일지) + IDS↔MAF context 캐싱 정책 (5절 미결 변수).

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

1. **Accessibility Service의 별도 프로세스 분리 가능성**: Android 프레임워크 제약 하에서 Accessibility Service를 메인 앱과 다른 OS 프로세스에 띄우는 것이 기술적으로 가능한지 검증 필요. 불가하면 자격 A 분리 경계는 K=1(LLM 추론만)로 축소되고, Accessibility 영역은 B 수준의 통째 재시작으로 떨어진다.
2. **Model-Server 프로세스의 모델 로딩 정책**: 콜드 스타트(요청 시 로드, 메모리 절약·지연↑) vs 항상 로드(메모리 소비·지연↓). 본 프로젝트의 QAS-002(≤180s)·QAS-014(Memory 300MB) 부등식에 맞춰 결정 필요.
3. **MAF의 idle 시 메모리 부하 측정** *(자격 B 분리 정당화 근거)*: MAF가 작업이 없을 때 같은 프로세스에서 점유하는 메모리(JVM 객체 + 네이티브 버퍼 + 캐시)가 얼마인가? 의미 있게 크면(예: ≥30MB) 별도 프로세스로 분리해 OS 회수가 정합. 작으면(<10MB) 같은 프로세스 lazy load + GC로 충분 — 그러면 MAF 분리는 보류.
4. **MAF 수명 관리 정책**: MAF 프로세스를 *언제 깨우고 언제 죽일지*. ① 누가 깨우나(IDS가 intent 감지 후 bindService?), ② 언제 죽이나(마지막 협상 직후? N분 idle 후?), ③ 새 요청이 종료 중간에 오면? ④ 콜드 스타트 비용은 QAS-002에 어떻게 영향?
5. **IDS↔MAF IPC 부하 측정** *(자격 B 분리의 숨은 비용)*: 협상 중 MAF가 IDS에게 context를 *얼마나 자주* 묻고 *얼마나 큰* 페이로드를 주고받는가? 호출 빈도·페이로드가 크면 IPC 직렬화 지연이 QAS-002 압박 → 분리 정당성 재검토 또는 캐싱 정책 추가.
6. **분리 자격 추가 후보 검증**: LLM·Accessibility·MAF 외에 *자격 A 또는 자격 B*가 있는 모듈이 더 있는가? (예: 외부 SDK·센서 통합 중 협조적 취소를 지원하지 않는 사례, 또는 IDS·MAF와 또 다른 생애주기를 갖는 모듈)
7. **동시 세션 수**: 본 프로젝트가 실제로 동시 N세션을 운영하는가, 보통 1~2세션인가? → 1~2개면 C로 충분. 많고 *세션 간* 격리가 추가로 필요하면 *세션별 분리*를 C 위에 얹는 추가 결정 필요(현재는 범위 밖).
8. **멈춤의 성격 분포**: 취소 불가 네이티브 멈춤의 발생 빈도가 *드물면* 자격 A 분리(LLM·Accessibility)의 비용 정당화 약화. C의 분리 비용을 정당화하려면 네이티브 멈춤이 *실제로 발생*한다는 운영 데이터(또는 합리적 가정)가 필요.

---

## 6. 다이어그램

[DP-fault-isolation-candidates.drawio](./DP-fault-isolation-candidates.drawio) — 두 가지 다이어그램이 한 페이지에 위·아래로 배치되어 있다 (draw.io로 열어 편집 가능):

- **상단 (이전 버전)**: A/B/C 3안 비교. 보존용 — *전면 분리* C를 포함한 초기 검토 형태.
- **하단 (본 버전)**: B(K=2) vs C(K=3) 비교. B는 LLM·Accessibility만 분리하고 IDS+MAF는 같은 프로세스, C는 거기에 MAF 추가 분리. 본 DP의 핵심 결정(MAF 분리 여부)이 시각적으로 드러남.

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

_본 문서는 2026-06-11 작성·2026-06-15 B/C 2-안 구조로 재정리·2026-06-16 B=K=2/C=K=3 의미 재정의 (MAF 분리 결정 질문 명확화)되었으며, [07-QAS.md](../07-QAS.md)·[05-NFR.md](../05-NFR.md)의 변경에 종속된다._
