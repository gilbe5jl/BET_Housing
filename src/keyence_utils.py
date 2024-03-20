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
from time import sleep
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
from colorama import Fore, Style
import logging
from datetime import timedelta,time
from datetime import datetime 
from slp_utils import sleep_time


with open(os.path.join(sys.path[0], 'config.json'), "r") as config_file:
    config_data = config_file.read()
    config_info = json.loads(config_data)


def configure_logger(logger_name,log_file_name,machine_num):
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)
    handler = logging.FileHandler(log_file_name)
    now = datetime.now().strftime("%I:%M:%S")
    formatter = logging.Formatter(f"{now}-ROBOT({machine_num})-%(levelname)s-\n%(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.propagate = False
    return logger
today = datetime.now().strftime("%a-%b-%d-%Y")
log_file_3 = f"ROBOT(3)_{today}.log"
log_file_4 = f"ROBOT(4)_{today}.log"
log_file_5 = f"ROBOT(5)_{today}.log"
logger_r3 = configure_logger("Logger_r3",log_file_3,3)
logger_r4 = configure_logger("Logger_r4",log_file_4,4)
logger_r5 = configure_logger("Logger_r5",log_file_5,5)




def extract_machine_num(message):
    # Find the opening parenthesis and closing parenthesis in the message
    start_index = message.find('(')
    end_index = message.find(')')
    # Check if both parentheses are found
    if start_index != -1 and end_index != -1:
        # Extract the substring between the parentheses
        machine_num_str = message[start_index + 1:end_index]
        
        try:
            # Attempt to convert the extracted substring to an integer
            machine_num = int(machine_num_str)
            return machine_num
        except ValueError:
            # Handle the case where the substring cannot be converted to an integer
            return None
    return None  # Return None if the parentheses are not found
def print_color(message:str)->None:
    machine_num = str(extract_machine_num(message))
    if machine_num == '3':
        print_green(message)
        logger_r3.info(message)
    elif machine_num == '4':
        print_blue(message)
        logger_r4.info(message)
    elif machine_num == '5':
        print_yellow(message)
        logger_r5.info(message)


def print_green(message:str)->None:
    # logger_r3.info(message)
    print(Fore.GREEN + f"{message}\n" + Style.RESET_ALL)
def print_blue(message:str)->None:
    # logger_r4.info(message)
    print(Fore.BLUE + f"{message}" + Style.RESET_ALL)
def print_yellow(message:str)->None:
    # logger_r5.info(message)
    print(Fore.YELLOW + f"{message}" + Style.RESET_ALL)
def print_red(message:str)->None:
    print(Fore.RED + f"[{datetime.now()}]{message}" + Style.RESET_ALL)    
    
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




def keyence_string_generator(machine_num: str, part_type: int, results_dict: dict, sock: socket.socket, config_info: dict,part_program):
    try:
        # print_color(f"({machine_num}) PART TYPE: {PartT}")
        # print_color(f"({machine_num}) RESULTS: {results_dict}")
        # for i,j in zip(results_dict.keys(), results_dict.values()):
        #     print_color(f"({machine_num}) KEY: {i},\n\tVALUE:{j}")
        scan_set = 'scan_names' + config_info['part_type_switch'][str(part_type)]
        # keyence_string = config_info[scan_set][str(results_dict[config_info['tags']['PartProgram']][1])] + f'_{config_info["part_type_switch"][str(PartT)]}'
        keyence_string = config_info[scan_set][str(part_program)] + f'_{config_info["part_type_switch"][str(part_type)]}'

        # print_color(f"Keyence String:{keyence_string}")
    except Exception as error:
        print_color(f'({machine_num}) Error building Keyence String: Incorrect PART_PROGRAM({part_program}) or PART_TYPE({part_type})...\nError:{error}')
        return 'ERROR'
    return keyence_string

# used to ensure the correct Keyence program is loaded for the part being processed 
def keyence_swap_check(sock: socket.socket, machine_num: str, part_type: int):
    # print_color(f'({machine_num}) Checking if Keyence has [part_type= {part_type}] Loaded...')
    try:
        scan_set = config_info["part_type_switch"][str(part_type)]
        def read_keynce_value():
            sock.sendall('PR\r\n'.encode())
            keyence_value = int(sock.recv(32).decode().split(',')[2].split('\\')[0][3])
            return keyence_value
        def wait_for_correct_part_type_loaded_into_keyence():
            while read_keynce_value() != part_type:
                # print_color(f'({machine_num}) Swapping Keyence program to: {part_type}...')
                sock.sendall(f'PW,1,{part_type}\r\n'.encode())
                # time.sleep(0.2)
                sleep_time(0.2)
        try:
            wait_for_correct_part_type_loaded_into_keyence()
        except TimeoutError as Error:
            print_color(f'CRITICAL -- Keyence Communication Error -- PLEASE RESTART PYTHON\n{Error}')
    except KeyError as error:
        print_color(f'({machine_num}) INVALID PART TYPE: {part_type}\nError during Keyence Swap Check:{error}\n')
        return 0
    except Exception as error:
        print_color(f'({machine_num}) An error occurred during Keyence Swap Check: {error}\n')



def trigger_keyence(sock: socket.socket, machine_num: str,plc:LogixDriver):
    def read_busy():
        sock.sendall(b'MR,%Trg1Ready\r\n')
        return sock.recv(32)
    def wait_for_busy(busy_value):
        while read_busy() != busy_value:
            print_color(f'({machine_num})[STAGE:1] KEYENCE WAITING FOR BUSY SIGNAL...\n')
            # time.sleep(0.2)
            sleep_time(0.02)
    def measure_execution_time(start_time):
        execution_time = (datetime.now() - start_time).total_seconds() * 1000
        if execution_time > 100:
            print_color(f'({machine_num}) Keyence Trigger Delayed (Over 100ms)! Execution Time: {execution_time} ms\n')
    #wait_for_busy(b'MR,+0000000000.000000\r')
    #measure_execution_time(datetime.now())
    trigger_start_time = datetime.now()
    print_color(f'({machine_num}) KEYENCE TRIGGERED AT [{trigger_start_time}]\n')
    try:
        sock.sendall(b'T1\r\n')
        sock.recv(32)
        wait_for_busy(b'MR,+0000000000.000000\r')
        write_plc_single(plc, machine_num, 'Busy', True)
    except Exception as error:
        print_color(f'({machine_num}) Error during Keyence Trigger: {error}\n')
    print_color(f'({machine_num})[STAGE:1] KEYENCE TRIGGERED...\n')
    print_color(f'({machine_num})[STAGE:1] KEYENCE SCANNING...\n')
    measure_execution_time(trigger_start_time)
    #wait_for_busy(b'MR,+0000000000.000000\r')
    measure_execution_time(trigger_start_time)
    #write_plc_single(plc, machine_num, 'Busy', True)
# END 'TriggerKeyence'


#sends specific Keyence Program (branch) info to pre-load/prepare Keyence for Trigger(T1), also loads naming variables for result files
def load_keyence(sock:socket.socket, machine_num:str, partProgram:int, keyence_str:str,plc:LogixDriver):
    # monitor_end_scan(plc, machine_num, sock)
    # time.sleep(1)
    branch_info = f'MW,#PhoenixControlFaceBranch,{partProgram}\r\n' # keyence message
    stw_cmd = 'STW,0,"' + keyence_str + '\r\n' # keyence message sets image names for part
    result_cmd = f'OW,42,"{keyence_str}-Result\r\n' # keyence message specifies output unit
    #need sock.recv to clear keyence buffer
    # sending branch info
    sock.sendall(branch_info.encode()) 
    sock.recv(32)
    sock.sendall(stw_cmd.encode())
    sock.recv(32)
    # try:
    sock.sendall(result_cmd.encode())
    # keyence_response = sock.recv(1024)
    # print_color(f"KEYENCE Response OW,42: {keyence_response}")
    sock.recv(32)
    # except TimeoutError as error:
        # pass
    message = 'OW,43,"' + keyence_str + '-10ZPos\r\n' # keyence message output unit
    sock.sendall(message.encode())
    # keyence_response = sock.recv(1024)
    # print_color(f"KEYENCE Response OW,43: {keyence_response}")

    sock.recv(32)
    message = 'OW,44,"' + keyence_str + '-10Loc\r\n' # keyence message output unit
    sock.sendall(message.encode())
    # keyence_response = sock.recv(1024)
    # print_color(f"KEYENCE Response OW,43: {keyence_response}")
    sock.recv(32)
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
def exit_keyence(sock: socket.socket,machine_num:str):
    commands = ['TE,0\r\n', 'TE,1\r\n']
    for command in commands:
        sock.sendall(command.encode())
        sock.recv(32)
    def read_busy():
        sock.sendall(b'MR,%Busy\r\n')
        return sock.recv(32)
    while read_busy() != b'MR,+0000000000.000000\r':
        # time.sleep(0.2)
        sleep_time(0.2)
        read_busy()
# END 'ExtKeyence'



# reading PLC(EndScan) until it goes high to interrupt current Keyence scan
# This version uses a dictionary comprehension to initialize the current dictionary with the desired tags. 
# It then continuously checks the PLC tags' values until both conditions are met (either EndScan or Reset is True).
def monitor_end_scan(plc: LogixDriver, machine_num: str, sock: socket.socket):
    # print_color(f'({machine_num})[STAGE:1] WAITING for PLC(END_SCAN)')
    # current = {tag: None for tag in ['EndScan', 'Reset']}
    # while not all(tag_value[1] for tag_value in current.values()):
    #     current.update({tag: read_plc_single(plc, machine_num, tag) for tag in current})
    #     time.sleep(0.005)
    current = read_plc_single(plc,machine_num,'EndScan')
    current.update(read_plc_single(plc,machine_num,'Reset'))
    while((current[config_info['tags']['EndScan']][1] == False) and (current[config_info['tags']['Reset']][1]== False)):
        current = read_plc_single(plc,machine_num,'EndScan')
        current.update(read_plc_single(plc,machine_num,'Reset'))
        # time.sleep(.005)
        sleep_time(.005)
    print_color(f'({machine_num})[STAGE:1] PLC(END_SCAN) Received - KEYENCE Scan Terminated...\n')
    exit_keyence(sock,machine_num)  # Interrupt Keyence scan
#END monitor_endScan

# function to monitor the Keyence tag 'KeyenceNotRunning', when True (+00001.00000) we know Keyence has completed result processing and FTP file write
def monitor_keyence_not_running(sock: socket.socket, machine_num: str,plc:LogixDriver):
    # print_color(f'({machine_num})[STAGE:1] KEYENCE performing result processing & FTP file write...\n')
    write_plc_single(plc, machine_num, 'Ready', False)
    msg = 'MR,#KeyenceNotRunning\r\n'
    def check_keyence_running():
        sock.sendall(msg.encode())
        return sock.recv(32)
    while check_keyence_running() != b'MR,+0000000001.000000\r':
        print_color(f'({machine_num})[STAGE:1] KEYENCE Processing...\n')
        # time.sleep(0.005)
        sleep_time(0.005)
    print_color(f'({machine_num})[STAGE:1] KEYENCE Processing Complete...\n')
# END monitor_KeyenceNotRunning


# read defect information from the Keyence, then passes that as well as pass,fail,done to PLC, returns a list of result data for .txt file creation
# def keyence_results_to_PLC(sock: socket.socket, plc: LogixDriver, machine_num: str)->list:
#     print(f'({machine_num}) SENDING RESULTS TO PLC...\n')
#     # Define result messages and PLC tags
#     result_mapping = {
#         '#ReportDefectCount': 'DefectNumber',
#         '#ReportLargestDefectSize': 'DefectSize',
#         '#ReportLargestDefectZoneNumber': 'DefectZone',
#         '#ReportPass': 'Pass',
#         '#ReportFail': 'Fail',
#         '#ReportMaskFail': 'MaskFail',
#         '#ReportSizeFail': 'SizeFail',
#         '#ReportSpacingFail': 'SpacingFail',
#         '#ReportDensityFail': 'DensityFail'
#     }
#     results = []
#     # Read and store results, then write to PLC tags

#     for msg, plc_tag in result_mapping.items():
#         encode_message = f"MR,{msg}\r\n".encode()
#         sock.sendall(encode_message)
#         data = sock.recv(32)
#         n = str(data).split('.')
#         m = n[0].split('+')
#         o = int(m[1])
#         data = int(o)
#         write_plc_single(plc, machine_num, plc_tag, data)
#         results.append(data)

#     # Set 'Done' tag to True

#     # Print results
#     print(f"({machine_num})KEYENCE RESULTS:")
#     for msg, plc_tag in result_mapping.items():
#         print(f'\t({machine_num}) {plc_tag}: {read_plc_single(plc, machine_num, plc_tag)[plc_tag][1]}')
#     write_plc_single(plc, machine_num, 'Done', True)
#     return results
# # END keyenceResults_to_PLC

def keyence_results_to_PLC(sock:socket.socket, plc:LogixDriver, machine_num:str):
    #read results from Keyence then pass to proper tags on PLC
    result_messages = ['MR,#ReportDefectCount\r\n', 'MR,#ReportLargestDefectSize\r\n', 'MR,#ReportLargestDefectZoneNumber\r\n', 'MR,#ReportPass\r\n', 'MR,#ReportFail\r\n',
                        'MR,#ReportMaskFail\r\n', 'MR,#ReportSizeFail\r\n', 'MR,#ReportSpacingFail\r\n', 'MR,#ReportDensityFail\r\n','MR,#Zpoint1_Pass\r\n','MR,#Zpoint2_Pass\r\n']
    # 'MR,#Z1_pass\r\n','MR,#Z2_pass\r\n'
    results = []

    # sending result messages to Keyence, then cleaning results to 'human-readable' list
    for msg in result_messages:
        sock.sendall(msg.encode())
        data = sock.recv(32)
        keyence_value_raw = str(data).split('.') # ["b'MR,-0000","8878\\r"]
        keyence_value_raw = keyence_value_raw[0].split('+')
        keyence_value = int(keyence_value_raw[1])
        results.append(keyence_value)

        # # print(keyence_value_raw)
        # if '+' in keyence_value_raw[0]:
        #     if msg == 'MR,#CurrentPoint1_Z\r\n' or msg == 'MR,#CurrentPoint2_Z\r\n':
        #         positive_decimal = int(keyence_value_raw[1])
        #         if positive_decimal >= 0:
        #             keyence_value = f"{keyence_value}.{positive_decimal}"
        # elif '-' in keyence_value_raw[0]:
        #     keyence_value_raw = keyence_value_raw[0].split('-') #b'MR,-0000000002.814430\r'
        #     print_color(f"({machine_num})[STAGE:1] KEYENCE Results byte string Z-POINT[]:({data})")
        #     keyence_value = round(float(keyence_z_point_data),4)
        #     # keyence_value = f"-{keyence_value[0]}.{decimal}"
        #     print_color(f"({machine_num})[STAGE:1] KEYENCE Results float Z-POINT[]:({keyence_value})")
        #     # print_color(f"Z_POINT:({keyence_value})")
    z_point_cmds = ['MR,#CurrentPoint1_Z\r\n','MR,#CurrentPoint2_Z\r\n']
    for msg in z_point_cmds:
        sock.sendall(msg.encode())
        data = sock.recv(32)
        keyence_value_raw = str(data).split('.') # ["b'MR,-0000","8878\\r"]
        get_keyence_whole_num = keyence_value_raw[0].split(',') #["b'MR","-000"]
        get_keyence_fractional_num = keyence_value_raw[1].split('\\') #["8878","\\r"]
        keyence_whole_num = get_keyence_whole_num[1]
        keyence_fractional_num = get_keyence_fractional_num[0]
        keyence_z_point_data = f"{keyence_whole_num}.{keyence_fractional_num}"
        if '-' in keyence_z_point_data:
            keyence_z_point_data = keyence_z_point_data.split('-')
            keyence_z_point_data = round(float(keyence_z_point_data[1]),4)
            keyence_z_point_data = f"-{keyence_z_point_data}"
        if '+' in keyence_z_point_data:
            keyence_z_point_data = keyence_z_point_data.split('+')
            keyence_z_point_data = round(float(keyence_z_point_data[1]),4)
        # print(f'KEYNCE {msg}: {keyence_z_point_data}')
        results.append(keyence_z_point_data)


    # print_color(f'({machine_num})[STAGE:1] Defect_Number: {results[0]}')
    # print_color(f'({machine_num})[STAGE:1] Defect_Size: {results[1]}')
    # print_color(f'({machine_num})[STAGE:1] Defect_Zone: {results[2]}')
    # print_color(f'({machine_num})[STAGE:1] Pass: {results[3]}')
    # print_color(f'({machine_num})[STAGE:1] Fail: {results[4]}')
    # print_color(f'({machine_num})[STAGE:1] Mask_Fail: {results[5]}')
    # print_color(f'({machine_num})[STAGE:1] Size_Fail: {results[6]}')
    # print_color(f'({machine_num})[STAGE:1] Spacing_Fail: {results[7]}')
    # print_color(f'({machine_num})[STAGE:1] Density_Fail: {results[8]}')
    # print_color(f'({machine_num})[STAGE:1] Current Z-Point_(1): {results[9]}')
    # print_color(f'({machine_num})[STAGE:1] Current Z-Point_(2): {results[10]}')



    # writing normalized Keyence results to proper PLC tags
    
    tag_list = ['DEFECT_NUMBER','DEFECT_SIZE','DEFECT_ZONE','PASS','FAIL','MASK_FAIL','SIZE_FAIL','SPACING_FAIL','DENSITY_FAIL','Z1','Z2','ZPOINT_1','ZPOINT_2']
    result_hash = dict(zip(tag_list,results))
    result_tag_list = tag_lists.result_tag_list()
    for i in range(len(result_tag_list)):
        write_plc_single(plc, machine_num, result_tag_list[i], results[i])
    write_plc_single(plc, machine_num, 'Done', True)
    # print_color(f'({machine_num})[STAGE:1] KEYENCE Results written to PLC...\n')
  
    
    # return {results[i]: result_tags[i] for i in range(len(results))} #return results to use in result files
    return [results,result_hash]
#END keyenceResults_to_PLC



def check_keyence_error(machine_num:str, sock:socket.socket, plc:LogixDriver):
    # error_msg = 'MR,%Error0Code\r\n'
    # sock.sendall(error_msg.encode())
    # n = str(data).split('.')
    # m = n[0].split('+')
    # o = int(m[1])
    # data = int(o)
    # if(data < 16):
    #     # print(f'({machine_num}) Error Code:\n',data)
    #     write_plc_single(plc, machine_num, 'Faulted', True)
    #     write_plc_single(plc, machine_num, 'PhoenixFltCode', data)
    # elif(data >= 16 and data < 48):
    #     # print(f'({machine_num}) Error Code:\n',data)
    #     write_plc_single(plc, machine_num, 'Faulted', True)
    #     write_plc_single(plc, machine_num, 'KeyenceFltCode', data)
    # else:
    #     # print(f'({machine_num}) Error Code (non-crit):{data}\n')
    #     pass
    pass







def set_keyence_run_mode(machine_num:str, sock:socket.socket):
    # print_color(f'({machine_num}) SETTING KEYENCE TO RUN MODE...\n')
    msg = 'R0'
    sock.sendall(msg.encode())
    _ = sock.recv(32) #Clearing buffer

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
    tag_values = []
    for cmd, tag in zip(keyence_commands, check_pass_tags.get(machine_num, [])):
        sock.sendall(cmd.encode())
        data = sock.recv(32)
        # keyence_value_raw = int(str(data).split('+')[1])
        n = str(data).split('.')
        m = n[0].split('+')
        o = int(m[1])
        data = o
        # write_plc_check_pass(plc, machine_num, f"{tag}{machine_num}", data)
        tag_values.append(data)



        # keyence_commands = ['MR,#Hole1\r\n','MR,#Hole2\r\n','MR,#Hole3\r\n','MR,#Hole4\r\n']
        # check_pass_data = []
        # for cmd in keyence_commands:
        #     sock.sendall(cmd.encode())
        #     data = sock.recv(32)
        # # keyence_value_raw = int(str(data).split('+')[1])
        #     n = str(data).split('.')
        #     m = n[0].split('+')
        #     o = int(m[1])
        #     data = o
        #     check_pass_data.append(data)
        # check_pass_tags = [
        #     'Program:DU050CA02.CAM01.I.Check_Pass.3',
        #     'Program:DU050CA03.CAM01.I.Check_Pass.4',
        #     'Program:DU050CA03.CAM02.I.Check_Pass.5'
        #     ]
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
    for i,j in zip(tags,tag_values):
        write_plc_check_pass(plc,machine_num,i,j)
            
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

def reset_toEnd_cycle(plc:LogixDriver, machine_num:str):
    # print_color(f'({machine_num})[STAGE:2] PLC(END_PROGRAM) is high. Dropping PHOENIX(DONE) low...\n')
    reset_plc_tags(plc, machine_num,'type_three')
    check_pass_flush(plc,machine_num) #Flush Check/Pass data before sending data to PLC again
    write_plc_flush(plc,machine_num) # defaults all .I Phoenix tags at start of cycle
    write_plc_single(plc, machine_num, 'Ready', True)
    
# import os 

# # path = f"C:\MiddleManPython\MMHousingDeployment\{i}-Aug-{j}-2023_py.log"


