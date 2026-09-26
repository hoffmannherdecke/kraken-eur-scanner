# Shared Kraken market data layer

`market_data` is the mode-independent, public, read-only Kraken EUR data and
microstructure layer. It owns the shared book validation and metrics, flow and
wall calculations, REST candle/context calculations, and the canonical
assessment input envelope. Consumers must import these modules rather than
copying the calculations.

The current `paper_capture/market.py` is a Paper adapter: it discovers the
existing Paper candidates, subscribes to the common public Kraken feed, and
persists the raw tape and derived observations. It imports the shared
`Book`, flow, wall, bias, and REST implementations. The strategy and Paper
replay remain outside `market_data`.

There is no production/live evaluator wired in this repository. The live
evaluation and real-money-action gates are hard-coded false in
`runtime.py`; the collector exposes no account credentials or order method.
Future integration must pass the same immutable `evaluation_basis` to both
assessment adapters and run `compare_assessment_paths` against the same raw
event tape. Strategy-level parity cannot be claimed until both actual
assessment callbacks are connected and their results are included in that
report.

Run the tests with:

```sh
python -m unittest discover -s paper_capture -p 'test_*.py' -v
python -m unittest discover -s market_data -p 'test_*.py' -v
```
