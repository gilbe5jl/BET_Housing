from keyence_utils import *
from plc_utils import *
from tag_lists import *
from pycomm3 import LogixDriver
from export_data import *
import socket
import datetime
def exe_time(start_time, end_time):
    return (end_time - start_time).total_seconds() * 1000
def read_config()->dict:
    with open(os.path.join(sys.path[0], 'config.json'), "r") as config_file:
        config_data = config_file.read()
        config_vars = json.loads(config_data)
        return config_vars

def get_status_info(machine_num:str,plc:LogixDriver)->list:
    config_info = read_config()
    print(f'({machine_num}) Reading PLC\n')
    tag_data = read_plc_dict(plc, machine_num) #initial PLC tag read
    part_type = tag_data[config_info['tags']['PartType']][1]
    reset_check = read_plc_single(plc, machine_num, 'Reset')   # PLC read and check to reset system off PLC(Reset) tag
    return {"part_type":part_type,"reset_check":reset_check,"tag_data":tag_data}

def start_stage_zero(machine_num:str,plc:LogixDriver,sock:socket.socket,current_stage:int)->None:
    print(f'({machine_num})[STAGE:{current_stage}] Entering Stage 0: Awaiting PLC(LOAD_PROGRAM) and PLC(BUSY) state changes...')
    check_keyence_error(machine_num, sock, plc) #check keyence for error codes
    set_bool_tags(plc, machine_num)
def stage_zero_preLoad(machine_num:str,plc:LogixDriver,sock:socket.socket)->int:
    tag_data = read_plc_dict(plc, machine_num)
    tag_data_og = tag_data.copy()
    part_program = tag_data[config_info['tags']['PartProgram']][1] 
    print(f"Reading PART_PROGRAM as: {part_program}\n({machine_num}) Lowering Phoenix PLC(READY) and Mirroring Data...")
    write_plc_single(plc, machine_num, 'Ready', False) #setting PLC(READY) low
    write_plc(plc,machine_num,tag_data_og) # MIRRORING DATA
    part_type = tag_data[config_info['tags']['PartType']][1]
    swap_check = keyence_swap_check(sock, machine_num, part_type) #ensure keyence has proper program loaded   
    return {"swap_check":swap_check,"part_program": part_program,"part_type": part_type}
def stage_zero_load(plc: LogixDriver, sock: socket.socket, machine_num: str, tag_data: dict) -> None:
    try:
        pun_str = int_array_to_str(tag_data['PUN'][1])
        datetime_info_len_check = [str(tag_data[config_info['tags']['Month']][1]),
                                  str(tag_data[config_info['tags']['Day']][1]),
                                  str(tag_data[config_info['tags']['Hour']][1]),
                                  str(tag_data[config_info['tags']['Minute']][1]),
                                  str(tag_data[config_info['tags']['Second']][1])]

        for x in range(0, len(datetime_info_len_check)): 
            if int(datetime_info_len_check[x]) < 10:
                datetime_info_len_check[x] = '0' + datetime_info_len_check[x]

        keyence_string = str(pun_str[10:22]) + '_' + str(tag_data[config_info['tags']['Year']][1]) + '-' + datetime_info_len_check[0] + '-' + datetime_info_len_check[1] + '-' + datetime_info_len_check[2] + '-' + datetime_info_len_check[3] + '-' + datetime_info_len_check[4] + '_' + keyence_string

        load_keyence(sock, machine_num, str(tag_data[config_info['tags']['PartProgram']][1]), keyence_string, plc)
    except Exception as error:
        print(f'({machine_num}) Error in utils.py//stage_zero_load: {error}')
        raise error

def stage_one_trigger(plc: LogixDriver, sock: socket.socket, machine_num: str, tag_data: dict) -> None:
    try:
        tag_data = read_plc_dict(plc, machine_num)
        start_trigger_timer = datetime.datetime.now()
        trigger_keyence(sock, machine_num, plc)
        end_trigger_timer = datetime.datetime.now()
        exe_time = exe_time(start_trigger_timer, end_trigger_timer)
        return {"exe_time": exe_time, "tag_data": tag_data, "start_trigger_timer": start_trigger_timer}
    except Exception as error:
        print(f'({machine_num}) Error in utils.py//stage_one_trigger: {error}')
        raise error

def stage_one_post_trigger(plc: LogixDriver, sock: socket.socket, machine_num: str, tag_data: dict, start_trigger_timer) -> None:
    try:
        monitor_end_scan(plc, machine_num, sock, plc)
        end_trigger_timer = datetime.datetime.now()
        scan_duration = (end_trigger_timer - start_trigger_timer).total_seconds() * 1000
        write_plc_single(plc, machine_num, 'Busy', False)
        start_result_timer = datetime.datetime.now()
        monitor_keyence_not_running(sock, machine_num)
        end_result_timer = datetime.datetime.now()
        exe_time = exe_time(start_result_timer, end_result_timer)
        return {"scan_duration": scan_duration, "exe_time": exe_time, "tag_data": tag_data}
    except Exception as error:
        print(f'({machine_num}) Error in utils.py//stage_one_post_trigger: {error}')
        raise error

def end_stage_one(plc: LogixDriver, sock: socket.socket, machine_num: str, tag_data: dict, scan_duration: int, keyence_string, part_type, part_program) -> None:
    try:
        keyence_check_pass(machine_num, sock, plc)
        keyence_results = keyence_results_to_PLC(sock, plc, machine_num)
        export_all_data(machine_num, tag_data, keyence_results, keyence_string, scan_duration, part_type, part_program)
        keyence_control_cont(sock, machine_num)
    except Exception as error:
        print(f'({machine_num}) Error in utils.py//end_stage_one: {error}')
        raise error
    
def get_stage_zero_data(plc:LogixDriver,machine_num:str):
    try:
        tag_data = read_plc_dict(plc, machine_num) #continuous full PLC read
        reset_check = read_plc_single(plc, machine_num, 'Reset') #single plc tag read
        return {"tag_data":tag_data,"reset_check":reset_check}
    except Exception as error:
        print(f'({machine_num}) Error in utils.py//get_stage_zero_data: {error}')
        raise error

# move exe_time function to this file and call it from here so that these functions can return less variables 

