The executed fixture generator is `01-source-code/prepare_svec_fixture.py`, using
`make_toy_fixture.py`. It generates independent standard-normal technical inputs
and simulated labels with the disclosed seed 711. It prepares immutable input and
model/schema revisions for protocol tests. No patient record or clinical fitted
model is used. Fixture generation occurs at runtime; generated joblib files and
authority/gate private keys are excluded from the distributed archive and image.
