from keyence_utils import *
from plc_utils import *
from tag_lists import *
from pycomm3 import LogixDriver
import socket

def read_config()->dict:
    with open(os.path.join(sys.path[0], 'config.json'), "r") as config_file:
        config_data = config_file.read()
        config_vars = json.loads(config_data)
        return config_vars

def get_status_info(machine_num:str,plc:LogixDriver)->list:
    config_info = read_config()
    print(f'({machine_num}) Reading PLC\n')
    results_map = read_plc_dict(plc, machine_num) #initial PLC tag read
    part_type = results_map[config_info['tags']['PartType']][1]
    reset_check = read_plc_single(plc, machine_num, 'Reset')   # PLC read and check to reset system off PLC(Reset) tag
    return [part_type, reset_check]

def start_stage_zero(machine_num:str,plc:LogixDriver,sock:socket.socket,current_stage:int)->None:
    print(f'({machine_num})[STAGE:{current_stage}] Entering Stage 0: Awaiting PLC(LOAD_PROGRAM) and PLC(BUSY) state changes...')
    check_keyence_error(machine_num, sock, plc) #check keyence for error codes
    set_bool_tags(plc, machine_num)

    
    pass