
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
function_name = frame_info.function
today = datetime.date.today().strftime("%a-%b-%d-%Y")
now = datetime.datetime.now().strftime("%I:%M:%S.%f")[:-3]
logger = logging.getLogger(filename)
logger.setLevel(logging.DEBUG)
log_filename = f"{today}_{filename}.log"  # Include filename in the log name
handler = logging.FileHandler(log_filename)
formatter = logging.Formatter(f"{now} - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.propagate = False
handler.close()
logger.removeHandler(handler)
#########################################################


### GLOBALS ########################################################
spec_map = {}
event = threading.Event()
kill_threads = threading.Event()
part_program = 0
# END GLOBALS ####################################################
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
#reads config file into dict
def read_config():
    with open(os.path.join(sys.path[0], 'config.json'), "r") as config_file:
        config_data = config_file.read()
        config_vars = json.loads(config_data)
        return config_vars
#END
 
# primary function, to be used by 14/15 threads
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
        print_blue(f'({machine_num}) Sequence Started')
        config_info = read_config()
        scan_duration = 0 # keeping track of scan time in MS
        print_green(f'({machine_num}) Connecting to PLC...\n')
        with LogixDriver(config_info['plc_ip']) as plc: #context manager for plc connection, currently resetting connection after ~24 hrs to avoid issues
            print_green(f'({machine_num}) ...PLC Connection Successful...\n')
            # Keyence socket connections
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((keyence_ip, 8500))
            print_blue(f'({machine_num}) Connected to Keyence at {keyence_ip}\n')
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
                # PLC read and check to reset system off PLC(Reset) tag
                reset_check = read_plc_single(plc, machine_num, 'Reset')
                if (reset_check[config_info['tags']['Reset']][1]):
                    print_yellow(f'({machine_num}) (Pre-Load) Reset Detected! Setting back to Stage 0...\n')
                    self.current_stage = 0
                    print_yellow(f'({machine_num}) Flushing PLC Fault Codes...\n')
                    write_plc_flush(plc,machine_num)
                    write_plc_single(plc, machine_num, 'Faulted', False)
                    write_plc_single(plc, machine_num, 'PhoenixFltCode', 0)
                    write_plc_single(plc, machine_num, 'KeyenceFltCode', 0)
                    write_plc_single(plc, machine_num, 'FaultStatus', 0)
                    # kill_threads.set()
                    current_thread = threading.current_thread()
                    if current_thread in reset_events:
                        reset_events[current_thread].set()          
                if(self.current_stage == 0):
                    print_yellow(f'({machine_num}) ...Stage 0...\n')
                    check_keyence_error(machine_num, sock, plc) #check keyence for error codes
                    print_yellow(f'({machine_num}) Setting Boolean Flags for Stage 0\n') #flag reset/beginning of timing diagram
                    write_plc_single(plc, machine_num, 'Done', False)
                    write_plc_single(plc, machine_num, 'Pass', False)
                    write_plc_single(plc, machine_num, 'Busy', False)
                    write_plc_single(plc, machine_num, 'Fail', False)
                    write_plc_single(plc, machine_num, 'Ready', True)
                    print_yellow(f'({machine_num}) Stage 0: Listening for PLC(LOAD_PROGRAM) to go HIGH\n({machine_num}) Waiting for PLC(BUSY) to go LOW\n') #reading PLC until LOAD_PROGRAM goes high
                    while(results_map[config_info['tags']['LoadProgram']][1] != True): #Looping until LOAD PROGRAM goes high 
                        # Data is only valid while LOAD_PROGRAM is low
                        if (kill_threads.is_set() or reset_events[current_thread].is_set()):
                            print_red(f'({machine_num}) kill_threads detected while waiting for LOAD! Restarting threads...\n')
                            break
                        results_map = read_plc_dict(plc, machine_num) #continuous full PLC read
                        reset_check = read_plc_single(plc, machine_num, 'Reset') #single plc tag read
                        if (reset_check[config_info['tags']['Reset']][1] == True):
                            print_red(f'({machine_num}) (Pre-Load) Reset Detected! Setting back to Stage 0...\n')
                            self.current_stage = 0
                            print_yellow(f'({machine_num}) Flushing PLC(Result) tag data...\n')
                            write_plc_flush(plc,machine_num)
                            write_plc_single(plc, machine_num, 'Faulted', False)
                            write_plc_single(plc, machine_num, 'PhoenixFltCode', 0)
                            write_plc_single(plc, machine_num, 'KeyenceFltCode', 0)
                            write_plc_single(plc, machine_num, 'FaultStatus', 0)
                            # kill_threads.set()
                            current_thread = threading.current_thread()
                            if current_thread in reset_events:
                                reset_events[current_thread].set()
                        time.sleep(.050) # 5ms pause between reads
                    if (kill_threads.is_set() or reset_events[current_thread].is_set()):
                        break
                    print_green(f'({machine_num}) PLC(LOAD_PROGRAM) went HIGH! preparing to drop READY\n')
                    print_blue(f'({machine_num}) Gathering part data and program number...\n')
                    results_map = read_plc_dict(plc, machine_num)
                    results_map_og = results_map.copy()
                    part_program = results_map[config_info['tags']['PartProgram']][1]
                    print_green(f"Reading PART_PROGRAM as: {part_program}")
                    # Once PLC(LOAD_PROGRAM) goes high, mirror data and set Phoenix(READY) high, signifies end of "loading" process
                    write_plc_single(plc, machine_num, 'Ready', False)
                    print_yellow(f'({machine_num}) Dropping Phoenix(READY) low.\n')
                    #################### Mirror ############################
                    print_yellow(f'({machine_num}) ...Mirroring Data...\n')
                    write_plc(plc,machine_num,results_map_og)
                    ############################################################
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
                    #confirming all date/time fields are 2 digits (except year)
                    for x in range(0,len(datetime_info_len_check)):
                        if(int(datetime_info_len_check[x]) < 10):
                            datetime_info_len_check[x] = '0' + datetime_info_len_check[x]
                    # print_blue(f'{pun_str, pun_str[10:22]} \n',  str(results_map[config_info['tags']['Year']][1]))
                    keyence_string = str(pun_str[10:22]) + '_' + str(results_map[config_info['tags']['Year']][1]) + '-' + datetime_info_len_check[0] + '-' + datetime_info_len_check[1] + '-' + datetime_info_len_check[2] + '-' + datetime_info_len_check[3] + '-' + datetime_info_len_check[4] + '_' + keyence_string
                    print_green(f'({machine_num}) LOADING : {keyence_string}\n')
                    load_keyence(sock, machine_num, str(results_map[config_info['tags']['PartProgram']][1]), keyence_string ) #Keyence loading message, uses PartProgram from PLC to load specific branch
                    print_green(f'({machine_num}) Keyence Loaded!\n')
                    write_plc_single(plc, machine_num, 'Ready', True)
                    self.current_stage += 1 #increment current stage to proceed forward
                #END STAGE0
                #START STAGE1 : START/END Program
                elif(self.current_stage == 1):
                    print_yellow(f'({machine_num}) __STAGE ONE ({machine_num})__\n\tWaiting for START_PROGRAM\n')
                    while(results_map[config_info['tags']['StartProgram']][1] != True): #Loop until START_PROGRAM goes High 
                        if (kill_threads.is_set() or reset_events[threading.current_thread()].is_set()):
                            print_red(f'({machine_num}) kill_threads detected while waiting for START!\n...Restarting threads...\n')
                            break
                        results_map = read_plc_dict(plc, machine_num) # continuous PLC read
                        if (results_map[config_info['tags']['Reset']][1] == True):
                            print_yellow(f'({machine_num}) (StartProgram Check) Reset Detected! Setting back to Stage 0...')
                            self.current_stage = 0
                            print_yellow(f'({machine_num}) Flushing PLC(Result) tag data...\n')
                            write_plc_flush(plc,machine_num)
                            write_plc_single(plc, machine_num, 'Reset', False)
                            write_plc_single(plc, machine_num, 'Faulted', False)
                            write_plc_single(plc, machine_num, 'FaultStatus', 0)
                            write_plc_single(plc, machine_num, 'PhoenixFltCode', 0)
                            write_plc_single(plc, machine_num, 'KeyenceFltCode', 0)
                            # kill_threads.set()
                            current_thread = threading.current_thread()
                            if current_thread in reset_events:
                                reset_events[current_thread].set()
                        time.sleep(.050) # 5ms pause between reads
                    #Update part type and part program if needed
                    results_map = read_plc_dict(plc, machine_num)
                    print_green(f'({machine_num}) StartProgram went high!\n')
                    start_timer_Trigger_to_Busy = datetime.datetime.now()
                    #Actual Keyence Trigger (T1) here***
                    trigger_keyence(sock, machine_num)
                    write_plc_single(plc, machine_num, 'Busy', True)
                    print_green(f'({machine_num}) Keyence Triggered!\n')
                    start_timer_T1_to_EndProgram = datetime.datetime.now()
                    time_diff = (start_timer_T1_to_EndProgram - start_timer_Trigger_to_Busy)
                    execution_time = time_diff.total_seconds() * 1000
                    if(execution_time > 3000):
                        print_red(f'({machine_num}) Trigger Keyence timeout fault (longer than 3 seconds)! PhoenixFltCode : 2')
                        write_plc_single(plc, machine_num, 'PhoenixFltCode', 2)
                        write_plc_single(plc, machine_num, 'FaultStatus', 2)
                        write_plc_single(plc, machine_num, 'Faulted', True)
                    write_plc_single(plc, machine_num, 'Ready', False)
                    #BUSY BEFORE KEYENCE TRIGGER TEST ***
                    monitor_end_scan(plc, machine_num, sock) # ends Keyence with EndScan
                    end_timer_T1_to_EndScan = datetime.datetime.now()
                    diff_timer_T1_to_EndScan = (end_timer_T1_to_EndScan - start_timer_T1_to_EndProgram)
                    execution_time = diff_timer_T1_to_EndScan.total_seconds() * 1000
                    scan_duration = execution_time #for logging in .csv
                    write_plc_single(plc, machine_num, 'Busy', False)
                    keyence_result_check_start = datetime.datetime.now()
                    monitor_keyence_not_running(sock, machine_num) # verify Keyence has processed results and written out FTP files
                    keyence_result_check_end = datetime.datetime.now()
                    time_diff = (keyence_result_check_end - keyence_result_check_start)
                    execution_time = time_diff.total_seconds() * 1000
                    if(execution_time > 3000):
                        print_red(f'({machine_num}) TIMEOUT ERROR: Keyence not running (Execution time exceeded 3 seconds)\n\tPhoenixFltCode : 3\n')
                        write_plc_single(plc, machine_num, 'PhoenixFltCode', 3)
                        write_plc_single(plc, machine_num, 'FaultStatus', 3)
                        write_plc_single(plc, machine_num, 'Faulted', True)
                    keyence_results = []
                    keyence_check_pass(machine_num,sock,plc) # Get Check/Pass data from Keyence Keyence Functions
                    keyence_results = keyence_results_to_PLC(sock, plc, machine_num)
                    create_csv(machine_num, results_map, keyence_results, keyence_string, scan_duration,part_type,part_program) # results to .csv, PER SCAN
                    #check if we're ready to write out a parts results, PER PART
                    write_part_results(machine_num, results_map, keyence_results, keyence_string) #appends to result string, writes out file and clears string if on final scan of part
                    # Setting Chinmay's Keyence tag high
                    keyence_msg = 'MW,#PhoenixControlContinue,1\r\n'
                    sock.sendall(keyence_msg.encode())
                    print_blue(f'({machine_num}) Sent \'#PhoenixControlContinue,1\' to Keyence!')
                    _ = sock.recv(32) #obligatory Keyence read to keep buffer clear
                    print_green(f'({machine_num})Stage 1 Complete!\n')
                    self.current_stage += 1
                #Final Stage, reset to Stage 0 once PLC(END_PROGRAM) and PHOENIX(DONE) have been set low
                elif(self.current_stage == 2):
                    write_plc_single(plc, machine_num, 'Done', True)
                    print_yellow(f'({machine_num}) Stage 2 : Listening for PLC(ENDPROGRAM) high to reset back to Stage 0\n')
                    while(results_map[config_info['tags']['EndProgram']][1] != True):
                        if (kill_threads.is_set() or reset_events[threading.current_thread()].is_set()):
                            print_red(f'({machine_num}) kill_threads detected while waiting for ENDPROGRAM! Restarting threads...\n')
                            break
                        results_map = read_plc_dict(plc, machine_num) # continuous PLC read
                        if (results_map[config_info['tags']['Reset']][1] == True):
                            print_yellow(f'({machine_num}) (StartProgram Check) Reset Detected! Setting back to Stage 0...\n')
                            self.current_stage = 0
                            print_yellow(f'({machine_num}) Flushing PLC Fault Tags...\n')
                            write_plc_flush(plc,machine_num)
                            write_plc_single(plc, machine_num, 'Reset', False)
                            write_plc_single(plc, machine_num, 'Faulted', False)
                            write_plc_single(plc, machine_num, 'FaultStatus', 0)
                            write_plc_single(plc, machine_num, 'PhoenixFltCode', 0)
                            write_plc_single(plc, machine_num, 'KeyenceFltCode', 0)
                            # kill_threads.set()
                            current_thread = threading.current_thread()
                            if current_thread in reset_events:
                                reset_events[current_thread].set()
                        time.sleep(.050) # 5ms pause between reads
                    print_yellow(f'({machine_num}) PLC(END_PROGRAM) is high. Dropping PHOENIX(DONE) low\n')
                    write_plc_single(plc, machine_num, 'Done', False)
                    write_plc_single(plc, machine_num, 'Pass', False)
                    write_plc_single(plc, machine_num, 'Busy', False)
                    write_plc_single(plc, machine_num, 'Fail', False)
                    write_plc_single(plc, machine_num, 'Aborted', False)
                    check_pass_flush(plc,machine_num) #Flush Check/Pass data before sending data to PLC again
                    print_yellow(f'({machine_num}) Flushing PLC(Result) tag data...\n')
                    write_plc_flush(plc,machine_num) # defaults all .I Phoenix tags at start of cycle
                    write_plc_single(plc, machine_num, 'Ready', True)
                    self.current_stage = 0 # cycle complete, reset to stage 0
                if (abs(datetime.datetime.now() - connection_timer).total_seconds() > 86400):
                    print_red(f'({machine_num}) Connection reset detected! restarting threads...\n')
                    connection_timer = datetime.datetime.now()
                    # kill_threads.set()
                    current_thread = threading.current_thread()
                    if current_thread in reset_events:
                                reset_events[current_thread].set()
                if (kill_threads.is_set() or reset_events[current_thread].is_set()):
                    print_red(f'({machine_num}) kill_threads detected at cycle end! Restarting threads...\n')
                    break # Kill thread if global is set True for any reason
                time.sleep(.005) #artificial loop timer
#END class Cycler
#sets PLC(Heartbeat) high every second to verify we're still running and communicating
def heartbeat(machine_num, reset_event):
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
#START main()
def main():
    config_info = read_config()  # Read configuration information
    cycle_threads = []  # Store created cycle threads
    heartbeat_threads = []  # Store created heartbeat threads
    reset_events = {}  # Store reset events for each cycle thread
    # Loop through machines in config
    for machine_num in list(config_info['mnKeyenceIP'].keys()):
        ip = config_info['mnKeyenceIP'][machine_num]
        cycle_object = cycler(machine_num, ip)
        reset_events[cycle_object] = threading.Event()
        # Create and start cycle thread
        cycle_thread = threading.Thread(target=cycle_object.cycle, args=[machine_num, ip, reset_events], name=f"machine_{machine_num}")
        cycle_thread.start()
        cycle_threads.append(cycle_thread)
        # Create and start heartbeat thread
        heartbeat_thread = threading.Thread(target=heartbeat, args=[machine_num, reset_events], name=f"{machine_num}_heartBeat")
        heartbeat_thread.start()
        # Store the heartbeat thread in the list
        heartbeat_threads.append(heartbeat_thread)
    event.set()  # Signal threads to start
    # Loop through cycle threads and reset them
    for cycle_thread, heartbeat_thread in zip(cycle_threads, heartbeat_threads):
        cycle_thread.join()
        reset_event = reset_events[cycle_thread]
        reset_event.set()  # Signal cycle thread to reset
        heartbeat_thread.join()
        # Create a new cycle thread instance and start it
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
