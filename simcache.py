#!/usr/bin/python3

# Author: David Basin
# The purpose of the following program is to update a set of registers, including a pc, based
# on the given input machine code, and also to simulate how a cache (or two caches) are used
# when using memory

from collections import namedtuple
import re
import argparse

Constants = namedtuple("Constants",["NUM_REGS", "MEM_SIZE", "REG_SIZE"])
constants = Constants(NUM_REGS = 8, 
                      MEM_SIZE = 2**15,
                      REG_SIZE = 2**16)

# The following functions before the main are all used in the previous project, where I made
# sim.py. The only function that has been changed is the sw/lw function, named memImm; as well
# as two additional functions, print_cache_config and print_log_entry, which are given in the
# starter code by Professor Epstein

# The load_machine_code features code given by Professor Epstein in his starter code. It takes
# an E20 machine code file and loads it into the memory list, ignoring everything besides for
# the binary digits
def load_machine_code(machine_code, mem):
    machine_code_re = re.compile("^ram\[(\d+)\] = 16'b(\d+);.*$")
    expectedaddr = 0
    for line in machine_code:
        match = machine_code_re.match(line)
        if not match:
            raise Exception("Can't parse line: %s" % line)
        addr, instr = match.groups()
        addr = int(addr,10)
        instr = int(instr,2)
        if addr != expectedaddr:
            raise Exception("Memory addresses encountered out of sequence: %s" % addr)
        expectedaddr += 1
        mem[addr] = instr

# The threereg function deals with any machine code starting with "000" and thus instructions
# that deal with three registers. It returns the location that the pc will be at next
def threereg(pc, regs, instr):
    dstIndex = int(instr[9:12],2)
    srcA_Index = int(instr[3:6],2)
    srcB_Index = int(instr[6:9],2)
    if instr[-4:] == "0000": #add
        regs[dstIndex] = (regs[srcA_Index] + regs[srcB_Index]) % 2**16
    elif instr[-4:] == "0001": #sub
        regs[dstIndex] = (regs[srcA_Index] - regs[srcB_Index]) % 2**16
    elif instr[-4:] == "0010": #and
        regs[dstIndex] = regs[srcA_Index] & regs[srcB_Index]
    elif instr[-4:] == "0011": #or
        regs[dstIndex] = regs[srcA_Index] | regs[srcB_Index]
    elif instr[-4:] == "0100": #slt
        if regs[srcA_Index] < regs[srcB_Index]: regs[dstIndex] = 1
        else: regs[dstIndex] = 0
    elif instr[-4:] == "1000": #jr
        # returns the value inside the register, because that's the value pc will take next
        return regs[srcA_Index]
    return pc+1

# The tworegImm function deals with machine code that features two registers and an imm
# value, specifically slti and addi. It returns the location that the pc will be at next. 
def tworegImm(pc, regs, instr):
    dstIndex = int(instr[6:9],2)
    srcIndex = int(instr[3:6],2)
    imm = int(instr[10:],2)
    # If the MSB of the immediate is a 1, the immediate is actually negative
    if instr[9] == "1":
        imm -= 64
    if instr[:3] == "001": #slti
        if regs[srcIndex] < (imm % 2**16): regs[dstIndex] = 1
        else: regs[dstIndex] = 0
    elif instr[:3] == "111": #addi or movi
        regs[dstIndex] = (regs[srcIndex] + imm) % 2**16
    return pc+1

# The mem function deals with machine code that features two registers and an imm
# value and deals with memory location (sw and lw). It then returns pc+1 as the next pc.
def memImm(pc, regs, memory, instr):
    addrIndex = int(instr[3:6],2)
    imm = int(instr[10:],2)
    if instr[9] == "1":
        imm -= 64
    if instr[:3] == "100": #lw
        dstIndex = int(instr[6:9],2)
        regs[dstIndex] = memory[(regs[addrIndex]+imm)]
    elif instr[:3] == "101": #sw
        srcIndex = int(instr[6:9],2)
        memory[(regs[addrIndex]+imm)] = regs[srcIndex]
    # New in this project, I return a tuple of the pc and the memory address being looked at,
    # as I now need that memory address to deal with the cache
    return (pc+1,regs[addrIndex]+imm)

# The jeq function deals specifically with a jeq instruction. If it does jump, the function
# returns the immediate (pc+1+rel_imm), and pc+1 otherwise.
def jeq(pc, regs, instr):
    regA_Index = int(instr[3:6],2)
    regB_Index = int(instr[6:9],2)
    rel_imm = int(instr[10:],2)
    if instr[9] == "1":
        rel_imm -= 64
    if regs[regA_Index] == regs[regB_Index]:
        return pc+1+rel_imm
    else:
        return pc+1

# The j_or_jal function is called whenever there's a jump with a 13-bit immediate (thus,
# j or jal). If the pc is equal to the immediate, then we will set Halt to true in the
# return statement, indicating for the program to stop. The immediate value will be returned
# as the next pc location
def j_or_jal(pc, regs, instr):
    if instr[:3] == "011":
        regs[7] = pc+1
    imm = int(instr[3:],2)
    if pc == imm: return (imm,True)
    else: return (imm, False)

# This function takes in details about a cache (which cache - L1 or L2, it's size, blocksize,
# associativity, and # of lines in the cache), and prints out the info in an organized way
def print_cache_config(cache_name, size, assoc, blocksize, num_lines):
    summary = "Cache %s has size %s, associativity %s, " \
        "blocksize %s, lines %s" % (cache_name,
        size, assoc, blocksize, num_lines)
    print(summary)

# This function takes in details about the current status of the memory address being dealt
# with and where it will go in the cache (which cache, which access type - hit, miss, or sw,
# the program counter, memory address, and cache line number), and prints out the info
def print_log_entry(cache_name, status, pc, addr, line):
    log_entry = "{event:8s} pc:{pc:5d}\taddr:{addr:5d}\t" \
        "line:{line:4d}".format(line=line, pc=pc, addr=addr,
            event = cache_name + " " + status)
    print(log_entry)

def main():
    parser = argparse.ArgumentParser(description='Simulate E20 machine')
    parser.add_argument('filename', help=
        'The file containing machine code, typically with .bin suffix')
    parser.add_argument('--cache', help=
        'Cache configuration: size,associativity,blocksize (for one cache) '
        'or size,associativity,blocksize,size,associativity,blocksize (for two caches)')
    cmdline = parser.parse_args()

    # initialize system
    pc = 0
    regs = [0] * constants.NUM_REGS
    memory = [0] * constants.MEM_SIZE

    # load program into memory
    with open(cmdline.filename) as file:
        load_machine_code(file.readlines(), memory)

    # The cache part of the command line will take either 3 or 6 variables
    if cmdline.cache is not None:
        parts = cmdline.cache.split(",")
        if len(parts) == 3:
            [L1size, L1assoc, L1blocksize] = [int(x) for x in parts]
            twocache = False;
            numlines_1 = L1size//(L1assoc*L1blocksize)
            # The assoc_list will store the mem blocks values for a certain line;
            # If the associativity is > 1, then a line will have more than 1 slot
            # The tuple is there so that the first value is the tag, while the 2nd
            # value will keep track of the LRU
            L1_assoc_list = [(-1,-1)]*L1assoc
            # Then, the list itself will have num_lines assoc. arrays in it
            L1 = []
            for i in range(numlines_1): L1.append(L1_assoc_list.copy())
        # If there's 6 inputs, then there will be two caches, L1 and L2
        elif len(parts) == 6:
            [L1size, L1assoc, L1blocksize, L2size, L2assoc, L2blocksize] = \
                [int(x) for x in parts]
            twocache = True;
            numlines_1 = L1size//(L1assoc*L1blocksize)
            # I do the same thing here as before, but now with two caches
            L1_assoc_list = [(-1,-1)]*L1assoc
            L1 = []
            for i in range(numlines_1): L1.append(L1_assoc_list.copy())
            numlines_2 = L2size//(L2assoc*L2blocksize)
            L2_assoc_list = [(-1,-1)]*L2assoc
            L2 = []
            for i in range(numlines_2): L2.append(L2_assoc_list.copy())
        else:
            raise Exception("Invalid cache config")

    # Here, I print the cache configuration (general info for L1 and maybe L2)
    print_cache_config("L1", L1size, L1assoc, L1blocksize, numlines_1)
    if twocache: print_cache_config("L2", L2size, L2assoc, L2blocksize, numlines_2)
    
    # set halt to False to indicate the program shouldn't stop
    halt = False;
    # while the program isn't halted, we turn the instruction in the memory to a
    # 16-bit string, and check the first 3 or 2 characters in order to determine
    # which instruction function should be called
    while not halt:
        instr = bin(memory[pc])[2:].zfill(16)
        if instr[:3] == "000": pc = threereg(pc,regs,instr)
        elif instr[:3] in {"001","111"}: pc = tworegImm(pc,regs,instr)
        elif instr[:2] == "10":
            tup = memImm(pc,regs,memory,instr)
            mem_val = tup[1]
            L1_status = "SW"
            L1_block_number = mem_val//L1blocksize
            L1_line = L1_block_number % numlines_1
            L1_tag = L1_block_number//numlines_1
            done_with_mem = False;
            # In this loop I search whether the mem block being looked at is already
            # in L1, or if there are any empty L1 array slots at L1_line
            for i in range(L1assoc):
                # If the tag is found in the line, then it stays there but the second
                # part of the tuple is given the minimum value of 0, indicating that
                # it's the most recently used space. If it's LW, then it's a HIT
                if L1[L1_line][i][0] == L1_tag:
                    L1[L1_line][i] = (L1_tag,0)
                    # All the second values in the tuple are updated to 1 higher as they
                    # are now 1 clock time less recently used
                    for j in range(L1assoc):
                        order_tup = L1[L1_line][j]
                        L1[L1_line][j] = (order_tup[0],order_tup[1]+1)
                    done_with_mem = True;
                    if instr[2] == "0": L1_status = "HIT"
                    break
                # If the tag is still uninitialized, it means that this tag isn't in the
                # array but there's an empty space availbale for it; for LWs, it's MISS
                elif L1[L1_line][i][0] == -1: 
                    L1[L1_line][i] = (L1_tag, 0)
                    # Again, the second value in the tuple for the rest of the line is 
                    # updated to be 1 higher to reflect one more clock cycle passed
                    for j in range(i+1):
                        order_tup = L1[L1_line][j]
                        L1[L1_line][j] = (order_tup[0],order_tup[1]+1)
                    done_with_mem = True;
                    if instr[2] == "0": L1_status = "MISS"
                    break
            # If it's neither a "hit" nor are there any open slots in a line, the line has
            # to replace the LRU value; again, for LW, this is a MISS
            if not done_with_mem:
                if instr[2] == "0": L1_status = "MISS"
                maxi = -1
                # The index in the line with the greatest second value in the tuple will
                # be the LRU and thus replaced. This for loop looks for that index
                for i in range(L1assoc):
                    if L1[L1_line][i][1] > maxi:
                        maxi = L1[L1_line][i][1]
                        maxi_index = i
                # Once found, that tag is evicted and replaced with the new mem value
                L1[L1_line][maxi_index] = (L1_tag,0)
                # Again, the second value in the rest of the list is updated too
                for i in range(L1assoc):
                    order_tup = L1[L1_line][i]
                    L1[L1_line][i] = (order_tup[0],order_tup[1]+1)
            # Finally, the entry is printed with the given information
            print_log_entry("L1", L1_status, pc, mem_val, L1_line)
            # If there are two caches, and it's either an SW or an L1 Miss, we update L2
            # The process below is the exact same as with the first cache, except now
            # being done to L2
            if twocache and L1_status != "HIT":
                L2_status = "SW"
                L2_block_number = mem_val//L2blocksize
                L2_line = L2_block_number % numlines_2
                L2_tag = L2_block_number//numlines_2
                done_with_mem = False;
                for i in range(L2assoc):
                    if L2[L2_line][i][0] == L2_tag:
                        L2[L2_line][i] = (L2_tag,0)
                        for j in range(L2assoc):
                            order_tup = L2[L2_line][j]
                            L2[L2_line][j] = (order_tup[0],order_tup[1]+1)
                        done_with_mem = True;
                        if instr[2] == "0": L2_status = "HIT"
                        break
                    elif L2[L2_line][i][0] == -1: 
                        L2[L2_line][i] = (L2_tag, 0)
                        for j in range(i+1):
                            order_tup = L2[L2_line][j]
                            L2[L2_line][j] = (order_tup[0],order_tup[1]+1)
                        done_with_mem = True;
                        if instr[2] == "0": L2_status = "MISS"
                        break
                if not done_with_mem:
                    if instr[2] == "0": L2_status = "MISS"
                    maxi = -1
                    for i in range(L2assoc):
                        if L2[L2_line][i][1] > maxi:
                            maxi = L2[L2_line][i][1]
                            maxi_index = i
                    L2[L2_line][maxi_index] = (L2_tag,0)
                    for i in range(L2assoc):
                        order_tup = L2[L2_line][i]
                        L2[L2_line][i] = (order_tup[0],order_tup[1]+1) 
                print_log_entry("L2", L2_status, pc, mem_val, L2_line)
            # Finally, after the cache/s is/are updated, it moves on to the next pc loc.    
            pc = tup[0]
        elif instr[:3] == "110": pc = jeq(pc,regs,instr)
        # If a jump is detected, we recheck whether the program should be halted or not
        elif instr[:2] == "01":
            result = j_or_jal(pc,regs,instr)
            if result[1]: halt = True
            else:
                pc = result[0]



if __name__ == "__main__":
    main()
