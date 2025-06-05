import sys
import re
import time
import datetime
import os  # Import os module to handle file paths


class VertigoError(Exception):
    def __init__(self, message, line_num=None, instruction=None):
        super().__init__(message)
        self.line_num = line_num
        self.instruction = instruction

    def __str__(self):
        if self.line_num is not None:
            return f"Line {self.line_num}: {super().__str__()}"
        return super().__str__()


class VertigoSyntaxError(VertigoError):
    pass


class VertigoRuntimeError(VertigoError):
    pass


class VertigoNameError(VertigoError):
    pass


class VertigoTypeError(VertigoError):
    pass


class VertigoIndexError(VertigoError):
    pass


class VertigoZeroDivisionError(VertigoError):
    pass


class VertigoImportError(VertigoError):
    pass


class VertigoLexer:
    FIELDS_PATTERN = re.compile(r'\"(.*?)\"|(\S+)')

    @staticmethod
    def split(data):
        parts = []
        for match in VertigoLexer.FIELDS_PATTERN.finditer(data):
            if match.group(1) is not None:
                parts.append(f'"{match.group(1)}"')
            elif match.group(2) is not None:
                parts.append(match.group(2))
        return parts


class InterpreterState:
    def __init__(self):
        self.stacks = {"_loop_stack": []}
        self.current_stack_name = ""
        self.registers = {
            "ODA": None,
            "IDA": None,
            "CLI": 0,
            "LTM": 0
        }
        self.local_register_stack = []
        self.immutables = {}
        self.comparison_flags = {"equal": False, "greater": False, "less": False}
        self.labels = {}
        self.subroutines = {}
        self.return_stack = []
        self.loop_stack = []
        self.settings = {"intpr": False}
        self.dump_log = ""
        self.instruction_pointer = 0

    def get_value(self, operand):
        if operand.startswith('"') and operand.endswith('"'):
            return operand[1:-1]

        try:
            if operand.startswith('0x'):
                return int(operand, 16)
            elif operand.startswith('0o'):
                return int(operand, 8)
            elif operand.startswith('0b'):
                return int(operand, 2)
            else:
                return int(operand)
        except ValueError:
            try:
                return float(operand)
            except ValueError:
                pass

        if operand.startswith("$"):
            target_name = operand[1:]
            if target_name in self.stacks:
                return len(self.stacks[target_name])
            if self.local_register_stack and target_name in self.local_register_stack[-1]:
                if isinstance(self.local_register_stack[-1][target_name], str):
                    return len(self.local_register_stack[-1][target_name])
                elif isinstance(self.local_register_stack[-1][target_name], (int, float)):
                    return 1
            elif target_name in self.registers:
                if isinstance(self.registers[target_name], str):
                    return len(self.registers[target_name])
                elif isinstance(self.registers[target_name], (int, float)):
                    return 1
            else:
                raise VertigoValueError(f"Invalid identifier for length operator '{operand}'.",
                                        line_num=self.instruction_pointer + 1)

        if operand.startswith("+"):
            immutable_name = operand
            if immutable_name in self.immutables:
                return self.immutables[immutable_name]
            else:
                raise VertigoNameError(f"Undefined immutable '{immutable_name}'.",
                                       line_num=self.instruction_pointer + 1)

        if operand.startswith("@"):
            if not self.current_stack_name:
                raise VertigoValueError("No stack selected for '@' reference.", line_num=self.instruction_pointer + 1)
            stack = self.stacks[self.current_stack_name]
            if len(operand) > 1 and operand[1:].isdigit():
                index_from_top = int(operand[1:])
                if 1 <= index_from_top <= len(stack):
                    return stack[len(stack) - index_from_top]
                else:
                    raise VertigoIndexError(
                        f"Stack index out of bounds '{operand}' for stack '{self.current_stack_name}'.",
                        line_num=self.instruction_pointer + 1)
            elif len(stack) > 0:
                return stack[-1]
            else:
                raise VertigoIndexError(f"Current stack '{self.current_stack_name}' is empty for '@'.",
                                        line_num=self.instruction_pointer + 1)

        if operand.upper() == "TRUE":
            return True
        if operand.upper() == "FALSE":
            return False

        if self.local_register_stack and operand in self.local_register_stack[-1]:
            return self.local_register_stack[-1][operand]
        elif operand in self.registers:
            return self.registers[operand]

        if operand == "#":
            if self.current_stack_name:
                return "\n".join(map(str, self.stacks[self.current_stack_name]))
            else:
                raise VertigoValueError("No stack selected for '#' content dump.",
                                        line_num=self.instruction_pointer + 1)

        raise VertigoTypeError(f"Invalid data type or undefined variable/literal: '{operand}'.",
                               line_num=self.instruction_pointer + 1)


class InstructionHandlers:
    def __init__(self, state: InterpreterState, file_lines: list, interpreter_instance):
        self.state = state
        self.file_lines = file_lines
        self.interpreter = interpreter_instance
        self.idt = {
            0x0: self._end_program,
            0x1: self._print_int_oda
        }

    def _end_program(self):
        sys.exit()

    def _print_int_oda(self):
        if self.state.settings["intpr"] is True:
            print(self.state.registers["ODA"])
            self.state.registers["ODA"] = None
        else:
            print("intpr not init")

    def handle_new(self, parts):
        if len(parts) == 2:
            stack_name = parts[1]
            if stack_name in self.state.stacks:
                raise VertigoNameError(f"Stack '{stack_name}' already exists.",
                                       line_num=self.state.instruction_pointer + 1)
            self.state.stacks[stack_name] = []
        else:
            raise VertigoSyntaxError("Invalid NEW syntax. Expected 'NEW <stack_name>'.",
                                     line_num=self.state.instruction_pointer + 1)

    def handle_push(self, parts):
        if len(parts) == 2:
            value_to_push = self.state.get_value(parts[1])
            if not self.state.current_stack_name:
                raise VertigoLookupError("No stack selected for PUSH operation.",
                                         line_num=self.state.instruction_pointer + 1)
            self.state.stacks[self.state.current_stack_name].append(value_to_push)
        else:
            raise VertigoSyntaxError("Invalid PUSH syntax. Expected 'PUSH <value>'.",
                                     line_num=self.state.instruction_pointer + 1)

    def handle_dup(self, parts):
        if not self.state.current_stack_name:
            raise VertigoLookupError("No stack selected for DUP operation.",
                                     line_num=self.state.instruction_pointer + 1)
        if not self.state.stacks[self.state.current_stack_name]:
            raise VertigoIndexError(f"Cannot DUP from an empty stack '{self.state.current_stack_name}'.",
                                    line_num=self.state.instruction_pointer + 1)
        top_value = self.state.stacks[self.state.current_stack_name][-1]
        self.state.stacks[self.state.current_stack_name].append(top_value)

    def handle_rm(self, parts):
        if not self.state.current_stack_name:
            raise VertigoLookupError("No stack selected for DROP operation.",
                                     line_num=self.state.instruction_pointer + 1)
        if not self.state.stacks[self.state.current_stack_name]:
            raise VertigoIndexError(f"Stack '{self.state.current_stack_name}' is empty for DROP operation.",
                                    line_num=self.state.instruction_pointer + 1)
        self.state.stacks[self.state.current_stack_name].pop()

    def handle_pop(self, parts):
        if len(parts) == 2:
            reg = parts[1]
            target_reg_dict = None
            if self.state.local_register_stack and reg in self.state.local_register_stack[-1]:
                target_reg_dict = self.state.local_register_stack[-1]
            elif reg in self.state.registers:
                target_reg_dict = self.state.registers

            if target_reg_dict is None:
                raise VertigoNameError(f"Invalid register '{reg}' for POP operation.",
                                       line_num=self.state.instruction_pointer + 1)

            if not self.state.current_stack_name:
                raise VertigoLookupError("No stack selected for POP operation.",
                                         line_num=self.state.instruction_pointer + 1)
            if not self.state.stacks[self.state.current_stack_name]:
                raise VertigoIndexError(f"Stack '{self.state.current_stack_name}' is empty for POP operation.",
                                        line_num=self.state.instruction_pointer + 1)

            target_reg_dict[reg] = self.state.stacks[self.state.current_stack_name].pop()
        else:
            raise VertigoSyntaxError("Invalid POP syntax. Expected 'POP <register>'.",
                                     line_num=self.state.instruction_pointer + 1)

    def handle_math(self, parts):
        if len(parts) == 5:
            op = parts[1].upper()
            dest = parts[2]
            arg1 = self.state.get_value(parts[3])
            arg2 = self.state.get_value(parts[4])

            if not isinstance(arg1, (int, float)) or not isinstance(arg2, (int, float)):
                raise VertigoTypeError(
                    f"MATH operations require numerical operands. Got {type(arg1).__name__} and {type(arg2).__name__}.",
                    line_num=self.state.instruction_pointer + 1)

            result = None
            if op == "ADD":
                result = arg1 + arg2
            elif op == "MINUS":
                result = arg1 - arg2
            elif op == "MUL":
                result = arg1 * arg2
            elif op == "DIV":
                if arg2 != 0:
                    result = arg1 / arg2
                else:
                    raise VertigoZeroDivisionError("Division by zero is not allowed.",
                                                   line_num=self.state.instruction_pointer + 1)
            elif op == "MOD":
                if arg2 != 0:
                    result = arg1 % arg2
                else:
                    raise VertigoZeroDivisionError("Modulo by zero is not allowed.",
                                                   line_num=self.state.instruction_pointer + 1)
            elif op == "POW":
                result = arg1 ** arg2
            else:
                raise VertigoRuntimeError(f"Unknown MATH operation '{op}'.",
                                          line_num=self.state.instruction_pointer + 1)

            if dest == "&":
                if not self.state.current_stack_name:
                    raise VertigoLookupError("No stack selected for '&' destination.",
                                             line_num=self.state.instruction_pointer + 1)
                self.state.stacks[self.state.current_stack_name].append(result)
            elif self.state.local_register_stack and dest in self.state.local_register_stack[-1]:
                self.state.local_register_stack[-1][dest] = result
            elif dest in self.state.registers:
                self.state.registers[dest] = result
            else:
                raise VertigoNameError(f"Invalid destination '{dest}' for MATH operation.",
                                       line_num=self.state.instruction_pointer + 1)
        else:
            raise VertigoSyntaxError("Invalid MATH syntax. Expected 'MATH <operation> <destination> <arg1> <arg2>'.",
                                     line_num=self.state.instruction_pointer + 1)

    def handle_reg(self, parts):
        if len(parts) == 2:
            reg_name = parts[1]
            if self.state.local_register_stack:
                if reg_name in self.state.local_register_stack[-1]:
                    raise VertigoNameError(f"Local register '{reg_name}' already exists in current scope.",
                                           line_num=self.state.instruction_pointer + 1)
                self.state.local_register_stack[-1][reg_name] = None
            else:
                if reg_name in self.state.registers:
                    raise VertigoNameError(f"Global register '{reg_name}' already exists.",
                                           line_num=self.state.instruction_pointer + 1)
                self.state.registers[reg_name] = None
        else:
            raise VertigoSyntaxError("Invalid REG syntax. Expected 'REG <register_name>'.",
                                     line_num=self.state.instruction_pointer + 1)

    def handle_jump(self, parts):
        if len(parts) == 2:
            label_to_jump = parts[1]
            if label_to_jump in self.state.labels:
                self.state.instruction_pointer = self.state.labels[label_to_jump]
            else:
                raise VertigoNameError(f"Undefined label '{label_to_jump}' for JUMP.",
                                       line_num=self.state.instruction_pointer + 1)
        else:
            raise VertigoSyntaxError("Invalid JUMP syntax. Expected 'JUMP <label>'.",
                                     line_num=self.state.instruction_pointer + 1)

    def handle_jumpeq(self, parts):
        if len(parts) == 2:
            label_to_jump = parts[1]
            if label_to_jump in self.state.labels:
                if self.state.comparison_flags["equal"]:
                    self.state.instruction_pointer = self.state.labels[label_to_jump]
            else:
                raise VertigoNameError(f"Undefined label '{label_to_jump}' for JUMPEQ.",
                                       line_num=self.state.instruction_pointer + 1)
        else:
            raise VertigoSyntaxError("Invalid JUMPEQ syntax. Expected 'JUMPEQ <label>'.",
                                     line_num=self.state.instruction_pointer + 1)

    def handle_cmp(self, parts):
        if len(parts) == 3:
            operand1 = self.state.get_value(parts[1])
            operand2 = self.state.get_value(parts[2])

            if type(operand1) != type(operand2) and not (
                    isinstance(operand1, (int, float)) and isinstance(operand2, (int, float))):
                raise VertigoTypeError(
                    f"CMP operands must be of the same type or both numbers. Got {type(operand1).__name__} and {type(operand2).__name__}.",
                    line_num=self.state.instruction_pointer + 1)

            self.state.comparison_flags["equal"] = (operand1 == operand2)
            self.state.comparison_flags["greater"] = (operand1 > operand2)
            self.state.comparison_flags["less"] = (operand1 < operand2)
        else:
            raise VertigoSyntaxError("Invalid CMP syntax. Expected 'CMP <operand1> <operand2>'.",
                                     line_num=self.state.instruction_pointer + 1)

    def handle_point(self, parts):
        pass

    def handle_in(self, parts):
        prompt_str = ""
        if len(parts) > 1:
            prompt_str = self.state.get_value(parts[1])

        user_input = input(str(prompt_str))

        try:
            self.state.registers["IDA"] = int(user_input)
        except ValueError:
            try:
                self.state.registers["IDA"] = float(user_input)
            except ValueError:
                self.state.registers["IDA"] = user_input

    def handle_concat(self, parts):
        if len(parts) == 4:
            dest_reg = parts[1]
            val1 = self.state.get_value(parts[2])
            val2 = self.state.get_value(parts[3])

            str1 = str(val1)
            str2 = str(val2)

            if self.state.local_register_stack and dest_reg in self.state.local_register_stack[-1]:
                self.state.local_register_stack[-1][dest_reg] = str1 + str2
            elif dest_reg in self.state.registers:
                self.state.registers[dest_reg] = str1 + str2
            else:
                raise VertigoNameError(f"Invalid destination register '{dest_reg}' for CONCAT.",
                                       line_num=self.state.instruction_pointer + 1)
        else:
            raise VertigoSyntaxError(
                "Invalid CONCAT syntax. Expected 'CONCAT <destination_register> <value1> <value2>'.",
                line_num=self.state.instruction_pointer + 1)

    def handle_strlen(self, parts):
        if len(parts) == 3:
            dest_reg = parts[1]
            string_val = self.state.get_value(parts[2])
            if dest_reg not in self.state.registers and not (
                    self.state.local_register_stack and dest_reg in self.state.local_register_stack[-1]):
                raise VertigoNameError(f"Invalid destination register '{dest_reg}' for STRLEN.",
                                       line_num=self.state.instruction_pointer + 1)

            if self.state.local_register_stack and dest_reg in self.state.local_register_stack[-1]:
                self.state.local_register_stack[-1][dest_reg] = len(string_val)
            else:
                self.state.registers[dest_reg] = len(string_val)
        else:
            raise VertigoSyntaxError(
                "Invalid STRLEN syntax. Expected 'STRLEN <destination_register> <string_operand>'.",
                line_num=self.state.instruction_pointer + 1)

    def handle_strcmp(self, parts):
        if len(parts) == 3:
            str1 = self.state.get_value(parts[1])
            str2 = self.state.get_value(parts[2])
            if not isinstance(str1, str) or not isinstance(str2, str):
                raise VertigoTypeError("STRCMP operands must be strings.", line_num=self.state.instruction_pointer + 1)
            self.state.comparison_flags["equal"] = (str1 == str2)
            self.state.comparison_flags["greater"] = (str1 > str2)
            self.state.comparison_flags["less"] = (str1 < str2)
        else:
            raise VertigoSyntaxError("Invalid STRCMP syntax. Expected 'STRCMP <string1> <string2>'.",
                                     line_num=self.state.instruction_pointer + 1)

    def handle_jumpgt(self, parts):
        if len(parts) == 2:
            label_to_jump = parts[1]
            if label_to_jump in self.state.labels:
                if self.state.comparison_flags["greater"]:
                    self.state.instruction_pointer = self.state.labels[label_to_jump]
            else:
                raise VertigoNameError(f"Undefined label '{label_to_jump}' for JUMPGT.",
                                       line_num=self.state.instruction_pointer + 1)
        else:
            raise VertigoSyntaxError("Invalid JUMPGT syntax. Expected 'JUMPGT <label>'.",
                                     line_num=self.state.instruction_pointer + 1)

    def handle_jumplt(self, parts):
        if len(parts) == 2:
            label_to_jump = parts[1]
            if label_to_jump in self.state.labels:
                if self.state.comparison_flags["less"]:
                    self.state.instruction_pointer = self.state.labels[label_to_jump]
            else:
                raise VertigoNameError(f"Undefined label '{label_to_jump}' for JUMPLT.",
                                       line_num=self.state.instruction_pointer + 1)
        else:
            raise VertigoSyntaxError("Invalid JUMPLT syntax. Expected 'JUMPLT <label>'.",
                                     line_num=self.state.instruction_pointer + 1)

    def handle_jumpneq(self, parts):
        if len(parts) == 2:
            label_to_jump = parts[1]
            if label_to_jump in self.state.labels:
                if not self.state.comparison_flags["equal"]:
                    self.state.instruction_pointer = self.state.labels[label_to_jump]
            else:
                raise VertigoNameError(f"Undefined label '{label_to_jump}' for JUMPNEQ.",
                                       line_num=self.state.instruction_pointer + 1)
        else:
            raise VertigoSyntaxError("Invalid JUMPNEQ syntax. Expected 'JUMPNEQ <label>'.",
                                     line_num=self.state.instruction_pointer + 1)

    def handle_swap(self, parts):
        if not self.state.current_stack_name:
            raise VertigoLookupError("No stack selected for SWAP operation.",
                                     line_num=self.state.instruction_pointer + 1)
        if len(self.state.stacks[self.state.current_stack_name]) < 2:
            raise VertigoIndexError(f"Not enough items on stack '{self.state.current_stack_name}' for SWAP.",
                                    line_num=self.state.instruction_pointer + 1)
        stack = self.state.stacks[self.state.current_stack_name]
        stack[-1], stack[-2] = stack[-2], stack[-1]

    def handle_pick(self, parts):
        if len(parts) != 2:
            raise VertigoSyntaxError("Invalid PICK syntax. Expected 'PICK <n>' or 'PICK <register>'.",
                                     line_num=self.state.instruction_pointer + 1)
        index_arg = parts[1]
        n = None
        try:
            n = int(index_arg)
            if n < 0:
                raise VertigoValueError("PICK index must be non-negative.", line_num=self.state.instruction_pointer + 1)
        except ValueError:
            if self.state.local_register_stack and index_arg in self.state.local_register_stack[-1]:
                reg_value = self.state.local_register_stack[-1][index_arg]
                if isinstance(reg_value, int) and reg_value >= 0:
                    n = reg_value
                else:
                    raise VertigoTypeError(
                        f"Local register '{index_arg}' does not contain a valid non-negative integer for PICK.",
                        line_num=self.state.instruction_pointer + 1)
            elif index_arg in self.state.registers:
                reg_value = self.state.registers[index_arg]
                if isinstance(reg_value, int) and reg_value >= 0:
                    n = reg_value
                else:
                    raise VertigoTypeError(
                        f"Global register '{index_arg}' does not contain a valid non-negative integer for PICK.",
                        line_num=self.state.instruction_pointer + 1)
            else:
                raise VertigoValueError(
                    f"Invalid PICK index '{index_arg}'. Must be a non-negative integer or a valid register containing one.",
                    line_num=self.state.instruction_pointer + 1)

        if not self.state.current_stack_name:
            raise VertigoLookupError("No stack selected for PICK operation.",
                                     line_num=self.state.instruction_pointer + 1)
        stack = self.state.stacks[self.state.current_stack_name]
        if len(stack) <= n:
            raise VertigoIndexError(f"Not enough items on stack '{self.state.current_stack_name}' for PICK {n}.",
                                    line_num=self.state.instruction_pointer + 1)
        value_to_push = stack[-(n + 1)]
        stack.append(value_to_push)

    def handle_ppick(self, parts):
        if len(parts) != 2:
            raise VertigoSyntaxError("Invalid PPICK syntax. Expected 'PPICK <n>' or 'PPICK <register>'.",
                                     line_num=self.state.instruction_pointer + 1)
        index_arg = parts[1]
        n = None
        try:
            n = int(index_arg)
            if n < 0:
                raise VertigoValueError("PPICK index must be non-negative.",
                                        line_num=self.state.instruction_pointer + 1)
        except ValueError:
            if self.state.local_register_stack and index_arg in self.state.local_register_stack[-1]:
                reg_value = self.state.local_register_stack[-1][index_arg]
                if isinstance(reg_value, int) and reg_value >= 0:
                    n = reg_value
                else:
                    raise VertigoTypeError(
                        f"Local register '{index_arg}' does not contain a valid non-negative integer for PPICK.",
                        line_num=self.state.instruction_pointer + 1)
            elif index_arg in self.state.registers:
                reg_value = self.state.registers[index_arg]
                if isinstance(reg_value, int) and reg_value >= 0:
                    n = reg_value
                else:
                    raise VertigoTypeError(
                        f"Global register '{index_arg}' does not contain a valid non-negative integer for PPICK.",
                        line_num=self.state.instruction_pointer + 1)
            else:
                raise VertigoValueError(
                    f"Invalid PPICK index '{index_arg}'. Must be a non-negative integer or a valid register containing one.",
                    line_num=self.state.instruction_pointer + 1)

        if not self.state.current_stack_name:
            raise VertigoLookupError("No stack selected for PPICK operation.",
                                     line_num=self.state.instruction_pointer + 1)
        stack = self.state.stacks[self.state.current_stack_name]
        if len(stack) <= n:
            raise VertigoIndexError(f"Not enough items on stack '{self.state.current_stack_name}' for PPICK {n}.",
                                    line_num=self.state.instruction_pointer + 1)

        value_to_move = stack.pop(len(stack) - (n + 1))
        stack.append(value_to_move)

    def handle_clear(self, parts):
        if len(parts) == 1:
            if not self.state.current_stack_name:
                raise VertigoLookupError("No stack selected to CLEAR.", line_num=self.state.instruction_pointer + 1)
            self.state.stacks[self.state.current_stack_name].clear()
        else:
            raise VertigoSyntaxError("Invalid CLEAR syntax. Expected 'CLEAR'.",
                                     line_num=self.state.instruction_pointer + 1)

    def handle_rrot(self, parts):
        if len(parts) == 1:
            if not self.state.current_stack_name:
                raise VertigoLookupError("No stack selected for RROT.", line_num=self.state.instruction_pointer + 1)
            stack = self.state.stacks[self.state.current_stack_name]
            if len(stack) < 3:
                raise VertigoIndexError(
                    f"Not enough items on stack '{self.state.current_stack_name}' for RROT (requires at least 3).",
                    line_num=self.state.instruction_pointer + 1)
            top = stack.pop()
            middle = stack.pop()
            bottom = stack.pop()
            stack.append(top)
            stack.append(bottom)
            stack.append(middle)
        else:
            raise VertigoSyntaxError("Invalid RROT syntax. Expected 'RROT'.",
                                     line_num=self.state.instruction_pointer + 1)

    def handle_rot(self, parts):
        if len(parts) == 1:
            if not self.state.current_stack_name:
                raise VertigoLookupError("No stack selected for ROT.", line_num=self.state.instruction_pointer + 1)
            stack = self.state.stacks[self.state.current_stack_name]
            if len(stack) < 3:
                raise VertigoIndexError(
                    f"Not enough items on stack '{self.state.current_stack_name}' for ROT (requires at least 3).",
                    line_num=self.state.instruction_pointer + 1)
            top = stack.pop()
            middle = stack.pop()
            bottom = stack.pop()
            stack.append(middle)
            stack.append(top)
            stack.append(bottom)
        else:
            raise VertigoSyntaxError("Invalid ROT syntax. Expected 'ROT'.", line_num=self.state.instruction_pointer + 1)

    def handle_dump(self, parts):
        filename = self._dump_filename()

        if len(parts) == 1:
            print("--- STACKS ---")
            for name, stack in self.state.stacks.items():
                print(f"  {name}: {stack}")
            print("--- REGISTERS (GLOBAL) ---")
            for name, reg_val in self.state.registers.items():
                print(f"  {name}: {reg_val}")
            if self.state.local_register_stack:
                print("--- REGISTERS (LOCAL SCOPES - Top to Bottom) ---")
                for i, scope in enumerate(reversed(self.state.local_register_stack)):
                    print(f"  Scope {i + 1} (Depth {len(self.state.local_register_stack) - i}): {scope}")
            print("--- IMMUTABLES ---")
            for name, imm_val in self.state.immutables.items():
                print(f"  {name}: {imm_val}")
            print("--- COMPARISON FLAGS ---")
            for flag, val in self.state.comparison_flags.items():
                print(f"  {flag}: {val}")
        elif parts[1] == "@":
            if not self.state.current_stack_name:
                raise VertigoLookupError("No stack selected to DUMP '@'.", line_num=self.state.instruction_pointer + 1)
            print(f"--- CURRENT STACK ({self.state.current_stack_name}) ---")
            print(self.state.stacks[self.state.current_stack_name])
        elif parts[1].upper() == "LOGS":
            try:
                with open(filename, 'w') as dumpfile:
                    dumpfile.write(f"==={sys.argv[1]} LOG DUMP===\n{self.state.dump_log}\n")
                print(f"Dump logs written to {filename}")
            except IOError as e:
                raise VertigoRuntimeError(f"Failed to write dump logs to file: {e}",
                                          line_num=self.state.instruction_pointer + 1)
        else:
            raise VertigoSyntaxError("Invalid DUMP syntax. Expected 'DUMP', 'DUMP @', or 'DUMP LOGS'.",
                                     line_num=self.state.instruction_pointer + 1)

    def _dump_filename(self):
        now = datetime.datetime.now()
        timestamp_str = now.strftime("%M%S%Y-%H%M%S")
        filename = f"dump-{timestamp_str}.vtd"
        return filename

    def handle_ops(self, parts):
        if len(parts) < 3:
            raise VertigoSyntaxError(
                "Insufficient arguments for OPS. Expected 'OPS <operation> <destination> <arg1> [arg2...]'.",
                line_num=self.state.instruction_pointer + 1)
        operation = parts[1].upper()
        destination = parts[2]
        arguments = [self.state.get_value(arg) for arg in parts[3:]]
        result = None

        if operation == "AND":
            if len(arguments) < 2:
                raise VertigoSyntaxError("AND operation requires at least two arguments.",
                                         line_num=self.state.instruction_pointer + 1)
            result = True
            for arg in arguments:
                if not bool(arg):
                    result = False
                    break
        elif operation == "OR":
            if len(arguments) < 2:
                raise VertigoSyntaxError("OR operation requires at least two arguments.",
                                         line_num=self.state.instruction_pointer + 1)
            result = False
            for arg in arguments:
                if bool(arg):
                    result = True
                    break
        elif operation == "NOT":
            if len(arguments) != 1:
                raise VertigoSyntaxError("NOT operation requires exactly one argument.",
                                         line_num=self.state.instruction_pointer + 1)
            result = not bool(arguments[0])
        elif operation == "EQUAL":
            if len(arguments) != 2:
                raise VertigoSyntaxError("EQUAL operation requires exactly two arguments.",
                                         line_num=self.state.instruction_pointer + 1)
            result = (arguments[0] == arguments[1])
        elif operation == "NEQUAL":
            if len(arguments) != 2:
                raise VertigoSyntaxError("NEQUAL operation requires exactly two arguments.",
                                         line_num=self.state.instruction_pointer + 1)
            result = (arguments[0] != arguments[1])
        else:
            raise VertigoRuntimeError(f"Unknown OPS operation '{operation}'.",
                                      line_num=self.state.instruction_pointer + 1)

        result_val = 1 if result else 0

        if destination == "&":
            if not self.state.current_stack_name:
                raise VertigoLookupError("No stack selected for '&' destination.",
                                         line_num=self.state.instruction_pointer + 1)
            self.state.stacks[self.state.current_stack_name].append(result_val)
        elif self.state.local_register_stack and destination in self.state.local_register_stack[-1]:
            self.state.local_register_stack[-1][destination] = result_val
        elif destination in self.state.registers:
            self.state.registers[destination] = result_val
        else:
            raise VertigoNameError(f"Invalid destination '{destination}' for OPS operation.",
                                   line_num=self.state.instruction_pointer + 1)

    def handle_loop(self, parts):
        if "LTM" not in self.state.registers or "CLI" not in self.state.registers:
            raise VertigoRuntimeError("LOOP requires 'LTM' and 'CLI' registers to be defined.",
                                      line_num=self.state.instruction_pointer + 1)
        self.state.loop_stack.append({
            'loop_start_ip': self.state.instruction_pointer,
            'previous_cli': self.state.registers["CLI"],
            'previous_ltm': self.state.registers["LTM"]
        })
        self.state.registers["CLI"] = 0

    def handle_endloop(self, parts):
        if not self.state.loop_stack:
            raise VertigoRuntimeError("ENDLOOP encountered without a matching LOOP.",
                                      line_num=self.state.instruction_pointer + 1)

        ltm_for_current_loop = self.state.registers["LTM"]
        self.state.registers["CLI"] += 1

        if ltm_for_current_loop == 0 or self.state.registers["CLI"] <= ltm_for_current_loop:
            loop_context = self.state.loop_stack[-1]
            self.state.instruction_pointer = loop_context['loop_start_ip']
        else:
            loop_context = self.state.loop_stack.pop()
            self.state.registers["CLI"] = loop_context['previous_cli']
            self.state.registers["LTM"] = loop_context['previous_ltm']

    def handle_sub(self, parts):
        pass

    def handle_endsub(self, parts):
        pass

    def handle_call(self, parts):
        if len(parts) != 2:
            raise VertigoSyntaxError("Invalid CALL syntax. Expected 'CALL <subroutine_name>'.",
                                     line_num=self.state.instruction_pointer + 1)
        subroutine_name = parts[1]
        if subroutine_name not in self.state.subroutines:
            raise VertigoNameError(f"Undefined subroutine '{subroutine_name}'.",
                                   line_num=self.state.instruction_pointer + 1)

        self.state.return_stack.append(self.state.instruction_pointer)
        # CALL does NOT push a new local_register_stack scope.
        # Registers in the called subroutine will operate on the caller's scope.

        subroutine_info = self.state.subroutines[subroutine_name]
        subroutine_code_lines = subroutine_info['code']
        subroutine_start_line_in_file = subroutine_info['start_line']

        subroutine_ip_local = 0
        while subroutine_ip_local < len(subroutine_code_lines):
            line = self.file_lines[subroutine_start_line_in_file + 1 + subroutine_ip_local].split(';')[0].strip()
            sub_parts = VertigoLexer.split(line)
            if sub_parts:
                absolute_line_in_file = subroutine_start_line_in_file + 1 + subroutine_ip_local

                self.interpreter._execute_instruction(sub_parts, absolute_line_in_file)

            subroutine_ip_local += 1

        self.state.instruction_pointer = self.state.return_stack.pop()

    def handle_lcall(self, parts):
        if len(parts) != 2:
            raise VertigoSyntaxError("Invalid LCALL syntax. Expected 'LCALL <subroutine_name>'.",
                                     line_num=self.state.instruction_pointer + 1)
        subroutine_name = parts[1]
        if subroutine_name not in self.state.subroutines:
            raise VertigoNameError(f"Undefined subroutine '{subroutine_name}'.",
                                   line_num=self.state.instruction_pointer + 1)

        self.state.return_stack.append(self.state.instruction_pointer)
        self.state.local_register_stack.append({})  # Push a new local scope for LCALL

        subroutine_info = self.state.subroutines[subroutine_name]
        subroutine_code_lines = subroutine_info['code']
        subroutine_start_line_in_file = subroutine_info['start_line']

        subroutine_ip_local = 0
        try:
            while subroutine_ip_local < len(subroutine_code_lines):
                line = self.file_lines[subroutine_start_line_in_file + 1 + subroutine_ip_local].split(';')[0].strip()
                sub_parts = VertigoLexer.split(line)
                if sub_parts:
                    absolute_line_in_file = subroutine_start_line_in_file + 1 + subroutine_ip_local

                    self.interpreter._execute_instruction(sub_parts, absolute_line_in_file)

                subroutine_ip_local += 1
        finally:
            if self.state.local_register_stack:
                self.state.local_register_stack.pop()
            self.state.instruction_pointer = self.state.return_stack.pop()

    def handle_wait(self, parts):
        if len(parts) != 2:
            raise VertigoSyntaxError("Invalid WAIT syntax. Expected 'WAIT <milliseconds>'.",
                                     line_num=self.state.instruction_pointer + 1)
        try:
            sleeptime_ms = int(self.state.get_value(parts[1]))
            if sleeptime_ms < 0:
                raise VertigoValueError("WAIT time must be non-negative.", line_num=self.state.instruction_pointer + 1)
            time.sleep(sleeptime_ms / 1000.0)
        except (ValueError, TypeError):
            raise VertigoTypeError("WAIT operand must be a number.", line_num=self.state.instruction_pointer + 1)

    def handle_bring(self, parts):
        if len(parts) != 2:
            raise VertigoSyntaxError("Invalid BRING syntax. Expected 'BRING <library_filename>'.",
                                     line_num=self.state.instruction_pointer + 1)

        # Construct path to libs directory
        # sys.path[0] is the directory of the currently running script (vertigo.py or vertigo.exe)
        # Using os.path.join for cross-platform compatibility
        libs_dir = os.path.join(sys.path[0], "libs")
        library_filename = os.path.join(libs_dir,
                                        self.state.get_value(parts[1]))  # get_value for potential variables in path

        try:
            with open(library_filename, 'r') as lib_file:
                library_content = lib_file.read()
        except FileNotFoundError:
            raise VertigoImportError(f"Library file '{library_filename}' not found.",
                                     line_num=self.state.instruction_pointer + 1)
        except Exception as e:
            raise VertigoImportError(f"Error reading library file '{library_filename}': {e}",
                                     line_num=self.state.instruction_pointer + 1)

        blocks = library_content.strip().split(':')
        i = 0
        while i < len(blocks):
            if blocks[i].strip():
                subroutine_name = blocks[i].strip()
                i += 1
                subroutine_code = []
                if i < len(blocks):
                    code_lines = blocks[i].strip().split('\n')
                    for line in code_lines:
                        if line.strip():
                            subroutine_code.append(line)
                    if subroutine_name in self.state.subroutines:
                        raise VertigoNameError(
                            f"Subroutine '{subroutine_name}' from library '{library_filename}' already defined.",
                            line_num=self.state.instruction_pointer + 1)
                    self.state.subroutines[subroutine_name] = {'code': subroutine_code, 'from_library': True}
                else:
                    raise VertigoSyntaxError(
                        f"Malformed library file '{library_filename}': missing code for subroutine '{subroutine_name}'.",
                        line_num=self.state.instruction_pointer + 1)
            i += 1

    def handle_import(self, parts):
        if len(parts) != 2:
            raise VertigoSyntaxError("Invalid IMPORT syntax. Expected 'IMPORT <python_module_name>'.",
                                     line_num=self.state.instruction_pointer + 1)

        module_name_raw = parts[1].strip('"')

        # Construct path to libs directory
        # sys.path[0] is the directory of the currently running script (vertigo.py or vertigo.exe)
        # Using os.path.join for cross-platform compatibility
        libs_dir = os.path.join(sys.path[0], "libs")
        module_path = os.path.join(libs_dir, f"{module_name_raw}.py")  # Construct full path including .py extension

        try:
            module_globals = {}
            # Inject VertigoError classes into the module's globals so it can raise them
            module_globals['VertigoError'] = VertigoError
            module_globals['VertigoSyntaxError'] = VertigoSyntaxError
            module_globals['VertigoRuntimeError'] = VertigoRuntimeError
            module_globals['VertigoNameError'] = VertigoNameError
            module_globals['VertigoTypeError'] = VertigoTypeError
            module_globals['VertigoIndexError'] = VertigoIndexError
            module_globals['VertigoZeroDivisionError'] = VertigoZeroDivisionError
            module_globals['VertigoImportError'] = VertigoImportError

            # Execute the module content in its own globals
            module_file_content = open(module_path).read()  # Open using the constructed path
            exec(module_file_content, module_globals)

            if '__vertigo_library__' in module_globals and isinstance(module_globals['__vertigo_library__'], dict):
                library_info = module_globals['__vertigo_library__']

                if 'initializer' in library_info and callable(library_info['initializer']):
                    library_info['initializer'](self.state)

                if 'instructions' in library_info and isinstance(library_info['instructions'], dict):
                    for instr_name, handler_func in library_info['instructions'].items():
                        if callable(handler_func):
                            bound_handler = handler_func.__get__(self, self.__class__)
                            self.interpreter.instruction_handlers_map[instr_name.upper()] = bound_handler
                        else:
                            raise VertigoImportError(
                                f"Handler for instruction '{instr_name}' in module '{module_name_raw}' is not callable.",
                                line_num=self.state.instruction_pointer + 1)
                else:
                    raise VertigoImportError(
                        f"Imported library '{module_name_raw}' does not have a valid 'instructions' dictionary in __vertigo_library__.",
                        line_num=self.state.instruction_pointer + 1)
            else:
                raise VertigoImportError(
                    f"Python module '{module_name_raw}' is not a valid Vertigo library (missing or malformed '__vertigo_library__').",
                    line_num=self.state.instruction_pointer + 1)

        except FileNotFoundError:
            raise VertigoImportError(f"Python module file '{module_path}' not found.",
                                     line_num=self.state.instruction_pointer + 1)
        except Exception as e:
            raise VertigoImportError(f"Failed to import Python module '{module_name_raw}': {e}",
                                     line_num=self.state.instruction_pointer + 1)

    def handle_im(self, parts):
        if len(parts) != 3:
            raise VertigoSyntaxError("Invalid IM syntax. Expected 'IM <immutable_name> <value>'.",
                                     line_num=self.state.instruction_pointer + 1)

        immutable_key = "+" + parts[1]
        value_to_store = self.state.get_value(parts[2])

        if immutable_key in self.state.immutables:
            self.state.dump_log += f"\nImmutable {immutable_key} already defined, skipping."
        else:
            self.state.immutables[immutable_key] = value_to_store

    def handle_int(self, parts):
        if len(parts) != 2:
            raise VertigoSyntaxError("Invalid INT syntax. Expected 'INT <interrupt_code>'.",
                                     line_num=self.state.instruction_pointer + 1)

        interrupt_code_operand = parts[1]
        try:
            interrupt_code = int(self.state.get_value(interrupt_code_operand))
        except (ValueError, TypeError):
            raise VertigoTypeError(f"Invalid interrupt code '{interrupt_code_operand}'. Must be an integer.",
                                   line_num=self.state.instruction_pointer + 1)

        if interrupt_code in self.idt:
            self.idt[interrupt_code]()
        else:
            raise VertigoRuntimeError(f"Unknown interrupt code '{interrupt_code}'.",
                                      line_num=self.state.instruction_pointer + 1)

    def handle_set(self, parts):
        if len(parts) != 3:
            raise VertigoSyntaxError("Invalid SET syntax. Expected 'SET <setting_name> <value>'.",
                                     line_num=self.state.instruction_pointer + 1)
        setting_name = parts[1]
        set_value = self.state.get_value(parts[2])

        if setting_name in self.state.settings:
            if setting_name == "intpr":
                if isinstance(set_value, int) and set_value in (0, 1):
                    set_value = bool(set_value)
                elif not isinstance(set_value, bool):
                    raise VertigoTypeError(
                        f"Setting 'intpr' requires a boolean value (TRUE/FALSE or 1/0). Got {type(set_value).__name__}.",
                        line_num=self.state.instruction_pointer + 1)
            self.state.settings[setting_name] = set_value
        else:
            raise VertigoNameError(f"Unknown setting '{setting_name}'.", line_num=self.state.instruction_pointer + 1)


class VertigoInterpreter:
    def __init__(self, filename):
        self.state = InterpreterState()
        self.filename = filename
        self.file_lines = self._load_file(filename)
        self.instruction_handlers = InstructionHandlers(self.state, self.file_lines, self)
        self.instruction_handlers_map = {
            "NEW": self.instruction_handlers.handle_new,
            "PUSH": self.instruction_handlers.handle_push,
            "DUP": self.instruction_handlers.handle_dup,
            "DROP": self.instruction_handlers.handle_rm,
            "POP": self.instruction_handlers.handle_pop,
            "MATH": self.instruction_handlers.handle_math,
            "REG": self.instruction_handlers.handle_reg,
            "JUMP": self.instruction_handlers.handle_jump,
            "JUMPEQ": self.instruction_handlers.handle_jumpeq,
            "CMP": self.instruction_handlers.handle_cmp,
            "POINT": self.instruction_handlers.handle_point,
            "IN": self.instruction_handlers.handle_in,
            "CONCAT": self.instruction_handlers.handle_concat,
            "STRLEN": self.instruction_handlers.handle_strlen,
            "STRCMP": self.instruction_handlers.handle_strcmp,
            "JUMPGT": self.instruction_handlers.handle_jumpgt,
            "JUMPLT": self.instruction_handlers.handle_jumplt,
            "JUMPNEQ": self.instruction_handlers.handle_jumpneq,
            "SWAP": self.instruction_handlers.handle_swap,
            "PICK": self.instruction_handlers.handle_pick,
            "PPICK": self.instruction_handlers.handle_ppick,
            "CLEAR": self.instruction_handlers.handle_clear,
            "RROT": self.instruction_handlers.handle_rrot,
            "ROT": self.instruction_handlers.handle_rot,
            "DUMP": self.instruction_handlers.handle_dump,
            "OPS": self.instruction_handlers.handle_ops,
            "LOOP": self.instruction_handlers.handle_loop,
            "ENDLOOP": self.instruction_handlers.handle_endloop,
            "SUB": self.instruction_handlers.handle_sub,
            "ENDSUB": self.instruction_handlers.handle_endsub,
            "CALL": self.instruction_handlers.handle_call,
            "LCALL": self.instruction_handlers.handle_lcall,
            "WAIT": self.instruction_handlers.handle_wait,
            "BRING": self.instruction_handlers.handle_bring,
            "IMPORT": self.instruction_handlers.handle_import,
            "IM": self.instruction_handlers.handle_im,
            "INT": self.instruction_handlers.handle_int,
            "SET": self.instruction_handlers.handle_set
        }

    def _load_file(self, filename):
        try:
            with open(filename, 'r') as f:
                return f.read().split("\n")
        except FileNotFoundError:
            raise VertigoRuntimeError(f"Source file '{filename}' not found.")
        except Exception as e:
            raise VertigoRuntimeError(f"Error loading source file '{filename}': {e}")

    def _first_pass(self):
        line_num = 0
        while line_num < len(self.file_lines):
            line = self.file_lines[line_num].split(';')[0].strip()
            parts = VertigoLexer.split(line)

            if parts and parts[0].upper() == "POINT":
                if len(parts) == 2:
                    label_name = parts[1]
                    if label_name in self.state.labels:
                        raise VertigoNameError(f"Label '{label_name}' already defined.", line_num=line_num + 1)
                    self.state.labels[label_name] = line_num
                else:
                    raise VertigoSyntaxError("Invalid POINT syntax. Expected 'POINT <label_name>'.",
                                             line_num=line_num + 1)
            elif parts and parts[0].upper() == "SUB":
                if len(parts) < 2:
                    raise VertigoSyntaxError("SUB requires a subroutine name.", line_num=line_num + 1)
                subroutine_name = parts[1]
                if subroutine_name in self.state.subroutines:
                    raise VertigoNameError(f"Subroutine '{subroutine_name}' already defined.", line_num=line_num + 1)

                subroutine_code = []
                sub_line_num = line_num + 1
                start_sub_line = line_num
                while sub_line_num < len(self.file_lines):
                    sub_line = self.file_lines[sub_line_num].split(';')[0].strip()
                    sub_parts = VertigoLexer.split(sub_line)
                    if sub_parts and sub_parts[0].upper() == "ENDSUB":
                        self.state.subroutines[subroutine_name] = {
                            'code': subroutine_code,
                            'start_line': start_sub_line,
                            'end_line': sub_line_num
                        }
                        line_num = sub_line_num
                        break
                    subroutine_code.append(sub_line)
                    sub_line_num += 1
                else:
                    raise VertigoSyntaxError(f"Missing ENDSUB for subroutine '{subroutine_name}'.",
                                             line_num=line_num + 1)
            line_num += 1

    def _execute_instruction(self, parts, current_line_num):
        instruction = parts[0].upper()

        self.state.instruction_pointer = current_line_num

        if instruction in self.instruction_handlers_map:
            self.instruction_handlers_map[instruction](parts)
        elif parts[0] in self.state.stacks:
            self.state.current_stack_name = parts[0]
        else:
            raise VertigoSyntaxError(f"Unknown instruction '{instruction}'.", line_num=current_line_num + 1)

    def run(self, args):
        self._first_pass()

        if len(args) > 1:
            for i, arg_val in enumerate(args[1:]):
                self.state.registers[f"LIN{i}"] = self.state.get_value(arg_val)

        start_time = time.perf_counter()

        while self.state.instruction_pointer < len(self.file_lines):
            current_line_num = self.state.instruction_pointer
            line = self.file_lines[current_line_num].split(';')[0].strip()
            parts = VertigoLexer.split(line)

            try:
                if parts:
                    instruction_name = parts[0].upper()
                    if instruction_name == "SUB":
                        subroutine_name = parts[1]
                        if subroutine_name in self.state.subroutines:
                            self.state.instruction_pointer = self.state.subroutines[subroutine_name]['end_line']
                        self.state.instruction_pointer += 1
                        continue
                    elif instruction_name == "ENDSUB":
                        self.state.instruction_pointer += 1
                        continue

                    self._execute_instruction(parts, current_line_num)

                    if instruction_name not in ["JUMP", "JUMPEQ", "JUMPGT", "JUMPLT", "JUMPNEQ", "ENDLOOP"]:
                        self.state.instruction_pointer += 1
                else:
                    self.state.instruction_pointer += 1

                current_time = time.perf_counter() - start_time
                self.state.dump_log += (
                    f"{parts[0].upper() if parts else 'EMPTY'} ARGS {parts[1:] if parts else ''}\n"
                    f"{current_line_num + 1} [{current_time:.4f}] "
                )
                if self.state.registers["ODA"] is not None and self.state.settings["intpr"] is False:
                    print(self.state.registers["ODA"])
                    self.state.registers["ODA"] = None

            except VertigoError as e:
                raise e
            except KeyboardInterrupt:
                print("KeyboardInterrupt")
                sys.exit()
            except Exception as e:
                raise VertigoRuntimeError(f"An unexpected error occurred: {e}", line_num=current_line_num + 1)


def vertigo_exception_hook(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, VertigoError):
        print(f"File {sys.argv[1]} at line {exc_value.line_num if exc_value.line_num is not None else '?'}; STOP.")
        print(f"{exc_type.__name__}: {exc_value}")
    else:
        sys.__excepthook__(exc_type, exc_value, exc_traceback)


sys.excepthook = vertigo_exception_hook

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python vertigo_interpreter.py <source_file.vtd> [arg1] [arg2]...")
        sys.exit(1)

    interpreter = VertigoInterpreter(sys.argv[1])
    interpreter.run(sys.argv[1:])
