
import threading
import datetime, time
import socket
from pycomm3 import LogixDriver
import json
from tag_lists import *
from plc_utils import *
from keyence_utils import *
from export_data import *
from colorama import Fore, Style
##################### LOGGING ###########################
import logging
import inspect
import datetime
current_frame = inspect.currentframe()
frame_info = inspect.getframeinfo(current_frame)
path = frame_info.filename
filename = path.split("/")[-1]
# function_name = frame_info.function
today = datetime.date.today().strftime("%a-%b-%d-%Y")
now = datetime.datetime.now().strftime("%I:%M:%S.%f")[:-3]
logger = logging.getLogger(filename)
logger.setLevel(logging.DEBUG)
log_filename = f"{today}_MAIN.log"  # Include filename in the log name
handler = logging.FileHandler(log_filename)
formatter = logging.Formatter(f"{now} - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.propagate = False
handler.close()
logger.removeHandler(handler)
#########################################################
spec_map = {}
event = threading.Event()
kill_threads = threading.Event()
part_program = 0
def print_green(message:str)->None:
    logger.debug(message)
    print(Fore.GREEN + f"{message}\n" + Style.RESET_ALL)
def print_blue(message:str)->None:
    logger.info(message)
    print(Fore.BLUE + f"{message}" + Style.RESET_ALL)
def print_yellow(message:str)->None:
    logger.info(message)
    print(Fore.YELLOW + f"{message}" + Style.RESET_ALL)
def print_red(message:str)->None:
    logger.critical(message)
    print(Fore.RED + f"{message}" + Style.RESET_ALL)
def exe_time(start_time, end_time):
    return (end_time - start_time).total_seconds() * 1000
def read_config()->dict:
    with open(os.path.join(sys.path[0], 'config.json'), "r") as config_file:
        config_data = config_file.read()
        config_vars = json.loads(config_data)
        return config_vars
class cycler:
    def __init__(self, machine_num, keyence_ip):   
        self.self = self
        self.machine_num = machine_num
        self.keyence_ip = keyence_ip
        self.current_stage = 0
    def cycle(self, machine_num, keyence_ip,reset_events):
        kill_threads.clear()
        event.wait()
        time.sleep(.05)
        config_info = read_config()
        print_blue(f'({machine_num}) Sequence Started\n({machine_num}) Connecting to PLC at {config_info["plc_ip"]}\n({machine_num}) Connected to Keyence at {keyence_ip}\n')
        scan_duration = 0 # keeping track of scan time in MS
        with LogixDriver(config_info['plc_ip']) as plc: #context manager for plc connection, currently resetting connection after ~24 hrs to avoid issues
            print_green(f'({machine_num}) ...PLC Connection Successful...\n')
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # Keyence socket connections
            sock.connect((keyence_ip, 8500))
           # setKeyenceRunMode(machine_num, sock)
            write_plc_fault_flush(plc,machine_num) # Fault Codes and raise ready
            connection_timer = datetime.datetime.now() #reset connection timer
            while(True):
                if(kill_threads.is_set()): #check reset at beginning of cycle
                    print_red(f'({machine_num}) kill_threads detected at cycle start! Restarting threads...\n')
                    break
                #spec_map = check_keyene_spec(sock, spec_map)
                print_green(f'({machine_num}) Reading PLC\n')
                results_map = read_plc_dict(plc, machine_num) #initial PLC tag read
                part_type = results_map[config_info['tags']['PartType']][1]
                reset_check = read_plc_single(plc, machine_num, 'Reset')   # PLC read and check to reset system off PLC(Reset) tag
                if (reset_check[config_info['tags']['Reset']][1]):
                    self.current_stage = 0
                    reset_plc_tags(plc, machine_num,'type_one')
                    # kill_threads.set()
                    current_thread = threading.current_thread()
                    if current_thread in reset_events:
                        reset_events[current_thread].set()          
                if(self.current_stage == 0):
                    print_yellow(f'({machine_num}) Stage 0: Awaiting PLC(LOAD_PROGRAM) and PLC(BUSY) state changes...')
                    check_keyence_error(machine_num, sock, plc) #check keyence for error codes
                    set_bool_tags(plc, machine_num)
                    while(results_map[config_info['tags']['LoadProgram']][1] != True): #Looping until LOAD PROGRAM goes high  # Data from PLC is only valid while LOAD_PROGRAM is low
                        if (kill_threads.is_set() or reset_events[current_thread].is_set()):
                            print_red(f'({machine_num}) kill_threads detected while waiting for LOAD! Restarting threads...\n')
                            break
                        results_map = read_plc_dict(plc, machine_num) #continuous full PLC read
                        reset_check = read_plc_single(plc, machine_num, 'Reset') #single plc tag read
                        if (reset_check[config_info['tags']['Reset']][1] == True):
                            self.current_stage = 0
                            reset_plc_tags(plc, machine_num,'type_one')
                            # kill_threads.set()
                            current_thread = threading.current_thread()
                            if current_thread in reset_events:
                                reset_events[current_thread].set()
                        time.sleep(.050) # 5ms pause between reads
                    if (kill_threads.is_set() or reset_events[current_thread].is_set()):
                        break
                    print_green(f'({machine_num}) PLC(LOAD_PROGRAM) activated. Retrieving part data and program number...') # Once PLC(LOAD_PROGRAM) goes high, mirror data and set Phoenix(READY) high, signifies end of "loading" process
                    results_map = read_plc_dict(plc, machine_num)
                    results_map_og = results_map.copy()
                    part_program = results_map[config_info['tags']['PartProgram']][1] 
                    print_green(f"Reading PART_PROGRAM as: {part_program}\n({machine_num}) Lowering Phoenix PLC(READY) and Mirroring Data...")
                    write_plc_single(plc, machine_num, 'Ready', False) #setting PLC(READY) low
                    write_plc(plc,machine_num,results_map_og) # MIRRORING DATA
                    part_type = results_map[config_info['tags']['PartType']][1]
                    swap_check = keyence_swap_check(sock, machine_num, part_type) #ensure keyence has proper program loaded   
                    if swap_check == 0: # reset threads if invalid part type
                        # kill_threads.set()
                        current_thread = threading.current_thread()
                        if current_thread in reset_events:
                                reset_events[current_thread].set()
                    part_type = results_map[config_info['tags']['PartType']][1]
                    print_blue(f'({machine_num}) READING PART_TYPE AFTER LOAD AS:({part_type})')
                    keyence_string = keyence_string_generator(machine_num, part_type, results_map, sock, config_info) #building out external Keyence string for scan file naming
                    if keyence_string == 'ERROR':
                        # kill_threads.set()
                        current_thread = threading.current_thread()
                        if current_thread in reset_events:
                                reset_events[current_thread].set()
                    pun_str = int_array_to_str(results_map['PUN'][1])
                    datetime_info_len_check = [str(results_map[config_info['tags']['Month']][1]), str(results_map[config_info['tags']['Day']][1]), str(results_map[config_info['tags']['Hour']][1]), str(results_map[config_info['tags']['Minute']][1]), str(results_map[config_info['tags']['Second']][1])]
                    for x in range(0,len(datetime_info_len_check)): # confirming all date/time fields are 2 digits (except year)
                        if(int(datetime_info_len_check[x]) < 10):
                            datetime_info_len_check[x] = '0' + datetime_info_len_check[x]
                    keyence_string = str(pun_str[10:22]) + '_' + str(results_map[config_info['tags']['Year']][1]) + '-' + datetime_info_len_check[0] + '-' + datetime_info_len_check[1] + '-' + datetime_info_len_check[2] + '-' + datetime_info_len_check[3] + '-' + datetime_info_len_check[4] + '_' + keyence_string                     # print_blue(f'{pun_str, pun_str[10:22]} \n',  str(results_map[config_info['tags']['Year']][1]))
                    load_keyence(sock, machine_num, str(results_map[config_info['tags']['PartProgram']][1]), keyence_string,plc ) #Keyence loading message, uses PartProgram from PLC to load specific branch and raise PLC(READY) when complete
                    self.current_stage += 1 #increment current stage to proceed forward
                elif self.current_stage == 1:
                    print_yellow(f'({machine_num}) __STAGE ONE ({machine_num})__\n\tWaiting for START_PROGRAM\n')
                    while not results_map[config_info['tags']['StartProgram']][1]: #looping until PLC(START_PROGRAM) goes high
                        if kill_threads.is_set() or reset_events[threading.current_thread()].is_set(): #check for reset at beginning of cycle
                            print_red(f'({machine_num}) kill_threads detected while waiting for START!\n...Restarting threads...\n') 
                            break
                        results_map = read_plc_dict(plc, machine_num) #continuous PLC read
                        if results_map[config_info['tags']['Reset']][1]: #check for reset during cycle
                            self.current_stage = 0
                            reset_plc_tags(plc, machine_num, 'type_two') # type_two reset for stage 1
                            if threading.current_thread() in reset_events:
                                reset_events[threading.current_thread()].set()
                        time.sleep(0.050)
                    results_map = read_plc_dict(plc, machine_num) #continuous PLC read
                    print_green(f'({machine_num}) PLC(START_PROGRAM) went high!\n')
                    start_trigger_timer = datetime.datetime.now()
                    trigger_keyence(sock, machine_num, plc) #Keyence trigger message, raises PLC(BUSY) when complete
                    end_trigger_timer = datetime.datetime.now()
                    if (exe_time(end_trigger_timer,start_trigger_timer) > 3000):
                        write_plc_fault(plc, machine_num, 2)
                    monitor_end_scan(plc, machine_num, sock, plc) #monitoring PLC(END_SCAN) to ensure it goes high
                    end_trigger_timer = datetime.datetime.now()
                    scan_duration = (end_trigger_timer - start_trigger_timer).total_seconds() * 1000
                    write_plc_single(plc, machine_num, 'Busy', False)
                    start_result_timer = datetime.datetime.now()
                    monitor_keyence_not_running(sock, machine_num) #monitoring Keyence to ensure it is not running
                    end_result_timer = datetime.datetime.now()
                    if exe_time(end_result_timer,start_result_timer) > 3000:
                        write_plc_fault(plc, machine_num, 3)
                    keyence_check_pass(machine_num, sock, plc)
                    keyence_results = keyence_results_to_PLC(sock, plc, machine_num)
                    export_all_data(machine_num, results_map, keyence_results, keyence_string, scan_duration, part_type, part_program)
                    keyence_control_cont(sock, machine_num)
                    print_green(f'({machine_num}) Stage 1 Complete!\n')
                    self.current_stage += 1
                elif self.current_stage == 2:  # Final Stage, reset to Stage 0 once PLC(END_PROGRAM) and PHOENIX(DONE) have been set low
                    write_plc_single(plc, machine_num, 'Done', True)
                    print_yellow(f'({machine_num}) Stage 2 : Listening for PLC(ENDPROGRAM) high to reset back to Stage 0\n')
                    while not results_map[config_info['tags']['EndProgram']][1]:
                        if kill_threads.is_set() or reset_events[threading.current_thread()].is_set():
                            print_red(f'({machine_num}) kill_threads detected while waiting for ENDPROGRAM! Restarting threads...\n')
                            break
                        results_map = read_plc_dict(plc, machine_num)  # continuous PLC read
                        if results_map[config_info['tags']['Reset']][1]:
                            print_yellow(f'({machine_num}) (StartProgram Check) Reset Detected! Setting back to Stage 0...\n')
                            self.current_stage = 0
                            reset_plc_tags(plc, machine_num, 'type_two')  # type_two reset for stage 2
                            current_thread = threading.current_thread()
                            if current_thread in reset_events:
                                reset_events[current_thread].set()
                        time.sleep(0.050)  # 5ms pause between reads
                    reset_toEnd_cycle(plc, machine_num, sock)  # reset PLC tags to end cycle
                    self.current_stage = 0  # cycle complete, reset to stage 0
                if abs(datetime.datetime.now() - connection_timer).total_seconds() > 86400:
                    print_red(f'({machine_num}) Connection reset detected! restarting threads...\n')
                    connection_timer = datetime.datetime.now()
                    current_thread = threading.current_thread()
                    if current_thread in reset_events:
                        reset_events[current_thread].set()
                if kill_threads.is_set() or reset_events[current_thread].is_set():
                    print_red(f'({machine_num}) kill_threads detected at cycle end! Restarting threads...\n')
                    break  # Kill thread if global is set True for any reason
                time.sleep(0.005)  # artificial loop timer
#END class Cycler
def heartbeat(machine_num, reset_event): #sets PLC(Heartbeat) high every second to verify we're still running and communicating
    config_info = read_config()
    def write_heartbeat(plc, machine_num):
        try:
            write_plc_single(plc, machine_num, 'HeartBeat', True)
        except Exception as error:
            print_red(f'({machine_num}) Exception in Heartbeat {error}')
            reset_event.set()
    with LogixDriver(config_info['plc_ip']) as plc:
        print_yellow(f'({machine_num}) Heartbeat thread connected to PLC. Writing \'Heartbeat\' high every 1 second\n')
        counter = 0
        while not (kill_threads.is_set() or reset_event.is_set()):
            write_heartbeat(plc, machine_num)
            if (counter % 200) == 0:
                print(f"({machine_num}) Active PLC Connection", end='\r')
            counter += 1
            time.sleep(1)
        print_red(f'({machine_num}) Heartbeat: kill_threads high or reset event set, restarting all threads')
# END heartbeat
def main():
    config_info = read_config()  # Read configuration information
    cycle_threads = []  # Store created cycle threads
    heartbeat_threads = []  # Store created heartbeat threads
    reset_events = {}  # Store reset events for each cycle thread
    for machine_num in list(config_info['mnKeyenceIP'].keys()):  # Loop through machines in config
        ip = config_info['mnKeyenceIP'][machine_num]
        cycle_object = cycler(machine_num, ip)
        reset_events[cycle_object] = threading.Event()
        cycle_thread = threading.Thread(target=cycle_object.cycle, args=[machine_num, ip, reset_events], name=f"machine_{machine_num}")
        cycle_thread.start()
        cycle_threads.append(cycle_thread)
        heartbeat_thread = threading.Thread(target=heartbeat, args=[machine_num, reset_events], name=f"{machine_num}_heartBeat")
        heartbeat_thread.start()
        heartbeat_threads.append(heartbeat_thread) 
    event.set()  # Signal threads to start
    for cycle_thread, heartbeat_thread in zip(cycle_threads, heartbeat_threads):
        cycle_thread.join()
        reset_event = reset_events[cycle_thread]
        reset_event.set()  # Signal cycle thread to reset
        heartbeat_thread.join()
        cycle_object = cycle_threads.pop(0)
        new_cycle_thread = threading.Thread(target=cycle_object.cycle, args=[machine_num, ip, reset_events], name=f"machine_{machine_num}")
        cycle_threads.append(cycle_object)
        new_cycle_thread.start()
    for reset_event in reset_events.values():
        reset_event.clear()  # Clear reset events
#END 'main'
if __name__ == '__main__':
    while(True):
        main()
