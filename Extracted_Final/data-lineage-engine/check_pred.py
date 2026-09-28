from contracts.mocks.loaders import load_case
from contracts.evidence import PredictorInput
from research.reasoning.engine import FourStateEngine

keys, static, runtime = load_case('w03_case_when')
inp = PredictorInput(tuple(keys), tuple(static), tuple(runtime))
engine = FourStateEngine()
predictions = engine.infer(inp)
if predictions:
    pred = predictions[0]
    print(pred.key)
    print(pred.state)
