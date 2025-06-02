import math

class RSAKeyPython:
    def __init__(self, public_exponent_hex: str, modulus_hex: str):
        """
        根据十六进制的公钥指数和模数初始化 RSA 密钥对象。
        """
        self.e = int(public_exponent_hex, 16)
        self.m = int(modulus_hex, 16)

        if self.m == 0:
            raise ValueError("Modulus cannot be zero.")

        # chunkSize 计算基于 biHighIndex。
        # biHighIndex(m) 返回 m.digits 中最高非零项的索引。
        # JS库中 BigInt 的 digits 是16位的。
        # ref: RSAUtils.biHighIndex, bitsPerDigit = 16 in security.js
        
        bi_high_index_m: int
        if self.m == 0: 
            # JS: biHighIndex for a BigInt representing 0 (e.g. digits=[0]) is 0.
            bi_high_index_m = 0
        else:
            # 模数m需要多少个16位单元来表示
            # (self.m.bit_length() + 15) // 16 计算实际需要的16位字数
            num_16bit_words_m = (self.m.bit_length() + 15) // 16
            bi_high_index_m = num_16bit_words_m - 1
            # 确保 bi_high_index_m 不为负，例如 m=1 (1 bit), num_words=1, index=0.
            if bi_high_index_m < 0:
                 bi_high_index_m = 0


        # ref: this.chunkSize = 2 * $dmath.biHighIndex(this.m); in RSAKeyPair
        self.chunkSize = 2 * bi_high_index_m 
        
        # ref: this.radix = 16; in RSAKeyPair
        self.radix = 16 

        # 如果 chunkSize 为0（例如模数 <= 0xFFFF），则加密无法进行。
        # JS 代码中的 encryptedString 的填充循环 `while (a.length % key.chunkSize != 0)`
        # 在 chunkSize 为 0 时，若 a.length 非0则会无限循环。
        # Python 中使用 % 0 会直接报错。
        if self.chunkSize <= 0 and self.m > 0xFFFF: # 模数大于0xFFFF时chunkSize不应为0
             # 这是一个不太可能发生的情况，除非bit_length计算或逻辑有误
             print(f"Warning: chunkSize is {self.chunkSize} for a modulus > 0xFFFF. Check logic.")
        elif self.chunkSize <= 0 and self.m <= 0xFFFF and self.m != 0 : # m=0 时 index=0, chunkSize=0
             # 对于 m <= 0xFFFF, biHighIndex(m) = 0, chunkSize = 0. 这是预期的。
             # print(f"Note: chunkSize is {self.chunkSize} due to small modulus (<=0xFFFF). Encryption may not proceed if data exists.")
             pass


def encrypted_string_python(key: RSAKeyPython, s: str) -> str:
    """
    使用给定的 RSA 密钥加密字符串 s。
    与 JavaScript RSAUtils.encryptedString(key, s) 行为一致。

    注意：输入字符串 s 中的每个字符其 ord() 值必须在 0-255 范围内，
    因为JS代码 `a[i] = s.charCodeAt(i)` 后，这些值被用于构建16位数字单元
    `a[k] | (a[k+1] << 8)`，这隐含了a[k]和a[k+1]是字节。
    """

    # 1. 将字符串 s 转换为其字符的 Unicode 码点列表
    #    ref: while (i < sl) { a[i] = s.charCodeAt(i); i++; }
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
    
    # JS `a` 数组现在是 char_codes
    # ref: var a = []; ... while (i < sl) { a[i] = s.charCodeAt(i); i++; }

    # 2. 尾部填充0，使列表长度是 key.chunkSize 的倍数
    #    ref: while (a.length % key.chunkSize != 0) { a[i++] = 0; }
    if key.chunkSize == 0:
        if not char_codes: # 如果输入字符串为空且 chunkSize 为 0
            return ""      # JS 原始代码中，若 a.length=0, 循环不执行，后续result=""
        # 如果输入字符串非空但 chunkSize 为 0，JS会无限循环 (如果a.length != 0)
        raise ValueError(
            "key.chunkSize is 0. This typically means the RSA modulus is too small "
            "(<= 16 bits or 0xFFFF), making encryption impossible with this scheme."
        )

    # `i` 在JS中会继续递增用于填充，Python中可以直接计算和追加
    current_len = len(char_codes)
    padding_count = 0
    if current_len % key.chunkSize != 0:
        padding_count = key.chunkSize - (current_len % key.chunkSize)
    
    char_codes.extend([0] * padding_count)
    
    # `al` is the new length
    # ref: var al = a.length;
    al = len(char_codes)
    result_parts = []

    # ref: for (i = 0; i < al; i += key.chunkSize) { ... }
    for i in range(0, al, key.chunkSize):
        # `block = new BigInt();` (Python int will represent this)
        # The bytes for the current block
        current_block_bytes_source = char_codes[i : i + key.chunkSize]
        
        # Pack bytes into an integer.
        # JS: for (k = i; k < i + key.chunkSize; ++j) {
        #         block.digits[j] = a[k++];
        #         block.digits[j] += a[k++] << 8;
        #     }
        # This means pairs of bytes (val1, val2) from current_block_bytes_source
        # form 16-bit digits: val1 | (val2 << 8).
        # These 16-bit digits are arranged in little-endian order in block.digits.
        # So, the entire byte sequence current_block_bytes_source (which has length key.chunkSize)
        # forms the integer `block_int` in little-endian byte order.
        block_int = int.from_bytes(bytes(current_block_bytes_source), byteorder='little')

        # Perform modular exponentiation: block_int ^ e mod m
        # JS: var crypt = key.barrett.powMod(block, key.e);
        # Python's pow(base, exp, mod) is equivalent.
        encrypted_int = pow(block_int, key.e, key.m)

        # Convert encrypted integer to hex string.
        # JS: var text = key.radix == 16 ? RSAUtils.biToHex(crypt) : RSAUtils.biToString(crypt, key.radix);
        # Since key.radix is 16, RSAUtils.biToHex(crypt) is used.
        # RSAUtils.biToHex(crypt) converts crypt into a lowercase hex string.
        # Each 16-bit digit of crypt becomes 4 hex characters (e.g., 0 -> "0000", 0xABC -> "0abc").
        # ref: RSAUtils.biToHex and RSAUtils.digitToHex logic in security.js

        hex_text: str
        if encrypted_int == 0:
            # biHighIndex(0) is 0, meaning one digit {0}. digitToHex(0) is "0000".
            num_16bit_digits_crypt = 1 
        else:
            num_16bit_digits_crypt = (encrypted_int.bit_length() + 15) // 16
        
        expected_hex_len = num_16bit_digits_crypt * 4 # Each 16-bit digit is 4 hex chars
        hex_text = format(encrypted_int, f'0{expected_hex_len}x') # 'x' gives lowercase

        result_parts.append(hex_text)

    # Join hex parts with space and remove trailing space (if any)
    # JS: result += text + " "; ... return result.substring(0, result.length - 1);
    if not result_parts: # Should not happen if al > 0. If al=0 (empty s, chunkSize > 0), loop doesn't run.
        return ""
    
    final_result = " ".join(result_parts)
    return final_result

if __name__ == "__main__":
    # --- 示例使用 ---
    # public_exponent_hex 一般是 "010001" (65537)
    public_exponent_hex = "10001"

    # modulus_hex 是您的RSA模数，一个很长的十六进制字符串
    # 例如 (仅为示意，您需要替换为真实的、完整的模数):
    # modulus_hex = "YOUR_RSA_MODULUS_HEX_STRING_HERE" 
    # 一个用于测试的小模数 (大于0xFFFF以使chunkSize > 0)
    # 0x10001 (decimal 65537) -> biHighIndex=1, chunkSize=2
    # 0x12345678 (decimal 305419896) -> biHighIndex=1, chunkSize=2 (因为只占两个16-bit word: 0x4996, 0x02D2. No, 0x12345678 = 0x1234 << 16 | 0x5678. So digits are [0x5678, 0x1234]. biHighIndex=1, chunkSize=2)
    # 一个实际的1024位模数大概有 1024/4 = 256 个十六进制字符
    # 例如，一个128字节的模数 (1024位)
    # (1024 bits + 15) // 16 = 64 words. biHighIndex = 63. chunkSize = 2 * 63 = 126.

    # 请替换为您的实际模数进行测试
    # modulus_hex_example = "a3a9075565be6c3ebe19229607695e63..." # (替换为完整模数)

    # 为了让代码可运行，我们用一个能产生正 chunkSize 的示例模数
    # modulus_hex = "12345678" # m = 0x12345678. bit_length = 29. num_16bit_words = (29+15)//16 = 2. biHighIndex = 1. chunkSize = 2.
    modulus_hex_for_testing = "dc872dd3b9591a3c6002c770c7c2379b60eab897689da1b5bd5d6e7f4f9a857f3bf0db01b113806db0c36bef788257318f963447222012b47e0d063cf2d2a455" # 129-bit modulus, highIndex = 8, chunkSize=16

    original_password = "hhy060125crq" # 假设这是JS中的 s
    original_password = original_password[::-1]
    # JS 调用示例中通常会对密码先做反转：
    # var reversedPwd = password.split("").reverse().join("");
    # var encrypedPwd = RSAUtils.encryptedString(key, reversedPwd);
    # 所以我们应该把反转后的字符串传给 python 函数，或者在函数内部反转，
    # 这里假设传入的 s 就是 JS RSAUtils.encryptedString 所接收的 s。

    # 1. 创建密钥对象
    try:
        print(f"使用测试模数: {modulus_hex_for_testing}")
        key_obj = RSAKeyPython(public_exponent_hex, modulus_hex_for_testing)
        print(f"RSAKey Initialized:")
        print(f"  e (int): {key_obj.e}")
        print(f"  m (int): Truncated for display if too long... {str(key_obj.m)[:30]}...")
        print(f"  chunkSize: {key_obj.chunkSize}")
        print(f"  radix: {key_obj.radix}")

        if key_obj.chunkSize > 0 :
        # 2. 加密
        # 注意：如果原始JS代码在调用 encryptedString 前对密码字符串 s 做了预处理（如反转），
        # 那么传递给此Python函数的字符串 s 也应该是预处理后的。
        # 例如，如果JS是 encryptedString(key, password.reverse()), 那么 s = password.reverse()
        
            print(f"\nEncrypting string: '{original_password}'")
            encrypted_data = encrypted_string_python(key_obj, original_password)
            print(f"Encrypted data: {encrypted_data}")

        else:
            print(f"\nChunkSize is {key_obj.chunkSize}, encryption cannot proceed with this input configuration.")
            print("This usually means the modulus is too small (<= 0xFFFF or 16 bits).")


    except ValueError as e:
        print(f"\nAn error occurred: {e}")
    except Exception as e:
        print(f"\nAn unexpected error: {e}")
