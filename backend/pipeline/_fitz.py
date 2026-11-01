"""PyMuPDF, imported when it is first used.

Reading a PDF needs PyMuPDF (AGPL-3.0 or a commercial licence); serving what is already analysed does
not. The hosted demo ships without it (and without the analysis pipeline that uses it), so the
modules that read PDFs take it from here and the app starts, and serves everything else, without it.
"""


class _Lazy:
    def __getattr__(self, name):
        import fitz as _fitz        # noqa: PLC0415 (deliberately late)
        return getattr(_fitz, name)


fitz = _Lazy()
