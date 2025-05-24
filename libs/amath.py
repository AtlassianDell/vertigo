import math

immutables["pi"] = 3.14159
immutables["e"] = 2.71828
immutables["y"] = 0.57721
immutables["gr"] = 1.618
immutables["c"] = 29979
immutables["g"] = 6.6743
immutables["h"] = 1.0545

def handle_amath(parts):
    global instruction_pointer, stacks, curstack, registers
    if len(parts) >= 3:
        op = parts[1].upper()
        dest = parts[2]
        args = [get_value(arg) for arg in parts[3:]]

        result = None

        try:
            if op == "SIN" and len(args) == 1:
                result = math.sin(args[0])
            elif op == "COS" and len(args) == 1:
                result = math.cos(args[0])
            elif op == "TAN" and len(args) == 1:
                result = math.tan(args[0])
            elif op == "ASIN" and len(args) == 1:
                result = math.asin(args[0])
            elif op == "ACOS" and len(args) == 1:
                result = math.acos(args[0])
            elif op == "ATAN" and len(args) == 1:
                result = math.atan(args[0])
            elif op == "ATAN2" and len(args) == 2:
                result = math.atan2(args[0], args[1])
            elif op == "LOG" and len(args) == 1:
                if args[0] > 0:
                    result = math.log(args[0])
                else:
                    raise ValueError("Logarithm of non-positive number")
            elif op == "LOG10" and len(args) == 1:
                if args[0] > 0:
                    result = math.log10(args[0])
                else:
                    raise ValueError("Logarithm of non-positive number")
            elif op == "EXP" and len(args) == 1:
                result = math.exp(args[0])
            elif op == "SQRT" and len(args) == 1:
                if args[0] >= 0:
                    result = math.sqrt(args[0])
                else:
                    raise ValueError("Square root of negative number")
            elif op == "ABS" and len(args) == 1:
                result = abs(args[0])
            elif op == "FLOOR" and len(args) == 1:
                result = math.floor(args[0])
            elif op == "CEIL" and len(args) == 1:
                result = math.ceil(args[0])
            elif op == "ROUND" and len(args) in [1, 2]:
                if len(args) == 1:
                    result = round(args[0])
                else:
                    result = round(args[0], int(args[1]))
            elif op == "FACTORIAL" and len(args) == 1:
                if isinstance(args[0], int) and args[0] >= 0:
                    result = math.factorial(args[0])
                else:
                    raise ValueError("Factorial requires a non-negative integer")
            elif op == "GCD" and len(args) == 2:
                result = math.gcd(int(args[0]), int(args[1]))
            elif op == "LCM" and len(args) == 2:
                result = (int(args[0]) * int(args[1])) // math.gcd(int(args[0]), int(args[1]))
            # Complex number operations (assuming complex numbers are handled as a type)
            elif op == "COMPLEX" and len(args) == 2:
                result = complex(args[0], args[1])
            elif op == "REALPART" and len(args) == 1 and isinstance(args[0], complex):
                result = args[0].real
            elif op == "IMAGPART" and len(args) == 1 and isinstance(args[0], complex):
                result = args[0].imag
            elif op == "CONJUGATE" and len(args) == 1 and isinstance(args[0], complex):
                result = args[0].conjugate()
            elif op == "MAGNITUDE" and len(args) == 1 and isinstance(args[0], complex):
                result = abs(args[0])
            elif op == "PHASE" and len(args) == 1 and isinstance(args[0], complex):
                result = math.atan2(args[0].imag, args[0].real)
            else:
                raise ValueError(f"Unknown or incorrect arguments for math operation '{op}'")

            if result is not None:
                if dest == "&":
                    if curstack:
                        stacks[curstack].append(result)
                    else:
                        raise ValueError("No stack selected for '&' destination")
                elif dest in registers:
                    registers[dest] = result
                elif dest.startswith("$"):
                    raise TypeError(f"Cannot assign to immutable '{dest}'")
                else:
                    raise ValueError(f"Invalid destination '{dest}'")

        except ValueError as e:
            raise ValueError(f"Math error in operation '{op}': {e}")
        except TypeError as e:
            raise TypeError(f"Type error in operation '{op}': {e}")

    else:
        raise SyntaxError("Invalid advanced MATH syntax")

instruction_handlers["AMATH"] = handle_amath
