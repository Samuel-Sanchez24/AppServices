class ErrorNormalizacion(Exception):

    def __init__(self, campo, valor, motivo):
        self.campo = campo
        self.valor = valor
        self.motivo = motivo
        super().__init__("campo '%s' (valor %r): %s" % (campo, valor, motivo))


class ErrorLectura(Exception):
    pass
