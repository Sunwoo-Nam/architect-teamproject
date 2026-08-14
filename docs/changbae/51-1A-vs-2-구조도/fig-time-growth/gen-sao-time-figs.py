# -*- coding: utf-8 -*-
"""Standard SAO round-robin time growth — line and bar versions (S = 1,296)."""
import os
import subprocess

TP, ALPHA, S = 0.075, 0.4, 6 ** 4
NS = [3, 5, 10, 20, 50]


def tmin(N):
    return ALPHA * S ** (1 - 1 / N) * N * TP / 60.0


def fmt(m):
    return "%.0f s" % (m * 60) if m < 1 else "%.1f min" % m


PRE = r"""\documentclass[border=2pt]{standalone}
\usepackage[T1]{fontenc}
\usepackage[scaled=1.0]{helvet}
\renewcommand{\familydefault}{\sfdefault}
\usepackage{amsmath}
\usepackage{sansmath}
\usepackage{anyfontsize}
\usepackage{xcolor}
\usepackage{tikz}
\usepackage{pgfplots}
\pgfplotsset{compat=1.18}
\definecolor{ink}{HTML}{1A1A1A}
\definecolor{acc}{HTML}{2F5D8C}
\definecolor{gry}{HTML}{8A8A8A}
\pgfplotsset{
  natstyle/.style={
    width=52mm, height=52mm, scale only axis,
    axis lines=left,
    axis line style={line width=0.3pt, ink, -},
    tick align=outside, major tick length=1.6pt,
    xtick style={line width=0.3pt, ink}, ytick style={line width=0.3pt, ink},
    tick label style={font=\fontsize{7}{8.4}\selectfont},
    label style={font=\fontsize{7}{8.4}\selectfont},
    clip=false,
  }}
\begin{document}
\sansmath\fontsize{7}{8.4}\selectfont
\begin{tikzpicture}[font=\fontsize{7}{8.4}\selectfont,text=ink]
"""
POST = "\\end{tikzpicture}\n\\end{document}\n"

HEAD = (r"\node[anchor=south west,text=gry,font=\fontsize{6.6}{8}\selectfont]"
        r" at (rel axis cs:0,1.10) {Standard SAO round-robin \textbullet\ "
        r"4 issues $\times$ 6 values ($S$ = 1,296)};")

HEAD_BELOW = (r"\node[anchor=north west,text=gry,font=\fontsize{6.6}{8}\selectfont]"
              r" at (rel axis cs:0,0) [yshift=-10mm] {Round-robin SAO \textbullet\ "
              r"4 issues $\times$ 6 values ($S$ = 1,296)};")

# ---------------------------------------------------------------- line
curve = " ".join("(%d,%.4f)" % (n, tmin(n)) for n in range(3, 51))
pts = " ".join("(%d,%.4f)" % (n, tmin(n)) for n in NS)
lab = []
# N = 10, 20, 50 — direct labels above-left of the marker (curve is below)
for n in (10, 20, 50):
    lab.append(r"\node[anchor=south east,font=\fontsize{6.5}{7.8}\selectfont,inner sep=0pt,"
               "xshift=-2pt,yshift=2.5pt] at (axis cs:%d,%.4f) {%s};" % (n, tmin(n), fmt(tmin(n))))
# N = 3, 5 — points are too close to the origin: label with a thin leader
for n, lx, ly in ((3, 4.5, 20.5), (5, 4.5, 16.0)):
    lab.append(r"\node[anchor=west,font=\fontsize{6.5}{7.8}\selectfont,inner sep=1.5pt]"
               " (L%d) at (axis cs:%.1f,%.1f) {%s ($N$ = %d)};" % (n, lx, ly, fmt(tmin(n)), n))
    lab.append(r"\draw[gry,line width=0.16pt] (L%d.south west) -- (axis cs:%d,%.4f);"
               % (n, n, tmin(n)))

LINE = r"""
\begin{axis}[natstyle, xmin=3, xmax=50, ymin=0, ymax=32,
  xtick={3,10,20,30,40,50}, ytick={0,10,20,30},
  xlabel={Number of participants, $N$}, ylabel={Time per negotiation (min)}]
%s
\addplot[draw=none,fill=acc,fill opacity=0.06] coordinates {%s} \closedcycle;
\addplot[acc,line width=0.6pt] coordinates {%s};
\addplot[only marks,mark=*,mark size=1.0pt,
  mark options={fill=white,draw=acc,line width=0.4pt}] coordinates {%s};
%s
\end{axis}
""" % (HEAD, curve, curve, pts, "\n".join(lab))

# ---------------------------------------------------------------- bar
bars = " ".join("(%d,%.4f)" % (n, tmin(n)) for n in NS)
labb = "\n".join(
    r"\node[anchor=south,font=\fontsize{6.5}{7.8}\selectfont,inner sep=2pt]"
    " at (axis cs:%d,%.4f) {%s};" % (n, tmin(n), fmt(tmin(n))) for n in NS)

BAR = r"""
\begin{axis}[natstyle, width=56mm, ybar, bar width=6mm,
  symbolic x coords={3,5,10,20,50}, xtick=data,
  ymin=0, ymax=32, ytick={0,10,20,30}, enlarge x limits=0.14,
  xlabel={Number of participants, $N$}, ylabel={Time per negotiation (min)}]
%s
\addplot[draw=acc, fill=acc, fill opacity=0.85, line width=0.3pt] coordinates {%s};
%s
\end{axis}
""" % (HEAD_BELOW, bars, labb)

OUT = "a1figs"
os.makedirs(OUT, exist_ok=True)
env = dict(os.environ)
env["PATH"] = os.path.expanduser("~/Library/TinyTeX/bin/universal-darwin") + ":" + env["PATH"]

for stem, body in [("fig-sao-time-line", LINE), ("fig-sao-time-bar", BAR)]:
    with open(os.path.join(OUT, stem + ".tex"), "w", encoding="utf-8") as fh:
        fh.write(PRE + body + POST)
    r = subprocess.run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error", stem + ".tex"],
                       cwd=OUT, env=env, capture_output=True, text=True)
    print(stem, "OK" if r.returncode == 0 else "FAIL")
    if r.returncode:
        print("\n".join(r.stdout.splitlines()[-15:]))

print({n: fmt(tmin(n)) for n in NS})
