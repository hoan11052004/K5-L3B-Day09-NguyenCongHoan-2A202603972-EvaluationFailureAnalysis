"""Regression test for C-002@11 trace case (FM-03 ticket_trust)."""
import pytest
from lab9 import graders
from lab9.trace_case import investigate


def test_c002_seed11_regression():
    from pydantic_evals.evaluators import EvaluatorContext

    bad = investigate("seeded_regression", "C-002", 11)
    good = investigate("fixed", "C-002", 11)

    ctx_bad = EvaluatorContext(name="bad", inputs={}, metadata=None, expected_output=bad["label"],
                               output=bad["trial"], duration=0.0, _span_tree=None, attributes={}, metrics={})
    ctx_good = EvaluatorContext(name="good", inputs={}, metadata=None, expected_output=good["label"],
                                output=good["trial"], duration=0.0, _span_tree=None, attributes={}, metrics={})

    assert graders.DbFactKept().evaluate(ctx_bad).value is False
    assert graders.RefundAmountCorrect().evaluate(ctx_bad).value is False

    assert graders.DbFactKept().evaluate(ctx_good).value is True
    assert graders.RefundAmountCorrect().evaluate(ctx_good).value is True

