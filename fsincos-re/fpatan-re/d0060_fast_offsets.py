"""Checked Python interface to the analysis-only exact residue enumerator."""
import ctypes


class FastOffsets:
    def __init__(self, library):
        self.library = ctypes.CDLL(str(library))
        self.call = self.library.d0060_offsets
        word = ctypes.c_uint64
        self.call.argtypes = [word, ctypes.POINTER(word), ctypes.POINTER(word), word]
        self.call.restype = word
        self.words = (word * 10)()
        self.capacity = 256
        self.output = (word * self.capacity)()

    def offsets(self, n, modulus, slope, intercept, lower, upper):
        assert 0 <= n <= 1 << 20 and 0 < modulus < 1 << 108
        assert modulus * (n + 1) < 1 << 128
        assert lower >= 0 and upper >= 0
        values = modulus, slope % modulus, intercept % modulus, min(lower, modulus), min(upper, modulus)
        for i, value in enumerate(values):
            self.words[2 * i], self.words[2 * i + 1] = value >> 64, value & ((1 << 64) - 1)
        count = self.call(n, self.words, self.output, self.capacity)
        assert count <= n
        if count > self.capacity:
            self.capacity = count
            self.output = (ctypes.c_uint64 * count)()
            assert self.call(n, self.words, self.output, count) == count
        return list(self.output[:count])

    def long_indices(self, params, start, length):
        p = params
        slope = 2 * p['alpha'] * start + p['beta']
        intercept = p['alpha'] * start * start + p['beta'] * start + p['gamma']
        upper = p['error_high'] + p['alpha'] * (length - 1) ** 2
        return [start + offset for offset in self.offsets(length, p['modulus'], slope, intercept,
                                                        p['error_low'], upper)]
