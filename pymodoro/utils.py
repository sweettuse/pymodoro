class classproperty:
    def __init__(self, f):
        self.f = f

    def __get__(self, _, cls):
        return self.f(cls)
