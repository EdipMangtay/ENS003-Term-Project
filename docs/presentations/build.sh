#!/usr/bin/env bash
# Build the three ENS003 software-team presentations.
# Requires pdflatex with the metropolis theme (TeX Live 2017+ or MacTeX).

set -e
cd "$(dirname "$0")"

DECKS=(
  ata-bulut
  recep-kamil-firat
  ali-edip-mangtay
  ata-bulut-en
  recep-kamil-firat-en
  ali-edip-mangtay-en
)

mkdir -p .build

for deck in "${DECKS[@]}"; do
  echo "==> Building ${deck}.pdf"
  # Two passes so frame numbering "x / N" resolves on the first slide.
  # pdflatex may exit non-zero on harmless warnings; treat the presence
  # of a fresh PDF as the success signal instead of relying on $?.
  for pass in 1 2; do
    pdflatex -interaction=nonstopmode -output-directory=.build "${deck}.tex" \
      > ".build/${deck}.log" 2>&1 || true
  done
  if [ ! -f ".build/${deck}.pdf" ]; then
    echo "    Build failed -- see .build/${deck}.log"
    grep -E "^!|^l\.[0-9]" ".build/${deck}.log" | head -10
    exit 1
  fi
  cp ".build/${deck}.pdf" "./${deck}.pdf"
done

echo ""
echo "Wrote:"
for deck in "${DECKS[@]}"; do
  if [ -f "${deck}.pdf" ]; then
    size=$(du -h "${deck}.pdf" | cut -f1)
    echo "  ${deck}.pdf  (${size})"
  fi
done
