# ENS003 Software-Team Presentations

Beamer slide decks (Turkish + English) for the three software-side
contributors. Each deck is ~10 slides, ~5–8 minutes of speaking, focused
on the speaker's own module.

| File | Speaker | Module |
|---|---|---|
| `ata-bulut.tex` · `ata-bulut-en.tex` | Ata Bulut (CE) | Converter, feature engineering, CV grouping helper |
| `recep-kamil-firat.tex` · `recep-kamil-firat-en.tex` | Recep Kamil Fırat (CE) | GPR surrogate, model selection, 5-fold grouped CV |
| `ali-edip-mangtay.tex` · `ali-edip-mangtay-en.tex` | Ali Edip Mangtay (SE) | Flask dashboard, predict CLI, integration |

## Build

Requires `pdflatex` with the `metropolis` Beamer theme (MacTeX or TeX Live ≥ 2017):

```bash
./build.sh
```

Outputs 6 PDF files next to the `.tex` sources. Intermediate artefacts
live in `.build/`.

If `metropolis` is unavailable in your TeX installation, open
`_preamble.tex` and switch:

```latex
\usetheme{metropolis}      % -> \usetheme{Madrid}
```

## Notes for speakers

- The PDFs reference screenshots in `../../screenshots/`. Re-run
  `python scripts/capture_screenshots.py` after any dashboard change so
  the slides stay in sync with the live UI.
- Each deck closes with file references --- use them to pivot to a code
  walkthrough if the audience asks.
- Live demo paths: `./run.sh convert`, `./run.sh train`,
  `./run.sh predict --mass 70 --k 2.5 --angle 0`, `./run.sh app`.
