import socket
import time
import datetime

from pycomm3 import LogixDriver

from plcFuncs import write_plc_single, write_plc_check_pass, flush_check_pass
from plcFuncs import read_plc_single, int_array_to_str
import tagLists
from pycomm3.tag import Tag
import tagLists
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




def keyence_string_generator(machine_num:str, PartT:int, results_dict:dict, sock:socket.socket, config_info:dict):
    try:
        scanSet = 'scan_names' + config_info['PartT_switch'][str(PartT)] #get key for config to use correct PartProgram dictionary
        keyence_string = config_info[scanSet][str(results_dict[config_info['tags']['PartProgram']][1])] + f'_{config_info["PartT_switch"][str(PartT)]}'
    except Exception as error:
        print(f'({machine_num}) Error Building Keyence String Check PartProgram and PartType',error)
        return 'ERROR' # The return value is checked in main.py
    return keyence_string

# used to ensure the correct Keyence program is loaded for the part being processed 
def keyence_swap_check(sock:socket.socket, machine_num:str, partType:int):
    #global swapDelay
   
    print(f'({machine_num}) Validating Keyence has proper program loaded...\n')
    try:
        print(f'({machine_num}) Attempting Swap to scanSet {config_info["PartT_switch"][str(partType)]}')
    except KeyError as e:
        print(f'{machine_num}) INVALID PART_TYPE: {partType}')
        return 0
    msg = 'PR\r\n'

    #with lock:
    sock.sendall(msg.encode())
    data = sock.recv(32)
    #print('received "%s"' % data)

    keyence_value_raw = str(data).split(',')
    keyence_value_raw = str(keyence_value_raw[2]).split('\\')
    print(f'({machine_num}) Keyence currently has program : {keyence_value_raw[0][3]} loaded')
    keyence_value = int(keyence_value_raw[0][3]) # current program number loaded on Keyence

    if(keyence_value != partType):
        print(f'({machine_num}) Swapping Keyence program to: {partType}')
        message = 'PW,1,' + str(partType) + '\r\n'
        sock.sendall(message.encode()) 
        data = sock.recv(32)
        time.sleep(2)
    else:
        pass
    
#END KeyenceSwapCheck


# Triggering Keyence (to start a scan)
def trigger_keyence(sock:socket.socket, machine_num:str):

    message = 'MR,%Busy\r\n' #initial read of '%Busy' to ensure scan is actually taking place (%Busy == 1)
    sock.sendall(message.encode())
    data = sock.recv(32)

    first_busy_pull_start = datetime.datetime.now()
    # looping until '%Busy' == 0
    while(data != b'MR,+0000000000.000000\r'):
        message = 'MR,%Busy\r\n'
        sock.sendall(message.encode())
        data = sock.recv(32)
        time.sleep(.2) # artificial 1ms pause between Keyence reads
    first_busy_pull_stop = datetime.datetime.now()
    time_diff = (first_busy_pull_stop - first_busy_pull_start)
    execution_time = time_diff.total_seconds() * 1000
    if(int(execution_time) > 100):
        print(f'\n({machine_num}) TriggerKeyence (First Busy Pull) SLOW (over 100ms)! Took {execution_time} ms!!!\n')

    message = 'T1\r\n' # 'T1' in this case
    trigger_start_time = datetime.datetime.now() # marking when 'T1' is sent
    #with lock:
    sock.sendall(message.encode()) #*** sending 'T1', actual trigger command ***
    data = sock.recv(32)
    trigger_t1Only_end = datetime.datetime.now()
    time_diff = (trigger_t1Only_end - trigger_start_time)
    execution_time = time_diff.total_seconds() * 1000
    if(int(execution_time) > 50):
        print(f'({machine_num}) TriggerKeyence (Sending T1) SLOW (over 50ms)! Took {execution_time} ms!!!\n')

    message = 'MR,%Busy\r\n' #initial read of '%Busy' to ensure scan is actually taking place (%Busy == 1)
    sock.sendall(message.encode())
    data = sock.recv(32)
    #print(f'%Busy = {data}')

    final_busy_pull_start = datetime.datetime.now()
    # looping until '%Busy' == 0
    while(data != b'MR,+0000000001.000000\r'):
    #while(data != b'T1\r'):
        #message = 'T1\r\n'
        message = 'MR,%Busy\r\n'
        sock.sendall(message.encode())
        data = sock.recv(32)
        print(f'({machine_num}) Scanning\n')

        time.sleep(.2) # artificial 1ms pause between Keyence reads

    trigger_end_time = datetime.datetime.now() # marking when '%Busy' is read off Keyence
    time_diff = (trigger_end_time - final_busy_pull_start)
    execution_time = time_diff.total_seconds() * 1000
    if(int(execution_time) > 100):
        print(f'({machine_num}) TriggerKeyence (Final Busy Pull) SLOW (over 100ms)! Took {execution_time} ms!!!\n')

#END 'TriggerKeyence'

#sends specific Keyence Program (branch) info to pre-load/prepare Keyence for Trigger(T1), also loads naming variables for result files
def load_keyence(sock:socket.socket, machine_num:str, partProgram:int, keyenceString:str):
    print(f'({machine_num}) LOADING KEYENCE\n') 
    branch_info = f'MW,#PhoenixControlFaceBranch,{partProgram}\r\n' # keyence message
    stw_cmd = 'STW,0,"' + keyenceString + '\r\n' # keyence message sets image names for part
    result_cmd = f'OW,42,"{keyenceString}-Result\r\n' # keyence message specifies output unit
    #need sock.recv to clear keyence buffer
    # sending branch info
    sock.sendall(branch_info.encode()) 
    _ = sock.recv(32)
    sock.sendall(stw_cmd.encode())
    _ = sock.recv(32)
    sock.sendall(result_cmd.encode())
    _ = sock.recv(32)
    message = 'OW,43,"' + keyenceString + '-10Lar\r\n' # keyence message output unit
    sock.sendall(message.encode())
    _ = sock.recv(32)
    message = 'OW,44,"' + keyenceString + '-10Loc\r\n' # keyence message output unit
    sock.sendall(message.encode())
    _ = sock.recv(32)
    


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
def exit_keyence(sock:socket.socket):
    message = 'TE,0\r\n' # setting 'TE,0' first
    sock.sendall(message.encode()) # sending TE,0
    data = sock.recv(32)

    message = 'TE,1\r\n' # setting 'TE,1' to reset
    sock.sendall(message.encode()) # sending, TE,1
    data = sock.recv(32)

    message = 'MR,%Busy\r\n' #read of '%Busy' to ensure scan has ended (should be 0)
    sock.sendall(message.encode())
    data = sock.recv(32)

    # looping until '%Busy' == 0
    while(data != b'MR,+0000000000.000000\r'):
        message = 'MR,%Busy\r\n'
        sock.sendall(message.encode())
        data = sock.recv(32)
        time.sleep(.2) # artificial 1ms pause between Keyence reads
# END 'ExtKeyence'


# reading PLC(EndScan) until it goes high to interrupt current Keyence scan
def monitor_endScan(plc:LogixDriver, machine_num:str, sock:socket.socket):
    print(f'({machine_num}) Listening for PLC(END_SCAN) high\n')
    #print(read_plc_singles(plc, machine_num, ['EndScan', 'Reset']))
    current = read_plc_single(plc, machine_num, 'EndScan')
    current.update(read_plc_single(plc, machine_num, 'Reset'))
    #print((current[config_info['tags']['EndScan']][1] == False) and (current[config_info['tags']['Reset']][1] == False))
    while((current[config_info['tags']['EndScan']][1] == False) and (current[config_info['tags']['Reset']][1] == False)):
        #continuing tag check(s)
        current = read_plc_single(plc, machine_num, 'EndScan')
        current.update(read_plc_single(plc, machine_num, 'Reset'))
        time.sleep(.005)
    #print(f'({machine_num}) PLC(END_SCAN) went high!\n')
    exit_keyence(sock) #function to interrupt Keyence
    print(f'({machine_num}) End_Scan Signal Recieved ##################### Scan Stopped ###################\n')
#END monitor_endScan

# function to monitor the Keyence tag 'KeyenceNotRunning', when True (+00001.00000) we know Keyence has completed result processing and FTP file write
def monitor_keyence_not_running(sock:socket.socket, machine_num:str):
    print(f'({machine_num}) Keyence Processing...')
    msg = 'MR,#KeyenceNotRunning\r\n'
    sock.sendall(msg.encode())
    data = sock.recv(32)

    #until #KeyenceNotRunning from Keyence goes high, continuously check its value
    while(data != b'MR,+0000000001.000000\r'):
        sock.sendall(msg.encode())
        data = sock.recv(32)
        time.sleep(.005)
    print(f'({machine_num}) Keyence Processing Complete!\n')
#END monitor_KeyenceNotRunning

# read defect information from the Keyence, then passes that as well as pass,fail,done to PLC, returns a list of result data for .txt file creation
def keyenceResults_to_PLC(sock:socket.socket, plc:LogixDriver, machine_num:str):
    #read results from Keyence then pass to proper tags on PLC
    result_messages = ['MR,#ReportDefectCount\r\n', 'MR,#ReportLargestDefectSize\r\n', 'MR,#ReportLargestDefectZoneNumber\r\n', 'MR,#ReportPass\r\n', 'MR,#ReportFail\r\n',
                        'MR,#ReportMaskFail\r\n', 'MR,#ReportSizeFail\r\n', 'MR,#ReportSpacingFail\r\n', 'MR,#ReportDensityFail\r\n']
    results = []

    # sending result messages to Keyence, then cleaning results to 'human-readable' list
    for msg in result_messages:
        sock.sendall(msg.encode())
        data = sock.recv(32)
        keyence_value_raw = str(data).split('.')
        keyence_value_raw = keyence_value_raw[0].split('+')
        keyence_value = int(keyence_value_raw[1])
        results.append(keyence_value)
        # print("KEYENCE Results RAW --",data)
        # print("KEYENCE Results COOKED --",keyence_value)

    print(f'({machine_num}) Defect_Number: {results[0]}')
    print(f'({machine_num}) Defect_Size: {results[1]}')
    print(f'({machine_num}) Defect_Zone: {results[2]}')
    print(f'({machine_num}) Pass: {results[3]}')
    print(f'({machine_num}) Fail: {results[4]}')
    print(f'({machine_num}) Mask_Fail: {results[5]}')
    print(f'({machine_num}) Size_Fail: {results[6]}')
    print(f'({machine_num}) Spacing_Fail: {results[7]}')
    print(f'({machine_num}) Density_Fail: {results[8]}')

    # writing normalized Keyence results to proper PLC tags
    

    result_tags = tagLists.result_tag_list()
    for i in range(len(result_tags)):
        write_plc_single(plc, machine_num, result_tags[i], results[i])
    write_plc_single(plc, machine_num, 'Done', True)

    print(f'({machine_num}) Keyence Results written to PLC!')
    print("===KEYENCE RESULTS ===")
    for i in results:
        print(i)
    
    return results #return results to use in result files

#END keyenceResults_to_PLC

def check_keyence_error(machine_num:str, sock:socket.socket, plc:LogixDriver):
    error_msg = 'MR,%Error0Code\r\n'
    sock.sendall(error_msg.encode())
    data = sock.recv(32)
    n = str(data).split('.')
    m = n[0].split('+')
    o = int(m[1])
    data = o
    if(data==0):
        pass
    
    elif(data < 16):
        print(f'({machine_num}) Error Code:\n',data)
        write_plc_single(plc, machine_num, 'Faulted', True)
        write_plc_single(plc, machine_num, 'PhoenixFltCode', data)
        
    elif(data>=16 and data!=48):
        print(f'({machine_num}) Error Code:\n',data)
        write_plc_single(plc, machine_num, 'Faulted', True)
        write_plc_single(plc, machine_num, 'KeyenceFltCode', data)
        
    elif(data==48):
        print(f'({machine_num}) Error Code (non-crit):\n',data)
        pass
    else:
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
def keyence_check_pass(machine_num:str,sock:socket.socket,plc:LogixDriver):
    keyence_commands = [
        'MR,#Hole1\r\n',
        'MR,#Hole2\r\n',
        'MR,#Hole3\r\n',
        'MR,#Hole4\r\n']
    check_pass_tags = {
        '3':"Program:DU050CA02.CAM01.I.Check_Pass.",
        '4':"Program:DU050CA03.CAM01.I.Check_Pass.",
        '5':"Program:DU050CA03.CAM02.I.Check_Pass."
        }
    check_pass_data = [] #Used to hold response data from keyence 
    tags = [] # Used to hold all four tag names for each robot 
    for msg in keyence_commands: # Send all commands to keyence
        sock.sendall(msg.encode())
        data = sock.recv(32)
        keyence_value_raw = str(data).split('.')
        keyence_value_raw = keyence_value_raw[0].split('+')
        keyence_value = int(keyence_value_raw[1])
        check_pass_data.append(keyence_value)
        # check_pass_data.append(data)
        # Keyence DATA -b'ER,MR,91\r'
        print(f"Keyence DATA -{data}")
    for i in range(1,5):
        x = f"{check_pass_tags[machine_num]}{i}"
        tags.append(x) # Construct four full tag names based on machine number
    # for i in tags:
    #     flush_check_pass(plc, machine_num,i)
    for i,j in zip(tags,check_pass_data):
        # write_plc_single(plc,machine_num,i,j) # Write the check pass data to the plc 
        write_plc_check_pass(plc,machine_num,i,j)
        
    
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

# import os 

# # path = f"C:\MiddleManPython\MMHousingDeployment\{i}-Aug-{j}-2023_py.log"


# # import os 
# # today = datetime.date.today().strftime("%a-%b-%d-%Y")
# try:
#     days = ['Mon','Tue','Wed','Thu','Fri']
#     dates = ['14','15','16','17','18']
#     for i,j in zip(days,dates):
#         path = f"C:\MiddleManPython\MMHousingDeployment\{i}-Aug-{j}-2023_py.log"
#         os.remove(path)
# except FileNotFoundError as error:
#     message = f"Log file was NOT deleted...{error}"
#     print(message)
    # return message