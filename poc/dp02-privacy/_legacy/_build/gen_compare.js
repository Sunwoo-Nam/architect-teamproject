// DP03 게이트웨이 구조 비교 — A안 모놀리식 vs B안 연합형 (단일 슬라이드)
// 공통 모듈은 좌/우 동일 좌표(회색), 차이(정규화 위치)만 가운데 칸 주황 강조.
const pptxgen = require("pptxgenjs");

const pres = new pptxgen();
pres.defineLayout({ name: "WIDE", width: 13.33, height: 7.5 });
pres.layout = "WIDE";
pres.author = "architect-teamproject";
pres.title = "DP03 게이트웨이 구조 비교";

const slide = pres.addSlide();
slide.background = { color: "FFFFFF" };

const FONT = "Calibri";

// ---- palette ----
const COMMON = { fill: "ECEEF1", line: "AEB6BF", text: "2C313A" };   // 공통 모듈 = 회색
const DIFF   = { fill: "FFE0B2", line: "E08A1E", text: "5A3D0A" };   // 차이(정규화) = 주황 강조
const EXT    = { fill: "EADDF3", line: "9B6FB0", text: "3B2E47" };   // 외부 = 보라
const WHITEB = { fill: "FFFFFF", line: "9AA3AD", text: "2C313A" };
const PANEL  = "FFF6E9";   // 차이 영역 배경 패널 (연주황)
const BOUND  = "C0392B";   // 신뢰경계 점선
const E_GRAY = "8A929C";   // 공통 흐름
const E_RAW  = "C0392B";   // 원본 PII (A)
const E_SAFE = "2E7D32";   // 안전형 (B)

// ---- helpers ----
function box(x, y, w, h, text, sty, opt = {}) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x, y, w, h, rectRadius: 0.06,
    fill: { color: sty.fill }, line: { color: sty.line, width: 1.25 },
    shadow: { type: "outer", color: "000000", blur: 3, offset: 1, angle: 90, opacity: 0.10 },
  });
  slide.addText(text, {
    x, y, w, h, align: "center", valign: "middle", margin: 1,
    fontFace: FONT, fontSize: opt.fs || 10.5, bold: opt.bold !== false,
    color: sty.text, lineSpacingMultiple: 0.95,
  });
}

function line(x1, y1, x2, y2, color, opt = {}) {
  slide.addShape(pres.shapes.LINE, {
    x: Math.min(x1, x2), y: Math.min(y1, y2),
    w: Math.abs(x2 - x1), h: Math.abs(y2 - y1),
    flipH: x2 < x1, flipV: y2 < y1,
    line: {
      color, width: opt.w || 1.25,
      dashType: opt.dash ? "dash" : "solid",
      endArrowType: opt.end === false ? "none" : "triangle",
      beginArrowType: opt.both ? "triangle" : "none",
    },
  });
}

// ---- title ----
slide.addText("DP03 게이트웨이 구조 비교 — A안 모놀리식 vs B안 연합형", {
  x: 0.3, y: 0.10, w: 12.73, h: 0.42, align: "center", valign: "middle", margin: 0,
  fontFace: FONT, fontSize: 22, bold: true, color: "1F2937",
});
slide.addText("공통 모듈은 좌·우 같은 위치(회색)에 고정 · 차이는 가운데 ‘정규화 위치’(주황)에 집중", {
  x: 0.3, y: 0.52, w: 12.73, h: 0.26, align: "center", valign: "middle", margin: 0,
  fontFace: FONT, fontSize: 11.5, color: "6B7280",
});

// center divider
slide.addShape(pres.shapes.LINE, { x: 6.665, y: 0.92, w: 0, h: 6.0, line: { color: "D0D5DC", width: 1 } });

// ====== half renderer ======
function drawHalf(OX, V) {  // V: "A" or "B"
  const isA = V === "A";

  // half subtitle + color dot
  slide.addShape(pres.shapes.OVAL, { x: OX + 0.10, y: 0.92, w: 0.20, h: 0.20, fill: { color: DIFF.line }, line: { color: DIFF.line } });
  slide.addText(isA ? "A안 — Monolithic Gateway (단일 게이트웨이)" : "B안 — Federated Adapters (연합형 어댑터)", {
    x: OX + 0.38, y: 0.83, w: 5.6, h: 0.36, align: "left", valign: "middle", margin: 0,
    fontFace: FONT, fontSize: 14, bold: true, color: "1F2937",
  });

  // trust boundary (dashed) — encloses inputs + norm + core (excludes 사용자 & externals)
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x: OX + 0.0, y: 1.72, w: 4.40, h: 3.62, rectRadius: 0.05,
    fill: { type: "solid", color: "FFFFFF", transparency: 100 },
    line: { color: BOUND, width: 1.25, dashType: "dash" },
  });
  slide.addText("온디바이스 신뢰경계", {
    x: OX + 0.08, y: 1.74, w: 1.9, h: 0.15, align: "left", valign: "middle", margin: 0,
    fontFace: FONT, fontSize: 9, bold: true, color: BOUND,
  });

  // difference-zone highlight panel (behind norm column)
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x: OX + 1.26, y: 1.84, w: 1.36, h: 2.84, rectRadius: 0.05,
    fill: { color: PANEL }, line: { color: DIFF.line, width: 1, dashType: "dash" },
  });
  slide.addText("차이 지점: 정규화 위치", {
    x: OX + 1.26, y: 4.70, w: 1.36, h: 0.20, align: "center", valign: "middle", margin: 0,
    fontFace: FONT, fontSize: 8, bold: true, color: DIFF.text,
  });

  // ---- INPUTS (공통, 회색) ----
  box(OX + 0.05, 1.25, 1.05, 0.40, "사용자", WHITEB, { fs: 10 });
  box(OX + 0.05, 1.90, 1.05, 0.60, "IDS\n(Intent 감지)", COMMON, { fs: 9.5 });
  box(OX + 0.05, 2.95, 1.05, 0.60, "DPA\n(가전 상태)", COMMON, { fs: 9.5 });
  box(OX + 0.05, 4.00, 1.05, 0.60, "Sub-Agent\n(실행/조회)", COMMON, { fs: 9.5 });

  // ---- NORMALIZATION (차이, 주황) ----
  if (isA) {
    box(OX + 1.31, 1.90, 1.25, 2.70, "중앙 정규화기\n분류 · 권한 · 어휘\n\n[ 단일 게이트웨이 ]", DIFF, { fs: 10.5 });
  } else {
    box(OX + 1.31, 1.90, 1.25, 0.60, "어댑터 1\n(IDS 정규화)", DIFF, { fs: 9.5 });
    box(OX + 1.31, 2.95, 1.25, 0.60, "어댑터 2\n(DPA 정규화)", DIFF, { fs: 9.5 });
    box(OX + 1.31, 4.00, 1.25, 0.60, "어댑터 3\n(Sub 정규화)", DIFF, { fs: 9.5 });
  }

  // ---- CORE (공통, 회색) ----
  box(OX + 2.90, 1.90, 1.40, 0.60, "출력 빌더\n(Outcome/요청)", COMMON, { fs: 9.5 });
  box(OX + 2.90, 2.75, 1.40, 0.78, "Meta Agent (협상 두뇌)\nufun · 협상엔진", COMMON, { fs: 9.5 });
  box(OX + 2.90, 3.78, 1.40, 0.60, "Orchestrator\n(계획 작성)", COMMON, { fs: 9.5 });
  box(OX + 2.90, 4.62, 1.40, 0.60, isA ? "PII 금고 (Vault)" : "공유 Vault", COMMON, { fs: 9.5 });

  // ---- EXTERNAL (공통, 보라; 신뢰경계 밖) ----
  box(OX + 4.54, 2.75, 1.40, 0.62, "상대 PPA\n(외부)", EXT, { fs: 9.5 });
  box(OX + 4.54, 3.76, 1.40, 0.62, "Cloud LLM\n(외부)", EXT, { fs: 9.5 });
  box(OX + 1.55, 6.00, 1.60, 0.48, "외부 서비스 API (외부)", EXT, { fs: 9.5 });

  // ===== EDGES =====
  // 사용자 -> IDS
  line(OX + 0.575, 1.65, OX + 0.575, 1.90, E_GRAY, { w: 1.1 });

  // inputs -> normalization (차이 강조: A 빨강 원본 / B 초록 안전형)
  const ec = isA ? E_RAW : E_SAFE;
  line(OX + 1.10, 2.20, OX + 1.30, 2.20, ec, { w: 2.25 });
  line(OX + 1.10, 3.25, OX + 1.30, 3.25, ec, { w: 2.25 });
  line(OX + 1.10, 4.30, OX + 1.30, 4.30, ec, { w: 2.25 });

  // normalization -> 출력 빌더 (공통 회색)
  if (isA) {
    line(OX + 2.56, 3.05, OX + 2.90, 2.20, E_GRAY, { w: 1.4 });
  } else {
    line(OX + 2.56, 2.20, OX + 2.90, 2.20, E_GRAY, { w: 1.3 });
    line(OX + 2.56, 3.25, OX + 2.90, 2.30, E_GRAY, { w: 1.3 });
    line(OX + 2.56, 4.30, OX + 2.90, 2.40, E_GRAY, { w: 1.3 });
  }

  // 빌더 -> Meta -> Orchestrator
  line(OX + 3.60, 2.50, OX + 3.60, 2.75, E_GRAY, { w: 1.25 });
  line(OX + 3.60, 3.53, OX + 3.60, 3.78, E_GRAY, { w: 1.25 });

  // Meta <-> 상대 PPA (양방향), Orchestrator -> Cloud
  line(OX + 4.30, 3.10, OX + 4.54, 3.06, E_GRAY, { w: 1.25, both: true });
  line(OX + 4.30, 4.08, OX + 4.54, 4.07, E_GRAY, { w: 1.25, dash: true });

  // Vault -> Sub (재주입, 점선)
  line(OX + 2.90, 4.92, OX + 1.10, 4.45, E_GRAY, { w: 1.1, dash: true });

  // Sub -> 외부 API (실행, 점선)
  line(OX + 0.70, 4.60, OX + 1.80, 6.00, E_GRAY, { w: 1.1, dash: true });

  // ---- footer caption (강점/약점) ----
  const cap = isA
    ? [ { text: "강점  ", options: { bold: true, color: "2E7D32" } },
        { text: "단일 검증 지점 · 감사/교차일관성 용이", options: { color: "374151", breakLine: true } },
        { text: "약점  ", options: { bold: true, color: "B23B2E" } },
        { text: "원본 PII 체류 구간 존재 · God Object 위험", options: { color: "374151" } } ]
    : [ { text: "강점  ", options: { bold: true, color: "2E7D32" } },
        { text: "발생 즉시 안전형 변환 · 독립적 확장 용이", options: { color: "374151", breakLine: true } },
        { text: "약점  ", options: { bold: true, color: "B23B2E" } },
        { text: "통합 조율 복잡 · SDK 버전 파편화 리스크", options: { color: "374151" } } ];
  slide.addText(cap, {
    x: OX + 0.05, y: 6.62, w: 5.85, h: 0.62, align: "left", valign: "top", margin: 2,
    fontFace: FONT, fontSize: 11, lineSpacingMultiple: 1.05,
  });
}

drawHalf(0.30, "A");
drawHalf(6.98, "B");

// ---- legend (bottom) ----
const ly = 7.20;
function chip(x, color, dash, label) {
  slide.addShape(pres.shapes.LINE, { x, y: ly + 0.09, w: 0.30, h: 0, line: { color, width: 2.25, dashType: dash ? "dash" : "solid", endArrowType: "triangle" } });
  slide.addText(label, { x: x + 0.34, y: ly, w: 2.4, h: 0.22, align: "left", valign: "middle", margin: 0, fontFace: FONT, fontSize: 9, color: "374151" });
}
chip(0.45, E_GRAY, false, "공통 흐름");
chip(2.05, E_RAW, false, "원본 PII 이동 (A)");
chip(4.30, E_SAFE, false, "즉시 안전형 (B)");
chip(6.55, E_GRAY, true, "점선: PII 재주입/실행");
slide.addText("박스 색: 회색=공통 · 주황=차이(정규화) · 보라=신뢰경계 밖", {
  x: 8.35, y: ly, w: 4.40, h: 0.22, align: "right", valign: "middle", margin: 0, fontFace: FONT, fontSize: 8.5, color: "374151",
});

pres.writeFile({ fileName: "/sessions/loving-admiring-goldberg/mnt/outputs/DP03-전체구조-AB비교.pptx" })
  .then(() => console.log("done"));
