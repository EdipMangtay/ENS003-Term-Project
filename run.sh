#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
  ./.venv/bin/pip install -q --upgrade pip
  ./.venv/bin/pip install -q -r requirements.txt
fi

source .venv/bin/activate

case "${1:-}" in
  convert) python src/convert.py ;;
  train)   python src/train.py ;;
  predict) shift; python src/predict.py "$@" ;;
  app)     python src/app.py ;;
  check)   python src/preprocess.py ;;
  *)       echo "Kullanım: ./run.sh {check|convert|train|predict|app}"
           echo "  check    - dataset'i göster"
           echo "  convert  - Ti64_Hip_Implant_Dataset.csv -> data/dataset.csv"
           echo "  train    - tüm hedefler için model eğit (5-fold grouped CV)"
           echo "  predict  - CLI tahmin (--mass 70 --k 2.5 --angle 0)"
           echo "             ya da preset:  --mass 70 --activity walking"
           echo "  app      - Flask web app (http://localhost:5050)"
           ;;
esac
