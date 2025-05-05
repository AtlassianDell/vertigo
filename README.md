#   Vertigo

##   Version 1 Documentation

##   Overview

Vertigo is a stack-based scripting language designed for data manipulation and control flow. It operates primarily using stacks for data storage and retrieval. Instructions manipulate these stacks and the program's state. 

##   Core Concepts

###   Stacks

Vertigo utilizes multiple named stacks. Data is pushed onto and popped from these stacks. The currently active stack is selected using its name as an instruction. 

###   Registers

The language includes a set of registers for storing single values. These registers can be used for intermediate calculations or storing input/output data. The initial registers are `ODA` (Output Data Accumulator) and `IDA` (Input Data Accumulator). New registers can be declared dynamically. 

###   Instruction Pointer

The `instruction_pointer` tracks the current line number being executed in the script. Control flow instructions modify this pointer. 

###   Comparison Flags

A set of flags (`equal`, `greater`, `less`) are set as a result of `CMP` and `STRCMP` instructions. Conditional jump instructions use these flags to determine the flow of execution. 

###   Labels

Labels are markers within the code, defined using the `POINT` instruction. They serve as targets for jump instructions. 

##   Instructions

Each line in a Vertigo script typically contains a single instruction followed by its arguments. Instructions are case-insensitive. 

###   Stack Manipulation

* **`NEW <stack_name>`**: Creates a new empty stack with the specified `<stack_name>`. 
* **`<stack_name>`**: Selecting a stack by its name makes it the currently active stack for subsequent `PUSH`, `POP`, `DUP`, and `RM` operations. 
* **`PUSH <value>`**: Pushes the specified `<value>` onto the currently active stack. `<value>` can be a number, a string literal (enclosed in double quotes), or the name of a register. String literals are pushed without the surrounding quotes. 
    If `<value>` can be evaluated as a Python literal (e.g., `True`, `False`, `None`), it will be pushed as that type; otherwise, it's treated as a string.
* **`POP <register>`**: Pops the top value from the currently active stack and stores it in the specified `<register>`. An error occurs if no stack is selected or if the stack is empty. 
* **`DUP`**: Duplicates the top value on the currently active stack. An error occurs if no stack is selected or if the stack is empty. 
* **`RM`**: Removes the top value from the currently active stack. An error occurs if no stack is selected or if the stack is empty. 
* **`SWAP`**: Swaps the top two items on the currently active stack.
* **`PICK <n>`**: Copies the nth item from the top of the stack to the top (0-based index).
* **`PPICK <n>`**: Moves the nth item from the top of the stack to the top (0-based index).
* **`CLEAR`**: Removes all items from the currently active stack.
* **`RROT`**: Rotates the top three items on the stack to the right.
* **`ROT`**: Rotates the top three items on the stack to the left.
* **`DUMP`**: Prints the entire current stack to the console (for debugging). If used without arguments, prints all stacks.

###   Register Operations

* **`REG <register_name>`**: Declares a new register with the specified `<register_name>` and initializes its value to `None`. If the register already exists, this instruction has no effect. 

###   Input/Output

* **`STEP`**: Prints the value currently stored in the `ODA` register to the console. If `ODA` is `None`, nothing is printed. After printing, `ODA` is set back to `None`. 
* **`IN ["<prompt>"]`**: Reads input from the user. If an optional `<prompt>` string (enclosed in double quotes) is provided, it is displayed to the user before reading input. The user's input is stored as a string in the `IDA` register. 

###   Math Operations

* **`MATH <operation> <destination_register> <operand1> <operand2>`**: Performs a mathematical `<operation>` on `<operand1>` and `<operand2>` and stores the result in the `<destination_register>`. 
    * `<operation>` can be `ADD`, `MINUS`, `MUL`, `DIV`, `MOD`, or `POW`. 
    * `<destination_register>` must be a valid register name. 
    * `<operand1>` and `<operand2>` can be numbers or register names containing numbers. If register names are used, their values are retrieved. 
    * An error occurs if the operands are not numbers or if division by zero is attempted. 
* **`OPS <operation> <destination> <argument1> <argument2> [...]`**: Performs a logical or comparison `<operation>` and stores the result.
    * `<operation>` can be `AND`, `OR`, `NOT`, `EQUAL`, `NEQUAL`.
    * `<destination>` can be a register or `@` to push to the current stack.
    * `<argument1>`, `<argument2>`, etc., are the arguments for the operation.

###   String Operations

* **`CONCAT <destination_register> <string1> <string2>`**: Concatenates `<string1>` and `<string2>` and stores the result in the `<destination_register>`. 
    * `<string1>` and `<string2>` can be string literals (in double quotes) or register names containing strings. 
* **`STRLEN <destination_register> <string>`**: Gets the length of the `<string>` and stores the integer result in the `<destination_register>`. 
    * `<string>` can be a string literal (in double quotes) or a register name containing a string. 
* **`STRCMP <string1> <string2>`**: Compares `<string1>` and `<string2>` lexicographically. The comparison flags (`equal`, `greater`, `less`) are set based on the result. 
    * `<string1>` and `<string2>` can be string literals (in double quotes) or register names containing strings. 

###   Control Flow

* **`POINT <label_name>`**: Defines a label at the current line. `<label_name>` can be any alphanumeric string. Labels must be unique within a script. 
* **`JUMP <label_name>`**: Unconditionally jumps the execution to the line marked by the specified `<label_name>`. An error occurs if the label is not defined. 
* **`JUMPEQ <label_name>`**: Jumps to the line marked by `<label_name>` if the `equal` comparison flag is `True`. Otherwise, execution continues to the next line. An error occurs if the label is not defined. 
* **`JUMPGT <label_name>`**: Jumps to the line marked by `<label_name>` if the `greater` comparison flag is `True`. Otherwise, execution continues to the next line. An error occurs if the label is not defined. 
* **`JUMPLT <label_name>`**: Jumps to the line marked by `<label_name>` if the `less` comparison flag is `True`. Otherwise, execution continues to the next line. An error occurs if the label is not defined. 
* **`JUMPNEQ <label_name>`**: Jumps to the line marked by `<label_name>` if the `equal` comparison flag is `False`. Otherwise, execution continues to the next line. An error occurs if the label is not defined. 
* **`CMP <operand1> <operand2>`**: Compares `<operand1>` and `<operand2>`. The comparison flags (`equal`, `greater`, `less`) are set based on the result. Operands can be numbers or register names containing numbers. If the operands are strings, they are compared lexicographically. An error occurs if the operands are of different types (unless one is a number and the other can be evaluated as such). 
* **`SUB <subroutine_name>`**: Defines a subroutine with the specified `<subroutine_name>`.
* **`ENDSUB`**: Marks the end of a subroutine definition.
* **`CALL <subroutine_name>`**: Calls the subroutine with the specified `<subroutine_name>`.
* **`LOOP`**: Starts a loop block. The loop continues as long as the `CLI` register is less than or equal to the `LTM` register.
* **`ENDLOOP`**: Marks the end of a loop block.

###   Comments

Lines starting with a semicolon (`;`) are treated as comments and are ignored by the interpreter. Comments can appear on their own line or after an instruction. 

##   Program Structure

A Vertigo program consists of a sequence of instructions, one per line. The interpreter executes the instructions sequentially from the first line to the last, unless a jump instruction alters the control flow. 

##   Error Handling

The Vertigo interpreter performs basic error checking, such as:

* Syntax errors in instructions. 
* Undefined stack or register names. 
* Operating on empty stacks. 
* Type errors in math and string operations. 
* Division by zero. 
* Undefined labels for jump instructions. 
* Duplicate label definitions. 

When an error occurs, the interpreter prints an error message to the console indicating the type of error and the line number where it occurred, and then terminates execution. 

##   Example

```
NEW my_stack      ; Create a new stack
named my_stack
my_stack          ; Select the my_stack
REG result        ; Create register result
PUSH 10           ; Push the number 10
onto my_stack
PUSH 5            ; Push the number 5
onto my_stack
MATH MINUS result 10 5 ; Subtract 5 from 10 and store in register "result"
```
