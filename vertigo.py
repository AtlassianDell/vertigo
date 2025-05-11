import sys
import os
import shlex
import re
import time
import datetime
starttime = time.perf_counter()
opt = True

def dumpfilename():
 now = datetime.datetime.now()
 timestamp_str = now.strftime("%m%d%S")
 filename = f"dump-{timestamp_str}.vtd"
 return filename

labels = {}

file = open(sys.argv[1]).read().split("\n")

stacks = {"_loop_stack":[]}
curstack = ""
registers = {
    "ODA": None,
    "IDA": None,
    "CLI": 0,
    "LTM": 0
}
comparison_flags = {"equal": False, "greater": False, "less": False}
subroutines = {}  # Dictionary to store subroutine definitions
return_stack = []  # List to store return addresses
instruction_pointer = 0
is_in_subroutine = False
current_subroutine_code = []
current_subroutine_ip = 0
subroutine_return_address = None

def handle_wait(parts):
 sleeptime = (int(parts[1]))/100
 time.sleep(sleeptime)

def handle_call(parts):
    global instruction_pointer, subroutines, return_stack
    if len(parts) != 2:
        print(f"Syntax Error: CALL instruction requires a subroutine name on Line {instruction_pointer + 1}")
        exit()

    subroutine_name = parts[1]
    if subroutine_name not in subroutines:
        print(f"Error: Undefined subroutine '{subroutine_name}' on Line {instruction_pointer + 1}")
        exit()

    return_stack.append(instruction_pointer)  # Store the return address

    subroutine_code = subroutines[subroutine_name]['code']
    subroutine_ip = 0

    while subroutine_ip < len(subroutine_code):
        line = subroutine_code[subroutine_ip]
        sub_parts = shlex.split(line)
        if sub_parts:
            instruction = sub_parts[0].upper()
            if instruction in instruction_handlers:
                instruction_handlers[instruction](sub_parts)
            elif sub_parts[0] in stacks.keys():
                global curstack
                curstack = sub_parts[0] # Handle stack selection within subroutine
        subroutine_ip += 1

    instruction_pointer = return_stack.pop()  # Restore the instruction pointer after subroutine execution

def handle_sub(parts):
    global instruction_pointer, file, subroutines
    if len(parts) < 2:
        print(f"Syntax Error: SUB instruction requires a subroutine name on Line {instruction_pointer + 1}")
        exit()

    subroutine_name = parts[1]
    if subroutine_name in subroutines:
        print(f"Error: Subroutine '{subroutine_name}' already defined on Line {instruction_pointer + 1}")
        exit()

    subroutines[subroutine_name] = {'code': [], 'start': instruction_pointer + 1}
    instruction_pointer += 1  # Move past the SUB line

    while instruction_pointer < len(file):
        line = file[instruction_pointer].strip()
        parts = line.split()
        if parts and parts[0].upper() == "ENDSUB":
            instruction_pointer += 1  # Move past ENDSUB
            return  # Exit handle_sub
        subroutines[subroutine_name]['code'].append(line)
        instruction_pointer += 1
    print(f"Error: Missing ENDSUB for subroutine '{subroutine_name}'")
    exit()

def handle_endsub(parts):
    pass  # The ENDSUB instruction is handled within handle_sub



def handle_loop(parts):
    global instruction_pointer, stacks, registers
    global start_ip
    if "LTM" not in registers or "CLI" not in registers:
        error("LTM or CLI not initialized")

    ltm = registers["LTM"]
    start_ip = instruction_pointer
    registers["CLI"] += 1
      # Increment to move past LOOP

def handle_endloop(parts):
    global instruction_pointer, stacks, registers
    if "CLI" not in registers:
        error("LTM or CLI not initialized")
    ltm = registers["LTM"]
    registers["CLI"] += 1

    if ltm == 0 or registers["CLI"] <= ltm:
        instruction_pointer = start_ip  # Go back to the start of the loop
    else:
        registers["CLI"] = 0
          # Let main loop handle increment


def handle_ops(parts):
    global instruction_pointer, stacks, curstack, registers

    if len(parts) < 3:
        error("Invalid OPS syntax")

    operation = parts[1].upper()
    destination = parts[2]
    arguments = [get_value(arg) for arg in parts[3:]]

    result = None

    if operation == "AND":
        if len(arguments) < 2:
            error("Invalid AND syntax")
        result = 1
        for arg in arguments:
            if not arg:
                result = 0
                break
    elif operation == "OR":
        if len(arguments) < 2:
            error("Invalid OR syntax")
        result = 0
        for arg in arguments:
            if arg:
                result = 1
                break
    elif operation == "NOT":
        if len(arguments) != 1:
            error("Invalid NOT syntax")
        result = 1 if not arguments[0] else 0
    elif operation == "EQUAL":
        if len(arguments) != 2:
            error("Invalid EQUAL syntax")
        result = 1 if arguments[0] == arguments[1] else 0
    elif operation == "NEQUAL":
        if len(arguments) != 2:
            error("Invalid NEQUAL syntax")
        result = 1 if arguments[0] != arguments[1] else 0
    else:
        print(f"Error: Unknown OPS operation '{operation}' on Line {instruction_pointer + 1}")
        exit()

    if result is not None:
        if destination == "&":
            if curstack:
                stacks[curstack].append(result)
            else:
                print(f"Error: No stack selected for '&' destination on Line {instruction_pointer + 1}")
                exit()
        elif destination in registers:
            registers[destination] = result
        else:
            print(f"Error: Invalid destination '{destination}' on Line {instruction_pointer + 1}")
            exit()

def handle_dump(parts):
  filename = dumpfilename()
  if len(parts) == 1:
    print(stacks)
    exit()
  elif parts[1] == "@":
    print(stacks[curstack])
    exit()
  elif parts[1] == "LOGS":
    with open(filename, 'w') as dumpfile:
     dumpfile.write(f"==={sys.argv[1]} LOG DUMP===\n"+dump+"\n")
  else:
    print("ERROR: Invalid on line "+str(instruction_pointer+1))
    exit()

def handle_rrot(parts):
    global instruction_pointer, stacks, curstack
    if len(parts) == 1:
        if curstack and len(stacks[curstack]) >= 3:
            stack = stacks[curstack]
            top = stack.pop()
            middle = stack.pop()
            bottom = stack.pop()
            stack.append(top)
            stack.append(bottom)
            stack.append(middle)
        elif not curstack:
            print(f"Error: No stack selected for RROT on Line {instruction_pointer + 1}")
            exit()
        else:
            print(f"Error: Not enough items on stack '{curstack}' for RROT on Line {instruction_pointer + 1}")
            exit()
    else:
        print(f"Syntax Error: Invalid RROT syntax. Expected 'RROT' on Line {instruction_pointer + 1}")
        exit()


def handle_rot(parts):
    global instruction_pointer, stacks, curstack
    if len(parts) == 1:
        if curstack and len(stacks[curstack]) >= 3:
            stack = stacks[curstack]
            top = stack.pop()
            middle = stack.pop()
            bottom = stack.pop()
            stack.append(middle)
            stack.append(top)
            stack.append(bottom)
        elif not curstack:
            print(f"Error: No stack selected for ROT on Line {instruction_pointer + 1}")
            exit()
        else:
            print(f"Error: Not enough items on stack '{curstack}' for ROT on Line {instruction_pointer + 1}")
            exit()
    else:
        print(f"Syntax Error: Invalid ROT syntax. Expected 'ROT' on Line {instruction_pointer + 1}")
        exit()


def handle_clear(parts):
    global instruction_pointer, stacks, curstack
    if len(parts) == 1:  # CLEAR should not have any arguments
        if curstack:
            stacks[curstack] = []
        else:
            print(f"Error: No stack selected to CLEAR on Line {instruction_pointer + 1}")
            exit()
    else:
        print(f"Syntax Error: Invalid CLEAR syntax. Expected 'CLEAR' on Line {instruction_pointer + 1}")
        exit()

def handle_ppick(parts):
    global instruction_pointer
    if len(parts) != 2:
        print(f"Syntax Error: Invalid PPICK syntax. Expected 'PPICK <n>' or 'PPICK <register>' on Line {instruction_pointer + 1}")
        exit()

    index_arg = parts[1]
    try:
        n = int(index_arg)
        if n < 0:
            print(f"Error: PPICK index must be non-negative on Line {instruction_pointer + 1}")
            exit()
    except ValueError:
        # Argument is not a direct integer, check if it's a register
        if index_arg in registers:
            reg_value = registers[index_arg]
            if isinstance(reg_value, int) and reg_value >= 0:
                n = reg_value
            else:
                print(f"Error: Register '{index_arg}' does not contain a valid non-negative integer for PPICK on Line {instruction_pointer + 1}")
                exit()
        else:
            print(f"Error: Invalid PPICK index '{index_arg}'. Must be a non-negative integer or a valid register containing one on Line {instruction_pointer + 1}")
            exit()

    if not curstack or len(stacks[curstack]) <= n:
        print(f"Error: Not enough items on stack '{curstack}' for PPICK {n} on Line {instruction_pointer + 1}")
        exit()

    stack = stacks[curstack]
    value_to_push = stack[-(n + 1)]
    stack.append(value_to_push)
    del stack[-(n + 2)]

def handle_pick(parts):
    global instruction_pointer
    if len(parts) != 2:
        print(f"Syntax Error: Invalid PICK syntax. Expected 'PICK <n>' or 'PICK <register>' on Line {instruction_pointer + 1}")
        exit()

    index_arg = parts[1]
    try:
        n = int(index_arg)
        if n < 0:
            print(f"Error: PICK index must be non-negative on Line {instruction_pointer + 1}")
            exit()
    except ValueError:
        # Argument is not a direct integer, check if it's a register
        if index_arg in registers:
            reg_value = registers[index_arg]
            if isinstance(reg_value, int) and reg_value >= 0:
                n = reg_value
            else:
                print(f"Error: Register '{index_arg}' does not contain a valid non-negative integer for PICK on Line {instruction_pointer + 1}")
                exit()
        else:
            print(f"Error: Invalid PICK index '{index_arg}'. Must be a non-negative integer or a valid register containing one on Line {instruction_pointer + 1}")
            exit()

    if not curstack or len(stacks[curstack]) <= n:
        print(f"Error: Not enough items on stack '{curstack}' for PICK {n} on Line {instruction_pointer + 1}")
        exit()

    stack = stacks[curstack]
    value_to_push = stack[-(n + 1)]
    stack.append(value_to_push)

def handle_swap(parts):
    global instruction_pointer
    if not curstack or len(stacks[curstack]) < 2:
        print(f"Error: Not enough items on stack '{curstack}' for SWAP on Line {instruction_pointer + 1}")
        exit()
    stack = stacks[curstack]
    stack[-1], stack[-2] = stack[-2], stack[-1]

def regstep():
    if registers["ODA"] != None:
        print(registers["ODA"])
        registers["ODA"] = None

def get_value(operand):
    global stacks, curstack, registers, ida

    if operand.isdigit() or (operand.startswith("-") and operand[1:].isdigit()):
        return int(operand)
    elif operand.replace('.', '', 1).isdigit() or (operand.startswith("-") and operand[1:].replace('.', '', 1).isdigit()):
        try:
            return float(operand)
        except ValueError:
            pass
    elif operand.startswith('"') and operand.endswith('"'):
        return operand[1:-1]
    elif operand.startswith('$"') and operand.endswith('"'):
        return len(operand[1:-1])
    elif operand.upper() == "TRUE":
        return 1
    elif operand.upper() == "FALSE":
        return 0
    elif operand in registers:
        return registers[operand]
    elif operand.startswith("$"):
        stack_reg_name = operand[1:]
        if stack_reg_name in stacks:
            return len(stacks[stack_reg_name])
        elif stack_reg_name in registers and isinstance(registers[stack_reg_name], str):
            return len(registers[stack_reg_name])
        elif stack_reg_name in registers and isinstance(registers[stack_reg_name], (int, float)):
            return 1
        else:
            print(f"Error: Invalid identifier '{operand}' on Line {instruction_pointer + 1}")
            exit()
    elif operand.startswith("@"):
        if curstack:
            stack = stacks[curstack]
            if len(operand) > 1 and operand[1:].isdigit():
                index_from_top = int(operand[1:])
                if 1 <= index_from_top <= len(stack):
                    return stack[len(stack) - index_from_top]  # Access using 1-based index from top
                else:
                    print(f"Error: Stack index out of bounds '{operand}' on Line {instruction_pointer + 1}")
                    exit()
            elif len(stack) > 0:
                return stack[-1]  # Default to top element if no index (which is now @1)
            else:
                print(f"Error: Current stack '{curstack}' is empty for '@' on Line {instruction_pointer + 1}")
                exit()
        else:
            print(f"Error: No stack selected for '@' on Line {instruction_pointer + 1}")
            exit()
    elif operand == "#":
      txt = "\n".join(map(str, stacks[curstack]))
      return txt
    else:
        return operand

def handle_new(parts):
    global instruction_pointer
    if len(parts) == 2:
        stacks[parts[1]] = []
    else:
        print(f"Syntax Error: Invalid NEW syntax on Line {instruction_pointer + 1}")
        exit()

def handle_stack_select(parts):
    global curstack, instruction_pointer
    curstack = parts[0]

def handle_push(parts):
    global instruction_pointer
    if len(parts) == 2:
        value_to_push = parts[1]
        if not curstack:
            print(f"Error: No stack selected for PUSH on Line {instruction_pointer + 1}")
            exit()
        stacks[curstack].append(get_value(value_to_push))
    else:
        print(f"Error: Invalid PUSH syntax on Line {instruction_pointer + 1}")
        exit()

def handle_dup(parts):
    global instruction_pointer
    if not curstack:
        print(f"Error: No stack selected for DUP on Line {instruction_pointer + 1}")
        exit()
    if stacks[curstack]:
        top_value = stacks[curstack][-1]
        stacks[curstack].append(top_value)
    else:
        print(f"Error: Cannot DUP from an empty stack on Line {instruction_pointer + 1}")
        exit()

def handle_rm(parts):
    global instruction_pointer
    if curstack and stacks[curstack]:
        stacks[curstack].pop()
    elif not curstack:
        print(f"Error: No stack selected for RM operation on Line {instruction_pointer + 1}")
        exit()
    else:
        print(f"Error: Stack "+curstack+" is empty on Line {instruction_pointer + 1}")
        exit()

def handle_step(parts):
    global instruction_pointer
    regstep()

def handle_pop(parts):
    global instruction_pointer
    if len(parts) == 2:
        reg = parts[1]
        if reg in registers:
            try:
                if curstack and stacks[curstack]:
                    registers[reg] = stacks[curstack].pop()
                elif not curstack:
                    print(f"Error: No stack selected for POP on Line {instruction_pointer + 1}")
                    exit()
                else:
                    print(f"Error: Stack "+curstack+" is empty for POP on Line {instruction_pointer + 1}")
                    exit()
            except IndexError:
                print(f"Error: Stack "+curstack+" is empty for POP on Line {instruction_pointer + 1}")
                exit()
        else:
            print(f"Error: Invalid register '{reg}' for POP on Line {instruction_pointer + 1}")
            exit()
    else:
        print(f"Error: Invalid POP syntax on Line {instruction_pointer + 1}")
        exit()

def handle_math(parts):
    global instruction_pointer, stacks, curstack
    if len(parts) == 5:
        op = parts[1].upper()
        dest = parts[2]
        arg1 = get_value(parts[3])
        arg2 = get_value(parts[4])

        if isinstance(arg1, (int, float)) and isinstance(arg2, (int, float)):
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
                    print(f"Error: Division by zero on Line {instruction_pointer + 1}")
                    exit()
            elif op == "MOD":
                result = arg1 % arg2
            elif op == "POW":
                result = arg1 ** arg2
            else:
                print(f"Error: Unknown math operation '{op}' on Line {instruction_pointer + 1}")
                exit()

            if dest == "&":
                if curstack:
                    stacks[curstack].append(result)
                else:
                    print(f"Error: No stack selected for '&' destination on Line {instruction_pointer + 1}")
                    exit()
            elif dest in registers:
                registers[dest] = result
            else:
                print(f"Error: Invalid destination '{dest}' on Line {instruction_pointer + 1}")
                exit()
        else:
            print(f"Error: MATH operations require numerical operands on Line {instruction_pointer + 1}")
            exit()
    else:
        print(f"Syntax Error: Invalid MATH syntax on Line {instruction_pointer + 1}")
        exit()

def handle_reg(parts):
    global instruction_pointer
    if len(parts) == 2:
        reg_name = parts[1]
        if reg_name not in registers:
            registers[reg_name] = None
    else:
        print(f"Syntax Error: Invalid REG syntax on Line {instruction_pointer + 1}")
        exit()

def handle_jump(parts):
    global instruction_pointer
    if len(parts) == 2:
        label_to_jump = parts[1]
        if label_to_jump in labels:
            instruction_pointer = labels[label_to_jump]
        else:
            print(f"Error: Undefined label '{label_to_jump}' on Line {instruction_pointer + 1}")
            exit()
    else:
        print(f"Syntax Error: Invalid JUMP syntax on Line {instruction_pointer + 1}")
        exit()

def handle_jumpgt(parts):
    global instruction_pointer, comparison_flags
    if len(parts) == 2:
        label_to_jump = parts[1]
        if label_to_jump in labels:
            if comparison_flags["greater"]:
                instruction_pointer = labels[label_to_jump]
        else:
            print(f"Error: Undefined label '{label_to_jump}' for JUMPGT on Line {instruction_pointer + 1}")
            exit()
    else:
        print(f"Syntax Error: Invalid JUMPGT syntax on Line {instruction_pointer + 1}")
        exit()

def handle_jumplt(parts):
    global instruction_pointer, comparison_flags
    if len(parts) == 2:
        label_to_jump = parts[1]
        if label_to_jump in labels:
            if comparison_flags["less"]:
                instruction_pointer = labels[label_to_jump]
        else:
            print(f"Error: Undefined label '{label_to_jump}' for JUMPLT on Line {instruction_pointer + 1}")
            exit()
    else:
        print(f"Syntax Error: Invalid JUMPLT syntax on Line {instruction_pointer + 1}")
        exit()

def handle_jumpneq(parts):
    global instruction_pointer, comparison_flags
    if len(parts) == 2:
        label_to_jump = parts[1]
        if label_to_jump in labels:
            if not comparison_flags["equal"]:
                instruction_pointer = labels[label_to_jump]
        else:
            print(f"Error: Undefined label '{label_to_jump}' for JUMPNEQ on Line {instruction_pointer + 1}")
            exit()
    else:
        print(f"Syntax Error: Invalid JUMPNEQ syntax on Line {instruction_pointer + 1}")
        exit()

def handle_jumpeq(parts):
    global instruction_pointer, comparison_flags
    if len(parts) == 2:
        label_to_jump = parts[1]
        if label_to_jump in labels:
            if comparison_flags["equal"]:
                instruction_pointer = labels[label_to_jump]
        else:
            print(f"Error: Undefined label '{label_to_jump}' for JUMPEQ on Line {instruction_pointer + 1}")
            exit()
    else:
        print(f"Syntax Error: Invalid JUMPEQ syntax on Line {instruction_pointer + 1}")
        exit()

def handle_cmp(parts):
    global instruction_pointer, comparison_flags
    if len(parts) == 3:
        operand1 = get_value(parts[1])
        operand2 = get_value(parts[2])

        if isinstance(operand1, (int, float)) and isinstance(operand2, (int, float)):
            comparison_flags["equal"] = (operand1 == operand2)
            comparison_flags["greater"] = (operand1 > operand2)
            comparison_flags["less"] = (operand1 < operand2)
        elif isinstance(operand1, str) and isinstance(operand2, str):
            comparison_flags["equal"] = (operand1 == operand2)
            comparison_flags["greater"] = (operand1 > operand2)
            comparison_flags["less"] = (operand1 < operand2)
        else:
            print(f"Error: CMP operands must be of the same type (number or string) on Line {instruction_pointer + 1}")
            exit()

    else:
        print(f"Syntax Error: Invalid CMP syntax on Line {instruction_pointer + 1}")
        exit()

def handle_point(parts):
    global instruction_pointer

def handle_in(parts):
    global instruction_pointer, registers
    if len(parts) > 0:
        prompt_parts = shlex.split(" ".join(parts[1:]))
        if prompt_parts:
            prompt_str = prompt_parts[0]
            try:
                prompt = eval(prompt_str)
                if not isinstance(prompt, str):
                    prompt = str(prompt)
                user_input = input(prompt)
                registers["IDA"] = user_input
            except (NameError, TypeError, SyntaxError):
                print(f"Error: Invalid prompt expression '{prompt_str}' for IN on Line {instruction_pointer + 1}")
                exit()
        else:
            user_input = input()
            registers["IDA"] = user_input
    else:
        print(f"Syntax Error: Invalid IN syntax. Expected a prompt after 'IN' on Line {instruction_pointer + 1}")
        exit()

def handle_concat(parts):
    global instruction_pointer, registers
    if len(parts) == 4:
        dest_reg = parts[1]
        val1 = get_value(parts[2])
        val2 = get_value(parts[3])

        str1 = str(val1)
        str2 = str(val2)

        if dest_reg in registers:
            registers[dest_reg] = str1 + str2
        else:
            print(f"Error: Invalid destination register '{dest_reg}' for CONCAT on Line {instruction_pointer + 1}")
            exit()
    else:
        print(f"Syntax Error: Invalid CONCAT syntax on Line {instruction_pointer + 1}")
        exit()

def handle_strlen(parts):
    global instruction_pointer, registers
    if len(parts) == 3:
        dest_reg = parts[1]
        string = get_value(parts[2])
        if dest_reg in registers and isinstance(string, str):
            registers[dest_reg] = len(string)
        elif dest_reg not in registers:
            print(f"Error: Invalid destination register '{dest_reg}' for STRLEN on Line {instruction_pointer + 1}")
            exit()
        else:
            print(f"Error: STRLEN operand must be a string on Line {instruction_pointer + 1}")
            exit()
    else:
        print(f"Syntax Error: Invalid STRLEN syntax on Line {instruction_pointer + 1}")
        exit()
def handle_strcmp(parts):
        global instruction_pointer, comparison_flags
        if len(parts) == 3:
          str1 = get_value(parts[1])
          str2 = get_value(parts[2])
          if isinstance(str1, str) and isinstance(str2, str):
            comparison_flags["equal"] = (str1 == str2)
            comparison_flags["greater"] = (str1 > str2)
            comparison_flags["less"] = (str1 < str2)
          else:
            print(f"Error: STRCMP operands must be strings on Line {instruction_pointer + 1}")
            exit()
        else:
          print(f"Syntax Error: Invalid STRCMP syntax on Line {instruction_pointer + 1}")
          exit()

labels_pass = {}
for line_num, line in enumerate(file):
    line = line.split(';')[0].strip()
    parts = shlex.split(line)
    if parts and parts[0] == "POINT":
        if len(parts) == 2:
            label_name = parts[1]
            if label_name in labels_pass:
                print(f"Error: Duplicate label '{label_name}' on Line {line_num + 1}")
                exit()
            labels_pass[label_name] = line_num

labels = labels_pass

instruction_handlers = {
    "NEW": handle_new,
    "PUSH": handle_push,
    "DUP": handle_dup,
    "DROP": handle_rm,
    "STEP": handle_step,
    "POP": handle_pop,
    "MATH": handle_math,
    "REG": handle_reg,
    "JUMP": handle_jump,
    "JUMPEQ": handle_jumpeq,
    "CMP": handle_cmp,
    "POINT": handle_point,
    "IN": handle_in,
    "CONCAT": handle_concat,
    "STRLEN": handle_strlen,
    "STRCMP": handle_strcmp,
    "JUMPGT": handle_jumpgt,
    "JUMPLT": handle_jumplt,
    "JUMPNEQ": handle_jumpneq,
    "SWAP": handle_swap,
    "PICK": handle_pick,
    "PPICK": handle_ppick,
    "CLEAR": handle_clear,
    "RROT": handle_rrot,
    "ROT": handle_rot,
    "DUMP": handle_dump,
    "OPS": handle_ops,
    "LOOP": handle_loop,
    "ENDLOOP": handle_endloop,
    "SUB": handle_sub,
    "ENDSUB": handle_endsub,
    "CALL": handle_call,
    "WAIT": handle_wait
}
instruction_pointer = 0
dump = ""

while instruction_pointer < len(file):
 try:
    curtime = time.perf_counter() - starttime
    line = file[instruction_pointer].split(';')[0].strip()
    parts = shlex.split(line)
    if parts:
        instruction = parts[0]
        if instruction in instruction_handlers:
            instruction_handlers[instruction](parts)
            if instruction != "SUB":
                instruction_pointer += 1
        elif line in stacks.keys():
            curstack = parts[0]
            instruction_pointer += 1
        elif not line:
            instruction_pointer += 1
        else:
            print(f"Syntax Error: Unknown instruction '{instruction}' on Line {instruction_pointer + 1}")
            exit()
    else:
        instruction_pointer += 1
    dump += f"{instruction} ARGS {parts[1:]}\n" + f"{instruction_pointer + 1} " + f"[{curtime:.4f}] "
 except KeyboardInterrupt:
    print("KeyboardInterrupt")
    if opt == True:
     handle_dump(["DUMP","LOGS"])
    exit()
