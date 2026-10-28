"""Finite user-facing failures; raw paths, response bodies and traces stay local."""


class UserError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code
