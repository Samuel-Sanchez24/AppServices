"""Excepciones propias del integrador."""


class ErrorNormalizacion(Exception):
    """El valor no puede representarse con el contrato institucional.

    Se lanza cuando un dato de origen no admite conversión al tipo o a la
    representación exigida (texto no numérico, nulo, fecha no interpretable).
    """

    def __init__(self, campo, valor, motivo):
        self.campo = campo
        self.valor = valor
        self.motivo = motivo
        super().__init__("campo '%s' (valor %r): %s" % (campo, valor, motivo))


class ErrorLectura(Exception):
    """No fue posible leer un dataset completo (archivo o formato)."""
