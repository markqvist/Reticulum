class PKCS7:
    BLOCKSIZE = 16

    @staticmethod
    def pad(data, bs=BLOCKSIZE):
        l = len(data)
        n = bs-l%bs
        v = bytes([n])
        return data+v*n

    @staticmethod
    def unpad(data, bs=BLOCKSIZE):
        l = len(data)
        n = data[-1]
        if n > bs:
            raise ValueError("Cannot unpad, invalid padding length of "+str(n)+" bytes")
        else:
            return data[:l-n]