class RSAKeyPython:
    def __init__(self, public_exponent_hex: str, modulus_hex: str):
        """
        根据十六进制的公钥指数和模数初始化 RSA 密钥对象。
        """
        self.e = int(public_exponent_hex, 16)
        self.m = int(modulus_hex, 16)
        if self.m == 0:
            raise ValueError("Modulus cannot be zero.")
        bi_high_index_m: int
        if self.m == 0:   
            bi_high_index_m = 0
        else:
            num_16bit_words_m = (self.m.bit_length() + 15) // 16
            bi_high_index_m = num_16bit_words_m - 1
            
            if bi_high_index_m < 0:
                 bi_high_index_m = 0
        
        self.chunkSize = 2 * bi_high_index_m 
        self.radix = 16 

        if self.chunkSize <= 0 and self.m > 0xFFFF:    
             print(f"Warning: chunkSize is {self.chunkSize} for a modulus > 0xFFFF. Check logic.")
        elif self.chunkSize <= 0 and self.m <= 0xFFFF and self.m != 0 : 
             pass

def encrypted_string_python(key: RSAKeyPython, s: str) -> str:
    """
    使用给定的 RSA 密钥加密字符串 s。
    与 JavaScript RSAUtils.encryptedString(key, s) 行为一致。
    注意：输入字符串 s 中的每个字符其 ord() 值必须在 0-255 范围内，
    因为JS代码 `a[i] = s.charCodeAt(i)` 后，这些值被用于构建16位数字单元
    `a[k] | (a[k+1] << 8)`，这隐含了a[k]和a[k+1]是字节。
    """
    char_codes = []
    for char_in_s in s:
        code = ord(char_in_s)
        if not (0 <= code <= 255):
            raise ValueError(
                f"Character '{char_in_s}' with ord() value {code} is outside the "
                "byte range (0-255). The RSA encryption logic in the provided "
                "JavaScript expects character codes that fit into byte-sized "
                "components for block construction."
            )
        char_codes.append(code)

    if key.chunkSize == 0:
        if not char_codes: 
            return ""      
        
        raise ValueError(
            "key.chunkSize is 0. This typically means the RSA modulus is too small "
            "(<= 16 bits or 0xFFFF), making encryption impossible with this scheme."
        )
    
    current_len = len(char_codes)
    padding_count = 0
    if current_len % key.chunkSize != 0:
        padding_count = key.chunkSize - (current_len % key.chunkSize)
    
    char_codes.extend([0] * padding_count)
    al = len(char_codes)
    result_parts = []
    for i in range(0, al, key.chunkSize):
        current_block_bytes_source = char_codes[i : i + key.chunkSize]
        block_int = int.from_bytes(bytes(current_block_bytes_source), byteorder='little')
        encrypted_int = pow(block_int, key.e, key.m)
        hex_text: str
        if encrypted_int == 0:
            num_16bit_digits_crypt = 1 
        else:
            num_16bit_digits_crypt = (encrypted_int.bit_length() + 15) // 16
        
        expected_hex_len = num_16bit_digits_crypt * 4 
        hex_text = format(encrypted_int, f'0{expected_hex_len}x') 
        result_parts.append(hex_text)
    
    if not result_parts: 
        return ""
    
    final_result = " ".join(result_parts)
    return final_result