'''
 ___________
||         ||            _______
|| PHOENIX ||           | _____ |
|| IMAGING ||           ||_____||
||_________||           |  ___  |
|  + + + +  |           | |___| |
    _|_|_   \           |       |
   (_____)   \          |       |
              \    ___  |       |
       ______  \__/   \_|       |
      |   _  |      _/  |       |
      |  ( ) |     /    |_______|
      |___|__|    /         V:9.1.23
           \_____/
'''




import socket
import time
import datetime

from pycomm3 import LogixDriver

from plc_utils import write_plc_single, write_plc_check_pass, flush_check_pass
from plc_utils import read_plc_single, int_array_to_str,reset_plc_tags,write_plc_flush
import tag_lists
from pycomm3.tag import Tag
import tag_lists
import sys
import os
import json
import csv

with open(os.path.join(sys.path[0], 'config.json'), "r") as config_file:
    config_data = config_file.read()
    config_info = json.loads(config_data)
    
    
'''def handle_socket_errors(func):
    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            # Perform additional checks on the result
            keyence_prefix = str(result).split(",")
            keyence_prefix = keyence_prefix[0]
            if keyence_prefix == 'ER':
                    write_plc_single(plc, )
            # Add more checks as needed
            return result
        except socket.error as e:
            print(f"Socket error occurred: {str(e)}", f"Error occurred at function call {str(func)}")
            # Handle the error or raise it again if needed

    return wrapper'''




def keyence_string_generator(machine_num: str, PartT: int, results_dict: dict, sock: socket.socket, config_info: dict):
    try:
        scan_set = 'scan_names' + config_info['PartT_switch'][str(PartT)]
        keyence_string = config_info[scan_set][str(results_dict[config_info['tags']['PartProgram']][1])] + f'_{config_info["PartT_switch"][str(PartT)]}'
    except Exception as error:
        print(f'({machine_num}) Error Building Keyence String Check PartProgram and PartType', error)
        return 'ERROR-KeyenceString'
    return keyence_string

# used to ensure the correct Keyence program is loaded for the part being processed 
def keyence_swap_check(sock: socket.socket, machine_num: str, partType: int):
    try:
        scanSet = config_info["part_type_switch"][str(partType)]
        sock.sendall('PR\r\n'.encode())
        keyence_value = int(sock.recv(32).decode().split(',')[2].split('\\')[0][3])
        
        if keyence_value != partType:
            print(f'({machine_num}) Swapping Keyence program to: {partType}')
            sock.sendall(f'PW,1,{partType}\r\n'.encode())
            time.sleep(2)
    except KeyError as error:
        print(f'({machine_num}) INVALID PART_TYPE: {partType}\nError: {error}\n')
        return 0
    except Exception as error:
        print(f'({machine_num}) An error occurred during keyence_swap_check: {error}\n')



def trigger_keyence(sock: socket.socket, machine_num: str,plc:LogixDriver):
    def read_busy():
        sock.sendall(b'MR,%Busy\r\n')
        return sock.recv(32)
    def wait_for_busy(busy_value):
        while read_busy() != busy_value:
            time.sleep(0.2)
    def measure_execution_time(start_time, message):
        execution_time = (datetime.datetime.now() - start_time).total_seconds() * 1000
        if execution_time > 100:
            print(f'({machine_num}) {message} SLOW (over 100ms)! Took {execution_time} ms!!!')
    wait_for_busy(b'MR,+0000000000.000000\r')
    measure_execution_time(datetime.datetime.now(), 'TriggerKeyence (First Busy Pull)')
    trigger_start_time = datetime.datetime.now()
    sock.sendall(b'T1\r\n')
    sock.recv(32)
    measure_execution_time(trigger_start_time, 'TriggerKeyence (Sending T1)')
    wait_for_busy(b'MR,+0000000001.000000\r')
    print(f'({machine_num}) Scanning\n')
    measure_execution_time(trigger_start_time, 'TriggerKeyence (Final Busy Pull)')
    print(f'({machine_num}) Keyence Triggered!\n')
    write_plc_single(plc, machine_num, 'Busy', True)
# END 'TriggerKeyence'


#sends specific Keyence Program (branch) info to pre-load/prepare Keyence for Trigger(T1), also loads naming variables for result files
def load_keyence(sock:socket.socket, machine_num:str, partProgram:int, keyence_str:str,plc:LogixDriver):
    print(f'({machine_num}) LOADING : {keyence_str}\n')
    branch_info = f'MW,#PhoenixControlFaceBranch,{partProgram}\r\n' # keyence message
    stw_cmd = 'STW,0,"' + keyence_str + '\r\n' # keyence message sets image names for part
    result_cmd = f'OW,42,"{keyence_str}-Result\r\n' # keyence message specifies output unit
    #need sock.recv to clear keyence buffer
    # sending branch info
    sock.sendall(branch_info.encode()) 
    _ = sock.recv(32)
    sock.sendall(stw_cmd.encode())
    _ = sock.recv(32)
    sock.sendall(result_cmd.encode())
    _ = sock.recv(32)
    message = 'OW,43,"' + keyence_str + '-10Lar\r\n' # keyence message output unit
    sock.sendall(message.encode())
    _ = sock.recv(32)
    message = 'OW,44,"' + keyence_str + '-10Loc\r\n' # keyence message output unit
    sock.sendall(message.encode())
    _ = sock.recv(32)
    print(f'({machine_num}) LOADING KEYENCE COMPLETE\n') 
    write_plc_single(plc, machine_num, 'Ready', True)


    


def check_keyene_spec(sock:socket.socket, oldDict:dict):
    with open(os.path.join(sys.path[0], 'spec.json'), "r") as spec_file:
        spec_data = spec_file.read()
        spec_map = json.loads(spec_data)
            
        if spec_map == oldDict:
            return spec_map
        else:
            for i in spec_map.keys:
                keyence_branch = str(i)
                new_spec = str(spec_map[i])
                message = f'MW,#Branch1Spec,{new_spec}\r\n'
                sock.sendall(message.encode())
                _ = sock.recv(32)
        spec_file.close()
    return spec_map

# sends 'TE,0' then 'TE,1' to the Keyence, resetting to original state (ready for new 'T1')
#interrupts active scans on 'EndScan' from PLC
def exit_keyence(sock: socket.socket):
    commands = ['TE,0\r\n', 'TE,1\r\n']
    for command in commands:
        sock.sendall(command.encode())
        sock.recv(32)
    def read_busy():
        sock.sendall(b'MR,%Busy\r\n')
        return sock.recv(32)
    while read_busy() != b'MR,+0000000000.000000\r':
        time.sleep(0.2)
        read_busy()
# END 'ExtKeyence'



# reading PLC(EndScan) until it goes high to interrupt current Keyence scan
# This version uses a dictionary comprehension to initialize the current dictionary with the desired tags. 
# It then continuously checks the PLC tags' values until both conditions are met (either EndScan or Reset is True).
def monitor_end_scan(plc: LogixDriver, machine_num: str, sock: socket.socket):
    print(f'({machine_num}) Listening for PLC(END_SCAN) high')
    current = {tag: None for tag in ['EndScan', 'Reset']}
    while not all(tag_value[1] for tag_value in current.values()):
        current.update({tag: read_plc_single(plc, machine_num, tag) for tag in current})
        time.sleep(0.005)
    print(f'({machine_num}) End_Scan Signal Received - Scan Stopped')
    exit_keyence(sock)  # Interrupt Keyence scan
#END monitor_endScan

# function to monitor the Keyence tag 'KeyenceNotRunning', when True (+00001.00000) we know Keyence has completed result processing and FTP file write
def monitor_keyence_not_running(sock: socket.socket, machine_num: str,plc:LogixDriver):
    write_plc_single(plc, machine_num, 'Ready', False)
    msg = 'MR,#KeyenceNotRunning\r\n'
    def check_keyence_running():
        sock.sendall(msg.encode())
        return sock.recv(32)
    print(f'({machine_num}) Keyence Processing...')
    while check_keyence_running() != b'MR,+0000000001.000000\r':
        time.sleep(0.005)
    print(f'({machine_num}) Keyence Processing Complete!\n')
# END monitor_KeyenceNotRunning


# read defect information from the Keyence, then passes that as well as pass,fail,done to PLC, returns a list of result data for .txt file creation
def keyence_results_to_PLC(sock: socket.socket, plc: LogixDriver, machine_num: str)->list:
    # Define result messages and PLC tags
    result_mapping = {
        '#ReportDefectCount': 'Defect_Number',
        '#ReportLargestDefectSize': 'Defect_Size',
        '#ReportLargestDefectZoneNumber': 'Defect_Zone',
        '#ReportPass': 'Pass',
        '#ReportFail': 'Fail',
        '#ReportMaskFail': 'Mask_Fail',
        '#ReportSizeFail': 'Size_Fail',
        '#ReportSpacingFail': 'Spacing_Fail',
        '#ReportDensityFail': 'Density_Fail'
    }
    results = []
    # Read and store results, then write to PLC tags
    for msg, plc_tag in result_mapping.items():
        sock.sendall(f'MR,{msg}\r\n'.encode())
        data = sock.recv(32)
        keyence_value = int(str(data).split('+')[1])
        write_plc_single(plc, machine_num, plc_tag, keyence_value)
        results.append(keyence_value)

    # Set 'Done' tag to True
    write_plc_single(plc, machine_num, 'Done', True)

    # Print results
    print(f'({machine_num}) Keyence Results written to PLC!')
    print("===KEYENCE RESULTS ===")
    for msg, plc_tag in result_mapping.items():
        print(f'({machine_num}) {plc_tag}: {read_plc_single(plc, machine_num, plc_tag)[plc_tag][1]}')
    return results
# END keyenceResults_to_PLC


def check_keyence_error(machine_num:str, sock:socket.socket, plc:LogixDriver):
    errmsg = 'MR,%Error0Code\r\n'
    sock.sendall(errmsg.encode())
    data = sock.recv(32)
    n = str(data).split('.')
    m = n[0].split('+')
    o = int(m[1])
    data = o
    if(data < 16):
        # print(f'({machine_num}) Error Code:\n',data)
        write_plc_single(plc, machine_num, 'Faulted', True)
        write_plc_single(plc, machine_num, 'PhoenixFltCode', data)
    elif(data >= 16 and data < 48):
        # print(f'({machine_num}) Error Code:\n',data)
        write_plc_single(plc, machine_num, 'Faulted', True)
        write_plc_single(plc, machine_num, 'KeyenceFltCode', data)
    else:
        # print(f'({machine_num}) Error Code (non-crit):{data}\n')
        pass







def set_keyence_run_mode(machine_num:str, sock:socket.socket):
    msg = 'R0'
    sock.sendall(msg.encode())
    _ = sock.recv(32) #Clearing buffer
    print(f'({machine_num}) Keyence: Setting to Run Mode')

'''
8/4/2023 
Function to request pass/fail data for individual holes per inspection from keyence 
'''
def keyence_check_pass(machine_num: str, sock: socket.socket, plc: LogixDriver):
    keyence_commands = [f'MR,#Hole{i}\r\n' for i in range(1, 5)]
    check_pass_tags = {
        '3': 'Program:DU050CA02.CAM01.I.Check_Pass.',
        '4': 'Program:DU050CA03.CAM01.I.Check_Pass.',
        '5': 'Program:DU050CA03.CAM02.I.Check_Pass.'
    }

    for cmd, tag in zip(keyence_commands, check_pass_tags.get(machine_num, [])):
        sock.sendall(cmd.encode())
        data = sock.recv(32)
        keyence_value_raw = int(str(data).split('+')[1])
        write_plc_check_pass(plc, machine_num, f"{tag}{machine_num}", keyence_value_raw)
# END keyence_check_pass
    
def check_pass_flush(plc,machine_num):
    check_pass_tags = {
        '3':"Program:DU050CA02.CAM01.I.Check_Pass.",
        '4':"Program:DU050CA03.CAM01.I.Check_Pass.",
        '5':"Program:DU050CA03.CAM02.I.Check_Pass."
        }
    tags = []
    for i in range(1,5):
        tag_prefix = check_pass_tags[machine_num]
        full_tag_name =  f"{tag_prefix}{i}"
        tags.append(full_tag_name)
    for i in tags:
        flush_check_pass(plc,i)
def keyence_control_cont(sock:socket.socket, machine_num:str):
    keyence_command = 'MW,#PhoenixControlContinue,1\r\n'
    sock.sendall(keyence_command.encode())
    _ = sock.recv(32) #Clearing buffer
    print(f'({machine_num}) Sending the command "PhoenixControlContinue,1" to the Keyence controller.')

def reset_toEnd_cycle(plc:LogixDriver, machine_num:str):
    print(f'({machine_num}) PLC(END_PROGRAM) is high. Dropping PHOENIX(DONE) low\n')
    reset_plc_tags(plc, machine_num,'type_three')
    check_pass_flush(plc,machine_num) #Flush Check/Pass data before sending data to PLC again
    write_plc_flush(plc,machine_num) # defaults all .I Phoenix tags at start of cycle
    write_plc_single(plc, machine_num, 'Ready', True)
    
# import os 

# # path = f"C:\MiddleManPython\MMHousingDeployment\{i}-Aug-{j}-2023_py.log"


