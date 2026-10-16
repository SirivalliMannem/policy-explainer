"""Test settings shared by every backend test."""

import os

# Flagged answers are analysed by the language model in the background in normal use; tests never
# call the model on their own (tests that need an analysis store one or call it explicitly).
os.environ.setdefault("ATTENTION_ANALYSIS_ON_FLAG", "off")
