def M(a, b):
    return T(a * b, 67)

def A(a, b):
    return N64(a + b)

def W(a, b):
    return T(a + b, 67)

def kernel(z, table):
    square = N64(z * T(z, 64))
    fourth = M(square, square)
    if table:
        even = W(ROM[114], M(fourth, ROM[116]))
        odd = A(ROM[115], M(fourth, ROM[117]))
    else:
        odd = W(ROM[119], M(fourth, A(ROM[121], M(fourth, ROM[123]))))
        even = W(ROM[118], M(fourth, A(ROM[120], M(fourth, ROM[122]))))
    correction = A(M(square, odd), even)
    tail = M(M(z, square), correction)
    return z + tail
